from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker


class DatabaseCore:
    def __init__(self, url_con: str, create_tables: bool = False):        
        self.engine = create_async_engine(
            url_con,
            pool_size=10, max_overflow=20
        )
        self.Session = async_sessionmaker(bind=self.engine, expire_on_commit=False)