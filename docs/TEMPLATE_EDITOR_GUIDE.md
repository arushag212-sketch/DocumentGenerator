# SVNIT ClubDocs — TipTap Template Editor Guide

Welcome to the **TipTap Visual Template Editor** in SVNIT ClubDocs. This Word-like visual editor empowers club officers to design, edit, and publish official document templates without writing raw code or dealing with raw Jinja syntax.

---

## 📐 Layout & Workspace

- **A4 Desk View**: The editor is rendered as a clean, paginated A4 page (210mm × 297mm) with clear margins and shadows.
- **Top Bar**:
  - **Template Title & Category**: Rename your template draft and choose its stage (Pre-Event, Post-Event, Meeting).
  - **Status Pill**: Real-time indicator displaying `Saved` (green), `Saving...` (yellow), or `Unsaved changes` (gray).
  - **Live Preview Button**: Compiles the draft with mock data and opens an instant LibreOffice PDF preview modal.
  - **Publish Button**: Validates all field identifiers and publishes the new version to the club catalog.
- **Right Sidebar (Fields Palette)**:
  - Searchable list of all known variables categorized by Event, Signatories, Club Settings, and Tables.
  - One-click **Insert** button places the field chip directly at your current cursor location.

---

## ⚡ Slash Commands (`/`)

Press `/` at the start of any new paragraph or blank line to open the interactive command palette:

| Command | Action | Description |
| :--- | :--- | :--- |
| `/h1` or `/heading1` | **Heading 1** | Large section heading (20pt bold) |
| `/h2` or `/heading2` | **Heading 2** | Subsection heading (16pt bold) |
| `/h3` or `/heading3` | **Heading 3** | Minor subheading (14pt bold) |
| `/infotable` | **Info Table (Key-Value)** | Inserts a 2-column key-value table preset for event parameters |
| `/repeatingtable` | **Repeating Table** | Inserts a dynamic table with header and repeating template row |
| `/signatures` | **Signature Grid** | Inserts a 2×2 grid with designated signatory titles |
| `/table` | **Standard Table** | Inserts a customizable 3×3 table grid |
| `/field` | **Insert Field** | Prompts for a variable name and inserts a draggable field chip |
| `/bullet` | **Bullet List** | Unordered list (`* ` or `- `) |
| `/number` | **Numbered List** | Ordered numbered list (`1. `) |
| `/pagebreak` | **Page Break** | Inserts a visible A4 page break boundary |

---

## 🔤 Formatting & Bubble Menu

Highlight any text in the editor to reveal the **Floating Bubble Toolbar**:
- **Bold (`Ctrl+B`)**: Applies heavy weight font.
- **Italic (`Ctrl+I`)**: Applies slanted emphasis.
- **Underline (`Ctrl+U`)**: Applies official document underlining.
- **Strike (`Ctrl+Shift+X`)**: Strikes through text.
- **Insert Field**: Converts the selected text or cursor position into an official field placeholder chip.

---

## 📊 Table Editing Capabilities

Every table in the rebuilt editor is built on native table nodes (`TableKit`):

1. **Direct In-Cell Editing**:
   - Click into **any cell** to type directly.
   - Cells support rich text (bold, italic, links) and embedded field chips.
2. **Navigation**:
   - `Tab`: Jump to the next table cell (or creates a new row if at the end).
   - `Shift + Tab`: Jump to the previous cell.
3. **Table Controls Toolbar**:
   - Click inside any table to access table manipulation actions:
     - **Add Row Above / Below**
     - **Delete Row**
     - **Add Column Before / After**
     - **Delete Column**
     - **Toggle Header Row**
     - **Delete Table**
4. **Table Presets**:
   - **Info Table**: Pre-configured with left column light-gray label background and right column editable data.
   - **Repeating Table**: The first row serves as the header; the second row acts as the template row that iterates over list objects (such as `budget_items.description`, `budget_items.amount`, or `winners.name`).
   - **Signature Grid**: Pre-formatted 2×2 layout with sufficient spacing for physical ink signatures, seals, and designations.

---

## 🧩 Field Chips (`{{ variable_name }}`)

- Field chips appear as distinctive rounded badges (e.g. `{{ event_name }}`) within the editor text.
- When generating official documents:
  - The engine replaces each chip with the real data submitted in the Home tab.
  - User-entered text is treated strictly as **DATA**: any braces or special characters in user text are automatically escaped.
  - Identifiers must follow standard identifier whitelist rules (`^[a-z][a-z0-9_]{0,39}$` or dot notation for table lists).

---

## 🛡️ Safety & Reliability

- **Autosave with Debounce**: Changes are debounced by 1 second and saved to the server. You will never lose edits from accidental navigation or browser refreshes.
- **Version Number Conflict Safety**: The editor tracks `version_no`. If another tab or user updates the template, a friendly conflict prompt will warn you before overwriting.
- **Error Boundary**: If a rendering error occurs in TipTap, the editor safely displays a friendly recovery screen:
  > *"Something went wrong in the editor. Your last saved draft is safe."*  
  with a **Reload** button to restore your work without blanking the page.
- **Live LibreOffice Preview**: Click **Live Preview** at any time to verify how the document will look when compiled to Microsoft Word `.docx` and converted to official PDF.
