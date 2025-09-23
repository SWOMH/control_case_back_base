"""
Тесты для Kafka Producer (включая Mock версию)
"""
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime

from utils.kafka_producer import SupportChatKafkaProducer, MockSupportChatKafkaProducer
from config.kafka_config import ChatEventType, SupportQueueEventType, OperatorEventType


class TestMockSupportChatKafkaProducer:
    """Тесты для Mock Kafka Producer"""
    
    @pytest_asyncio.fixture
    async def mock_producer(self):
        """Создает Mock Producer для тестов"""
        producer = MockSupportChatKafkaProducer()
        await producer.start()
        yield producer
        await producer.stop()
    
    async def test_mock_producer_initialization(self):
        """Тест инициализации Mock Producer"""
        producer = MockSupportChatKafkaProducer()
        assert not producer._started
    
    async def test_mock_producer_start_stop(self):
        """Тест запуска и остановки Mock Producer"""
        producer = MockSupportChatKafkaProducer()
        
        # Запуск
        await producer.start()
        assert producer._started
        
        # Остановка
        await producer.stop()
        assert not producer._started
    
    async def test_send_chat_created(self, mock_producer):
        """Тест отправки события создания чата"""
        chat_id = 123
        user_id = 456
        metadata = {"test": "data"}
        
        # Должно выполниться без ошибок
        await mock_producer.send_chat_created(chat_id, user_id, metadata)
    
    async def test_send_message_sent(self, mock_producer):
        """Тест отправки события сообщения"""
        chat_id = 123
        sender_id = 456
        sender_type = "client"
        message_id = 789
        message_text = "Тестовое сообщение"
        
        await mock_producer.send_message_sent(
            chat_id, sender_id, sender_type, message_id, message_text
        )
    
    async def test_send_operator_events(self, mock_producer):
        """Тест отправки событий оператора"""
        operator_id = 123
        operator_type = "support"
        
        # Оператор онлайн
        await mock_producer.send_operator_online(operator_id, operator_type, 5)
        
        # Оператор оффлайн
        await mock_producer.send_operator_offline(operator_id, operator_type)
        
        # Оператор принял чат
        chat_id = 456
        client_id = 789
        await mock_producer.send_operator_accept_chat(
            operator_id, operator_type, chat_id, client_id
        )
    
    async def test_send_assignment_events(self, mock_producer):
        """Тест отправки событий назначений"""
        chat_id = 123
        operator_id = 456
        operator_type = "support"
        client_id = 789
        
        # Назначение чата
        await mock_producer.send_chat_assigned(
            chat_id, operator_id, operator_type, client_id, "test_assignment"
        )
        
        # Перевод чата
        new_operator_id = 999
        await mock_producer.send_chat_transferred(
            chat_id, new_operator_id, operator_type, operator_id, client_id, "test_transfer"
        )
        
        # Назначение юриста
        lawyer_id = 111
        await mock_producer.send_lawyer_assigned(client_id, lawyer_id, chat_id)
    
    async def test_send_admin_actions(self, mock_producer):
        """Тест отправки административных действий"""
        admin_id = 1
        chat_id = 123
        target_operator_id = 456
        source_operator_id = 789
        reason = "Test force transfer"
        
        await mock_producer.send_force_transfer(
            admin_id, chat_id, target_operator_id, source_operator_id, reason
        )


