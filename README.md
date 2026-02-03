# Project Reeve: The "Chief of Staff" Protocol

## I. The Core Philosophy (The "Why")

### 1. Beyond the Chatbot: The "Push" Paradigm

The fundamental flaw of modern AI assistants is their passivity. They wait for a prompt. They are tools that sit in a drawer until the user picks them up.

**Reeve is different.** Reeve is built on a **"Push" Paradigm**.

* **Proactivity First:** Reeve does not wait to be asked. It anticipates needs based on time, context, and history. It initiates the conversation.
* **The "Living" System:** Reeve runs on a continuous loop, a persistent entity that exists even when the user is away. It "thinks" while you sleep, organizing your digital life so you wake up to a prepared day.
* **Cognitive Offloading:** The ultimate goal is to reduce the user's "mental RAM" usage. If the user has to remember to ask the assistant to check something, the assistant has failed.

### 2. The Identity: Proxy & Gatekeeper

Reeve is not just a productivity tool; it is an active layer between the User and the World. It functions as a **High-Fidelity Proxy**.

* **The "Ear" (Input Filter):** The world is noisy. Reeve connects to high-volume channels (WhatsApp, Email, etc.) and filters the signal from the noise. It reads the group chat spam so you don't have to, surfacing only what requires your attention.
* **The "Mouth" (Output Delegate):** Reeve empowers the user to be in many places at once. It can draft replies, coordinate logistics with friends, or manage vendors, requiring only a simple "Approved" from the user to execute.
* **The "Gatekeeper":** Reeve protects the user's attention. It knows the difference between a "notification" (passive info) and an "interruption" (urgent action), ensuring the user is never distracted unnecessarily.

### 3. The Persona: The Adaptive Coach

Reeve acts as a **Productivity Coach and Task Manager**, but one that is deeply socially and emotionally aware.

* **Dynamic Scheduling:** Reeve understands that a calendar is not just a grid of slots. It observes the user's tasks completion rates and energy levels. If the user is falling behind, Reeve doesn't nag—it adapts. It might reschedule lower-priority tasks or suggest a break.
* **Emotional Intelligence:** Reeve picks up on cues. It knows when to push ("You promised you'd finish this today") and when to support ("You seem overwhelmed; let's push the research task to tomorrow").
* **The "Why" Over the "What":** Through its understanding of the user's long-term goals, Reeve connects daily drudgery to the bigger picture. It doesn't just remind you to "exercise"; it reminds you that you are "training for the snowboarding season."

### 4. Transparent Personalization: The "Glass Box" Principle

* **No Hidden Agendas:** Most AIs are "Black Boxes"—you have no idea *why* they think you want a salad. Reeve is a **"Glass Box."** Its entire understanding of you is visible in plain text folders on the Desk. It hides nothing.
* **The "Garden" You Can Tend (Or Ignore):** Just through all the conversation with Reeve, it proactively tends to this garden—organizing your **Goals**, tracking your **Responsibilities**, and refining your **Preferences** as it learns so you don't have to if you don't want to.
* **The "Steering Wheel" Guarantee:** You can let Reeve run on autopilot forever. But if you ever want to change course—tweak a goal, rewrite a personality trait, or adjust its communication style—you don't need to argue with a chatbot. You just open the file and edit it. It offers the ease of a chauffeur, but you never lose the steering wheel.

---

## II. The Landscape: Reeve vs. OpenClaw (The "Why This?")

