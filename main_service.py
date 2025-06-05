#!/usr/bin/env python3
"""
Main Service - Alternative version with improved multiprocessing support
"""

import os
import sys
import time
import signal
import logging
import threading
import subprocess
from typing import Dict, List, Optional
from dataclasses import dataclass

from config import get_config, setup_logging, validate_config
from database import DatabaseManager

logger = logging.getLogger(__name__)


@dataclass
class ServiceProcess:
    """Information about a running service process"""
    name: str
    process: Optional[subprocess.Popen] = None
    enabled: bool = True
    restart_count: int = 0
    last_restart: Optional[float] = None


class PropertyMonitorOrchestrator:
    """Main orchestrator using subprocess instead of multiprocessing"""

    def __init__(self):
        self.config = get_config()
        self.db = DatabaseManager()
        self.services = {}
        self.running = False
        self._monitor_thread = None
        self._setup_services()

    def _setup_services(self):
        """Setup service configurations"""
        self.services = {
            'scraping': ServiceProcess('scraping', enabled=True),
            'geocoding': ServiceProcess('geocoding', enabled=True),
            'web': ServiceProcess('web', enabled=True),
            'admin': ServiceProcess('admin', enabled=True)
        }

    def start_all_services(self):
        """Start all enabled services"""
        logger.info("Starting Property Monitor Orchestrator")
        self.running = True

        # Validate configuration first
        config_errors = validate_config(self.config)
        if config_errors:
            logger.error("Configuration validation failed:")
            for error in config_errors:
                logger.error(f"  - {error}")
            return False

        # Log startup event
        self.db.log_health_event(
            component="orchestrator",
            status="success",
            message="Starting Property Monitor Orchestrator",
            data={
                "config_environment": self.config.environment,
                "services_to_start": [name for name, service in self.services.items() if service.enabled]
            }
        )

        # Start individual services
        try:
            startup_success = True

            if self.services['scraping'].enabled:
                if not self._start_scraping_service():
                    startup_success = False

            if self.services['geocoding'].enabled:
                if not self._start_geocoding_service():
                    startup_success = False

            if self.services['web'].enabled:
                if not self._start_web_service():
                    startup_success = False

            if self.services['admin'].enabled:
                if not self._start_admin_service():
                    startup_success = False

            if not startup_success:
                logger.error("Some services failed to start")
                self.stop_all_services()
                return False

            # Setup signal handlers
            signal.signal(signal.SIGINT, self._signal_handler)
            signal.signal(signal.SIGTERM, self._signal_handler)

            # Start monitoring thread
            self._monitor_thread = threading.Thread(target=self.monitor_services, daemon=True, name="ServiceMonitor")
            self._monitor_thread.start()

            logger.info("All services started successfully")
            self.db.log_health_event(
                component="orchestrator",
                status="success",
                message="All services started successfully",
                data=self.get_service_status()
            )
            return True

        except Exception as e:
            logger.error(f"Failed to start services: {e}")
            self.db.log_health_event(
                component="orchestrator",
                status="error",
                message=f"Failed to start services: {str(e)}"
            )
            self.stop_all_services()
            return False

    def _get_python_executable(self) -> str:
        """Get the Python executable path"""
        # Try to use the same Python executable that's running this script
        return sys.executable

    def _get_service_command(self, service_name: str) -> List[str]:
        """Get the command to start a specific service"""
        python_exe = self._get_python_executable()
        base_path = os.path.dirname(os.path.abspath(__file__))
        
        service_commands = {
            'scraping': [python_exe, os.path.join(base_path, 'property_scraper_service.py'), 'daemon'],
            'geocoding': [python_exe, os.path.join(base_path, 'geocoding_service.py'), 'daemon'],
            'web': [python_exe, os.path.join(base_path, 'web_service.py')],
            'admin': [python_exe, os.path.join(base_path, 'admin_service.py')]
        }
        
        return service_commands.get(service_name, [])

    def _start_scraping_service(self) -> bool:
        """Start scraping service as subprocess"""
        try:
            cmd = self._get_service_command('scraping')
            if not cmd:
                logger.error("No command defined for scraping service")
                return False

            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=os.environ.copy()
            )

            # Give the process a moment to start
            time.sleep(3)

            if process.poll() is None:  # Process is still running
                self.services['scraping'].process = process
                logger.info(f"Scraping service started successfully (PID: {process.pid})")
                return True
            else:
                stdout, stderr = process.communicate()
                logger.error(f"Scraping service failed to start: {stderr.decode()}")
                return False

        except Exception as e:
            logger.error(f"Failed to start scraping service: {e}")
            return False

    def _start_geocoding_service(self) -> bool:
        """Start geocoding service as subprocess"""
        try:
            cmd = self._get_service_command('geocoding')
            if not cmd:
                logger.error("No command defined for geocoding service")
                return False

            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=os.environ.copy()
            )

            # Give the process a moment to start
            time.sleep(3)

            if process.poll() is None:  # Process is still running
                self.services['geocoding'].process = process
                logger.info(f"Geocoding service started successfully (PID: {process.pid})")
                return True
            else:
                stdout, stderr = process.communicate()
                logger.error(f"Geocoding service failed to start: {stderr.decode()}")
                return False

        except Exception as e:
            logger.error(f"Failed to start geocoding service: {e}")
            return False

    def _start_web_service(self) -> bool:
        """Start web service as subprocess"""
        try:
            cmd = self._get_service_command('web')
            if not cmd:
                logger.error("No command defined for web service")
                return False

            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=os.environ.copy()
            )

            # Give the process a moment to start
            time.sleep(3)

            if process.poll() is None:  # Process is still running
                self.services['web'].process = process
                logger.info(f"Web service started successfully (PID: {process.pid}) on port {self.config.web_server.port}")
                return True
            else:
                stdout, stderr = process.communicate()
                logger.error(f"Web service failed to start: {stderr.decode()}")
                return False

        except Exception as e:
            logger.error(f"Failed to start web service: {e}")
            return False

    def _start_admin_service(self) -> bool:
        """Start admin service as subprocess"""
        try:
            cmd = self._get_service_command('admin')
            if not cmd:
                logger.error("No command defined for admin service")
                return False

            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=os.environ.copy()
            )

            # Give the process a moment to start
            time.sleep(3)

            if process.poll() is None:  # Process is still running
                self.services['admin'].process = process
                logger.info(f"Admin service started successfully (PID: {process.pid}) on port {self.config.web_server.admin_port}")
                return True
            else:
                stdout, stderr = process.communicate()
                logger.error(f"Admin service failed to start: {stderr.decode()}")
                return False

        except Exception as e:
            logger.error(f"Failed to start admin service: {e}")
            return False

    def stop_all_services(self):
        """Stop all running services"""
        logger.info("Stopping all services...")
        self.running = False

        # Stop monitoring thread
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=5)

        # Stop all service processes
        for service_name, service_info in self.services.items():
            if service_info.process and service_info.process.poll() is None:
                logger.info(f"Stopping {service_name} service...")

                try:
                    service_info.process.terminate()
                    
                    # Wait for graceful shutdown
                    try:
                        service_info.process.wait(timeout=15)
                    except subprocess.TimeoutExpired:
                        logger.warning(f"Force killing {service_name} service")
                        service_info.process.kill()
                        service_info.process.wait()

                    logger.info(f"{service_name} service stopped")

                except Exception as e:
                    logger.error(f"Error stopping {service_name} service: {e}")

        logger.info("All services stopped")
        self.db.log_health_event(
            component="orchestrator",
            status="success",
            message="All services stopped"
        )

    def get_service_status(self) -> Dict[str, Dict]:
        """Get status of all services"""
        status = {}

        for service_name, service_info in self.services.items():
            is_running = (service_info.process and 
                         service_info.process.poll() is None)

            status[service_name] = {
                'enabled': service_info.enabled,
                'running': is_running,
                'pid': service_info.process.pid if is_running else None,
                'restart_count': service_info.restart_count,
                'last_restart': service_info.last_restart
            }

        return status

    def restart_service(self, service_name: str) -> bool:
        """Restart a specific service"""
        if service_name not in self.services:
            logger.error(f"Unknown service: {service_name}")
            return False

        service_info = self.services[service_name]

        logger.info(f"Restarting {service_name} service...")

        # Stop the service if running
        if service_info.process and service_info.process.poll() is None:
            logger.info(f"Stopping {service_name} service for restart...")
            service_info.process.terminate()
            
            try:
                service_info.process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                logger.warning(f"Force killing {service_name} service")
                service_info.process.kill()
                service_info.process.wait()

        # Update restart tracking
        service_info.restart_count += 1
        service_info.last_restart = time.time()

        # Restart the service
        try:
            success = False
            if service_name == 'scraping':
                success = self._start_scraping_service()
            elif service_name == 'geocoding':
                success = self._start_geocoding_service()
            elif service_name == 'web':
                success = self._start_web_service()
            elif service_name == 'admin':
                success = self._start_admin_service()

            if success:
                logger.info(f"Service {service_name} restarted successfully")
                self.db.log_health_event(
                    component="orchestrator",
                    status="success",
                    message=f"Service {service_name} restarted successfully",
                    data={"restart_count": service_info.restart_count}
                )
                return True
            else:
                logger.error(f"Failed to restart {service_name} service")
                self.db.log_health_event(
                    component="orchestrator",
                    status="error",
                    message=f"Failed to restart {service_name} service"
                )
                return False

        except Exception as e:
            logger.error(f"Failed to restart {service_name} service: {e}")
            self.db.log_health_event(
                component="orchestrator",
                status="error",
                message=f"Failed to restart {service_name} service: {str(e)}"
            )
            return False

    def monitor_services(self):
        """Monitor services and restart if needed with improved logic"""
        logger.info("Service monitoring started")
        
        while self.running:
            try:
                # Check each service
                for service_name, service_info in self.services.items():
                    if not service_info.enabled:
                        continue

                    # Check if process is still alive
                    if service_info.process and service_info.process.poll() is not None:
                        logger.warning(f"Service {service_name} has stopped unexpectedly (exit code: {service_info.process.returncode})")

                        # Check restart limits and conditions
                        should_restart = (
                            self.config.service.enable_auto_restart and
                            service_info.restart_count < self.config.service.max_restart_attempts
                        )

                        # Check if enough time has passed since last restart
                        if service_info.last_restart:
                            time_since_restart = time.time() - service_info.last_restart
                            if time_since_restart < self.config.service.restart_delay_seconds * 2:
                                should_restart = False
                                logger.warning(f"Service {service_name} restarted too recently, waiting...")

                        if should_restart:
                            logger.info(f"Attempting to restart {service_name} service")
                            time.sleep(self.config.service.restart_delay_seconds)

                            if self.restart_service(service_name):
                                logger.info(f"Service {service_name} restarted successfully")
                            else:
                                logger.error(f"Failed to restart {service_name} service")
                        else:
                            reason = "auto-restart disabled" if not self.config.service.enable_auto_restart else "restart limit exceeded"
                            logger.error(f"Service {service_name} not restarted: {reason}")
                            
                            self.db.log_health_event(
                                component="orchestrator",
                                status="error",
                                message=f"Service {service_name} failed and not restarted: {reason}",
                                data={
                                    "restart_count": service_info.restart_count,
                                    "max_attempts": self.config.service.max_restart_attempts
                                }
                            )

                # Log periodic health status
                if hasattr(self, '_last_health_log'):
                    if time.time() - self._last_health_log > 300:  # Every 5 minutes
                        self._log_periodic_health()
                else:
                    self._last_health_log = time.time()

                # Sleep for the monitoring interval
                time.sleep(60)  # Check every minute

            except Exception as e:
                logger.error(f"Service monitoring error: {e}")
                self.db.log_health_event(
                    component="orchestrator",
                    status="error",
                    message=f"Service monitoring error: {str(e)}"
                )
                time.sleep(60)

        logger.info("Service monitoring stopped")

    def _log_periodic_health(self):
        """Log periodic health status"""
        try:
            status = self.get_service_status()
            running_services = sum(1 for s in status.values() if s['running'])
            total_services = len(status)

            self.db.log_health_event(
                component="orchestrator",
                status="success" if running_services == total_services else "warning",
                message=f"Periodic health check: {running_services}/{total_services} services running",
                data=status
            )

            self._last_health_log = time.time()

        except Exception as e:
            logger.error(f"Failed to log periodic health: {e}")

    def run_forever(self):
        """Run orchestrator and monitor services"""
        if not self.start_all_services():
            logger.error("Failed to start services")
            return 1

        try:
            logger.info("Property Monitor Orchestrator is running...")
            logger.info("Services:")
            for service_name, service_info in self.services.items():
                if service_info.enabled and service_info.process:
                    logger.info(f"  - {service_name}: PID {service_info.process.pid}")

            # Keep main process alive
            while self.running:
                time.sleep(5)

                # Check if any critical service has died
                web_alive = (self.services['web'].process and
                             self.services['web'].process.poll() is None)

                if not web_alive and self.services['web'].enabled:
                    logger.error("Critical web service has died")
                    break

        except KeyboardInterrupt:
            logger.info("Received interrupt signal")

        finally:
            self.stop_all_services()

        return 0

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Received signal {signum}, shutting down...")
        self.running = False


