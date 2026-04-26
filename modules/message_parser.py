"""消息解析模块 - 将OCR结果解析为结构化消息"""
import logging
import hashlib
import re
import difflib
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class ChatMessage:
    """单条聊天消息"""
    sender: str = ""           # 发送者昵称
    content: str = ""          # 消息内容
    timestamp: str = ""        # 时间（OCR识别到的或当前时间）
    is_bot: bool = False       # 是否是机器人自己发送的
    msg_hash: str = ""         # 内容哈希，用于去重

    def __post_init__(self):
        if not self.msg_hash:
            self.msg_hash = self._compute_hash()

    def _compute_hash(self) -> str:
        """计算消息内容的哈希值"""
        text = f"{self.sender}:{self.content}"
        return hashlib.md5(text.encode("utf-8")).hexdigest()[:16]


class MessageParser:
    """解析OCR识别结果，提取结构化消息"""

    # 常见的时间格式正则
    TIME_PATTERNS = [
        r"(\d{1,2}:\d{2}(?::\d{2})?)",           # 12:34 或 12:34:56
        r"(\d{4}-\d{2}-\d{2}\s+\d{1,2}:\d{2})", # 2024-01-15 12:34
        r"(昨天\s+\d{1,2}:\d{2})",               # 昨天 12:34
        r"(今天\s+\d{1,2}:\d{2})",               # 今天 12:34
    ]

    def __init__(self, bot_name: str = ""):
        self.bot_name = bot_name
        self._message_history: List[ChatMessage] = []
        self._seen_hashes: set = set()

    def parse_ocr_results(self, ocr_results: List[Tuple]) -> List[ChatMessage]:
        """
        将OCR识别结果解析为结构化消息列表
        :param ocr_results: OCR引擎返回的结果，每项为 (text, bbox, confidence)
        :return: 解析后的消息列表
        """
        if not ocr_results:
            return []

        # 提取所有文字并按y坐标分组（同一行的文字可能属于同一条消息）
        lines = self._group_by_lines(ocr_results)

        messages = []
        current_sender = ""
        current_content = ""
        current_time = ""

        for line_text in lines:
            line_text = line_text.strip()
            if not line_text:
                continue

            # 判断这一行是否是发送者/时间信息
            sender, time_str = self._extract_sender_and_time(line_text)
            if sender and current_sender and not current_content and not self._has_explicit_sender_marker(line_text):
                sender = None

            if sender:
                # 如果之前有内容，保存为一条消息
                if current_content:
                    msg = ChatMessage(
                        sender=current_sender or "未知用户",
                        content=current_content.strip(),
                        timestamp=current_time or datetime.now().strftime("%H:%M"),
                        is_bot=self._is_bot_message(current_sender or "")
                    )
                    messages.append(msg)

                # 开始新消息
                current_sender = sender
                current_time = time_str
                current_content = ""
            else:
                # 这是消息内容的一部分
                current_content += line_text + " "

        # 保存最后一条消息
        if current_content:
            msg = ChatMessage(
                sender=current_sender or "未知用户",
                content=current_content.strip(),
                timestamp=current_time or datetime.now().strftime("%H:%M"),
                is_bot=self._is_bot_message(current_sender or "")
            )
            messages.append(msg)

        # 过滤明显是乱码/UI元素的消息
        filtered = []
        for msg in messages:
            if not self._is_garbage(msg.content):
                filtered.append(msg)
            else:
                logger.debug(f"过滤乱码消息: {msg.content[:30]}")

        logger.debug(f"解析出 {len(messages)} 条消息，过滤后 {len(filtered)} 条")
        return filtered

    def _is_garbage(self, text: str) -> bool:
        """检查消息是否是乱码或QQ界面元素"""
        if not text or len(text.strip()) < 2:
            return True

        text = text.strip()

        meaningful_chars = [c for c in text if c.isalnum() or '一' <= c <= '鿿']
        if not meaningful_chars:
            return True

        symbol_count = len(text) - len(meaningful_chars)
        if len(text) >= 8 and symbol_count / len(text) > 0.65:
            return True

        # 明显的游戏/界面元素
        garbage_patterns = [
            r'Exp\s*\+\s*\d+',      # 经验值
            r'V\d+\.\d+',           # 版本号如 V3.1
            r'\d{2}/\d{2}',         # 日期格式如 04/25
            r'\d{2}:\d{2}:\d{2}',   # 时间格式
        ]
        for pattern in garbage_patterns:
            if re.fullmatch(pattern, text, re.IGNORECASE):
                return True

        return False

    def _group_by_lines(self, ocr_results: List[Tuple]) -> List[str]:
        """
        将OCR结果按行分组，返回每行的合并文字
        """
        if not ocr_results:
            return []

        # 按y坐标排序
        sorted_results = sorted(ocr_results, key=lambda x: x[1][0][1])

        lines = []
        current_line = []
        current_y = None
        y_threshold = 15  # y坐标差异小于15像素视为同一行

        for text, bbox, confidence in sorted_results:
            y = bbox[0][1]

            if current_y is None or abs(y - current_y) < y_threshold:
                current_line.append((text, bbox))
                current_y = y
            else:
                # 保存当前行
                current_line.sort(key=lambda x: x[1][0][0])  # 按x坐标排序
                line_text = "".join([item[0] for item in current_line])
                lines.append(line_text)

                # 开始新行
                current_line = [(text, bbox)]
                current_y = y

        # 保存最后一行
        if current_line:
            current_line.sort(key=lambda x: x[1][0][0])
            line_text = "".join([item[0] for item in current_line])
            lines.append(line_text)

        return lines

    def _extract_sender_and_time(self, text: str) -> Tuple[Optional[str], str]:
        """
        从一行文字中提取发送者和时间
        QQ群聊消息的格式：
        - "发送者昵称 12:34"（带时间）
        - "发送者昵称"（不带时间）
        - "昵称 LV100" / "昵称 LV.6"（带等级）
        返回 (sender, time_str)，如果不是发送者行返回 (None, "")
        """
        text = text.strip()

        # 尝试匹配时间
        time_str = ""
        for pattern in self.TIME_PATTERNS:
            match = re.search(pattern, text)
            if match:
                time_str = match.group(1)
                # 去掉时间部分，剩余的是发送者
                sender = text[:match.start()].strip()
                if sender:
                    return sender, time_str
                break

        # 检测QQ等级标识（如 LV100、Lv.6）
        lv_match = re.search(r'LV\.?\d+', text, re.IGNORECASE)
        if lv_match:
            # 去掉等级部分作为发送者
            sender = text[:lv_match.start()].strip()
            if sender:
                return sender, ""
            # 如果连昵称都没有，整行作为发送者
            return text, ""

        # 如果没有时间/等级，检查是否可能是发送者（短文本，不包含明显是消息内容的特征）
        if len(text) < 20 and not text.endswith(("，", "。", "！", "？", "~", "…")):
            return text, ""

        return None, ""

    def _has_explicit_sender_marker(self, text: str) -> bool:
        """Return True when a line clearly carries QQ sender metadata."""
        if any(re.search(pattern, text) for pattern in self.TIME_PATTERNS):
            return True
        return re.search(r'LV\.?\d+', text, re.IGNORECASE) is not None

    def _is_bot_message(self, sender: str) -> bool:
        """判断是否是机器人自己发送的消息"""
        if not self.bot_name or not sender:
            return False
        return self.bot_name in sender

    def _is_similar(self, msg: ChatMessage, recent_messages: List[ChatMessage], threshold: float = 0.70) -> bool:
        """检查消息是否与最近的消息内容相似（防止OCR微小差异导致重复）"""
        for recent in recent_messages:
            if recent.sender == msg.sender:
                similarity = difflib.SequenceMatcher(None, msg.content, recent.content).ratio()
                if similarity >= threshold:
                    return True
        return False

    def get_new_messages(self, messages: List[ChatMessage]) -> List[ChatMessage]:
        """
        从解析出的消息中筛选出新消息（未在历史中出现过的）
        同时检查内容相似度，防止OCR微小差异导致重复
        """
        new_messages = []
        for msg in messages:
            # 先检查精确哈希
            if msg.msg_hash in self._seen_hashes:
                continue

            # 再检查与最近20条消息的相似度
            recent = self._message_history[-20:] if self._message_history else []
            if self._is_similar(msg, recent):
                self._seen_hashes.add(msg.msg_hash)
                continue

            new_messages.append(msg)
            self._seen_hashes.add(msg.msg_hash)
            self._message_history.append(msg)

        # 限制历史记录大小
        max_history = 1000
        if len(self._message_history) > max_history:
            removed = self._message_history[:len(self._message_history) - max_history]
            self._message_history = self._message_history[-max_history:]
            for msg in removed:
                self._seen_hashes.discard(msg.msg_hash)

        return new_messages

    def filter_bot_messages(self, messages: List[ChatMessage]) -> List[ChatMessage]:
        """过滤掉机器人自己发送的消息"""
        return [msg for msg in messages if not msg.is_bot]

    def get_recent_history(self, count: int = 10) -> List[ChatMessage]:
        """获取最近N条消息"""
        return self._message_history[-count:]

    def seed_history(self, records: List) -> None:
        """用已保存记录预热去重历史，避免重启后重复回复屏幕上的旧消息。"""
        for record in records or []:
            if isinstance(record, ChatMessage):
                msg = record
            elif isinstance(record, dict):
                msg = ChatMessage(
                    sender=record.get("sender", ""),
                    content=record.get("content", ""),
                    timestamp=record.get("timestamp", ""),
                    is_bot=record.get("is_bot", False)
                )
            else:
                continue
            if not msg.content:
                continue
            self._seen_hashes.add(msg.msg_hash)
            self._message_history.append(msg)

        if len(self._message_history) > 1000:
            self._message_history = self._message_history[-1000:]
            self._seen_hashes = {msg.msg_hash for msg in self._message_history}

    def clear_history(self):
        """清空历史记录"""
        self._message_history.clear()
        self._seen_hashes.clear()
