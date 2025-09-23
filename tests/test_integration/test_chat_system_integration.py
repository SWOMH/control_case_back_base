# """
# Интеграционные тесты всей системы чата поддержки
# """
# import pytest
# import pytest_asyncio
# import asyncio
# import json
# from unittest.mock import AsyncMock, patch, MagicMock
# from fastapi.testclient import TestClient

# from utils.chat_system_init import SupportChatSystem, startup_chat_system, shutdown_chat_system
# from tests.conftest import MockWebSocket, TEST_USER_ID, TEST_CLIENT_ID, TEST_OPERATOR_ID, TEST_CHAT_ID


# class TestFullChatSystemIntegration:
#     """Интеграционные тесты полной системы чата"""
    
#     @pytest_asyncio.fixture
#     async def chat_system(self):
#         """Создает полную систему чата для тестов"""
#         system = SupportChatSystem()
        
#         # Мокаем все внешние зависимости
#         with patch('utils.kafka_producer.kafka_producer') as mock_producer, \
#              patch('utils.kafka_consumer.kafka_consumer') as mock_consumer, \
#              patch('database.logic.chats.chat.chat_db') as mock_chat_db:
            
#             # Настраиваем моки
#             mock_producer._started = False
#             mock_producer.start = AsyncMock()
#             mock_producer.stop = AsyncMock()
            
#             mock_consumer._started = False
#             mock_consumer.start = AsyncMock()
#             mock_consumer.stop = AsyncMock()
#             mock_consumer.register_handler = MagicMock()
            
#             mock_chat_db.get_async_session = AsyncMock()
            
#             await system.initialize()
#             yield system
#             await system.shutdown()
    
#     async def test_system_initialization(self, chat_system):
#         """Тест инициализации всей системы"""
#         assert chat_system.is_running()
        
#         status = chat_system.get_system_status()
#         assert status["status"] == "running"
#         assert "queue_manager" in status
#         assert "kafka" in status
#         assert "websockets" in status
#         assert "assignments" in status
    
#     async def test_client_to_operator_chat_flow(self, chat_system):
#         """Тест полного потока: клиент -> очередь -> назначение оператору -> чат"""
        
#         # Создаем мок пользователей
#         client_user = MagicMock()
#         client_user.id = TEST_CLIENT_ID
#         client_user.is_client = True
        
#         operator_user = MagicMock()
#         operator_user.id = TEST_OPERATOR_ID
#         operator_user.is_client = False
        
#         with patch('endpoints.chats.chat_kafka.get_current_user') as mock_get_user, \
#              patch('endpoints.chats.chat_kafka.chat_db') as mock_chat_db, \
#              patch('endpoints.chats.chat_kafka.kafka_producer') as mock_producer:
            
#             # Настраиваем возврат пользователей
#             mock_get_user.side_effect = lambda token: client_user if "client" in token else operator_user
            
#             # Настраиваем создание чата
#             mock_chat = MagicMock()
#             mock_chat.id = TEST_CHAT_ID
#             mock_chat_db.get_active_chat_by_user.return_value = None
#             mock_chat_db.create_chat.return_value = mock_chat
            
#             # 1. Клиент подключается к чату
#             queue_manager = chat_system.assignment_manager.queue_manager
            
#             # Добавляем клиента в очередь
#             await queue_manager.add_client_to_queue(TEST_CLIENT_ID, TEST_CHAT_ID)
            
#             # Проверяем что клиент в очереди
#             assert TEST_CLIENT_ID in queue_manager.waiting_clients
            
#             # 2. Оператор подключается к системе
#             await queue_manager.set_operator_online(TEST_OPERATOR_ID, "support", max_concurrent_chats=5)
            
#             # Проверяем что оператор зарегистрирован
#             assert TEST_OPERATOR_ID in queue_manager.operators
#             operator = queue_manager.operators[TEST_OPERATOR_ID]
#             assert operator.is_online
#             assert operator.can_accept_chat
            
