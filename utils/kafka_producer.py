"""
Kafka Producer для отправки событий чата поддержки
"""
import json
import uuid
import asyncio
from datetime import datetime
from typing import Optional, Dict, Any
from aiokafka import AIOKafkaProducer
import logging

from config.kafka_config import (
    KAFKA_CONFIG, KafkaTopics, 
    BaseKafkaEvent, ChatEvent, SupportQueueEvent, 
    OperatorEvent, AssignmentEvent, AdminActionEvent,
    ChatEventType, SupportQueueEventType, OperatorEventType,
    AssignmentEventType, AdminActionType
)

logger = logging.getLogger(__name__)


class SupportChatKafkaProducer:
    """Kafka Producer для чата поддержки"""
    
    def __init__(self):
        self.producer: Optional[AIOKafkaProducer] = None
        self._started = False
    
    async def start(self):
        """Запуск producer"""
        if not self._started:
            self.producer = AIOKafkaProducer(
                bootstrap_servers=KAFKA_CONFIG['bootstrap_servers'],
                client_id=KAFKA_CONFIG['client_id'],
                value_serializer=lambda v: json.dumps(v, default=str).encode('utf-8')
            )
            await self.producer.start()
            self._started = True
            logger.info("Kafka Producer запущен")
    
    async def stop(self):
        """Остановка producer"""
        if self.producer and self._started:
            await self.producer.stop()
            self._started = False
            logger.info("Kafka Producer остановлен")
    
    async def _send_event(self, topic: str, event: BaseKafkaEvent, key: Optional[str] = None):
        """Отправка события в Kafka"""
        if not self._started:
            await self.start()
        
        try:
            event_dict = event.model_dump()
            await self.producer.send_and_wait(
                topic=topic,
                value=event_dict,
                key=key.encode('utf-8') if key else None
            )
            logger.debug(f"Событие отправлено в топик {topic}: {event.event_type}")
        except Exception as e:
            logger.error(f"Ошибка отправки события в Kafka: {e}")
            raise
    
    # Методы для отправки событий чата
    
    async def send_chat_created(self, chat_id: int, user_id: int, metadata: Optional[Dict] = None):
        """Отправка события создания чата"""
        event = ChatEvent(
            event_id=str(uuid.uuid4()),
            event_type=ChatEventType.CHAT_CREATED,
            timestamp=datetime.utcnow(),
            chat_id=chat_id,
            user_id=user_id,
            metadata=metadata
        )
        await self._send_event(KafkaTopics.CHAT_EVENTS, event, key=f"chat_{chat_id}")
    
    async def send_message_sent(self, chat_id: int, sender_id: int, sender_type: str, 
                               message_id: int, message_text: Optional[str] = None):
        """Отправка события отправки сообщения"""
        event = ChatEvent(
            event_id=str(uuid.uuid4()),
            event_type=ChatEventType.MESSAGE_SENT,
            timestamp=datetime.utcnow(),
            chat_id=chat_id,
            sender_id=sender_id,
            sender_type=sender_type,
            message_id=message_id,
            message_text=message_text
        )
        await self._send_event(KafkaTopics.CHAT_EVENTS, event, key=f"chat_{chat_id}")
    
    async def send_operator_joined(self, chat_id: int, operator_id: int, operator_type: str):
        """Отправка события входа оператора в чат"""
        event = ChatEvent(
            event_id=str(uuid.uuid4()),
            event_type=ChatEventType.OPERATOR_JOINED,
            timestamp=datetime.utcnow(),
            chat_id=chat_id,
            user_id=operator_id,
            metadata={'operator_type': operator_type}
        )
        await self._send_event(KafkaTopics.CHAT_EVENTS, event, key=f"chat_{chat_id}")
    
    async def send_chat_closed(self, chat_id: int, closed_by_user_id: int, reason: Optional[str] = None):
        """Отправка события закрытия чата"""
        event = ChatEvent(
            event_id=str(uuid.uuid4()),
            event_type=ChatEventType.CHAT_CLOSED,
            timestamp=datetime.utcnow(),
            chat_id=chat_id,
            user_id=closed_by_user_id,
            metadata={'reason': reason} if reason else None
        )
        await self._send_event(KafkaTopics.CHAT_EVENTS, event, key=f"chat_{chat_id}")
    
    # Методы для отправки событий очереди поддержки
    
    async def send_client_waiting(self, client_id: int, priority: int = 0, metadata: Optional[Dict] = None):
        """Отправка события ожидания клиента в очереди"""
        event = SupportQueueEvent(
            event_id=str(uuid.uuid4()),
            event_type=SupportQueueEventType.CLIENT_WAITING,
            timestamp=datetime.utcnow(),
            client_id=client_id,
            user_id=client_id,
            priority=priority,
            metadata=metadata
        )
        await self._send_event(KafkaTopics.SUPPORT_QUEUE, event, key=f"client_{client_id}")
    
    async def send_client_request_removed(self, client_id: int, operator_id: int, chat_id: int):
        """Отправка события удаления запроса клиента из очереди (принят оператором)"""
        event = SupportQueueEvent(
            event_id=str(uuid.uuid4()),
            event_type=SupportQueueEventType.CLIENT_REQUEST_REMOVED,
            timestamp=datetime.utcnow(),
            client_id=client_id,
            user_id=client_id,
            chat_id=chat_id,
            metadata={'operator_id': operator_id}
        )
        await self._send_event(KafkaTopics.SUPPORT_QUEUE, event, key=f"client_{client_id}")
    
    # Методы для отправки событий операторов
    
    async def send_operator_online(self, operator_id: int, operator_type: str, max_concurrent_chats: int = 5):
        """Отправка события выхода оператора в онлайн"""
        event = OperatorEvent(
            event_id=str(uuid.uuid4()),
            event_type=OperatorEventType.OPERATOR_ONLINE,
            timestamp=datetime.utcnow(),
            operator_id=operator_id,
            operator_type=operator_type,
            max_concurrent_chats=max_concurrent_chats,
            current_chat_count=0
        )
        await self._send_event(KafkaTopics.OPERATOR_EVENTS, event, key=f"operator_{operator_id}")
    
    async def send_operator_offline(self, operator_id: int, operator_type: str):
        """Отправка события выхода оператора из онлайн"""
        event = OperatorEvent(
            event_id=str(uuid.uuid4()),
            event_type=OperatorEventType.OPERATOR_OFFLINE,
            timestamp=datetime.utcnow(),
            operator_id=operator_id,
            operator_type=operator_type
        )
        await self._send_event(KafkaTopics.OPERATOR_EVENTS, event, key=f"operator_{operator_id}")
    
    async def send_operator_accept_chat(self, operator_id: int, operator_type: str, chat_id: int, client_id: int):
        """Отправка события принятия чата оператором"""
        event = OperatorEvent(
            event_id=str(uuid.uuid4()),
            event_type=OperatorEventType.OPERATOR_ACCEPT_CHAT,
            timestamp=datetime.utcnow(),
            operator_id=operator_id,
            operator_type=operator_type,
            chat_id=chat_id,
            metadata={'client_id': client_id}
        )
        await self._send_event(KafkaTopics.OPERATOR_EVENTS, event, key=f"operator_{operator_id}")
    
    # Методы для отправки событий назначений
    
    async def send_chat_assigned(self, chat_id: int, operator_id: int, operator_type: str, 
                                client_id: int, assignment_reason: Optional[str] = None):
        """Отправка события назначения чата оператору"""
        event = AssignmentEvent(
            event_id=str(uuid.uuid4()),
            event_type=AssignmentEventType.CHAT_ASSIGNED,
            timestamp=datetime.utcnow(),
            chat_id=chat_id,
            user_id=client_id,
            operator_id=operator_id,
            operator_type=operator_type,
            assignment_reason=assignment_reason
        )
        await self._send_event(KafkaTopics.CHAT_ASSIGNMENTS, event, key=f"chat_{chat_id}")
    
    async def send_chat_transferred(self, chat_id: int, new_operator_id: int, new_operator_type: str,
                                   previous_operator_id: int, client_id: int, reason: Optional[str] = None):
        """Отправка события перевода чата другому оператору"""
        event = AssignmentEvent(
            event_id=str(uuid.uuid4()),
            event_type=AssignmentEventType.CHAT_TRANSFERRED,
            timestamp=datetime.utcnow(),
            chat_id=chat_id,
            user_id=client_id,
            operator_id=new_operator_id,
            operator_type=new_operator_type,
            previous_operator_id=previous_operator_id,
            assignment_reason=reason
        )
        await self._send_event(KafkaTopics.CHAT_ASSIGNMENTS, event, key=f"chat_{chat_id}")
    
    async def send_lawyer_assigned(self, client_id: int, lawyer_id: int, chat_id: int):
        """Отправка события назначения персонального юриста"""
        event = AssignmentEvent(
            event_id=str(uuid.uuid4()),
            event_type=AssignmentEventType.LAWYER_ASSIGNED,
            timestamp=datetime.utcnow(),
            chat_id=chat_id,
            user_id=client_id,
            operator_id=lawyer_id,
            operator_type='lawyer',
            assignment_reason='personal_lawyer_assignment'
        )
        await self._send_event(KafkaTopics.CHAT_ASSIGNMENTS, event, key=f"client_{client_id}")
    
    # Методы для отправки административных действий
    
    async def send_force_transfer(self, admin_id: int, chat_id: int, target_operator_id: int, 
                                 source_operator_id: int, reason: str):
        """Отправка события принудительного перевода чата"""
        event = AdminActionEvent(
            event_id=str(uuid.uuid4()),
            event_type=AdminActionType.FORCE_TRANSFER,
            timestamp=datetime.utcnow(),
            admin_id=admin_id,
            chat_id=chat_id,
            target_operator_id=target_operator_id,
            source_operator_id=source_operator_id,
            reason=reason,
            force=True
        )
        await self._send_event(KafkaTopics.ADMIN_ACTIONS, event, key=f"chat_{chat_id}")


