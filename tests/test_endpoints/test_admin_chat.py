"""
Тесты для административных REST API эндпоинтов чата поддержки
"""
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi import HTTPException
import json

from endpoints.chats.admin_chat import (
    transfer_chat, assign_lawyer, update_operator_status, close_chat,
    update_queue_priority, get_detailed_queue, get_detailed_operators,
    get_active_chats, get_admin_stats, remove_client_from_queue,
    check_admin_permissions
)
from tests.conftest import TEST_USER_ID, TEST_CLIENT_ID, TEST_OPERATOR_ID, TEST_CHAT_ID, TEST_ADMIN_ID


class TestAdminPermissions:
    """Тесты для проверки административных прав"""
    
    async def test_check_admin_permissions_success(self):
        """Тест успешной проверки административных прав"""
        mock_user = MagicMock()
        mock_user.is_admin = True
        
        result = await check_admin_permissions(mock_user)
        assert result == mock_user
    
    async def test_check_admin_permissions_failure(self):
        """Тест неуспешной проверки административных прав"""
        mock_user = MagicMock()
        mock_user.is_admin = False
        
        with pytest.raises(HTTPException) as exc_info:
            await check_admin_permissions(mock_user)
        
        assert exc_info.value.status_code == 403
        assert "Недостаточно прав" in exc_info.value.detail


class TestTransferChat:
    """Тесты для принудительного перевода чата"""
    
    @pytest_asyncio.fixture
    async def mock_admin_user(self):
        """Создает мок администратора"""
        user = MagicMock()
        user.id = TEST_ADMIN_ID
        user.is_admin = True
        return user
    
    @pytest_asyncio.fixture
    async def mock_dependencies(self):
        """Создает моки для зависимостей"""
        with patch('endpoints.chats.admin_chat.assignment_manager') as mock_assignment:
            mock_assignment.get_chat_operator.return_value = TEST_OPERATOR_ID
            mock_assignment.is_operator_available.return_value = True
            mock_assignment.force_transfer_chat.return_value = True
            yield mock_assignment
    
    async def test_transfer_chat_success(self, mock_admin_user, mock_dependencies):
        """Тест успешного перевода чата"""
        from endpoints.chats.admin_chat import TransferChatRequest
        
        request = TransferChatRequest(
            chat_id=TEST_CHAT_ID,
            target_operator_id=999,
            reason="test transfer"
        )
        
        result = await transfer_chat(request, mock_admin_user)
        
        # Проверяем результат
        assert result["message"] == "Чат успешно переведен"
        assert result["chat_id"] == TEST_CHAT_ID
        assert result["from_operator"] == TEST_OPERATOR_ID
        assert result["to_operator"] == 999
        assert result["reason"] == "test transfer"
        
        # Проверяем вызовы
        mock_dependencies.get_chat_operator.assert_called_once_with(TEST_CHAT_ID)
        mock_dependencies.is_operator_available.assert_called_once_with(999)
        mock_dependencies.force_transfer_chat.assert_called_once_with(
            TEST_CHAT_ID, 999, TEST_OPERATOR_ID, TEST_ADMIN_ID, "test transfer"
        )
    
    async def test_transfer_chat_not_found(self, mock_admin_user, mock_dependencies):
        """Тест перевода несуществующего чата"""
        from endpoints.chats.admin_chat import TransferChatRequest
        
        # Настраиваем что чат не найден
        mock_dependencies.get_chat_operator.return_value = None
        
        request = TransferChatRequest(
            chat_id=TEST_CHAT_ID,
            target_operator_id=999,
            reason="test transfer"
        )
        
        with pytest.raises(HTTPException) as exc_info:
            await transfer_chat(request, mock_admin_user)
        
        assert exc_info.value.status_code == 404
        assert "Чат не найден" in exc_info.value.detail
    
    async def test_transfer_chat_operator_unavailable(self, mock_admin_user, mock_dependencies):
        """Тест перевода чата недоступному оператору"""
        from endpoints.chats.admin_chat import TransferChatRequest
        
        # Настраиваем недоступного оператора
        mock_dependencies.is_operator_available.return_value = False
        
        request = TransferChatRequest(
            chat_id=TEST_CHAT_ID,
            target_operator_id=999,
            reason="test transfer"
        )
        
        with pytest.raises(HTTPException) as exc_info:
            await transfer_chat(request, mock_admin_user)
        
        assert exc_info.value.status_code == 400
        assert "недоступен" in exc_info.value.detail
    
    async def test_transfer_chat_failure(self, mock_admin_user, mock_dependencies):
        """Тест неуспешного перевода чата"""
        from endpoints.chats.admin_chat import TransferChatRequest
        
        # Настраиваем неуспешный перевод
        mock_dependencies.force_transfer_chat.return_value = False
        
        request = TransferChatRequest(
            chat_id=TEST_CHAT_ID,
            target_operator_id=999,
            reason="test transfer"
        )
        
        with pytest.raises(HTTPException) as exc_info:
            await transfer_chat(request, mock_admin_user)
        
        assert exc_info.value.status_code == 500
        assert "Не удалось выполнить перевод" in exc_info.value.detail


