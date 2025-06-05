#!/usr/bin/env python3
"""
Enhanced Database Manager for Property Monitoring System - Fixed JSON serialization + Missing Methods
"""

import os
import re
import sqlite3
import json
import hashlib
import logging
import unicodedata
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Union
from contextlib import contextmanager

from models import (
    Property, GeocodingCache, ScrapingConfig, GeocodingConfig,
    SystemHealth, CategoryStats, FailedGeocoding,
    DEFAULT_SCRAPING_CATEGORIES, DEFAULT_GEOCODING_CONFIG
)

logger = logging.getLogger(__name__)


class DateTimeEncoder(json.JSONEncoder):
    """Custom JSON encoder to handle datetime objects"""
    
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, (timedelta,)):
            return str(obj)
        return super().default(obj)


class DatabaseManager:
    """Enhanced database manager with admin controls and fixed JSON serialization"""

    def __init__(self, db_path: str = "/var/lib/property_monitor/properties.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.init_database()

    @contextmanager
    def get_connection(self):
        """Context manager for database connections"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Enable dict-like access
        try:
            yield conn
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def _serialize_json_data(self, data: Any) -> Optional[str]:
        """Safely serialize data to JSON with datetime handling"""
        if data is None:
            return None
        
        try:
            return json.dumps(data, cls=DateTimeEncoder, ensure_ascii=False)
        except (TypeError, ValueError) as e:
            logger.error(f"Failed to serialize data to JSON: {e}")
            # Fallback: convert problematic objects to strings
            try:
                return json.dumps(self._convert_to_serializable(data), ensure_ascii=False)
            except Exception as fallback_e:
                logger.error(f"Fallback JSON serialization also failed: {fallback_e}")
                return json.dumps({"error": f"Serialization failed: {str(e)}"})

    def _convert_to_serializable(self, obj: Any) -> Any:
        """Convert complex objects to JSON-serializable types"""
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, timedelta):
            return str(obj)
        elif isinstance(obj, dict):
            return {k: self._convert_to_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [self._convert_to_serializable(item) for item in obj]
        elif hasattr(obj, '__dict__'):
            # Convert dataclass or custom objects
            return self._convert_to_serializable(obj.__dict__)
        else:
            return obj

    def _normalize_city(self, city: str) -> str:
        """Normalize city name for consistent caching"""
        if not city:
            return ""
        
        # Remove extra whitespace and convert to lowercase
        city = city.strip().lower()
        
        # Remove common prefixes
        prefixes = ['gmina ', 'gm. ', 'miasto ', 'm. ', 'powiat ', 'pow. ']
        for prefix in prefixes:
            if city.startswith(prefix):
                city = city[len(prefix):].strip()
                break
        
        # Normalize Unicode characters (remove diacritics)
        city = unicodedata.normalize('NFKD', city)
        city = city.encode('ascii', 'ignore').decode('ascii')
        
        # Remove special characters except spaces and hyphens
        city = re.sub(r'[^\w\s\-]', '', city)
        
        # Replace multiple spaces with single space
        city = re.sub(r'\s+', ' ', city)
        
        # Replace spaces with underscores for consistent key format
        city = city.replace(' ', '_')
        
        return city

    def init_database(self):
        """Initialize database with enhanced schema"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Enhanced properties table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS properties (
                    id INTEGER PRIMARY KEY,
                    title TEXT,
                    city TEXT,
                    main_category TEXT,
                    sub_category TEXT,
                    estimate REAL,
                    opening_value REAL,
                    margin REAL,
                    is_margin_required BOOLEAN,
                    start_auction_at TEXT,
                    margin_due_date TEXT,
                    date_created TEXT,
                    status TEXT,
                    bailiff_office TEXT,
                    main_photo_base64 TEXT,
                    explanation TEXT,
                    land_area_m2 REAL,
                    land_area_ha REAL,
                    land_type TEXT,
                    utilities TEXT,
                    ownership_form TEXT,
                    ownership_share TEXT,
                    -- Geocoding fields
                    geocoded BOOLEAN DEFAULT FALSE,
                    latitude DECIMAL(10,8),
                    longitude DECIMAL(11,8),
                    geocoding_source TEXT,
                    geocoding_attempts INTEGER DEFAULT 0,
                    last_geocoded TIMESTAMP,
                    -- System fields
                    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    auction_closed BOOLEAN DEFAULT FALSE
                )
            ''')

            # Geocoding cache
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS geocoding_cache (
                    city_key VARCHAR(100) PRIMARY KEY,
                    latitude DECIMAL(10,8),
                    longitude DECIMAL(11,8),
                    source TEXT,
                    success BOOLEAN,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # System configuration
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS system_config (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Scraping configuration
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS scraping_config (
                    category TEXT PRIMARY KEY,
                    enabled BOOLEAN DEFAULT TRUE,
                    max_pages INTEGER,
                    delay_seconds REAL DEFAULT 2.0,
                    priority INTEGER DEFAULT 1,
                    last_run TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # System health and logs
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS system_health (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    component TEXT,
                    status TEXT,
                    message TEXT,
                    data TEXT
                )
            ''')

            # Failed geocoding for manual review
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS failed_geocoding (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    property_id INTEGER,
                    city TEXT,
                    property_title TEXT,
                    attempts INTEGER DEFAULT 0,
                    last_attempt TIMESTAMP,
                    error_message TEXT,
                    suggested_latitude DECIMAL(10,8),
                    suggested_longitude DECIMAL(11,8),
                    resolved BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (property_id) REFERENCES properties (id)
                )
            ''')
            
            self.init_watched_properties_table()
            
            # Create indexes for performance
            self._create_indexes(cursor)

            # Initialize default configurations
            self._init_default_configs(cursor)

            conn.commit()
            logger.info("Database initialized successfully")

    def init_watched_properties_table(self):
        """Initialize watched properties table - call this in init_database()"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS watched_properties (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    property_id INTEGER NOT NULL,
                    notes TEXT,
                    watched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (property_id) REFERENCES properties (id),
                    UNIQUE(property_id)
                )
            ''')

            # Create index for faster lookups
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_watched_property_id ON watched_properties(property_id)')
            conn.commit()

    def add_to_watched(self, property_id: int, notes: str = "") -> bool:
        """Add property to watched list"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO watched_properties (property_id, notes, updated_at)
                    VALUES (?, ?, ?)
                ''', (property_id, notes, datetime.now().isoformat()))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Failed to add property {property_id} to watched: {e}")
            return False

    def remove_from_watched(self, property_id: int) -> bool:
        """Remove property from watched list"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM watched_properties WHERE property_id = ?', (property_id,))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Failed to remove property {property_id} from watched: {e}")
            return False

    def update_watched_notes(self, property_id: int, notes: str) -> bool:
        """Update notes for watched property"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE watched_properties
                    SET notes = ?, updated_at = ?
                    WHERE property_id = ?
                ''', (notes, datetime.now().isoformat(), property_id))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Failed to update notes for property {property_id}: {e}")
            return False

    def get_watched_properties(self) -> List[Dict]:
        """Get all watched properties with full property details"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT
                        p.id, p.title, p.city, p.opening_value, p.estimate,
                        p.latitude, p.longitude, p.status, p.land_area_ha, p.land_type,
                        p.start_auction_at, p.sub_category, p.date_created,
                        w.notes, w.watched_at, w.updated_at
                    FROM watched_properties w
                    JOIN properties p ON w.property_id = p.id
                    WHERE p.geocoded = TRUE AND p.latitude IS NOT NULL AND p.longitude IS NOT NULL
                    ORDER BY w.updated_at DESC
                ''')

                watched_properties = []
                for row in cursor.fetchall():
                    # Generate property URL
                    title = row['title'] or ""
                    slug = title.lower().replace(" ", "-").replace(",", "").replace(".", "")
                    slug = "".join(c for c in slug if c.isalnum() or c in "-")
                    property_url = f"https://elicytacje.komornik.pl/items/{row['id']}/{slug}" if slug else f"https://elicytacje.komornik.pl/items/{row['id']}"

                    watched_properties.append({
                        'id': row['id'],
                        'title': row['title'],
                        'city': row['city'],
                        'opening_value': row['opening_value'],
                        'estimate': row['estimate'],
                        'latitude': float(row['latitude']),
                        'longitude': float(row['longitude']),
                        'status': row['status'],
                        'land_area_ha': row['land_area_ha'],
                        'land_type': row['land_type'],
                        'start_auction_at': row['start_auction_at'],
                        'sub_category': row['sub_category'],
                        'date_created': row['date_created'],
                        'property_url': property_url,
                        'notes': row['notes'] or '',
                        'watched_at': row['watched_at'],
                        'updated_at': row['updated_at'],
                        'is_watched': True
                    })

                return watched_properties
        except Exception as e:
            logger.error(f"Failed to get watched properties: {e}")
            return []

    def get_watched_property_ids(self) -> set:
        """Get set of watched property IDs for quick lookup"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT property_id FROM watched_properties')
                return {row['property_id'] for row in cursor.fetchall()}
        except Exception as e:
            logger.error(f"Failed to get watched property IDs: {e}")
            return set()

    def is_property_watched(self, property_id: int) -> bool:
        """Check if property is in watched list"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT 1 FROM watched_properties WHERE property_id = ?', (property_id,))
                return cursor.fetchone() is not None
        except Exception as e:
            logger.error(f"Failed to check if property {property_id} is watched: {e}")
            return False

    def get_watched_property_details(self, property_id: int) -> Optional[Dict]:
        """Get watched property details including notes"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT notes, watched_at, updated_at
                    FROM watched_properties
                    WHERE property_id = ?
                ''', (property_id,))

                result = cursor.fetchone()
                if result:
                    return {
                        'notes': result['notes'] or '',
                        'watched_at': result['watched_at'],
                        'updated_at': result['updated_at']
                    }
                return None
        except Exception as e:
            logger.error(f"Failed to get watched property details for {property_id}: {e}")
            return None


    def _create_indexes(self, cursor):
        """Create database indexes"""
        indexes = [
            'CREATE INDEX IF NOT EXISTS idx_properties_geocoded ON properties(geocoded)',
            'CREATE INDEX IF NOT EXISTS idx_properties_city ON properties(city)',
            'CREATE INDEX IF NOT EXISTS idx_properties_category ON properties(sub_category)',
            'CREATE INDEX IF NOT EXISTS idx_properties_auction_date ON properties(start_auction_at)',
            'CREATE INDEX IF NOT EXISTS idx_properties_status ON properties(status)',
            'CREATE INDEX IF NOT EXISTS idx_cache_city ON geocoding_cache(city_key)',
            'CREATE INDEX IF NOT EXISTS idx_health_timestamp ON system_health(timestamp)',
            'CREATE INDEX IF NOT EXISTS idx_failed_geocoding_resolved ON failed_geocoding(resolved)'
        ]

        for index_sql in indexes:
            cursor.execute(index_sql)

    def _init_default_configs(self, cursor):
        """Initialize default configurations"""
        # Initialize scraping configurations
        for config in DEFAULT_SCRAPING_CATEGORIES:
            cursor.execute('''
                INSERT OR IGNORE INTO scraping_config 
                (category, enabled, max_pages, delay_seconds, priority)
                VALUES (?, ?, ?, ?, ?)
            ''', (config.category, config.enabled, config.max_pages,
                  config.delay_seconds, config.priority))

        # Initialize geocoding configuration
        geocoding_config = DEFAULT_GEOCODING_CONFIG.to_dict()
        cursor.execute('''
            INSERT OR IGNORE INTO system_config (key, value)
            VALUES ('geocoding_config', ?)
        ''', (self._serialize_json_data(geocoding_config),))

    # Properties operations
    def save_properties(self, properties: List[Dict]) -> Tuple[int, int]:
        """Save properties with incremental updates"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            new_count = 0
            updated_count = 0

            for prop in properties:
                # Check if property exists
                cursor.execute('SELECT id, last_updated FROM properties WHERE id = ?', (prop.get('id'),))
                existing = cursor.fetchone()

                # Extract and process property data
                property_data = self._process_property_data(prop)

                if existing:
                    # Update existing property
                    self._update_property(cursor, property_data)
                    updated_count += 1
                else:
                    # Insert new property
                    self._insert_property(cursor, property_data)
                    new_count += 1

            conn.commit()
            logger.info(f"Database updated: {new_count} new, {updated_count} updated properties")
            return new_count, updated_count

    def _process_property_data(self, prop: Dict) -> Dict:
        """Process and clean property data"""
        # Extract land parameters
        land_area_m2 = land_area_ha = land_type = utilities = ownership_form = ownership_share = None
        if 'params' in prop:
            params = prop['params']
            land_area_m2 = params.get('LAND_AREA')
            land_area_ha = params.get('LAND_AREAHA')
            land_type = params.get('LAND_LOTTYPE')
            utilities = self._serialize_json_data(params.get('LAND_MEDIA', [])) if params.get('LAND_MEDIA') else None
            ownership_form = params.get('LAND_FORMOFOWNERSHIP')
            ownership_share = params.get('LAND_SHARESIZE')

        now = datetime.now().isoformat()

        return {
            'id': prop.get('id'),
            'title': prop.get('title'),
            'city': prop.get('city'),
            'main_category': prop.get('mainCategory'),
            'sub_category': prop.get('subCategory'),
            'estimate': prop.get('estimate'),
            'opening_value': prop.get('openingValue'),
            'margin': prop.get('margin'),
            'is_margin_required': prop.get('isMarginRequired'),
            'start_auction_at': prop.get('startAuctionAt'),
            'margin_due_date': prop.get('marginDueDate'),
            'date_created': prop.get('dateCreated'),
            'status': prop.get('status'),
            'bailiff_office': prop.get('bailiffOffice'),
            'main_photo_base64': prop.get('mainPhoto'),
            'explanation': prop.get('explanation'),
            'land_area_m2': land_area_m2,
            'land_area_ha': land_area_ha,
            'land_type': land_type,
            'utilities': utilities,
            'ownership_form': ownership_form,
            'ownership_share': ownership_share,
            'last_updated': now
        }

    def _insert_property(self, cursor, data: Dict):
        """Insert new property"""
        cursor.execute('''
            INSERT INTO properties (
                id, title, city, main_category, sub_category, estimate, opening_value,
                margin, is_margin_required, start_auction_at, margin_due_date,
                date_created, status, bailiff_office, main_photo_base64, explanation,
                land_area_m2, land_area_ha, land_type, utilities, ownership_form, ownership_share,
                first_seen, last_updated
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data['id'], data['title'], data['city'], data['main_category'],
            data['sub_category'], data['estimate'], data['opening_value'],
            data['margin'], data['is_margin_required'], data['start_auction_at'],
            data['margin_due_date'], data['date_created'], data['status'],
            data['bailiff_office'], data['main_photo_base64'], data['explanation'],
            data['land_area_m2'], data['land_area_ha'], data['land_type'],
            data['utilities'], data['ownership_form'], data['ownership_share'],
            data['last_updated'], data['last_updated']
        ))

    def _update_property(self, cursor, data: Dict):
        """Update existing property"""
        cursor.execute('''
            UPDATE properties SET
                title=?, city=?, main_category=?, sub_category=?, estimate=?, 
                opening_value=?, margin=?, is_margin_required=?, start_auction_at=?, 
                margin_due_date=?, date_created=?, status=?, bailiff_office=?, 
                main_photo_base64=?, explanation=?, land_area_m2=?, land_area_ha=?, 
                land_type=?, utilities=?, ownership_form=?, ownership_share=?,
                last_updated=?
            WHERE id=?
        ''', (
            data['title'], data['city'], data['main_category'], data['sub_category'],
            data['estimate'], data['opening_value'], data['margin'], data['is_margin_required'],
            data['start_auction_at'], data['margin_due_date'], data['date_created'],
            data['status'], data['bailiff_office'], data['main_photo_base64'],
            data['explanation'], data['land_area_m2'], data['land_area_ha'],
            data['land_type'], data['utilities'], data['ownership_form'],
            data['ownership_share'], data['last_updated'], data['id']
        ))

    def get_properties_for_geocoding(self, limit: int = 50) -> List[Dict]:
        """Get properties that need geocoding"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute('''
                SELECT id, city, title, latitude, longitude, geocoding_attempts
                FROM properties 
                WHERE geocoded = FALSE AND geocoding_attempts < ?
                ORDER BY first_seen ASC
                LIMIT ?
            ''', (self.get_geocoding_config().max_attempts, limit))

            properties = []
            for row in cursor.fetchall():
                properties.append({
                    'id': row['id'],
                    'city': row['city'],
                    'title': row['title'],
                    'latitude': row['latitude'],
                    'longitude': row['longitude'],
                    'geocoding_attempts': row['geocoding_attempts']
                })

            return properties

    def get_map_properties(self) -> List[Dict]:
        """Get all geocoded properties for map display"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute('''
                SELECT id, title, city, opening_value, estimate, latitude, longitude, 
                       status, land_area_ha, land_type, start_auction_at, sub_category
                FROM properties 
                WHERE geocoded = TRUE AND latitude IS NOT NULL AND longitude IS NOT NULL
            ''')

            properties = []
            for row in cursor.fetchall():
                # Generate property URL
                title = row['title'] or ""
                slug = title.lower().replace(" ", "-").replace(",", "").replace(".", "")
                slug = "".join(c for c in slug if c.isalnum() or c in "-")
                property_url = f"https://elicytacje.komornik.pl/items/{row['id']}/{slug}" if slug else f"https://elicytacje.komornik.pl/items/{row['id']}"

                properties.append({
                    'id': row['id'],
                    'title': row['title'],
                    'city': row['city'],
                    'opening_value': row['opening_value'],
                    'estimate': row['estimate'],
                    'latitude': float(row['latitude']),
                    'longitude': float(row['longitude']),
                    'status': row['status'],
                    'land_area_ha': row['land_area_ha'],
                    'land_type': row['land_type'],
                    'start_auction_at': row['start_auction_at'],
                    'sub_category': row['sub_category'],
                    'property_url': property_url
                })

            return properties

    # Geocoding operations
    def get_cached_geocoding(self, city: str) -> Optional[Tuple[float, float]]:
        """Get cached geocoding result"""
        city_key = self._normalize_city(city)

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT latitude, longitude FROM geocoding_cache 
                WHERE city_key = ? AND success = TRUE
            ''', (city_key,))

            result = cursor.fetchone()
            return (result['latitude'], result['longitude']) if result else None

    def save_geocoding_result(self, city: str, lat: Optional[float], lng: Optional[float], source: str, success: bool):
        """Save geocoding result to cache"""
        city_key = self._normalize_city(city)

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO geocoding_cache 
                (city_key, latitude, longitude, source, success) 
                VALUES (?, ?, ?, ?, ?)
            ''', (city_key, lat, lng, source, success))
            conn.commit()

    def update_property_geocoding(self, property_id: int, lat: Optional[float], lng: Optional[float], source: str):
        """Update property with geocoding results"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            success = lat is not None and lng is not None
            now = datetime.now().isoformat()

            cursor.execute('''
                UPDATE properties SET 
                    latitude=?, longitude=?, geocoded=?, geocoding_source=?, 
                    last_geocoded=?, geocoding_attempts=geocoding_attempts+1
                WHERE id=?
            ''', (lat, lng, success, source, now, property_id))

            # If geocoding failed after max attempts, add to failed geocoding table
            if not success:
                cursor.execute('SELECT geocoding_attempts, city, title FROM properties WHERE id=?', (property_id,))
                result = cursor.fetchone()

                if result and result['geocoding_attempts'] >= self.get_geocoding_config().max_attempts:
                    self._add_failed_geocoding(cursor, property_id, result['city'], result['title'],
                                               result['geocoding_attempts'])

            conn.commit()

    def manual_geocoding_update(self, property_id: int, lat: float, lng: float) -> bool:
        """Manually update property geocoding"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            now = datetime.now().isoformat()
            cursor.execute('''
                UPDATE properties SET 
                    latitude=?, longitude=?, geocoded=TRUE, geocoding_source='manual', 
                    last_geocoded=?
                WHERE id=?
            ''', (lat, lng, now, property_id))

            # Remove from failed geocoding if exists
            cursor.execute('UPDATE failed_geocoding SET resolved=TRUE WHERE property_id=?', (property_id,))

            conn.commit()
            return cursor.rowcount > 0

    def _add_failed_geocoding(self, cursor, property_id: int, city: str, title: str, attempts: int):
        """Add failed geocoding entry"""
        cursor.execute('''
            INSERT OR IGNORE INTO failed_geocoding 
            (property_id, city, property_title, attempts, last_attempt)
            VALUES (?, ?, ?, ?, ?)
        ''', (property_id, city, title, attempts, datetime.now().isoformat()))

    def get_failed_geocoding_entries(self, limit: int = 100) -> List[FailedGeocoding]:
        """Get failed geocoding entries for manual review"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute('''
                SELECT id, property_id, city, property_title, attempts, last_attempt, error_message,
                       suggested_latitude, suggested_longitude
                FROM failed_geocoding 
                WHERE resolved = FALSE
                ORDER BY last_attempt DESC
                LIMIT ?
            ''', (limit,))

            entries = []
            for row in cursor.fetchall():
                entries.append(FailedGeocoding(
                    id=row['id'],
                    property_id=row['property_id'],
                    city=row['city'],
                    property_title=row['property_title'],
                    attempts=row['attempts'],
                    last_attempt=datetime.fromisoformat(row['last_attempt']),
                    error_message=row['error_message'],
                    suggested_latitude=row['suggested_latitude'],
                    suggested_longitude=row['suggested_longitude']
                ))

            return entries

    # Configuration operations
    def get_scraping_configs(self) -> List[ScrapingConfig]:
        """Get all scraping configurations"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute('SELECT * FROM scraping_config ORDER BY priority')
            configs = []

            for row in cursor.fetchall():
                configs.append(ScrapingConfig(
                    category=row['category'],
                    enabled=bool(row['enabled']),
                    max_pages=row['max_pages'],
                    delay_seconds=row['delay_seconds'],
                    priority=row['priority'],
                    last_run=datetime.fromisoformat(row['last_run']) if row['last_run'] else None
                ))

            return configs

    def update_scraping_config(self, category: str, config: ScrapingConfig) -> bool:
        """Update scraping configuration"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            last_run_iso = config.last_run.isoformat() if config.last_run else None
            cursor.execute('''
                UPDATE scraping_config SET
                    enabled=?, max_pages=?, delay_seconds=?, priority=?, last_run=?, updated_at=?
                WHERE category=?
            ''', (config.enabled, config.max_pages, config.delay_seconds,
                  config.priority, last_run_iso, datetime.now().isoformat(), category))

            conn.commit()
            return cursor.rowcount > 0

    def get_geocoding_config(self) -> GeocodingConfig:
        """Get geocoding configuration"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute('SELECT value FROM system_config WHERE key = ?', ('geocoding_config',))
            result = cursor.fetchone()

            if result:
                try:
                    config_data = json.loads(result['value'])
                    return GeocodingConfig(**config_data)
                except (json.JSONDecodeError, TypeError) as e:
                    logger.error(f"Failed to deserialize geocoding config: {e}")
                    return DEFAULT_GEOCODING_CONFIG
            else:
                return DEFAULT_GEOCODING_CONFIG

    def update_geocoding_config(self, config: GeocodingConfig) -> bool:
        """Update geocoding configuration"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute('''
                INSERT OR REPLACE INTO system_config (key, value, updated_at)
                VALUES (?, ?, ?)
            ''', ('geocoding_config', self._serialize_json_data(config.to_dict()), datetime.now().isoformat()))

            conn.commit()
            return True

    # Statistics and health
    def get_system_health(self) -> SystemHealth:
        """Get comprehensive system health statistics"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Total properties
            cursor.execute('SELECT COUNT(*) as count FROM properties')
            total_properties = cursor.fetchone()['count']

            # Geocoded properties
            cursor.execute('SELECT COUNT(*) as count FROM properties WHERE geocoded = TRUE')
            geocoded_properties = cursor.fetchone()['count']

            # Failed geocoding
            cursor.execute(
                'SELECT COUNT(*) as count FROM properties WHERE geocoding_attempts >= ? AND geocoded = FALSE',
                (self.get_geocoding_config().max_attempts,))
            failed_geocoding = cursor.fetchone()['count']

            # Pending geocoding
            cursor.execute('SELECT COUNT(*) as count FROM properties WHERE geocoded = FALSE AND geocoding_attempts < ?',
                           (self.get_geocoding_config().max_attempts,))
            pending_geocoding = cursor.fetchone()['count']

            # Last scrape time
            cursor.execute('SELECT MAX(last_updated) as last_update FROM properties')
            last_scrape_str = cursor.fetchone()['last_update']
            last_scrape = datetime.fromisoformat(last_scrape_str) if last_scrape_str else None

            # Last geocoding time
            cursor.execute('SELECT MAX(last_geocoded) as last_geocoded FROM properties WHERE last_geocoded IS NOT NULL')
            last_geocoding_str = cursor.fetchone()['last_geocoded']
            last_geocoding = datetime.fromisoformat(last_geocoding_str) if last_geocoding_str else None

            # Recent errors
            cursor.execute('''
                SELECT COUNT(*) as count FROM system_health 
                WHERE timestamp > ? AND status = 'error'
            ''', ((datetime.now() - timedelta(hours=24)).isoformat(),))
            recent_errors = cursor.fetchone()['count']

            return SystemHealth(
                timestamp=datetime.now(),
                total_properties=total_properties,
                geocoded_properties=geocoded_properties,
                failed_geocoding=failed_geocoding,
                pending_geocoding=pending_geocoding,
                last_scrape=last_scrape,
                last_geocoding=last_geocoding,
                scraping_errors=recent_errors,
                geocoding_errors=failed_geocoding
            )

    def get_category_stats(self) -> List[CategoryStats]:
        """Get statistics by category"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute('''
                SELECT 
                    sub_category,
                    COUNT(*) as total_count,
                    SUM(CASE WHEN geocoded = TRUE THEN 1 ELSE 0 END) as geocoded_count,
                    AVG(opening_value) as avg_price,
                    MIN(opening_value) as min_price,
                    MAX(opening_value) as max_price,
                    MAX(last_updated) as latest_update
                FROM properties 
                WHERE sub_category IS NOT NULL
                GROUP BY sub_category
                ORDER BY total_count DESC
            ''')

            stats = []
            for row in cursor.fetchall():
                stats.append(CategoryStats(
                    category=row['sub_category'],
                    total_count=row['total_count'],
                    geocoded_count=row['geocoded_count'],
                    avg_price=row['avg_price'],
                    min_price=row['min_price'],
                    max_price=row['max_price'],
                    latest_update=datetime.fromisoformat(row['latest_update']) if row['latest_update'] else None
                ))

            return stats

    # Utility methods
    def cleanup_old_auctions(self, grace_days: int = 2) -> int:
        """Remove auctions closed for more than grace_days"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            cutoff_date = (datetime.now() - timedelta(days=grace_days)).isoformat()

            cursor.execute('''
                DELETE FROM properties 
                WHERE start_auction_at < ? AND auction_closed = FALSE
            ''', (cutoff_date,))

            deleted_count = cursor.rowcount
            conn.commit()

            logger.info(f"Cleaned up {deleted_count} old auction properties")
            return deleted_count

    def log_health_event(self, component: str, status: str, message: str, data: Optional[Any] = None):
        """Log health event with proper JSON serialization"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Serialize data safely
            serialized_data = self._serialize_json_data(data) if data is not None else None

            cursor.execute('''
                INSERT INTO system_health (component, status, message, data)
                VALUES (?, ?, ?, ?)
            ''', (component, status, message, serialized_data))

            conn.commit()

    def update_service_status(self, service_name: str, status_data: Dict[str, Any]):
        """Update service status information"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Create service_status table if it doesn't exist
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS service_status (
                    service_name TEXT PRIMARY KEY,
                    status_data TEXT,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            cursor.execute('''
                INSERT OR REPLACE INTO service_status (service_name, status_data, last_updated)
                VALUES (?, ?, ?)
            ''', (service_name, self._serialize_json_data(status_data), datetime.now().isoformat()))
            
            conn.commit()

    def get_service_status(self, service_name: str) -> Optional[Dict[str, Any]]:
        """Get service status information"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Check if table exists
            cursor.execute('''
                SELECT name FROM sqlite_master WHERE type='table' AND name='service_status'
            ''')
            if not cursor.fetchone():
                return None
                
            cursor.execute('''
                SELECT status_data, last_updated FROM service_status 
                WHERE service_name = ?
            ''', (service_name,))
            
            result = cursor.fetchone()
            if result:
                try:
                    status_data = json.loads(result['status_data'])
                    status_data['last_status_update'] = result['last_updated']
                    return status_data
                except (json.JSONDecodeError, TypeError):
                    return None
            return None
