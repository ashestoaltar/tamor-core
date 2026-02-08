# Phase 9: Intelligence Redesign — Tamor Learns to Grow

## Vision

Phases 1–7 built Tamor's mind. Phase 8 defined its soul. Phase 9 teaches it to grow.

Tamor's core systems — memory, personality, context assembly, routing, and learning — were built as functional v1 implementations. They work. But they were designed without the ability to evolve, adapt, or deepen over time. After hundreds of conversations, thousands of library files, and months of use, Tamor knows its user deeply — but none of that knowledge shapes how it behaves, retrieves, or reasons.

Phase 9 redesigns Tamor's intelligence layer so the system gets meaningfully better with use.

---

## What's Wrong Today

### Memory: Flat Bag of Text
- 81 memories, all equal weight, no relationships between them
- Auto-classification by regex pattern matching ("my name is", "i prefer") — fragile, noisy
- Retrieval: load all memories, cosine similarity, top 5. No sense of *what kind* of memory matters right now
- No forgetting. No decay. No consolidation. Irrelevant memories accumulate forever
- No distinction between types: identity facts, episodic events, procedural knowledge, and working context all sit in one table with a category tag

### Personality: Static YAML
- `personality.json` is a fixed file that never changes
- After 81 memories and hundreds of conversations, Tamor has deep knowledge of its user — none of it shapes tone, vocabulary, depth, or approach
- Mode personas are 800+ lines of static instruction. After 50 theological conversations, Tamor should know the user's positions, favorite scholars, and hermeneutic instincts — it doesn't

### Context Assembly: Dumb Concatenation
- System prompt built by stacking layers: personality + mode persona (~2000 tokens) + memories + scripture refs + library chunks (up to 4000 chars) + project files + GHM instructions + hermeneutic directives
- No token budget awareness — can easily blow past context limits with large projects
- No prioritization — is a library chunk more important than a memory right now? Depends on the question, but the system doesn't reason about that
- No compression of older conversation history