class TestAssignLawyer:
    """Тесты для назначения персонального юриста"""
    
    @pytest_asyncio.fixture
    async def mock_admin_user(self):
        """Создает мок администратора"""
        user = MagicMock()
        user.id = TEST_ADMIN_ID
        user.is_admin = True
        return user
    
    @pytest_asyncio.fixture
    async def mock_dependencies(self):
        """Создает моки для зависимостей"""
        with patch('endpoints.chats.admin_chat.assignment_manager') as mock_assignment:
            mock_assignment.get_client_lawyer.return_value = None
            mock_assignment.assign_personal_lawyer.return_value = 888  # chat_id
            yield mock_assignment
    
    async def test_assign_lawyer_success(self, mock_admin_user, mock_dependencies):
        """Тест успешного назначения юриста"""
        from endpoints.chats.admin_chat import AssignLawyerRequest
        
        request = AssignLawyerRequest(
            client_id=TEST_CLIENT_ID,
            lawyer_id=999
        )
        
        result = await assign_lawyer(request, mock_admin_user)
        
        # Проверяем результат
        assert result["message"] == "Юрист успешно назначен"
        assert result["client_id"] == TEST_CLIENT_ID
        assert result["lawyer_id"] == 999
        assert result["lawyer_chat_id"] == 888
        
        # Проверяем вызовы
        mock_dependencies.get_client_lawyer.assert_called_once_with(TEST_CLIENT_ID)
        mock_dependencies.assign_personal_lawyer.assert_called_once_with(
            TEST_CLIENT_ID, 999, TEST_ADMIN_ID
        )
    
    async def test_assign_lawyer_already_assigned(self, mock_admin_user, mock_dependencies):
        """Тест назначения юриста когда уже есть назначение"""
        from endpoints.chats.admin_chat import AssignLawyerRequest
        
        # Настраиваем существующего юриста
        mock_dependencies.get_client_lawyer.return_value = 888
        
        request = AssignLawyerRequest(
            client_id=TEST_CLIENT_ID,
            lawyer_id=999
        )
        
        with pytest.raises(HTTPException) as exc_info:
            await assign_lawyer(request, mock_admin_user)
        
        assert exc_info.value.status_code == 400
        assert "уже назначен юрист" in exc_info.value.detail
    
    async def test_assign_lawyer_failure(self, mock_admin_user, mock_dependencies):
        """Тест неуспешного назначения юриста"""
        from endpoints.chats.admin_chat import AssignLawyerRequest
        
        # Настраиваем неуспешное назначение
        mock_dependencies.assign_personal_lawyer.return_value = None
        
        request = AssignLawyerRequest(
            client_id=TEST_CLIENT_ID,
            lawyer_id=999
        )
        
        with pytest.raises(HTTPException) as exc_info:
            await assign_lawyer(request, mock_admin_user)
        
        assert exc_info.value.status_code == 500
        assert "Не удалось назначить юриста" in exc_info.value.detail


