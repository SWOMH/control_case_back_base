import smtplib
from email.message import EmailMessage

from config import celery_app
from config.constants import DEV_CONSTANT
from celery import shared_task
from jinja2 import Environment, FileSystemLoader
import os


@celery_app.task
def send_confirmation_email(to_email: str, confirmation_code: int, template_type: str = 'mail_conf') -> None:
    # confirmation_code = code
    basedir = os.path.abspath(os.path.dirname(__file__))
    templates_dir = os.path.join(basedir, 'templates')  # папка с шаблонами

    # Создаем Jinja2 окружение
    env = Environment(loader=FileSystemLoader(templates_dir))
    if template_type == 'mail_conf':
        template = env.get_template("register_confirm.html")  # Загружаем шаблон
    elif template_type == 'reset_password':
        template = env.get_template("reset_password.html")  # Загружаем шаблон
    
    # Рендерим шаблон с кодом
    html_content = template.render(confirmation_code=confirmation_code)

    message = EmailMessage()
    message.add_alternative(html_content, subtype="html")
    message["From"] = DEV_CONSTANT.EMAIL_USERNAME
    message["To"] = to_email
    message["Subject"] = "Подтверждение регистрации"
    print('Сообщение создано')
    print(f'Отправляем на почту {to_email}')
    with smtplib.SMTP_SSL(
            host=DEV_CONSTANT.EMAIL_HOST,
            port=DEV_CONSTANT.EMAIL_PORT
    ) as smtp:
        smtp.login(
            user=DEV_CONSTANT.EMAIL_USERNAME,
            password=DEV_CONSTANT.EMAIL_PASSWORD,
        )
        print('Сообщение залогинино')
        smtp.send_message(msg=message)
        print('Сообщение отправлено')