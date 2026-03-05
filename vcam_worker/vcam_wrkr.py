import os
import time 
import sys
import json
import logging
import cv2

from datetime import datetime
import shutil
import requests
import base64
from ultralytics import YOLO
import numpy as np
import redis
from rq import Queue

from shared_tasks import tasks

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

try:
    logger.debug(" Завантажую модель ")
    model = YOLO('relay_digits_v16.pt')
    logger.debug(" Завантажую модель OK")
except Exception as e:
    logger.debug(f"Failed to load model: {e}")



logger.debug("Читаю налаштування Redis з config.env")


# Налаштування з вашого config.env
irds_host = os.getenv('RDS_HOST', 'localhost')
irds_port = int(os.getenv('RDS_PORT', 6379))
irds_tlgqueue = os.getenv('RDS_QUEUE', 'voltage_message')

logger.debug( 'Підключаємось до Redis на {}:{}'.format(irds_host, irds_port) )
red = redis.StrictRedis(host=irds_host, port=irds_port, decode_responses=True)
logger.debug( 'Підключення до Redis встановлено' )

logger.debug( 'Ініціалізуємо чергу RQ з ім\'ям "{}"'.format(irds_tlgqueue) )
q = Queue( name=irds_tlgqueue, connection=red)   
logger.debug( 'Черга RQ "{}" готова до використання'.format(irds_tlgqueue) ) 

def prepare_debug_dir(dir_name="debug_images"):
    """Створює чисту папку для збереження налагоджувальних зображень"""
    if os.path.exists(dir_name):
        shutil.rmtree(dir_name)  # Видаляємо все старе
    os.makedirs(dir_name)        # Створюємо чисту папку
    return dir_name

def prepare_db_dir(dir_name="db_detected"):
    """Створює чисту папку для збереження результатів та логів"""
    if os.path.exists(dir_name):
        shutil.rmtree(dir_name)  # Видаляємо все старе
    os.makedirs(dir_name)        # Створюємо чисту папку
    return dir_name

def log_to_jsonl(data, filename="db_detected/processing_log.jsonl"):
    """Додає запис до JSONL файлу (кожен запис - окремий рядок у форматі JSON)"""
    with open(filename, "a", encoding="utf-8") as f:
        f.write(json.dumps(data, ensure_ascii=False) + "\n")

def apply_gamma(image, gamma=0.5):
    """Застосовує гамма-корекцію до зображення для покращення видимості деталей"""
    # Гамма < 1.0 робить зображення темнішим і "проявляє" деталі в яскравих зонах
    invGamma = 1.0 / gamma
    table = np.array([((i / 255.0) ** invGamma) * 255 for i in np.arange(0, 256)]).astype("uint8")
    return cv2.LUT(image, table)

def get_voltage_local(frame, istest=False, frame_count=0):
    """Обробляє кадр з камери, виділяє ROI, запускає модель та повертає розпізнану 
       напругу та зображення з відмітками для налагодження
    """
    # 1. Поворот та ROI (вже ідеально налаштовані)
    frame = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
    h, w, _ = frame.shape
    roi = frame[int(h*0.35):int(h*0.65), int(w*0.05):int(w*0.95)]

    # 2. Мінімальна підготовка (тільки якщо потрібно прибрати легкий пересвіт)
    #    Можливо є сенс спробувати коефіцієнти 1.0 або 0.8
    roi_prepared = apply_gamma(roi, gamma=1.0) 

    # 3. ОДИН запуск моделі з оптимальним conf
    #    imgz=640 допоможе краще бачити дрібні деталі одиниці
    results = model(roi_prepared, conf=0.7, imgsz=640)[0]
    boxes = results.boxes

    detected_objects = []
    detected_objects_l = []
    debug_roi = roi_prepared.copy()
    voltage = ""
    if istest:
        logger.debug(f"Розмір ROI: {roi.shape}")
        logger.debug(f"Кількість знайдених об'єктів: {len(boxes)}")
        logger.debug(f"Початковий розмір кадру: {frame.shape}")
        logger.debug(f"Розмір ROI: {roi_prepared.shape}")
        isToLabel = False
        fail_filename = None
        for box in boxes:
            coords = box.xyxy[0].tolist()
            x1, y1, x2, y2 = map(int, coords)
            
            cls_id = int(box.cls[0].item())
            cls_name = model.names[cls_id]
            conf = box.conf[0].item()

            detected_objects.append((x1, cls_name))
            detected_objects_l.append({
                "class": cls_name,
                "confidence": conf,
                "bbox": [x1, y1, x2, y2]
            })

            # Малюємо рамки навколо кожної цифри
            cv2.rectangle(debug_roi, (x1, y1), (x2, y2), (0, 255, 0), 2)
            label = f"{cls_name} {conf:.2f}"
            cv2.putText(debug_roi, label, (x1, y1 - 10), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)

        # ФОРМУВАННЯ РЕЗУЛЬТАТУ ТА ВИВЕДЕННЯ НА КАРТИНКУ
        detected_objects.sort()
        voltage = "".join([obj[1] for obj in detected_objects])

        # Логіка для визначення, чи потрібно відправляти на донабір даних 
        # (наприклад, якщо розпізнано менше 4 символів або низька впевненість)
        if len(voltage) < 4 or any(box.conf[0] < 0.6 for box in results.boxes):
            fail_filename = os.path.join("./to_label", f"fix_{frame_count}.jpg")
            cv2.imwrite(fail_filename, roi) # Зберігаємо чистий ROI для навчання
            isToLabel = True
        
        # Для відладки: безумовне збереження ROI, який не вдалося розпізнати, 
        # для аналізу та донабору даних 
        #fail_filename = os.path.join("./to_label", f"fix_{frame_count}.jpg")
        #cv2.imwrite(fail_filename, roi) # Зберігаємо чистий ROI для навчання

        # Виводимо результат на зображення для налагодження
        result_text = f"{voltage}V"
        cv2.putText(debug_roi, result_text, (3, 30), 
                    cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 255), 2)

        logger.debug(f"Результат: {voltage}V")

        # Формуємо лог для збереження в JSONL
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "raw_voltage": voltage,
            "clean_voltage": int( voltage.replace("U", "") ) if voltage.startswith("U") and voltage[1:].isdigit() else 0,
            "detections": detected_objects_l,
            "frame_id": frame_count,
            "isToLabel": isToLabel,
            "fail_filename": fail_filename if isToLabel else None
                
        }

    return voltage, debug_roi, log_entry




