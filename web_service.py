#!/usr/bin/env python3
"""
Web Service - Public web interface for property map
"""

import os
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any

from flask import Flask, render_template, jsonify, request

from config import get_config
from database import DatabaseManager

logger = logging.getLogger(__name__)


class WebService:
    """Public web interface service"""
    def __init__(self):
        self.config = get_config()
        self.db = DatabaseManager()
        self.app = None
        self._setup_flask_app()

    def _setup_flask_app(self):
        """Setup Flask application with public routes"""
        self.app = Flask(__name__, template_folder='templates')
        self.app.secret_key = self.config.web_server.secret_key

        # Add server configuration to template context
        @self.app.context_processor
        def inject_server_config():
            return {
                'server_config': {
                    'public_url': self.config.web_server.public_url,
                    'admin_url': self.config.web_server.admin_url,
                    'server_name': self.config.web_server.server_name,
                    'environment': self.config.environment
                }
            }

        # Public routes
        self.app.add_url_rule('/', 'index', self.index)
        self.app.add_url_rule('/api/properties', 'api_properties', self.api_properties)
        self.app.add_url_rule('/api/health', 'api_health', self.api_health)
        self.app.add_url_rule('/api/stats', 'api_stats', self.api_stats)
        self.app.add_url_rule('/watched', 'watched_page', self.watched_page)
        self.app.add_url_rule('/api/watched', 'api_watched', self.api_watched, methods=['GET'])
        self.app.add_url_rule('/api/watched', 'api_add_watched', self.api_add_watched, methods=['POST'])
        self.app.add_url_rule('/api/watched/<int:property_id>', 'api_remove_watched', self.api_remove_watched, methods=['DELETE'])
        self.app.add_url_rule('/api/watched/<int:property_id>', 'api_update_watched', self.api_update_watched, methods=['PUT'])
        self.app.add_url_rule('/api/watched/check/<int:property_id>', 'api_check_watched', self.api_check_watched, methods=['GET'])

        # Optional force scrape endpoint (if enabled)
        if self.config.environment != 'production':
            self.app.add_url_rule('/api/force-scrape', 'api_force_scrape', self.api_force_scrape, methods=['POST'])

    def watched_page(self):
        """Watched properties page"""
        try:
            watched_properties = self.db.get_watched_properties()
            return render_template('watched.html',
                                 watched_properties=watched_properties,
                                 total_watched=len(watched_properties))
        except Exception as e:
            logger.error(f"Watched page error: {e}")
            return f"Error loading watched properties: {e}", 500

    def api_watched(self):
        """Get all watched properties"""
        try:
            watched_properties = self.db.get_watched_properties()
            return jsonify(watched_properties)
        except Exception as e:
            logger.error(f"Watched API error: {e}")
            return jsonify({"error": str(e)}), 500

    def api_add_watched(self):
        """Add property to watched list"""
        try:
            data = request.get_json()
            property_id = data.get('property_id')
            notes = data.get('notes', '')

            if not property_id:
                return jsonify({"error": "property_id is required"}), 400

            success = self.db.add_to_watched(property_id, notes)

            if success:
                return jsonify({
                    "success": True,
                    "message": f"Property {property_id} added to watched list"
                })
            else:
                return jsonify({"error": "Failed to add property to watched list"}), 500

        except Exception as e:
            logger.error(f"Add watched API error: {e}")
            return jsonify({"error": str(e)}), 500

    def api_remove_watched(self, property_id):
        """Remove property from watched list"""
        try:
            success = self.db.remove_from_watched(property_id)

            if success:
                return jsonify({
                    "success": True,
                    "message": f"Property {property_id} removed from watched list"
                })
            else:
                return jsonify({"error": "Property not found in watched list"}), 404

        except Exception as e:
            logger.error(f"Remove watched API error: {e}")
            return jsonify({"error": str(e)}), 500

    def api_update_watched(self, property_id):
        """Update notes for watched property"""
        try:
            data = request.get_json()
            notes = data.get('notes', '')

            success = self.db.update_watched_notes(property_id, notes)

            if success:
                return jsonify({
                    "success": True,
                    "message": f"Notes updated for property {property_id}"
                })
            else:
                return jsonify({"error": "Property not found in watched list"}), 404

        except Exception as e:
            logger.error(f"Update watched API error: {e}")
            return jsonify({"error": str(e)}), 500

    def api_check_watched(self, property_id):
        """Check if property is watched and get details"""
        try:
            is_watched = self.db.is_property_watched(property_id)
            details = None

            if is_watched:
                details = self.db.get_watched_property_details(property_id)

            return jsonify({
                "is_watched": is_watched,
                "details": details
            })

        except Exception as e:
            logger.error(f"Check watched API error: {e}")
            return jsonify({"error": str(e)}), 500


    def index(self):
        """Main property map interface"""
        try:
            # Get basic statistics for the page
            health = self.db.get_system_health()

            return render_template('index.html',
                                   total_properties=health.total_properties,
                                   geocoded_properties=health.geocoded_properties,
                                   admin_url=self.config.web_server.admin_url)
        except Exception as e:
            logger.error(f"Index page error: {e}")
            return f"Error loading page: {e}", 500


    def api_properties(self):
        """Get all geocoded properties for map display"""
        try:
            # Get query parameters for filtering
            city = request.args.get('city', '').strip()
            min_price = request.args.get('min_price', type=float)
            max_price = request.args.get('max_price', type=float)
            category = request.args.get('category', '').strip()
            status = request.args.get('status', '').strip()
            land_type = request.args.get('land_type', '').strip()

            # Get all properties
            properties = self.db.get_map_properties()

            # Apply filters if provided
            if city:
                properties = [p for p in properties if city.lower() in p['city'].lower()]

            if min_price is not None:
                properties = [p for p in properties if p['opening_value'] and p['opening_value'] >= min_price]

            if max_price is not None:
                properties = [p for p in properties if p['opening_value'] and p['opening_value'] <= max_price]

            if category:
                properties = [p for p in properties if p['sub_category'] == category]

            if status:
                properties = [p for p in properties if p['status'] == status]

            if land_type:
                properties = [p for p in properties if p['land_type'] == land_type]

            properties = self.db.get_map_properties()
            
            # Get watched property IDs for efficient lookup
            watched_ids = self.db.get_watched_property_ids()
            
            # Add watched status to each property
            for prop in properties:
                prop['is_watched'] = prop['id'] in watched_ids
            
            # Apply filters including watched filter
            watched_only = request.args.get('watched_only', '').lower() == 'true'
            
            if watched_only:
                properties = [p for p in properties if p['is_watched']]


            logger.debug(f"Returning {len(properties)} properties (filtered from all geocoded)")
            return jsonify(properties)

        except Exception as e:
            logger.error(f"Properties API error: {e}")
            return jsonify({"error": str(e)}), 500

    def api_health(self):
        """System health status for public interface"""
        try:
            health = self.db.get_system_health()

            # Return simplified health status for public
            public_health = {
                'status': 'healthy' if health.health_status == 'healthy' else 'maintenance',
                'total_properties': health.total_properties,
                'geocoded_properties': health.geocoded_properties,
                'geocoding_percentage': round(health.geocoding_percentage, 1),
                'last_update': health.last_scrape.isoformat() if health.last_scrape else None,
                'timestamp': health.timestamp.isoformat()
            }

            return jsonify(public_health)

        except Exception as e:
            logger.error(f"Health API error: {e}")
            return jsonify({
                'status': 'error',
                'total_properties': 0,
                'geocoded_properties': 0,
                'geocoding_percentage': 0,
                'last_update': None,
                'timestamp': datetime.now().isoformat()
            }), 500

    def api_stats(self):
        """Public statistics API"""
        try:
            category_stats = self.db.get_category_stats()
            health = self.db.get_system_health()

            stats = {
                'overview': {
                    'total_properties': health.total_properties,
                    'geocoded_properties': health.geocoded_properties,
                    'geocoding_percentage': round(health.geocoding_percentage, 1),
                    'categories_count': len(category_stats)
                },
                'categories': []
            }

            # Add category statistics (simplified for public)
            for cat_stat in category_stats:
                stats['categories'].append({
                    'category': cat_stat.category,
                    'count': cat_stat.total_count,
                    'geocoded_count': cat_stat.geocoded_count,
                    'avg_price': cat_stat.avg_price,
                    'min_price': cat_stat.min_price,
                    'max_price': cat_stat.max_price
                })

            return jsonify(stats)

        except Exception as e:
            logger.error(f"Stats API error: {e}")
            return jsonify({"error": str(e)}), 500

    def api_force_scrape(self):
        """Force scrape endpoint (development only)"""
        if self.config.environment == 'production':
            return jsonify({"error": "Not available in production"}), 403

        try:
            # Import here to avoid circular imports
            from property_scraper_service import ScrapingService

            scraping_service = ScrapingService()

            # Run in background thread
            import threading
            def run_scraping():
                try:
                    results = scraping_service.manual_scrape()
                    logger.info(f"Force scrape completed: {len(results)} categories processed")
                except Exception as e:
                    logger.error(f"Force scrape failed: {e}")

            threading.Thread(target=run_scraping, daemon=True).start()

            return jsonify({
                'status': 'started',
                'message': 'Scraping started in background'
            })

        except Exception as e:
            logger.error(f"Force scrape error: {e}")
            return jsonify({"error": str(e)}), 500

    def start_service(self):
        """Start the web service"""
        logger.info(f"Starting web service on port {self.config.web_server.port}")

        # Ensure templates directory exists
        os.makedirs('templates', exist_ok=True)

        self.app.run(
            host=self.config.web_server.host,
            port=self.config.web_server.port,
            debug=self.config.web_server.debug,
            threaded=True
        )


def main():
    """Main entry point for web service"""
    from config import setup_logging

    setup_logging()

    web_service = WebService()
    try:
        web_service.start_service()
    except KeyboardInterrupt:
        logger.info("Web service stopped")
    except Exception as e:
        logger.error(f"Web service error: {e}")


if __name__ == "__main__":
    main()
