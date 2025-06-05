#!/usr/bin/env python3
"""
Configuration Management for Property Monitoring System - Updated version
"""

import os
import json
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from pathlib import Path


@dataclass
class DatabaseConfig:
    """Database configuration"""
    path: str = "/var/lib/property_monitor/properties.db"
    backup_path: str = "/var/lib/property_monitor/backups"
    backup_retention_days: int = 30

    def __post_init__(self):
        # Ensure directories exist
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        os.makedirs(self.backup_path, exist_ok=True)


@dataclass
class LoggingConfig:
    """Logging configuration"""
    level: str = "INFO"
    file_path: str = "/var/log/property_monitor"
    max_file_size: str = "10MB"
    backup_count: int = 5
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    def __post_init__(self):
        # Ensure log directory exists
        os.makedirs(self.file_path, exist_ok=True)

    @property
    def log_file(self) -> str:
        return os.path.join(self.file_path, "property_monitor.log")


@dataclass
class ScrapingApiConfig:
    """Enhanced scraping API configuration"""
    base_url: str = "https://elicytacje.komornik.pl"
    api_endpoint: str = "/services/item-back/rest/item/search"
    timeout: int = 30
    retry_attempts: int = 3
    retry_delay: float = 5.0
    user_agent: str = "PropertyMonitorBot/1.0"
    
    # Connection settings
    max_connections: int = 10
    keep_alive: bool = True
    
    # Rate limiting
    requests_per_minute: int = 30
    burst_requests: int = 5

    @property
    def api_url(self) -> str:
        return f"{self.base_url}{self.api_endpoint}"

    @property
    def headers(self) -> Dict[str, str]:
        return {
            'User-Agent': self.user_agent,
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Accept-Language': 'pl-PL,pl;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive' if self.keep_alive else 'close',
            'Referer': f'{self.base_url}/',
            'Cache-Control': 'no-cache'
        }


@dataclass
class GeocodingApiConfig:
    """Geocoding API configuration"""
    service: str = "nominatim"  # nominatim, google, mapbox
    nominatim_url: str = "https://nominatim.openstreetmap.org"
    timeout: int = 10
    retry_attempts: int = 2
    retry_delay: float = 1.0
    user_agent: str = "PropertyMonitor/1.0"
    
    # Poland-specific settings
    restrict_to_poland: bool = True
    country_codes: List[str] = None
    language: str = "pl"
    
    # Fuzzy search settings
    enable_fuzzy_search: bool = True
    similarity_threshold: float = 0.8

    def __post_init__(self):
        if self.country_codes is None:
            self.country_codes = ['PL']



@dataclass
class ServiceConfig:
    """Service scheduling configuration"""
    scraping_time: str = "06:00"  # Daily scraping time
    geocoding_interval_minutes: int = 60  # Geocoding every hour
    cleanup_time: str = "02:00"  # Daily cleanup time
    health_check_interval_minutes: int = 5  # Health check interval

    # Service management
    enable_auto_restart: bool = True
    max_restart_attempts: int = 3
    restart_delay_seconds: int = 30
    
    # Performance monitoring
    memory_limit_mb: int = 1024
    cpu_threshold: float = 80.0
    disk_threshold: float = 85.0

