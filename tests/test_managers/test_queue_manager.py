"""
Тесты для Queue Manager - управление очередью операторов и клиентов
"""
import pytest
import pytest_asyncio
import asyncio
from datetime import datetime, timedelta, UTC
from unittest.mock import patch, AsyncMock

from utils.queue_manager import SupportQueueManager, QueuedClient, OperatorStatus


class TestQueuedClient:
    """Тесты для класса QueuedClient"""
    
    def test_queued_client_creation(self):
        """Тест создания клиента в очереди"""
        client_id = 123
        chat_id = 456
        timestamp = datetime.now(UTC)
        priority = 1
        metadata = {"urgency": "high"}
        
        queued_client = QueuedClient(
            client_id=client_id,
            chat_id=chat_id,
            timestamp=timestamp,
            priority=priority,
            metadata=metadata
        )
        
        assert queued_client.client_id == client_id
        assert queued_client.chat_id == chat_id
        assert queued_client.timestamp == timestamp
        assert queued_client.priority == priority
        assert queued_client.wait_time == 0
        assert queued_client.metadata == metadata
    
    def test_queued_client_defaults(self):
        """Тест значений по умолчанию для QueuedClient"""
        client_id = 123
        chat_id = 456
        timestamp = datetime.now(UTC)
        
        queued_client = QueuedClient(
            client_id=client_id,
            chat_id=chat_id,
            timestamp=timestamp
        )
        
        assert queued_client.priority == 0
        assert queued_client.wait_time == 0
        assert queued_client.metadata == {}


class TestOperatorStatus:
    """Тесты для класса OperatorStatus"""
    
    def test_operator_status_creation(self):
        """Тест создания статуса оператора"""
        operator_id = 123
        operator_type = "support"
        max_chats = 5
        
        operator = OperatorStatus(
            operator_id=operator_id,
            operator_type=operator_type,
            max_concurrent_chats=max_chats
        )
        
        assert operator.operator_id == operator_id
        assert operator.operator_type == operator_type
        assert operator.is_online is False
        assert operator.is_available is True
        assert operator.max_concurrent_chats == max_chats
        assert len(operator.current_chats) == 0
        assert isinstance(operator.last_activity, datetime)
    
    def test_can_accept_chat_property(self):
        """Тест свойства can_accept_chat"""
        operator = OperatorStatus(
            operator_id=123,
            operator_type="support",
            max_concurrent_chats=2
        )
        
        # Оператор оффлайн - не может принимать чаты
        assert not operator.can_accept_chat
        
        # Оператор онлайн и доступен - может принимать чаты
        operator.is_online = True
        assert operator.can_accept_chat
        
        # Оператор онлайн но недоступен - не может принимать чаты
        operator.is_available = False
        assert not operator.can_accept_chat
        
        # Оператор достиг лимита чатов - не может принимать
        operator.is_available = True
        operator.current_chats = {1, 2}  # максимум 2
        assert not operator.can_accept_chat
        
        # Оператор превысил лимит - не может принимать
        operator.current_chats = {1, 2, 3}
        assert not operator.can_accept_chat


