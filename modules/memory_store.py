"""聊天记录持久化模块 - 保存文字记录作为记忆"""
import json
import logging
import os
from datetime import datetime
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class MemoryStore:
    """将聊天记录保存到本地文件，支持按日期分文件"""

    def __init__(self, data_dir: str = "data", split_by_date: bool = True):
        self.data_dir = data_dir
        self.split_by_date = split_by_date
        self._ensure_dir()

    def _ensure_dir(self):
        """确保数据目录存在"""
        os.makedirs(self.data_dir, exist_ok=True)

    def _get_filepath(self, date_str: str = None) -> str:
        """获取当天的记录文件路径"""
        if date_str is None:
            date_str = datetime.now().strftime("%Y-%m-%d")

        if self.split_by_date:
            filename = f"chat_history_{date_str}.jsonl"
        else:
            filename = "chat_history.jsonl"

        return os.path.join(self.data_dir, filename)

    def save_message(self, sender: str, content: str, is_bot: bool = False, timestamp: str = None):
        """
        保存单条消息
        """
        if not content or not content.strip():
            return

        record = {
            "timestamp": timestamp or datetime.now().isoformat(),
            "sender": sender,
            "content": content,
            "is_bot": is_bot,
        }

        filepath = self._get_filepath()

        try:
            with open(filepath, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
            logger.debug(f"保存消息: {sender}: {content[:50]}...")
        except Exception as e:
            logger.error(f"保存消息失败: {e}")

    def save_messages(self, messages: List):
        """批量保存消息"""
        for msg in messages:
            self.save_message(
                sender=getattr(msg, "sender", "未知用户"),
                content=getattr(msg, "content", ""),
                is_bot=getattr(msg, "is_bot", False),
                timestamp=getattr(msg, "timestamp", None)
            )

    def load_recent(self, count: int = 20, date_str: str = None) -> List[Dict]:
        """
        加载最近N条记录
        """
        filepath = self._get_filepath(date_str)

        if not os.path.exists(filepath):
            return []

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                lines = f.readlines()

            records = []
            for line in lines[-count:]:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                    records.append(record)
                except json.JSONDecodeError:
                    continue

            return records

        except Exception as e:
            logger.error(f"加载记录失败: {e}")
            return []

    def load_all(self, date_str: str = None) -> List[Dict]:
        """加载某天的所有记录"""
        filepath = self._get_filepath(date_str)

        if not os.path.exists(filepath):
            return []

        records = []
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                        records.append(record)
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            logger.error(f"加载所有记录失败: {e}")

        return records

    def search(self, keyword: str, date_str: str = None) -> List[Dict]:
        """搜索包含关键词的记录"""
        records = self.load_all(date_str)
        results = []
        keyword_lower = keyword.lower()

        for record in records:
            content = record.get("content", "").lower()
            sender = record.get("sender", "").lower()
            if keyword_lower in content or keyword_lower in sender:
                results.append(record)

        return results

    def get_available_dates(self) -> List[str]:
        """获取所有有记录的日期"""
        dates = []
        try:
            for filename in os.listdir(self.data_dir):
                if filename.startswith("chat_history_") and filename.endswith(".jsonl"):
                    date = filename.replace("chat_history_", "").replace(".jsonl", "")
                    dates.append(date)
        except Exception:
            pass

        dates.sort(reverse=True)
        return dates

    def delete_record(self, record_id: int, date_str: str = None) -> bool:
        """
        删除指定记录（通过行号）
        """
        filepath = self._get_filepath(date_str)

        if not os.path.exists(filepath):
            return False

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                lines = f.readlines()

            if record_id < 0 or record_id >= len(lines):
                return False

            lines.pop(record_id)

            with open(filepath, "w", encoding="utf-8") as f:
                f.writelines(lines)

            return True

        except Exception as e:
            logger.error(f"删除记录失败: {e}")
            return False

    def update_record(self, record_id: int, new_content: str, date_str: str = None) -> bool:
        """更新指定记录的内容"""
        filepath = self._get_filepath(date_str)

        if not os.path.exists(filepath):
            return False

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                lines = f.readlines()

            if record_id < 0 or record_id >= len(lines):
                return False

            record = json.loads(lines[record_id])
            record["content"] = new_content
            lines[record_id] = json.dumps(record, ensure_ascii=False) + "\n"

            with open(filepath, "w", encoding="utf-8") as f:
                f.writelines(lines)

            return True

        except Exception as e:
            logger.error(f"更新记录失败: {e}")
            return False
