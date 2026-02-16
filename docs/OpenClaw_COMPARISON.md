# Reeve vs. OpenClaw: Architectural Comparison & Strategic Decision

**Status:** Open Question | **Last Updated:** 2026-02-15

> **Fact-Check Note:** This document was originally written 2026-01-29. It has been substantially revised based on a [detailed codebase fact-check](https://github.com/reubenjohn/reeve-bot/blob/master/docs/OpenClaw_COMPARISON.md) (OpenClaw commit `0cf93b8fa`, 2026-02-09) that found several original claims to be inaccurate. Corrections are noted inline. The overall framing has shifted from "opaque vs. transparent" to a more honest comparison of architectural philosophies.

## Executive Summary

[OpenClaw](https://github.com/openclaw/openclaw) is the dominant open-source personal AI assistant (174k+ GitHub stars, 455+ contributors). This document provides a technical comparison between OpenClaw and Reeve, and frames the strategic question:

**Should Reeve be abandoned, merged with OpenClaw, compete directly, or coexist as a complementary approach?**

Both systems share more architectural DNA than originally understood — plain Markdown memory, configurable session isolation, scheduled proactivity. The genuine differences lie in **session philosophy** (continuity vs. isolation as default), **conversation-level meta-skills** (retrospection, self-testing, self-improvement), and the **Desk as an opinionated thinking framework** vs. a general-purpose workspace.

---

## The Fundamental Difference: Runtime vs. Orchestrator

### OpenClaw: The All-in-One Runtime

**Architecture:** OpenClaw is a **custom agent runtime** built in TypeScript/Node.js. It directly implements the agent loop — the core "Thought → Tool → Observation" cycle that powers agentic AI.

**Philosophy:** Integration over modularity. OpenClaw is a complete system where the agent loop, memory management, tool execution, and communication protocols are tightly coupled in a single codebase.

**Key Components:**
- Custom WebSocket "Gateway" serving as the central nervous system
- Native tool/skill execution engine
- Plain Markdown memory (`MEMORY.md`, `memory/YYYY-MM-DD.md`) with hybrid search (BM25 + vector embeddings)
- Multiple session types with configurable isolation (`dmScope`: `main`, `per-peer`, `per-channel-peer`)
- Multi-platform integrations (Telegram, Discord, WhatsApp, iMessage — 7+ channels)
- 5 proactive mechanisms: Heartbeat, Cron, Hooks, Webhooks, Agent-to-Agent
- ClawHub marketplace (31,000+ skills) + 52+ bundled skills
- OpenProse declarative workflow engine for `.prose` programs
- Web dashboard and Terminal UI (TUI)

**Strengths:**
- Batteries-included experience with massive ecosystem
- 174k+ stars, active community, rapid development
- Unified architecture where everything "just works"
- Real-time streaming of tool outputs via WebSockets
- Multiple scheduling mechanisms with fine-grained control
- OpenProse enables code-level self-improvement for `.prose` workflows

**Trade-offs:**
- High coupling to the custom implementation
- Breaking changes during rapid development phase
- Must maintain compatibility with evolving LLM APIs
- Context management within sessions relies on compaction/summarization

### Reeve: The Specialized Orchestrator

**Architecture:** Reeve is a **supervisor process** that orchestrates specialized agentic IDEs (Claude Code, GitHub Copilot, Goose, Cursor) rather than reimplementing the agent loop.

**Philosophy:** Specialization over integration. Bet on billion-dollar companies (Anthropic, GitHub, Microsoft) to build the best agent loops, focus on what they're NOT building — proactive scheduling, context management, and conversation-level self-improvement.

**Key Components:**
- **Pulse Queue** (Python/SQLite): Core scheduling system for wake-up events
- **Executor**: Launches fresh agent sessions with explicit context injection
- **Desk**: An opinionated thinking framework ([reeve_desk](https://github.com/reubenjohn/reeve-desk)) with structured folders for Goals, Responsibilities, Preferences, and Diary — each with distinct update cadences
- **Session Hygiene**: Treats each wake-up as a new, isolated session by default
- **Meta-Skills**: Conversation-level retrospection (nightly pattern analysis), self-testing (git worktree fork-test-merge), and source code self-awareness
- MCP servers for self-scheduling and notifications
- HTTP API for external event triggers
- Lightweight integrations (Telegram listener)

**Strengths:**
- **Decoupling from implementation churn**: Anthropic/GitHub teams optimize the agent loop while Reeve focuses on orchestration
- **Session isolation by default**: Fresh context per task prevents hallucination accumulation
- **Conversation-level self-improvement**: Nightly retrospection analyzes conversations for patterns, mistakes, and behavioral updates — a feedback loop not present in OpenClaw
- **Self-testing with rollback**: Behavior changes validated via git worktree isolation before being merged
- **Opinionated personalization**: Desk framework bootstraps a highly personalized assistant out of the box
- **Research-backed design**: Informed by [agentic IDE analysis](https://github.com/reubenjohn/agentic-ide-power-user)
- **Model flexibility**: Desk can be optimized per-model (Claude, GPT-4, Gemini) without touching orchestration logic

**Trade-offs:**
- Depends on external CLIs remaining stable and accessible
- No plugin ecosystem or marketplace (starting from zero)
- Higher per-wake-up latency (process spawning overhead)
- Solo developer vs. large community (for now)
- Risk of context loss if information not captured in Desk between sessions

---

## Technical Deep Dive

### 1. The "Gateway" vs. The "Pulse Queue"

#### OpenClaw's Gateway
A local WebSocket server (port 18789) that serves as the event hub:
- Different adapters (Telegram, Discord, CLI) connect as WebSocket clients
- Agent awakened by scheduled heartbeats (~30min default) and cron jobs
- **Proactivity via integrated subsystems:** Cron (precise scheduling with 5-field expressions) + Heartbeat (periodic awareness) + Hooks + Webhooks + Agent-to-Agent
- Multiple session types: main, per-peer, per-channel-peer, isolated cron sessions
- Context is continuous within a session, managed by compaction + daily resets

**Code Evidence:** `src/gateway/server-cron.ts`, `src/cron/service.ts`, `src/infra/heartbeat-wake.ts`

**Use Case:** You send a Telegram message. The adapter emits a WebSocket event, the agent immediately "hears" it and responds. Efficient and real-time. For proactive tasks, the cron timer polls for due jobs and can spawn isolated sessions (`sessionKey: "cron:<jobId>"`).

#### Reeve's Pulse Queue
A SQLite-backed scheduler with priority-based execution:
- Periodic pulses (hourly heartbeat) and aperiodic pulses (self-scheduled alarms)
- Each pulse spawns a fresh agent session with explicit context
- "Sticky Notes" carry forward essential context between sessions
- Failed pulses retry with exponential backoff

**Use Case:** At 6:45 AM, a pulse fires to check flight status. A new Claude Code session starts with the prompt "Check flight UA123 for delays" + sticky note "User departs at 8:00 AM". Session completes, process exits. Clean slate for next pulse.

### 2. Memory & Learning Architecture

**Both systems use plain Markdown files for persistent memory.** The difference is in session integration, structure, and what the memory is *designed for*.

#### OpenClaw
- **Plain Markdown** memory: `MEMORY.md` (curated long-term), `memory/YYYY-MM-DD.md` (daily logs)
- **Hybrid search**: BM25 (FTS5) + vector similarity with weighted scoring for retrieval
- Agent maintains continuous context within session, reading/writing files during long-running session
- Pre-compaction flush: Summarizes before context window fills, extracting key info to durable files
- Session resets: `/new` command, daily reset (default 4:00 AM), idle expiry
- **Agent-centric workspace bootstrap**: `AGENTS.md`, `SOUL.md`, `USER.md`, `IDENTITY.md`, `TOOLS.md` — defining what the agent *is*
- Git repo auto-initialized for workspace, but no automatic commits

**Strength:** Continuous learning within sessions, sophisticated retrieval (hybrid search), immediate context accumulation
**Design Challenge:** Context drift within long sessions (mitigated via compaction), compaction can lose nuanced details

#### Reeve (with [reeve_desk](https://github.com/reubenjohn/reeve-desk))
- Separate Git repository holding user context ([example](https://github.com/reubenjohn/reeve-desk))
- Agent reads files **at session start**, writes updates **before session exit**
- **User-centric structured folders** with distinct update cadences:
  - `Goals/`: Long-term objectives with success criteria (updated weekly/monthly)
  - `Responsibilities/`: Recurring duties with cadences — daily, weekly, monthly (updated as duties change)
  - `Preferences/`: User constraints and communication rules (updated when preferences evolve)
  - `Diary/`: Activity logs, pattern tracking, temporal context (updated every session)
  - `Diary/Patterns/`: Emergent patterns, created when data appears 3+ days in a row
  - `.claude/skills/`: 14 specialized skills including 3 meta-skills (retrospection, self-testing, session analysis)
- **Template model**: Public template ([reeve_desk_template](https://github.com/reubenjohn/reeve-desk-template)) that users fork and personalize. ~60% template structure, ~40% organic growth.
- **Context engineering as first-class skill**: Decision tree and size guidelines for what goes where. "You are ephemeral. The Desk is eternal."
- **Self-organization discipline**: Mandatory checklist per pulse (context capture, desk hygiene, anticipation, learning)
- **Automatic git commits with diff notifications**: Every Desk modification is committed and the user is texted a link to the diff

**Strength:** Git-versioned knowledge evolution, session isolation prevents hallucination bleed, cost efficiency (only loads needed context per session), opinionated structure bootstraps personalization out of the box

**Design Challenge:** Process spawning overhead (mitigated via priority-based scheduling), risk of context loss if information not captured in Desk between sessions (user may need to repeat information), requires discipline in maintaining Desk files

#### What's Equivalent, What's Different

| Dimension | OpenClaw | Reeve |
|-----------|----------|-------|
| **Storage format** | Plain Markdown | Plain Markdown |
| **Inspectability** | Fully transparent | Fully transparent |
| **Git support** | Auto-initialized, manual commits | Auto-commits + diff notifications |
| **Bootstrap philosophy** | Agent-centric ("what is the agent?") | User-centric ("what does the user need?") |
| **Structure** | General-purpose workspace | Opinionated thinking framework |
| **Template/sharing** | Portable workspaces | Fork-and-personalize template model |
| **Retrieval** | Hybrid search (BM25 + vector) | File-based progressive disclosure |

### 3. The Cost/Context Trade-Off

The session model choice has direct implications on operational costs and user experience:

#### OpenClaw's Continuous Context Approach
**Advantages:**
- **No repetition needed**: Context accumulates naturally within session
- **Low latency**: No process spawning overhead per interaction
- **Implicit learning**: Agent picks up patterns without explicit memory writes

**Costs:**
- **Higher token usage**: Full context sent with each API call
- **Context window pressure**: Requires pre-compaction flush mechanisms
- **Compaction risks**: Summarization can lose nuanced details

**Example:** After discussing project preferences once, agent remembers them for the entire session (hours/days). But session accumulates 50k+ tokens, requiring periodic summarization.

#### Reeve's Session Isolation Approach
**Advantages:**
- **Cost efficiency**: Only loads relevant Desk files per pulse (~2-5k tokens)
- **No context drift**: Each session starts clean
- **Explicit knowledge**: All learning visible in git diffs

**Costs:**
- **Context loss risk**: If information not captured in Desk, user must repeat
- **Process overhead**: Fresh Hapi session spawn per pulse (~1-3s latency)
- **Manual curation**: Requires discipline in updating Desk files

**Example:** Morning briefing pulse reads Goals.md + today's Responsibilities.md (~3k tokens). If user mentioned preference yesterday but it wasn't written to Preferences.md, they'll need to repeat it.

**The Fundamental Trade-Off:**
- **OpenClaw**: Pays in tokens/compaction for seamless continuity
- **Reeve**: Pays in latency/discipline for cost efficiency and session hygiene

> **Note:** OpenClaw also supports isolated sessions (cron with `session: isolated`, `/new` command, daily resets). The difference is *default philosophy*: OpenClaw defaults to session continuity; Reeve defaults to session isolation.

### 4. Conversation-Level Meta-Skills

This is the core differentiator confirmed by codebase fact-checking. OpenClaw's OpenProse provides sophisticated self-improvement for `.prose` program execution — but NOT for agent-user conversations. These are different domains.

#### Reeve's Meta-Skill Feedback Loop

1. **Daily Retrospection** — Every night, Reeve analyzes its diary entries (conversations, decisions, user feedback) looking for *patterns*, not just summaries. It identifies recurring mistakes, missed opportunities, and behavioral adjustments. Updates its own behavior accordingly.

2. **Self-Testing** — When Reeve modifies its own behavior (e.g., updating CLAUDE.md or skill definitions), it forks an isolated copy of the Desk via git worktree, runs simulated scenarios against the modified behavior, and compares results. If any test fails, it rolls back and re-iterates. Only validated changes are merged.

3. **Source Code Self-Awareness** — Reeve reads its own source code, skill definitions, and configuration. 443 lines of CLAUDE.md defining identity, architecture, limitations, decision-making frameworks, and runtime behavior. It knows its own retry policies, context window limits, and scheduling implementation.

#### What OpenClaw Has Instead

- **OpenProse retrospection** (`49-prose-run-retrospective.prose`): Analyzes `.prose` program execution traces — different domain than conversations
- **OpenProse simulation** (`39-architect-by-simulation.prose`): Tests `.prose` program specifications — not conversation behavior
- **OpenProse inspection** (`lib/inspector.prose`): Inspects `.prose` code quality — not agent personality
- **Session transcripts** stored as JSONL — available for analysis, but no automatic nightly processing
- **`session-memory` hook** saves summaries when user types `/new` — but no pattern extraction
- Agents can read configuration files (AGENTS.md, SOUL.md) at bootstrap and have the `read` tool for any file — but are NOT explicitly guided to read their own source code

#### Why This Matters

This is the meta-skill feedback loop: the agent improves its own *conversation behavior* over time. OpenClaw improves its *code workflows* (via OpenProse); Reeve improves its *human interaction*. These are complementary capabilities, not competing ones.

**Implementation gap assessment**: ~3 weeks of work for OpenClaw to achieve parity on conversation-level meta-skills (retrospection analyzer: 3-4 days, scheduled cron integration: 2-3 days, workspace editor with git safety: 3-4 days, test harness: 3-4 days).

### 5. The "Wrapper" Bet

**OpenClaw's Approach:** "We are the runtime. We'll stay competitive with LLM providers."
- Requires ongoing maintenance as APIs evolve
- Community-driven improvements to tool execution
- Full control over agent behavior

**Reeve's Approach:** "Let the billion-dollar companies fight over agent loop optimization. We'll orchestrate."
- Delegates complex reasoning to an agentic IDE (Claude Code, Goose, Cursor, etc.)
- Assumes the underlying CLI will remain competitive and accessible
- Risk: If the chosen CLI is deprecated or restricted, Reeve needs a new engine

> **Terms of Service Note:** Programmatically invoking Claude Code or VS Code's agentic features may raise ToS concerns. Reeve is engine-agnostic — open-source alternatives like [**Goose**](https://github.com/block/goose) (Apache 2.0, by Block) or **Aider** work as drop-in replacements with no restrictions. Just set `HAPI_COMMAND=goose` to swap engines.

### 6. Extensibility & Integration

#### OpenClaw
- **WebSocket Gateway architecture:** Plugins connect to central hub
- **ClawHub marketplace:** 31,000+ community skills
- **52+ bundled skills** covering common workflows
- **7 plugin types**: Channel, Provider, Tool, Service, Skill, Hook, CLI
- **MCP access via mcporter skill** (not native, but functional)
- **Integration model:** Tight coupling with runtime, real-time streaming, in-process TypeScript execution

**Strength:** Massive ecosystem, batteries-included, community contributions
**Challenge:** Plugins must adapt to runtime API changes during rapid development

#### Reeve
- **Three-layer extension model:**
  1. **MCP Servers** - Direct tool integration (pulse scheduling, notifications, calendar, etc.)
  2. **HTTP REST API** - External event triggers (any system can POST to `/api/pulse/schedule`)
  3. **Integration Listeners** - Modular connectors (Telegram, email, etc.) as separate processes
- **Native MCP support**: Accesses ~7,000+ MCP tool implementations on GitHub (same ecosystem OpenClaw accesses via mcporter)
- **Protocol-based:** Standard HTTP, MCP, asyncio patterns
- **Process isolation:** Listener crashes don't affect daemon

**Strength:** Modular, no vendor lock-in, standard protocols, native MCP integration
**Challenge:** No marketplace, no community plugins (ecosystem starting from scratch)

> **Note:** Both systems access the same MCP ecosystem (~7,000+ tools on GitHub). OpenClaw additionally has ClawHub (31,000+ skills). There is no "Reeve marketplace."

**Example Integration:**
```python
# Adding a Slack listener (independent process)
class SlackListener:
    async def start(self):
        while True:
            events = await self.slack_client.poll()
            for event in events:
                await self.api.schedule_pulse(
                    prompt=f"Slack message: {event.text}",
                    priority="high",
                    source="slack"
                )
```

---

## Verified Advantages

### Genuine Reeve Advantages (Confirmed by Fact-Check)

These differentiators were verified against the OpenClaw codebase and confirmed as genuine gaps:

| Advantage | Detail | OpenClaw Status |
|-----------|--------|----------------|
| **Git auto-commit + diff notifications** | Every Desk modification is committed; user texted a link to the diff | Git repo auto-initialized but no auto-commit or notification |
| **Conversation-level retrospection** | Nightly pattern analysis of conversations, mistakes, and behavioral updates | OpenProse analyzes `.prose` programs, not conversations |
| **Conversation-level self-testing** | Git worktree fork-test-merge for behavior changes | OpenProse tests `.prose` specs, not conversation behavior |
| **Source code self-awareness** | 443-line CLAUDE.md explicitly guides agent to read own source, architecture, and limitations | Agents can read files but are not guided to own source code |
| **Opinionated Desk framework** | User-centric structure (Goals/Responsibilities/Preferences/Diary) with template model, update cadences, and self-organization discipline | General-purpose workspace with agent-centric bootstrap files |

### Genuine OpenClaw Advantages (Acknowledged)

Honest recognition of where OpenClaw excels:

| Advantage | Detail | Reeve Status |
|-----------|--------|-------------|
| **ClawHub marketplace** | 31,000+ community skills | No marketplace |
| **Proactive mechanisms** | 5 types: Heartbeat, Cron, Hooks, Webhooks, Agent-to-Agent | 1 type: Pulse |
| **OpenProse** | Declarative workflow engine for code-level self-improvement of `.prose` programs | No equivalent |
| **Bundled skills** | 52+ bundled skills | 14 skills |
| **Plugin architecture** | 7 plugin types with in-process TypeScript execution | MCP servers (out-of-process) |
| **Community & momentum** | 174k+ stars, 455+ contributors, active development | Solo developer |
| **Multi-channel real-time** | 7+ channel adapters with real-time WebSocket streaming | Telegram listener only |

---

## Safety via Session Isolation

### Session Hygiene

Both systems support session isolation, but with different defaults:
- **OpenClaw** defaults to session continuity (with compaction, daily resets, and `/new` for fresh starts)
- **Reeve** defaults to session isolation (each pulse starts clean, Desk carries forward state)

The practical impact of isolation-by-default:

**Doom Loop Prevention:** Continuous-context agents can get stuck in "doom loops" — repeating the same bad error because the failed attempt pollutes the context. Reeve's session isolation means each wake-up starts clean. A bad pulse dies; the next pulse doesn't inherit its mistakes.

**Drift Detection:** By forcing the agent to reconcile actions against a static `Responsibilities.md` every cycle, Reeve acts as a self-correcting system — reducing the hallucination drift seen in ungrounded agents.

**Hot-Swapping the Brain:** Agent stuck in a loop? Don't kill the process. Open `Diary/current_task.md`, delete the bad logic, save. Next pulse reads the corrected state and proceeds.

### Git as "Undo Button"

The Desk is a **Git repository** with automatic commits. This provides transaction rollback for agentic mistakes:

- Agent deletes something important? `git checkout` to restore it.
- Agent rewrites your Goals incorrectly? `git diff` shows exactly what changed, `git revert` to undo.
- Want to audit what the agent did last week? Full history available.
- Every modification triggers a diff notification to the user — you always know what changed and why.

> **Note:** OpenClaw also auto-initializes a git repo for its workspace, but does not automatically commit changes or notify the user. Users must manually run `git add` and `git commit`. This is a genuine gap — approximately 1-2 days of implementation effort.

---

## Research Foundation

Reeve's architecture is informed by systematic research documented in [agentic-ide-power-user](https://github.com/reubenjohn/agentic-ide-power-user), which analyzes context engineering, grounding, and human-machine interaction patterns across major agentic IDEs (Claude Code, Cursor, GitHub Copilot).

### Key Research Findings Applied to Reeve

1. **Context Rot Prevention:** Performance degrades at 100k+ tokens ([Burke Holland SNR Equation](https://github.com/reubenjohn/agentic-ide-power-user#context-rot), [Liu et al., TACL 2024](https://arxiv.org/abs/2307.03172) — 10-25pp accuracy drop for mid-context info)
   - **Both systems address this:** OpenClaw via compaction/memory flush; Reeve via fresh sessions per pulse

2. **Session Hygiene Best Practice:** Research-Plan-Implement loop with context resets
   - **Reeve's Solution:** Each pulse = one phase, results written to Desk, next pulse reads artifacts

3. **Progressive Disclosure:** Hierarchical information density prevents tool/instruction bloat
   - **Both systems implement this:** OpenClaw via skill listing + on-demand SKILL.md reads; Reeve via Desk structure (CLAUDE.md → Goals/ → Skills/)

4. **MCP Tool Overhead:** Each tool description costs 100-200 tokens, unconditionally injected
   - **Reeve's Solution:** Minimal MCP surface (4 pulse tools + notification), Skills for workflows

5. **Grounding Mechanisms:** Deterministic validation (tests, linters, hooks) prevents hallucinations
   - **Reeve's Solution:** Executor can invoke arbitrary validation, Desk git history provides auditability

See [research summary](https://github.com/reubenjohn/agentic-ide-power-user) for full analysis.

---

## Code-Based Validation

Claims in this document have been validated against the OpenClaw codebase in two rounds:
- **Initial review:** Commit `4583f8862` (2026-01-29)
- **Fact-check update:** Commit `0cf93b8fa` (2026-02-09) — full report in `openclaw/findings/FINAL_REPORT.md`

### Validated Claims (Held Up)

| Claim | Evidence |
|-------|----------|
| **Custom agent runtime** | `src/agents/pi-embedded-runner/run.ts` (470+ lines) — hand-written loop with retry logic, profile failover |
| **WebSocket Gateway hub** | `src/gateway/server.impl.ts`, `ws-connection.ts` — 100+ RPC methods, broadcast coordination |
| **Markdown + hybrid storage** | `src/memory/internal.ts`, `memory-schema.ts` — `.md` files indexed in SQLite with FTS5 + vector embeddings |
| **Pre-compaction memory flush** | `src/auto-reply/reply/memory-flush.ts` — triggers at (contextWindow - reserve - 4000) tokens |
| **Plugin ecosystem** | `src/plugins/registry.ts`, `channels/plugins/` — comprehensive adapter system, 7+ built-in channels |
| **Proactivity: Cron + Heartbeat** | `src/cron/service.ts`, `src/infra/heartbeat-wake.ts` — core subsystems (NOT plugins) |
| **Runtime vs. Orchestrator framing** | Architectural fact: OpenClaw implements agent loop; Reeve delegates to external CLIs |

### Corrected Claims (From Fact-Check)

| Original Claim | Correction | Evidence |
|----------------|------------|----------|
| "One long-running conversation" | OpenClaw has **multiple separate sessions** configurable via `dmScope` (`main`, `per-peer`, `per-channel-peer`). Cron jobs can run in isolated sessions. | `src/routing/session-key.ts`, `docs/concepts/session.md` |
| "Hidden/opaque memory" | OpenClaw memory is **plain Markdown** (`MEMORY.md`, `memory/YYYY-MM-DD.md`), fully inspectable | `docs/concepts/memory.md` lines 9-27 |
| "Unbounded context accumulation" | OpenClaw has **auto-compaction**, daily session resets, idle expiry, and `/new` for fresh starts | `docs/reference/session-management-compaction.md` lines 89-92 |
| "Isolated sessions unique to Reeve" | OpenClaw supports isolated sessions via cron (`session: isolated`), `sessions_spawn` tool, and session scoping | `src/agents/tools/cron-tool.ts` |
| "Desk pattern unique to Reeve" | OpenClaw workspace (`~/.openclaw/workspace`) is **storage-equivalent** (both plain Markdown). The distinction is in structure and philosophy, not transparency. | `src/agents/workspace.ts`, `docs/concepts/agent-workspace.md` |
| "Pulses unique to Reeve" | OpenClaw has **5 scheduling mechanisms**: Heartbeat, Cron, Hooks, Webhooks, Agent-to-Agent | `src/cron/service.ts`, `src/infra/heartbeat-wake.ts` |
| "Summarization is a workaround" | Compaction and memory flush are **first-class architectural components**, not bolted-on fixes | `agents.defaults.compaction.*` configuration, integrated into session lifecycle |

### Confirmed Reeve Advantages (New Findings)

| Advantage | Verification |
|-----------|-------------|
| **Conversation-level retrospection** | OpenProse's `49-prose-run-retrospective.prose` analyzes `.prose` programs, NOT conversations. No conversation analysis exists. |
| **Conversation-level self-testing** | OpenProse's `39-architect-by-simulation.prose` tests `.prose` specs, NOT conversation behavior. No conversation testing exists. |
| **Git auto-commit + notifications** | `src/infra/git-commit.ts` only reads HEAD hash for version info. No auto-commit or notification pipeline. |
| **Source code self-awareness** | Agents can read files via `read` tool but are not explicitly guided to own source. `src/agents/system-prompt.ts` does not reference source code location. |

### Key Implementation Details

**Proactivity Architecture** (from code analysis):
- **Cron Service**: Timer-based polling (`setTimeout`) with priority-ordered job execution
- **Heartbeat**: Coalescing event handler with 30min default cycle
- **System Events**: In-memory queue (`src/infra/system-events.ts`) injected at agent turn start
- **Isolated Jobs**: Cron can spawn fresh sessions (`sessionKey: "cron:<jobId>"`)

**Memory Retrieval** (from code analysis):
- **Hybrid search**: BM25 (FTS5) + vector similarity with weighted scoring
- **Daily logs**: `memory/YYYY-MM-DD.md` (append-only, read today + yesterday)
- **Curated memory**: `MEMORY.md` (optional, main session only)
- **Chunk indexing**: 400-token chunks with 80-token overlap, embedding cache per provider

**Plugin Architecture** (from code analysis):
- **7 plugin types**: Channel, Provider, Tool, Service, Skill, Hook, CLI
- **Adapter pattern**: 25+ optional adapters per channel plugin
- **Discovery order**: Config → Workspace → Global → Bundled
- **Examples**: Mattermost (250 lines), Voice Call (400+ lines), Telegram, Discord, Slack, WhatsApp, Signal

---

## The Strategic Question: Abandon, Merge, Compete, or Coexist?

### Option A: Abandon Reeve
**Rationale:** OpenClaw has momentum, community, and plugins. Why reinvent the wheel?

**Counter-argument:**
- Reeve's conversation-level meta-skills (retrospection, self-testing) address real gaps in OpenClaw
- The opinionated Desk framework offers a distinct personalization philosophy
- The orchestrator pattern may prove more robust long-term

**Verdict:** Premature. Reeve contributes ideas that don't yet exist in OpenClaw.

---

### Option B: Merge/Contribute to OpenClaw
**Rationale:** Join forces. Port Reeve's concepts as OpenClaw extensions.

**Feasibility:** Medium (improved from original "Low" assessment)
- Tech stack incompatibility (Python vs. TypeScript) — but concepts are portable
- Conversation retrospection and self-testing could be implemented as OpenClaw skills/hooks
- Desk structure ideas could inform workspace improvements

**What could be contributed:**
- Conversation-level retrospection as a scheduled cron job (~1-2 weeks)
- Git auto-commit hook for workspace changes (~1-2 days)
- Self-testing framework for behavior changes (~1-2 weeks)
- Desk structure patterns for memory organization

**Verdict:** Concepts can be shared. The fact-check estimated ~3 weeks for OpenClaw to achieve parity on conversation meta-skills.

---

### Option C: Compete Head-to-Head
**Rationale:** Build a rival ecosystem. Aim for OpenClaw's breadth of plugins.

**Feasibility:** Low
- OpenClaw's 174k stars and 455+ contributors are a massive advantage
- ClawHub's 31,000+ skills vs. zero Reeve marketplace
- Competing on "number of integrations" is a resource war Reeve cannot win

**Winning Strategy (if competing):**
- Don't compete on breadth (number of tools)
- Compete on depth (meta-skills, self-improvement, personalization)
- Position as "Jarvis" (task executive) vs. OpenClaw's "Her" (conversational OS)

**Verdict:** Not viable as a head-to-head competition. Differentiation is the only path.

---

### Option D: Coexist as Complementary Systems
**Rationale:** Reeve and OpenClaw target different use cases, with genuinely different architectural strengths.

| Dimension | OpenClaw | Reeve |
|-----------|---------|-------|
| **Use Case** | Conversational buddy, general assistant | Proactive task executive, "Chief of Staff" |
| **Architecture** | All-in-one runtime | Modular orchestrator |
| **Session Default** | Continuity (with isolation options) | Isolation (with context carry-forward) |
| **Memory** | Plain Markdown + hybrid search | Plain Markdown + opinionated structure |
| **Meta-Skills** | OpenProse (code/workflow improvement) | Conversation-level (retrospection, self-testing) |
| **Ecosystem** | ClawHub (31k+ skills), 174k+ stars | No marketplace, solo developer |
| **Key Strength** | Ecosystem, real-time interaction, OpenProse | Session hygiene, Desk framework, conversation self-improvement |

**Coexistence Scenarios:**
1. **Independent Evolution:** Different tools for different needs
2. **Concept Sharing:** Reeve's meta-skill patterns adopted as OpenClaw extensions
3. **Potential Integration:** Reeve's Pulse Queue could *trigger* OpenClaw sessions via API

**Verdict:** This is the strongest path forward. The fact-check confirms the systems have different genuine strengths. The gap is meaningful but not insurmountable (~3 weeks of implementation). Both architectural philosophies can thrive.

---

## What the Research Says

Recent industry discussions (January 2026) highlight the architectural debates around agentic AI:

- ["The Agentic Architect"](https://medium.com/the-cyber-wall/the-agentic-architect-software-in-2026-is-no-longer-written-its-negotiated-f4f9d1b993eb) - Software is negotiated with agents, not written
- ["Keep it simple, stupid: Agentic AI tools choke on complexity"](https://www.theregister.com/2026/01/26/agentic_ai_tools_complecity) - Complexity is the enemy
- ["Agentic AI Isn't a Feature. It's a Re-Platforming"](https://hackernoon.com/agentic-ai-isnt-a-feature-its-a-replatforming-and-it-will-decide-who-sets-the-tone-in-2026) - Fundamental shift in how we build systems

**Key Takeaway:** The space is too new for there to be a "one true architecture." Multiple approaches are needed to explore the design space.

---

## Community Feedback Needed

This is an open question. Before investing further, the project seeks input:

### Questions for the Community

1. **Do conversation-level meta-skills (retrospection, self-testing) matter enough to justify a separate project?**
   - Or could these be contributed as OpenClaw extensions?

2. **Is the "wrapper" bet (orchestrating Claude Code) smart or risky?**
   - Does delegating the agent loop to Anthropic reduce maintenance burden?
   - Or does it create unacceptable dependency risk?

3. **Is there room for a "Proactive First" assistant distinct from conversational bots?**
   - Do users want scheduled, reliable task execution (Reeve's focus)?
   - Or is real-time chat interaction (OpenClaw's strength) sufficient?

4. **Does the opinionated Desk framework (Goals/Responsibilities/Diary) add value over a general-purpose workspace?**
   - Does the structured thinking framework bootstrap better personalization?
   - Or is flexibility (OpenClaw's approach) more important than opinionation?

### How to Provide Feedback

- **GitHub Issues:** [reeve-bot/issues](https://github.com/reubenjohn/reeve-bot/issues)
- **Discussions:** [reeve-bot/discussions](https://github.com/reubenjohn/reeve-bot/discussions)
- **Twitter/X:** [@reubenjohn](https://twitter.com/reubenjohn)
- **LinkedIn:** [Reuben John](https://www.linkedin.com/in/reubenjohn/)

---

## Relevant Resources

- **OpenClaw Project:** [github.com/openclaw/openclaw](https://github.com/openclaw/openclaw) (174k+ stars)
- **Reeve Desk:** [github.com/reubenjohn/reeve-desk](https://github.com/reubenjohn/reeve-desk)
- **Desk Template:** [github.com/reubenjohn/reeve-desk-template](https://github.com/reubenjohn/reeve-desk-template)
- **Agentic IDE Research:** [github.com/reubenjohn/agentic-ide-power-user](https://github.com/reubenjohn/agentic-ide-power-user)
- **Fact-Check Report:** `openclaw/findings/FINAL_REPORT.md` (codebase verification of all OpenClaw claims)
- **OpenClaw Setup Tutorial:** [YouTube - Your Own 24/7 AI Assistant](https://www.youtube.com/watch?v=VIDEO_ID)
- **TechCrunch Coverage:** [Everything you need to know about OpenClaw](https://techcrunch.com/2026/01/27/everything-you-need-to-know-about-viral-personal-ai-assistant-openclaw-now-OpenClaw/)

---

## Conclusion: Complementary, Not Competitive

As of February 2026, the fact-check has **clarified the picture**. The original framing — "opaque vs. transparent," "one conversation vs. isolated sessions" — was a false dichotomy. Both systems use transparent Markdown memory. Both support session isolation. Both have proactive scheduling.

**Where Reeve genuinely differentiates:**
1. **Conversation-level meta-skills** — retrospection, self-testing, self-improvement for human interaction (not code workflows)
2. **Opinionated Desk framework** — user-centric personalization with template model, update cadences, and self-organization discipline
3. **Git transparency** — automatic commits with diff notifications
4. **Orchestrator architecture** — delegates agent loop to specialized tools, bets on decoupling

**Where OpenClaw genuinely excels:**
1. **Ecosystem scale** — 174k+ stars, ClawHub (31k+ skills), 455+ contributors
2. **Proactive mechanisms** — 5 types vs. 1
3. **OpenProse** — declarative workflows and code-level self-improvement
4. **Batteries-included** — everything works out of the box

**The goal is not to "beat" OpenClaw, but to explore whether conversation-level meta-skills and the opinionated Desk framework solve real problems that general-purpose runtimes don't address.** If the answer is yes, these patterns can be shared. If no, we'll have learned something valuable.

If you have thoughts on this direction, please share them.