@dataclass
class WebServerConfig:
    """Web server configuration"""
    host: str = "0.0.0.0"
    port: int = 80
    admin_port: int = 8080
    debug: bool = False
    secret_key: Optional[str] = None
    
    # NEW: Server public configuration
    server_name: Optional[str] = None  # e.g., "property-monitor.example.com"
    server_protocol: str = "http"      # "http" or "https"
    admin_subdomain: Optional[str] = None  # e.g., "admin" for admin.example.com
    
    # Security settings
    max_content_length: int = 16 * 1024 * 1024  # 16MB
    session_timeout: int = 3600  # 1 hour
    
    # Performance settings
    threaded: bool = True
    processes: int = 1

    def __post_init__(self):
        if not self.secret_key:
            self.secret_key = os.urandom(24).hex()
    
    @property
    def public_url(self) -> str:
        """Get the public URL for the main interface"""
        if self.server_name:
            return f"{self.server_protocol}://{self.server_name}"
        else:
            # Fallback to localhost for development
            port_suffix = f":{self.port}" if self.port != 80 else ""
            return f"http://localhost{port_suffix}"
    
    @property
    def admin_url(self) -> str:
        """Get the admin URL"""
        if self.server_name:
            if self.admin_subdomain:
                return f"{self.server_protocol}://{self.admin_subdomain}.{self.server_name}"
            else:
                port_suffix = f":{self.admin_port}" if self.admin_port != 80 else ""
                return f"{self.server_protocol}://{self.server_name}{port_suffix}"
        else:
            # Fallback to localhost for development
            return f"http://localhost:{self.admin_port}"

@dataclass
class MonitoringConfig:
    """System monitoring configuration"""
    enable_health_monitoring: bool = True
    
    # NEW: Dynamic health check URL
    health_check_url: Optional[str] = None  # Will be auto-generated if None
    
    # Alerting
    enable_email_alerts: bool = False
    email_smtp_server: str = ""
    email_smtp_port: int = 587
    email_username: str = ""
    email_password: str = ""
    email_recipients: List[str] = None
    
    # Metrics retention
    metrics_retention_days: int = 30
    
    def __post_init__(self):
        if self.email_recipients is None:
            self.email_recipients = []

@dataclass
class SystemConfig:
    """Main system configuration"""
    environment: str = "production"  # production, development, testing
    database: DatabaseConfig = None
    logging: LoggingConfig = None
    scraping_api: ScrapingApiConfig = None
    geocoding_api: GeocodingApiConfig = None
    web_server: WebServerConfig = None
    service: ServiceConfig = None
    monitoring: MonitoringConfig = None

    def __post_init__(self):
        if self.database is None:
            self.database = DatabaseConfig()
        if self.logging is None:
            self.logging = LoggingConfig()
        if self.scraping_api is None:
            self.scraping_api = ScrapingApiConfig()
        if self.geocoding_api is None:
            self.geocoding_api = GeocodingApiConfig()
        if self.web_server is None:
            self.web_server = WebServerConfig()
        if self.service is None:
            self.service = ServiceConfig()
        if self.monitoring is None:
            self.monitoring = MonitoringConfig()

    @classmethod
    def from_file(cls, config_path: str) -> 'SystemConfig':
        """Load configuration from JSON file"""
        if not os.path.exists(config_path):
            # Create default config file
            default_config = cls()
            default_config.save_to_file(config_path)
            return default_config

        with open(config_path, 'r') as f:
            config_data = json.load(f)

        return cls(
            environment=config_data.get('environment', 'production'),
            database=DatabaseConfig(**config_data.get('database', {})),
            logging=LoggingConfig(**config_data.get('logging', {})),
            scraping_api=ScrapingApiConfig(**config_data.get('scraping_api', {})),
            geocoding_api=GeocodingApiConfig(**config_data.get('geocoding_api', {})),
            web_server=WebServerConfig(**config_data.get('web_server', {})),
            service=ServiceConfig(**config_data.get('service', {})),
            monitoring=MonitoringConfig(**config_data.get('monitoring', {}))
        )

    def save_to_file(self, config_path: str):
        """Save configuration to JSON file"""
        config_data = {
            'environment': self.environment,
            'database': self.database.__dict__,
            'logging': self.logging.__dict__,
            'scraping_api': self.scraping_api.__dict__,
            'geocoding_api': self.geocoding_api.__dict__,
            'web_server': self.web_server.__dict__,
            'service': self.service.__dict__,
            'monitoring': self.monitoring.__dict__
        }

        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        with open(config_path, 'w') as f:
            json.dump(config_data, f, indent=2)

    def setup_logging(self):
        """Setup logging based on configuration"""
        log_level = getattr(logging, self.logging.level.upper())

        # Create formatters
        formatter = logging.Formatter(self.logging.format)

        # Setup file handler with rotation
        from logging.handlers import RotatingFileHandler
        file_handler = RotatingFileHandler(
            self.logging.log_file,
            maxBytes=self._parse_size(self.logging.max_file_size),
            backupCount=self.logging.backup_count
        )
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)

        # Setup console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(log_level)
        console_handler.setFormatter(formatter)

        # Configure root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(log_level)
        
        # Clear existing handlers
        root_logger.handlers.clear()
        
        root_logger.addHandler(file_handler)
        root_logger.addHandler(console_handler)

        # Reduce noise from external libraries
        logging.getLogger('urllib3').setLevel(logging.WARNING)
        logging.getLogger('requests').setLevel(logging.WARNING)
        logging.getLogger('schedule').setLevel(logging.WARNING)

    def _parse_size(self, size_str: str) -> int:
        """Parse size string like '10MB' to bytes"""
        size_str = size_str.upper()
        if size_str.endswith('KB'):
            return int(size_str[:-2]) * 1024
        elif size_str.endswith('MB'):
            return int(size_str[:-2]) * 1024 * 1024
        elif size_str.endswith('GB'):
            return int(size_str[:-2]) * 1024 * 1024 * 1024
        else:
            return int(size_str)


