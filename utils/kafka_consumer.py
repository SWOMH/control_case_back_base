"""
Kafka Consumer для обработки событий чата поддержки
"""
import json
import asyncio
from typing import Dict, Callable, Any, Set
from aiokafka import AIOKafkaConsumer
import logging

from config.kafka_config import (
    KAFKA_CONFIG, KafkaTopics,
    ChatEventType, SupportQueueEventType, OperatorEventType,
    AssignmentEventType, AdminActionType
)

logger = logging.getLogger(__name__)


class SupportChatKafkaConsumer:
    """Kafka Consumer для чата поддержки"""
    
    def __init__(self):
        self.consumers: Dict[str, AIOKafkaConsumer] = {}
        self.handlers: Dict[str, Dict[str, Callable]] = {}
        self.running_tasks: Set[asyncio.Task] = set()
        self._started = False
    
    def register_handler(self, topic: str, event_type: str, handler: Callable):
        """Регистрация обработчика для конкретного типа события в топике"""
        if topic not in self.handlers:
            self.handlers[topic] = {}
        self.handlers[topic][event_type] = handler
        logger.info(f"Зарегистрирован обработчик для {topic}:{event_type}")
    
    async def start(self):
        """Запуск всех consumer'ов"""
        if self._started:
            return
        
        # Создаем consumer'ы для всех топиков
        topics_to_consume = [
            KafkaTopics.CHAT_EVENTS,
            KafkaTopics.SUPPORT_QUEUE,
            KafkaTopics.OPERATOR_EVENTS,
            KafkaTopics.CHAT_ASSIGNMENTS,
            KafkaTopics.ADMIN_ACTIONS
        ]
        
        for topic in topics_to_consume:
            consumer = AIOKafkaConsumer(
                topic,
                bootstrap_servers=KAFKA_CONFIG['bootstrap_servers'],
                group_id=f"{KAFKA_CONFIG['group_id']}_{topic}",
                auto_offset_reset=KAFKA_CONFIG['auto_offset_reset'],
                enable_auto_commit=KAFKA_CONFIG['enable_auto_commit'],
                value_deserializer=lambda m: json.loads(m.decode('utf-8'))
            )
            
            await consumer.start()
            self.consumers[topic] = consumer
            
            # Запускаем задачу обработки сообщений для каждого топика
            task = asyncio.create_task(self._consume_messages(topic, consumer))
            self.running_tasks.add(task)
        
        self._started = True
        logger.info("Kafka Consumer запущен для всех топиков")
    
    async def stop(self):
        """Остановка всех consumer'ов"""
        if not self._started:
            return
        
        # Отменяем все задачи
        for task in self.running_tasks:
            task.cancel()
        
        # Ждем завершения задач
        if self.running_tasks:
            await asyncio.gather(*self.running_tasks, return_exceptions=True)
        
        # Останавливаем consumer'ы
        for consumer in self.consumers.values():
            await consumer.stop()
        
        self.consumers.clear()
        self.running_tasks.clear()
        self._started = False
        logger.info("Kafka Consumer остановлен")
    
    async def _consume_messages(self, topic: str, consumer: AIOKafkaConsumer):
        """Обработка сообщений из топика"""
        try:
            async for message in consumer:
                try:
                    event_data = message.value
                    event_type = event_data.get('event_type')
                    
                    if topic in self.handlers and event_type in self.handlers[topic]:
                        handler = self.handlers[topic][event_type]
                        await handler(event_data)
                    else:
                        logger.warning(f"Нет обработчика для {topic}:{event_type}")
                
                except Exception as e:
                    logger.error(f"Ошибка обработки сообщения из {topic}: {e}")
                    continue
                    
        except asyncio.CancelledError:
            logger.info(f"Обработка сообщений для топика {topic} отменена")
        except Exception as e:
            logger.error(f"Критическая ошибка в обработке топика {topic}: {e}")


