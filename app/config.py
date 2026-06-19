from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    db_url: str
    postgres_user: str
    postgres_db: str
    postgres_password: str
    secret_key: str
    expire_access_token_min: int
    expire_refresh_token_days: int
    max_active_sessions: int
    algorithm: str
    yookassa_shop_id: str
    yookassa_secret_key: str
    return_url: str
    ngrok_authtoken: str | None = None
    rate_limiting_storage: str
    cache_storage: str
    tasks_storage: str
    mail_server: str
    mail_port: int
    mail_username: str
    mail_password: str
    mail_from: str
    ttl_pending_bookings: int
    log_level: str = "INFO"
    verify_webhook_ip: bool = False

    class Config:
        env_file = ".env"

settings = Settings()
