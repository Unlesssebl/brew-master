from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Telegram
    BOT_TOKEN: str = Field(..., description="Telegram Bot token from BotFather")

    # PostgreSQL Database
    POSTGRES_USER: str = Field("postgres")
    POSTGRES_PASSWORD: str = Field("postgres")
    POSTGRES_HOST: str = Field("localhost")
    POSTGRES_PORT: int = Field(5432)
    POSTGRES_DB: str = Field("beer_empire")
    DATABASE_URL: str = Field(..., description="PostgreSQL asyncpg connection URL")

    # LLM Game Master
    GEMINI_API_KEY: str = Field(..., description="Google Gemini API Key")
    LLM_MODEL_NAME: str = Field("gemini-2.5-flash")

    # Game Settings
    OFFLINE_INCOME_LIMIT_HOURS: int = Field(24)
    MARKET_UPDATE_INTERVAL_SECONDS: int = Field(14400)
    ROYALTY_TAX_INTERVAL_SECONDS: int = Field(3600)
    REVERSE_ENGINEERING_COOLDOWN_SECONDS: int = Field(86400)

    # Logging
    LOG_LEVEL: str = Field("INFO")


# Global settings instance
settings = Settings()
