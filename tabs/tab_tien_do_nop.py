"""Tiến độ nộp báo cáo định kỳ của các PGD — đọc từ Google Sheets."""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st
from streamlit.delta_generator import DeltaGenerator

import db
from auth import la_phan_he_cn, normalize_role
from config import DS_PGD, DON_VI_CHI_NHANH
from utils import xuat_excel

SHEET_ID = "15Ev2rTv6khLFaMpAiMwqJCVC_33ocJ-6cp016RGNkYk"
SHEET_TAB = "TIENDO_BAOCAO"
CREDENTIALS_FILE = "credentials.json"
COT = ["thoi_gian", "email", "ten_pgd", "loai_bao_cao",
       "ky_bao_cao", "noi_dung", "file_dinh_kem", "ho_ten"]

DS_PGD_ALL = [DON_VI_CHI_NHANH] + DS_PGD

_EMOJI = {"dung_han": "🟢", "tre": "🟡", "chua_nop": "🔴", "da_nop": "⚪"}
_LABEL = {"dung_han": "Đúng hạn", "tre": "Trễ hạn", "chua_nop": "Chưa nộp", "da_nop": "Đã nộp"}


# ── Kết nối & đọc Google Sheets ──────────────────────────────────────────────

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
        raise RuntimeError("Thiếu thư viện gspread. Cài đặt: pip install gspread google-auth")
    try:
        return gspread.service_account(filename=CREDENTIALS_FILE, scopes=scope)
    except Exception:
        try:
            from oauth2client.service_account import ServiceAccountCredentials
        except ImportError:
            raise RuntimeError("Không thể kết nối GSheet: cần cài google-auth hoặc oauth2client.")
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


# ── Deadline config ───────────────────────────────────────────────────────────

def _doc_deadline_config() -> dict:
    """Đọc cấu hình deadline: {loai_bao_cao: {ky_bao_cao: 'YYYY-MM-DD'}}"""
    return db.doc_kv("bao_cao_deadline_config") or {}


def _luu_deadline_config(cfg: dict, username: str) -> None:
    db.ghi_kv("bao_cao_deadline_config", cfg, username)
    tong = sum(len(v) for v in cfg.values())
    db.ghi_audit(username, "luu_deadline_bao_cao", f"{tong} deadline đã lưu")


def _phan_loai(ngay_nop, deadline_str: str | None) -> str:
    """Trả về: 'dung_han' | 'tre' | 'chua_nop' | 'da_nop' (không có deadline)."""
    if ngay_nop is None or (hasattr(ngay_nop, "__class__") and pd.isna(ngay_nop)):
        return "chua_nop"
    if not deadline_str:
        return "da_nop"
    try:
        dl = pd.to_datetime(deadline_str).date()
        nop = ngay_nop.date() if hasattr(ngay_nop, "date") else pd.to_datetime(ngay_nop).date()
        return "dung_han" if nop <= dl else "tre"
    except Exception:
        return "da_nop"


def _gan_trang_thai(df: pd.DataFrame, deadline_cfg: dict) -> pd.DataFrame:
    df = df.copy()
    df["tt"] = df.apply(
        lambda r: _phan_loai(r["thoi_gian"], deadline_cfg.get(r["loai_bao_cao"], {}).get(r["ky_bao_cao"])),
        axis=1,
    )
    return df


# ── Tab 1: Tổng quan ──────────────────────────────────────────────────────────

