#!/bin/bash

# Property Monitor - Installation Script
# This script installs and configures Property Monitor on Linux systems

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
APP_NAME="property-monitor"
APP_USER="property-monitor"
APP_DIR="/opt/property-monitor"
DATA_DIR="/var/lib/property_monitor"
LOG_DIR="/var/log/property_monitor"
SERVICE_FILE="/etc/systemd/system/property-monitor.service"

# Functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_root() {
    if [[ $EUID -ne 0 ]]; then
        log_error "This script must be run as root (use sudo)"
        exit 1
    fi
}

check_system() {
    log_info "Checking system requirements..."
    
    # Check OS
    if [[ ! -f /etc/os-release ]]; then
        log_error "Cannot determine OS version"
        exit 1
    fi
    
    source /etc/os-release
    log_info "Detected OS: $PRETTY_NAME"
    
    # Check Python
    if ! command -v python3 &> /dev/null; then
        log_error "Python 3 is not installed"
        exit 1
    fi
    
    PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
    log_info "Python version: $PYTHON_VERSION"
    
    # Check if Python 3.8+
    if ! python3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)"; then
        log_error "Python 3.8 or higher is required"
        exit 1
    fi
    
    # Check pip
    if ! command -v pip3 &> /dev/null; then
        log_warning "pip3 not found, installing..."
        install_pip
    fi
}

install_dependencies() {
    log_info "Installing system dependencies..."
    
    # Update package list
    apt-get update
    
    # Install required packages
    apt-get install -y \
        python3-pip \
        python3-venv \
        sqlite3 \
        curl \
        nginx \
        supervisor \
        git \
        wget \
        gnupg \
        software-properties-common
    
    log_success "System dependencies installed"
}

install_pip() {
    log_info "Installing pip3..."
    curl -sSL https://bootstrap.pypa.io/get-pip.py | python3
}

create_user() {
    log_info "Creating application user..."
    
    if id "$APP_USER" &>/dev/null; then
        log_warning "User $APP_USER already exists"
    else
        useradd --system --shell /bin/bash --home-dir $APP_DIR --create-home $APP_USER
        log_success "User $APP_USER created"
    fi
}

create_directories() {
    log_info "Creating application directories..."
    
    # Create directories
    mkdir -p $APP_DIR
    mkdir -p $DATA_DIR/backups
    mkdir -p $LOG_DIR
    
    # Set permissions
    chown -R $APP_USER:$APP_USER $APP_DIR
    chown -R $APP_USER:$APP_USER $DATA_DIR
    chown -R $APP_USER:$APP_USER $LOG_DIR
    
    # Set proper permissions for log directory
    chmod 755 $LOG_DIR
    chmod 755 $DATA_DIR
    
    log_success "Directories created and configured"
}

