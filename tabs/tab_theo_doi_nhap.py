"""Theo dõi tiến trình nhập liệu của PGD trên Google Sheet phân cấp.

Sheet có cấu trúc:
  - PGD header row: Col STT = Số La Mã (I, II, III...), Col tên = "PGD X"
  - Xã/phường row:  Col STT = số thập phân (1.0, 2.0...), Col tên = "Phường Y"
Admin cấu hình SHEET_ID, tab, và cột cần theo dõi qua UI.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st
from streamlit.delta_generator import DeltaGenerator

import db
from auth import la_phan_he_cn, normalize_role
from components.delta_card import kpi_row
from logger import get_logger
from utils import get_tab_context, xuat_excel

logger = get_logger(__name__)

CREDENTIALS_FILE = "credentials.json"
KV_CONFIG_KEY    = "gsheet_theo_doi_nhap_config"

DEFAULT_CONFIG: dict = {
    "sheet_id":  "",
    "sheet_tab": "DANH MỤC ĐIỀU CHỈNH HSSV LẦN 2",
    "header_row": 10,   # hàng header (1-indexed), dữ liệu bắt đầu từ header_row+1
    "stt_col":    1,    # cột STT (1-indexed)
    "name_col":   2,    # cột tên PGD/xã (1-indexed)
    "ds_chuong_trinh": [
        {"ten": "HSSV",      "col": 4},
        {"ten": "Nước sạch", "col": 8},
        {"ten": "Việc làm",  "col": 13},
    ],
}

_EMOJI_PCT = {"full": "🟢", "partial": "🟡", "empty": "🔴"}


# ── GSheet auth ───────────────────────────────────────────────────────────────

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
        logger.error("_ket_noi_gsheet: %s", e, exc_info=True)
        try:
            from oauth2client.service_account import ServiceAccountCredentials
            creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, scope)
            return gspread.authorize(creds)
        except ImportError:
            raise RuntimeError("Không thể kết nối GSheet: cần google-auth hoặc oauth2client.")


# ── Đọc sheet ────────────────────────────────────────────────────────────────

@st.cache_data(ttl=300)
def _doc_sheet(sheet_id: str, sheet_tab: str, header_row: int) -> list[list]:
    """Đọc toàn bộ sheet, trả về raw list-of-rows từ hàng (header_row+1) trở đi."""
    try:
        client = _ket_noi_gsheet()
        ws     = client.open_by_key(sheet_id).worksheet(sheet_tab)
        all_rows = ws.get_all_values()
        # Bỏ header rows, lấy từ data_row trở đi
        data_rows = all_rows[header_row:]   # header_row = 10 → index 10 = row 11 trong sheet
        return data_rows
    except Exception as e:
        logger.error("_doc_sheet: %s", e, exc_info=True)
        raise


# ── Logic phân nhóm PGD ──────────────────────────────────────────────────────

def _la_pgd_header(stt_value: str) -> bool:
    """Hàng PGD = Col STT là chuỗi (La Mã: I, II, III...), không phải số."""
    if stt_value is None:
        return False
    s = str(stt_value).strip()
    return s != "" and not _is_number(s)


def _is_number(s: str) -> bool:
    try:
        float(s)
        return True
    except (ValueError, TypeError):
        return False


def _da_nhap(val) -> bool:
    """True nếu ô đã được điền (kể cả 0)."""
    if val is None:
        return False
    return str(val).strip() != ""


def _phan_nhom_pgd(
    rows: list[list],
    stt_col_idx: int,   # 0-indexed
    name_col_idx: int,  # 0-indexed
) -> dict[str, list[list]]:
    """Phân nhóm rows theo PGD. Trả về {pgd_name: [sub_rows...]}."""
    groups: dict[str, list[list]] = {}
    current_pgd: str | None = None

    for row in rows:
        if not any(str(c).strip() for c in row):
            continue  # bỏ hàng trống

        stt  = row[stt_col_idx]  if len(row) > stt_col_idx  else ""
        name = row[name_col_idx] if len(row) > name_col_idx else ""

        if _la_pgd_header(stt):
            current_pgd = str(name).strip()
            if current_pgd and current_pgd not in groups:
                groups[current_pgd] = []
        elif current_pgd is not None:
            groups[current_pgd].append(row)

    return groups


# ── Tính tiến độ ─────────────────────────────────────────────────────────────

def _tinh_tien_do(
    pgd_groups: dict[str, list[list]],
    ds_chuong_trinh: list[dict],
) -> pd.DataFrame:
    """Tính % điền của mỗi PGD cho từng chương trình.

    Returns DataFrame với cols: Đơn vị, {CT}_filled, {CT}_total, {CT}_pct, Tổng_pct
    """
    rows_out = []
    for pgd, sub_rows in pgd_groups.items():
        total = len(sub_rows)
        row: dict = {"Đơn vị": pgd, "_total": total}
        sum_pct = 0.0
        for ct in ds_chuong_trinh:
            col_idx = ct["col"] - 1  # convert 1-indexed → 0-indexed
            ten = ct["ten"]
            filled = sum(
                1 for r in sub_rows
                if len(r) > col_idx and _da_nhap(r[col_idx])
            )
            pct = (filled / total * 100) if total > 0 else 0.0
            row[f"{ten}_filled"] = filled
            row[f"{ten}_total"]  = total
            row[f"{ten}_pct"]    = round(pct, 1)
            sum_pct += pct
        row["Tổng_pct"] = round(sum_pct / len(ds_chuong_trinh), 1) if ds_chuong_trinh else 0.0
        rows_out.append(row)

    return pd.DataFrame(rows_out) if rows_out else pd.DataFrame()


def _emoji_pct(pct: float) -> str:
    if pct >= 100:
        return _EMOJI_PCT["full"]
    if pct > 0:
        return _EMOJI_PCT["partial"]
    return _EMOJI_PCT["empty"]


# ── Config ────────────────────────────────────────────────────────────────────

def _doc_config() -> dict:
    saved = db.doc_kv(KV_CONFIG_KEY)
    if not saved:
        return DEFAULT_CONFIG.copy()
    # Merge với DEFAULT để không thiếu key mới
    cfg = DEFAULT_CONFIG.copy()
    cfg.update(saved)
    return cfg


def _luu_config(cfg: dict, username: str) -> None:
    db.ghi_kv(KV_CONFIG_KEY, cfg, username)
    db.ghi_audit(username, "luu_theo_doi_nhap_config", f"Sheet ID: {cfg.get('sheet_id', '')[:20]}")


# ── Tab UI ────────────────────────────────────────────────────────────────────

def _render_tong_quan(df_td: pd.DataFrame, ds_chuong_trinh: list[dict]) -> None:
    if df_td.empty:
        st.info("Chưa có dữ liệu. Vui lòng cấu hình Sheet ID trong tab ⚙️ Cài đặt.")
        return

    total_pgd = len(df_td)
    pgd_full  = int((df_td["Tổng_pct"] >= 100).sum())
    pgd_empty = int((df_td["Tổng_pct"] == 0).sum())
    pct_avg   = round(df_td["Tổng_pct"].mean(), 1)
    tong_xa   = int(df_td["_total"].sum()) if "_total" in df_td.columns else 0

    kpi_row([
        {"label": "Đã điền đủ (3 CT)",   "value": pgd_full,  "suffix": f"/{total_pgd} PGD", "icon": "🟢"},
        {"label": "Chưa điền gì",        "value": pgd_empty, "suffix": f"/{total_pgd} PGD", "icon": "🔴"},
        {"label": "% hoàn thành TB",      "value": pct_avg,   "suffix": "%",                 "icon": "📊"},
        {"label": "Tổng xã/phường",       "value": tong_xa,   "suffix": " xã/phường",        "icon": "🏘️"},
    ], num_columns=4)

    st.divider()
    st.markdown("**Ma trận tiến độ — Đơn vị × Chương trình**")

    # Xây dựng bảng hiển thị
    display_rows = []
    for _, r in df_td.iterrows():
        row_disp: dict = {"Đơn vị": r["Đơn vị"]}
        for ct in ds_chuong_trinh:
            ten  = ct["ten"]
            pct  = r.get(f"{ten}_pct", 0)
            fil  = r.get(f"{ten}_filled", 0)
            tot  = r.get(f"{ten}_total", 0)
            emoji = _emoji_pct(pct)
            row_disp[ten] = f"{emoji} {fil}/{tot} ({pct:.0f}%)"
        tong = r.get("Tổng_pct", 0)
        row_disp["Tổng"] = f"{_emoji_pct(tong)} {tong:.0f}%"
        display_rows.append(row_disp)

    df_disp = pd.DataFrame(display_rows).sort_values("Đơn vị")
    st.dataframe(df_disp, hide_index=True, use_container_width=True)

    # Danh sách chưa điền
    df_chua = df_td[df_td["Tổng_pct"] == 0]
    if not df_chua.empty:
        st.divider()
        st.warning(f"⚠️ **{len(df_chua)} đơn vị chưa điền dữ liệu nào:**  "
                   + " · ".join(df_chua["Đơn vị"].tolist()))


def _render_chi_tiet(df_td: pd.DataFrame, ds_chuong_trinh: list[dict], username: str) -> None:
    if df_td.empty:
        st.info("Chưa có dữ liệu.")
        return

    # Bộ lọc
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        ten_ct_list = [ct["ten"] for ct in ds_chuong_trinh]
        ct_chon = st.selectbox("Lọc theo chương trình", ["Tất cả"] + ten_ct_list, key="ttdn_ct_filter")
    with col_f2:
        tt_filter = st.selectbox("Trạng thái", ["Tất cả", "Đã điền đủ 🟢", "Điền một phần 🟡", "Chưa điền 🔴"], key="ttdn_tt_filter")

    df_show = df_td.copy()
    if tt_filter == "Đã điền đủ 🟢":
        df_show = df_show[df_show["Tổng_pct"] >= 100]
    elif tt_filter == "Điền một phần 🟡":
        df_show = df_show[(df_show["Tổng_pct"] > 0) & (df_show["Tổng_pct"] < 100)]
    elif tt_filter == "Chưa điền 🔴":
        df_show = df_show[df_show["Tổng_pct"] == 0]

    st.caption(f"Hiển thị {len(df_show)} / {len(df_td)} đơn vị")

    # Chọn cột hiển thị
    cols_hien = ["Đơn vị"]
    for ct in ds_chuong_trinh:
        ten = ct["ten"]
        if ct_chon == "Tất cả" or ct_chon == ten:
            cols_hien += [f"{ten}_filled", f"{ten}_total", f"{ten}_pct"]
    cols_hien += ["Tổng_pct"]
    cols_co = [c for c in cols_hien if c in df_show.columns]

    df_export = df_show[cols_co].rename(columns={
        **{f"{ct['ten']}_filled": f"{ct['ten']} đã điền" for ct in ds_chuong_trinh},
        **{f"{ct['ten']}_total":  f"{ct['ten']} tổng"    for ct in ds_chuong_trinh},
        **{f"{ct['ten']}_pct":    f"{ct['ten']} %"       for ct in ds_chuong_trinh},
        "Tổng_pct": "Tổng %",
    })

    st.dataframe(df_export, hide_index=True, use_container_width=True)

    if st.button("📥 Xuất Excel", key="ttdn_btn_excel", type="primary"):
        excel_bytes = xuat_excel({"Theo dõi nhập liệu": df_export})
        st.download_button(
            "⬇ Tải Excel",
            data=excel_bytes,
            file_name="theo_doi_nhap_lieu.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="ttdn_dl_excel",
        )


def _render_cai_dat(cfg: dict, username: str) -> None:
    st.markdown("**Cấu hình kết nối Google Sheet**")

    sheet_id  = st.text_input("Google Sheet ID", value=cfg.get("sheet_id", ""),
                               key="ttdn_sheet_id",
                               help="Lấy từ URL: docs.google.com/spreadsheets/d/**[ID]**/edit")
    sheet_tab = st.text_input("Tên worksheet (tab)", value=cfg.get("sheet_tab", ""),
                               key="ttdn_sheet_tab")
    header_row = st.number_input("Hàng header (1-indexed)", min_value=1, max_value=50,
                                  value=cfg.get("header_row", 10),
                                  key="ttdn_header_row",
                                  help="Dữ liệu bắt đầu từ hàng tiếp theo sau header")

    st.divider()
    st.markdown("**Cột dữ liệu (1-indexed)**")
    st.caption("Cột 1 = cột đầu tiên trong sheet")

    stt_col  = st.number_input("Cột STT", min_value=1, max_value=30,
                                value=cfg.get("stt_col", 1), key="ttdn_stt_col")
    name_col = st.number_input("Cột Tên đơn vị", min_value=1, max_value=30,
                                value=cfg.get("name_col", 2), key="ttdn_name_col")

    st.divider()
    st.markdown("**Cột 'Điều chỉnh tăng trưởng' của từng chương trình**")

    ds_ct = cfg.get("ds_chuong_trinh", DEFAULT_CONFIG["ds_chuong_trinh"])
    new_ds_ct = []
    for ct in ds_ct:
        col1, col2 = st.columns([3, 1])
        with col1:
            ten = st.text_input("Tên chương trình", value=ct["ten"],
                                 key=f"ttdn_ct_ten_{ct['ten']}")
        with col2:
            col_num = st.number_input("Cột", min_value=1, max_value=50,
                                       value=ct["col"],
                                       key=f"ttdn_ct_col_{ct['ten']}")
        new_ds_ct.append({"ten": ten, "col": col_num})

    st.divider()

    col_test, col_save = st.columns(2)
    with col_test:
        if st.button("🔌 Test kết nối", key="ttdn_btn_test", use_container_width=True):
            if not sheet_id.strip():
                st.error("❌ Chưa nhập Sheet ID")
            else:
                try:
                    with st.spinner("Đang kết nối..."):
                        rows = _doc_sheet(sheet_id.strip(), sheet_tab.strip(), header_row)
                    data_rows = [r for r in rows if any(str(c).strip() for c in r)]
                    st.success(f"✅ Kết nối OK — đọc được {len(data_rows)} hàng có dữ liệu")
                except Exception as e:
                    st.error(f"❌ Lỗi: {e}")

    with col_save:
        if st.button("💾 Lưu cấu hình", key="ttdn_btn_save", type="primary", use_container_width=True):
            new_cfg = {
                "sheet_id":         sheet_id.strip(),
                "sheet_tab":        sheet_tab.strip(),
                "header_row":       int(header_row),
                "stt_col":          int(stt_col),
                "name_col":         int(name_col),
                "ds_chuong_trinh":  new_ds_ct,
            }
            _luu_config(new_cfg, username)
            _doc_sheet.clear()
            st.success("✅ Đã lưu cấu hình")
            st.rerun()


# ── Entry point ───────────────────────────────────────────────────────────────

def render(tab: DeltaGenerator = None, **kwargs) -> None:
    role_raw = str(kwargs.get("role", "user") or "user")
    role_n   = normalize_role(role_raw)
    is_cn    = la_phan_he_cn(role_n)
    username = kwargs.get("username", st.session_state.get("username", "unknown"))

    ctx = get_tab_context(tab)
    with ctx:
        st.subheader("📋 Theo dõi tiến trình nhập liệu PGD")
        st.caption("Đọc từ Google Sheet · Tự động cập nhật mỗi 5 phút")

        if not Path(CREDENTIALS_FILE).exists():
            st.warning("⚠️ Chưa có file `credentials.json`. Không thể kết nối Google Sheet.")
            return

        cfg = _doc_config()
        can_config = role_n in ("admin_cn", "manager_cn", "admin", "manager")

        # Nút làm mới
        col_r, _ = st.columns([1, 7])
        with col_r:
            if st.button("🔄 Làm mới", key="ttdn_refresh"):
                _doc_sheet.clear()
                st.rerun()

        # Đọc và xử lý dữ liệu (nếu đã cấu hình)
        df_td = pd.DataFrame()
        sheet_id = cfg.get("sheet_id", "").strip()
        if sheet_id:
            try:
                with st.spinner("Đang đọc Google Sheet..."):
                    raw_rows = _doc_sheet(
                        sheet_id,
                        cfg.get("sheet_tab", ""),
                        cfg.get("header_row", 10),
                    )
                stt_idx  = cfg.get("stt_col", 1) - 1
                name_idx = cfg.get("name_col", 2) - 1
                pgd_groups = _phan_nhom_pgd(raw_rows, stt_idx, name_idx)
                df_td = _tinh_tien_do(pgd_groups, cfg.get("ds_chuong_trinh", []))
            except Exception as e:
                logger.error("tab_theo_doi_nhap render: %s", e, exc_info=True)
                st.error(f"❌ Lỗi đọc Google Sheet: {e}")
        else:
            st.info("⚙️ Chưa cấu hình Sheet ID. Vào tab **⚙️ Cài đặt** để nhập.")

        # Tabs
        ds_ct = cfg.get("ds_chuong_trinh", [])
        if can_config:
            t0, t1, t2 = st.tabs(["📊 Tổng quan", "📋 Chi tiết", "⚙️ Cài đặt"])
        else:
            t0, t1 = st.tabs(["📊 Tổng quan", "📋 Chi tiết"])
            t2 = None

        with t0:
            _render_tong_quan(df_td, ds_ct)

        with t1:
            _render_chi_tiet(df_td, ds_ct, username)

        if t2 is not None:
            with t2:
                _render_cai_dat(cfg, username)
