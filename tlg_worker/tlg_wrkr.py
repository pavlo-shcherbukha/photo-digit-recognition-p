import os
import time 
import sys
import json
import logging
#import cv2

from datetime import datetime
import shutil
import requests
import base64

import redis
from rq import Queue, Worker
from  shared_tasks import tasks 




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
irds_host = os.getenv('RDS_HOST', 'localhost')
irds_port = int(os.getenv('RDS_PORT', 6379))
irds_tlgqueue = os.getenv('RDS_QUEUE', 'voltage_message')

logger.debug( 'Підключаємось до Redis на {}:{}'.format(irds_host, irds_port) )
red = redis.StrictRedis(host=irds_host, port=irds_port, decode_responses=False)
logger.debug( 'Підключення до Redis встановлено' )

def main():
    logger.info("Запускаю TLG Worker")


    # Створюємо список об'єктів Queue правильно
    # Для кожної назви черги в listen створюємо об'єкт Queue з підключенням
    listen = [irds_tlgqueue]
    queues = [Queue(irds_tlgqueue, connection=red) for name in listen]
    
    logger.debug(f"running worker for queues: {listen}")

     # Ініціалізація клієнта черги
    try:
        logger.debug("Починаю роботу воркера")
        # Передаємо вже створені об'єкти черг у воркер
        # Параметр connection=red тут також бажано залишити
        worker = Worker(queues, connection=red)
        process_result=worker.work()
        logger.debug(f"Робота воркера завершена з результатом: {process_result}")
  
    except Exception as e:
        logger.error(f"Помилка під час роботи воркера: {e}")   