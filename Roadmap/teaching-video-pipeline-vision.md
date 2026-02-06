# Teaching Video Pipeline — Vision & Planning Document

**Created:** February 5, 2026
**Status:** Pre-planning / Captured Vision
**Context:** This document captures the full thought process from competitive analysis through technical feasibility to realistic timeline. It is NOT a committed roadmap item — it's a reference for when the time is right.

---

## 1. Origin: The 119 Assistant Comparison

### What 119 Built

119 Ministries launched the **119 Assistant** (119assistant.ai) publicly at Sukkot 2025. It's a subscription-based AI Bible study chatbot — a Next.js web app on top of OpenAI's API (GPT-5 available as "Boost" for 3 credits/message). As of Build 1.32 (January 2026), it offers:

- **9 chat modes:** Standard, Response, Review, Q&A, Debate, Study, ELI12, Kids, Family Study
- **Doctrine guardrails:** Responses align with 119's published teachings; explicit ekklesia continuity enforcement (Acts 7:38, Eph 2:11–22); avoids teaching a "Church Age"
- **YHWH rendering:** Replaces "LORD" with "YHWH" in all OT quotes; uses WEB translation for pop-ups
- **Bible verse pop-ups:** Hover/tap Scripture references for inline preview
- **Community Prompt Hub:** Users submit, browse, and vote on prompts
- **Referral program:** Free month for new subscribers, 100 bonus message credits for referrers
- **Pricing:** Basic $9.99/250 msgs, Pro $19.99/500 msgs, Add-on 100 msgs for $4.99
- **Per-message cost transparency:** $0.03–$0.18 per message in API costs

**Coming soon (per their roadmap):**
- Auto-generated teachings: slides + narration (MP4 download)
- Voice conversations
- Mobile apps (iOS & Android)

### Where Tamor Is Already Ahead

| Dimension | 119 Assistant | Tamor |
|-----------|---------------|-------|
| **Epistemic honesty** | Single-framework enforcement | Four-tier classification (Deterministic / Grounded-Direct / Grounded-Contested / Ungrounded) |
| **LLM architecture** | Single provider (OpenAI) | Multi-provider with theological bias testing (xAI Scholar, Anthropic Engineer, Ollama local) |
| **Research grounding** | Teaching corpus via system prompt | Researcher agent queries 27,839+ library chunks before LLM generates |
| **Provenance** | Trust the response | Citations tracked, sources surfaced, verifiable |
| **Configuration** | System prompts (model-decided) | YAML governance files (human-controlled) |
| **Data ownership** | Cloud SaaS, their servers | Local-first, your hardware, full ownership |
| **Agent architecture** | One chatbot, different modes | Specialized agents (Researcher, Writer, Engineer, Archivist) with provider routing |
| **Framework approach** | Enforces one doctrinal lens | GHM challenges framework assumptions before analysis |

### Features Worth Adapting

| 119 Feature | Tamor Adaptation | Effort | Notes |
|---|---|---|---|
| Inline verse pop-ups | Click/hover Scripture refs in chat to preview via SWORD/Sefaria | Medium | Natural fit for chat panel |
| Mode descriptions in UI | "What this mode does / Best for / Not for" in mode selector | Low | Phase 3.4 candidate |
| Auto-reset mode toggle | Setting to revert to default mode after each response | Low | Extensions candidate |
| YHWH rendering option | Display preference to substitute LORD→YHWH in reference text | Low | Extensions candidate |
| Prompt templates library | Local collection of reusable research prompts | Low-Medium | Extensions candidate |
| "Test everything" footer | Configurable reminder appended to scholarly responses | Low | Personality config |
| Output formatting per mode | Different response structures per mode | Medium | Writer agent maturity |

### Strategic Takeaway

119 proved the market exists for AI-assisted Torah-positive Bible study. They're iterating fast (32 builds in ~4 months) and charging $10–20/month. Their weakness is depth — it's a polished ChatGPT wrapper with good UX and strong doctrinal system prompts. Tamor is a research instrument. The features worth pulling across are mostly presentation-layer improvements. The core architecture difference is philosophical and shouldn't change.

> "I know where the ground is firm, and I won't pretend the hills are bedrock."
>
> 119 Assistant pretends the hills are bedrock — confidently. Tamor tells you which is which.

---

## 2. The Teaching Video Pipeline Concept

### What It Is

An automated pipeline that transforms a topic into a downloadable teaching video (MP4): library-grounded research → structured slide content → AI-generated illustrations → local TTS narration → video composition. A 5–7 slide teaching, roughly 3–5 minutes, with every claim traceable to a library source.

