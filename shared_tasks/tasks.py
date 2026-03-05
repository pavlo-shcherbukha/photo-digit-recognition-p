"""
    Цей файл містить функції, які можуть бути викликані з інших частин  проєкту, 
    наприклад, для відправки повідомлень у Telegram або запису даних у Redis.

 

"""

from pyrogram import Client, client
import logging
import os
import io
import sys
import redis
#from rq import Queue

# Налаштування логування (використовуємо ваш формат)
LOG_FORMAT = '%(asctime)s - %(levelname)s - %(name)s - %(message)s'
logger = logging.getLogger(__name__)
logger = logging.getLogger(__name__)

apploglevel=os.environ.get("LOGLEVEL")
if apploglevel==None:
    logger.setLevel(logging.DEBUG)
elif apploglevel=='DEBUG':
    logger.setLevel(logging.DEBUG)    
elif apploglevel=='INFO':
    logger.setLevel(logging.INFO)    
elif apploglevel=='WARNING':
    logger.setLevel(logging.WARNING)    
elif apploglevel=='ERROR':    
    logger.setLevel(logging.ERROR)    
elif apploglevel=='CRITICAL':
    logger.setLevel(logging.CRITICAL)    
else:
    logger.setLevel(logging.DEBUG)  

stream_handler = logging.StreamHandler(sys.stdout)
stream_handler.setFormatter(logging.Formatter(LOG_FORMAT))
if not logger.handlers:
    logger.addHandler(stream_handler)

logger.debug("debug message")
logger.debug("Читаю налаштування Redis з config.env")

# Налаштування з вашого config.env
iapi_id = int(os.getenv('API_ID'))
iapi_hash = os.getenv('API_HASH')

irds_host = os.getenv('RDS_HOST', 'localhost')
irds_port = int(os.getenv('RDS_PORT', 6379))
irds_tlgqueue = os.getenv('RDS_QUEUE', 'voltage_message')

isession_name = os.getenv('SESSION_NAME')
ichat_id = int(os.getenv('CHAT_ID'))

logger.debug( 'Підключаємось до Redis на {}:{}'.format(irds_host, irds_port) )
red = redis.StrictRedis(host=irds_host, port=irds_port, decode_responses=False)
logger.debug( 'Підключення до Redis встановлено' )

def send_telegram_alert(message, image_data=None):
    logger.debug(f"Виклик функції send_telegram_alert з повідомленням: {message}")
    # Отримуємо картинку з Redis

    #frame_bytes = red.get('voltage:last_frame')

    with Client(isession_name, iapi_id, iapi_hash) as app:

        if image_data:
            # Створюємо потік у пам'яті
            photo_stream = io.BytesIO(image_data)
            photo_stream.name = "alert_frame.jpg"
            app.send_photo( ichat_id, photo=photo_stream, caption=message)
            logger.info(f"Фото успішно надіслано для користувача ")            
        else:
            app.send_message(ichat_id, message)

