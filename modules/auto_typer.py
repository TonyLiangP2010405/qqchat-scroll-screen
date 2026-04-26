"""自动输入模块 - 将文字输入到QQ聊天框"""
import logging
import time
from typing import Optional

try:
    import pyautogui
    import pyperclip
    PYAUTOGUI_AVAILABLE = True
except ImportError:
    PYAUTOGUI_AVAILABLE = False
    pyautogui = None
    pyperclip = None

try:
    import win32gui
    import win32con
    WIN32_AVAILABLE = True
except ImportError:
    WIN32_AVAILABLE = False
    win32gui = None
    win32con = None

logger = logging.getLogger(__name__)


class AutoTyper:
    """自动将文字输入到指定窗口"""

    def __init__(self, safety_delay: float = 0.5):
        self.safety_delay = safety_delay

        if not PYAUTOGUI_AVAILABLE:
            logger.warning("pyautogui/pyperclip未安装，自动输入功能不可用")
        else:
            pyautogui.FAILSAFE = True

    def _is_valid_position(self, x: int, y: int) -> bool:
        if not PYAUTOGUI_AVAILABLE:
            return False
        try:
            width, height = pyautogui.size()
            return 0 <= int(x) < width and 0 <= int(y) < height
        except Exception:
            return True

    def _safe_restore_mouse(self, position):
        if not PYAUTOGUI_AVAILABLE or position is None:
            return
        try:
            width, height = pyautogui.size()
            margin = 5
            x = min(max(int(position[0]), margin), max(margin, width - margin - 1))
            y = min(max(int(position[1]), margin), max(margin, height - margin - 1))
            pyautogui.moveTo(x, y)
        except Exception as e:
            logger.debug(f"恢复鼠标位置失败: {e}")

    def _focus_window(self, hwnd: int) -> bool:
        """将窗口置前并激活"""
        if not WIN32_AVAILABLE:
            return False

        try:
            # 如果窗口最小化，恢复它
            if win32gui.IsIconic(hwnd):
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                time.sleep(0.2)

            # 将窗口置前
            win32gui.SetForegroundWindow(hwnd)
            time.sleep(0.2)
            return True
        except Exception as e:
            logger.warning(f"激活窗口失败: {e}")
            return False

    def _get_input_area_position(self, hwnd: int) -> Optional[tuple]:
        """
        估算QQ输入框的位置（窗口底部中间区域）
        返回相对于屏幕的(x, y)坐标
        """
        if not WIN32_AVAILABLE:
            return None

        try:
            left, top, right, bottom = win32gui.GetWindowRect(hwnd)
            width = right - left
            height = bottom - top

            # 输入框大约在窗口底部，宽度中间位置
            # 底部往上约60像素，左右居中偏左一些
            x = left + int(width * 0.15)
            y = bottom - 50

            return (x, y)
        except Exception as e:
            logger.warning(f"计算输入框位置失败: {e}")
            return None

    def type_message(self, hwnd: int, message: str) -> bool:
        """
        将消息输入到QQ聊天框并发送
        :param hwnd: QQ窗口句柄
        :param message: 要发送的消息
        :return: 是否成功
        """
        if not PYAUTOGUI_AVAILABLE or not WIN32_AVAILABLE:
            logger.error("自动输入功能不可用")
            return False

        try:
            # 保存当前鼠标位置
            original_position = pyautogui.position()

            # 激活窗口
            if not self._focus_window(hwnd):
                return False

            time.sleep(self.safety_delay)

            # 点击输入框
            input_pos = self._get_input_area_position(hwnd)
            if input_pos:
                pyautogui.click(input_pos[0], input_pos[1])
                time.sleep(0.2)

            # 使用剪贴板粘贴中文（比typewrite更稳定）
            # 先清空输入框
            pyautogui.keyDown('ctrl')
            pyautogui.keyDown('a')
            pyautogui.keyUp('a')
            pyautogui.keyUp('ctrl')
            time.sleep(0.1)
            pyautogui.press('delete')
            time.sleep(0.1)

            # 复制消息到剪贴板并粘贴
            pyperclip.copy(message)
            time.sleep(0.1)

            pyautogui.keyDown('ctrl')
            pyautogui.keyDown('v')
            pyautogui.keyUp('v')
            pyautogui.keyUp('ctrl')
            time.sleep(0.2)

            # 发送消息（回车）
            pyautogui.press('return')
            time.sleep(0.3)

            # 恢复鼠标位置
            self._safe_restore_mouse(original_position)

            logger.info(f"已发送消息: {message[:50]}...")
            return True

        except Exception as e:
            logger.error(f"自动输入失败: {e}")
            return False

    def type_at_position(self, x: int, y: int, message: str) -> bool:
        """
        在指定屏幕坐标点击并输入消息
        流程：点击输入框 → 粘贴消息 → 按回车发送
        """
        if not PYAUTOGUI_AVAILABLE:
            logger.error("pyautogui 不可用")
            return False

        try:
            x, y = int(x), int(y)
            if not self._is_valid_position(x, y):
                logger.error(f"回复坐标超出当前屏幕范围: ({x}, {y})")
                self.copy_to_clipboard_only(message)
                return False

            original = pyautogui.position()
            logger.info(f"准备发送消息到 ({x}, {y})")

            pyperclip.copy(message)
            time.sleep(0.1)

            # 1. 点击输入框，让光标进入
            pyautogui.click(x, y)
            time.sleep(0.3)

            # 2. 清空输入框并粘贴剪贴板内容
            pyautogui.hotkey('ctrl', 'a')
            time.sleep(0.1)
            pyautogui.press('delete')
            time.sleep(0.1)
            pyautogui.hotkey('ctrl', 'v')
            time.sleep(0.2)

            # 3. 按回车发送
            pyautogui.press('enter')
            time.sleep(0.2)

            # 恢复鼠标位置
            self._safe_restore_mouse(original)

            logger.info(f"已发送: {message[:50]}...")
            return True

        except Exception as e:
            logger.error(f"发送失败: {e}")
            return False

    def copy_to_clipboard_only(self, message: str) -> bool:
        """
        仅将消息复制到剪贴板，不尝试自动输入
        用于手动截图模式下，用户自行粘贴到QQ
        """
        if not PYAUTOGUI_AVAILABLE:
            return False

        try:
            message = message.strip()
            if not message:
                return False

            pyperclip.copy(message)
            logger.info(f"回复已复制到剪贴板: {message[:50]}...")
            return True

        except Exception as e:
            logger.error(f"复制到剪贴板失败: {e}")
            return False

    def safe_type(self, hwnd, message: str) -> bool:
        """
        安全地输入消息，如果失败会尝试恢复
        hwnd 可以为 None（手动模式下未找到QQ窗口），此时直接返回False
        """
        try:
            message = message.strip()
            if not message:
                logger.warning("消息为空，跳过发送")
                return False

            if hwnd is None:
                logger.info("未提供QQ窗口句柄，无法自动输入")
                return False

            # 限制消息长度（QQ单条消息限制）
            max_length = 2000
            if len(message) > max_length:
                message = message[:max_length]
                logger.warning(f"消息过长，已截断至{max_length}字符")

            return self.type_message(hwnd, message)

        except Exception as e:
            logger.error(f"safe_type失败: {e}")
            return False