class SupportChatEventHandlers:
    """Обработчики событий чата поддержки"""
    
    def __init__(self, websocket_manager, queue_manager, assignment_manager):
        self.websocket_manager = websocket_manager
        self.queue_manager = queue_manager
        self.assignment_manager = assignment_manager
    
    # Обработчики событий чата
    
    async def handle_chat_created(self, event_data: Dict[str, Any]):
        """Обработка создания чата"""
        chat_id = event_data['chat_id']
        user_id = event_data['user_id']
        
        logger.info(f"Обработка создания чата {chat_id} для пользователя {user_id}")
        
        # Добавляем клиента в очередь ожидания операторов
        await self.queue_manager.add_client_to_queue(user_id, chat_id)
        
        # Уведомляем всех доступных операторов о новом чате
        await self.websocket_manager.notify_operators_new_chat(chat_id, user_id)
    
    async def handle_message_sent(self, event_data: Dict[str, Any]):
        """Обработка отправки сообщения"""
        chat_id = event_data['chat_id']
        sender_id = event_data['sender_id']
        message_text = event_data.get('message_text')
        
        # Рассылаем сообщение всем участникам чата
        await self.websocket_manager.broadcast_to_chat(chat_id, {
            'type': 'message',
            'payload': {
                'chat_id': chat_id,
                'sender_id': sender_id,
                'message': message_text,
                'timestamp': event_data['timestamp']
            }
        })
    
    async def handle_operator_joined(self, event_data: Dict[str, Any]):
        """Обработка входа оператора в чат"""
        chat_id = event_data['chat_id']
        operator_id = event_data['user_id']
        operator_type = event_data['metadata']['operator_type']
        
        logger.info(f"Оператор {operator_id} ({operator_type}) вошел в чат {chat_id}")
        
        # Уведомляем участников чата о входе оператора
        await self.websocket_manager.broadcast_to_chat(chat_id, {
            'type': 'operator_joined',
            'payload': {
                'chat_id': chat_id,
                'operator_id': operator_id,
                'operator_type': operator_type
            }
        })
    
    async def handle_chat_closed(self, event_data: Dict[str, Any]):
        """Обработка закрытия чата"""
        chat_id = event_data['chat_id']
        closed_by = event_data['user_id']
        reason = event_data.get('metadata', {}).get('reason')
        
        logger.info(f"Чат {chat_id} закрыт пользователем {closed_by}, причина: {reason}")
        
        # Уведомляем всех участников о закрытии чата
        await self.websocket_manager.broadcast_to_chat(chat_id, {
            'type': 'chat_closed',
            'payload': {
                'chat_id': chat_id,
                'closed_by': closed_by,
                'reason': reason
            }
        })
        
        # Освобождаем оператора
        await self.assignment_manager.release_operator_from_chat(chat_id)
    
    # Обработчики событий очереди поддержки
    
    async def handle_client_waiting(self, event_data: Dict[str, Any]):
        """Обработка ожидания клиента в очереди"""
        client_id = event_data['client_id']
        priority = event_data['priority']
        
        logger.info(f"Клиент {client_id} ожидает в очереди с приоритетом {priority}")
        
        # Обновляем очередь и уведомляем операторов
        queue_position = await self.queue_manager.update_queue_position(client_id, priority)
        await self.websocket_manager.notify_operators_queue_update(client_id, queue_position)
    
    async def handle_client_request_removed(self, event_data: Dict[str, Any]):
        """Обработка удаления запроса клиента из очереди"""
        client_id = event_data['client_id']
        operator_id = event_data['metadata']['operator_id']
        chat_id = event_data['chat_id']
        
        logger.info(f"Запрос клиента {client_id} удален из очереди - принят оператором {operator_id}")
        
        # Удаляем клиента из очереди
        await self.queue_manager.remove_client_from_queue(client_id)
        
        # Уведомляем других операторов что клиент больше не доступен
        await self.websocket_manager.hide_client_from_operators(client_id, except_operator=operator_id)
    
    # Обработчики событий операторов
    
    async def handle_operator_online(self, event_data: Dict[str, Any]):
        """Обработка выхода оператора в онлайн"""
        operator_id = event_data['operator_id']
        operator_type = event_data['operator_type']
        max_chats = event_data['max_concurrent_chats']
        
        logger.info(f"Оператор {operator_id} ({operator_type}) вышел в онлайн, макс. чатов: {max_chats}")
        
        await self.assignment_manager.set_operator_online(operator_id, operator_type, max_chats)
    
    async def handle_operator_offline(self, event_data: Dict[str, Any]):
        """Обработка выхода оператора из онлайн"""
        operator_id = event_data['operator_id']
        
        logger.info(f"Оператор {operator_id} вышел из онлайн")
        
        await self.assignment_manager.set_operator_offline(operator_id)
    
    async def handle_operator_accept_chat(self, event_data: Dict[str, Any]):
        """Обработка принятия чата оператором"""
        operator_id = event_data['operator_id']
        chat_id = event_data['chat_id']
        client_id = event_data['metadata']['client_id']
        
        logger.info(f"Оператор {operator_id} принял чат {chat_id} с клиентом {client_id}")
        
        # Назначаем чат оператору
        await self.assignment_manager.assign_chat_to_operator(chat_id, operator_id, client_id)
    
    # Обработчики событий назначений
    
    async def handle_chat_assigned(self, event_data: Dict[str, Any]):
        """Обработка назначения чата"""
        chat_id = event_data['chat_id']
        operator_id = event_data['operator_id']
        client_id = event_data['user_id']
        
        logger.info(f"Чат {chat_id} назначен оператору {operator_id}")
        
        # Уведомляем оператора и клиента о назначении
        await self.websocket_manager.notify_chat_assigned(chat_id, operator_id, client_id)
    
    async def handle_chat_transferred(self, event_data: Dict[str, Any]):
        """Обработка перевода чата"""
        chat_id = event_data['chat_id']
        new_operator_id = event_data['operator_id']
        previous_operator_id = event_data['previous_operator_id']
        reason = event_data.get('assignment_reason')
        
        logger.info(f"Чат {chat_id} переведен с оператора {previous_operator_id} на {new_operator_id}")
        
        # Уведомляем всех участников о переводе
        await self.websocket_manager.notify_chat_transferred(
            chat_id, new_operator_id, previous_operator_id, reason
        )
    
    async def handle_lawyer_assigned(self, event_data: Dict[str, Any]):
        """Обработка назначения персонального юриста"""
        client_id = event_data['user_id']
        lawyer_id = event_data['operator_id']
        chat_id = event_data['chat_id']
        
        logger.info(f"Клиенту {client_id} назначен персональный юрист {lawyer_id}")
        
        # Создаем отдельный чат с юристом если нужно
        await self.assignment_manager.create_lawyer_chat(client_id, lawyer_id)
        
        # Уведомляем клиента и юриста
        await self.websocket_manager.notify_lawyer_assigned(client_id, lawyer_id, chat_id)
    
    # Обработчики административных действий
    
    async def handle_force_transfer(self, event_data: Dict[str, Any]):
        """Обработка принудительного перевода чата"""
        admin_id = event_data['admin_id']
        chat_id = event_data['chat_id']
        target_operator_id = event_data['target_operator_id']
        source_operator_id = event_data['source_operator_id']
        reason = event_data['reason']
        
        logger.info(f"Админ {admin_id} принудительно перевел чат {chat_id} с {source_operator_id} на {target_operator_id}")
        
        # Выполняем принудительный перевод
        await self.assignment_manager.force_transfer_chat(
            chat_id, target_operator_id, source_operator_id, admin_id, reason
        )


# Mock класс для работы без Kafka
class MockSupportChatKafkaConsumer:
    """Mock Kafka Consumer для режима без Kafka"""
    
    def __init__(self):
        self.handlers = {}
        self._started = False
    
    def register_handler(self, topic: str, event_type: str, handler):
        """Mock регистрация обработчика"""
        if topic not in self.handlers:
            self.handlers[topic] = {}
        self.handlers[topic][event_type] = handler
        logger.debug(f"Mock: Зарегистрирован обработчик для {topic}:{event_type}")
    
    async def start(self):
        """Mock запуск consumer"""
        self._started = True
        logger.info("Mock Kafka Consumer запущен")
    
    async def stop(self):
        """Mock остановка consumer"""
        self._started = False
        logger.info("Mock Kafka Consumer остановлен")


# Выбор реализации в зависимости от конфигурации
from config.kafka_config import KAFKA_ENABLED

if KAFKA_ENABLED:
    kafka_consumer = SupportChatKafkaConsumer()
else:
    kafka_consumer = MockSupportChatKafkaConsumer()
    logger.info("Используется Mock Kafka Consumer (Kafka отключен)")