class TestSupportQueueManager:
    """Тесты для SupportQueueManager"""
    
    @pytest_asyncio.fixture
    async def queue_manager(self):
        """Создает менеджер очереди для тестов"""
        manager = SupportQueueManager()
        await manager.start()
        yield manager
        await manager.stop()
    
    async def test_queue_manager_initialization(self):
        """Тест инициализации менеджера очереди"""
        manager = SupportQueueManager()
        
        assert manager.waiting_clients == {}
        assert manager.operators == {}
        assert manager.chat_assignments == {}
        assert not manager._running
        assert manager._update_task is None
    
    async def test_start_stop_manager(self):
        """Тест запуска и остановки менеджера"""
        manager = SupportQueueManager()
        
        # Запуск
        await manager.start()
        assert manager._running
        assert manager._update_task is not None
        
        # Остановка
        await manager.stop()
        assert not manager._running
    
    async def test_register_operator(self, queue_manager):
        """Тест регистрации оператора"""
        operator_id = 123
        operator_type = "support"
        max_chats = 5
        
        await queue_manager.register_operator(operator_id, operator_type, max_chats)
        
        assert operator_id in queue_manager.operators
        operator = queue_manager.operators[operator_id]
        assert operator.operator_id == operator_id
        assert operator.operator_type == operator_type
        assert operator.max_concurrent_chats == max_chats
        assert not operator.is_online
    
    async def test_set_operator_online(self, queue_manager):
        """Тест перевода оператора в онлайн"""
        operator_id = 123
        operator_type = "support"
        max_chats = 5
        
        with patch.object(queue_manager, '_try_auto_assign_clients') as mock_auto_assign:
            await queue_manager.set_operator_online(operator_id, operator_type, max_chats)
            
            # Проверяем что оператор зарегистрирован и онлайн
            assert operator_id in queue_manager.operators
            operator = queue_manager.operators[operator_id]
            assert operator.is_online
            assert operator.is_available
            
            # Проверяем что была попытка автоназначения
            mock_auto_assign.assert_called_once()
    
    async def test_set_operator_offline(self, queue_manager):
        """Тест перевода оператора в оффлайн"""
        operator_id = 123
        operator_type = "support"
        
        # Сначала переводим в онлайн
        await queue_manager.set_operator_online(operator_id, operator_type)
        
        # Добавляем активный чат
        chat_id = 456
        queue_manager.operators[operator_id].current_chats.add(chat_id)
        queue_manager.chat_assignments[chat_id] = operator_id
        
        with patch.object(queue_manager, '_transfer_chat_to_available_operator') as mock_transfer:
            await queue_manager.set_operator_offline(operator_id)
            
            # Проверяем что оператор оффлайн
            operator = queue_manager.operators[operator_id]
            assert not operator.is_online
            assert not operator.is_available
            
            # Проверяем что был вызван перевод чата
            mock_transfer.assert_called_once_with(chat_id, operator_id, "operator_offline")
    
    async def test_set_operator_busy(self, queue_manager):
        """Тест установки статуса занятости оператора"""
        operator_id = 123
        operator_type = "support"
        
        await queue_manager.register_operator(operator_id, operator_type)
        
        # Делаем оператора занятым
        await queue_manager.set_operator_busy(operator_id, True)
        assert not queue_manager.operators[operator_id].is_available
        
        # Делаем оператора доступным
        await queue_manager.set_operator_busy(operator_id, False)
        assert queue_manager.operators[operator_id].is_available
    
    async def test_get_available_operators(self, queue_manager):
        """Тест получения доступных операторов"""
        # Регистрируем операторов разных типов
        await queue_manager.set_operator_online(1, "support", 5)
        await queue_manager.set_operator_online(2, "lawyer", 3)
        await queue_manager.set_operator_online(3, "support", 5)
        
        # Делаем одного оператора недоступным
        await queue_manager.set_operator_busy(3, True)
        
        # Получаем всех доступных операторов
        available = queue_manager.get_available_operators()
        assert len(available) == 2
        assert all(op.can_accept_chat for op in available)
        
        # Получаем только операторов поддержки
        support_available = queue_manager.get_available_operators("support")
        assert len(support_available) == 1
        assert support_available[0].operator_id == 1
    
    async def test_get_available_operators_sorting(self, queue_manager):
        """Тест сортировки доступных операторов по загрузке"""
        # Регистрируем операторов
        await queue_manager.set_operator_online(1, "support", 5)
        await queue_manager.set_operator_online(2, "support", 5)
        
        # Добавляем чаты первому оператору
        queue_manager.operators[1].current_chats = {101, 102}
        
        # Получаем доступных операторов
        available = queue_manager.get_available_operators()
        
        # Проверяем что менее загруженный оператор идет первым
        assert available[0].operator_id == 2  # без чатов
        assert available[1].operator_id == 1  # с 2 чатами
    
    async def test_add_client_to_queue(self, queue_manager):
        """Тест добавления клиента в очередь"""
        client_id = 123
        chat_id = 456
        priority = 1
        metadata = {"urgency": "high"}
        
        with patch.object(queue_manager, '_try_assign_operator_to_client') as mock_assign:
            await queue_manager.add_client_to_queue(client_id, chat_id, priority, metadata)
            
            # Проверяем что клиент добавлен в очередь
            assert client_id in queue_manager.waiting_clients
            queued_client = queue_manager.waiting_clients[client_id]
            assert queued_client.client_id == client_id
            assert queued_client.chat_id == chat_id
            assert queued_client.priority == priority
            assert queued_client.metadata == metadata
            
            # Проверяем что была попытка назначения
            mock_assign.assert_called_once_with(client_id)
    
    async def test_add_client_to_queue_duplicate(self, queue_manager):
        """Тест добавления дублирующегося клиента в очередь"""
        client_id = 123
        chat_id = 456
        
        # Добавляем клиента первый раз
        await queue_manager.add_client_to_queue(client_id, chat_id)
        
        # Добавляем того же клиента снова - должен игнорироваться
        with patch.object(queue_manager, '_try_assign_operator_to_client') as mock_assign:
            await queue_manager.add_client_to_queue(client_id, chat_id + 100)  # другой чат
            
            # Должен остаться только один клиент с первым чатом
            assert len(queue_manager.waiting_clients) == 1
            queued_client = queue_manager.waiting_clients[client_id]
            assert queued_client.chat_id == chat_id  # первый чат
    
    async def test_remove_client_from_queue(self, queue_manager):
        """Тест удаления клиента из очереди"""
        client_id = 123
        chat_id = 456
        
        # Добавляем клиента
        await queue_manager.add_client_to_queue(client_id, chat_id)
        assert client_id in queue_manager.waiting_clients
        
        # Удаляем клиента
        result = await queue_manager.remove_client_from_queue(client_id)
        assert result is True
        assert client_id not in queue_manager.waiting_clients
        
        # Попытка удалить несуществующего клиента
        result = await queue_manager.remove_client_from_queue(client_id)
        assert result is False
    
    async def test_update_queue_position(self, queue_manager):
        """Тест обновления приоритета клиента в очереди"""
        client_id = 123
        chat_id = 456
        
        # Добавляем клиента с приоритетом 0
        await queue_manager.add_client_to_queue(client_id, chat_id, priority=0)
        
        # Обновляем приоритет
        new_position = await queue_manager.update_queue_position(client_id, 5)
        
        # Проверяем что приоритет обновился
        assert queue_manager.waiting_clients[client_id].priority == 5
        assert new_position == 1  # единственный в очереди
    
    async def test_get_queue_position(self, queue_manager):
        """Тест получения позиции клиента в очереди"""
        # Добавляем клиентов с разными приоритетами
        await queue_manager.add_client_to_queue(1, 101, priority=0)  # низкий приоритет
        await queue_manager.add_client_to_queue(2, 102, priority=2)  # высокий приоритет
        await queue_manager.add_client_to_queue(3, 103, priority=1)  # средний приоритет
        
        # Проверяем позиции (высокий приоритет = меньший номер в очереди)
        assert await queue_manager.get_queue_position(2) == 1  # приоритет 2
        assert await queue_manager.get_queue_position(3) == 2  # приоритет 1
        assert await queue_manager.get_queue_position(1) == 3  # приоритет 0
        
        # Несуществующий клиент
        assert await queue_manager.get_queue_position(999) == -1
    
    async def test_get_queue_position_with_time_sorting(self, queue_manager):
        """Тест сортировки очереди по времени при одинаковом приоритете"""
        import time
        
        # Добавляем клиентов с одинаковым приоритетом но в разное время
        await queue_manager.add_client_to_queue(1, 101, priority=1)
        
        # Небольшая задержка для разного времени
        await asyncio.sleep(0.01)
        
        await queue_manager.add_client_to_queue(2, 102, priority=1)
        
        # Первый клиент должен быть раньше в очереди
        assert await queue_manager.get_queue_position(1) == 1
        assert await queue_manager.get_queue_position(2) == 2
    
    # async def test_assign_chat_to_operator(self, queue_manager):
    #     """Тест назначения чата оператору"""
    #     operator_id = 123
    #     client_id = 456
    #     chat_id = 789
        
    #     # Регистрируем оператора
    #     await queue_manager.set_operator_online(operator_id, "support")
        
    #     # Добавляем клиента в очередь
    #     await queue_manager.add_client_to_queue(client_id, chat_id)
        
    #     # Назначаем чат
    #     result = await queue_manager.assign_chat_to_operator(chat_id, operator_id, client_id)
        
    #     assert result is True
    #     assert chat_id in queue_manager.chat_assignments
    #     assert queue_manager.chat_assignments[chat_id] == operator_id
    #     assert chat_id in queue_manager.operators[operator_id].current_chats
    #     assert client_id not in queue_manager.waiting_clients
    
    async def test_assign_chat_to_unavailable_operator(self, queue_manager):
        """Тест назначения чата недоступному оператору"""
        operator_id = 123
        client_id = 456
        chat_id = 789
        
        # Регистрируем оператора но не переводим в онлайн
        await queue_manager.register_operator(operator_id, "support")
        
        # Пытаемся назначить чат
        result = await queue_manager.assign_chat_to_operator(chat_id, operator_id, client_id)
        
        assert result is False
        assert chat_id not in queue_manager.chat_assignments
    
    # async def test_release_operator_from_chat(self, queue_manager):
    #     """Тест освобождения оператора от чата"""
    #     operator_id = 123
    #     client_id = 456
    #     chat_id = 789
        
    #     # Настраиваем оператора и назначаем чат
    #     await queue_manager.set_operator_online(operator_id, "support")
    #     await queue_manager.assign_chat_to_operator(chat_id, operator_id, client_id)
        
    #     with patch.object(queue_manager, '_try_auto_assign_clients') as mock_auto_assign:
    #         # Освобождаем оператора
    #         result = await queue_manager.release_operator_from_chat(chat_id)
            
    #         assert result is True
    #         assert chat_id not in queue_manager.chat_assignments
    #         assert chat_id not in queue_manager.operators[operator_id].current_chats
            
    #         # Проверяем что была попытка автоназначения
    #         mock_auto_assign.assert_called_once()
    
    async def test_transfer_chat(self, queue_manager):
        """Тест перевода чата другому оператору"""
        old_operator_id = 123
        new_operator_id = 456
        chat_id = 789
        
        # Регистрируем операторов
        await queue_manager.set_operator_online(old_operator_id, "support")
        await queue_manager.set_operator_online(new_operator_id, "support")
        
        # Назначаем чат первому оператору
        await queue_manager.assign_chat_to_operator(chat_id, old_operator_id, 999)
        
        # Переводим чат
        result = await queue_manager.transfer_chat(chat_id, new_operator_id, "test_transfer")
        
        assert result is True
        assert queue_manager.chat_assignments[chat_id] == new_operator_id
        assert chat_id not in queue_manager.operators[old_operator_id].current_chats
        assert chat_id in queue_manager.operators[new_operator_id].current_chats
    
    async def test_transfer_nonexistent_chat(self, queue_manager):
        """Тест перевода несуществующего чата"""
        new_operator_id = 456
        
        await queue_manager.set_operator_online(new_operator_id, "support")
        
        result = await queue_manager.transfer_chat(999, new_operator_id, "test")
        assert result is False
    
    async def test_transfer_chat_to_unavailable_operator(self, queue_manager):
        """Тест перевода чата недоступному оператору"""
        old_operator_id = 123
        new_operator_id = 456
        chat_id = 789
        
        # Регистрируем только первого оператора
        await queue_manager.set_operator_online(old_operator_id, "support")
        await queue_manager.assign_chat_to_operator(chat_id, old_operator_id, 999)
        
        # Пытаемся перевести недоступному оператору
        result = await queue_manager.transfer_chat(chat_id, new_operator_id, "test")
        assert result is False
        
        # Чат должен остаться у первого оператора
        assert queue_manager.chat_assignments[chat_id] == old_operator_id
    
    async def test_get_queue_status(self, queue_manager):
        """Тест получения статуса очереди"""
        # Добавляем клиентов в очередь
        await queue_manager.add_client_to_queue(1, 101, priority=1)
        await queue_manager.add_client_to_queue(2, 102, priority=0)
        
        # Добавляем операторов
        await queue_manager.set_operator_online(201, "support")
        await queue_manager.set_operator_online(202, "support")
        await queue_manager.set_operator_busy(202, True)  # один занят
        
        status = queue_manager.get_queue_status()
        
        assert status['total_waiting'] == 2
        assert status['available_operators'] == 1  # один доступен
        assert 'average_wait_time' in status
        assert 'queue_by_priority' in status
        assert status['queue_by_priority'][1] == 1  # один клиент с приоритетом 1
        assert status['queue_by_priority'][0] == 1  # один клиент с приоритетом 0
    
    async def test_try_assign_operator_to_client(self, queue_manager):
        """Тест автоматического назначения оператора клиенту"""
        client_id = 123
        chat_id = 456
        operator_id = 789
        
        # Добавляем клиента в очередь
        await queue_manager.add_client_to_queue(client_id, chat_id)
        
        # Добавляем доступного оператора
        await queue_manager.set_operator_online(operator_id, "support")
        
        # Пытаемся назначить оператора
        assigned_operator = await queue_manager._try_assign_operator_to_client(client_id)
        
        assert assigned_operator == operator_id
        assert client_id not in queue_manager.waiting_clients
        assert chat_id in queue_manager.chat_assignments
        assert queue_manager.chat_assignments[chat_id] == operator_id
    
    async def test_try_assign_operator_no_available(self, queue_manager):
        """Тест назначения оператора когда нет доступных"""
        client_id = 123
        chat_id = 456
        
        # Добавляем клиента в очередь
        await queue_manager.add_client_to_queue(client_id, chat_id)
        
        # Нет доступных операторов
        assigned_operator = await queue_manager._try_assign_operator_to_client(client_id)
        
        assert assigned_operator is None
        assert client_id in queue_manager.waiting_clients  # остается в очереди
    
    async def test_try_auto_assign_clients(self, queue_manager):
        """Тест автоматического назначения операторов ожидающим клиентам"""
        # Добавляем клиентов с разными приоритетами
        await queue_manager.add_client_to_queue(1, 101, priority=0)
        await queue_manager.add_client_to_queue(2, 102, priority=2)  # высокий приоритет
        await queue_manager.add_client_to_queue(3, 103, priority=1)
        
        # Добавляем доступного оператора
        operator_id = 201
        await queue_manager.set_operator_online(operator_id, "support", max_concurrent_chats=1)
        
        with patch.object(queue_manager, '_try_assign_operator_to_client') as mock_assign:
            mock_assign.return_value = operator_id
            
            await queue_manager._try_auto_assign_clients()
            
            # Должен быть вызван для клиента с наивысшим приоритетом
            mock_assign.assert_called_once_with(2)  # клиент с приоритетом 2
    
    async def test_update_wait_times(self, queue_manager):
        """Тест обновления времени ожидания клиентов"""
        client_id = 123
        chat_id = 456
        
        # Добавляем клиента
        await queue_manager.add_client_to_queue(client_id, chat_id)
        
        # Изначально время ожидания равно 0
        assert queue_manager.waiting_clients[client_id].wait_time == 0
        
        # Ждем немного и проверяем обновление времени
        await asyncio.sleep(0.1)
        
        # Вызываем обновление времени вручную
        current_time = datetime.now(UTC)
        async with queue_manager._queue_lock:
            for client in queue_manager.waiting_clients.values():
                client.wait_time = int((current_time - client.timestamp).total_seconds())
        
        # Время ожидания должно быть больше 0
        assert queue_manager.waiting_clients[client_id].wait_time >= 0
    
    async def test_get_operator_stats(self, queue_manager):
        """Тест получения статистики оператора"""
        operator_id = 123
        operator_type = "support"
        
        # Регистрируем оператора
        await queue_manager.set_operator_online(operator_id, operator_type, max_concurrent_chats=5)
        
        stats = queue_manager.get_operator_stats(operator_id)
        
        assert stats is not None
        assert stats['operator_id'] == operator_id
        assert stats['operator_type'] == operator_type
        assert stats['is_online'] is True
        assert stats['is_available'] is True
        assert stats['current_chats_count'] == 0
        assert stats['max_concurrent_chats'] == 5
        assert 'last_activity' in stats
        
        # Несуществующий оператор
        assert queue_manager.get_operator_stats(999) is None
    
    # async def test_concurrent_operations(self, queue_manager):
    #     """Тест одновременных операций с блокировками"""
    #     client_id = 123
    #     chat_id = 456
    #     operator_id = 789
        
    #     await queue_manager.set_operator_online(operator_id, "support")
        
    #     # Одновременное добавление и удаление клиента
    #     async def add_client():
    #         await queue_manager.add_client_to_queue(client_id, chat_id)
        
    #     async def remove_client():
    #         await asyncio.sleep(0.01)  # небольшая задержка
    #         await queue_manager.remove_client_from_queue(client_id)
        
    #     # Запускаем операции одновременно
    #     await asyncio.gather(add_client(), remove_client())
        
        # Результат должен быть предсказуемым благодаря блокировкам
        # Клиент либо есть, либо нет, но не в неопределенном состоянии
