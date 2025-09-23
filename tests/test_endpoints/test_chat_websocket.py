"""
Тесты для WebSocket эндпоинтов чата поддержки
"""
import pytest
import pytest_asyncio
import json
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi import status
from fastapi.testclient import TestClient

from endpoints.chats.chat_kafka import ws_chat_endpoint, handle_websocket_message
from tests.conftest import MockWebSocket, TEST_USER_ID, TEST_CLIENT_ID, TEST_OPERATOR_ID, TEST_CHAT_ID


class TestWebSocketChatEndpoint:
    """Тесты для WebSocket эндпоинта чата"""
    
    @pytest_asyncio.fixture
    async def mock_dependencies(self):
        """Создает моки для всех зависимостей"""
        mocks = {}
        
        with patch('endpoints.chats.chat_kafka.get_current_user') as mock_get_user, \
             patch('endpoints.chats.chat_kafka.websocket_manager') as mock_ws_manager, \
             patch('endpoints.chats.chat_kafka.kafka_producer') as mock_producer, \
             patch('endpoints.chats.chat_kafka.queue_manager') as mock_queue, \
             patch('endpoints.chats.chat_kafka.assignment_manager') as mock_assignment, \
             patch('endpoints.chats.chat_kafka.chat_db') as mock_chat_db:
            
            # Настройка моков
            mock_user = MagicMock()
            mock_user.id = TEST_USER_ID
            mock_user.is_client = True
            mock_get_user.return_value = mock_user
            
            mock_ws_manager.connect_user = AsyncMock()
            mock_ws_manager.join_chat = AsyncMock()
            mock_ws_manager.leave_chat = AsyncMock()
            mock_ws_manager.disconnect_user = AsyncMock()
            mock_ws_manager.send_to_user = AsyncMock()
            
            mock_assignment.get_operator_type = AsyncMock(return_value="client")
            mock_assignment.set_operator_online = AsyncMock()
            mock_assignment.set_operator_offline = AsyncMock()
            mock_assignment.get_chat_operator = AsyncMock(return_value=None)
            
            mock_queue.add_client_to_queue = AsyncMock()
            
            mock_chat_db.get_active_chat_by_user = AsyncMock(return_value=None)
            mock_chat_db.create_chat = AsyncMock()
            mock_chat_db.add_message = AsyncMock()
            
            mock_producer.send_chat_created = AsyncMock()
            
            mocks.update({
                'get_user': mock_get_user,
                'ws_manager': mock_ws_manager,
                'producer': mock_producer,
                'queue': mock_queue,
                'assignment': mock_assignment,
                'chat_db': mock_chat_db,
                'user': mock_user
            })
            
            yield mocks
    
    async def test_websocket_client_connection_new_chat(self, mock_dependencies):
        """Тест подключения клиента с созданием нового чата"""
        websocket = MockWebSocket()
        token = "test_token"
        
        # Настраиваем создание нового чата
        mock_chat = MagicMock()
        mock_chat.id = TEST_CHAT_ID
        mock_dependencies['chat_db'].create_chat.return_value = mock_chat
        
        # Имитируем отключение клиента
        websocket.add_received_message('{"type": "disconnect"}')
        
        # Вызываем эндпоинт
        try:
            await ws_chat_endpoint(websocket, token, chat_id=None)
        except Exception:
            pass  # Ожидается исключение при receive_text
        
        # Проверяем что WebSocket был принят
        assert websocket.accepted
        
        # Проверяем создание чата
        mock_dependencies['chat_db'].create_chat.assert_called_once_with(TEST_USER_ID)
        
        # Проверяем отправку события создания чата
        mock_dependencies['producer'].send_chat_created.assert_called_once_with(TEST_CHAT_ID, TEST_USER_ID)
        
        # Проверяем подключение пользователя
        mock_dependencies['ws_manager'].connect_user.assert_called_once()
        
        # Проверяем присоединение к чату
        mock_dependencies['ws_manager'].join_chat.assert_called_once_with(TEST_USER_ID, TEST_CHAT_ID)
        
        # Проверяем добавление в очередь
        mock_dependencies['queue'].add_client_to_queue.assert_called_once_with(TEST_USER_ID, TEST_CHAT_ID)
    
    async def test_websocket_client_connection_existing_chat(self, mock_dependencies):
        """Тест подключения клиента с существующим чатом"""
        websocket = MockWebSocket()
        token = "test_token"
        
        # Настраиваем существующий чат
        mock_chat = MagicMock()
        mock_chat.id = TEST_CHAT_ID
        mock_dependencies['chat_db'].get_active_chat_by_user.return_value = mock_chat
        
        websocket.add_received_message('{"type": "disconnect"}')
        
        try:
            await ws_chat_endpoint(websocket, token, chat_id=None)
        except Exception:
            pass
        
        # Проверяем что новый чат не создавался
        mock_dependencies['chat_db'].create_chat.assert_not_called()
        
        # Проверяем использование существующего чата
        mock_dependencies['ws_manager'].join_chat.assert_called_once_with(TEST_USER_ID, TEST_CHAT_ID)
    
    async def test_websocket_operator_connection(self, mock_dependencies):
        """Тест подключения оператора"""
        websocket = MockWebSocket()
        token = "test_token"
        
        # Настраиваем пользователя как оператора
        mock_dependencies['user'].is_client = False
        mock_dependencies['assignment'].get_operator_type.return_value = "support"
        
        websocket.add_received_message('{"type": "disconnect"}')
        
        try:
            await ws_chat_endpoint(websocket, token, chat_id=None)
        except Exception:
            pass
        
        # Проверяем что оператор переведен в онлайн
        mock_dependencies['assignment'].set_operator_online.assert_called_once_with(TEST_USER_ID, "support")
        
        # Проверяем что не создавался чат
        mock_dependencies['chat_db'].create_chat.assert_not_called()
    
    async def test_websocket_unauthorized_access(self, mock_dependencies):
        """Тест неавторизованного доступа"""
        websocket = MockWebSocket()
        token = "invalid_token"
        
        # Настраиваем ошибку авторизации
        mock_dependencies['get_user'].return_value = None
        
        await ws_chat_endpoint(websocket, token, chat_id=None)
        
        # Проверяем что соединение было закрыто
        assert websocket.closed
    
    async def test_websocket_with_specific_chat_id(self, mock_dependencies):
        """Тест подключения к конкретному чату"""
        websocket = MockWebSocket()
        token = "test_token"
        chat_id = TEST_CHAT_ID
        
        websocket.add_received_message('{"type": "disconnect"}')
        
        try:
            await ws_chat_endpoint(websocket, token, chat_id=chat_id)
        except Exception:
            pass
        
        # Проверяем присоединение к указанному чату
        mock_dependencies['ws_manager'].join_chat.assert_called_once_with(TEST_USER_ID, chat_id)
    
    async def test_websocket_cleanup_on_disconnect(self, mock_dependencies):
        """Тест очистки при отключении"""
        websocket = MockWebSocket()
        token = "test_token"
        
        # Настраиваем как оператора
        mock_dependencies['user'].is_client = False
        mock_dependencies['assignment'].get_operator_type.return_value = "support"
        
        websocket.add_received_message('{"type": "disconnect"}')
        
        try:
            await ws_chat_endpoint(websocket, token, chat_id=TEST_CHAT_ID)
        except Exception:
            pass
        
        # Проверяем очистку при отключении
        mock_dependencies['ws_manager'].leave_chat.assert_called_once_with(TEST_USER_ID, TEST_CHAT_ID)
        mock_dependencies['assignment'].set_operator_offline.assert_called_once_with(TEST_USER_ID)
        mock_dependencies['ws_manager'].disconnect_user.assert_called_once_with(TEST_USER_ID)


