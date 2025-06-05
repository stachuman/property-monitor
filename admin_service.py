#!/usr/bin/env python3
"""
Admin Service - Web interface for system administration
"""

import json
import logging
import threading
from datetime import datetime
from typing import Dict, List, Optional, Any

from flask import Flask, render_template, jsonify, request, redirect, url_for, flash

from config import get_config
from database import DatabaseManager
from models import ScrapingConfig, GeocodingConfig, ApiResponse
from property_scraper_service import ScrapingService
from geocoding_service import GeocodingService
from datetime import datetime, timedelta
import schedule

logger = logging.getLogger(__name__)


class AdminService:
    """Admin web interface service"""

    def __init__(self):
        self.config = get_config()
        self.db = DatabaseManager()
        self.scraping_service = ScrapingService()
        self.geocoding_service = GeocodingService()
        self.app = None
        self._setup_flask_app()

    def _setup_flask_app(self):
        """Setup Flask application with admin routes"""
        self.app = Flask(__name__, template_folder='admin_templates')
        self.app.secret_key = self.config.web_server.secret_key

        # Admin dashboard routes
        self.app.add_url_rule('/', 'dashboard', self.dashboard)
        self.app.add_url_rule('/scraping', 'scraping', self.scraping_control)
        self.app.add_url_rule('/geocoding', 'geocoding', self.geocoding_control)
        self.app.add_url_rule('/failed-geocoding', 'failed_geocoding', self.failed_geocoding)
        self.app.add_url_rule('/system', 'system_status', self.system_status)

        # API routes
        self.app.add_url_rule('/api/health', 'api_health', self.api_health)
        self.app.add_url_rule('/api/scraping/status', 'api_scraping_status', self.api_scraping_status)
        self.app.add_url_rule('/api/scraping/trigger', 'api_scraping_trigger', self.api_scraping_trigger,
                              methods=['POST'])
        self.app.add_url_rule('/api/scraping/config', 'api_scraping_config', self.api_scraping_config,
                              methods=['GET', 'POST'])

        self.app.add_url_rule('/api/geocoding/status', 'api_geocoding_status', self.api_geocoding_status)
        self.app.add_url_rule('/api/geocoding/trigger', 'api_geocoding_trigger', self.api_geocoding_trigger,
                              methods=['POST'])
        self.app.add_url_rule('/api/geocoding/config', 'api_geocoding_config', self.api_geocoding_config,
                              methods=['GET', 'POST'])
        self.app.add_url_rule('/api/geocoding/failed', 'api_geocoding_failed', self.api_geocoding_failed)
        self.app.add_url_rule('/api/geocoding/fix', 'api_geocoding_fix', self.api_geocoding_fix, methods=['POST'])
        self.app.add_url_rule('/api/geocoding/retry', 'api_geocoding_retry', self.api_geocoding_retry, methods=['POST'])

        self.app.add_url_rule('/api/stats/categories', 'api_stats_categories', self.api_stats_categories)
        self.app.add_url_rule('/api/stats/overview', 'api_stats_overview', self.api_stats_overview)

    # Dashboard routes
    def dashboard(self):
        """Main admin dashboard"""
        try:
            health = self.db.get_system_health()
            category_stats = self.db.get_category_stats()
		
            # POPRAWIONE: Sprawdź rzeczywisty status usług
            scraping_status = self._get_real_scraping_status()
            geocoding_status = self._get_real_geocoding_status()

            return render_template('admin_dashboard.html',
                health=health,
                category_stats=category_stats,
                scraping_status=scraping_status,
                geocoding_status=geocoding_status)
        except Exception as e:
            logger.error(f"Dashboard error: {e}")
            return f"Dashboard error: {e}", 500

    def _get_real_scraping_status(self):
      """Get real scraping service status by checking database and scheduler"""
      try:
        # Sprawdź status z bazy danych
        db_status = self.db.get_service_status('scraping')
        
        # Sprawdź czy są zaplanowane joby
        import schedule
        scraping_jobs = [job for job in schedule.get_jobs() if 'scraping' in str(job)]
        
        # Sprawdź ostatnią aktywność
        configs = self.db.get_scraping_configs()
        recent_activity = any(
           config.last_run and 
            (datetime.now() - config.last_run).total_seconds() < 3600  # ostatnia godzina
            for config in configs
        )
        
        # Określ czy usługa działa
        service_running = bool(db_status or scraping_jobs or recent_activity)
        
        # Zwróć status w formacie kompatybilnym z template
        status = {
            "service_running": service_running,
            "scheduler_active": len(scraping_jobs) > 0,
            "scheduled_jobs_count": len(scraping_jobs),
            "categories": [
                {
                    "category": config.category,
                    "enabled": config.enabled,
                    "max_pages": config.max_pages,
                    "last_run": config.last_run.isoformat() if config.last_run else None
                }
                for config in configs
            ],
            "next_scheduled_scrape": self._get_next_scheduled_time(),
            "daily_scrape_time": self.config.service.scraping_time
        }
        
        return status
        
      except Exception as e:
        logger.error(f"Error getting scraping status: {e}")
        return {
            "service_running": False,
            "scheduler_active": False,
            "scheduled_jobs_count": 0,
            "categories": [],
            "next_scheduled_scrape": None,
            "daily_scrape_time": "Unknown"
        }

    def _get_real_geocoding_status(self):
      """Get real geocoding service status by checking database and activity"""
      try:
        # Sprawdź status z bazy danych
        db_status = self.db.get_service_status('geocoding')
        
        # Sprawdź ostatnią aktywność geokodowania
        health = self.db.get_system_health()
        recent_geocoding = (
            health.last_geocoding and 
            (datetime.now() - health.last_geocoding).total_seconds() < 7200  # ostatnie 2 godziny
        )
        
        # Sprawdź czy są zaplanowane joby
        import schedule
        geocoding_jobs = [job for job in schedule.get_jobs() if 'geocoding' in str(job)]
        
        # Określ czy usługa działa
        service_running = bool(db_status or recent_geocoding or geocoding_jobs)
        
        # Pobierz konfigurację
        geocoding_config = self.db.get_geocoding_config()
        
        status = {
            "service_running": service_running,
            "enabled": geocoding_config.enabled,
            "batch_size": geocoding_config.batch_size,
            "delay_seconds": geocoding_config.delay_seconds,
            "max_attempts": geocoding_config.max_attempts,
            "retry_failed_after_hours": geocoding_config.retry_failed_after_hours,
            "total_properties": health.total_properties,
            "geocoded_properties": health.geocoded_properties,
            "failed_geocoding": health.failed_geocoding,
            "pending_geocoding": health.pending_geocoding,
            "geocoding_percentage": health.geocoding_percentage,
            "last_geocoding": health.last_geocoding.isoformat() if health.last_geocoding else None,
            "next_scheduled_run": self._get_next_geocoding_time()
        }
        
        return status
        
      except Exception as e:
        logger.error(f"Error getting geocoding status: {e}")
        return {
            "service_running": False,
            "enabled": False,
            "batch_size": 50,
            "delay_seconds": 1.1,
            "max_attempts": 3,
            "total_properties": 0,
            "geocoded_properties": 0,
            "failed_geocoding": 0,
            "pending_geocoding": 0,
            "geocoding_percentage": 0,
            "last_geocoding": None,
            "next_scheduled_run": None
        }

    def _get_next_scheduled_time(self):
      """Get next scheduled scraping time"""
      try:
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

    def _get_next_geocoding_time(self):
      """Get next scheduled geocoding time"""
      try:
        interval = self.config.service.geocoding_interval_minutes
        if interval <= 0:
            return None
            
        # Oszacuj następny czas na podstawie interwału
        next_run = datetime.now() + timedelta(minutes=interval)
        return next_run.isoformat()
        
      except Exception as e:
        logger.error(f"Failed to calculate next geocoding time: {e}")
        return None

    def scraping_control(self):
        """Scraping control page"""
        try:
            configs = self.db.get_scraping_configs()
            status = self.scraping_service.get_scraping_status()
            category_stats = self.db.get_category_stats()

            return render_template('admin_scraping.html',
                                   configs=configs,
                                   status=status,
                                   category_stats=category_stats)
        except Exception as e:
            logger.error(f"Scraping control error: {e}")
            return f"Scraping control error: {e}", 500

    def geocoding_control(self):
        """Geocoding control page"""
        try:
            config = self.db.get_geocoding_config()
            status = self.geocoding_service.get_geocoding_status()

            return render_template('admin_geocoding.html',
                                   config=config,
                                   status=status)
        except Exception as e:
            logger.error(f"Geocoding control error: {e}")
            return f"Geocoding control error: {e}", 500

    def failed_geocoding(self):
        """Failed geocoding review page"""
        try:
            failed_entries = self.geocoding_service.get_failed_geocoding_entries(100)

            return render_template('admin_failed_geocoding.html',
                                   failed_entries=failed_entries)
        except Exception as e:
            logger.error(f"Failed geocoding error: {e}")
            return f"Failed geocoding error: {e}", 500

    def system_status(self):
        """System status page"""
        try:
            health = self.db.get_system_health()
            config = self.config

            # Get recent health events
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT timestamp, component, status, message
                    FROM system_health 
                    ORDER BY timestamp DESC 
                    LIMIT 50
                ''')
                health_events = cursor.fetchall()

            return render_template('admin_system.html',
                                   health=health,
                                   config=config,
                                   health_events=health_events,
                                   max=max,  # Pass max function to template
                                   min=min,  # Pass min function to template
                                   len=len,  # Pass len function to template
                                   round=round)  # Pass round function to template
        except Exception as e:
            logger.error(f"System status error: {e}")
            return f"System status error: {e}", 500

    # API routes
    def api_health(self):
        """System health API"""
        try:
            health = self.db.get_system_health()
            return jsonify(health.to_dict())
        except Exception as e:
            logger.error(f"Health API error: {e}")
            return jsonify({"error": str(e)}), 500

    def api_scraping_status(self):
        """Scraping status API"""
        try:
            status = self.scraping_service.get_scraping_status()
            return jsonify(status)
        except Exception as e:
            logger.error(f"Scraping status API error: {e}")
            return jsonify({"error": str(e)}), 500

    def api_scraping_trigger(self):
        """Trigger scraping API"""
        try:
            data = request.get_json() or {}
            category = data.get('category')

            # Run scraping in background thread
            def run_scraping():
                try:
                    results = self.scraping_service.manual_scrape(category)
                    logger.info(f"Manual scraping completed: {len(results)} categories processed")
                except Exception as e:
                    logger.error(f"Manual scraping failed: {e}")

            threading.Thread(target=run_scraping, daemon=True).start()

            response = ApiResponse(
                success=True,
                message=f"Scraping started for {'all categories' if not category else category}"
            )
            return jsonify(response.to_dict())

        except Exception as e:
            logger.error(f"Scraping trigger API error: {e}")
            response = ApiResponse(success=False, message="Failed to trigger scraping", error=str(e))
            return jsonify(response.to_dict()), 500

    def api_scraping_config(self):
        """Scraping configuration API"""
        if request.method == 'GET':
            try:
                configs = self.db.get_scraping_configs()
                return jsonify([config.to_dict() for config in configs])
            except Exception as e:
                logger.error(f"Get scraping config error: {e}")
                return jsonify({"error": str(e)}), 500

        elif request.method == 'POST':
            try:
                data = request.get_json()
                category = data.get('category')

                if not category:
                    return jsonify({"error": "Category is required"}), 400

                config = ScrapingConfig(
                    category=category,
                    enabled=data.get('enabled', True),
                    max_pages=data.get('max_pages'),
                    delay_seconds=data.get('delay_seconds', 2.0),
                    priority=data.get('priority', 1)
                )

                success = self.db.update_scraping_config(category, config)

                if success:
                    response = ApiResponse(success=True, message=f"Configuration updated for {category}")
                else:
                    response = ApiResponse(success=False, message=f"Failed to update configuration for {category}")

                return jsonify(response.to_dict())

            except Exception as e:
                logger.error(f"Update scraping config error: {e}")
                response = ApiResponse(success=False, message="Failed to update configuration", error=str(e))
                return jsonify(response.to_dict()), 500

    def api_geocoding_status(self):
        """Geocoding status API"""
        try:
            status = self.geocoding_service.get_geocoding_status()
            return jsonify(status)
        except Exception as e:
            logger.error(f"Geocoding status API error: {e}")
            return jsonify({"error": str(e)}), 500

    def api_geocoding_trigger(self):
        """Trigger geocoding API"""
        try:
            data = request.get_json() or {}
            batch_size = data.get('batch_size')

            # Run geocoding in background thread
            def run_geocoding():
                try:
                    result = self.geocoding_service.manual_geocoding(batch_size)
                    logger.info(f"Manual geocoding completed: {result.successful} successful, {result.failed} failed")
                except Exception as e:
                    logger.error(f"Manual geocoding failed: {e}")

            threading.Thread(target=run_geocoding, daemon=True).start()

            response = ApiResponse(
                success=True,
                message=f"Geocoding started with batch size: {batch_size or 'default'}"
            )
            return jsonify(response.to_dict())

        except Exception as e:
            logger.error(f"Geocoding trigger API error: {e}")
            response = ApiResponse(success=False, message="Failed to trigger geocoding", error=str(e))
            return jsonify(response.to_dict()), 500

    def api_geocoding_config(self):
        """Geocoding configuration API"""
        if request.method == 'GET':
            try:
                config = self.db.get_geocoding_config()
                return jsonify(config.to_dict())
            except Exception as e:
                logger.error(f"Get geocoding config error: {e}")
                return jsonify({"error": str(e)}), 500

        elif request.method == 'POST':
            try:
                data = request.get_json()

                config = GeocodingConfig(
                    batch_size=data.get('batch_size', 50),
                    delay_seconds=data.get('delay_seconds', 1.1),
                    max_attempts=data.get('max_attempts', 3),
                    retry_failed_after_hours=data.get('retry_failed_after_hours', 24),
                    enabled=data.get('enabled', True)
                )

                success = self.geocoding_service.update_geocoding_config(config)

                if success:
                    response = ApiResponse(success=True, message="Geocoding configuration updated")
                else:
                    response = ApiResponse(success=False, message="Failed to update geocoding configuration")

                return jsonify(response.to_dict())

            except Exception as e:
                logger.error(f"Update geocoding config error: {e}")
                response = ApiResponse(success=False, message="Failed to update configuration", error=str(e))
                return jsonify(response.to_dict()), 500

    def api_geocoding_failed(self):
        """Failed geocoding entries API"""
        try:
            limit = request.args.get('limit', 100, type=int)
            failed_entries = self.geocoding_service.get_failed_geocoding_entries(limit)
            return jsonify([entry.to_dict() for entry in failed_entries])
        except Exception as e:
            logger.error(f"Failed geocoding API error: {e}")
            return jsonify({"error": str(e)}), 500

    def api_geocoding_fix(self):
        """Manual geocoding fix API"""
        try:
            data = request.get_json()
            property_id = data.get('property_id')
            latitude = data.get('latitude')
            longitude = data.get('longitude')

            if not all([property_id, latitude, longitude]):
                return jsonify({"error": "property_id, latitude, and longitude are required"}), 400

            success = self.geocoding_service.manual_geocoding_fix(property_id, latitude, longitude)

            if success:
                response = ApiResponse(success=True, message=f"Geocoding fixed for property {property_id}")
            else:
                response = ApiResponse(success=False, message=f"Failed to fix geocoding for property {property_id}")

            return jsonify(response.to_dict())

        except Exception as e:
            logger.error(f"Geocoding fix API error: {e}")
            response = ApiResponse(success=False, message="Failed to fix geocoding", error=str(e))
            return jsonify(response.to_dict()), 500

    def api_geocoding_retry(self):
        """Retry failed geocoding API"""
        try:
            data = request.get_json() or {}
            max_retries = data.get('max_retries', 50)

            # Run retry in background thread
            def run_retry():
                try:
                    result = self.geocoding_service.retry_failed_geocoding(max_retries)
                    logger.info(f"Geocoding retry completed: {result.successful} successful, {result.failed} failed")
                except Exception as e:
                    logger.error(f"Geocoding retry failed: {e}")

            threading.Thread(target=run_retry, daemon=True).start()

            response = ApiResponse(
                success=True,
                message=f"Geocoding retry started for up to {max_retries} entries"
            )
            return jsonify(response.to_dict())

        except Exception as e:
            logger.error(f"Geocoding retry API error: {e}")
            response = ApiResponse(success=False, message="Failed to retry geocoding", error=str(e))
            return jsonify(response.to_dict()), 500

    def api_stats_categories(self):
        """Category statistics API"""
        try:
            stats = self.db.get_category_stats()
            return jsonify([stat.to_dict() for stat in stats])
        except Exception as e:
            logger.error(f"Category stats API error: {e}")
            return jsonify({"error": str(e)}), 500

    def api_stats_overview(self):
        """Overview statistics API"""
        try:
            health = self.db.get_system_health()
            category_stats = self.db.get_category_stats()

            overview = {
                "health": health.to_dict(),
                "categories": [stat.to_dict() for stat in category_stats],
                "summary": {
                    "total_categories": len(category_stats),
                    "total_properties": health.total_properties,
                    "geocoding_percentage": health.geocoding_percentage,
                    "health_status": health.health_status
                }
            }

            return jsonify(overview)
        except Exception as e:
            logger.error(f"Overview stats API error: {e}")
            return jsonify({"error": str(e)}), 500

    def start_service(self):
        """Start the admin web service"""
        logger.info(f"Starting admin service on port {self.config.web_server.admin_port}")

        self.app.run(
            host=self.config.web_server.host,
            port=self.config.web_server.admin_port,
            debug=self.config.web_server.debug,
            threaded=True
        )


def main():
    """Main entry point for admin service"""
    import os
    from config import setup_logging

    setup_logging()

    # Create admin templates directory if it doesn't exist
    os.makedirs('admin_templates', exist_ok=True)

    admin_service = AdminService()
    try:
        admin_service.start_service()
    except KeyboardInterrupt:
        logger.info("Admin service stopped")
    except Exception as e:
        logger.error(f"Admin service error: {e}")


if __name__ == "__main__":
    main()
