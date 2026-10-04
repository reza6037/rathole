#!/bin/bash

echo "--- Updating Package Lists ---"
apt update

echo "--- Installing Python and Dependencies via APT (No PyPI needed) ---"
apt install -y python3 python3-fastapi python3-uvicorn python3-jinja2 python3-paramiko python3-cryptography python3-requests python3-multipart unzip curl wget git

echo "--- Installing Rathole Core Binary ---"
if [ ! -f /usr/local/bin/rathole ]; then
    wget -qO /tmp/rathole.zip "https://github.com/rathole-org/rathole/releases/download/v0.5.0/rathole-x86_64-unknown-linux-gnu.zip"
    unzip -o /tmp/rathole.zip -d /usr/local/bin/
    chmod +x /usr/local/bin/rathole
    rm -f /tmp/rathole.zip
fi

echo "--- Creating Systemd Service ---"
cat << EOF > /etc/systemd/system/rathole-panel.service
[Unit]
Description=Rathole Panel Service
After=network.target

[Service]
Type=simple
WorkingDirectory=$(pwd)
ExecStart=/usr/bin/python3 app.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now rathole-panel

echo "------------------------------------------------"
echo "✅ Installation Complete Successfully!"
echo "🌐 Panel URL: http://$(curl -s https://api.ipify.org):8000"
echo "🔑 Default Password: 123456"
echo "------------------------------------------------"
