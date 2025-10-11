import os
from src.config.settings import AppSettings

settings = AppSettings.from_env()
print(settings.alpaca_key_id, settings.alpaca_secret_key)
