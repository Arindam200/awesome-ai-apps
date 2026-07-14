from pydantic import BaseModel, ConfigDict, Field, field_validator


class _ProviderModel(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)


class TranscriptionResult(_ProviderModel):
    text: str = Field(min_length=1)
    language: str | None = None

    @field_validator("language", mode="before")
    @classmethod
    def normalize_optional_language(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value


class ActionItem(_ProviderModel):
    task: str = Field(min_length=1)
    owner: str | None = None
    due: str | None = None

    @field_validator("owner", "due", mode="before")
    @classmethod
    def normalize_optional_text(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value


class VoiceNoteBrief(_ProviderModel):
    summary: str = Field(min_length=1)
    key_points: list[str]
    action_items: list[ActionItem]
    follow_up_message: str = Field(min_length=1)
