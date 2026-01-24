# api/services/references/sword_manager.py
"""
SWORD module manager for downloading and managing Bible translations.

Downloads modules from the CrossWire repository and manages local installation.
Uses pysword for reading the installed modules.
"""

import os
import shutil
import zipfile
import logging
from pathlib import Path
from typing import Optional

import requests

from .storage import ReferenceStorage

logger = logging.getLogger(__name__)

# Known good modules with their download URLs
# These are public domain or freely distributable translations
SWORD_MODULES = {
    "KJV": {
        "name": "King James Version",
        "url": "https://crosswire.org/ftpmirror/pub/sword/packages/rawzip/KJV.zip",
        "size_mb": 2,
        "language": "en",
        "description": "1769 King James Version of the Holy Bible",
    },
    # Note: WEB module not available on CrossWire (removed from repository)
    # "WEB": {
    #     "name": "World English Bible",
    #     "url": "https://crosswire.org/ftpmirror/pub/sword/packages/rawzip/WEB.zip",
    #     "size_mb": 2,
    #     "language": "en",
    #     "description": "Public domain modern English translation",
    # },
    "ASV": {
        "name": "American Standard Version",
        "url": "https://crosswire.org/ftpmirror/pub/sword/packages/rawzip/ASV.zip",
        "size_mb": 2,
        "language": "en",
        "description": "1901 American Standard Version",
    },
    "YLT": {
        "name": "Young's Literal Translation",
        "url": "https://crosswire.org/ftpmirror/pub/sword/packages/rawzip/YLT.zip",
        "size_mb": 1.5,
        "language": "en",
        "description": "Literal translation by Robert Young (1862/1898)",
    },
    "OSHB": {
        "name": "Open Scriptures Hebrew Bible",
        "url": "https://crosswire.org/ftpmirror/pub/sword/packages/rawzip/OSHB.zip",
        "size_mb": 5,
        "language": "he",
        "description": "Hebrew text of the Old Testament with morphology",
    },
    "LXX": {
        "name": "Septuagint",
        "url": "https://crosswire.org/ftpmirror/pub/sword/packages/rawzip/LXX.zip",
        "size_mb": 3,
        "language": "grc",
        "description": "Greek translation of the Hebrew Bible",
    },
    "SBLGNT": {
        "name": "SBL Greek New Testament",
        "url": "https://crosswire.org/ftpmirror/pub/sword/packages/rawzip/SBLGNT.zip",
        "size_mb": 1,
        "language": "grc",
        "description": "Society of Biblical Literature Greek New Testament",
    },
    "TR": {
        "name": "Textus Receptus",
        "url": "https://crosswire.org/ftpmirror/pub/sword/packages/rawzip/TR.zip",
        "size_mb": 1,
        "language": "grc",
        "description": "Greek New Testament Textus Receptus (1550/1894)",
    },
    "Vulgate": {
        "name": "Latin Vulgate",
        "url": "https://crosswire.org/ftpmirror/pub/sword/packages/rawzip/Vulgate.zip",
        "size_mb": 2,
        "language": "la",
        "description": "Latin Vulgate Bible",
    },
}


class SwordModuleError(Exception):
    """Base exception for SWORD module operations."""
    pass


class ModuleNotFoundError(SwordModuleError):
    """Raised when a requested module is not in the known list."""
    pass


class DownloadError(SwordModuleError):
    """Raised when module download fails."""
    pass


class ExtractionError(SwordModuleError):
    """Raised when zip extraction fails."""
    pass


