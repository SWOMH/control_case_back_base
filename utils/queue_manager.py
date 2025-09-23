"""
Менеджер очереди операторов и клиентов для чата поддержки
"""
import asyncio
import time
from typing import Dict, List, Set, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta, UTC
import logging

logger = logging.getLogger(__name__)


@dataclass
class QueuedClient:
    """Клиент в очереди ожидания оператора"""
    client_id: int
    chat_id: int
    timestamp: datetime
    priority: int = 0
    wait_time: int = 0
    metadata: Dict = field(default_factory=dict)


@dataclass
class OperatorStatus:
    """Статус оператора"""
    operator_id: int
    operator_type: str  # support, lawyer, salesman
    is_online: bool = False
    is_available: bool = True
    max_concurrent_chats: int = 5  # сколько у оператора может быть максимум чатов (регулировать нагрузку на оператора, но такое себе)
    current_chats: Set[int] = field(default_factory=set)
    last_activity: datetime = field(default_factory=datetime.utcnow)
    
    @property
    def can_accept_chat(self) -> bool:
        """Может ли оператор принять новый чат"""
        return (self.is_online and 
                self.is_available and 
                len(self.current_chats) < self.max_concurrent_chats)


class SupportQueueManager:
    """Менеджер очереди поддержки"""
    
    def __init__(self):
        # Очередь клиентов ожидающих операторов
        self.waiting_clients: Dict[int, QueuedClient] = {}
        
        # Статусы операторов
        self.operators: Dict[int, OperatorStatus] = {}
        
        # Назначения чатов операторам
        self.chat_assignments: Dict[int, int] = {}  # chat_id -> operator_id
        
        # Блокировки для обработки одновременных запросов
        self._queue_lock = asyncio.Lock()
        self._assignment_lock = asyncio.Lock()
        
        # Задача обновления времени ожидания
        self._update_task: Optional[asyncio.Task] = None
        self._running = False
    
    async def start(self):
        """Запуск менеджера очереди"""
        if not self._running:
            self._running = True
            self._update_task = asyncio.create_task(self._update_wait_times())
            logger.info("Менеджер очереди запущен")
    
    async def stop(self):
        """Остановка менеджера очереди"""
        if self._running:
            self._running = False
            if self._update_task:
                self._update_task.cancel()
                try:
                    await self._update_task
                except asyncio.CancelledError:
                    pass
            logger.info("Менеджер очереди остановлен")
    
    async def _update_wait_times(self):
        """Обновление времени ожидания клиентов"""
        try:
            while self._running:
                current_time = datetime.now(UTC)
                
                async with self._queue_lock:
                    for client in self.waiting_clients.values():
                        client.wait_time = int((current_time - client.timestamp).total_seconds())
                
                await asyncio.sleep(30)  # Обновляем каждые 30 секунд
                
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Ошибка в обновлении времени ожидания: {e}")
    
    # Управление операторами
    
    async def register_operator(self, operator_id: int, operator_type: str, max_concurrent_chats: int = 5):
        """Регистрация оператора в системе"""
        if operator_id not in self.operators:
            self.operators[operator_id] = OperatorStatus(
                operator_id=operator_id,
                operator_type=operator_type,
                max_concurrent_chats=max_concurrent_chats
            )
            logger.info(f"Оператор {operator_id} ({operator_type}) зарегистрирован")
    
    async def set_operator_online(self, operator_id: int, operator_type: str, max_concurrent_chats: int = 5):
        """Перевод оператора в онлайн"""
        await self.register_operator(operator_id, operator_type, max_concurrent_chats)
        
        operator = self.operators[operator_id]
        operator.is_online = True
        operator.is_available = True
        operator.last_activity = datetime.now(UTC)
        
        logger.info(f"Оператор {operator_id} ({operator_type}) в онлайн")
        
        # Проверяем, есть ли ожидающие клиенты
        await self._try_auto_assign_clients()
    
    async def set_operator_offline(self, operator_id: int):
        """Перевод оператора в оффлайн"""
        if operator_id in self.operators:
            operator = self.operators[operator_id]
            operator.is_online = False
            operator.is_available = False
            
            # Переводим все активные чаты оператора другим операторам
            chats_to_transfer = list(operator.current_chats)
            for chat_id in chats_to_transfer:
                await self._transfer_chat_to_available_operator(chat_id, operator_id, "operator_offline")
            
            logger.info(f"Оператор {operator_id} перешел в оффлайн")
    
    async def set_operator_busy(self, operator_id: int, busy: bool = True):
        """Установка статуса занятости оператора"""
        if operator_id in self.operators:
            self.operators[operator_id].is_available = not busy
            status = "занят" if busy else "доступен"
            logger.info(f"Оператор {operator_id} {status}")
    
    def get_available_operators(self, operator_type: Optional[str] = None) -> List[OperatorStatus]:
        """Получение списка доступных операторов"""
        available = []
        for operator in self.operators.values():
            if operator.can_accept_chat:
                if operator_type is None or operator.operator_type == operator_type:
                    available.append(operator)
        
        # Сортируем по загрузке (менее загруженные первыми)
        available.sort(key=lambda op: len(op.current_chats))
        return available
    
    def get_operator_stats(self, operator_id: int) -> Optional[Dict]:
        """Получение статистики оператора"""
        if operator_id in self.operators:
            operator = self.operators[operator_id]
            return {
                'operator_id': operator_id,
                'operator_type': operator.operator_type,
                'is_online': operator.is_online,
                'is_available': operator.is_available,
                'current_chats_count': len(operator.current_chats),
                'max_concurrent_chats': operator.max_concurrent_chats,
                'last_activity': operator.last_activity.isoformat()
            }
        return None
    
    # Управление очередью клиентов
    
    async def add_client_to_queue(self, client_id: int, chat_id: int, priority: int = 0, metadata: Optional[Dict] = None):
        """Добавление клиента в очередь ожидания"""
        async with self._queue_lock:
            if client_id not in self.waiting_clients:
                queued_client = QueuedClient(
                    client_id=client_id,
                    chat_id=chat_id,
                    timestamp=datetime.now(UTC),
                    priority=priority,
                    metadata=metadata or {}
                )
                self.waiting_clients[client_id] = queued_client
                
                logger.info(f"Клиент {client_id} добавлен в очередь (приоритет: {priority})")
                
                # Пытаемся сразу назначить доступного оператора
                await self._try_assign_operator_to_client(client_id)
    
    async def remove_client_from_queue(self, client_id: int) -> bool:
        """Удаление клиента из очереди"""
        async with self._queue_lock:
            if client_id in self.waiting_clients:
                del self.waiting_clients[client_id]
                logger.info(f"Клиент {client_id} удален из очереди")
                return True
            return False
    
    async def update_queue_position(self, client_id: int, new_priority: int) -> int:
        """Обновление приоритета клиента в очереди"""
        async with self._queue_lock:
            if client_id in self.waiting_clients:
                self.waiting_clients[client_id].priority = new_priority
                logger.info(f"Приоритет клиента {client_id} изменен на {new_priority}")
        
        return await self.get_queue_position(client_id)
    
    async def get_queue_position(self, client_id: int) -> int:
        """Получение позиции клиента в очереди"""
        if client_id not in self.waiting_clients:
            return -1
        
        # Сортируем клиентов по приоритету (выше приоритет = меньше номер в очереди)
        # Затем по времени ожидания
        sorted_clients = sorted(
            self.waiting_clients.values(),
            key=lambda c: (-c.priority, c.timestamp)
        )
        
        for position, client in enumerate(sorted_clients, 1):
            if client.client_id == client_id:
                return position
        return -1
    
    def get_queue_status(self) -> Dict:
        """Получение статуса очереди"""
        return {
            'total_waiting': len(self.waiting_clients),
            'average_wait_time': sum(c.wait_time for c in self.waiting_clients.values()) / len(self.waiting_clients) if self.waiting_clients else 0,
            'available_operators': len(self.get_available_operators()),
            'queue_by_priority': self._get_queue_by_priority()
        }
    
    def _get_queue_by_priority(self) -> Dict[int, int]:
        """Получение количества клиентов по приоритетам"""
        priority_counts = {}
        for client in self.waiting_clients.values():
            priority_counts[client.priority] = priority_counts.get(client.priority, 0) + 1
        return priority_counts
    
    # Управление назначениями чатов
    
    async def assign_chat_to_operator(self, chat_id: int, operator_id: int, client_id: int) -> bool:
        """Назначение чата оператору"""
        async with self._assignment_lock:
            if operator_id not in self.operators:
                return False
            
            operator = self.operators[operator_id]
            if not operator.can_accept_chat:
                return False
            
            # Назначаем чат
            self.chat_assignments[chat_id] = operator_id
            operator.current_chats.add(chat_id)
            operator.last_activity = datetime.now(UTC)
            
            # Удаляем клиента из очереди
            await self.remove_client_from_queue(client_id)
            
            logger.info(f"Чат {chat_id} назначен оператору {operator_id}")
            return True
    
    async def release_operator_from_chat(self, chat_id: int) -> bool:
        """Освобождение оператора от чата"""
        async with self._assignment_lock:
            if chat_id not in self.chat_assignments:
                return False
            
            operator_id = self.chat_assignments[chat_id]
            del self.chat_assignments[chat_id]
            
            if operator_id in self.operators:
                operator = self.operators[operator_id]
                operator.current_chats.discard(chat_id)
                operator.last_activity = datetime.now(UTC)
                
                # Если оператор снова доступен, проверяем очередь
                if operator.can_accept_chat:
                    await self._try_auto_assign_clients()
            
            logger.info(f"Оператор {operator_id} освобожден от чата {chat_id}")
            return True
    
    async def transfer_chat(self, chat_id: int, new_operator_id: int, reason: str = "manual_transfer") -> bool:
        """Перевод чата другому оператору"""
        if chat_id not in self.chat_assignments:
            return False
        
        old_operator_id = self.chat_assignments[chat_id]
        
        # Проверяем, что новый оператор может принять чат
        if new_operator_id not in self.operators or not self.operators[new_operator_id].can_accept_chat:
            return False
        
        async with self._assignment_lock:
            # Освобождаем старого оператора
            if old_operator_id in self.operators:
                self.operators[old_operator_id].current_chats.discard(chat_id)
            
            # Назначаем новому оператору
            self.chat_assignments[chat_id] = new_operator_id
            self.operators[new_operator_id].current_chats.add(chat_id)
            self.operators[new_operator_id].last_activity = datetime.now(UTC)
        
        logger.info(f"Чат {chat_id} переведен с оператора {old_operator_id} на {new_operator_id}, причина: {reason}")
        return True
    
    # Автоматическое назначение
    
    async def _try_assign_operator_to_client(self, client_id: int):
        """Попытка назначить оператора клиенту"""
        if client_id not in self.waiting_clients:
            return
        
        client = self.waiting_clients[client_id]
        available_operators = self.get_available_operators("support")  # Сначала ищем операторов поддержки
        
        if available_operators:
            # Выбираем оператора с наименьшей загрузкой
            selected_operator = available_operators[0]
            await self.assign_chat_to_operator(client.chat_id, selected_operator.operator_id, client_id)
            
            # Отправляем событие о назначении (это будет делать вызывающий код через Kafka)
            return selected_operator.operator_id
        
        return None
    
    async def _try_auto_assign_clients(self):
        """Попытка автоматически назначить операторов ожидающим клиентам"""
        if not self.waiting_clients:
            return
        
        # Сортируем клиентов по приоритету и времени ожидания
        sorted_clients = sorted(
            self.waiting_clients.values(),
            key=lambda c: (-c.priority, c.timestamp)
        )
        
        for client in sorted_clients:
            operator_id = await self._try_assign_operator_to_client(client.client_id)
            if operator_id:
                logger.info(f"Автоматически назначен оператор {operator_id} клиенту {client.client_id}")
    
    async def _transfer_chat_to_available_operator(self, chat_id: int, offline_operator_id: int, reason: str):
        """Перевод чата доступному оператору при уходе оператора"""
        available_operators = self.get_available_operators("support")
        
        if available_operators:
            new_operator = available_operators[0]
            await self.transfer_chat(chat_id, new_operator.operator_id, reason)
            logger.info(f"Чат {chat_id} автоматически переведен на оператора {new_operator.operator_id}")
        else:
            # Нет доступных операторов - возвращаем клиента в очередь
            if chat_id in self.chat_assignments:
                # Получаем информацию о клиенте из базы данных (нужно будет реализовать)
                # Пока просто логируем
                logger.warning(f"Нет доступных операторов для перевода чата {chat_id}")
                await self.release_operator_from_chat(chat_id)


# Глобальный экземпляр менеджера очереди
queue_manager = SupportQueueManager()
