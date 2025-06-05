#!/usr/bin/env python3
"""
Property Monitor - System Monitoring Script
Monitor system health, send alerts, and generate reports
"""

import os
import sys
import time
import json
import psutil
import smtplib
import logging
import requests
import subprocess
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from email.mime.text import MimeText
from email.mime.multipart import MimeMultipart

# Add the application directory to Python path
sys.path.insert(0, '/opt/property-monitor')

from config import get_config
from database import DatabaseManager


class SystemMonitor:
    """System monitoring and alerting"""

    def __init__(self):
        self.config = get_config()
        self.db = DatabaseManager()
        self.alerts = []
        self.metrics = {}

        # Configure logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('/var/log/property_monitor/monitor.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)

    def check_system_health(self) -> Dict[str, Any]:
        """Comprehensive system health check"""
        health_report = {
            'timestamp': datetime.now().isoformat(),
            'overall_status': 'healthy',
            'services': {},
            'performance': {},
            'database': {},
            'network': {},
            'alerts': []
        }

        try:
            # Check services
            health_report['services'] = self._check_services()

            # Check performance metrics
            health_report['performance'] = self._check_performance()

            # Check database health
            health_report['database'] = self._check_database()

            # Check network connectivity
            health_report['network'] = self._check_network()

            # Determine overall status
            health_report['overall_status'] = self._determine_overall_status(health_report)

            # Generate alerts
            health_report['alerts'] = self._generate_alerts(health_report)

        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
            health_report['overall_status'] = 'error'
            health_report['alerts'].append(f"Health check system error: {e}")

        return health_report

    def _check_services(self) -> Dict[str, Any]:
        """Check status of all services"""
        services = {}

        # Check main systemd service
        try:
            result = subprocess.run(
                ['systemctl', 'is-active', 'property-monitor'],
                capture_output=True, text=True
            )
            services['property_monitor'] = {
                'status': result.stdout.strip(),
                'healthy': result.returncode == 0
            }
        except Exception as e:
            services['property_monitor'] = {
                'status': 'error',
                'healthy': False,
                'error': str(e)
            }

        # Check web interfaces
        services['web_interface'] = self._check_web_service('http://localhost/', 'public')
        services['admin_interface'] = self._check_web_service('http://localhost:8080/', 'admin')

        # Check API endpoints
        services['public_api'] = self._check_web_service('http://localhost/api/health', 'api')
        services['admin_api'] = self._check_web_service('http://localhost:8080/api/health', 'api')

        return services

    def _check_web_service(self, url: str, service_type: str) -> Dict[str, Any]:
        """Check web service availability"""
        try:
            response = requests.get(url, timeout=10)
            return {
                'status': 'active',
                'healthy': response.status_code == 200,
                'response_time': response.elapsed.total_seconds(),
                'status_code': response.status_code
            }
        except requests.exceptions.ConnectionError:
            return {
                'status': 'connection_error',
                'healthy': False,
                'error': 'Connection refused'
            }
        except requests.exceptions.Timeout:
            return {
                'status': 'timeout',
                'healthy': False,
                'error': 'Request timeout'
            }
        except Exception as e:
            return {
                'status': 'error',
                'healthy': False,
                'error': str(e)
            }

    def _check_performance(self) -> Dict[str, Any]:
        """Check system performance metrics"""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)

            # Memory usage
            memory = psutil.virtual_memory()

            # Disk usage
            disk = psutil.disk_usage('/opt/property-monitor')
            data_disk = psutil.disk_usage('/var/lib/property_monitor')

            # Process information
            process_info = {}
            try:
                for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
                    if 'python' in proc.info['name'].lower() and 'property' in ' '.join(proc.cmdline()):
                        process_info = {
                            'pid': proc.info['pid'],
                            'cpu_percent': proc.info['cpu_percent'],
                            'memory_percent': proc.info['memory_percent'],
                            'memory_mb': proc.memory_info().rss / 1024 / 1024
                        }
                        break
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

            return {
                'cpu_percent': cpu_percent,
                'memory': {
                    'total_gb': memory.total / 1024 ** 3,
                    'available_gb': memory.available / 1024 ** 3,
                    'percent_used': memory.percent
                },
                'disk': {
                    'app_disk_percent': disk.percent,
                    'data_disk_percent': data_disk.percent,
                    'app_free_gb': disk.free / 1024 ** 3,
                    'data_free_gb': data_disk.free / 1024 ** 3
                },
                'process': process_info,
                'load_average': os.getloadavg() if hasattr(os, 'getloadavg') else None
            }

        except Exception as e:
            self.logger.error(f"Performance check failed: {e}")
            return {'error': str(e)}

    def _check_database(self) -> Dict[str, Any]:
        """Check database health"""
        try:
            health = self.db.get_system_health()

            # Check database file size
            db_path = self.config.database.path
            db_size_mb = os.path.getsize(db_path) / 1024 / 1024 if os.path.exists(db_path) else 0

            # Check backup status
            backup_dir = self.config.database.backup_path
            backup_files = []
            if os.path.exists(backup_dir):
                backup_files = [f for f in os.listdir(backup_dir) if f.endswith('.db.gz')]
                backup_files.sort(reverse=True)

            last_backup = None
            if backup_files:
                backup_path = os.path.join(backup_dir, backup_files[0])
                last_backup = datetime.fromtimestamp(os.path.getmtime(backup_path))

            return {
                'total_properties': health.total_properties,
                'geocoded_properties': health.geocoded_properties,
                'geocoding_percentage': health.geocoding_percentage,
                'failed_geocoding': health.failed_geocoding,
                'last_scrape': health.last_scrape.isoformat() if health.last_scrape else None,
                'last_geocoding': health.last_geocoding.isoformat() if health.last_geocoding else None,
                'database_size_mb': db_size_mb,
                'backup_count': len(backup_files),
                'last_backup': last_backup.isoformat() if last_backup else None
            }

        except Exception as e:
            self.logger.error(f"Database check failed: {e}")
            return {'error': str(e)}

    def _check_network(self) -> Dict[str, Any]:
        """Check network connectivity"""
        network_status = {}

        # Test external connectivity
        test_urls = [
            'https://elicytacje.komornik.pl',
            'https://nominatim.openstreetmap.org',
            'https://www.google.com'
        ]

        for url in test_urls:
            try:
                response = requests.get(url, timeout=10)
                network_status[url] = {
                    'accessible': response.status_code == 200,
                    'response_time': response.elapsed.total_seconds(),
                    'status_code': response.status_code
                }
            except Exception as e:
                network_status[url] = {
                    'accessible': False,
                    'error': str(e)
                }

        return network_status

    def _determine_overall_status(self, health_report: Dict) -> str:
        """Determine overall system health status"""
        # Check for critical service failures
        services = health_report.get('services', {})
        if not services.get('property_monitor', {}).get('healthy', False):
            return 'critical'

        if not services.get('web_interface', {}).get('healthy', False):
            return 'degraded'

        # Check performance thresholds
        performance = health_report.get('performance', {})
        if performance.get('cpu_percent', 0) > 90:
            return 'warning'

        memory = performance.get('memory', {})
        if memory.get('percent_used', 0) > 90:
            return 'warning'

        disk = performance.get('disk', {})
        if disk.get('app_disk_percent', 0) > 90 or disk.get('data_disk_percent', 0) > 90:
            return 'warning'

        # Check database health
        database = health_report.get('database', {})
        if database.get('geocoding_percentage', 0) < 70:
            return 'warning'

        # Check if scraping is recent (within 25 hours)
        last_scrape = database.get('last_scrape')
        if last_scrape:
            last_scrape_time = datetime.fromisoformat(last_scrape)
            if datetime.now() - last_scrape_time > timedelta(hours=25):
                return 'warning'

        return 'healthy'

    def _generate_alerts(self, health_report: Dict) -> List[str]:
        """Generate alerts based on health report"""
        alerts = []

        # Service alerts
        services = health_report.get('services', {})
        for service_name, service_info in services.items():
            if not service_info.get('healthy', False):
                alerts.append(f"Service {service_name} is not healthy: {service_info.get('status', 'unknown')}")

        # Performance alerts
        performance = health_report.get('performance', {})
        if performance.get('cpu_percent', 0) > 80:
            alerts.append(f"High CPU usage: {performance['cpu_percent']:.1f}%")

        memory = performance.get('memory', {})
        if memory.get('percent_used', 0) > 80:
            alerts.append(f"High memory usage: {memory['percent_used']:.1f}%")

        disk = performance.get('disk', {})
        if disk.get('app_disk_percent', 0) > 80:
            alerts.append(f"High app disk usage: {disk['app_disk_percent']:.1f}%")
        if disk.get('data_disk_percent', 0) > 80:
            alerts.append(f"High data disk usage: {disk['data_disk_percent']:.1f}%")

        # Database alerts
        database = health_report.get('database', {})
        if database.get('failed_geocoding', 0) > 100:
            alerts.append(f"High number of failed geocoding: {database['failed_geocoding']}")

        # Backup alerts
        last_backup = database.get('last_backup')
        if not last_backup:
            alerts.append("No database backups found")
        else:
            last_backup_time = datetime.fromisoformat(last_backup)
            if datetime.now() - last_backup_time > timedelta(days=2):
                alerts.append(f"Database backup is old: {last_backup}")

        # Network alerts
        network = health_report.get('network', {})
        for url, status in network.items():
            if not status.get('accessible', False):
                alerts.append(f"Cannot access {url}: {status.get('error', 'unknown error')}")

        return alerts

    def generate_report(self, format_type: str = 'text') -> str:
        """Generate monitoring report"""
        health_report = self.check_system_health()

        if format_type == 'json':
            return json.dumps(health_report, indent=2)
        elif format_type == 'html':
            return self._generate_html_report(health_report)
        else:
            return self._generate_text_report(health_report)

    def _generate_text_report(self, health_report: Dict) -> str:
        """Generate text format report"""
        lines = []
        lines.append("=" * 50)
        lines.append("Property Monitor - System Health Report")
        lines.append("=" * 50)
        lines.append(f"Timestamp: {health_report['timestamp']}")
        lines.append(f"Overall Status: {health_report['overall_status'].upper()}")
        lines.append("")

        # Services
        lines.append("SERVICES:")
        for service, info in health_report.get('services', {}).items():
            status = "✅" if info.get('healthy') else "❌"
            lines.append(f"  {status} {service}: {info.get('status', 'unknown')}")
        lines.append("")

        # Performance
        perf = health_report.get('performance', {})
        lines.append("PERFORMANCE:")
        lines.append(f"  CPU Usage: {perf.get('cpu_percent', 0):.1f}%")
        memory = perf.get('memory', {})
        lines.append(f"  Memory Usage: {memory.get('percent_used', 0):.1f}%")
        disk = perf.get('disk', {})
        lines.append(f"  App Disk Usage: {disk.get('app_disk_percent', 0):.1f}%")
        lines.append(f"  Data Disk Usage: {disk.get('data_disk_percent', 0):.1f}%")
        lines.append("")

        # Database
        db = health_report.get('database', {})
        lines.append("DATABASE:")
        lines.append(f"  Total Properties: {db.get('total_properties', 0):,}")
        lines.append(f"  Geocoded: {db.get('geocoded_properties', 0):,} ({db.get('geocoding_percentage', 0):.1f}%)")
        lines.append(f"  Failed Geocoding: {db.get('failed_geocoding', 0)}")
        lines.append(f"  Database Size: {db.get('database_size_mb', 0):.1f} MB")
        lines.append(f"  Last Scrape: {db.get('last_scrape', 'Never')}")
        lines.append("")

        # Alerts
        alerts = health_report.get('alerts', [])
        if alerts:
            lines.append("ALERTS:")
            for alert in alerts:
                lines.append(f"  ⚠️  {alert}")
        else:
            lines.append("ALERTS: None")

        lines.append("")
        lines.append("=" * 50)

        return "\n".join(lines)

    def _generate_html_report(self, health_report: Dict) -> str:
        """Generate HTML format report"""
        status_colors = {
            'healthy': '#10b981',
            'warning': '#f59e0b',
            'degraded': '#ef4444',
            'critical': '#dc2626'
        }

        overall_status = health_report['overall_status']
        status_color = status_colors.get(overall_status, '#6b7280')

        html = f"""
        <html>
        <head>
            <title>Property Monitor - Health Report</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .header {{ background: {status_color}; color: white; padding: 20px; border-radius: 8px; }}
                .section {{ margin: 20px 0; padding: 15px; border: 1px solid #ddd; border-radius: 8px; }}
                .healthy {{ color: #10b981; }}
                .unhealthy {{ color: #ef4444; }}
                table {{ width: 100%; border-collapse: collapse; }}
                th, td {{ padding: 8px; text-align: left; border-bottom: 1px solid #ddd; }}
                .alert {{ background: #fef3c7; border: 1px solid #f59e0b; padding: 10px; margin: 5px 0; border-radius: 4px; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>Property Monitor - Health Report</h1>
                <p>Status: {overall_status.upper()}</p>
                <p>Generated: {health_report['timestamp']}</p>
            </div>
        """

        # Services section
        html += '<div class="section"><h2>Services</h2><table>'
        for service, info in health_report.get('services', {}).items():
            status_class = 'healthy' if info.get('healthy') else 'unhealthy'
            html += f'<tr><td>{service}</td><td class="{status_class}">{info.get("status", "unknown")}</td></tr>'
        html += '</table></div>'

        # Performance section
        perf = health_report.get('performance', {})
        html += '<div class="section"><h2>Performance</h2><table>'
        html += f'<tr><td>CPU Usage</td><td>{perf.get("cpu_percent", 0):.1f}%</td></tr>'
        memory = perf.get('memory', {})
        html += f'<tr><td>Memory Usage</td><td>{memory.get("percent_used", 0):.1f}%</td></tr>'
        disk = perf.get('disk', {})
        html += f'<tr><td>App Disk Usage</td><td>{disk.get("app_disk_percent", 0):.1f}%</td></tr>'
        html += '</table></div>'

        # Alerts section
        alerts = health_report.get('alerts', [])
        if alerts:
            html += '<div class="section"><h2>Alerts</h2>'
            for alert in alerts:
                html += f'<div class="alert">⚠️ {alert}</div>'
            html += '</div>'

        html += '</body></html>'
        return html

    def save_report(self, filename: str, format_type: str = 'text'):
        """Save monitoring report to file"""
        report = self.generate_report(format_type)

        with open(filename, 'w') as f:
            f.write(report)

        self.logger.info(f"Report saved to {filename}")


def main():
    """Main monitoring script entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Property Monitor - System Monitoring")
    parser.add_argument('--format', choices=['text', 'json', 'html'], default='text',
                        help='Report format')
    parser.add_argument('--output', help='Output file path')
    parser.add_argument('--check-only', action='store_true',
                        help='Only perform health check without generating report')
    parser.add_argument('--alerts-only', action='store_true',
                        help='Only show alerts')

    args = parser.parse_args()

    monitor = SystemMonitor()

    if args.check_only:
        health = monitor.check_system_health()
        print(f"System Status: {health['overall_status'].upper()}")
        if health['alerts']:
            print(f"Alerts: {len(health['alerts'])}")
            for alert in health['alerts']:
                print(f"  - {alert}")
        sys.exit(0 if health['overall_status'] == 'healthy' else 1)

    if args.alerts_only:
        health = monitor.check_system_health()
        alerts = health.get('alerts', [])
        if alerts:
            for alert in alerts:
                print(f"⚠️ {alert}")
            sys.exit(1)
        else:
            print("✅ No alerts")
            sys.exit(0)

    # Generate full report
    report = monitor.generate_report(args.format)

    if args.output:
        monitor.save_report(args.output, args.format)
    else:
        print(report)


if __name__ == "__main__":
    main()