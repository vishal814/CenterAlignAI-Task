# CentrAlign AI Operator

> **Autonomous Enterprise AI Employee Prototype for Customer Payment Resolution**  
> Built for CentrAlign AI Engineering Evaluation.

---

## 1. Problem Interpretation

Enterprise workflows require autonomous systems capable of executing multi-step business objectives under strict constraints, policies, and regulations. Traditional LLM chatbot prototypes merely generate speculative text describing what "would" happen. In high-stakes business environments (such as financial transactions, billing, and customer relations), this approach introduces catastrophic hallucinations and lack of auditability.

**The CentrAlign AI Operator** interprets the challenge by building a genuine autonomous AI employee:
- It receives a high-level, human-style enterprise objective (e.g., *"Resolve Rahul Sharma's payment issue."*).
- It independently decomposes the objective into entities, discovers the operational context, evaluates enterprise Standard Operating Procedures (SOPs), dynamically formulates an execution plan, invokes typed tools against real enterprise state, observes intermediate results, handles failures, engages human oversight when thresholds dictate, and **independently verifies** that state changes actually took place before claiming success.

---

## 2. Why This Workflow

Customer payment resolution was chosen as the workflow for this prototype because it represents the optimal intersection of enterprise autonomy challenges:

1. **High Impact & Risk**: Financial disbursements cannot be trusted to unconstrained generative text.
2. **Strict SOP Policies**: Enterprise refund thresholds (e.g. automatic <= ₹5,000 vs. managerial approval > ₹5,000) mirror real corporate governance.
3. **Multi-System Interaction**: Requires synchronizing CRM/Customer records, ticketing platforms, payment gateways, and policy documentation.
4. **Resilience Mandate**: Payment gateways frequently encounter transient network/service errors (503s, timeouts) that require intelligent retry logic rather than immediate failure.
5. **Verification Imperative**: Ensuring a ticket is marked resolved and a refund is recorded in the ledger requires querying source-of-truth databases, not trusting a return code alone.

---

## 3. Architecture

The system is organized into modular layers adhering to separation of concerns:

```
                                      +---------------------------------------------+
                                      |                 USER GOAL                   |
                                      +---------------------------------------------+
                                                             |
                                                             v
                                      +---------------------------------------------+
                                      |             CentrAlign AI Operator          |
                                      |              (LangGraph Workflow)           |
                                      +---------------------------------------------+
                                         /         |                   |         \
                                        /          |                   |          \
                                       v           v                   v           v
                          +--------------+  +--------------+  +--------------+  +---------------+
                          |  Understand  |  |    Gather    |  |    Dynamic   |  |   Executor    |
                          |  Goal Entity |  |   Context    |  |    Planner   |  |   & Verifier  |
                          +--------------+  +--------------+  +--------------+  +---------------+
                                                             |
                                                             v
                                            +---------------------------------+
                                            |   Allowlisted Tool Registry     |
                                            |   (Strict Typing & Validation)  |
                                            +---------------------------------+
                                               /       |       |       \
                                              /        |       |        \
                                             v         v       v         v
                                        +--------+ +--------+ +----+ +--------------+
                                        |Customer| | Ticket | |Pay | |  Playwright  |
                                        | Tools  | | Tools  | |Tool| | Browser Tool |
                                        +--------+ +--------+ +----+ +--------------+
                                               \       |       |       /
                                                v      v       v      v
                                        +---------------------------------+
                                        |    Enterprise State (SQLite)    |
                                        | Customers, Tickets, Payments,   |
                                        | Refunds, Approvals, Transients  |
                                        +---------------------------------+
```

### Components
1. **LLM Cognitive Layer (`app/agent/llm.py`, `app/agent/llm_schemas.py`)**:
   - Generates structured JSON responses validated by Pydantic models (`LLMGoalUnderstanding`, `LLMStructuredPlan`, `LLMNextAction`).
   - Genuinely determines what information is needed, devises dynamic plans, selects tools, interprets tool observations, and adapts plans after failures.
   - Provides a deterministic fallback only when the Gemini API key is unconfigured or in offline test environments.
2. **Deterministic Safety Validator (`app/agent/executor.py`, `app/agent/planner.py`)**:
   - **The Model Proposes. The Deterministic System Validates. The Tool Executes.**
   - Intercepts every LLM proposal. Enforces tool allowlists, checks SOP refund thresholds, prevents duplicate financial transactions, and guards against unauthorized actions.
