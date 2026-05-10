#!/usr/bin/env python3
"""
Fix all nested st.button → st.download_button patterns in the VBSP-SCM codebase.
Replaces with session_state-based pattern to prevent "Invalid binary data format: NoneType" errors.
"""

import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

REPLACEMENTS = []

# ─── Helper ─────────────────────────────────────────────────────────────────
def make_fix_ss(btn_label, btn_key, dl_key, btn_code_old, btn_code_new,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                file_tpl='file_name'):
    """Build old → new replacement for a simple st.button → st.download_button pattern."""
    old = f'''if st.button("{btn_label}", key="{btn_key}"):
    {btn_code_old}
    st.download_button("⬇ Tải Excel",
        data={dl_key},
        file_name={file_tpl},
        mime="{mime}",
        key="{btn_key}_dl")'''

    new = f'''if st.button("{btn_label}", key="{btn_key}"):
    {btn_code_old}
    st.session_state["_bytes_{btn_key}"] = {dl_key}
    st.session_state["_file_{btn_key}"] = {file_tpl}

bytes_{btn_key} = st.session_state.get("_bytes_{btn_key}")
if bytes_{btn_key} is not None:
    st.download_button("⬇ Tải Excel",
        data=bytes_{btn_key},
        file_name=st.session_state.get("_file_{btn_key}", "{btn_key}.xlsx"),
        mime="{mime}",
        key="{btn_key}_dl")'''
    return old, new


# ═══════════════════════════════════════════════════════════════════════════════
# 1. tab_baocao.py — 2 nút (Xuất tổng hợp + Xuất báo cáo chi tiết)
# ═══════════════════════════════════════════════════════════════════════════════

def fix_tab_baocao(content):
    import streamlit as st

    # Fix 1: Xuất tổng hợp (around line 295)
    # Find the pattern
    p1_old = '''                if st.button("📥 Xuất tổng hợp Excel", key="btn_xuat_th"):
                    sheets = {"Tổng hợp": dbc_raw}
                    data_excel = xuat_bao_cao(sheets, tieu_de="Báo cáo tổng hợp",
                                              nguoi_xuat=username or "Người dùng")
                    st.download_button(
                        "⬇ Tải Excel",
                        data=data_excel,
                        file_name=ten_file_bao_cao("BC_TH"),
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key="dl_bc_th",
                    )'''
    p1_new = '''                if st.button("📥 Xuất tổng hợp Excel", key="btn_xuat_th"):
                    sheets = {"Tổng hợp": dbc_raw}
                    st.session_state["_bytes_btn_xuat_th"] = xuat_bao_cao(
                        sheets, tieu_de="Báo cáo tổng hợp",
                        nguoi_xuat=username or "Người dùng")
                    st.session_state["_file_btn_xuat_th"] = ten_file_bao_cao("BC_TH")

                if st.session_state.get("_bytes_btn_xuat_th"):
                    st.download_button(
                        "⬇ Tải Excel",
                        data=st.session_state["_bytes_btn_xuat_th"],
                        file_name=st.session_state["_file_btn_xuat_th"],
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key="dl_bc_th",
                    )'''
    content = content.replace(p1_old, p1_new)

    # Fix 2: Xuất báo cáo chi tiết (around line 478)
    # This is more complex - need to match the exact text
    p2_old = '''                    if st.button("📥 Xuất báo cáo chi tiết", key="btn_bc_ct"):
                        sheets_xuat = {}
                        for sheet_nhan, sheet_df in list(sheets.items()):
                            sheets_xuat[sheet_nhan] = sheet_df
                        data_excel = xuat_bao_cao(sheets_xuat, tieu_de="Báo cáo chi tiết",
                                                  nguoi_xuat=username or "Người dùng")
                        st.download_button(
                            "⬇ Tải Excel",
                            data=data_excel,
                            file_name=ten_file_bao_cao("BC_CT"),
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            key="dl_bc_ct",
                        )'''
    p2_new = '''                    if st.button("📥 Xuất báo cáo chi tiết", key="btn_bc_ct"):
                        sheets_xuat = {}
                        for sheet_nhan, sheet_df in list(sheets.items()):
                            sheets_xuat[sheet_nhan] = sheet_df
                        st.session_state["_bytes_btn_bc_ct"] = xuat_bao_cao(
                            sheets_xuat, tieu_de="Báo cáo chi tiết",
                            nguoi_xuat=username or "Người dùng")
                        st.session_state["_file_btn_bc_ct"] = ten_file_bao_cao("BC_CT")

                    if st.session_state.get("_bytes_btn_bc_ct"):
                        st.download_button(
                            "⬇ Tải Excel",
                            data=st.session_state["_bytes_btn_bc_ct"],
                            file_name=st.session_state["_file_btn_bc_ct"],
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            key="dl_bc_ct",
                        )'''
    content = content.replace(p2_old, p2_new)

    # Also check for PDF inside the chi tiet block
    p2b_old = '''                        if st.button("📄 Xuất PDF", key="btn_bc_pdf"):
                            pdf_bytes = xuat_pdf_ct(...)
                            st.download_button(
                                "⬇ Tải PDF",
                                data=pdf_bytes,
                                file_name=ten_file_bao_cao("BC_CT") + ".pdf",
                                mime="application/pdf",
                                key="dl_bc_pdf",
                            )'''
    p2b_new = '''                        if st.button("📄 Xuất PDF", key="btn_bc_pdf"):
                            st.session_state["_bytes_btn_bc_pdf"] = xuat_pdf_ct(...)
                            st.session_state["_file_btn_bc_pdf"] = ten_file_bao_cao("BC_CT") + ".pdf"

                        if st.session_state.get("_bytes_btn_bc_pdf"):
                            st.download_button(
                                "⬇ Tải PDF",
                                data=st.session_state["_bytes_btn_bc_pdf"],
                                file_name=st.session_state["_file_btn_bc_pdf"],
                                mime="application/pdf",
                                key="dl_bc_pdf",
                            )'''
    content = content.replace(p2b_old, p2b_new)

    return content


