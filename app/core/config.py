from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    DATABASE_URL: str
    REDIS_URL: str
    UPSTREAM_LLM_URL: str
    LATENCY_BUCKETS: str = "0.05,0.1,0.25,0.5,1.0,2.5"
    APP_ENV: str = "development"

    def get_latency_buckets(self) -> List[float]:
        return [float(x) for x in self.LATENCY_BUCKETS.split(",")]

    class Config:
        env_file = ".env"


settings = Settings()