3. **Agent State Graph (`app/agent/graph.py`)**: A LangGraph state machine orchestrating conditional edges, recovery loops, approval pauses, and terminal states.
4. **Allowlisted Tool Registry (`app/tools/registry.py`)**: A security layer constraining tool execution. The agent cannot run shell commands or execute raw database queries.
5. **Enterprise REST API (`app/api/`)**: FastAPI endpoints providing realistic enterprise CRUD access to customers, tickets, payments, refunds, and policy documents.
6. **Mock Support Portal (`mock_portal/`)**: A functional web portal UI reflecting ticket queues, customer metadata, and resolution workflows.
7. **Browser Automation Layer (`app/tools/browser_tools.py`)**: Playwright automation driving a real Chromium instance to inspect and update the support portal DOM.
8. **Unified Dashboard (`frontend/`)**: Modern glassmorphic monitoring dashboard providing real-time visibility into the agent's plan, live execution trace with explicit `decision_source` tags, human approval alerts, and verified evidence.

---

## 4. Agent Loop

The operator executes a structured cognitive cycle with deterministic guardrails:

```
User Goal
    ↓
LLM understand_goal
    ↓
LLM create_structured_plan
    ↓
Plan validator
    ↓
Tool executor
    ↓
Observation
    ↓
LLM choose_next_action
    ↓
Policy/tool validation
    ↓
Tool executor
    ↓
...
    ↓
Independent verifier
    ↓
Complete
```

1. **User Goal**: Receives a raw, unstructured instruction (e.g. *"Resolve Rahul Sharma's payment issue."*).
2. **LLM understand_goal**: Evaluates the goal, extracts target entities (customer name, customer ID, ticket ID), determines intent, and formulates a list of required context entities.
3. **LLM create_structured_plan**: Proposes a structured multi-step plan with explicit justifications.
4. **Plan Validator**: Validates all proposed plan steps against tool allowlists and safety constraints.
5. **LLM choose_next_action**: Evaluates current context, observations, errors, and retry status to select the next action, returning typed Pydantic JSON:
   ```json
   {
     "action": "get_payment",
     "reason": "Need payment status before deciding whether refund is permitted",
     "arguments": { "payment_id": "PAY9001" }
   }
   ```
6. **Policy / Tool Validation**: Deterministically verifies:
   - Tool is in allowlist.
   - Arguments match function signatures.
   - Financial amount $\le$ ₹5,000 (if $>$ ₹5,000 and not approved, forces `paused_for_approval`).
   - Transaction is not already refunded (overrides to `skip_refund` on completed refunds).
7. **Tool Executor**: Dispatches action against the enterprise mock environment.
8. **Observation**: Records structured tool results in `state["observations"]`.
9. **Adapt / Recover**:
   - On transient failure (`temporary_payment_service_error`), increments `retry_count`, logs `recovery logic`, and triggers a bounded retry.
10. **Independent Verifier**: Re-queries source-of-truth tables in SQLite (`refunds`, `payments`, `tickets`) to verify state transitions before marking complete.
11. **Complete**: Assembles cryptographic/structured evidence and generates an executive summary.

---

## 5. Agent State

The agent maintains an explicit, typed state (`AgentState`) passed between all nodes:

| Field | Type | Description |
|---|---|---|
| `task_id` | `str` | Unique task execution identifier (`TASK_XXXXXX`). |
| `goal` | `str` | High-level user goal. |
| `customer` | `Optional[dict]` | Customer profile details (ID, name, tier, email). |
| `ticket` | `Optional[dict]` | Support ticket details (ID, issue, status, notes). |
| `payment` | `Optional[dict]` | Payment record (ID, amount, currency, status, refund_status). |
| `policy` | `Optional[dict]` | Parsed company refund policy rules and thresholds. |
| `plan` | `List[dict]` | Dynamic execution plan steps with individual statuses. |
| `current_step` | `str` | Active node identifier in LangGraph. |
| `executed_actions` | `List[dict]` | Audit list of actions taken by tools. |
| `observations` | `List[dict]` | Intermediate tool observation payloads. |
| `errors` | `List[dict]` | Errors encountered during execution. |
| `retry_count` | `int` | Number of retries attempted (bounded by `max_retries = 1`). |
| `approval_required`| `bool` | True if action triggered an enterprise approval threshold. |
| `approval_id` | `Optional[str]` | Unique approval request ID in the enterprise ledger. |
| `approval_status` | `Optional[str]` | Status of approval (`pending`, `approved`, `rejected`). |
| `verification` | `dict` | Independent verification report (`refund_verified`, `ticket_verified`). |
| `evidence` | `dict` | Final structured proof payload. |
| `final_status` | `str` | State enum (`running`, `paused_for_approval`, `completed`, `failed`). |
| `summary` | `str` | Executive human-readable natural language summary. |
| `trace` | `List[dict]` | Complete chronological execution trace with inputs/outputs. |

