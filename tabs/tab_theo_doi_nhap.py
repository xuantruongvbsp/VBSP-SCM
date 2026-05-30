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


def _render_form_sheet(cfg: dict, prefix: str) -> dict:
    """Form nhập 1 sheet config, trả về dict đã cập nhật."""
    ten = st.text_input("Tên hiển thị", value=cfg.get("ten_hien_thi", ""),
                        key=f"{prefix}_ten",
                        help="VD: HSSV Lần 2 - 2026")
    sid = st.text_input("Google Sheet ID", value=cfg.get("sheet_id", ""),
                        key=f"{prefix}_sid",
                        help="Lấy từ URL: .../spreadsheets/d/**[ID]**/edit")
    tab = st.text_input("Tên worksheet (tab)", value=cfg.get("sheet_tab", ""),
                        key=f"{prefix}_tab")

    c1, c2, c3 = st.columns(3)
    with c1:
        hr = st.number_input("Header row", min_value=1, max_value=50,
                             value=cfg.get("header_row", 10), key=f"{prefix}_hr")
    with c2:
        sc = st.number_input("Cột STT", min_value=1, max_value=30,
                             value=cfg.get("stt_col", 1), key=f"{prefix}_sc")
    with c3:
        nc = st.number_input("Cột Tên đơn vị", min_value=1, max_value=30,
                             value=cfg.get("name_col", 2), key=f"{prefix}_nc")

    st.markdown("**Cột 'Điều chỉnh tăng trưởng' (1-indexed):**")
    ds_ct_old = cfg.get("ds_chuong_trinh", list(DEFAULT_CT))
    ds_ct_new = []
    for i, ct in enumerate(ds_ct_old):
        ca, cb = st.columns([3, 1])
        with ca:
            tn = st.text_input("Tên CT", value=ct["ten"], key=f"{prefix}_ct{i}_ten")
        with cb:
            cl = st.number_input("Cột", min_value=1, max_value=50,
                                 value=ct["col"], key=f"{prefix}_ct{i}_col")
        ds_ct_new.append({"ten": tn, "col": int(cl)})

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
    st.markdown("**➕ Thêm sheet mới**")
    with st.expander("Mở form thêm mới", expanded=len(ds_sheet) == 0):
        new_cfg = _render_form_sheet(_sheet_moi(), prefix="cd_new")
        col_t2, col_s2 = st.columns(2)
        with col_t2:
            if st.button("🔌 Test kết nối", key="cd_new_test", use_container_width=True):
                try:
                    with st.spinner("Kết nối..."):
                        rows = _doc_sheet(new_cfg["sheet_id"],
                                          new_cfg["sheet_tab"],
                                          new_cfg["header_row"])
                    n = sum(1 for r in rows if any(str(c).strip() for c in r))
                    st.success(f"✅ OK — {n} hàng dữ liệu")
                except Exception as e:
                    st.error(f"❌ {e}")
        with col_s2:
            if st.button("➕ Thêm vào danh sách", key="cd_new_add",
                         type="primary", use_container_width=True):
                if not new_cfg["sheet_id"] or not new_cfg["ten_hien_thi"]:
                    st.error("❌ Cần nhập Tên hiển thị và Sheet ID")
                else:
                    ds_sheet.append(new_cfg)
                    _doc_sheet.clear()
                    _luu_ds_sheet(ds_sheet, username)
                    st.success(f"✅ Đã thêm: {new_cfg['ten_hien_thi']}")
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
