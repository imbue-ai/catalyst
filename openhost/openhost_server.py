import os
import pty
import fcntl
import termios
import struct
import signal
import json
import asyncio
import logging
import subprocess
import time
from typing import Optional, Dict
from fastapi import FastAPI, Request, Response, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import httpx

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("openhost_server")
# Suppress noisy HTTP requests logs from httpx proxy client and uvicorn access logs
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

app = FastAPI(title="OpenHost Admin & Proxy Gateway")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

CATALYST_PORT = os.environ.get("CATALYST_PORT", "8141")
CATALYST_URL = f"http://127.0.0.1:{CATALYST_PORT}"

# Create httpx async client for proxying with no timeout to support long running queries
client = httpx.AsyncClient(base_url=CATALYST_URL, timeout=None)

# Process handle for spawned Catalyst backend server
catalyst_process: Optional[subprocess.Popen] = None

def get_env_file_path() -> Optional[str]:
    app_data_dir = os.environ.get("OPENHOST_APP_DATA_DIR")
    if not app_data_dir:
        logger.warning("OPENHOST_APP_DATA_DIR environment variable is not set. Environment variables will not be loaded or persisted.")
        return None
    os.makedirs(app_data_dir, exist_ok=True)
    return os.path.join(app_data_dir, "env_vars.json")

def load_env_vars() -> Dict[str, str]:
    path = get_env_file_path()
    if path and os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return {str(k): str(v) for k, v in data.items()}
        except Exception as e:
            logger.error(f"Failed to load env_vars.json from {path}: {e}")
    return {}