class TestSupportChatKafkaProducer:
    """Тесты для реального Kafka Producer"""
    
    @pytest_asyncio.fixture
    async def real_producer(self):
        """Создает реальный Producer для тестов"""
        with patch('aiokafka.AIOKafkaProducer') as mock_kafka_producer:
            # Мокаем AIOKafkaProducer
            kafka_instance = AsyncMock()
            mock_kafka_producer.return_value = kafka_instance
            
            producer = SupportChatKafkaProducer()
            await producer.start()
            yield producer, kafka_instance
            await producer.stop()
    
    async def test_real_producer_initialization(self):
        """Тест инициализации реального Producer"""
        producer = SupportChatKafkaProducer()
        assert producer.producer is None
        assert not producer._started
    
    async def test_real_producer_start_stop(self, real_producer):
        """Тест запуска и остановки реального Producer"""
        producer, kafka_instance = real_producer
        
        # Проверяем что Producer запущен
        assert producer._started
        kafka_instance.start.assert_called_once()
    
    async def test_send_chat_created_real(self, real_producer):
        """Тест отправки события создания чата в реальном Producer"""
        producer, kafka_instance = real_producer
        
        chat_id = 123
        user_id = 456
        metadata = {"test": "data"}
        
        await producer.send_chat_created(chat_id, user_id, metadata)
        
        # Проверяем что send_and_wait был вызван
        kafka_instance.send_and_wait.assert_called_once()
        
        # Проверяем аргументы вызова
        call_args = kafka_instance.send_and_wait.call_args
        assert call_args[1]['topic'] == 'chat_events'
        assert call_args[1]['key'] == f'chat_{chat_id}'.encode('utf-8')
        
        # Проверяем данные события
        event_data = call_args[1]['value']
        assert event_data['event_type'] == ChatEventType.CHAT_CREATED.value
        assert event_data['chat_id'] == chat_id
        assert event_data['user_id'] == user_id
        assert event_data['metadata'] == metadata
    
    async def test_send_message_sent_real(self, real_producer):
        """Тест отправки события сообщения в реальном Producer"""
        producer, kafka_instance = real_producer
        
        chat_id = 123
        sender_id = 456
        sender_type = "client"
        message_id = 789
        message_text = "Тестовое сообщение"
        
        await producer.send_message_sent(
            chat_id, sender_id, sender_type, message_id, message_text
        )
        
        kafka_instance.send_and_wait.assert_called()
        call_args = kafka_instance.send_and_wait.call_args
        
        event_data = call_args[1]['value']
        assert event_data['event_type'] == ChatEventType.MESSAGE_SENT.value
        assert event_data['chat_id'] == chat_id
        assert event_data['sender_id'] == sender_id
        assert event_data['sender_type'] == sender_type
        assert event_data['message_id'] == message_id
        assert event_data['message_text'] == message_text
    
    async def test_send_operator_online_real(self, real_producer):
        """Тест отправки события оператора онлайн в реальном Producer"""
        producer, kafka_instance = real_producer
        
        operator_id = 123
        operator_type = "support"
        max_concurrent_chats = 5
        
        await producer.send_operator_online(operator_id, operator_type, max_concurrent_chats)
        
        kafka_instance.send_and_wait.assert_called()
        call_args = kafka_instance.send_and_wait.call_args
        
        assert call_args[1]['topic'] == 'operator_events'
        event_data = call_args[1]['value']
        assert event_data['event_type'] == OperatorEventType.OPERATOR_ONLINE.value
        assert event_data['operator_id'] == operator_id
        assert event_data['operator_type'] == operator_type
        assert event_data['max_concurrent_chats'] == max_concurrent_chats
    
    async def test_send_client_waiting_real(self, real_producer):
        """Тест отправки события ожидания клиента в реальном Producer"""
        producer, kafka_instance = real_producer
        
        client_id = 123
        priority = 1
        metadata = {"urgency": "high"}
        
        await producer.send_client_waiting(client_id, priority, metadata)
        
        kafka_instance.send_and_wait.assert_called()
        call_args = kafka_instance.send_and_wait.call_args
        
        assert call_args[1]['topic'] == 'support_queue'
        event_data = call_args[1]['value']
        assert event_data['event_type'] == SupportQueueEventType.CLIENT_WAITING.value
        assert event_data['client_id'] == client_id
        assert event_data['priority'] == priority
        assert event_data['metadata'] == metadata
    
    async def test_producer_error_handling(self):
        """Тест обработки ошибок Producer"""
        with patch('aiokafka.AIOKafkaProducer') as mock_kafka_producer:
            kafka_instance = AsyncMock()
            kafka_instance.send_and_wait.side_effect = Exception("Kafka error")
            mock_kafka_producer.return_value = kafka_instance
            
            producer = SupportChatKafkaProducer()
            await producer.start()
            
            # Должно вызвать исключение
            with pytest.raises(Exception, match="Kafka error"):
                await producer.send_chat_created(123, 456)
            
            await producer.stop()
    
    async def test_auto_start_on_send(self):
        """Тест автоматического запуска при отправке события"""
        with patch('aiokafka.AIOKafkaProducer') as mock_kafka_producer:
            kafka_instance = AsyncMock()
            mock_kafka_producer.return_value = kafka_instance
            
            producer = SupportChatKafkaProducer()
            assert not producer._started
            
            # Отправляем событие без явного запуска
            await producer.send_chat_created(123, 456)
            
            # Producer должен автоматически запуститься
            assert producer._started
            kafka_instance.start.assert_called_once()
            
            await producer.stop()


