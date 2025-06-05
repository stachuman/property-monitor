#!/usr/bin/env python3
"""
Property Scraper Service - Fixed version with improved scheduler and JSON serialization
"""

import time
import json
import requests
import schedule
import logging
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass

from config import get_config
from database import DatabaseManager
from models import ScrapingConfig, ApiResponse

logger = logging.getLogger(__name__)


@dataclass
class ScrapingResult:
    """Result of a scraping operation"""
    category: str
    new_properties: int
    updated_properties: int
    total_scraped: int
    errors: List[str]
    duration_seconds: float
    timestamp: datetime

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary with JSON-serializable types"""
        return {
            'category': self.category,
            'new_properties': self.new_properties,
            'updated_properties': self.updated_properties,
            'total_scraped': self.total_scraped,
            'errors': self.errors,
            'duration_seconds': self.duration_seconds,
            'timestamp': self.timestamp.isoformat()
        }


class PropertyScraper:
    """Enhanced property scraper with category control"""

    def __init__(self, db_manager: DatabaseManager):
        self.config = get_config()
        self.db = db_manager
        self.session = requests.Session()
        self.session.headers.update(self.config.scraping_api.headers)
        self._setup_session()

    def _setup_session(self):
        """Setup requests session with retries"""
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry

        retry_strategy = Retry(
            total=self.config.scraping_api.retry_attempts,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )

        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def scrape_category(self, category_config: ScrapingConfig) -> ScrapingResult:
        """Scrape specific category with configuration"""
        start_time = time.time()
        errors = []
        all_properties = []

        logger.info(f"Starting scrape for category: {category_config.category}")

        try:
            # Get properties for this category
            properties = self._scrape_category_data(
                category_config.category,
                max_pages=category_config.max_pages,
                delay_seconds=category_config.delay_seconds
            )

            all_properties.extend(properties)

            # Save to database
            new_count, updated_count = self.db.save_properties(properties)

            # Update last run time
            category_config.last_run = datetime.now()
            self.db.update_scraping_config(category_config.category, category_config)

            duration = time.time() - start_time

            result = ScrapingResult(
                category=category_config.category,
                new_properties=new_count,
                updated_properties=updated_count,
                total_scraped=len(properties),
                errors=errors,
                duration_seconds=duration,
                timestamp=datetime.now()
            )

            logger.info(f"Scraping completed for {category_config.category}: "
                        f"{new_count} new, {updated_count} updated in {duration:.1f}s")

            return result

        except Exception as e:
            error_msg = f"Failed to scrape {category_config.category}: {str(e)}"
            logger.error(error_msg)
            errors.append(error_msg)

            duration = time.time() - start_time
            return ScrapingResult(
                category=category_config.category,
                new_properties=0,
                updated_properties=0,
                total_scraped=0,
                errors=errors,
                duration_seconds=duration,
                timestamp=datetime.now()
            )

    def _scrape_category_data(self, category: str, max_pages: Optional[int] = None, delay_seconds: float = 2.0) -> List[
        Dict]:
        """Scrape data for specific category"""
        properties = []
        offset = 0
        limit = 30
        page_count = 0

        while True:
            # Check page limit
            if max_pages and page_count >= max_pages:
                logger.info(f"Reached max pages limit ({max_pages}) for {category}")
                break

            payload = self._build_payload(category, limit, offset)

            try:
                response = self.session.post(
                    self.config.scraping_api.api_url,
                    json=payload,
                    timeout=self.config.scraping_api.timeout
                )
                response.raise_for_status()
                data = response.json()

                items = data.get('items', [])
                if not items:
                    logger.info(f"No more items found for {category} at offset {offset}")
                    break

                properties.extend(items)
                logger.debug(f"Scraped {len(items)} items for {category} (page {page_count + 1})")

                # Check if we've got all items
                if len(items) < limit:
                    break

                offset += limit
                page_count += 1

                # Rate limiting
                if delay_seconds > 0:
                    time.sleep(delay_seconds)

            except requests.exceptions.RequestException as e:
                logger.error(f"Request failed for {category} at offset {offset}: {e}")
                break
            except Exception as e:
                logger.error(f"Unexpected error scraping {category}: {e}")
                break

        logger.info(f"Scraped {len(properties)} total properties for {category}")
        return properties

    def _build_payload(self, sub_category: str, limit: int, offset: int) -> Dict:
        """Build API payload for category"""
        payload = {
            "aggregations": [] if sub_category == "inne" else [
                "params.LAND_LOTTYPE", "params.LAND_AREAHA", "params.LAND_MEDIA",
                "params.LAND_FORMOFOWNERSHIP", "params.LAND_SHARESIZE", "params.LAND_AREA"
            ],
            "termFilters": [
                {"field": "mainCategory", "value": ["Nieruchomości"]},
                {"field": "subCategory", "value": [sub_category]}
            ],
            "numberFilters": [],
            "dateRangeFilters": [],
            "fullTextFilters": [],
            "limit": limit,
            "orderBy": "DESC",
            "orderByField": "startAuctionAt",
            "offset": offset
        }
        return payload

    def scrape_all_enabled_categories(self) -> List[ScrapingResult]:
        """Scrape all enabled categories"""
        configs = self.db.get_scraping_configs()
        enabled_configs = [c for c in configs if c.enabled]

        if not enabled_configs:
            logger.warning("No enabled scraping categories found")
            return []

        results = []
        for config in sorted(enabled_configs, key=lambda x: x.priority):
            try:
                result = self.scrape_category(config)
                results.append(result)

                # Log health event with proper JSON serialization
                self.db.log_health_event(
                    component="scraper",
                    status="success" if not result.errors else "warning",
                    message=f"Scraped {config.category}: {result.new_properties} new, {result.updated_properties} updated",
                    data=result.to_dict()  # Use the serializable version
                )

            except Exception as e:
                logger.error(f"Failed to scrape category {config.category}: {e}")
                self.db.log_health_event(
                    component="scraper",
                    status="error",
                    message=f"Failed to scrape {config.category}: {str(e)}"
                )

        return results


class ScrapingService:
    """Main scraping service with improved scheduling"""

    def __init__(self):
        self.config = get_config()
        self.db = DatabaseManager()
        self.scraper = PropertyScraper(self.db)
        self.running = False
        self._scheduler_thread = None
        self._stop_event = threading.Event()

    def start_service(self):
        """Start the scraping service with improved scheduler"""
        if self.running:
            logger.warning("Scraping service is already running")
            return

        logger.info("Starting Property Scraping Service")
        self.running = True
        self._stop_event.clear()

        # Clear any existing scheduled jobs
        schedule.clear()

        # Schedule daily scraping
        schedule.every().day.at(self.config.service.scraping_time).do(self._daily_scrape_job)
        logger.info(f"Scheduled daily scraping at {self.config.service.scraping_time}")

        # Schedule cleanup
        schedule.every().day.at(self.config.service.cleanup_time).do(self._cleanup_job)
        logger.info(f"Scheduled daily cleanup at {self.config.service.cleanup_time}")

        # Start scheduler thread with improved error handling
        self._scheduler_thread = threading.Thread(target=self._run_scheduler, daemon=True, name="ScrapingScheduler")
        self._scheduler_thread.start()

        logger.info("Scraping service started successfully")

    def stop_service(self):
        """Stop the scraping service"""
        logger.info("Stopping scraping service...")
        self.running = False
        self._stop_event.set()

        # Clear scheduled jobs
        schedule.clear()

        if self._scheduler_thread and self._scheduler_thread.is_alive():
            self._scheduler_thread.join(timeout=10)
            if self._scheduler_thread.is_alive():
                logger.warning("Scheduler thread did not stop gracefully")

        logger.info("Scraping service stopped")

    def _run_scheduler(self):
        """Run the scheduler loop with improved error handling"""
        logger.info("Scheduler thread started")
        
        while self.running and not self._stop_event.is_set():
            try:
                # Check for pending jobs
                pending_jobs = schedule.get_jobs()
                if pending_jobs:
                    logger.debug(f"Scheduler running with {len(pending_jobs)} jobs scheduled")
                    schedule.run_pending()
                else:
                    logger.warning("No scheduled jobs found!")
                    # Re-schedule if jobs are missing
                    self._reschedule_jobs()

                # Update service status in database every few minutes
                if hasattr(self, '_last_status_update'):
                    if time.time() - self._last_status_update > 300:  # Every 5 minutes
                        self._update_service_status()
                else:
                    self._update_service_status()

                # Wait for 60 seconds or until stop event
                if self._stop_event.wait(60):
                    break

            except Exception as e:
                logger.error(f"Scheduler error: {e}")
                # Continue running despite errors
                if self._stop_event.wait(60):
                    break

        logger.info("Scheduler thread stopped")

    def _update_service_status(self):
        """Update service status in database"""
        try:
            status = self.get_scraping_status()
            self.db.update_service_status('scraping', status)
            self._last_status_update = time.time()
            logger.debug("Updated scraping service status in database")
        except Exception as e:
            logger.error(f"Failed to update service status: {e}")

    def _reschedule_jobs(self):
        """Re-schedule jobs if they're missing"""
        try:
            schedule.clear()
            schedule.every().day.at(self.config.service.scraping_time).do(self._daily_scrape_job)
            schedule.every().day.at(self.config.service.cleanup_time).do(self._cleanup_job)
            logger.info("Jobs rescheduled successfully")
        except Exception as e:
            logger.error(f"Failed to reschedule jobs: {e}")

    def _daily_scrape_job(self):
        """Daily scraping job with improved error handling"""
        try:
            logger.info("Starting daily scrape job")
            
            # Check if scraping is still enabled
            configs = self.db.get_scraping_configs()
            enabled_configs = [c for c in configs if c.enabled]
            
            if not enabled_configs:
                logger.warning("No enabled scraping categories found, skipping daily scrape")
                return

            results = self.scraper.scrape_all_enabled_categories()

            # Log summary
            total_new = sum(r.new_properties for r in results)
            total_updated = sum(r.updated_properties for r in results)
            total_errors = sum(len(r.errors) for r in results)

            logger.info(f"Daily scrape completed: {total_new} new, {total_updated} updated, {total_errors} errors")

            # Create serializable data for health event
            results_data = {
                "total_new": total_new,
                "total_updated": total_updated,
                "total_errors": total_errors,
                "categories_processed": len(results),
                "results": [r.to_dict() for r in results]
            }

            self.db.log_health_event(
                component="scraper",
                status="success" if total_errors == 0 else "warning",
                message=f"Daily scrape: {total_new} new, {total_updated} updated properties",
                data=results_data
            )

        except Exception as e:
            logger.error(f"Daily scrape failed: {e}")
            self.db.log_health_event(
                component="scraper",
                status="error",
                message=f"Daily scrape failed: {str(e)}"
            )

    def _cleanup_job(self):
        """Daily cleanup job"""
        try:
            logger.info("Starting cleanup job")
            deleted_count = self.db.cleanup_old_auctions(grace_days=2)

            logger.info(f"Cleanup completed: {deleted_count} old auctions removed")
            self.db.log_health_event(
                component="cleanup",
                status="success",
                message=f"Cleanup: {deleted_count} old auctions removed",
                data={"deleted_count": deleted_count}
            )

        except Exception as e:
            logger.error(f"Cleanup job failed: {e}")
            self.db.log_health_event(
                component="cleanup",
                status="error",
                message=f"Cleanup failed: {str(e)}"
            )

    def manual_scrape(self, category: Optional[str] = None) -> List[ScrapingResult]:
        """Manually trigger scraping"""
        if category:
            # Scrape specific category
            configs = self.db.get_scraping_configs()
            category_config = next((c for c in configs if c.category == category), None)

            if not category_config:
                logger.error(f"Category '{category}' not found")
                return []

            if not category_config.enabled:
                logger.warning(f"Category '{category}' is disabled")

            logger.info(f"Manual scrape triggered for category: {category}")
            result = self.scraper.scrape_category(category_config)
            return [result]
        else:
            # Scrape all enabled categories
            logger.info("Manual scrape triggered for all enabled categories")
            return self.scraper.scrape_all_enabled_categories()

    def get_scraping_status(self) -> Dict[str, Any]:
        """Get current scraping status"""
        configs = self.db.get_scraping_configs()

        # Calculate next scheduled run time based on configuration
        next_run = None
        if self.running and self.config.service.scraping_time:
            next_run = self._calculate_next_scrape_time()

        # Get scheduler information
        jobs = schedule.get_jobs() if hasattr(self, '_scheduler_thread') else []
        scheduler_active = (hasattr(self, '_scheduler_thread') and 
                          self._scheduler_thread is not None and 
                          self._scheduler_thread.is_alive())

        status = {
            "service_running": self.running,
            "scheduler_active": scheduler_active,
            "scheduled_jobs_count": len(jobs),
            "next_scheduled_scrape": next_run,
            "daily_scrape_time": self.config.service.scraping_time,
            "categories": []
        }

        for config in configs:
            category_status = {
                "category": config.category,
                "enabled": config.enabled,
                "max_pages": config.max_pages,
                "delay_seconds": config.delay_seconds,
                "priority": config.priority,
                "last_run": config.last_run.isoformat() if config.last_run else None
            }
            status["categories"].append(category_status)

        return status

    def _calculate_next_scrape_time(self) -> Optional[str]:
        """Calculate next scheduled scrape time based on configuration"""
        try:
            from datetime import datetime, timedelta
            import time
            
            scrape_time = self.config.service.scraping_time  # e.g., "06:00"
            if not scrape_time:
                return None
                
            # Parse the time
            hour, minute = map(int, scrape_time.split(':'))
            
            # Get current time
            now = datetime.now()
            
            # Create next scheduled time for today
            next_scrape = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            
            # If the time has already passed today, schedule for tomorrow
            if next_scrape <= now:
                next_scrape += timedelta(days=1)
                
            return next_scrape.isoformat()
            
        except Exception as e:
            logger.error(f"Failed to calculate next scrape time: {e}")
            return None


