"""大模型统一调用模块 - 兼容OpenAI格式的国产模型"""
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class LLMClient:
    """通过OpenAI兼容格式调用各种国产大模型"""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        max_tokens: int = 500,
        temperature: float = 0.7
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self._client = None

        try:
            from openai import OpenAI
            self._client = OpenAI(
                base_url=self.base_url,
                api_key=self.api_key,
                timeout=60,
            )
            logger.info(f"LLM客户端初始化成功，模型: {model}")
        except ImportError:
            logger.error("openai库未安装，请运行: pip install openai")
            raise
        except Exception as e:
            logger.error(f"LLM客户端初始化失败: {e}")
            raise

    def chat(
        self,
        system_prompt: str,
        messages: List[Dict[str, str]],
        max_tokens: int = None,
        temperature: float = None
    ) -> Optional[str]:
        """
        调用大模型生成回复
        :param system_prompt: 系统提示词（人设）
        :param messages: 历史消息列表，每项为 {"role": "user"|"assistant", "content": "..."}
        :return: 生成的回复文本，失败返回None
        """
        if self._client is None:
            logger.error("LLM客户端未初始化")
            return None

        try:
            # 构建消息列表
            # 如果 system prompt 很长（超过 2000 字），合并到第一条消息里，
            # 避免某些 API 把长 system prompt 当成普通消息
            if len(system_prompt) > 2000 and messages:
                chat_messages = messages.copy()
                chat_messages[0]["content"] = f"【你的角色设定】\n{system_prompt}\n\n【群友消息】\n{chat_messages[0]['content']}"
                logger.debug(f"长 system prompt 已合并到首条消息，消息数: {len(chat_messages)}")
            else:
                chat_messages = [{"role": "system", "content": system_prompt}]
                chat_messages.extend(messages)
                logger.debug(f"发送请求，消息数: {len(chat_messages)}")

            # 限制 max_tokens 上限，防止配置错误导致超长回复
            mt = self.max_tokens if max_tokens is None else max_tokens
            if mt > 1000:
                mt = 1000

            response = self._client.chat.completions.create(
                model=self.model,
                messages=chat_messages,
                max_tokens=mt,
                temperature=self.temperature if temperature is None else temperature,
                stream=False,
            )

            if response.choices and len(response.choices) > 0:
                content = response.choices[0].message.content
                if not content:
                    logger.warning("LLM返回空内容")
                    return None
                logger.debug(f"收到回复: {content[:100]}...")
                return content.strip()
            else:
                logger.warning("LLM返回空响应")
                return None

        except Exception as e:
            logger.error(f"LLM调用失败: {e}")
            return None

    def build_chat_context(
        self,
        history: List,
        new_messages: List,
        bot_name: str = ""
    ) -> List[Dict[str, str]]:
        """
        构建发送给大模型的消息上下文
        :param history: 历史消息对象列表
        :param new_messages: 新消息对象列表
        :return: OpenAI格式的消息列表
        """
        context = []

        # 添加历史消息
        for msg in history:
            role = "assistant" if msg.is_bot else "user"
            prefix = f"{msg.sender}: " if not msg.is_bot else ""
            context.append({
                "role": role,
                "content": f"{prefix}{msg.content}"
            })

        # 添加新消息
        for msg in new_messages:
            if not msg.is_bot:
                context.append({
                    "role": "user",
                    "content": f"{msg.sender}: {msg.content}"
                })

        return context

    def test_connection(self) -> bool:
        """测试API连接是否正常"""
        try:
            response = self._client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "你好"}],
                max_tokens=10,
                stream=False,
            )
            return response.choices is not None and len(response.choices) > 0
        except Exception as e:
            logger.error(f"API连接测试失败: {e}")
            return False