def create_systemd_service_file():
    """Create systemd service file for production deployment"""
    service_content = """[Unit]
Description=Property Monitoring System
After=network.target
Wants=network.target

[Service]
Type=simple
User=property-monitor
Group=property-monitor
WorkingDirectory=/opt/property-monitor
ExecStart=/opt/property-monitor/venv/bin/python /opt/property-monitor/main_service.py
Restart=always
RestartSec=10

# Environment
Environment=PYTHONPATH=/opt/property-monitor
Environment=CONFIG_PATH=/opt/property-monitor/config.json

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=property-monitor

# Resource limits
LimitNOFILE=65536
MemoryLimit=1G

[Install]
WantedBy=multi-user.target
"""

    service_file_path = "/etc/systemd/system/property-monitor.service"

    try:
        with open(service_file_path, 'w') as f:
            f.write(service_content)

        print(f"Systemd service file created: {service_file_path}")
        print("To enable and start the service:")
        print("  sudo systemctl daemon-reload")
        print("  sudo systemctl enable property-monitor")
        print("  sudo systemctl start property-monitor")

    except PermissionError:
        print(f"Cannot write to {service_file_path} - run as root or with sudo")
        print("\nService file content:")
        print(service_content)


def print_service_urls():
    """Print URLs for accessing services"""
    config = get_config()

    print("\n=== Service URLs ===")
    print(f"🌐 Public Map Interface: http://localhost:{config.web_server.port}")
    print(f"🛠️ Admin Panel: http://localhost:{config.web_server.admin_port}")
    print(f"📊 Health Check: http://localhost:{config.web_server.port}/api/health")
    print(f"⚙️ Admin API: http://localhost:{config.web_server.admin_port}/api/health")


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Property Monitoring System")
    parser.add_argument('--systemd', action='store_true',
                        help='Create systemd service file')
    parser.add_argument('--status', action='store_true',
                        help='Show service status')
    parser.add_argument('--config-check', action='store_true',
                        help='Validate configuration')
    parser.add_argument('--restart-service', type=str,
                        help='Restart specific service (scraping, geocoding, web, admin)')

    args = parser.parse_args()

    if args.systemd:
        create_systemd_service_file()
        return 0

    setup_logging()

    if args.config_check:
        config = get_config()
        errors = validate_config(config)

        if errors:
            print("❌ Configuration validation failed:")
            for error in errors:
                print(f"  - {error}")
            return 1
        else:
            print("✅ Configuration is valid")
            print_service_urls()
            return 0

    orchestrator = PropertyMonitorOrchestrator()

    if args.status:
        status = orchestrator.get_service_status()

        print("=== Service Status ===")
        for service_name, service_status in status.items():
            status_emoji = "🟢" if service_status['running'] else "🔴"
            enabled_text = "enabled" if service_status['enabled'] else "disabled"

            print(f"{service_name:12}: {status_emoji} {enabled_text}")
            if service_status['running']:
                print(f"{'':15} PID: {service_status['pid']}")
            if service_status['restart_count'] > 0:
                print(f"{'':15} Restarts: {service_status['restart_count']}")

        return 0

    if args.restart_service:
        service_name = args.restart_service
        if service_name not in orchestrator.services:
            print(f"❌ Unknown service: {service_name}")
            print("Available services: scraping, geocoding, web, admin")
            return 1

        print(f"Restarting {service_name} service...")
        if orchestrator.restart_service(service_name):
            print(f"✅ Service {service_name} restarted successfully")
            return 0
        else:
            print(f"❌ Failed to restart service {service_name}")
            return 1

    # Default: Run the orchestrator
    print("🚀 Starting Property Monitoring System...")
    print_service_urls()
    print("\nPress Ctrl+C to stop all services")

    return orchestrator.run_forever()


if __name__ == "__main__":
    sys.exit(main())
