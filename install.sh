#!/bin/bash

echo "--- 1. Fixing DNS (for Iran Servers) ---"
cat << 'EOF' > /etc/resolv.conf
nameserver 178.22.122.100
nameserver 185.51.200.2
nameserver 8.8.8.8
EOF

echo "--- 2. Updating APT Repositories ---"
apt update

echo "--- 3. Installing Dependencies via APT (No pip needed) ---"
apt install -y python3 python3-fastapi python3-uvicorn python3-jinja2 python3-paramiko python3-cryptography python3-requests python3-multipart unzip curl wget git

echo "--- 4. Installing Rathole Core Binary ---"
if [ ! -f /usr/local/bin/rathole ]; then
    wget -qO /tmp/rathole.zip "https://github.com/rathole-org/rathole/releases/download/v0.5.0/rathole-x86_64-unknown-linux-gnu.zip"
    unzip -o /tmp/rathole.zip -d /usr/local/bin/
    chmod +x /usr/local/bin/rathole
    rm -f /tmp/rathole.zip
fi

echo "--- 5. Creating Systemd Service for Permanent Running ---"
# Detect current directory
CUR_DIR=$(pwd)

cat << EOF > /etc/systemd/system/rathole-panel.service
[Unit]
Description=Rathole Panel Web Service
After=network.target

[Service]
Type=simple
WorkingDirectory=$CUR_DIR
ExecStart=/usr/bin/python3 app.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

echo "--- 6. Starting Service ---"
systemctl daemon-reload
systemctl enable --now rathole-panel

echo "------------------------------------------------"
echo "✅ Installation Completed Successfully!"
echo "🌐 Panel URL: http://$(curl -s https://api.ipify.org):8000"
echo "🔑 Default Password: 123456"
echo "------------------------------------------------"
