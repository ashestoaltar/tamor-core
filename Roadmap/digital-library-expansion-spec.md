# Digital Library Expansion Spec

**Status:** Approved for Extension
**Created:** 2026-02-05
**Context:** Conversation between Chuck and Claude (web) planning ebook acquisition pipeline, audio player, and reading workflow

---

## Vision

Tamor's library is the intelligence layer — semantically indexed, searchable, and able to ground AI responses in real sources. But a research library also needs a **consumption layer**: the ability to actually read books and listen to audio teachings from within the workflow.

This spec covers four interconnected pieces:

1. **Ebook Acquisition Pipeline** — Kindle/EPUB → Calibre → NAS → Tamor
2. **Calibre Content Server** — External reading app for full-fidelity book reading
3. **Library Audio Player** — In-Tamor playback of MP3s with transcript sync
4. **"Ask About This" Context** — Bridge between reading/listening and AI chat

---

## Design Principles

- **Don't reinvent the wheel.** EPUB rendering is a solved problem. Use Calibre for reading, not a custom reader.
- **Tamor's reader stays for quick reference.** The existing extracted-text reader is still useful for scanning content, TTS, and bookmarking — it just isn't the right tool for reading a full book cover-to-cover.
- **Intelligence and consumption are decoupled.** You can read anywhere; Tamor answers questions from the indexed library regardless.
- **Automate the boring parts.** Manual conversion is fine for 5 books. For 200+, automation is essential.

---

## 1. Ebook Acquisition Pipeline

### Overview

```
Purchase → Calibre (DRM removal + conversion) → NAS Inbox → Auto-Ingest → Tamor Library
```

### 1.1 Calibre Setup (One-Time)

Install Calibre on the ASUS mini PC:

```bash
sudo apt install calibre
```

