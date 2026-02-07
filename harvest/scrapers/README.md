# Harvest Scrapers

Scripts that discover and download content from ministry websites, producing raw JSON files for the harvest pipeline.

## Pipeline Flow

```
Scraper (this dir)          Processor (processor-1)        Tamor
──────────────────          ──────────────────────         ─────
Discover lessons      →     process_raw.py reads JSON  →   harvest import API
Download transcripts  →     Chunks + embeds text       →   Inserts into library
Write raw JSON to     →     Writes packages to         →   Marks as indexed
/harvest/raw/{source}/      /harvest/ready/                /harvest/ready/imported/
```

## Writing a New Scraper

### 1. Output Format

Write one JSON file per content item to `/mnt/library/harvest/raw/{source-slug}/`.

See `harvest/config/metadata_schema.md` for the full schema. At minimum:

```json
{
  "text": "full extracted text",
  "filename": "source-book-l01-slug.txt",
  "source_name": "Ministry Name",
  "teacher": "Teacher Name",
  "content_type": "lesson",
  "url": "https://example.com/original-page",
  "collection": "Ministry Name",
  "topics": ["topic1", "topic2"],
  "series": "Series Name",
  "metadata": {
    "theological_stream": "messianic-torah-observant",
    "scripture_refs": ["Genesis 1-3"],
    "language": "en",
    "original_format": "pdf",
    "word_count": 4500
  }
}
```

### 2. Two-Phase Design

Separate discovery from downloading:

- `--discover` crawls the site and builds a manifest JSON
- `--download --book X --limit N` fetches content in controlled batches

This lets you review the manifest before downloading and resume from failures.

### 3. Rate Limiting

**Minimum 1.5 seconds between requests.** These are ministry websites, not CDNs. Be polite.

### 4. Naming Conventions

- Source slug: lowercase, hyphens (e.g., `torah-class`, `lion-lamb`)
- Filenames: `{source}-{book/topic}-l{nn}-{slug}.txt`
- Manifest: `/mnt/library/harvest/config/{source}-manifest.json`
- Download log: `/mnt/library/harvest/config/{source}-download-log.json`

### 5. Testing

```bash
# 1. Run discovery
python3 scrapers/torah_class.py --discover

# 2. Download a small batch
python3 scrapers/torah_class.py --download --book genesis --limit 5

# 3. Check raw JSON
cat /mnt/library/harvest/raw/torah-class/*.json | python3 -m json.tool | head -30

# 4. Process (on processor-1)
python3 processor/process_raw.py --source torah-class

# 5. Import to Tamor
curl -b /tmp/tamor-cookies.txt -X POST http://localhost:5055/api/harvest/import-all

# 6. Verify
sqlite3 api/memory/tamor.db "SELECT filename, metadata_json FROM library_files WHERE source_type='harvest' LIMIT 5"
```

## Existing Scrapers

| Script | Source | Content | Items |
|--------|--------|---------|-------|
| `torah_class.py` | torahclass.com | Verse-by-verse Bible study transcripts (PDF) | ~700 lessons |
| `torah_resource.py` | torahresource.com | Tim Hegg articles + Torah commentaries (PDF from S3) | 170 articles, 151 commentaries |
| `yavoh.py` | yavohmagazine.com | Monte Judah messianic teachings (HTML from Squarespace) | 119 articles |

## Running All Scrapers

```bash
# Sequential (default) — discover all, then download all
python3 scrapers/run_all.py

# Concurrent — scrapers run in parallel
python3 scrapers/run_all.py --concurrent

# Specific scrapers only
python3 scrapers/run_all.py --scrapers torah_resource yavoh

# Discovery only / download only
python3 scrapers/run_all.py --discover-only
python3 scrapers/run_all.py --download-only

# Test with limit
python3 scrapers/run_all.py --limit 5 --dry-run
```

## Dependencies

Scrapers run on the **scraper machine** (or Tamor for testing).

Required packages: `requests`, `beautifulsoup4`, `lxml`, `pypdf`, `pyyaml`

Install: `pip install requests beautifulsoup4 lxml pypdf pyyaml`
