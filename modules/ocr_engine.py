"""OCR文字识别模块 - 优先使用PaddleOCR，失败时回退到EasyOCR"""
import logging
import os
from typing import List, Tuple, Optional

# 禁用 oneDNN，避免 Windows 上的兼容性问题
os.environ['FLAGS_use_mkldnn'] = '0'
os.environ['OMP_NUM_THREADS'] = '1'

logger = logging.getLogger(__name__)


class OCREngine:
    """使用PaddleOCR进行中文文字识别"""

    def __init__(self, languages: List[str] = None, gpu: bool = False):
        self.languages = languages or ["ch_sim", "en"]
        self.gpu = gpu
        self._ocr = None
        self._engine = ""

        if self._init_paddle():
            return
        if self._init_easyocr():
            return
        logger.error("没有可用的OCR引擎，请安装 paddleocr 或 easyocr")

    def _init_paddle(self) -> bool:
        try:
            from paddleocr import PaddleOCR
            logger.info("正在初始化PaddleOCR...")
            import logging as py_logging
            py_logging.getLogger('ppocr').setLevel(py_logging.WARNING)

            self._ocr = PaddleOCR(
                use_angle_cls=True,
                lang='ch'
            )
            self._engine = "paddle"
            logger.info("PaddleOCR初始化完成")
            return True
        except ImportError:
            logger.warning("paddleocr未安装，将尝试使用EasyOCR")
        except Exception as e:
            logger.warning(f"PaddleOCR初始化失败，将尝试使用EasyOCR: {e}")
        self._ocr = None
        return False

    def _init_easyocr(self) -> bool:
        try:
            import easyocr
            logger.info("正在初始化EasyOCR...")
            self._ocr = easyocr.Reader(self.languages, gpu=self.gpu, verbose=False)
            self._engine = "easyocr"
            logger.info("EasyOCR初始化完成")
            return True
        except ImportError:
            logger.warning("easyocr未安装")
        except Exception as e:
            logger.error(f"EasyOCR初始化失败: {e}")
        self._ocr = None
        return False

    def recognize(self, image) -> List[Tuple[str, list, float]]:
        """
        识别图像中的文字
        :param image: PIL Image 或 numpy array 或文件路径
        :return: 列表，每项为 (文字, 边界框坐标, 置信度)
                 边界框格式: [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
        """
        if self._ocr is None:
            logger.error("OCR引擎未初始化")
            return []

        try:
            # 如果是PIL Image，先转换为numpy array
            img_input = image
            if hasattr(image, 'convert'):  # PIL Image
                import numpy as np
                img_input = np.array(image.convert("RGB"))

            if self._engine == "easyocr":
                parsed = self._recognize_easyocr(img_input)
            else:
                parsed = self._recognize_paddle(img_input)

            # 按y坐标排序（从上到下）
            parsed.sort(key=lambda x: x[1][0][1])

            logger.debug(f"OCR识别到 {len(parsed)} 行文字")
            return parsed

        except Exception as e:
            logger.error(f"OCR识别失败: {e}")
            if self._engine == "paddle" and self._init_easyocr():
                try:
                    parsed = self._recognize_easyocr(img_input)
                    parsed.sort(key=lambda x: x[1][0][1])
                    return parsed
                except Exception as retry_error:
                    logger.error(f"EasyOCR回退识别失败: {retry_error}")
            return []

    def _recognize_paddle(self, img_input) -> List[Tuple[str, list, float]]:
        try:
            result = self._ocr.ocr(img_input)
        except TypeError as e:
            if "cls" not in str(e) and "ocr" not in str(e):
                raise
            result = self._ocr.predict(img_input)

        parsed = []
        if not result:
            return parsed

        # PaddleOCR 2.x: [[ [bbox, (text, confidence)], ... ]]
        if isinstance(result, list) and result and isinstance(result[0], list):
            lines = result[0] if result and result[0] else []
            for line in lines:
                if line and len(line) >= 2:
                    bbox = line[0]
                    text = line[1][0]
                    confidence = line[1][1]
                    parsed.append((str(text), bbox, float(confidence)))
            return parsed

        # PaddleOCR 3.x predict result: dict-like objects with rec_texts/scores/polys.
        for page in result if isinstance(result, list) else [result]:
            if hasattr(page, "json"):
                page = page.json
            if not isinstance(page, dict):
                continue
            texts = page.get("rec_texts") or page.get("texts") or []
            scores = page.get("rec_scores") or page.get("scores") or []
            boxes = page.get("rec_polys") or page.get("rec_boxes") or page.get("dt_polys") or []
            for idx, text in enumerate(texts):
                bbox = boxes[idx] if idx < len(boxes) else [[0, idx * 20], [1, idx * 20], [1, idx * 20 + 1], [0, idx * 20 + 1]]
                confidence = scores[idx] if idx < len(scores) else 0.0
                parsed.append((str(text), self._normalize_bbox(bbox), float(confidence)))
        return parsed

    def _recognize_easyocr(self, img_input) -> List[Tuple[str, list, float]]:
        result = self._ocr.readtext(img_input, detail=1, paragraph=False)
        parsed = []
        for item in result:
            if len(item) >= 3:
                bbox, text, confidence = item[0], item[1], item[2]
                parsed.append((str(text), self._normalize_bbox(bbox), float(confidence)))
        return parsed

    def _normalize_bbox(self, bbox):
        try:
            points = bbox.tolist() if hasattr(bbox, "tolist") else bbox
            if len(points) == 4 and all(isinstance(p, (list, tuple)) for p in points):
                return [[int(p[0]), int(p[1])] for p in points]
            if len(points) == 4:
                x1, y1, x2, y2 = [int(v) for v in points]
                return [[x1, y1], [x2, y1], [x2, y2], [x1, y2]]
        except Exception:
            pass
        return [[0, 0], [1, 0], [1, 1], [0, 1]]

    def recognize_to_text(self, image) -> str:
        """
        识别图像中的文字并返回合并后的文本
        """
        results = self.recognize(image)
        if not results:
            return ""

        lines = []
        for text, bbox, confidence in results:
            lines.append(text)

        return "\n".join(lines)
