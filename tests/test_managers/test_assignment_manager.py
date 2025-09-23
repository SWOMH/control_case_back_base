"""
Тесты для Assignment Manager - управление назначениями операторов и юристов
"""
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch, MagicMock

from utils.assignment_manager import ChatAssignmentManager, create_assignment_manager
from utils.queue_manager import SupportQueueManager, OperatorStatus
from utils.websocket_manager import WebSocketConnectionManager


class TestChatAssignmentManager:
    """Тесты для ChatAssignmentManager"""
    
    @pytest_asyncio.fixture
    async def queue_manager(self):
        """Создает менеджер очереди для тестов"""
        manager = SupportQueueManager()
        await manager.start()
        yield manager
        await manager.stop()
    
    @pytest_asyncio.fixture
    async def websocket_manager(self):
        """Создает менеджер WebSocket для тестов"""
        return WebSocketConnectionManager()
    
    @pytest_asyncio.fixture
    async def assignment_manager(self, queue_manager, websocket_manager):
        """Создает менеджер назначений для тестов"""
        return ChatAssignmentManager(queue_manager, websocket_manager)
    
    @pytest_asyncio.fixture
    async def mock_chat_db(self):
        """Создает мок базы данных чатов"""
        with patch('utils.assignment_manager.chat_db') as mock_db:
            mock_db.update_chat_operator = AsyncMock()
            mock_db.add_chat_participant = AsyncMock()
            mock_db.mark_chat_participant_left = AsyncMock()
            mock_db.transfer_chat = AsyncMock()
            mock_db.close_chat = AsyncMock()
            mock_db.create_chat = AsyncMock()
            mock_db.create_lawyer_assignment = AsyncMock()
            mock_db.get_active_lawyer_chat = AsyncMock()
            mock_db.get_active_lawyer_assignment = AsyncMock()
            mock_db.get_chat_by_id = AsyncMock()
            yield mock_db
    
    @pytest_asyncio.fixture
    async def mock_kafka_producer(self):
        """Создает мок Kafka Producer"""
        with patch('utils.assignment_manager.kafka_producer') as mock_producer:
            mock_producer.send_chat_assigned = AsyncMock()
            mock_producer.send_operator_accept_chat = AsyncMock()
            mock_producer.send_chat_transferred = AsyncMock()
            mock_producer.send_force_transfer = AsyncMock()
            mock_producer.send_lawyer_assigned = AsyncMock()
            mock_producer.send_chat_closed = AsyncMock()
            mock_producer.send_operator_online = AsyncMock()
            mock_producer.send_operator_offline = AsyncMock()
            yield mock_producer
    
    async def test_assignment_manager_initialization(self, queue_manager, websocket_manager):
        """Тест инициализации менеджера назначений"""
        manager = ChatAssignmentManager(queue_manager, websocket_manager)
        
        assert manager.queue_manager == queue_manager
        assert manager.websocket_manager == websocket_manager
        assert manager.user_roles_cache == {}
        assert manager.lawyer_assignments == {}
    
    async def test_create_assignment_manager_function(self, queue_manager, websocket_manager):
        """Тест функции создания менеджера назначений"""
        manager = create_assignment_manager(queue_manager, websocket_manager)
        
        assert isinstance(manager, ChatAssignmentManager)
        assert manager.queue_manager == queue_manager
        assert manager.websocket_manager == websocket_manager
    
    async def test_set_operator_online(self, assignment_manager, mock_kafka_producer):
        """Тест установки оператора в онлайн состояние"""
        operator_id = 123
        operator_type = "support"
        max_chats = 5
        
        await assignment_manager.set_operator_online(operator_id, operator_type, max_chats)
        
        # Проверяем что оператор добавлен в очередной менеджер
        assert operator_id in assignment_manager.queue_manager.operators
        operator = assignment_manager.queue_manager.operators[operator_id]
        assert operator.is_online
        assert operator.operator_type == operator_type
        assert operator.max_concurrent_chats == max_chats
        
        # Проверяем отправку Kafka события
        mock_kafka_producer.send_operator_online.assert_called_once_with(
            operator_id, operator_type, max_chats
        )
    
    async def test_set_operator_offline(self, assignment_manager, mock_kafka_producer):
        """Тест установки оператора в оффлайн состояние"""
        operator_id = 123
        operator_type = "support"
        
        # Сначала переводим в онлайн
        await assignment_manager.set_operator_online(operator_id, operator_type)
        
        # Переводим в оффлайн
        await assignment_manager.set_operator_offline(operator_id)
        
        # Проверяем что оператор оффлайн
        operator = assignment_manager.queue_manager.operators[operator_id]
        assert not operator.is_online
        
        # Проверяем отправку Kafka события
        mock_kafka_producer.send_operator_offline.assert_called_once_with(
            operator_id, operator_type
        )
    
    async def test_get_operator_type(self, assignment_manager):
        """Тест получения типа оператора"""
        user_id = 123
        
        # Первый вызов - кэша нет
        operator_type = await assignment_manager.get_operator_type(user_id)
        assert operator_type == "support"  # значение по умолчанию
        
        # Проверяем что значение закэшировано
        assert assignment_manager.user_roles_cache[user_id] == "support"
        
        # Второй вызов - из кэша
        operator_type = await assignment_manager.get_operator_type(user_id)
        assert operator_type == "support"
    
    async def test_assign_chat_to_operator_success(self, assignment_manager, mock_chat_db, mock_kafka_producer):
        """Тест успешного назначения чата оператору"""
        chat_id = 456
        operator_id = 123
        client_id = 789
        
        # Настраиваем оператора
        await assignment_manager.set_operator_online(operator_id, "support")
        
        # Мокаем возвращаемое значение для create_chat
        mock_chat = MagicMock()
        mock_chat.id = chat_id
        mock_chat_db.create_chat.return_value = mock_chat
        
        # Выполняем назначение
        success = await assignment_manager.assign_chat_to_operator(chat_id, operator_id, client_id)
        
        assert success is True
        
        # Проверяем обновления в queue_manager
        assert chat_id in assignment_manager.queue_manager.chat_assignments
        assert assignment_manager.queue_manager.chat_assignments[chat_id] == operator_id
        
        # Проверяем вызовы БД
        mock_chat_db.update_chat_operator.assert_called_once()
        mock_chat_db.add_chat_participant.assert_called_once()
        
        # Проверяем отправку Kafka событий
        mock_kafka_producer.send_chat_assigned.assert_called_once()
        mock_kafka_producer.send_operator_accept_chat.assert_called_once()
    
    async def test_assign_chat_to_operator_unavailable(self, assignment_manager):
        """Тест назначения чата недоступному оператору"""
        chat_id = 456
        operator_id = 123  # не зарегистрирован
        client_id = 789
        
        success = await assignment_manager.assign_chat_to_operator(chat_id, operator_id, client_id)
        
        assert success is False
    
    async def test_assign_chat_to_operator_database_error(self, assignment_manager, mock_chat_db):
        """Тест обработки ошибки БД при назначении чата"""
        chat_id = 456
        operator_id = 123
        client_id = 789
        
        # Настраиваем оператора
        await assignment_manager.set_operator_online(operator_id, "support")
        
        # Настраиваем ошибку БД
        mock_chat_db.update_chat_operator.side_effect = Exception("Database error")
        
        success = await assignment_manager.assign_chat_to_operator(chat_id, operator_id, client_id)
        
        assert success is False
        
        # Проверяем что назначение было откачено
        assert chat_id not in assignment_manager.queue_manager.chat_assignments
    
    async def test_release_operator_from_chat(self, assignment_manager, mock_chat_db):
        """Тест освобождения оператора от чата"""
        chat_id = 456
        operator_id = 123
        client_id = 789
        
        # Настраиваем оператора и назначаем чат
        await assignment_manager.set_operator_online(operator_id, "support")
        await assignment_manager.assign_chat_to_operator(chat_id, operator_id, client_id)
        
        # Освобождаем оператора
        await assignment_manager.release_operator_from_chat(chat_id)
        
        # Проверяем что чат удален из назначений
        assert chat_id not in assignment_manager.queue_manager.chat_assignments
        
        # Проверяем вызов БД
        mock_chat_db.mark_chat_participant_left.assert_called_once_with(
            mock_chat_db.get_async_session().__aenter__.return_value,
            chat_id,
            operator_id
        )
    
    async def test_transfer_chat_to_operator_success(self, assignment_manager, mock_chat_db, mock_kafka_producer):
        """Тест успешного перевода чата другому оператору"""
        chat_id = 456
        old_operator_id = 123
        new_operator_id = 789
        client_id = 999
        reason = "test_transfer"
        
        # Настраиваем операторов
        await assignment_manager.set_operator_online(old_operator_id, "support")
        await assignment_manager.set_operator_online(new_operator_id, "support")
        
        # Назначаем чат первому оператору
        await assignment_manager.assign_chat_to_operator(chat_id, old_operator_id, client_id)
        
        # Мокаем получение client_id
        with patch.object(assignment_manager, '_get_client_id_from_chat', return_value=client_id):
            # Переводим чат
            success = await assignment_manager.transfer_chat_to_operator(
                chat_id, new_operator_id, old_operator_id, reason
            )
        
        assert success is True
        
        # Проверяем что чат переведен
        assert assignment_manager.queue_manager.chat_assignments[chat_id] == new_operator_id
        
        # Проверяем вызовы БД
        mock_chat_db.transfer_chat.assert_called_once()
        
        # Проверяем отправку Kafka события
        mock_kafka_producer.send_chat_transferred.assert_called_once()
    
    async def test_transfer_chat_to_unavailable_operator(self, assignment_manager):
        """Тест перевода чата недоступному оператору"""
        chat_id = 456
        old_operator_id = 123
        new_operator_id = 789  # не зарегистрирован
        reason = "test_transfer"
        
        # Настраиваем только старого оператора
        await assignment_manager.set_operator_online(old_operator_id, "support")
        
        success = await assignment_manager.transfer_chat_to_operator(
            chat_id, new_operator_id, old_operator_id, reason
        )
        
        assert success is False
    
    async def test_assign_personal_lawyer_success(self, assignment_manager, mock_chat_db, mock_kafka_producer):
        """Тест успешного назначения персонального юриста"""
        client_id = 123
        lawyer_id = 456
        assigned_by = 789
        
        # Мокаем создание чата с юристом
        mock_chat = MagicMock()
        mock_chat.id = 999
        mock_chat_db.create_chat.return_value = mock_chat
        
        # Назначаем юриста
        lawyer_chat_id = await assignment_manager.assign_personal_lawyer(
            client_id, lawyer_id, assigned_by
        )
        
        assert lawyer_chat_id == 999
        
        # Проверяем что назначение сохранено
        assert assignment_manager.lawyer_assignments[client_id] == lawyer_id
        
        # Проверяем вызовы БД
        mock_chat_db.create_chat.assert_called_once()
        mock_chat_db.create_lawyer_assignment.assert_called_once()
        
        # Проверяем отправку Kafka события
        mock_kafka_producer.send_lawyer_assigned.assert_called_once_with(
            client_id, lawyer_id, 999
        )
    
    async def test_assign_personal_lawyer_database_error(self, assignment_manager, mock_chat_db):
        """Тест обработки ошибки БД при назначении юриста"""
        client_id = 123
        lawyer_id = 456
        assigned_by = 789
        
        # Настраиваем ошибку БД
        mock_chat_db.create_chat.side_effect = Exception("Database error")
        
        lawyer_chat_id = await assignment_manager.assign_personal_lawyer(
            client_id, lawyer_id, assigned_by
        )
        
        assert lawyer_chat_id is None
    
    async def test_create_lawyer_chat_new(self, assignment_manager, mock_chat_db):
        """Тест создания нового чата с юристом"""
        client_id = 123
        lawyer_id = 456
        
        # Мокаем что активного чата нет
        mock_chat_db.get_active_lawyer_chat.return_value = None
        
        # Мокаем создание нового чата
        mock_chat = MagicMock()
        mock_chat.id = 999
        mock_chat_db.create_chat.return_value = mock_chat
        
        chat_id = await assignment_manager.create_lawyer_chat(client_id, lawyer_id)
        
        assert chat_id == 999
        
        # Проверяем вызовы БД
        mock_chat_db.get_active_lawyer_chat.assert_called_once()
        mock_chat_db.create_chat.assert_called_once()
        mock_chat_db.add_chat_participant.assert_called()  # должен быть вызван дважды
    
    async def test_create_lawyer_chat_existing(self, assignment_manager, mock_chat_db):
        """Тест использования существующего чата с юристом"""
        client_id = 123
        lawyer_id = 456
        
        # Мокаем существующий чат
        mock_existing_chat = MagicMock()
        mock_existing_chat.id = 888
        mock_chat_db.get_active_lawyer_chat.return_value = mock_existing_chat
        
        chat_id = await assignment_manager.create_lawyer_chat(client_id, lawyer_id)
        
        assert chat_id == 888
        
        # Проверяем что новый чат не создавался
        mock_chat_db.create_chat.assert_not_called()
    
    async def test_get_client_lawyer_from_cache(self, assignment_manager):
        """Тест получения назначенного юриста из кэша"""
        client_id = 123
        lawyer_id = 456
        
        # Добавляем в кэш
        assignment_manager.lawyer_assignments[client_id] = lawyer_id
        
        result = await assignment_manager.get_client_lawyer(client_id)
        assert result == lawyer_id
    
    async def test_get_client_lawyer_from_database(self, assignment_manager, mock_chat_db):
        """Тест получения назначенного юриста из БД"""
        client_id = 123
        lawyer_id = 456
        
        # Мокаем результат из БД
        mock_assignment = MagicMock()
        mock_assignment.lawyer_id = lawyer_id
        mock_chat_db.get_active_lawyer_assignment.return_value = mock_assignment
        
        result = await assignment_manager.get_client_lawyer(client_id)
        
        assert result == lawyer_id
        # Проверяем что значение закэшировано
        assert assignment_manager.lawyer_assignments[client_id] == lawyer_id
    
    async def test_get_client_lawyer_not_found(self, assignment_manager, mock_chat_db):
        """Тест получения юриста когда назначения нет"""
        client_id = 123
        
        # Мокаем что назначения нет
        mock_chat_db.get_active_lawyer_assignment.return_value = None
        
        result = await assignment_manager.get_client_lawyer(client_id)
        assert result is None
    
    async def test_force_transfer_chat(self, assignment_manager, mock_kafka_producer):
        """Тест принудительного перевода чата администратором"""
        chat_id = 456
        target_operator_id = 123
        source_operator_id = 789
        admin_id = 1
        reason = "admin action"
        
        # Настраиваем операторов
        await assignment_manager.set_operator_online(source_operator_id, "support")
        await assignment_manager.set_operator_online(target_operator_id, "support")
        
        # Назначаем чат исходному оператору
        await assignment_manager.assign_chat_to_operator(chat_id, source_operator_id, 999)
        
        with patch.object(assignment_manager, 'transfer_chat_to_operator', return_value=True) as mock_transfer:
            success = await assignment_manager.force_transfer_chat(
                chat_id, target_operator_id, source_operator_id, admin_id, reason
            )
            
            assert success is True
            
            # Проверяем что был вызван transfer_chat_to_operator с правильными параметрами
            mock_transfer.assert_called_once_with(
                chat_id, target_operator_id, source_operator_id,
                f"admin_force_transfer: {reason}", admin_id
            )
    
    async def test_force_close_chat(self, assignment_manager, mock_chat_db, mock_kafka_producer):
        """Тест принудительного закрытия чата администратором"""
        chat_id = 456
        admin_id = 1
        reason = "admin action"
        operator_id = 123
        
        # Настраиваем оператора и назначаем чат
        await assignment_manager.set_operator_online(operator_id, "support")
        await assignment_manager.assign_chat_to_operator(chat_id, operator_id, 999)
        
        success = await assignment_manager.force_close_chat(chat_id, admin_id, reason)
        
        assert success is True
        
        # Проверяем вызов БД
        mock_chat_db.close_chat.assert_called_once()
        
        # Проверяем что оператор освобожден
        assert chat_id not in assignment_manager.queue_manager.chat_assignments
        
        # Проверяем отправку Kafka события
        mock_kafka_producer.send_chat_closed.assert_called_once_with(
            chat_id, admin_id, f"admin_force_close: {reason}"
        )
    
    async def test_force_close_chat_database_error(self, assignment_manager, mock_chat_db):
        """Тест обработки ошибки БД при принудительном закрытии чата"""
        chat_id = 456
        admin_id = 1
        reason = "admin action"
        
        # Настраиваем ошибку БД
        mock_chat_db.close_chat.side_effect = Exception("Database error")
        
        success = await assignment_manager.force_close_chat(chat_id, admin_id, reason)
        
        assert success is False
    
    async def test_get_operator_chats(self, assignment_manager):
        """Тест получения списка чатов оператора"""
        operator_id = 123
        chat_ids = [456, 789, 999]
        
        # Настраиваем оператора
        await assignment_manager.set_operator_online(operator_id, "support")
        
        # Добавляем чаты
        for chat_id in chat_ids:
            assignment_manager.queue_manager.operators[operator_id].current_chats.add(chat_id)
        
        result = await assignment_manager.get_operator_chats(operator_id)
        
        assert set(result) == set(chat_ids)
    
    async def test_get_operator_chats_nonexistent(self, assignment_manager):
        """Тест получения чатов несуществующего оператора"""
        result = await assignment_manager.get_operator_chats(999)
        assert result == []
    
    async def test_get_chat_operator(self, assignment_manager):
        """Тест получения оператора чата"""
        chat_id = 456
        operator_id = 123
        
        # Назначаем чат оператору
        assignment_manager.queue_manager.chat_assignments[chat_id] = operator_id
        
        result = await assignment_manager.get_chat_operator(chat_id)
        assert result == operator_id
        
        # Несуществующий чат
        result = await assignment_manager.get_chat_operator(999)
        assert result is None
    
    async def test_is_operator_available(self, assignment_manager):
        """Тест проверки доступности оператора"""
        operator_id = 123
        
        # Оператор не зарегистрирован
        result = await assignment_manager.is_operator_available(operator_id)
        assert result is False
        
        # Регистрируем оператора
        await assignment_manager.set_operator_online(operator_id, "support")
        
        result = await assignment_manager.is_operator_available(operator_id)
        assert result is True
        
        # Делаем оператора недоступным
        assignment_manager.queue_manager.operators[operator_id].is_available = False
        
        result = await assignment_manager.is_operator_available(operator_id)
        assert result is False
    
    async def test_get_assignment_stats(self, assignment_manager):
        """Тест получения статистики назначений"""
        # Настраиваем операторов
        await assignment_manager.set_operator_online(1, "support", 5)
        await assignment_manager.set_operator_online(2, "lawyer", 3)
        
        # Добавляем чаты
        assignment_manager.queue_manager.chat_assignments[101] = 1
        assignment_manager.queue_manager.chat_assignments[102] = 2
        assignment_manager.queue_manager.operators[1].current_chats.add(101)
        assignment_manager.queue_manager.operators[2].current_chats.add(102)
        
        # Добавляем назначения юристов
        assignment_manager.lawyer_assignments[201] = 2
        
        stats = assignment_manager.get_assignment_stats()
        
        assert stats['total_active_chats'] == 2
        assert stats['total_lawyer_assignments'] == 1
        assert 'operator_loads' in stats
        
        # Проверяем нагрузку операторов
        operator_loads = stats['operator_loads']
        assert 1 in operator_loads
        assert 2 in operator_loads
        
        assert operator_loads[1]['type'] == "support"
        assert operator_loads[1]['current_chats'] == 1
        assert operator_loads[1]['max_chats'] == 5
        assert operator_loads[1]['utilization'] == 0.2  # 1/5
        
        assert operator_loads[2]['type'] == "lawyer"
        assert operator_loads[2]['current_chats'] == 1
        assert operator_loads[2]['max_chats'] == 3
        assert operator_loads[2]['utilization'] == 0.33333333333333337  # 1/3 (примерно)
    
    async def test_get_client_id_from_chat(self, assignment_manager, mock_chat_db):
        """Тест получения ID клиента из чата"""
        chat_id = 456
        client_id = 123
        
        # Мокаем результат из БД
        mock_chat = MagicMock()
        mock_chat.user_id = client_id
        mock_chat_db.get_chat_by_id.return_value = mock_chat
        
        result = await assignment_manager._get_client_id_from_chat(chat_id)
        assert result == client_id
        
        # Несуществующий чат
        mock_chat_db.get_chat_by_id.return_value = None
        result = await assignment_manager._get_client_id_from_chat(999)
        assert result is None
    
    async def test_concurrent_assignment_operations(self, assignment_manager):
        """Тест одновременных операций назначения с блокировками"""
        import asyncio
        
        chat_id1 = 456
        chat_id2 = 789
        operator_id = 123
        client_id1 = 111
        client_id2 = 222
        
        # Настраиваем оператора
        await assignment_manager.set_operator_online(operator_id, "support", max_concurrent_chats=2)
        
        # Одновременное назначение двух чатов одному оператору
        async def assign_chat1():
            return await assignment_manager.assign_chat_to_operator(chat_id1, operator_id, client_id1)
        
        async def assign_chat2():
            return await assignment_manager.assign_chat_to_operator(chat_id2, operator_id, client_id2)
        
        # Мокаем БД операции
        with patch('utils.assignment_manager.chat_db') as mock_db:
            mock_db.update_chat_operator = AsyncMock()
            mock_db.add_chat_participant = AsyncMock()
            
            results = await asyncio.gather(assign_chat1(), assign_chat2())
        
        # Оба назначения должны быть успешными благодаря блокировкам
        assert results[0] is True
        assert results[1] is True
        
        # Проверяем что оба чата назначены
        assert len(assignment_manager.queue_manager.operators[operator_id].current_chats) == 2
