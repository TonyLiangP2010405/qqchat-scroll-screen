"""消息和记忆查询API"""
from fastapi import APIRouter, Query
from typing import List, Optional
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from modules.memory_store import MemoryStore

router = APIRouter(prefix="/messages", tags=["messages"])

# 需要在外部注入
memory_store: Optional[MemoryStore] = None


def set_memory_store(store: MemoryStore):
    global memory_store
    memory_store = store


@router.get("")
async def get_messages(
    date: Optional[str] = Query(None, description="日期，格式YYYY-MM-DD，默认今天"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    search: Optional[str] = Query(None, description="搜索关键词")
):
    """分页获取聊天记录"""
    if memory_store is None:
        return {"total": 0, "items": [], "page": page, "page_size": page_size}

    date_str = date or None

    if search:
        records = memory_store.search(search, date_str)
    else:
        records = memory_store.load_all(date_str)

    total = len(records)
    start = (page - 1) * page_size
    end = start + page_size
    items = records[start:end]

    # 添加行号作为id
    for i, item in enumerate(items):
        item["id"] = start + i

    return {
        "total": total,
        "items": items,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size
    }


@router.get("/dates")
async def get_dates():
    """获取有记录的日期列表"""
    if memory_store is None:
        return []
    return memory_store.get_available_dates()


@router.get("/memory")
async def get_memory(count: int = Query(20, ge=1, le=100)):
    """获取近期记忆（用于大模型上下文）"""
    if memory_store is None:
        return []
    return memory_store.load_recent(count)


@router.put("/{msg_id}")
async def update_message(msg_id: int, content: str, date: Optional[str] = None):
    """更新某条消息内容"""
    if memory_store is None:
        return {"status": "error", "message": "记忆存储未初始化"}

    success = memory_store.update_record(msg_id, content, date)
    return {"status": "success" if success else "error"}


@router.delete("/{msg_id}")
async def delete_message(msg_id: int, date: Optional[str] = None):
    """删除某条消息"""
    if memory_store is None:
        return {"status": "error", "message": "记忆存储未初始化"}

    success = memory_store.delete_record(msg_id, date)
    return {"status": "success" if success else "error"}