def save_env_vars(env_dict: Dict[str, str]) -> Dict[str, str]:
    path = get_env_file_path()
    if not path:
        logger.warning("Cannot save env_vars.json because OPENHOST_APP_DATA_DIR is not set.")
        return env_dict
    clean_dict = {str(k).strip(): str(v) for k, v in env_dict.items() if str(k).strip()}
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(clean_dict, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save env_vars.json to {path}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save environment variables: {e}")
    return clean_dict

def stop_running_catalyst():
    global catalyst_process
    if catalyst_process and catalyst_process.poll() is None:
        logger.info(f"Terminating tracked Catalyst process PID {catalyst_process.pid}...")
        try:
            catalyst_process.terminate()
            catalyst_process.wait(timeout=60)
        except Exception as e:
            logger.warning(f"Error terminating tracked process: {e}")
            if catalyst_process.poll() is None:
                try:
                    catalyst_process.kill()
                except Exception:
                    pass
        catalyst_process = None


def start_catalyst_server():
    global catalyst_process
    env = os.environ.copy()
    custom_env = load_env_vars()
    env.update(custom_env)

    env["CATALYST_PORT"] = os.environ.get("CATALYST_PORT", "8141")

    src_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
    if not os.path.exists(src_dir):
        src_dir = os.getcwd()

    cmd = ["uv", "run", "python", "server.py"]
    logger.info(f"Spawning Catalyst server.py in {src_dir} with env overrides: {list(custom_env.keys())}")

    catalyst_process = subprocess.Popen(
        cmd,
        cwd=src_dir,
        env=env,
    )
    logger.info(f"Catalyst server.py started with PID {catalyst_process.pid}")

def restart_catalyst_server():
    stop_running_catalyst()
    time.sleep(1)
    start_catalyst_server()

@app.on_event("startup")
async def startup_event():
    logger.info("OpenHost Gateway starting. Spawning Catalyst backend server...")
    start_catalyst_server()

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("OpenHost Gateway shutting down. Terminating Catalyst backend server...")
    stop_running_catalyst()


class EnvVarsRequest(BaseModel):
    env: Dict[str, str]

@app.get("/openhost/api/env")
async def get_env_endpoint():
    env_vars = load_env_vars()
    return {
        "env": env_vars,
        "openhost_app_data_dir_set": bool(os.environ.get("OPENHOST_APP_DATA_DIR"))
    }

@app.post("/openhost/api/env")
async def save_env_endpoint(req: EnvVarsRequest):
    saved = save_env_vars(req.env)
    return {"status": "ok", "env": saved}

@app.post("/openhost/api/restart")
async def restart_endpoint(req: Optional[EnvVarsRequest] = None):
    if req and req.env is not None:
        save_env_vars(req.env)

    logger.info("Restart request received. Restarting Catalyst backend server...")
    try:
        restart_catalyst_server()
        return {"status": "ok", "message": "Catalyst backend server restart initiated"}
    except Exception as e:
        logger.error(f"Failed to restart Catalyst server: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to restart Catalyst server: {e}")

def set_pty_size(fd, rows, cols):

    """Set the window size of a pseudo-terminal descriptor."""
    try:
        size = struct.pack("HHHH", rows, cols, 0, 0)
        fcntl.ioctl(fd, termios.TIOCSWINSZ, size)
    except Exception as e:
        logger.error(f"Failed to set PTY size: {e}")

@app.websocket("/openhost/api/pty/{command}")
async def pty_ws(websocket: WebSocket, command: str):
    await websocket.accept()
    logger.info(f"Accepted WebSocket connection for command: {command}")
    
    cmd_map = {
        "agy": ["agy"],
        "codex": ["codex", "login", "--device-auth"],
        "gemini": ["gemini"],
        "claude": ["claude", "auth", "login"],
    }
    
    if command not in cmd_map:
        await websocket.send_text("Error: Unknown command\r\n")
        await websocket.close()
        return
        
    cmd = cmd_map[command]
    
    # Fork pseudo-terminal
    pid, fd = pty.fork()
    if pid == 0:
        # Child process
        # Set default terminal size in the child process to guarantee non-zero size before execvp
        set_pty_size(0, 24, 80)
        os.environ["TERM"] = "xterm-256color"
        try:
            os.execvp(cmd[0], cmd)
        except Exception as e:
            print(f"Error executing command {cmd}: {e}")
            os._exit(1)
    else:
        # Parent process
        # Set default terminal size
        set_pty_size(fd, 24, 80)
        
        # Set fd to non-blocking
        flags = fcntl.fcntl(fd, fcntl.F_GETFL)
        fcntl.fcntl(fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
        
        queue = asyncio.Queue()
        loop = asyncio.get_running_loop()
        
        def on_read():
            try:
                data = os.read(fd, 4096)
                if not data:
                    loop.remove_reader(fd)
                    queue.put_nowait(None)
                else:
                    queue.put_nowait(data)
            except Exception:
                loop.remove_reader(fd)
                queue.put_nowait(None)
                
        loop.add_reader(fd, on_read)
        
        async def read_from_pty():
            try:
                while True:
                    data = await queue.get()
                    if data is None:
                        break
                    await websocket.send_bytes(data)
            except Exception as e:
                logger.error(f"Error reading from PTY: {e}")
            finally:
                try:
                    loop.remove_reader(fd)
                except Exception:
                    pass
                
        async def write_to_pty():
            try:
                while True:
                    msg = await websocket.receive()
                    if "text" in msg:
                        text_data = msg["text"]
                        # Check for resize event
                        if text_data.startswith('{"resize":'):
                            try:
                                data = json.loads(text_data)
                                cols, rows = data["resize"]
                                set_pty_size(fd, rows, cols)
                            except Exception as e:
                                logger.error(f"Error parsing resize: {e}")
                        else:
                            os.write(fd, text_data.encode("utf-8"))
                    elif "bytes" in msg:
                        os.write(fd, msg["bytes"])
                    else:
                        break
            except WebSocketDisconnect:
                pass
            except Exception as e:
                logger.error(f"Error writing to PTY: {e}")

        # Run reader and writer tasks concurrently
        reader_task = asyncio.create_task(read_from_pty())
        writer_task = asyncio.create_task(write_to_pty())
        
        done, pending = await asyncio.wait(
            [reader_task, writer_task],
            return_when=asyncio.FIRST_COMPLETED
        )
        for task in pending:
            task.cancel()
            
        # Unregister reader synchronously before closing the file descriptor!
        try:
            loop.remove_reader(fd)
        except Exception:
            pass

        # Cleanup
        try:
            os.close(fd)
        except OSError:
            pass
        try:
            # Kill process group / child process gracefully first
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass
            
        # Reap child process asynchronously to prevent zombie processes
        async def reap_child():
            try:
                for _ in range(20):
                    res_pid, _ = os.waitpid(pid, os.WNOHANG)
                    if res_pid == pid:
                        return
                    await asyncio.sleep(0.1)
                os.kill(pid, signal.SIGKILL)
                os.waitpid(pid, 0)
            except OSError:
                pass
                
        asyncio.create_task(reap_child())
            
        logger.info(f"PTY connection for command {command} closed.")

@app.get("/openhost/health")
async def openhost_health():
    try:
        # Verify that the Catalyst backend is up and responsive before returning ok
        await client.request("HEAD", "/", timeout=5.0)
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"OpenHost Health Check Failed: Catalyst backend on port {CATALYST_PORT} is not responsive: {e}")
        return Response(content="Catalyst backend is not running or responsive", status_code=503)

# Mount the static openhost admin panel directly
frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "frontend", "dist"))
if os.path.exists(frontend_dir):
    logger.info(f"Mounting OpenHost admin frontend static directory: {frontend_dir}")
    app.mount("/openhost", StaticFiles(directory=frontend_dir, html=True), name="openhost_static")
else:
    logger.warning(f"OpenHost admin frontend directory NOT found at {frontend_dir}. Please build frontend first.")

# Catch-all proxy to redirect all other traffic to Catalyst on 8141
@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"])
async def proxy_catch_all(request: Request, path: str):
    # Construct full proxied URL
    url = httpx.URL(path=request.url.path, query=request.url.query.encode("utf-8"))
    body = await request.body()
    
    # Filter request headers to avoid conflicts
    headers = dict(request.headers)
    headers.pop("host", None)
    headers.pop("content-length", None)
    
    req = client.build_request(
        method=request.method,
        url=url,
        headers=headers,
        content=body,
    )
    
    try:
        res = await client.send(req, stream=True)
    except Exception as e:
        logger.error(f"Error proxying request to {url}: {e}")
        return Response(
            content=f"Error connecting to backend Catalyst server: {e}\nIs the Catalyst server starting up?",
            status_code=502
        )
        
    return StreamingResponse(
        res.aiter_raw(),
        status_code=res.status_code,
        headers=dict(res.headers),
        background=res.aclose,
    )

if __name__ == "__main__":
    import uvicorn
    admin_port = int(os.environ.get("ADMIN_PORT", 8139))
    logger.info(f"Starting OpenHost Admin gateway on port {admin_port}")
    uvicorn.run(app, host="0.0.0.0", port=admin_port, access_log=False)