# ═══════════════════════════════════════════════════════════════════════════════
# 2. tab_khtd_xuat.py — Nút Xuất Excel
# ═══════════════════════════════════════════════════════════════════════════════

def fix_tab_khtd_xuat(content):
    p_old = '''                    if st.button("📥 Xuất Excel", key="btn_xuat_khtd"):
                        xlsx_data = xuat_khtd_excel(...)
                        st.download_button(
                            "⬇ Tải Excel",
                            data=xlsx_data,
                            file_name=ten_file_xuat(f"KHTD_{nam}"),
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            key="dl_khtd_xuat",
                        )'''
    p_new = '''                    if st.button("📥 Xuất Excel", key="btn_xuat_khtd"):
                        st.session_state["_bytes_btn_xuat_khtd"] = xuat_khtd_excel(...)
                        st.session_state["_file_btn_xuat_khtd"] = ten_file_xuat(f"KHTD_{nam}")

                    if st.session_state.get("_bytes_btn_xuat_khtd"):
                        st.download_button(
                            "⬇ Tải Excel",
                            data=st.session_state["_bytes_btn_xuat_khtd"],
                            file_name=st.session_state["_file_btn_xuat_khtd"],
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            key="dl_khtd_xuat",
                        )'''
    content = content.replace(p_old, p_new)
    return content


# ═══════════════════════════════════════════════════════════════════════════════
# 3. tab_nq11.py — Nút Xuất Excel
# ═══════════════════════════════════════════════════════════════════════════════

def fix_tab_nq11(content):
    p_old = '''        if st.button("📥 Xuất dữ liệu NQ11 ra Excel", key="btn_nq11_xuat"):
            excel_data = xuat_nq11(...)
            st.download_button(
                "⬇ Tải Excel",
                data=excel_data,
                file_name=ten_file_xuat(f"NQ11_{thang_chon}"),
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="dl_nq11_xuat",
            )'''
    p_new = '''        if st.button("📥 Xuất dữ liệu NQ11 ra Excel", key="btn_nq11_xuat"):
            st.session_state["_bytes_btn_nq11_xuat"] = xuat_nq11(...)
            st.session_state["_file_btn_nq11_xuat"] = ten_file_xuat(f"NQ11_{thang_chon}")

        if st.session_state.get("_bytes_btn_nq11_xuat"):
            st.download_button(
                "⬇ Tải Excel",
                data=st.session_state["_bytes_btn_nq11_xuat"],
                file_name=st.session_state["_file_btn_nq11_xuat"],
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="dl_nq11_xuat",
            )'''
    content = content.replace(p_old, p_new)
    return content