# CLI functions for manual operations
def run_manual_scrape(category: Optional[str] = None):
    """Run manual scrape from CLI"""
    service = ScrapingService()
    results = service.manual_scrape(category)

    for result in results:
        print(f"\nCategory: {result.category}")
        print(f"  New properties: {result.new_properties}")
        print(f"  Updated properties: {result.updated_properties}")
        print(f"  Total scraped: {result.total_scraped}")
        print(f"  Duration: {result.duration_seconds:.1f}s")
        if result.errors:
            print(f"  Errors: {len(result.errors)}")
            for error in result.errors:
                print(f"    - {error}")


def main():
    """Main entry point for scraping service"""
    import sys
    from config import setup_logging

    setup_logging()

    if len(sys.argv) > 1:
        command = sys.argv[1]

        if command == "scrape":
            category = sys.argv[2] if len(sys.argv) > 2 else None
            run_manual_scrape(category)
        elif command == "status":
            service = ScrapingService()
            status = service.get_scraping_status()
            print(json.dumps(status, indent=2))
        elif command == "daemon":
            # Run as daemon service
            service = ScrapingService()
            try:
                service.start_service()
                logger.info("Scraping service is running. Press Ctrl+C to stop.")
                # Keep running
                while service.running:
                    time.sleep(1)
            except KeyboardInterrupt:
                logger.info("Received interrupt signal")
            finally:
                service.stop_service()
        else:
            print("Usage: python property_scraper_service.py [scrape|status|daemon] [category]")
    else:
        # Default: run manual scrape of all categories
        run_manual_scrape()


if __name__ == "__main__":
    main()
