import sys
from pathlib import Path

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import fitz  # PyMuPDF
from PIL import Image

from decimal import Decimal
from docgen.config import load_config
from docgen.functions import fn_amount_in_words_inr, fn_format_inr, fn_sum
from docgen.renderer import Renderer
from tests.fixtures.sih_event import get_sih_fixture


def rasterize_pdf_first_page(pdf_path: Path, dpi: int = 150) -> Image.Image:
    """Rasterize the first page of a PDF to a PIL Image."""
    doc = fitz.open(str(pdf_path))
    page = doc[0]
    pix = page.get_pixmap(dpi=dpi)
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    doc.close()
    return img


def create_side_by_side(sample_pdf: Path, rendered_pdf: Path, output_png: Path):
    """Combine first page of sample PDF and rendered PDF side-by-side."""
    if not sample_pdf.exists() or not rendered_pdf.exists():
        return
    output_png.parent.mkdir(parents=True, exist_ok=True)
    img_sample = rasterize_pdf_first_page(sample_pdf)
    img_rendered = rasterize_pdf_first_page(rendered_pdf)

    # Resize to match height if different
    target_height = max(img_sample.height, img_rendered.height)
    if img_sample.height != target_height:
        new_w = int(img_sample.width * (target_height / img_sample.height))
        img_sample = img_sample.resize((new_w, target_height), Image.Resampling.LANCZOS)
    if img_rendered.height != target_height:
        new_w = int(img_rendered.width * (target_height / img_rendered.height))
        img_rendered = img_rendered.resize((new_w, target_height), Image.Resampling.LANCZOS)

    # Create canvas
    total_width = img_sample.width + img_rendered.width + 20
    canvas = Image.new("RGB", (total_width, target_height), (240, 240, 240))
    canvas.paste(img_sample, (0, 0))
    canvas.paste(img_rendered, (img_sample.width + 20, 0))
    canvas.save(str(output_png))
    print(f"  [VISUAL] Saved comparison: {output_png}")