# ═══════════════════════════════════════════════════════════════════════════════
# 4. tab_gqvl.py — 2 nút
# ═══════════════════════════════════════════════════════════════════════════════

def fix_tab_gqvl(content):
    # Fix 1: Xuất danh sách NQH
    p1_old = '''            if st.button("📥 Xuất danh sách NQH", key="btn_gqvl_nqh"):
                excel_data = xuat_gqvl(...)
                st.download_button(
                    "⬇ Tải Excel",
                    data=excel_data,
                    file_name=ten_file_xuat(f"GQVL_NQH_{thang}"),
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="dl_gqvl_nqh",
                )'''
    p1_new = '''            if st.button("📥 Xuất danh sách NQH", key="btn_gqvl_nqh"):
                st.session_state["_bytes_btn_gqvl_nqh"] = xuat_gqvl(...)
                st.session_state["_file_btn_gqvl_nqh"] = ten_file_xuat(f"GQVL_NQH_{thang}")

            if st.session_state.get("_bytes_btn_gqvl_nqh"):
                st.download_button(
                    "⬇ Tải Excel",
                    data=st.session_state["_bytes_btn_gqvl_nqh"],
                    file_name=st.session_state["_file_btn_gqvl_nqh"],
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="dl_gqvl_nqh",
                )'''
    content = content.replace(p1_old, p1_new)

    # Fix 2: Xuất danh sách đang lọc
    p2_old = '''            if st.button("📥 Xuất danh sách đang lọc", key="btn_gqvl_loc"):
                excel_data = xuat_gqvl(...)
                st.download_button(
                    "⬇ Tải Excel",
                    data=excel_data,
                    file_name=ten_file_xuat(f"GQVL_loc"),
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="dl_gqvl_loc",
                )'''
    p2_new = '''            if st.button("📥 Xuất danh sách đang lọc", key="btn_gqvl_loc"):
                st.session_state["_bytes_btn_gqvl_loc"] = xuat_gqvl(...)
                st.session_state["_file_btn_gqvl_loc"] = ten_file_xuat(f"GQVL_loc")

            if st.session_state.get("_bytes_btn_gqvl_loc"):
                st.download_button(
                    "⬇ Tải Excel",
                    data=st.session_state["_bytes_btn_gqvl_loc"],
                    file_name=st.session_state["_file_btn_gqvl_loc"],
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="dl_gqvl_loc",
                )'''
    content = content.replace(p2_old, p2_new)
    return content


# ═══════════════════════════════════════════════════════════════════════════════
# 5. tab_qd62.py — Nút Xuất Excel
# ═══════════════════════════════════════════════════════════════════════════════

def fix_tab_qd62(content):
    p_old = '''                if st.button("⬇️ Xuất Excel toàn CN", key="btn_qd62_xuat"):
                    excel_data = xuat_qd62(...)
                    st.download_button(
                        "⬇ Tải Excel",
                        data=excel_data,
                        file_name=ten_file_xuat(f"QD62_{thang}"),
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key="dl_qd62_xuat",
                    )'''
    p_new = '''                if st.button("⬇️ Xuất Excel toàn CN", key="btn_qd62_xuat"):
                    st.session_state["_bytes_btn_qd62_xuat"] = xuat_qd62(...)
                    st.session_state["_file_btn_qd62_xuat"] = ten_file_xuat(f"QD62_{thang}")

                if st.session_state.get("_bytes_btn_qd62_xuat"):
                    st.download_button(
                        "⬇ Tải Excel",
                        data=st.session_state["_bytes_btn_qd62_xuat"],
                        file_name=st.session_state["_file_btn_qd62_xuat"],
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key="dl_qd62_xuat",
                    )'''
    content = content.replace(p_old, p_new)

    # Also check for other export patterns
    p2_old = '''            if st.button("⬇️ Xuất Excel mẫu", key="btn_qd62_mau"):
                excel_data = xuat_qd62_mau(...)
                st.download_button(
                    "⬇ Tải Excel",
                    data=excel_data,
                    file_name=ten_file_xuat("QD62_mau"),
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="dl_qd62_mau",
                )'''
    p2_new = '''            if st.button("⬇️ Xuất Excel mẫu", key="btn_qd62_mau"):
                st.session_state["_bytes_btn_qd62_mau"] = xuat_qd62_mau(...)
                st.session_state["_file_btn_qd62_mau"] = ten_file_xuat("QD62_mau")

            if st.session_state.get("_bytes_btn_qd62_mau"):
                st.download_button(
                    "⬇ Tải Excel",
                    data=st.session_state["_bytes_btn_qd62_mau"],
                    file_name=st.session_state["_file_btn_qd62_mau"],
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="dl_qd62_mau",
                )'''
    content = content.replace(p2_old, p2_new)
    return content


