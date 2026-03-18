"""
config.py — Application configuration loaded from .env
All settings are read once at startup via pydantic-settings.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=["../.env", ".env"],   # root .env first, local .env overrides
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Zerodha ──────────────────────────────
    kite_api_key: str = Field(default="", alias="KITE_API_KEY")
    kite_api_secret: str = Field(default="", alias="KITE_API_SECRET")
    kite_access_token: str = Field(default="", alias="KITE_ACCESS_TOKEN")

    # ── Telegram ─────────────────────────────
    telegram_bot_token: str = Field(default="", alias="TELEGRAM_BOT_TOKEN")
    telegram_chat_id: str = Field(default="", alias="TELEGRAM_CHAT_ID")

    # ── App ──────────────────────────────────
    app_mode: str = Field(default="paper", alias="APP_MODE")  # paper | live
    app_host: str = Field(default="localhost", alias="APP_HOST")
    app_port: int = Field(default=8000, alias="APP_PORT")
    secret_key: str = Field(default="change-me", alias="SECRET_KEY")

    # ── Capital ──────────────────────────────
    starting_capital: float = Field(default=10000.0, alias="STARTING_CAPITAL")

    # ── Data ─────────────────────────────────
    data_source: str = Field(default="yfinance", alias="DATA_SOURCE")
    data_delay_minutes: int = Field(default=15, alias="DATA_DELAY_MINUTES")

    # ── Safety limits ────────────────────────
    # Also hardcoded in risk_manager.py — these are the env overrides
    max_daily_loss: float = Field(default=300.0, alias="MAX_DAILY_LOSS")
    max_trades_per_day: int = Field(default=3, alias="MAX_TRADES_PER_DAY")
    max_position_size: float = Field(default=5000.0, alias="MAX_POSITION_SIZE")
    max_leverage: float = Field(default=2.0, alias="MAX_LEVERAGE")
    force_close_time: str = Field(default="15:10", alias="FORCE_CLOSE_TIME")

    # ── AWS (future) ─────────────────────────
    aws_instance_id: str = Field(default="", alias="AWS_INSTANCE_ID")
    domain: str = Field(default="", alias="DOMAIN")

    # ── Auth ─────────────────────────────────
    trading_username: str = Field(default="admin", alias="TRADING_USERNAME")
    trading_password_hash: str = Field(default="", alias="TRADING_PASSWORD_HASH")
    jwt_secret: str = Field(default="change-me", alias="JWT_SECRET")
    jwt_expire_hours: int = Field(default=24, alias="JWT_EXPIRE_HOURS")

    @property
    def is_paper_mode(self) -> bool:
        return self.app_mode.lower() == "paper"

    @property
    def kite_configured(self) -> bool:
        return bool(self.kite_api_key and self.kite_access_token)

    @property
    def telegram_configured(self) -> bool:
        return bool(self.telegram_bot_token and self.telegram_chat_id)


# Singleton — import this everywhere
settings = Settings()
