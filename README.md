# LokProcure

**AI-Powered Bilateral Government Procurement Platform**

> *"AI negotiates. Policy controls. Humans authorize exceptions. The system remembers everything."*

---

## Overview

LokProcure is a dual-sided procurement platform built for government procurement workflows. It connects government procurement officers with registered vendors through a structured, AI-assisted process that covers the full lifecycle from purchase request to approved purchase order.

The platform addresses a core problem in public procurement: negotiations between government buyers and commercial vendors are slow, opaque, and difficult to audit. LokProcure automates the negotiation loop using AI agents while keeping deterministic policy rules and human approvers firmly in control of any decision that exceeds pre-configured authority limits.

---

## Core Capabilities

| Capability | Description |
|---|---|
| **Dual-portal architecture** | Separate, role-enforced Government and Vendor portals with independent views |
| **Vendor bidding marketplace** | Vendors submit competitive bids against open purchase requests (RFQs) |
| **Bilateral AI negotiation** | Independent Government Agent and Vendor Agent negotiate price and delivery in alternating turns |
| **Confidential boundary isolation** | Each agent operates with private state (budget ceiling, price floor) invisible to the counterparty |
| **Deterministic policy guardrails** | Every AI proposal is evaluated by a rule engine before it is accepted; proposals that exceed authority limits are blocked regardless of LLM output |
| **Human-in-the-loop escalation** | When a proposal crosses a policy boundary, negotiation pauses and routes to an authorized human approver |
| **Approval / reject / modify / resume** | Human approvers can approve, reject, submit a counter-proposal, or resume the automated loop |
| **Policy-RAG compliance audit** | ChromaDB vector index over five procurement policy documents; each purchase request is audited against retrieved policy excerpts before negotiation begins |
| **Approval routing rules** | Budget- and urgency-driven rules automatically route PRs to the appropriate authority tier (Department Manager to Plant Head) |
| **Purchase order generation** | Approved negotiations produce a ReportLab PDF purchase order with line items, audit trail, and INR amounts |
| **Full audit and negotiation history** | Every negotiation turn, escalation, approval action, and policy check is persisted and visible to authorized reviewers |

---

## How It Works

```
Government Issues Purchase Request (PR)
    |
    v
Vendors Submit Bids (Marketplace)
    |
    v
Bilateral AI Negotiation Begins
    |-- Government Agent proposes (price, delivery)
    |       `-- Deterministic policy check: ALLOW / ESCALATE
    |-- Vendor Agent counter-proposes
    |       `-- Deterministic policy check: ALLOW / ESCALATE
    `-- Rounds continue (up to 5) or until consensus
    |
    v
Policy Violation Detected?
    |-- YES -> Negotiation paused -> Human Escalation Queue
    |           `-- Approver: Approve / Reject / Counter / Resume
    `-- NO  -> Agreement reached automatically
    |
    v
Human Final Authorization
    |
    v
Purchase Order Generated (PDF, INR)
    |
    v
