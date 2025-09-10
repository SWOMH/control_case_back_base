"""
Конфигурация Kafka для чата поддержки
"""
from enum import Enum
from typing import Optional, Dict, Any
from pydantic import BaseModel
from datetime import datetime


class KafkaTopics:
    """Топики Kafka для чата поддержки"""
    
    # Основные топики
    CHAT_EVENTS = "chat_events"                    # События чата (сообщения, подключения)
    SUPPORT_QUEUE = "support_queue"                # Очередь обращений в поддержку
    OPERATOR_EVENTS = "operator_events"            # События операторов (онлайн/оффлайн, принятие чатов)
    CHAT_ASSIGNMENTS = "chat_assignments"          # Назначения чатов операторам/юристам
    ADMIN_ACTIONS = "admin_actions"                # Административные действия (переводы, закрытия)


class ChatEventType(str, Enum):
    """Типы событий чата"""
    
    # Базовые события чата
    CHAT_CREATED = "chat_created"
    CHAT_CLOSED = "chat_closed"
    MESSAGE_SENT = "message_sent"
    MESSAGE_READ = "message_read"
    TYPING_START = "typing_start"
    TYPING_STOP = "typing_stop"
    
    # События подключения
    USER_CONNECTED = "user_connected"
    USER_DISCONNECTED = "user_disconnected"
    OPERATOR_JOINED = "operator_joined"
    OPERATOR_LEFT = "operator_left"


class SupportQueueEventType(str, Enum):
    """Типы событий очереди поддержки"""
    
    CLIENT_WAITING = "client_waiting"              # Клиент ждет оператора
    CLIENT_REQUEST_REMOVED = "client_request_removed"  # Запрос клиента удален (принят оператором)
    PRIORITY_CHANGE = "priority_change"            # Изменение приоритета в очереди


class OperatorEventType(str, Enum):
    """Типы событий операторов"""
    
    OPERATOR_ONLINE = "operator_online"
    OPERATOR_OFFLINE = "operator_offline"
    OPERATOR_BUSY = "operator_busy"
    OPERATOR_AVAILABLE = "operator_available"
    OPERATOR_ACCEPT_CHAT = "operator_accept_chat"
    OPERATOR_REJECT_CHAT = "operator_reject_chat"


class AssignmentEventType(str, Enum):
    """Типы событий назначений"""
    
    CHAT_ASSIGNED = "chat_assigned"                # Чат назначен оператору
    CHAT_TRANSFERRED = "chat_transferred"          # Чат переведен другому оператору
    LAWYER_ASSIGNED = "lawyer_assigned"            # Клиенту назначен персональный юрист
    SUPPORT_TO_LAWYER = "support_to_lawyer"        # Перевод из поддержки к юристу


class AdminActionType(str, Enum):
    """Типы административных действий"""
    
    FORCE_TRANSFER = "force_transfer"              # Принудительный перевод чата
    FORCE_CLOSE = "force_close"                    # Принудительное закрытие чата
    OPERATOR_REASSIGN = "operator_reassign"        # Переназначение оператора
    PRIORITY_SET = "priority_set"                  # Установка приоритета


# Схемы событий

class BaseKafkaEvent(BaseModel):
    """Базовая схема события Kafka"""
    
    event_id: str
    event_type: str
    timestamp: datetime
    user_id: Optional[int] = None
    chat_id: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None


class ChatEvent(BaseKafkaEvent):
    """События чата"""
    
    event_type: ChatEventType
    sender_id: Optional[int] = None
    sender_type: Optional[str] = None
    message_id: Optional[int] = None
    message_text: Optional[str] = None


class SupportQueueEvent(BaseKafkaEvent):
    """События очереди поддержки"""
    
    event_type: SupportQueueEventType
    priority: int = 0
    client_id: int
    wait_time: Optional[int] = None  # время ожидания в секундах
    queue_position: Optional[int] = None


class OperatorEvent(BaseKafkaEvent):
    """События операторов"""
    
    event_type: OperatorEventType
    operator_id: int
    operator_type: str  # support, lawyer, salesman
    max_concurrent_chats: Optional[int] = None
    current_chat_count: Optional[int] = None


class AssignmentEvent(BaseKafkaEvent):
    """События назначений"""
    
    event_type: AssignmentEventType
    operator_id: int
    operator_type: str
    previous_operator_id: Optional[int] = None
    assignment_reason: Optional[str] = None


class AdminActionEvent(BaseKafkaEvent):
    """Административные действия"""
    
    event_type: AdminActionType
    admin_id: int
    target_operator_id: Optional[int] = None
    source_operator_id: Optional[int] = None
    reason: Optional[str] = None
    force: bool = False


# Конфигурация Kafka
KAFKA_CONFIG = {
    'bootstrap_servers': ['localhost:9092'],
    'client_id': 'support_chat_service',
    'auto_offset_reset': 'latest',
    'enable_auto_commit': True,
    'group_id': 'support_chat_group'
}

# Конфигурация топиков
TOPIC_CONFIG = {
    'num_partitions': 3,
    'replication_factor': 1,
    'config': {
        'retention.ms': 604800000,  # 7 дней
        'cleanup.policy': 'delete'
    }
}
