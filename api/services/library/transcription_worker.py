"""
Transcription worker for processing the queue.

Uses faster-whisper for CPU-based transcription.
Can be run as a background process or called directly.
"""

import os
import time
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

from utils.db import get_db
from .transcription_service import TranscriptionQueueService
from .library_service import LibraryService
from .storage_service import LibraryStorageService


class TranscriptionWorker:
    def __init__(self):
        self.queue_service = TranscriptionQueueService()
        self.library = LibraryService()
        self.storage = LibraryStorageService()
        self._model_cache = {}

    def _get_whisper_model(self, model_name: str):
        """
        Load and cache a whisper model.

        Uses faster-whisper for CPU inference.
        """
        if model_name in self._model_cache:
            return self._model_cache[model_name]

        try:
            from faster_whisper import WhisperModel

            # Use CPU with int8 quantization for efficiency
            model = WhisperModel(
                model_name,
                device="cpu",
                compute_type="int8"
            )

            self._model_cache[model_name] = model
            return model

        except ImportError:
            raise RuntimeError("faster-whisper not installed. Run: pip install faster-whisper")

    def transcribe_file(
        self,
        audio_path: str,
        model_name: str = 'base',
        language: str = None
    ) -> Dict[str, Any]:
        """
        Transcribe an audio/video file.

        Returns:
            {
                'text': str,           # Full transcript
                'segments': [...],     # Timestamped segments
                'language': str,       # Detected language
                'duration': float      # Audio duration in seconds
            }
        """
        model = self._get_whisper_model(model_name)

        # Transcribe
        segments, info = model.transcribe(
            audio_path,
            language=language,
            beam_size=5,
            vad_filter=True  # Filter out silence
        )

        # Collect segments
        segment_list = []
        full_text_parts = []

        for segment in segments:
            segment_list.append({
                'start': round(segment.start, 2),
                'end': round(segment.end, 2),
                'text': segment.text.strip()
            })
            full_text_parts.append(segment.text.strip())

        full_text = ' '.join(full_text_parts)

        return {
            'text': full_text,
            'segments': segment_list,
            'language': info.language,
            'duration': info.duration
        }

    def process_queue_item(self, queue_item: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a single queue item.

        Returns:
            {'success': bool, 'transcript_id': int?, 'error': str?}
        """
        queue_id = queue_item['id']
        library_file_id = queue_item['library_file_id']
        model = queue_item.get('model', 'base')
        language = queue_item.get('language')

        # Mark as processing
        if not self.queue_service.mark_processing(queue_id):
            return {'success': False, 'error': 'Could not acquire lock'}

        start_time = time.time()

        try:
            # Get file path
            stored_path = queue_item['stored_path']
            full_path = self.storage.resolve_path(stored_path)

            if not full_path.exists():
                raise FileNotFoundError(f"Audio file not found: {full_path}")

            # Transcribe
            result = self.transcribe_file(
                str(full_path),
                model_name=model,
                language=language
            )

            # Save transcript to file
            transcript_filename = f"{Path(queue_item['filename']).stem}_transcript.json"
            transcript_path = self._save_transcript(
                transcript_filename,
                result,
                queue_item
            )

            # Add transcript to library
            transcript_result = self.library.add_transcript(
                file_path=transcript_path,
                source_library_file_id=library_file_id,
                metadata={
                    'source_filename': queue_item['filename'],
                    'model': model,
                    'language': result['language'],
                    'duration_seconds': result['duration'],
                    'segment_count': len(result['segments']),
                    'transcribed_at': datetime.now().isoformat()
                }
            )

            processing_time = int(time.time() - start_time)

            # Mark completed
            self.queue_service.mark_completed(
                queue_id,
                result_library_file_id=transcript_result['id'],
                processing_time=processing_time
            )

            return {
                'success': True,
                'transcript_id': transcript_result['id'],
                'processing_time': processing_time
            }

        except Exception as e:
            self.queue_service.mark_failed(queue_id, str(e))
            return {'success': False, 'error': str(e)}

    def _save_transcript(
        self,
        filename: str,
        result: Dict[str, Any],
        queue_item: Dict[str, Any]
    ) -> str:
        """Save transcript to a JSON file in the library."""
        # Determine save path
        mount_path = self.storage.get_mount_path()
        transcripts_dir = mount_path / 'transcripts'
        transcripts_dir.mkdir(exist_ok=True)

        # Create transcript document
        doc = {
            'source': {
                'filename': queue_item['filename'],
                'library_file_id': queue_item['library_file_id']
            },
            'transcription': {
                'model': queue_item.get('model', 'base'),
                'language': result['language'],
                'duration_seconds': result['duration'],
                'created_at': datetime.now().isoformat()
            },
            'text': result['text'],
            'segments': result['segments']
        }

        # Save
        file_path = transcripts_dir / filename
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(doc, f, indent=2, ensure_ascii=False)

        return str(file_path)

    def process_next(self) -> Optional[Dict[str, Any]]:
        """
        Process the next item in the queue.

        Returns result dict or None if queue is empty.
        """
        item = self.queue_service.get_next_pending()
        if not item:
            return None

        return self.process_queue_item(item)

    def process_batch(self, count: int = 5) -> Dict[str, Any]:
        """
        Process multiple items from the queue.

        Returns:
            {'processed': int, 'success': int, 'failed': int, 'details': [...]}
        """
        results = {
            'processed': 0,
            'success': 0,
            'failed': 0,
            'details': []
        }

        for _ in range(count):
            result = self.process_next()

            if result is None:
                break  # Queue empty

            results['processed'] += 1

            if result['success']:
                results['success'] += 1
            else:
                results['failed'] += 1

            results['details'].append(result)

        return results

    def run_continuous(self, poll_interval: int = 30):
        """
        Run continuously, processing queue items as they appear.

        This is intended for running as a background service.

        Args:
            poll_interval: Seconds to wait when queue is empty
        """
        print(f"Transcription worker started. Poll interval: {poll_interval}s")

        while True:
            try:
                result = self.process_next()

                if result is None:
                    # Queue empty, wait
                    time.sleep(poll_interval)
                elif result['success']:
                    print(f"Transcribed: {result.get('transcript_id')} in {result.get('processing_time')}s")
                else:
                    print(f"Failed: {result.get('error')}")
                    time.sleep(5)  # Brief pause after error

            except KeyboardInterrupt:
                print("Worker stopped")
                break
            except Exception as e:
                print(f"Worker error: {e}")
                time.sleep(10)