class TestUpdateOperatorStatus:
    """Тесты для изменения статуса оператора"""
    
    @pytest_asyncio.fixture
    async def mock_admin_user(self):
        """Создает мок администратора"""
        user = MagicMock()
        user.id = TEST_ADMIN_ID
        user.is_admin = True
        return user
    
    @pytest_asyncio.fixture
    async def mock_dependencies(self):
        """Создает моки для зависимостей"""
        with patch('endpoints.chats.admin_chat.assignment_manager') as mock_assignment, \
             patch('endpoints.chats.admin_chat.queue_manager') as mock_queue:
            
            mock_assignment.get_operator_type.return_value = "support"
            mock_assignment.set_operator_online = AsyncMock()
            mock_assignment.set_operator_offline = AsyncMock()
            mock_queue.set_operator_busy = AsyncMock()
            
            yield {'assignment': mock_assignment, 'queue': mock_queue}
    
    async def test_update_operator_status_online(self, mock_admin_user, mock_dependencies):
        """Тест перевода оператора в онлайн"""
        from endpoints.chats.admin_chat import UpdateOperatorStatusRequest
        
        request = UpdateOperatorStatusRequest(
            operator_id=TEST_OPERATOR_ID,
            status="online",
            max_concurrent_chats=10
        )
        
        result = await update_operator_status(request, mock_admin_user)
        
        # Проверяем результат
        assert result["message"] == "Статус оператора обновлен"
        assert result["operator_id"] == TEST_OPERATOR_ID
        assert result["status"] == "online"
        
        # Проверяем вызовы
        mock_dependencies['assignment'].set_operator_online.assert_called_once_with(
            TEST_OPERATOR_ID, "support", 10
        )
    
    async def test_update_operator_status_offline(self, mock_admin_user, mock_dependencies):
        """Тест перевода оператора в оффлайн"""
        from endpoints.chats.admin_chat import UpdateOperatorStatusRequest
        
        request = UpdateOperatorStatusRequest(
            operator_id=TEST_OPERATOR_ID,
            status="offline"
        )
        
        result = await update_operator_status(request, mock_admin_user)
        
        # Проверяем результат
        assert result["status"] == "offline"
        
        # Проверяем вызовы
        mock_dependencies['assignment'].set_operator_offline.assert_called_once_with(TEST_OPERATOR_ID)
    
    async def test_update_operator_status_busy(self, mock_admin_user, mock_dependencies):
        """Тест установки статуса занят"""
        from endpoints.chats.admin_chat import UpdateOperatorStatusRequest
        
        request = UpdateOperatorStatusRequest(
            operator_id=TEST_OPERATOR_ID,
            status="busy"
        )
        
        result = await update_operator_status(request, mock_admin_user)
        
        # Проверяем вызовы
        mock_dependencies['queue'].set_operator_busy.assert_called_once_with(TEST_OPERATOR_ID, True)
    
    async def test_update_operator_status_available(self, mock_admin_user, mock_dependencies):
        """Тест установки статуса доступен"""
        from endpoints.chats.admin_chat import UpdateOperatorStatusRequest
        
        request = UpdateOperatorStatusRequest(
            operator_id=TEST_OPERATOR_ID,
            status="available"
        )
        
        result = await update_operator_status(request, mock_admin_user)
        
        # Проверяем вызовы
        mock_dependencies['queue'].set_operator_busy.assert_called_once_with(TEST_OPERATOR_ID, False)
    
    async def test_update_operator_status_invalid(self, mock_admin_user, mock_dependencies):
        """Тест некорректного статуса"""
        from endpoints.chats.admin_chat import UpdateOperatorStatusRequest
        
        request = UpdateOperatorStatusRequest(
            operator_id=TEST_OPERATOR_ID,
            status="invalid_status"
        )
        
        with pytest.raises(HTTPException) as exc_info:
            await update_operator_status(request, mock_admin_user)
        
        assert exc_info.value.status_code == 400
        assert "Неверный статус" in exc_info.value.detail


