from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    PROJECT_NAME: str = "选股池自动化系统"
    VERSION: str = "1.0.0"
    API_PREFIX: str = "/api/v1"
    
    DATABASE_URL: str = "mysql+aiomysql://stock_user:stock_password@mysql:3306/stock_pool"
    DATABASE_URL_SYNC: str = "mysql+pymysql://stock_user:stock_password@mysql:3306/stock_pool"
    
    REDIS_URL: str = "redis://redis:6379/0"
    
    SECRET_KEY: str = "your-secret-key-change-in-production-min-32-chars"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7
    
    CHROME_DRIVER_PATH: Optional[str] = None
    SELENIUM_URL: str = "http://selenium:4444/wd/hub"
    
    DATA_DIR: str = "/app/data"
    EXCEL_DIR: str = "/app/data/excel"
    LOGS_DIR: str = "/app/data/logs"
    COOKIES_DIR: str = "/app/data/cookies"
    
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_API_BASE: Optional[str] = None
    
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    EMAIL_FROM: Optional[str] = None
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