**[OpenClaw](https://github.com/clawdbot/clawdbot)** (formerly Clawdbot, 30k+ stars) is an outstanding all-in-one runtime implementing the agent loop directly in TypeScript. It has a thriving plugin ecosystem and real-time interaction.

**Reeve exists** because I heard about OpenClaw a couple weeks late, but also represents a fundamentally different architectural bet:

| | OpenClaw | Reeve |
|---|---------|-------|
| **Paradigm** | Custom runtime | Orchestrator wrapping specialized CLIs ([Claude Code](https://claude.com/claude-code), [Goose](https://github.com/square/goose)) |
| **Session** | Continuous context | Isolated per wake-up ([research-backed](https://github.com/reubenjohn/agentic-ide-power-user#session-hygiene)) |
| **Memory** | Markdown files, in-session read/write during continuous execution | Git-versioned [Desk](https://github.com/reubenjohn/reeve_desk_template) (Goals/, Diary/, Preferences/), read-at-start/write-at-end |
| **Extensibility** | WebSocket Gateway + plugins | [MCP + HTTP API + Skills](docs/OpenClaw_COMPARISON.md#5-extensibility--integration), optional C.O.R.E. graph memory |
| **Trade-offs** | Higher token costs (full context), context drift risk | Context loss risk (if not captured in Desk), process overhead |
| **Best For** | Real-time OS integration, seamless continuity | Scheduled task isolation, cost efficiency, session hygiene |

**Reeve's Core Bet:** Let billion-dollar companies compete on agent loops. Focus on orchestration, proactive scheduling, and [context hygiene](https://github.com/reubenjohn/agentic-ide-power-user#context-rot).

**The Strategic Question:** Should Reeve be abandoned, merged, compete, or coexist? See **[docs/OpenClaw_COMPARISON.md](docs/OpenClaw_COMPARISON.md)** for detailed analysis and open invitation for feedback.

---

## III. Use Cases: Proxy, Coach, Gatekeeper in Action

### The Snowboarding Trip (Social Secretary)
**Context:** Reeve knows Goal: *"Snowboard 5+ times this season"* + user's friends ("Shred Crew").
**Trigger:** Weather agent detects 18" forecast at Mammoth.
**Action:** Sends Telegram alert: *"🔔 Powder Alert: 18 inches forecast for Mammoth this weekend. Shall I check if the Shred Crew is free?"*
**Outcome:** Upon approval, messages WhatsApp group, parses replies, summarizes headcount, offers to draft Airbnb booking. **Zero mental load.**

### The Deep Work Defender (Gatekeeper)
**Context:** Calendar filling with 30-min meetings, no coding time.
**Intervention:** Sunday pulse proactively blocks 9 AM–1 PM Monday as "Deep Work."
**Gatekeeper Logic:**
- 10:30 AM: Family group chat banter → 🔕 Silenced
- 11:00 AM: Wife texts *"Emergency, car won't start"* → 🚨 **Critical**, breaks Deep Work lock, pushes alert immediately

### The Adaptive Coach (Burnout Prevention)
**Pattern:** Missed "Daily Spanish" 3 days + curt message replies = burnout risk.
**Response:** *"🔔 You've been grinding hard. I've cleared non-essentials for tonight (moved Spanish and Budget Review to weekend). Why not order takeout and disconnect?"*
**Adaptation:** Shifts from Taskmaster → Supporter, prioritizing mental health over to-do list.

---

## IV. The Cognitive Mechanics (The "How It Thinks")

Reeve’s intelligence is not magic; it is a structured system of transparency, rhythm, and memory.

### 1. The Desk: A Collaborative Workspace (The Library)

At the center of Reeve's mind is **"The Desk"**—a local Git repository of Markdown files ([template](https://github.com/reubenjohn/reeve_desk_template), [example desk](https://github.com/reubenjohn/reeve-desk)). This is not just storage; it is a shared whiteboard between the User, Reeve, and its Sub-Agents.

* **The Folder Structure** (hierarchical context, [progressive disclosure](https://github.com/reubenjohn/agentic-ide-power-user#progressive-disclosure)):
* `Goals/`: The North Star. Contains `Goals.md` and other optional markdown files defining additional high-level objectives (e.g., `Financial_Freedom.md`, `Marathon_Training.md`).
* `Responsibilities/`: The Operational Manual. Recurring duties and active projects. Contains `Responsibilities.md` and optional supporting documents referenced from `Responsibilities.md` (e.g., `Daily_Hygiene.md`, `Project_Alpha_Specs.md`).
* `Preferences/`: The User Manual. Explicit constraints on communication style, diet, budget, and values. Contains `Preferences.md` and other optional supporting documents referenced from `Preferences.md`.
* `Diary/`: The Stream of Consciousness. Reeve logs its internal monologue here to maintain continuity between wake-up cycles. Reeve must find the best way to organize this and evolve the organization over time.
* `.claude/skills/`: Workflow automation (7+ specialized skills for morning briefing, pulse scheduling, diary logging, etc.)


* **The "Blackboard" Pattern:**
* When Reeve delegates a task (e.g., "Plan the Japan trip") to a sub-agent, it doesn't just pass a prompt. It creates a dedicated project folder on the Desk.
* Sub-agents read from and write to this folder, treating it as a shared blackboard. This allows complex, multi-day tasks to persist without clogging Reeve’s immediate context window.


### 2. The Pulse: A Rhythm of Existence

Reeve rejects the "Always On" model (which breeds distraction) and the "On Demand" model (which breeds passivity). Instead, it operates on a **Pulse**.

* **Periodic Pulse (The Heartbeat):**
* An hourly cron job wakes Reeve up. It checks the time, reviews the Desk, and asks: *"Does anything need to be done right now?"*


* **Aperiodic Pulse (The Alarm Clock):**
* Reeve can set its own alarms using the `schedule_aperiodic_pulse` tool. If it needs to check check for flight delays at exactly 6:45 AM sharp and notify the user that they can sleep in a little longer, it sets a wake-up call for that exact moment.


* **The Queue System (Noise Control):**
* **Pulse Queue:** High-urgency events (Alarms, 🚨 Critical Emails, messages from the user, wife, etc). These wake Reeve up *immediately*.
* **Activity Queue:** Low-urgency events (Newsletters, server logs). These sit silently. When Reeve next wakes up, it sees a "Ticker" (e.g., *"4 new items in Activity Queue"*) and decides whether to process them.


* **"Sticky Notes" (Self-Prompting):**
* Reeve can leave instructions for its future self. A sticky note like *"Check if the user replied to the snowboarding proposal"* is injected into the prompt of the next Pulse, ensuring follow-through without permanent storage.



### 3. Dual-Store Memory: The Conscious vs. Subconscious

Reeve manages the trade-off between "Context Window Limits" and "Total Recall" using a two-tiered system.

* **Tier 1: Working Context (The Desk):**
* *Type:* Explicit Markdown Files.
* *Role:* "System 2" Thinking. Slow, deliberate, and organized. This is what Reeve is "thinking about" right now. It is editable, transparent, and concise.


* **Tier 2: The Archive (C.O.R.E.):**
* *Type:* Graph-based persistent memory (via RedPlanetHQ/core).
* *Role:* "System 1" Association. This is the subconscious. It holds the massive, messy web of history—chat logs, specific entity relationships, and minor details (e.g., "What restaurant did we go to last November?").
* *Function:* Reeve queries C.O.R.E. only when it needs to retrieve specific details, preventing the Desk from becoming cluttered with trivia.

---

## V. The System Architecture (The "Body")

Reeve is designed to be interface-agnostic. It does not live *inside* an app; it lives in the terminal, and the world connects to it.

### 1. Initial Prototype (Completed)

*Status: Operational but Reactive (User-Initiated Only)*

The current prototype functions as a high-intelligence chatbot but lacks the defining "Chief of Staff" agency. It responds to the user but does not yet inhabit the user's life proactively.

#### 1. The Core Infrastructure (The Hapi Stack)

* **The Engine:** **Claude Code**. It serves as the primary reasoning agent, capable of executing terminal commands and managing complex context.
* **The Interface Layer:** **Hapi** (`tiann/hapi`).
* *Function:* Acts as the seamless bridge between local terminal use and remote web access.
* *Session Management:* Hapi natively handles session isolation. This allows the user to have distinct, focused conversations (e.g., "Debug Session," "Trip Planning") without context bleeding.
* *Notification Gap:* While Hapi handles the chat interface, its native notifications are generic. Therefore, the **Telegram Notification Tool** (detailed in the MVP spec) remains essential for delivering rich, content-aware alerts to the user.

#### 2. Connected Systems
* **Memory:** **C.O.R.E.** is active and connected, providing the "Archive" (System 1) memory.
* **Messaging Proxy (WhatsApp):** Full integration is complete. Reeve "masquerades" as the user, capable of reading group chats and injecting replies back into threads transparently.
* **Email Proxy (Gmail):** Full read/write integration is complete. Reeve can triage the inbox, draft replies, and manage threads without the user opening the Gmail client.

#### 3. The "Proactivity Gap" (Why this is not yet an MVP)

While the system is "smart," it fails the "Push" paradigm test:

1. **No Pulse:** The agent cannot wake itself up. It only acts when the user types in Hapi.
2. **No "Desk":** There is no structured, transparent file system (`Goals/`, `Responsibilities/`) for the agent to ground its decisions.
3. **Context Amnesia:** Without the "Desk" or "Pulse," the agent relies entirely on the current session window, losing the "Big Picture" view of the user's life.

---

### 2. The MVP Specification (In Progress)

*Status: Architecture Defined. Implementation Pending.*

The MVP transforms the current reactive prototype into a functional "Proactive Chief of Staff." The key innovation is moving from a single bot repo to a **Dual-Repo Architecture** that separates *Logic* from *Context*.

#### 1. The Dual-Repo Structure

To ensure transparency and modularity, the system is split into two distinct repositories:

* **A. The Engine: `reeve_bot/`**
    * **Role:** The immutable logic code.
    * **Contents:**
    * Implementation of the **Pulse Queue** (Cron jobs & SQLite/File-based queue).
    * Custom MCP Servers / Tools (Pulse Tools, Telegram Notification Tool).
    * Wrappers to launch Hapi/Claude Code with the correct environment.

* **B. The Desk: `my_reeve/`**
    * **Role:** The user’s personal context and "Consciousness." This is the Present Working Directory (PWD) when the agent launches.
    * **Contents:**
    * `CLAUDE.md`: The "Soul." A transparent system prompt explaining: "You are Reeve. Your goal is X. Your operating mode is Proactive."
    * `SKILLS.md`: Explicit definition of available skills (Pulse management, Calendar access).
    * `Goals/`: Directory of Markdown files defining high-level objectives.
    * `Responsibilities/`: Directory of Markdown files defining recurring duties.

#### 2. The Pulse System (MVP)

Since Hapi/Claude Code are reactive, `reeve_bot` introduces an external "Heartbeat" mechanism.

* **The Queue:** A unified **Pulse Queue** managing triggers. Each Pulse consists of:
    * `datetime`: When to wake up.
    * `prompt`: What to think about (e.g., "Hourly Check" vs. "Check Ticket Prices").
    * `session_link`: (Optional) Context to resume.


* **The Mechanic:**
    1. The Cron/Scheduler fires.
    2. It launches a **new Hapi session** (preventing context confusion in old threads).
    3. **Sticky Note Injection:** It checks for any "Sticky Notes" left by the previous session (e.g., *"Check if the user replied to the ski trip"*) and injects them into the new context.
    4. It injects the specific `prompt` + content of `CLAUDE.md` + `Goals/` summary.


* **The Tools (Exposed via `.claude/skills/../SKILL.md`):**
    * `schedule_aperiodic_pulse(datetime, prompt) -> PulseId`: Allows Reeve to set its own alarm clock for specific future tasks.
    * `list_upcoming_pulses() -> List[Pulse]`: Self-awareness of its future schedule.


#### 3. The Notification Bridge (Hapi + Telegram)

* **The Problem:** Hapi’s native push notifications are empty ("New output").
* **The Solution:** A dedicated `send_user_notification` tool.
* Reeve bypasses Hapi's native alerts for content.
* It sends a rich message via **Telegram**: *"🔔 Found a slot for your Deep Work."*
* **The Deep Link:** The message includes a URL to the specific Hapi session, allowing the user to click and immediately jump into the relevant context/chat thread on their device.



#### 4. Integration: Google Calendar

* **Requirement:** Full Read/Write MCP Integration.
* **Capabilities:**
* *Audit:* Read the upcoming week to identify fragments and conflicts.
* *Defense:* Write "Blockers" for Deep Work without asking.
* *Coordination:* Send invites to external contacts.


### 3. The Future Roadmap

* **Activity Queue Implementation:**
    * Development of a "Low-Urgency" parallel queue for passive events (e.g., newsletter summaries, system logs, non-critical updates).
    * *Mechanism:* Unlike the Pulse Queue, these items do **not** trigger a wake-up. They are buffered and presented as a summary ticker (e.g., *"3 new log items"*) during the next scheduled Periodic Pulse, preventing "alert fatigue."


* **Recursive Sub-Agents (maybe using claude sub-agents):**
    * Implementation of a robust "Manager/Worker" pattern where Reeve spawns ephemeral agent processes for long-running tasks (e.g., "Monitor this eBay listing for 3 days").
    * *Mechanism:* Sub-agents report back via the "Blackboard" (Desk files) rather than context stuffing.

* **Custom notification priorities:**
The notification tool has an additional priority to control user attention:
  * 🔕 **Silent:** Logged to history but triggers *no notification* (e.g., "Updated the library," "Sub-agent finished research").
  * 🔔 **Normal:** Standard push notification to Telegram.
  * 🚨 **Critical:** High-priority alert that overrides DND settings (via the Wrapper's API privileges).


* **Full "World" Proxy (WhatsApp/Email):**
    * *Current State:* Reeve "listens" (via local listeners) and reports to Telegram.
    * *Future State:* Reeve "masquerades." It will have tools to inject messages back into WhatsApp threads or draft emails directly, allowing the user to reply to a WhatsApp group via Telegram without ever opening the WhatsApp app.

* **Hardware Independence:**
    * Because the architecture is just a "Terminal Wrapper," Reeve can eventually be ported to voice interfaces, wearables, or custom hardware with zero changes to the core agent logic.

---

## Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines on:

- Setting up your development environment
- Running tests and formatting code
- Submitting pull requests
- Reporting issues
- Understanding the project architecture

Whether you're fixing bugs, adding features, or improving documentation, we appreciate your help in making Reeve better.

### Strategic Direction Feedback

Before diving into code contributions, consider reading **[docs/OpenClaw_COMPARISON.md](docs/OpenClaw_COMPARISON.md)** for context on Reeve's architectural philosophy and the open strategic questions facing the project. Community feedback on the "orchestrator vs. runtime" trade-offs is especially valuable and can be shared in [GitHub Discussions](https://github.com/reubenjohn/reeve_bot2/discussions).

