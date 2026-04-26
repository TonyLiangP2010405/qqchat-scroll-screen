"""运行控制API"""
import logging
import os
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional, Callable

router = APIRouter(prefix="/control", tags=["control"])

logger = logging.getLogger(__name__)

# 外部注入的状态和控制函数
_bot_status = {
    "running": True,
    "paused": False,
    "window_title": "",
    "window_online": False,
    "last_capture": "",
    "last_reply": "",
    "message_count": 0,
    "mode": "manual",
}

_send_message_func: Optional[Callable] = None
_test_api_func: Optional[Callable] = None
_switch_desktop_func: Optional[Callable] = None
_clear_history_func: Optional[Callable] = None


def set_bot_status(status: dict):
    global _bot_status
    _bot_status.update(status)


def get_bot_status() -> dict:
    return _bot_status.copy()


def set_send_message_func(func: Callable):
    global _send_message_func
    _send_message_func = func


def set_test_api_func(func: Callable):
    global _test_api_func
    _test_api_func = func


def set_switch_desktop_func(func: Callable):
    global _switch_desktop_func
    _switch_desktop_func = func


def set_clear_history_func(func: Callable):
    global _clear_history_func
    _clear_history_func = func


class SendMessageRequest(BaseModel):
    message: str


@router.get("/status")
async def get_status():
    """获取当前运行状态"""
    return get_bot_status()


@router.post("/pause")
async def pause_bot():
    """暂停自动回复"""
    _bot_status["paused"] = True
    return {"status": "success", "paused": True}


@router.post("/resume")
async def resume_bot():
    """恢复自动回复"""
    _bot_status["paused"] = False
    return {"status": "success", "paused": False}


@router.post("/send")
async def send_message(req: SendMessageRequest):
    """手动发送消息"""
    if _send_message_func is None:
        return {"status": "error", "message": "发送功能未初始化"}

    if not req.message.strip():
        return {"status": "error", "message": "消息不能为空"}

    try:
        _send_message_func(req.message)
        return {"status": "success", "message": "消息已发送"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.post("/test-api")
async def test_api():
    """测试大模型API连接"""
    if _test_api_func is None:
        return {"status": "error", "message": "测试功能未初始化"}

    try:
        result = _test_api_func()
        if result:
            return {"status": "success", "model": _bot_status.get("model", "")}
        else:
            return {"status": "error", "message": "API连接测试失败，请检查配置"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.post("/switch-desktop")
async def switch_desktop():
    """切换到QQ虚拟桌面"""
    if _switch_desktop_func is None:
        return {"status": "error", "message": "虚拟桌面功能未初始化"}

    try:
        _switch_desktop_func()
        return {"status": "success", "message": "已切换到QQ桌面"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.post("/clear-history")
async def clear_history():
    """清空历史记录和记忆"""
    if _clear_history_func is None:
        return {"status": "error", "message": "清空功能未初始化"}

    try:
        _clear_history_func()
        return {"status": "success", "message": "已清空所有历史记录"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.post("/capture-screen")
async def capture_screen():
    """截取全屏并保存为临时图片"""
    try:
        from PIL import ImageGrab
        import time

        screenshot = ImageGrab.grab()
        temp_dir = "web/static/temp"
        os.makedirs(temp_dir, exist_ok=True)
        filepath = os.path.join(temp_dir, "screenshot.png")
        screenshot.save(filepath, "PNG")

        # 返回图片URL（带时间戳防止缓存）
        ts = int(time.time())
        return {
            "status": "success",
            "url": f"/static/temp/screenshot.png?t={ts}",
            "size": screenshot.size
        }
    except Exception as e:
        logger.error(f"截图失败: {e}")
        return {"status": "error", "message": str(e)}


@router.post("/start-region-picker")
async def start_region_picker():
    """启动独立的浮动窗口区域选择工具"""
    import subprocess
    import sys

    try:
        # 使用 pythonw.exe 启动无控制台窗口
        python_exe = sys.executable.replace("python.exe", "pythonw.exe")
        if not os.path.exists(python_exe):
            python_exe = sys.executable

        subprocess.Popen(
            [python_exe, "region_picker_gui.py"],
            creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == "win32" else 0
        )
        return {"status": "success", "message": "区域选取工具已启动，请在屏幕右下角查看浮动窗口"}
    except Exception as e:
        logger.error(f"启动区域选取工具失败: {e}")
        return {"status": "error", "message": str(e)}


class RegionConfigRequest(BaseModel):
    read_rect: list
    reply_pos: list


@router.post("/region-config")
async def save_region_config(req: RegionConfigRequest):
    """保存区域配置到config.yaml"""
    try:
        import yaml

        config_path = "config.yaml"
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}

        if "capture" not in config:
            config["capture"] = {}

        config["capture"]["mode"] = "region"
        config["capture"]["read_rect"] = req.read_rect
        config["capture"]["reply_pos"] = req.reply_pos

        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(config, f, allow_unicode=True, sort_keys=False)

        return {"status": "success", "message": "区域配置已保存"}
    except Exception as e:
        logger.error(f"保存区域配置失败: {e}")
        return {"status": "error", "message": str(e)}
