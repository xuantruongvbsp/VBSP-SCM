"""Template-based document generation cho VBSP-SCM."""
from __future__ import annotations
import io, os, tempfile, logging
from pathlib import Path
from typing import Any

from docxtpl import DocxTemplate

from config import BASE_DIR

TEMPLATE_DIR = BASE_DIR / "templates"
logger = logging.getLogger(__name__)

# ── Tên file template chuẩn ──────────────────────────
TMPL_MAU06    = "mau_06td.docx"
TMPL_MAU06A   = "mau_06atd.docx"
TMPL_MAU15    = "mau_15td.docx"
TMPL_MAU16    = "mau_16td.docx"   # BB kiểm tra Tổ TK&VV
TMPL_KH_KT    = "ke_hoach_kt.docx"
TMPL_BB_XMN   = "bb_xac_minh_no.docx"

# ── Mẫu xử lý nợ rủi ro QĐ 62/2015/QĐ-TTg ──────────────────────────────────
TMPL_13XLN     = "mau_13xln.docx"     # Đề nghị khoanh nợ
TMPL_14XLN     = "mau_14xln.docx"     # Đề nghị xóa nợ
TMPL_TT_KHOANH = "to_trinh_khoanh_no.docx"  # Tờ trình khoanh nợ
TMPL_TT_XOA    = "to_trinh_xoa_no.docx"     # Tờ trình xóa nợ


def co_template(ten_mau: str) -> bool:
    """Kiểm tra file template có tồn tại không."""
    return (TEMPLATE_DIR / ten_mau).exists()


def dien_template(ten_mau: str, context: dict[str, Any]) -> bytes:
    """
    Điền dữ liệu vào template .docx → trả về bytes.
    Raise FileNotFoundError nếu template chưa có.
    """
    path = TEMPLATE_DIR / ten_mau
    if not path.exists():
        raise FileNotFoundError(
            f"Template '{ten_mau}' chưa có trong {TEMPLATE_DIR}. "
            f"Vui lòng upload template vào thư mục templates/."
        )
    tpl = DocxTemplate(str(path))
    tpl.render(context)
    buf = io.BytesIO()
    tpl.save(buf)
    return buf.getvalue()


def docx_to_pdf(docx_bytes: bytes) -> bytes | None:
    """
    Convert .docx → .pdf bằng docx2pdf (cần MS Word trên Windows).
    Trả về None nếu không convert được — caller tự xử lý fallback.
    """
    try:
        from docx2pdf import convert
        with tempfile.TemporaryDirectory() as tmp:
            inp = os.path.join(tmp, "input.docx")
            out = os.path.join(tmp, "input.pdf")
            with open(inp, "wb") as f:
                f.write(docx_bytes)
            convert(inp, out)
            if os.path.exists(out):
                with open(out, "rb") as f:
                    return f.read()
        return None
    except Exception as e:
        logger.warning(f"docx_to_pdf failed: {e}")
        return None


def docx_bytes_to_pdf(docx_bytes: bytes) -> bytes | None:
    """Convert .docx bytes → .pdf bytes dùng MS Word (Windows)."""
    try:
        from docx2pdf import convert
        import tempfile, os
        with tempfile.TemporaryDirectory() as tmp:
            inp = os.path.join(tmp, "input.docx")
            out = os.path.join(tmp, "input.pdf")
            with open(inp, "wb") as f:
                f.write(docx_bytes)
            convert(inp, out)
            if os.path.exists(out):
                with open(out, "rb") as f:
                    return f.read()
        return None
    except Exception as e:
        import logging
        logging.warning(f"docx_to_pdf failed: {e}")
        return None


def nut_tai_word_va_pdf(
    docx_bytes: bytes,
    ten_file_goc: str,
    key_prefix: str,
) -> None:
    """
    Lưu Word + PDF bytes vào session_state.
    Gọi bên trong if st.button().
    """
    import streamlit as st

    st.session_state[f"_w_bytes_{key_prefix}"] = docx_bytes
    st.session_state[f"_f_name_{key_prefix}"] = ten_file_goc
    pdf_bytes = docx_to_pdf(docx_bytes)
    if pdf_bytes:
        st.session_state[f"_p_bytes_{key_prefix}"] = pdf_bytes


def hien_thi_nut_tai(key_prefix: str) -> None:
    """
    Hiển thị 2 nút download: Word + PDF từ session_state.
    Gọi NGOÀI if st.button() — luôn render.
    """
    import streamlit as st

    docx_bytes = st.session_state.get(f"_w_bytes_{key_prefix}")
    if not docx_bytes:
        return

    col1, col2 = st.columns(2)
    with col1:
        st.download_button(
            "⬇️ Tải Word (.docx)",
            data=docx_bytes,
            file_name=f"{st.session_state.get(f'_f_name_{key_prefix}', 'file')}.docx",
            mime="application/vnd.openxmlformats-officedocument"
                 ".wordprocessingml.document",
            key=f"{key_prefix}_dl_docx",
            width='stretch',
        )
    with col2:
        pdf_bytes = st.session_state.get(f"_p_bytes_{key_prefix}")
        if pdf_bytes:
            st.download_button(
                "⬇️ Tải PDF",
                data=pdf_bytes,
                file_name=f"{st.session_state.get(f'_f_name_{key_prefix}', 'file')}.pdf",
                mime="application/pdf",
                key=f"{key_prefix}_dl_pdf",
                width='stretch',
            )
        else:
            st.caption("⚠️ PDF: cần MS Word trên server")
