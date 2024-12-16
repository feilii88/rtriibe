from functools import lru_cache
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Required settings
    PG_DATABASE_URL: str

    SECRET_KEY: str
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int

    BASE_URL: str

    TWILIO_ACCOUNT_SID: str
    TWILIO_AUTH_TOKEN: str
    TWILIO_FROM_PHONE: str
    TWILIO_WHATSAPP_NUMBER: str

    ELEVEN_LABS_API_KEY: str
    ELEVEN_LABS_VOICE_ID: str

    VAPI_KEY: str
    VAPI_VOICE_ID: str
    VAPI_PHONE_NUMBER_ID: str

    RELEVANCE_AI_PROJECT: str
    RELEVANCE_AI_API_KEY: str
    RELEVANCE_AI_AUTH_TOKEN: str
    RELEVANCE_AI_REGION: str

    OPENAI_API_KEY: str


@lru_cache
def get_settings():
    return Settings()

constants = get_settings()