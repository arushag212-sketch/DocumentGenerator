# SVNIT ClubDocs

Official documents for SVNIT student clubs (permission letters, approval notes, certificates, bills,
minutes) in minutes instead of hours. Describe what you need, check the details, download PDF or Word.

- **Sign in with your SVNIT Google account** (only `@svnit.ac.in` addresses).
- **Each club has its own space:** members, letterhead, logo, templates and reference numbers.
- **Templates:** built-in SVNIT formats, a visual editor, and AI help to draft or import new ones.
- **Documents:** generated from one description, numbered automatically, reviewed and approved in the app.
  Approved PDFs carry a code anyone can verify at `/verify`.

## Tech stack

| Part | Built with |
|---|---|
| Website | React 18, TypeScript, Vite, Tailwind CSS, TipTap editor |
| Backend | Python 3.12, FastAPI, SQLAlchemy 2, Alembic |
| Documents | python-docx and docxtpl (Word), LibreOffice (PDF), PyMuPDF (page images) |
| AI | Google Gemini (optional; simple built-in rules without a key) |
| Data | SQLite locally, PostgreSQL in production; files on disk or Supabase Storage |

## Run it locally (Windows)

Needs Python 3.12+, Node 20+ and LibreOffice.

```powershell
copy .env.example .env          # then fill in at least GOOGLE_CLIENT_ID
python -m pip install -r requirements-dev.txt
python -m server.scripts.seed   # built-in templates and the demo accounts
python -m server.scripts.doctor # checks Python packages, LibreOffice and the database
python -m uvicorn server.app.main:app --port 8000
```

In a second terminal:

```powershell
cd web
copy .env.example .env          # VITE_GOOGLE_CLIENT_ID
npm install
npm run dev
```

Open http://localhost:5173. Demo accounts for local testing are listed in [docs/DEMO_ACCOUNTS.md](docs/DEMO_ACCOUNTS.md).

## Tests

```powershell
python -m pytest -q --timeout=300 -p no:cacheprovider
cd web; npm run build
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
server/      FastAPI app (api/, core/, models/), Alembic migrations, admin scripts
docgen/      Document engine: extraction, rendering, numbering, letterhead
web/         React website
templates/   Built-in Word templates and their schemas
assets/      Fonts, college crest
tests/       pytest suite
scripts/     Build and developer tools
docs/        Guides
```

## Guides

- [Deployment](docs/DEPLOYMENT.md)
- [User guide](docs/USER_GUIDE.md)
- [Templates (editor and Word templates)](docs/TEMPLATES.md)
- [AI setup](docs/AI_SETUP.md)
- [Numbering rules](docs/NUMBERING_SPEC.md)
- [Database schema](docs/DB_SCHEMA.md)

To share the code safely as a zip (no secrets, databases or dependencies):
`powershell -ExecutionPolicy Bypass -File scripts/make_share_zip.ps1`
