"""Tiến độ nộp báo cáo định kỳ của các PGD — đọc từ Google Sheets."""


from __future__ import annotations

from logger import get_logger
logger = get_logger(__name__)

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
       "noi_dung", "file_dinh_kem", "ho_ten"]

DS_PGD_ALL = [DON_VI_CHI_NHANH] + DS_PGD

_EMOJI = {"dung_han": "🟢", "tre": "🟡", "chua_nop": "🔴", "da_nop": "⚪"}
_LABEL = {"dung_han": "Đúng hạn", "tre": "Trễ hạn", "chua_nop": "Chưa nộp", "da_nop": "Đã nộp"}


# ── Kết nối & đọc Google Sheets ──────────────────────────────────────────────

@st.cache_resource(show_spinner=False)
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
    except Exception as e:
        logger.error("_ket_noi_gsheet: fallback oauth2client — %s", e, exc_info=True)
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
        df = pd.DataFrame([r[:len(COT)] for r in data[1:]], columns=COT)
        df["thoi_gian"] = pd.to_datetime(df["thoi_gian"], dayfirst=True, errors="coerce")
        return df
    except Exception as e:
        logger.error("Lỗi trong khối except: %s", e, exc_info=True)
        st.error(f"Lỗi kết nối GSheet: {e}")
        return pd.DataFrame(columns=COT)


# ── Deadline config ───────────────────────────────────────────────────────────

def _doc_deadline_config() -> dict:
    """Đọc cấu hình deadline: {loai_bao_cao: 'YYYY-MM-DD'}"""
    return db.doc_kv("bao_cao_deadline_config") or {}


def _luu_deadline_config(cfg: dict, username: str) -> None:
    db.ghi_kv("bao_cao_deadline_config", cfg, username)
    db.ghi_audit(username, "luu_deadline_bao_cao", f"{len(cfg)} deadline đã lưu")


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
    except Exception as e:
        logger.error("_phan_loai: parse ngay loi — %s", e, exc_info=True)
        return "da_nop"


def _gan_trang_thai(df: pd.DataFrame, deadline_cfg: dict) -> pd.DataFrame:
    df = df.copy()
    df["tt"] = df.apply(
        lambda r: _phan_loai(r["thoi_gian"], deadline_cfg.get(r["loai_bao_cao"])),
        axis=1,
    )
    return df


# ── Tab 1: Tổng quan ──────────────────────────────────────────────────────────

