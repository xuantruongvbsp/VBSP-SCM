"""Tab Báo cáo KHNV — Upload Điện báo & So sánh kỳ.

THIẾT KẾ THEO MẪU DIEN BAO NGAY CN:
- Upload file HIỆN TẠI (vd: sheet M) + file KỲ TRƯỚC (vd: sheet Y)
- Bảng so sánh: Chỉ tiêu | Hiện tại | Kỳ trước | Chênh lệch | Tỷ lệ %
- Tự động phát hiện đơn vị, định dạng số
- Xuất Excel/Word

3 chế độ:
- 📡 Điện báo:     Upload 2 file → bảng so sánh
- 📊 HSTD:         Từ dữ liệu chi tiết
- 🔄 Đối chiếu:    HSTD vs Điện báo
"""
from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

from io import BytesIO

import streamlit as st
import pandas as pd
import os

from logger import get_logger
from services.khnv_bao_cao_service import (
    tong_hop_so_lieu_thang,
    tong_hop_tu_dienbao,
    so_sanh_hstd_vs_dienbao,
    lay_danh_sach_mau,
    xuat_excel_bao_cao_khnv,
    xuat_word_bao_cao_khnv,
    build_template_vars,
    render_mau_preview,
)
from components.delta_card import kpi_row
from data import ts_file
from config import DB_HT_CACHE, DB_PREV_CACHE, FILE_PATH_DB, FILE_PATH_DB_PREV
from services.upload_service import luu_dienbao
from utils import fmt_so, fmt_ty

from tabs.base_tab import TabContext

if TYPE_CHECKING:
    from streamlit.delta_generator import DeltaGenerator

logger = get_logger(__name__)


def _find_db_file(loai: str) -> str | None:
    if loai == "ht":
        return DB_HT_CACHE if os.path.exists(DB_HT_CACHE) else (FILE_PATH_DB if os.path.exists(FILE_PATH_DB) else None)
    elif loai == "prev":
        return DB_PREV_CACHE if os.path.exists(DB_PREV_CACHE) else (FILE_PATH_DB_PREV if os.path.exists(FILE_PATH_DB_PREV) else None)
    return None


def _file_info(fp: str) -> str:
    try:
        kb = os.path.getsize(fp) // 1024
        mt = datetime.fromtimestamp(os.path.getmtime(fp)).strftime("%d/%m/%Y %H:%M")
        return f"📂 {os.path.basename(fp)} · {kb} KB · {mt}"
    except Exception:
        return f"📂 {os.path.basename(fp)}"


def _fmt_vnd(x, don_vi_trieu: bool = False) -> str:
    """Format số: nếu triệu đồng → tỷ đồng, nếu đồng → triệu đồng."""
    try:
        x = float(x)
        if don_vi_trieu:
            value = f"{x/1000:,.1f}"
        else:
            value = f"{x/1_000_000:,.0f}"
        return value.replace(",", "_").replace(".", ",").replace("_", ".")
    except Exception:
        return "—"


def _bang_hstd_hien_thi(df: pd.DataFrame) -> pd.DataFrame:
    """Tạo bản hiển thị Việt Nam; giữ DataFrame số gốc cho Excel/Word."""
    if df is None or df.empty:
        return pd.DataFrame()
    result = df.copy()
    rename: dict[str, str] = {}
    for col in result.columns:
        col_norm = str(col).casefold().replace("_", " ")
        if "dư nợ" in col_norm:
            result[col] = pd.to_numeric(result[col], errors="coerce").apply(fmt_ty)
            rename[col] = f"{str(col).replace('_', ' ')} (triệu đồng)"
        elif "số khách hàng" in col_norm or "số món" in col_norm:
            result[col] = pd.to_numeric(result[col], errors="coerce").apply(fmt_so)
            rename[col] = str(col).replace("_", " ")
        elif "tỷ lệ" in col_norm:
            result[col] = pd.to_numeric(result[col], errors="coerce").apply(
                lambda value: f"{value:.2f}".replace(".", ",") + "%"
            )
            rename[col] = str(col).replace("_", " ")
        else:
            rename[col] = str(col).replace("_", " ")
    return result.rename(columns=rename)