Audit Trail Persisted
```

---

## Architecture

### Negotiation Design

LokProcure uses a **bilateral agent model** built on LangGraph. Two independent agents take alternating turns in a stateful graph:

- **Government Agent** (`gov_agent.py`): Calls Google Gemini to generate proposals within the government's declared price ceiling and delivery requirement. Falls back to a deterministic rule-based offer if the API is unavailable.
- **Vendor Agent** (`vendor_agent.py`): Calls Google Gemini to counter-propose, guarding its declared price floor and minimum feasible delivery. Private floor values are never surfaced to the government agent's context.
- **Policy engine** (`policy.py`): After every LLM proposal, a deterministic check compares the proposed price and delivery against the current agent's configured limits. A proposal that fails the check triggers ESCALATE and is never passed to the counterparty.

> **"LLM proposes; deterministic policy rules enforce."**

### Compliance Audit

Before a negotiation starts, each purchase request is audited by `compliance_service.py`, which:

1. Performs a semantic similarity search over five policy documents stored in ChromaDB (`all-MiniLM-L6-v2` embeddings).
2. Runs a deterministic heuristic guard over the retrieved excerpts to check five procurement rules (spend caps, sole-source restrictions, budget thresholds, renewal disclosure, urgent procurement documentation).
3. Records violations and required actions alongside the purchase request.

### Approval Routing

When a PR requires human approval, one of four deterministic routing rules selects the appropriate authority:

| Rule | Condition | Authority |
|---|---|---|
| Rule 1 | Operations CapEx > Rs. 1,00,000 | Plant Head |
| Rule 2 | Critical urgency AND quantity > 500 | VP Operations |
| Rule 3 | Budget > Rs. 50,000 | Finance Director |
| Rule 4 | All other cases | Department Manager |

---

## Technology Stack

| Technology | Purpose |
|---|---|
| **React 19 + Vite** | Frontend SPA - Government and Vendor portals |
| **Tailwind CSS** | Utility-first styling |
| **Recharts** | Dashboard analytics and bid comparison charts |
| **FastAPI** | Backend REST API and business logic |
| **SQLAlchemy + SQLite** | ORM and persistence |
| **LangGraph** | Bilateral negotiation graph state machine |
| **Google Gemini (`google-genai`)** | LLM used by both negotiation agents |
| **ChromaDB** | Vector store for policy document retrieval |
| **`all-MiniLM-L6-v2`** | Sentence embedding model for policy RAG |
| **ReportLab** | PDF purchase order generation |
| **bcrypt** | Password hashing |
| **python-jose** | JWT creation and validation |
| **python-dotenv** | Environment configuration |

---

## Security & Governance

The following controls are implemented in the current codebase:

- **JWT authentication** (HS256, 60-minute token lifetime) - all API routes require a valid bearer token
- **Role-based authorization** - `require_gov_role` and `require_vendor_role` middleware enforced on every portal router
- **API-level authorization checks** - route handlers verify the caller's role before accessing or modifying any resource
- **Login rate limiting** - maximum 5 failed attempts per IP address per 60-second window; excess requests return HTTP 429
- **Concurrent negotiation lock** - active LangGraph negotiation sessions are locked to prevent duplicate concurrent submissions (HTTP 409 on conflict)
- **HTTP security headers** - `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin` added to all responses
- **Configurable CORS** - allowed origins defined via `CORS_ORIGINS` environment variable; defaults to localhost only
- **Confidential negotiation-state isolation** - each agent's private state (government budget ceiling, vendor price floor) is held in separate `GovAgentState` / `VendorAgentState` structs and is never included in the shared event log
- **Deterministic policy enforcement** - LLM output is always validated by the rule engine before being applied; the LLM cannot bypass policy limits
- **Human approval gate** - purchase orders cannot be generated until an authorized human approver acts on the workflow record
- **Audit and event history** - every negotiation turn, escalation, and approval action is persisted in the database

---

## Government Workflow

1. **Login** as a government persona
2. **Create a Purchase Request** - title, description, department, quantity, budget, urgency
3. **Review bids** submitted by vendors in the marketplace
4. **Start AI negotiation** for a selected bid - the bilateral agents begin alternating turns
5. **Monitor the negotiation** - view round-by-round events, current price, and delivery terms
6. **Act on escalations** if a policy boundary is triggered - approve, reject, counter, or resume
7. **Authorize the final proposal** - approve through the Approval Queue
8. **Download the generated PO PDF** - ReportLab PDF with full line items and audit trail in INR

---

## Vendor Workflow

1. **Login** as a vendor persona
2. **Browse the bid marketplace** - view open purchase requests from the government
3. **Submit a bid** - quoted price and delivery days
4. **Enter negotiation** when the government initiates - the vendor's AI agent responds in alternating turns
5. **Intervene manually if required** - vendors can escalate or counter-propose at any round
6. **Receive and acknowledge the PO** - awarded orders appear in the Vendor Active Orders view

---

## Repository Structure

```
LokProcure/
├── backend/
│   ├── app/
│   │   ├── compliance/
│   │   │   ├── policies/          # Five procurement policy documents (Markdown)
│   │   │   ├── chroma_db/         # ChromaDB vector store
│   │   │   ├── compliance_service.py
│   │   │   └── ingest.py
│   │   ├── generated_pos/         # Generated PO PDF files
│   │   ├── negotiation/
│   │   │   ├── gov_agent.py       # Government AI agent
│   │   │   ├── vendor_agent.py    # Vendor AI agent
│   │   │   ├── graph.py           # LangGraph bilateral graph
│   │   │   ├── policy.py          # Deterministic policy rule engine
│   │   │   ├── prompts.py         # LLM system prompts
│   │   │   └── state.py           # TypedDict state schema
│   │   ├── routers/
│   │   │   ├── auth.py
│   │   │   ├── government/
│   │   │   │   ├── approvals.py   # Approval workflows and PO generation
│   │   │   │   ├── dashboard.py
│   │   │   │   ├── purchase_requests.py
│   │   │   │   └── vendors.py
│   │   │   └── vendor_portal/
│   │   │       ├── bids.py
│   │   │       ├── negotiation.py
│   │   │       └── orders.py
│   │   ├── auth.py                # JWT, bcrypt, rate limiting
│   │   ├── database.py
│   │   ├── main.py                # FastAPI app, middleware, router registration
│   │   ├── models.py              # SQLAlchemy ORM models
│   │   └── schemas.py             # Pydantic request/response schemas
│   ├── seed_data.py               # Demo database seed
│   ├── venv/
│   └── procureiq.db               # SQLite database (generated at runtime)
├── frontend/
│   ├── public/
│   │   └── assets/                # Static assets
│   ├── src/
│   │   ├── components/
│   │   │   ├── government/        # Gov portal views (Bids, Negotiations, Orders, Sidebar)
│   │   │   ├── vendor/            # Vendor portal views (Dashboard, Bids, Orders, Sidebar)
│   │   │   ├── negotiation/       # NegotiationPanel
│   │   │   ├── ApprovalQueue.jsx
│   │   │   ├── Dashboard.jsx
│   │   │   ├── Login.jsx
│   │   │   ├── PurchaseOrders.jsx
│   │   │   ├── PurchaseRequestForm.jsx
│   │   │   ├── Sidebar.jsx
│   │   │   └── VendorComparison.jsx
│   │   ├── App.jsx
│   │   ├── api.js
│   │   ├── index.css
│   │   └── main.jsx
│   ├── package.json
│   └── vite.config.js
├── README.md
└── .gitignore
```

---

## Local Development Setup

### Prerequisites

- Python 3.12+
- Node.js 18+
- A `.env` file in `backend/` (see Environment Configuration below)

### Environment Configuration

Create `backend/.env` with the following variables:

```env
SECRET_KEY=<a-strong-random-secret-key>
GEMINI_API_KEY=<your-google-gemini-api-key>
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
ENABLE_API_DOCS=true
```

> **Note:** `SECRET_KEY` must be set to a non-default value. The application will refuse to start if it detects the placeholder default.

### Backend

```cmd
cd /d P:\Projects\LokProcure\backend

