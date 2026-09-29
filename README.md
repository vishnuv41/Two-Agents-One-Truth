# Two Agents, One Truth ⚖️🧠

**Deterministic, Auditable Multi-Agent Consensus Powered by MeTTa & Symbolic Reasoning.**

When two AI agents present conflicting data (e.g., official calendar vs. live field sensor data), how do we determine the truth without relying on an opaque LLM black box? 

**Two Agents, One Truth** bridges multi-agent disagreement by passing agent claims and evidence into a **Hyperon/MeTTa** symbolic reasoning engine. MeTTa weighs evidence (reliability × recency), evaluates conflicts through agent-specific lenses, determines auditable resolutions (concede, conditional truth, or escalate to human), and learns new rules to update agent memory for subsequent runs.

---

## 🎯 Key Principles

- **No Black-Box Reasoning**: The LLM *never* decides the resolution outcome. Every decision, weight adjustment, and rule synthesis is performed explicitly inside `core/weigh.metta`.
- **Auditable Trace**: Every step—evidence assertion, agent lens evaluation, conflict detection, score calculation, and resolution—produces a clear symbolic execution log.
- **Continuous Learning & Memory**: When an agent concedes or a condition is established, the system updates source reliability scores and writes new symbolic rules. Subsequent runs converge immediately using learned rules.

---

## 🏗 System Architecture

```text
       User Input / Preloaded Scenario
                     │
                     ▼
           ┌──────────────────┐
           │ Free-Text Intake │ (Optional LLM JSON Extraction)
           └────────┬─────────┘
                    │
                    ▼
           ┌──────────────────┐
           │  Agent A / B     │ (Claims & Evidence Assertions)
           └────────┬─────────┘
                    │
                    ▼
          🧠 MeTTa Engine (weigh.metta)
    ┌─────────────────────────────────┐
    │ • Reliability × Recency Weights │
    │ • Agent Lens Evaluation         │
    │ • Conflict Detection            │
    │ • Resolution (Concede/Cond/Esc) │
    └────────────────┬────────────────┘
                     │
                     ▼
        ┌─────────────────────────┐
        │ Memory & Learning Diff  │
        │  • Reliability Update   │
        │  • Rule Synthesis       │
        └─────────────────────────┘
```

---

## 🚀 Scenarios & Resolution Types

| Scenario | Conflict | Resolution Type | Learning / Memory Behavior |
| :--- | :--- | :--- | :--- |
| **Crop (`crop`)** | Sowing timing (Advocate: Sow now, Auditor: Wait 7 days) | **Conditional Truth** | Learns rule: `sow = wait-7d` *if* `moisture-below-30pct`. |
| **Campus (`campus`)** | Library closing time (Official page vs Student report) | **Concede** | Agent A concedes to Agent B; source reliability adjusted in memory (`reliability[official-page]` ↓, `student-report` ↑). |
| **Tie (`tie`)** | Procurement vendor quote tie (Vendor X vs Vendor Y) | **Escalate** | Scores too close; escalates to human reviewer. Human input synthesizes a new learned rule. |

---

## 🛠 Technology Stack

- **Reasoning Core**: [Hyperon / MeTTa](https://github.com/trueagi-io/hyperon-experimental) (`hyperon`)
- **Backend API**: Python 3.11+, FastAPI, Uvicorn
- **Frontend**: Clean lightweight single-page HTML/JS interface
- **Testing**: Pytest (7 unit tests covering engine, learning diffs, and scenarios)
- **Omega Skill / Bridge**: `app/omega/` (Metta custom skill patch & Python bridge for SingularityNET Omega framework)

---

## ⚙️ Quickstart

### 1. Installation

```bash
git clone https://github.com/vishnuv41/Two-Agents-One-Truth.git
cd Two-Agents-One-Truth/app
pip install -r requirements.txt
```

### 2. Running the Web Application

```bash
uvicorn app:app --reload --port 8000
```
Open **`http://localhost:8000`** in your browser.

### 3. Running Unit Tests

```bash
pytest
```
*(All 7 unit tests pass deterministically without external LLM dependencies).*

---

## 🤖 Optional LLM Configuration

An OpenAI-compatible LLM (e.g. Groq, OpenRouter, OpenAI, Antigravity) is strictly **optional**.

If environment variables (`LLM_KEY`, `LLM_BASE_URL`, `LLM_MODEL`) are set:
1. **Free-Text Intake**: Translates unstructured user text into validated claims/evidence JSON. (Fallback: Structured line format parser).
2. **Trace Narration**: Generates plain-language 3-sentence explanations of the completed MeTTa trace.

> ⚠️ **Important**: The LLM has zero authority over decision-making or rule synthesis.

---

## 🌌 Omega Framework Integration

The repository includes a dedicated bridge in `app/omega/`:
- `skills_patch.metta`: Custom MeTTa skill definition following the Omega extension pattern.
- `twoagents_bridge.py`: Python wrapper exposing the MeTTa engine to Omega agents.

*Status: Omega skill/bridge implemented; runtime integration verified during the hackathon after mentor confirmation.*

---

## 📜 AI & Tooling Disclosure

- **Coding & Scaffolding**: Antigravity AI (Google DeepMind) was used for project organization, refactoring, test suite setup, and README documentation, reviewed and verified by the team.
- **Runtime Execution**: Deterministic symbolic reasoning is executed entirely by **Hyperon/MeTTa** (`weigh.metta`).
- **Optional Runtime LLM**: Used solely for free-text parsing into JSON and trace narration.

---

## 📄 License

MIT License.
