"""
Инициализация системы чата поддержки с Kafka
"""
import asyncio
import logging
from typing import Optional

from utils.kafka_producer import kafka_producer
from utils.kafka_consumer import kafka_consumer, SupportChatEventHandlers
from utils.queue_manager import queue_manager
from utils.assignment_manager import create_assignment_manager
from utils.websocket_manager import websocket_manager
from config.kafka_config import KafkaTopics, ChatEventType, SupportQueueEventType, OperatorEventType, AssignmentEventType, AdminActionType

logger = logging.getLogger(__name__)


class SupportChatSystem:
    """Главный класс системы чата поддержки"""
    
    def __init__(self):
        self.started = False
        self.assignment_manager = None
        self.event_handlers = None
        
    async def initialize(self):
        """Инициализация всей системы чата"""
        if self.started:
            logger.warning("Система чата уже инициализирована")
            return
        
        try:
            logger.info("Начало инициализации системы чата поддержки...")
            
            # 1. Запускаем Kafka Producer
            await kafka_producer.start()
            logger.info("Kafka Producer запущен")
            
            # 2. Запускаем менеджер очереди
            await queue_manager.start()
            logger.info("Менеджер очереди запущен")
            
            # 3. Создаем менеджер назначений
            self.assignment_manager = create_assignment_manager(queue_manager, websocket_manager)
            logger.info("Менеджер назначений создан")
            
            # 4. Создаем обработчики событий
            self.event_handlers = SupportChatEventHandlers(
                websocket_manager, 
                queue_manager, 
                self.assignment_manager
            )
            
            # 5. Регистрируем обработчики событий в Kafka Consumer
            self._register_event_handlers()
            logger.info("Обработчики событий зарегистрированы")
            
            # 6. Запускаем Kafka Consumer
            await kafka_consumer.start()
            logger.info("Kafka Consumer запущен")
            
            self.started = True
            logger.info("Система чата поддержки успешно инициализирована")
            
        except Exception as e:
            logger.error(f"Ошибка инициализации системы чата: {e}")
            await self.shutdown()
            raise
    
    def _register_event_handlers(self):
        """Регистрация обработчиков событий Kafka"""
        
        # Обработчики событий чата
        kafka_consumer.register_handler(
            KafkaTopics.CHAT_EVENTS, 
            ChatEventType.CHAT_CREATED.value, 
            self.event_handlers.handle_chat_created
        )
        kafka_consumer.register_handler(
            KafkaTopics.CHAT_EVENTS, 
            ChatEventType.MESSAGE_SENT.value, 
            self.event_handlers.handle_message_sent
        )
        kafka_consumer.register_handler(
            KafkaTopics.CHAT_EVENTS, 
            ChatEventType.OPERATOR_JOINED.value, 
            self.event_handlers.handle_operator_joined
        )
        kafka_consumer.register_handler(
            KafkaTopics.CHAT_EVENTS, 
            ChatEventType.CHAT_CLOSED.value, 
            self.event_handlers.handle_chat_closed
        )
        
        # Обработчики событий очереди поддержки
        kafka_consumer.register_handler(
            KafkaTopics.SUPPORT_QUEUE, 
            SupportQueueEventType.CLIENT_WAITING.value, 
            self.event_handlers.handle_client_waiting
        )
        kafka_consumer.register_handler(
            KafkaTopics.SUPPORT_QUEUE, 
            SupportQueueEventType.CLIENT_REQUEST_REMOVED.value, 
            self.event_handlers.handle_client_request_removed
        )
        
        # Обработчики событий операторов
        kafka_consumer.register_handler(
            KafkaTopics.OPERATOR_EVENTS, 
            OperatorEventType.OPERATOR_ONLINE.value, 
            self.event_handlers.handle_operator_online
        )
        kafka_consumer.register_handler(
            KafkaTopics.OPERATOR_EVENTS, 
            OperatorEventType.OPERATOR_OFFLINE.value, 
            self.event_handlers.handle_operator_offline
        )
        kafka_consumer.register_handler(
            KafkaTopics.OPERATOR_EVENTS, 
            OperatorEventType.OPERATOR_ACCEPT_CHAT.value, 
            self.event_handlers.handle_operator_accept_chat
        )
        
        # Обработчики событий назначений
        kafka_consumer.register_handler(
            KafkaTopics.CHAT_ASSIGNMENTS, 
            AssignmentEventType.CHAT_ASSIGNED.value, 
            self.event_handlers.handle_chat_assigned
        )
        kafka_consumer.register_handler(
            KafkaTopics.CHAT_ASSIGNMENTS, 
            AssignmentEventType.CHAT_TRANSFERRED.value, 
            self.event_handlers.handle_chat_transferred
        )
        kafka_consumer.register_handler(
            KafkaTopics.CHAT_ASSIGNMENTS, 
            AssignmentEventType.LAWYER_ASSIGNED.value, 
            self.event_handlers.handle_lawyer_assigned
        )
        
        # Обработчики административных действий
        kafka_consumer.register_handler(
            KafkaTopics.ADMIN_ACTIONS, 
            AdminActionType.FORCE_TRANSFER.value, 
            self.event_handlers.handle_force_transfer
        )
        
        logger.info("Все обработчики событий зарегистрированы")
    
    async def shutdown(self):
        """Корректное завершение работы системы"""
        if not self.started:
            return
        
        logger.info("Начало завершения работы системы чата...")
        
        try:
            # Останавливаем компоненты в обратном порядке
            await kafka_consumer.stop()
            logger.info("Kafka Consumer остановлен")
            
            await queue_manager.stop()
            logger.info("Менеджер очереди остановлен")
            
            await kafka_producer.stop()
            logger.info("Kafka Producer остановлен")
            
            self.started = False
            logger.info("Система чата поддержки завершена")
            
        except Exception as e:
            logger.error(f"Ошибка при завершении работы системы чата: {e}")
    
    def is_running(self) -> bool:
        """Проверка, запущена ли система"""
        return self.started
    
    def get_system_status(self) -> dict:
        """Получение статуса всей системы"""
        if not self.started:
            return {"status": "stopped"}
        
        return {
            "status": "running",
            "queue_manager": {
                "running": queue_manager._running,
                "operators_count": len(queue_manager.operators),
                "waiting_clients": len(queue_manager.waiting_clients),
                "active_chats": len(queue_manager.chat_assignments)
            },
            "kafka": {
                "producer_started": kafka_producer._started,
                "consumer_started": kafka_consumer._started
            },
            "websockets": websocket_manager.get_connection_stats(),
            "assignments": self.assignment_manager.get_assignment_stats() if self.assignment_manager else {}
        }


# Глобальный экземпляр системы чата
chat_system = SupportChatSystem()


# Функции для интеграции с FastAPI

async def startup_chat_system():
    """Функция для запуска системы чата при старте приложения"""
    await chat_system.initialize()


async def shutdown_chat_system():
    """Функция для остановки системы чата при завершении приложения"""
    await chat_system.shutdown()


def get_chat_system() -> SupportChatSystem:
    """Получение экземпляра системы чата"""
    return chat_system


def get_assignment_manager():
    """Получение менеджера назначений"""
    if not chat_system.started or not chat_system.assignment_manager:
        raise RuntimeError("Система чата не инициализирована")
    return chat_system.assignment_manager


def get_queue_manager():
    """Получение менеджера очереди"""
    return queue_manager


def get_websocket_manager():
    """Получение менеджера WebSocket соединений"""
    return websocket_manager
