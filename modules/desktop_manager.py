"""Windows虚拟桌面管理模块"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class DesktopManager:
    """管理Windows虚拟桌面的创建、切换和窗口移动"""

    def __init__(self, enabled: bool = True, desktop_name: str = "QQ机器人"):
        self.enabled = enabled
        self.desktop_name = desktop_name
        self._available = False
        self._original_desktop = None
        self._bot_desktop = None

        if not enabled:
            logger.info("虚拟桌面功能已禁用")
            return

        try:
            from pyvda import VirtualDesktop, AppView
            self._VirtualDesktop = VirtualDesktop
            self._AppView = AppView
            self._available = True
            logger.info("虚拟桌面管理模块初始化成功")
        except ImportError:
            logger.warning("pyvda未安装，虚拟桌面功能不可用，程序将在当前桌面运行")
            self._available = False
        except Exception as e:
            logger.warning(f"虚拟桌面功能初始化失败，程序将在当前桌面运行: {e}")
            self._available = False

    @property
    def available(self) -> bool:
        return self._available

    def create_desktop(self) -> Optional[object]:
        """创建一个新的虚拟桌面"""
        if not self._available:
            return None
        try:
            # 获取当前桌面数量
            current_count = len(self._VirtualDesktop.get_all_desktops())
            # 创建新桌面
            new_desktop = self._VirtualDesktop.create()
            logger.info(f"创建虚拟桌面成功，当前共有 {current_count + 1} 个桌面")
            return new_desktop
        except Exception as e:
            logger.error(f"创建虚拟桌面失败: {e}")
            return None

    def get_current_desktop(self) -> Optional[object]:
        """获取当前虚拟桌面"""
        if not self._available:
            return None
        try:
            return self._VirtualDesktop.current()
        except Exception as e:
            logger.error(f"获取当前桌面失败: {e}")
            return None

    def switch_to_desktop(self, desktop) -> bool:
        """切换到指定虚拟桌面"""
        if not self._available or desktop is None:
            return False
        try:
            desktop.go()
            logger.info("切换到目标虚拟桌面")
            return True
        except Exception as e:
            logger.error(f"切换虚拟桌面失败: {e}")
            return False

    def move_window_to_desktop(self, hwnd: int, desktop) -> bool:
        """将指定窗口移动到指定虚拟桌面"""
        if not self._available or desktop is None:
            return False
        try:
            view = self._AppView(hwnd=hwnd)
            view.move(desktop)
            logger.info(f"将窗口 {hwnd} 移动到虚拟桌面")
            return True
        except Exception as e:
            logger.error(f"移动窗口到虚拟桌面失败: {e}")
            return False

    def setup(self, hwnd: int) -> bool:
        """
        设置虚拟桌面环境：
        1. 保存当前桌面
        2. 创建/获取后台桌面
        3. 将QQ窗口移动到后台桌面
        4. 切换到后台桌面
        """
        if not self._available:
            logger.info("虚拟桌面不可用，跳过桌面设置")
            return False

        try:
            # 保存当前桌面
            self._original_desktop = self.get_current_desktop()
            if self._original_desktop is None:
                logger.warning("无法获取当前桌面")
                return False

            # 检查是否已经有名为QQ机器人的桌面
            all_desktops = self._VirtualDesktop.get_all_desktops()
            self._bot_desktop = None
            for d in all_desktops:
                # 尝试匹配桌面名称（pyvda可能不支持命名）
                pass

            # 如果没有找到，创建新桌面
            if self._bot_desktop is None:
                self._bot_desktop = self.create_desktop()

            if self._bot_desktop is None:
                logger.warning("无法创建虚拟桌面")
                return False

            # 将QQ窗口移动到后台桌面
            if hwnd:
                self.move_window_to_desktop(hwnd, self._bot_desktop)

            # 切换到后台桌面
            self.switch_to_desktop(self._bot_desktop)

            logger.info("虚拟桌面环境设置完成")
            return True

        except Exception as e:
            logger.error(f"设置虚拟桌面环境失败: {e}")
            return False

    def restore(self) -> bool:
        """恢复到原始桌面"""
        if not self._available or self._original_desktop is None:
            return False
        try:
            self.switch_to_desktop(self._original_desktop)
            logger.info("已恢复到原始桌面")
            return True
        except Exception as e:
            logger.error(f"恢复原始桌面失败: {e}")
            return False
