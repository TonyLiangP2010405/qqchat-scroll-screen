"""
QQ群聊自动回复机器人 - 桌面控制台版

运行方式：
    python main.py

功能：
1. 后台运行机器人主循环（截图/OCR/LLM/自动输入）
2. 桌面浮动控制台（状态显示/设置区域/发送消息/配置管理/查看记录和日志）
"""
import io
import logging
import os
import random
import sys
import threading
import time
import glob
import shutil
import subprocess
from datetime import datetime
from typing import Optional

from modules.platform_utils import enable_dpi_awareness

# Windows控制台UTF-8编码修复
if sys.platform == "win32":
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")
    except Exception:
        pass
    enable_dpi_awareness()

import yaml
from PIL import Image, ImageGrab

from modules.desktop_manager import DesktopManager
from modules.window_finder import WindowFinder
from modules.screenshot import Screenshot
from modules.ocr_engine import OCREngine
from modules.message_parser import MessageParser, ChatMessage
from modules.llm_client import LLMClient
from modules.auto_typer import AutoTyper
from modules.memory_store import MemoryStore


class BotState:
    def __init__(self):
        self.running = True
        self.paused = False
        self.hwnd: Optional[int] = None
        self.window_title = ""
        self.last_capture_time = ""
        self.last_reply = ""
        self.last_detected = ""
        self.message_count = 0
        self.mode = "manual"


# 尝试导入 keyboard 库（全局快捷键）
try:
    import keyboard
    KEYBOARD_AVAILABLE = True
except ImportError:
    KEYBOARD_AVAILABLE = False
    keyboard = None


