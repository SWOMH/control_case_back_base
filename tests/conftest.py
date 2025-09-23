"""
Конфигурация тестов для системы чата поддержки
"""
import os
import asyncio
import pytest
import pytest_asyncio
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from httpx import AsyncClient
from faker import Faker

# Установка переменных окружения для тестов
os.environ['KAFKA_ENABLED'] = 'false'
os.environ['REDIS_URL'] = 'redis://localhost:6379/1'
os.environ['TESTING'] = 'true'

# Регистрация плагинов
pytest_plugins = ['pytest_asyncio']

TEST_USER_ID = 1
TEST_CLIENT_ID = 2
TEST_OPERATOR_ID = 3
TEST_LAWYER_ID = 4
TEST_ADMIN_ID = 5
TEST_CHAT_ID = 100
TEST_MESSAGE_ID = 200


# Импорты после установки переменных окружения
from database.models.users import Group, Users
from database.models.support import Chat, ChatMessage
from utils.queue_manager import SupportQueueManager
from utils.websocket_manager import WebSocketConnectionManager
from utils.kafka_producer import kafka_producer
from utils.kafka_consumer import kafka_consumer
from utils.assignment_manager import create_assignment_manager

fake = Faker('ru_RU')


@pytest.fixture(scope="session")
def event_loop():
    """Создает event loop для всей сессии тестов"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def mock_user():
    """Создает мок пользователя для тестов"""
    user = Users()
    user.id = fake.random_int(min=1, max=1000)
    user.login = fake.user_name()
    user.email = fake.email()
    user.password = fake.password()
    user.surname = fake.last_name()
    user.first_name = fake.first_name()
    user.patronymic = fake.middle_name() if fake.middle_name() else "Петрович"
    user.is_client = False
    user.is_active = True
    user.is_banned = False
    user.is_admin = False
    user.account_confirmed = True
    return user


@pytest_asyncio.fixture
async def mock_client_user():
    """Создает мок клиента для тестов"""
    user = await mock_user()
    user.is_client = True
    return user


@pytest_asyncio.fixture
async def mock_support_user():
    """Создает мок оператора поддержки для тестов"""    
    user = await mock_user()
    user.is_client = False
    user.groups = [Group(name="support")]     
    return user


@pytest_asyncio.fixture
async def mock_admin_user():
    """Создает мок администратора для тестов"""
    user = await mock_user()
    user.is_admin = True
    return user


@pytest_asyncio.fixture
async def mock_chat():
    """Создает мок чата для тестов"""
    chat = Chat()
    chat.id = fake.random_int(min=1, max=1000)
    chat.user_id = fake.random_int(min=1, max=1000)
    chat.user_support_id = None
    chat.active = True
    chat.resolved = False
    return chat


@pytest_asyncio.fixture
async def mock_message():
    """Создает мок сообщения для тестов"""
    message = ChatMessage()
    message.id = fake.random_int(min=1, max=1000)
    message.chat_id = fake.random_int(min=1, max=1000)
    message.sender_id = fake.random_int(min=1, max=1000)
    message.sender_type = "client"
    message.message = fake.text(max_nb_chars=200)
    return message


@pytest_asyncio.fixture
async def queue_manager():
    """Создает менеджер очереди для тестов"""
    manager = SupportQueueManager()
    await manager.start()
    yield manager
    await manager.stop()


@pytest_asyncio.fixture
async def websocket_manager():
    """Создает менеджер WebSocket для тестов"""
    return WebSocketConnectionManager()


@pytest_asyncio.fixture
async def assignment_manager(queue_manager, websocket_manager):
    """Создает менеджер назначений для тестов"""
    return create_assignment_manager(queue_manager, websocket_manager)


@pytest_asyncio.fixture
async def mock_websocket():
    """Создает мок WebSocket соединения"""
    websocket = AsyncMock()
    websocket.accept = AsyncMock()
    websocket.send_json = AsyncMock()
    websocket.receive_text = AsyncMock()
    websocket.close = AsyncMock()
    return websocket


@pytest_asyncio.fixture
async def mock_database_session():
    """Создает мок сессии базы данных"""
    session = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.execute = AsyncMock()
    session.close = AsyncMock()
    return session


@pytest_asyncio.fixture
async def mock_chat_db():
    """Создает мок базы данных чатов"""
    with patch('database.logic.chats.chat.chat_db') as mock_db:
        # Настраиваем базовые методы
        mock_db.get_active_chat_by_user = AsyncMock()
        mock_db.create_chat = AsyncMock()
        mock_db.add_message = AsyncMock()
        mock_db.close_chat = AsyncMock()
        mock_db.transfer_chat = AsyncMock()
        mock_db.get_chat_by_id = AsyncMock()
        mock_db.update_chat_operator = AsyncMock()
        mock_db.add_chat_participant = AsyncMock()
        mock_db.mark_chat_participant_left = AsyncMock()
        mock_db.mark_messages_read = AsyncMock()        
        yield mock_db


@pytest_asyncio.fixture
async def mock_auth():
    """Создает мок авторизации"""
    with patch('utils.auth.get_current_user') as mock_auth:
        yield mock_auth


@pytest.fixture
def mock_redis():
    """Создает мок Redis"""
    with patch('config.redis.redis_db') as mock_redis:
        mock_redis.set = MagicMock()
        mock_redis.get = MagicMock()
        mock_redis.delete = MagicMock()
        yield mock_redis


@pytest_asyncio.fixture
async def test_app():
    """Создает тестовое приложение FastAPI"""
    from fastapi import FastAPI
    from endpoints.chats.chat_kafka import router as chat_router
    from endpoints.chats.admin_chat import router as admin_router
    
    app = FastAPI()
    app.include_router(chat_router, prefix="/api/v1")
    app.include_router(admin_router, prefix="/api/v1")
    
    return app


@pytest_asyncio.fixture
async def async_client(test_app):
    """Создает асинхронный HTTP клиент для тестов"""
    async with AsyncClient(app=test_app, base_url="http://test") as client:
        yield client


@pytest.fixture
def auth_headers():
    """Создает заголовки авторизации для тестов"""
    return {"Authorization": "Bearer test_token"}


@pytest.fixture
def sample_chat_event():
    """Создает пример события чата"""
    return {
        "event_id": "test-event-123",
        "event_type": "chat_created",
        "timestamp": "2023-01-01T12:00:00Z",
        "chat_id": TEST_CHAT_ID,
        "user_id": TEST_CLIENT_ID,
        "metadata": {}
    }


@pytest.fixture
def sample_message_data():
    """Создает пример данных сообщения"""
    return {
        "type": "message",
        "payload": {
            "text": "Тестовое сообщение"
        }
    }


@pytest.fixture
def sample_operator_data():
    """Создает пример данных оператора"""
    return {
        "operator_id": TEST_OPERATOR_ID,
        "operator_type": "support",
        "is_online": True,
        "max_concurrent_chats": 5
    }


# Вспомогательные функции для тестов

def create_mock_token_data(user_id: int, email: str = None):
    """Создает мок данных токена"""
    from schemas.user_schema import TokenData
    return TokenData(
        user_id=user_id,
        email=email or f"user{user_id}@test.com"
    )


def create_test_event(event_type: str, **kwargs):
    """Создает тестовое событие Kafka"""
    return {
        "event_id": f"test-{fake.uuid4()}",
        "event_type": event_type,
        "timestamp": fake.date_time().isoformat(),
        **kwargs
    }


async def wait_for_condition(condition, timeout=1.0, interval=0.1):
    """Ждет выполнения условия с таймаутом"""
    elapsed = 0
    while elapsed < timeout:
        if await condition() if asyncio.iscoroutinefunction(condition) else condition():
            return True
        await asyncio.sleep(interval)
        elapsed += interval
    return False


class MockWebSocket:
    """Более продвинутый мок WebSocket для сложных тестов"""
    
    def __init__(self):
        self.accepted = False
        self.closed = False
        self.sent_messages = []
        self.received_messages = []
        self.current_message_index = 0
    
    async def accept(self):
        self.accepted = True
    
    async def send_json(self, data):
        self.sent_messages.append(data)
    
    async def receive_text(self):
        if self.current_message_index < len(self.received_messages):
            message = self.received_messages[self.current_message_index]
            self.current_message_index += 1
            return message
        raise Exception("No more messages")
    
    async def close(self, code=None):
        self.closed = True
    
    def add_received_message(self, message):
        """Добавляет сообщение для получения"""
        self.received_messages.append(message)
    
    def get_sent_messages(self):
        """Возвращает отправленные сообщения"""
        return self.sent_messages.copy()
    
    def clear_messages(self):
        """Очищает все сообщения"""
        self.sent_messages.clear()
        self.received_messages.clear()
        self.current_message_index = 0


@pytest.fixture
def advanced_mock_websocket():
    """Продвинутый мок WebSocket"""
    return MockWebSocket()


# Настройки pytest
pytestmark = pytest.mark.asyncio
