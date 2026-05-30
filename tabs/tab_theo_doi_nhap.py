"""Theo dõi tiến trình nhập liệu của PGD trên nhiều Google Sheet phân cấp.

Sheet có cấu trúc:
  - PGD header row: Col STT = Số La Mã (I, II, III...), Col tên = "PGD X"
  - Xã/phường row:  Col STT = số thập phân (1.0, 2.0...), Col tên = "Phường Y"
Admin cấu hình nhiều sheet, mỗi sheet có tên hiển thị riêng.
"""
from __future__ import annotations

from datetime import date as _date
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

CREDENTIALS_FILE  = "credentials.json"
KV_LIST_KEY       = "gsheet_theo_doi_nhap_list"   # list nhiều sheet
KV_LEGACY_KEY     = "gsheet_theo_doi_nhap_config"  # key cũ — tự migrate

DEFAULT_CT = [
    {"ten": "HSSV",       "col": 4},
    {"ten": "Nước sạch",  "col": 8},
    {"ten": "Việc làm",   "col": 13},
]

_EMOJI_PCT = {"full": "🟢", "partial": "🟡", "empty": "🔴"}


# ── GSheet auth ───────────────────────────────────────────────────────────────

@st.cache_resource(show_spinner=False)
def _ket_noi_gsheet():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]
    if not Path(CREDENTIALS_FILE).exists():
        raise FileNotFoundError(f"Không tìm thấy {CREDENTIALS_FILE}")
    try:
        import gspread
        return gspread.service_account(filename=CREDENTIALS_FILE, scopes=scope)
    except Exception as e:
        logger.error("_ket_noi_gsheet: %s", e, exc_info=True)
        try:
            from oauth2client.service_account import ServiceAccountCredentials
            import gspread
            creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, scope)
            return gspread.authorize(creds)
        except ImportError:
            raise RuntimeError("Không thể kết nối GSheet.")


@st.cache_data(ttl=300)
def _doc_sheet(sheet_id: str, sheet_tab: str, header_row: int) -> list[list]:
    try:
        client   = _ket_noi_gsheet()
        ws       = client.open_by_key(sheet_id).worksheet(sheet_tab)
        all_rows = ws.get_all_values()
        return all_rows[header_row:]   # bỏ header, trả data từ header_row+1
    except Exception as e:
        logger.error("_doc_sheet: %s", e, exc_info=True)
        raise


# ── Logic phân nhóm + tính tiến độ ──────────────────────────────────────────
# loai_cau_truc:
#   "phan_cap_stt"  — STT chữ La Mã = PGD header, STT số = xã/phường con (mặc định)
#   "phang"         — mỗi hàng = 1 đơn vị, không có con
#   "cot_pgd"       — có cột riêng ghi tên PGD cho mỗi hàng; name_col = tên xã/phường

def _la_pgd_header(stt) -> bool:
    if stt is None:
        return False
    s = str(stt).strip()
    if not s:
        return False
    try:
        float(s)
        return False
    except (ValueError, TypeError):
        return True


def _da_nhap(val) -> bool:
    return val is not None and str(val).strip() != ""


def _phan_nhom_pgd(
    rows: list[list],
    stt_idx: int,
    name_idx: int,
    loai: str = "phan_cap_stt",
    pgd_col_idx: int = 0,   # dùng cho loai="cot_pgd"
) -> dict[str, list[list]]:
    """Phân nhóm rows theo PGD dựa theo loại cấu trúc."""

    if loai == "phang":
        # Mỗi hàng = 1 đơn vị, không có con — đơn vị = name_idx
        groups: dict[str, list[list]] = {}
        for row in rows:
            if not any(str(c).strip() for c in row):
                continue
            name = str(row[name_idx]).strip() if len(row) > name_idx else ""
            if name:
                groups[name] = [row]   # mỗi đơn vị = 1 hàng
        return groups

    if loai == "cot_pgd":
        # Có cột riêng ghi tên PGD; name_col = tên xã/phường
        groups = {}
        for row in rows:
            if not any(str(c).strip() for c in row):
                continue
            pgd  = str(row[pgd_col_idx]).strip() if len(row) > pgd_col_idx else ""
            if pgd:
                groups.setdefault(pgd, []).append(row)
        return groups

    # Mặc định: phan_cap_stt — STT chữ = PGD, STT số = con
    groups = {}
    current: str | None = None
    for row in rows:
        if not any(str(c).strip() for c in row):
            continue
        stt  = row[stt_idx]  if len(row) > stt_idx  else ""
        name = row[name_idx] if len(row) > name_idx else ""
        if _la_pgd_header(stt):
            current = str(name).strip()
            if current and current not in groups:
                groups[current] = []
        elif current is not None:
            groups[current].append(row)
    return groups


def _tinh_tien_do(pgd_groups: dict, ds_ct: list[dict]) -> pd.DataFrame:
    rows_out = []
    for pgd, sub_rows in pgd_groups.items():
        total = len(sub_rows)
        row: dict = {"Đơn vị": pgd, "_total": total}
        sum_pct = 0.0
        for ct in ds_ct:
            ci   = ct["col"] - 1
            ten  = ct["ten"]
            filled = sum(1 for r in sub_rows if len(r) > ci and _da_nhap(r[ci]))
            pct    = (filled / total * 100) if total > 0 else 0.0
            row[f"{ten}_filled"] = filled
            row[f"{ten}_total"]  = total
            row[f"{ten}_pct"]    = round(pct, 1)
            sum_pct += pct
        row["Tổng_pct"] = round(sum_pct / len(ds_ct), 1) if ds_ct else 0.0
        rows_out.append(row)
    return pd.DataFrame(rows_out) if rows_out else pd.DataFrame()


def _emoji_pct(pct: float) -> str:
    if pct >= 100:  return _EMOJI_PCT["full"]
    if pct > 0:     return _EMOJI_PCT["partial"]
    return _EMOJI_PCT["empty"]


# ── Config (list nhiều sheet) ─────────────────────────────────────────────────

def _doc_ds_sheet() -> list[dict]:
    """Đọc danh sách sheet đã cấu hình. Tự migrate từ config cũ nếu có."""
    saved = db.doc_kv(KV_LIST_KEY)
    if saved and isinstance(saved, list):
        return saved

    # Migrate từ key cũ (single config)
    legacy = db.doc_kv(KV_LEGACY_KEY)
    if legacy and isinstance(legacy, dict) and legacy.get("sheet_id"):
        migrated = [{
            "ten_hien_thi": legacy.get("sheet_tab", "Sheet cũ")[:40],
            **legacy,
        }]
        db.ghi_kv(KV_LIST_KEY, migrated, "system")
        return migrated
    return []


