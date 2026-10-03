from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    app_name: str = "AI Business Workforce API"
    database_url: str = "sqlite:///./development.db"
    secret_key: str = "change-me"
    access_token_expire_minutes: int = 60
    class Config:
        env_file = ".env"

settings = Settings()
