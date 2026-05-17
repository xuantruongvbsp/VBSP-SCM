import streamlit as st
import pandas as pd
from pathlib import Path
from typing import Optional
from config import DS_PGD, DON_VI_CHI_NHANH
from utils import xuat_excel

SHEET_ID = "15Ev2rTv6khLFaMpAiMwqJCVC_33ocJ-6cp016RGNkYk"
SHEET_TAB = "TIENDO_BAOCAO"
CREDENTIALS_FILE = "credentials.json"
COT = ["thoi_gian", "email", "ten_pgd", "loai_bao_cao",
       "ky_bao_cao", "noi_dung", "file_dinh_kem", "ho_ten"]


def _ket_noi_gsheet():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]
    if not Path(CREDENTIALS_FILE).exists():
        raise FileNotFoundError(f"Không tìm thấy file credentials: {CREDENTIALS_FILE}")

    try:
        import gspread
    except ImportError:
        raise RuntimeError(
            "Thiếu thư viện gspread. Cài đặt: pip install gspread google-auth"
        )

    try:
        client = gspread.service_account(filename=CREDENTIALS_FILE, scopes=scope)
        return client
    except Exception:
        try:
            from oauth2client.service_account import ServiceAccountCredentials
        except ImportError:
            raise RuntimeError(
                "Không thể kết nối GSheet: cần cài google-auth hoặc oauth2client."
            )
        creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, scope)
        return gspread.authorize(creds)


@st.cache_data(ttl=300)
def _doc_du_lieu() -> pd.DataFrame:
    try:
        client = _ket_noi_gsheet()
        sheet = client.open_by_key(SHEET_ID).worksheet(SHEET_TAB)
        data = sheet.get_all_values()
        if len(data) <= 1:
            return pd.DataFrame(columns=COT)

        df = pd.DataFrame(data[1:], columns=COT)
        df["thoi_gian"] = pd.to_datetime(df["thoi_gian"], dayfirst=True, errors="coerce")
        return df
    except Exception as e:
        st.error(f"Lỗi kết nối GSheet: {e}")
        return pd.DataFrame(columns=COT)


def render(tab: Optional[st.delta_generator.DeltaGenerator] = None, **kwargs) -> None:
    role = kwargs.get("role")

    st.subheader("📋 Báo cáo Tiến độ — PGD")
    st.caption("Dữ liệu từ Google Form · Tự động cập nhật mỗi 5 phút")

    if not Path(CREDENTIALS_FILE).exists():
        st.warning(
            "⚠️ Chưa cấu hình Google Sheets. "
            "Đặt file `credentials.json` (Service Account) vào thư mục gốc "
            "để kết nối Google Form tự động."
        )
        return

    if st.button("🔄 Làm mới", key="tdn_refresh"):
        st.cache_data.clear()
        st.rerun()

    df = _doc_du_lieu()

    if df.empty:
        st.info("Chưa có dữ liệu. PGD chưa nộp báo cáo hoặc chưa kết nối GSheet.")
        return

    tong_nop = len(df)
    so_pgd = df["ten_pgd"].nunique()
    ky_moi = df["ky_bao_cao"].iloc[-1] if tong_nop else "—"

    c1, c2, c3 = st.columns(3)
    c1.metric("Tổng lượt nộp", tong_nop)
    c2.metric("Số PGD đã nộp", so_pgd)
    c3.metric("Kỳ mới nhất", ky_moi)

    st.divider()

    col1, col2, col3 = st.columns(3)
    with col1:
        ds_ky = ["Tất cả"] + sorted(df["ky_bao_cao"].dropna().unique().tolist(), reverse=True)
        ky_chon = st.selectbox("Kỳ báo cáo", ds_ky, key="tdn_ky")
    with col2:
        ds_loai = ["Tất cả"] + sorted(df["loai_bao_cao"].dropna().unique().tolist())
        loai_chon = st.selectbox("Loại báo cáo", ds_loai, key="tdn_loai")
    with col3:
        ds_pgd = ["Tất cả"] + sorted(df["ten_pgd"].dropna().unique().tolist())
        pgd_chon = st.selectbox("Đơn vị", ds_pgd, key="tdn_pgd")

    df_loc = df.copy()
    if ky_chon != "Tất cả": df_loc = df_loc[df_loc["ky_bao_cao"] == ky_chon]
    if loai_chon != "Tất cả": df_loc = df_loc[df_loc["loai_bao_cao"] == loai_chon]
    if pgd_chon != "Tất cả": df_loc = df_loc[df_loc["ten_pgd"] == pgd_chon]

    st.caption(f"Hiển thị {len(df_loc)} / {len(df)} lượt nộp")

    df_hien = df_loc[[
        "thoi_gian", "ho_ten", "ten_pgd",
        "loai_bao_cao", "ky_bao_cao", "noi_dung", "file_dinh_kem"
    ]].copy()
    df_hien["thoi_gian"] = df_hien["thoi_gian"].dt.strftime("%d/%m/%Y %H:%M")
    df_hien = df_hien.rename(columns={
        "thoi_gian": "Thời gian",
        "ho_ten": "Họ tên",
        "ten_pgd": "Đơn vị",
        "loai_bao_cao": "Loại",
        "ky_bao_cao": "Kỳ",
        "noi_dung": "Nội dung tóm tắt",
        "file_dinh_kem": "File đính kèm",
    })

    st.dataframe(
        df_hien,
        width='stretch',
        hide_index=True,
        column_config={
            "File đính kèm": st.column_config.LinkColumn(
                "File đính kèm",
                display_text="📎 Xem file"
            ),
            "Nội dung tóm tắt": st.column_config.TextColumn(
                width="large"
            ),
        }
    )

    # ── Xuất Excel / PDF ──
    st.divider()
    col_excel, col_pdf, _ = st.columns([1, 1, 5])
    with col_excel:
        if st.button("📥 Xuất Excel", key="btn_xuat_tdn", width='stretch', type="primary"):
            sheets = {"Tiến độ nộp báo cáo": df_loc}
            excel_bytes = xuat_excel(sheets)
            st.session_state["_excel_tdn_bytes"] = excel_bytes
            st.session_state["_excel_tdn_ten"] = f"tien_do_nop_{len(df_loc)}_dong.xlsx"

    if st.session_state.get("_excel_tdn_bytes"):
        st.download_button(
            "⬇ Tải Excel",
            data=st.session_state["_excel_tdn_bytes"],
            file_name=st.session_state["_excel_tdn_ten"],
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="dl_excel_tdn",
        )

    with col_pdf:
        from pdf_service import nut_xuat_pdf
        nut_xuat_pdf(
            df_loc,
            "Tiến độ nộp báo cáo PGD",
            st.session_state.get("txt_username", "unknown"),
            cols_tien=[],
            prefix_file="TienDoNop",
            key="pdf_tdn",
        )

    if ky_chon != "Tất cả":
        ds_tat_ca = [DON_VI_CHI_NHANH] + DS_PGD
        da_nop = df_loc["ten_pgd"].unique().tolist()
        chua_nop = [p for p in ds_tat_ca if p not in da_nop]
        if chua_nop:
            st.warning(f"⚠️ {len(chua_nop)} đơn vị chưa nộp kỳ **{ky_chon}**")
            st.dataframe(
                pd.DataFrame({"Đơn vị chưa nộp": chua_nop}),
                hide_index=True,
                width='stretch',
            )
