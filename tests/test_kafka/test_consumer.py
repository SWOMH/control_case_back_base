"""
Тесты для Kafka Consumer (включая Mock версию)
"""
import pytest
import pytest_asyncio
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock

from utils.kafka_consumer import SupportChatKafkaConsumer, MockSupportChatKafkaConsumer, SupportChatEventHandlers
from config.kafka_config import KafkaTopics, ChatEventType, SupportQueueEventType, OperatorEventType


class TestMockSupportChatKafkaConsumer:
    """Тесты для Mock Kafka Consumer"""
    
    @pytest_asyncio.fixture
    async def mock_consumer(self):
        """Создает Mock Consumer для тестов"""
        consumer = MockSupportChatKafkaConsumer()
        await consumer.start()
        yield consumer
        await consumer.stop()
    
    async def test_mock_consumer_initialization(self):
        """Тест инициализации Mock Consumer"""
        consumer = MockSupportChatKafkaConsumer()
        assert consumer.handlers == {}
        assert not consumer._started
    
    async def test_mock_consumer_start_stop(self):
        """Тест запуска и остановки Mock Consumer"""
        consumer = MockSupportChatKafkaConsumer()
        
        # Запуск
        await consumer.start()
        assert consumer._started
        
        # Остановка
        await consumer.stop()
        assert not consumer._started
    
    async def test_register_handler(self, mock_consumer):
        """Тест регистрации обработчиков"""
        topic = "test_topic"
        event_type = "test_event"
        handler = AsyncMock()
        
        mock_consumer.register_handler(topic, event_type, handler)
        
        assert topic in mock_consumer.handlers
        assert event_type in mock_consumer.handlers[topic]
        assert mock_consumer.handlers[topic][event_type] == handler
    
    async def test_multiple_handlers_same_topic(self, mock_consumer):
        """Тест регистрации нескольких обработчиков для одного топика"""
        topic = "test_topic"
        handler1 = AsyncMock()
        handler2 = AsyncMock()
        
        mock_consumer.register_handler(topic, "event1", handler1)
        mock_consumer.register_handler(topic, "event2", handler2)
        
        assert len(mock_consumer.handlers[topic]) == 2
        assert mock_consumer.handlers[topic]["event1"] == handler1
        assert mock_consumer.handlers[topic]["event2"] == handler2


