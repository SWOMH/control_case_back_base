"""
Менеджер назначений операторов и юристов для чата поддержки
"""
import asyncio
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import logging

from database.logic.chats.chat import chat_db
from utils.kafka_producer import kafka_producer

logger = logging.getLogger(__name__)


class ChatAssignmentManager:
    """Менеджер назначений чатов операторам и юристам"""
    
    def __init__(self, queue_manager, websocket_manager=None):
        self.queue_manager = queue_manager
        self.websocket_manager = websocket_manager
        
        # Кэш информации о пользователях и их ролях
        self.user_roles_cache: Dict[int, str] = {}
        self.lawyer_assignments: Dict[int, int] = {}  # client_id -> lawyer_id
        
        # Блокировки для избежания race conditions
        self._assignment_lock = asyncio.Lock()
    
    # Управление операторами
    
    async def set_operator_online(self, operator_id: int, operator_type: str, max_concurrent_chats: int = 5):
        """Установка оператора в онлайн состояние"""
        await self.queue_manager.set_operator_online(operator_id, operator_type, max_concurrent_chats)
        
        # Отправляем Kafka событие
        await kafka_producer.send_operator_online(operator_id, operator_type, max_concurrent_chats)
    
    async def set_operator_offline(self, operator_id: int):
        """Установка оператора в оффлайн состояние"""
        if operator_id in self.queue_manager.operators:
            operator_type = self.queue_manager.operators[operator_id].operator_type
            await self.queue_manager.set_operator_offline(operator_id)
            
            # Отправляем Kafka событие
            await kafka_producer.send_operator_offline(operator_id, operator_type)
    
    async def get_operator_type(self, user_id: int) -> Optional[str]:
        """Получение типа оператора по ID пользователя"""
        # Кэширование ролей пользователей
        if user_id in self.user_roles_cache:
            return self.user_roles_cache[user_id]
        
        # Здесь нужно реализовать запрос к БД для получения роли пользователя
        # Пока заглушка - в реальном коде нужно проверять группы пользователя
        # и определять роль на основе разрешений
        
        # TODO: Реализовать получение роли из БД
        # Временная заглушка
        role = "support"  # По умолчанию
        self.user_roles_cache[user_id] = role
        return role
    
    # Назначение чатов
    
    async def assign_chat_to_operator(self, chat_id: int, operator_id: int, client_id: int) -> bool:
        """Назначение чата оператору"""
        async with self._assignment_lock:
            # Проверяем, что оператор может принять чат
            if operator_id not in self.queue_manager.operators:
                logger.error(f"Оператор {operator_id} не найден")
                return False
            
            operator = self.queue_manager.operators[operator_id]
            if not operator.can_accept_chat:
                logger.error(f"Оператор {operator_id} не может принять чат")
                return False
            
            # Назначаем чат в менеджере очереди
            success = await self.queue_manager.assign_chat_to_operator(chat_id, operator_id, client_id)
            
            if success:
                # Обновляем БД
                try:
                    async with chat_db.get_async_session() as session:
                        # Обновляем чат в БД - назначаем оператора
                        await chat_db.update_chat_operator(session, chat_id, operator_id)
                        
                        # Добавляем участника в чат
                        await chat_db.add_chat_participant(
                            session, chat_id, operator_id, operator.operator_type
                        )
                    
                    # Отправляем Kafka события
                    await kafka_producer.send_chat_assigned(
                        chat_id, operator_id, operator.operator_type, client_id, "operator_assignment"
                    )
                    await kafka_producer.send_operator_accept_chat(
                        operator_id, operator.operator_type, chat_id, client_id
                    )
                    
                    logger.info(f"Чат {chat_id} успешно назначен оператору {operator_id}")
                    return True
                    
                except Exception as e:
                    logger.error(f"Ошибка обновления БД при назначении чата: {e}")
                    # Откатываем назначение
                    await self.queue_manager.release_operator_from_chat(chat_id)
                    return False
            
            return False
    
    async def release_operator_from_chat(self, chat_id: int):
        """Освобождение оператора от чата"""
        if chat_id in self.queue_manager.chat_assignments:
            operator_id = self.queue_manager.chat_assignments[chat_id]
            
            await self.queue_manager.release_operator_from_chat(chat_id)
            
            # Обновляем БД
            try:
                async with chat_db.get_async_session() as session:
                    await chat_db.mark_chat_participant_left(session, chat_id, operator_id)
                    
                logger.info(f"Оператор {operator_id} освобожден от чата {chat_id}")
            except Exception as e:
                logger.error(f"Ошибка обновления БД при освобождении оператора: {e}")
    
    async def transfer_chat_to_operator(self, chat_id: int, new_operator_id: int, 
                                      from_operator_id: int, reason: str = "manual_transfer",
                                      admin_id: Optional[int] = None) -> bool:
        """Перевод чата другому оператору"""
        async with self._assignment_lock:
            # Проверяем, что новый оператор может принять чат
            if new_operator_id not in self.queue_manager.operators:
                logger.error(f"Новый оператор {new_operator_id} не найден")
                return False
            
            new_operator = self.queue_manager.operators[new_operator_id]
            if not new_operator.can_accept_chat:
                logger.error(f"Новый оператор {new_operator_id} не может принять чат")
                return False
            
            # Выполняем перевод
            success = await self.queue_manager.transfer_chat(chat_id, new_operator_id, reason)
            
            if success:
                try:
                    async with chat_db.get_async_session() as session:
                        # Выполняем перевод чата в БД
                        await chat_db.transfer_chat(
                            session, chat_id, new_operator_id, from_operator_id, None
                        )
                    
                    # Получаем информацию о клиенте
                    client_id = await self._get_client_id_from_chat(chat_id)
                    
                    # Отправляем Kafka события
                    await kafka_producer.send_chat_transferred(
                        chat_id, new_operator_id, new_operator.operator_type,
                        from_operator_id, client_id, reason
                    )
                    
                    if admin_id:
                        await kafka_producer.send_force_transfer(
                            admin_id, chat_id, new_operator_id, from_operator_id, reason
                        )
                    
                    logger.info(f"Чат {chat_id} переведен с оператора {from_operator_id} на {new_operator_id}")
                    return True
                    
                except Exception as e:
                    logger.error(f"Ошибка БД при переводе чата: {e}")
                    return False
            
            return False
    
    # Назначение юристов
    
    async def assign_personal_lawyer(self, client_id: int, lawyer_id: int, assigned_by: int) -> Optional[int]:
        """Назначение персонального юриста клиенту"""
        async with self._assignment_lock:
            try:
                # Проверяем, что юрист доступен
                if lawyer_id not in self.queue_manager.operators:
                    await self.queue_manager.register_operator(lawyer_id, "lawyer", 10)
                
                # Создаем новый чат с юристом
                async with chat_db.get_async_session() as session:
                    # Создаем чат клиента с юристом
                    lawyer_chat = await chat_db.create_chat(session, client_id, lawyer_id)
                    
                    # Добавляем запись о назначении юриста
                    await chat_db.create_lawyer_assignment(session, client_id, lawyer_id)
                
                # Сохраняем назначение
                self.lawyer_assignments[client_id] = lawyer_id
                
                # Отправляем Kafka событие
                await kafka_producer.send_lawyer_assigned(client_id, lawyer_id, lawyer_chat.id)
                
                logger.info(f"Клиенту {client_id} назначен персональный юрист {lawyer_id}")
                return lawyer_chat.id
                
            except Exception as e:
                logger.error(f"Ошибка назначения юриста: {e}")
                return None
    
    async def create_lawyer_chat(self, client_id: int, lawyer_id: int) -> Optional[int]:
        """Создание отдельного чата с юристом"""
        try:
            async with chat_db.get_async_session() as session:
                # Проверяем, нет ли уже активного чата с этим юристом
                existing_chat = await chat_db.get_active_lawyer_chat(session, client_id, lawyer_id)
                
                if existing_chat:
                    logger.info(f"У клиента {client_id} уже есть активный чат с юристом {lawyer_id}")
                    return existing_chat.id
                
                # Создаем новый чат
                lawyer_chat = await chat_db.create_chat(session, client_id, lawyer_id)
                
                # Добавляем участников
                await chat_db.add_chat_participant(session, lawyer_chat.id, client_id, "client")
                await chat_db.add_chat_participant(session, lawyer_chat.id, lawyer_id, "lawyer")
                
                logger.info(f"Создан чат {lawyer_chat.id} между клиентом {client_id} и юристом {lawyer_id}")
                return lawyer_chat.id
                
        except Exception as e:
            logger.error(f"Ошибка создания чата с юристом: {e}")
            return None
    
    async def get_client_lawyer(self, client_id: int) -> Optional[int]:
        """Получение назначенного юриста для клиента"""
        if client_id in self.lawyer_assignments:
            return self.lawyer_assignments[client_id]
        
        # Проверяем в БД
        try:
            async with chat_db.get_async_session() as session:
                assignment = await chat_db.get_active_lawyer_assignment(session, client_id)
                if assignment:
                    self.lawyer_assignments[client_id] = assignment.lawyer_id
                    return assignment.lawyer_id
        except Exception as e:
            logger.error(f"Ошибка получения назначенного юриста: {e}")
        
        return None
    
    # Принудительные действия (для администраторов)
    
    async def force_transfer_chat(self, chat_id: int, target_operator_id: int, 
                                 source_operator_id: int, admin_id: int, reason: str) -> bool:
        """Принудительный перевод чата администратором"""
        logger.info(f"Админ {admin_id} принудительно переводит чат {chat_id}")
        
        return await self.transfer_chat_to_operator(
            chat_id, target_operator_id, source_operator_id, 
            f"admin_force_transfer: {reason}", admin_id
        )
    
    async def force_close_chat(self, chat_id: int, admin_id: int, reason: str) -> bool:
        """Принудительное закрытие чата администратором"""
        try:
            async with chat_db.get_async_session() as session:
                await chat_db.close_chat(session, chat_id, admin_id, None)
            
            # Освобождаем оператора
            await self.release_operator_from_chat(chat_id)
            
            # Отправляем событие закрытия
            await kafka_producer.send_chat_closed(chat_id, admin_id, f"admin_force_close: {reason}")
            
            logger.info(f"Админ {admin_id} принудительно закрыл чат {chat_id}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка принудительного закрытия чата: {e}")
            return False
    
    # Вспомогательные методы
    
    async def _get_client_id_from_chat(self, chat_id: int) -> Optional[int]:
        """Получение ID клиента из чата"""
        try:
            async with chat_db.get_async_session() as session:
                chat = await chat_db.get_chat_by_id(session, chat_id)
                return chat.user_id if chat else None
        except Exception as e:
            logger.error(f"Ошибка получения клиента из чата {chat_id}: {e}")
            return None
    
    async def get_operator_chats(self, operator_id: int) -> List[int]:
        """Получение списка чатов оператора"""
        if operator_id in self.queue_manager.operators:
            return list(self.queue_manager.operators[operator_id].current_chats)
        return []
    
    async def get_chat_operator(self, chat_id: int) -> Optional[int]:
        """Получение оператора чата"""
        return self.queue_manager.chat_assignments.get(chat_id)
    
    async def is_operator_available(self, operator_id: int) -> bool:
        """Проверка доступности оператора"""
        if operator_id in self.queue_manager.operators:
            return self.queue_manager.operators[operator_id].can_accept_chat
        return False
    
    def get_assignment_stats(self) -> Dict:
        """Получение статистики назначений"""
        total_assignments = len(self.queue_manager.chat_assignments)
        operator_loads = {}
        
        for operator_id, operator in self.queue_manager.operators.items():
            operator_loads[operator_id] = {
                'type': operator.operator_type,
                'current_chats': len(operator.current_chats),
                'max_chats': operator.max_concurrent_chats,
                'utilization': len(operator.current_chats) / operator.max_concurrent_chats if operator.max_concurrent_chats > 0 else 0,
                'is_available': operator.can_accept_chat
            }
        
        return {
            'total_active_chats': total_assignments,
            'total_lawyer_assignments': len(self.lawyer_assignments),
            'operator_loads': operator_loads
        }


# Функция создания экземпляра (будет вызвана после инициализации всех зависимостей)
def create_assignment_manager(queue_manager, websocket_manager=None):
    """Создание экземпляра менеджера назначений"""
    return ChatAssignmentManager(queue_manager, websocket_manager)
