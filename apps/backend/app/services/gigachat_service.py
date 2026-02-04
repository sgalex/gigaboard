"""
GigaChat Service - обертка над langchain-gigachat для интеграции с GigaBoard.

См. docs/AI_ASSISTANT.md и docs/MULTI_AGENT_SYSTEM.md
"""
import logging
from typing import List, Dict, Any, Optional, AsyncIterator
from langchain_gigachat import GigaChat
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

logger = logging.getLogger(__name__)


class GigaChatService:
    """
    Сервис для работы с GigaChat API через langchain-gigachat.
    
    Функционал:
    - Chat completion (синхронный и асинхронный)
    - Streaming responses
    - Context management для board conversations
    - Error handling и retry logic
    """
    
    def __init__(
        self,
        api_key: str,
        model: str = "GigaChat",
        temperature: float = 0.7,
        max_tokens: Optional[int] = 2048,
        verify_ssl_certs: bool = False,
        scope: str = "GIGACHAT_API_CORP",
    ):
        """
        Инициализация GigaChat сервиса.
        
        Args:
            api_key: API ключ GigaChat
            model: Название модели (GigaChat, GigaChat-Pro, GigaChat-Max)
            temperature: Креативность ответов (0.0-1.0)
            max_tokens: Максимальная длина ответа
            verify_ssl_certs: Проверка SSL сертификатов
            scope: Scope доступа (GIGACHAT_API_PERS или GIGACHAT_API_CORP)
        """
        if not api_key:
            raise ValueError("GigaChat API key is required")
        
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.scope = scope
        
        # Инициализация LangChain GigaChat
        try:
            self.client = GigaChat(
                credentials=api_key,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                verify_ssl_certs=verify_ssl_certs,
                scope=scope,
                timeout=120.0,  # Увеличен таймаут до 120 секунд для сложных запросов
            )
            logger.info(f"GigaChat service initialized with model: {model}, scope: {scope}")
        except Exception as e:
            logger.error(f"Failed to initialize GigaChat: {e}")
            raise
    
    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """
        Отправить запрос к GigaChat и получить ответ.
        
        Args:
            messages: Список сообщений в формате [{"role": "user", "content": "..."}]
            temperature: Override температуры
            max_tokens: Override максимальной длины
            
        Returns:
            Текстовый ответ от GigaChat
            
        Example:
            >>> messages = [
            ...     {"role": "system", "content": "You are a data analyst assistant."},
            ...     {"role": "user", "content": "Analyze sales data trends."}
            ... ]
            >>> response = await service.chat_completion(messages)
        """
        try:
            # Конвертация в LangChain message format
            lc_messages = self._convert_to_langchain_messages(messages)
            
            # Временное переопределение параметров
            original_temp = self.client.temperature
            original_max = self.client.max_tokens
            
            if temperature is not None:
                self.client.temperature = temperature
            if max_tokens is not None:
                self.client.max_tokens = max_tokens
            
            # Вызов GigaChat
            logger.debug(f"Sending request to GigaChat: {len(messages)} messages")
            response = await self.client.ainvoke(lc_messages)
            
            # Восстановление параметров
            self.client.temperature = original_temp
            self.client.max_tokens = original_max
            
            logger.debug(f"Received response from GigaChat: {len(response.content)} chars")
            return response.content
            
        except Exception as e:
            logger.error(f"GigaChat API error: {e}")
            raise RuntimeError(f"Failed to get response from GigaChat: {e}")
    
    async def chat_completion_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
    ) -> AsyncIterator[str]:
        """
        Streaming responses от GigaChat.
        
        Args:
            messages: Список сообщений
            temperature: Override температуры
            
        Yields:
            Chunks текстового ответа
            
        Example:
            >>> async for chunk in service.chat_completion_stream(messages):
            ...     print(chunk, end="", flush=True)
        """
        try:
            lc_messages = self._convert_to_langchain_messages(messages)
            
            original_temp = self.client.temperature
            if temperature is not None:
                self.client.temperature = temperature
            
            logger.debug(f"Starting streaming request to GigaChat")
            
            async for chunk in self.client.astream(lc_messages):
                if chunk.content:
                    yield chunk.content
            
            self.client.temperature = original_temp
            
        except Exception as e:
            logger.error(f"GigaChat streaming error: {e}")
            raise RuntimeError(f"Failed to stream from GigaChat: {e}")
    
    def _convert_to_langchain_messages(
        self,
        messages: List[Dict[str, str]]
    ) -> List[SystemMessage | HumanMessage | AIMessage]:
        """
        Конвертация словарей в LangChain message objects.
        
        Args:
            messages: [{"role": "user", "content": "..."}, ...]
            
        Returns:
            List of LangChain message objects
        """
        lc_messages = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            
            if role == "system":
                lc_messages.append(SystemMessage(content=content))
            elif role == "assistant":
                lc_messages.append(AIMessage(content=content))
            else:  # user or any other
                lc_messages.append(HumanMessage(content=content))
        
        return lc_messages
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Проверка доступности GigaChat API.
        
        Returns:
            {"status": "ok"/"error", "model": "...", "error": "..."}
        """
        try:
            test_messages = [{"role": "user", "content": "ping"}]
            response = await self.chat_completion(test_messages)
            
            return {
                "status": "ok",
                "model": self.model,
                "response_length": len(response),
            }
        except Exception as e:
            logger.error(f"GigaChat health check failed: {e}")
            return {
                "status": "error",
                "model": self.model,
                "error": str(e),
            }


# Singleton instance для использования в приложении
_gigachat_service: Optional[GigaChatService] = None


def initialize_gigachat_service(
    api_key: str,
    model: str = "GigaChat",
    temperature: float = 0.7,
    max_tokens: int = 2048,
    scope: str = "GIGACHAT_API_CORP",
    verify_ssl_certs: bool = False,
) -> GigaChatService:
    """
    Инициализация глобального instance GigaChat сервиса.
    
    Args:
        api_key: GigaChat API key
        model: Название модели
        temperature: Температура
        max_tokens: Максимальное количество токенов
        scope: Scope доступа
        verify_ssl_certs: Проверка SSL сертификатов
        
    Returns:
        Инициализированный GigaChatService
    """
    global _gigachat_service
    
    _gigachat_service = GigaChatService(
        api_key=api_key,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        scope=scope,
        verify_ssl_certs=verify_ssl_certs,
    )
    
    logger.info("Global GigaChat service initialized")
    return _gigachat_service


def get_gigachat_service() -> GigaChatService:
    """
    Получить глобальный instance GigaChat сервиса.
    
    Returns:
        GigaChatService instance
        
    Raises:
        RuntimeError: Если сервис не был инициализирован
    """
    if _gigachat_service is None:
        raise RuntimeError(
            "GigaChat service not initialized. "
            "Call initialize_gigachat_service() first."
        )
    return _gigachat_service