class TestSupportChatKafkaConsumer:
    """Тесты для реального Kafka Consumer"""
    
    @pytest_asyncio.fixture
    async def real_consumer(self):
        """Создает реальный Consumer для тестов"""
        with patch('aiokafka.AIOKafkaConsumer') as mock_kafka_consumer:
            # Мокаем несколько экземпляров AIOKafkaConsumer для разных топиков
            consumer_instances = {}
            
            def create_consumer_mock(*args, **kwargs):
                topic = args[0] if args else "unknown"
                instance = AsyncMock()
                consumer_instances[topic] = instance
                return instance
            
            mock_kafka_consumer.side_effect = create_consumer_mock
            
            consumer = SupportChatKafkaConsumer()
            await consumer.start()
            yield consumer, consumer_instances
            await consumer.stop()
    
    async def test_real_consumer_initialization(self):
        """Тест инициализации реального Consumer"""
        consumer = SupportChatKafkaConsumer()
        assert consumer.consumers == {}
        assert consumer.handlers == {}
        assert consumer.running_tasks == set()
        assert not consumer._started
    
    async def test_real_consumer_start_creates_consumers(self, real_consumer):
        """Тест создания consumer'ов для всех топиков при запуске"""
        consumer, consumer_instances = real_consumer
        
        # Проверяем что Consumer запущен
        assert consumer._started
        
        # Проверяем что созданы consumer'ы для всех топиков
        expected_topics = [
            KafkaTopics.CHAT_EVENTS,
            KafkaTopics.SUPPORT_QUEUE,
            KafkaTopics.OPERATOR_EVENTS,
            KafkaTopics.CHAT_ASSIGNMENTS,
            KafkaTopics.ADMIN_ACTIONS
        ]
        
        for topic in expected_topics:
            assert topic in consumer.consumers
            assert topic in consumer_instances
            # Проверяем что start был вызван для каждого consumer'а
            consumer_instances[topic].start.assert_called_once()
    
    async def test_register_handler_real(self, real_consumer):
        """Тест регистрации обработчиков в реальном Consumer"""
        consumer, _ = real_consumer
        
        topic = KafkaTopics.CHAT_EVENTS
        event_type = ChatEventType.CHAT_CREATED.value
        handler = AsyncMock()
        
        consumer.register_handler(topic, event_type, handler)
        
        assert topic in consumer.handlers
        assert event_type in consumer.handlers[topic]
        assert consumer.handlers[topic][event_type] == handler
    
    async def test_message_processing(self):
        """Тест обработки сообщений"""
        with patch('aiokafka.AIOKafkaConsumer') as mock_kafka_consumer:
            # Создаем мок для обработки сообщений
            consumer_instance = AsyncMock()
            messages = [
                MagicMock(value={
                    "event_type": "chat_created",
                    "chat_id": 123,
                    "user_id": 456
                }),
                MagicMock(value={
                    "event_type": "message_sent",
                    "chat_id": 123,
                    "sender_id": 456,
                    "message": "Test message"
                })
            ]
            
            # Настраиваем async итератор для сообщений
            async def async_messages():
                for msg in messages:
                    yield msg
            
            consumer_instance.__aiter__ = lambda self: async_messages()
            mock_kafka_consumer.return_value = consumer_instance
            
            consumer = SupportChatKafkaConsumer()
            
            # Регистрируем обработчики
            chat_handler = AsyncMock()
            message_handler = AsyncMock()
            
            consumer.register_handler(KafkaTopics.CHAT_EVENTS, "chat_created", chat_handler)
            consumer.register_handler(KafkaTopics.CHAT_EVENTS, "message_sent", message_handler)
            
            # Запускаем consumer (это создаст задачи обработки)
            await consumer.start()
            
            # Даем время для обработки сообщений
            await asyncio.sleep(0.1)
            
            # Останавливаем consumer
            await consumer.stop()
            
            # Проверяем что обработчики были вызваны
            chat_handler.assert_called_once_with({
                "event_type": "chat_created",
                "chat_id": 123,
                "user_id": 456
            })
            message_handler.assert_called_once_with({
                "event_type": "message_sent",
                "chat_id": 123,
                "sender_id": 456,
                "message": "Test message"
            })
    
    async def test_message_processing_error_handling(self):
        """Тест обработки ошибок при обработке сообщений"""
        with patch('aiokafka.AIOKafkaConsumer') as mock_kafka_consumer:
            consumer_instance = AsyncMock()
            
            # Сообщение которое вызовет ошибку в обработчике
            messages = [
                MagicMock(value={
                    "event_type": "chat_created",
                    "chat_id": 123
                })
            ]
            
            async def async_messages():
                for msg in messages:
                    yield msg
            
            consumer_instance.__aiter__ = lambda self: async_messages()
            mock_kafka_consumer.return_value = consumer_instance
            
            consumer = SupportChatKafkaConsumer()
            
            # Регистрируем обработчик который вызывает ошибку
            error_handler = AsyncMock(side_effect=Exception("Handler error"))
            consumer.register_handler(KafkaTopics.CHAT_EVENTS, "chat_created", error_handler)
            
            await consumer.start()
            await asyncio.sleep(0.1)
            await consumer.stop()
            
            # Проверяем что обработчик был вызван (но ошибка была обработана)
            error_handler.assert_called_once()
    
    async def test_unknown_event_type_handling(self):
        """Тест обработки неизвестного типа события"""
        with patch('aiokafka.AIOKafkaConsumer') as mock_kafka_consumer:
            consumer_instance = AsyncMock()
            
            # Сообщение с неизвестным типом события
            messages = [
                MagicMock(value={
                    "event_type": "unknown_event",
                    "data": "test"
                })
            ]
            
            async def async_messages():
                for msg in messages:
                    yield msg
            
            consumer_instance.__aiter__ = lambda self: async_messages()
            mock_kafka_consumer.return_value = consumer_instance
            
            consumer = SupportChatKafkaConsumer()
            await consumer.start()
            await asyncio.sleep(0.1)
            await consumer.stop()
            
            # Должно пройти без ошибок (просто логируется предупреждение)


