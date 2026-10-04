#!/bin/bash

# 1. Fix DNS (Set Shecan DNS for Iran Servers)
echo "Setting DNS for Iran Servers..."
cat << 'EOF' > /etc/resolv.conf
nameserver 178.22.122.100
nameserver 185.51.200.2
nameserver 1.1.1.1
EOF

# 2. Update and Install System Dependencies
echo "Installing System Dependencies..."
apt update && apt install -y python3 python3-venv unzip curl wget git

# 3. Setup Python Virtual Environment
echo "Setting up Virtual Environment..."
python3 -m venv venv

# 4. Install Requirements with Timeout
echo "Installing Python Packages..."
./venv/bin/pip install --default-timeout=100 -r requirements.txt

# 5. Download and Install Rathole Binary
echo "Installing Rathole Binary..."
if [ ! -f /usr/local/bin/rathole ]; then
    wget -qO /tmp/rathole.zip "https://github.com/rathole-org/rathole/releases/download/v0.5.0/rathole-x86_64-unknown-linux-gnu.zip"
    unzip -o /tmp/rathole.zip -d /usr/local/bin/
    chmod +x /usr/local/bin/rathole
    rm -f /tmp/rathole.zip
fi

# 6. Create Systemd Service for Permanent Running
echo "Creating Systemd Service..."
cat << EOF > /etc/systemd/system/rathole-panel.service
[Unit]
Description=Rathole Panel Service
After=network.target

[Service]
Type=simple
WorkingDirectory=$(pwd)
ExecStart=$(pwd)/venv/bin/python app.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

# 7. Start the Service
systemctl daemon-reload
systemctl enable --now rathole-panel

echo "------------------------------------------------"
echo "✅ Installation Complete!"
echo "🌐 Panel URL: http://$(curl -s https://api.ipify.org):8000"
echo "🔑 Default Password: 123456"
echo "------------------------------------------------"
