import os
import json
import subprocess
import asyncio
import paramiko
import requests
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
NODES_FILE = os.path.join(BASE_DIR, "nodes.json")
SERVER_TOML = "/etc/rathole/server.toml"

app = FastAPI()
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

try:
    IRAN_IP = requests.get('https://api.ipify.org', timeout=5).text.strip()
except:
    IRAN_IP = "127.0.0.1"

def get_config():
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "w") as f: json.dump({"password": "123456"}, f)
    with open(CONFIG_FILE, "r") as f: return json.load(f)

def get_nodes():
    if not os.path.exists(NODES_FILE):
        with open(NODES_FILE, "w") as f: json.dump([], f)
    with open(NODES_FILE, "r") as f: return json.load(f)

def save_nodes(nodes):
    with open(NODES_FILE, "w") as f: json.dump(nodes, f, indent=4)

def update_iran_config(core_port: int, user_port: int):
    os.makedirs(os.path.dirname(SERVER_TOML), exist_ok=True)
    
    # If file doesn't exist, create it with the provided core_port
    if not os.path.exists(SERVER_TOML):
        content = f'[server]\nbind_addr = "0.0.0.0:{core_port}"\ndefault_token = "musixal"\nheartbeat_interval = 30\n\n[server.transport]\ntype = "tcp"\n\n[server.transport.tcp]\nnodelay = true\n'
        with open(SERVER_TOML, "w") as f: f.write(content)
    else:
        # File exists, check if we need to update global bind_addr or just add service
        with open(SERVER_TOML, "r") as f: content = f.read()
        # Ensure the server binds to the correct port (simple string replace for bind_addr)
        import re
        content = re.sub(r'bind_addr = "0.0.0.0:\d+"', f'bind_addr = "0.0.0.0:{core_port}"', content)
        
        service_block = f'\n[server.services.{user_port}]\ntype = "tcp"\nbind_addr = "0.0.0.0:{user_port}"\n'
        if f"[server.services.{user_port}]" not in content:
            content += service_block
        
        with open(SERVER_TOML, "w") as f: f.write(content)
    
    subprocess.run(["ufw", "allow", f"{core_port}/tcp"], capture_output=True)
    subprocess.run(["ufw", "allow", f"{user_port}/tcp"], capture_output=True)
    subprocess.run(["systemctl", "restart", "rathole-server"], capture_output=True)

async def setup_remote_node(node_data: dict):
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(node_data['ip'], port=node_data['ssh_port'], username=node_data['ssh_user'], password=node_data['ssh_password'], timeout=15)
        
        setup_script = f"""
        if [ ! -f /usr/local/bin/rathole ]; then
            ARCH=$(uname -m)
            FILE="rathole-x86_64-unknown-linux-gnu.zip"
            if [ "$ARCH" = "aarch64" ] || [ "$ARCH" = "arm64" ]; then FILE="rathole-aarch64-unknown-linux-musl.zip"; fi
            wget -qO /tmp/rathole.zip "https://github.com/rathole-org/rathole/releases/download/v0.5.0/$FILE"
            unzip -o /tmp/rathole.zip -d /usr/local/bin/
            chmod +x /usr/local/bin/rathole
            rm -f /tmp/rathole.zip
        fi
        mkdir -p /etc/rathole
        cat << 'EOF' > /etc/rathole/client.toml
[client]
remote_addr = "{IRAN_IP}:{node_data['core_port']}"
default_token = "musixal"
heartbeat_interval = 30
[client.transport]
type = "tcp"
[client.transport.tcp]
nodelay = true
[client.services.{node_data['user_port']}]
type = "tcp"
local_addr = "127.0.0.1:{node_data['target_port']}"
EOF
        cat << 'EOF' > /etc/systemd/system/rathole.service
[Unit]
Description=Rathole Client Tunnel
After=network.target
[Service]
Type=simple
ExecStart=/usr/local/bin/rathole --client /etc/rathole/client.toml
Restart=always
RestartSec=3
[Install]
WantedBy=multi-user.target
EOF
        systemctl daemon-reload
        systemctl enable --now rathole
        systemctl restart rathole
        """
        stdin, stdout, stderr = ssh.exec_command(setup_script)
        exit_code = stdout.channel.recv_exit_status()
        ssh.close()
        return exit_code == 0
    except: return False

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(request, "index.html", {"nodes": get_nodes(), "config": get_config()})

class NodeModel(BaseModel):
    label: str; ip: str; ssh_port: int; ssh_user: str; ssh_password: str; 
    core_port: int; user_port: int; target_port: int

@app.post("/add_node")
async def add_node(data: NodeModel):
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(data.ip, port=data.ssh_port, username=data.ssh_user, password=data.ssh_password, timeout=10)
        ssh.close()
    except Exception as e:
        return JSONResponse({"status": "error", "message": f"خطا در اتصال SSH: {str(e)}"}, status_code=400)

    try:
        update_iran_config(data.core_port, data.user_port)
    except Exception as e:
        return JSONResponse({"status": "error", "message": f"خطا در سرور ایران: {str(e)}"}, status_code=400)

    nodes = get_nodes()
    node_id = f"node_{len(nodes) + 1}"
    node_data = {
        "id": node_id, "name": data.label, "ip": data.ip, "ssh_port": data.ssh_port,
        "ssh_user": data.ssh_user, "ssh_password": data.ssh_password,
        "core_port": data.core_port, "user_port": data.user_port, "target_port": data.target_port, "status": "active"
    }
    
    success = await setup_remote_node(node_data)
    if not success:
        node_data["status"] = "error"
        nodes.append(node_data); save_nodes(nodes)
        return JSONResponse({"status": "error", "message": "نصب روی سرور خارج با خطا مواجه شد."}, status_code=400)

    nodes.append(node_data); save_nodes(nodes)
    return JSONResponse({"status": "success", "message": "تانل با موفقیت نصب و متصل گردید."})

@app.get("/delete_node/{node_id}")
async def delete_node(node_id: str):
    nodes = [n for n in get_nodes() if n['id'] != node_id]
    save_nodes(nodes); return JSONResponse({"status": "success"})

class PasswordModel(BaseModel):
    new_password: str

@app.post("/update_password")
async def update_password(data: PasswordModel):
    config = get_config(); config["password"] = data.new_password
    with open(CONFIG_FILE, "w") as f: json.dump(config, f)
    return JSONResponse({"status": "success"})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
