FROM python:3.11-slim

WORKDIR /app

# Встановлюємо залежності
COPY requirements.tlg.txt .
RUN pip install --no-cache-dir -r requirements.tlg.txt

# Копіюємо ваш код

COPY ./shared_tasks ./shared_tasks
COPY ./tlg_worker ./tlg_worker
COPY tlg_runner.py .
COPY <session file> .


CMD ["python", "tlg_runner.py"]