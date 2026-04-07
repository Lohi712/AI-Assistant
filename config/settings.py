"""
Centralized configuration management for VEGA AI Assistant.

Loads all settings from environment variables (via .env file)
and validates that required keys are present at startup.
"""

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv


# Resolve the project root (one level up from config/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent


@dataclass
class Settings:
    """Immutable application settings loaded from the .env file."""

    # --- Google Gemini AI ---
    google_ai_api_key: str = ""

    # --- Picovoice Wake Word ---
    picovoice_access_key: str = ""
    wake_word_model: str = str(PROJECT_ROOT / "assets" / "Hey-Vega_en_windows_v3_0_0.ppn")

    # --- OpenWeatherMap ---
    openweather_api_key: str = ""

    # --- GNews ---
    gnews_api_key: str = ""

    # --- Gmail SMTP ---
    gmail_user: str = ""
    gmail_app_password: str = ""

    # --- Logging ---
    log_level: str = "INFO"

    # --- Paths ---
    project_root: str = field(default_factory=lambda: str(PROJECT_ROOT))
    assets_dir: str = field(default_factory=lambda: str(PROJECT_ROOT / "assets"))

    # --- Speech ---
    listen_timeout: int = 5
    listen_phrase_limit: int = 15
    speech_language: str = "en-in"

    @classmethod
    def load(cls) -> "Settings":
        """
        Load settings from the .env file and environment variables.

        Returns:
            A fully populated Settings instance.

        Raises:
            SystemExit: If critical API keys are missing.
        """
        # Load .env from project root
        env_path = PROJECT_ROOT / ".env"
        load_dotenv(dotenv_path=env_path)

        instance = cls(
            google_ai_api_key=os.getenv("GOOGLE_AI_API_KEY", ""),
            picovoice_access_key=os.getenv("PICOVOICE_ACCESS_KEY", ""),
            openweather_api_key=os.getenv("OPENWEATHER_API_KEY", ""),
            gnews_api_key=os.getenv("GNEWS_API_KEY", ""),
            gmail_user=os.getenv("GMAIL_USER", ""),
            gmail_app_password=os.getenv("GMAIL_APP_PASSWORD", ""),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
        )

        instance._validate()
        return instance

    def _validate(self) -> None:
        """Check that critical keys are present and warn about optional ones."""
        critical = {
            "GOOGLE_AI_API_KEY": self.google_ai_api_key,
            "PICOVOICE_ACCESS_KEY": self.picovoice_access_key,
        }
        optional = {
            "OPENWEATHER_API_KEY": self.openweather_api_key,
            "GNEWS_API_KEY": self.gnews_api_key,
            "GMAIL_APP_PASSWORD": self.gmail_app_password,
        }

        missing_critical = [k for k, v in critical.items() if not v]
        missing_optional = [k for k, v in optional.items() if not v]

        if missing_critical:
            print(f"\n[FATAL] Missing required environment variables: {', '.join(missing_critical)}")
            print("Please set them in your .env file. See .env.example for reference.\n")
            sys.exit(1)

        if missing_optional:
            print(f"\n[WARNING] Missing optional environment variables: {', '.join(missing_optional)}")
            print("Some features (weather, news, email) may not work.\n")