### Agent Routing: Single-Path, No Collaboration
- Router picks one intent → one agent sequence → runs linearly
- Agents can't call each other or request help mid-task
- No dynamic re-routing (researcher can't hand off to planner mid-discovery)
- No parallel execution (can't search library AND scripture simultaneously)

### Learning: The System Never Gets Smarter
- After months of use, nothing improves
- Routing uses the same regex + phi3 classification forever
- Memory retrieval doesn't learn which memories were useful
- Library search doesn't learn which sources the user valued
- No feedback loops anywhere. Everything is static rules that require manual maintenance

### Conversation Continuity
- Each conversation starts nearly from scratch
- No session summaries ("last time we discussed X and decided Y")
- No thread tracking ("this is the 4th conversation about the embedding migration")
- No working context that persists across related conversations

---

## What's Already Strong (Don't Over-Redesign)

- **Epistemic honesty system** — contestation levels, risky phrase detection, hedge-collapsing, repair pipeline. Genuinely more sophisticated than most AI systems.
- **GHM / Hermeneutic framework** — canonical authority order, frame challenges, framework disclosure. Real intellectual infrastructure unique to Tamor's use case.
- **Mode personas** — the 800+ line deep specs for Scholar, Forge, Path, etc. feel like real personalities, not generic helpfulness.

These systems may benefit from *integration* with the redesigned memory/context layer, but their core design is sound.

---

## Phase 9 Components

### 9.1 Memory Redesign — Tiered, LLM-Managed, Relational

**The single highest-impact change.** Foundation for everything else.

#### Tiered Memory Architecture

| Tier | Name | Lifecycle | Injection | Examples |
|------|------|-----------|-----------|----------|
| **Core** | Identity & Values | Permanent, manually curated | Always loaded (every request) | "Chuck is the creator of Tamor", "Torah-observant perspective", "Values clarity and depth" |
| **Long-term** | Knowledge & Preferences | Persistent, subject to consolidation/decay | Retrieved by relevance (semantic search) | "Tamor uses Flask + React", "Prefers concise 3-5 paragraph responses", "Studies with Tim Hegg and Monte Judah" |
| **Episodic** | Session Summaries | Persistent but fades unless reinforced | Retrieved by relevance + recency | "2026-02-07: Worked on BGE-M3 embedding migration", "2026-02-05: Built planner/writer pipeline" |
| **Working** | Current Session | Ephemeral, dies with conversation | Always present in current context | Active topic, recent decisions, in-progress tasks |

#### LLM-Managed Storage (Replace Regex Classification)

The current regex auto-classifier (`classify_auto_memory()`) is the weakest link. Replace with:

- **Post-conversation archivist pass**: After each conversation, the Archivist agent reviews the exchange and decides what to store, update, consolidate, or discard
- **LLM judgment for classification**: The LLM determines tier, category, and importance — not regex
- **Explicit tools**: `remember()`, `update_memory()`, `forget()`, `consolidate()` — the archivist calls these as tools
- **User override always wins**: "Remember this" / "Forget that" commands take precedence

#### Memory Relationships

Move beyond isolated text blobs:

- **Entity-relationship tagging**: "Chuck → builds → Tamor", "Tamor → uses → Flask", "Tim Hegg → teaches → TorahResource"
- **Connected retrieval**: When asking about Tamor's stack, pull related memories about Flask, React, SQLite — not just cosine-similar text
- **Memory clusters**: Group related memories (all memories about "library system", all memories about "theological methodology")

#### Memory Aging & Decay

- **`last_accessed` tracking**: Record when each memory was last retrieved for context
- **Recency-weighted retrieval**: Recent memories get a boost, old untouched memories fade
- **Configurable decay curve**: Not deletion — reduced retrieval priority
- **Reinforcement**: Memories that keep getting retrieved stay strong
- **Consolidation**: Periodic pass merges similar/redundant memories ("mentioned preferring concise answers 5 times" → single memory with higher confidence)

#### Migration Strategy

- Keep existing `memories` table as-is during transition
- Add `memory_tier`, `last_accessed`, `access_count`, `confidence`, `entity_links` columns
- Backfill existing 81 memories into appropriate tiers (most → long-term, 5-10 → core)
- New classification pipeline runs alongside old one until validated
- Old regex classifier becomes fallback, then removed

---

### 9.2 Context Assembly Redesign — Token-Budget-Aware, Relevance-Ranked

**Currently**: Stack everything, hope it fits. **Target**: Intelligent allocation.

#### Token Budget System

- Define total context budget (model-dependent: 8K, 32K, 128K, etc.)
- Allocate fixed budgets for non-negotiable content:
  - System identity + mode persona: ~2000 tokens (fixed)
  - Core memories: ~500 tokens (always loaded)
  - Conversation history: variable, compressed if needed
- Remaining budget allocated dynamically by relevance

#### Relevance-Ranked Injection

For each request, score all injectable context against the current query:

- Long-term memories (semantic similarity to query)
- Episodic memories (relevance + recency)
- Library chunks (semantic similarity)
- Scripture references (if detected)
- Project files (if project-scoped)
- GHM/hermeneutic directives (if theological)

Rank everything, fill the budget from most relevant to least. What doesn't fit doesn't get injected — but the system knows it exists and can note "additional context available on request."

#### Conversation History Compression

- Recent messages: verbatim
- Older messages: LLM-summarized (key points, decisions, open questions)
- Ancient messages: dropped or compressed to single-line summaries
- This prevents conversation history from consuming the entire budget in long sessions

#### Context Source Attribution

Every piece of injected context carries metadata:
- Source type (memory, library, scripture, project file)
- Relevance score
- Why it was included

This feeds into the learning loop (9.4) and makes context decisions auditable.

---

### 9.3 Personality Evolution — Memory-Informed Identity

**Currently**: Static YAML. **Target**: Core identity stays fixed; expression adapts.

#### What Stays Fixed

- Tamor's name, Hebrew roots, core directives
- Ethical boundaries (BOUNDARIES.md)
- Epistemic honesty constraints
- GHM hermeneutic rules

These are authored, not learned. They define Tamor's character.

#### What Adapts

- **Vocabulary depth**: After 50 theological conversations, Tamor should use Hebrew terms more naturally without being told to
- **Preferred response style**: If the user consistently prefers concise answers, the system prompt should reflect that — not from YAML, but from observed memory
- **Domain familiarity**: Tamor should recognize when it's in well-traveled territory vs. new ground, and adjust confidence accordingly
- **Source preferences**: If the user consistently values certain scholars or sources, weight them higher in research

#### Implementation

- **Memory-derived personality layer**: At prompt build time, query core + long-term memories for personality-relevant facts
- **Dynamic persona enrichment**: Mode personas stay as baseline, but get enriched with user-specific knowledge
- **Example**: Scholar mode baseline says "use Hebrew terms with explanation." After learning user is fluent, Scholar mode says "use Hebrew terms freely; user is fluent"
- **Guardrail**: Personality adaptation never overrides ethical boundaries or epistemic rules

---

### 9.4 Learning Loops — The System Gets Better

**Currently**: Nothing improves. **Target**: Simple, measurable feedback.

#### What We Track

- **Memory utility**: Which memories were retrieved but not relevant? Which were relevant and used? (Implicit signal from conversation flow)
- **Source quality**: Which library chunks actually got cited in responses? Which were retrieved but ignored?
- **Routing accuracy**: When the user switches modes manually, was the auto-detected mode wrong? Track mismatches
- **Search patterns**: What does the user search for repeatedly? These are signals for memory creation or library gaps

#### How We Use It

- **Memory scoring**: Memories that are frequently retrieved and useful get higher retrieval priority. Memories that are retrieved but never useful get deprioritized
- **Source ranking**: Library sources that consistently prove useful for certain query types get boosted
- **Routing refinement**: Classification patterns that lead to mode switches get adjusted
- **Gap detection**: Queries that consistently return poor results signal missing content or weak coverage

#### What We Don't Do

- No training or fine-tuning (we don't control the LLM weights)
- No hidden optimization (all learning is inspectable via memory/settings)
- No behavior changes without user awareness

---

### 9.5 Agent Collaboration (Future)

**Lower priority than 9.1–9.4.** Only build if the current pipeline model blocks real workflows.

#### Potential Improvements

- **Agent-to-agent requests**: Researcher can ask Archivist "what do we already know about this topic?" mid-research
- **Dynamic re-routing**: If researcher discovers the question is actually a planning question, hand off to Planner
- **Parallel execution**: Search library AND scripture AND memories simultaneously, merge results
- **Composition**: Complex tasks can involve multiple agents collaborating, not just sequential handoffs

#### Decision Criteria

Build this only when:
- Users report frustration with single-agent limitations
- Specific workflows are blocked (document which ones)
- The memory and context redesign is stable (9.1 + 9.2 are prerequisites)

---

## Implementation Order

| Order | Component | Why This Order | Dependencies |
|-------|-----------|---------------|--------------|
| 1 | **9.1 Memory Redesign** | Foundation for everything else. Context assembly needs tiered memory. Personality needs memory to adapt from. Learning needs memory to track. | None |
| 2 | **9.2 Context Assembly** | Can't do intelligent injection without tiered memory. Once memory is tiered, context assembly becomes the bottleneck. | 9.1 |
| 3 | **9.3 Personality Evolution** | Requires tiered memory (core vs long-term) and intelligent context assembly (dynamic persona enrichment). | 9.1, 9.2 |
| 4 | **9.4 Learning Loops** | Requires all previous systems to be stable. Learning tracks memory utility, source quality, and routing accuracy — all of which depend on 9.1-9.3. | 9.1, 9.2, 9.3 |
| 5 | **9.5 Agent Collaboration** | Only if needed. Evaluate after 9.1-9.4 are stable. | 9.1, 9.2 minimum |

---

## Design Principles

1. **Evolution, not revolution**: Each component can be built incrementally alongside the existing system. Old systems stay as fallback until new ones are validated.
2. **Inspectable intelligence**: Every adaptive behavior is visible to the user. No hidden optimization. Memory, personality changes, and learning signals are all auditable.
3. **User sovereignty**: Tamor adapts to serve the user better, not to develop its own agenda. The user can always override, correct, or reset any learned behavior.
4. **Earned trust**: The epistemic and hermeneutic systems (Phase 8) constrain what Tamor claims. Phase 9 makes Tamor smarter within those constraints, not looser with them.
5. **Simple before clever**: Start with the simplest version of each component that delivers value. Complexity only when measured benefit justifies it.

---

## Success Criteria

Phase 9 succeeds when:

1. Tamor remembers what matters and forgets what doesn't — without being told
2. Context injection is always relevant, never overflows, and adapts to the question
3. After 100 conversations, Tamor's responses feel notably more personalized than after 10
4. The user never has to re-explain something Tamor should already know
5. System behavior is transparent: you can always ask "why do you know this?" and get a clear answer

---

## Relationship to Existing Roadmap

- **Phase 8 declared stability**: "Core is feature-complete." Phase 9 does not add features — it redesigns how existing intelligence works.
- **Extensions governance still applies**: Phase 9 components enter the main roadmap because they touch core architecture, not because they bypass governance.
- **Parked items absorbed**: Roadmap-extensions items #20 (Memory Aging), #21 (Compression), #22 (Token Budget), #23 (Memory Stats Dashboard) are subsumed into Phase 9. They are no longer separate proposals.
- **Library system untouched**: Phase 9 redesigns how Tamor *uses* the library (context assembly, source ranking), not the library infrastructure itself. The BGE-M3 migration, harvest pipeline, and ingest system remain as-is.

---

## Open Questions

1. **Memory graph complexity**: How much entity-relationship structure is worth maintaining? Simple tags ("relates to: Tamor") vs. full knowledge graph (entities, predicates, objects)?
2. **Consolidation automation**: Should consolidation run on a schedule, after N conversations, or on-demand? What's the right trigger?
3. **Personality drift guardrails**: How do we prevent personality adaptation from drifting in unwanted directions? User review of learned traits? Periodic reset option?
4. **Learning signal quality**: Implicit signals (what got used) vs. explicit signals (user thumbs-up/down). Which is more reliable? Both?
5. **Multi-session episodic memory**: How many session summaries before they need their own consolidation? What's the retention window?