class SwordManager:
    """
    Manages SWORD Bible modules: download, install, remove.

    Usage:
        manager = SwordManager()

        # List available modules
        for mod in manager.list_available():
            print(f"{mod['code']}: {mod['name']}")

        # Download a module
        manager.download_module("KJV")

        # Check what's installed
        print(manager.list_installed())
    """

    def __init__(self):
        self.storage = ReferenceStorage()
        self._download_timeout = 60  # seconds

    def list_available(self) -> list[dict]:
        """
        List modules available for download.

        Returns:
            List of dicts with code, name, url, size_mb, language, description
        """
        result = []
        installed = set(self.list_installed())

        for code, info in SWORD_MODULES.items():
            result.append({
                "code": code,
                "installed": code in installed,
                **info
            })

        return sorted(result, key=lambda x: x["name"])

    def list_installed(self) -> list[str]:
        """
        List locally installed module codes.

        Returns:
            List of module codes (uppercase)
        """
        mods_d = self.storage.sword_mods_path
        if not mods_d.exists():
            return []

        installed = []
        for conf_file in mods_d.glob("*.conf"):
            # Module name is filename without .conf (may be lowercase)
            installed.append(conf_file.stem.upper())

        return sorted(installed)

    def is_installed(self, module_code: str) -> bool:
        """Check if a module is installed locally."""
        return module_code.upper() in self.list_installed()

    def get_module_info(self, module_code: str) -> Optional[dict]:
        """
        Get info about a specific module.

        Returns:
            Module info dict or None if unknown
        """
        module_code = module_code.upper()
        if module_code not in SWORD_MODULES:
            return None

        info = SWORD_MODULES[module_code].copy()
        info["code"] = module_code
        info["installed"] = self.is_installed(module_code)
        return info

    def download_module(self, module_code: str, progress_callback=None) -> bool:
        """
        Download and install a SWORD module.

        Args:
            module_code: The module code (e.g., "KJV")
            progress_callback: Optional callable(bytes_downloaded, total_bytes)

        Returns:
            True on success

        Raises:
            ModuleNotFoundError: If module code is unknown
            DownloadError: If download fails
            ExtractionError: If zip extraction fails
        """
        module_code = module_code.upper()

        if module_code not in SWORD_MODULES:
            raise ModuleNotFoundError(f"Unknown module: {module_code}")

        if self.is_installed(module_code):
            logger.info(f"Module {module_code} already installed")
            return True

        module_info = SWORD_MODULES[module_code]
        url = module_info["url"]

        logger.info(f"Downloading {module_code} from {url}")

        # Download zip file
        zip_path = self.storage.sword_path / f"{module_code}.zip"
        try:
            self._download_file(url, zip_path, progress_callback)
        except requests.RequestException as e:
            zip_path.unlink(missing_ok=True)
            raise DownloadError(f"Failed to download {module_code}: {e}")

        # Extract to modules directory
        try:
            self._extract_module(zip_path, module_code)
        except Exception as e:
            zip_path.unlink(missing_ok=True)
            raise ExtractionError(f"Failed to extract {module_code}: {e}")
        finally:
            # Clean up zip file
            zip_path.unlink(missing_ok=True)

        # Update config to enable module
        self.storage.enable_module(module_code)

        logger.info(f"Successfully installed {module_code}")
        return True

    def _download_file(self, url: str, dest_path: Path, progress_callback=None):
        """Download a file with optional progress reporting."""
        response = requests.get(
            url,
            stream=True,
            timeout=self._download_timeout
        )
        response.raise_for_status()

        total_size = int(response.headers.get("content-length", 0))
        downloaded = 0

        with open(dest_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
                downloaded += len(chunk)
                if progress_callback and total_size:
                    progress_callback(downloaded, total_size)

    def _extract_module(self, zip_path: Path, module_code: str):
        """
        Extract a SWORD module zip file.

        SWORD zips typically contain:
        - mods.d/{module}.conf  (module configuration)
        - modules/texts/{category}/{module}/  (module data)

        Files are extracted to match the SWORD expected structure where
        DataPath in .conf files is relative to the sword root.
        """
        with zipfile.ZipFile(zip_path, "r") as zf:
            # Check zip contents
            namelist = zf.namelist()
            logger.debug(f"Zip contents: {namelist[:10]}...")

            for member in zf.infolist():
                # Skip directories
                if member.is_dir():
                    continue

                # Normalize path separators
                member_path = member.filename.replace("\\", "/")

                # All files extract relative to sword_path
                # This preserves the structure: mods.d/, modules/texts/, etc.
                dest_path = self.storage.sword_path / member_path
                self._extract_member(zf, member, dest_path)

    def _extract_member(self, zf: zipfile.ZipFile, member: zipfile.ZipInfo, dest_path: Path):
        """Extract a single zip member to destination path."""
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        with zf.open(member) as src, open(dest_path, "wb") as dst:
            shutil.copyfileobj(src, dst)

        logger.debug(f"Extracted: {dest_path}")

    def remove_module(self, module_code: str) -> bool:
        """
        Remove an installed module.

        Args:
            module_code: The module code to remove

        Returns:
            True if removed, False if not installed
        """
        module_code = module_code.upper()

        if not self.is_installed(module_code):
            logger.info(f"Module {module_code} not installed")
            return False

        # Find and remove conf file
        conf_removed = False
        for conf_file in self.storage.sword_mods_path.glob("*.conf"):
            if conf_file.stem.upper() == module_code:
                conf_file.unlink()
                conf_removed = True
                logger.debug(f"Removed conf: {conf_file}")
                break

        # Find and remove module data directory
        # Module data is in modules/texts/{category}/{module_lower}/
        module_lower = module_code.lower()
        if self.storage.sword_texts_path.exists():
            for category_dir in self.storage.sword_texts_path.iterdir():
                if category_dir.is_dir():
                    module_dir = category_dir / module_lower
                    if module_dir.exists():
                        shutil.rmtree(module_dir)
                        logger.debug(f"Removed data: {module_dir}")

        # Update config to disable module
        self.storage.disable_module(module_code)

        logger.info(f"Removed module {module_code}")
        return conf_removed

    def get_sword_library(self):
        """
        Get a pysword SwordLibrary instance for reading modules.

        Returns:
            pysword.modules.SwordLibrary or None if no modules installed
        """
        try:
            from pysword.modules import SwordModules

            modules_path = str(self.storage.sword_path)
            sword = SwordModules(modules_path)
            return sword
        except ImportError:
            logger.error("pysword not installed")
            return None
        except Exception as e:
            logger.error(f"Failed to load SWORD library: {e}")
            return None