#             # 3. Назначаем чат оператору
#             success = await queue_manager.assign_chat_to_operator(TEST_CHAT_ID, TEST_OPERATOR_ID, TEST_CLIENT_ID)
#             assert success
            
#             # Проверяем что клиент удален из очереди
#             assert TEST_CLIENT_ID not in queue_manager.waiting_clients
            
#             # Проверяем что чат назначен оператору
#             assert TEST_CHAT_ID in queue_manager.chat_assignments
#             assert queue_manager.chat_assignments[TEST_CHAT_ID] == TEST_OPERATOR_ID
#             assert TEST_CHAT_ID in operator.current_chats
    
#     async def test_chat_transfer_flow(self, chat_system):
#         """Тест потока перевода чата между операторами"""
        
#         queue_manager = chat_system.assignment_manager.queue_manager
        
#         # Настраиваем двух операторов
#         operator1_id = 123
#         operator2_id = 456
        
#         await queue_manager.set_operator_online(operator1_id, "support")
#         await queue_manager.set_operator_online(operator2_id, "support")
        
#         # Назначаем чат первому оператору
#         await queue_manager.assign_chat_to_operator(TEST_CHAT_ID, operator1_id, TEST_CLIENT_ID)
        
#         # Проверяем исходное состояние
#         assert queue_manager.chat_assignments[TEST_CHAT_ID] == operator1_id
#         assert TEST_CHAT_ID in queue_manager.operators[operator1_id].current_chats
#         assert TEST_CHAT_ID not in queue_manager.operators[operator2_id].current_chats
        
#         # Переводим чат второму оператору
#         success = await queue_manager.transfer_chat(TEST_CHAT_ID, operator2_id, "test_transfer")
#         assert success
        
#         # Проверяем результат перевода
#         assert queue_manager.chat_assignments[TEST_CHAT_ID] == operator2_id
#         assert TEST_CHAT_ID not in queue_manager.operators[operator1_id].current_chats
#         assert TEST_CHAT_ID in queue_manager.operators[operator2_id].current_chats
    
#     async def test_lawyer_assignment_flow(self, chat_system):
#         """Тест потока назначения персонального юриста"""
        
#         assignment_manager = chat_system.assignment_manager
        
#         client_id = TEST_CLIENT_ID
#         lawyer_id = 789
#         support_id = TEST_OPERATOR_ID
        
#         with patch('utils.assignment_manager.chat_db') as mock_chat_db, \
#              patch('utils.assignment_manager.kafka_producer') as mock_producer:
            
#             # Настраиваем создание чата с юристом
#             mock_chat = MagicMock()
#             mock_chat.id = 999
#             mock_chat_db.create_chat.return_value = mock_chat
#             mock_chat_db.create_lawyer_assignment.return_value = MagicMock()
            
#             # Назначаем юриста
#             lawyer_chat_id = await assignment_manager.assign_personal_lawyer(
#                 client_id, lawyer_id, support_id
#             )
            
#             assert lawyer_chat_id == 999
            
#             # Проверяем что назначение сохранено
#             assert assignment_manager.lawyer_assignments[client_id] == lawyer_id
            
#             # Проверяем вызовы БД
#             mock_chat_db.create_chat.assert_called_once()
#             mock_chat_db.create_lawyer_assignment.assert_called_once()
            
#             # Проверяем отправку события
#             mock_producer.send_lawyer_assigned.assert_called_once_with(
#                 client_id, lawyer_id, 999
#             )
    
#     async def test_operator_offline_chat_redistribution(self, chat_system):
#         """Тест перераспределения чатов при отключении оператора"""
        
#         queue_manager = chat_system.assignment_manager.queue_manager
        
#         # Настраиваем операторов
#         offline_operator_id = 123
#         online_operator_id = 456
        
#         await queue_manager.set_operator_online(offline_operator_id, "support")
#         await queue_manager.set_operator_online(online_operator_id, "support")
        
