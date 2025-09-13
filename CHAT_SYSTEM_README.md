# Система чата поддержки с Kafka

Комплексная система чата поддержки с использованием Kafka для масштабируемости и надежности.

## Архитектура системы

### Основные компоненты:

1. **Kafka Producer/Consumer** - для обмена событиями между сервисами
2. **Queue Manager** - управление очередью клиентов и статусами операторов
3. **Assignment Manager** - назначение операторов и юристов
4. **WebSocket Manager** - управление WebSocket соединениями
5. **Event Handlers** - обработчики событий Kafka

### Топики Kafka:

- `chat_events` - события чата (сообщения, подключения)
- `support_queue` - очередь обращений в поддержку
- `operator_events` - события операторов (онлайн/оффлайн)
- `chat_assignments` - назначения чатов операторам
- `admin_actions` - административные действия

## Логика работы

### Поток обращения клиента:

1. **Клиент создает чат** → событие `chat_created` → добавление в очередь
2. **Операторы видят обращение** → уведомления через WebSocket
3. **Оператор принимает чат** → событие `operator_accept_chat` → удаление из очереди
4. **Чат назначается оператору** → другие операторы перестают видеть клиента
5. **Обмен сообщениями** → события `message_sent` → рассылка участникам

### Назначение персонального юриста:

1. **Оператор поддержки назначает юриста** → событие `lawyer_assigned`
2. **Создается отдельный чат с юристом** → уведомления клиента и юриста
3. **Клиент может общаться с персональным юристом** независимо от поддержки

### Административные функции:

1. **Принудительный перевод чатов** между операторами
2. **Управление статусами операторов** (онлайн/оффлайн/занят)
3. **Изменение приоритетов в очереди**
4. **Мониторинг и статистика**

## Установка и настройка

### 1. Установка зависимостей

```bash
pip install aiokafka
```

### 2. Настройка Kafka

```bash
# Запуск Kafka (пример с Docker)
docker run -p 9092:9092 apache/kafka:2.8.0
```

### 3. Конфигурация

Отредактируйте `config/kafka_config.py`:

```python
KAFKA_CONFIG = {
    'bootstrap_servers': ['localhost:9092'],
    'client_id': 'support_chat_service',
    'auto_offset_reset': 'latest',
    'enable_auto_commit': True,
    'group_id': 'support_chat_group'
}
```

### 4. Интеграция в приложение

```python
from utils.chat_system_init import startup_chat_system, shutdown_chat_system
from endpoints.chats.chat_kafka import router as chat_router
from endpoints.chats.admin_chat import router as admin_chat_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Запуск системы чата
    await startup_chat_system()
    yield
    # Остановка системы чата
    await shutdown_chat_system()

app = FastAPI(lifespan=lifespan)
app.include_router(chat_router, prefix="/api/v1/chat")
app.include_router(admin_chat_router, prefix="/api/v1/chat")
```

## API Эндпоинты

### WebSocket

- `ws://localhost:8000/api/v1/chat/ws/chat?token={token}&chat_id={chat_id}`

### REST API

#### Для администраторов:

- `POST /api/v1/chat/admin/transfer-chat` - перевод чата
- `POST /api/v1/chat/admin/assign-lawyer` - назначение юриста
- `POST /api/v1/chat/admin/update-operator-status` - изменение статуса оператора
- `POST /api/v1/chat/admin/close-chat` - закрытие чата
- `GET /api/v1/chat/admin/queue` - детальная очередь
- `GET /api/v1/chat/admin/operators` - статусы операторов
- `GET /api/v1/chat/admin/stats` - общая статистика

#### Общие:

- `GET /api/v1/chat/chats/queue` - статус очереди
- `GET /api/v1/chat/chats/operators` - список операторов
- `GET /api/v1/chat/chats/stats` - статистика чатов

## Протокол WebSocket

### Сообщения от клиента:

```json
{
  "type": "message",
  "payload": {
    "text": "Текст сообщения"
  }
}
```

```json
{
  "type": "accept_chat",
  "payload": {
    "client_id": 123,
    "chat_id": 456
  }
}
```

```json
{
  "type": "transfer_chat",
  "payload": {
    "chat_id": 456,
    "target_operator_id": 789,
    "reason": "Специализация"
  }
}
```

```json
{
  "type": "assign_lawyer",
  "payload": {
    "client_id": 123,
    "lawyer_id": 456
  }
}
```

### Сообщения от сервера:

```json
{
  "type": "connected",
  "payload": {
    "user_id": 123,
    "chat_id": 456,
    "role": "support"
  }
}
```

```json
{
  "type": "new_chat_available",
  "payload": {
    "chat_id": 456,
    "client_id": 123
  }
}
```

```json
{
  "type": "chat_assigned",
  "payload": {
    "chat_id": 456,
    "client_id": 123,
    "role": "operator"
  }
}
```

```json
{
  "type": "message",
  "payload": {
    "chat_id": 456,
    "sender_id": 123,
    "message": "Текст сообщения",
    "timestamp": "2023-01-01T12:00:00Z"
  }
}
```

## Мониторинг и логирование

### Статистика системы:

```python
from utils.chat_system_init import get_chat_system

chat_system = get_chat_system()
status = chat_system.get_system_status()
```

### Логи:

Система пока использует стандартное логирование Python (потом изменю):

```python
import logging
logging.basicConfig(level=logging.INFO)
```

## Развертывание

### Docker Compose пример:

```yaml
version: '3.8'
services:
  zookeeper:
    image: confluentinc/cp-zookeeper:latest
    environment:
      ZOOKEEPER_CLIENT_PORT: 2181

  kafka:
    image: confluentinc/cp-kafka:latest
    depends_on:
      - zookeeper
    ports:
      - "9092:9092"
    environment:
      KAFKA_BROKER_ID: 1
      KAFKA_ZOOKEEPER_CONNECT: zookeeper:2181
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://localhost:9092
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1

  app:
    build: .
    ports:
      - "8000:8000"
    depends_on:
      - kafka
    environment:
      KAFKA_BOOTSTRAP_SERVERS: kafka:9092
```

## Масштабирование

1. **Горизонтальное масштабирование** - несколько экземпляров приложения
2. **Партиционирование Kafka** - для увеличения пропускной способности
3. **Load Balancer** - для распределения WebSocket соединений
4. **Redis** - для общего состояния между экземплярами (опционально)

## Безопасность

1. **Аутентификация** через токены
2. **Авторизация** по ролям (клиент/оператор/админ)
3. **Валидация** всех входящих сообщений
4. **Rate limiting** для предотвращения спама

## Тестирование

```python
# Пример теста WebSocket соединения
import pytest
from fastapi.testclient import TestClient
from websockets.sync import connect

def test_websocket_connection():
    with connect("ws://localhost:8000/api/v1/chat/ws/chat?token=test_token") as websocket:
        # Отправляем сообщение
        websocket.send('{"type": "message", "payload": {"text": "Тест"}}')
        
        # Получаем ответ
        response = websocket.recv()
        assert "connected" in response
```

## FAQ

**Q: Что происходит при отключении оператора?**
A: Все его активные чаты автоматически переводятся другим доступным операторам или возвращаются в очередь.

**Q: Можно ли изменить приоритет клиента в очереди?**
A: Да, через административный API эндпоинт `/admin/update-queue-priority`.

**Q: Как работает назначение персонального юриста?**
A: Создается отдельный чат между клиентом и юристом, независимый от чата поддержки.

**Q: Что делать при сбое Kafka?**
A: Система автоматически пытается переподключиться. WebSocket соединения сохраняются, но события могут быть потеряны.
