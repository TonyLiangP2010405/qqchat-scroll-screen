"""FastAPI Web服务入口"""
import logging
import os
from typing import Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse
import uvicorn

from web.api import config, messages, control

logger = logging.getLogger(__name__)

# 全局WebSocket连接管理器
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket客户端连接，当前连接数: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"WebSocket客户端断开，当前连接数: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)

        for conn in disconnected:
            self.disconnect(conn)


manager = ConnectionManager()

# FastAPI应用
app = FastAPI(title="QQ聊天机器人管理页面", version="1.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册API路由
app.include_router(config.router, prefix="/api")
app.include_router(messages.router, prefix="/api")
app.include_router(control.router, prefix="/api")

# 静态文件
app.mount("/static", StaticFiles(directory="web/static"), name="static")


@app.get("/")
async def root():
    return FileResponse("web/static/index.html")


# 日志API
@app.get("/api/logs")
async def get_logs(lines: int = 200):
    """获取最近N行日志"""
    log_file = "bot.log"
    if not os.path.exists(log_file):
        return {"logs": ["暂无日志文件"]}

    try:
        with open(log_file, "r", encoding="utf-8") as f:
            all_lines = f.readlines()
        recent = all_lines[-lines:] if len(all_lines) > lines else all_lines
        return {"logs": [line.rstrip() for line in recent]}
    except Exception as e:
        return {"logs": [f"读取日志失败: {e}"]}


@app.get("/api/logs/download")
async def download_log():
    """下载日志文件"""
    log_file = "bot.log"
    if os.path.exists(log_file):
        return FileResponse(log_file, filename="bot.log", media_type="text/plain")
    return PlainTextResponse("日志文件不存在", status_code=404)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.warning(f"WebSocket异常: {e}")
        manager.disconnect(websocket)


async def broadcast_message(msg_type: str, data: dict):
    """向所有WebSocket客户端广播消息"""
    await manager.broadcast({"type": msg_type, "data": data})


def run_server(host: str = "127.0.0.1", port: int = 8080):
    """启动Web服务器（阻塞调用，应在独立线程中运行）"""
    logger.info(f"启动Web管理页面: http://{host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level="warning")
