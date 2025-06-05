#!/bin/bash
# Property Monitor Health Check Script

HEALTH_URL="http://localhost:5000/api/health"
LOG_FILE="/var/log/property-monitor/health.log"

# Function to log messages
log_message() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" >> "$LOG_FILE"
}

# Check if service is running
if ! systemctl is-active --quiet property-monitor; then
    log_message "ERROR: Property monitor service is not running"
    systemctl restart property-monitor
    exit 1
fi

# Check health endpoint
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$HEALTH_URL" || echo "000")

if [ "$HTTP_CODE" != "200" ]; then
    log_message "ERROR: Health check failed with HTTP code: $HTTP_CODE"
    systemctl restart property-monitor
    exit 1
fi

# Check response content
RESPONSE=$(curl -s "$HEALTH_URL" 2>/dev/null)
STATUS=$(echo "$RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('status', 'unknown'))" 2>/dev/null)

if [ "$STATUS" == "error" ]; then
    log_message "WARNING: Health check reports error status"
    exit 1
fi

log_message "INFO: Health check passed - Status: $STATUS"
exit 0