class TestWebSocketMessageHandlers:
    """Тесты для обработчиков WebSocket сообщений"""
    
    @pytest_asyncio.fixture
    async def mock_handlers(self):
        """Создает моки для обработчиков сообщений"""
        with patch('endpoints.chats.chat_kafka.chat_db') as mock_chat_db, \
             patch('endpoints.chats.chat_kafka.kafka_producer') as mock_producer, \
             patch('endpoints.chats.chat_kafka.queue_manager') as mock_queue, \
             patch('endpoints.chats.chat_kafka.assignment_manager') as mock_assignment, \
             patch('endpoints.chats.chat_kafka.websocket_manager') as mock_ws_manager:
            
            # Настройка моков
            mock_message = MagicMock()
            mock_message.id = 123
            mock_chat_db.add_message.return_value = mock_message
            
            yield {
                'chat_db': mock_chat_db,
                'producer': mock_producer,
                'queue': mock_queue,
                'assignment': mock_assignment,
                'ws_manager': mock_ws_manager,
                'message': mock_message
            }
    
    async def test_handle_chat_message(self, mock_handlers):
        """Тест обработки сообщения чата"""
        user_id = TEST_USER_ID
        user_role = "client"
        chat_id = TEST_CHAT_ID
        message_data = {
            "type": "message",
            "payload": {"text": "Тестовое сообщение"}
        }
        
        await handle_websocket_message(user_id, user_role, chat_id, message_data)
        
        # Проверяем сохранение в БД
        mock_handlers['chat_db'].add_message.assert_called_once_with(
            chat_id, user_id, user_role, "Тестовое сообщение"
        )
        
        # Проверяем отправку в Kafka
        mock_handlers['producer'].send_message_sent.assert_called_once_with(
            chat_id, user_id, user_role, 123, "Тестовое сообщение"
        )
    
    async def test_handle_chat_message_empty_text(self, mock_handlers):
        """Тест обработки пустого сообщения"""
        user_id = TEST_USER_ID
        user_role = "client"
        chat_id = TEST_CHAT_ID
        message_data = {
            "type": "message",
            "payload": {"text": ""}
        }
        
        with pytest.raises(ValueError, match="Сообщение не может быть пустым"):
            await handle_websocket_message(user_id, user_role, chat_id, message_data)
    
    async def test_handle_chat_message_no_chat_id(self, mock_handlers):
        """Тест обработки сообщения без chat_id"""
        user_id = TEST_USER_ID
        user_role = "client"
        chat_id = None
        message_data = {
            "type": "message",
            "payload": {"text": "Тестовое сообщение"}
        }
        
        with pytest.raises(ValueError, match="Не указан ID чата"):
            await handle_websocket_message(user_id, user_role, chat_id, message_data)
    
    async def test_handle_accept_chat(self, mock_handlers):
        """Тест обработки принятия чата оператором"""
        user_id = TEST_OPERATOR_ID
        user_role = "support"
        chat_id = None
        message_data = {
            "type": "accept_chat",
            "payload": {
                "client_id": TEST_CLIENT_ID,
                "chat_id": TEST_CHAT_ID
            }
        }
        
        # Настраиваем клиента в очереди
        mock_handlers['queue'].waiting_clients = {TEST_CLIENT_ID: MagicMock()}
        mock_handlers['assignment'].assign_chat_to_operator.return_value = True
        
        await handle_websocket_message(user_id, user_role, chat_id, message_data)
        
        # Проверяем назначение чата
        mock_handlers['assignment'].assign_chat_to_operator.assert_called_once_with(
            TEST_CHAT_ID, TEST_OPERATOR_ID, TEST_CLIENT_ID
        )
    
    async def test_handle_accept_chat_unauthorized(self, mock_handlers):
        """Тест попытки принятия чата неоператором"""
        user_id = TEST_CLIENT_ID
        user_role = "client"
        chat_id = None
        message_data = {
            "type": "accept_chat",
            "payload": {
                "client_id": TEST_CLIENT_ID,
                "chat_id": TEST_CHAT_ID
            }
        }
        
        with pytest.raises(ValueError, match="Только операторы могут принимать чаты"):
            await handle_websocket_message(user_id, user_role, chat_id, message_data)
    
    async def test_handle_accept_chat_client_already_taken(self, mock_handlers):
        """Тест принятия чата когда клиент уже принят"""
        user_id = TEST_OPERATOR_ID
        user_role = "support"
        chat_id = None
        message_data = {
            "type": "accept_chat",
            "payload": {
                "client_id": TEST_CLIENT_ID,
                "chat_id": TEST_CHAT_ID
            }
        }
        
        # Настраиваем что клиента нет в очереди
        mock_handlers['queue'].waiting_clients = {}
        
        # Мокаем WebSocket менеджер для отправки ошибки
        mock_handlers['ws_manager'].send_to_user = AsyncMock()
        
        await handle_websocket_message(user_id, user_role, chat_id, message_data)
        
        # Проверяем отправку ошибки
        mock_handlers['ws_manager'].send_to_user.assert_called_once()
        error_call = mock_handlers['ws_manager'].send_to_user.call_args[0][1]
        assert error_call['type'] == 'error'
        assert 'уже принят' in error_call['payload']['message']
    
    async def test_handle_transfer_chat(self, mock_handlers):
        """Тест обработки перевода чата"""
        user_id = TEST_OPERATOR_ID
        user_role = "support"
        chat_id = None
        message_data = {
            "type": "transfer_chat",
            "payload": {
                "chat_id": TEST_CHAT_ID,
                "target_operator_id": 999,
                "reason": "specialization"
            }
        }
        
        # Настраиваем что чат назначен текущему оператору
        mock_handlers['assignment'].get_chat_operator.return_value = TEST_OPERATOR_ID
        mock_handlers['assignment'].transfer_chat_to_operator.return_value = True
        
        await handle_websocket_message(user_id, user_role, chat_id, message_data)
        
        # Проверяем выполнение перевода
        mock_handlers['assignment'].transfer_chat_to_operator.assert_called_once_with(
            TEST_CHAT_ID, 999, TEST_OPERATOR_ID, "specialization", None
        )
    
    async def test_handle_transfer_chat_unauthorized(self, mock_handlers):
        """Тест попытки перевода чата неавторизованным пользователем"""
        user_id = TEST_CLIENT_ID
        user_role = "client"
        chat_id = None
        message_data = {
            "type": "transfer_chat",
            "payload": {
                "chat_id": TEST_CHAT_ID,
                "target_operator_id": 999
            }
        }
        
        with pytest.raises(ValueError, match="Недостаточно прав для перевода чата"):
            await handle_websocket_message(user_id, user_role, chat_id, message_data)
    
    async def test_handle_transfer_chat_not_owner(self, mock_handlers):
        """Тест попытки перевода чужого чата"""
        user_id = TEST_OPERATOR_ID
        user_role = "support"
        chat_id = None
        message_data = {
            "type": "transfer_chat",
            "payload": {
                "chat_id": TEST_CHAT_ID,
                "target_operator_id": 999
            }
        }
        
        # Настраиваем что чат назначен другому оператору
        mock_handlers['assignment'].get_chat_operator.return_value = 888
        
        with pytest.raises(ValueError, match="Вы не можете передавать чужие чаты"):
            await handle_websocket_message(user_id, user_role, chat_id, message_data)
    
    async def test_handle_assign_lawyer(self, mock_handlers):
        """Тест обработки назначения юриста"""
        user_id = TEST_OPERATOR_ID
        user_role = "support"
        chat_id = None
        message_data = {
            "type": "assign_lawyer",
            "payload": {
                "client_id": TEST_CLIENT_ID,
                "lawyer_id": 999
            }
        }
        
        # Настраиваем успешное назначение юриста
        mock_handlers['assignment'].assign_personal_lawyer.return_value = 888  # chat_id
        mock_handlers['ws_manager'].send_to_user = AsyncMock()
        
        await handle_websocket_message(user_id, user_role, chat_id, message_data)
        
        # Проверяем назначение юриста
        mock_handlers['assignment'].assign_personal_lawyer.assert_called_once_with(
            TEST_CLIENT_ID, 999, TEST_OPERATOR_ID
        )
        
        # Проверяем отправку уведомления об успехе
        mock_handlers['ws_manager'].send_to_user.assert_called_once()
        success_call = mock_handlers['ws_manager'].send_to_user.call_args[0][1]
        assert success_call['type'] == 'lawyer_assigned_success'
    
    async def test_handle_assign_lawyer_unauthorized(self, mock_handlers):
        """Тест попытки назначения юриста неавторизованным пользователем"""
        user_id = TEST_CLIENT_ID
        user_role = "client"
        chat_id = None
        message_data = {
            "type": "assign_lawyer",
            "payload": {
                "client_id": TEST_CLIENT_ID,
                "lawyer_id": 999
            }
        }
        
        with pytest.raises(ValueError, match="Только операторы поддержки и админы могут назначать юристов"):
            await handle_websocket_message(user_id, user_role, chat_id, message_data)
    
    async def test_handle_close_chat(self, mock_handlers):
        """Тест обработки закрытия чата"""
        user_id = TEST_OPERATOR_ID
        user_role = "support"
        chat_id = TEST_CHAT_ID
        message_data = {
            "type": "close_chat",
            "payload": {
                "reason": "resolved"
            }
        }
        
        await handle_websocket_message(user_id, user_role, chat_id, message_data)
        
        # Проверяем закрытие чата в БД
        mock_handlers['chat_db'].close_chat.assert_called_once_with(TEST_CHAT_ID, TEST_OPERATOR_ID)
        
        # Проверяем отправку события закрытия
        mock_handlers['producer'].send_chat_closed.assert_called_once_with(
            TEST_CHAT_ID, TEST_OPERATOR_ID, "resolved"
        )
    
    async def test_handle_close_chat_unauthorized(self, mock_handlers):
        """Тест попытки закрытия чата неавторизованным пользователем"""
        user_id = TEST_CLIENT_ID
        user_role = "client"
        chat_id = TEST_CHAT_ID
        message_data = {
            "type": "close_chat",
            "payload": {
                "reason": "resolved"
            }
        }
        
        with pytest.raises(ValueError, match="Недостаточно прав для закрытия чата"):
            await handle_websocket_message(user_id, user_role, chat_id, message_data)
    
    async def test_handle_typing(self, mock_handlers):
        """Тест обработки индикатора печати"""
        user_id = TEST_USER_ID
        user_role = "client"
        chat_id = TEST_CHAT_ID
        message_data = {
            "type": "typing",
            "payload": {
                "is_typing": True
            }
        }
        
        await handle_websocket_message(user_id, user_role, chat_id, message_data)
        
        # Проверяем рассылку индикатора печати
        mock_handlers['ws_manager'].broadcast_to_chat.assert_called_once()
        call_args = mock_handlers['ws_manager'].broadcast_to_chat.call_args
        
        assert call_args[0][0] == TEST_CHAT_ID  # chat_id
        assert call_args[1]['exclude_user'] == TEST_USER_ID  # исключить отправителя
        
        message_payload = call_args[0][1]
        assert message_payload['type'] == 'typing'
        assert message_payload['payload']['is_typing'] is True
    
    async def test_handle_read_messages(self, mock_handlers):
        """Тест обработки отметки о прочтении сообщений"""
        user_id = TEST_USER_ID
        user_role = "client"
        chat_id = TEST_CHAT_ID
        message_data = {
            "type": "read_messages",
            "payload": {
                "upto_message_id": 123
            }
        }
        
        await handle_websocket_message(user_id, user_role, chat_id, message_data)
        
        # Проверяем отметку сообщений как прочитанных
        mock_handlers['chat_db'].mark_messages_read.assert_called_once_with(
            TEST_CHAT_ID, TEST_USER_ID, 123
        )
        
        # Проверяем уведомление других участников
        mock_handlers['ws_manager'].broadcast_to_chat.assert_called_once()
        call_args = mock_handlers['ws_manager'].broadcast_to_chat.call_args
        
        message_payload = call_args[0][1]
        assert message_payload['type'] == 'messages_read'
        assert message_payload['payload']['upto_message_id'] == 123
    
    async def test_handle_operator_status(self, mock_handlers):
        """Тест обработки изменения статуса оператора"""
        user_id = TEST_OPERATOR_ID
        user_role = "support"
        chat_id = None
        message_data = {
            "type": "operator_status",
            "payload": {
                "status": "busy"
            }
        }
        
        await handle_websocket_message(user_id, user_role, chat_id, message_data)
        
        # Проверяем изменение статуса
        mock_handlers['queue'].set_operator_busy.assert_called_once_with(TEST_OPERATOR_ID, True)
        
        # Проверяем уведомление о смене статуса
        mock_handlers['ws_manager'].notify_operator_status_change.assert_called_once_with(
            TEST_OPERATOR_ID, "busy"
        )
    
    async def test_handle_operator_status_unauthorized(self, mock_handlers):
        """Тест попытки изменения статуса оператора неоператором"""
        user_id = TEST_CLIENT_ID
        user_role = "client"
        chat_id = None
        message_data = {
            "type": "operator_status",
            "payload": {
                "status": "busy"
            }
        }
        
        with pytest.raises(ValueError, match="Только операторы могут изменять свой статус"):
            await handle_websocket_message(user_id, user_role, chat_id, message_data)
    
    async def test_handle_unknown_message_type(self, mock_handlers):
        """Тест обработки неизвестного типа сообщения"""
        user_id = TEST_USER_ID
        user_role = "client"
        chat_id = TEST_CHAT_ID
        message_data = {
            "type": "unknown_type",
            "payload": {}
        }
        
        mock_handlers['ws_manager'].send_to_user = AsyncMock()
        
        await handle_websocket_message(user_id, user_role, chat_id, message_data)
        
        # Проверяем отправку ошибки
        mock_handlers['ws_manager'].send_to_user.assert_called_once()
        error_call = mock_handlers['ws_manager'].send_to_user.call_args[0][1]
        assert error_call['type'] == 'error'
        assert 'Неизвестный тип сообщения' in error_call['payload']['message']
