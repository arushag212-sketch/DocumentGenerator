"""Extract images (logos, crests) from sample PDF documents using PyMuPDF."""

import fitz  # PyMuPDF
from pathlib import Path


def extract_images(pdf_path: str | Path, output_dir: str | Path, prefix: str = ""):
    """Extract all images from a PDF file."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    doc = fitz.open(str(pdf_path))
    extracted = []
    
    for page_num in range(len(doc)):
        page = doc[page_num]
        images = page.get_images(full=True)
        
        for img_idx, img_info in enumerate(images):
            xref = img_info[0]
            try:
                pix = fitz.Pixmap(doc, xref)
                
                # Convert CMYK to RGB if needed
                if pix.n > 4:
                    pix = fitz.Pixmap(fitz.csRGB, pix)
                elif pix.n == 4:
                    pix = fitz.Pixmap(fitz.csRGB, pix)
                
                filename = f"{prefix}page{page_num + 1}_img{img_idx + 1}.png"
                filepath = output_dir / filename
                pix.save(str(filepath))
                extracted.append(filepath)
                print(f"  Extracted: {filepath} ({pix.width}x{pix.height})")
            except Exception as e:
                print(f"  Failed to extract image {xref}: {e}")
    
    doc.close()
    return extracted


def main():
    samples_dir = Path("sample docs")
    assets_dir = Path("assets")
    
    pdfs = [
        ("Permission_public.pdf", "permission_"),
        ("Prize Money Format 2026.pdf", "prize_"),
        ("ACM_Sample_Submitted.pdf", "approval_"),
        ("BIll_summary_public.pdf", "billsummary_"),
        ("Bill Certificate_public.pdf", "billcert_"),
    ]
    
    for pdf_name, prefix in pdfs:
        pdf_path = samples_dir / pdf_name
        if pdf_path.exists():
            print(f"\nExtracting from: {pdf_name}")
            extract_images(pdf_path, assets_dir, prefix)
        else:
            print(f"  NOT FOUND: {pdf_path}")
    
    print("\nDone! Check the assets/ directory.")


if __name__ == "__main__":
    main()
