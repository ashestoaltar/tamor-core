# Tamor Code Agent — Architectural Decision

**Date:** 2026-02-04
**Decision:** Build a Claude Code-like interactive coding agent as a CLI tool using Tamor's LLM infrastructure
**Status:** Approved — implementation in progress

---

## 1. Background and Motivation

Claude Code's killer feature isn't magic — it's a **tool-use conversation loop** that eliminates the copy-paste-error-trace-fix cycle. The model reads files, proposes changes, applies them, runs commands, sees errors, and iterates — all in a single conversational flow.

This is an agent pattern Tamor already implements for research and writing. The Code Agent extends it to filesystem operations.

### Design Goals

1. **Insurance policy** — If Claude Code disappears or changes, Tamor has its own coding agent
2. **Provider-agnostic** — Works with any provider that supports tool use (Anthropic today, others later)
3. **Tamor-native** — Follows existing architecture patterns exactly
4. **Safety-first** — Git integration, confirmation gates, scoped access
5. **CLI-first** — Interactive terminal interface (the right UX for rapid code iteration)

### Scope: CLI Tool, Not Web Feature

This design produces a **standalone terminal application** that uses Tamor's LLM infrastructure (`llm_service.py`, `AGENT_PROVIDER_MAP`). It does **not** add a "Code" mode to the Tamor web UI. The tool-use loop pattern doesn't map cleanly to the existing web chat's request/response cycle without WebSocket/SSE support.

The `"code": "anthropic"` entry in `AGENT_PROVIDER_MAP` is cheap insurance for future web integration.

---

## 2. Architecture

### Overview

```
┌─────────────────────────────────────────────┐
│              tamor-code (CLI)               │
│                                             │
│  User Input ──► Session Manager             │
│                    │                        │
│                    ▼                        │
│              Conversation Loop              │
│              ┌─────────────┐               │
│              │  LLM Call    │◄── System     │
│              │  (tool-use)  │    Prompt     │
│              └──────┬──────┘               │
│                     │                       │
│              ┌──────▼──────┐               │
│              │ Tool Router  │               │
│              └──────┬──────┘               │
│                     │                       │
│         ┌───────────┼───────────┐          │
│         ▼           ▼           ▼          │
│    File Tools   Shell Tools  Git Tools     │
│    read_file    run_command   git_status   │
│    write_file                 git_commit   │
│    patch_file                 git_diff     │
│    list_dir                                │
│         │           │           │          │
│         └───────────┼───────────┘          │
│                     ▼                       │
│              Tool Results                   │
│              (fed back to LLM)              │
│                                             │
│              Loop until:                    │
│              - Model says "done"            │
│              - User interrupts (Ctrl+C)     │
│              - Max iterations reached       │
└─────────────────────────────────────────────┘
```

### Mapping to Existing Tamor Patterns

| Tamor Concept | Code Agent Equivalent |
|---|---|
| `LLMProvider.chat_completion()` | New: `LLMProvider.tool_use_completion()` |
| `LLMProvider.supports_tool_use()` | New: capability check method |
| `AGENT_PROVIDER_MAP` | New entry: `"code": "anthropic"` |
| Raw `requests` pattern | Matches xAI/Anthropic/Ollama providers |
| "Confirmation over autonomy" | Approval gates before destructive operations |

---

## 3. The One Real Architectural Change

The existing `LLMProvider` ABC only has `chat_completion() → str`. Tool use needs a richer interaction:
- Send tool definitions with messages
- Get back structured tool calls (not just text)
- Send tool results back
- Loop until completion

### New Dataclasses

```python
@dataclass
class ToolDefinition:
    name: str
    description: str
    parameters: Dict[str, Any]  # JSON Schema

@dataclass
class ToolCall:
    id: str
    name: str
    arguments: Dict[str, Any]

@dataclass
class LLMToolResponse:
    text: Optional[str]
    tool_calls: List[ToolCall]
    stop_reason: str
    input_tokens: int
    output_tokens: int
```

### New ABC Methods

```python
class LLMProvider(ABC):
    def supports_tool_use(self) -> bool:
        """Returns False by default. Override in providers that support tool use."""
        return False

    def tool_use_completion(
        self, messages, tools, system=None, model=None, **kwargs
    ) -> LLMToolResponse:
        """Raises NotImplementedError by default."""
        raise NotImplementedError(...)
```

