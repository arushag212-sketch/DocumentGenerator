# SVNIT ClubDocs — Smart Document Generator

The official template-driven document generation and approval platform for student chapters and clubs at **Sardar Vallabhbhai National Institute of Technology (SVNIT), Surat**.

---

## 🚀 Run the Website

Follow these exact Windows PowerShell instructions to set up and run the portal.

### 1. Prerequisites Check
Ensure you have installed:
- **Python >= 3.11** ([python.org](https://www.python.org/downloads/))
- **Node.js >= 18** and **npm** ([nodejs.org](https://nodejs.org/))
- **LibreOffice** for official PDF conversion ([libreoffice.org](https://www.libreoffice.org/download/download/))

---

### 2. Environment Setup & Dependency Installation (PowerShell)

Open PowerShell in the project directory:

```powershell
# 1. Create and activate a Python virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2. Upgrade pip and install all project dependencies
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -e .
```

---

### 3. Database Setup: PostgreSQL & SQLite

The platform supports both **PostgreSQL** (production standard) and **SQLite** (local development fallback).

#### Option A: PostgreSQL via Docker Compose (Recommended)
1. Start the PostgreSQL container:
   ```powershell
   docker compose up -d postgres
   ```
2. Configure your environment variable (or put in `.env`):
   ```powershell
   $env:DATABASE_URL="postgresql://clubdocs_user:clubdocs_password@localhost:5432/clubdocs"
   ```
3. Run migrations and seed data:
   ```powershell
   alembic upgrade head
   python -m server.scripts.seed
   ```

#### Option B: SQLite (Quick Local Development)
If you do not have Docker installed, you can use SQLite directly:
```powershell
# Set DATABASE_URL or let it default to sqlite:///data/clubdocs.db
$env:DATABASE_URL="sqlite:///data/clubdocs.db"
alembic upgrade head
python -m server.scripts.seed
```

*(Optional) Create a custom platform administrator account interactively:*
```powershell
python -m server.scripts.create_admin
```

---

### 4. Run the System Doctor

Verify that Python, Node, LibreOffice (`soffice`), the database, and cryptographic configurations are ready:

```powershell
python -m server.scripts.doctor
```
> You should see `[OK] All system checks passed! ClubDocs is ready to run.`

---

### 5. Running the Application

You can run in **Development Mode** (with hot reload on both frontend and backend) or **Single-URL Production Mode**:

#### Option A: Full-Stack Development Mode (Recommended for Development)
Open two separate PowerShell terminal tabs:

- **Terminal 1 — Backend API (FastAPI + Uvicorn):**
  ```powershell
  .\.venv\Scripts\Activate.ps1
  python -m uvicorn server.app.main:app --reload --port 8000
  ```
  *Swagger API Documentation available at: [http://localhost:8000/docs](http://localhost:8000/docs)*

- **Terminal 2 — Frontend UI (React + Vite + Tailwind):**
  ```powershell
  cd web
  npm install
  npm run dev
  ```
  *Web Portal available at: [http://localhost:5173](http://localhost:5173)*

---

#### Option B: Single-URL Production Mode
Build the frontend production bundle and serve everything (UI + API + Assets) from FastAPI on a single port:

```powershell
# Build the React frontend distribution
cd web
npm install
npm run build
cd ..

# Start the unified server
python -m uvicorn server.app.main:app --host 0.0.0.0 --port 8000
```
*Open your browser at: [http://localhost:8000](http://localhost:8000)*

---

#### Option C: 1-Click All-in-One Launcher Script
You can also run the bundled PowerShell launcher script:

```powershell
# Starts doctor, seeds DB, and launches dev servers
.\scripts\dev.ps1

# Or run in single-URL production mode:
.\scripts\dev.ps1 -Production
```

---

## 🔑 Demo Credentials (Dummy Data Only)

The database seed creates the following documented test accounts:

| Role | Email | Password | Access Scope |
| :--- | :--- | :--- | :--- |
| **Demo Club Owner** | `demo.owner@svnit.ac.in` | `DemoOwnerPass123!` | Owner of ACM Student Chapter, full document creation & settings |
| **Demo Lead** | `demo.lead@example.com` | `DemoSecurePass123!` | Lead/Owner member of ACM Student Chapter |
| **Platform Administrator** | Set via `create_admin` | (your password) | Full institute-wide superuser across all clubs |

---

## 📑 Supported Official Documents

1. **Permission Letter** (`permission_letter`): Formal venue, lab, and seminar hall booking request addressed to HoD (CSE Dept.) with single-line institute & chapter letterhead.
2. **Event Approval Note** (`approval_note`): Financial sanction and approval note with 1-page fit, budget breakdown table, and 2x2 official approval signatures.
3. **Bill Certificate (Form BC-R)** (`bill_certificate`): Two-page expenditure passing certificate with invoice itemization, GST breakdown, and certifier signature.
4. **Bill Summary** (`bill_summary`): Consolidated post-event expenditure sheet auto-computing grand totals across winners and vendor payees.
5. **Prize Money Receipt** (`prize_money_receipt`): Individual winner disbursement acknowledgement voucher with revenue stamp block and amount in words.
6. **Minutes of Meeting (MoM)** (`mom`): Structured minutes recording sanction decisions, committee attendees, and action items.

---

## 🧪 Running Automated Tests

Run the full automated test suite (including document rendering, security tests, and cross-document verification):

```powershell
python -m pytest tests/ -v
```