def _render_tong_quan(df: pd.DataFrame, deadline_cfg: dict, is_cn: bool, pgd_user: str | None) -> None:
    if df.empty:
        st.info("Chưa có dữ liệu từ Google Sheets.")
        return

    ds_loai = sorted(df["loai_bao_cao"].dropna().unique().tolist())
    ds_pgd_scope = [pgd_user] if (not is_cn and pgd_user) else DS_PGD_ALL

    df = _gan_trang_thai(df, deadline_cfg)

    dung_han = (df["tt"] == "dung_han").sum()
    tre = (df["tt"] == "tre").sum()
    da_nop = len(df)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Tổng lượt nộp", da_nop)
    c2.metric("🟢 Đúng hạn", dung_han)
    c3.metric("🟡 Trễ hạn", tre)
    tong_can = len(ds_pgd_scope) * len(ds_loai)
    chua_nop = max(0, tong_can - da_nop)
    c4.metric("🔴 Chưa nộp", chua_nop)

    st.divider()
    st.markdown("**Ma trận trạng thái — PGD × Loại báo cáo**")

    rows = []
    for pgd in ds_pgd_scope:
        row: dict = {"Đơn vị": pgd}
        for loai in ds_loai:
            match = df[(df["ten_pgd"] == pgd) & (df["loai_bao_cao"] == loai)]
            if match.empty:
                has_dl = loai in deadline_cfg
                row[loai] = "🔴 Chưa nộp" if has_dl else "⚪ Chưa nộp"
            else:
                tt = match.sort_values("thoi_gian").iloc[-1]["tt"]
                row[loai] = f"{_EMOJI[tt]} {_LABEL[tt]}"
        rows.append(row)

    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)

    ds_don_doc = []
    for r in rows:
        for loai in ds_loai:
            if "🔴" in str(r.get(loai, "")):
                dl = deadline_cfg.get(loai, "")
                ds_don_doc.append({
                    "Đơn vị": r["Đơn vị"],
                    "Loại báo cáo": loai,
                    "Deadline": dl or "Chưa cài",
                })

    if ds_don_doc:
        df_don_doc = pd.DataFrame(ds_don_doc)
        st.divider()
        st.warning(f"⚠️ **{len(df_don_doc)} báo cáo chưa nộp**")

        ds_pgd_thieu = ["Tất cả"] + sorted(df_don_doc["Đơn vị"].unique().tolist())
        pgd_xuat = st.selectbox("Lọc đơn vị trước khi xuất", ds_pgd_thieu, key="dd_pgd_xuat")
        df_xuat = df_don_doc if pgd_xuat == "Tất cả" else df_don_doc[df_don_doc["Đơn vị"] == pgd_xuat]

        st.dataframe(df_xuat, hide_index=True, use_container_width=True)

        ten_file_goc = "don_doc_bao_cao"
        username_xuat = st.session_state.get("txt_username", "unknown")

        col_excel, col_pdf, col_pdf_hd, _ = st.columns([1, 1, 1.4, 3])

        with col_excel:
            if st.button("📥 Excel", key="btn_dd_excel", use_container_width=True, type="primary"):
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
            if st.button("📄 PDF", key="btn_dd_pdf", use_container_width=True, type="primary"):
                try:
                    from pdf_service import xuat_pdf
                    with st.spinner("Đang tạo PDF..."):
                        pdf_bytes = xuat_pdf(
                            df_xuat,
                            "Danh sách tiến độ nộp báo cáo",
                            username_xuat,
                            cols_tien=[],
                            them_dong_tong=False,
                        )
                    st.session_state["_dd_pdf_bytes"] = pdf_bytes
                    st.session_state["_dd_pdf_ten"] = f"{ten_file_goc}.pdf"
                except Exception as e:
                    logger.error("Lỗi trong khối except: %s", e, exc_info=True)
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
            if st.button("📄 PDF có Header", key="btn_dd_pdf_hd", use_container_width=True, type="primary"):
                try:
                    from pdf_service import xuat_pdf_group_header
                    with st.spinner("Đang tạo PDF..."):
                        pdf_bytes = xuat_pdf_group_header(
                            df_xuat,
                            tieu_de="DANH SÁCH TIẾN ĐỘ NỘP BÁO CÁO",
                            nhom_theo="Đơn vị",
                            nguoi_xuat=username_xuat,
                            tieu_de_phu="",
                            loai_van_ban="DANH SÁCH",
                        )
                    st.session_state["_dd_pdf_hd_bytes"] = pdf_bytes
                    st.session_state["_dd_pdf_hd_ten"] = f"{ten_file_goc}_header.pdf"
                except Exception as e:
                    logger.error("Lỗi trong khối except: %s", e, exc_info=True)
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

    col1, col2 = st.columns(2)
    with col1:
        ds_loai = ["Tất cả"] + sorted(df["loai_bao_cao"].dropna().unique().tolist())
        loai_chon = st.selectbox("Loại báo cáo", ds_loai, key="ds_loai")
    with col2:
        if is_cn:
            ds_don_vi = ["Tất cả"] + sorted(df["ten_pgd"].dropna().unique().tolist())
            pgd_chon = st.selectbox("Đơn vị", ds_don_vi, key="ds_pgd")
        else:
            pgd_chon = pgd_user or "Tất cả"
            st.caption(f"Đơn vị: **{pgd_chon}**")

    df_loc = df.copy()
    if loai_chon != "Tất cả":
        df_loc = df_loc[df_loc["loai_bao_cao"] == loai_chon]
    if pgd_chon and pgd_chon != "Tất cả":
        df_loc = df_loc[df_loc["ten_pgd"] == pgd_chon]

    df_loc = _gan_trang_thai(df_loc, deadline_cfg)
    df_loc["tt_hien"] = df_loc["tt"].map(lambda x: f"{_EMOJI.get(x, '')} {_LABEL.get(x, x)}")

    st.caption(f"Hiển thị {len(df_loc)} / {len(df)} lượt nộp")

    df_hien = df_loc[["thoi_gian", "ho_ten", "ten_pgd", "loai_bao_cao",
                       "tt_hien", "noi_dung", "file_dinh_kem"]].copy()
    df_hien["thoi_gian"] = df_hien["thoi_gian"].dt.strftime("%d/%m/%Y %H:%M")
    df_hien = df_hien.rename(columns={
        "thoi_gian": "Thời gian", "ho_ten": "Họ tên", "ten_pgd": "Đơn vị",
        "loai_bao_cao": "Loại", "tt_hien": "Trạng thái",
        "noi_dung": "Nội dung", "file_dinh_kem": "File",
    })
    st.dataframe(
        df_hien, use_container_width=True, hide_index=True,
        column_config={
            "File": st.column_config.LinkColumn("File", display_text="📎 Xem"),
            "Nội dung": st.column_config.TextColumn(width="large"),
        },
    )

    st.divider()
    col_excel, col_pdf, _ = st.columns([1, 1, 5])
    with col_excel:
        if st.button("📥 Xuất Excel", key="btn_xuat_tdn", use_container_width=True, type="primary"):
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
    st.markdown("**Cấu hình deadline cho từng loại báo cáo**")
    st.caption("Sau khi lưu, cột Trạng thái sẽ tự tính 🟢 Đúng hạn / 🟡 Trễ / 🔴 Chưa nộp.")

    ds_loai = sorted(df["loai_bao_cao"].dropna().unique().tolist()) if not df.empty else []

    if not ds_loai:
        st.info("Chưa có dữ liệu từ Google Sheets để cấu hình deadline.")
        return

    loai_chon = st.selectbox("Loại báo cáo", ds_loai, key="cd_loai")

    dl_hien = deadline_cfg.get(loai_chon)
    dl_default = pd.to_datetime(dl_hien).date() if dl_hien else date.today()

    dl_moi = st.date_input(
        f"Deadline cho **{loai_chon}**",
        value=dl_default, format="DD/MM/YYYY",
        key="cd_dl_input",
    )

    if st.button("💾 Lưu deadline", key="cd_btn_luu", type="primary"):
        cfg_moi = dict(deadline_cfg)
        cfg_moi[loai_chon] = dl_moi.strftime("%Y-%m-%d")
        _luu_deadline_config(cfg_moi, username)
        st.success(f"✅ Đã lưu: **{loai_chon}** → deadline {dl_moi.strftime('%d/%m/%Y')}")
        st.rerun()

    st.divider()
    st.markdown("**Danh sách deadline đã cài đặt**")
    rows = [{"Loại báo cáo": loai, "Deadline": dl}
            for loai, dl in deadline_cfg.items()]
    if rows:
        st.dataframe(
            pd.DataFrame(rows).sort_values("Loại báo cáo"),
            hide_index=True, use_container_width=True,
        )
    else:
        st.info("Chưa có deadline nào. Dùng form trên để thêm.")