class TestCloseChat:
    """Тесты для принудительного закрытия чата"""
    
    @pytest_asyncio.fixture
    async def mock_admin_user(self):
        """Создает мок администратора"""
        user = MagicMock()
        user.id = TEST_ADMIN_ID
        user.is_admin = True
        return user
    
    @pytest_asyncio.fixture
    async def mock_dependencies(self):
        """Создает моки для зависимостей"""
        with patch('endpoints.chats.admin_chat.assignment_manager') as mock_assignment:
            mock_assignment.force_close_chat.return_value = True
            yield mock_assignment
    
    async def test_close_chat_success(self, mock_admin_user, mock_dependencies):
        """Тест успешного закрытия чата"""
        from endpoints.chats.admin_chat import CloseChatRequest
        
        request = CloseChatRequest(
            chat_id=TEST_CHAT_ID,
            reason="admin decision"
        )
        
        result = await close_chat(request, mock_admin_user)
        
        # Проверяем результат
        assert result["message"] == "Чат успешно закрыт"
        assert result["chat_id"] == TEST_CHAT_ID
        assert result["reason"] == "admin decision"
        
        # Проверяем вызовы
        mock_dependencies.force_close_chat.assert_called_once_with(
            TEST_CHAT_ID, TEST_ADMIN_ID, "admin decision"
        )
    
    async def test_close_chat_failure(self, mock_admin_user, mock_dependencies):
        """Тест неуспешного закрытия чата"""
        from endpoints.chats.admin_chat import CloseChatRequest
        
        # Настраиваем неуспешное закрытие
        mock_dependencies.force_close_chat.return_value = False
        
        request = CloseChatRequest(
            chat_id=TEST_CHAT_ID,
            reason="admin decision"
        )
        
        with pytest.raises(HTTPException) as exc_info:
            await close_chat(request, mock_admin_user)
        
        assert exc_info.value.status_code == 500
        assert "Не удалось закрыть чат" in exc_info.value.detail


class TestUpdateQueuePriority:
    """Тесты для изменения приоритета в очереди"""
    
    @pytest_asyncio.fixture
    async def mock_admin_user(self):
        """Создает мок администратора"""
        user = MagicMock()
        user.id = TEST_ADMIN_ID
        user.is_admin = True
        return user
    
    @pytest_asyncio.fixture
    async def mock_dependencies(self):
        """Создает моки для зависимостей"""
        with patch('endpoints.chats.admin_chat.queue_manager') as mock_queue:
            # Добавляем клиента в очередь
            mock_client = MagicMock()
            mock_queue.waiting_clients = {TEST_CLIENT_ID: mock_client}
            mock_queue.update_queue_position.return_value = 3
            yield mock_queue
    
    async def test_update_queue_priority_success(self, mock_admin_user, mock_dependencies):
        """Тест успешного обновления приоритета"""
        from endpoints.chats.admin_chat import QueuePriorityRequest
        
        request = QueuePriorityRequest(
            client_id=TEST_CLIENT_ID,
            priority=5
        )
        
        result = await update_queue_priority(request, mock_admin_user)
        
        # Проверяем результат
        assert result["message"] == "Приоритет в очереди обновлен"
        assert result["client_id"] == TEST_CLIENT_ID
        assert result["new_priority"] == 5
        assert result["new_position"] == 3
        
        # Проверяем вызовы
        mock_dependencies.update_queue_position.assert_called_once_with(TEST_CLIENT_ID, 5)
    
    async def test_update_queue_priority_client_not_found(self, mock_admin_user, mock_dependencies):
        """Тест обновления приоритета для несуществующего клиента"""
        from endpoints.chats.admin_chat import QueuePriorityRequest
        
        # Настраиваем пустую очередь
        mock_dependencies.waiting_clients = {}
        
        request = QueuePriorityRequest(
            client_id=999,
            priority=5
        )
        
        with pytest.raises(HTTPException) as exc_info:
            await update_queue_priority(request, mock_admin_user)
        
        assert exc_info.value.status_code == 404
        assert "Клиент не найден в очереди" in exc_info.value.detail