def _render_tong_quan(df: pd.DataFrame, deadline_cfg: dict, is_cn: bool, pgd_user: str | None) -> None:
    if df.empty:
        st.info("Chưa có dữ liệu từ Google Sheets.")
        return

    ds_ky = sorted(df["ky_bao_cao"].dropna().unique().tolist(), reverse=True)
    ky_chon = st.selectbox("Chọn kỳ báo cáo", ["Tất cả"] + ds_ky, key="tquan_ky")

    df_ky = df[df["ky_bao_cao"] == ky_chon].copy() if ky_chon != "Tất cả" else df.copy()
    df_ky = _gan_trang_thai(df_ky, deadline_cfg)

    dung_han = (df_ky["tt"] == "dung_han").sum()
    tre = (df_ky["tt"] == "tre").sum()
    da_nop = len(df_ky)

    ds_pgd_scope = [pgd_user] if (not is_cn and pgd_user) else DS_PGD_ALL
    ds_loai = sorted(df["loai_bao_cao"].dropna().unique().tolist())

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Tổng lượt nộp", da_nop)
    c2.metric("🟢 Đúng hạn", dung_han)
    c3.metric("🟡 Trễ hạn", tre)
    if ky_chon != "Tất cả":
        tong_can = len(ds_pgd_scope) * len(ds_loai)
        chua_nop = max(0, tong_can - da_nop)
        c4.metric("🔴 Chưa nộp", chua_nop)

    if ky_chon == "Tất cả" or not ds_loai:
        st.info("Chọn một kỳ cụ thể để xem ma trận trạng thái PGD.")
        return

    st.divider()
    st.markdown("**Ma trận trạng thái — PGD × Loại báo cáo**")

    rows = []
    for pgd in ds_pgd_scope:
        row: dict = {"Đơn vị": pgd}
        for loai in ds_loai:
            match = df_ky[(df_ky["ten_pgd"] == pgd) & (df_ky["loai_bao_cao"] == loai)]
            if match.empty:
                has_dl = bool(deadline_cfg.get(loai, {}).get(ky_chon))
                row[loai] = "🔴 Chưa nộp" if has_dl else "⚪ Chưa nộp"
            else:
                tt = match.sort_values("thoi_gian").iloc[-1]["tt"]
                row[loai] = f"{_EMOJI[tt]} {_LABEL[tt]}"
        rows.append(row)

    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")

    # Danh sách đôn đốc: từng dòng = 1 PGD × 1 loại báo cáo còn thiếu
    ds_don_doc = []
    for r in rows:
        for loai in ds_loai:
            if "🔴" in str(r.get(loai, "")):
                dl = deadline_cfg.get(loai, {}).get(ky_chon, "")
                ds_don_doc.append({
                    "Đơn vị": r["Đơn vị"],
                    "Loại báo cáo": loai,
                    "Kỳ": ky_chon,
                    "Deadline": dl or "Chưa cài",
                })

    if ds_don_doc:
        df_don_doc = pd.DataFrame(ds_don_doc)
        st.divider()
        st.warning(f"⚠️ **{len(df_don_doc)} báo cáo chưa nộp** — kỳ {ky_chon}")

        # Chọn PGD để lọc trước khi xuất
        ds_pgd_thieu = ["Tất cả"] + sorted(df_don_doc["Đơn vị"].unique().tolist())
        pgd_xuat = st.selectbox("Lọc đơn vị trước khi xuất", ds_pgd_thieu, key="dd_pgd_xuat")
        df_xuat = df_don_doc if pgd_xuat == "Tất cả" else df_don_doc[df_don_doc["Đơn vị"] == pgd_xuat]

        st.dataframe(df_xuat, hide_index=True, width="stretch")

        ten_file_goc = f"don_doc_{ky_chon.replace('/', '-')}"
        username_xuat = st.session_state.get("txt_username", "unknown")

        col_excel, col_pdf, col_pdf_hd, _ = st.columns([1, 1, 1.4, 3])

        with col_excel:
            if st.button("📥 Excel", key="btn_dd_excel", width="stretch", type="primary"):
                st.session_state["_don_doc_bytes"] = xuat_excel({"Đôn đốc nộp báo cáo": df_xuat})
                st.session_state["_don_doc_ten"] = f"{ten_file_goc}.xlsx"
            if st.session_state.get("_don_doc_bytes"):
                st.download_button(
                    "⬇ Tải Excel",
                    data=st.session_state["_don_doc_bytes"],
                    file_name=st.session_state["_don_doc_ten"],
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="dl_don_doc",
                )

        with col_pdf:
            if st.button("📄 PDF", key="btn_dd_pdf", width="stretch", type="primary"):
                try:
                    from pdf_service import xuat_pdf
                    with st.spinner("Đang tạo PDF..."):
                        pdf_bytes = xuat_pdf(
                            df_xuat,
                            f"Danh sách tiến độ nộp báo cáo — kỳ {ky_chon}",
                            username_xuat,
                            cols_tien=[],
                            them_dong_tong=False,
                        )
                    st.session_state["_dd_pdf_bytes"] = pdf_bytes
                    st.session_state["_dd_pdf_ten"] = f"{ten_file_goc}.pdf"
                except Exception as e:
                    st.error(f"❌ Lỗi PDF: {e}")
            if st.session_state.get("_dd_pdf_bytes"):
                st.download_button(
                    "⬇ Tải PDF",
                    data=st.session_state["_dd_pdf_bytes"],
                    file_name=st.session_state["_dd_pdf_ten"],
                    mime="application/pdf",
                    key="dl_dd_pdf",
                )

        with col_pdf_hd:
            if st.button("📄 PDF có Header", key="btn_dd_pdf_hd", width="stretch", type="primary"):
                try:
                    from pdf_service import xuat_pdf_group_header
                    with st.spinner("Đang tạo PDF..."):
                        pdf_bytes = xuat_pdf_group_header(
                            df_xuat,
                            tieu_de="DANH SÁCH TIẾN ĐỘ NỘP BÁO CÁO",
                            nhom_theo="Đơn vị",
                            nguoi_xuat=username_xuat,
                            tieu_de_phu=f"Kỳ: {ky_chon}",
                            loai_van_ban="DANH SÁCH",
                        )
                    st.session_state["_dd_pdf_hd_bytes"] = pdf_bytes
                    st.session_state["_dd_pdf_hd_ten"] = f"{ten_file_goc}_header.pdf"
                except Exception as e:
                    st.error(f"❌ Lỗi PDF Header: {e}")
            if st.session_state.get("_dd_pdf_hd_bytes"):
                st.download_button(
                    "⬇ Tải PDF Header",
                    data=st.session_state["_dd_pdf_hd_bytes"],
                    file_name=st.session_state["_dd_pdf_hd_ten"],
                    mime="application/pdf",
                    key="dl_dd_pdf_hd",
                )


