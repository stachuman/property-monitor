#!/usr/bin/env python3
"""
Data Models and Schemas for Property Monitoring System
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum
import json


class PropertyStatus(Enum):
    """Property auction status"""
    STARTING = "Rozpoczęcie"
    ACTIVE = "Rozpoczęta"
    ENDED = "Zakończona"
    UNKNOWN = "Nieznany"


class GeocodingStatus(Enum):
    """Geocoding status"""
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    MANUAL = "manual"

@dataclass
class WatchedProperty:
    """Watched property model"""
    id: int
    property_id: int
    notes: str = ""
    watched_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'property_id': self.property_id,
            'notes': self.notes,
            'watched_at': self.watched_at.isoformat() if self.watched_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


@dataclass
class Property:
    """Property model"""
    id: int
    title: str
    city: str
    main_category: str
    sub_category: str
    estimate: Optional[float] = None
    opening_value: Optional[float] = None
    margin: Optional[float] = None
    is_margin_required: Optional[bool] = None
    start_auction_at: Optional[str] = None
    margin_due_date: Optional[str] = None
    date_created: Optional[str] = None
    status: Optional[str] = None
    bailiff_office: Optional[str] = None
    main_photo_base64: Optional[str] = None
    explanation: Optional[str] = None

    # Land-specific fields
    land_area_m2: Optional[float] = None
    land_area_ha: Optional[float] = None
    land_type: Optional[str] = None
    utilities: Optional[List[str]] = None
    ownership_form: Optional[str] = None
    ownership_share: Optional[str] = None

    # Geocoding fields
    geocoded: bool = False
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    geocoding_source: Optional[str] = None
    geocoding_attempts: int = 0
    last_geocoded: Optional[datetime] = None

    # System fields
    first_seen: Optional[datetime] = None
    last_updated: Optional[datetime] = None
    auction_closed: bool = False

    @property
    def property_url(self) -> str:
        """Generate direct URL to property on elicytacje.komornik.pl"""
        if not self.title:
            return f"https://elicytacje.komornik.pl/items/{self.id}"

        # Create URL-safe slug from title
        slug = self.title.lower()
        slug = slug.replace(" ", "-").replace(",", "").replace(".", "")
        slug = "".join(c for c in slug if c.isalnum() or c in "-")

        return f"https://elicytacje.komornik.pl/items/{self.id}/{slug}"

    @property
    def status_enum(self) -> PropertyStatus:
        """Get property status as enum"""
        try:
            return PropertyStatus(self.status)
        except (ValueError, TypeError):
            return PropertyStatus.UNKNOWN

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'title': self.title,
            'city': self.city,
            'main_category': self.main_category,
            'sub_category': self.sub_category,
            'estimate': self.estimate,
            'opening_value': self.opening_value,
            'margin': self.margin,
            'is_margin_required': self.is_margin_required,
            'start_auction_at': self.start_auction_at,
            'margin_due_date': self.margin_due_date,
            'date_created': self.date_created,
            'status': self.status,
            'bailiff_office': self.bailiff_office,
            'explanation': self.explanation,
            'land_area_m2': self.land_area_m2,
            'land_area_ha': self.land_area_ha,
            'land_type': self.land_type,
            'utilities': self.utilities,
            'ownership_form': self.ownership_form,
            'ownership_share': self.ownership_share,
            'geocoded': self.geocoded,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'geocoding_source': self.geocoding_source,
            'geocoding_attempts': self.geocoding_attempts,
            'last_geocoded': self.last_geocoded.isoformat() if self.last_geocoded else None,
            'first_seen': self.first_seen.isoformat() if self.first_seen else None,
            'last_updated': self.last_updated.isoformat() if self.last_updated else None,
            'auction_closed': self.auction_closed,
            'property_url': self.property_url
        }


@dataclass
class GeocodingCache:
    """Geocoding cache entry"""
    city_key: str
    latitude: Optional[float]
    longitude: Optional[float]
    source: str
    success: bool
    created_at: datetime


@dataclass
class ScrapingConfig:
    """Scraping configuration"""
    category: str
    enabled: bool = True
    max_pages: Optional[int] = None
    delay_seconds: float = 2.0
    priority: int = 1
    last_run: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'category': self.category,
            'enabled': self.enabled,
            'max_pages': self.max_pages,
            'delay_seconds': self.delay_seconds,
            'priority': self.priority,
            'last_run': self.last_run.isoformat() if self.last_run else None
        }


@dataclass
class GeocodingConfig:
    """Geocoding configuration"""
    batch_size: int = 50
    delay_seconds: float = 1.1
    max_attempts: int = 3
    retry_failed_after_hours: int = 24
    enabled: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            'batch_size': self.batch_size,
            'delay_seconds': self.delay_seconds,
            'max_attempts': self.max_attempts,
            'retry_failed_after_hours': self.retry_failed_after_hours,
            'enabled': self.enabled
        }


@dataclass
class SystemHealth:
    """System health status"""
    timestamp: datetime
    total_properties: int = 0
    geocoded_properties: int = 0
    failed_geocoding: int = 0
    pending_geocoding: int = 0
    last_scrape: Optional[datetime] = None
    last_geocoding: Optional[datetime] = None
    scraping_errors: int = 0
    geocoding_errors: int = 0

    @property
    def geocoding_percentage(self) -> float:
        """Calculate geocoding completion percentage"""
        if self.total_properties == 0:
            return 0.0
        return (self.geocoded_properties / self.total_properties) * 100

    @property
    def health_status(self) -> str:
        """Determine overall health status"""
        if self.total_properties == 0:
            return "warning"
        if self.scraping_errors > 10 or self.geocoding_errors > 50:
            return "error"
        if self.geocoding_percentage < 80:
            return "warning"
        return "healthy"

    def to_dict(self) -> Dict[str, Any]:
        return {
            'timestamp': self.timestamp.isoformat(),
            'total_properties': self.total_properties,
            'geocoded_properties': self.geocoded_properties,
            'failed_geocoding': self.failed_geocoding,
            'pending_geocoding': self.pending_geocoding,
            'geocoding_percentage': round(self.geocoding_percentage, 1),
            'health_status': self.health_status,
            'last_scrape': self.last_scrape.isoformat() if self.last_scrape else None,
            'last_geocoding': self.last_geocoding.isoformat() if self.last_geocoding else None,
            'scraping_errors': self.scraping_errors,
            'geocoding_errors': self.geocoding_errors
        }


@dataclass
class CategoryStats:
    """Statistics for property category"""
    category: str
    total_count: int
    geocoded_count: int
    avg_price: Optional[float]
    min_price: Optional[float]
    max_price: Optional[float]
    latest_update: Optional[datetime]

    @property
    def geocoding_percentage(self) -> float:
        if self.total_count == 0:
            return 0.0
        return (self.geocoded_count / self.total_count) * 100

    def to_dict(self) -> Dict[str, Any]:
        return {
            'category': self.category,
            'total_count': self.total_count,
            'geocoded_count': self.geocoded_count,
            'geocoding_percentage': round(self.geocoding_percentage, 1),
            'avg_price': self.avg_price,
            'min_price': self.min_price,
            'max_price': self.max_price,
            'latest_update': self.latest_update.isoformat() if self.latest_update else None
        }


@dataclass
class FailedGeocoding:
    """Failed geocoding entry for manual review"""
    id: int
    property_id: int
    city: str
    property_title: str
    attempts: int
    last_attempt: datetime
    error_message: Optional[str] = None
    suggested_latitude: Optional[float] = None
    suggested_longitude: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'property_id': self.property_id,
            'city': self.city,
            'property_title': self.property_title,
            'attempts': self.attempts,
            'last_attempt': self.last_attempt.isoformat(),
            'error_message': self.error_message,
            'suggested_latitude': self.suggested_latitude,
            'suggested_longitude': self.suggested_longitude
        }


# API Response Models
@dataclass
class ApiResponse:
    """Standard API response"""
    success: bool
    message: str
    data: Optional[Any] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        response = {
            'success': self.success,
            'message': self.message
        }
        if self.data is not None:
            response['data'] = self.data
        if self.error is not None:
            response['error'] = self.error
        return response


# Constants
DEFAULT_SCRAPING_CATEGORIES = [
    ScrapingConfig("grunty", enabled=True, max_pages=100, priority=1),
    ScrapingConfig("domy", enabled=True, max_pages=100, priority=3),
    ScrapingConfig("inne", enabled=True, max_pages=100, priority=2)
]

DEFAULT_GEOCODING_CONFIG = GeocodingConfig(
    batch_size=50,
    delay_seconds=1.1,
    max_attempts=3,
    retry_failed_after_hours=24,
    enabled=True
)
