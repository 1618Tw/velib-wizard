from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://postgres@localhost:5432/velib_wizard"
    cron_secret: str = "dev-secret"
    gbfs_base: str = "https://velib-metropole-opendata.smovengo.cloud/opendata/Velib_Metropole"
    allowed_origins: str = "http://localhost:3000"

    # Email alerts. Leave SMTP_USER empty to disable alerting entirely.
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""           # Gmail address that sends the alert
    smtp_password: str = ""       # 16-char Google App Password
    alert_to: str = ""            # Recipient — defaults to smtp_user if empty
    alert_cooldown_minutes: int = 60


settings = Settings()
