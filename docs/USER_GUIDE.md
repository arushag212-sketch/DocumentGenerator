# SVNIT ClubDocs — Non-Technical Club Member User Guide

Welcome to **SVNIT ClubDocs**! This non-technical guide explains step-by-step how any club leader, secretary, or treasurer can create accounts, generate official packages, create templates, and download official PDFs without manual Word formatting or numbering errors.

---

## 1. Create an Account & Pick Your Club

![Registration Screen](screenshots/w7/01_register_form.png)

### Creating an Account
1. Open the portal at [http://localhost:8000](http://localhost:8000).
2. If you received an invite link (e.g. `http://localhost:8000/?invite=ACM-123456`), open it directly. Your club and assigned role are recognized automatically.
3. Otherwise, click **Sign Up**, enter your full name, SVNIT email (`@svnit.ac.in`), and password.
4. Select your club (e.g. *Association for Computing Machinery (ACM)*). If you are creating a new club, type the new club name and chapter code.
5. Choose your position (Student Head, Secretary, Treasurer, Committee Member, or Other).
6. Click **Submit**. If joining an existing club, a pending join request is routed to your club administrator for quick 1-click approval.

---

## 2. Describe What You Need (Home)

![Home Screen](screenshots/phase4/01_home_initial.png)

1. Navigate to the **Home** tab.
2. In the central box labeled **"What do you need?"**, type your requirements in plain conversational language:
   > *"We are organizing TechNova on 15 Nov 2026, 10 AM to 5 PM in the CSE Seminar Hall. We need permission, sanction note with 25000 budget, and cash prizes of 5000 and 3000."*
3. Or tap one of the suggested example chips below the text box.
4. Click **Understand & Suggest Documents**.

---

## 3. Review What Was Understood & Answer Questions

![Understood Details](screenshots/phase4/03_ready_to_generate.png)

The engine extracts details automatically into clean, editable cards:
- **Event Name & Purpose**: Review and edit if needed.
- **Date & Timings**: Handled via clean calendar pickers (`DD/MM/YYYY`) and native time pickers (e.g. `10:00 AM` to `05:00 PM`).
- **Venue**: Picked from the SVNIT venue directory or select "Other".
- **Money & Budget**: Displayed with Indian grouping (e.g. `₹25,000.00`).
- **AI-Suggested Content**: Any AI-drafted description or summary is tagged `[AI-drafted, review]`. Click **Accept AI Draft** to approve it.
- **Reserve Serial Numbers**: Tick the checkbox confirming the sequential reference numbers (e.g. `ACM/26-27/ROOM/001`) that will be officially reserved upon generation.

---

## 4. Generate & Download Your Documents

![Batch Complete](screenshots/phase4/04_batch_generated_success.png)

1. Click **Generate Documents**.
2. Within seconds:
   - Official sequential reference numbers are allocated without collisions.
   - Word DOCX files are compiled.
   - SVNIT-compliant PDFs are generated via headless LibreOffice.
   - A single coordinated ZIP archive is assembled.
3. On the result screen, you can:
   - Preview individual PDFs directly in the browser.
   - Download individual `.pdf` or `.docx` files.
   - Click **Download Batch ZIP** to download the entire package at once.

---

## 5. Finding Past Documents

1. Click **My Documents** in the navigation bar.
2. Search by reference number (`ACM/26-27/ROOM/001`) or event title (`TechNova`).
3. Click any document to view its creation history, author details, and download fresh copies.

---

## 6. Creating a Template by Describing It (AI)

1. Click **Templates** in the navigation bar.
2. In the prominent **"Create a template by describing it"** card:
   - Type your requirements: e.g. *"A permission letter to the Dean of Student Welfare requesting sound system permission for our open-air amphitheater cultural night."*
3. Click **Draft with AI**.
4. The system drafts the structure, fields, and letterhead layout, and opens it directly in the visual editor for your inspection and review.

---

## 7. Building or Customizing a Template in Studio

![Studio Editor View](screenshots/part1_editor_smoke.png)

1. On the **Templates** tab, click **New Blank Template** or click **Customize** on any standard template.
2. The Studio editor opens in a modern, 3-pane responsive layout:
   - **Left Palette**: Drag blocks, clauses, tables, and club logos directly onto the canvas.
   - **Center A4 Canvas**: Paginated A4 view with drop shadows, live word count, and zoom controls.
   - **Right Tabs**: Switch between **AI Chat**, **Fields**, **Design**, and **Checks**.

---

## 8. AI Chat Copilot (Editing by Talking to Your Document)

![AI Chat Copilot](screenshots/part2_chat_copilot.png)

1. Open the **AI Chat** tab on the right side of the editor.
2. Type conversational instructions: e.g. *"Make the heading SVNIT blue and centered"*, *"Add a signature box for the faculty advisor"*, or *"Convert this list into a 3-column table"*.
3. Click quick-action chips for common tasks:
   - **Make it Formal**: Upgrades wording to institute standards.
   - **Fix Spelling**: Corrects typos and grammatical mistakes.
   - **Add Signatures**: Inserts official signatory blocks.
   - **Translate to Hindi / Gujarati**: Translates text while preserving field placeholders.
4. Review the change summary and click **Apply** to accept or **Reject** to discard. Every set of changes can be completely undone in one step (`Ctrl+Z`).

---

## 9. Drag & Drop Direct Manipulation

![Drag and Drop](screenshots/part3_drag_drop.png)

- **Block Reordering**: Hover over any paragraph, table, or signature grid to reveal the six-dot drag handle (`::`) and drag it to a new location, or press `Alt + ArrowUp/Down`.
- **Palette Drops**: Drag elements from the Left Palette (tables, clauses, club crests) and drop them anywhere on the page.
- **Field Chips**: Drag variable chips from the Right "Fields" panel into text or table cells.
- **In-Table Controls**: Click inside any table to access floating row and column reordering buttons, or merge and split cells.

---

## 10. Design Studio: Curated Themes & Self-Hosted Typography

![Design Studio](screenshots/part4_design_studio.png)

1. Open the **Design** tab on the right panel.
2. Select from 6 curated institute themes:
   - **Official Navy**, **SVNIT Blue & Gold**, **Classic Black & White**, **Modern Green**, **Warm Sunset**, **Minimal Grey**.
3. Customize typography with 10 self-hosted open-license fonts (Tinos, Merriweather, Playfair Display, Roboto, Open Sans, Montserrat, Roboto Mono, Noto Sans Devanagari, Noto Sans Gujarati).
4. Monitor readability with the built-in **WCAG Contrast Checker** (green `AA Pass` badge).
5. Configure margins, page borders, and subtle watermarks (e.g. *DRAFT* or *SAMPLE*).

---

## 11. AI Template Creation Wizard & Document Importer

![Template Wizard](screenshots/part5_ai_everywhere.png)

- **Template Creation Wizard**:
  - In Template Gallery, click **"Template Creation Wizard"**.
  - Type what document you need in plain words: e.g. *"Campus Venue & Lab Booking Permission"*.
  - Answer up to 3 clarifying question chips (Purpose, Audience, Tone).
  - Click **"Build My Template"**: a complete designed template opens in the editor in seconds.
- **Notice & Letter Importer**:
  - In Template Gallery, click **"Import Template"**.
  - Paste existing text or upload a `.docx` file: the engine automatically identifies variable placeholders and formats the document into blocks.
- **Document Checker & One-Click Fixes**:
  - Switch to the **Checks** tab to audit your draft against institutional standards (unfilled official wording, date consistency, low contrast).
  - Click **Fix** next to any issue to repair it instantly.

---

## 12. Sharing & Club Collaboration

- Club administrators can invite team members by navigating to **Club Settings → Members** and clicking **Invite Member**.
- Copy the unique invite link and share it over WhatsApp or email.
- New members join with pre-assigned permissions, ready to generate documents instantly.
