# api/services/library/ocr_service.py

"""
OCR service for library files.

Detects scanned PDFs and runs OCR to extract text.
Uses ocrmypdf with --skip-text to only process pages without text layers.
"""

import shutil
import subprocess
from pathlib import Path
from typing import Optional, Tuple

from utils.db import get_db

from .storage_service import LibraryStorageService


# Minimum characters to consider a PDF as having usable text
# Below this threshold, we assume it's a scanned document
MIN_TEXT_CHARS = 100

# Minimum chars per page - if average is below this, likely scanned
MIN_CHARS_PER_PAGE = 50


class LibraryOCRService:
    """Service for OCR processing of scanned library files."""

    def __init__(self):
        self.storage = LibraryStorageService()

    def is_ocr_available(self) -> bool:
        """Check if ocrmypdf is installed."""
        return shutil.which("ocrmypdf") is not None

    def needs_ocr(self, library_file_id: int) -> Tuple[bool, str]:
        """
        Check if a library file needs OCR.

        Returns:
            (needs_ocr, reason)
        """
        conn = get_db()

        # Get file info
        cur = conn.execute(
            "SELECT mime_type, stored_path FROM library_files WHERE id = ?",
            (library_file_id,),
        )
        row = cur.fetchone()
        if not row:
            return (False, "file_not_found")

        # Only process PDFs
        if row["mime_type"] != "application/pdf":
            return (False, "not_pdf")

        # Check cached text length
        cur = conn.execute(
            "SELECT text_content FROM library_text_cache WHERE library_file_id = ?",
            (library_file_id,),
        )
        text_row = cur.fetchone()

        if not text_row:
            return (True, "no_text_extracted")

        text = text_row["text_content"] or ""
        text_len = len(text.strip())

        if text_len < MIN_TEXT_CHARS:
            return (True, f"text_too_short ({text_len} chars)")

        # Could also check chars per page ratio here if we have page count

        return (False, "has_text")

    def run_ocr(
        self,
        library_file_id: int,
        language: str = "eng",
        optimize: int = 1,
    ) -> dict:
        """
        Run OCR on a library file.

        Args:
            library_file_id: File to OCR
            language: Tesseract language code
            optimize: Optimization level (0-3)

        Returns:
            {'success': bool, 'message': str, 'pages_ocred': int?}
        """
        if not self.is_ocr_available():
            return {"success": False, "message": "ocrmypdf not installed"}

        conn = get_db()

        # Get file path
        cur = conn.execute(
            "SELECT stored_path, filename FROM library_files WHERE id = ?",
            (library_file_id,),
        )
        row = cur.fetchone()
        if not row:
            return {"success": False, "message": "file_not_found"}

        file_path = self.storage.resolve_path(row["stored_path"])
        if not file_path.exists():
            return {"success": False, "message": "file_missing_on_disk"}

        # Create temp output path
        output_path = file_path.with_suffix(".pdf.ocr")

        try:
            # Run ocrmypdf
            result = subprocess.run(
                [
                    "ocrmypdf",
                    "--skip-text",  # Only OCR pages without text
                    "--optimize", str(optimize),
                    "--language", language,
                    "--quiet",
                    str(file_path),
                    str(output_path),
                ],
                capture_output=True,
                text=True,
                timeout=600,  # 10 minute timeout
            )

            if result.returncode == 0:
                # Replace original with OCR'd version
                output_path.replace(file_path)

                # Clear text cache so it gets re-extracted
                conn.execute(
                    "DELETE FROM library_text_cache WHERE library_file_id = ?",
                    (library_file_id,),
                )
                conn.commit()

                return {"success": True, "message": "ocr_complete"}

            elif result.returncode == 6:
                # Already has text, nothing to do
                if output_path.exists():
                    output_path.unlink()
                return {"success": True, "message": "already_has_text"}

            else:
                if output_path.exists():
                    output_path.unlink()
                return {
                    "success": False,
                    "message": f"ocrmypdf failed: {result.stderr[:200]}",
                }

        except subprocess.TimeoutExpired:
            if output_path.exists():
                output_path.unlink()
            return {"success": False, "message": "ocr_timeout"}

        except Exception as e:
            if output_path.exists():
                output_path.unlink()
            return {"success": False, "message": str(e)}

    def process_if_needed(self, library_file_id: int) -> dict:
        """
        Check if OCR is needed and run it if so.

        Returns:
            {'ocr_run': bool, 'reason': str, 'result': dict?}
        """
        needs, reason = self.needs_ocr(library_file_id)

        if not needs:
            return {"ocr_run": False, "reason": reason}

        result = self.run_ocr(library_file_id)

        return {"ocr_run": True, "reason": reason, "result": result}