# ── Tab 2: Danh sách nộp ─────────────────────────────────────────────────────

def _render_danh_sach(df: pd.DataFrame, deadline_cfg: dict, is_cn: bool, pgd_user: str | None) -> None:
    if df.empty:
        st.info("Chưa có dữ liệu.")
        return

    col1, col2, col3 = st.columns(3)
    with col1:
        ds_ky = ["Tất cả"] + sorted(df["ky_bao_cao"].dropna().unique().tolist(), reverse=True)
        ky_chon = st.selectbox("Kỳ báo cáo", ds_ky, key="ds_ky")
    with col2:
        ds_loai = ["Tất cả"] + sorted(df["loai_bao_cao"].dropna().unique().tolist())
        loai_chon = st.selectbox("Loại báo cáo", ds_loai, key="ds_loai")
    with col3:
        if is_cn:
            ds_don_vi = ["Tất cả"] + sorted(df["ten_pgd"].dropna().unique().tolist())
            pgd_chon = st.selectbox("Đơn vị", ds_don_vi, key="ds_pgd")
        else:
            pgd_chon = pgd_user or "Tất cả"
            st.caption(f"Đơn vị: **{pgd_chon}**")

    df_loc = df.copy()
    if ky_chon != "Tất cả":
        df_loc = df_loc[df_loc["ky_bao_cao"] == ky_chon]
    if loai_chon != "Tất cả":
        df_loc = df_loc[df_loc["loai_bao_cao"] == loai_chon]
    if pgd_chon and pgd_chon != "Tất cả":
        df_loc = df_loc[df_loc["ten_pgd"] == pgd_chon]

    df_loc = _gan_trang_thai(df_loc, deadline_cfg)
    df_loc["tt_hien"] = df_loc["tt"].map(lambda x: f"{_EMOJI.get(x, '')} {_LABEL.get(x, x)}")

    st.caption(f"Hiển thị {len(df_loc)} / {len(df)} lượt nộp")

    df_hien = df_loc[["thoi_gian", "ho_ten", "ten_pgd", "loai_bao_cao",
                       "ky_bao_cao", "tt_hien", "noi_dung", "file_dinh_kem"]].copy()
    df_hien["thoi_gian"] = df_hien["thoi_gian"].dt.strftime("%d/%m/%Y %H:%M")
    df_hien = df_hien.rename(columns={
        "thoi_gian": "Thời gian", "ho_ten": "Họ tên", "ten_pgd": "Đơn vị",
        "loai_bao_cao": "Loại", "ky_bao_cao": "Kỳ",
        "tt_hien": "Trạng thái", "noi_dung": "Nội dung", "file_dinh_kem": "File",
    })
    st.dataframe(
        df_hien, width="stretch", hide_index=True,
        column_config={
            "File": st.column_config.LinkColumn("File", display_text="📎 Xem"),
            "Nội dung": st.column_config.TextColumn(width="large"),
        },
    )

    st.divider()
    col_excel, col_pdf, _ = st.columns([1, 1, 5])
    with col_excel:
        if st.button("📥 Xuất Excel", key="btn_xuat_tdn", width="stretch", type="primary"):
            df_export = df_loc.drop(columns=["tt", "tt_hien"], errors="ignore")
            st.session_state["_excel_tdn_bytes"] = xuat_excel({"Tiến độ nộp báo cáo": df_export})
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


