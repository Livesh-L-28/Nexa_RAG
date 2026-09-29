"""Configuration loader and settings validation for Guardrails."""

from pathlib import Path
from typing import Any

from app.core.config import get_settings

settings = get_settings()


class GuardrailConfigLoader:
    """Loads and validates configuration files for NeMo Guardrails."""

    @staticmethod
    def get_config_dir() -> Path:
        """Resolve the path to the guardrails configuration directory."""
        configured_path = Path(settings.GUARDRAILS_CONFIG_PATH)
        if configured_path.is_absolute():
            return configured_path

        # Look relative to current file's parent directory
        pkg_dir = Path(__file__).parent / "config"
        if pkg_dir.exists():
            return pkg_dir
        return Path.cwd() / configured_path

    @classmethod
    def load_nemo_config(cls) -> dict[str, Any]:
        """Validate config files exist in config dir."""
        config_dir = cls.get_config_dir()
        config_file = config_dir / "config.yml"
        if not config_file.exists():
            return {}
        return {"config_path": str(config_dir)}
