"""Theo dõi tiến trình nhập liệu của PGD trên nhiều Google Sheet phân cấp.

Sheet có cấu trúc:
  - PGD header row: Col STT = Số La Mã (I, II, III...), Col tên = "PGD X"
  - Xã/phường row:  Col STT = số thập phân (1.0, 2.0...), Col tên = "Phường Y"
Admin cấu hình nhiều sheet, mỗi sheet có tên hiển thị riêng.
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


def _phan_nhom_pgd(rows: list[list], stt_idx: int, name_idx: int) -> dict[str, list[list]]:
    groups: dict[str, list[list]] = {}
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

    st.markdown("**Cấu hình hàng & cột**")
    c1, c2, c3 = st.columns(3)
    with c1:
        hr = st.number_input("Header row (hàng tên cột)", min_value=1, max_value=50,
                             value=cfg.get("header_row", 10), key=f"{prefix}_hr",
                             help="Hàng chứa STT, Tên PGD, tên cột... Dữ liệu bắt đầu từ hàng tiếp theo")
    with c2:
        sc = st.number_input("Cột STT (phân biệt PGD/xã)", min_value=1, max_value=30,
                             value=cfg.get("stt_col", 1), key=f"{prefix}_sc",
                             help="Cột chứa số thứ tự. PGD = chữ La Mã (I,II...), Xã = số (1,2...)")
    with c3:
        nc = st.number_input("Cột Tên đơn vị", min_value=1, max_value=30,
                             value=cfg.get("name_col", 2), key=f"{prefix}_nc",
                             help="Cột chứa tên PGD / tên xã phường")

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
        "ds_chuong_trinh":  ds_ct_new,
    }


def _render_cai_dat(ds_sheet: list[dict], username: str) -> None:
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

                    col_a, col_b, col_c = st.columns([2, 2, 1])
                    with col_a:
                        tab_chon = st.selectbox("Chọn tab", tab_list, key="cd_tab_chon")
                    with col_b:
                        ten_hien_thi = st.text_input(
                            "Đặt tên", key="cd_ten_moi",
                            placeholder="VD: HSSV Lần 3 - 2026",
                            value=tab_chon[:40] if tab_chon else "",
                        )
                    with col_c:
                        st.write("")
                        if st.button("➕ Thêm", key="cd_add_quick",
                                     type="primary", use_container_width=True):
                            # Copy cấu hình cột từ sheet đầu tiên (cùng cấu trúc)
                            base_cfg = ds_sheet[0] if ds_sheet else _sheet_moi()
                            new_cfg  = {
                                **base_cfg,
                                "ten_hien_thi": ten_hien_thi.strip() or tab_chon,
                                "sheet_id":     sid,
                                "sheet_tab":    tab_chon,
                            }
                            ds_sheet.append(new_cfg)
                            _doc_sheet.clear()
                            _luu_ds_sheet(ds_sheet, username)
                            st.success(f"✅ Đã thêm: {new_cfg['ten_hien_thi']}")
                            st.rerun()

                    if ds_sheet:
                        st.caption(f"💡 Cấu hình cột sẽ copy từ **{ds_sheet[0].get('ten_hien_thi', 'sheet đầu tiên')}**. "
                                   "Nếu cột khác → mở expander sheet vừa thêm để chỉnh.")
                except Exception as e:
                    st.error(f"❌ Không đọc được sheet: {e}")


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
                    groups = _phan_nhom_pgd(raw,
                                            cfg_sel.get("stt_col", 1) - 1,
                                            cfg_sel.get("name_col", 2) - 1)
                    df_td  = _tinh_tien_do(groups, ds_ct)
                    st.caption(f"📅 Cache 5 phút · {len(groups)} đơn vị · "
                               f"{sum(len(v) for v in groups.values())} xã/phường")
                except Exception as e:
                    logger.error("tab_theo_doi_nhap: %s", e, exc_info=True)
                    st.error(f"❌ Lỗi đọc sheet: {e}")
            else:
                st.warning("Sheet này chưa có Sheet ID. Vào Cài đặt để nhập.")

        # ── Tabs ─────────────────────────────────────────────────────────────
        if can_config:
            t0, t1, t2 = st.tabs(["📊 Tổng quan", "📋 Chi tiết", "⚙️ Cài đặt"])
        else:
            t0, t1 = st.tabs(["📊 Tổng quan", "📋 Chi tiết"])
            t2 = None

        with t0:
            _render_tong_quan(df_td, ds_ct, ten_sheet)
        with t1:
            _render_chi_tiet(df_td, ds_ct, username)
        if t2 is not None:
            with t2:
                _render_cai_dat(ds_sheet, username)