# Default configuration paths
DEFAULT_CONFIG_PATH = "/opt/property-monitor/config.json"
DEVELOPMENT_CONFIG_PATH = "./config.json"


class ConfigManager:
    """Configuration manager singleton"""

    _instance = None
    _config = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def load_config(self, config_path: Optional[str] = None) -> SystemConfig:
        """Load system configuration"""
        if self._config is not None:
            return self._config

        if config_path is None:
            # Auto-detect config path
            if os.path.exists(DEFAULT_CONFIG_PATH):
                config_path = DEFAULT_CONFIG_PATH
            elif os.path.exists(DEVELOPMENT_CONFIG_PATH):
                config_path = DEVELOPMENT_CONFIG_PATH
            else:
                config_path = DEFAULT_CONFIG_PATH

        self._config = SystemConfig.from_file(config_path)
        return self._config

    def get_config(self) -> SystemConfig:
        """Get current configuration"""
        if self._config is None:
            return self.load_config()
        return self._config

    def reload_config(self, config_path: Optional[str] = None):
        """Reload configuration"""
        self._config = None
        return self.load_config(config_path)


# Utility functions
def get_config() -> SystemConfig:
    """Get system configuration"""
    return ConfigManager().get_config()


def setup_logging():
    """Setup logging with current configuration"""
    config = get_config()
    config.setup_logging()


def get_env_var(key: str, default: Any = None, var_type: type = str) -> Any:
    """Get environment variable with type conversion"""
    value = os.environ.get(key, default)

    if value is None or value == default:
        return default

    try:
        if var_type == bool:
            return value.lower() in ('true', '1', 'yes', 'on')
        elif var_type == int:
            return int(value)
        elif var_type == float:
            return float(value)
        else:
            return var_type(value)
    except (ValueError, TypeError):
        return default


# Environment-specific configurations
def get_development_config() -> SystemConfig:
    """Get development configuration"""
    config = SystemConfig()
    config.environment = "development"
    config.web_server.debug = True
    config.web_server.port = 5000
    config.web_server.admin_port = 5001
    config.database.path = "./data/properties.db"
    config.logging.level = "DEBUG"
    config.logging.file_path = "./logs"
    config.scraping_api.requests_per_minute = 60  # Higher rate for development
    config.geocoding_api.retry_attempts = 1  # Faster for development
    return config


def get_testing_config() -> SystemConfig:
    """Get testing configuration"""
    config = SystemConfig()
    config.environment = "testing"
    config.database.path = ":memory:"  # In-memory database for tests
    config.logging.level = "WARNING"
    config.service.scraping_time = "00:00"  # Disable scheduled scraping
    config.service.geocoding_interval_minutes = 0  # Disable scheduled geocoding
    config.scraping_api.timeout = 5  # Faster timeouts for tests
    config.geocoding_api.timeout = 5
    return config