def main():
    print("=" * 70)
    print(" RENDERING ALL DOCUMENTS FROM SIH FIXTURE & GENERATING VISUAL COMPARISONS")
    print("=" * 70)

    config = load_config()
    renderer = Renderer(config=config, outputs_dir="outputs/sih_test")
    event = get_sih_fixture()

    # 1. Permission Letter
    print("\n1. Rendering Permission Letter...")
    res_perm = renderer.render("permission_letter", event, convert_pdf=True)
    print(f"   DOCX: {res_perm.docx_path}")
    print(f"   PDF:  {res_perm.pdf_path}")
    create_side_by_side(
        Path("sample docs/Permission_public.pdf"),
        res_perm.pdf_path,
        Path("tests/visual/permission_letter_comparison.png")
    )

    # 2. Approval Note
    print("\n2. Rendering Approval Note...")
    res_appr = renderer.render("approval_note", event, convert_pdf=True)
    print(f"   DOCX: {res_appr.docx_path}")
    print(f"   PDF:  {res_appr.pdf_path}")
    create_side_by_side(
        Path("sample docs/ACM_Sample_Submitted.pdf"),
        res_appr.pdf_path,
        Path("tests/visual/approval_note_comparison.png")
    )

    # 3. Prize Money Receipt (first winner Aarav)
    print("\n3. Rendering Prize Money Receipt...")
    w1 = event.winners[0]
    w1_ctx = {
        "winner_name": w1.name,
        "winner_position": w1.position,
        "winner_amount": fn_format_inr(w1.amount),
        "winner_amount_words": fn_amount_in_words_inr(w1.amount),
        "winner_roll_no": w1.roll_no,
        "winner_course_semester": w1.course_semester,
        "winner_mobile": w1.mobile,
        "winner_bank_name_as_per_bank": w1.bank.name_as_per_bank,
        "winner_bank_name": w1.bank.bank_name,
        "winner_bank_branch": w1.bank.branch,
        "winner_account_no": w1.bank.account_no,
        "winner_ifsc": w1.bank.ifsc,
        "winner_pan": w1.bank.pan,
        "sr_no": 1,
    }
    res_prize = renderer.render("prize_money_receipt", event, extra_context=w1_ctx, convert_pdf=True)
    print(f"   DOCX: {res_prize.docx_path}")
    print(f"   PDF:  {res_prize.pdf_path}")
    create_side_by_side(
        Path("sample docs/Prize Money Format 2026.pdf"),
        res_prize.pdf_path,
        Path("tests/visual/prize_money_receipt_comparison.png")
    )

    # 4. Bill Summary
    print("\n4. Rendering Bill Summary...")
    res_billsum = renderer.render("bill_summary", event, convert_pdf=True)
    print(f"   DOCX: {res_billsum.docx_path}")
    print(f"   PDF:  {res_billsum.pdf_path}")
    create_side_by_side(
        Path("sample docs/BIll_summary_public.pdf"),
        res_billsum.pdf_path,
        Path("tests/visual/bill_summary_comparison.png")
    )

    # 5. Bill Certificate (Form BC-R)
    print("\n5. Rendering Bill Certificate (Form BC-R)...")
    b1 = event.bills[0]
    b1_ctx = {
        "approval_note_no": event.approval_note.no,
        "approval_note_date": event.approval_note.date,
        "ref_no": "BILL-091",
        "bill_amount": fn_format_inr(Decimal("800.00")),
        "supplier_name": b1.supplier.name,
        "supplier_gst": b1.supplier.gst_no,
        "invoice_no": b1.invoice_no,
        "invoice_date": b1.invoice_date,
        "bill_items": [{"name": i.name, "qty": i.qty, "unit_cost": fn_format_inr(i.unit_cost), "line_total": fn_format_inr(i.qty * i.unit_cost)} for i in b1.items],
        "tax_type": b1.tax_type,
        "tax_amount": fn_format_inr(b1.tax_rate_or_amount),
        "certifier_name": "Demo Student Head",
        "payment_party": b1.payment.party,
        "payment_account_no": b1.payment.account_no,
        "payment_holder": b1.payment.holder,
        "payment_bank": b1.payment.bank,
        "payment_branch": b1.payment.branch,
        "payment_ifsc": b1.payment.ifsc,
        "bill_total": fn_format_inr(Decimal("800.00")),
        "bill_total_with_tax": fn_format_inr(Decimal("944.00")),
    }
    res_billcert = renderer.render("bill_certificate", event, extra_context=b1_ctx, convert_pdf=True)
    print(f"   DOCX: {res_billcert.docx_path}")
    print(f"   PDF:  {res_billcert.pdf_path}")
    create_side_by_side(
        Path("sample docs/Bill Certificate_public.pdf"),
        res_billcert.pdf_path,
        Path("tests/visual/bill_certificate_comparison.png")
    )

    # 6. Minutes of Meeting (MoM)
    print("\n6. Rendering Minutes of Meeting (MoM)...")
    mom_ctx = {
        "meeting_title": event.meeting.title,
        "ref_no": event.meeting.ref_no,
        "meeting_date": event.meeting.date,
        "meeting_start_time": "05:00 PM",
        "meeting_end_time": "06:30 PM",
        "chaired_by": event.meeting.chaired_by,
        "attendees": event.meeting.attendees,
        "absentees": event.meeting.absentees,
        "agenda_items": [{"topic": a.topic, "discussion": a.discussion, "decision": a.decision} for a in event.meeting.agenda_items],
        "action_items": [{"task": ac.task, "owner": ac.owner, "deadline": ac.deadline} for ac in event.meeting.action_items],
        "next_meeting_date": "18 September 2026",
        "prepared_by": event.meeting.prepared_by,
        "approved_by": event.meeting.approved_by,
    }
    res_mom = renderer.render("mom", event, extra_context=mom_ctx, convert_pdf=True)
    print(f"   DOCX: {res_mom.docx_path}")
    print(f"   PDF:  {res_mom.pdf_path}")

    print("\n" + "=" * 70)
    print(" ALL 6 DOCUMENTS RENDERED & SIDE-BY-SIDE VISUAL COMPARISONS GENERATED!")
    print("=" * 70)


if __name__ == "__main__":
    main()