install_application() {
    log_info "Installing Property Monitor application..."
    
    # Change to app directory
    cd $APP_DIR
    
    # Copy files (assuming we're running from the source directory)
    if [[ -f "$(dirname $0)/main_service.py" ]]; then
        cp -r $(dirname $0)/* $APP_DIR/
    else
        log_error "Source files not found. Please run this script from the project directory."
        exit 1
    fi
    
    # Create virtual environment
    sudo -u $APP_USER python3 -m venv venv
    
    # Install Python dependencies
    sudo -u $APP_USER $APP_DIR/venv/bin/pip install --upgrade pip
    sudo -u $APP_USER $APP_DIR/venv/bin/pip install -r requirements.txt
    
    # Copy configuration template
    if [[ ! -f $APP_DIR/config.json ]]; then
        sudo -u $APP_USER cp config.json $APP_DIR/config.json
        log_info "Configuration file created at $APP_DIR/config.json"
    fi
    
    # Initialize database
    sudo -u $APP_USER $APP_DIR/venv/bin/python -c "from database import DatabaseManager; DatabaseManager().init_database()"
    
    # Set permissions
    chown -R $APP_USER:$APP_USER $APP_DIR
    
    log_success "Application installed"
}

create_systemd_service() {
    log_info "Creating systemd service..."
    
    cat > $SERVICE_FILE << EOF
[Unit]
Description=Property Monitoring System
After=network.target
Wants=network.target

[Service]
Type=simple
User=$APP_USER
Group=$APP_USER
WorkingDirectory=$APP_DIR
ExecStart=$APP_DIR/venv/bin/python main_service.py
Restart=always
RestartSec=10

# Environment
Environment=PYTHONPATH=$APP_DIR
Environment=CONFIG_PATH=$APP_DIR/config.json

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=property-monitor

# Resource limits
LimitNOFILE=65536
MemoryLimit=1G

[Install]
WantedBy=multi-user.target
EOF
    
    # Reload systemd and enable service
    systemctl daemon-reload
    systemctl enable property-monitor
    
    log_success "Systemd service created and enabled"
}

configure_nginx() {
    log_info "Configuring Nginx..."
    
    # Backup default nginx config if it exists
    if [[ -f /etc/nginx/sites-enabled/default ]]; then
        mv /etc/nginx/sites-enabled/default /etc/nginx/sites-available/default.backup
    fi
    
    # Create nginx configuration
    cat > /etc/nginx/sites-available/property-monitor << EOF
server {
    listen 80;
    server_name _;
    
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
    
    location /admin {
        proxy_pass http://127.0.0.1:5001;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF
    
    # Enable site
    ln -sf /etc/nginx/sites-available/property-monitor /etc/nginx/sites-enabled/
    
    # Test nginx configuration
    nginx -t
    
    # Restart nginx
    systemctl restart nginx
    systemctl enable nginx
    
    log_success "Nginx configured and restarted"
}

setup_firewall() {
    log_info "Configuring firewall..."
    
    if command -v ufw &> /dev/null; then
        # Allow SSH, HTTP, and HTTPS
        ufw allow ssh
        ufw allow http
        ufw allow https
        ufw allow 8080/tcp  # Admin panel
        
        # Enable firewall if not already enabled
        echo "y" | ufw enable
        
        log_success "UFW firewall configured"
    else
        log_warning "UFW not found, skipping firewall configuration"
    fi
}

create_backup_script() {
    log_info "Creating backup script..."
    
    cat > /usr/local/bin/property-monitor-backup << 'EOF'
#!/bin/bash
# Property Monitor Backup Script

BACKUP_DIR="/var/lib/property_monitor/backups"
DB_PATH="/var/lib/property_monitor/properties.db"
DATE=$(date +%Y%m%d_%H%M%S)

# Create backup
if [[ -f "$DB_PATH" ]]; then
    cp "$DB_PATH" "$BACKUP_DIR/properties_backup_$DATE.db"
    
    # Compress old backups (keep last 30 days)
    find "$BACKUP_DIR" -name "properties_backup_*.db" -mtime +30 -delete
    
    echo "Backup created: properties_backup_$DATE.db"
else
    echo "Database file not found: $DB_PATH"
    exit 1
fi
EOF
    
    chmod +x /usr/local/bin/property-monitor-backup
    
    # Add to crontab
    (crontab -l 2>/dev/null; echo "0 2 * * * /usr/local/bin/property-monitor-backup") | crontab -
    
    log_success "Backup script created and scheduled"
}

start_services() {
    log_info "Starting services..."
    
    # Start Property Monitor
    systemctl start property-monitor
    
    # Check status
    sleep 5
    if systemctl is-active --quiet property-monitor; then
        log_success "Property Monitor service started successfully"
    else
        log_error "Failed to start Property Monitor service"
        systemctl status property-monitor
        exit 1
    fi
}

print_summary() {
    log_success "Installation completed successfully!"
    echo
    echo -e "${GREEN}=== Property Monitor Installation Summary ===${NC}"
    echo -e "Application directory: ${BLUE}$APP_DIR${NC}"
    echo -e "Data directory: ${BLUE}$DATA_DIR${NC}"
    echo -e "Log directory: ${BLUE}$LOG_DIR${NC}"
    echo -e "Configuration file: ${BLUE}$APP_DIR/config.json${NC}"
    echo
    echo -e "${GREEN}=== Service URLs ===${NC}"
    echo -e "Public Map Interface: ${BLUE}http://$(hostname -I | awk '{print $1}')${NC}"
    echo -e "Admin Panel: ${BLUE}http://$(hostname -I | awk '{print $1}'):8080${NC}"
    echo
    echo -e "${GREEN}=== Useful Commands ===${NC}"
    echo -e "View logs: ${BLUE}journalctl -u property-monitor -f${NC}"
    echo -e "Service status: ${BLUE}systemctl status property-monitor${NC}"
    echo -e "Restart service: ${BLUE}systemctl restart property-monitor${NC}"
    echo -e "CLI tools: ${BLUE}cd $APP_DIR && ./venv/bin/python cli_tools.py status${NC}"
    echo -e "Manual backup: ${BLUE}/usr/local/bin/property-monitor-backup${NC}"
    echo
    echo -e "${YELLOW}Next steps:${NC}"
    echo "1. Edit configuration file: $APP_DIR/config.json"
    echo "2. Configure email alerts (optional)"
    echo "3. Set up SSL certificate for production use"
    echo "4. Access the admin panel to start initial data scraping"
}

# Main installation process
main() {
    echo -e "${BLUE}╔══════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║        Property Monitor Installation         ║${NC}"
    echo -e "${BLUE}╚══════════════════════════════════════════════╝${NC}"
    echo
    
    check_root
    check_system
    install_dependencies
    create_user
    create_directories
    install_application
    create_systemd_service
    configure_nginx
    setup_firewall
    create_backup_script
    start_services
    print_summary
}

# Run main function
main "$@"
