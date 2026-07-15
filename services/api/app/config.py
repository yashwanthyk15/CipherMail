from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    ENVIRONMENT: str = "development"
    
    # Postgres
    POSTGRES_HOST: str = "postgres"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "email_gateway"
    POSTGRES_USER: str = "gateway_user"
    POSTGRES_PASSWORD: str
    
    # Kafka
    KAFKA_BROKER: str = "kafka:9092"
    
    # Redis
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379

    class Config:
        env_file = ".env"

settings = Settings()
