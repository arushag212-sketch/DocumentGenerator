# Guide: Authoring & Customizing DOCX Templates

This document explains how to edit, customize, or create new DOCX templates for the ACM SVNIT Document Generator.

---

## 1. Core Principle
Templates are real Microsoft Word (`.docx`) files combined with a `schema.yaml` definition file located in `templates/<template_id>/`.
All rendering is powered by `docxtpl` using Jinja2 syntax.

---

## 2. Best Practices for Authoring in Microsoft Word

### A. Tag Splitting Prevention (Crucial)
Microsoft Word frequently splits text runs when you type or edit. If Word saves `{{` in one XML run and `event_name` in another, Jinja2 will fail to detect the tag.

- **Tip 1**: Always type each template tag (`{{ variable }}`) in a single uninterrupted burst.
- **Tip 2**: If copying and pasting, paste as **Unformatted Plain Text** (`Ctrl + Shift + V`).
- **Tip 3**: Run the template validator immediately after saving:
  ```bash
  python -m docgen.cli validate-templates
  ```

### B. Table Loops Syntax
When repeating rows in a table (e.g. winners, budget items, purchased goods):
1. **Loop Start Row**: Insert a dedicated row with:
   ```jinja
   {%tr for item in items %}
   ```
2. **Data Row**: Add your columns containing:
   ```jinja
   {{ loop.index }} | {{ item.name }} | {{ item.amount }}
   ```
3. **Loop End Row**: Insert a dedicated closing row with:
   ```jinja
   {%tr endfor %}
   ```
`docxtpl` will dynamically eliminate the start/end wrapper rows and repeat the data row cleanly for each item.

---

## 3. Letterhead & Branding
- Templates use standard A4 dimensions with `0.75 in` or `0.6 in` margins.
- Official institutional logos are stored in `assets/`.
- Dual logos (SVNIT Seal on left, ACM Badge on right) belong inside the Word Header section inside a borderless table.

---

## 4. Computed Functions Available in Templates
You can use any of the registered functions inside tags or expressions:
- `{{ format_inr(amount) }}`: Formats currency with Indian numbering (e.g. `1,00,000.00`).
- `{{ amount_in_words_inr(amount) }}`: Converts numbers to words (e.g. `Rupees One Thousand Only`).
- `{{ ordinal(n) }}`: Ordinal suffix generator (`1st`, `2nd`, `3rd`).
- `{{ format_date_range(start, end) }}`: Formats single or multi-day date ranges cleanly.
- `{{ document_date }}` / `{{ today_str }}`: Current formatted date.