# ── Tab Hướng dẫn với Mockup ───────────────────────────────────────────────────

def _render_huong_dan_mockup() -> None:
    """Hiển thị hướng dẫn sử dụng và mockup luồng xử lý."""
    st.markdown("## 📖 Hướng dẫn sử dụng")
    
    col1, col2 = st.columns(2)
    with col1:
        st.info("""
        **👤 Dành cho PGD**
        
        1. Nhận **link Google Form** từ Phòng KH-NV
        2. Truy cập Form → điền đầy đủ thông tin
        3. Upload file báo cáo lên **Google Drive**
        4. Copy link Drive dán vào Form
        5. Bấm **"Gửi báo cáo"**
        6. Đợi ~5 phút, kiểm tra tab *Danh sách nộp*
        """)
    with col2:
        st.success("""
        **👔 Dành cho Phòng KH-NV**
        
        1. **Cài đặt deadline** trước mỗi kỳ báo cáo
        2. Theo dõi tiến độ qua tab *Tổng quan*
        3. Xem ma trận PGD × Loại báo cáo
        4. Danh sách 🔴 Chưa nộp tự động hiện
        5. Xuất Excel/PDF để **đôn đốc** các PGD
        6. Gọi điện/Zalo nhắc nhở đơn vị trễ hạn
        """)
    
    st.divider()
    st.markdown("### 🔄 Quy trình xử lý")
    
    # Flow diagram bằng HTML
    flow_html = """
    <div style="display: flex; align-items: center; justify-content: center; gap: 15px; 
                flex-wrap: wrap; padding: 20px; background: #f8f9fa; border-radius: 12px;">
        <div style="text-align: center; padding: 15px; background: #e3f2fd; border-radius: 10px; min-width: 120px;">
            <div style="font-size: 32px;">📝</div>
            <div style="font-weight: 600; font-size: 13px; margin-top: 5px;">PGD nộp Form</div>
        </div>
        <div style="color: #666; font-size: 24px;">→</div>
        <div style="text-align: center; padding: 15px; background: #e8f5e9; border-radius: 10px; min-width: 120px;">
            <div style="font-size: 32px;">📊</div>
            <div style="font-weight: 600; font-size: 13px; margin-top: 5px;">Lưu Sheets</div>
        </div>
        <div style="color: #666; font-size: 24px;">→</div>
        <div style="text-align: center; padding: 15px; background: #fff3e0; border-radius: 10px; min-width: 120px;">
            <div style="font-size: 32px;">⚙️</div>
            <div style="font-weight: 600; font-size: 13px; margin-top: 5px;">VBSP đọc (5 phút)</div>
        </div>
        <div style="color: #666; font-size: 24px;">→</div>
        <div style="text-align: center; padding: 15px; background: #fce4ec; border-radius: 10px; min-width: 120px;">
            <div style="font-size: 32px;">📈</div>
            <div style="font-weight: 600; font-size: 13px; margin-top: 5px;">KH-NV theo dõi</div>
        </div>
    </div>
    """
    st.html(flow_html)
    
    st.caption("💡 Dữ liệu từ Form → Sheets là **tức thời** | Sheets → VBSP-SCM có độ trễ **5 phút** (do cache)")
    
    st.divider()
    st.markdown("### 📋 Các trạng thái báo cáo")
    
    status_cols = st.columns(4)
    with status_cols[0]:
        st.metric("🟢 Đúng hạn", "Nộp ≤ deadline")
    with status_cols[1]:
        st.metric("🟡 Trễ hạn", "Nộp > deadline")
    with status_cols[2]:
        st.metric("🔴 Chưa nộp", "Quá hạn, chưa có data")
    with status_cols[3]:
        st.metric("⚪ Chưa nộp", "Chưa có deadline")
    
    st.divider()
    with st.expander("📊 Xem mockup chi tiết (Google Form mẫu)", expanded=False):
        try:
            mockup_path = Path(__file__).parent.parent / "docs" / "mockup_bc_tu_pgd.html"
            if mockup_path.exists():
                with open(mockup_path, "r", encoding="utf-8") as f:
                    mockup_content = f.read()
                # Chỉ lấy phần body và giới hạn chiều cao
                st.components.v1.html(
                    f'<div style="height: 600px; overflow-y: auto; border: 1px solid #ddd; border-radius: 8px;">{mockup_content}</div>',
                    height=620,
                    scrolling=True
                )
            else:
                st.info("File mockup chưa được tạo. Vui lòng kiểm tra docs/mockup_bc_tu_pgd.html")
        except Exception as e:
            logger.error("render mockup html: %s", e, exc_info=True)
            st.error(f"Không thể tải mockup: {e}")


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

        # Tab hướng dẫn hiển thị cho tất cả users
        if can_config:
            # Thứ tự tab theo quy trình vận hành trong hướng dẫn:
            # Bước 1: Cài đặt deadline → Bước 2: Tổng quan → Bước 4: Danh sách nộp
            t0, t1, t2, t3 = st.tabs(["📖 Hướng dẫn PGD gửi BC về CN", "⚙️ Cài đặt deadline", "📊 Tổng quan", "📋 Danh sách nộp"])
        else:
            t0, t2, t3 = st.tabs(["📖 Hướng dẫn PGD gửi BC về CN", "📊 Tổng quan", "📋 Danh sách nộp"])
            t1 = None

        with t0:
            _render_huong_dan_mockup()

        if t1 is not None:
            with t1:
                _render_cai_dat(df, deadline_cfg, username)

        with t2:
            _render_tong_quan(df, deadline_cfg, is_cn, pgd_user)

        with t3:
            _render_danh_sach(df, deadline_cfg, is_cn, pgd_user)
