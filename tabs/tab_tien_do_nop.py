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
from config import BASE_DIR, DS_PGD, DON_VI_CHI_NHANH
from utils import xuat_excel


SHEET_ID = "15Ev2rTv6khLFaMpAiMwqJCVC_33ocJ-6cp016RGNkYk"
SHEET_TAB = "TIENDO_BAOCAO"
COT = ["thoi_gian", "email", "ten_pgd", "loai_bao_cao",
       "ky_bao_cao", "noi_dung", "file_dinh_kem", "ho_ten"]

DS_PGD_ALL = [DON_VI_CHI_NHANH] + DS_PGD

_EMOJI = {"dung_han": "🟢", "tre": "🟡", "chua_nop": "🔴", "da_nop": "⚪"}
_LABEL = {"dung_han": "Đúng hạn", "tre": "Trễ hạn", "chua_nop": "Chưa nộp", "da_nop": "Đã nộp"}

_EMOJI_STRIP = ("🟢", "🟡", "🔴", "⚪", "⚠️", "📝")

def _clean_trang_thai(val: str) -> str:
    """Bỏ emoji + badge cho PDF — thiếu file → Trễ hạn."""
    if "⚠️" in str(val):
        return "Trễ hạn"
    text = str(val)
    for ch in _EMOJI_STRIP:
        text = text.replace(ch, "")
    return text.replace("*", "").strip()

def _clear_export_cache():
    """Xóa bytes export cũ khi user đổi filter — tránh tải nhầm file."""
    for k in ["_don_doc_bytes", "_don_doc_ten",
              "_dd_pdf_bytes", "_dd_pdf_bytes__ten",
              "_dd_pdf_dv_bytes", "_dd_pdf_dv_bytes__ten"]:
        st.session_state.pop(k, None)


# ── Kết nối & đọc Google Sheets ──────────────────────────────────────────────

@st.cache_resource(show_spinner=False)
def _ket_noi_gsheet():
    _p = Path(__file__).resolve().parent.parent / "credentials.json"
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]
    if not _p.exists():
        raise FileNotFoundError(f"Không tìm thấy file credentials: {_p}")
    try:
        import gspread
    except ImportError:
        raise RuntimeError("Thiếu thư viện gspread. Cài đặt: pip install gspread google-auth")
    try:
        return gspread.service_account(filename=_p, scopes=scope)
    except Exception as e:
        logger.error("_ket_noi_gsheet: fallback oauth2client — %s", e, exc_info=True)
        try:
            from oauth2client.service_account import ServiceAccountCredentials
        except ImportError:
            raise RuntimeError("Không thể kết nối GSheet: cần cài google-auth hoặc oauth2client.")
        creds = ServiceAccountCredentials.from_json_keyfile_name(_p, scope)
        return gspread.authorize(creds)


def _chuan_hoa_ten_pgd(raw: str) -> str:
    if not isinstance(raw, str) or not raw.strip():
        return raw
    s = raw.strip()
    for prefix in ("Phòng giao dịch ", "Phong giao dich ", "PGD ", "pgd "):
        if s.lower().startswith(prefix.lower()):
            return "PGD " + s[len(prefix):].strip()
    return s


@st.cache_data(ttl=300)
def _doc_du_lieu() -> pd.DataFrame:
    try:
        client = _ket_noi_gsheet()
        sheet = client.open_by_key(SHEET_ID).worksheet(SHEET_TAB)
        data = sheet.get_all_values()
        if len(data) <= 1:
            return pd.DataFrame(columns=COT)
        df = pd.DataFrame([r[:len(COT)] for r in data[1:]], columns=COT)
        df["ten_pgd"] = df["ten_pgd"].apply(_chuan_hoa_ten_pgd)
        df["thoi_gian"] = pd.to_datetime(df["thoi_gian"], dayfirst=True, errors="coerce")
        return df
    except Exception as e:
        logger.error("Lỗi trong khối except: %s", e, exc_info=True)
        st.error(f"Lỗi kết nối GSheet: {e}")
        return pd.DataFrame(columns=COT)


# ── Thời hạn hoàn thành ────────────────────────────────────────────────────

