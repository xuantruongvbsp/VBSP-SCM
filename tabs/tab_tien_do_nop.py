import streamlit as st
import pandas as pd
import gspread
# import oauth2client only as fallback; prefer google-auth via gspread.service_account
# oauth2client will be imported lazily inside _ket_noi_gsheet() if needed
from pathlib import Path
from typing import Optional
from config import DS_PGD, DON_VI_CHI_NHANH

# HẰNG SỐ
SHEET_ID = "15Ev2rTv6khLFaMpAiMwqJCVC_33ocJ-6cp016RGNkYk"
SHEET_TAB = "TIENDO_BAOCAO"
CREDENTIALS_FILE = "credentials.json"
COT = ["thoi_gian", "email", "ten_pgd", "loai_bao_cao",
       "ky_bao_cao", "noi_dung", "file_dinh_kem", "ho_ten"]

def _ket_noi_gsheet():
    """Kết nối Google Sheet."""
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]
    if not Path(CREDENTIALS_FILE).exists():
        raise FileNotFoundError(f"Không tìm thấy file credentials: {CREDENTIALS_FILE}")
    # Thử dùng google-auth (gspread.service_account) trước — hiện đại và không cần oauth2client
    try:
        client = gspread.service_account(filename=CREDENTIALS_FILE, scopes=scope)
        return client
    except Exception:
        # Fallback: nếu môi trường còn dùng oauth2client
        try:
            from oauth2client.service_account import ServiceAccountCredentials  # type: ignore
        except Exception as e:
            raise RuntimeError(
                "Không thể kết nối GSheet: cần cài đặt google-auth và gspread, hoặc oauth2client."
            ) from e
        creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, scope)
        return gspread.authorize(creds)

@st.cache_data(ttl=300)
def _doc_du_lieu() -> pd.DataFrame:
    """Đọc dữ liệu từ Google Sheet."""
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
    """Render tab Báo cáo Tiến độ PGD."""
    role = kwargs.get("role")

    st.subheader("📋 Báo cáo Tiến độ — PGD")
    st.caption("Dữ liệu từ Google Form · Tự động cập nhật mỗi 5 phút")

    if not Path(CREDENTIALS_FILE).exists():
        st.warning("Chưa cấu hình kết nối Google Sheet (thiếu credentials.json)")
        return

    if st.button("🔄 Làm mới", key="tdn_refresh"):
        st.cache_data.clear()
        st.rerun()

    df = _doc_du_lieu()

    if df.empty:
        st.info("Chưa có dữ liệu. PGD chưa nộp báo cáo hoặc chưa kết nối GSheet.")
        return

    # ── PHẦN A: Metric tổng quan ─────────────────────
    tong_nop = len(df)
    so_pgd = df["ten_pgd"].nunique()
    ky_moi = df["ky_bao_cao"].iloc[-1] if tong_nop else "—"

    c1, c2, c3 = st.columns(3)
    c1.metric("Tổng lượt nộp", tong_nop)
    c2.metric("Số PGD đã nộp", so_pgd)
    c3.metric("Kỳ mới nhất", ky_moi)

    st.divider()

    # ── PHẦN B: Bộ lọc ───────────────────────────────
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

    # ── PHẦN C: Bảng chi tiết ────────────────────────
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
        use_container_width=True,
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

    # ── PHẦN D: Bảng PGD chưa nộp (nếu có lọc theo kỳ) ──
    if ky_chon != "Tất cả":
        ds_tat_ca = [DON_VI_CHI_NHANH] + DS_PGD
        da_nop = df_loc["ten_pgd"].unique().tolist()
        chua_nop = [p for p in ds_tat_ca if p not in da_nop]
        if chua_nop:
            st.warning(f"⚠️ {len(chua_nop)} đơn vị chưa nộp kỳ **{ky_chon}**")
            st.dataframe(
                pd.DataFrame({"Đơn vị chưa nộp": chua_nop}),
                hide_index=True,
                use_container_width=True,
            )
