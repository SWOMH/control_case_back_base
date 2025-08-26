import redis
from config.constants import DEV_CONSTANT

redis_db = redis.Redis(
    host=DEV_CONSTANT.REDIS_HOST,
    port=DEV_CONSTANT.REDIS_PORT,
    db=DEV_CONSTANT.REDIS_DB
)
