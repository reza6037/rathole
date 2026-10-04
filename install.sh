#!/bin/bash

echo "--- 1. Updating Repositories ---"
apt update

echo "--- 2. Installing Dependencies via APT ---"
apt install -y python3 python3-fastapi python3-uvicorn python3-jinja2 python3-paramiko python3-cryptography python3-requests unzip curl wget git

echo "--- 3. Installing Rathole Core Binary ---"
if [ ! -f /usr/local/bin/rathole ]; then
    wget -qO /tmp/rathole.zip "https://github.com/rathole-org/rathole/releases/download/v0.5.0/rathole-x86_64-unknown-linux-gnu.zip"
    unzip -o /tmp/rathole.zip -d /usr/local/bin/
    chmod +x /usr/local/bin/rathole
    rm -f /tmp/rathole.zip
fi

echo "--- 4. Creating Systemd Service ---"
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

echo "--- 5. Starting Service ---"
systemctl daemon-reload
systemctl enable --now rathole-panel

echo "------------------------------------------------"
echo "✅ Installation Completed Successfully!"
echo "🌐 Panel URL: http://$(curl -s https://api.ipify.org):8000"
echo "🔑 Default Password: 123456"
echo "------------------------------------------------"