# ── Tab 3: Cài đặt deadline ───────────────────────────────────────────────────

def _render_cai_dat(df: pd.DataFrame, deadline_cfg: dict, username: str) -> None:
    st.markdown("**Cấu hình deadline cho từng loại báo cáo × kỳ**")
    st.caption("Sau khi lưu, cột Trạng thái sẽ tự tính 🟢 Đúng hạn / 🟡 Trễ / 🔴 Chưa nộp.")

    ds_loai = sorted(df["loai_bao_cao"].dropna().unique().tolist()) if not df.empty else []
    ds_ky = sorted(df["ky_bao_cao"].dropna().unique().tolist(), reverse=True) if not df.empty else []

    if not ds_loai:
        st.info("Chưa có dữ liệu từ Google Sheets để cấu hình deadline.")
        return

    col1, col2 = st.columns(2)
    with col1:
        loai_chon = st.selectbox("Loại báo cáo", ds_loai, key="cd_loai")
    with col2:
        ky_chon = st.selectbox("Kỳ báo cáo", ds_ky, key="cd_ky")

    dl_hien = deadline_cfg.get(loai_chon, {}).get(ky_chon)
    dl_default = pd.to_datetime(dl_hien).date() if dl_hien else date.today()

    dl_moi = st.date_input(
        f"Deadline — **{loai_chon}** / kỳ **{ky_chon}**",
        value=dl_default,
        key="cd_dl_input",
        format="DD/MM/YYYY",
    )

    if st.button("💾 Lưu deadline", key="cd_btn_luu", type="primary"):
        cfg_moi = {k: dict(v) for k, v in deadline_cfg.items()}
        if loai_chon not in cfg_moi:
            cfg_moi[loai_chon] = {}
        cfg_moi[loai_chon][ky_chon] = dl_moi.strftime("%Y-%m-%d")
        _luu_deadline_config(cfg_moi, username)
        st.success(f"✅ Đã lưu: **{loai_chon}** — kỳ **{ky_chon}** → deadline {dl_moi.strftime('%d/%m/%Y')}")
        st.rerun()

    st.divider()
    st.markdown("**Danh sách deadline đã cài đặt**")
    rows = [{"Loại báo cáo": loai, "Kỳ": ky, "Deadline": dl}
            for loai, kys in deadline_cfg.items() for ky, dl in kys.items()]
    if rows:
        st.dataframe(
            pd.DataFrame(rows).sort_values(["Loại báo cáo", "Kỳ"]),
            hide_index=True, width="stretch",
        )
    else:
        st.info("Chưa có deadline nào. Dùng form trên để thêm.")


# ── Entry point ───────────────────────────────────────────────────────────────

