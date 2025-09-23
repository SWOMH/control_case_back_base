# Команды для запуска тестов системы чата поддержки

## Установка зависимостей для тестирования

```bash
# Установка основных зависимостей
poetry install

# Установка зависимостей для тестирования
poetry install --with test

# Или если используете pip
pip install pytest pytest-asyncio pytest-mock httpx websockets pytest-cov faker
```

## Базовые команды

### Запуск всех тестов
```bash
# Запуск всех тестов
poetry run pytest

# Или с более подробным выводом
poetry run pytest -v

# Запуск с показом покрытия кода
poetry run pytest --cov=utils --cov=endpoints --cov-report=html --cov-report=term-missing
```

### Запуск тестов по категориям

```bash
# Unit тесты
poetry run pytest tests/test_kafka/ tests/test_managers/ -m "not integration"

# Интеграционные тесты
poetry run pytest tests/test_integration/ -m integration

# Тесты авторизации
poetry run pytest tests/test_auth/ -m auth

# Тесты WebSocket
poetry run pytest tests/test_endpoints/test_chat_websocket.py -m websocket

# Быстрые тесты (исключая медленные)
poetry run pytest -m "not slow"
```

### Запуск конкретных тестовых файлов

```bash
# Kafka компоненты
poetry run pytest tests/test_kafka/test_producer.py
poetry run pytest tests/test_kafka/test_consumer.py

# Менеджеры
poetry run pytest tests/test_managers/test_queue_manager.py
poetry run pytest tests/test_managers/test_assignment_manager.py
poetry run pytest tests/test_managers/test_websocket_manager.py

# Эндпоинты
poetry run pytest tests/test_endpoints/test_chat_websocket.py
poetry run pytest tests/test_endpoints/test_admin_chat.py

# Авторизация
poetry run pytest tests/test_auth/test_chat_auth_integration.py

# Полная интеграция
poetry run pytest tests/test_integration/test_chat_system_integration.py
```

### Запуск конкретных тестов

```bash
# Конкретный тестовый класс
poetry run pytest tests/test_kafka/test_producer.py::TestMockSupportChatKafkaProducer

# Конкретный тестовый метод
poetry run pytest tests/test_managers/test_queue_manager.py::TestSupportQueueManager::test_add_client_to_queue

# Тесты по паттерну имени
poetry run pytest -k "test_assign" # все тесты содержащие "assign"
poetry run pytest -k "kafka and producer" # тесты содержащие "kafka" И "producer"
```

## Расширенные опции

### Параллельное выполнение (если установлен pytest-xdist)
```bash
poetry run pytest -n auto  # автоматическое определение числа процессов
poetry run pytest -n 4     # использовать 4 процесса
```

### Отладка
```bash
# Остановка на первой ошибке
poetry run pytest -x

# Остановка после N ошибок
poetry run pytest --maxfail=3

# Запуск с pdb при ошибке
poetry run pytest --pdb

# Запуск последних неудачных тестов
poetry run pytest --lf

# Запуск только новых или измененных тестов
poetry run pytest --ff
```

### Вывод и логирование
```bash
# Показать все print statements
poetry run pytest -s

# Показать локальные переменные в трейсбеке
poetry run pytest -l

# Показать самые медленные тесты
poetry run pytest --durations=10

# Показать все тесты (включая пропущенные)
poetry run pytest -v --tb=short
```

### Работа с маркерами

```bash
# Показать все доступные маркеры
poetry run pytest --markers

# Запуск тестов с конкретным маркером
poetry run pytest -m unit
poetry run pytest -m integration
poetry run pytest -m "kafka and not slow"

# Пропуск тестов с маркером
poetry run pytest -m "not slow"
```

## Тестирование покрытия кода

```bash
# Базовый отчет покрытия
poetry run pytest --cov=utils --cov=endpoints

# HTML отчет (создает папку htmlcov/)
poetry run pytest --cov=utils --cov=endpoints --cov-report=html

# Показать строки без покрытия
poetry run pytest --cov=utils --cov=endpoints --cov-report=term-missing

# Установить минимальный порог покрытия
poetry run pytest --cov=utils --cov=endpoints --cov-fail-under=80

# Только покрытие без выполнения тестов (если уже запускались)
poetry run coverage report
poetry run coverage html
```

## Конфигурационные файлы

### pytest.ini (основная конфигурация)
```ini
[tool:pytest]
testpaths = tests
markers =
    unit: Unit tests
    integration: Integration tests
    slow: Slow tests
asyncio_mode = auto
```

### conftest.py (фикстуры и настройки)
- Общие фикстуры для всех тестов
- Моки для базы данных и внешних сервисов
- Настройки окружения для тестов

## Переменные окружения для тестов

```bash
# В .env файле или экспорт в shell
export KAFKA_ENABLED=false
export REDIS_URL=redis://localhost:6379/1
export TESTING=true

# Запуск с переменными окружения
KAFKA_ENABLED=false pytest tests/
```

## Примеры команд для CI/CD

```bash
# Команда для непрерывной интеграции
poetry run pytest --cov=utils --cov=endpoints --cov-report=xml --junitxml=test-results.xml

# Быстрые тесты для pull request проверки
poetry run pytest -m "not slow" --maxfail=5

# Полный набор тестов для релиза
poetry run pytest --cov=utils --cov=endpoints --cov-fail-under=85 --durations=20
```

## Отладка конкретных проблем

### Проблемы с async/await
```bash
# Включить отладку asyncio
poetry run pytest -s --log-cli-level=DEBUG tests/test_managers/

# Показать все корутины
PYTHONASYNCIODEBUG=1 poetry run pytest tests/test_websocket/
```

### Проблемы с WebSocket
```bash
# Тесты WebSocket с детальным выводом
poetry run pytest tests/test_endpoints/test_chat_websocket.py -s -v

# Только тесты WebSocket соединений
poetry run pytest -k "websocket" -v
```

### Проблемы с Kafka
```bash
# Тесты только mock Kafka (без реального Kafka)
poetry run pytest tests/test_kafka/ -m mock

# Тесты с реальным Kafka (если настроен)
KAFKA_ENABLED=true poetry run pytest tests/test_kafka/ -m real
```

## Структура тестов

```
tests/
├── conftest.py              # Общие фикстуры и настройки
├── test_kafka/              # Тесты Kafka компонентов
│   ├── test_producer.py     # Тесты Kafka Producer
│   └── test_consumer.py     # Тесты Kafka Consumer
├── test_managers/           # Тесты менеджеров
│   ├── test_queue_manager.py
│   ├── test_assignment_manager.py
│   └── test_websocket_manager.py
├── test_endpoints/          # Тесты API эндпоинтов
│   ├── test_chat_websocket.py
│   └── test_admin_chat.py
├── test_auth/               # Тесты авторизации
│   └── test_chat_auth_integration.py
└── test_integration/        # Интеграционные тесты
    └── test_chat_system_integration.py
```

## Рекомендации

1. **Запускайте unit тесты часто** - они быстрые и помогают найти проблемы рано
2. **Интеграционные тесты перед коммитом** - убедитесь что компоненты работают вместе
3. **Полное покрытие перед релизом** - запустите все тесты с проверкой покрытия
4. **Используйте маркеры** - для группировки и фильтрации тестов
5. **Следите за производительностью** - медленные тесты выносите в отдельную группу