REM Activate virtual environment
.\venv\Scripts\activate

REM Seed the database (first run only)
python seed_data.py

REM Start the API server
.\venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

API available at: `http://127.0.0.1:8000`
Interactive API docs (when `ENABLE_API_DOCS=true`): `http://127.0.0.1:8000/docs`

### Frontend

```cmd
cd /d P:\Projects\LokProcure\frontend

REM Install dependencies (first run only)
npm install

REM Start the dev server
npm run dev -- --port 5173
```

Frontend available at: `http://localhost:5173`

---

## Demo Personas

The following personas are created by `seed_data.py` and are intended for local demonstration purposes only.


### Vendor Personas

Vendor users are also seeded alongside the government users. Log in using the **Vendor** tab on the login screen to access the Vendor portal.

> These credentials exist solely for local demonstration. The .internal email domain is a seed data artifact; use the emails exactly as shown to log in. Do not use them in any internet-accessible or shared deployment.

---

## Production Considerations

The current implementation is a functional demonstration. A production deployment would require additional infrastructure:

- **Database**: Replace SQLite with PostgreSQL for concurrent access and durability
- **Authentication**: Migrate to HttpOnly cookie-based token storage; implement server-side token revocation (e.g., Redis blocklist)
- **Session management**: Externalize rate-limit state to Redis for multi-process deployments
- **MFA**: Add multi-factor authentication for high-authority approver roles
- **Secrets management**: Use a secrets manager (e.g., HashiCorp Vault, GCP Secret Manager) rather than `.env` files
- **Audit infrastructure**: Stream negotiation and approval events to a centralized, tamper-evident audit log
- **Deployment**: Container-based deployment with a reverse proxy (nginx or Caddy), TLS termination, and health monitoring
- **ERP integration**: The data model includes fields representing a purchase order payload compatible with Oracle NetSuite SuiteTalk REST API conventions. Actual ERP integration would require a configured API connection and is not implemented in the current codebase

---

## Project Status

The current implementation includes:

- Government and Vendor portal workflows (bidding, negotiation, approvals, orders)
- Bilateral AI negotiation with LangGraph (Government Agent + Vendor Agent)
- Deterministic policy rule engine (guardrails applied to every LLM proposal)
- Policy-RAG compliance audit (ChromaDB + 5 procurement policy documents)
- Human-in-the-loop escalation and approval queue
- Approval routing rules (4-tier authority routing based on budget and urgency)
- Purchase order generation (ReportLab PDF, INR formatting with Indian number grouping)
- Security hardening (JWT, RBAC, login rate limiting, security headers, negotiation concurrency lock)
- Full negotiation event history and audit trail