def _doc_deadline_config() -> dict:
    """Đọc cấu hình deadline: {loai_bao_cao: 'YYYY-MM-DD'} — tự normalize từ định dạng cũ."""
    raw = db.doc_kv("bao_cao_deadline_config") or {}
    normalized = {}
    for key, val in raw.items():
        if isinstance(val, dict):
            vals = [v for v in val.values() if isinstance(v, str)]
            if vals:
                normalized[key] = vals[0]
        elif isinstance(val, str):
            normalized[key] = val
    return normalized


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


# ── Manual submit log ─────────────────────────────────────────────────────────

_MANUAL_KV_KEY = "manual_nop_tdn"

def _doc_manual_log() -> dict:
    """Đọc danh sách đánh dấu thủ công: {(pgd, loai): entry_dict}"""
    raw = db.doc_kv(_MANUAL_KV_KEY)
    if not isinstance(raw, list):
        return {}
    result = {}
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        pgd = entry.get("pgd")
        loai = entry.get("loai")
        if pgd and loai:
            result[(pgd, loai)] = entry
    return result

def _doc_manual_log_raw() -> list[dict]:
    """Đọc danh sách đánh dấu thủ công dạng list nguyên gốc."""
    raw = db.doc_kv(_MANUAL_KV_KEY)
    if isinstance(raw, list):
        return raw
    return []

def _luu_manual_log(ds: list[dict], username: str) -> None:
    db.ghi_kv(_MANUAL_KV_KEY, ds, username)
    db.ghi_audit(username, "tdn_manual_submit", f"{len(ds)} đánh dấu thủ công")


# ── Tab 1: Tổng quan ──────────────────────────────────────────────────────────

