"""Optional language-model interfaces. Not used by default; numeric analysis stays in Python."""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
import os

@dataclass(frozen=True)
class LLMConfig:
    provider: str = ""
    base_url: str = ""
    api_key: str = ""
    model: str = ""
    timeout_seconds: float = 15.0

    @classmethod
    def from_environment(cls) -> "LLMConfig":
        return cls(provider=os.environ.get("LLM_PROVIDER", "").strip(),
            base_url=os.environ.get("LLM_API_BASE_URL", "").strip(),
            api_key=os.environ.get("LLM_API_KEY", "").strip(),
            model=os.environ.get("LLM_MODEL", "").strip())

    @property
    def is_configured(self) -> bool:
        return bool(self.provider and self.base_url and self.api_key and self.model)

class LanguageModelProvider(ABC):
    """A provider can generate prose, but must not be the source of numeric market calculations."""
    @abstractmethod
    def generate_text(self, system_instruction: str, user_content: str) -> str:
        raise NotImplementedError

class DisabledLanguageModelProvider(LanguageModelProvider):
    """Default no-network implementation for reproducible offline use."""
    def generate_text(self, system_instruction: str, user_content: str) -> str:
        raise RuntimeError("Language-model integration is disabled. No external model call was made.")


def load_optional_provider() -> LanguageModelProvider:
    """Return disabled provider unless all fields are set; this function never makes a network call."""
    config = LLMConfig.from_environment()
    # A concrete API adapter is deliberately not auto-selected in this release.
    # This avoids assuming that a CLI login provides API billing or authorization.
    if config.is_configured:
        raise NotImplementedError("LLM credentials were detected, but no concrete provider adapter is enabled in this release. Remove or leave the values blank to stay in deterministic mode.")
    return DisabledLanguageModelProvider()