#         # Назначаем чат первому оператору
#         await queue_manager.assign_chat_to_operator(TEST_CHAT_ID, offline_operator_id, TEST_CLIENT_ID)
        
#         # Переводим первого оператора в оффлайн
#         with patch.object(queue_manager, '_transfer_chat_to_available_operator') as mock_transfer:
#             await queue_manager.set_operator_offline(offline_operator_id)
            
#             # Проверяем что был вызван перевод чата
#             mock_transfer.assert_called_once_with(TEST_CHAT_ID, offline_operator_id, "operator_offline")
        
#         # Проверяем что оператор оффлайн
#         operator = queue_manager.operators[offline_operator_id]
#         assert not operator.is_online
#         assert not operator.is_available
    
#     # async def test_queue_priority_handling(self, chat_system):
#     #     """Тест обработки приоритетов в очереди"""
        
#     #     queue_manager = chat_system.assignment_manager.queue_manager
        
#     #     # Добавляем клиентов с разными приоритетами
#     #     await queue_manager.add_client_to_queue(1, 101, priority=0)  # низкий
#     #     await queue_manager.add_client_to_queue(2, 102, priority=2)  # высокий
#     #     await queue_manager.add_client_to_queue(3, 103, priority=1)  # средний
        
#     #     # Проверяем позиции в очереди
#     #     assert await queue_manager.get_queue_position(2) == 1  # высокий приоритет первый
#     #     assert await queue_manager.get_queue_position(3) == 2  # средний приоритет второй
#     #     assert await queue_manager.get_queue_position(1) == 3  # низкий приоритет последний
        
#     #     # Добавляем оператора
#     #     await queue_manager.set_operator_online(TEST_OPERATOR_ID, "support", max_concurrent_chats=1)
        
#     #     # Имитируем автоназначение - должен получить клиента с высшим приоритетом
#     #     with patch.object(queue_manager, '_try_assign_operator_to_client') as mock_assign:
#     #         mock_assign.return_value = TEST_OPERATOR_ID
            
#     #         await queue_manager._try_auto_assign_clients()
            
#     #         # Должен быть вызван для клиента с приоритетом 2
#     #         mock_assign.assert_called_once_with(2)
    
#     async def test_concurrent_operations(self, chat_system):
#         """Тест одновременных операций в системе"""
        
#         queue_manager = chat_system.assignment_manager.queue_manager
        
#         # Регистрируем операторов
#         operator_ids = [100, 200, 300]
#         for op_id in operator_ids:
#             await queue_manager.set_operator_online(op_id, "support", max_concurrent_chats=2)
        
#         # Одновременно добавляем клиентов в очередь
#         client_ids = list(range(1, 11))  # 10 клиентов
#         chat_ids = list(range(101, 111))  # 10 чатов
        
#         async def add_client(client_id, chat_id):
#             await queue_manager.add_client_to_queue(client_id, chat_id)
        
#         # Запускаем одновременное добавление
#         await asyncio.gather(*[add_client(cid, chid) for cid, chid in zip(client_ids, chat_ids)])
        
#         # Проверяем что все клиенты добавлены
#         assert len(queue_manager.waiting_clients) == 10
        
#         # Одновременно назначаем чаты
#         async def assign_chat(chat_id, operator_id, client_id):
#             return await queue_manager.assign_chat_to_operator(chat_id, operator_id, client_id)
        
#         # Назначаем первые 6 чатов (по 2 на каждого оператора)
#         assignments = []
#         for i in range(6):
#             operator_id = operator_ids[i % 3]  # распределяем между операторами
#             assignments.append(assign_chat(chat_ids[i], operator_id, client_ids[i]))
        
#         results = await asyncio.gather(*assignments)
        
#         # Все назначения должны быть успешными
#         assert all(results)
        
#         # Проверяем что операторы достигли лимита
#         for op_id in operator_ids:
#             operator = queue_manager.operators[op_id]
#             assert len(operator.current_chats) == 2
#             assert not operator.can_accept_chat  # достигли лимита
    