def render(tab: DeltaGenerator = None, **kwargs) -> None:
    role_raw = str(kwargs.get("role", "user") or "user")
    role_n = normalize_role(role_raw)
    is_cn = la_phan_he_cn(role_n)
    pgd_user = kwargs.get("pgd_user")
    username = kwargs.get("username", st.session_state.get("txt_username", "unknown"))

    ctx = tab if tab is not None else st.container()
    with ctx:
        st.subheader("📋 Tiến độ Báo cáo của PGD")
        st.caption("Dữ liệu từ Google Form · Tự động cập nhật mỗi 5 phút")

        with st.expander("📖 Hướng dẫn vận hành", expanded=False):
            st.markdown("""
**Quy trình vận hành — Tiến độ Báo cáo của PGD**

---

**Bước 1 — Cài đặt deadline** *(Phòng KH-NV thực hiện 1 lần mỗi kỳ)*
- Vào tab **⚙️ Cài đặt deadline**
- Chọn loại báo cáo → chọn kỳ → nhập ngày deadline → bấm **Lưu**
- Sau khi lưu, hệ thống tự tính trạng thái 🟢 / 🟡 / 🔴 cho từng đơn vị

---

**Bước 2 — Theo dõi tiến độ** *(Phòng KH-NV theo dõi hàng ngày)*
- Vào tab **📊 Tổng quan** → chọn kỳ báo cáo
- Xem ma trận **PGD × Loại báo cáo** — nhìn ngay đơn vị nào còn thiếu
- Bên dưới ma trận: danh sách chi tiết các báo cáo chưa nộp

---

**Bước 3 — Đôn đốc PGD chưa nộp** *(Khi gần hoặc quá deadline)*
- Trong danh sách chưa nộp: chọn lọc theo từng đơn vị nếu cần
- Bấm **📥 Excel** hoặc **📄 PDF** / **📄 PDF có Header** để xuất danh sách
- Dùng file xuất để gọi điện / nhắn Zalo đôn đốc từng PGD

---

**Bước 4 — PGD nộp báo cáo**
- PGD nộp qua **Google Form** (link form do Phòng KH-NV cung cấp)
- Sau khi nộp, dữ liệu tự vào Google Sheets → hệ thống cập nhật sau **5 phút**
- PGD có thể vào tab **📋 Danh sách nộp** để kiểm tra báo cáo đã được ghi nhận chưa

---

| Trạng thái | Ý nghĩa |
|---|---|
| 🟢 Đúng hạn | Nộp trước hoặc đúng ngày deadline |
| 🟡 Trễ hạn | Đã nộp nhưng sau deadline |
| 🔴 Chưa nộp | Chưa có dữ liệu trong kỳ này |
| ⚪ Chưa nộp | Chưa nộp — chưa có deadline được cài |
""")

        if not Path(CREDENTIALS_FILE).exists():
            st.warning(
                "⚠️ Chưa cấu hình Google Sheets. "
                "Đặt file `credentials.json` (Service Account) vào thư mục gốc."
            )
            return

        col_r, _ = st.columns([1, 7])
        with col_r:
            if st.button("🔄 Làm mới", key="tdn_refresh"):
                st.cache_data.clear()
                st.rerun()

        df = _doc_du_lieu()
        deadline_cfg = _doc_deadline_config()

        # PGD role: chỉ thấy dữ liệu của PGD mình
        if not is_cn and pgd_user:
            df = df[df["ten_pgd"] == pgd_user]

        can_config = role_n in ("admin_cn", "manager_cn", "admin", "manager")

        if can_config:
            t1, t2, t3 = st.tabs(["📊 Tổng quan", "📋 Danh sách nộp", "⚙️ Cài đặt deadline"])
        else:
            t1, t2 = st.tabs(["📊 Tổng quan", "📋 Danh sách nộp"])
            t3 = None

        with t1:
            _render_tong_quan(df, deadline_cfg, is_cn, pgd_user)

        with t2:
            _render_danh_sach(df, deadline_cfg, is_cn, pgd_user)

        if t3 is not None:
            with t3:
                _render_cai_dat(df, deadline_cfg, username)
