#!/usr/bin/env python3
"""
Simplified Geocoding Service - Clean, maintainable approach
"""

import asyncio
import time
import schedule
import logging
import threading
import re
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from difflib import SequenceMatcher

from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderQuotaExceeded, GeocoderServiceError

from config import get_config
from database import DatabaseManager
from models import GeocodingConfig, FailedGeocoding

logger = logging.getLogger(__name__)


@dataclass
class GeocodingResult:
    """Result of a geocoding operation"""
    property_id: int
    city: str
    success: bool
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    source: Optional[str] = None
    error: Optional[str] = None
    duration_seconds: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary with JSON-serializable types"""
        return {
            'property_id': self.property_id,
            'city': self.city,
            'success': self.success,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'source': self.source,
            'error': self.error,
            'duration_seconds': self.duration_seconds
        }


@dataclass
class BatchGeocodingResult:
    """Result of a batch geocoding operation"""
    total_processed: int
    successful: int
    failed: int
    cached: int
    duration_seconds: float
    errors: List[str]
    timestamp: datetime

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary with JSON-serializable types"""
        return {
            'total_processed': self.total_processed,
            'successful': self.successful,
            'failed': self.failed,
            'cached': self.cached,
            'duration_seconds': self.duration_seconds,
            'errors': self.errors,
            'timestamp': self.timestamp.isoformat()
        }


