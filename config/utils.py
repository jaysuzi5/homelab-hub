import os
from config.models import HubConfig
from dotenv import load_dotenv

load_dotenv()

def get_config(key: str, default=None):
    """
    Returns the config value with the following precedence:
    1. Environment variable
    2. Database value
    3. Provided default
    """
    env_val = os.environ.get(key)
    if env_val is not None:
        return env_val

    try:
        config_obj = HubConfig.objects.get(key=key)
        return config_obj.value
    except HubConfig.DoesNotExist:
        return default
