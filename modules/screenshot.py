"""窗口级截图模块 - 支持截取被遮挡/最小化/跨桌面的窗口"""
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from ctypes import windll, c_int, c_void_p, create_string_buffer, sizeof
from typing import Optional, Tuple
from datetime import datetime

try:
    import win32gui
    import win32ui
    import win32con
    WIN32_AVAILABLE = True
except ImportError:
    WIN32_AVAILABLE = False
    win32gui = None
    win32ui = None
    win32con = None

from PIL import Image

try:
    from PIL import ImageGrab
    IMAGEGRAB_AVAILABLE = True
except ImportError:
    IMAGEGRAB_AVAILABLE = False
    ImageGrab = None

logger = logging.getLogger(__name__)

# PrintWindow flags
PW_RENDERFULLCONTENT = 0x00000002

# Windows API 函数
user32 = windll.user32
gdi32 = windll.gdi32


class Screenshot:
    """使用Windows API截取指定窗口的内容"""

    def __init__(self, debug: bool = False, debug_dir: str = "debug_screenshots"):
        self.debug = debug
        self.debug_dir = debug_dir
        self._capture_count = 0

        if debug:
            os.makedirs(debug_dir, exist_ok=True)

        if not WIN32_AVAILABLE:
            logger.warning("win32模块未安装，窗口截图功能不可用")

    def _print_window(self, hwnd: int, hdc: int, flags: int) -> bool:
        """通过ctypes调用PrintWindow API"""
        try:
            # user32.PrintWindow(HWND hwnd, HDC hdcBlt, UINT nFlags)
            result = user32.PrintWindow(c_int(hwnd), c_int(hdc), c_int(flags))
            return result != 0
        except Exception as e:
            logger.debug(f"PrintWindow调用失败: {e}")
            return False

    def capture_window(self, hwnd: int) -> Optional[Image.Image]:
        """
        截取指定窗口的完整内容
        使用PrintWindow API，即使窗口被遮挡也能截取
        """
        if not WIN32_AVAILABLE:
            return None

        try:
            # 获取窗口尺寸
            left, top, right, bottom = win32gui.GetWindowRect(hwnd)
            width = right - left
            height = bottom - top

            if width <= 0 or height <= 0:
                logger.warning(f"窗口尺寸无效: {width}x{height}")
                return None

            # 创建设备上下文
            hwnd_dc = win32gui.GetWindowDC(hwnd)
            if hwnd_dc == 0:
                logger.warning("无法获取窗口DC")
                return None

            try:
                mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
                save_dc = mfc_dc.CreateCompatibleDC()

                # 创建位图
                save_bitmap = win32ui.CreateBitmap()
                save_bitmap.CreateCompatibleBitmap(mfc_dc, width, height)
                save_dc.SelectObject(save_bitmap)

                # 使用PrintWindow截取窗口
                # 先尝试PW_RENDERFULLCONTENT (2) 获取硬件加速内容
                result = self._print_window(hwnd, save_dc.GetSafeHdc(), PW_RENDERFULLCONTENT)

                if not result:
                    # 如果失败，尝试普通模式 (0)
                    logger.debug("PW_RENDERFULLCONTENT失败，尝试普通模式")
                    result = self._print_window(hwnd, save_dc.GetSafeHdc(), 0)

                if not result:
                    # 最后尝试BitBlt作为fallback
                    logger.debug("PrintWindow失败，尝试BitBlt")
                    result = save_dc.BitBlt(
                        (0, 0, width, height),
                        mfc_dc,
                        (0, 0),
                        0x00CC0020  # SRCCOPY
                    )
                    if not result:
                        logger.warning("所有截图方法均失败")
                        return None

                # 转换为PIL Image
                bmp_info = save_bitmap.GetInfo()
                bmp_str = save_bitmap.GetBitmapBits(True)
                image = Image.frombuffer(
                    "RGB",
                    (bmp_info["bmWidth"], bmp_info["bmHeight"]),
                    bmp_str,
                    "raw",
                    "BGRX",
                    0,
                    1,
                )

                return image

            finally:
                # 清理资源
                try:
                    save_dc.DeleteDC()
                except Exception:
                    pass
                try:
                    mfc_dc.DeleteDC()
                except Exception:
                    pass
                try:
                    win32gui.ReleaseDC(hwnd, hwnd_dc)
                except Exception:
                    pass

        except Exception as e:
            logger.error(f"截图失败: {e}")
            return None

    def capture_with_imagegrab(self, hwnd: int) -> Optional[Image.Image]:
        """
        使用PIL.ImageGrab作为截图fallback
        只能截取当前可见屏幕的内容，但不会在Chrome/Electron窗口上卡死
        截图前会将窗口最大化到最前面，确保能截取到正确内容
        """
        if not IMAGEGRAB_AVAILABLE or not WIN32_AVAILABLE:
            return None

        # 保存原始窗口状态以便恢复
        original_rect = None
        try:
            original_rect = win32gui.GetWindowRect(hwnd)
        except Exception:
            pass

        try:
            # 恢复并最大化窗口，确保它在屏幕最前面
            try:
                if win32gui.IsIconic(hwnd):
                    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                    time.sleep(0.3)
                # 最大化窗口（确保覆盖其他窗口）
                win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
                time.sleep(0.5)
            except Exception as e:
                logger.debug(f"最大化窗口失败: {e}")

            rect = win32gui.GetWindowRect(hwnd)
            left, top, right, bottom = rect
            width = right - left
            height = bottom - top
            if width <= 0 or height <= 0:
                return None
            # ImageGrab.grab 使用 (left, top, right, bottom)
            image = ImageGrab.grab(bbox=(left, top, right, bottom))
            logger.info(f"ImageGrab截图成功，尺寸: {image.size}")
            return image
        except Exception as e:
            logger.warning(f"ImageGrab截图失败: {e}")
            return None
        finally:
            # 截图完成后恢复窗口原来状态
            try:
                if original_rect:
                    # 恢复为原来大小和位置
                    win32gui.SetWindowPos(
                        hwnd, 0,
                        original_rect[0], original_rect[1],
                        original_rect[2] - original_rect[0],
                        original_rect[3] - original_rect[1],
                        win32con.SWP_NOZORDER | win32con.SWP_SHOWWINDOW
                    )
                else:
                    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            except Exception:
                pass

    def capture_window_safe(self, hwnd: int, timeout: float = 5.0) -> Optional[Image.Image]:
        """
        带超时的窗口截图，防止PrintWindow在某些窗口上卡死
        """
        if not WIN32_AVAILABLE:
            return None

        # 先快速检查窗口是否有效
        try:
            if not win32gui.IsWindow(hwnd):
                logger.warning("窗口句柄无效")
                return None
            left, top, right, bottom = win32gui.GetWindowRect(hwnd)
            width = right - left
            height = bottom - top
            logger.info(f"窗口rect: ({left}, {top}, {right}, {bottom}), 尺寸: {width}x{height}")
            if width <= 0 or height <= 0:
                logger.warning(f"窗口尺寸无效: {width}x{height}")
                return None
            # 检查窗口是否最小化
            if win32gui.IsIconic(hwnd):
                logger.warning("窗口已最小化，尝试恢复...")
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                time.sleep(0.5)
                # 重新获取尺寸
                left, top, right, bottom = win32gui.GetWindowRect(hwnd)
                width = right - left
                height = bottom - top
                logger.info(f"恢复后窗口尺寸: {width}x{height}")
            # 如果窗口仍然太小，可能是真正的尺寸问题
            if width < 300 or height < 200:
                logger.warning(f"窗口尺寸过小({width}x{height})，可能不是正常的聊天窗口，跳过截图")
                return None
        except Exception as e:
            logger.warning(f"获取窗口信息失败: {e}")
            return None

        # 使用线程池执行截图，防止PrintWindow卡死主线程
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(self.capture_window, hwnd)
            try:
                result = future.result(timeout=timeout)
                if result is not None and not self._is_black_screen(result):
                    return result
                if result is not None:
                    logger.warning("PrintWindow返回黑屏，尝试ImageGrab fallback")
                else:
                    logger.warning("PrintWindow返回None，尝试ImageGrab fallback")
            except TimeoutError:
                logger.warning(f"PrintWindow截图超时({timeout}秒)，尝试ImageGrab fallback")
            except Exception as e:
                logger.error(f"PrintWindow截图异常: {e}，尝试ImageGrab fallback")

        # fallback: 使用ImageGrab截取可见区域
        return self.capture_with_imagegrab(hwnd)

    def _is_black_screen(self, image: Image.Image, threshold: float = 0.90) -> bool:
        """
        检测截图是否为黑屏（PrintWindow对硬件加速窗口可能返回黑屏）
        threshold: 黑色像素占比阈值
        """
        if image is None:
            return True
        try:
            # 转换为灰度图
            gray = image.convert("L")
            pixels = list(gray.getdata())
            if not pixels:
                return True
            # 统计接近黑色的像素（亮度<15）
            black_count = sum(1 for p in pixels if p < 15)
            ratio = black_count / len(pixels)
            if ratio > threshold:
                logger.warning(f"检测到黑屏截图（黑色像素占比: {ratio:.1%}），将使用ImageGrab")
                return True
            return False
        except Exception as e:
            logger.debug(f"黑屏检测失败: {e}")
            return False

    def capture_message_area(self, hwnd: int, area_rect: Tuple[int, int, int, int]) -> Optional[Image.Image]:
        """
        截取窗口的消息区域
        :param hwnd: 窗口句柄
        :param area_rect: 消息区域坐标 (left, top, right, bottom)
        :return: PIL Image
        """
        logger.info("开始截图...")
        # 先截取整个窗口（带超时保护）
        full_image = self.capture_window_safe(hwnd)
        if full_image is None:
            logger.warning("截图失败，返回None")
            return None
        logger.info(f"截图成功，尺寸: {full_image.size}")

        try:
            # 获取窗口在屏幕上的位置
            window_rect = win32gui.GetWindowRect(hwnd)
            win_left, win_top, _, _ = window_rect

            # 计算消息区域相对于窗口的坐标
            area_left, area_top, area_right, area_bottom = area_rect

            rel_left = area_left - win_left
            rel_top = area_top - win_top
            rel_right = area_right - win_left
            rel_bottom = area_bottom - win_top

            # 确保坐标在图像范围内
            img_width, img_height = full_image.size
            rel_left = max(0, min(rel_left, img_width))
            rel_top = max(0, min(rel_top, img_height))
            rel_right = max(0, min(rel_right, img_width))
            rel_bottom = max(0, min(rel_bottom, img_height))

            if rel_right <= rel_left or rel_bottom <= rel_top:
                logger.warning("消息区域裁剪坐标无效，返回完整窗口截图")
                return full_image

            # 裁剪消息区域
            cropped = full_image.crop((rel_left, rel_top, rel_right, rel_bottom))
            logger.info(f"消息区域裁剪: ({rel_left}, {rel_top}, {rel_right}, {rel_bottom}) -> 尺寸: {cropped.size}")

            # 保存调试用截图
            if self.debug:
                self._save_debug_image(full_image, "full")
                self._save_debug_image(cropped, "cropped")

            return cropped

        except Exception as e:
            logger.error(f"裁剪消息区域失败: {e}")
            return full_image  # 如果裁剪失败，返回完整截图

    def _save_debug_image(self, image: Image.Image, prefix: str):
        """保存调试用截图"""
        if not self.debug:
            return

        self._capture_count += 1
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{prefix}_{timestamp}_{self._capture_count:04d}.png"
        filepath = os.path.join(self.debug_dir, filename)

        try:
            image.save(filepath)
            logger.debug(f"保存调试截图: {filepath}")
        except Exception as e:
            logger.error(f"保存调试截图失败: {e}")

    def resize_for_ocr(self, image: Image.Image, max_width: int = 1280) -> Image.Image:
        """
        调整图像大小以提高OCR速度
        """
        width, height = image.size
        if width <= max_width:
            return image

        ratio = max_width / width
        new_height = int(height * ratio)
        return image.resize((max_width, new_height), Image.Resampling.LANCZOS)