### Implementation on AnthropicProvider

Full implementation using raw `requests` (matching existing pattern). Includes retry logic via shared `utils/http_retry.py`.

---

## 4. Tool Definitions

Intentionally minimal — covers 95% of what Claude Code actually does.

| Tool | Purpose |
|------|---------|
| `read_file` | Read file contents (optional line range) |
| `write_file` | Create or overwrite files |
| `patch_file` | Surgical string replacement (must be unique) |
| `list_directory` | Directory listing with depth and ignore patterns |
| `run_command` | Shell command execution (timeout, captured output) |
| `git_status` | Show working tree status |
| `git_diff` | Show staged or unstaged changes |
| `git_commit` | Stage all and commit |

---

## 5. Safety Architecture

| Layer | Mechanism |
|---|---|
| **Path sandboxing** | `PathSandbox` validates all paths; writes restricted to `working_dir` |
| **Read-only expansion** | `--allow-read` grants read access to specific external paths |
| **Git checkpoint** | Auto-stash uncommitted work before session starts |
| **Commit gates** | All `git_commit` calls require user confirmation |
| **Destructive command gates** | `rm -rf`, `DROP TABLE`, etc. require explicit `y` |
| **Iteration limit** | Configurable via `--max-iterations` (default 25) |
| **Iteration warning** | Prompts at 80% of limit: "Continue? [Y/n]" |
| **Command timeout** | Shell commands timeout at 30s (max 120s) |
| **`/undo` command** | Soft-reset last git commit from CLI |

---

## 6. Files Created/Modified

| File | Change |
|------|--------|
| `api/utils/http_retry.py` | **NEW** — Shared HTTP retry utility (~80 lines) |
| `api/services/llm_service.py` | Add dataclasses (~40 lines), ABC methods (~25 lines), Anthropic impl (~100 lines), AGENT_PROVIDER_MAP entry |
| `api/services/agents/code_tools.py` | **NEW** — Tool definitions, PathSandbox, implementations (~300 lines) |
| `api/services/agents/code_agent.py` | **NEW** — Tool-use conversation loop (~200 lines) |
| `tools/tamor_code.py` | **NEW** — CLI entry point (~250 lines) |

**Total new code:** ~1000 lines
**Changes to existing code:** ~170 lines added, 0 modified

---

## 7. Implementation Phases

| Phase | Description | Est. Sessions |
|-------|-------------|---------------|
| A | LLM service extension | 1 |
| B | Tools (code_tools.py, PathSandbox) | 1 |
| C | Agent loop (code_agent.py) | 1 |
| D | CLI (tamor_code.py) | 1 |
| D.5 | Streaming output | 1 |
| E | Polish | Ongoing |

---

## 8. Cost Estimates

| Step | ~Tokens |
|---|---|
| System prompt | ~500 |
| Read 2-3 files | ~3,000 |
| Edit + verify | ~2,000 |
| Run tests + fix | ~2,000 |
| **Typical task total** | **~7,500** |

At Claude Sonnet 4.5 rates (~$3/M input, $15/M output), a typical task costs roughly **$0.05-0.15**.

---

## 9. What This Gets You vs Claude Code

| Capability | Claude Code | Tamor Code |
|---|---|---|
| Read/write files | ✅ | ✅ |
| Run shell commands | ✅ | ✅ |
| Git integration | ✅ | ✅ |
| Surgical edits (patch) | ✅ | ✅ |
| Multi-step iteration | ✅ | ✅ |
| Confirmation gates | ✅ | ✅ |
| Read outside project | ✅ | ✅ `--allow-read` |
| Configurable limits | ❌ | ✅ `--max-iterations` |
| Streaming output | ✅ | ⬜ Phase D.5 |
| Provider-agnostic | ❌ | ✅ |
| Your infrastructure | ❌ | ✅ |

---

## 10. Future Extensions

- **Web UI integration** — WebSocket/SSE support for browser-based coding
- **Project context injection** — Auto-read README, git log at session start
- **Planner integration** — Planner decomposes features, hands to CodeAgent
- **Session persistence** — Save/restore conversation state across sessions
- **Local model fallback** — Route simple ops to Ollama to save API costs

---

*Decision reached 2026-02-04 through collaborative design review.*