class TestGetDetailedQueue:
    """Тесты для получения детальной информации об очереди"""
    
    @pytest_asyncio.fixture
    async def mock_admin_user(self):
        """Создает мок администратора"""
        user = MagicMock()
        user.id = TEST_ADMIN_ID
        user.is_admin = True
        return user
    
    @pytest_asyncio.fixture
    async def mock_dependencies(self):
        """Создает моки для зависимостей"""
        with patch('endpoints.chats.admin_chat.queue_manager') as mock_queue:
            # Настраиваем очередь клиентов
            mock_client1 = MagicMock()
            mock_client1.client_id = 1
            mock_client1.chat_id = 101
            mock_client1.wait_time = 60
            mock_client1.priority = 1
            mock_client1.timestamp = MagicMock()
            mock_client1.timestamp.isoformat.return_value = "2023-01-01T12:00:00Z"
            mock_client1.metadata = {"urgency": "high"}
            
            mock_client2 = MagicMock()
            mock_client2.client_id = 2
            mock_client2.chat_id = 102
            mock_client2.wait_time = 30
            mock_client2.priority = 0
            mock_client2.timestamp = MagicMock()
            mock_client2.timestamp.isoformat.return_value = "2023-01-01T12:01:00Z"
            mock_client2.metadata = {}
            
            mock_queue.waiting_clients = {1: mock_client1, 2: mock_client2}
            mock_queue.get_queue_position = AsyncMock(side_effect=lambda x: 1 if x == 1 else 2)
            mock_queue.get_available_operators.return_value = []  # 0 операторов
            mock_queue.get_queue_status.return_value = {"test": "data"}
            
            yield mock_queue
    
    async def test_get_detailed_queue(self, mock_admin_user, mock_dependencies):
        """Тест получения детальной очереди"""
        result = await get_detailed_queue(mock_admin_user)
        
        # Проверяем структуру ответа
        assert "queue" in result
        assert "total_waiting" in result
        assert "available_operators" in result
        assert "queue_stats" in result
        
        # Проверяем данные очереди
        queue = result["queue"]
        assert len(queue) == 2
        
        # Проверяем что очередь отсортирована по позиции
        assert queue[0]["client_id"] == 1  # позиция 1
        assert queue[1]["client_id"] == 2  # позиция 2
        
        # Проверяем данные первого клиента
        first_client = queue[0]
        assert first_client["chat_id"] == 101
        assert first_client["wait_time"] == 60
        assert first_client["priority"] == 1
        assert first_client["position"] == 1
        assert first_client["metadata"] == {"urgency": "high"}
        
        # Проверяем общие данные
        assert result["total_waiting"] == 2
        assert result["available_operators"] == 0


class TestGetDetailedOperators:
    """Тесты для получения детальной информации об операторах"""
    
    @pytest_asyncio.fixture
    async def mock_admin_user(self):
        """Создает мок администратора"""
        user = MagicMock()
        user.id = TEST_ADMIN_ID
        user.is_admin = True
        return user
    
    @pytest_asyncio.fixture
    async def mock_dependencies(self):
        """Создает моки для зависимостей"""
        with patch('endpoints.chats.admin_chat.queue_manager') as mock_queue, \
             patch('endpoints.chats.admin_chat.assignment_manager') as mock_assignment:
            
            # Настраиваем операторов
            mock_operator1 = MagicMock()
            mock_operator1.operator_id = 1
            mock_operator1.operator_type = "support"
            mock_operator1.is_online = True
            mock_operator1.is_available = True
            mock_operator1.current_chats = {101, 102}
            mock_operator1.max_concurrent_chats = 5
            mock_operator1.can_accept_chat = True
            mock_operator1.last_activity = MagicMock()
            mock_operator1.last_activity.isoformat.return_value = "2023-01-01T12:00:00Z"
            
            mock_operator2 = MagicMock()
            mock_operator2.operator_id = 2
            mock_operator2.operator_type = "lawyer"
            mock_operator2.is_online = False
            mock_operator2.is_available = False
            mock_operator2.current_chats = set()
            mock_operator2.max_concurrent_chats = 3
            mock_operator2.can_accept_chat = False
            mock_operator2.last_activity = MagicMock()
            mock_operator2.last_activity.isoformat.return_value = "2023-01-01T11:00:00Z"
            
            mock_queue.operators = {1: mock_operator1, 2: mock_operator2}
            mock_assignment.get_operator_chats.return_value = [101, 102]
            
            yield {'queue': mock_queue, 'assignment': mock_assignment}
    
    async def test_get_detailed_operators(self, mock_admin_user, mock_dependencies):
        """Тест получения детальной информации об операторах"""
        result = await get_detailed_operators(mock_admin_user)
        
        # Проверяем структуру ответа
        assert "operators" in result
        assert "total_operators" in result
        assert "online_operators" in result
        assert "available_operators" in result
        
        # Проверяем данные операторов
        operators = result["operators"]
        assert len(operators) == 2
        
        # Проверяем данные первого оператора
        operator1 = next(op for op in operators if op["operator_id"] == 1)
        assert operator1["operator_type"] == "support"
        assert operator1["is_online"] is True
        assert operator1["is_available"] is True
        assert operator1["current_chats"] == [101, 102]
        assert operator1["current_chats_count"] == 2
        assert operator1["max_concurrent_chats"] == 5
        assert operator1["utilization"] == 0.4  # 2/5
        assert operator1["can_accept_chat"] is True
        
        # Проверяем общие данные
        assert result["total_operators"] == 2
        assert result["online_operators"] == 1
        assert result["available_operators"] == 1