class BotController:
    """机器人核心控制器 - 供UI层调用"""

    def __init__(self):
        self.state = BotState()
        self.config = {}
        self.config_path = "config.yaml"
        self._last_mtime = 0

        # 模块（延迟初始化）
        self.desktop = None
        self.finder = None
        self.screenshot = None
        self.ocr = None
        self.parser = None
        self.llm = None
        self.typer = None
        self.memory = None

        # 快捷引用
        self.capture_config = {}
        self.bot_config = {}
        self.memory_config = {}

    def setup_logging(self):
        # 确保控制台日志实时刷新
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.flush = sys.stdout.flush

        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%H:%M:%S",
            handlers=[
                console_handler,
                logging.FileHandler("bot.log", encoding="utf-8")
            ]
        )
        return logging.getLogger("main")

    def load_config(self):
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                self.config = yaml.safe_load(f) or {}
            self.config = self._normalize_config(self.config)
            self._last_mtime = os.path.getmtime(self.config_path)
        except Exception as e:
            logging.error(f"加载配置失败: {e}")
        self.capture_config = self.config.get("capture", {})
        self.bot_config = self.config.get("bot", {})
        self.memory_config = self.config.get("memory", {})
        self.state.mode = self.capture_config.get("mode", "manual")
        return self.config

    def save_config(self, config: dict) -> bool:
        try:
            config = self._normalize_config(config)
            with open(self.config_path, "w", encoding="utf-8") as f:
                yaml.dump(config, f, allow_unicode=True, sort_keys=False)
            self.config = config
            self._last_mtime = os.path.getmtime(self.config_path)
            self.capture_config = config.get("capture", {})
            self.bot_config = config.get("bot", {})
            self.memory_config = config.get("memory", {})
            self.state.mode = self.capture_config.get("mode", "manual")
            if self.parser:
                self.parser.bot_name = self.bot_config.get("name", "")
            new_llm = self._create_llm()
            if new_llm:
                self.llm = new_llm
            return True
        except Exception as e:
            logging.getLogger("main").error(f"保存配置失败: {e}")
            return False

    def check_reload(self):
        try:
            mtime = os.path.getmtime(self.config_path)
            if mtime != self._last_mtime:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    self.config = yaml.safe_load(f) or {}
                self.config = self._normalize_config(self.config)
                self._last_mtime = mtime
                self.capture_config = self.config.get("capture", {})
                self.bot_config = self.config.get("bot", {})
                self.memory_config = self.config.get("memory", {})
                self.state.mode = self.capture_config.get("mode", "manual")
                if self.parser:
                    self.parser.bot_name = self.bot_config.get("name", "")
                new_llm = self._create_llm()
                if new_llm:
                    self.llm = new_llm
                return True
        except Exception:
            pass
        return False

    def _normalize_config(self, config: dict) -> dict:
        config = dict(config or {})
        config.setdefault("llm", {})
        config.setdefault("bot", {})
        config.setdefault("capture", {})
        config.setdefault("filter", {})
        config.setdefault("memory", {})

        llm = config["llm"]
        try:
            llm["temperature"] = max(0.0, min(float(llm.get("temperature", 0.7)), 2.0))
        except Exception:
            llm["temperature"] = 0.7
        try:
            llm["max_tokens"] = max(1, min(int(llm.get("max_tokens", 500)), 2000))
        except Exception:
            llm["max_tokens"] = 500

        bot = config["bot"]
        try:
            bot["reply_probability"] = max(0.0, min(float(bot.get("reply_probability", 1.0)), 1.0))
        except Exception:
            bot["reply_probability"] = 1.0

        capture = config["capture"]
        try:
            capture["interval"] = max(1, int(capture.get("interval", 10)))
        except Exception:
            capture["interval"] = 10
        try:
            capture["message_area_ratio"] = max(0.1, min(float(capture.get("message_area_ratio", 0.7)), 1.0))
        except Exception:
            capture["message_area_ratio"] = 0.7

        filter_cfg = config["filter"]
        try:
            filter_cfg["max_history_messages"] = max(1, int(filter_cfg.get("max_history_messages", 10)))
        except Exception:
            filter_cfg["max_history_messages"] = 10

        memory = config["memory"]
        try:
            memory["load_recent"] = max(0, int(memory.get("load_recent", 20)))
        except Exception:
            memory["load_recent"] = 20

        return config

    def _create_llm(self):
        cfg = self.config.get("llm", {})
        url = cfg.get("base_url", "").strip()
        key = self._resolve_secret(cfg.get("api_key", ""))
        model = cfg.get("model", "").strip()
        if not url or not key or not model:
            return None
        try:
            return LLMClient(
                base_url=url, api_key=key, model=model,
                max_tokens=cfg.get("max_tokens", 500),
                temperature=cfg.get("temperature", 0.7)
            )
        except Exception as e:
            logging.getLogger("main").error(f"创建LLM客户端失败: {e}")
            return None

    def _resolve_secret(self, value: str) -> str:
        value = str(value or "").strip()
        if value.startswith("env:"):
            return os.getenv(value[4:].strip(), "").strip()
        if value.startswith("${") and value.endswith("}"):
            return os.getenv(value[2:-1].strip(), "").strip()
        return value

    def init(self):
        logger = self.setup_logging()
        logger.info("=" * 50)
        logger.info("QQ聊天机器人启动")
        logger.info("=" * 50)

        self.load_config()
        if not self.config:
            logger.error("无法加载配置，请检查 config.yaml")
            return False

        try:
            dc = self.config.get("desktop", {})
            self.desktop = DesktopManager(enabled=dc.get("enabled", True), desktop_name=dc.get("desktop_name", "QQ机器人"))
            cc = self.capture_config
            self.finder = WindowFinder(title_keywords=cc.get("window_title_keywords", ["QQ"]))
            self.screenshot = Screenshot(debug=cc.get("debug_screenshots", False), debug_dir=cc.get("debug_dir", "debug_screenshots"))
            logger.info("正在初始化OCR引擎...")
            self.ocr = OCREngine(languages=["ch_sim", "en"], gpu=False)
            self.parser = MessageParser(bot_name=self.bot_config.get("name", ""))
            self.llm = self._create_llm()
            self.typer = AutoTyper(safety_delay=0.5)
            self.memory = MemoryStore(
                data_dir=self.memory_config.get("data_dir", "data"),
                split_by_date=self.memory_config.get("split_by_date", True)
            )
            recent_records = self.memory.load_recent(max(
                self.memory_config.get("load_recent", 20),
                self.config.get("filter", {}).get("max_history_messages", 10)
            ))
            self.parser.seed_history(recent_records)
            logger.info("所有模块初始化完成")
            if self.llm:
                logger.info("LLM客户端已就绪")
            else:
                logger.warning("LLM未配置，请在配置窗口设置API信息")
            self.setup_hotkeys()
            return True
        except Exception as e:
            logger.error(f"模块初始化失败: {e}")
            return False

    def setup_hotkeys(self):
        """注册全局快捷键（需安装 keyboard 库: pip install keyboard）"""
        logger = logging.getLogger("main")
        if not KEYBOARD_AVAILABLE:
            logger.warning("未安装 keyboard 库，全局快捷键不可用")
            logger.warning("如需全局快捷键，请运行: pip install keyboard")
            return

        try:
            # Ctrl+Q 退出程序
            keyboard.add_hotkey("ctrl+q", self._on_hotkey_quit, suppress=False)
            # Ctrl+P 暂停/恢复
            keyboard.add_hotkey("ctrl+p", self._on_hotkey_pause, suppress=False)
            logger.info("全局快捷键已注册: Ctrl+Q=退出, Ctrl+P=暂停/恢复")
        except Exception as e:
            logger.warning(f"注册全局快捷键失败: {e}")

    def _on_hotkey_quit(self):
        logging.getLogger("main").info("收到快捷键 Ctrl+Q，正在退出...")
        self.state.running = False
        # 尝试关闭桌面控制台窗口
        try:
            import tkinter as tk
            for widget in tk.Tcl().interps():
                pass  # 无法直接关闭其他tkinter实例
        except Exception:
            pass

    def _on_hotkey_pause(self):
        if self.state.paused:
            logging.getLogger("main").info("收到快捷键 Ctrl+P，恢复运行")
            self.resume()
        else:
            logging.getLogger("main").info("收到快捷键 Ctrl+P，暂停运行")
            self.pause()

    def get_status(self):
        region_ready = (
            self.capture_config.get("mode") == "region"
            and isinstance(self.capture_config.get("read_rect"), (list, tuple))
            and len(self.capture_config.get("read_rect")) == 4
        )
        window_online = self.state.hwnd is not None or region_ready
        return {
            "running": self.state.running,
            "paused": self.state.paused,
            "mode": self.state.mode,
            "window_title": self.state.window_title or ("区域坐标已配置" if region_ready else ""),
            "window_online": window_online,
            "last_capture": self.state.last_capture_time,
            "last_reply": self.state.last_reply,
            "last_detected": self.state.last_detected,
            "message_count": self.state.message_count,
        }

    def pause(self):
        self.state.paused = True
        logging.getLogger("main").info("已暂停")

    def resume(self):
        self.state.paused = False
        logging.getLogger("main").info("已恢复")

    def test_api(self):
        return self.llm.test_connection() if self.llm else False

    def clear_history(self):
        if self.parser:
            self.parser.clear_history()
        if not self.memory:
            return
        patterns = ["chat_history_*.jsonl", "chat_history.jsonl"]
        for pattern in patterns:
            files = glob.glob(os.path.join(self.memory.data_dir, pattern))
            for f in files:
                try:
                    os.remove(f)
                except Exception:
                    pass
        logging.getLogger("main").info("已清空所有历史记录")

    def _get_region_reply_pos(self):
        reply_pos = self.capture_config.get("reply_pos")
        if isinstance(reply_pos, (list, tuple)) and len(reply_pos) == 2:
            try:
                return int(reply_pos[0]), int(reply_pos[1])
            except Exception:
                pass
        return None

    def send_message(self, msg: str):
        if not self.typer or not msg.strip():
            return
        text = msg.strip()
        reply_pos = self._get_region_reply_pos()
        if reply_pos:
            self.typer.type_at_position(reply_pos[0], reply_pos[1], text)
            return
        if not self.typer.safe_type(self.state.hwnd, text):
            self.typer.copy_to_clipboard_only(text)

    def get_config(self):
        return dict(self.config)

    def get_messages(self, count=50):
        if not self.memory:
            return []
        return self.memory.load_recent(count)

    def get_memory_records(self, count=100):
        """获取记忆记录（用于记忆管理窗口）"""
        if not self.memory:
            return []
        return self.memory.load_recent(count)

    def export_messages(self, filepath="chat_export.json"):
        """导出所有聊天记录到JSON文件"""
        try:
            import json
            msgs = self.memory.load_recent(9999)
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(msgs, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logging.getLogger("main").error(f"导出失败: {e}")
            return False

    def switch_desktop(self):
        """切换到QQ虚拟桌面"""
        if self.desktop and self.desktop.available:
            try:
                self.desktop.switch_to()
                return True
            except Exception as e:
                logging.getLogger("main").warning(f"切换虚拟桌面失败: {e}")
        return False

    def get_logs(self, lines=100):
        try:
            with open("bot.log", "r", encoding="utf-8") as f:
                all_lines = f.readlines()
            return all_lines[-lines:] if len(all_lines) > lines else all_lines
        except Exception:
            return []

    def start_region_picker(self):
        script = os.path.join(os.path.dirname(__file__), "region_picker_gui.py")
        try:
            py = sys.executable.replace("python.exe", "pythonw.exe")
            if not os.path.exists(py):
                py = sys.executable
            subprocess.Popen([py, script], creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == "win32" else 0)
            return True
        except Exception as e:
            logging.getLogger("main").error(f"启动区域选择器失败: {e}")
            return False

    # ====== 内部处理流程 ======

    def _ocr_pipeline(self, image, label=""):
        resized = self.screenshot.resize_for_ocr(image, max_width=1280)
        results = self.ocr.recognize(resized)
        if not results:
            return None, []
        messages = self.parser.parse_ocr_results(results)
        if not messages:
            return None, []
        new_msgs = self.parser.get_new_messages(messages)
        if not new_msgs:
            return None, []

        if self.memory_config.get("enabled", True):
            self.memory.save_messages(new_msgs)

        # 限制一次处理的新消息数量，防止截图区域包含太多消息
        if len(new_msgs) > 3:
            logger = logging.getLogger("main")
            logger.info(f"一次检测到 {len(new_msgs)} 条新消息，只取最新 3 条")
            new_msgs = new_msgs[-3:]

        # 打印识别到的消息，方便排查
        logger = logging.getLogger("main")
        for m in new_msgs:
            logger.info(f"[识别] {m.sender}: {m.content[:40]}")
        # 更新状态栏显示
        if new_msgs:
            self.state.last_detected = f"{new_msgs[-1].sender}: {new_msgs[-1].content[:30]}"

        if self.config.get("filter", {}).get("ignore_my_messages", True):
            new_msgs = self.parser.filter_bot_messages(new_msgs)
            if not new_msgs:
                return None, []

        # 额外过滤：如果消息内容和机器人上次发的回复高度相似，说明是机器人自己的消息被OCR识别到了
        last_reply = self.state.last_reply
        if last_reply:
            import difflib
            filtered = []
            for m in new_msgs:
                sim = difflib.SequenceMatcher(None, m.content, last_reply).ratio()
                if sim >= 0.75:
                    logger.info(f"[过滤] 消息与上次回复相似度{sim:.0%}，判定为自身消息: {m.content[:30]}")
                    continue
                filtered.append(m)
            new_msgs = filtered
            if not new_msgs:
                return None, []
        # 回复概率检查
        prob = self.bot_config.get("reply_probability", 1.0)
        if random.random() > prob:
            logging.getLogger("main").info(f"未命中回复概率 ({prob:.0%})，跳过本次回复")
            return None, new_msgs

        if not self.llm:
            return None, new_msgs

        new_hashes = {m.msg_hash for m in new_msgs}
        recent = self.parser.get_recent_history(self.config.get("filter", {}).get("max_history_messages", 10))
        mem = self.memory.load_recent(self.memory_config.get("load_recent", 20)) if self.memory else []
        mem_ctx = [
            ChatMessage(
                sender=r.get("sender", ""),
                content=r.get("content", ""),
                is_bot=r.get("is_bot", False),
                timestamp=r.get("timestamp", "")
            )
            for r in mem
        ]
        history = []
        seen_hashes = set()
        for msg in mem_ctx + recent:
            if msg.msg_hash in new_hashes or msg.msg_hash in seen_hashes:
                continue
            history.append(msg)
            seen_hashes.add(msg.msg_hash)

        ctx = self.llm.build_chat_context(history=history, new_messages=new_msgs, bot_name=self.bot_config.get("name", ""))
        prompt = self.bot_config.get("system_prompt", "你是一个 helpful assistant.")
        reply = self.llm.chat(prompt, ctx)
        return reply, new_msgs

    def _send_reply(self, reply):
        if not reply:
            return
        self.state.last_reply = reply[:100]
        self.typer.copy_to_clipboard_only(reply)
        ok = self.typer.safe_type(self.state.hwnd, reply)
        if ok:
            self.memory.save_message(sender=self.bot_config.get("name", "机器人"), content=reply, is_bot=True)
            self.parser.get_new_messages([ChatMessage(sender=self.bot_config.get("name", "机器人"), content=reply, is_bot=True)])
            self.state.message_count += 1
        else:
            logging.getLogger("main").info("自动输入未成功，回复已复制到剪贴板")

    def _send_reply_at(self, reply, pos):
        if not reply:
            return
        self.state.last_reply = reply[:100]

        self.typer.copy_to_clipboard_only(reply)
        ok = self.typer.type_at_position(pos[0], pos[1], reply)
        if ok:
            self.memory.save_message(sender=self.bot_config.get("name", "机器人"), content=reply, is_bot=True)
            self.parser.get_new_messages([ChatMessage(sender=self.bot_config.get("name", "机器人"), content=reply, is_bot=True)])
            self.state.message_count += 1
        else:
            logging.getLogger("main").info("自动输入未成功，回复已复制到剪贴板")

    def run_loop(self):
        logger = logging.getLogger("main")
        mode = self.capture_config.get("mode", "manual")
        interval = self.capture_config.get("interval", 10)
        read_rect = self.capture_config.get("read_rect")
        reply_pos = self.capture_config.get("reply_pos")
        finder = self.finder

        # 模式初始化
        if mode == "manual":
            pd = os.path.join(self.capture_config.get("screenshot_dir", "screenshots"), "processed")
            os.makedirs(pd, exist_ok=True)
            logger.info("=" * 50)
            logger.info("手动截图模式已启动")
            logger.info(f"请将截图保存到: {os.path.abspath(self.capture_config.get('screenshot_dir', 'screenshots'))}")
            logger.info("=" * 50)
            self.state.hwnd = finder.find_qq_chat_window()
            if self.state.hwnd:
                self.state.window_title = finder.get_window_title(self.state.hwnd)

        elif mode == "region":
            if read_rect and isinstance(read_rect, (list, tuple)) and len(read_rect) == 4:
                logger.info("=" * 50)
                logger.info("屏幕区域模式已启动")
                logger.info(f"消息区域: {read_rect}")
                if reply_pos and len(reply_pos) == 2:
                    logger.info(f"回复位置: {reply_pos}")
                logger.info("=" * 50)
            else:
                logger.warning("=" * 50)
                logger.warning("区域模式已启动，尚未配置坐标")
                logger.warning("请点击桌面控制台的 [设置区域] 按钮进行配置")
                logger.warning("=" * 50)

        else:
            logger.info("正在寻找QQ聊天窗口...")
            while self.state.running and not self.state.hwnd:
                self.state.hwnd = finder.find_qq_chat_window()
                if not self.state.hwnd:
                    time.sleep(5)
                else:
                    self.state.window_title = finder.get_window_title(self.state.hwnd)
                    logger.info(f"已锁定窗口: {self.state.window_title}")

        last_check = time.time()
        pd = os.path.join(self.capture_config.get("screenshot_dir", "screenshots"), "processed") if mode == "manual" else ""

        while self.state.running:
            try:
                if time.time() - last_check > 5:
                    if self.check_reload():
                        mode = self.capture_config.get("mode", "manual")
                        interval = self.capture_config.get("interval", 10)
                        read_rect = self.capture_config.get("read_rect")
                        reply_pos = self.capture_config.get("reply_pos")
                    last_check = time.time()

                if self.state.paused:
                    time.sleep(1)
                    continue

                # 手动模式
                if mode == "manual":
                    files = []
                    for ext in ['*.png', '*.jpg', '*.jpeg', '*.bmp']:
                        files.extend(glob.glob(os.path.join(self.capture_config.get("screenshot_dir", "screenshots"), ext)))
                    files = [f for f in files if os.path.isfile(f) and pd not in f]
                    files.sort(key=os.path.getmtime)
                    for fp in files:
                        if not self.state.running or self.state.paused:
                            break
                        try:
                            img = Image.open(fp)
                            self.state.last_capture_time = datetime.now().strftime("%H:%M:%S")
                            reply, _ = self._ocr_pipeline(img, os.path.basename(fp))
                            if reply:
                                self._send_reply(reply)
                            if os.path.exists(fp):
                                dest = os.path.join(pd, os.path.basename(fp))
                                c = 1
                                while os.path.exists(dest):
                                    n, e = os.path.splitext(os.path.basename(fp))
                                    dest = os.path.join(pd, f"{n}_{c}{e}")
                                    c += 1
                                shutil.move(fp, dest)
                        except Exception as e:
                            logger.error(f"处理失败: {e}")
                    time.sleep(1.5)
                    continue

                # 区域模式
                if mode == "region":
                    if not read_rect or not isinstance(read_rect, (list, tuple)) or len(read_rect) != 4:
                        time.sleep(3)
                        continue
                    try:
                        img = ImageGrab.grab(bbox=tuple(read_rect))
                        self.state.last_capture_time = datetime.now().strftime("%H:%M:%S")
                        reply, _ = self._ocr_pipeline(img, "区域截图")
                        if reply:
                            if reply_pos and isinstance(reply_pos, (list, tuple)) and len(reply_pos) == 2:
                                self._send_reply_at(reply, reply_pos)
                            else:
                                self._send_reply(reply)
                    except Exception as e:
                        logger.error(f"[区域] 截图失败: {e}")
                    time.sleep(interval)
                    continue

                # 自动模式
                if not finder.is_window_alive(self.state.hwnd):
                    self.state.hwnd = finder.find_qq_chat_window()
                    if not self.state.hwnd:
                        time.sleep(5)
                        continue
                    self.state.window_title = finder.get_window_title(self.state.hwnd)

                rect = finder.get_message_area_rect(self.state.hwnd)
                img = self.screenshot.capture_message_area(self.state.hwnd, rect)
                if img is None:
                    time.sleep(interval)
                    continue
                self.state.last_capture_time = datetime.now().strftime("%H:%M:%S")
                reply, _ = self._ocr_pipeline(img, "自动截图")
                if reply:
                    self._send_reply(reply)
                time.sleep(interval)

            except Exception as e:
                logger.error(f"主循环异常: {e}", exc_info=True)
                time.sleep(interval)

        logger.info("正在清理...")
        if self.desktop and self.desktop.available:
            self.desktop.restore()
        logger.info("程序已退出")


def main():
    controller = BotController()
    if not controller.init():
        return

    # 启动机器人主循环（后台线程）
    bot_thread = threading.Thread(target=controller.run_loop, daemon=True)
    bot_thread.start()

    # 启动桌面控制台（主线程 - tkinter需要主线程）
    from desktop_widget import DesktopWidget
    widget = DesktopWidget(controller)
    widget.run()


if __name__ == "__main__":
    main()
