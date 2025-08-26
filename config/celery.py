from celery import Celery

celery_task_app = Celery('task_c', broker='redis://redis:6379/2')
celery_task_app.conf.enable_utc = False
celery_task_app.conf.timezone = 'Europe/Moscow'
