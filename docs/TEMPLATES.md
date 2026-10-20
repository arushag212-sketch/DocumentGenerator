# Templates guide

ClubDocs templates can be made in two ways:

- **In the web editor** (most clubs): visual, no Word needed. See section 1.
- **As Word files in `templates/`** (built-in templates, maintained by developers). See section 2.

---

## 1. The template editor

Open **Templates**, pick a template and click **Edit** (or **Preview** first to see it with sample data).

### Layout

| Area | What it holds |
|---|---|
| **Left sidebar** | **Blocks** (headings, paragraphs, tables, signature grids, club logo, college logo), **Fields** and **Design** |
| **Page** | The A4 page you edit. The club letterhead at the top is generated from your club settings |
| **Right panel** | **AI chat**, **Fields**, **Design** and **Checks** |

### Fields (the parts that change per document)

- Type `{{` in the page, or use **Insert field**, to add a field such as *Event Name* or *Venue*.
- Click a field chip to rename it, mark it required or sensitive, or change its type.
- The **Fields** list shows every field. Example values typed there are used only by **Preview**.

### Editing

- Type `/` for the block menu.
- Select text for the formatting bar (bold, italic, underline, alignment, font and size).
- Right-click inside the page for cut, copy, paste, formatting, font and size, and duplicate or delete block.
- Drag the handle on the left of a block to move it. `Alt + ↑ / ↓` moves the current block.
- Shortcuts: `Ctrl+S` save, `Ctrl+P` preview, `Ctrl+Z` / `Ctrl+Y` undo and redo, `Esc` closes menus.

### Design

Choose portrait or landscape, margins, page border, theme colour and fonts. Fonts are bundled with the
app (Tinos, Merriweather, Playfair Display, Roboto, Open Sans, Montserrat, Roboto Mono, Noto Sans
Devanagari and Noto Sans Gujarati), so PDFs look the same everywhere.

### AI chat

Describe a change in plain words (*"add a table for expenses"*, *"make the tone more formal"*). The
assistant shows what it will change; nothing is applied until you accept it, and one undo reverts it.
It never invents official approval wording. Without a Gemini key it falls back to simple built-in rules.

### Checks and publishing

**Checks** lists missing official details, inconsistent dates and hard-to-read colours. **Publish**
makes the template available for creating documents. AI-written blocks must be reviewed before publishing.

### Other ways to start a template

- **Template wizard**: describe the document and answer up to three questions.
- **Import**: paste the text of an existing letter or upload a `.docx`; dates, names and amounts become fields.
- **Translate**: Hindi or Gujarati, keeping fields and tables intact.

---

## 2. Built-in Word templates (developers)

Built-in templates live in `templates/<template_id>/` as a Word file plus `schema.yaml`, rendered with
`docxtpl` (Jinja2 syntax). `scripts/build_templates.py` generates them.

### Avoid split tags

Word often splits text into several runs, and `{{ event_name }}` split across runs is not recognised.

- Type each tag in one go, or paste it as plain text (`Ctrl+Shift+V`).
- Validate after saving: `python -m docgen.cli validate-templates`

### Repeating table rows

Put the loop tags in their own rows; `docxtpl` removes those rows and repeats the row between them:

```jinja
{%tr for item in items %}
{{ loop.index }} | {{ item.name }} | {{ format_inr(item.amount) }}
{%tr endfor %}
```

### Functions available in templates

| Function | Example output |
|---|---|
| `format_inr(amount)` | `1,00,000.00` |
| `amount_in_words_inr(amount)` | `Rupees One Thousand Only` |
| `ordinal(n)` | `1st`, `2nd` |
| `format_date_range(start, end)` | `15/10/2026 - 16/10/2026` |
| `document_date`, `today_str` | today's date |

### Letterhead

Every club gets one generated letterhead (college logo, club logo, club name and college name). Templates
use a placeholder image in the header, which is swapped for the club's letterhead when a document is
made. Clubs edit the letterhead text in **Settings → Letterhead**.
