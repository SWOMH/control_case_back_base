"""
Пример интеграции системы чата поддержки в основное приложение
"""
from fastapi import FastAPI
from contextlib import asynccontextmanager

# Импорты для системы чата
from utils.chat_system_init import startup_chat_system, shutdown_chat_system
from endpoints.chats.chat_kafka import router as chat_router
from endpoints.chats.admin_chat import router as admin_chat_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения"""
    # Запуск
    print("Запуск системы чата поддержки...")
    await startup_chat_system()
    print("Система чата поддержки запущена")
    
    yield
    
    # Завершение
    print("Остановка системы чата поддержки...")
    await shutdown_chat_system()
    print("Система чата поддержки остановлена")


# Создание приложения с управлением жизненным циклом
app = FastAPI(
    title="Control Case API with Support Chat",
    description="API с системой чата поддержки на Kafka",
    version="1.0.0",
    lifespan=lifespan
)

# Подключение роутеров чата
app.include_router(
    chat_router,
    prefix="/api/v1/chat",
    tags=["Support Chat"]
)

app.include_router(
    admin_chat_router,
    prefix="/api/v1/chat",
    tags=["Support Chat Admin"]
)

# Здесь можно добавить другие роутеры приложения
# app.include_router(other_router, prefix="/api/v1", tags=["Other"])


@app.get("/")
async def root():
    """Корневой эндпоинт"""
    return {"message": "Control Case API with Support Chat System"}


@app.get("/health")
async def health_check():
    """Проверка здоровья системы"""
    from utils.chat_system_init import get_chat_system
    
    chat_system = get_chat_system()
    system_status = chat_system.get_system_status()
    
    return {
        "status": "healthy" if system_status["status"] == "running" else "unhealthy",
        "chat_system": system_status
    }


if __name__ == "__main__":
    import uvicorn
    
    # Запуск для разработки
    uvicorn.run(
        "chat_integration_example:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