def _render_tong_quan(df: pd.DataFrame, deadline_cfg: dict, is_cn: bool, pgd_user: str | None, username: str, can_config: bool) -> None:
    if df.empty:
        st.info("Chưa có dữ liệu từ Google Sheets.")
        return

    if not deadline_cfg:
        st.info("ℹ️ Chưa có thời hạn hoàn thành nào được cài đặt. Vào tab **⚙️ Cài đặt thời hạn** để thêm.")
        return

    # Chỉ hiển thị loại báo cáo có thời hạn — xóa thời hạn là không còn theo dõi
    ds_loai = sorted(deadline_cfg.keys())
    ds_pgd_scope = [pgd_user] if (not is_cn and pgd_user) else DS_PGD_ALL

    df = _gan_trang_thai(df, deadline_cfg)
    manual_map = _doc_manual_log()

    # Build ma trận trước — metrics tính từ đây để nhất quán với những gì hiển thị
    rows = []
    for pgd in ds_pgd_scope:
        row: dict = {"Đơn vị": pgd}
        for loai in ds_loai:
            manual_key = (pgd, loai)
            entry = manual_map.get(manual_key)
            ghi_de = entry.get("ghi_de", True) if entry else False

            if entry and ghi_de:
                # Ghi đè: trạng thái tính từ ngày manual, badge *
                ngay = pd.to_datetime(entry.get("ngay_nop"))
                tt = _phan_loai(ngay, deadline_cfg.get(loai))
                row[loai] = f"{_EMOJI[tt]} {_LABEL[tt]} *"
            else:
                match = df[(df["ten_pgd"] == pgd) & (df["loai_bao_cao"] == loai)]
                if match.empty:
                    row[loai] = "🔴 Chưa nộp" if loai in deadline_cfg else "⚪ Chưa nộp"
                else:
                    last = match.sort_values("thoi_gian").iloc[-1]
                    tt = last["tt"]
                    # ⚠️ auto-detect thiếu file từ GSheet
                    co_file = str(last.get("file_dinh_kem", "")).strip()
                    badge_file = " ⚠️" if not co_file else ""
                    # 📝 có ghi chú nhưng không ghi đè
                    badge_note = " 📝" if entry and not ghi_de else ""
                    row[loai] = f"{_EMOJI[tt]} {_LABEL[tt]}{badge_file}{badge_note}"
        rows.append(row)

    # Metrics từ rows — khớp chính xác với ma trận
    dung_han = sum(1 for r in rows for l in ds_loai if "🟢" in str(r.get(l, "")))
    tre      = sum(1 for r in rows for l in ds_loai if "🟡" in str(r.get(l, "")))
    chua_nop = sum(1 for r in rows for l in ds_loai if "🔴" in str(r.get(l, "")))
    da_nop   = dung_han + tre

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Đã nộp (đơn vị × loại)", da_nop)
    c2.metric("🟢 Đúng hạn", dung_han)
    c3.metric("🟡 Trễ hạn", tre)
    c4.metric("🔴 Chưa nộp", chua_nop)

    st.divider()
    st.markdown("**Ma trận trạng thái — PGD × Loại báo cáo**")

    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
    st.caption("* Ghi đè thủ công  ·  ⚠️ Thiếu file đính kèm  ·  📝 Có ghi chú")

    ds_tat_ca = []
    ds_chua = []
    ds_da = []
    for r in rows:
        for loai in ds_loai:
            cell = str(r.get(loai, ""))
            dl = deadline_cfg.get(loai, "")
            dl_hien = dl
            if dl:
                try:
                    dl_hien = pd.to_datetime(dl).strftime("%d/%m/%Y")
                except Exception:
                    dl_hien = dl
            entry = {
                "Đơn vị": r["Đơn vị"],
                "Loại báo cáo": loai,
                "Trạng thái": cell,
                "Thời hạn": dl_hien or "Chưa cài",
            }
            ds_tat_ca.append(entry)
            if "🔴" in cell or "⚠️" in cell:
                ds_chua.append(entry)
            elif "🟢" in cell or "🟡" in cell:
                ds_da.append(entry)

    st.divider()
    st.markdown("### 📥 Xuất báo cáo")

    loai_xuat = st.radio(
        "Chọn loại danh sách để xuất",
        ["Tất cả", "Đã hoàn thành", "Chưa hoàn thành"],
        horizontal=True,
        key="tq_loai_xuat",
        on_change=_clear_export_cache,
    )

    if loai_xuat == "Tất cả":
        ds_xuat = ds_tat_ca
    elif loai_xuat == "Đã hoàn thành":
        ds_xuat = ds_da
    else:
        ds_xuat = ds_chua

    if not ds_xuat:
        st.info(f"Không có báo cáo **{loai_xuat.lower()}**.")
    else:
        if loai_xuat == "Chưa hoàn thành":
            st.warning(f"⚠️ **{len(ds_xuat)} báo cáo chưa hoàn thành**")
        else:
            st.caption(f"📋 {len(ds_xuat)} báo cáo — **{loai_xuat}**")

        df_xuat_full = pd.DataFrame(ds_xuat)
        ds_pgd_thieu = ["Tất cả"] + sorted(df_xuat_full["Đơn vị"].unique().tolist())
        pgd_xuat = st.selectbox("Lọc đơn vị trước khi xuất", ds_pgd_thieu, key="dd_pgd_xuat", on_change=_clear_export_cache)
        df_xuat = df_xuat_full if pgd_xuat == "Tất cả" else df_xuat_full[df_xuat_full["Đơn vị"] == pgd_xuat]

        st.dataframe(df_xuat, hide_index=True, use_container_width=True)

        _slug_map = {"Tất cả": "tat_ca", "Đã hoàn thành": "da_hoan_thanh", "Chưa hoàn thành": "chua_hoan_thanh"}
        ten_file_goc = f"tien_do_{_slug_map.get(loai_xuat, 'xuat')}"
        username_xuat = st.session_state.get("username", "unknown")

        # Import 1 lần — tránh lặp trong từng handler
        from pdf_service import xuat_pdf, xuat_pdf_group_header

        # df đã clean emoji — dùng chung cho cả 2 loại PDF
        df_pdf_base = df_xuat.copy()
        if "Trạng thái" in df_pdf_base.columns:
            df_pdf_base["Trạng thái"] = df_pdf_base["Trạng thái"].apply(_clean_trang_thai)

        # df Excel — clean emoji cho nhất quán với file công vụ
        df_excel = df_xuat.copy()
        if "Trạng thái" in df_excel.columns:
            df_excel["Trạng thái"] = df_excel["Trạng thái"].apply(_clean_trang_thai)

        def _pdf_button(col, btn_label, btn_key, dl_key, file_name, generator_fn):
            """Helper dùng chung: nút generate → lưu session_state → nút download."""
            _ten_key = f"{dl_key}__ten"
            with col:
                if st.button(btn_label, key=btn_key, use_container_width=True, type="primary"):
                    try:
                        with st.spinner("Đang tạo PDF..."):
                            pdf_bytes = generator_fn()
                        st.session_state[dl_key] = pdf_bytes
                        st.session_state[_ten_key] = file_name
                    except Exception as e:
                        logger.error("%s: %s", btn_key, e, exc_info=True)
                        st.error(f"❌ Lỗi PDF: {e}")
                if st.session_state.get(dl_key):
                    st.download_button(
                        "⬇ Tải PDF",
                        data=st.session_state[dl_key],
                        file_name=st.session_state.get(_ten_key, file_name),
                        mime="application/pdf",
                        key=f"dl_{dl_key}",
                    )

        col_excel, col_pdf, col_pdf_dv, _ = st.columns([1, 1, 1.2, 3])

        with col_excel:
            if st.button("📥 Excel", key="btn_dd_excel", use_container_width=True, type="primary"):
                with st.spinner("Đang tạo Excel..."):
                    st.session_state["_don_doc_bytes"] = xuat_excel({f"Tiến độ — {loai_xuat}": df_excel})
                    st.session_state["_don_doc_ten"] = f"{ten_file_goc}.xlsx"
            if st.session_state.get("_don_doc_bytes"):
                st.download_button(
                    "⬇ Tải Excel",
                    data=st.session_state["_don_doc_bytes"],
                    file_name=st.session_state["_don_doc_ten"],
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="dl_don_doc",
                )

        _pdf_button(
            col=col_pdf,
            btn_label="📄 PDF",
            btn_key="btn_dd_pdf",
            dl_key="_dd_pdf_bytes",
            file_name=f"{ten_file_goc}.pdf",
            generator_fn=lambda: xuat_pdf(
                df_pdf_base,
                f"Tiến độ nộp báo cáo — {loai_xuat}",
                username_xuat,
                cols_tien=[],
                them_dong_tong=False,
            ),
        )

        _pdf_button(
            col=col_pdf_dv,
            btn_label="📊 PDF theo đơn vị",
            btn_key="btn_dd_pdf_dv",
            dl_key="_dd_pdf_dv_bytes",
            file_name=f"{ten_file_goc}_theo_don_vi.pdf",
            generator_fn=lambda: xuat_pdf_group_header(
                df_pdf_base,
                tieu_de=f"DANH SÁCH TIẾN ĐỘ NỘP BÁO CÁO — {loai_xuat.upper()}",
                nhom_theo="Đơn vị",
                nguoi_xuat=username_xuat,
                loai_van_ban="DANH SÁCH",
            ),
        )

    # ── Đánh dấu thủ công (chỉ admin CN) ────────────────────────────────────
    if can_config:
        st.divider()
        st.markdown("### ✏️ Đánh dấu thủ công")
        st.caption("Dùng khi PGD gửi báo cáo ngoài Google Form (email, Zip...)")

        manual_ds = _doc_manual_log_raw()

        col_pgd, col_loai, col_ngay = st.columns([2, 2, 1.5])
        with col_pgd:
            pgd_manual = st.selectbox("PGD", ds_pgd_scope, key="man_pgd")
        with col_loai:
            loai_manual = st.selectbox("Loại BC", ds_loai, key="man_loai")
        with col_ngay:
            ngay_manual = st.date_input("Ngày nộp", value=date.today(), format="DD/MM/YYYY", key="man_ngay")

        col_note, col_opt = st.columns([4, 2])
        with col_note:
            ghi_chu_manual = st.text_input(
                "Ghi chú (tùy chọn)",
                placeholder="VD: Nộp qua email, thiếu file BCTC",
                key="man_ghi_chu",
            )
        with col_opt:
            st.write("")
            ghi_de_manual = st.checkbox(
                "Ghi đè trạng thái trên ma trận",
                value=True,
                key="man_ghi_de",
                help="Bỏ chọn nếu chỉ muốn lưu ghi chú, không thay đổi trạng thái 🟢/🟡/🔴",
            )

        col_btn, _ = st.columns([1, 5])
        with col_btn:
            if st.button("✅ Đánh dấu", key="man_btn", type="primary", use_container_width=True):
                ds_moi = [e for e in manual_ds if not (e.get("pgd") == pgd_manual and e.get("loai") == loai_manual)]
                ds_moi.append({
                    "pgd": pgd_manual,
                    "loai": loai_manual,
                    "ngay_nop": ngay_manual.strftime("%Y-%m-%d"),
                    "ghi_chu": ghi_chu_manual.strip(),
                    "ghi_de": ghi_de_manual,
                    "username_tao": username,
                    "tao_luc": pd.Timestamp.now().isoformat(),
                })
                _luu_manual_log(ds_moi, username)
                st.success(f"✅ Đã đánh dấu: **{pgd_manual}** — **{loai_manual}**")
                st.rerun()

        match_form = df[(df["ten_pgd"] == pgd_manual) & (df["loai_bao_cao"] == loai_manual)]
        if not match_form.empty and ghi_de_manual:
            lan_cuoi = match_form.sort_values("thoi_gian").iloc[-1]
            ngay_form = pd.to_datetime(lan_cuoi["thoi_gian"]).strftime("%d/%m/%Y")
            st.warning(
                f"⚠️ **{pgd_manual}** đã nộp **{loai_manual}** qua Google Form "
                f"vào **{ngay_form}**. Đánh dấu sẽ ghi đè trạng thái này trên ma trận."
            )

        if manual_ds:
            st.divider()
            st.caption(f"📌 {len(manual_ds)} đánh dấu thủ công hiện tại:")
            for i, entry in enumerate(manual_ds):
                e_pgd  = entry.get("pgd", "?")
                e_loai = entry.get("loai", "?")
                e_ngay = entry.get("ngay_nop", "?")
                e_note = entry.get("ghi_chu", "")
                e_gde  = entry.get("ghi_de", True)
                try:
                    e_ngay_str = pd.to_datetime(e_ngay).strftime("%d/%m/%Y")
                except Exception:
                    e_ngay_str = str(e_ngay)
                loai_str = "* ghi đè" if e_gde else "📝 ghi chú"
                c1, c2, c3, c4 = st.columns([2, 2, 3, 1])
                with c1:
                    st.write(f"**{e_pgd}**")
                with c2:
                    st.write(f"{e_loai} — {e_ngay_str} ({loai_str})")
                with c3:
                    st.write(e_note if e_note else "—")
                with c4:
                    if st.button("↩️ Bỏ", key=f"man_del_{i}", use_container_width=True):
                        ds_moi = [e for j, e in enumerate(manual_ds) if j != i]
                        _luu_manual_log(ds_moi, username)
                        st.success(f"✅ Đã bỏ: **{e_pgd}** — **{e_loai}**")
                        st.rerun()


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
    st.markdown("### 📥 Xuất báo cáo")
    loai_xuat_ds = st.radio(
        "Chọn trạng thái để xuất",
        ["Tất cả", "Đã hoàn thành", "Chưa hoàn thành"],
        horizontal=True,
        key="ds_loai_xuat",
    )
    if loai_xuat_ds == "Đã hoàn thành":
        df_xuat_ds = df_loc[df_loc["tt"].isin(["dung_han", "tre", "da_nop"])]
    elif loai_xuat_ds == "Chưa hoàn thành":
        df_xuat_ds = df_loc[df_loc["tt"] == "chua_nop"]
    else:
        df_xuat_ds = df_loc

    if df_xuat_ds.empty:
        st.info(f"Không có báo cáo **{loai_xuat_ds.lower()}**.")
    else:
        st.caption(f"📋 {len(df_xuat_ds)} lượt nộp — **{loai_xuat_ds}**")
        ten_file_ds = f"tien_do_nop_{loai_xuat_ds.replace(' ', '_').lower()}"
        col_excel, col_pdf, _ = st.columns([1, 1, 5])
        with col_excel:
            if st.button("📥 Xuất Excel", key="btn_xuat_tdn", use_container_width=True, type="primary"):
                df_export = df_xuat_ds.drop(columns=["tt", "tt_hien"], errors="ignore")
                st.session_state["_excel_tdn_bytes"] = xuat_excel({f"Tiến độ nộp — {loai_xuat_ds}": df_export})
                st.session_state["_excel_tdn_ten"] = f"{ten_file_ds}.xlsx"
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
                df_xuat_ds,
                f"Tiến độ nộp báo cáo — {loai_xuat_ds}",
                st.session_state.get("username", "unknown"),
                cols_tien=[],
                prefix_file=ten_file_ds,
                key="pdf_tdn",
            )


