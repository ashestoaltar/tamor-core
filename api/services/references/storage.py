# api/services/references/storage.py
"""
Reference storage management for SWORD modules and Sefaria cache.

Provides directory structure management and configuration persistence
for the reference system. The base path can be configured via environment
variable to support migration to NAS or other storage locations.
"""

import os
import json
from pathlib import Path


class ReferenceStorage:
    """
    Manages the reference storage directory structure and configuration.

    Directory structure:
        {TAMOR_REFERENCE_PATH}/
        ├── sword/
        │   └── modules/
        │       ├── texts/
        │       └── mods.d/
        ├── sefaria_cache/
        │   ├── texts/
        │   ├── search/
        │   └── commentary/
        └── config.json
    """

    def __init__(self):
        self.base_path = Path(os.getenv(
            "TAMOR_REFERENCE_PATH",
            "/home/tamor/data/references"
        ))
        self._ensure_structure()

    def _ensure_structure(self):
        """Create directory structure if it doesn't exist."""
        dirs = [
            self.base_path / "sword" / "modules" / "texts",
            self.base_path / "sword" / "modules" / "mods.d",
            self.base_path / "sefaria_cache" / "texts",
            self.base_path / "sefaria_cache" / "search",
            self.base_path / "sefaria_cache" / "commentary",
        ]
        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)

        # Initialize config if missing
        config_path = self.base_path / "config.json"
        if not config_path.exists():
            self._write_config(self._default_config())

    def _default_config(self) -> dict:
        """Return default configuration values."""
        return {
            "default_translation": os.getenv("DEFAULT_BIBLE_TRANSLATION", "KJV"),
            "enabled_modules": [],
            "sefaria_cache_ttl_days": int(os.getenv("SEFARIA_CACHE_TTL_DAYS", "30")),
        }

    @property
    def sword_path(self) -> Path:
        """Path to SWORD modules directory."""
        return self.base_path / "sword" / "modules"

    @property
    def sword_texts_path(self) -> Path:
        """Path to SWORD text modules."""
        return self.sword_path / "texts"

    @property
    def sword_mods_path(self) -> Path:
        """Path to SWORD module configuration files."""
        return self.sword_path / "mods.d"

    @property
    def sefaria_cache_path(self) -> Path:
        """Path to Sefaria cache directory."""
        return self.base_path / "sefaria_cache"

    @property
    def sefaria_texts_path(self) -> Path:
        """Path to cached Sefaria texts."""
        return self.sefaria_cache_path / "texts"

    @property
    def sefaria_search_path(self) -> Path:
        """Path to cached Sefaria search results."""
        return self.sefaria_cache_path / "search"

    @property
    def sefaria_commentary_path(self) -> Path:
        """Path to cached Sefaria commentary."""
        return self.sefaria_cache_path / "commentary"

    def get_config(self) -> dict:
        """Load and return current configuration."""
        config_path = self.base_path / "config.json"
        with open(config_path) as f:
            return json.load(f)

    def _write_config(self, config: dict):
        """Write configuration to disk."""
        config_path = self.base_path / "config.json"
        with open(config_path, "w") as f:
            json.dump(config, f, indent=2)

    def update_config(self, **kwargs):
        """Update configuration with provided key-value pairs."""
        config = self.get_config()
        config.update(kwargs)
        self._write_config(config)

    def get_enabled_modules(self) -> list:
        """Return list of enabled SWORD module names."""
        return self.get_config().get("enabled_modules", [])

    def enable_module(self, module_name: str):
        """Add a module to the enabled list."""
        config = self.get_config()
        if module_name not in config["enabled_modules"]:
            config["enabled_modules"].append(module_name)
            self._write_config(config)

    def disable_module(self, module_name: str):
        """Remove a module from the enabled list."""
        config = self.get_config()
        if module_name in config["enabled_modules"]:
            config["enabled_modules"].remove(module_name)
            self._write_config(config)

    def get_cache_ttl_seconds(self) -> int:
        """Return Sefaria cache TTL in seconds."""
        days = self.get_config().get("sefaria_cache_ttl_days", 30)
        return days * 24 * 60 * 60
