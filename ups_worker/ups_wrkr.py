import os
import time 
import sys
import json
import logging
import time
import redis

from ups_worker.PSHINA219 import INA219

# Налаштування логування (використовуємо такий формат)
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
# Налаштування з оточення (як у vcam_wrkr)
irds_host = os.getenv('RDS_HOST', 'localhost')
irds_port = int(os.getenv('RDS_PORT', 6379))

# Підключення до Redis (decode_responses=True для тексту)
logger.debug( 'Підключаємось до Redis на {}:{}'.format(irds_host, irds_port) )
red = redis.StrictRedis(host=irds_host, port=irds_port, decode_responses=True)
logger.debug( 'Підключення до Redis встановлено' )

logger.debug( 'Підключення до I2C' )
ina = INA219(addr=0x41)
logger.debug( 'Підключення до I2C' )
def main():
    logger.info("Запускаю UPS S3 Worker")
    while True:
        try:
            bus_v = ina.getBusVoltage_V()
            current_a = ina.getCurrent_mA() / 1000.0 # переводимо в Ампери
            
            p = (bus_v - 9) / 3.6 * 100
            p = max(0, min(100, p))
            
            # Пишемо "пульс" системи в Redis
            # Використовуємо pipeline для швидкості, якщо треба
            with red.pipeline() as pipe:
                pipe.set('ups:v', round(bus_v, 3))
                pipe.set('ups:p', round(p, 1))
                pipe.set('ups:a', round(current_a, 4))
                pipe.execute()
            
            logger.debug(f"UPS Status - Voltage: {bus_v:.3f} V, Current: {current_a:.4f} A, Power: {p:.1f}%")
        except Exception as e:
            logger.error(f"I2C Error: {e}")
            
        time.sleep(120) # 120 секунд  для UPS

if __name__ == "__main__":
    main()