class TestSupportChatEventHandlers:
    """Тесты для обработчиков событий чата"""
    
    @pytest_asyncio.fixture
    async def event_handlers(self, websocket_manager, queue_manager, assignment_manager):
        """Создает обработчики событий для тестов"""
        return SupportChatEventHandlers(
            websocket_manager, queue_manager, assignment_manager
        )
    
    async def test_handle_chat_created(self, event_handlers, queue_manager, websocket_manager):
        """Тест обработки события создания чата"""
        event_data = {
            "chat_id": 123,
            "user_id": 456,
            "timestamp": "2023-01-01T12:00:00Z"
        }
        
        # Мокаем методы
        queue_manager.add_client_to_queue = AsyncMock()
        websocket_manager.notify_operators_new_chat = AsyncMock()
        
        await event_handlers.handle_chat_created(event_data)
        
        # Проверяем что клиент добавлен в очередь
        queue_manager.add_client_to_queue.assert_called_once_with(456, 123)
        
        # Проверяем что операторы уведомлены
        websocket_manager.notify_operators_new_chat.assert_called_once_with(123, 456)
    
    async def test_handle_message_sent(self, event_handlers, websocket_manager):
        """Тест обработки события отправки сообщения"""
        event_data = {
            "chat_id": 123,
            "sender_id": 456,
            "message_text": "Тестовое сообщение",
            "timestamp": "2023-01-01T12:00:00Z"
        }
        
        websocket_manager.broadcast_to_chat = AsyncMock()
        
        await event_handlers.handle_message_sent(event_data)
        
        # Проверяем что сообщение разослано участникам чата
        websocket_manager.broadcast_to_chat.assert_called_once()
        call_args = websocket_manager.broadcast_to_chat.call_args
        
        assert call_args[0][0] == 123  # chat_id
        message_payload = call_args[0][1]
        assert message_payload['type'] == 'message'
        assert message_payload['payload']['chat_id'] == 123
        assert message_payload['payload']['sender_id'] == 456
        assert message_payload['payload']['message'] == "Тестовое сообщение"
    
    async def test_handle_operator_joined(self, event_handlers, websocket_manager):
        """Тест обработки события входа оператора в чат"""
        event_data = {
            "chat_id": 123,
            "user_id": 456,
            "metadata": {"operator_type": "support"}
        }
        
        websocket_manager.broadcast_to_chat = AsyncMock()
        
        await event_handlers.handle_operator_joined(event_data)
        
        websocket_manager.broadcast_to_chat.assert_called_once()
        call_args = websocket_manager.broadcast_to_chat.call_args
        
        assert call_args[0][0] == 123  # chat_id
        message_payload = call_args[0][1]
        assert message_payload['type'] == 'operator_joined'
        assert message_payload['payload']['operator_id'] == 456
        assert message_payload['payload']['operator_type'] == "support"
    
    async def test_handle_chat_closed(self, event_handlers, websocket_manager, assignment_manager):
        """Тест обработки события закрытия чата"""
        event_data = {
            "chat_id": 123,
            "user_id": 456,
            "metadata": {"reason": "resolved"}
        }
        
        websocket_manager.broadcast_to_chat = AsyncMock()
        assignment_manager.release_operator_from_chat = AsyncMock()
        
        await event_handlers.handle_chat_closed(event_data)
        
        # Проверяем уведомление участников
        websocket_manager.broadcast_to_chat.assert_called_once()
        call_args = websocket_manager.broadcast_to_chat.call_args
        
        assert call_args[0][0] == 123  # chat_id
        message_payload = call_args[0][1]
        assert message_payload['type'] == 'chat_closed'
        assert message_payload['payload']['closed_by'] == 456
        assert message_payload['payload']['reason'] == "resolved"
        
        # Проверяем освобождение оператора
        assignment_manager.release_operator_from_chat.assert_called_once_with(123)
    
    async def test_handle_client_waiting(self, event_handlers, queue_manager, websocket_manager):
        """Тест обработки события ожидания клиента"""
        event_data = {
            "client_id": 123,
            "priority": 1
        }
        
        queue_manager.update_queue_position = AsyncMock(return_value=5)
        websocket_manager.notify_operators_queue_update = AsyncMock()
        
        await event_handlers.handle_client_waiting(event_data)
        
        queue_manager.update_queue_position.assert_called_once_with(123, 1)
        websocket_manager.notify_operators_queue_update.assert_called_once_with(123, 5)
    
    async def test_handle_client_request_removed(self, event_handlers, queue_manager, websocket_manager):
        """Тест обработки события удаления запроса клиента из очереди"""
        event_data = {
            "client_id": 123,
            "chat_id": 456,
            "metadata": {"operator_id": 789}
        }
        
        queue_manager.remove_client_from_queue = AsyncMock()
        websocket_manager.hide_client_from_operators = AsyncMock()
        
        await event_handlers.handle_client_request_removed(event_data)
        
        queue_manager.remove_client_from_queue.assert_called_once_with(123)
        websocket_manager.hide_client_from_operators.assert_called_once_with(123, except_operator=789)
    
    async def test_handle_operator_online(self, event_handlers, assignment_manager):
        """Тест обработки события выхода оператора в онлайн"""
        event_data = {
            "operator_id": 123,
            "operator_type": "support",
            "max_concurrent_chats": 5
        }
        
        assignment_manager.set_operator_online = AsyncMock()
        
        await event_handlers.handle_operator_online(event_data)
        
        assignment_manager.set_operator_online.assert_called_once_with(123, "support", 5)
    
    async def test_handle_operator_accept_chat(self, event_handlers, assignment_manager):
        """Тест обработки события принятия чата оператором"""
        event_data = {
            "operator_id": 123,
            "chat_id": 456,
            "metadata": {"client_id": 789}
        }
        
        assignment_manager.assign_chat_to_operator = AsyncMock()
        
        await event_handlers.handle_operator_accept_chat(event_data)
        
        assignment_manager.assign_chat_to_operator.assert_called_once_with(456, 123, 789)
    
    async def test_handle_chat_assigned(self, event_handlers, websocket_manager):
        """Тест обработки события назначения чата"""
        event_data = {
            "chat_id": 123,
            "operator_id": 456,
            "user_id": 789
        }
        
        websocket_manager.notify_chat_assigned = AsyncMock()
        
        await event_handlers.handle_chat_assigned(event_data)
        
        websocket_manager.notify_chat_assigned.assert_called_once_with(123, 456, 789)
    
    async def test_handle_chat_transferred(self, event_handlers, websocket_manager):
        """Тест обработки события перевода чата"""
        event_data = {
            "chat_id": 123,
            "operator_id": 456,
            "previous_operator_id": 789,
            "assignment_reason": "test transfer"
        }
        
        websocket_manager.notify_chat_transferred = AsyncMock()
        
        await event_handlers.handle_chat_transferred(event_data)
        
        websocket_manager.notify_chat_transferred.assert_called_once_with(
            123, 456, 789, "test transfer"
        )
    
    async def test_handle_lawyer_assigned(self, event_handlers, assignment_manager, websocket_manager):
        """Тест обработки события назначения юриста"""
        event_data = {
            "user_id": 123,
            "operator_id": 456,
            "chat_id": 789
        }
        
        assignment_manager.create_lawyer_chat = AsyncMock()
        websocket_manager.notify_lawyer_assigned = AsyncMock()
        
        await event_handlers.handle_lawyer_assigned(event_data)
        
        assignment_manager.create_lawyer_chat.assert_called_once_with(123, 456)
        websocket_manager.notify_lawyer_assigned.assert_called_once_with(123, 456, 789)
    
    async def test_handle_force_transfer(self, event_handlers, assignment_manager):
        """Тест обработки события принудительного перевода"""
        event_data = {
            "admin_id": 1,
            "chat_id": 123,
            "target_operator_id": 456,
            "source_operator_id": 789,
            "reason": "admin action"
        }
        
        assignment_manager.force_transfer_chat = AsyncMock()
        
        await event_handlers.handle_force_transfer(event_data)
        
        assignment_manager.force_transfer_chat.assert_called_once_with(
            123, 456, 789, 1, "admin action"
        )


class TestConsumerIntegration:
    """Интеграционные тесты Consumer"""
    
    async def test_consumer_selection_kafka_enabled(self):
        """Тест выбора Consumer при включенном Kafka"""
        with patch('config.kafka_config.KAFKA_ENABLED', True):
            import importlib
            import utils.kafka_consumer
            importlib.reload(utils.kafka_consumer)
            
            from utils.kafka_consumer import kafka_consumer
            assert isinstance(kafka_consumer, SupportChatKafkaConsumer)
    
    async def test_consumer_selection_kafka_disabled(self):
        """Тест выбора Consumer при отключенном Kafka"""
        with patch('config.kafka_config.KAFKA_ENABLED', False):
            import importlib
            import utils.kafka_consumer
            importlib.reload(utils.kafka_consumer)
            
            from utils.kafka_consumer import kafka_consumer
            assert isinstance(kafka_consumer, MockSupportChatKafkaConsumer)