# ── Tab 3: Cài đặt thời hạn hoàn thành ────────────────────────────────────────

def _render_cai_dat(df: pd.DataFrame, deadline_cfg: dict, username: str) -> None:
    st.markdown("**Cấu hình thời hạn hoàn thành cho từng loại báo cáo**")
    st.caption("Sau khi lưu, cột Trạng thái sẽ tự tính 🟢 Đúng hạn / 🟡 Trễ / 🔴 Chưa nộp.")

    # Gộp loại từ GSheet + loại đã có trong deadline_cfg
    ds_loai_gsheet = sorted(df["loai_bao_cao"].dropna().unique().tolist()) if not df.empty else []
    ds_loai_cfg    = sorted(deadline_cfg.keys())
    ds_loai = sorted(set(ds_loai_gsheet) | set(ds_loai_cfg))

    if not ds_loai:
        st.info("Chưa có dữ liệu từ Google Sheets và chưa có thời hạn hoàn thành nào được cài đặt.")
        return

    # Hiển thị label kèm trạng thái đã có thời hạn chưa
    def _label(loai: str) -> str:
        return f"{loai}  ✅" if loai in deadline_cfg else loai

    loai_options = ds_loai
    loai_labels  = [_label(l) for l in loai_options]
    idx = st.selectbox(
        "Chọn loại báo cáo",
        range(len(loai_options)),
        format_func=lambda i: loai_labels[i],
        key="cd_loai",
    )
    loai_chon = loai_options[idx]

    dl_hien   = deadline_cfg.get(loai_chon)
    dl_default = pd.to_datetime(dl_hien).date() if dl_hien else date.today()

    col_input, col_btn, col_del = st.columns([3, 1, 1])
    with col_input:
        dl_moi = st.date_input(
            f"Thời hạn hoàn thành — **{loai_chon}**",
            value=dl_default, format="DD/MM/YYYY",
            key="cd_dl_input",
        )
    with col_btn:
        st.write("")  # spacing
        if st.button("💾 Lưu", key="cd_btn_luu", type="primary", use_container_width=True):
            cfg_moi = dict(deadline_cfg)
            cfg_moi[loai_chon] = dl_moi.strftime("%Y-%m-%d")
            _luu_deadline_config(cfg_moi, username)
            st.success(f"✅ Đã lưu: **{loai_chon}** → {dl_moi.strftime('%d/%m/%Y')}")
            st.rerun()
    with col_del:
        st.write("")  # spacing
        if dl_hien:
            with st.popover("🗑 Xóa", use_container_width=True):
                st.warning(f"Xóa thời hạn hoàn thành của **{loai_chon}**?")
                st.caption("Loại báo cáo này sẽ không còn được theo dõi ở tab Tổng quan.")
                if st.button("⚠️ Xác nhận xóa", key="cd_btn_xoa_cf", type="primary", use_container_width=True):
                    cfg_moi = dict(deadline_cfg)
                    cfg_moi.pop(loai_chon, None)
                    _luu_deadline_config(cfg_moi, username)
                    st.success(f"✅ Đã xóa thời hạn: **{loai_chon}**")
                    st.rerun()

    st.divider()
    st.markdown("**Danh sách thời hạn hoàn thành đã cài đặt**")
    rows = [{"Loại báo cáo": loai, "Thời hạn": pd.to_datetime(dl).strftime("%d/%m/%Y") if dl else dl}
            for loai, dl in sorted(deadline_cfg.items())]
    if rows:
        st.dataframe(
            pd.DataFrame(rows),
            hide_index=True, use_container_width=True,
        )
    else:
        st.info("Chưa có thời hạn hoàn thành nào. Dùng form trên để thêm.")


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
        
        1. **Cài đặt thời hạn hoàn thành** trước mỗi kỳ báo cáo
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
                flex-wrap: wrap; padding: 20px; background: var(--background-color, transparent);
                border: 1px solid var(--border-color, #ddd); border-radius: 12px;">
        <div style="text-align: center; padding: 15px; border: 1px solid var(--border-color, #ccc);
                    border-radius: 10px; min-width: 120px;">
            <div style="font-size: 32px;">📝</div>
            <div style="font-weight: 600; font-size: 13px; margin-top: 5px;">PGD nộp Form</div>
        </div>
        <div style="font-size: 24px;">→</div>
        <div style="text-align: center; padding: 15px; border: 1px solid var(--border-color, #ccc);
                    border-radius: 10px; min-width: 120px;">
            <div style="font-size: 32px;">📊</div>
            <div style="font-weight: 600; font-size: 13px; margin-top: 5px;">Lưu Sheets</div>
        </div>
        <div style="font-size: 24px;">→</div>
        <div style="text-align: center; padding: 15px; border: 1px solid var(--border-color, #ccc);
                    border-radius: 10px; min-width: 120px;">
            <div style="font-size: 32px;">⚙️</div>
            <div style="font-weight: 600; font-size: 13px; margin-top: 5px;">VBSP đọc (5 phút)</div>
        </div>
        <div style="font-size: 24px;">→</div>
        <div style="text-align: center; padding: 15px; border: 1px solid var(--border-color, #ccc);
                    border-radius: 10px; min-width: 120px;">
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
        st.metric("🟢 Đúng hạn", "Nộp ≤ thời hạn")
    with status_cols[1]:
        st.metric("🟡 Trễ hạn", "Nộp > thời hạn")
    with status_cols[2]:
        st.metric("🔴 Chưa nộp", "Quá hạn, chưa có data")
    with status_cols[3]:
        st.metric("⚪ Chưa nộp", "Chưa có thời hạn")
    
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

_CACHE_VER = "v2"

def render(tab: DeltaGenerator = None, **kwargs) -> None:
    role_raw = str(kwargs.get("role", "user") or "user")
    role_n = normalize_role(role_raw)
    is_cn = la_phan_he_cn(role_n)
    pgd_user = kwargs.get("pgd_user")
    username = kwargs.get("username", st.session_state.get("username", "unknown"))

    ctx = tab if tab is not None else st.container()
    with ctx:
        st.subheader("📋 Tiến độ Báo cáo của PGD")
        st.caption("Dữ liệu từ Google Form · Tự động cập nhật mỗi 5 phút")

        if st.session_state.get(f"_tdn_cache_ver") != _CACHE_VER:
            _doc_du_lieu.clear()
            st.session_state[f"_tdn_cache_ver"] = _CACHE_VER

        _credentials_path = str(BASE_DIR / "credentials.json")
        if not Path(_credentials_path).exists():
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
            # Bước 1: Cài đặt thời hạn → Bước 2: Tổng quan → Bước 4: Danh sách nộp
            t0, t1, t2, t3 = st.tabs(["📖 Hướng dẫn PGD gửi BC về CN", "⚙️ Cài đặt thời hạn", "📊 Tổng quan", "📋 Danh sách nộp"])
        else:
            t0, t2, t3 = st.tabs(["📖 Hướng dẫn PGD gửi BC về CN", "📊 Tổng quan", "📋 Danh sách nộp"])
            t1 = None

        with t0:
            _render_huong_dan_mockup()

        if t1 is not None:
            with t1:
                _render_cai_dat(df, deadline_cfg, username)

        with t2:
            _render_tong_quan(df, deadline_cfg, is_cn, pgd_user, username, can_config)

        with t3:
            _render_danh_sach(df, deadline_cfg, is_cn, pgd_user)