---

## 6. Tool System

Tools are registered in a strictly typed, allowlisted `ToolRegistry`. The LLM or reasoning engine has **no direct database write access** and **no shell access**.

### Allowlisted Tools:
- `search_customers(query: str)`: Searches customer directory by name, email, or ID.
- `get_customer(customer_id: str)`: Retrieves customer details.
- `search_tickets(customer_id: Optional[str], query: Optional[str])`: Finds open support tickets.
- `get_ticket(ticket_id: str)`: Retrieves support ticket information.
- `get_payment(payment_id: str)`: Retrieves payment ledger status.
- `read_company_policy(policy_name: str)`: Loads policy guidelines from markdown.
- `issue_refund(payment_id: str, reason: str, amount: Optional[float])`: Issues refund in SQLite; detects duplicate refunds; triggers simulated transient errors when configured.
- `update_ticket(ticket_id: str, status: str, notes: Optional[str])`: Updates ticket status and appends audit logs.
- `verify_refund(payment_id: str, expected_refund_id: Optional[str])`: Re-queries payment and refund tables.
- `verify_ticket(ticket_id: str, expected_status: str)`: Re-queries ticket table.
- `inspect_ticket_in_browser(ticket_id: str, portal_url: Optional[str])`: Real Playwright Chromium DOM inspection.
- `resolve_ticket_in_browser(ticket_id: str, notes: str, portal_url: Optional[str])`: Real Playwright Chromium DOM interaction.

---

## 7. Autonomy

The user does not supply procedural steps. The LLM is genuinely responsible for:
1. **Understanding the Goal**: Extracts semantic entities and formulates the exact list of required enterprise context (`LLMGoalUnderstanding`).
2. **Creating the Structured Plan**: Proposes an ordered DAG plan with explicit justifications (`LLMStructuredPlan`).
3. **Selecting the Next Action**: Analyzes intermediate observations and chooses the exact tool, arguments, and reasoning (`LLMNextAction`).
4. **Adapting After Failures**: Interprets transient gateway errors and devises bounded retry actions.

### Deterministic Safety Guardrails
Autonomy does **not** mean unconstrained execution. CentrAlign AI Operator enforces the core principle:
> **The Model Proposes. The Deterministic System Validates. The Tool Executes.**

- **Tool Allowlist**: The LLM cannot call unapproved tools or arbitrary shell commands.
- **Threshold Enforcement**: The LLM cannot bypass the ₹5,000 auto-refund threshold; amounts > ₹5,000 are deterministically intercepted and paused for Human Manager Approval.
- **Duplicate Prevention**: The LLM cannot disburse a second refund for a transaction already marked completed.
- **Bounded Retries**: Maximum retry limit (`max_retries = 1`) is strictly enforced by deterministic recovery logic.
- **Independent Verification Gate**: The LLM cannot declare a task complete without database ledger proof verified by independent queries.

---

## 8. Reliability

The operator implements structured failure classification:

- **Transient Failure (`temporary_payment_service_error`)**:
  - Payment gateway timeouts, 503s, or network drops.
  - Classified as `retryable: true`.
  - The agent retries up to `max_retries = 1`. If the retry fails, the agent stops safely and logs an audit error without risking infinite loops.
- **Permanent Business Rule Violations**:
  - `duplicate_refund_prevented`: Payment is already refunded. The agent safely skips disbursement and references the existing refund.
  - `invalid_payment_status`: Payment is not `charged` (e.g. `failed`). Refund is halted per policy.
  - `missing_entity`: Customer, ticket, or payment does not exist. Safe exit with explanatory diagnostics.

---

## 9. Human Approval

To prevent unauthorized capital outflow, CentrAlign AI SOP enforces an approval gate:
- Refunds $\le$ ₹5,000: Autonomous execution allowed.
- Refunds $>$ ₹5,000: Mandatory Human Approval.

