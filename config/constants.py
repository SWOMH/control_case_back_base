
class Constants:
    DB_DRIVER: str
    DB_USER: str
    DB_PASSWORD: str
    DB_HOST: str
    DB_PORT: int
    DB_NAME: str

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
