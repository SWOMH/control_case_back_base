"""
Тесты для WebSocket Manager - управление WebSocket соединениями
"""
import pytest
import pytest_asyncio
import asyncio
from unittest.mock import AsyncMock, MagicMock

from utils.websocket_manager import WebSocketConnectionManager


class TestWebSocketConnectionManager:
    """Тесты для WebSocketConnectionManager"""
    
    @pytest_asyncio.fixture
    async def websocket_manager(self):
        """Создает менеджер WebSocket соединений для тестов"""
        return WebSocketConnectionManager()
    
    @pytest_asyncio.fixture
    async def mock_websocket(self):
        """Создает мок WebSocket соединения"""
        websocket = AsyncMock()
        websocket.accept = AsyncMock()
        websocket.send_json = AsyncMock()
        websocket.close = AsyncMock()
        return websocket
    
    async def test_websocket_manager_initialization(self, websocket_manager):
        """Тест инициализации менеджера WebSocket"""
        assert websocket_manager.user_connections == {}
        assert websocket_manager.chat_connections == {}
        assert websocket_manager.operator_connections == {}
        assert websocket_manager.role_connections == {
            'support': set(),
            'lawyer': set(),
            'salesman': set(),
            'admin': set()
        }
        assert websocket_manager.connection_metadata == {}
    
    async def test_connect_user_new_connection(self, websocket_manager, mock_websocket):
        """Тест подключения нового пользователя"""
        user_id = 123
        user_role = "support"
        metadata = {"test": "data"}
        
        await websocket_manager.connect_user(user_id, mock_websocket, user_role, metadata)
        
        # Проверяем что соединение установлено
        assert user_id in websocket_manager.user_connections
        assert websocket_manager.user_connections[user_id] == mock_websocket
        
        # Проверяем метаданные
        assert user_id in websocket_manager.connection_metadata
        assert websocket_manager.connection_metadata[user_id] == metadata
        
        # Проверяем роль
        assert user_id in websocket_manager.role_connections[user_role]
        assert user_id in websocket_manager.operator_connections
        
        # Проверяем что WebSocket был принят
        mock_websocket.accept.assert_called_once()
    
    async def test_connect_user_replace_existing(self, websocket_manager, mock_websocket):
        """Тест замены существующего соединения пользователя"""
        user_id = 123
        user_role = "support"
        
        # Создаем старое соединение
        old_websocket = AsyncMock()
        websocket_manager.user_connections[user_id] = old_websocket
        
        # Подключаем нового
        await websocket_manager.connect_user(user_id, mock_websocket, user_role)
        
        # Проверяем что старое соединение было закрыто
        old_websocket.close.assert_called_once()
        
        # Проверяем что новое соединение установлено
        assert websocket_manager.user_connections[user_id] == mock_websocket
    
    async def test_connect_user_different_roles(self, websocket_manager, mock_websocket):
        """Тест подключения пользователей с разными ролями"""
        # Клиент
        client_id = 123
        await websocket_manager.connect_user(client_id, mock_websocket, "client")
        
        assert client_id in websocket_manager.user_connections
        assert client_id not in websocket_manager.operator_connections  # клиент не оператор
        
        # Оператор поддержки
        support_id = 456
        support_websocket = AsyncMock()
        await websocket_manager.connect_user(support_id, support_websocket, "support")
        
        assert support_id in websocket_manager.user_connections
        assert support_id in websocket_manager.operator_connections
        assert support_id in websocket_manager.role_connections["support"]
        
        # Юрист
        lawyer_id = 789
        lawyer_websocket = AsyncMock()
        await websocket_manager.connect_user(lawyer_id, lawyer_websocket, "lawyer")
        
        assert lawyer_id in websocket_manager.operator_connections
        assert lawyer_id in websocket_manager.role_connections["lawyer"]
    
    async def test_disconnect_user(self, websocket_manager, mock_websocket):
        """Тест отключения пользователя"""
        user_id = 123
        user_role = "support"
        chat_id = 456
        
        # Подключаем пользователя
        await websocket_manager.connect_user(user_id, mock_websocket, user_role)
        await websocket_manager.join_chat(user_id, chat_id)
        
        # Отключаем пользователя
        await websocket_manager.disconnect_user(user_id)
        
        # Проверяем что все связи удалены
        assert user_id not in websocket_manager.user_connections
        assert user_id not in websocket_manager.connection_metadata
        assert user_id not in websocket_manager.operator_connections
        assert user_id not in websocket_manager.role_connections[user_role]
        assert user_id not in websocket_manager.chat_connections.get(chat_id, set())
    
    async def test_join_chat(self, websocket_manager):
        """Тест присоединения к чату"""
        user_id = 123
        chat_id = 456
        
        await websocket_manager.join_chat(user_id, chat_id)
        
        # Проверяем что пользователь добавлен в чат
        assert chat_id in websocket_manager.chat_connections
        assert user_id in websocket_manager.chat_connections[chat_id]
    
    async def test_join_chat_multiple_users(self, websocket_manager):
        """Тест присоединения нескольких пользователей к одному чату"""
        chat_id = 456
        user_ids = [123, 456, 789]
        
        for user_id in user_ids:
            await websocket_manager.join_chat(user_id, chat_id)
        
        # Проверяем что все пользователи в чате
        assert chat_id in websocket_manager.chat_connections
        assert websocket_manager.chat_connections[chat_id] == set(user_ids)
    
    async def test_leave_chat(self, websocket_manager):
        """Тест выхода из чата"""
        user_id = 123
        chat_id = 456
        
        # Присоединяемся к чату
        await websocket_manager.join_chat(user_id, chat_id)
        
        # Выходим из чата
        await websocket_manager.leave_chat(user_id, chat_id)
        
        # Проверяем что пользователь удален из чата
        assert user_id not in websocket_manager.chat_connections.get(chat_id, set())
    
    async def test_leave_chat_remove_empty_chat(self, websocket_manager):
        """Тест удаления пустого чата при выходе последнего участника"""
        user_id = 123
        chat_id = 456
        
        # Присоединяемся к чату
        await websocket_manager.join_chat(user_id, chat_id)
        
        # Выходим из чата (последний участник)
        await websocket_manager.leave_chat(user_id, chat_id)
        
        # Проверяем что чат удален
        assert chat_id not in websocket_manager.chat_connections
    
    async def test_send_to_user_success(self, websocket_manager, mock_websocket):
        """Тест успешной отправки сообщения пользователю"""
        user_id = 123
        message = {"type": "test", "payload": {"data": "test"}}
        
        # Подключаем пользователя
        await websocket_manager.connect_user(user_id, mock_websocket, "client")
        
        # Отправляем сообщение
        result = await websocket_manager.send_to_user(user_id, message)
        
        assert result is True
        mock_websocket.send_json.assert_called_once_with(message)
    
    async def test_send_to_user_connection_error(self, websocket_manager, mock_websocket):
        """Тест обработки ошибки соединения при отправке сообщения"""
        user_id = 123
        message = {"type": "test"}
        
        # Подключаем пользователя
        await websocket_manager.connect_user(user_id, mock_websocket, "client")
        
        # Настраиваем ошибку при отправке
        mock_websocket.send_json.side_effect = Exception("Connection error")
        
        # Отправляем сообщение
        result = await websocket_manager.send_to_user(user_id, message)
        
        assert result is False
        # Проверяем что пользователь был отключен
        assert user_id not in websocket_manager.user_connections
    
    async def test_send_to_user_not_connected(self, websocket_manager):
        """Тест отправки сообщения неподключенному пользователю"""
        user_id = 123
        message = {"type": "test"}
        
        result = await websocket_manager.send_to_user(user_id, message)
        assert result is False
    
    async def test_broadcast_to_chat(self, websocket_manager):
        """Тест рассылки сообщения участникам чата"""
        chat_id = 456
        user_ids = [123, 789, 999]
        message = {"type": "test", "payload": {"data": "broadcast"}}
        
        # Подключаем пользователей и добавляем в чат
        websockets = {}
        for user_id in user_ids:
            websocket = AsyncMock()
            websockets[user_id] = websocket
            await websocket_manager.connect_user(user_id, websocket, "client")
            await websocket_manager.join_chat(user_id, chat_id)
        
        # Рассылаем сообщение
        await websocket_manager.broadcast_to_chat(chat_id, message)
        
        # Проверяем что всем отправлено
        for user_id in user_ids:
            websockets[user_id].send_json.assert_called_once_with(message)
    
    async def test_broadcast_to_chat_exclude_user(self, websocket_manager):
        """Тест рассылки сообщения с исключением пользователя"""
        chat_id = 456
        user_ids = [123, 789, 999]
        exclude_user = 789
        message = {"type": "test"}
        
        # Подключаем пользователей и добавляем в чат
        websockets = {}
        for user_id in user_ids:
            websocket = AsyncMock()
            websockets[user_id] = websocket
            await websocket_manager.connect_user(user_id, websocket, "client")
            await websocket_manager.join_chat(user_id, chat_id)
        
        # Рассылаем сообщение с исключением
        await websocket_manager.broadcast_to_chat(chat_id, message, exclude_user=exclude_user)
        
        # Проверяем что исключенному не отправлено
        websockets[exclude_user].send_json.assert_not_called()
        
        # Проверяем что остальным отправлено
        for user_id in user_ids:
            if user_id != exclude_user:
                websockets[user_id].send_json.assert_called_once_with(message)
    
    async def test_broadcast_to_role(self, websocket_manager):
        """Тест рассылки сообщения по роли"""
        role = "support"
        user_ids = [123, 456, 789]
        message = {"type": "role_message"}
        
        # Подключаем пользователей с указанной ролью
        websockets = {}
        for user_id in user_ids:
            websocket = AsyncMock()
            websockets[user_id] = websocket
            await websocket_manager.connect_user(user_id, websocket, role)
        
        # Рассылаем сообщение по роли
        await websocket_manager.broadcast_to_role(role, message)
        
        # Проверяем что всем отправлено
        for user_id in user_ids:
            websockets[user_id].send_json.assert_called_once_with(message)
    
    async def test_broadcast_to_role_exclude_user(self, websocket_manager):
        """Тест рассылки сообщения по роли с исключением пользователя"""
        role = "support"
        user_ids = [123, 456, 789]
        exclude_user = 456
        message = {"type": "role_message"}
        
        # Подключаем пользователей
        websockets = {}
        for user_id in user_ids:
            websocket = AsyncMock()
            websockets[user_id] = websocket
            await websocket_manager.connect_user(user_id, websocket, role)
        
        # Рассылаем с исключением
        await websocket_manager.broadcast_to_role(role, message, exclude_user=exclude_user)
        
        # Проверяем исключение
        websockets[exclude_user].send_json.assert_not_called()
        
        # Проверяем отправку остальным
        for user_id in user_ids:
            if user_id != exclude_user:
                websockets[user_id].send_json.assert_called_once_with(message)
    
    async def test_broadcast_to_operators(self, websocket_manager):
        """Тест рассылки сообщения операторам"""
        message = {"type": "operator_message"}
        
        # Подключаем операторов разных типов
        support_websocket = AsyncMock()
        lawyer_websocket = AsyncMock()
        salesman_websocket = AsyncMock()
        client_websocket = AsyncMock()
        
        await websocket_manager.connect_user(1, support_websocket, "support")
        await websocket_manager.connect_user(2, lawyer_websocket, "lawyer")
        await websocket_manager.connect_user(3, salesman_websocket, "salesman")
        await websocket_manager.connect_user(4, client_websocket, "client")  # не оператор
        
        # Рассылаем всем операторам
        await websocket_manager.broadcast_to_operators(message)
        
        # Проверяем что всем операторам отправлено
        support_websocket.send_json.assert_called_once_with(message)
        lawyer_websocket.send_json.assert_called_once_with(message)
        salesman_websocket.send_json.assert_called_once_with(message)
        
        # Проверяем что клиенту не отправлено
        client_websocket.send_json.assert_not_called()
    
    async def test_broadcast_to_operators_specific_types(self, websocket_manager):
        """Тест рассылки сообщения только определенным типам операторов"""
        message = {"type": "support_only_message"}
        
        # Подключаем операторов
        support_websocket = AsyncMock()
        lawyer_websocket = AsyncMock()
        
        await websocket_manager.connect_user(1, support_websocket, "support")
        await websocket_manager.connect_user(2, lawyer_websocket, "lawyer")
        
        # Рассылаем только операторам поддержки
        await websocket_manager.broadcast_to_operators(message, operator_types=["support"])
        
        # Проверяем рассылку
        support_websocket.send_json.assert_called_once_with(message)
        lawyer_websocket.send_json.assert_not_called()
    
    async def test_notify_operators_new_chat(self, websocket_manager):
        """Тест уведомления операторов о новом чате"""
        chat_id = 456
        client_id = 123
        
        # Подключаем оператора поддержки
        support_websocket = AsyncMock()
        await websocket_manager.connect_user(1, support_websocket, "support")
        
        # Отправляем уведомление
        await websocket_manager.notify_operators_new_chat(chat_id, client_id)
        
        # Проверяем что уведомление отправлено
        support_websocket.send_json.assert_called_once()
        call_args = support_websocket.send_json.call_args[0][0]
        
        assert call_args['type'] == 'new_chat_available'
        assert call_args['payload']['chat_id'] == chat_id
        assert call_args['payload']['client_id'] == client_id
    
    async def test_hide_client_from_operators(self, websocket_manager):
        """Тест скрытия клиента от других операторов"""
        client_id = 123
        except_operator = 2
        
        # Подключаем операторов
        support1_websocket = AsyncMock()
        support2_websocket = AsyncMock()
        
        await websocket_manager.connect_user(1, support1_websocket, "support")
        await websocket_manager.connect_user(2, support2_websocket, "support")
        
        # Скрываем клиента
        await websocket_manager.hide_client_from_operators(client_id, except_operator=except_operator)
        
        # Проверяем что первому оператору отправлено уведомление
        support1_websocket.send_json.assert_called_once()
        call_args = support1_websocket.send_json.call_args[0][0]
        
        assert call_args['type'] == 'client_taken'
        assert call_args['payload']['client_id'] == client_id
        assert call_args['payload']['taken_by'] == except_operator
        
        # Проверяем что исключенному оператору не отправлено
        support2_websocket.send_json.assert_not_called()
    
    async def test_notify_chat_assigned(self, websocket_manager):
        """Тест уведомления о назначении чата"""
        chat_id = 456
        operator_id = 123
        client_id = 789
        
        # Подключаем оператора и клиента
        operator_websocket = AsyncMock()
        client_websocket = AsyncMock()
        
        await websocket_manager.connect_user(operator_id, operator_websocket, "support")
        await websocket_manager.connect_user(client_id, client_websocket, "client")
        
        # Отправляем уведомление
        await websocket_manager.notify_chat_assigned(chat_id, operator_id, client_id)
        
        # Проверяем уведомления
        operator_websocket.send_json.assert_called_once()
        client_websocket.send_json.assert_called_once()
        
        # Проверяем содержимое уведомлений
        operator_call = operator_websocket.send_json.call_args[0][0]
        client_call = client_websocket.send_json.call_args[0][0]
        
        assert operator_call['type'] == 'chat_assigned'
        assert operator_call['payload']['chat_id'] == chat_id
        assert operator_call['payload']['client_id'] == client_id
        
        assert client_call['type'] == 'operator_assigned'
        assert client_call['payload']['chat_id'] == chat_id
        assert client_call['payload']['operator_id'] == operator_id
        
        # Проверяем что участники добавлены в чат
        assert chat_id in websocket_manager.chat_connections
        assert operator_id in websocket_manager.chat_connections[chat_id]
        assert client_id in websocket_manager.chat_connections[chat_id]
    
    async def test_notify_chat_transferred(self, websocket_manager):
        """Тест уведомления о переводе чата"""
        chat_id = 456
        new_operator_id = 123
        previous_operator_id = 789
        reason = "specialization"
        
        # Подключаем операторов
        new_operator_websocket = AsyncMock()
        previous_operator_websocket = AsyncMock()
        
        await websocket_manager.connect_user(new_operator_id, new_operator_websocket, "support")
        await websocket_manager.connect_user(previous_operator_id, previous_operator_websocket, "support")
        
        # Добавляем старого оператора в чат
        await websocket_manager.join_chat(previous_operator_id, chat_id)
        
        # Отправляем уведомление о переводе
        await websocket_manager.notify_chat_transferred(
            chat_id, new_operator_id, previous_operator_id, reason
        )
        
        # Проверяем уведомления операторов
        new_operator_websocket.send_json.assert_called()
        previous_operator_websocket.send_json.assert_called()
        
        # Проверяем что участники чата обновлены
        assert chat_id in websocket_manager.chat_connections
        assert new_operator_id in websocket_manager.chat_connections[chat_id]
        assert previous_operator_id not in websocket_manager.chat_connections[chat_id]
    
    async def test_notify_lawyer_assigned(self, websocket_manager):
        """Тест уведомления о назначении юриста"""
        client_id = 123
        lawyer_id = 456
        chat_id = 789
        
        # Подключаем клиента и юриста
        client_websocket = AsyncMock()
        lawyer_websocket = AsyncMock()
        
        await websocket_manager.connect_user(client_id, client_websocket, "client")
        await websocket_manager.connect_user(lawyer_id, lawyer_websocket, "lawyer")
        
        # Отправляем уведомление
        await websocket_manager.notify_lawyer_assigned(client_id, lawyer_id, chat_id)
        
        # Проверяем уведомления
        client_websocket.send_json.assert_called_once()
        lawyer_websocket.send_json.assert_called_once()
        
        # Проверяем содержимое
        client_call = client_websocket.send_json.call_args[0][0]
        lawyer_call = lawyer_websocket.send_json.call_args[0][0]
        
        assert client_call['type'] == 'lawyer_assigned'
        assert client_call['payload']['lawyer_id'] == lawyer_id
        
        assert lawyer_call['type'] == 'client_assigned'
        assert lawyer_call['payload']['client_id'] == client_id
        
        # Проверяем участников чата
        assert chat_id in websocket_manager.chat_connections
        assert client_id in websocket_manager.chat_connections[chat_id]
        assert lawyer_id in websocket_manager.chat_connections[chat_id]
    
    async def test_get_connection_stats(self, websocket_manager):
        """Тест получения статистики соединений"""
        # Подключаем пользователей
        await websocket_manager.connect_user(1, AsyncMock(), "support")
        await websocket_manager.connect_user(2, AsyncMock(), "lawyer")
        await websocket_manager.connect_user(3, AsyncMock(), "client")
        
        # Добавляем в чаты
        await websocket_manager.join_chat(1, 101)
        await websocket_manager.join_chat(2, 101)
        await websocket_manager.join_chat(3, 102)
        
        stats = websocket_manager.get_connection_stats()
        
        assert stats['total_connections'] == 3
        assert stats['operator_connections'] == 2  # support + lawyer
        assert stats['active_chats'] == 2
        
        assert stats['connections_by_role']['support'] == 1
        assert stats['connections_by_role']['lawyer'] == 1
        assert stats['connections_by_role']['client'] == 0  # client не в role_connections
        
        assert stats['chat_participants'][101] == 2
        assert stats['chat_participants'][102] == 1
    
    async def test_is_user_online(self, websocket_manager, mock_websocket):
        """Тест проверки онлайн статуса пользователя"""
        user_id = 123
        
        # Пользователь не подключен
        assert not websocket_manager.is_user_online(user_id)
        
        # Подключаем пользователя
        await websocket_manager.connect_user(user_id, mock_websocket, "client")
        assert websocket_manager.is_user_online(user_id)
        
        # Отключаем пользователя
        await websocket_manager.disconnect_user(user_id)
        assert not websocket_manager.is_user_online(user_id)
    
    async def test_get_chat_participants(self, websocket_manager):
        """Тест получения участников чата"""
        chat_id = 456
        user_ids = [123, 789, 999]
        
        # Добавляем участников
        for user_id in user_ids:
            await websocket_manager.join_chat(user_id, chat_id)
        
        participants = websocket_manager.get_chat_participants(chat_id)
        assert participants == set(user_ids)
        
        # Несуществующий чат
        empty_participants = websocket_manager.get_chat_participants(999)
        assert empty_participants == set()
    
    async def test_get_online_operators(self, websocket_manager):
        """Тест получения списка онлайн операторов"""
        # Подключаем операторов разных типов
        await websocket_manager.connect_user(1, AsyncMock(), "support")
        await websocket_manager.connect_user(2, AsyncMock(), "lawyer")
        await websocket_manager.connect_user(3, AsyncMock(), "salesman")
        await websocket_manager.connect_user(4, AsyncMock(), "client")  # не оператор
        
        # Все операторы
        all_operators = websocket_manager.get_online_operators()
        assert set(all_operators) == {1, 2, 3}
        
        # Только операторы поддержки
        support_operators = websocket_manager.get_online_operators("support")
        assert support_operators == [1]
        
        # Только юристы
        lawyers = websocket_manager.get_online_operators("lawyer")
        assert lawyers == [2]
    
    async def test_concurrent_websocket_operations(self, websocket_manager):
        """Тест одновременных WebSocket операций с блокировками"""
        import asyncio
        
        user_ids = [1, 2, 3, 4, 5]
        chat_id = 456
        
        # Одновременное подключение пользователей
        async def connect_user(user_id):
            websocket = AsyncMock()
            await websocket_manager.connect_user(user_id, websocket, "support")
            await websocket_manager.join_chat(user_id, chat_id)
        
        # Запускаем одновременное подключение
        await asyncio.gather(*[connect_user(user_id) for user_id in user_ids])
        
        # Проверяем что все пользователи подключены корректно
        assert len(websocket_manager.user_connections) == len(user_ids)
        assert len(websocket_manager.chat_connections[chat_id]) == len(user_ids)
        
        # Одновременное отключение
        async def disconnect_user(user_id):
            await websocket_manager.disconnect_user(user_id)
        
        await asyncio.gather(*[disconnect_user(user_id) for user_id in user_ids])
        
        # Проверяем что все отключены корректно
        assert len(websocket_manager.user_connections) == 0
        assert chat_id not in websocket_manager.chat_connections  # чат должен быть удален