### Why It Matters

119's "coming soon" version will almost certainly be: topic → GPT generates script → template slides → cloud TTS → video. A black box.

Tamor's version: topic → Researcher queries library → Writer structures grounded content with citations → custom AI illustrations matched to each point → local Piper narration → local FFmpeg composition. Every claim traceable. No cloud dependency for narration. Full control over voice, pacing, branding.

Same feature category, fundamentally different quality floor.

### The Six-Stage Pipeline

```
┌─────────────────────────────────────────────────────────────┐
│                  TEACHING VIDEO PIPELINE                     │
├──────────┬──────────────────────────────────────────────────┤
│ Stage 1  │ RESEARCH                                         │
│          │ Researcher agent queries Global Library           │
│          │ Tool: Existing Researcher + Library (27,839+ chunks) │
│          │ Status: ✅ BUILT                                  │
├──────────┼──────────────────────────────────────────────────┤
│ Stage 2  │ STRUCTURE                                        │
│          │ Writer agent produces structured slide output     │
│          │ (title, headings, points, notes, image prompts,  │
│          │  source citations — per slide)                    │
│          │ Tool: Writer agent with new output format         │
│          │ Status: 🔶 NEW OUTPUT MODE for existing agent     │
├──────────┼──────────────────────────────────────────────────┤
│ Stage 3  │ ILLUSTRATION                                     │
│          │ Custom AI image per slide via Grok Imagine        │
│          │ Prompts generated by Writer in Stage 2            │
│          │ Tool: xAI Grok Imagine API (grok-imagine-image)   │
│          │ Status: 🔶 NEW — wire into llm_service.py         │
├──────────┼──────────────────────────────────────────────────┤
│ Stage 4  │ SLIDE COMPOSITION                                │
│          │ Layer text content over illustrations             │
│          │ Tool: HTML templates → Playwright screenshot      │
│          │ Status: 🔶 NEW component                          │
├──────────┼──────────────────────────────────────────────────┤
│ Stage 5  │ NARRATION                                        │
│          │ Piper TTS reads speaker notes per slide           │
│          │ Tool: Existing tts_service.py (3.8x real-time)    │
│          │ Status: ✅ BUILT                                  │
├──────────┼──────────────────────────────────────────────────┤
│ Stage 6  │ VIDEO ASSEMBLY                                   │
│          │ Combine slide images + audio → MP4                │
│          │ Tool: FFmpeg or MoviePy                           │
│          │ Status: 🔶 NEW — glue code over available tools   │
└──────────┴──────────────────────────────────────────────────┘
```

### Example Structured Output (Stage 2)

The Writer agent would produce something like this for each slide:

```yaml
teaching:
  title: "The Sabbath Was Not Abolished"
  topic: sabbath-continuity
  estimated_duration: "4:30"
  slides:
    - type: title
      heading: "The Sabbath Was Not Abolished"
      subheading: "What Scripture Actually Says"
      notes: >
        Welcome to this teaching. Today we're examining one of the most
        common claims in modern Christianity — that the Sabbath was
        abolished at the cross. We'll look at the passages most often
        cited and what they actually say in context.
      image_prompt: >
        Ancient Torah scroll partially unrolled on a wooden table,
        warm oil lamp light, Hebrew text visible, peaceful study atmosphere
      sources: []

    - type: content
      heading: "The Common Claim"
      points:
        - "Colossians 2:16 is cited as proof the Sabbath ended"
        - "But Paul is addressing shadow vs. substance — not abolition"
        - "The Greek 'mē oun tis' means 'don't let anyone judge you'"
      notes: >
        The most frequently cited passage against Sabbath observance
        is Colossians 2:16. Let's look at what Paul actually wrote
        and who he was writing to...
      image_prompt: >
        Open Bible with highlighted text, study notes in margins,
        warm desk lamp, scholarly atmosphere
      sources:
        - chunk_id: 4821
          source: "119 Ministries - Colossians 2 Study"
        - chunk_id: 12043
          source: "Bill Cloud - Shadow and Substance"

    - type: scripture
      heading: "Colossians 2:16-17"
      text: >
        Therefore let no one pass judgment on you in questions of
        food and drink, or with regard to a festival or a new moon
        or a Sabbath. These are a shadow of the things to come,
        but the substance belongs to Messiah.
      notes: >
        Notice what Paul does NOT say. He does not say these things
        are abolished. He says they are a shadow of things to come.
        A shadow proves the object exists — it doesn't erase it.
      image_prompt: >
        Dramatic shadow cast by a menorah onto a stone wall,
        warm golden light, symbolic and contemplative mood
      sources:
        - chunk_id: 4823
          source: "119 Ministries - Colossians 2 Study"

    - type: summary
      heading: "What We've Seen"
      points:
        - "Colossians 2:16 defends Sabbath keepers, not abolishes Sabbath"
        - "Shadow imagery confirms ongoing relevance"
        - "Context matters — Paul wrote to believers already observing"
      notes: >
        The evidence is clear. When we read these passages in context,
        with attention to the original language and audience, the
        Sabbath stands. Test everything. Always go back to Scripture.
      image_prompt: >
        Sunrise over Jerusalem hills, new day beginning,
        path leading toward the city, hope and continuity
      sources: []
```

