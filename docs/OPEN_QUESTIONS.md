# Open Questions & Ambiguities Identified in PDF Sample Analysis

*Generated during PDF Document Analysis for DocumentGenerator*

---

### 1. Typo Preservation vs. Correction Policy
- **Background**: We discovered several distinct administrative typos and quirks in the official templates:
  - `SARDAR VALLABHBHAI NATIOINAL INSTITUTE OF TECHNOLOGY, SURAT` (misspelling of "NATIONAL" in `Prize Money Format 2026.pdf` and `Bill Certificate_public.pdf`).
  - `Moblie No.` under faculty signatures in `ACM_Sample_Submitted.pdf`.
  - `“I, am ________________, personally satisfied...` (erroneous comma after "I") in `Bill Certificate_public.pdf`.
  - `Code No . 6/52` (space before period) in `Bill Certificate_public.pdf`.
- **Question**: Should the document generator strictly reproduce these exact typos to guarantee 100% legacy fidelity with previously signed institute templates, or should it offer a configuration toggle (e.g., `preserve_legacy_typos: bool = True`) allowing users to generate clean versions?

---

### 2. Trailing Blank Page Elimination
- **Background**: 3 out of the 5 sample documents had accidental trailing blank pages:
  - `Permission_public.pdf` Page 2: Header only, blank body.
  - `ACM_Sample_Submitted.pdf` Page 3: Header only, blank body.
  - `BIll_summary_public.pdf` Page 3: Border frame only, completely blank.
- **Question**: Can we confirm that all generated DOCX documents should strictly eliminate these overflow pages and fit cleanly into their intended target page counts (`Permission`: 1 page, `Prize Money`: 1 page, `Event Approval`: 2 pages, `Bill Summary`: 2 pages, `Bill Certificate`: 2 pages)?

---

### 3. Image Assets Strategy & Extraction
- **Background**: The documents require three core graphical assets:
  - SVNIT Full Color Seal (`svnit_crest_color.png`)
  - SVNIT Monochrome/Grayscale Seal (`svnit_crest_mono.png`)
  - ACM Diamond Blue Badge (`acm_logo_blue.png`)
- **Question**: Are high-resolution official vector/PNG master assets available in the SVNIT ACM repository, or should we clean and upscale the embedded raster assets extracted from the sample PDFs?

---

### 4. Hardcoded Date and Year Fields
- **Background**: In `Prize Money Format 2026.pdf`, the date field is printed with a hardcoded year: `held on    /    / 2026 at ___________________`.
- **Question**: Should the template generator dynamically inject the target year from the event date (e.g., `held on __/__/{{ year }}`), or keep `2026` hardcoded when generating fillable blank forms?

---

### 5. Multi-Language Font Rendering Across Operating Systems
- **Background**: `ACM_Sample_Submitted.pdf` includes Gujarati (`સરદાર વલ્લભભાઈ...`) and Hindi (`सरदार वल्लभभाई...`). `Bill Certificate_public.pdf` and `Prize Money Format 2026.pdf` include Hindi.
- **Question**: What is the target production deployment environment (Windows server, Linux container, or local desktop)? On Linux/server environments, standard Windows fonts (Arial, Times New Roman, Mangal, Shruti) may not be installed. What fallback fonts (e.g., Google Noto Sans Devanagari, Noto Sans Gujarati, Liberation Serif) should be specified?

---

### 6. Dynamic Table Growth & Multi-Page Pagination
- **Background**:
  - `Bill Certificate (Form BC-R)` Page 1 contains the purchased equipment table.
  - `BIll_summary_public.pdf` Page 1 contains the itemized bill summary, and Page 2 contains account details.
- **Question**: If an event has more items than fit on Page 1 (e.g., 10+ items or 15+ prize winners), what is the expected pagination behavior? Should the table flow dynamically with repeating header rows, or should additional sub-pages be attached?

---

### 7. Signatory Hierarchy & Roles
- **Background**: Across the 5 documents, role labels vary slightly:
  - Student leader: `Chairperson , ACM` (Permission), `Student Head` (Bill Summary), `Signature of Student Head` (Event Approval).
  - Faculty head: `Chairman , ACM` (Permission), `Faculty Chairman` (Bill Summary), `Signature of Faculty Chairman` (Event Approval), `Faculty Chairman/Co-Chairman` (Form BC-R).
- **Question**: Should the system define a canonical role enumeration (`STUDENT_HEAD`, `STUDENT_SECRETARY`, `FACULTY_CHAIRMAN`, `FACULTY_CO_CHAIRMAN`, `HOD_CSE`, `DEAN_SW`) with template-specific title rendering mappings?

---

### 8. Bill Certificate 'for Rs.' Line: Subtotal vs. Total Including Tax
- **Background**: On Form BC-R Page 1, the meta line reads:
  `Original Approval Note/Comparative Statement attached herewith/sent with bill No. {invoice_no} dtd.: {invoice_date} for Rs. {amount} of M/s. {supplier_name}`
  Later on the same page, under `SUPPLIER DETAILS`, the table lists:
  `Amount (Rs.): {bill_total_with_tax}`
- **Question**: Should the top meta line `for Rs.` always reflect the final invoice total including taxes (e.g. ₹944.00, matching `SUPPLIER DETAILS Amount`), or should it reflect the pre-tax item cost subtotal (e.g. ₹800.00)?
- **Current Implementation**: Updated per W3.2 to use the grand total including taxes (`bill_total_with_tax`), guaranteeing identical figures across both locations on Page 1.