# ═══════════════════════════════════════════════════════════════════════════════
# 6. tab_kehoach.py — 2 nút
# ═══════════════════════════════════════════════════════════════════════════════

def fix_tab_kehoach(content):
    # Fix 1: Tải file mẫu kế hoạch
    p1_old = '''            if st.button("⬇ Tải file mẫu kế hoạch Excel", key="btn_kh_mau"):
                excel_data = tao_file_mau_kehoach(...)
                st.download_button(
                    "⬇ Tải Excel",
                    data=excel_data,
                    file_name="ke_hoach_mau.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="dl_kh_mau",
                )'''
    p1_new = '''            if st.button("⬇ Tải file mẫu kế hoạch Excel", key="btn_kh_mau"):
                st.session_state["_bytes_btn_kh_mau"] = tao_file_mau_kehoach(...)
                st.session_state["_file_btn_kh_mau"] = "ke_hoach_mau.xlsx"

            if st.session_state.get("_bytes_btn_kh_mau"):
                st.download_button(
                    "⬇ Tải Excel",
                    data=st.session_state["_bytes_btn_kh_mau"],
                    file_name=st.session_state["_file_btn_kh_mau"],
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="dl_kh_mau",
                )'''
    content = content.replace(p1_old, p1_new)

    # Fix 2: Xuất báo cáo KH vs TH
    p2_old = '''            if st.button("📥 Xuất báo cáo KH vs TH", key="btn_kh_vs_th"):
                excel_data = xuat_kh_vs_th(...)
                st.download_button(
                    "⬇ Tải Excel",
                    data=excel_data,
                    file_name=ten_file_xuat("KHvsTH"),
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="dl_kh_vs_th",
                )'''
    p2_new = '''            if st.button("📥 Xuất báo cáo KH vs TH", key="btn_kh_vs_th"):
                st.session_state["_bytes_btn_kh_vs_th"] = xuat_kh_vs_th(...)
                st.session_state["_file_btn_kh_vs_th"] = ten_file_xuat("KHvsTH")

            if st.session_state.get("_bytes_btn_kh_vs_th"):
                st.download_button(
                    "⬇ Tải Excel",
                    data=st.session_state["_bytes_btn_kh_vs_th"],
                    file_name=st.session_state["_file_btn_kh_vs_th"],
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="dl_kh_vs_th",
                )'''
    content = content.replace(p2_old, p2_new)
    return content


# ═══════════════════════════════════════════════════════════════════════════════
# 7. tab_candoi.py — Nút Xuất Excel
# ═══════════════════════════════════════════════════════════════════════════════

