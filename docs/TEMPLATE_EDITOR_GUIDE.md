# SVNIT ClubDocs — Studio Template Editor & Design Guide

The **SVNIT ClubDocs Studio** is a professional, modular, AI-assisted document template editor designed specifically for student chapters and clubs at **Sardar Vallabhbhai National Institute of Technology (SVNIT), Surat**.

---

## 1. 📐 Three-Pane Responsive Workspace

The Studio is organized into three ergonomic workspaces:

1. **Left Palette (Collapsible)**:
   - **Blocks**: Headings (H1, H2, H3), Paragraphs, Official Clauses, Page Breaks.
   - **Tables**: Standard Tables, Key-Value Info Tables, Repeating Tables (e.g. Budget, Vouchers, Attendees).
   - **Signatures**: 2×2 or 1×2 Official Signatory Grids.
   - **Assets & Logos**: Drag SVNIT bilingual header, club crest, or uploaded club logos.
2. **Center Canvas (A4 Desk View)**:
   - Paginated A4 layout (210mm × 297mm) rendered with realistic page boundaries and drop shadows.
   - Zoom controls (50% to 150%) and live word count.
   - Floating Slash Command Menu (`/`) and empty-line quick adder (`+`).
   - Floating Bubble Formatting Menu (Bold, Italic, Underline, Strike, Convert to Field Chip).
3. **Right Tabs Panel**:
   - **AI Chat (Default)**: Interactive copilot that talks to your template.
   - **Fields**: Variable catalog (search, filter by essential/optional, toggle required/sensitive, delete).
   - **Design**: Curated themes, self-hosted typography, color pickers, margins, watermark, and WCAG contrast check.
   - **Checks**: Document auditor detecting unfilled official placeholders, inconsistent dates, and contrast issues.

---

## 2. 🖱️ Drag-and-Drop Direct Manipulation

Every element on the canvas can be manipulated directly:

- **Block Drag Handles**:
  - Hover over any block to reveal the six-dot drag handle (`::`).
  - Drag up or down to reorder paragraphs, headings, tables, or signature grids.
  - **Keyboard Alternative**: Press `Alt + ArrowUp` or `Alt + ArrowDown` on any focused block to shift it immediately.
- **Palette Drag & Drop**:
  - Drag blocks, clauses, or signature grids from the Left Palette directly onto the canvas.
  - Drop indicator lines display exactly where the block will land.
- **Field Chip Placement**:
  - Drag field chips from the Right "Fields" panel into any paragraph or table cell.
  - Drag existing chips on canvas to move them to a new sentence or cell.
- **Table Controls (In-Table Floating Toolbar)**:
  - **Reorder Rows**: Move row up or down with a single click.
  - **Reorder Columns**: Move column left or right.
  - **Cell Merging**: Select multiple cells and click "Merge Cells" or "Split Cell".
- **Image & Logo Controls**:
  - Click any image or logo to open the **Image Block Popover**.
  - Wrapping modes: `Inline`, `Behind text` (watermark style), or `In front of text`.
  - Alignment presets: `Left`, `Center`, `Right`.
  - Dimensions: `120px`, `240px`, `360px`, `100%`.

---

## 3. 🤖 AI Chat Copilot (Natural-Language Template Editing)

The Right-hand AI Chat Copilot understands document editing instructions and executes them as atomic, single-undo transactions:

### Supported Actions (24 Atomic Actions)
- **Document Structure**: `set_title`, `set_description`, `insert_block`, `update_block`, `delete_block`, `move_block`, `duplicate_block`.
- **Styling**: `set_text_style` (font, size, color, bold, alignment), `set_block_style` (background, border, padding).
- **Themes & Layout**: `set_theme`, `set_page` (orientation, margins, background, border, watermark).
- **Field Management**: `add_field`, `rename_field`, `set_field_property` (required, essential, sensitive, ask-text), `insert_chip`, `insert_clause`.
- **Tables**: `add_table_column`, `add_table_row`, `set_table_total`.
- **Text & Language**: `rewrite_text`, `translate_text`, `proofread_text`, `ask_clarifying_question`.