class TestGetActiveChats:
    """Тесты для получения информации об активных чатах"""
    
    @pytest_asyncio.fixture
    async def mock_admin_user(self):
        """Создает мок администратора"""
        user = MagicMock()
        user.id = TEST_ADMIN_ID
        user.is_admin = True
        return user
    
    @pytest_asyncio.fixture
    async def mock_dependencies(self):
        """Создает моки для зависимостей"""
        with patch('endpoints.chats.admin_chat.queue_manager') as mock_queue, \
             patch('endpoints.chats.admin_chat.chat_db') as mock_chat_db, \
             patch('endpoints.chats.admin_chat.websocket_manager') as mock_ws_manager:
            
            # Настраиваем назначения чатов
            mock_queue.chat_assignments = {101: 1, 102: 2}
            
            # Настраиваем чаты в БД
            mock_chat1 = MagicMock()
            mock_chat1.user_id = TEST_CLIENT_ID
            mock_chat1.date_created = MagicMock()
            mock_chat1.date_created.isoformat.return_value = "2023-01-01T12:00:00Z"
            mock_chat1.active = True
            mock_chat1.resolved = False
            
            mock_chat2 = MagicMock()
            mock_chat2.user_id = 456
            mock_chat2.date_created = MagicMock()
            mock_chat2.date_created.isoformat.return_value = "2023-01-01T13:00:00Z"
            mock_chat2.active = True
            mock_chat2.resolved = False
            
            mock_chat_db.get_chat_by_id.side_effect = lambda chat_id: mock_chat1 if chat_id == 101 else mock_chat2
            
            # Настраиваем участников WebSocket
            mock_ws_manager.get_chat_participants.side_effect = lambda chat_id: {1, 2} if chat_id == 101 else {3}
            
            yield {
                'queue': mock_queue,
                'chat_db': mock_chat_db,
                'ws_manager': mock_ws_manager
            }
    
    async def test_get_active_chats(self, mock_admin_user, mock_dependencies):
        """Тест получения активных чатов"""
        result = await get_active_chats(mock_admin_user)
        
        # Проверяем структуру ответа
        assert "active_chats" in result
        assert "total_chats" in result
        
        # Проверяем данные чатов
        chats = result["active_chats"]
        assert len(chats) == 2
        
        # Проверяем данные первого чата
        chat1 = next(chat for chat in chats if chat["chat_id"] == 101)
        assert chat1["client_id"] == TEST_CLIENT_ID
        assert chat1["operator_id"] == 1
        assert chat1["active"] is True
        assert chat1["resolved"] is False
        assert chat1["online_participants"] == [1, 2]
        assert chat1["participants_count"] == 2
        
        # Проверяем общие данные
        assert result["total_chats"] == 2