class TestProducerIntegration:
    """Интеграционные тесты Producer"""
    
    async def test_producer_selection_kafka_enabled(self):
        """Тест выбора Producer при включенном Kafka"""
        with patch('config.kafka_config.KAFKA_ENABLED', True):
            # Перезагружаем модуль для применения новой конфигурации
            import importlib
            import utils.kafka_producer
            importlib.reload(utils.kafka_producer)
            
            from utils.kafka_producer import kafka_producer
            assert isinstance(kafka_producer, SupportChatKafkaProducer)
    
    async def test_producer_selection_kafka_disabled(self):
        """Тест выбора Producer при отключенном Kafka"""
        with patch('config.kafka_config.KAFKA_ENABLED', False):
            # Перезагружаем модуль для применения новой конфигурации
            import importlib
            import utils.kafka_producer
            importlib.reload(utils.kafka_producer)
            
            from utils.kafka_producer import kafka_producer
            assert isinstance(kafka_producer, MockSupportChatKafkaProducer)
    
    # async def test_event_serialization(self, real_producer):
    #     """Тест сериализации событий"""
    #     producer, kafka_instance = real_producer
        
    #     # Отправляем событие с различными типами данных
    #     await producer.send_chat_created(
    #         chat_id=123,
    #         user_id=456,
    #         metadata={
    #             "string": "test",
    #             "number": 42,
    #             "boolean": True,
    #             "null": None,
    #             "list": [1, 2, 3],
    #             "dict": {"nested": "value"}
    #         }
    #     )
        
    #     # Проверяем что событие было сериализовано
    #     kafka_instance.send_and_wait.assert_called_once()
    #     call_args = kafka_instance.send_and_wait.call_args
    #     event_data = call_args[1]['value']
        
    #     # Проверяем что все типы данных корректно сериализованы
    #     assert isinstance(event_data, dict)
    #     assert event_data['metadata']['string'] == "test"
    #     assert event_data['metadata']['number'] == 42
    #     assert event_data['metadata']['boolean'] is True
    #     assert event_data['metadata']['null'] is None
    #     assert event_data['metadata']['list'] == [1, 2, 3]
    #     assert event_data['metadata']['dict'] == {"nested": "value"}
    
    # async def test_event_timestamp_format(self, real_producer):
    #     """Тест формата временных меток в событиях"""
    #     producer, kafka_instance = real_producer
        
    #     await producer.send_chat_created(123, 456)
        
    #     call_args = kafka_instance.send_and_wait.call_args
    #     event_data = call_args[1]['value']
        
    #     # Проверяем что timestamp есть и имеет правильный формат
    #     assert 'timestamp' in event_data
    #     timestamp_str = event_data['timestamp']
        
    #     # Проверяем что можно распарсить обратно в datetime
    #     from datetime import datetime
    #     parsed_time = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
    #     assert isinstance(parsed_time, datetime)