### Safety & Guardrails
- **Preview & Apply**: Every AI reply shows a summary of proposed actions and a **Preview of Changes** with **Apply** and **Reject** buttons.
- **Single-Step Undo**: Pressing `Undo` (`Ctrl+Z`) reverts the entire set of AI changes in one step.
- **AI-Suggested Tagging**: All AI-authored blocks are labeled "AI-suggested" until explicitly reviewed and accepted before publishing.
- **Official Wording Protection**: The AI never fabricates approval or sanction clauses; it inserts an `"Add official wording here"` placeholder.
- **Prompt-Injection Resistance**: Jinja delimiters (`{{`, `{%`) are automatically escaped into data literals.
- **Offline Fallback**: When Gemini API is unavailable or unconfigured, the copilot automatically falls back to an offline rule-based assistant.

---

## 4. 🎨 Design Studio (Fonts, Themes, & Contrast)

The **Design** tab allows club officers to create distinctive club document designs without compromising printability:

### 10 Self-Hosted Open-License Fonts
All fonts are bundled locally under `assets/fonts/` (no external CDNs) and registered for PDF embedding:
- **Formal Serif**: `Tinos` (Times-like), `Merriweather`, `Playfair Display`.
- **Modern Sans**: `Roboto`, `Open Sans`, `Montserrat`.
- **Monospace**: `Roboto Mono`.
- **Indic Scripts**: `Noto Sans Devanagari` (Hindi), `Noto Sans Gujarati` (Gujarati).

### Curated Document Themes
- **Official Navy**: Traditional institute formal palette with deep navy accents.
- **SVNIT Blue & Gold**: The institute signature identity featuring SVNIT gold headers.
- **Classic Black & White**: High-contrast, ink-saving minimalist design for bulk printouts.
- **Modern Green**: Clean emerald accent for environmental, IEEE, or technical club reports.
- **Warm Sunset**: Warm terracotta palette for cultural festivals and arts documents.
- **Minimal Grey**: Slate elegance with clean typography.

### WCAG 2.1 Contrast Guard & Ink Consumption
- Every theme and color selection runs live contrast ratio calculations (`calculateContrastRatio`).
- Displays an **AA Pass** badge or an amber **Low Contrast Warning** if text may be difficult to read.
- Warns users if page background colors are ink-heavy for physical printing.

---

## 5. 🚀 AI Everywhere (From Beginner to Final Document)

1. **Template Creation Wizard**:
   - In Template Gallery, click **"Template Creation Wizard"**.
   - Type what document you need in plain words: e.g. *"Lab permission letter for AI hackathon"*.
   - Answer up to 3 clarifying question chips (Purpose, Audience, Tone).
   - Click **"Build My Template"**: a complete designed template opens in the editor in seconds.
2. **Text & DOCX Importer**:
   - In Template Gallery, click **"Import Template"**.
   - Paste existing notice/letter text OR upload an existing `.docx` file.
   - The engine automatically detects variable parts (names, dates, amounts, venues), creates bracketed field chips, and imports paragraphs and tables.
3. **Text Improver**:
   - In Home Page or editor, click **"Improve text"** chips: `Formal Tone`, `Proofread & Fix`, `Shorten`, or `Expand`.
   - Inspect word-level before/after diffs before accepting.
4. **Document Checker & Audit**:
   - Open the **Checks** tab to audit your draft against institutional standards.
   - Detects unfilled official placeholders, inconsistent dates, missing essential fields, overlong paragraphs, and low contrast.
   - Click **"Fix"** next to any issue to resolve it automatically.
5. **Indic Language Translation**:
   - In the top toolbar, click the **Translate** dropdown (`Hindi (हिंदी)` or `Gujarati (ગુજરાતી)`).
   - Translates text paragraphs while keeping field chips and tables intact, and switches typography to Noto Sans Devanagari or Gujarati.
