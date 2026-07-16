#!/bin/bash

echo "============================================================"
echo "Setting up Auto-Settlement Scheduler Service"
echo "============================================================"

# Copy service file to systemd
echo "1. Copying service file to systemd..."
sudo cp orchpay-auto-settlement.service /etc/systemd/system/

# Reload systemd
echo "2. Reloading systemd daemon..."
sudo systemctl daemon-reload

# Enable service to start on boot
echo "3. Enabling service to start on boot..."
sudo systemctl enable orchpay-auto-settlement

# Start the service
echo "4. Starting auto-settlement scheduler..."
sudo systemctl start orchpay-auto-settlement

# Check status
echo "5. Checking service status..."
sudo systemctl status orchpay-auto-settlement

echo ""
echo "============================================================"
echo "Setup Complete!"
echo "============================================================"
echo ""
echo "Useful commands:"
echo "  Check status:  sudo systemctl status orchpay-auto-settlement"
echo "  View logs:     sudo tail -f /var/log/orchpay_auto_settlement.log"
echo "  View errors:   sudo tail -f /var/log/orchpay_auto_settlement_error.log"
echo "  Restart:       sudo systemctl restart orchpay-auto-settlement"
echo "  Stop:          sudo systemctl stop orchpay-auto-settlement"
echo ""
echo "The scheduler runs every 5 minutes and checks for due settlements."
echo "============================================================"
