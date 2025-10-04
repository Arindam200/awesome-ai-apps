import os

from dotenv import load_dotenv
load_dotenv()

class Settings:
    # ScaleKit Configuration
    SCALEKIT_ENVIRONMENT_URL: str = os.environ.get("SCALEKIT_ENVIRONMENT_URL", "")
    SCALEKIT_CLIENT_ID: str = os.environ.get("SCALEKIT_CLIENT_ID", "")
    SCALEKIT_CLIENT_SECRET: str = os.environ.get("SCALEKIT_CLIENT_SECRET", "")
    SCALEKIT_RESOURCE_METADATA_URL: str = os.environ.get("SCALEKIT_RESOURCE_METADATA_URL", "")
    SCALEKIT_AUDIENCE_NAME: str = os.environ.get("SCALEKIT_AUDIENCE_NAME", "")
    METADATA_JSON_RESPONSE: str = os.environ.get("METADATA_JSON_RESPONSE", "")

    # Exa API Key
    EXA_API_KEY: str = os.environ.get("EXA_API_KEY", "")

    # Server Port
    PORT: int = int(os.environ.get("PORT", 10000))

    def __post_init__(self):
        if not self.SCALEKIT_CLIENT_ID:
            raise ValueError("SCALEKIT_CLIENT_ID environment variable not set")
        if not self.SCALEKIT_CLIENT_SECRET:
            raise ValueError("SCALEKIT_CLIENT_SECRET environment variable not set")
        if not self.SCALEKIT_ENVIRONMENT_URL:
            raise ValueError("SCALEKIT_ENVIRONMENT_URL environment variable not set")
        if not self.SCALEKIT_RESOURCE_METADATA_URL:
            raise ValueError("SCALEKIT_RESOURCE_METADATA_URL environment variable not set")
        if not self.SCALEKIT_AUDIENCE_NAME:
            raise ValueError("SCALEKIT_AUDIENCE_NAME environment variable not set")
        if not self.EXA_API_KEY:
            raise ValueError("EXA_API_KEY environment variable not set")

settings = Settings()