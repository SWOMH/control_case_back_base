"""
Административные функции для управления чатами поддержки
"""
from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
from pydantic import BaseModel

from utils.auth import get_current_user
from utils.kafka_producer import kafka_producer
from utils.queue_manager import queue_manager
from utils.assignment_manager import create_assignment_manager
from utils.websocket_manager import websocket_manager
from database.logic.chats.chat import chat_db
from database.models.users import Users

router = APIRouter()

# Создаем менеджер назначений
assignment_manager = create_assignment_manager(queue_manager, websocket_manager)


class TransferChatRequest(BaseModel):
    """Запрос на перевод чата"""
    chat_id: int
    target_operator_id: int
    reason: str


class AssignLawyerRequest(BaseModel):
    """Запрос на назначение юриста"""
    client_id: int
    lawyer_id: int


class UpdateOperatorStatusRequest(BaseModel):
    """Запрос на изменение статуса оператора"""
    operator_id: int
    status: str  # 'online', 'offline', 'busy', 'available'
    max_concurrent_chats: Optional[int] = None


class CloseChatRequest(BaseModel):
    """Запрос на закрытие чата"""
    chat_id: int
    reason: str


class QueuePriorityRequest(BaseModel):
    """Запрос на изменение приоритета в очереди"""
    client_id: int
    priority: int


async def check_admin_permissions(current_user: Users = Depends(get_current_user)):
    """Проверка административных прав"""
    if not current_user.is_admin:
        # Здесь нужно добавить проверку групп и разрешений
        # Пока упрощенная проверка
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Недостаточно прав для выполнения административных действий"
        )
    return current_user


@router.post("/admin/transfer-chat")
async def transfer_chat(
    request: TransferChatRequest,
    admin_user: Users = Depends(check_admin_permissions)
):
    """Принудительный перевод чата другому оператору"""
    
    # Получаем текущего оператора чата
    current_operator_id = await assignment_manager.get_chat_operator(request.chat_id)
    if not current_operator_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Чат не найден или не назначен оператору"
        )
    
    # Проверяем, что целевой оператор существует и доступен
    if not await assignment_manager.is_operator_available(request.target_operator_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Целевой оператор недоступен"
        )
    
    # Выполняем перевод
    success = await assignment_manager.force_transfer_chat(
        request.chat_id,
        request.target_operator_id,
        current_operator_id,
        admin_user.id,
        request.reason
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Не удалось выполнить перевод чата"
        )
    
    return {
        "message": "Чат успешно переведен",
        "chat_id": request.chat_id,
        "from_operator": current_operator_id,
        "to_operator": request.target_operator_id,
        "reason": request.reason
    }


@router.post("/admin/assign-lawyer")
async def assign_lawyer(
    request: AssignLawyerRequest,
    admin_user: Users = Depends(check_admin_permissions)
):
    """Назначение персонального юриста клиенту"""
    
    # Проверяем, что у клиента еще нет назначенного юриста
    existing_lawyer = await assignment_manager.get_client_lawyer(request.client_id)
    if existing_lawyer:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Клиенту уже назначен юрист с ID {existing_lawyer}"
        )
    
    # Назначаем юриста
    lawyer_chat_id = await assignment_manager.assign_personal_lawyer(
        request.client_id,
        request.lawyer_id,
        admin_user.id
    )
    
    if not lawyer_chat_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Не удалось назначить юриста"
        )
    
    return {
        "message": "Юрист успешно назначен",
        "client_id": request.client_id,
        "lawyer_id": request.lawyer_id,
        "lawyer_chat_id": lawyer_chat_id
    }


@router.post("/admin/update-operator-status")
async def update_operator_status(
    request: UpdateOperatorStatusRequest,
    admin_user: Users = Depends(check_admin_permissions)
):
    """Изменение статуса оператора"""
    
    if request.status == "online":
        operator_type = await assignment_manager.get_operator_type(request.operator_id)
        max_chats = request.max_concurrent_chats or 5
        await assignment_manager.set_operator_online(request.operator_id, operator_type, max_chats)
        
    elif request.status == "offline":
        await assignment_manager.set_operator_offline(request.operator_id)
        
    elif request.status == "busy":
        await queue_manager.set_operator_busy(request.operator_id, True)
        
    elif request.status == "available":
        await queue_manager.set_operator_busy(request.operator_id, False)
        
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Неверный статус. Допустимые значения: online, offline, busy, available"
        )
    
    return {
        "message": "Статус оператора обновлен",
        "operator_id": request.operator_id,
        "status": request.status
    }


@router.post("/admin/close-chat")
async def close_chat(
    request: CloseChatRequest,
    admin_user: Users = Depends(check_admin_permissions)
):
    """Принудительное закрытие чата"""
    
    success = await assignment_manager.force_close_chat(
        request.chat_id,
        admin_user.id,
        request.reason
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Не удалось закрыть чат"
        )
    
    return {
        "message": "Чат успешно закрыт",
        "chat_id": request.chat_id,
        "reason": request.reason
    }


