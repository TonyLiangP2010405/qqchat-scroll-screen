"""配置管理API"""
import yaml
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/config", tags=["config"])

CONFIG_FILE = "config.yaml"


class LLMConfig(BaseModel):
    base_url: str
    api_key: str
    model: str
    max_tokens: int = 500
    temperature: float = 0.7


class BotConfig(BaseModel):
    name: str
    system_prompt: str


class CaptureConfig(BaseModel):
    interval: int = 10
    window_title_keywords: list = ["QQ"]
    message_area_ratio: float = 0.7
    debug_screenshots: bool = False


class FullConfig(BaseModel):
    llm: LLMConfig
    bot: BotConfig
    capture: CaptureConfig


def _load_config() -> dict:
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


def _save_config(config: dict):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        yaml.dump(config, f, allow_unicode=True, sort_keys=False)


@router.get("")
async def get_config():
    """获取当前配置"""
    return _load_config()


@router.post("")
async def update_config(new_config: dict):
    """更新配置 - 与现有配置合并，不丢失未修改的字段"""
    try:
        # 先加载现有配置
        current = _load_config()
        # 深度合并：用新配置覆盖旧配置的对应字段
        _deep_merge(current, new_config)
        _save_config(current)
        return {"status": "success", "message": "配置已保存，重启后生效"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _deep_merge(base: dict, update: dict):
    """深度合并两个字典"""
    for key, value in update.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value


@router.get("/llm")
async def get_llm_config():
    config = _load_config()
    return config.get("llm", {})


@router.post("/llm")
async def update_llm_config(llm_config: LLMConfig):
    config = _load_config()
    config["llm"] = llm_config.model_dump()
    _save_config(config)
    return {"status": "success"}


@router.get("/bot")
async def get_bot_config():
    config = _load_config()
    return config.get("bot", {})


@router.post("/bot")
async def update_bot_config(bot_config: BotConfig):
    config = _load_config()
    config["bot"] = bot_config.model_dump()
    _save_config(config)
    return {"status": "success"}