Configure:
- **Library location:** `/mnt/library/calibre/` (on NAS, so books survive drive changes)
- **DeDRM plugin:** Install from [github.com/noDRM/DeDRM_tools](https://github.com/noDRM/DeDRM_tools) for Kindle DRM removal
- **Output format:** EPUB preferred (Tamor has full EPUB parsing with chapter structure and metadata)
- **Auto-convert on add:** Enable in Calibre preferences → "Adding books" → auto-convert to EPUB

### 1.2 Acquisition Strategy (Priority Order)

For each book you want to add:

1. **Check Internet Archive first** — Free, already integrated with IA Harvester
2. **Check for DRM-free EPUB** — Publisher direct sales, Google Play Books (some titles). Drop straight to NAS inbox, skip Calibre entirely
3. **Kindle purchase** — Fallback. Requires Calibre + DeDRM conversion

### 1.3 Kindle Workflow

1. Purchase on Amazon
2. Download via Kindle for PC (running under Wine) or Kindle desktop app
3. Calibre auto-imports and strips DRM on add
4. Calibre auto-converts to EPUB
5. EPUB lands in Calibre library on NAS

### 1.4 NAS Inbox Watcher (New Service)

**Purpose:** Monitor a designated inbox folder for new ebook files and auto-ingest them into Tamor's library.

**Path:** `/mnt/library/ebook-inbox/`

**Behavior:**
- Watch for new `.epub`, `.pdf`, `.mobi` files appearing in inbox
- Extract metadata from file (author, title) using ebooklib or similar
- Determine destination folder based on publisher/source:
  - `/mnt/library/books/pronomian-publishing/`
  - `/mnt/library/books/ffoz/`
  - `/mnt/library/books/academic/`
  - `/mnt/library/books/general/`
- Copy file to destination (preserve original in Calibre library)
- Call Tamor ingest API for the new file
- Auto-assign to Library Collection based on folder/publisher
- Log the action, remove from inbox

**Implementation:**
- Start with cron job running every 5 minutes scanning inbox (simpler, more predictable)
- Graduate to `watchdog` library only if scan overhead becomes a problem
- Systemd service (like transcription worker)
- Config in YAML for folder → collection mappings

**File:** `api/services/library/inbox_watcher.py`
**Config:** `config/library_inbox.yml`

```yaml
# library_inbox.yml
inbox_path: /mnt/library/ebook-inbox/
scan_interval_seconds: 300  # 5 minutes
supported_extensions: [.epub, .pdf, .mobi]

# Publisher detection → folder + collection mapping
publisher_rules:
  - match_field: publisher  # from EPUB metadata
    pattern: "Pronomian Publishing"
    destination: books/pronomian-publishing
    collection: "Pronomian Publishing"

  - match_field: publisher
    pattern: "First Fruits of Zion"
    destination: books/ffoz
    collection: "First Fruits of Zion"

  - match_field: author
    pattern: "David Wilber"
    destination: books/pronomian-publishing
    collection: "Pronomian Publishing"

# Fallback for unmatched files
default_destination: books/uncategorized
default_collection: null  # don't auto-assign

# Post-ingest
auto_index: true  # generate embeddings immediately
delete_from_inbox: true  # clean up after successful ingest
```

### 1.5 Calibre Auto-Export (Alternative to Inbox)

If Calibre's "save to disk" or "send to folder" feature can be configured to auto-export converted EPUBs to the inbox folder, the pipeline becomes fully automatic from the moment you add a book to Calibre.

Calibre supports this via:
- **calibredb add** CLI (for scripted imports)
- **Calibre Connect/Send** to a folder
- **Calibre Content Server** webhooks (limited)

The simplest approach: configure Calibre's library location to overlap with the inbox watcher's scan path, or use a symlink.

---

## 2. Calibre Content Server (Reading App)

### Overview

Calibre includes a built-in web-based content server that provides full EPUB reading in the browser. This becomes the "read a book" experience.

### 2.1 Setup

```bash
# Start content server (can run as systemd service)
calibre-server /mnt/library/calibre/ --port 8180 --enable-local-write
```

**Systemd service:** `calibre-server.service`

```ini
[Unit]
Description=Calibre Content Server
After=network.target mnt-library.mount

[Service]
Type=simple
User=chuck
ExecStart=/usr/bin/calibre-server /mnt/library/calibre/ --port 8180 --enable-local-write
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

### 2.2 Access

- **Local:** `http://localhost:8180`
- **From mobile (PWA/network):** `http://<mini-pc-ip>:8180`
- Provides: browse library, full EPUB rendering, bookmarks, reading progress, search

### 2.3 Integration with Tamor

Add a "Read in Calibre" button to Tamor's Library UI for ebook files. This opens the Calibre content server in a new tab, navigated to that book.

**Matching strategy:** Match by file hash or store Calibre's `book_id` in Tamor's `library_files.metadata` JSON. Calibre stores its metadata in `metadata.db` (SQLite) at the library root — can query it directly. Avoid matching by title/filename alone (fragile).

**UI change in LibraryTab.jsx:**
- For files with mime_type `application/epub+zip`: show "Read" button that opens Calibre reader
- For PDFs: existing "View Original" behavior (opens inline in browser)
- For audio: new audio player (see section 3)

---

## 3. Library Audio Player

### Overview

An in-Tamor audio player for MP3 files in the library, with synchronized transcript display.

### 3.1 Features

- **Playback controls:** Play/pause, seek bar, skip ±15s, speed adjustment (0.5x–2x)
- **Transcript sync:** If a Whisper transcript exists for the audio file, display it alongside with the current segment highlighted as audio plays
- **Timestamp navigation:** Click any line in the transcript to jump to that point in the audio
- **Playlist/queue:** Play multiple files in sequence (e.g., a sermon series)
- **Resume:** Remember playback position per file (reuse `reading_sessions` table with content_type='audio')
- **Mini player:** Collapsible player bar that persists while you navigate other tabs (similar pattern to music apps) — **note: this is polish, not MVP**

### 3.2 Architecture

**Backend:**
- `api/routes/audio_api.py` — Serve audio files from library with range request support (for seeking)
- Reuse `reading_sessions` for position tracking (add content_type='audio' support)
- API to fetch transcript with timestamps for a library file

**Frontend:**
- `ui/src/components/AudioPlayer/AudioPlayer.jsx` — Main player component
- `ui/src/components/AudioPlayer/TranscriptSync.jsx` — Scrolling transcript with highlight
- `ui/src/components/AudioPlayer/MiniPlayer.jsx` — Collapsed persistent player (Phase 2)
- `ui/src/context/AudioPlayerContext.jsx` — Global player state (Phase 2)

**API Endpoints:**

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/library/<id>/audio` | GET | Stream audio file (supports Range headers) |
| `/api/library/<id>/transcript` | GET | Get Whisper transcript with timestamps |
| `/api/audio/session` | POST | Get/create audio playback session |
| `/api/audio/session/<id>/position` | POST | Update playback position |
| `/api/audio/queue` | GET/POST | Get/set playback queue |

### 3.3 Transcript Sync Details

Whisper transcripts are already stored as JSON with segment timestamps:

```json
{
  "segments": [
    {"start": 0.0, "end": 4.2, "text": "Welcome to today's teaching..."},
    {"start": 4.2, "end": 8.1, "text": "We're going to be looking at..."}
  ]
}
```

The TranscriptSync component:
- Renders all segments as scrollable text
- Highlights the current segment based on audio currentTime
- Auto-scrolls to keep current segment visible
- Click handler on each segment calls audio.currentTime = segment.start

### 3.4 Mini Player Behavior (Phase 2)

- When audio is playing and user navigates to a different tab, the mini player appears at the bottom of the right panel
- Shows: title, play/pause, progress bar, current time
- Click to expand back to full player view
- Similar to Spotify/podcast app patterns
- **Build after core player + transcript sync are working.** The AudioPlayerContext adds significant UI state complexity.

---

## 4. "Ask About This" Context

### Overview

A lightweight feature that bridges the consumption experience (reading in Calibre, listening in audio player) with Tamor's AI chat.

### 4.1 Concept

When you're reading or listening to something from the library, you can set it as your **active context**. Tamor then prioritizes that item's content when answering questions, without you having to specify "in the book I'm reading..."

### 4.2 Implementation

**Backend:**
- Add `active_context` field to user session or project state
- Structure: `{ content_type: 'library', content_id: 42, title: 'Remember the Sabbath' }`
- When active, the researcher agent boosts search results from this file (similar to project library refs but stronger)
- Inject a system prompt note: "The user is currently reading/listening to: [title]. Prioritize this source when answering questions."

**Frontend:**
- "Set as Active" button on library items (toggle)
- Small indicator in chat header showing what's active
- Auto-set when opening audio player for a file
- Clear manually (manual-only for MVP; timer-based auto-clear deferred to avoid surprising the user)

**API:**

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/context/active` | GET | Get current active context |
| `/api/context/active` | POST | Set active context `{content_type, content_id}` |
| `/api/context/active` | DELETE | Clear active context |

### 4.3 Chat Integration

In `chat_api.py`, when building context:
1. Check for active context
2. If set, fetch chunks from that library file
3. Inject as a prioritized context block (before general library search results)
4. Label it clearly in the system prompt so the LLM knows the user's current focus

---

## 5. Implementation Order

**Phase A — Foundation (do first):**
1. Calibre installation and configuration (manual, one-time)
2. Calibre content server as systemd service
3. NAS folder structure for books (`/mnt/library/books/`)

**Phase B — Automation:**
4. Inbox watcher service (start with cron)
5. Publisher detection and auto-collection assignment
6. "Read in Calibre" button in Library UI

**Phase C — Audio Player:**
7. Audio streaming endpoint with range support
8. AudioPlayer component with playback controls
9. TranscriptSync component
10. Playback session tracking
11. *(Later)* AudioPlayerContext + MiniPlayer for persistence

**Phase D — Context Bridge:**
12. Active context API endpoints
13. Chat integration (context injection)
14. UI indicators (active reading badge, set-as-active buttons)

> **Note:** Phase D (Active Reading Context) can be built independently of Phases A–C. It's low-effort and high-value. Consider building it first.

---

## 6. Known Considerations

### Calibre on Headless Server
Calibre is primarily a GUI app but the content server runs headless. The `calibredb` CLI also works headless for library management. If the mini PC runs Ubuntu Desktop, this is a non-issue.

### DeDRM Legal Note
DeDRM tools remove DRM from books you've purchased for personal use. This is for Chuck's personal research library. The tools should only be used on personally purchased content.

### FFOZ Availability
Not all FFOZ titles may be available digitally. The Torah Club multi-volume commentaries in particular may be physical-only. Check the FFOZ store and Amazon for each title before purchasing. Physical-only titles remain a scanning problem (or a "wait for digital release" situation).

### Calibre ↔ Tamor Deduplication
Both Calibre and Tamor will have copies of the same EPUB files. This is intentional:
- Calibre's copy is for reading (may include metadata edits, covers, etc.)
- Tamor's copy (on NAS) is for indexing and search
- The NAS has 6TB of storage; ebook duplication is negligible (a few GB at most)

### Audio Player and Existing Reader
The audio player is a new component, not a modification of the existing reader. The reader handles text (with optional Piper TTS). The audio player handles original audio files. They serve different purposes and should remain separate.

### Audio Range Request Performance
Flask's `send_file()` handles Range headers but can be unreliable for large files under Gunicorn. If audio files are large (25+ MB MP3s), test thoroughly. If issues arise, consider serving audio directly from nginx via `X-Accel-Redirect`, or serving from the NAS via a static file route.
