#!/bin/bash
apt update && apt install -y python3 python3-fastapi python3-uvicorn python3-jinja2 python3-paramiko python3-cryptography python3-requests unzip curl wget
if [ ! -f /usr/local/bin/rathole ]; then
    wget -qO /tmp/rathole.zip "https://github.com/rathole-org/rathole/releases/download/v0.5.0/rathole-x86_64-unknown-linux-gnu.zip"
    unzip -o /tmp/rathole.zip -d /usr/local/bin/ && chmod +x /usr/local/bin/rathole
fi
CUR_DIR=$(pwd)
cat << EOF > /etc/systemd/system/rathole-panel.service
[Unit]
Description=Rathole Panel Service
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
systemctl daemon-reload && systemctl enable --now rathole-panel
