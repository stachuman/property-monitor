#!/usr/bin/env python3
"""
Template Utilities - Common functions and filters for Jinja2 templates
"""

import json
from datetime import datetime
from typing import Any, Dict


def setup_template_globals(app):
    """Setup global functions and filters for Jinja2 templates"""
    
    # Add built-in Python functions to template context
    app.jinja_env.globals.update({
        'max': max,
        'min': min,
        'len': len,
        'round': round,
        'abs': abs,
        'sum': sum,
        'sorted': sorted,
        'enumerate': enumerate,
        'zip': zip,
        'range': range,
        'str': str,
        'int': int,
        'float': float,
        'bool': bool,
        'list': list,
        'dict': dict,
    })
    
    # Add custom template functions
    app.jinja_env.globals.update({
        'format_number': format_number,
        'format_percentage': format_percentage,
        'format_currency': format_currency,
        'format_datetime': format_datetime,
        'format_file_size': format_file_size,
        'safe_divide': safe_divide,
        'get_status_class': get_status_class,
        'get_status_emoji': get_status_emoji,
    })

    # Add custom filters
    app.jinja_env.filters.update({
        'money': format_currency,
        'percent': format_percentage,
        'filesize': format_file_size,
        'datetime': format_datetime,
        'status_class': get_status_class,
        'status_emoji': get_status_emoji,
    })


def format_number(value, decimals=0):
    """Format number with thousands separators"""
    if value is None:
        return "N/A"
    try:
        return f"{float(value):,.{decimals}f}"
    except (ValueError, TypeError):
        return str(value)


def format_percentage(value, decimals=1):
    """Format percentage value"""
    if value is None:
        return "N/A"
    try:
        return f"{float(value):.{decimals}f}%"
    except (ValueError, TypeError):
        return str(value)


def format_currency(value, currency="PLN"):
    """Format currency value"""
    if value is None:
        return "N/A"
    try:
        return f"{float(value):,.0f} {currency}"
    except (ValueError, TypeError):
        return str(value)


def format_datetime(value, format_str="%Y-%m-%d %H:%M:%S"):
    """Format datetime value"""
    if value is None:
        return "Never"
    
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace('Z', '+00:00'))
        except ValueError:
            return value
    
    if isinstance(value, datetime):
        return value.strftime(format_str)
    
    return str(value)


def format_file_size(bytes_value):
    """Format file size in human readable format"""
    if bytes_value is None:
        return "N/A"
    
    try:
        bytes_value = float(bytes_value)
    except (ValueError, TypeError):
        return str(bytes_value)
    
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_value < 1024.0:
            return f"{bytes_value:.1f} {unit}"
        bytes_value /= 1024.0
    return f"{bytes_value:.1f} PB"


def safe_divide(numerator, denominator, default=0):
    """Safely divide two numbers, returning default if denominator is 0"""
    try:
        num = float(numerator) if numerator is not None else 0
        den = float(denominator) if denominator is not None else 0
        
        if den == 0:
            return default
        return num / den
    except (ValueError, TypeError, ZeroDivisionError):
        return default


def get_status_class(status):
    """Get CSS class for status"""
    status_classes = {
        'healthy': 'status-healthy',
        'success': 'status-healthy',
        'warning': 'status-warning',
        'error': 'status-error',
        'critical': 'status-error',
        'degraded': 'status-warning',
        'maintenance': 'status-warning',
        'enabled': 'status-healthy',
        'disabled': 'status-error',
        'active': 'status-healthy',
        'inactive': 'status-error',
        'running': 'status-healthy',
        'stopped': 'status-error',
        'failed': 'status-error',
    }
    
    if isinstance(status, str):
        return status_classes.get(status.lower(), 'status-neutral')
    elif isinstance(status, bool):
        return 'status-healthy' if status else 'status-error'
    else:
        return 'status-neutral'


def get_status_emoji(status):
    """Get emoji for status"""
    status_emojis = {
        'healthy': '🟢',
        'success': '✅',
        'warning': '⚠️',
        'error': '❌',
        'critical': '🔴',
        'degraded': '🟡',
        'maintenance': '🔧',
        'enabled': '✅',
        'disabled': '❌',
        'active': '🟢',
        'inactive': '⚪',
        'running': '🟢',
        'stopped': '🔴',
        'failed': '❌',
        'pending': '🟡',
        'processing': '🔄',
    }
    
    if isinstance(status, str):
        return status_emojis.get(status.lower(), '⚪')
    elif isinstance(status, bool):
        return '🟢' if status else '🔴'
    else:
        return '⚪'


# Template context processors
def inject_template_globals():
    """Inject global template variables"""
    return {
        'current_year': datetime.now().year,
        'app_name': 'Property Monitor',
        'app_version': '1.0.0',
    }
