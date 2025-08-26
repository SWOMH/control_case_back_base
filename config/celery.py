from celery import Celery
from config.constants import DEV_CONSTANT

celery_app = Celery('case', broker=DEV_CONSTANT.CELERY_BROKER)
celery_app.conf.enable_utc = False
celery_app.conf.timezone = 'Europe/Moscow'

celery_app.autodiscover_tasks(packages=["case.apps"])