class TestRemoveClientFromQueue:
    """Тесты для удаления клиента из очереди"""
    
    @pytest_asyncio.fixture
    async def mock_admin_user(self):
        """Создает мок администратора"""
        user = MagicMock()
        user.id = TEST_ADMIN_ID
        user.is_admin = True
        return user
    
    @pytest_asyncio.fixture
    async def mock_dependencies(self):
        """Создает моки для зависимостей"""
        with patch('endpoints.chats.admin_chat.queue_manager') as mock_queue:
            mock_queue.remove_client_from_queue.return_value = True
            yield mock_queue
    
    async def test_remove_client_from_queue_success(self, mock_admin_user, mock_dependencies):
        """Тест успешного удаления клиента из очереди"""
        result = await remove_client_from_queue(TEST_CLIENT_ID, mock_admin_user)
        
        # Проверяем результат
        assert result["message"] == "Клиент удален из очереди"
        assert result["client_id"] == TEST_CLIENT_ID
        
        # Проверяем вызовы
        mock_dependencies.remove_client_from_queue.assert_called_once_with(TEST_CLIENT_ID)
    
    async def test_remove_client_from_queue_not_found(self, mock_admin_user, mock_dependencies):
        """Тест удаления несуществующего клиента из очереди"""
        # Настраиваем что клиент не найден
        mock_dependencies.remove_client_from_queue.return_value = False
        
        with pytest.raises(HTTPException) as exc_info:
            await remove_client_from_queue(999, mock_admin_user)
        
        assert exc_info.value.status_code == 404
        assert "Клиент не найден в очереди" in exc_info.value.detail


class TestGetAdminStats:
    """Тесты для получения общей статистики"""
    
    @pytest_asyncio.fixture
    async def mock_admin_user(self):
        """Создает мок администратора"""
        user = MagicMock()
        user.id = TEST_ADMIN_ID
        user.is_admin = True
        return user
    
    @pytest_asyncio.fixture
    async def mock_dependencies(self):
        """Создает моки для зависимостей"""
        with patch('endpoints.chats.admin_chat.queue_manager') as mock_queue, \
             patch('endpoints.chats.admin_chat.assignment_manager') as mock_assignment, \
             patch('endpoints.chats.admin_chat.websocket_manager') as mock_ws_manager:
            
            # Настраиваем операторов
            mock_operator1 = MagicMock()
            mock_operator1.is_online = True
            mock_operator1.is_available = True
            
            mock_operator2 = MagicMock()
            mock_operator2.is_online = True
            mock_operator2.is_available = False
            
            mock_operator3 = MagicMock()
            mock_operator3.is_online = False
            mock_operator3.is_available = False
            
            mock_queue.operators = {1: mock_operator1, 2: mock_operator2, 3: mock_operator3}
            mock_queue.get_available_operators.return_value = [mock_operator1]
            mock_queue.get_queue_status.return_value = {"queue": "stats"}
            
            mock_assignment.get_assignment_stats.return_value = {"assignment": "stats"}
            mock_ws_manager.get_connection_stats.return_value = {"connection": "stats"}
            
            yield {
                'queue': mock_queue,
                'assignment': mock_assignment,
                'ws_manager': mock_ws_manager
            }
    
    async def test_get_admin_stats(self, mock_admin_user, mock_dependencies):
        """Тест получения общей статистики для администратора"""
        result = await get_admin_stats(mock_admin_user)
        
        # Проверяем структуру ответа
        assert "queue" in result
        assert "assignments" in result
        assert "connections" in result
        assert "operators_summary" in result
        
        # Проверяем данные
        assert result["queue"] == {"queue": "stats"}
        assert result["assignments"] == {"assignment": "stats"}
        assert result["connections"] == {"connection": "stats"}
        
        # Проверяем сводку по операторам
        operators_summary = result["operators_summary"]
        assert operators_summary["total"] == 3
        assert operators_summary["online"] == 2
        assert operators_summary["available"] == 1
        assert operators_summary["busy"] == 1
