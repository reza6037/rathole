import os
import json
import subprocess
import asyncio
import paramiko
from fastapi import FastAPI, Request, Form, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

app = FastAPI()
templates = Jinja2Templates(directory="templates")

CONFIG_FILE = "config.json"
NODES_FILE = "nodes.json"
SERVER_TOML = "/etc/rathole/server.toml"
CORE_PORT = 2020

if not os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE, "w") as f:
        json.dump({"password": "123456", "core_port": CORE_PORT}, f)

if not os.path.exists(NODES_FILE):
    with open(NODES_FILE, "w") as f:
        json.dump([], f)

def get_config():
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)

def get_nodes():
    with open(NODES_FILE, "r") as f:
        return json.load(f)

def save_nodes(nodes):
    with open(NODES_FILE, "w") as f:
        json.dump(nodes, f, indent=4)

def update_iran_config(user_port: int):
    if not os.path.exists(SERVER_TOML):
        os.makedirs(os.path.dirname(SERVER_TOML), exist_ok=True)
        with open(SERVER_TOML, "w") as f:
            f.write(f'[server]\nbind_addr = "0.0.0.0:{CORE_PORT}"\ndefault_token = "musixal"\nheartbeat_interval = 30\n\n[server.transport]\ntype = "tcp"\n\n[server.transport.tcp]\nnodelay = true\n')

    with open(SERVER_TOML, "r") as f:
        content = f.read()

    service_block = f'\n[server.services.{user_port}]\ntype = "tcp"\nbind_addr = "0.0.0.0:{user_port}"\n'
    
    if f"[server.services.{user_port}]" not in content:
        with open(SERVER_TOML, "a") as f:
            f.write(service_block)
    
    subprocess.run(["ufw", "allow", f"{user_port}/tcp"], capture_output=True)
    subprocess.run(["systemctl", "restart", "rathole-server"], capture_output=True)

async def setup_remote_node(node_data: dict):
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(
            hostname=node_data['ip'],
            port=node_data['ssh_port'],
            username=node_data['ssh_user'],
            password=node_data['ssh_password'],
            timeout=15
        )

        iran_ip = "194.5.207.192"
        
        setup_script = f"""
        if [ ! -f /usr/local/bin/rathole ]; then
            ARCH=$(uname -m)
            if [ "$ARCH" = "x86_64" ]; then
                FILE="rathole-x86_64-unknown-linux-gnu.zip"
            elif [ "$ARCH" = "aarch64" ] || [ "$ARCH" = "arm64" ]; then
                FILE="rathole-aarch64-unknown-linux-musl.zip"
            fi
            wget -qO /tmp/rathole.zip "https://github.com/rathole-org/rathole/releases/download/v0.5.0/$FILE"
            unzip -o /tmp/rathole.zip -d /usr/local/bin/
            chmod +x /usr/local/bin/rathole
            rm -f /tmp/rathole.zip
        fi

        mkdir -p /etc/rathole
        cat << 'EOF' > /etc/rathole/client.toml
[client]
remote_addr = "{iran_ip}:{CORE_PORT}"
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
        """
        
        stdin, stdout, stderr = ssh.exec_command(setup_script)
        exit_status = stdout.channel.recv_exit_status()
        ssh.close()
        return exit_status == 0
    except Exception as e:
        print(f"SSH Error: {e}")
        return False

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(request, "index.html", {"nodes": get_nodes(), "config": get_config()})

@app.post("/update_password")
async def update_password(new_password: str = Form(...)):
    config = get_config()
    config["password"] = new_password
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f)
    return JSONResponse({"status": "success"})

@app.post("/add_node")
async def add_node(
    label: str = Form(...),
    ip: str = Form(...),
    ssh_port: int = Form(22),
    ssh_user: str = Form("root"),
    ssh_password: str = Form(...),
    user_port: int = Form(...),
    target_port: int = Form(...)
):
    update_iran_config(user_port)
    
    nodes = get_nodes()
    node_id = f"node_{len(nodes) + 1}"
    new_node = {
        "id": node_id,
        "name": label,
        "ip": ip,
        "ssh_port": ssh_port,
        "ssh_user": ssh_user,
        "ssh_password": ssh_password,
        "user_port": user_port,
        "target_port": target_port,
        "status": "pending"
    }
    nodes.append(new_node)
    save_nodes(nodes)
    
    asyncio.create_task(setup_remote_and_update_status(node_id, new_node))
    
    return RedirectResponse(url="/", status_code=303)

async def setup_remote_and_update_status(node_id, node_data):
    success = await setup_remote_node(node_data)
    nodes = get_nodes()
    for n in nodes:
        if n['id'] == node_id:
            n['status'] = 'active' if success else 'error'
            break
    save_nodes(nodes)

@app.get("/delete_node/{node_id}")
async def delete_node(node_id: str):
    nodes = get_nodes()
    nodes = [n for n in nodes if n['id'] != node_id]
    save_nodes(nodes)
    return RedirectResponse(url="/", status_code=303)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
