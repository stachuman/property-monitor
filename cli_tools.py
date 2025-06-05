#!/usr/bin/env python3
"""
CLI Tools - Command line interface for system management - Fixed version
"""

import sys
import json
import time
import argparse
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any

from config import get_config, setup_logging
from database import DatabaseManager
from models import ScrapingConfig, GeocodingConfig
from property_scraper_service import ScrapingService
from geocoding_service import GeocodingService

logger = logging.getLogger(__name__)


class PropertyMonitorCLI:
    """Main CLI interface for property monitoring system"""

    def __init__(self):
        self.config = get_config()
        self.db = DatabaseManager()
        self.scraping_service = ScrapingService()
        self.geocoding_service = GeocodingService()

    def status(self, args):
        """Show system status"""
        print("=== Property Monitoring System Status ===\n")

        try:
            # System health
            health = self.db.get_system_health()
            print(f"System Health: {health.health_status.upper()}")
            print(f"Total Properties: {health.total_properties:,}")
            print(f"Geocoded Properties: {health.geocoded_properties:,} ({health.geocoding_percentage:.1f}%)")
            print(f"Failed Geocoding: {health.failed_geocoding:,}")
            print(f"Pending Geocoding: {health.pending_geocoding:,}")

            if health.last_scrape:
                print(f"Last Scrape: {health.last_scrape.strftime('%Y-%m-%d %H:%M:%S')}")
            else:
                print("Last Scrape: Never")

            if health.last_geocoding:
                print(f"Last Geocoding: {health.last_geocoding.strftime('%Y-%m-%d %H:%M:%S')}")
            else:
                print("Last Geocoding: Never")

            print()

            # Category breakdown
            category_stats = self.db.get_category_stats()
            if category_stats:
                print("=== Category Breakdown ===")
                for stat in category_stats:
                    print(
                        f"{stat.category:12}: {stat.total_count:6,} total, {stat.geocoded_count:6,} geocoded ({stat.geocoding_percentage:5.1f}%)")
                    if stat.avg_price:
                        print(
                            f"{'':15} Price: {stat.min_price:10,.0f} - {stat.max_price:10,.0f} PLN (avg: {stat.avg_price:10,.0f})")
                print()

            # Scraping status
            scraping_status = self.scraping_service.get_scraping_status()
            print("=== Scraping Status ===")
            print(f"Service Running: {scraping_status['service_running']}")
            print(f"Scheduler Active: {scraping_status.get('scheduler_active', 'Unknown')}")
            print(f"Scheduled Jobs: {scraping_status.get('scheduled_jobs_count', 0)}")
            print(f"Daily Scrape Time: {scraping_status.get('daily_scrape_time', 'Not set')}")
            
            if scraping_status.get('next_scheduled_scrape'):
                next_scrape = datetime.fromisoformat(scraping_status['next_scheduled_scrape'])
                print(f"Next Scheduled Scrape: {next_scrape.strftime('%Y-%m-%d %H:%M:%S')}")
            else:
                print(f"Next Scheduled Scrape: Not scheduled")

            for category in scraping_status['categories']:
                status_str = "ENABLED" if category['enabled'] else "DISABLED"
                last_run = category['last_run']
                if last_run:
                    last_run = datetime.fromisoformat(last_run).strftime('%Y-%m-%d %H:%M')
                else:
                    last_run = "Never"
                print(
                    f"{category['category']:12}: {status_str:8} (last: {last_run}, pages: {category['max_pages'] or 'unlimited'})")
            print()

            # Geocoding status
            geocoding_status = self.geocoding_service.get_geocoding_status()
            print("=== Geocoding Status ===")
            print(f"Service Running: {geocoding_status['service_running']}")
            print(f"Enabled: {geocoding_status['enabled']}")
            print(f"Poland Restriction: {geocoding_status.get('poland_restriction', True)}")
            print(f"Fuzzy Search: {geocoding_status.get('fuzzy_search', True)}")
            print(f"Batch Size: {geocoding_status['batch_size']}")
            print(f"Delay: {geocoding_status['delay_seconds']}s")
            print(f"Max Attempts: {geocoding_status['max_attempts']}")
            if geocoding_status.get('next_scheduled_run'):
                next_run = datetime.fromisoformat(geocoding_status['next_scheduled_run'])
                print(f"Next Scheduled Run: {next_run.strftime('%Y-%m-%d %H:%M:%S')}")

        except Exception as e:
            print(f"Error getting status: {e}")
            logger.error(f"Status command failed: {e}")
            return 1

        return 0

    def scrape(self, args):
        """Run scraping operations"""
        try:
            print("Starting manual scrape...")
            if args.category:
                print(f"Category: {args.category}")
                results = self.scraping_service.manual_scrape(args.category)
            else:
                print("All enabled categories")
                results = self.scraping_service.manual_scrape()

            print("\n=== Scraping Results ===")
            total_new = 0
            total_updated = 0
            total_errors = 0

            for result in results:
                print(f"{result.category:12}: {result.new_properties:4} new, {result.updated_properties:4} updated, "
                      f"{result.total_scraped:4} total ({result.duration_seconds:5.1f}s)")
                if result.errors:
                    print(f"{'':15} Errors: {len(result.errors)}")
                    for error in result.errors[:3]:  # Show first 3 errors
                        print(f"{'':15}   - {error}")
                    if len(result.errors) > 3:
                        print(f"{'':15}   ... and {len(result.errors) - 3} more")

                total_new += result.new_properties
                total_updated += result.updated_properties
                total_errors += len(result.errors)

            print(f"\nTotal: {total_new} new, {total_updated} updated, {total_errors} errors")
            
            if total_errors > 0:
                print("\n⚠️  Some errors occurred during scraping. Check logs for details.")
                return 1
            else:
                print("\n✅ Scraping completed successfully!")
                return 0

        except Exception as e:
            print(f"❌ Scraping failed: {e}")
            logger.error(f"Scrape command failed: {e}")
            return 1

    def geocode(self, args):
        """Run geocoding operations"""
        try:
            if args.retry_failed:
                print(f"Retrying failed geocoding entries (max {args.batch_size or 50})")
                print("Using Poland restriction and fuzzy search...")
                result = self.geocoding_service.retry_failed_geocoding(args.batch_size or 50)
            else:
                print(f"Starting manual geocoding (batch size: {args.batch_size or 'default'})")
                print("Using Poland restriction and fuzzy search...")
                result = self.geocoding_service.manual_geocoding(args.batch_size)

            print("\n=== Geocoding Results ===")
            print(f"Total Processed: {result.total_processed}")
            print(f"Successful: {result.successful}")
            print(f"Cached: {result.cached}")
            print(f"Failed: {result.failed}")
            print(f"Duration: {result.duration_seconds:.1f}s")

            if result.successful > 0:
                success_rate = (result.successful / result.total_processed) * 100 if result.total_processed > 0 else 0
                print(f"Success Rate: {success_rate:.1f}%")

            if result.errors:
                print(f"\nErrors ({len(result.errors)}):")
                for error in result.errors[:5]:  # Show first 5 errors
                    print(f"  - {error}")
                if len(result.errors) > 5:
                    print(f"  ... and {len(result.errors) - 5} more errors")

            if result.failed == 0:
                print("\n✅ Geocoding completed successfully!")
                return 0
            else:
                print(f"\n⚠️  {result.failed} properties failed geocoding.")
                return 1

        except Exception as e:
            print(f"❌ Geocoding failed: {e}")
            logger.error(f"Geocode command failed: {e}")
            return 1

    def config(self, args):
        """Manage configuration"""
        try:
            if args.show:
                # Show current configuration
                print("=== Current Configuration ===\n")

                # Scraping configs
                print("Scraping Categories:")
                scraping_configs = self.db.get_scraping_configs()
                for config in scraping_configs:
                    status = "ENABLED" if config.enabled else "DISABLED"
                    print(f"  {config.category:12}: {status:8} (pages: {config.max_pages or 'unlimited'}, "
                          f"delay: {config.delay_seconds}s, priority: {config.priority})")

                print()

                # Geocoding config
                print("Geocoding Configuration:")
                geocoding_config = self.db.get_geocoding_config()
                print(f"  Enabled: {geocoding_config.enabled}")
                print(f"  Poland Restriction: Enabled")
                print(f"  Fuzzy Search: Enabled")
                print(f"  Batch Size: {geocoding_config.batch_size}")
                print(f"  Delay: {geocoding_config.delay_seconds}s")
                print(f"  Max Attempts: {geocoding_config.max_attempts}")
                print(f"  Retry After: {geocoding_config.retry_failed_after_hours}h")

            elif args.set_scraping:
                # Update scraping configuration
                try:
                    category, setting, value = args.set_scraping.split('=', 2)
                except ValueError:
                    print("❌ Invalid format. Use: category.setting=value")
                    print("Example: grunty.enabled=true")
                    return 1

                configs = self.db.get_scraping_configs()
                config = next((c for c in configs if c.category == category), None)

                if not config:
                    print(f"❌ Category '{category}' not found")
                    print(f"Available categories: {', '.join(c.category for c in configs)}")
                    return 1

                # Update the setting
                if setting == 'enabled':
                    config.enabled = value.lower() in ('true', '1', 'yes')
                elif setting == 'max_pages':
                    config.max_pages = int(value) if value.lower() != 'none' else None
                elif setting == 'delay_seconds':
                    config.delay_seconds = float(value)
                elif setting == 'priority':
                    config.priority = int(value)
                else:
                    print(f"❌ Unknown setting: {setting}")
                    print("Available settings: enabled, max_pages, delay_seconds, priority")
                    return 1

                success = self.db.update_scraping_config(category, config)
                if success:
                    print(f"✅ Updated {category}.{setting} = {value}")
                else:
                    print(f"❌ Failed to update {category}.{setting}")
                    return 1

            elif args.set_geocoding:
                # Update geocoding configuration
                try:
                    setting, value = args.set_geocoding.split('=', 1)
                except ValueError:
                    print("❌ Invalid format. Use: setting=value")
                    print("Example: enabled=true")
                    return 1

                geocoding_config = self.db.get_geocoding_config()

                # Update the setting
                if setting == 'enabled':
                    geocoding_config.enabled = value.lower() in ('true', '1', 'yes')
                elif setting == 'batch_size':
                    geocoding_config.batch_size = int(value)
                elif setting == 'delay_seconds':
                    geocoding_config.delay_seconds = float(value)
                elif setting == 'max_attempts':
                    geocoding_config.max_attempts = int(value)
                elif setting == 'retry_failed_after_hours':
                    geocoding_config.retry_failed_after_hours = int(value)
                else:
                    print(f"❌ Unknown setting: {setting}")
                    print("Available settings: enabled, batch_size, delay_seconds, max_attempts, retry_failed_after_hours")
                    return 1

                success = self.geocoding_service.update_geocoding_config(geocoding_config)
                if success:
                    print(f"✅ Updated geocoding.{setting} = {value}")
                else:
                    print(f"❌ Failed to update geocoding.{setting}")
                    return 1

            return 0

        except Exception as e:
            print(f"❌ Configuration error: {e}")
            logger.error(f"Config command failed: {e}")
            return 1

    def failed_geocoding(self, args):
        """Manage failed geocoding entries"""
        try:
            failed_entries = self.geocoding_service.get_failed_geocoding_entries(args.limit)

            if not failed_entries:
                print("✅ No failed geocoding entries found")
                return 0

            print(f"=== Failed Geocoding Entries ({len(failed_entries)}) ===\n")

            for entry in failed_entries:
                print(f"ID: {entry.id}")
                print(f"  Property: {entry.property_id} - {entry.property_title}")
                print(f"  City: {entry.city}")
                print(f"  Attempts: {entry.attempts}")
                print(f"  Last Attempt: {entry.last_attempt.strftime('%Y-%m-%d %H:%M:%S')}")
                if entry.error_message:
                    print(f"  Error: {entry.error_message}")
                print()

            if args.fix and len(failed_entries) > 0:
                print("To manually fix geocoding, use:")
                print("  python cli_tools.py geocode-fix <property_id> <latitude> <longitude>")
                print("\nYou can find coordinates using:")
                print("  - Google Maps (right-click on location)")
                print("  - OpenStreetMap")
                print("  - Admin panel failed geocoding page")

            return 0

        except Exception as e:
            print(f"❌ Failed geocoding error: {e}")
            logger.error(f"Failed geocoding command failed: {e}")
            return 1

    def geocode_fix(self, args):
        """Fix geocoding for specific property"""
        try:
            # Validate coordinates are in Poland
            if not (49.0 <= args.latitude <= 54.9 and 14.1 <= args.longitude <= 24.2):
                print("⚠️  Warning: Coordinates appear to be outside Poland")
                response = input("Continue anyway? (y/N): ")
                if response.lower() != 'y':
                    print("❌ Geocoding fix cancelled")
                    return 1

            success = self.geocoding_service.manual_geocoding_fix(
                args.property_id, args.latitude, args.longitude
            )

            if success:
                print(f"✅ Geocoding fixed for property {args.property_id}")
                print(f"   Coordinates: {args.latitude}, {args.longitude}")
                return 0
            else:
                print(f"❌ Failed to fix geocoding for property {args.property_id}")
                return 1

        except Exception as e:
            print(f"❌ Geocoding fix error: {e}")
            logger.error(f"Geocode fix command failed: {e}")
            return 1

    def cleanup(self, args):
        """Cleanup old data"""
        try:
            print(f"Cleaning up auctions older than {args.grace_days} days...")
            deleted_count = self.db.cleanup_old_auctions(args.grace_days)
            print(f"✅ Cleaned up {deleted_count} old auction properties")
            return 0

        except Exception as e:
            print(f"❌ Cleanup error: {e}")
            logger.error(f"Cleanup command failed: {e}")
            return 1

    def export_data(self, args):
        """Export data to JSON"""
        try:
            print(f"Exporting data to {args.output_file}...")

            # Get all data
            properties = self.db.get_map_properties()
            health = self.db.get_system_health()
            category_stats = self.db.get_category_stats()

            export_data = {
                'export_timestamp': datetime.now().isoformat(),
                'system_info': {
                    'version': '1.0',
                    'environment': self.config.environment,
                    'poland_restriction': True,
                    'fuzzy_search': True
                },
                'system_health': health.to_dict(),
                'category_stats': [stat.to_dict() for stat in category_stats],
                'properties': properties,
                'total_properties': len(properties)
            }

            with open(args.output_file, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)

            print(f"✅ Exported {len(properties)} properties to {args.output_file}")
            return 0

        except Exception as e:
            print(f"❌ Export error: {e}")
            logger.error(f"Export command failed: {e}")
            return 1

    def test_geocoding(self, args):
        """Test geocoding for a specific city"""
        try:
            print(f"Testing geocoding for: {args.city}")
            print("Using Poland restriction and fuzzy search...")
            
            # Create a test property
            test_property = {
                'id': 999999,  # Test ID
                'city': args.city,
                'title': 'Test Property'
            }

            # Test geocoding
            from geocoding_service import PolishGeocodingWorker
            import asyncio
            
            worker = PolishGeocodingWorker(self.db)
            result = asyncio.run(worker.geocode_property(test_property))

            print("\n=== Geocoding Test Results ===")
            print(f"City: {result.city}")
            print(f"Success: {result.success}")
            
            if result.success:
                print(f"Coordinates: {result.latitude}, {result.longitude}")
                print(f"Source: {result.source}")
                print(f"Duration: {result.duration_seconds:.2f}s")
                print("✅ Geocoding test successful!")
            else:
                print(f"Error: {result.error}")
                print("❌ Geocoding test failed")
                return 1

            return 0

        except Exception as e:
            print(f"❌ Geocoding test error: {e}")
            logger.error(f"Test geocoding command failed: {e}")
            return 1


