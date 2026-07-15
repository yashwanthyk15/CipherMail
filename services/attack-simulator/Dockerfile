FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Non-root user
RUN useradd -m -u 1000 simulator && chown -R simulator:simulator /app
USER simulator

CMD ["python", "-m", "app.main"]
