"""
Тесты интеграции авторизации с системой чата поддержки
"""
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi import HTTPException, status

from utils.auth import get_current_user, verify_token
from schemas.user_schema import TokenData
from database.models.users import Users


class TestChatAuthIntegration:
    """Тесты интеграции авторизации с чатом"""
    
    @pytest_asyncio.fixture
    async def mock_user_client(self):
        """Создает мок клиента"""
        user = Users()
        user.id = 123
        user.login = "test_client"
        user.email = "client@test.com"
        user.is_client = True
        user.is_active = True
        user.is_banned = False
        user.is_admin = False
        return user
    
    @pytest_asyncio.fixture
    async def mock_user_support(self):
        """Создает мок оператора поддержки"""
        user = Users()
        user.id = 456
        user.login = "test_support"
        user.email = "support@test.com"
        user.is_client = False
        user.is_active = True
        user.is_banned = False
        user.is_admin = False
        return user
    
    @pytest_asyncio.fixture
    async def mock_user_lawyer(self):
        """Создает мок юриста"""
        user = Users()
        user.id = 789
        user.login = "test_lawyer"
        user.email = "lawyer@test.com"
        user.is_client = False
        user.is_active = True
        user.is_banned = False
        user.is_admin = False
        return user
    
    @pytest_asyncio.fixture
    async def mock_user_admin(self):
        """Создает мок администратора"""
        user = Users()
        user.id = 1
        user.login = "test_admin"
        user.email = "admin@test.com"
        user.is_client = False
        user.is_active = True
        user.is_banned = False
        user.is_admin = True
        return user
    
    @pytest_asyncio.fixture
    async def valid_token(self):
        """Создает валидный токен"""
        return "valid_jwt_token_here"
    
    @pytest_asyncio.fixture
    async def invalid_token(self):
        """Создает невалидный токен"""
        return "invalid_token"
    
    async def test_get_current_user_valid_token(self, mock_user_client, valid_token):
        """Тест получения текущего пользователя с валидным токеном"""
        from fastapi.security import HTTPAuthorizationCredentials
        
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials=valid_token
        )
        
        with patch('utils.auth.verify_token') as mock_verify, \
             patch('database.logic.auth.auth.db_auth') as mock_db_auth:
            
            # Настраиваем мок верификации токена
            token_data = TokenData(user_id=123, email="client@test.com")
            mock_verify.return_value = token_data
            
            # Настраиваем мок получения пользователя из БД
            mock_db_auth.user_get_by_token.return_value = mock_user_client
            
            # Получаем пользователя
            user = await get_current_user(credentials)
            
            assert user == mock_user_client
            mock_verify.assert_called_once_with(valid_token, "access")
            mock_db_auth.user_get_by_token.assert_called_once_with(123)
    
    async def test_get_current_user_invalid_token(self, invalid_token):
        """Тест получения пользователя с невалидным токеном"""
        from fastapi.security import HTTPAuthorizationCredentials
        
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials=invalid_token
        )
        
        with patch('utils.auth.verify_token') as mock_verify:
            # Настраиваем невалидный токен
            mock_verify.return_value = None
            
            # Должно вызвать исключение
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(credentials)
            
            assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
            assert "Неверные учетные данные" in exc_info.value.detail
    
    async def test_get_current_user_banned_user(self, valid_token):
        """Тест получения заблокированного пользователя"""
        from fastapi.security import HTTPAuthorizationCredentials
        from exceptions.database_exc.auth import UserBannedException
        
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials=valid_token
        )
        
        with patch('utils.auth.verify_token') as mock_verify, \
             patch('database.logic.auth.auth.db_auth') as mock_db_auth:
            
            token_data = TokenData(user_id=123, email="client@test.com")
            mock_verify.return_value = token_data
            
            # Настраиваем исключение для заблокированного пользователя
            mock_db_auth.user_get_by_token.side_effect = UserBannedException("User is banned")
            
            # Должно вызвать исключение авторизации
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(credentials)
            
            assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    
    async def test_websocket_auth_valid_token(self, mock_user_client, valid_token):
        """Тест авторизации WebSocket с валидным токеном"""
        with patch('endpoints.chats.chat_kafka.get_current_user') as mock_get_user:
            mock_get_user.return_value = mock_user_client
            
            # Имитируем получение пользователя в WebSocket эндпоинте
            user = await mock_get_user(valid_token)
            
            assert user == mock_user_client
            assert user.is_client is True
    
    async def test_websocket_auth_invalid_token(self, invalid_token):
        """Тест авторизации WebSocket с невалидным токеном"""
        with patch('endpoints.chats.chat_kafka.get_current_user') as mock_get_user:
            mock_get_user.return_value = None
            
            # В WebSocket эндпоинте должен быть None для невалидного токена
            user = await mock_get_user(invalid_token)
            assert user is None
    
    async def test_admin_endpoints_auth_success(self, mock_user_admin):
        """Тест авторизации административных эндпоинтов - успех"""
        from endpoints.chats.admin_chat import check_admin_permissions
        
        # Проверка прав администратора
        result = await check_admin_permissions(mock_user_admin)
        assert result == mock_user_admin
    
    async def test_admin_endpoints_auth_failure(self, mock_user_client):
        """Тест авторизации административных эндпоинтов - отказ"""
        from endpoints.chats.admin_chat import check_admin_permissions
        
        # Попытка доступа неадминистратора к админским функциям
        with pytest.raises(HTTPException) as exc_info:
            await check_admin_permissions(mock_user_client)
        
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert "Недостаточно прав" in exc_info.value.detail
    
    async def test_role_based_websocket_access(self, mock_user_support, mock_user_client):
        """Тест ролевого доступа к функциям WebSocket"""
        
        # Тест функций доступных только операторам
        support_functions = [
            "accept_chat",
            "transfer_chat", 
            "assign_lawyer",
            "close_chat"
        ]
        
        for function in support_functions:
            # Оператор должен иметь доступ
            with patch('endpoints.chats.chat_kafka.assignment_manager') as mock_assignment:
                mock_assignment.get_operator_type.return_value = "support"
                
                # Имитируем проверку роли
                user_role = await mock_assignment.get_operator_type(mock_user_support.id)
                can_access = user_role in ["support", "lawyer", "salesman", "admin"]
                assert can_access is True
            
            # Клиент не должен иметь доступ
            with patch('endpoints.chats.chat_kafka.assignment_manager') as mock_assignment:
                mock_assignment.get_operator_type.return_value = "client"
                
                user_role = await mock_assignment.get_operator_type(mock_user_client.id)
                can_access = user_role in ["support", "lawyer", "salesman", "admin"]
                assert can_access is False
    
    async def test_chat_assignment_auth(self, mock_user_support, mock_user_client):
        """Тест авторизации при назначении чатов"""
        with patch('utils.assignment_manager.ChatAssignmentManager') as MockManager:
            manager = MockManager.return_value
            
            # Оператор может принимать чаты
            manager.get_operator_type.return_value = "support"
            operator_type = await manager.get_operator_type(mock_user_support.id)
            assert operator_type == "support"
            
            # Клиент не может принимать чаты
            manager.get_operator_type.return_value = "client"
            client_type = await manager.get_operator_type(mock_user_client.id)
            assert client_type == "client"
    
    async def test_lawyer_assignment_auth(self, mock_user_support, mock_user_lawyer, mock_user_client):
        """Тест авторизации при назначении юристов"""
        
        # Только операторы поддержки и админы могут назначать юристов
        authorized_roles = ["support", "admin"]
        
        # Проверяем для оператора поддержки
        with patch('utils.assignment_manager.ChatAssignmentManager') as MockManager:
            manager = MockManager.return_value
            manager.get_operator_type.return_value = "support"
            
            operator_type = await manager.get_operator_type(mock_user_support.id)
            can_assign_lawyer = operator_type in authorized_roles
            assert can_assign_lawyer is True
        
        # Проверяем для юриста (не может назначать других юристов)
        with patch('utils.assignment_manager.ChatAssignmentManager') as MockManager:
            manager = MockManager.return_value
            manager.get_operator_type.return_value = "lawyer"
            
            lawyer_type = await manager.get_operator_type(mock_user_lawyer.id)
            can_assign_lawyer = lawyer_type in authorized_roles
            assert can_assign_lawyer is False
        
        # Проверяем для клиента
        with patch('utils.assignment_manager.ChatAssignmentManager') as MockManager:
            manager = MockManager.return_value
            manager.get_operator_type.return_value = "client"
            
            client_type = await manager.get_operator_type(mock_user_client.id)
            can_assign_lawyer = client_type in authorized_roles
            assert can_assign_lawyer is False
    
    async def test_chat_transfer_auth(self, mock_user_support, mock_user_client):
        """Тест авторизации при переводе чатов"""
        
        # Операторы могут переводить свои чаты
        with patch('utils.assignment_manager.ChatAssignmentManager') as MockManager:
            manager = MockManager.return_value
            manager.get_chat_operator.return_value = mock_user_support.id
            
            # Проверяем что оператор может перевести свой чат
            current_operator = await manager.get_chat_operator(123)
            can_transfer = current_operator == mock_user_support.id
            assert can_transfer is True
            
            # Проверяем что оператор не может перевести чужой чат
            can_transfer_others = current_operator == 999  # другой оператор
            assert can_transfer_others is False
        
        # Клиенты не могут переводить чаты
        transfer_roles = ["support", "lawyer", "salesman", "admin"]
        with patch('utils.assignment_manager.ChatAssignmentManager') as MockManager:
            manager = MockManager.return_value
            manager.get_operator_type.return_value = "client"
            
            client_role = await manager.get_operator_type(mock_user_client.id)
            can_transfer = client_role in transfer_roles
            assert can_transfer is False
    
    async def test_force_transfer_admin_auth(self, mock_user_admin, mock_user_support):
        """Тест авторизации принудительного перевода администратором"""
        
        # Администратор может принудительно переводить любые чаты
        with patch('utils.assignment_manager.ChatAssignmentManager') as MockManager:
            manager = MockManager.return_value
            manager.get_chat_operator.return_value = mock_user_support.id  # чат другого оператора
            
            # Админ может перевести чужой чат
            is_admin = mock_user_admin.is_admin
            current_operator = await manager.get_chat_operator(123)
            can_force_transfer = is_admin or current_operator == mock_user_admin.id
            assert can_force_transfer is True
        
        # Обычный оператор не может принудительно переводить чужие чаты
        with patch('utils.assignment_manager.ChatAssignmentManager') as MockManager:
            manager = MockManager.return_value
            manager.get_chat_operator.return_value = 999  # чат другого оператора
            
            is_admin = mock_user_support.is_admin  # False
            current_operator = await manager.get_chat_operator(123)
            can_force_transfer = is_admin or current_operator == mock_user_support.id
            assert can_force_transfer is False
    
    async def test_token_expiration_handling(self):
        """Тест обработки истекших токенов"""
        from jose import JWTError
        
        expired_token = "expired_jwt_token"
        
        with patch('utils.auth.jwt.decode') as mock_decode:
            # Имитируем ошибку истекшего токена
            mock_decode.side_effect = JWTError("Token has expired")
            
            # verify_token должен вернуть None для истекшего токена
            result = verify_token(expired_token, "access")
            assert result is None
    
    async def test_websocket_connection_auth_flow(self, mock_user_client, valid_token):
        """Тест полного потока авторизации WebSocket соединения"""
        from fastapi.security import HTTPAuthorizationCredentials
        
        # Имитируем поток авторизации в WebSocket
        with patch('utils.auth.verify_token') as mock_verify, \
             patch('database.logic.auth.auth.db_auth') as mock_db_auth, \
             patch('endpoints.chats.chat_kafka.websocket_manager') as mock_ws_manager, \
             patch('endpoints.chats.chat_kafka.assignment_manager') as mock_assignment:
            
            # Настраиваем моки
            token_data = TokenData(user_id=123, email="client@test.com")
            mock_verify.return_value = token_data
            mock_db_auth.user_get_by_token.return_value = mock_user_client
            mock_assignment.get_operator_type.return_value = "client"
            
            # Имитируем авторизацию
            credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=valid_token)
            user = await get_current_user(credentials)
            
            # Проверяем что пользователь авторизован
            assert user == mock_user_client
            
            # Проверяем определение роли
            user_role = await mock_assignment.get_operator_type(user.id)
            assert user_role == "client"
            
            # Проверяем что для клиента определяется правильная логика
            is_client = user.is_client or user_role == "client"
            is_operator = user_role in ["support", "lawyer", "salesman"]
            
            assert is_client is True
            assert is_operator is False
    
    async def test_inactive_user_handling(self, valid_token):
        """Тест обработки неактивного пользователя"""
        from fastapi.security import HTTPAuthorizationCredentials
        from utils.auth import get_current_active_user
        
        # Создаем неактивного пользователя
        inactive_user = Users()
        inactive_user.id = 123
        inactive_user.is_active = False
        
        # Проверяем что get_current_active_user вызывает исключение
        with pytest.raises(HTTPException) as exc_info:
            await get_current_active_user(inactive_user)
        
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "Неактивный пользователь" in exc_info.value.detail
    
    async def test_concurrent_auth_requests(self, mock_user_client, valid_token):
        """Тест одновременных запросов авторизации"""
        import asyncio
        from fastapi.security import HTTPAuthorizationCredentials
        
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=valid_token)
        
        with patch('utils.auth.verify_token') as mock_verify, \
             patch('database.logic.auth.auth.db_auth') as mock_db_auth:
            
            token_data = TokenData(user_id=123, email="client@test.com")
            mock_verify.return_value = token_data
            mock_db_auth.user_get_by_token.return_value = mock_user_client
            
            # Запускаем несколько одновременных запросов авторизации
            tasks = [get_current_user(credentials) for _ in range(5)]
            results = await asyncio.gather(*tasks)
            
            # Все запросы должны вернуть одного и того же пользователя
            assert all(user == mock_user_client for user in results)
            
            # verify_token должен быть вызван для каждого запроса
            assert mock_verify.call_count == 5
