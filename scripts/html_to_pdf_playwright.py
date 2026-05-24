"""Chuyển HTML sang PDF dùng Playwright + Chrome."""

import subprocess
import sys
from pathlib import Path

def install_playwright():
    """Cài đặt playwright và browser binaries."""
    print("🔄 Đang cài đặt playwright...")
    subprocess.run([sys.executable, "-m", "pip", "install", "playwright"], check=True)
    print("🔄 Đang cài đặt browser binaries...")
    subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)
    print("✅ Cài đặt hoàn tất!")

def html_to_pdf(html_path: str, pdf_path: str = None):
    """Chuyển HTML sang PDF dùng Playwright."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        install_playwright()
        from playwright.sync_api import sync_playwright
    
    html_file = Path(html_path)
    if not html_file.exists():
        print(f"❌ Không tìm thấy file: {html_path}")
        return
    
    if pdf_path is None:
        pdf_path = html_file.with_suffix('.pdf')
    
    # Chuyển đường dẫn sang file:// URL
    abs_path = html_file.resolve().as_posix()
    file_url = f"file:///{abs_path}"
    
    print(f"🔄 Đang chuyển {html_file.name} → PDF...")
    
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(file_url, wait_until="networkidle")
        
        # Tùy chỉnh PDF
        page.pdf(
            path=str(pdf_path),
            format="A4",
            print_background=True,
            margin={"top": "20mm", "bottom": "20mm", "left": "15mm", "right": "15mm"}
        )
        browser.close()
    
    print(f"✅ Đã tạo PDF: {pdf_path}")
    return pdf_path


if __name__ == "__main__":
    # Mặc định chuyển file mockup
    html_file = Path(__file__).parent.parent / "docs" / "mockup_bc_tu_pgd.html"
    pdf_file = html_file.with_suffix('.pdf')
    
    html_to_pdf(str(html_file), str(pdf_file))
