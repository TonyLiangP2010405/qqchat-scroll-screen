"""QQ窗口检测模块"""
import logging
import time
from typing import Optional, Tuple, List

try:
    import win32gui
    import win32process
    import win32con
    WIN32_AVAILABLE = True
except ImportError:
    WIN32_AVAILABLE = False
    win32gui = None
    win32process = None
    win32con = None

logger = logging.getLogger(__name__)


class WindowFinder:
    """查找QQ聊天窗口"""

    # QQ进程名
    QQ_PROCESS_NAMES = ["qq.exe", "qqnt.exe", "qxpcore.exe"]

    # QQ窗口可能的类名
    QQ_CLASS_NAMES = [
        "TXGuiFoundation",
        "Qt5152QWindowIcon",
        "Qt5QWindowIcon",
        "Chrome_WidgetWin_1",  # QQ NT (Electron)
        "QQ",
    ]

    # 排除的窗口标题（精确匹配，这些不是聊天窗口）
    # 注意："QQ"已从列表中移除，因为QQ NT客户端主面板标题就是"QQ"
    EXCLUDE_TITLES = [
        "登录",
        "设置",
        "消息管理器",
        "查找",
        "添加好友",
        "系统设置",
        "QQ安全中心",
        "腾讯",
        "播放队列",     # QQ音乐
        "",             # 空标题
    ]

    # 排除的标题关键词（部分匹配）
    EXCLUDE_KEYWORDS = [
        "管理页面",     # 机器人Web管理页面
        "机器人",       # 机器人相关页面
        "QQMusic",      # QQ音乐
        "QQ音乐",       # QQ音乐中文
        "Slack",        # Slack
        "QQ游戏",       # QQ游戏
        "原神",         # QQ音乐相关
    ]

    def __init__(self, title_keywords: List[str] = None):
        self.title_keywords = title_keywords or ["QQ"]
        self._hwnd = None
        self._last_rect = None

        if not WIN32_AVAILABLE:
            logger.warning("win32gui未安装，窗口检测功能不可用")

    def _is_qq_class(self, class_name: str) -> bool:
        """判断类名是否可能是QQ窗口"""
        class_name_lower = class_name.lower()
        for qname in self.QQ_CLASS_NAMES:
            if qname.lower() in class_name_lower:
                return True
        return False

    def _is_valid_chat_window(self, title: str, class_name: str = "") -> bool:
        """判断窗口标题是否是有效的QQ聊天窗口"""
        if not title or len(title.strip()) == 0:
            return False

        title_stripped = title.strip()

        # 排除QQ主面板（标题只有"QQ"）
        # 但对于QQ NT客户端（Chrome_WidgetWin_1），主面板就是聊天窗口，不排除
        if title_stripped == "QQ" and not self._is_qq_class(class_name):
            return False

        # 排除其他非聊天窗口（精确匹配）
        for exclude in self.EXCLUDE_TITLES:
            if title_stripped == exclude:
                return False

        # 排除包含特定关键词的窗口（部分匹配）
        for keyword in self.EXCLUDE_KEYWORDS:
            if keyword in title_stripped:
                return False

        # 检查是否包含关键词
        for keyword in self.title_keywords:
            if keyword.lower() in title_stripped.lower():
                return True

        # 兜底：仅当类名也匹配QQ时才接受短标题
        # 但对于Electron窗口(Chrome_WidgetWin_1)，必须包含QQ关键词或群聊特征
        # 防止把Slack、VSCode等Electron应用误认为QQ窗口
        if class_name and self._is_qq_class(class_name) and 1 < len(title_stripped) < 60:
            # Chrome_WidgetWin_1是Electron通用类名，需要额外验证
            if "Chrome_WidgetWin_1".lower() in class_name.lower():
                has_qq_keyword = any(kw.lower() in title_stripped.lower() for kw in self.title_keywords)
                has_group = "群" in title_stripped  # QQ群聊特征
                if not has_qq_keyword and not has_group:
                    return False
            return True

        return False

    def list_all_windows(self) -> List[Tuple[int, str, str]]:
        """列出所有可见窗口（调试用）"""
        if not WIN32_AVAILABLE:
            return []

        windows = []

        def enum_callback(hwnd, extra):
            if not win32gui.IsWindowVisible(hwnd):
                return True
            try:
                title = win32gui.GetWindowText(hwnd)
                class_name = win32gui.GetClassName(hwnd)
            except Exception:
                return True

            if title:  # 只记录有标题的窗口
                extra.append((hwnd, title, class_name))
            return True

        win32gui.EnumWindows(enum_callback, windows)
        return windows

    def _check_window_size(self, hwnd: int) -> bool:
        """检查窗口尺寸是否合理（排除任务栏图标等小窗口）"""
        try:
            left, top, right, bottom = win32gui.GetWindowRect(hwnd)
            w, h = right - left, bottom - top
            return w >= 300 and h >= 200
        except Exception:
            return False

    # 已知的非QQ应用类名（用于排除QQ音乐等）
    NON_QQ_CLASSES = [
        "QQMusicweiyun",
        "QQMusicDummyWindow",
        "QQMusic_MolePluginWnd",
        "QQMusic_Daemon_Wnd",
        "QQMusic_COM_WND",
    ]

    def _is_known_non_qq(self, class_name: str) -> bool:
        """判断是否是已知的非QQ应用窗口类"""
        c = class_name.lower()
        for non_qq in self.NON_QQ_CLASSES:
            if non_qq.lower() in c:
                return True
        # 也排除QQ音乐相关类名
        if "qqmusic" in c or "csqqmusic" in c:
            return True
        return False

    def _find_qq_windows(self, only_visible: bool = True) -> list:
        """查找所有QQ相关窗口，返回候选列表"""
        candidates = []

        def enum_callback(hwnd, extra):
            if only_visible and not win32gui.IsWindowVisible(hwnd):
                return True

            try:
                title = win32gui.GetWindowText(hwnd)
                class_name = win32gui.GetClassName(hwnd)
                # 跳过尺寸过小的窗口（任务栏图标等）
                if not self._check_window_size(hwnd):
                    return True
                # 排除已知的非QQ应用窗口
                if self._is_known_non_qq(class_name):
                    return True
            except Exception:
                return True

            # 策略1：通过类名匹配QQ窗口
            if self._is_qq_class(class_name) and self._is_valid_chat_window(title, class_name):
                extra.append((hwnd, title, class_name, "class_match"))
                return True

            # 策略2：通过标题关键词匹配（要求类名也合理）
            # 只接受常见的窗口类名，防止匹配各种应用内部窗口
            valid_classes = ["Chrome_WidgetWin_1", "TXGuiFoundation", "QQ", "Qt"]
            has_valid_class = any(vc.lower() in class_name.lower() for vc in valid_classes)
            if has_valid_class and self._is_valid_chat_window(title, class_name):
                extra.append((hwnd, title, class_name, "title_match"))

            return True

        try:
            win32gui.EnumWindows(enum_callback, candidates)
        except Exception as e:
            logger.error(f"枚举窗口失败: {e}")

        return candidates

    def find_qq_chat_window(self, debug: bool = True) -> Optional[int]:
        """
        查找QQ聊天窗口的句柄
        会先搜索可见窗口，找不到则搜索被最小化的窗口并自动恢复
        返回窗口句柄hwnd，如果没找到返回None
        """
        if not WIN32_AVAILABLE:
            return None

        # 阶段1：搜索可见窗口
        candidates = self._find_qq_windows(only_visible=True)

        # 阶段2：如果没找到，搜索所有窗口（包括最小化的）
        if not candidates:
            logger.info("未找到可见的QQ窗口，尝试查找被最小化的窗口...")
            candidates = self._find_qq_windows(only_visible=False)

            if candidates:
                # 自动恢复第一个找到的QQ窗口
                hwnd = candidates[0][0]
                try:
                    if win32gui.IsIconic(hwnd):
                        logger.info(f"发现被最小化的QQ窗口，正在恢复: {candidates[0][1]}")
                        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                        time.sleep(0.5)
                except Exception as e:
                    logger.warning(f"恢复窗口失败: {e}")

        if debug and not candidates:
            # 打印所有可见窗口供用户排查
            all_windows = self.list_all_windows()
            logger.info("=== 当前可见窗口列表（调试用） ===")
            for hwnd, title, class_name in all_windows:
                logger.info(f"  hwnd={hwnd} | title='{title}' | class='{class_name}'")
            logger.info("==================================")
            logger.info("未找到QQ聊天窗口。请确认：")
            logger.info("  1. 已打开QQ客户端并进入群聊")
            logger.info("  2. 窗口没有被其他全屏应用完全遮挡")

        if not candidates:
            return None

        # 排序策略：
        # 1. 优先选择标题包含"群"字的窗口（用户目标就是群聊）
        # 2. 其次按匹配类型（class_match优先）
        # 3. 最后选择标题最长的（群聊名通常较长）
        def sort_key(x):
            has_group = 1 if "群" in x[1] else 0
            is_class_match = 0 if x[3] == "class_match" else 1
            return (-has_group, is_class_match, -len(x[1]))

        candidates.sort(key=sort_key)

        self._hwnd = candidates[0][0]
        logger.info(f"找到QQ聊天窗口: {candidates[0][1]} (hwnd={self._hwnd}, class={candidates[0][2]})")
        return self._hwnd

    def get_window_rect(self, hwnd: int = None) -> Optional[Tuple[int, int, int, int]]:
        """获取窗口的屏幕坐标 (left, top, right, bottom)"""
        if not WIN32_AVAILABLE:
            return None

        hwnd = hwnd or self._hwnd
        if hwnd is None:
            return None

        try:
            rect = win32gui.GetWindowRect(hwnd)
            self._last_rect = rect
            return rect
        except Exception as e:
            logger.error(f"获取窗口位置失败: {e}")
            return self._last_rect

    def is_window_alive(self, hwnd: int = None) -> bool:
        """检查窗口是否仍然存在（不检查可见性，因为窗口可能在其他虚拟桌面）"""
        if not WIN32_AVAILABLE:
            return False

        hwnd = hwnd or self._hwnd
        if hwnd is None:
            return False

        try:
            # 只检查窗口句柄是否有效，不检查可见性
            # 因为窗口可能被移到其他虚拟桌面，此时IsWindowVisible返回False
            return win32gui.IsWindow(hwnd) and len(win32gui.GetWindowText(hwnd)) > 0
        except Exception:
            return False

    def get_message_area_rect(self, hwnd: int = None) -> Optional[Tuple[int, int, int, int]]:
        """
        获取QQ窗口中消息显示区域的坐标
        针对QQ NT客户端布局优化（左侧联系人列表 + 中间消息区 + 右侧群成员列表）
        如果窗口最小化，会先恢复窗口
        """
        if not WIN32_AVAILABLE:
            return None

        hwnd = hwnd or self._hwnd
        if hwnd is None:
            return None

        # 如果窗口最小化，先恢复它
        try:
            if win32gui.IsIconic(hwnd):
                logger.info("窗口已最小化，正在恢复...")
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                time.sleep(0.3)
        except Exception as e:
            logger.warning(f"恢复窗口失败: {e}")

        rect = self.get_window_rect(hwnd)
        if rect is None:
            return None

        left, top, right, bottom = rect
        width = right - left
        height = bottom - top

        # QQ NT客户端布局：
        # 左侧联系人列表约占18%宽度
        # 右侧群成员列表约占28%宽度
        # 顶部标题栏约40像素
        # 底部输入框约70像素
        left_margin = int(width * 0.18)
        right_margin = int(width * 0.28)
        title_height = 40
        input_height = 70

        msg_left = left + left_margin
        msg_top = top + title_height
        msg_right = right - right_margin
        msg_bottom = bottom - input_height

        if msg_right <= msg_left or msg_bottom <= msg_top:
            logger.warning(f"消息区域计算异常，返回完整窗口: width={width}, height={height}")
            return rect

        logger.debug(f"消息区域: ({msg_left}, {msg_top}, {msg_right}, {msg_bottom})")
        return (msg_left, msg_top, msg_right, msg_bottom)

    def get_window_title(self, hwnd: int = None) -> str:
        """获取窗口标题"""
        if not WIN32_AVAILABLE:
            return ""

        hwnd = hwnd or self._hwnd
        if hwnd is None:
            return ""

        try:
            return win32gui.GetWindowText(hwnd)
        except Exception:
            return ""
