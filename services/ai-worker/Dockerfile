FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Non-root user
RUN useradd -m -u 1000 worker && chown -R worker:worker /app
USER worker

CMD ["python", "-m", "app.main"]