### Approval Mechanism:
1. When Amit Kumar's refund (₹8,500) is evaluated, the agent triggers `approval_required = True`.
2. A record is inserted into SQLite `approvals` with status `pending`.
3. The LangGraph workflow **pauses** at the `paused_for_approval` state.
4. The dashboard displays an interactive approval banner with customer details, requested amount, and policy justification.
5. **Approve Flow**: Manager clicks **Approve** (`POST /api/tasks/{id}/approve`). The agent resumes from its exact execution point without restarting, processes the refund, updates the ticket, and verifies.
6. **Reject Flow**: Manager clicks **Reject** (`POST /api/tasks/{id}/reject`). The agent closes the ticket noting managerial denial, issues no refund, and exits safely.

---

## 10. Verification

In autonomous systems, **Action Success $\neq$ Verified Outcome**. An API endpoint returning HTTP 200 does not prove the financial ledger was updated, nor that the customer's support ticket was transitioned.

The CentrAlign AI Operator mandates **independent verification**:
1. After `issue_refund` completes, the agent invokes `verify_refund()`.
2. This runs an independent query against SQLite `payments` and `refunds` to confirm:
   - `refund_status == 'completed'`.
   - A distinct refund ID exists in `refunds` with positive amount.
3. The agent invokes `verify_ticket()`.
4. This runs an independent query against `tickets` to confirm:
   - `status == 'resolved'`.
   - Resolution audit notes are present.
5. If any check fails, `verified = False` and the task is marked `failed_verification`.

---

## 11. Generalization

The agent is not hardcoded for a single user. The exact same architecture, state graph, and tool pipeline handles all scenarios seamlessly:

| Scenario | Customer | Condition | Agent Behavior |
|---|---|---|---|
| **Scenario 1** | Rahul Sharma | Amount $\le$ ₹5,000 | Fully autonomous resolution & verification |
| **Scenario 2** | Priya Patel | Transient Gateway Error | Observes failure, performs auto-retry, completes |
| **Scenario 3** | Amit Kumar | Amount $>$ ₹5,000 | Pauses for human approval; resumes upon decision |
| **Scenario 4** | Neha Verma | Already Refunded | Prevents double-disbursement; links existing refund |
| **Scenario 5** | Vikram Singh | Failed Transaction | Safeguard detects uncharged payment; halts safely |
| **Scenario 6** | Unknown Customer | Entity Missing | Fails gracefully with diagnostic message |

---

## 12. Technical Decisions

- **Structured Output Contracts (Pydantic)**: All LLM decisions (understanding, planning, next action) are strictly typed Pydantic models. This eliminates free-form parsing errors and provides deterministic validation before execution.
- **FastAPI**: Asynchronous, typed, high-performance REST framework with automatic OpenAPI documentation.
- **LangGraph**: Explicit state graph with first-class support for cyclical recovery loops, conditional routing, and human-in-the-loop pauses.
- **Playwright (Chromium)**: True headless/headed browser automation that verifies actual enterprise UI DOM rendering.
- **SQLite (WAL Mode)**: Embedded relational database with zero external dependencies, ACID transactions, and instant test re-seeding.
- **Dual-Mode Engine (Live Gemini + Offline Fallback)**: Calls Gemini API for structured JSON reasoning when configured, with an intelligent deterministic fallback that executes the exact same state machine when running offline, ensuring deterministic reproducibility across the 24 automated tests without faking autonomy.
- **Vanilla Modern Frontend (HTML5/CSS3/JS)**: Fast, dependency-free dashboard with glassmorphism, responsive grids, and zero build tool overhead.

---

## 13. Setup

### Prerequisites
- Python 3.11+
- Git

### Installation Commands
```powershell
# 1. Clone repository (or navigate to workspace)
cd "d:\CenterAlignAI Task"

# 2. Create virtual environment
python -m venv .venv

# 3. Activate virtual environment
# On Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# On Linux/macOS:
# source .venv/bin/activate

# 4. Install dependencies
pip install -r requirements.txt

# 5. Install Playwright Chromium browser
playwright install chromium
```

---

## 14. Configuration

Create or inspect `.env` in the project root:

```env
# Google Gemini API Key (Optional: system runs in robust autonomous mode if blank)
GEMINI_API_KEY=
GEMINI_MODEL=gemini-2.5-flash

# Enterprise Server
HOST=127.0.0.1
PORT=8000
DATABASE_URL=sqlite:///./enterprise.db

# SOP Rules
AUTO_REFUND_THRESHOLD=5000

# Browser Automation
PLAYWRIGHT_HEADLESS=true
```

