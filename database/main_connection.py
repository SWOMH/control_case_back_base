from database.core import DatabaseCore
from config.constant import CONSTANT


class DataBaseMainConnect(DatabaseCore):
    def __init__(self):
        url_con = CONSTANT.url_connection
        super().__init__(str(url_con), create_tables=True)