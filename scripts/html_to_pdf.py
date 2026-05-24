"""Chuyển file HTML sang PDF."""

from pathlib import Path
import sys

def html_to_pdf(html_path: str, pdf_path: str = None):
    """Chuyển HTML sang PDF dùng WeasyPrint."""
    try:
        from weasyprint import HTML, CSS
    except ImportError:
        print("Đang cài đặt weasyprint...")
        import subprocess
        subprocess.run([sys.executable, "-m", "pip", "install", "weasyprint"], check=True)
        from weasyprint import HTML, CSS
    
    html_file = Path(html_path)
    if not html_file.exists():
        print(f"❌ Không tìm thấy file: {html_path}")
        return
    
    if pdf_path is None:
        pdf_path = html_file.with_suffix('.pdf')
    
    print(f"🔄 Đang chuyển {html_path} → {pdf_path}...")
    
    # Chuyển sang PDF
    HTML(filename=str(html_path)).write_pdf(str(pdf_path))
    
    print(f"✅ Đã tạo PDF: {pdf_path}")
    return pdf_path


if __name__ == "__main__":
    # Mặc định chuyển file mockup
    html_file = Path(__file__).parent.parent / "docs" / "mockup_bc_tu_pgd.html"
    pdf_file = html_file.with_suffix('.pdf')
    
    html_to_pdf(str(html_file), str(pdf_file))