def fix_tab_candoi(content):
    p_old = '''                    if st.button("📥 Xuất so sánh cân đối ra Excel", key="btn_cd_xuat"):
                        excel_data = xuat_candoi(...)
                        st.download_button(
                            "⬇ Tải Excel",
                            data=excel_data,
                            file_name=ten_file_xuat("CanDoi"),
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            key="dl_cd_xuat",
                        )'''
    p_new = '''                    if st.button("📥 Xuất so sánh cân đối ra Excel", key="btn_cd_xuat"):
                        st.session_state["_bytes_btn_cd_xuat"] = xuat_candoi(...)
                        st.session_state["_file_btn_cd_xuat"] = ten_file_xuat("CanDoi")

                    if st.session_state.get("_bytes_btn_cd_xuat"):
                        st.download_button(
                            "⬇ Tải Excel",
                            data=st.session_state["_bytes_btn_cd_xuat"],
                            file_name=st.session_state["_file_btn_cd_xuat"],
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            key="dl_cd_xuat",
                        )'''
    content = content.replace(p_old, p_new)
    return content


# ═══════════════════════════════════════════════════════════════════════════════
# 8. tab_danhsach.py — Nút Xuất Excel
# ═══════════════════════════════════════════════════════════════════════════════

def fix_tab_danhsach(content):
    p_old = '''        if st.button("📥 Xuất danh sách đang lọc"):
            buf = BytesIO()
            with pd.ExcelWriter(buf, engine="openpyxl") as w:
                dl[ch].to_excel(w, index=False, sheet_name="Danh sách")
            st.download_button("⬇ Tải file Excel", data=buf.getvalue(),
                file_name=f"danh_sach_{datetime.today().strftime('%d%m%Y')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")'''
    p_new = '''        if st.button("📥 Xuất danh sách đang lọc", key="btn_ds_xuat"):
            buf = BytesIO()
            with pd.ExcelWriter(buf, engine="openpyxl") as w:
                dl[ch].to_excel(w, index=False, sheet_name="Danh sách")
            st.session_state["_bytes_btn_ds_xuat"] = buf.getvalue()
            st.session_state["_file_btn_ds_xuat"] = f"danh_sach_{datetime.today().strftime('%d%m%Y')}.xlsx"

        if st.session_state.get("_bytes_btn_ds_xuat"):
            st.download_button("⬇ Tải file Excel",
                data=st.session_state["_bytes_btn_ds_xuat"],
                file_name=st.session_state["_file_btn_ds_xuat"],
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="dl_ds_xuat")'''
    content = content.replace(p_old, p_new)
    return content


# ═══════════════════════════════════════════════════════════════════════════════
# 9. tab_cbtd.py — Nút Xuất Excel
# ═══════════════════════════════════════════════════════════════════════════════

def fix_tab_cbtd(content):
    p_old = '''            if st.button("📥 Xuất báo cáo CBTD", key="btn_cbtd_xuat"):
                excel_data = xuat_cbtd(...)
                st.download_button(
                    "⬇ Tải Excel",
                    data=excel_data,
                    file_name=ten_file_xuat("CBTD"),
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="dl_cbtd_xuat",
                )'''
    p_new = '''            if st.button("📥 Xuất báo cáo CBTD", key="btn_cbtd_xuat"):
                st.session_state["_bytes_btn_cbtd_xuat"] = xuat_cbtd(...)
                st.session_state["_file_btn_cbtd_xuat"] = ten_file_xuat("CBTD")

            if st.session_state.get("_bytes_btn_cbtd_xuat"):
                st.download_button(
                    "⬇ Tải Excel",
                    data=st.session_state["_bytes_btn_cbtd_xuat"],
                    file_name=st.session_state["_file_btn_cbtd_xuat"],
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="dl_cbtd_xuat",
                )'''
    content = content.replace(p_old, p_new)
    return content


# ═══════════════════════════════════════════════════════════════════════════════
# 10. tab_cdtotkvv.py — 2 nút (PDF + Excel)
# ═══════════════════════════════════════════════════════════════════════════════

def fix_tab_cdtotkvv(content):
    # Excel download at ~L914
    p_old = '''                        st.download_button(
                            label="📥 Tải file Excel",
                            data=xlsx_bytes,
                            file_name=ten_file_xuat(f"ToYeu_{thang_chon}"),
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            key="cdto4_download_yeu"
                        )'''
    # This one is already inside a try block with no st.button guard
    # Actually, let me check the context more carefully...
    # From the search results, it shows this is inside a try-except, not inside if st.button():
    # Let me leave this one - it's a direct st.download_button

    # Fix the other one at ~L914 - need to check actual context
    # Actually from search, this isn't inside an if st.button() guard, it's inside try-except
    # So this is SAFE - no change needed

    return content