---

## 3. Grok Imagine Integration

### What's Available (as of January 28, 2026)

xAI launched the **Grok Imagine API** — a unified bundle for image generation, image editing, video generation, and video editing. Since Tamor already uses xAI for Scholar mode, the API keys and SDK are in place.

**Image Generation** (`grok-imagine-image`):
- Text-to-image, image editing, batch generation (up to 10)
- Configurable aspect ratios (16:9, 4:3, 1:1, 9:16)
- Base64 or URL output
- Simple API via `xai_sdk`

```python
from xai_sdk import Client
client = Client(api_key=os.getenv('XAI_API_KEY'))
response = client.image.sample(
    model="grok-imagine-image",
    prompt="Ancient scroll unrolled on a wooden table, warm lamp light",
    image_format="url",
    aspect_ratio="16:9"
)
# response.url → download image
```

**Video Generation** (`grok-imagine-video`):
- Text-to-video, image-to-video (animate a still), video editing
- Up to 10 seconds per clip at 720p
- Native audio generation (ambient, not speech)
- $4.20/minute (71% cheaper than Veo, 86% cheaper than Sora)
- Async: submit request → poll for result

```python
response = client.video.generate(
    prompt="Scroll slowly unrolling, revealing text",
    model="grok-imagine-video",
    duration=5,
    aspect_ratio="16:9"
)
```

### How Each Fits the Pipeline

**Image generation → Primary tool for slide illustrations.** Each slide gets a custom AI-generated image that matches the content. The Writer agent generates the image prompt as part of its structured output. This is the high-value integration.

**Video generation → Optional polish for animated title cards.** Take the title slide image and animate it (scroll unrolling, candles flickering, sunrise brightening) for a 3–5 second cinematic intro. Nice-to-have, not essential for MVP.

**Video generation is NOT suitable for teaching content itself.** It generates cinematic/creative motion — not presentations with text, bullet points, and structured narration. The narration comes from Piper TTS, the structure comes from slide composition. Grok video is an accent, not the backbone.

### Cost Per Teaching

For a 7-slide teaching:
- 7 image generations: ~$0.15–0.35
- 1 animated title card (optional): ~$0.35–0.70
- Writer agent generation: existing xAI costs (~$0.05–0.15)
- Piper TTS narration: free (local)
- FFmpeg composition: free (local)
- **Total: well under $1 per teaching**

### Integration Point

Add image generation method to the existing xAI provider in `services/llm_service.py`. The provider abstraction is already built. This is a new method on an existing class, not a new architecture.

```python
# Conceptual addition to LLM provider ABC (not xAI-specific)
def generate_image(self, prompt: str, aspect_ratio: str = "16:9") -> str:
    """Generate an image. Returns URL or local path."""
    raise NotImplementedError
```

**Note:** Keep this provider-abstract. Grok Imagine pricing could change; local Stable Diffusion could be swapped in later.

---

## 4. What Already Exists vs. What's Needed

### Already Built

| Component | Location | Status |
|---|---|---|
| Researcher agent + library search | `services/router.py`, `LibrarySearchService` | ✅ Production |
| Writer agent (prose synthesis) | `services/router.py` | ✅ Production |
| Piper TTS with caching | `services/tts_service.py` | ✅ Production |
| Audio chunking & preloading | `services/tts_service.py` | ✅ Production |
| 13 voice models available | `/mnt/library/piper_voices/` | ✅ Installed |
| xAI API integration | `services/llm_service.py` | ✅ Production |
| LLM provider abstraction | `services/llm_service.py` | ✅ Production |
| Pipeline workflow templates | `services/pipeline_service.py` | ✅ Production |
| Global Library (27,839+ chunks) | NAS mount, `LibrarySearchService` | ✅ Growing |

### Needs to Be Built

