# Harvest Metadata Schema

Version 1.0 — All scrapers MUST produce raw JSON conforming to this schema.

## Raw JSON Format

Every raw JSON file placed in `/mnt/library/harvest/raw/{source}/` must contain:

```json
{
  "text": "REQUIRED — full text content",
  "filename": "REQUIRED — output filename (e.g., torah-class-genesis-l01.txt)",
  "source_name": "REQUIRED — ministry/organization name",
  "teacher": "REQUIRED — primary teacher/author",
  "content_type": "REQUIRED — enum value (see below)",
  "url": "REQUIRED — source URL for provenance",

  "title": "Human-readable title",
  "date": "ISO date (YYYY-MM-DD)",
  "collection": "Tamor collection name for auto-assignment",
  "series": "Series name (e.g., Genesis)",
  "topics": ["topic1", "topic2"],
  "copyright_note": "Personal research use only",
  "stored_path": "Override stored_path (usually auto-generated)",
  "mime_type": "text/plain",

  "metadata": {
    "theological_stream": "enum value (see below)",
    "scripture_refs": ["Genesis 1-3", "John 1:1"],
    "language": "en",
    "original_format": "pdf | html | mp3 | auto-caption | markdown",
    "word_count": 4500,
    "lesson_number": 1
  }
}
```

## content_type Values

| Value | Use For |
|-------|---------|
| `lesson` | Structured teaching lesson (Torah Class, Bible study) |
| `article` | Standalone written article |
| `transcript` | Transcription of audio/video |
| `study` | In-depth study guide or workbook |
| `devotional` | Daily/weekly devotional |
| `sermon` | Sermon or message |
| `commentary` | Verse-by-verse or chapter commentary |
| `lecture` | Academic lecture |

## theological_stream Values

| Value | Examples |
|-------|---------|
| `messianic-torah-observant` | Torah Class, FFOZ, Tim Hegg, Monte Judah |
| `hebrew-roots` | Broader Hebrew Roots movement |
| `messianic-jewish` | Jewish believers in Yeshua |
| `evangelical-reformed` | Traditional Protestant/Reformed |
| `academic-secular` | Secular academic scholarship |
| `patristic` | Church fathers / early Christianity |
| `founding-era` | American founding documents |

## Field Flow: Raw JSON → Package → Database

```
Raw JSON                Package JSON              library_files.metadata_json
─────────               ────────────              ──────────────────────────
source_name         →   source.name           →   harvest_source
teacher             →   source.teacher        →   harvest_teacher
content_type        →   source.content_type   →   harvest_content_type
url                 →   source.url            →   harvest_url
copyright_note      →   source.copyright_note →   harvest_copyright
                        processing.*          →   harvest_processed_at, harvest_processor
metadata.date       →   file.metadata.date    →   date
metadata.topics     →   file.metadata.topics  →   topics
metadata.series     →   file.metadata.series  →   series
metadata.*          →   file.metadata.*       →   (passed through as-is)
collection          →   source.collection     →   (used for collection assignment)
```

## Naming Conventions

**Filenames:** `{source-slug}-{book/topic}-l{nn}-{slug}.txt`
- `torah-class-genesis-l01-intro.txt`
- `yavoh-2024-03-the-appointed-times.txt`
- `torahresource-acts15-who-are-the-gentiles.txt`

**Source slugs (for directories):**
- `torah-class` — Torah Class (Tom Bradford)
- `lion-lamb` — Lion & Lamb Ministries
- `torahresource` — TorahResource (Tim Hegg)
- `hrn` — Hebraic Roots Network

## Notes

- The processor (`process_raw.py`) passes `metadata` dict through to the package unchanged
- The import service (`harvest_import_service.py`) stores everything in `metadata_json`
- No database schema changes needed — `metadata_json` is flexible JSON
- All `metadata.*` fields are optional — add what you have, skip what you don't
- Hebrew corrections are applied automatically by the processor