# ═══════════════════════════════════════════════════════════════════════════════
# 11. tab_cdtotkvv_pgd.py — Nút Xuất Excel
# ═══════════════════════════════════════════════════════════════════════════════

def fix_tab_cdtotkvv_pgd(content):
    p_old = '''            if st.button("📥 Xuất Excel Tổ Yếu", key="btn_cdpgd_yeu"):
                excel_data = xuat_cdpgd(...)
                st.download_button(
                    "⬇ Tải Excel",
                    data=excel_data,
                    file_name=ten_file_xuat(f"ToYeu_{thang}"),
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="dl_cdpgd_yeu",
                )'''
    p_new = '''            if st.button("📥 Xuất Excel Tổ Yếu", key="btn_cdpgd_yeu"):
                st.session_state["_bytes_btn_cdpgd_yeu"] = xuat_cdpgd(...)
                st.session_state["_file_btn_cdpgd_yeu"] = ten_file_xuat(f"ToYeu_{thang}")

            if st.session_state.get("_bytes_btn_cdpgd_yeu"):
                st.download_button(
                    "⬇ Tải Excel",
                    data=st.session_state["_bytes_btn_cdpgd_yeu"],
                    file_name=st.session_state["_file_btn_cdpgd_yeu"],
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="dl_cdpgd_yeu",
                )'''
    content = content.replace(p_old, p_new)
    return content


# ═══════════════════════════════════════════════════════════════════════════════
# 12. ws_operation.py — 3 nút (Word + Excel + Word doc hub)
# ═══════════════════════════════════════════════════════════════════════════════

def fix_ws_operation(content):
    # Fix 1: Xuất Biên bản Word ~L532-558
    p1_old = '''                if st.button("🖨️ Xuất Biên bản Word", key="btn_op_bienban"):
                    docx_bytes = tao_bien_ban(...)
                    st.download_button(
                        "⬇ Tải Word",
                        data=docx_bytes,
                        file_name=f"BienBan_{ten_pgd}.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        key="dl_op_bienban",
                    )'''
    p1_new = '''                if st.button("🖨️ Xuất Biên bản Word", key="btn_op_bienban"):
                    st.session_state["_bytes_btn_op_bienban"] = tao_bien_ban(...)
                    st.session_state["_file_btn_op_bienban"] = f"BienBan_{ten_pgd}.docx"

                if st.session_state.get("_bytes_btn_op_bienban"):
                    st.download_button(
                        "⬇ Tải Word",
                        data=st.session_state["_bytes_btn_op_bienban"],
                        file_name=st.session_state["_file_btn_op_bienban"],
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        key="dl_op_bienban",
                    )'''
    content = content.replace(p1_old, p1_new)

    # Fix 2: Xuất Excel (Báo cáo GB) ~L776-795
    p2_old = '''                if st.button("⬇️ Xuất Excel", key="btn_op_excel"):
                    excel_data = xuat_op_excel(...)
                    st.download_button(
                        "⬇ Tải Excel",
                        data=excel_data,
                        file_name=ten_file_xuat("BC_GB"),
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key="dl_op_excel",
                    )'''
    p2_new = '''                if st.button("⬇️ Xuất Excel", key="btn_op_excel"):
                    st.session_state["_bytes_btn_op_excel"] = xuat_op_excel(...)
                    st.session_state["_file_btn_op_excel"] = ten_file_xuat("BC_GB")

                if st.session_state.get("_bytes_btn_op_excel"):
                    st.download_button(
                        "⬇ Tải Excel",
                        data=st.session_state["_bytes_btn_op_excel"],
                        file_name=st.session_state["_file_btn_op_excel"],
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key="dl_op_excel",
                    )'''
    content = content.replace(p2_old, p2_new)

    # Fix 3: Tạo văn bản (doc hub) ~L244-269
    # This is inside a loop, more complex
    p3_old = '''                    if st.button("🖨️ Tạo văn bản", key=f"btn_op_doc_{i}"):
                        docx_bytes = tao_van_ban(...)
                        st.download_button(
                            "⬇ Tải Word",
                            data=docx_bytes,
                            file_name=f"VanBan_{i}.docx",
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            key=f"dl_op_doc_{i}",
                        )'''
    p3_new = '''                    if st.button("🖨️ Tạo văn bản", key=f"btn_op_doc_{i}"):
                        st.session_state[f"_bytes_btn_op_doc_{i}"] = tao_van_ban(...)
                        st.session_state[f"_file_btn_op_doc_{i}"] = f"VanBan_{i}.docx"

                    dl_key = f"_bytes_btn_op_doc_{i}"
                    if st.session_state.get(dl_key):
                        st.download_button(
                            "⬇ Tải Word",
                            data=st.session_state[dl_key],
                            file_name=st.session_state.get(f"_file_btn_op_doc_{i}", f"VanBan_{i}.docx"),
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            key=f"dl_op_doc_{i}",
                        )'''
    content = content.replace(p3_old, p3_new)
    return content


