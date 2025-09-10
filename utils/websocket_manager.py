"""
WebSocket менеджер для чата поддержки с интеграцией Kafka
"""
import json
import asyncio
from typing import Dict, Set, List, Optional, Any
from fastapi import WebSocket
import logging

logger = logging.getLogger(__name__)


class WebSocketConnectionManager:
    """Менеджер WebSocket соединений для чата поддержки"""
    
    def __init__(self):
        # Активные соединения пользователей
        self.user_connections: Dict[int, WebSocket] = {}
        
        # Соединения по чатам (chat_id -> set of user_ids)
        self.chat_connections: Dict[int, Set[int]] = {}
        
        # Соединения операторов (operator_id -> websocket)
        self.operator_connections: Dict[int, WebSocket] = {}
        
        # Соединения по ролям (role -> set of user_ids)
        self.role_connections: Dict[str, Set[int]] = {
            'support': set(),
            'lawyer': set(),
            'salesman': set(),
            'admin': set()
        }
        
        # Метаданные соединений
        self.connection_metadata: Dict[int, Dict[str, Any]] = {}
        
        # Блокировка для потокобезопасности
        self._lock = asyncio.Lock()
    
    async def connect_user(self, user_id: int, websocket: WebSocket, user_role: str, metadata: Optional[Dict] = None):
        """Подключение пользователя"""
        async with self._lock:
            await websocket.accept()
            
            # Закрываем предыдущее соединение если есть
            if user_id in self.user_connections:
                try:
                    await self.user_connections[user_id].close()
                except:
                    pass
            
            self.user_connections[user_id] = websocket
            self.connection_metadata[user_id] = metadata or {}
            
            # Добавляем в соответствующую роль
            if user_role in self.role_connections:
                self.role_connections[user_role].add(user_id)
                
                # Если это оператор, добавляем в список операторов
                if user_role in ['support', 'lawyer', 'salesman']:
                    self.operator_connections[user_id] = websocket
            
            logger.info(f"Пользователь {user_id} ({user_role}) подключен")
    
    async def disconnect_user(self, user_id: int):
        """Отключение пользователя"""
        async with self._lock:
            if user_id in self.user_connections:
                del self.user_connections[user_id]
            
            if user_id in self.connection_metadata:
                del self.connection_metadata[user_id]
            
            if user_id in self.operator_connections:
                del self.operator_connections[user_id]
            
            # Удаляем из всех ролей
            for role_set in self.role_connections.values():
                role_set.discard(user_id)
            
            # Удаляем из всех чатов
            for chat_users in self.chat_connections.values():
                chat_users.discard(user_id)
            
            logger.info(f"Пользователь {user_id} отключен")
    
    async def join_chat(self, user_id: int, chat_id: int):
        """Присоединение пользователя к чату"""
        async with self._lock:
            if chat_id not in self.chat_connections:
                self.chat_connections[chat_id] = set()
            
            self.chat_connections[chat_id].add(user_id)
            logger.info(f"Пользователь {user_id} присоединился к чату {chat_id}")
    
    async def leave_chat(self, user_id: int, chat_id: int):
        """Выход пользователя из чата"""
        async with self._lock:
            if chat_id in self.chat_connections:
                self.chat_connections[chat_id].discard(user_id)
                
                # Удаляем пустые чаты
                if not self.chat_connections[chat_id]:
                    del self.chat_connections[chat_id]
            
            logger.info(f"Пользователь {user_id} вышел из чата {chat_id}")
    
    async def send_to_user(self, user_id: int, message: Dict[str, Any]) -> bool:
        """Отправка сообщения конкретному пользователю"""
        if user_id in self.user_connections:
            try:
                websocket = self.user_connections[user_id]
                await websocket.send_json(message)
                return True
            except Exception as e:
                logger.error(f"Ошибка отправки сообщения пользователю {user_id}: {e}")
                # Удаляем неработающее соединение
                await self.disconnect_user(user_id)
        return False
    
    async def broadcast_to_chat(self, chat_id: int, message: Dict[str, Any], exclude_user: Optional[int] = None):
        """Рассылка сообщения всем участникам чата"""
        if chat_id not in self.chat_connections:
            return
        
        participants = self.chat_connections[chat_id].copy()
        if exclude_user:
            participants.discard(exclude_user)
        
        for user_id in participants:
            await self.send_to_user(user_id, message)
    
    async def broadcast_to_role(self, role: str, message: Dict[str, Any], exclude_user: Optional[int] = None):
        """Рассылка сообщения всем пользователям с определенной ролью"""
        if role not in self.role_connections:
            return
        
        users = self.role_connections[role].copy()
        if exclude_user:
            users.discard(exclude_user)
        
        for user_id in users:
            await self.send_to_user(user_id, message)
    
    async def broadcast_to_operators(self, message: Dict[str, Any], operator_types: Optional[List[str]] = None):
        """Рассылка сообщения операторам"""
        if operator_types is None:
            operator_types = ['support', 'lawyer', 'salesman']
        
        for role in operator_types:
            await self.broadcast_to_role(role, message)
    
    # Специализированные методы для событий чата поддержки
    
    async def notify_operators_new_chat(self, chat_id: int, client_id: int):
        """Уведомление операторов о новом чате"""
        message = {
            'type': 'new_chat_available',
            'payload': {
                'chat_id': chat_id,
                'client_id': client_id,
                'timestamp': asyncio.get_event_loop().time()
            }
        }
        await self.broadcast_to_role('support', message)
    
    async def notify_operators_queue_update(self, client_id: int, queue_position: int):
        """Уведомление операторов об обновлении очереди"""
        message = {
            'type': 'queue_update',
            'payload': {
                'client_id': client_id,
                'queue_position': queue_position
            }
        }
        await self.broadcast_to_role('support', message)
    
    async def hide_client_from_operators(self, client_id: int, except_operator: Optional[int] = None):
        """Скрытие клиента от других операторов (после принятия чата)"""
        message = {
            'type': 'client_taken',
            'payload': {
                'client_id': client_id,
                'taken_by': except_operator
            }
        }
        
        # Отправляем всем операторам поддержки кроме того, кто принял
        operators = self.role_connections['support'].copy()
        if except_operator:
            operators.discard(except_operator)
        
        for operator_id in operators:
            await self.send_to_user(operator_id, message)
    
    async def notify_chat_assigned(self, chat_id: int, operator_id: int, client_id: int):
        """Уведомление о назначении чата"""
        # Уведомляем оператора
        operator_message = {
            'type': 'chat_assigned',
            'payload': {
                'chat_id': chat_id,
                'client_id': client_id,
                'role': 'operator'
            }
        }
        await self.send_to_user(operator_id, operator_message)
        
        # Уведомляем клиента
        client_message = {
            'type': 'operator_assigned',
            'payload': {
                'chat_id': chat_id,
                'operator_id': operator_id
            }
        }
        await self.send_to_user(client_id, client_message)
        
        # Добавляем участников в чат
        await self.join_chat(operator_id, chat_id)
        await self.join_chat(client_id, chat_id)
    
    async def notify_chat_transferred(self, chat_id: int, new_operator_id: int, 
                                    previous_operator_id: int, reason: Optional[str] = None):
        """Уведомление о переводе чата"""
        # Уведомляем нового оператора
        new_operator_message = {
            'type': 'chat_transferred_to_you',
            'payload': {
                'chat_id': chat_id,
                'previous_operator_id': previous_operator_id,
                'reason': reason
            }
        }
        await self.send_to_user(new_operator_id, new_operator_message)
        
        # Уведомляем предыдущего оператора
        previous_operator_message = {
            'type': 'chat_transferred_from_you',
            'payload': {
                'chat_id': chat_id,
                'new_operator_id': new_operator_id,
                'reason': reason
            }
        }
        await self.send_to_user(previous_operator_id, previous_operator_message)
        
        # Уведомляем участников чата
        transfer_message = {
            'type': 'chat_transferred',
            'payload': {
                'chat_id': chat_id,
                'new_operator_id': new_operator_id,
                'previous_operator_id': previous_operator_id,
                'reason': reason
            }
        }
        await self.broadcast_to_chat(chat_id, transfer_message)
        
        # Обновляем участников чата
        await self.leave_chat(previous_operator_id, chat_id)
        await self.join_chat(new_operator_id, chat_id)
    
    async def notify_lawyer_assigned(self, client_id: int, lawyer_id: int, chat_id: int):
        """Уведомление о назначении персонального юриста"""
        # Уведомляем клиента
        client_message = {
            'type': 'lawyer_assigned',
            'payload': {
                'lawyer_id': lawyer_id,
                'chat_id': chat_id
            }
        }
        await self.send_to_user(client_id, client_message)
        
        # Уведомляем юриста
        lawyer_message = {
            'type': 'client_assigned',
            'payload': {
                'client_id': client_id,
                'chat_id': chat_id
            }
        }
        await self.send_to_user(lawyer_id, lawyer_message)
        
        # Добавляем участников в чат
        await self.join_chat(client_id, chat_id)
        await self.join_chat(lawyer_id, chat_id)
    
    async def notify_operator_status_change(self, operator_id: int, status: str, metadata: Optional[Dict] = None):
        """Уведомление об изменении статуса оператора"""
        message = {
            'type': 'operator_status_change',
            'payload': {
                'operator_id': operator_id,
                'status': status,
                'metadata': metadata
            }
        }
        
        # Уведомляем администраторов и других операторов
        await self.broadcast_to_role('admin', message)
        await self.broadcast_to_role('support', message, exclude_user=operator_id)
    
    # Статистика и мониторинг
    
    def get_connection_stats(self) -> Dict[str, Any]:
        """Получение статистики соединений"""
        return {
            'total_connections': len(self.user_connections),
            'operator_connections': len(self.operator_connections),
            'active_chats': len(self.chat_connections),
            'connections_by_role': {
                role: len(users) for role, users in self.role_connections.items()
            },
            'chat_participants': {
                chat_id: len(users) for chat_id, users in self.chat_connections.items()
            }
        }
    
    def is_user_online(self, user_id: int) -> bool:
        """Проверка, подключен ли пользователь"""
        return user_id in self.user_connections
    
    def get_chat_participants(self, chat_id: int) -> Set[int]:
        """Получение участников чата"""
        return self.chat_connections.get(chat_id, set()).copy()
    
    def get_online_operators(self, operator_type: Optional[str] = None) -> List[int]:
        """Получение списка онлайн операторов"""
        if operator_type:
            return list(self.role_connections.get(operator_type, set()))
        else:
            operators = set()
            for role in ['support', 'lawyer', 'salesman']:
                operators.update(self.role_connections.get(role, set()))
            return list(operators)


# Глобальный экземпляр менеджера
websocket_manager = WebSocketConnectionManager()
