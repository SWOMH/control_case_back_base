"""
WebSocket эндпоинт для чата поддержки с использованием Kafka
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException
from fastapi import status, Query
from typing import Optional
import json
import asyncio
import logging

from utils.auth import get_current_user
from utils.websocket_manager import websocket_manager
from utils.kafka_producer import kafka_producer
from utils.queue_manager import queue_manager
from utils.assignment_manager import create_assignment_manager
from database.logic.chats.chat import chat_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix='/chat', tags=['Чат'])

# Создаем менеджер назначений
assignment_manager = create_assignment_manager(queue_manager, websocket_manager)


@router.websocket("/ws/chat")
async def ws_chat_endpoint(websocket: WebSocket, token: str = Query(...), chat_id: Optional[int] = Query(None)):
    """
    WebSocket эндпоинт для чата поддержки с Kafka
    
    Клиент подключается к /ws/chat?token=...&chat_id=123
    Если chat_id не передан для клиента - сервер создаст новый чат.
    Для операторов chat_id может быть None - они видят доступные чаты.
    """
    user = None
    user_id = None
    user_role = None
    
    try:
        # 1) Авторизация
        user = await get_current_user(token)
        if not user:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
        
        user_id = user.id
        user_role = await assignment_manager.get_operator_type(user_id)
        
        # 2) Определяем роль пользователя
        is_operator = user_role in ['support', 'lawyer', 'salesman']
        is_client = user.is_client or user_role == 'client'
        
        # 3) Обработка chat_id
        if chat_id is None:
            if is_client:
                # Для клиента ищем или создаем активный чат
                existing_chat = await chat_db.get_active_chat_by_user(user_id)
                if existing_chat:
                    chat_id = existing_chat.id
                else:
                    # Создаем новый чат
                    new_chat = await chat_db.create_chat(user_id)
                    chat_id = new_chat.id
                    
                    # Отправляем событие создания чата
                    await kafka_producer.send_chat_created(chat_id, user_id)
            elif is_operator:
                # Операторы могут подключаться без конкретного чата для получения уведомлений
                chat_id = None
            else:
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                return
        
        # 4) Подключение пользователя
        await websocket_manager.connect_user(user_id, websocket, user_role, {
            'chat_id': chat_id,
            'is_operator': is_operator,
            'is_client': is_client
        })
        
        # 5) Если это конкретный чат - присоединяемся к нему
        if chat_id:
            await websocket_manager.join_chat(user_id, chat_id)
        
        # 6) Если это оператор - регистрируем в системе и переводим в онлайн
        if is_operator:
            await assignment_manager.set_operator_online(user_id, user_role)
        
        # 7) Отправляем приветственное сообщение
        welcome_message = {
            'type': 'connected',
            'payload': {
                'user_id': user_id,
                'chat_id': chat_id,
                'role': user_role,
                'timestamp': asyncio.get_event_loop().time()
            }
        }
        await websocket_manager.send_to_user(user_id, welcome_message)
        
        # 8) Если это клиент и чат только что создан - добавляем в очередь
        if is_client and chat_id:
            # Проверяем, есть ли уже назначенный оператор
            assigned_operator = await assignment_manager.get_chat_operator(chat_id)
            if not assigned_operator:
                await queue_manager.add_client_to_queue(user_id, chat_id)
        
        # 9) Основной цикл обработки сообщений
        while True:
            try:
                data_text = await websocket.receive_text()
                message_data = json.loads(data_text)
                
                await handle_websocket_message(user_id, user_role, chat_id, message_data)
                
            except json.JSONDecodeError:
                error_message = {
                    'type': 'error',
                    'payload': {'message': 'Неверный формат JSON'}
                }
                await websocket_manager.send_to_user(user_id, error_message)
                continue
                
    except WebSocketDisconnect:
        logger.info(f"Пользователь {user_id} отключился")
    except Exception as e:
        logger.error(f"Ошибка в WebSocket соединении пользователя {user_id}: {e}")
    finally:
        # Очистка при отключении
        if user_id:
            if chat_id:
                await websocket_manager.leave_chat(user_id, chat_id)
            
            # Если это оператор - переводим в оффлайн
            if user_role in ['support', 'lawyer', 'salesman']:
                await assignment_manager.set_operator_offline(user_id)
            
            await websocket_manager.disconnect_user(user_id)


async def handle_websocket_message(user_id: int, user_role: str, chat_id: Optional[int], message_data: dict):
    """Обработка сообщений от WebSocket клиентов"""
    message_type = message_data.get('type')
    payload = message_data.get('payload', {})
    
    try:
        if message_type == 'message':
            await handle_chat_message(user_id, user_role, chat_id, payload)
            
        elif message_type == 'accept_chat':
            await handle_accept_chat(user_id, user_role, payload)
            
        elif message_type == 'transfer_chat':
            await handle_transfer_chat(user_id, user_role, payload)
            
        elif message_type == 'assign_lawyer':
            await handle_assign_lawyer(user_id, user_role, payload)
            
        elif message_type == 'close_chat':
            await handle_close_chat(user_id, user_role, chat_id, payload)
            
        elif message_type == 'typing':
            await handle_typing(user_id, chat_id, payload)
            
        elif message_type == 'read_messages':
            await handle_read_messages(user_id, chat_id, payload)
            
        elif message_type == 'operator_status':
            await handle_operator_status(user_id, user_role, payload)
            
        else:
            error_message = {
                'type': 'error',
                'payload': {'message': f'Неизвестный тип сообщения: {message_type}'}
            }
            await websocket_manager.send_to_user(user_id, error_message)
            
    except Exception as e:
        logger.error(f"Ошибка обработки сообщения {message_type} от пользователя {user_id}: {e}")
        error_message = {
            'type': 'error',
            'payload': {'message': 'Ошибка обработки сообщения'}
        }
        await websocket_manager.send_to_user(user_id, error_message)


async def handle_chat_message(user_id: int, user_role: str, chat_id: Optional[int], payload: dict):
    """Обработка отправки сообщения в чат"""
    if not chat_id:
        raise ValueError("Не указан ID чата")
    
    text = payload.get('text', '').strip()
    if not text:
        raise ValueError("Сообщение не может быть пустым")
    
    # Сохраняем сообщение в БД
    message = await chat_db.add_message(chat_id, user_id, user_role, text)
    
    # Отправляем событие в Kafka
    await kafka_producer.send_message_sent(
        chat_id, user_id, user_role, message.id, text
    )


async def handle_accept_chat(user_id: int, user_role: str, payload: dict):
    """Обработка принятия чата оператором"""
    if user_role not in ['support', 'lawyer', 'salesman']:
        raise ValueError("Только операторы могут принимать чаты")
    
    client_id = payload.get('client_id')
    target_chat_id = payload.get('chat_id')
    
    if not client_id or not target_chat_id:
        raise ValueError("Не указаны client_id или chat_id")
    
    # Проверяем, что клиент все еще в очереди
    if client_id not in queue_manager.waiting_clients:
        error_message = {
            'type': 'error',
            'payload': {'message': 'Клиент уже принят другим оператором'}
        }
        await websocket_manager.send_to_user(user_id, error_message)
        return
    
    # Назначаем чат оператору
    success = await assignment_manager.assign_chat_to_operator(target_chat_id, user_id, client_id)
    
    if not success:
        error_message = {
            'type': 'error',
            'payload': {'message': 'Не удалось принять чат'}
        }
        await websocket_manager.send_to_user(user_id, error_message)


async def handle_transfer_chat(user_id: int, user_role: str, payload: dict):
    """Обработка перевода чата другому оператору"""
    if user_role not in ['support', 'lawyer', 'salesman', 'admin']:
        raise ValueError("Недостаточно прав для перевода чата")
    
    chat_id = payload.get('chat_id')
    target_operator_id = payload.get('target_operator_id')
    reason = payload.get('reason', 'manual_transfer')
    
    if not chat_id or not target_operator_id:
        raise ValueError("Не указаны chat_id или target_operator_id")
    
    # Проверяем, что чат назначен текущему пользователю или это админ
    current_operator = await assignment_manager.get_chat_operator(chat_id)
    is_admin = user_role == 'admin'
    
    if not is_admin and current_operator != user_id:
        raise ValueError("Вы не можете передавать чужие чаты")
    
    # Выполняем перевод
    success = await assignment_manager.transfer_chat_to_operator(
        chat_id, target_operator_id, current_operator or user_id, reason,
        user_id if is_admin else None
    )
    
    if not success:
        error_message = {
            'type': 'error',
            'payload': {'message': 'Не удалось перевести чат'}
        }
        await websocket_manager.send_to_user(user_id, error_message)


async def handle_assign_lawyer(user_id: int, user_role: str, payload: dict):
    """Обработка назначения персонального юриста"""
    if user_role not in ['support', 'admin']:
        raise ValueError("Только операторы поддержки и админы могут назначать юристов")
    
    client_id = payload.get('client_id')
    lawyer_id = payload.get('lawyer_id')
    
    if not client_id or not lawyer_id:
        raise ValueError("Не указаны client_id или lawyer_id")
    
    # Назначаем юриста
    lawyer_chat_id = await assignment_manager.assign_personal_lawyer(
        client_id, lawyer_id, user_id
    )
    
    if lawyer_chat_id:
        success_message = {
            'type': 'lawyer_assigned_success',
            'payload': {
                'client_id': client_id,
                'lawyer_id': lawyer_id,
                'lawyer_chat_id': lawyer_chat_id
            }
        }
        await websocket_manager.send_to_user(user_id, success_message)
    else:
        error_message = {
            'type': 'error',
            'payload': {'message': 'Не удалось назначить юриста'}
        }
        await websocket_manager.send_to_user(user_id, error_message)


async def handle_close_chat(user_id: int, user_role: str, chat_id: Optional[int], payload: dict):
    """Обработка закрытия чата"""
    if not chat_id:
        raise ValueError("Не указан ID чата")
    
    if user_role not in ['support', 'lawyer', 'admin']:
        raise ValueError("Недостаточно прав для закрытия чата")
    
    reason = payload.get('reason', 'manual_close')
    
    # Закрываем чат в БД
    await chat_db.close_chat(chat_id, user_id)
    
    # Отправляем событие закрытия
    await kafka_producer.send_chat_closed(chat_id, user_id, reason)


async def handle_typing(user_id: int, chat_id: Optional[int], payload: dict):
    """Обработка индикатора печати"""
    if not chat_id:
        return
    
    typing_message = {
        'type': 'typing',
        'payload': {
            'chat_id': chat_id,
            'user_id': user_id,
            'is_typing': payload.get('is_typing', True)
        }
    }
    
    # Отправляем всем участникам чата кроме отправителя
    await websocket_manager.broadcast_to_chat(chat_id, typing_message, exclude_user=user_id)


async def handle_read_messages(user_id: int, chat_id: Optional[int], payload: dict):
    """Обработка отметки о прочтении сообщений"""
    if not chat_id:
        return
    
    upto_message_id = payload.get('upto_message_id')
    
    # Отмечаем сообщения как прочитанные
    await chat_db.mark_messages_read(chat_id, user_id, upto_message_id)
    
    # Уведомляем других участников
    read_message = {
        'type': 'messages_read',
        'payload': {
            'chat_id': chat_id,
            'user_id': user_id,
            'upto_message_id': upto_message_id
        }
    }
    
    await websocket_manager.broadcast_to_chat(chat_id, read_message, exclude_user=user_id)


async def handle_operator_status(user_id: int, user_role: str, payload: dict):
    """Обработка изменения статуса оператора"""
    if user_role not in ['support', 'lawyer', 'salesman']:
        raise ValueError("Только операторы могут изменять свой статус")
    
    status = payload.get('status')  # 'available', 'busy', 'offline'
    
    if status == 'available':
        await queue_manager.set_operator_busy(user_id, False)
    elif status == 'busy':
        await queue_manager.set_operator_busy(user_id, True)
    elif status == 'offline':
        await assignment_manager.set_operator_offline(user_id)
    
    # Уведомляем о смене статуса
    await websocket_manager.notify_operator_status_change(user_id, status)


# REST эндпоинты для управления чатами

@router.get("/chats/queue")
async def get_queue_status():
    """Получение статуса очереди"""
    return queue_manager.get_queue_status()


@router.get("/chats/operators")
async def get_operators_status():
    """Получение статуса операторов"""
    operators = []
    for operator_id, operator in queue_manager.operators.items():
        operators.append({
            'operator_id': operator_id,
            'operator_type': operator.operator_type,
            'is_online': operator.is_online,
            'is_available': operator.is_available,
            'current_chats': len(operator.current_chats),
            'max_chats': operator.max_concurrent_chats
        })
    return {'operators': operators}


@router.get("/chats/stats")
async def get_chat_stats():
    """Получение общей статистики чатов"""
    return {
        'queue': queue_manager.get_queue_status(),
        'assignments': assignment_manager.get_assignment_stats(),
        'connections': websocket_manager.get_connection_stats()
    }
