from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://postgres@localhost:5432/velib_wizard"
    cron_secret: str = "dev-secret"
    gbfs_base: str = "https://velib-metropole-opendata.smovengo.cloud/opendata/Velib_Metropole"
    allowed_origins: str = "http://localhost:3000"


settings = Settings()