def _bang_doi_chieu_hien_thi(chenh_lech: list[dict]) -> pd.DataFrame:
    result = pd.DataFrame(chenh_lech)
    if result.empty:
        return result
    for col in ("HSTD", "Điện báo", "Chênh lệch"):
        if col in result.columns:
            result[col] = pd.to_numeric(result[col], errors="coerce").apply(fmt_ty)
    if "Tỷ lệ %" in result.columns:
        result["Tỷ lệ %"] = pd.to_numeric(result["Tỷ lệ %"], errors="coerce").apply(
            lambda value: f"{value:+.2f}".replace(".", ",") + "%"
        )
    return result.rename(
        columns={
            "HSTD": "HSTD (triệu đồng)",
            "Điện báo": "Điện báo (triệu đồng)",
            "Chênh lệch": "Chênh lệch (triệu đồng)",
        }
    )


def _build_ss_table(
    fp_ht: str, sheet_ht: str, fp_prev: str | None, sheet_prev: str | None,
) -> tuple[pd.DataFrame, bool, dict, dict]:
    """Xây bảng so sánh từ 2 file/sheet.

    Returns: (df_so_sanh, has_prev, db_ht, db_prev)
    """
    from data.hstd import doc_dienbao_matrix, doc_dienbao, liet_ke_sheet_dienbao

    # ── Đọc data hiện tại ──
    try:
        data_ht = doc_dienbao_matrix(fp_ht, ts_file(fp_ht), sheet_name=sheet_ht)
    except Exception as matrix_error:
        logger.warning(
            "Đọc Điện báo matrix thất bại, thử format dọc: %s",
            matrix_error,
            exc_info=True,
        )
        try:
            rows_ht = doc_dienbao(fp_ht, ts_file(fp_ht), sheet_name=sheet_ht)
            data_ht = {"rows": rows_ht, "units": [], "matrix": {}, "ngay_bao_cao": ""}
        except Exception as e:
            logger.error("Không đọc được Điện báo hiện tại: %s", e, exc_info=True)
            return pd.DataFrame({"Lỗi": [str(e)]}), False, {}, {}

    rows_ht = data_ht.get("rows", [])
    ngay_ht = data_ht.get("ngay_bao_cao", "Hiện tại")
    units = data_ht.get("units", [])
    matrix_ht = data_ht.get("matrix", {})
    _is_trieu = any(r.get("don_vi_trieu") for r in rows_ht)

    db_ht_info = {"ngay_bao_cao": ngay_ht, "units": units, "matrix": matrix_ht,
                  "rows": rows_ht, "is_trieu": _is_trieu}

    # ── Đọc data kỳ trước ──
    has_prev = bool(fp_prev and os.path.exists(fp_prev))
    rows_pv = []
    matrix_pv = {}
    ngay_pv = "Kỳ trước"
    if has_prev:
        try:
            data_pv = doc_dienbao_matrix(fp_prev, ts_file(fp_prev), sheet_name=sheet_prev)
            rows_pv = data_pv.get("rows", [])
            matrix_pv = data_pv.get("matrix", {})
            ngay_pv = data_pv.get("ngay_bao_cao", "Kỳ trước")
        except Exception:
            try:
                rows_pv = doc_dienbao(fp_prev, ts_file(fp_prev), sheet_name=sheet_prev)
            except Exception:
                rows_pv = []

    db_pv_info = {"ngay_bao_cao": ngay_pv, "matrix": matrix_pv, "rows": rows_pv}

    # ── Build dict tra cứu nhanh cho kỳ trước ──
    pv_lookup = {}
    for r in rows_pv:
        if not r.get("la_nqh_con"):
            pv_lookup[r["ten"]] = r["val"]

    # ── Xây bảng so sánh ──
    rows_ss = []
    for r in rows_ht:
        if r.get("la_nqh_con"):
            continue
        ten = r["ten"]
        val_ht = r["val"]
        val_pv = pv_lookup.get(ten, None) if has_prev else None

        if val_pv is not None:
            cl = val_ht - val_pv
            tl = round(cl / val_pv * 100, 2) if val_pv else (100.0 if val_ht else 0.0)
        else:
            cl = None
            tl = None

        rows_ss.append({
            "Chỉ tiêu": ten,
            ngay_ht[:25]: _fmt_vnd(val_ht, _is_trieu),
            ngay_pv[:25] if has_prev else "Kỳ trước": _fmt_vnd(val_pv, _is_trieu) if val_pv is not None else "—",
            "Chênh lệch": _fmt_vnd(cl, _is_trieu) if cl is not None else "—",
            "Tỷ lệ %": f"{tl:+.1f}%" if tl is not None else "—",
            "_ht": val_ht, "_pv": val_pv or 0, "_cl": cl or 0, "_tl": tl or 0,
        })

    df_ss = pd.DataFrame(rows_ss)
    return df_ss, has_prev, db_ht_info, db_pv_info