#     async def test_system_statistics(self, chat_system):
#         """Тест получения статистики системы"""
        
#         queue_manager = chat_system.assignment_manager.queue_manager
#         assignment_manager = chat_system.assignment_manager
#         websocket_manager = chat_system.assignment_manager.websocket_manager
        
#         # Настраиваем систему с данными
#         await queue_manager.set_operator_online(1, "support", 5)
#         await queue_manager.set_operator_online(2, "lawyer", 3)
#         await queue_manager.add_client_to_queue(101, 201)
#         await queue_manager.add_client_to_queue(102, 202, priority=1)
        
#         # Назначаем один чат
#         await queue_manager.assign_chat_to_operator(203, 1, 103)
#         assignment_manager.lawyer_assignments[104] = 2
        
#         # Имитируем WebSocket соединения
#         websocket_manager.user_connections = {1: MagicMock(), 2: MagicMock(), 101: MagicMock()}
#         websocket_manager.operator_connections = {1: MagicMock(), 2: MagicMock()}
#         websocket_manager.chat_connections = {203: {1, 103}}
        
#         # Получаем статистику системы
#         system_status = chat_system.get_system_status()
        
#         # Проверяем общий статус
#         assert system_status["status"] == "running"
        
#         # Проверяем статистику менеджера очереди
#         queue_stats = system_status["queue_manager"]
#         assert queue_stats["operators_count"] == 2
#         assert queue_stats["waiting_clients"] == 2
#         assert queue_stats["active_chats"] == 1
        
#         # Получаем детальную статистику
#         queue_status = queue_manager.get_queue_status()
#         assignment_stats = assignment_manager.get_assignment_stats()
#         connection_stats = websocket_manager.get_connection_stats()
        
#         # Проверяем статистику очереди
#         assert queue_status["total_waiting"] == 2
#         assert queue_status["available_operators"] == 2
        
#         # Проверяем статистику назначений
#         assert assignment_stats["total_active_chats"] == 1
#         assert assignment_stats["total_lawyer_assignments"] == 1
        
#         # Проверяем статистику соединений
#         assert connection_stats["total_connections"] == 3
#         assert connection_stats["operator_connections"] == 2
#         assert connection_stats["active_chats"] == 1
    
#     async def test_error_recovery(self, chat_system):
#         """Тест восстановления после ошибок"""
        
#         queue_manager = chat_system.assignment_manager.queue_manager
        
#         # Настраиваем оператора и клиента
#         await queue_manager.set_operator_online(TEST_OPERATOR_ID, "support")
#         await queue_manager.add_client_to_queue(TEST_CLIENT_ID, TEST_CHAT_ID)
        
#         # Имитируем ошибку при назначении чата
#         with patch.object(queue_manager, 'assign_chat_to_operator') as mock_assign:
#             mock_assign.side_effect = Exception("Database error")
            
#             # Попытка назначения должна вызвать исключение
#             with pytest.raises(Exception):
#                 await mock_assign(TEST_CHAT_ID, TEST_OPERATOR_ID, TEST_CLIENT_ID)
        
#         # Система должна остаться в консистентном состоянии
#         assert TEST_CLIENT_ID in queue_manager.waiting_clients
#         assert TEST_CHAT_ID not in queue_manager.chat_assignments
#         assert TEST_OPERATOR_ID in queue_manager.operators
#         assert queue_manager.operators[TEST_OPERATOR_ID].is_online
        
#         # После устранения ошибки операция должна работать
#         success = await queue_manager.assign_chat_to_operator(TEST_CHAT_ID, TEST_OPERATOR_ID, TEST_CLIENT_ID)
#         assert success
    
#     async def test_system_shutdown_cleanup(self, chat_system):
#         """Тест корректной очистки при завершении системы"""
        