def _luu_ds_sheet(ds: list[dict], username: str) -> None:
    db.ghi_kv(KV_LIST_KEY, ds, username)
    db.ghi_audit(username, "luu_theo_doi_nhap_config", f"{len(ds)} sheet(s)")


def _sheet_moi() -> dict:
    return {
        "ten_hien_thi": "",
        "sheet_id":     "",
        "sheet_tab":    "",
        "header_row":   10,
        "stt_col":      1,
        "name_col":     2,
        "ds_chuong_trinh": list(DEFAULT_CT),
    }


# ── Tab UI ────────────────────────────────────────────────────────────────────

def _render_tong_quan(df_td: pd.DataFrame, ds_ct: list[dict], ten_sheet: str) -> None:
    if df_td.empty:
        st.info("Chưa có dữ liệu. Kiểm tra lại Sheet ID hoặc cấu hình cột.")
        return

    total_pgd = len(df_td)
    pgd_full  = int((df_td["Tổng_pct"] >= 100).sum())
    pgd_empty = int((df_td["Tổng_pct"] == 0).sum())
    pct_avg   = round(float(df_td["Tổng_pct"].mean()), 1)
    tong_xa   = int(df_td["_total"].sum()) if "_total" in df_td.columns else 0

    kpi_row([
        {"label": "Hoàn thành",       "value": pgd_full,  "suffix": f"/{total_pgd} PGD", "icon": "🟢"},
        {"label": "Chưa điền",        "value": pgd_empty, "suffix": f"/{total_pgd} PGD", "icon": "🔴"},
        {"label": "% TB",             "value": pct_avg,   "suffix": "%",                 "icon": "📊"},
        {"label": "Tổng xã/phường",   "value": tong_xa,   "suffix": "",                  "icon": "🏘️"},
    ], num_columns=4)

    st.divider()
    st.markdown(f"**Ma trận tiến độ — {ten_sheet}**")

    display_rows = []
    for _, r in df_td.iterrows():
        rd: dict = {"Đơn vị": r["Đơn vị"]}
        for ct in ds_ct:
            ten = ct["ten"]
            pct = r.get(f"{ten}_pct", 0)
            fil = r.get(f"{ten}_filled", 0)
            tot = r.get(f"{ten}_total",  0)
            rd[ten] = f"{_emoji_pct(pct)} {fil}/{tot} ({pct:.0f}%)"
        tong = r.get("Tổng_pct", 0)
        rd["Tổng"] = f"{_emoji_pct(tong)} {tong:.0f}%"
        display_rows.append(rd)

    st.dataframe(
        pd.DataFrame(display_rows).sort_values("Đơn vị"),
        hide_index=True, use_container_width=True,
    )

    df_chua = df_td[df_td["Tổng_pct"] == 0]
    if not df_chua.empty:
        st.divider()
        st.warning(f"⚠️ **{len(df_chua)} đơn vị chưa điền:** "
                   + " · ".join(df_chua["Đơn vị"].tolist()))


