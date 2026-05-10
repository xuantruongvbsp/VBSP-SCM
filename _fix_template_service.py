# Fix template_service.py - split nut_tai_word_va_pdf into store + render
with open(r'c:\VBSP-SCM\services\template_service.py', 'r', encoding='utf-8') as f:
    content = f.read()

old = '''def nut_tai_word_va_pdf(
    docx_bytes: bytes,
    ten_file_goc: str,
    key_prefix: str,
) -> None:
    """
    Hiển thị 2 nút download: Word + PDF (nếu convert được).
    Dùng trong Streamlit sau khi render template.

    Args:
        docx_bytes: bytes file .docx đã render
        ten_file_goc: tên file không có extension, VD "Mau06_PGD_BienHoa_01052026"
        key_prefix: prefix để tránh trùng key Streamlit
    """
    import streamlit as st

    col1, col2 = st.columns(2)
    with col1:
        st.download_button(
            "⬇️ Tải Word (.docx)",
            data=docx_bytes,
            file_name=f"{ten_file_goc}.docx",
            mime="application/vnd.openxmlformats-officedocument"
                 ".wordprocessingml.document",
            key=f"{key_prefix}_dl_docx",
            use_container_width=True,
        )
    with col2:
        pdf_bytes = docx_to_pdf(docx_bytes)
        if pdf_bytes:
            st.download_button(
                "⬇️ Tải PDF",
                data=pdf_bytes,
                file_name=f"{ten_file_goc}.pdf",
                mime="application/pdf",
                key=f"{key_prefix}_dl_pdf",
                use_container_width=True,
            )
        else:
            st.caption("⚠️ PDF: cần MS Word trên server")'''

new = '''def nut_tai_word_va_pdf(
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
            use_container_width=True,
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
                use_container_width=True,
            )
        else:
            st.caption("⚠️ PDF: cần MS Word trên server")'''

if old not in content:
    print("ERROR: old string not found!")
    # Debug: find the function location
    idx = content.find("def nut_tai_word_va_pdf")
    if idx >= 0:
        print(f"Found at position {idx}")
        print("First 100 chars around it:")
        print(repr(content[idx:idx+300]))
else:
    content = content.replace(old, new)
    with open(r'c:\VBSP-SCM\services\template_service.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("SUCCESS: template_service.py updated!")