#         # Добавляем данные в систему
#         queue_manager = chat_system.assignment_manager.queue_manager
#         await queue_manager.set_operator_online(TEST_OPERATOR_ID, "support")
#         await queue_manager.add_client_to_queue(TEST_CLIENT_ID, TEST_CHAT_ID)
        
#         # Проверяем что система работает
#         assert chat_system.is_running()
#         assert len(queue_manager.operators) > 0
#         assert len(queue_manager.waiting_clients) > 0
        
#         # Завершаем систему
#         await chat_system.shutdown()
        
#         # Проверяем что система остановлена
#         assert not chat_system.is_running()
        
#         # Статус должен показывать остановку
#         status = chat_system.get_system_status()
#         assert status["status"] == "stopped"


# class TestChatSystemLifecycle:
#     """Тесты жизненного цикла системы чата"""
    
#     async def test_startup_shutdown_functions(self):
#         """Тест функций запуска и остановки системы"""
        
#         with patch('utils.chat_system_init.chat_system') as mock_system:
#             mock_system.initialize = AsyncMock()
#             mock_system.shutdown = AsyncMock()
            
#             # Тест запуска
#             await startup_chat_system()
#             mock_system.initialize.assert_called_once()
            
#             # Тест остановки
#             await shutdown_chat_system()
#             mock_system.shutdown.assert_called_once()
    
#     async def test_multiple_startup_shutdown_cycles(self):
#         """Тест множественных циклов запуска/остановки"""
        
#         system = SupportChatSystem()
        
#         with patch('utils.kafka_producer.kafka_producer') as mock_producer, \
#              patch('utils.kafka_consumer.kafka_consumer') as mock_consumer:
            
#             mock_producer.start = AsyncMock()
#             mock_producer.stop = AsyncMock()
#             mock_consumer.start = AsyncMock()
#             mock_consumer.stop = AsyncMock()
#             mock_consumer.register_handler = MagicMock()
            
#             # Несколько циклов запуска/остановки
#             for i in range(3):
#                 await system.initialize()
#                 assert system.is_running()
                
#                 await system.shutdown()
#                 assert not system.is_running()
            
#             # Проверяем что все компоненты были корректно запущены/остановлены
#             assert mock_producer.start.call_count == 3
#             assert mock_producer.stop.call_count == 3
    
#     async def test_kafka_enabled_disabled_modes(self):
#         """Тест работы в режимах с включенным и отключенным Kafka"""
        
#         # Тест с отключенным Kafka (mock режим)
#         with patch('utils.chat_system_init.KAFKA_ENABLED', False):
#             system = SupportChatSystem()
            
#             with patch('utils.kafka_producer.kafka_producer') as mock_producer, \
#                  patch('utils.kafka_consumer.kafka_consumer') as mock_consumer:
                
#                 mock_producer.start = AsyncMock()
#                 mock_consumer.start = AsyncMock()
#                 mock_consumer.register_handler = MagicMock()
                
#                 await system.initialize()
                
#                 status = system.get_system_status()
#                 assert status["kafka_enabled"] is False
#                 assert status["mode"] == "mock"
                
#                 await system.shutdown()
        
#         # Тест с включенным Kafka
#         with patch('utils.chat_system_init.KAFKA_ENABLED', True):
#             system = SupportChatSystem()
            
#             with patch('utils.kafka_producer.kafka_producer') as mock_producer, \
#                  patch('utils.kafka_consumer.kafka_consumer') as mock_consumer:
                
#                 mock_producer.start = AsyncMock()
#                 mock_consumer.start = AsyncMock()
#                 mock_consumer.register_handler = MagicMock()
                
#                 await system.initialize()
                
#                 status = system.get_system_status()
#                 assert status["kafka_enabled"] is True
#                 assert status["mode"] == "production"
                
#                 await system.shutdown()


# class TestRealWorldScenarios:
#     """Тесты реальных сценариев использования"""
    
#     @pytest_asyncio.fixture
#     async def chat_system(self):
#         """Создает систему для реальных сценариев"""
#         system = SupportChatSystem()
        