@router.post("/admin/update-queue-priority")
async def update_queue_priority(
    request: QueuePriorityRequest,
    admin_user: Users = Depends(check_admin_permissions)
):
    """Изменение приоритета клиента в очереди"""
    
    if request.client_id not in queue_manager.waiting_clients:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Клиент не найден в очереди"
        )
    
    new_position = await queue_manager.update_queue_position(
        request.client_id, 
        request.priority
    )
    
    return {
        "message": "Приоритет в очереди обновлен",
        "client_id": request.client_id,
        "new_priority": request.priority,
        "new_position": new_position
    }


@router.get("/admin/queue")
async def get_detailed_queue(admin_user: Users = Depends(check_admin_permissions)):
    """Получение детальной информации об очереди"""
    
    queue_clients = []
    for client_id, queued_client in queue_manager.waiting_clients.items():
        position = await queue_manager.get_queue_position(client_id)
        queue_clients.append({
            "client_id": client_id,
            "chat_id": queued_client.chat_id,
            "wait_time": queued_client.wait_time,
            "priority": queued_client.priority,
            "position": position,
            "timestamp": queued_client.timestamp.isoformat(),
            "metadata": queued_client.metadata
        })
    
    # Сортируем по позиции в очереди
    queue_clients.sort(key=lambda x: x["position"])
    
    return {
        "queue": queue_clients,
        "total_waiting": len(queue_clients),
        "available_operators": len(queue_manager.get_available_operators()),
        "queue_stats": queue_manager.get_queue_status()
    }


@router.get("/admin/operators")
async def get_detailed_operators(admin_user: Users = Depends(check_admin_permissions)):
    """Получение детальной информации об операторах"""
    
    operators = []
    for operator_id, operator in queue_manager.operators.items():
        operator_chats = await assignment_manager.get_operator_chats(operator_id)
        
        operators.append({
            "operator_id": operator_id,
            "operator_type": operator.operator_type,
            "is_online": operator.is_online,
            "is_available": operator.is_available,
            "current_chats": list(operator.current_chats),
            "current_chats_count": len(operator.current_chats),
            "max_concurrent_chats": operator.max_concurrent_chats,
            "utilization": len(operator.current_chats) / operator.max_concurrent_chats if operator.max_concurrent_chats > 0 else 0,
            "last_activity": operator.last_activity.isoformat(),
            "can_accept_chat": operator.can_accept_chat
        })
    
    return {
        "operators": operators,
        "total_operators": len(operators),
        "online_operators": len([op for op in operators if op["is_online"]]),
        "available_operators": len([op for op in operators if op["can_accept_chat"]])
    }


@router.get("/admin/chats")
async def get_active_chats(admin_user: Users = Depends(check_admin_permissions)):
    """Получение информации об активных чатах"""
    
    active_chats = []
    for chat_id, operator_id in queue_manager.chat_assignments.items():
        try:
            # Получаем информацию о чате из БД
            chat = await chat_db.get_chat_by_id(chat_id)
            if chat:
                participants = websocket_manager.get_chat_participants(chat_id)
                
                active_chats.append({
                    "chat_id": chat_id,
                    "client_id": chat.user_id,
                    "operator_id": operator_id,
                    "created_at": chat.date_created.isoformat(),
                    "active": chat.active,
                    "resolved": chat.resolved,
                    "online_participants": list(participants),
                    "participants_count": len(participants)
                })
        except Exception as e:
            # Если не удалось получить информацию о чате, пропускаем
            continue
    
    return {
        "active_chats": active_chats,
        "total_chats": len(active_chats)
    }


@router.get("/admin/stats")
async def get_admin_stats(admin_user: Users = Depends(check_admin_permissions)):
    """Получение общей статистики для администратора"""
    
    return {
        "queue": queue_manager.get_queue_status(),
        "assignments": assignment_manager.get_assignment_stats(),
        "connections": websocket_manager.get_connection_stats(),
        "operators_summary": {
            "total": len(queue_manager.operators),
            "online": len([op for op in queue_manager.operators.values() if op.is_online]),
            "available": len(queue_manager.get_available_operators()),
            "busy": len([op for op in queue_manager.operators.values() if op.is_online and not op.is_available])
        }
    }


@router.delete("/admin/remove-from-queue/{client_id}")
async def remove_client_from_queue(
    client_id: int,
    admin_user: Users = Depends(check_admin_permissions)
):
    """Удаление клиента из очереди"""
    
    success = await queue_manager.remove_client_from_queue(client_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Клиент не найден в очереди"
        )
    
    return {
        "message": "Клиент удален из очереди",
        "client_id": client_id
    }