class GeocodingDataManager:
    """Manages external geocoding data files"""
    
    def __init__(self, data_dir: str = "geocoding_data"):
        self.data_dir = data_dir
        self._ensure_data_directory()
        self._create_default_files()
        
        # Load data
        self.city_corrections = self._load_city_corrections()
        self.diacritic_map = self._load_diacritic_map()
        self.common_prefixes = self._load_common_prefixes()
    
    def _ensure_data_directory(self):
        """Create data directory if it doesn't exist"""
        os.makedirs(self.data_dir, exist_ok=True)
    
    def _create_default_files(self):
        """Create default data files if they don't exist"""
        
        # City corrections file
        corrections_file = os.path.join(self.data_dir, "city_corrections.json")
        if not os.path.exists(corrections_file):
            default_corrections = {
                "warszewa": "warszawa",
                "warsawa": "warszawa",
                "warshawa": "warszawa",
                "krakuw": "krakow",
                "krakof": "krakow",
                "wroclw": "wroclaw",
                "wrocalw": "wroclaw",
                "wrocaw": "wroclaw",
                "gdanks": "gdansk",
                "poznan": "poznan",
                "poznań": "poznan",
                "lodz": "lodz",
                "łódz": "lodz",
                "szczecin": "szczecin",
                "szczesz": "szczecin",
                "bydgoscz": "bydgoszcz",
                "bydgoszcz": "bydgoszcz",
                "lublin": "lublin",
                "lubllin": "lublin",
                "katovice": "katowice",
                "katowice": "katowice",
                "rzeszow": "rzeszow",
                "rzeszów": "rzeszow"
            }
            with open(corrections_file, 'w', encoding='utf-8') as f:
                json.dump(default_corrections, f, indent=2, ensure_ascii=False)
        
        # Diacritic mapping file
        diacritic_file = os.path.join(self.data_dir, "diacritic_mapping.json")
        if not os.path.exists(diacritic_file):
            default_diacritics = {
                "ą": "a", "ć": "c", "ę": "e", "ł": "l", "ń": "n", 
                "ó": "o", "ś": "s", "ź": "z", "ż": "z",
                "Ą": "A", "Ć": "C", "Ę": "E", "Ł": "L", "Ń": "N",
                "Ó": "O", "Ś": "S", "Ź": "Z", "Ż": "Z"
            }
            with open(diacritic_file, 'w', encoding='utf-8') as f:
                json.dump(default_diacritics, f, indent=2, ensure_ascii=False)
        
        # Common prefixes file
        prefixes_file = os.path.join(self.data_dir, "common_prefixes.json")
        if not os.path.exists(prefixes_file):
            default_prefixes = [
                "gmina", "gm.", "miasto", "m.", "powiat", "pow.",
                "województwo", "woj."
            ]
            with open(prefixes_file, 'w', encoding='utf-8') as f:
                json.dump(default_prefixes, f, indent=2, ensure_ascii=False)
    
    def _load_city_corrections(self) -> Dict[str, str]:
        """Load city correction mappings"""
        try:
            corrections_file = os.path.join(self.data_dir, "city_corrections.json")
            with open(corrections_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load city corrections: {e}")
            return {}
    
    def _load_diacritic_map(self) -> Dict[str, str]:
        """Load diacritic character mappings"""
        try:
            diacritic_file = os.path.join(self.data_dir, "diacritic_mapping.json")
            with open(diacritic_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load diacritic mappings: {e}")
            return {}
    
    def _load_common_prefixes(self) -> List[str]:
        """Load common city prefixes"""
        try:
            prefixes_file = os.path.join(self.data_dir, "common_prefixes.json")
            with open(prefixes_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load common prefixes: {e}")
            return []
    
    def get_corrected_city(self, city: str) -> str:
        """Get corrected city name if available"""
        city_lower = city.lower().strip()
        return self.city_corrections.get(city_lower, city)
    
    def remove_diacritics(self, text: str) -> str:
        """Remove Polish diacritics from text"""
        result = text
        for polish_char, latin_char in self.diacritic_map.items():
            result = result.replace(polish_char, latin_char)
        return result
    
    def clean_city_name(self, city: str) -> str:
        """Clean city name by removing common prefixes"""
        city = city.strip()
        city_lower = city.lower()
        
        for prefix in self.common_prefixes:
            if city_lower.startswith(prefix + " "):
                return city[len(prefix):].strip()
        
        return city


class SimpleFuzzyMatcher:
    """Simplified fuzzy matching for city names"""
    
    def __init__(self, data_manager: GeocodingDataManager):
        self.data_manager = data_manager
    
    def similarity(self, s1: str, s2: str) -> float:
        """Calculate similarity between two strings (0.0 to 1.0)"""
        return SequenceMatcher(None, s1.lower(), s2.lower()).ratio()
    
    def generate_variants(self, city: str) -> List[str]:
        """Generate simple variants of city name"""
        variants = set()
        
        # Original
        variants.add(city)
        
        # Cleaned version
        cleaned = self.data_manager.clean_city_name(city)
        variants.add(cleaned)
        
        # Without diacritics
        no_diacritics = self.data_manager.remove_diacritics(city)
        variants.add(no_diacritics)
        
        # Corrected version
        corrected = self.data_manager.get_corrected_city(city)
        variants.add(corrected)
        
        # Cleaned and corrected
        corrected_cleaned = self.data_manager.clean_city_name(corrected)
        variants.add(corrected_cleaned)
        
        # Remove empty variants and limit to reasonable number
        final_variants = [v for v in variants if v and len(v) > 1]
        return final_variants[:8]  # Limit to 8 variants max


class PolishGeocodingWorker:
    """Simplified geocoding worker for Polish cities"""

    def __init__(self, db_manager: DatabaseManager):
        self.config = get_config()
        self.db = db_manager
        self.nominatim = Nominatim(user_agent="PropertyMonitor/2.0")
        self._rate_limit_delay = 1.1  # Nominatim: max 1 request/second
        
        # Initialize data management
        self.data_manager = GeocodingDataManager()
        self.fuzzy_matcher = SimpleFuzzyMatcher(self.data_manager)
        
        # Poland bounding box
        self.poland_bounds = {
            'min_lat': 49.0, 'max_lat': 54.9,
            'min_lng': 14.1, 'max_lng': 24.2
        }

    async def geocode_property(self, property_data: Dict) -> GeocodingResult:
        """Geocode single property with simplified approach"""
        start_time = time.time()
        city = property_data['city']
        property_id = property_data['id']

        try:
            # Check cache first
            cached_result = self.db.get_cached_geocoding(city)
            if cached_result:
                lat, lng = cached_result
                self.db.update_property_geocoding(property_id, lat, lng, "cache")

                duration = time.time() - start_time
                logger.debug(f"Used cached geocoding for {city}")

                return GeocodingResult(
                    property_id=property_id, city=city, success=True,
                    latitude=lat, longitude=lng, source="cache",
                    duration_seconds=duration
                )

            # Try geocoding strategies
            result = await self._try_geocoding_strategies(city)
            
            if result and self._is_in_poland(result[0], result[1]):
                lat, lng, source = result

                # Save to cache and update property
                self.db.save_geocoding_result(city, lat, lng, source, True)
                self.db.update_property_geocoding(property_id, lat, lng, source)

                duration = time.time() - start_time
                logger.debug(f"Geocoded {city}: {lat}, {lng} using {source}")

                return GeocodingResult(
                    property_id=property_id, city=city, success=True,
                    latitude=lat, longitude=lng, source=source,
                    duration_seconds=duration
                )

            # All strategies failed
            duration = time.time() - start_time
            error_msg = f"Failed to geocode {city} (no valid Poland location found)"
            logger.warning(error_msg)

            self.db.save_geocoding_result(city, None, None, "failed", False)
            self.db.update_property_geocoding(property_id, None, None, "failed")

            return GeocodingResult(
                property_id=property_id, city=city, success=False,
                error=error_msg, duration_seconds=duration
            )

        except Exception as e:
            duration = time.time() - start_time
            error_msg = f"Geocoding error for {city}: {str(e)}"
            logger.error(error_msg)

            self.db.update_property_geocoding(property_id, None, None, "error")

            return GeocodingResult(
                property_id=property_id, city=city, success=False,
                error=error_msg, duration_seconds=duration
            )

    async def _try_geocoding_strategies(self, city: str) -> Optional[Tuple[float, float, str]]:
        """Try different geocoding strategies in order"""
        
        # Strategy 1: Direct search with Poland restriction
        result = await self._geocode_basic(city)
        if result:
            return result

        # Strategy 2: Try with cleaned city name
        cleaned_city = self.data_manager.clean_city_name(city)
        if cleaned_city != city:
            result = await self._geocode_basic(cleaned_city)
            if result:
                return (*result[:2], "cleaned")

        # Strategy 3: Try corrected version
        corrected_city = self.data_manager.get_corrected_city(city)
        if corrected_city != city:
            result = await self._geocode_basic(corrected_city)
            if result:
                return (*result[:2], "corrected")

        # Strategy 4: Try variants (fuzzy search)
        variants = self.fuzzy_matcher.generate_variants(city)
        for variant in variants:
            if variant != city:  # Don't repeat original
                result = await self._geocode_basic(variant)
                if result:
                    logger.info(f"Found match for '{city}' using variant '{variant}'")
                    return (*result[:2], "fuzzy")

        return None

    async def _geocode_basic(self, city: str) -> Optional[Tuple[float, float, str]]:
        """Basic geocoding with Poland restriction"""
        queries = [f"{city}, Poland", f"{city}, PL"]

        for query in queries:
            try:
                location = self.nominatim.geocode(
                    query, timeout=10, exactly_one=True, country_codes=['PL']
                )
                if location and self._is_in_poland(location.latitude, location.longitude):
                    return location.latitude, location.longitude, "nominatim"
                    
                await asyncio.sleep(self._rate_limit_delay)
                
            except Exception as e:
                logger.debug(f"Geocoding failed for {query}: {e}")
                continue

        return None

    def _is_in_poland(self, lat: float, lng: float) -> bool:
        """Check if coordinates are within Poland's bounding box"""
        return (self.poland_bounds['min_lat'] <= lat <= self.poland_bounds['max_lat'] and
                self.poland_bounds['min_lng'] <= lng <= self.poland_bounds['max_lng'])

    async def process_batch(self, batch_size: Optional[int] = None) -> BatchGeocodingResult:
        """Process a batch of properties for geocoding"""
        start_time = time.time()

        # Get geocoding configuration
        geocoding_config = self.db.get_geocoding_config()

        if not geocoding_config.enabled:
            logger.info("Geocoding is disabled")
            return BatchGeocodingResult(
                total_processed=0, successful=0, failed=0, cached=0,
                duration_seconds=0, errors=["Geocoding is disabled"],
                timestamp=datetime.now()
            )

        # Use configured batch size if not specified
        if batch_size is None:
            batch_size = geocoding_config.batch_size

        properties = self.db.get_properties_for_geocoding(batch_size)

        if not properties:
            logger.info("No properties need geocoding")
            return BatchGeocodingResult(
                total_processed=0, successful=0, failed=0, cached=0,
                duration_seconds=time.time() - start_time, errors=[],
                timestamp=datetime.now()
            )

        logger.info(f"Processing {len(properties)} properties for geocoding")

        successful = cached = failed = 0
        errors = []

        for prop in properties:
            try:
                result = await self.geocode_property(prop)

                if result.success:
                    if result.source == "cache":
                        cached += 1
                    else:
                        successful += 1
                else:
                    failed += 1
                    if result.error:
                        errors.append(f"Property {result.property_id}: {result.error}")

                # Rate limiting
                await asyncio.sleep(geocoding_config.delay_seconds)

            except Exception as e:
                failed += 1
                error_msg = f"Failed to geocode property {prop['id']}: {str(e)}"
                logger.error(error_msg)
                errors.append(error_msg)

        duration = time.time() - start_time
        total_processed = len(properties)

        logger.info(f"Geocoding batch completed: {successful} successful, {cached} cached, {failed} failed in {duration:.1f}s")

        return BatchGeocodingResult(
            total_processed=total_processed, successful=successful,
            failed=failed, cached=cached, duration_seconds=duration,
            errors=errors, timestamp=datetime.now()
        )


class GeocodingService:
    """Simplified geocoding service with scheduling"""

    def __init__(self):
        self.config = get_config()
        self.db = DatabaseManager()
        self.worker = PolishGeocodingWorker(self.db)
        self.running = False
        self._scheduler_thread = None
        self._stop_event = threading.Event()

    def start_service(self):
        """Start the geocoding service"""
        if self.running:
            logger.warning("Geocoding service is already running")
            return

        logger.info("Starting Simplified Geocoding Service")
        self.running = True
        self._stop_event.clear()

        # Clear any existing scheduled jobs for geocoding
        schedule.clear('geocoding')

        # Schedule geocoding based on configuration
        geocoding_config = self.db.get_geocoding_config()
        if geocoding_config.enabled and self.config.service.geocoding_interval_minutes > 0:
            schedule.every(self.config.service.geocoding_interval_minutes).minutes.do(
                self._geocoding_job
            ).tag('geocoding')
            logger.info(f"Scheduled geocoding every {self.config.service.geocoding_interval_minutes} minutes")

        # Start scheduler thread
        self._scheduler_thread = threading.Thread(target=self._run_scheduler, daemon=True, name="GeocodingScheduler")
        self._scheduler_thread.start()

        logger.info("Simplified geocoding service started")

    def stop_service(self):
        """Stop the geocoding service"""
        logger.info("Stopping geocoding service...")
        self.running = False
        self._stop_event.set()

        # Clear scheduled jobs
        schedule.clear('geocoding')

        if self._scheduler_thread and self._scheduler_thread.is_alive():
            self._scheduler_thread.join(timeout=5)

    def _run_scheduler(self):
        """Run the scheduler loop"""
        while self.running and not self._stop_event.is_set():
            try:
                schedule.run_pending()
                
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
                logger.error(f"Geocoding scheduler error: {e}")
                if self._stop_event.wait(60):
                    break

    def _update_service_status(self):
        """Update service status in database"""
        try:
            status = self.get_geocoding_status()
            self.db.update_service_status('geocoding', status)
            self._last_status_update = time.time()
            logger.debug("Updated geocoding service status in database")
        except Exception as e:
            logger.error(f"Failed to update geocoding service status: {e}")

    def _geocoding_job(self):
        """Scheduled geocoding job"""
        try:
            logger.info("Starting scheduled geocoding job")
            result = asyncio.run(self.worker.process_batch())

            logger.info(f"Scheduled geocoding completed: {result.successful} successful, "
                        f"{result.cached} cached, {result.failed} failed")

            # Log health event
            self.db.log_health_event(
                component="geocoding",
                status="success" if result.failed == 0 else "warning",
                message=f"Geocoding: {result.successful} successful, {result.failed} failed",
                data=result.to_dict()
            )

        except Exception as e:
            logger.error(f"Scheduled geocoding job failed: {e}")
            self.db.log_health_event(
                component="geocoding",
                status="error",
                message=f"Geocoding job failed: {str(e)}"
            )

    def manual_geocoding(self, batch_size: Optional[int] = None) -> BatchGeocodingResult:
        """Manually trigger geocoding"""
        logger.info(f"Manual geocoding triggered with batch size: {batch_size}")
        result = asyncio.run(self.worker.process_batch(batch_size))

        self.db.log_health_event(
            component="geocoding",
            status="success" if result.failed == 0 else "warning",
            message=f"Manual geocoding: {result.successful} successful, {result.failed} failed",
            data=result.to_dict()
        )

        return result

    def update_geocoding_config(self, config: GeocodingConfig) -> bool:
        """Update geocoding configuration"""
        try:
            success = self.db.update_geocoding_config(config)
            if success:
                logger.info("Geocoding configuration updated")
                self.db.log_health_event(
                    component="geocoding",
                    status="success",
                    message="Geocoding configuration updated",
                    data=config.to_dict()
                )
            return success
        except Exception as e:
            logger.error(f"Failed to update geocoding configuration: {e}")
            return False

    def get_geocoding_status(self) -> Dict[str, Any]:
        """Get current geocoding status"""
        config = self.db.get_geocoding_config()
        health = self.db.get_system_health()

        # Get next scheduled run time for geocoding jobs only
        next_run = None
        geocoding_jobs = [job for job in schedule.get_jobs() if 'geocoding' in job.tags]
        if geocoding_jobs:
            next_run = min(job.next_run for job in geocoding_jobs)
            if next_run:
                next_run = next_run.isoformat()

        status = {
            "service_running": self.running,
            "enabled": config.enabled,
            "batch_size": config.batch_size,
            "delay_seconds": config.delay_seconds,
            "max_attempts": config.max_attempts,
            "retry_failed_after_hours": config.retry_failed_after_hours,
            "total_properties": health.total_properties,
            "geocoded_properties": health.geocoded_properties,
            "failed_geocoding": health.failed_geocoding,
            "pending_geocoding": health.pending_geocoding,
            "geocoding_percentage": health.geocoding_percentage,
            "last_geocoding": health.last_geocoding.isoformat() if health.last_geocoding else None,
            "next_scheduled_run": next_run,
            "poland_restriction": True,
            "fuzzy_search": True,
            "data_files_loaded": True
        }

        return status

    def get_failed_geocoding_entries(self, limit: int = 100) -> List[FailedGeocoding]:
        """Get failed geocoding entries for manual review"""
        return self.db.get_failed_geocoding_entries(limit)

    def manual_geocoding_fix(self, property_id: int, latitude: float, longitude: float) -> bool:
        """Manually fix geocoding for a property"""
        try:
            # Verify coordinates are in Poland
            if not self.worker._is_in_poland(latitude, longitude):
                logger.warning(f"Manual fix coordinates for property {property_id} are outside Poland")
                return False

            success = self.db.manual_geocoding_update(property_id, latitude, longitude)
            if success:
                logger.info(f"Manual geocoding fix applied for property {property_id}")
                self.db.log_health_event(
                    component="geocoding",
                    status="success",
                    message=f"Manual geocoding fix applied for property {property_id}",
                    data={"property_id": property_id, "latitude": latitude, "longitude": longitude}
                )
            return success
        except Exception as e:
            logger.error(f"Failed to apply manual geocoding fix: {e}")
            return False

    def retry_failed_geocoding(self, max_retries: int = 50) -> BatchGeocodingResult:
        """Retry failed geocoding entries"""
        logger.info(f"Retrying failed geocoding entries (max {max_retries})")

        # Get failed entries and convert to property format
        failed_entries = self.get_failed_geocoding_entries(max_retries)

        if not failed_entries:
            return BatchGeocodingResult(
                total_processed=0, successful=0, failed=0, cached=0,
                duration_seconds=0, errors=[], timestamp=datetime.now()
            )

        # Convert to property format for processing
        properties = []
        for entry in failed_entries:
            properties.append({
                'id': entry.property_id,
                'city': entry.city,
                'title': entry.property_title
            })

        # Process the batch
        start_time = time.time()
        successful = failed = 0
        errors = []

        for prop in properties:
            try:
                result = asyncio.run(self.worker.geocode_property(prop))
                if result.success:
                    successful += 1
                else:
                    failed += 1
                    if result.error:
                        errors.append(result.error)

                # Rate limiting
                time.sleep(self.db.get_geocoding_config().delay_seconds)

            except Exception as e:
                failed += 1
                error_msg = f"Retry failed for property {prop['id']}: {str(e)}"
                logger.error(error_msg)
                errors.append(error_msg)

        duration = time.time() - start_time

        result = BatchGeocodingResult(
            total_processed=len(properties), successful=successful,
            failed=failed, cached=0, duration_seconds=duration,
            errors=errors, timestamp=datetime.now()
        )

        logger.info(f"Retry geocoding completed: {successful} successful, {failed} failed")
        return result


# CLI functions for manual operations
def run_manual_geocoding(batch_size: Optional[int] = None):
    """Run manual geocoding from CLI"""
    service = GeocodingService()
    result = service.manual_geocoding(batch_size)

    print(f"\nSimplified Geocoding Results:")
    print(f"  Total processed: {result.total_processed}")
    print(f"  Successful: {result.successful}")
    print(f"  Cached: {result.cached}")
    print(f"  Failed: {result.failed}")
    print(f"  Duration: {result.duration_seconds:.1f}s")

    if result.errors:
        print(f"  Errors: {len(result.errors)}")
        for error in result.errors[:5]:  # Show first 5 errors
            print(f"    - {error}")
        if len(result.errors) > 5:
            print(f"    ... and {len(result.errors) - 5} more errors")


def main():
    """Main entry point for simplified geocoding service"""
    import sys
    from config import setup_logging

    setup_logging()

    if len(sys.argv) > 1:
        command = sys.argv[1]

        if command == "geocode":
            batch_size = int(sys.argv[2]) if len(sys.argv) > 2 else None
            run_manual_geocoding(batch_size)
        elif command == "status":
            service = GeocodingService()
            status = service.get_geocoding_status()
            print(json.dumps(status, indent=2))
        elif command == "failed":
            service = GeocodingService()
            failed_entries = service.get_failed_geocoding_entries(50)
            print(f"Failed geocoding entries: {len(failed_entries)}")
            for entry in failed_entries[:10]:
                print(f"  {entry.property_id}: {entry.city} (attempts: {entry.attempts})")
        elif command == "retry":
            service = GeocodingService()
            result = service.retry_failed_geocoding()
            print(f"Retry results: {result.successful} successful, {result.failed} failed")
        elif command == "daemon":
            # Run as daemon service
            service = GeocodingService()
            try:
                service.start_service()
                # Keep running
                while service.running:
                    time.sleep(1)
            except KeyboardInterrupt:
                logger.info("Received interrupt signal")
            finally:
                service.stop_service()
        else:
            print("Usage: python geocoding_service.py [geocode|status|failed|retry|daemon] [batch_size]")
    else:
        # Default: run manual geocoding
        run_manual_geocoding()


if __name__ == "__main__":
    main()