# ═══════════════════════════════════════════════════════════════════════════════
# 13. ws_management.py — Nút Word KL giao ban
# ═══════════════════════════════════════════════════════════════════════════════

def fix_ws_management(content):
    p_old = '''            if st.button("🖨️ Tạo KL giao ban", key="btn_mgmt_kl"):
                docx_bytes = tao_kl_giao_ban(...)
                st.download_button(
                    "⬇ Tải Word",
                    data=docx_bytes,
                    file_name=f"KLGiaoBan_{datetime.now().strftime('%Y%m%d')}.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    key="dl_mgmt_kl",
                )'''
    p_new = '''            if st.button("🖨️ Tạo KL giao ban", key="btn_mgmt_kl"):
                st.session_state["_bytes_btn_mgmt_kl"] = tao_kl_giao_ban(...)
                st.session_state["_file_btn_mgmt_kl"] = f"KLGiaoBan_{datetime.now().strftime('%Y%m%d')}.docx"

            if st.session_state.get("_bytes_btn_mgmt_kl"):
                st.download_button(
                    "⬇ Tải Word",
                    data=st.session_state["_bytes_btn_mgmt_kl"],
                    file_name=st.session_state["_file_btn_mgmt_kl"],
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    key="dl_mgmt_kl",
                )'''
    content = content.replace(p_old, p_new)
    return content


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN: Read each file, apply fixes, write back
# ═══════════════════════════════════════════════════════════════════════════════

FIXES = {
    r'c:\VBSP-SCM\tabs\tab_baocao.py': fix_tab_baocao,
    r'c:\VBSP-SCM\tabs\tab_khtd_xuat.py': fix_tab_khtd_xuat,
    r'c:\VBSP-SCM\tabs\tab_nq11.py': fix_tab_nq11,
    r'c:\VBSP-SCM\tabs\tab_gqvl.py': fix_tab_gqvl,
    r'c:\VBSP-SCM\tabs\tab_qd62.py': fix_tab_qd62,
    r'c:\VBSP-SCM\tabs\tab_kehoach.py': fix_tab_kehoach,
    r'c:\VBSP-SCM\tabs\tab_candoi.py': fix_tab_candoi,
    r'c:\VBSP-SCM\tabs\tab_danhsach.py': fix_tab_danhsach,
    r'c:\VBSP-SCM\tabs\tab_cbtd.py': fix_tab_cbtd,
    r'c:\VBSP-SCM\tabs\tab_cdtotkvv.py': fix_tab_cdtotkvv,
    r'c:\VBSP-SCM\tabs\tab_cdtotkvv_pgd.py': fix_tab_cdtotkvv_pgd,
    r'c:\VBSP-SCM\workspaces\ws_operation.py': fix_ws_operation,
    r'c:\VBSP-SCM\workspaces\ws_management.py': fix_ws_management,
}

for filepath, fix_func in FIXES.items():
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original = content
    content = fix_func(content)
    
    if content != original:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"✅ {filepath} — fixed")
    else:
        # Try placeholder-based fixes if the exact patterns didn't match
        print(f"⚠️ {filepath} — no patterns matched (may need manual inspection)")

print("\n✅ Done!")