#         with patch('utils.kafka_producer.kafka_producer') as mock_producer, \
#              patch('utils.kafka_consumer.kafka_consumer') as mock_consumer, \
#              patch('database.logic.chats.chat.chat_db') as mock_chat_db:
            
#             mock_producer._started = False
#             mock_producer.start = AsyncMock()
#             mock_producer.stop = AsyncMock()
            
#             mock_consumer._started = False
#             mock_consumer.start = AsyncMock()
#             mock_consumer.stop = AsyncMock()
#             mock_consumer.register_handler = MagicMock()
            
#             await system.initialize()
#             yield system
#             await system.shutdown()
    
#     async def test_high_load_scenario(self, chat_system):
#         """Тест сценария высокой нагрузки"""
        
#         queue_manager = chat_system.assignment_manager.queue_manager
        
#         # Добавляем 10 операторов
#         operator_ids = list(range(1, 11))
#         for op_id in operator_ids:
#             await queue_manager.set_operator_online(op_id, "support", max_concurrent_chats=5)
        
#         # Добавляем 100 клиентов
#         client_ids = list(range(101, 201))
#         chat_ids = list(range(201, 301))
        
#         for client_id, chat_id in zip(client_ids, chat_ids):
#             await queue_manager.add_client_to_queue(client_id, chat_id)
        
#         # Проверяем что все клиенты в очереди
#         assert len(queue_manager.waiting_clients) == 100
        
#         # Назначаем максимальное количество чатов (50 чатов для 10 операторов по 5 чатов)
#         assigned_count = 0
#         for chat_id, client_id in zip(chat_ids[:50], client_ids[:50]):
#             operator_id = operator_ids[assigned_count % 10]
#             operator = queue_manager.operators[operator_id]
            
#             if operator.can_accept_chat:
#                 success = await queue_manager.assign_chat_to_operator(chat_id, operator_id, client_id)
#                 if success:
#                     assigned_count += 1
        
#         # Проверяем что все операторы загружены
#         for op_id in operator_ids:
#             operator = queue_manager.operators[op_id]
#             assert len(operator.current_chats) == 5
#             assert not operator.can_accept_chat
        
#         # Остальные клиенты должны остаться в очереди
#         assert len(queue_manager.waiting_clients) == 50
    
#     async def test_lawyer_escalation_scenario(self, chat_system):
#         """Тест сценария эскалации к юристу"""
        
#         assignment_manager = chat_system.assignment_manager
#         queue_manager = chat_system.assignment_manager.queue_manager
        
#         client_id = 123
#         support_id = 456
#         lawyer_id = 789
#         support_chat_id = 111
        
#         with patch('utils.assignment_manager.chat_db') as mock_chat_db, \
#              patch('utils.assignment_manager.kafka_producer') as mock_producer:
            
#             # 1. Клиент общается с поддержкой
#             await queue_manager.set_operator_online(support_id, "support")
#             await queue_manager.assign_chat_to_operator(support_chat_id, support_id, client_id)
            
#             # 2. Поддержка назначает персонального юриста
#             mock_lawyer_chat = MagicMock()
#             mock_lawyer_chat.id = 222
#             mock_chat_db.create_chat.return_value = mock_lawyer_chat
            
#             lawyer_chat_id = await assignment_manager.assign_personal_lawyer(
#                 client_id, lawyer_id, support_id
#             )
            
#             # 3. Проверяем результат
#             assert lawyer_chat_id == 222
#             assert assignment_manager.lawyer_assignments[client_id] == lawyer_id
            
#             # 4. Клиент теперь может общаться и с поддержкой, и с юристом
#             support_chat_operator = await assignment_manager.get_chat_operator(support_chat_id)
#             assigned_lawyer = await assignment_manager.get_client_lawyer(client_id)
            
#             assert support_chat_operator == support_id
#             assert assigned_lawyer == lawyer_id
    