---

## 15. Running

### Seed Database
```powershell
.\.venv\Scripts\python.exe -m app.db.seed
```

### Start Server
```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

### Accessing Interfaces:
- **Operator Dashboard**: [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
- **Support Portal UI**: [http://127.0.0.1:8000/portal](http://127.0.0.1:8000/portal)
- **API Swagger Docs**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

---

## 16. Testing

Run the comprehensive pytest suite verifying all scenarios, retry behaviors, human approvals, browser automation, and independent verification:

```powershell
.\.venv\Scripts\python.exe -m pytest -v
```

All 24 automated tests execute in $\sim$5 seconds.

---

## 17. Demo

### Demo Scenario 1: Normal Autonomous Execution (Rahul Sharma)
1. Open the Dashboard at `http://127.0.0.1:8000/`.
2. Click **Scenario 1: Rahul Sharma** (Goal: *"Resolve Rahul Sharma's payment issue."*).
3. Click **Dispatch Autonomous Agent**.
4. Observe the live plan generation, customer search, ticket retrieval, policy check, ₹2,499 refund issuance, ticket status update to `resolved`, and independent ledger verification.

### Demo Scenario 2: Transient Failure & Recovery (Priya Patel)
1. Click **Scenario 2: Priya Patel** (Goal: *"Resolve Priya Patel's payment issue."*).
2. Click **Dispatch Autonomous Agent**.
3. In the Execution Trace, observe:
   - Initial call to `issue_refund` triggers `temporary_payment_service_error`.
   - Agent observes error is retryable.
   - Retry counter updates to `1 / 1`.
   - Retry succeeds with new refund ID.
   - Verification confirms record in ledger.

### Demo Scenario 3: Human Approval Gate (Amit Kumar)
1. Click **Scenario 3: Amit Kumar** (Goal: *"Resolve Amit Kumar's payment issue."*).
2. Click **Dispatch Autonomous Agent**.
3. Observe that execution **pauses** at the Human Approval Gate because the ₹8,500 refund exceeds the ₹5,000 threshold.
4. An alert banner appears displaying customer metadata, ticket ID, and the ₹8,500 requested refund.
5. Click **Approve & Continue Execution**.
6. Observe the agent resume state, disburse the refund, update the ticket, and verify the ledger.

---

## 18. Assumptions

1. **Currency**: All mock transactions are denominated in INR (₹).
2. **Customer Identity**: Customer names in goals are matched case-insensitively or via unique IDs.
3. **Execution Environment**: Local SQLite simulates the distributed enterprise database ledger.
4. **Browser Availability**: Chromium is installed via Playwright for DOM verification.

---

## 19. Limitations

1. **Single-Process Task Store**: Active tasks are kept in an in-memory dictionary; multi-instance deployment would require persistent Redis/Postgres storage.
2. **Synchronous Tool Invocation**: Tool execution currently operates synchronously within the node; a production queue would leverage distributed task workers.
3. **Mock Gateway**: The payment gateway is simulated locally via SQLite rather than a live Stripe/Razorpay sandbox.

---

## 20. What I Would Build Next

1. **Multi-Agent Orchestration**: Separate specialized agents (Context Investigator Agent, Policy Compliance Agent, Execution Officer, and Quality Auditor).
2. **Temporal Checkpointing**: Persist LangGraph checkpoints into Postgres for fault tolerance across server restarts.
3. **Streaming Token Updates**: WebSockets/Server-Sent Events (SSE) for millisecond-level agent thought streaming.
4. **Biometric / SSO Approval Webhooks**: Slack/Teams notification webhooks for one-click manager approvals on mobile devices.

---

## 21. Models / APIs / Frameworks Used

- **LangGraph** (StateGraph, Conditional Edges, Checkpoint resumption)
- **FastAPI & Uvicorn** (REST API, static mounting, CORS)
- **Google GenAI / Gemini API** (`gemini-2.5-flash` for structured goal understanding, dynamic plan creation, next-action selection, and executive summarization)
- **Playwright** (Chromium headless DOM automation)
- **SQLite3** (ACID transactional enterprise ledger)
- **Pydantic v2 & Pydantic-Settings** (Data validation, schemas, and configuration)
- **Pytest & Pytest-Asyncio** (Automated test verification suite)
