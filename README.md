# SVNIT ClubDocs

Official documents for SVNIT student clubs (permission letters, approval notes, certificates, bills,
minutes) in minutes instead of hours. Describe what you need, check the details, download PDF or Word.

- **Sign in with your SVNIT Google account** (`rollno@dept.svnit.ac.in`, any department).
- **Each club has its own space:** members, letterhead, logo, templates and reference numbers.
- **Templates:** built-in SVNIT formats, a visual editor, and AI help to draft or import new ones.
- **Documents:** generated from one description, numbered automatically, reviewed and approved in the app.
  Approved PDFs carry a code anyone can verify at `/verify`.

## Live demo

**https://clubdocs.vercel.app**

Five demo clubs with their official logos, one owner account each (email and password sign-in):

| Club | Owner email |
|---|---|
| ACM Student Chapter, SVNIT | `acm.owner@demo.svnit.ac.in` |
| Google Developer Groups on Campus, SVNIT | `gdgc.owner@demo.svnit.ac.in` |
| Centre for Human Resource Development (CHRD), SVNIT | `chrd.owner@demo.svnit.ac.in` |
| Drishti, SVNIT | `drishti.owner@demo.svnit.ac.in` |
| Raag, SVNIT | `raag.owner@demo.svnit.ac.in` |

All five use the password `ClubDocs@1234`. These are demo accounts only; real clubs sign in with
their SVNIT Google account. The first visit after a quiet spell can take up to a minute while the
free server wakes up.

## Tech stack

| Part | Built with |
|---|---|
| Website | React 18, TypeScript, Vite, Tailwind CSS, TipTap editor |
| Backend | Python 3.12, FastAPI, SQLAlchemy 2, Alembic |
| Documents | python-docx and docxtpl (Word), LibreOffice (PDF), PyMuPDF (page images) |
| AI | Google Gemini, with Groq as a fallback and a response cache (optional; simple built-in rules without a key) |
| Data | SQLite locally, PostgreSQL in production; files on disk or Supabase Storage |

## Run it locally (Windows)

Needs Python 3.12+, Node 20+ and LibreOffice.

```powershell
cd backend
copy .env.example .env          # then fill in at least GOOGLE_CLIENT_ID
python -m pip install -r requirements-dev.txt
python -m server.scripts.seed   # built-in templates and the demo accounts
python -m server.scripts.doctor # checks Python packages, LibreOffice and the database
python -m uvicorn server.app.main:app --port 8000
```

In a second terminal:

```powershell
cd frontend
copy .env.example .env          # VITE_GOOGLE_CLIENT_ID
npm install
npm run dev
```

Open http://localhost:5173. Demo accounts for local testing are listed in [docs/DEMO_ACCOUNTS.md](docs/DEMO_ACCOUNTS.md).

## Tests

```powershell
cd backend; python -m pytest -q --timeout=300 -p no:cacheprovider
cd ..\frontend; npm run build
```

Tests use their own temporary database and storage folder; your local data is never touched.
Close the local backend while the tests run, since the suite checks that the dev database stays unchanged.

## Deploy

Free setup on Vercel (website), Render (backend) and Supabase (database and files):
see **[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)**.

## Roles

| Role | Can |
|---|---|
| Platform admin | Everything, in every club |
| Owner | Everything in the club, including ownership and deleting the club |
| Admin | Members, invites, letterhead, numbering, venues; approve documents |
| Editor | Create and edit templates and documents; send documents for review |
| Viewer | View documents |

## Ground rules the app follows

- It does not invent official details (dates, amounts, venues, signatories). Anything missing is asked for or left blank to fill in.
- AI-written text is marked for review before it goes into an official template.
- Reference numbers are reserved atomically, and changing a numbering format only affects new documents.

## Project layout

```
backend/                Python backend (run its commands from inside this folder)
  server/               FastAPI app: api/v1 routes, core logic, models, schemas,
                        alembic migrations, admin scripts (seed, migrate, doctor, ...)
  docgen/               Document engine: extraction, rendering, numbering, letterhead
  templates/            Built-in Word templates and their schemas
  assets/               College crest, fonts, placeholders (see assets/README.md)
  config/ demo/         Club config example and demo-club data
  tests/                pytest suite
  scripts/              Build and developer tools (dev.ps1, build_templates.py, ...)
  requirements*.txt     Python packages (production / tests)
frontend/               React website
  src/pages/            One file per screen (landing, sign-in, dashboard, profile, help, ...)
  src/components/       Pieces used by the pages, grouped by feature
                        (layout, create, documents, templates, settings, TemplateEditor, ...)
docs/                   Guides
Dockerfile, render.yaml, vercel.json, docker-compose.yml   Deployment
```

## Guides

- [Deployment](docs/DEPLOYMENT.md)
- [User guide](docs/USER_GUIDE.md)
- [Templates (editor and Word templates)](docs/TEMPLATES.md)
- [AI setup](docs/AI_SETUP.md)
- [Numbering rules](docs/NUMBERING_SPEC.md)
- [Database schema](docs/DB_SCHEMA.md)
- [Design decisions](docs/DECISIONS.md)

To share the code safely as a zip (no secrets, databases or dependencies):
`powershell -ExecutionPolicy Bypass -File backend/scripts/make_share_zip.ps1`