def main():
    debug_dir = prepare_debug_dir()
    db_dir = prepare_db_dir()
    logger.debug(f"Каталог для налагодження: {debug_dir}")
    logger.debug(f"Каталог для бази даних: {db_dir}")
    logger.debug("Запуск моніторингу напруги")
    RTSP_URL = os.environ.get('RTSP_URL', '0') # 0 для локальної камери Pi
    # Інтервал між замірами в секундах (5 хвилин=300 секунд)
    CHECK_INTERVAL = int(os.environ.get('CHECK_INTERVAL', 300)) # 300 секунд за замовчуванням
    frame_count = 0
    while True:
        cap = cv2.VideoCapture(RTSP_URL)
        if cap.isOpened():
            logger.info("З'єднання з камерою встановлено.")
            
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                
                frame_count += 1
                # Отримуємо напругу
 
                voltage_text, debug_roi, log_entry = get_voltage_local(frame, istest=True, frame_count=frame_count)
                log_to_jsonl(log_entry)
                # Зберігаємо зображення з відмітками для налагодження
                debug_filename = os.path.join(debug_dir, f"roi_{frame_count:04d}.jpg")
                cv2.imwrite(debug_filename, debug_roi)

                log_entry["debug_image"] = debug_filename   
                log_to_jsonl(log_entry)      
                
                if voltage_text:
                    logger.info(f"Зчитана напруга: {voltage_text}V")
                    # Після того, як YOLO відпрацювала і ви маєте annotated_frame:
                    # Кодуємо зображення в буфер (bytes)
                    success, buffer = cv2.imencode('.jpg', debug_roi, [cv2.IMWRITE_JPEG_QUALITY, 85]) 
                    img_buffer = buffer.tobytes()
                    try:
                        # Записуємо дані, які розпізнала YOLO
                        red.set('voltage:current', log_entry["clean_voltage"])
                        red.set('voltage:status', 'stable')
                
                                        
                        # Записуємо байти прямо в Redis
                        red.set('voltage:last_frame', img_buffer)

                        # Відправляємо повідомлення в Telegram через RQ, щоб не блокувати осноний цикл роботи
                        q.enqueue('shared_tasks.tasks.send_telegram_alert',
                                  message=f"⚠️ Увага! Напруга: {log_entry['clean_voltage']}V",
                                  image_data=img_buffer)
                    except Exception as e: 
                        logger.error(f"Помилка при записі в Redis для відправки в Telegram: {e}")                   
                    
                    # Зберігаємо скріншот для доказу (з часом у назві)
                    #filename = datetime.now().strftime("voltage_%Y%m%d_%H%M%S.jpg")
                    #cv2.imwrite(filename, frame) 
                else:
                    logger.warning("Не вдалося розпізнати текст напруги. ")
                # Чекаємо до наступного циклу заміру
                cap.release() # Закриваємо потік, щоб не гріти Pi 3 дарма
                time.sleep(CHECK_INTERVAL)
                break 
        else:
            logger.error("Камера недоступна. Спроба через 10 сек.")
            time.sleep(10)