#     async def test_operator_shift_change_scenario(self, chat_system):
#         """Тест сценария смены операторов"""
        
#         queue_manager = chat_system.assignment_manager.queue_manager
        
#         # Дневная смена операторов
#         day_operators = [1, 2, 3]
#         # Ночная смена операторов  
#         night_operators = [4, 5]
        
#         # Активируем дневную смену
#         for op_id in day_operators:
#             await queue_manager.set_operator_online(op_id, "support", max_concurrent_chats=3)
        
#         # Назначаем чаты дневной смене
#         chat_assignments = {}
#         for i, op_id in enumerate(day_operators):
#             for j in range(2):  # по 2 чата каждому
#                 chat_id = (i * 2) + j + 100
#                 client_id = chat_id + 1000
#                 await queue_manager.assign_chat_to_operator(chat_id, op_id, client_id)
#                 chat_assignments[chat_id] = op_id
        
#         # Проверяем что все чаты назначены
#         assert len(queue_manager.chat_assignments) == 6
        
#         # Начинается смена: активируем ночную смену
#         for op_id in night_operators:
#             await queue_manager.set_operator_online(op_id, "support", max_concurrent_chats=5)
        
#         # Переводим чаты от дневной смены к ночной
#         night_op_index = 0
#         for chat_id, day_op_id in list(chat_assignments.items()):
#             night_op_id = night_operators[night_op_index % len(night_operators)]
            
#             success = await queue_manager.transfer_chat(chat_id, night_op_id, "shift_change")
#             assert success
            
#             night_op_index += 1
        
#         # Деактивируем дневную смену
#         for op_id in day_operators:
#             await queue_manager.set_operator_offline(op_id)
        
#         # Проверяем что все чаты переведены на ночную смену
#         for chat_id in chat_assignments.keys():
#             assigned_operator = queue_manager.chat_assignments.get(chat_id)
#             assert assigned_operator in night_operators
        
#         # Проверяем что дневные операторы оффлайн
#         for op_id in day_operators:
#             operator = queue_manager.operators[op_id]
#             assert not operator.is_online
#             assert len(operator.current_chats) == 0
    
#     async def test_priority_queue_scenario(self, chat_system):
#         """Тест сценария приоритетной очереди"""
        
#         queue_manager = chat_system.assignment_manager.queue_manager
        
#         # Добавляем оператора
#         await queue_manager.set_operator_online(1, "support", max_concurrent_chats=1)
        
#         # Добавляем клиентов с разными приоритетами
#         clients = [
#             (101, 201, 0, "обычный клиент"),
#             (102, 202, 1, "постоянный клиент"),
#             (103, 203, 2, "VIP клиент"),
#             (104, 204, 0, "обычный клиент 2"),
#             (105, 205, 3, "критический случай")
#         ]
        
#         for client_id, chat_id, priority, description in clients:
#             await queue_manager.add_client_to_queue(
#                 client_id, chat_id, priority, {"description": description}
#             )
        
#         # Проверяем позиции в очереди (высший приоритет - первый)
#         positions = {}
#         for client_id, _, _, _ in clients:
#             positions[client_id] = await queue_manager.get_queue_position(client_id)
        
#         # Должны быть отсортированы по приоритету
#         assert positions[105] == 1  # критический случай (приоритет 3)
#         assert positions[103] == 2  # VIP клиент (приоритет 2)
#         assert positions[102] == 3  # постоянный клиент (приоритет 1)
#         # Обычные клиенты с приоритетом 0 - по времени добавления
#         assert positions[101] == 4  # добавлен первым
#         assert positions[104] == 5  # добавлен вторым
        
#         # Назначаем чат - должен получить клиента с высшим приоритетом
#         with patch.object(queue_manager, '_try_assign_operator_to_client') as mock_assign:
#             mock_assign.return_value = 1
            
#             await queue_manager._try_auto_assign_clients()
            
#             # Должен быть вызван для клиента с критическим приоритетом
#             mock_assign.assert_called_once_with(105)