def create_parser():
    """Create CLI argument parser"""
    parser = argparse.ArgumentParser(
        description="Property Monitoring System CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python cli_tools.py status                              # Show system status
  python cli_tools.py scrape --category grunty           # Scrape land plots only
  python cli_tools.py geocode --batch-size 10            # Geocode 10 properties
  python cli_tools.py geocode --retry-failed             # Retry failed geocoding
  python cli_tools.py config --set-scraping grunty.enabled=false
  python cli_tools.py geocode-fix 12345 52.2297 21.0122  # Fix coordinates
  python cli_tools.py test-geocoding "Warszawa"          # Test geocoding
        """
    )

    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Enable verbose logging')

    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # Status command
    status_parser = subparsers.add_parser('status', help='Show system status')

    # Scrape command
    scrape_parser = subparsers.add_parser('scrape', help='Run scraping')
    scrape_parser.add_argument('--category', help='Specific category to scrape (grunty, domy, inne)')

    # Geocode command
    geocode_parser = subparsers.add_parser('geocode', help='Run geocoding with Poland restriction')
    geocode_parser.add_argument('--batch-size', type=int, help='Batch size for geocoding')
    geocode_parser.add_argument('--retry-failed', action='store_true',
                                help='Retry failed geocoding entries')

    # Config command
    config_parser = subparsers.add_parser('config', help='Manage configuration')
    config_parser.add_argument('--show', action='store_true', help='Show current configuration')
    config_parser.add_argument('--set-scraping', help='Set scraping config: category.setting=value')
    config_parser.add_argument('--set-geocoding', help='Set geocoding config: setting=value')

    # Failed geocoding command
    failed_parser = subparsers.add_parser('failed-geocoding', help='Review failed geocoding')
    failed_parser.add_argument('--limit', type=int, default=50, help='Number of entries to show')
    failed_parser.add_argument('--fix', action='store_true', help='Show fix instructions')

    # Geocode fix command
    fix_parser = subparsers.add_parser('geocode-fix', help='Fix geocoding for property')
    fix_parser.add_argument('property_id', type=int, help='Property ID')
    fix_parser.add_argument('latitude', type=float, help='Latitude (must be in Poland)')
    fix_parser.add_argument('longitude', type=float, help='Longitude (must be in Poland)')

    # Test geocoding command
    test_parser = subparsers.add_parser('test-geocoding', help='Test geocoding for a city')
    test_parser.add_argument('city', help='City name to test')

    # Cleanup command
    cleanup_parser = subparsers.add_parser('cleanup', help='Cleanup old data')
    cleanup_parser.add_argument('--grace-days', type=int, default=2,
                                help='Grace period in days for old auctions')

    # Export command
    export_parser = subparsers.add_parser('export', help='Export data to JSON')
    export_parser.add_argument('output_file', help='Output JSON file path')

    return parser


def main():
    """Main CLI entry point"""
    parser = create_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.WARNING
    logging.getLogger().setLevel(log_level)
    setup_logging()

    # Create CLI instance and run command
    cli = PropertyMonitorCLI()

    try:
        if args.command == 'status':
            return cli.status(args)
        elif args.command == 'scrape':
            return cli.scrape(args)
        elif args.command == 'geocode':
            return cli.geocode(args)
        elif args.command == 'config':
            return cli.config(args)
        elif args.command == 'failed-geocoding':
            return cli.failed_geocoding(args)
        elif args.command == 'geocode-fix':
            return cli.geocode_fix(args)
        elif args.command == 'test-geocoding':
            return cli.test_geocoding(args)
        elif args.command == 'cleanup':
            return cli.cleanup(args)
        elif args.command == 'export':
            return cli.export_data(args)
        else:
            print(f"❌ Unknown command: {args.command}")
            return 1

    except KeyboardInterrupt:
        print("\n❌ Operation cancelled")
        return 130
    except Exception as e:
        logger.error(f"Command failed: {e}")
        print(f"❌ Error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