# Mock класс для работы без Kafka
class MockSupportChatKafkaProducer:
    """Mock Kafka Producer для режима без Kafka"""
    
    def __init__(self):
        self._started = False
    
    async def start(self):
        """Mock запуск producer"""
        self._started = True
        logger.info("Mock Kafka Producer запущен")
    
    async def stop(self):
        """Mock остановка producer"""
        self._started = False
        logger.info("Mock Kafka Producer остановлен")
    
    async def _send_event(self, topic: str, event: BaseKafkaEvent, key: Optional[str] = None):
        """Mock отправка события"""
        logger.debug(f"Mock: Событие {event.event_type} для топика {topic}")
    
    # Mock методы для всех событий чата
    async def send_chat_created(self, chat_id: int, user_id: int, metadata: Optional[Dict] = None):
        logger.debug(f"Mock: Чат {chat_id} создан для пользователя {user_id}")
    
    async def send_message_sent(self, chat_id: int, sender_id: int, sender_type: str, 
                               message_id: int, message_text: Optional[str] = None):
        logger.debug(f"Mock: Сообщение {message_id} отправлено в чат {chat_id}")
    
    async def send_operator_joined(self, chat_id: int, operator_id: int, operator_type: str):
        logger.debug(f"Mock: Оператор {operator_id} присоединился к чату {chat_id}")
    
    async def send_chat_closed(self, chat_id: int, closed_by_user_id: int, reason: Optional[str] = None):
        logger.debug(f"Mock: Чат {chat_id} закрыт пользователем {closed_by_user_id}")
    
    async def send_client_waiting(self, client_id: int, priority: int = 0, metadata: Optional[Dict] = None):
        logger.debug(f"Mock: Клиент {client_id} ожидает в очереди")
    
    async def send_client_request_removed(self, client_id: int, operator_id: int, chat_id: int):
        logger.debug(f"Mock: Запрос клиента {client_id} удален из очереди")
    
    async def send_operator_online(self, operator_id: int, operator_type: str, max_concurrent_chats: int = 5):
        logger.debug(f"Mock: Оператор {operator_id} онлайн")
    
    async def send_operator_offline(self, operator_id: int, operator_type: str):
        logger.debug(f"Mock: Оператор {operator_id} оффлайн")
    
    async def send_operator_accept_chat(self, operator_id: int, operator_type: str, chat_id: int, client_id: int):
        logger.debug(f"Mock: Оператор {operator_id} принял чат {chat_id}")
    
    async def send_chat_assigned(self, chat_id: int, operator_id: int, operator_type: str, 
                                client_id: int, assignment_reason: Optional[str] = None):
        logger.debug(f"Mock: Чат {chat_id} назначен оператору {operator_id}")
    
    async def send_chat_transferred(self, chat_id: int, new_operator_id: int, new_operator_type: str,
                                   previous_operator_id: int, client_id: int, reason: Optional[str] = None):
        logger.debug(f"Mock: Чат {chat_id} переведен на оператора {new_operator_id}")
    
    async def send_lawyer_assigned(self, client_id: int, lawyer_id: int, chat_id: int):
        logger.debug(f"Mock: Юрист {lawyer_id} назначен клиенту {client_id}")
    
    async def send_force_transfer(self, admin_id: int, chat_id: int, target_operator_id: int, 
                                 source_operator_id: int, reason: str):
        logger.debug(f"Mock: Принудительный перевод чата {chat_id} админом {admin_id}")


# Выбор реализации в зависимости от конфигурации
from config.kafka_config import KAFKA_ENABLED

if KAFKA_ENABLED:
    kafka_producer = SupportChatKafkaProducer()
else:
    kafka_producer = MockSupportChatKafkaProducer()
    logger.info("Используется Mock Kafka Producer (Kafka отключен)")
