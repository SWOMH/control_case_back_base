
class Constants:
    DB_DRIVER: str
    DB_USER: str
    DB_PASSWORD: str
    DB_HOST: str
    DB_PORT: int
    DB_NAME: str

    # === SMPT serve ===
    EMAIL_HOST = 'smtp.yandex.ru'
    EMAIL_PORT = 465
    EMAIL_USERNAME = 'info@yandex.ru'
    EMAIL_PASSWORD = 12345


    # === REDIS ===
    REDIS_HOST = 'redis'
    REDIS_PORT = 6379
    REDIS_DB = 0
    REDIS_URL = f'redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}'

    # === CELERY ===
    CELERY_BROKER = 'redis://redis:6379/2'


    MODIFIED_NEWS = True  # Нужно ли модерировать посты? или отдавать записи только после модерации

    def __init__(self,
                 DB_DRIVER="postgresql+asyncpg",
                 DB_USER="postgres",
                 DB_PASSWORD="postgres",
                 DB_HOST="localhost",
                 DB_PORT=5432,
                 DB_NAME="postgres"
                 ):
        self.DB_DRIVER = DB_DRIVER
        self.DB_USER = DB_USER
        self.DB_PASSWORD = DB_PASSWORD
        self.DB_HOST = DB_HOST
        self.DB_PORT = DB_PORT
        self.DB_NAME = DB_NAME

    @property
    def url_connection(self):
        return f"{self.DB_DRIVER}://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"


DEV_CONSTANT = Constants()