def get_production_config() -> SystemConfig:
    """Get production configuration with environment overrides"""
    config = SystemConfig()
    config.environment = "production"

    # Allow environment variable overrides
    config.web_server.host = get_env_var("FLASK_HOST", config.web_server.host)
    config.web_server.port = get_env_var("FLASK_PORT", config.web_server.port, int)
    config.web_server.admin_port = get_env_var("ADMIN_PORT", config.web_server.admin_port, int)
    config.web_server.debug = get_env_var("FLASK_DEBUG", config.web_server.debug, bool)
    
    # NEW: Server configuration from environment
    config.web_server.server_name = get_env_var("SERVER_NAME", config.web_server.server_name)
    config.web_server.server_protocol = get_env_var("SERVER_PROTOCOL", config.web_server.server_protocol)
    config.web_server.admin_subdomain = get_env_var("ADMIN_SUBDOMAIN", config.web_server.admin_subdomain)

    config.database.path = get_env_var("DATABASE_PATH", config.database.path)
    config.logging.level = get_env_var("LOG_LEVEL", config.logging.level)
    config.logging.file_path = get_env_var("LOG_PATH", config.logging.file_path)

    # Monitoring settings
    config.monitoring.enable_email_alerts = get_env_var("ENABLE_EMAIL_ALERTS", False, bool)
    config.monitoring.email_smtp_server = get_env_var("SMTP_SERVER", config.monitoring.email_smtp_server)
    config.monitoring.email_username = get_env_var("SMTP_USERNAME", config.monitoring.email_username)
    config.monitoring.email_password = get_env_var("SMTP_PASSWORD", config.monitoring.email_password)
    
    # Auto-generate health check URL if not provided
    if not config.monitoring.health_check_url:
        config.monitoring.health_check_url = f"{config.web_server.public_url}/api/health"

    return config


# Configuration validation
def validate_config(config: SystemConfig) -> List[str]:
    """Validate configuration and return list of errors"""
    errors = []

    # Validate database path
    try:
        if config.database.path != ":memory:":
            os.makedirs(os.path.dirname(config.database.path), exist_ok=True)
    except PermissionError:
        errors.append(f"No write permission for database path: {config.database.path}")

    # Validate log path
    try:
        os.makedirs(config.logging.file_path, exist_ok=True)
    except PermissionError:
        errors.append(f"No write permission for log path: {config.logging.file_path}")

    # Validate ports
    if not (1 <= config.web_server.port <= 65535):
        errors.append(f"Invalid web server port: {config.web_server.port}")

    if not (1 <= config.web_server.admin_port <= 65535):
        errors.append(f"Invalid admin port: {config.web_server.admin_port}")

    if config.web_server.port == config.web_server.admin_port:
        errors.append("Web server and admin ports cannot be the same")

    # Validate logging level
    valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
    if config.logging.level.upper() not in valid_levels:
        errors.append(f"Invalid logging level: {config.logging.level}")

    # Validate scraping API settings
    if config.scraping_api.timeout < 5:
        errors.append("Scraping API timeout should be at least 5 seconds")

    if config.scraping_api.requests_per_minute > 120:
        errors.append("Scraping requests per minute should not exceed 120 to be respectful")

    # Validate geocoding settings
    if config.geocoding_api.timeout < 5:
        errors.append("Geocoding API timeout should be at least 5 seconds")

    if config.geocoding_api.similarity_threshold < 0.5 or config.geocoding_api.similarity_threshold > 1.0:
        errors.append("Geocoding similarity threshold should be between 0.5 and 1.0")

    # Validate service settings
    if config.service.max_restart_attempts < 0 or config.service.max_restart_attempts > 10:
        errors.append("Max restart attempts should be between 0 and 10")

    if config.service.restart_delay_seconds < 1 or config.service.restart_delay_seconds > 300:
        errors.append("Restart delay should be between 1 and 300 seconds")

    return errors