def render(tab: DeltaGenerator | None = None, **kwargs) -> None:
    ctx = TabContext(tab, **kwargs)

    _df_full = kwargs.get("df_full")
    df_full = _df_full if _df_full is not None else kwargs.get("df")
    role = kwargs.get("role", "")
    username = kwargs.get("username", "unknown")

    # Biến dùng chung
    so_lieu: dict = {}
    bang_pgd = pd.DataFrame()
    bang_ct = pd.DataFrame()
    bang_uy_thac = pd.DataFrame()
    bang_dienbao = pd.DataFrame()
    chenh_lech: list = []

    with ctx:
        st.subheader("📄 Báo cáo KHNV")

        # ═══════════════════════════════════════════
        # STEP 1: CHỌN NGUỒN + THÁNG/NĂM
        # ═══════════════════════════════════════════
        nguon = st.radio(
            "📡 Nguồn dữ liệu:",
            ["📡 Điện báo (upload & so sánh)", "📊 HSTD (dữ liệu chi tiết)", "🔄 Đối chiếu HSTD vs Điện báo"],
            horizontal=True, key="khnv_bc_nguon",
        )

        col1, col2 = st.columns(2)
        nam_options = list(range(2024, max(2030, date.today().year) + 1))
        with col1:
            thang = st.selectbox("Tháng", list(range(1, 13)), index=date.today().month - 1, key="khnv_bc_thang")
        with col2:
            nam = st.selectbox(
                "Năm",
                nam_options,
                index=nam_options.index(date.today().year),
                key="khnv_bc_nam",
            )

        st.divider()

        # ═══════════════════════════════════════════
        # MODE 1: ĐIỆN BÁO — UPLOAD + SO SÁNH
        # ═══════════════════════════════════════════
        if nguon == "📡 Điện báo (upload & so sánh)":
            # ── Upload Area ──
            with st.container(border=True):
                st.caption("📤 **Upload file Điện báo**")

                up_ht, up_prev = st.columns(2)

                with up_ht:
                    fp_ht = _find_db_file("ht")
                    if fp_ht:
                        st.success(_file_info(fp_ht))
                    else:
                        st.warning("⚠️ Chưa có file hiện tại")
                    f_ht = st.file_uploader("File HIỆN TẠI (.xlsx)", type=["xlsx", "xls"],
                                            key="khnv_up_ht", label_visibility="collapsed")

                with up_prev:
                    fp_prev = _find_db_file("prev")
                    if fp_prev:
                        st.success(_file_info(fp_prev))
                    else:
                        st.info("💡 Upload để so sánh")
                    f_prev = st.file_uploader("File KỲ TRƯỚC (.xlsx)", type=["xlsx", "xls"],
                                              key="khnv_up_prev", label_visibility="collapsed")

                # Xử lý upload
                uploaded = False
                if f_ht:
                    kq = luu_dienbao("ht", f_ht.read(), f_ht.name)
                    kq.hien_thi()
                    if kq.thanh_cong:
                        uploaded = True
                if f_prev:
                    kq = luu_dienbao("prev", f_prev.read(), f_prev.name)
                    kq.hien_thi()
                    if kq.thanh_cong:
                        uploaded = True
                if uploaded:
                    st.cache_data.clear()
                    st.rerun()

            # ── Lấy lại path sau upload ──
            fp_ht = _find_db_file("ht")
            if not fp_ht:
                st.info("👆 Upload file Điện báo hiện tại để bắt đầu.")
                return
            fp_prev = _find_db_file("prev")

            # ── Chọn sheet ──
            from data.hstd import liet_ke_sheet_dienbao
            ds_sheet = liet_ke_sheet_dienbao(fp_ht)
            sheet_info = {s["sheet"]: s for s in ds_sheet}
            sheet_opts = [s["sheet"] for s in ds_sheet]

            col_sh, col_shp = st.columns(2)
            with col_sh:
                default_ix = sheet_opts.index("M") if "M" in sheet_opts else (sheet_opts.index("DB1") if "DB1" in sheet_opts else 0)
                sheet_ht = st.selectbox("Sheet HIỆN TẠI", sheet_opts, index=default_ix,
                                        key="khnv_sh_ht",
                                        format_func=lambda s: f"{s} · {sheet_info[s]['rows']} dòng · {sheet_info[s].get('ngay','')[:30]}")
            with col_shp:
                if fp_prev:
                    ds_sheet_pv = liet_ke_sheet_dienbao(fp_prev)
                    sheet_opts_pv = [s["sheet"] for s in ds_sheet_pv]
                    sheet_info_pv = {s["sheet"]: s for s in ds_sheet_pv}
                    # Tự map: nếu ht chọn M → prev tự chọn Y
                    auto_prev = {"M": "Y", "DB": "KH_GIAO_DAU_NAM"}.get(sheet_ht, sheet_ht)
                    default_pv = auto_prev if auto_prev in sheet_opts_pv else (sheet_opts_pv[0] if sheet_opts_pv else None)
                    sheet_prev = st.selectbox("Sheet KỲ TRƯỚC", sheet_opts_pv,
                                              index=sheet_opts_pv.index(default_pv) if default_pv else 0,
                                              key="khnv_sh_pv",
                                              format_func=lambda s: f"{s} · {sheet_info_pv.get(s, {}).get('rows','?')} dòng")
                else:
                    sheet_prev = None

            # ── BUILD SO SÁNH ──
            df_ss, has_prev, db_ht, db_pv = _build_ss_table(fp_ht, sheet_ht, fp_prev, sheet_prev)
            so_lieu_db = tong_hop_tu_dienbao(
                sheet_name=sheet_ht,
                file_path_override=fp_ht,
            )
            if "error" not in so_lieu_db:
                so_lieu = {**so_lieu_db, "thang": thang, "nam": nam}
                bang_dienbao = so_lieu_db.get("bang_theo_dv", pd.DataFrame())
            else:
                st.error(f"❌ Không tổng hợp được Điện báo: {so_lieu_db['error']}")

            _is_trieu = db_ht.get("is_trieu", False)
            _suffix = "tỷ đồng" if _is_trieu else "triệu đồng"
            _to_kpi = lambda x: round(x/1000, 1) if _is_trieu else round(x/1e6, 0)

            # ── KPI cards nhanh (hàng đầu của bảng) ──
            if not df_ss.empty and "Chỉ tiêu" in df_ss.columns:
                # Tìm dòng "TỔNG DƯ NỢ" để làm KPI tổng
                ten_dn = next((t for t in ["TỔNG DƯ NỢ", "Tổng dư nợ"] if t in df_ss["Chỉ tiêu"].values), None)
                if ten_dn:
                    row_dn = df_ss[df_ss["Chỉ tiêu"] == ten_dn].iloc[0]
                    st.markdown("### 📊 Tổng quan")
                    kpi_row([{
                        "label": "Tổng dư nợ", "value": _to_kpi(row_dn["_ht"]),
                        "icon": "💰", "suffix": _suffix, "precision": 1,
                        "delta": _to_kpi(row_dn["_cl"]) if has_prev and row_dn["_cl"] else None,
                        "delta_label": f"vs kỳ trước" if has_prev else "",
                        "delta_color": "normal",
                    }], num_columns=1)
                    st.caption(f"📅 {db_ht.get('ngay_bao_cao','Hiện tại')[:40]}" +
                               (f"  —  📅 {db_pv.get('ngay_bao_cao','Kỳ trước')[:40]}" if has_prev else ""))

            # ── Bảng so sánh chính ──
            st.divider()
            st.markdown("### 📋 Bảng so sánh chỉ tiêu")
            st.caption(f"Đơn vị hiển thị: **{_suffix}**")

            if not df_ss.empty:
                col_display = [c for c in df_ss.columns if not c.startswith("_")]
                # Dùng st.dataframe với column config
                st.dataframe(
                    df_ss[col_display],
                    use_container_width=True,
                    hide_index=True,
                    height=600,
                    column_config={
                        "Chỉ tiêu": st.column_config.TextColumn("Chỉ tiêu", width="large"),
                    },
                )

                # ── Download bảng ──
                buf = BytesIO()
                with pd.ExcelWriter(buf, engine="openpyxl") as w:
                    df_ss[col_display].to_excel(w, index=False, sheet_name="So sánh")
                st.download_button(
                    f"⬇️ Tải bảng so sánh (.xlsx)",
                    data=buf.getvalue(),
                    file_name=f"SoSanh_DienBao_T{thang:02d}_{nam}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="khnv_dl_ss",
                )
            else:
                st.warning("Không đọc được dữ liệu từ file.")

            if so_lieu:
                st.caption(
                    f"Đã chuẩn hóa số liệu nguồn từ **{so_lieu.get('don_vi_nguon', 'đồng')}** "
                    "sang VND để xuất và đối chiếu."
                )

        # ═══════════════════════════════════════════
        # MODE 2: HSTD
        # ═══════════════════════════════════════════
        elif nguon == "📊 HSTD (dữ liệu chi tiết)":
            if df_full is None or df_full.empty:
                st.warning("⚠️ Chưa có dữ liệu HSTD.")
                return
            so_lieu = tong_hop_so_lieu_thang(df_full, thang=thang, nam=nam)
            try:
                ngay_nguon = pd.to_datetime(
                    so_lieu.get("ngay_bao_cao"),
                    dayfirst=True,
                ).date()
                if (ngay_nguon.month, ngay_nguon.year) != (thang, nam):
                    st.warning(
                        f"⚠️ HSTD hiện là snapshot ngày {ngay_nguon.strftime('%d/%m/%Y')}; "
                        f"tháng/năm đã chọn ({thang:02d}/{nam}) chỉ dùng làm kỳ ghi trên báo cáo."
                    )
            except (TypeError, ValueError):
                pass

            st.markdown("### 📊 Số liệu từ HSTD")
            kpi_row([
                {"label": "Tổng dư nợ", "value": so_lieu.get("tong_du_no", 0) / 1e9, "icon": "💰", "suffix": "tỷ", "precision": 3},
                {"label": "Nợ quá hạn", "value": so_lieu.get("du_no_qua_han", 0) / 1e9, "icon": "⚠️", "suffix": "tỷ", "precision": 3,
                 "delta": so_lieu.get("ty_le_no_qua_han", 0), "delta_label": "%", "delta_color": "inverse"},
                {"label": "Số KH", "value": so_lieu.get("so_khach_hang", 0), "icon": "👥", "suffix": "", "precision": 0},
                {"label": "Giải ngân tháng", "value": so_lieu.get("giai_ngan_trong_thang", 0) / 1e9, "icon": "📤", "suffix": "tỷ", "precision": 3},
            ], num_columns=4)

            bang_pgd = so_lieu.get("bang_pgd", pd.DataFrame())
            bang_ct = so_lieu.get("bang_chuong_trinh", pd.DataFrame())
            bang_uy_thac = so_lieu.get("bang_uy_thac", pd.DataFrame())

            st.divider()
            t1, t2, t3 = st.tabs(["📋 Theo PGD", "📑 Chương trình", "🤝 Ủy thác"])
            with t1:
                st.dataframe(_bang_hstd_hien_thi(bang_pgd), use_container_width=True, hide_index=True) if not bang_pgd.empty else st.info("—")
            with t2:
                st.dataframe(_bang_hstd_hien_thi(bang_ct), use_container_width=True, hide_index=True) if not bang_ct.empty else st.info("—")
            with t3:
                st.dataframe(_bang_hstd_hien_thi(bang_uy_thac), use_container_width=True, hide_index=True) if not bang_uy_thac.empty else st.info("—")

        # ═══════════════════════════════════════════
        # MODE 3: ĐỐI CHIẾU
        # ═══════════════════════════════════════════
        elif nguon == "🔄 Đối chiếu HSTD vs Điện báo":
            if df_full is None or df_full.empty:
                st.warning("⚠️ Chưa có HSTD.")
                return
            fp_db = _find_db_file("ht")
            if not fp_db:
                st.warning("⚠️ Chưa có Điện báo.")
                return

            from data.hstd import liet_ke_sheet_dienbao
            sheets_db = liet_ke_sheet_dienbao(fp_db)
            sheet_options_db = [item["sheet"] for item in sheets_db]
            if not sheet_options_db:
                st.warning("⚠️ File Điện báo không có sheet dữ liệu.")
                return
            default_sheet = "DB1" if "DB1" in sheet_options_db else (
                "M" if "M" in sheet_options_db else sheet_options_db[0]
            )
            sheet_db = st.selectbox(
                "Sheet Điện báo dùng để đối chiếu",
                sheet_options_db,
                index=sheet_options_db.index(default_sheet),
                key="khnv_compare_sheet",
            )
            so_lieu = tong_hop_so_lieu_thang(df_full, thang=thang, nam=nam)
            so_lieu_db = tong_hop_tu_dienbao(
                sheet_name=sheet_db,
                file_path_override=fp_db,
            )
            if "error" not in so_lieu_db:
                chenh_lech = so_sanh_hstd_vs_dienbao(so_lieu, so_lieu_db)
                so_lieu["nguon"] = "HSTD + Điện báo"

            st.markdown("### 🔄 Đối chiếu HSTD vs Điện báo")
            if chenh_lech:
                so_khop = sum(item.get("Cảnh báo") == "✅" for item in chenh_lech)
                so_canh_bao = len(chenh_lech) - so_khop
                max_tl = max(abs(float(item.get("Tỷ lệ %", 0))) for item in chenh_lech)
                kpi_row([
                    {"label": "Chỉ tiêu đã kiểm tra", "value": len(chenh_lech), "icon": "🔎", "precision": 0},
                    {"label": "Khớp trong 1%", "value": so_khop, "icon": "✅", "precision": 0},
                    {"label": "Cần kiểm tra", "value": so_canh_bao, "icon": "⚠️", "precision": 0},
                    {"label": "Lệch lớn nhất", "value": max_tl, "icon": "📐", "suffix": "%", "precision": 2},
                ], num_columns=4)
                st.dataframe(
                    _bang_doi_chieu_hien_thi(chenh_lech),
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                st.info("Không có dữ liệu đối chiếu.")

            bang_pgd = so_lieu.get("bang_pgd", pd.DataFrame())
            bang_ct = so_lieu.get("bang_chuong_trinh", pd.DataFrame())
            bang_uy_thac = so_lieu.get("bang_uy_thac", pd.DataFrame())
            bang_dienbao = so_lieu_db.get("bang_theo_dv", pd.DataFrame())

        # ═══════════════════════════════════════════
        # 1. XEM & COPY BÁO CÁO (chính)
        # ═══════════════════════════════════════════
        st.divider()
        st.markdown("### 📋 Báo cáo (copy sang Word)")

        ds_mau = lay_danh_sach_mau()
        mau_options = [m["ten_hien_thi"] for m in ds_mau] or ["Không tìm thấy mẫu"]

        ten_mau_chon = st.selectbox("Chọn loại báo cáo", mau_options, key="khnv_bc_mau")

        if ten_mau_chon and ds_mau and so_lieu:
            mau_info = next((m for m in ds_mau if m["ten_hien_thi"] == ten_mau_chon), None)
            if mau_info:
                vars_map = build_template_vars(so_lieu, bang_pgd, chenh_lech)
                rendered = render_mau_preview(mau_info["ten_file"], vars_map)

                # Text area lớn — bôi đen → Ctrl+C → paste vào Word
                st.text_area(
                    "Bôi đen toàn bộ → Ctrl+C → mở Word → Ctrl+V",
                    value=rendered,
                    height=550,
                    key="khnv_bc_preview_area",
                    label_visibility="visible",
                )
        else:
            st.info("👆 Chọn nguồn dữ liệu & tháng/năm ở trên để hiển thị báo cáo.")

        st.divider()
        st.caption("⬇️ Hoặc tải file:")

        # ═══════════════════════════════════════════
        # 2. TẢI FILE Excel / Word (phụ)
        # ═══════════════════════════════════════════
        col_x1, col_x2 = st.columns(2)
        fn = f"BC_KHNV_T{thang:02d}_{nam}"

        with col_x1:
            eb = xuat_excel_bao_cao_khnv(
                so_lieu, bang_pgd, bang_ct, bang_uy_thac,
                bang_dienbao=bang_dienbao if not bang_dienbao.empty else None,
                chenh_lech=chenh_lech,
            )
            st.download_button(f"⬇️ Excel ({fn}.xlsx)", data=eb, file_name=f"{fn}.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                               key="khnv_dl_xl", use_container_width=True)

        with col_x2:
            wb = xuat_word_bao_cao_khnv(
                so_lieu, ten_mau_chon, bang_pgd, bang_ct,
                bang_dienbao=bang_dienbao if not bang_dienbao.empty else None,
                chenh_lech=chenh_lech,
            )
            st.download_button(f"⬇️ Word ({fn}.docx)", data=wb, file_name=f"{fn}.docx",
                               mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                               key="khnv_dl_wd", use_container_width=True)
