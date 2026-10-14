# Official Template Notes & Administrative Quirks

*Target Organization: ACM Student Chapter, SVNIT Surat*

---

## 1. Intentional Typos & Legacy Quirks

Per Section 3 (Rule 6) of the system specification, source wording must be faithfully preserved to match official administration templates. Do not silently "fix" these in official documents unless directed by faculty or chapter heads:

| Document | Erroneous / Legacy Text | Context | Expected Correct English |
| :--- | :--- | :--- | :--- |
| **Prize Money Receipt** & **Bill Certificate** | `SARDAR VALLABHBHAI NATIOINAL INSTITUTE OF TECHNOLOGY, SURAT` | Institution Header | *NATIONAL* |
| **Permission Letter** & **Prize Receipt** | `Mobile No.` | Signatory details | Standard spelling |
| **Approval Note** | `Moblie No.` | Faculty signatory blocks | Intentional legacy typo preserved strictly per sample |
| **Bill Certificate (Form BC-R)** | `“I, am ________________, personally satisfied...` | Certification sentence | Stray comma after "I" |
| **Bill Certificate (Form BC-R)** | `Code No . 6/52` | Header metadata | Stray space before dot |
| **Bill Certificate (Form BC-R)** | `NiL` | Default entries | *NIL* or *Nil* |

---

## 2. Accidental Trailing Blank Pages

The sample PDFs provided in `sample docs/` exhibit unintentional trailing blank pages produced by Microsoft Word spacing overflow:
- `Permission_public.pdf`: Page 2 contains only the header.
- `ACM_Sample_Submitted.pdf`: Page 3 contains only the header.
- `BIll_summary_public.pdf`: Page 3 contains only an empty page border.

**System Policy**:
All generated `.docx` and `.pdf` files are configured with tight paragraph margins and zero extra blank trailing paragraphs to guarantee that documents fit strictly on their intended pages without accidental blank page spillovers.
