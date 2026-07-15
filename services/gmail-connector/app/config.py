from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Kafka
    KAFKA_BOOTSTRAP_SERVERS: str = "kafka:9092"
    KAFKA_TOPIC_EMAIL_EVENTS: str = "email.events"
    KAFKA_TOPIC_DECISIONS: str = "email.decisions"
    KAFKA_GROUP_ID: str = "gmail-connector"

    # Redis
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379

    # Gmail
    GMAIL_CREDENTIALS_FILE: str = "/app/credentials/credentials.json"
    GMAIL_TOKEN_FILE: str = "/app/credentials/token.json"
    GMAIL_POLL_INTERVAL_SECONDS: int = 30
    GMAIL_MAX_RESULTS: int = 5

    class Config:
        env_prefix = ""


settings = Settings()
