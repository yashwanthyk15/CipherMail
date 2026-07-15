from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"
    
    KAFKA_BROKER: str = "kafka:9092"
    KAFKA_TOPIC_EMAIL_EVENTS: str = "email.events"
    KAFKA_TOPIC_AI_RESULTS: str = "email.ai_results"
    
    GEMINI_API_KEY: str = ""
    
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379

    class Config:
        env_file = ".env"

settings = Settings()
