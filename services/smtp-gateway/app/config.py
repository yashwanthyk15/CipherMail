from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # App Settings
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"
    
    # SMTP
    SMTP_LISTEN_HOST: str = "0.0.0.0"
    SMTP_LISTEN_PORT: int = 587
    
    # API
    API_PORT: int = 8000
    
    # Kafka
    KAFKA_BROKER: str = "kafka:9092"
    KAFKA_TOPIC_EMAIL_EVENTS: str = "email.events"
    
    # Redis
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    
    # Postgres
    POSTGRES_HOST: str = "postgres"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "email_gateway"
    POSTGRES_USER: str = "gateway_user"
    POSTGRES_PASSWORD: str
    
    # External APIs (just in case needed here, though mostly for workers)
    GEMINI_API_KEY: str = ""
    VIRUSTOTAL_API_KEY: str = ""

    class Config:
        env_file = ".env"

settings = Settings()
