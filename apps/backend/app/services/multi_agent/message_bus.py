"""
AgentMessageBus - Redis Pub/Sub для межагентной коммуникации.

Основные возможности:
- Publish/Subscribe через Redis
- Broadcast сообщения (все агенты)
- Direct messaging (точка-точка)
- Request-response с timeout
- Message history для debugging
- Статистика отправки/получения

Примеры использования см. в docs/MESSAGE_BUS_QUICKSTART.md
"""
import asyncio
import logging
from typing import Optional, Dict, Callable, List, Any
from datetime import datetime
from redis import asyncio as aioredis
from uuid import uuid4

from .message_types import MessageType, AgentMessage, AcknowledgementMessage
from .redis_config import RedisConfig, ChannelPatterns
from .exceptions import MessageBusError, MessageDeliveryError, TimeoutError

logger = logging.getLogger(__name__)


class AgentMessageBus:
    """
    Message Bus для коммуникации между агентами через Redis Pub/Sub.
    
    Архитектура:
    - Broadcast канал: gigaboard:board:{board_id}:agents:broadcast
    - Agent inbox: gigaboard:agents:{agent_name}:inbox
    - UI events: gigaboard:board:{board_id}:agents:ui_events
    - Session results: gigaboard:sessions:{session_id}:results
    - Errors: gigaboard:agents:errors
    
    Examples:
        # Создание и подключение
        bus = AgentMessageBus()
        await bus.connect()
        
        # Публикация сообщения
        message = AgentMessage(
            message_id=str(uuid4()),
            message_type=MessageType.USER_REQUEST,
            sender="orchestrator",
            receiver="broadcast",
            session_id="session_123",
            board_id="board_456",
            payload={"message": "Создай график"}
        )
        await bus.publish(message)
        
        # Подписка на сообщения
        async def handle_message(msg: AgentMessage):
            print(f"Received: {msg.message_type}")
        
        await bus.subscribe("planner", handle_message)
    """
    
    def __init__(self):
        """Инициализация Message Bus."""
        self.redis_client: Optional[aioredis.Redis] = None
        self._disconnecting = False
        
        # Отдельный PubSub connection для каждого агента
        self.agent_pubsubs: Dict[str, aioredis.client.PubSub] = {}
        
        # Хранение активных подписок
        self.subscriptions: Dict[str, List[Callable]] = {}
        
        # Pending responses для request-response паттерна
        self.pending_responses: Dict[str, asyncio.Future] = {}
        
        # Message history (для debugging, TTL 1 час в Redis)
        self.message_history: List[AgentMessage] = []
        
        # Статистика
        self.stats = {
            "messages_sent": 0,
            "messages_received": 0,
            "errors": 0,
            "broadcasts": 0,
            "direct_messages": 0,
        }
    
    async def connect(self):
        """
        Подключиться к Redis.
        
        Raises:
            MessageBusError: Если не удалось подключиться
        """
        try:
            self.redis_client = await RedisConfig.create_redis_client()
            logger.info("AgentMessageBus connected to Redis")
        except Exception as e:
            logger.error(f"Failed to connect AgentMessageBus: {e}")
            raise MessageBusError(f"Connection failed: {e}")
    
    async def disconnect(self):
        """Отключиться от Redis."""
        self._disconnecting = True
        # Закрываем все PubSub connections
        for agent_name, pubsub in self.agent_pubsubs.items():
            try:
                await pubsub.unsubscribe()
                await pubsub.close()
                logger.info(f"Closed PubSub for agent '{agent_name}'")
            except Exception as e:
                logger.error(f"Error closing PubSub for '{agent_name}': {e}")
        
        if self.redis_client:
            await self.redis_client.close()
        
        logger.info("AgentMessageBus disconnected")
    
    async def publish(
        self,
        message: AgentMessage,
        wait_for_ack: bool = False
    ) -> str:
        """
        Опубликовать сообщение в Redis channel.
        
        Args:
            message: Сообщение для публикации
            wait_for_ack: Ждать ли подтверждения получения
            
        Returns:
            str: ID опубликованного сообщения
            
        Raises:
            MessageBusError: Если не удалось опубликовать
        """
        if not self.redis_client:
            raise MessageBusError("Message Bus not connected")
        
        try:
            # Определяем target channel
            channel = self._get_channel_for_message(message)
            
            logger.info(
                f"📤 PUBLISH: {message.message_type} from {message.sender} "
                f"to {message.receiver} on channel '{channel}' (msg_id: {message.message_id[:8]}...)"
            )
            
            # Сериализуем сообщение
            message_json = message.model_dump_json()
            
            logger.debug(f"📦 Message payload: {message_json[:200]}...")
            
            # Публикуем в Redis
            subscribers = await self.redis_client.publish(channel, message_json)
            
            logger.info(
                f"✅ Published to {subscribers} subscriber(s) on channel '{channel}'"
            )
            
            # Сохраняем в историю (с TTL)
            await self._store_in_history(message)
            
            # Статистика
            self.stats["messages_sent"] += 1
            if message.receiver == "broadcast":
                self.stats["broadcasts"] += 1
            else:
                self.stats["direct_messages"] += 1
            
            logger.debug(
                f"Published {message.message_type} from {message.sender} "
                f"to {message.receiver} on channel {channel}"
            )
            
            # Если требуется ACK, ждём
            if wait_for_ack or message.requires_acknowledgement:
                await self._wait_for_acknowledgement(
                    message.message_id,
                    timeout=message.timeout_seconds or 30
                )
            
            return message.message_id
            
        except Exception as e:
            self.stats["errors"] += 1
            logger.error(f"Failed to publish message: {e}")
            raise MessageDeliveryError(f"Publish failed: {e}")
    
    async def subscribe(
        self,
        agent_name: str,
        callback: Callable[[AgentMessage], Any],
        listen_to_broadcast: bool = True
    ):
        """
        Подписать агента на получение сообщений.
        
        Агент будет получать:
        - Сообщения на свой inbox (gigaboard:agents:{agent_name}:inbox)
        - Broadcast сообщения (если listen_to_broadcast=True)
        
        Args:
            agent_name: Имя агента (уникальное)
            callback: Async функция для обработки сообщений
            listen_to_broadcast: Подписаться ли на broadcast канал
        """
        if not self.redis_client:
            raise MessageBusError("Message Bus not connected")
        
        # Создаём отдельный PubSub connection для этого агента
        if agent_name not in self.agent_pubsubs:
            pubsub = self.redis_client.pubsub()
            self.agent_pubsubs[agent_name] = pubsub
            logger.info(f"✨ Created dedicated PubSub connection for agent '{agent_name}'")
        
        pubsub = self.agent_pubsubs[agent_name]
        
        # Подписываемся на inbox агента
        inbox_channel = ChannelPatterns.get_agent_inbox(agent_name)
        
        logger.info(f"🔔 SUBSCRIBING agent '{agent_name}' to channel '{inbox_channel}'...")
        
        await pubsub.subscribe(inbox_channel)
        
        logger.info(f"✅ SUBSCRIBED agent '{agent_name}' to channel '{inbox_channel}'")
        
        # Опционально подписываемся на broadcast (нужен board_id, пока пропускаем)
        # TODO: Подписка на broadcast для конкретной доски
        
        # Сохраняем callback
        if agent_name not in self.subscriptions:
            self.subscriptions[agent_name] = []
        self.subscriptions[agent_name].append(callback)
        
        logger.info(f"📋 Callbacks registered for agent '{agent_name}': {len(self.subscriptions[agent_name])}")
        
        # Запускаем listener в фоне
        asyncio.create_task(self._listen_loop(agent_name, callback))
    
    async def request_response(
        self,
        message: AgentMessage,
        timeout: float = 30.0
    ) -> AgentMessage:
        """
        Отправить сообщение и ждать ответа (request-response паттерн).
        
        Args:
            message: Сообщение-запрос
            timeout: Таймаут ожидания ответа (секунды)
            
        Returns:
            AgentMessage: Ответное сообщение
            
        Raises:
            TimeoutError: Если ответ не получен за timeout
        """
        # Создаём Future для ожидания ответа
        response_future = asyncio.Future()
        self.pending_responses[message.message_id] = response_future
        
        # Создаём временный PubSub для получения ответа
        response_channel = ChannelPatterns.get_session_results_channel(message.session_id)
        temp_pubsub = self.redis_client.pubsub()
        
        await temp_pubsub.subscribe(response_channel)
        logger.info(f"👂 Subscribed to response channel: {response_channel}")
        
        # Публикуем запрос
        await self.publish(message)
        
        #Запускаем listener в фоне
        async def listen_for_response():
            try:
                async for raw_message in temp_pubsub.listen():
                    if raw_message["type"] == "message":
                        response = AgentMessage.model_validate_json(raw_message["data"])
                        if response.parent_message_id == message.message_id:
                            if not response_future.done():
                                response_future.set_result(response)
                            break
            except Exception as e:
                logger.error(f"Error in temp listener: {e}")
                if not response_future.done():
                    response_future.set_exception(e)
            finally:
                await temp_pubsub.unsubscribe(response_channel)
                await temp_pubsub.close()
        
        listener_task = asyncio.create_task(listen_for_response())
        
        try:
            # Ждём ответа с timeout
            response = await asyncio.wait_for(response_future, timeout=timeout)
            return response
        except asyncio.TimeoutError:
            # Удаляем из pending
            self.pending_responses.pop(message.message_id, None)
            listener_task.cancel()
            raise MessageBusError(
                f"No response received for message {message.message_id} "
                f"within {timeout}s"
            )
        finally:
            # Cleanup
            if not listener_task.done():
                listener_task.cancel()
            try:
                await listener_task
            except asyncio.CancelledError:
                pass
    
    async def _listen_loop(self, agent_name: str, callback: Callable):
        """
        Фоновая задача для прослушивания сообщений.
        
        Args:
            agent_name: Имя агента
            callback: Функция обработки сообщений
        """
        pubsub = self.agent_pubsubs.get(agent_name)
        if not pubsub:
            logger.error(f"No PubSub found for agent '{agent_name}'")
            return
        
        logger.info(f"🎧 LISTEN LOOP started for agent '{agent_name}'")
        
        try:
            async for redis_message in pubsub.listen():
                logger.debug(
                    f"📨 Raw Redis message for '{agent_name}': type={redis_message.get('type')}, "
                    f"channel={redis_message.get('channel')}"
                )
                
                if redis_message["type"] != "message":
                    continue
                
                try:
                    # Десериализуем сообщение
                    message_data = redis_message["data"]
                    
                    logger.info(
                        f"📥 RECEIVED raw message for agent '{agent_name}' on channel '{redis_message.get('channel')}'"
                    )
                    
                    message = AgentMessage.model_validate_json(message_data)
                    
                    # Статистика
                    self.stats["messages_received"] += 1
                    
                    logger.info(
                        f"✅ PARSED message for '{agent_name}': {message.message_type} "
                        f"from {message.sender} to {message.receiver} (msg_id: {message.message_id[:8]}...)"
                    )
                    
                    # Обрабатываем acknowledgements
                    if message.message_type == MessageType.ACKNOWLEDGEMENT:
                        self._handle_acknowledgement(message)
                        continue
                    
                    # Проверяем pending responses
                    if message.parent_message_id in self.pending_responses:
                        future = self.pending_responses.pop(message.parent_message_id)
                        if not future.done():
                            future.set_result(message)
                        continue
                    
                    # Вызываем callback
                    await callback(message)
                    
                except Exception as e:
                    logger.error(f"Error processing message in agent '{agent_name}': {e}")
                    self.stats["errors"] += 1
                    
        except asyncio.CancelledError:
            logger.info(f"Listening loop for '{agent_name}' cancelled")
        except Exception as e:
            if self._disconnecting and "Connection closed by server" in str(e):
                logger.info(
                    f"Listening loop for '{agent_name}' closed during shutdown: {e}"
                )
            else:
                logger.error(f"Fatal error in listening loop for '{agent_name}': {e}")
    
    def _get_channel_for_message(self, message: AgentMessage) -> str:
        """
        Определить Redis channel для сообщения на основе receiver.
        
        Args:
            message: Сообщение
            
        Returns:
            str: Redis channel name
        """
        if message.receiver == "broadcast":
            return ChannelPatterns.get_broadcast_channel(message.board_id)
        elif message.receiver == "orchestrator":
            return ChannelPatterns.get_session_results_channel(message.session_id)
        elif message.message_type == MessageType.ERROR:
            return ChannelPatterns.ERRORS
        elif message.message_type in [MessageType.NODE_CREATED, MessageType.UI_NOTIFICATION]:
            return ChannelPatterns.get_ui_events_channel(message.board_id)
        else:
            # Direct message to agent
            return ChannelPatterns.get_agent_inbox(message.receiver)
    
    async def _store_in_history(self, message: AgentMessage):
        """
        Сохранить сообщение в историю (Redis с TTL).
        
        Args:
            message: Сообщение для сохранения
        """
        if not self.redis_client:
            return
        
        try:
            history_key = f"gigaboard:messages:history:{message.session_id}"
            message_json = message.model_dump_json()
            
            # Добавляем в список с TTL
            await self.redis_client.lpush(history_key, message_json)
            await self.redis_client.expire(history_key, RedisConfig.MESSAGE_HISTORY_TTL)
            
        except Exception as e:
            logger.warning(f"Failed to store message in history: {e}")
    
    async def _wait_for_acknowledgement(
        self,
        message_id: str,
        timeout: float = 30.0
    ) -> bool:
        """
        Ждать подтверждения получения сообщения.
        
        Args:
            message_id: ID сообщения
            timeout: Таймаут ожидания
            
        Returns:
            bool: True если ACK получен, False если timeout
        """
        # TODO: Implement ACK waiting logic
        # Пока заглушка
        await asyncio.sleep(0.1)
        return True
    
    def _handle_acknowledgement(self, message: AgentMessage):
        """
        Обработать ACK сообщение.
        
        Args:
            message: ACK сообщение
        """
        # TODO: Implement ACK handling
        pass
    
    async def get_message_history(
        self,
        session_id: str,
        limit: int = 100
    ) -> List[AgentMessage]:
        """
        Получить историю сообщений для сессии.
        
        Args:
            session_id: ID сессии
            limit: Максимальное количество сообщений
            
        Returns:
            List[AgentMessage]: Список сообщений в хронологическом порядке
        """
        if not self.redis_client:
            return []
        
        try:
            history_key = f"gigaboard:messages:history:{session_id}"
            messages_json = await self.redis_client.lrange(history_key, 0, limit - 1)
            
            messages = [
                AgentMessage.model_validate_json(msg_json)
                for msg_json in messages_json
            ]
            
            # Возвращаем в хронологическом порядке (Redis lpush сохраняет в обратном)
            return list(reversed(messages))
            
        except Exception as e:
            logger.error(f"Failed to get message history: {e}")
            return []
    
    async def get_stats(self) -> Dict[str, Any]:
        """Получить статистику Message Bus."""
        return {
            **self.stats,
            "active_subscriptions": len(self.subscriptions),
            "pending_responses": len(self.pending_responses),
        }

    # ============================================================
    # Session Results Storage - централизованное хранение результатов
    # ============================================================
    
    async def store_session_result(
        self,
        session_id: str,
        agent_name: str,
        result: Dict[str, Any],
        ttl_seconds: int = 3600  # 1 час по умолчанию
    ) -> bool:
        """
        Сохранить результат агента в Redis для данной сессии.
        
        Результаты хранятся в Redis Hash:
        - Key: gigaboard:sessions:{session_id}:agent_results
        - Field: {agent_name}
        - Value: JSON результата
        
        Args:
            session_id: ID сессии
            agent_name: Имя агента (search, researcher, analyst, etc.)
            result: Результат работы агента
            ttl_seconds: Время жизни результата в секундах
            
        Returns:
            bool: True если успешно сохранено
        """
        if not self.redis_client:
            logger.error("Cannot store result: Redis not connected")
            return False
        
        try:
            import json
            
            key = f"gigaboard:sessions:{session_id}:agent_results"
            value = json.dumps(result, ensure_ascii=False, default=str)
            
            # Сохраняем в Hash
            await self.redis_client.hset(key, agent_name, value)
            
            # Устанавливаем/обновляем TTL на весь hash
            await self.redis_client.expire(key, ttl_seconds)
            
            logger.info(f"💾 Stored result for '{agent_name}' in session {session_id[:8]}...")
            return True
            
        except Exception as e:
            logger.error(f"Failed to store session result: {e}")
            return False
    
    async def get_session_result(
        self,
        session_id: str,
        agent_name: str
    ) -> Optional[Dict[str, Any]]:
        """
        Получить результат конкретного агента из сессии.
        
        Args:
            session_id: ID сессии
            agent_name: Имя агента
            
        Returns:
            Dict с результатом или None если не найден
        """
        if not self.redis_client:
            return None
        
        try:
            import json
            
            key = f"gigaboard:sessions:{session_id}:agent_results"
            value = await self.redis_client.hget(key, agent_name)
            
            if value:
                result = json.loads(value)
                logger.debug(f"📦 Retrieved result for '{agent_name}' from session {session_id[:8]}...")
                return result
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get session result: {e}")
            return None
    
    async def get_all_session_results(
        self,
        session_id: str
    ) -> Dict[str, Any]:
        """
        Получить все результаты агентов для сессии.
        
        Args:
            session_id: ID сессии
            
        Returns:
            Dict[agent_name, result] со всеми результатами
        """
        if not self.redis_client:
            return {}
        
        try:
            import json
            
            key = f"gigaboard:sessions:{session_id}:agent_results"
            all_results = await self.redis_client.hgetall(key)
            
            parsed_results = {}
            for agent_name, value in all_results.items():
                # Redis может вернуть bytes или str в зависимости от настроек
                if isinstance(agent_name, bytes):
                    agent_name = agent_name.decode('utf-8')
                if isinstance(value, bytes):
                    value = value.decode('utf-8')
                
                parsed_results[agent_name] = json.loads(value)
            
            logger.debug(f"📦 Retrieved {len(parsed_results)} results for session {session_id[:8]}...")
            return parsed_results
            
        except Exception as e:
            logger.error(f"Failed to get all session results: {e}")
            return {}
    
    async def clear_session_results(self, session_id: str) -> bool:
        """
        Очистить все результаты сессии.
        
        Args:
            session_id: ID сессии
            
        Returns:
            bool: True если успешно удалено
        """
        if not self.redis_client:
            return False
        
        try:
            key = f"gigaboard:sessions:{session_id}:agent_results"
            await self.redis_client.delete(key)
            logger.info(f"🗑️ Cleared results for session {session_id[:8]}...")
            return True
            
        except Exception as e:
            logger.error(f"Failed to clear session results: {e}")
            return False