def _render_chi_tiet(df_td: pd.DataFrame, ds_ct: list[dict], username: str) -> None:
    if df_td.empty:
        st.info("Chưa có dữ liệu.")
        return

    col_f1, col_f2 = st.columns(2)
    with col_f1:
        ct_chon = st.selectbox("Lọc chương trình",
                               ["Tất cả"] + [ct["ten"] for ct in ds_ct],
                               key="ttdn_ct_filter")
    with col_f2:
        tt_filter = st.selectbox("Trạng thái",
                                  ["Tất cả", "Hoàn thành 🟢", "Một phần 🟡", "Chưa điền 🔴"],
                                  key="ttdn_tt_filter")

    df_show = df_td.copy()
    if tt_filter == "Hoàn thành 🟢":
        df_show = df_show[df_show["Tổng_pct"] >= 100]
    elif tt_filter == "Một phần 🟡":
        df_show = df_show[(df_show["Tổng_pct"] > 0) & (df_show["Tổng_pct"] < 100)]
    elif tt_filter == "Chưa điền 🔴":
        df_show = df_show[df_show["Tổng_pct"] == 0]

    st.caption(f"Hiển thị {len(df_show)} / {len(df_td)} đơn vị")

    cols_hien = ["Đơn vị"]
    for ct in ds_ct:
        if ct_chon in ("Tất cả", ct["ten"]):
            cols_hien += [f"{ct['ten']}_filled", f"{ct['ten']}_total", f"{ct['ten']}_pct"]
    cols_hien.append("Tổng_pct")
    cols_co = [c for c in cols_hien if c in df_show.columns]

    rename = {
        **{f"{ct['ten']}_filled": f"{ct['ten']} đã điền" for ct in ds_ct},
        **{f"{ct['ten']}_total":  f"{ct['ten']} tổng"    for ct in ds_ct},
        **{f"{ct['ten']}_pct":    f"{ct['ten']} %"       for ct in ds_ct},
        "Tổng_pct": "Tổng %",
    }
    df_export = df_show[cols_co].rename(columns=rename)
    st.dataframe(df_export, hide_index=True, use_container_width=True)

    if st.button("📥 Xuất Excel", key="ttdn_btn_excel", type="primary"):
        excel_bytes = xuat_excel({"Theo dõi nhập liệu": df_export})
        st.download_button("⬇ Tải Excel", data=excel_bytes,
                           file_name="theo_doi_nhap_lieu.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           key="ttdn_dl_excel")


_MOCKUP_HTML = """
<div style="font-size:12px; border:1px solid var(--border-color,#ccc); border-radius:8px; overflow:auto; padding:12px;">
  <div style="margin-bottom:8px; font-weight:600;">📌 Cấu trúc Google Sheet được hỗ trợ</div>
  <table style="border-collapse:collapse; width:100%; font-size:11px;">
    <tr style="background:var(--secondary-background-color,#f0f2f6);">
      <td style="border:1px solid #ccc;padding:4px 8px;font-weight:600;">Hàng</td>
      <td style="border:1px solid #ccc;padding:4px 8px;font-weight:600;">Cột 1 (STT)</td>
      <td style="border:1px solid #ccc;padding:4px 8px;font-weight:600;">Cột 2 (Tên đơn vị)</td>
      <td style="border:1px solid #ccc;padding:4px 8px;font-weight:600;">Cột 3</td>
      <td style="border:1px solid #ccc;padding:4px 8px;font-weight:600; color:#e67e22;">Cột 4 ← theo dõi</td>
      <td style="border:1px solid #ccc;padding:4px 8px;font-weight:600;">Cột 5</td>
    </tr>
    <tr>
      <td style="border:1px solid #ccc;padding:4px 8px; color:#888;">1–7</td>
      <td colspan="5" style="border:1px solid #ccc;padding:4px 8px; color:#888; font-style:italic;">Tiêu đề, chú thích... (bỏ qua)</td>
    </tr>
    <tr style="background:#fff3cd;">
      <td style="border:1px solid #ccc;padding:4px 8px; font-weight:600;">8 ← Header row</td>
      <td style="border:1px solid #ccc;padding:4px 8px;">STT</td>
      <td style="border:1px solid #ccc;padding:4px 8px;">Tên PGD / xã</td>
      <td style="border:1px solid #ccc;padding:4px 8px;">KH đã giao</td>
      <td style="border:1px solid #ccc;padding:4px 8px; color:#e67e22; font-weight:600;">Điều chỉnh tăng trưởng</td>
      <td style="border:1px solid #ccc;padding:4px 8px;">Nợ đến hạn</td>
    </tr>
    <tr style="background:#d4edda;">
      <td style="border:1px solid #ccc;padding:4px 8px;">9</td>
      <td style="border:1px solid #ccc;padding:4px 8px; font-weight:600; color:#155724;">I ← chữ = PGD</td>
      <td style="border:1px solid #ccc;padding:4px 8px; font-weight:600; color:#155724;">Hội sở chi nhánh tỉnh</td>
      <td style="border:1px solid #ccc;padding:4px 8px;">92.539</td>
      <td style="border:1px solid #ccc;padding:4px 8px; color:#e67e22;">0</td>
      <td style="border:1px solid #ccc;padding:4px 8px;"></td>
    </tr>
    <tr>
      <td style="border:1px solid #ccc;padding:4px 8px;">10</td>
      <td style="border:1px solid #ccc;padding:4px 8px; color:#0c5460;">1 ← số = xã</td>
      <td style="border:1px solid #ccc;padding:4px 8px; color:#0c5460;">Phường Phước Tân</td>
      <td style="border:1px solid #ccc;padding:4px 8px;">4.336</td>
      <td style="border:1px solid #ccc;padding:4px 8px; color:#e67e22;"></td>
      <td style="border:1px solid #ccc;padding:4px 8px;"></td>
    </tr>
    <tr>
      <td style="border:1px solid #ccc;padding:4px 8px;">11</td>
      <td style="border:1px solid #ccc;padding:4px 8px; color:#0c5460;">2</td>
      <td style="border:1px solid #ccc;padding:4px 8px; color:#0c5460;">Phường Biên Hòa</td>
      <td style="border:1px solid #ccc;padding:4px 8px;">14.662</td>
      <td style="border:1px solid #ccc;padding:4px 8px; color:#e67e22;"></td>
      <td style="border:1px solid #ccc;padding:4px 8px;"></td>
    </tr>
    <tr style="background:#d4edda;">
      <td style="border:1px solid #ccc;padding:4px 8px;">...</td>
      <td style="border:1px solid #ccc;padding:4px 8px; font-weight:600; color:#155724;">II ← chữ = PGD tiếp</td>
      <td style="border:1px solid #ccc;padding:4px 8px; font-weight:600; color:#155724;">PGD Long Thành</td>
      <td style="border:1px solid #ccc;padding:4px 8px;">...</td>
      <td style="border:1px solid #ccc;padding:4px 8px;">...</td>
      <td style="border:1px solid #ccc;padding:4px 8px;">...</td>
    </tr>
  </table>
  <div style="margin-top:10px; display:flex; gap:16px; flex-wrap:wrap; font-size:11px;">
    <span>🟡 <b>Header row</b> = hàng chứa tên cột (STT, Tên PGD...)</span>
    <span>🟢 <b>Hàng PGD</b> = Cột STT là chữ La Mã (I, II, III...)</span>
    <span>🔵 <b>Hàng xã/phường</b> = Cột STT là số (1, 2, 3...)</span>
    <span>🟠 <b>Cột theo dõi</b> = Cột cần kiểm tra đã điền chưa</span>
  </div>
  <div style="margin-top:8px; font-size:11px; color:#888;">
    💡 Mở sheet → đếm số cột từ trái sang phải để biết số cột (A=1, B=2, C=3...)
  </div>
</div>
"""


def _render_form_sheet(cfg: dict, prefix: str) -> dict:
    """Form nhập 1 sheet config, trả về dict đã cập nhật."""
    ten = st.text_input("Tên hiển thị", value=cfg.get("ten_hien_thi", ""),
                        key=f"{prefix}_ten",
                        help="VD: HSSV Lần 2 - 2026")
    sid = st.text_input("Google Sheet ID", value=cfg.get("sheet_id", ""),
                        key=f"{prefix}_sid",
                        help="Lấy từ URL: docs.google.com/spreadsheets/d/**[ID]**/edit")
    tab = st.text_input("Tên worksheet (tab)", value=cfg.get("sheet_tab", ""),
                        key=f"{prefix}_tab",
                        help="Tên đúng của tab trong Google Sheet (phân biệt HOA/thường, dấu)")

    st.markdown("**Kiểu cấu trúc sheet**")
    LOAI_OPTIONS = {
        "phan_cap_stt": "📊 Phân cấp STT — STT chữ La Mã = PGD, STT số = xã/phường con",
        "phang":        "📋 Phẳng — mỗi hàng = 1 đơn vị, không có hàng con",
        "cot_pgd":      "🗂 Cột PGD riêng — có cột ghi tên PGD cho mỗi hàng",
    }
    loai_val = cfg.get("loai_cau_truc", "phan_cap_stt")
    loai_idx = list(LOAI_OPTIONS.keys()).index(loai_val) if loai_val in LOAI_OPTIONS else 0
    loai_chon = st.selectbox(
        "Kiểu cấu trúc",
        options=list(LOAI_OPTIONS.keys()),
        format_func=lambda k: LOAI_OPTIONS[k],
        index=loai_idx,
        key=f"{prefix}_loai",
    )

    st.markdown("**Cấu hình hàng & cột**")
    hr_col, nc_col = st.columns(2)
    with hr_col:
        hr = st.number_input("Header row (hàng tên cột)", min_value=1, max_value=50,
                             value=cfg.get("header_row", 10), key=f"{prefix}_hr",
                             help="Hàng chứa tên các cột. Dữ liệu bắt đầu từ hàng tiếp theo")
    with nc_col:
        nc = st.number_input("Cột Tên đơn vị", min_value=1, max_value=30,
                             value=cfg.get("name_col", 2), key=f"{prefix}_nc",
                             help="Cột chứa tên PGD / tên xã phường")

    # Cột bổ sung tùy theo kiểu
    if loai_chon == "phan_cap_stt":
        sc = st.number_input("Cột STT (phân biệt PGD/xã)", min_value=1, max_value=30,
                             value=cfg.get("stt_col", 1), key=f"{prefix}_sc",
                             help="Cột STT: hàng PGD = chữ La Mã (I,II...), hàng xã = số (1,2...)")
        pgd_col = cfg.get("pgd_col", 1)
    elif loai_chon == "cot_pgd":
        pgd_col = st.number_input("Cột tên PGD", min_value=1, max_value=30,
                                   value=cfg.get("pgd_col", 1), key=f"{prefix}_pgd_col",
                                   help="Cột ghi tên PGD (lặp lại ở mỗi hàng)")
        sc = cfg.get("stt_col", 1)
    else:  # phang
        sc      = cfg.get("stt_col", 1)
        pgd_col = cfg.get("pgd_col", 1)

    st.markdown("**Cột cần theo dõi** (có thể thêm nhiều chương trình)")
    st.caption("Mỗi dòng = 1 chỉ tiêu cần theo dõi. Cột tính từ 1 (cột A=1, B=2, C=3...)")

    ds_ct_old = list(cfg.get("ds_chuong_trinh", list(DEFAULT_CT)))

    # Session state để quản lý số lượng CT rows
    key_count = f"{prefix}_ct_count"
    if key_count not in st.session_state:
        st.session_state[key_count] = len(ds_ct_old)
    count = st.session_state[key_count]

    # Đảm bảo ds_ct_old đủ dài
    while len(ds_ct_old) < count:
        ds_ct_old.append({"ten": f"Chỉ tiêu {len(ds_ct_old)+1}", "col": 1})

    ds_ct_new = []
    for i in range(count):
        ct = ds_ct_old[i] if i < len(ds_ct_old) else {"ten": "", "col": 1}
        ca, cb, cc = st.columns([3, 1, 0.5])
        with ca:
            tn = st.text_input("Tên chỉ tiêu", value=ct.get("ten", ""),
                               key=f"{prefix}_ct{i}_ten",
                               placeholder="VD: HSSV, Nước sạch, Việc làm...")
        with cb:
            cl = st.number_input("Cột số", min_value=1, max_value=100,
                                 value=ct.get("col", 1), key=f"{prefix}_ct{i}_col",
                                 help="A=1, B=2, C=3...")
        with cc:
            st.write("")
            if count > 1 and st.button("✕", key=f"{prefix}_ct{i}_del",
                                        help="Xóa dòng này"):
                st.session_state[key_count] = max(1, count - 1)
                st.rerun()
        ds_ct_new.append({"ten": tn.strip(), "col": int(cl)})

    if st.button("➕ Thêm chỉ tiêu", key=f"{prefix}_ct_add"):
        st.session_state[key_count] = count + 1
        st.rerun()

    return {
        "ten_hien_thi":     ten.strip(),
        "sheet_id":         sid.strip(),
        "sheet_tab":        tab.strip(),
        "header_row":       int(hr),
        "stt_col":          int(sc),
        "name_col":         int(nc),
        "pgd_col":          int(pgd_col),
        "loai_cau_truc":    loai_chon,
        "ds_chuong_trinh":  ds_ct_new,
    }


def _render_template_section(username: str) -> None:
    """UI quản lý template cấu hình Google Sheet."""
    from services.template_manager import (
        doc_ds_template, luu_template, xoa_template,
        ten_da_ton_tai, clone_template as _clone_tpl,
    )
    from services.template_detection_service import phat_hien_cau_truc

    # ── Danh sách templates hiện có ───────────────────────────────────────────
    templates = doc_ds_template()
    if templates:
        st.markdown(f"**{len(templates)} template đã lưu:**")
        for t in templates:
            tid   = t["id"]
            mo_ta = t.get("mo_ta") or ""
            label = f"📁 {t['ten']}" + (f" — {mo_ta}" if mo_ta else "")
            with st.expander(label, expanded=False):
                new_ten   = st.text_input("Tên template", value=t["ten"],
                                          key=f"tpl_e_{tid}_ten")
                new_mo_ta = st.text_input("Mô tả", value=mo_ta,
                                          key=f"tpl_e_{tid}_mo_ta")
                cl1, cl2, cl3 = st.columns(3)
                with cl1:
                    if st.button("💾 Lưu tên/mô tả", key=f"tpl_e_{tid}_save",
                                 use_container_width=True):
                        if not new_ten.strip():
                            st.error("❌ Cần nhập tên.")
                        elif ten_da_ton_tai(new_ten.strip(), exclude_id=tid):
                            st.error(f"❌ Tên '{new_ten.strip()}' đã tồn tại.")
                        else:
                            luu_template({**t, "ten": new_ten.strip(),
                                          "mo_ta": new_mo_ta.strip()}, username)
                            st.success("✅ Đã lưu")
                            st.rerun()
                with cl2:
                    if st.button("📋 Clone", key=f"tpl_clone_{tid}",
                                 use_container_width=True, help="Tạo bản copy"):
                        st.session_state[f"tpl_clone_{tid}_show"] = True
                with cl3:
                    if st.button("🗑 Xóa", key=f"tpl_del_{tid}",
                                 use_container_width=True):
                        xoa_template(tid, username)
                        st.success(f"Đã xóa: {t['ten']}")
                        st.rerun()
                if st.session_state.get(f"tpl_clone_{tid}_show"):
                    clone_ten = st.text_input(
                        "Tên bản clone",
                        value=f"{t['ten']} (copy)",
                        key=f"tpl_clone_{tid}_ten",
                    )
                    cc1, cc2 = st.columns(2)
                    with cc1:
                        if st.button("✅ Tạo clone", key=f"tpl_clone_{tid}_ok",
                                     type="primary", use_container_width=True):
                            if not clone_ten.strip():
                                st.error("❌ Cần nhập tên.")
                            elif ten_da_ton_tai(clone_ten.strip()):
                                st.error(f"❌ '{clone_ten.strip()}' đã tồn tại.")
                            else:
                                _clone_tpl(tid, clone_ten.strip(), username)
                                st.session_state.pop(f"tpl_clone_{tid}_show", None)
                                st.success(f"✅ Đã tạo: {clone_ten.strip()}")
                                st.rerun()
                    with cc2:
                        if st.button("✕ Huỷ", key=f"tpl_clone_{tid}_cancel",
                                     use_container_width=True):
                            st.session_state.pop(f"tpl_clone_{tid}_show", None)
                            st.rerun()
        st.divider()

    # ── Tạo template mới từ file mẫu ─────────────────────────────────────────
    st.markdown("**Tạo template từ file mẫu**")
    uploaded = st.file_uploader(
        "Upload file Excel/CSV mẫu",
        type=["xlsx", "xls", "csv"],
        key="tpl_upload",
        help="Upload 1 file mẫu để hệ thống tự detect cấu trúc header, cột",
    )

    if uploaded:
        if st.button("🔍 Phân tích cấu trúc", key="tpl_analyze"):
            try:
                with st.spinner("Đang phân tích..."):
                    result = phat_hien_cau_truc(uploaded.read(), uploaded.name)
                st.session_state["tpl_detect_result"] = result
                st.session_state.pop("tpl_ct_count", None)
            except Exception as e:
                logger.error("_render_template_section: phân tích file — %s", e, exc_info=True)
                st.error(f"❌ {e}")

    detect = st.session_state.get("tpl_detect_result")
    if not detect:
        if not templates:
            st.caption("💡 Upload file Excel từ Phòng KH-NV rồi nhấn **Phân tích cấu trúc** để tạo template.")
        return

    # ── Hiển thị headers detect được ─────────────────────────────────────────
    all_headers = detect.get("all_headers", [])
    if all_headers:
        st.caption("Headers phát hiện: " +
                   " · ".join(f"[{i+1}] {h}" for i, h in enumerate(all_headers) if h.strip()))

    st.markdown("**Xem lại & điều chỉnh cấu hình:**")
    col_a, col_b = st.columns(2)
    with col_a:
        hr = st.number_input("Header row", min_value=1, max_value=50,
                             value=detect["header_row"], key="tpl_hr",
                             help="Hàng chứa tên cột (đếm từ 1)")
        sc = st.number_input("Cột STT", min_value=1, max_value=30,
                             value=detect["stt_col"], key="tpl_sc")
    with col_b:
        nc = st.number_input("Cột Tên đơn vị", min_value=1, max_value=30,
                             value=detect["name_col"], key="tpl_nc")
        _LOAI_OPTS = {
            "phan_cap_stt": "📊 Phân cấp STT",
            "phang":        "📋 Phẳng",
            "cot_pgd":      "🗂 Cột PGD riêng",
        }
        loai_val = detect.get("loai_cau_truc", "phan_cap_stt")
        loai_idx = list(_LOAI_OPTS.keys()).index(loai_val) if loai_val in _LOAI_OPTS else 0
        loai = st.selectbox("Kiểu cấu trúc", list(_LOAI_OPTS.keys()),
                            format_func=lambda k: _LOAI_OPTS[k],
                            index=loai_idx, key="tpl_loai")

    st.markdown("**Cột cần theo dõi** (nhấn ✕ để bỏ bớt):")
    ds_ct_init = list(detect.get("ds_chuong_trinh", []))

    key_count = "tpl_ct_count"
    if key_count not in st.session_state:
        st.session_state[key_count] = len(ds_ct_init)
    count = st.session_state[key_count]
    while len(ds_ct_init) < count:
        ds_ct_init.append({"ten": f"Cột {len(ds_ct_init)+1}", "col": 1})

    ds_ct_new = []
    for i in range(count):
        ct = ds_ct_init[i] if i < len(ds_ct_init) else {"ten": "", "col": 1}
        ca, cb, cc = st.columns([3, 1, 0.5])
        with ca:
            tn = st.text_input("Tên", value=ct.get("ten", ""),
                               key=f"tpl_ct{i}_ten", label_visibility="collapsed")
        with cb:
            cl = st.number_input("Cột", min_value=1, max_value=100,
                                 value=ct.get("col", 1), key=f"tpl_ct{i}_col",
                                 label_visibility="collapsed")
        with cc:
            st.write("")
            if count > 1 and st.button("✕", key=f"tpl_ct{i}_del"):
                st.session_state[key_count] = max(1, count - 1)
                st.rerun()
        if tn.strip():
            ds_ct_new.append({"ten": tn.strip(), "col": int(cl)})

    if st.button("➕ Thêm cột", key="tpl_ct_add"):
        st.session_state[key_count] = count + 1
        st.rerun()

    st.divider()
    tpl_ten   = st.text_input("Tên template *", key="tpl_ten",
                               placeholder="VD: NQH - Phân tích nguyên nhân")
    tpl_mo_ta = st.text_input("Mô tả (tùy chọn)", key="tpl_mo_ta",
                               placeholder="VD: Dùng cho sheet NQH từ 2024+")

    if st.button("💾 Lưu Template", key="tpl_save", type="primary"):
        if not tpl_ten.strip():
            st.error("❌ Cần nhập tên template.")
        elif ten_da_ton_tai(tpl_ten.strip()):
            st.error(f"❌ Template '{tpl_ten.strip()}' đã tồn tại. Dùng tên khác.")
        elif not ds_ct_new:
            st.error("❌ Cần có ít nhất 1 cột theo dõi.")
        else:
            template = {
                "ten":             tpl_ten.strip(),
                "mo_ta":           tpl_mo_ta.strip(),
                "nguoi_tao":       username,
                "ngay_tao":        _date.today().isoformat(),
                "header_row":      int(hr),
                "stt_col":         int(sc),
                "name_col":        int(nc),
                "loai_cau_truc":   loai,
                "ds_chuong_trinh": ds_ct_new,
            }
            luu_template(template, username)
            st.session_state.pop("tpl_detect_result", None)
            st.session_state.pop("tpl_ct_count", None)
            st.success(f"✅ Đã lưu template: {tpl_ten.strip()}")
            st.rerun()


def _render_cai_dat(ds_sheet: list[dict], username: str) -> None:
    with st.expander("📁 Quản lý Template", expanded=False):
        _render_template_section(username)

    st.divider()
    st.markdown("**Danh sách Google Sheet đang theo dõi**")

    if not ds_sheet:
        st.info("Chưa có sheet nào. Thêm mới bên dưới.")
    else:
        for i, cfg in enumerate(ds_sheet):
            ten = cfg.get("ten_hien_thi") or cfg.get("sheet_tab", f"Sheet {i+1}")
            with st.expander(f"📄 {ten}", expanded=False):
                new_cfg = _render_form_sheet(cfg, prefix=f"cd_{i}")

                col_t, col_s, col_d = st.columns([1, 1, 1])
                with col_t:
                    if st.button("🔌 Test", key=f"cd_{i}_test", use_container_width=True):
                        try:
                            with st.spinner("Kết nối..."):
                                rows = _doc_sheet(new_cfg["sheet_id"],
                                                  new_cfg["sheet_tab"],
                                                  new_cfg["header_row"])
                            n = sum(1 for r in rows if any(str(c).strip() for c in r))
                            st.success(f"✅ OK — {n} hàng dữ liệu")
                        except Exception as e:
                            st.error(f"❌ {e}")
                with col_s:
                    if st.button("💾 Lưu", key=f"cd_{i}_save", type="primary",
                                 use_container_width=True):
                        ds_sheet[i] = new_cfg
                        _doc_sheet.clear()
                        _luu_ds_sheet(ds_sheet, username)
                        st.success("✅ Đã lưu")
                        st.rerun()
                with col_d:
                    if st.button("🗑 Xóa", key=f"cd_{i}_del", use_container_width=True):
                        ds_sheet.pop(i)
                        _luu_ds_sheet(ds_sheet, username)
                        st.success("✅ Đã xóa")
                        st.rerun()

                # ── Migration: lưu config này thành template ─────────────────
                if st.button("📁 Lưu thành Template", key=f"cd_{i}_to_tpl",
                             use_container_width=True):
                    st.session_state[f"cd_mig_{i}"] = True

                if st.session_state.get(f"cd_mig_{i}"):
                    from services.template_manager import (
                        luu_template as _luu_tpl_m,
                        ten_da_ton_tai as _dup_m,
                    )
                    mig_ten = st.text_input(
                        "Tên template mới",
                        value=new_cfg.get("ten_hien_thi", ""),
                        key=f"cd_mig_{i}_ten",
                        placeholder="VD: NQH - Phân tích nguyên nhân",
                    )
                    cm1, cm2 = st.columns(2)
                    with cm1:
                        if st.button("✅ Lưu Template", key=f"cd_mig_{i}_ok",
                                     type="primary", use_container_width=True):
                            if not mig_ten.strip():
                                st.error("❌ Cần nhập tên.")
                            elif _dup_m(mig_ten.strip()):
                                st.error(f"❌ '{mig_ten.strip()}' đã tồn tại.")
                            else:
                                _luu_tpl_m({
                                    "ten":             mig_ten.strip(),
                                    "mo_ta":           f"Tạo từ: {new_cfg.get('ten_hien_thi','')}",
                                    "nguoi_tao":       username,
                                    "ngay_tao":        _date.today().isoformat(),
                                    "header_row":      new_cfg.get("header_row",   10),
                                    "stt_col":         new_cfg.get("stt_col",       1),
                                    "name_col":        new_cfg.get("name_col",      2),
                                    "pgd_col":         new_cfg.get("pgd_col",       1),
                                    "loai_cau_truc":   new_cfg.get("loai_cau_truc", "phan_cap_stt"),
                                    "ds_chuong_trinh": list(new_cfg.get("ds_chuong_trinh", [])),
                                }, username)
                                st.session_state.pop(f"cd_mig_{i}", None)
                                st.success(f"✅ Template '{mig_ten.strip()}' đã được lưu.")
                                st.rerun()
                    with cm2:
                        if st.button("✕ Huỷ", key=f"cd_mig_{i}_cancel",
                                     use_container_width=True):
                            st.session_state.pop(f"cd_mig_{i}", None)
                            st.rerun()

    st.divider()
    st.markdown("**➕ Thêm Google Sheet mới**")

    url_input = st.text_input(
        "Paste link Google Sheet",
        key="cd_url_input",
        placeholder="https://docs.google.com/spreadsheets/d/...",
        label_visibility="collapsed",
    )

    if url_input.strip():
        # Trích Sheet ID từ URL
        import re
        m = re.search(r"/spreadsheets/d/([a-zA-Z0-9_-]+)", url_input)
        if not m:
            st.error("❌ Link không hợp lệ. Cần dạng: .../spreadsheets/d/[ID]/...")
        else:
            sid = m.group(1)
            # Kiểm tra đã có chưa
            existing_ids = [s.get("sheet_id") for s in ds_sheet]
            if sid in existing_ids:
                st.warning("⚠️ Sheet này đã có trong danh sách.")
            else:
                try:
                    with st.spinner("Đang đọc danh sách tab..."):
                        client   = _ket_noi_gsheet()
                        ss       = client.open_by_key(sid)
                        tab_list = [w.title for w in ss.worksheets()]

                    # ── Chọn template (áp dụng cho tất cả tab được chọn) ──────
                    from services.template_manager import (
                        doc_ds_template as _tmpl_list,
                        ap_dung_template,
                        goi_y_template as _goi_y,
                    )
                    _templates    = _tmpl_list()
                    _existing_tabs = {s.get("sheet_tab") for s in ds_sheet
                                      if s.get("sheet_id") == sid}

                    if _templates:
                        _tpl_opts    = {"": "📋 Copy từ sheet đầu tiên"}
                        _tpl_opts.update({t["id"]: f"📁 {t['ten']}" for t in _templates})
                        _tpl_keys    = list(_tpl_opts.keys())
                        _suggest_id  = _goi_y(tab_list[0] if tab_list else "", _templates)
                        _suggest_idx = (_tpl_keys.index(_suggest_id)
                                        if _suggest_id and _suggest_id in _tpl_keys else 0)
                        tpl_sel_id = st.selectbox(
                            "Áp dụng template",
                            _tpl_keys,
                            format_func=lambda k: _tpl_opts[k],
                            index=_suggest_idx,
                            key="cd_tpl_sel",
                        )
                        if _suggest_id and _suggest_id == tpl_sel_id:
                            st.caption("✨ Tự động gợi ý dựa trên tên tab đầu tiên.")
                    else:
                        tpl_sel_id = ""

                    # ── Checkbox list chọn tab ────────────────────────────────
                    st.markdown("**Chọn tab cần theo dõi:**")
                    tab_chon_list = []
                    for tab_name in tab_list:
                        da_co = tab_name in _existing_tabs
                        label = tab_name + (" *(đã có)*" if da_co else "")
                        checked = st.checkbox(
                            label,
                            value=(not da_co),
                            key=f"cd_chk_{sid[:8]}_{tab_name[:30]}",
                            disabled=da_co,
                        )
                        if checked and not da_co:
                            tab_chon_list.append(tab_name)

                    n_chon = len(tab_chon_list)
                    if n_chon == 0:
                        st.info("Chưa chọn tab nào.")
                    else:
                        if st.button(f"➕ Thêm {n_chon} tab đã chọn",
                                     key="cd_add_multi", type="primary"):
                            added = []
                            for tab_name in tab_chon_list:
                                ten = tab_name[:40]
                                if tpl_sel_id:
                                    new_cfg = ap_dung_template(tpl_sel_id, sid, tab_name, ten)
                                    if new_cfg is None:
                                        st.warning(f"⚠️ Template lỗi, bỏ qua tab: {tab_name}")
                                        continue
                                else:
                                    base_cfg = ds_sheet[0] if ds_sheet else _sheet_moi()
                                    new_cfg  = {
                                        **base_cfg,
                                        "ten_hien_thi": ten,
                                        "sheet_id":     sid,
                                        "sheet_tab":    tab_name,
                                    }
                                ds_sheet.append(new_cfg)
                                added.append(ten)
                            if added:
                                _doc_sheet.clear()
                                _luu_ds_sheet(ds_sheet, username)
                                st.success(f"✅ Đã thêm {len(added)} tab: "
                                           + " · ".join(added))
                                st.rerun()

                    if tpl_sel_id and _templates:
                        st.caption(f"💡 Cấu hình từ template "
                                   f"**{_tpl_opts.get(tpl_sel_id, '')}** — áp dụng cho tất cả tab chọn.")
                    elif ds_sheet:
                        st.caption(f"💡 Không chọn template → copy cấu hình từ "
                                   f"**{ds_sheet[0].get('ten_hien_thi', 'sheet đầu tiên')}**.")
                    else:
                        st.caption("💡 Tạo template trong mục 📁 Quản lý Template để tự động điền cấu hình.")
                except Exception as e:
                    st.error(f"❌ Không đọc được sheet: {e}")


# ── Hướng dẫn sử dụng ────────────────────────────────────────────────────────

def _render_huong_dan() -> None:
    st.markdown("### 📖 Hướng dẫn sử dụng Theo dõi nhập liệu")

    st.markdown("""
    **Mục đích:** Theo dõi tiến trình nhập liệu của các PGD trên Google Sheets —
    giúp Ban Giám đốc và Phòng KH-NV nắm được PGD nào đã điền đầy đủ số liệu,
    PGD nào còn thiếu, và thiếu ở chỉ tiêu nào.
    """)

    st.divider()

    st.markdown("#### 🟢🟡🔴 Cách đọc kết quả")
    st.markdown("""
    | Biểu tượng | Ý nghĩa |
    |---|---|
    | 🟢 | **Hoàn thành** — tất cả các hàng trong PGD đã được điền đầy đủ |
    | 🟡 | **Một phần** — có điền nhưng chưa đầy đủ |
    | 🔴 | **Chưa điền** — chưa có dữ liệu nào |
    """)

    st.markdown("**Ví dụ:** `🟢 14/14 (100%)` → PGD có 14 xã/phường, đã điền đủ 14/14.")

    st.divider()

    st.markdown("#### 📊 Các tab chức năng")
    st.markdown("""
    - **📊 Tổng quan** — Ma trận tổng hợp PGD × Chỉ tiêu, giúp nhìn nhanh toàn cảnh
    - **📋 Chi tiết** — Bảng số liệu chi tiết, lọc theo chương trình và trạng thái, xuất Excel
    - **⚙️ Cài đặt** — *(Chỉ dành cho Admin/Manager CN)* Thêm/sửa/xóa cấu hình Google Sheet
    """)

    st.divider()

    st.markdown("#### 🗂️ Cấu trúc Google Sheet được hỗ trợ")

    st.markdown("Có **3 kiểu cấu trúc** sheet:")

    st.markdown("""
    **1. 📊 Phân cấp STT** *(mặc định, phổ biến nhất)*
    - Hàng PGD: Cột STT là chữ La Mã (I, II, III...), Cột tên = "PGD X"
    - Hàng xã/phường: Cột STT là số (1, 2, 3...), Cột tên = "Phường Y"
    - Mỗi PGD có nhiều xã/phường con bên dưới

    **2. 📋 Phẳng**
    - Mỗi hàng = 1 đơn vị, không có hàng con
    - Phù hợp khi sheet chỉ liệt kê các PGD (không có xã)

    **3. 🗂 Cột PGD riêng**
    - Có một cột riêng ghi tên PGD cho mỗi hàng
    - Phù hợp khi sheet không dùng STT phân cấp
    """)

    st.markdown("##### Ví dụ minh họa — Kiểu Phân cấp STT")
    st.html(_MOCKUP_HTML)

    st.divider()

    st.markdown("#### 🔌 Cách thêm Google Sheet mới *(dành cho Admin/Manager)*")
    st.markdown("""
    1. Vào tab **⚙️ Cài đặt**
    2. Kéo xuống mục **➕ Thêm Google Sheet mới**
    3. Paste link Google Sheet vào ô nhập
    4. Hệ thống sẽ tự động đọc danh sách tab — chọn tab cần theo dõi
    5. Đặt tên hiển thị cho sheet
    6. Nhấn **➕ Thêm**

    **Lưu ý:**
    - Google Sheet phải được chia sẻ quyền **Viewer** cho tài khoản service account trong `credentials.json`
    - Nếu các sheet có cùng cấu trúc cột, hệ thống sẽ tự copy cấu hình từ sheet đầu tiên
    - Sau khi thêm, có thể mở expander để chỉnh lại cấu hình cột nếu cần
    """)

    st.divider()

    st.markdown("#### ⚙️ Các thông số cấu hình chính")
    st.markdown("""
    | Thông số | Giải thích | Ví dụ |
    |---|---|---|
    | **Header row** | Hàng chứa tên cột (STT, Tên PGD...) | `8` → dữ liệu bắt đầu từ hàng 9 |
    | **Cột STT** | Cột phân biệt PGD (chữ) và xã (số) | `1` → cột A |
    | **Cột Tên đơn vị** | Cột chứa tên PGD hoặc tên xã | `2` → cột B |
    | **Cột theo dõi** | Các cột cần kiểm tra đã điền hay chưa | `4` → cột D (HSSV) |
    """)

    st.info(
        "💡 **Mẹo:** Mở Google Sheet → đếm cột từ trái sang phải để biết số cột. "
        "Cột A = 1, B = 2, C = 3..."
    )

    st.divider()

    st.markdown("#### 🔄 Làm mới dữ liệu")
    st.markdown("""
    - Dữ liệu được cache **5 phút** để tránh gọi GSheet liên tục
    - Nhấn nút **🔄** bên cạnh ô chọn sheet để làm mới ngay
    - Sau khi sửa cấu hình → dữ liệu tự động làm mới
    """)

    st.divider()

    st.markdown("#### ❓ Câu hỏi thường gặp")
    with st.expander("Tôi không thấy tab ⚙️ Cài đặt?"):
        st.markdown("Tab ⚙️ Cài đặt chỉ hiển thị cho **Admin CN** và **Manager CN**. Nếu bạn là PGD, vui lòng liên hệ Phòng KH-NV để được hỗ trợ cấu hình.")
    with st.expander("Sheet báo lỗi khi đọc?"):
        st.markdown("Kiểm tra:\n1. Sheet đã được chia sẻ cho service account chưa?\n2. Sheet ID và tên tab có đúng không?\n3. `credentials.json` đã có trong thư mục dự án chưa?")
    with st.expander("Sao kết quả không khớp với sheet?"):
        st.markdown("Kiểm tra:\n1. **Header row** đã đúng hàng chứa tên cột chưa?\n2. **Cột STT** và **Cột Tên đơn vị** đã đúng vị trí chưa?\n3. **Cột theo dõi** đã trỏ đúng cột cần kiểm tra chưa?\n4. Nhấn **🔄** để làm mới dữ liệu.")


# ── Entry point ───────────────────────────────────────────────────────────────

def render(tab: DeltaGenerator = None, **kwargs) -> None:
    role_raw = str(kwargs.get("role", "user") or "user")
    role_n   = normalize_role(role_raw)
    is_cn    = la_phan_he_cn(role_n)
    username = kwargs.get("username", st.session_state.get("username", "unknown"))

    ctx = get_tab_context(tab)
    with ctx:
        st.subheader("📋 Theo dõi tiến trình nhập liệu PGD")

        if not Path(CREDENTIALS_FILE).exists():
            st.warning("⚠️ Chưa có `credentials.json`.")
            return

        ds_sheet   = _doc_ds_sheet()
        can_config = role_n in ("admin_cn", "manager_cn", "admin", "manager")

        # ── Chọn sheet ────────────────────────────────────────────────────────
        df_td  = pd.DataFrame()
        ds_ct  = []
        ten_sheet = ""

        if not ds_sheet:
            st.info("⚙️ Chưa có sheet nào. Vào tab **⚙️ Cài đặt** để thêm.")
        else:
            labels = [
                cfg.get("ten_hien_thi") or cfg.get("sheet_tab", f"Sheet {i+1}")
                for i, cfg in enumerate(ds_sheet)
            ]
            col_sel, col_ref = st.columns([5, 1])
            with col_sel:
                idx = st.selectbox("📂 Chọn sheet theo dõi", range(len(labels)),
                                   format_func=lambda i: labels[i],
                                   key="ttdn_sheet_sel")
            with col_ref:
                st.write("")
                if st.button("🔄", key="ttdn_refresh", help="Làm mới dữ liệu",
                             use_container_width=True):
                    _doc_sheet.clear()
                    st.rerun()

            cfg_sel   = ds_sheet[idx]
            ten_sheet = labels[idx]
            ds_ct     = cfg_sel.get("ds_chuong_trinh", [])

            sheet_id = cfg_sel.get("sheet_id", "").strip()
            if sheet_id:
                try:
                    with st.spinner(f"Đang đọc **{ten_sheet}**..."):
                        raw = _doc_sheet(sheet_id,
                                         cfg_sel.get("sheet_tab", ""),
                                         cfg_sel.get("header_row", 10))
                    groups = _phan_nhom_pgd(
                        raw,
                        stt_idx     = cfg_sel.get("stt_col",  1) - 1,
                        name_idx    = cfg_sel.get("name_col", 2) - 1,
                        loai        = cfg_sel.get("loai_cau_truc", "phan_cap_stt"),
                        pgd_col_idx = cfg_sel.get("pgd_col", 1) - 1,
                    )
                    df_td = _tinh_tien_do(groups, ds_ct)
                    n_con = sum(len(v) for v in groups.values())
                    loai_label = {"phan_cap_stt": "phân cấp STT",
                                  "phang": "phẳng", "cot_pgd": "cột PGD"
                                  }.get(cfg_sel.get("loai_cau_truc", ""), "")
                    st.caption(f"📅 Cache 5 phút · {len(groups)} đơn vị · "
                               f"{n_con} hàng · {loai_label}")
                except Exception as e:
                    logger.error("tab_theo_doi_nhap: %s", e, exc_info=True)
                    st.error(f"❌ Lỗi đọc sheet: {e}")
            else:
                st.warning("Sheet này chưa có Sheet ID. Vào Cài đặt để nhập.")

        # ── Tabs ─────────────────────────────────────────────────────────────
        if can_config:
            t0, t1, t2, t3 = st.tabs(["📊 Tổng quan", "📋 Chi tiết", "⚙️ Cài đặt", "📖 Hướng dẫn"])
        else:
            t0, t1, t3 = st.tabs(["📊 Tổng quan", "📋 Chi tiết", "📖 Hướng dẫn"])
            t2 = None

        with t0:
            _render_tong_quan(df_td, ds_ct, ten_sheet)
        with t1:
            _render_chi_tiet(df_td, ds_ct, username)
        if t2 is not None:
            with t2:
                _render_cai_dat(ds_sheet, username)
        with t3:
            _render_huong_dan()
