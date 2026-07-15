import os
import pty
import fcntl
import termios
import struct
import signal
import json
import asyncio
import logging
from fastapi import FastAPI, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import httpx

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("openhost_server")
# Suppress noisy HTTP requests logs from httpx proxy client
logging.getLogger("httpx").setLevel(logging.WARNING)

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
        "codex": ["codex", "login"],
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
            
        logger.info(f"PTY connection for command {command} closed.")

@app.get("/openhost/health")
async def openhost_health():
    return {"status": "ok"}

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
    uvicorn.run(app, host="0.0.0.0", port=admin_port)