| Component | Effort | Dependencies | Notes |
|---|---|---|---|
| Writer structured output mode | Low-Medium | Real usage patterns from actual teachings | New output format, not new agent |
| Grok Imagine image endpoint | Low | xAI SDK already configured | New method on provider ABC |
| Slide composition service | Medium | Structured output format finalized | HTML templates + Playwright screenshot |
| Slide template designs | Medium | Design decisions (branding, layout) | 4–5 reusable layouts |
| Video assembly service | Medium | FFmpeg/MoviePy available on Ubuntu | Glue code: images + audio → MP4 |
| "teaching_video" pipeline template | Low | Pipeline service exists | New template in existing system |
| UI trigger + download | Low | Pipeline UI exists | New action in project view |
| **Human review gate** | Low | Pipeline `waiting_review` status exists | Review after Stage 2 and optionally Stage 3 |

---

## 5. Realistic Timeline

### The Principle: Don't Rush It

The content has to be worth putting on slides before the slides matter. The library needs to be richer. The Writer needs more real-world testing. The research workflows need to feel natural. All of that is happening organically through the sermon series, Torah portion teachings, and article projects already planned.

### Natural Sequence

**Now → April 2026 (Weeks 1–8): Foundation & Content**
- Complete Phase 3.4 Interface Restoration
- Expand library content (119 flash drive, OLL founding documents, academic sources)
- Run real research workflows: sermon series, Torah portions, articles
- Learn what the Writer agent produces well and where it falls short
- Tune and test. This is not idle time — it's prerequisite work.

*Signal that this phase is done:* You've written at least 2–3 full teachings through Tamor and have a clear sense of what the structured output should look like.

**April → May 2026 (Weeks 8–12): Foundation Pieces**
- Writer structured output mode (1–2 sessions with Claude Code)
- Grok Imagine image generation wired into `llm_service.py` (half a session)
- Test: can Writer produce a structured slide deck from a topic? Do the image prompts generate good illustrations?

*Signal that this phase is done:* You can give the Writer a topic and get back a structured YAML with slide content, image prompts, and source citations that you'd actually want to present.

**Late May → June 2026 (Weeks 12–16): Pipeline Assembly**
- Slide composition service (1 session)
- Video assembly service (1 session)
- Pipeline template + UI trigger (1 session)
- End-to-end test: topic → MP4

*Signal that this phase is done:* You can input a topic and get a watchable MP4 teaching with grounded content, custom illustrations, and clear narration.

**June → July 2026 (Weeks 16–20): Polish**
- Better slide templates and layouts
- Transitions between slides
- Thumbnail generation for the video
- Voice selection per teaching
- Optional animated title card via Grok video
- Background music option (royalty-free, configurable)

### Development Effort Summary

The actual pipeline-specific development is **4–6 focused sessions with Claude Code**, with the first 2–3 months being work you'd be doing anyway (library, testing, content, tuning). The pipeline doesn't require the Planner agent — it uses the existing pipeline template system for v1. The Planner agent would automate it further in the future.

---

## 6. Governance Notes

### Where This Lives in the Roadmap

This is NOT a committed roadmap phase. Per Tamor's governance rules, new ideas must originate in `Roadmap-extensions.md` and earn promotion through:
- Phase alignment
- Clear rationale
- Bounded scope
- Dependency awareness

When the time is right, this document provides the specification for an extensions entry that could be promoted to a new phase (likely Phase 9.x or a sub-phase of an "Output & Publishing" phase).

### What This Document Is

A captured vision with technical feasibility analysis. A reference for when the foundation work is done and the question becomes "what's the next meaningful capability?" This document says: "We already thought it through. Here's the plan. Here's what needs to be true before we start."

### What This Document Is Not

- Not a commitment
- Not a timeline promise
- Not a reason to skip foundation work
- Not a reason to rush library expansion or Writer tuning

---

## 7. The Difference That Matters

119 Ministries will ship auto-generated teaching videos. They'll be polished, probably good enough, and powered by GPT + cloud TTS + template slides. Their users will appreciate them.

Tamor's teaching videos will be different in ways that matter:
- **Every claim grounded in library sources** — not model-generated assertions
- **Custom illustrations per slide** — not generic templates
- **Local narration** — no cloud dependency, full privacy
- **Source citations embedded** — viewer can verify
- **Epistemic honesty preserved** — contested points marked, not glossed over
- **Human-governed** — you control what gets taught, the pipeline assists

The pipeline doesn't replace the teacher. It gives the teacher superpowers.

> "I know where the ground is firm, and I won't pretend the hills are bedrock."

That principle holds all the way through to the output.
