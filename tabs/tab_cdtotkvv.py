"""
Tab Chấm điểm Tổ TK&VV — chỉ admin/manager.

Sub-tab 1: Upload file Excel chấm điểm theo tháng.
Sub-tab 2: Tổng hợp theo Phòng giao dịch với KPI và xuất Excel.
Sub-tab 3: Phân tích Chất lượng - KPI và bảng tiêu chí bị trừ điểm.
Sub-tab 4: Bản đồ Chất lượng - Treemap và Heatmap không dùng folium.
Sub-tab 5: Xu hướng - Timeline và cảnh báo xu hướng xấu.
"""


from __future__ import annotations

from logger import get_logger
logger = get_logger(__name__)

import re
import socket
from datetime import datetime
from typing import TYPE_CHECKING

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

import db
from auth import la_phan_he_cn, la_phan_he_pgd, normalize_role
from config import (
    DS_PGD,
    CACHE_HSTD,
    COT_TEN_PGD,
    COT_TEN_TO,
    COT_TEN_XA,
    COT_MA_PGD,
    COT_MA_TO,
    COT_HINH_THUC_VAY,
    COT_TONG_DU_NO,
)
from utils import fmt_so, fmt_ty, vn, xuat_excel, ten_file_xuat, hien_thi_dataframe_phan_trang
from state_manager import SCMStateManager
from services.cdtotkvv_service import (
    bang_trang_thai_cdtotkvv as _bang_trang_thai_cdtotkvv,
    loc_df as _loc_df,
    cdtotkvv_ten_sheet_excel as _cdtotkvv_ten_sheet_excel,
    fmt_xuat_to_khong_dat_vn as _fmt_xuat_to_khong_dat_vn,
    thong_ke_tuoi_theo_pgd as _tk_tuoi_pgd,
    thong_ke_tuoi_theo_xa as _tk_tuoi_xa,
    enrich_tuoi_to_truong_fallback_tu_hstd as _enrich_tuoi_hstd,
    _tao_word_thong_ke_tuoi_to_truong as _tao_word_thong_ke_tuoi_to_truong,
)
from services.template_service import (
    nut_tai_word_va_pdf as _nut_tai_wp,
    hien_thi_nut_tai as _hien_thi_nut_tai,
)
from services.tongquan_cdto_service import load_cdto_toan_cn
from data.cdtotkvv import (

    doc_cdtotkvv, ds_thang_nam, tong_hop_theo_pgd, doi_chieu_cdtotkvv_hstd,
    _XEP_LOAI_TOT, _XEP_LOAI_KHA, _XEP_LOAI_TB, _XEP_LOAI_YEU
)

# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

@st.cache_data(show_spinner=False, ttl=300)
def _doi_chieu_hstd_cdto(df_cdto: pd.DataFrame, ts: float = 0.0) -> dict:
    try:
        import pyarrow.parquet as pq

        cols_available = set(pq.read_schema(CACHE_HSTD).names)
        required = {COT_MA_PGD, COT_MA_TO, COT_TONG_DU_NO}
        if not required.issubset(cols_available):
            return {}
        cols = [COT_MA_PGD, COT_MA_TO, COT_TONG_DU_NO]
        for col in (COT_TEN_PGD, COT_TEN_TO, COT_HINH_THUC_VAY):
            if col in cols_available:
                cols.append(col)
        df_hstd = pd.read_parquet(CACHE_HSTD, columns=cols)
    except Exception:
        return {}
    return doi_chieu_cdtotkvv_hstd(df_cdto, df_hstd)


def _cdtotkvv_key_cols(df: pd.DataFrame) -> list[str]:
    if df is None or df.empty or "ma_to" not in df.columns:
        return []
    if "ma_dv" in df.columns:
        return ["ma_dv", "ma_to"]
    if "ten_dv" in df.columns:
        return ["ten_dv", "ma_to"]
    return ["ma_to"]


def _dedupe_cdtotkvv_to(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    key_cols = _cdtotkvv_key_cols(df)
    if not key_cols:
        return df.copy()
    df_u = df.copy()
    for col in key_cols:
        df_u[col] = df_u[col].astype("string").str.strip().replace("", pd.NA)
    return df_u.dropna(subset=key_cols).drop_duplicates(key_cols).copy()


def _tong_to_cdtotkvv_unique(df: pd.DataFrame) -> int:
    return int(len(_dedupe_cdtotkvv_to(df)))


def _count_xep_loai(df: pd.DataFrame, label: str) -> int:
    if df is None or df.empty or "xep_loai" not in df.columns:
        return 0
    return int((df["xep_loai"].astype("string").str.strip() == label).sum())


# Điểm tối đa / nhãn tiêu chí — dùng chung bảng phân tích & xuất Excel Tổ không đạt
_CDTOTKVV_DIEM_TOI_DA: dict[str, int] = {
    "diem_gdtx": 20,
    "diem_thu_no": 15,
    "diem_thu_lai": 20,
    "diem_tv_tiengui": 5,
    "diem_ds_tg": 10,
    "diem_nqh": 30,
}
_CDTOTKVV_TEN_HIEN_THI: dict[str, str] = {
    "diem_gdtx": "Giao dịch tại xã",
    "diem_thu_no": "Thu nợ đến hạn",
    "diem_thu_lai": "Tỷ lệ thu lãi",
    "diem_tv_tiengui": "Tổ viên tham gia tiền gửi",
    "diem_ds_tg": "Số dư tiền gửi tăng thêm",
    "diem_nqh": "Tỷ lệ nợ quá hạn",
}


def _render_xuat_to_khong_dat_tieu_chi(
    df: pd.DataFrame,
    username: str,
    thang_chon: str,
) -> None:
    """
    Xuất danh sách tổ chưa đạt điểm tối đa theo tiêu chí (đúng cột `CDTOTKVV_COLS` / diem_*).
    Lọc PGD: bỏ trống = toàn bộ. Excel qua `xuat_excel`, PDF qua `pdf_service.xuat_pdf_bang` nếu có.
    """
    st.divider()
    st.markdown("**📤 Xuất danh sách Tổ chưa đạt tiêu chí**")

    tieu_chi_co_san = [k for k in _CDTOTKVV_DIEM_TOI_DA if k in df.columns]
    if not tieu_chi_co_san:
        st.caption("Không có cột tiêu chí chấm điểm trong dữ liệu tháng đã chọn.")
        return

    hostname = socket.gethostname()
    col1, col2 = st.columns([3, 2])
    with col1:
        tieu_chi_chon = st.multiselect(
            "Chọn tiêu chí (có thể chọn nhiều)",
            options=tieu_chi_co_san,
            default=[tieu_chi_co_san[0]],
            format_func=lambda x: _CDTOTKVV_TEN_HIEN_THI.get(x, x),
            key="xuat_tc_chon",
        )
    with col2:
        ds_pgd = sorted(df["ten_dv"].dropna().astype(str).unique()) if "ten_dv" in df.columns else []
        pgd_loc = st.multiselect(
            "Lọc PGD (bỏ trống = tất cả)",
            options=ds_pgd,
            default=[],
            key="xuat_tc_pgd",
        )

    if not tieu_chi_chon:
        st.info("Chọn ít nhất 1 tiêu chí để xuất.")
        return

    cot_noi_bo_doi_ten: list[tuple[str, str]] = [
        ("ten_dv", "PGD"),
        ("ten_xa", "Xã"),
        ("ma_to", "Mã Tổ"),
        ("ten_to_truong", "Tổ trưởng"),
        ("tong_diem", "Tổng điểm"),
        ("xep_loai", "Xếp loại"),
        ("du_no", "Dư nợ"),
        ("so_du_tk", "Số dư TK"),
    ]

    try:
        df_loc = (
            df[df["ten_dv"].isin(pgd_loc)].copy()
            if pgd_loc and "ten_dv" in df.columns
            else df.copy()
        )

        sheets: dict[str, pd.DataFrame] = {}
        tong_khong_dat = 0

        for tc in tieu_chi_chon:
            diem_max = _CDTOTKVV_DIEM_TOI_DA[tc]
            ten = _CDTOTKVV_TEN_HIEN_THI[tc]

            diem = pd.to_numeric(df_loc[tc], errors="coerce").fillna(0)
            df_nd = df_loc[diem < diem_max].copy()
            if df_nd.empty:
                continue
            df_nd["_diem"] = diem.loc[df_nd.index]

            cot_trong = [
                c for c, _ in cot_noi_bo_doi_ten
                if c in df_nd.columns and c != tc
            ]
            out = df_nd[cot_trong].rename(
                columns={s: d for s, d in cot_noi_bo_doi_ten if s in cot_trong}
            )
            out.insert(0, "Tiêu chí", ten)
            out.insert(1, "Điểm tối đa", diem_max)
            out.insert(2, "Điểm đạt được", df_nd["_diem"].values)
            out.insert(3, "Thiếu", diem_max - df_nd["_diem"].values)
            out = out.sort_values("Điểm đạt được", ascending=True)

            da_dung = set(sheets.keys())
            sheet_name = _cdtotkvv_ten_sheet_excel(ten, da_dung)
            sheets[sheet_name] = out
            tong_khong_dat += len(out)

        if not sheets:
            st.success("🎉 Tất cả các tổ đều đạt các tiêu chí đã chọn!")
            db.ghi_audit(
                username,
                "export_to_khong_dat_tieu_chi",
                f"[{hostname}] thang={thang_chon} tieu_chi={','.join(tieu_chi_chon)} so_to=0",
            )
            return

        c1, c2, c3, c4 = st.columns(4)
        c1.metric(
            "Tổng tổ không đạt",
            tong_khong_dat,
            help="Gộp theo các tiêu chí đã chọn (một tổ có thể đếm nhiều lần nếu không đạt nhiều tiêu chí)",
        )
        c2.metric("Số tiêu chí có dữ liệu xuất", len(sheets))
        c3.metric(
            "Số PGD",
            df_loc["ten_dv"].nunique() if "ten_dv" in df_loc.columns else "—",
        )
        c4.metric(
            "Tỷ lệ",
            f"{tong_khong_dat / len(df_loc) * 100:.1f}%" if len(df_loc) else "—",
        )

        for ten_sheet, df_s in sheets.items():
            with st.expander(f"{ten_sheet} — {len(df_s)} tổ", expanded=False):
                a, b, c = st.columns(3)
                a.metric("Điểm TB", f"{df_s['Điểm đạt được'].mean():.1f}")
                b.metric("Điểm thấp nhất", f"{df_s['Điểm đạt được'].min():.1f}")
                c.metric("Điểm cao nhất", f"{df_s['Điểm đạt được'].max():.1f}")
                st.dataframe(df_s.head(20), use_container_width=True, height=360)
                if len(df_s) > 20:
                    st.caption(f"Hiển thị 20/{len(df_s)} tổ, tải Excel/PDF để xem đầy đủ.")

        sheets_xuat = {k: _fmt_xuat_to_khong_dat_vn(v) for k, v in sheets.items()}
        excel_bytes = xuat_excel(sheets_xuat)
        slug = tieu_chi_chon[0] if len(tieu_chi_chon) == 1 else f"{len(tieu_chi_chon)}tc"
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")

        col_ex, col_pdf = st.columns(2)
        with col_ex:
            st.download_button(
                label=f"📥 Xuất Excel ({tong_khong_dat} dòng, {len(sheets)} sheet)",
                data=excel_bytes,
                file_name=ten_file_xuat(f"To_khong_dat_{slug}"),
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
                key="xuat_tc_excel",
            )
        with col_pdf:
            try:
                from pdf_service import xuat_pdf

                df_all = pd.concat(sheets.values(), ignore_index=True)
                cols_tien = [c for c in ("Dư nợ", "Số dư TK") if c in df_all.columns]
                pdf_bytes = xuat_pdf(
                    df=df_all,
                    tieu_de=f"Tổ chưa đạt tiêu chí — Tháng {thang_chon}",
                    nguoi_xuat=username,
                    cols_tien=cols_tien,
                    prefix_file="CDTOTKVV",
                )
                st.download_button(
                    label="📄 Xuất PDF",
                    data=pdf_bytes,
                    file_name=f"To_khong_dat_{slug}_{ts}.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                    key="xuat_tc_pdf",
                )
            except Exception as e_pdf:
                logger.error("Lỗi trong khối except: %s", e_pdf, exc_info=True)
                st.button(
                    "📄 Xuất PDF",
                    disabled=True,
                    help=f"Không tạo được PDF: {e_pdf}",
                    use_container_width=True,
                    key="xuat_tc_pdf_na",
                )

        db.ghi_audit(
            username,
            "export_to_khong_dat_tieu_chi",
            f"[{hostname}] thang={thang_chon} tieu_chi={','.join(tieu_chi_chon)} "
            f"so_to={tong_khong_dat} pgd={pgd_loc or 'all'}",
        )

    except Exception as e:
        logger.error("Lỗi trong khối except: %s", e, exc_info=True)
        import traceback


        st.error(f"❌ Lỗi khi xử lý xuất tổ không đạt tiêu chí: {e}")
        with st.expander("Chi tiết lỗi (debug)", expanded=False):
            st.code(traceback.format_exc())
        db.ghi_audit(
            username,
            "loi_he_thong",
            f"[{hostname}] export_to_khong_dat_tieu_chi thang={thang_chon} error={str(e)[:200]}",
        )


def _sub_upload(role: str, username: str) -> None:
    st.markdown("##### Trạng thái Upload CDTOTKVV")
    
    # Banner thông báo
    st.info(
        "📌 **Dữ liệu CDTOTKVV được upload tập trung tại Upload Dữ liệu — Phòng KH-NV. "
        "Tab này chỉ hiển thị trạng thái tổng hợp.**"
    )
    
    st.divider()
    
    # Tạo bảng trạng thái
    df_trang_thai = _bang_trang_thai_cdtotkvv()
    
    # Thống kê tổng hợp
    so_da_co = len([row for _, row in df_trang_thai.iterrows() if "✅" in row["Trạng thái"]])
    so_chua_co = 22 - so_da_co
    
    # Danh sách đơn vị còn thiếu
    dv_chua_co = [
        row["Đơn vị"] 
        for _, row in df_trang_thai.iterrows() 
        if "❌" in row["Trạng thái"]
    ]
    
    # Thông báo tổng hợp
    if so_chua_co == 0:
        st.success(f"**Đã có dữ liệu: {so_da_co} / 22 đơn vị**")
    else:
        st.warning(f"**Đã có dữ liệu: {so_da_co} / 22 đơn vị  |  ⚠️ Chưa tổng hợp: {so_chua_co} đơn vị**")
        if dv_chua_co:
            danh_sach_thieu = ", ".join(dv_chua_co)
            st.caption(f"Còn thiếu: {danh_sach_thieu}")
    
    st.divider()
    
    # Hiển thị bảng trạng thái
    st.markdown("**Bảng trạng thái từng đơn vị:**")
    hien_thi_dataframe_phan_trang(df_trang_thai, key="cdtotkvv_trang_thai_dv")

def _sub_tong_hop(username: str) -> None:
    st.markdown("##### Tổng hợp dữ liệu từ hệ thống tập trung")

    cdto = load_cdto_toan_cn()
    df = cdto["df_raw"]
    kpi = cdto["kpi"]
    thang_hien = cdto["thang_hien"]

    if df is None or df.empty:
        st.info("Chưa có dữ liệu CDTOTKVV nào từ hệ thống tập trung. Hãy kiểm tra tab Upload để xem trạng thái.")
        return

    th = tong_hop_theo_pgd(df)

    if cdto["so_don_vi_thieu"] > 0:
        ten_thieu = ", ".join(cdto["ds_don_vi_thieu"][:5])
        duoi = f" và {cdto['so_don_vi_thieu'] - 5} đơn vị khác" if cdto["so_don_vi_thieu"] > 5 else ""
        st.info(
            f"📊 Dữ liệu từ **{cdto['so_don_vi_co']}/{cdto['tong_don_vi_ky_vong']} đơn vị** · "
            f"Thiếu: **{ten_thieu}{duoi}**"
        )
    if thang_hien:
        st.caption(f"📅 Kỳ: Tháng {thang_hien}")
    st.caption(
        "Nguồn: `pgd_data/*/cdtotkvv_YYYY_MM.xlsx` hoặc `cdtotkvv_latest.xlsx`; "
        "tháng hiển thị lấy theo ngày báo cáo trong file CDTOTKVV."
    )

    if kpi is None:
        st.info("Không tính được KPI từ dữ liệu hiện có.")
        return

    tong_to_dong = int(kpi["tong_to"])
    df_unique_to = _dedupe_cdtotkvv_to(df)
    tong_to = int(len(df_unique_to))
    tong_to_unique_cdto = tong_to
    try:
        import os

        ts_hstd = os.path.getmtime(CACHE_HSTD) if os.path.exists(CACHE_HSTD) else 0.0
    except Exception:
        ts_hstd = 0.0
    doi_chieu = _doi_chieu_hstd_cdto(df_unique_to, ts_hstd) if ts_hstd else {}
    tong_to_hstd = int(doi_chieu.get("tong_hstd", 0) or 0)
    so_to_khop = int(doi_chieu.get("so_khop", 0) or 0)
    tong_tot = _count_xep_loai(df_unique_to, _XEP_LOAI_TOT)
    tong_kha = _count_xep_loai(df_unique_to, _XEP_LOAI_KHA)
    tong_tb = _count_xep_loai(df_unique_to, _XEP_LOAI_TB)
    tong_yeu = _count_xep_loai(df_unique_to, _XEP_LOAI_YEU)
    diem_tb = (
        pd.to_numeric(df_unique_to["tong_diem"], errors="coerce").mean()
        if "tong_diem" in df_unique_to.columns and not df_unique_to.empty
        else kpi["diem_tb"]
    )
    ty_le_dat = ((tong_tot + tong_kha) / tong_to * 100) if tong_to else 0.0
    ty_le_yeu_kem = (tong_yeu / tong_to * 100) if tong_to else 0.0

    c1, c2, c3, c4 = st.columns(4)
    delta_hstd = (
        f"Khớp HSTD: {fmt_so(so_to_khop)}/{fmt_so(tong_to_hstd)}"
        if tong_to_hstd else "HSTD: —"
    )
    c1.metric("Tổng số Tổ (CDTOTKVV)", fmt_so(tong_to_unique_cdto), delta=delta_hstd)
    c2.metric("Điểm TB toàn CN", f"{diem_tb:.2f}")
    c3.metric("% Đạt (Tốt+Khá)", f"{ty_le_dat:.1f}%")
    c4.metric("% Yếu+Kém", f"{ty_le_yeu_kem:.1f}%")
    if tong_to_unique_cdto != tong_to_dong:
        st.caption(
            f"ℹ️ CDTOTKVV: {fmt_so(tong_to_dong)} dòng dữ liệu, "
            f"unique theo (PGD, Mã Tổ) = {fmt_so(tong_to_unique_cdto)}. "
            "Các tỷ lệ xếp loại bên dưới cũng dùng mẫu số unique này."
        )
    df_chi_hstd = doi_chieu.get("chi_hstd", pd.DataFrame())
    df_chi_cdto = doi_chieu.get("chi_cdto", pd.DataFrame())
    df_truc_tiep = doi_chieu.get("cho_vay_truc_tiep", pd.DataFrame())
    if isinstance(df_truc_tiep, pd.DataFrame) and not df_truc_tiep.empty:
        st.info(
            f"ℹ️ HSTD có **{fmt_so(len(df_truc_tiep))} mã cho vay trực tiếp** "
            "(`Hình thức vay = 1`), không thuộc phạm vi chấm điểm Tổ TK&VV."
        )
        hien_tt = df_truc_tiep.copy()
        hien_tt["Ghi chú"] = "Cho vay trực tiếp — không thuộc CDTO"
        hien_tt = hien_tt.rename(columns={
            "ten_dv": "Đơn vị",
            "ma_to_chuan": "Mã",
            "ten_to": "Tên hiển thị trong HSTD",
            "du_no": "Dư nợ (triệu đồng)",
        })
        hien_tt["Dư nợ (triệu đồng)"] = hien_tt["Dư nợ (triệu đồng)"].apply(fmt_ty)
        cols_tt = [
            col for col in (
                "Đơn vị", "Mã", "Tên hiển thị trong HSTD",
                "Dư nợ (triệu đồng)", "Ghi chú",
            ) if col in hien_tt.columns
        ]
        hien_thi_dataframe_phan_trang(
            hien_tt[cols_tt],
            key="cdtotkvv_hstd_cho_vay_truc_tiep",
        )
    if isinstance(df_chi_hstd, pd.DataFrame) and not df_chi_hstd.empty:
        st.warning(
            f"⚠️ HSTD có **{fmt_so(len(df_chi_hstd))} Tổ** còn dư nợ nhưng chưa có trong CDTO kỳ này."
        )
        hien = df_chi_hstd.copy()
        hien = hien.rename(columns={
            "ten_dv": "Đơn vị",
            "ma_to_chuan": "Mã Tổ",
            "ten_to": "Tên Tổ/Tổ trưởng HSTD",
            "du_no": "Dư nợ (triệu đồng)",
        })
        hien["Dư nợ (triệu đồng)"] = hien["Dư nợ (triệu đồng)"].apply(fmt_ty)
        cols_hien = [
            col for col in ("Đơn vị", "Mã Tổ", "Tên Tổ/Tổ trưởng HSTD", "Dư nợ (triệu đồng)")
            if col in hien.columns
        ]
        hien_thi_dataframe_phan_trang(
            hien[cols_hien],
            key="cdtotkvv_hstd_thieu_cham_diem",
        )
    if isinstance(df_chi_cdto, pd.DataFrame) and not df_chi_cdto.empty:
        st.info(
            f"ℹ️ CDTO có **{fmt_so(len(df_chi_cdto))} Tổ** không còn dư nợ tương ứng trong HSTD."
        )

    def _render_xep_loai_card(col, label: str, count: int, bg: str, color: str) -> None:
        pct = (count / tong_to * 100) if tong_to else 0.0
        card_html = f"""
        <div style="background:{bg}; border-left:4px solid {color};
                    border-radius:8px; padding:12px 16px; text-align:center">
          <div style="font-size:11px; color:{color}; font-weight:600">{label}</div>
          <div style="font-size:24px; font-weight:700; color:{color}">{count}</div>
          <div style="font-size:13px; color:{color}">{pct:.1f}%</div>
        </div>
        """
        with col:
            st.markdown(card_html, unsafe_allow_html=True)

    c5, c6, c7, c8 = st.columns(4)
    _render_xep_loai_card(c5, "Tốt (≥90đ)", tong_tot, "#E8F5E9", "#2E7D32")
    _render_xep_loai_card(c6, "Khá (80-89)", tong_kha, "#F1F8E9", "#558B2F")
    _render_xep_loai_card(c7, "TB (70-79)", tong_tb, "#FFF8E1", "#F57F17")
    _render_xep_loai_card(c8, "Yếu (<70)", tong_yeu, "#FFEBEE", "#C62828")

    st.divider()
    fig_pie = go.Figure(go.Pie(
        labels=["Tốt", "Khá", "Trung bình", "Yếu"],
        values=[tong_tot, tong_kha, tong_tb, tong_yeu],
        marker_colors=["#2E7D32", "#66BB6A", "#F9A825", "#C62828"],
        textinfo="label+percent",
        textfont_size=12,
        hole=0.4,
        pull=[0, 0, 0, 0.08],
    ))
    fig_pie.update_layout(
        title="Phân bổ xếp loại Tổ TK&VV toàn Chi nhánh",
        height=320,
        margin=dict(t=40, b=10, l=10, r=10),
        legend=dict(orientation="h", y=-0.1),
        paper_bgcolor="rgba(0,0,0,0)",
    )

    col_pie, col_bang = st.columns([1, 2])
    with col_pie:
        st.plotly_chart(fig_pie, use_container_width=True)
    with col_bang:
        st.markdown("**Bảng tổng hợp theo Phòng giao dịch**")
        hien_thi_dataframe_phan_trang(
            th,
            key="cdtotkvv_tong_hop_pgd",
            column_config={
                "ma_dv":          st.column_config.TextColumn("Mã DV"),
                "ten_dv":         st.column_config.TextColumn("Tên đơn vị"),
                "tong_to":        st.column_config.NumberColumn("Tổng Tổ"),
                "tong_diem_tb":   st.column_config.NumberColumn("Điểm TB", format="%.1f"),
                "to_tot":         st.column_config.NumberColumn("Tốt"),
                "to_kha":         st.column_config.NumberColumn("Khá"),
                "to_tb":          st.column_config.NumberColumn("Trung bình"),
                "to_yeu":         st.column_config.NumberColumn("Yếu"),
                "to_tinh_trang_a": st.column_config.NumberColumn("TT A"),
                "to_tinh_trang_b": st.column_config.NumberColumn("TT B"),
                "to_tinh_trang_c": st.column_config.NumberColumn("TT C"),
            },
        )
    
    # Thông tin số đơn vị đã tổng hợp
    so_don_vi_co_data = len(th)
    st.caption(f"Đã tổng hợp: {so_don_vi_co_data} / 22 đơn vị")

    xlsx_bytes = xuat_excel({"Tong hop": th})
    st.download_button(
        label="⬇️ Xuất Excel",
        data=xlsx_bytes,
        file_name=ten_file_xuat("CDTOTKVV_TH_TapTrung"),
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key="cd_dl_excel",
    )
    db.ghi_audit(username, "xuat_excel_cdtotkvv", "tu_pgd_data")

def _sub_phan_tich_chat_luong(username: str, cdto_mode: str, pgd_user: str) -> None:
    """Sub-tab 3: Phân tích Chất lượng"""
    st.markdown("##### 📋 Phân tích Chất lượng Tổ TK&VV")
    
    ds = ds_thang_nam()
    if not ds:
        st.info("Chưa có file chấm điểm nào. Hãy upload ở tab Upload trước.")
        return

    thang_chon = st.selectbox("Chọn tháng", ds, key="cdto3_thang")
    
    try:
        df_raw = doc_cdtotkvv(thang_chon)
        if df_raw is None or df_raw.empty:
            st.warning(f"Không đọc được dữ liệu tháng {thang_chon}.")
            return
        
        df = _loc_df(df_raw, cdto_mode, pgd_user)
        if df.empty:
            st.warning("Không có dữ liệu cho PGD này.")
            return
            
    except Exception as e:
        logger.error("Lỗi trong khối except: %s", e, exc_info=True)
        st.warning(f"Lỗi đọc dữ liệu: {e}")
        return

    # Section A — 4 KPI cards
    tong_to = len(df)
    to_tot = len(df[df["xep_loai"] == _XEP_LOAI_TOT]) if "xep_loai" in df.columns else 0
    to_yeu = len(df[df["xep_loai"] == _XEP_LOAI_YEU]) if "xep_loai" in df.columns else 0
    diem_tb = df["tong_diem"].mean() if "tong_diem" in df.columns and not df["tong_diem"].isna().all() else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Tổng số Tổ", fmt_so(tong_to))
    c2.metric("% Tốt", f"{to_tot/tong_to*100:.1f}%" if tong_to else "—")
    c3.metric("% Yếu", f"{to_yeu/tong_to*100:.1f}%" if tong_to else "—")
    c4.metric("Điểm TB", f"{diem_tb:.2f}")

    st.divider()

    # Section B — Bảng tiêu chí bị trừ điểm
    st.markdown("**Tiêu chí bị trừ điểm**")

    tieu_chi_data = []
    for col, diem_max in _CDTOTKVV_DIEM_TOI_DA.items():
        if col not in df.columns:
            continue
        series = pd.to_numeric(df[col], errors="coerce").fillna(0)
        diem_tb = series.mean()
        bi_tru = round(diem_max - diem_tb, 2)
        so_to_khong_dat = len(series[series < diem_max])
        ty_le = so_to_khong_dat / tong_to * 100 if tong_to > 0 else 0
        if ty_le >= 50:
            muc_do = "🔴 Nghiêm trọng"
        elif ty_le >= 20:
            muc_do = "🟡 Cần cải thiện"
        else:
            muc_do = "🟢 Tốt"
        tieu_chi_data.append(
            {
                "Tiêu chí": _CDTOTKVV_TEN_HIEN_THI.get(col, col),
                "Điểm tối đa": diem_max,
                "Điểm TB": round(diem_tb, 2),
                "Bị trừ TB": bi_tru,
                "Số Tổ chưa đạt": so_to_khong_dat,
                "% Tổ chưa đạt": round(ty_le, 1),
                "Mức độ": muc_do,
            }
        )

    df_tc = pd.DataFrame(tieu_chi_data)
    df_tc = df_tc.sort_values("Bị trừ TB", ascending=False)

    ser_bi_tru = df_tc["Bị trừ TB"].copy()

    def highlight_rows(row):
        if ser_bi_tru.loc[row.name] > 2:
            return ["background-color: #ffebee; color: #7f1d1d"] * len(row)
        elif ser_bi_tru.loc[row.name] <= 0:
            return [""] * len(row)
        return [""] * len(row)

    df_tc["Điểm TB"] = df_tc["Điểm TB"].map(
        lambda x: f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    )
    df_tc["Bị trừ TB"] = df_tc["Bị trừ TB"].map(
        lambda x: f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    )
    df_tc["% Tổ chưa đạt"] = df_tc["% Tổ chưa đạt"].map(
        lambda x: f"{x:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".") + "%"
    )
    df_tc["Số Tổ chưa đạt"] = df_tc["Số Tổ chưa đạt"].map(
        lambda x: f"{int(x):,}".replace(",", ".")
    )

    if not df_tc.empty:
        hien_thi_dataframe_phan_trang(
            df_tc.style.apply(highlight_rows, axis=1),
            key="cdtotkvv_tieu_chi_tru_diem",
            column_config={
                "Tiêu chí": st.column_config.TextColumn("Tiêu chí"),
                "Điểm tối đa": st.column_config.NumberColumn("Điểm tối đa", format=",.0f"),
            },
        )
    else:
        st.info("Không có dữ liệu tiêu chí.")

    st.divider()

    # Section C — So sánh 2 tháng
    st.markdown("**So sánh 2 tháng**")
    
    thang_so_sanh = st.selectbox(
        "Chọn tháng so sánh",
        [t for t in ds if t != thang_chon],
        key="cdto3_thang2"
    )
    
    if thang_so_sanh:
        try:
            df2_raw = doc_cdtotkvv(thang_so_sanh)
            if df2_raw is not None and not df2_raw.empty:
                df2 = _loc_df(df2_raw, cdto_mode, pgd_user)
                
                # Tính chỉ số tháng 2
                tong_to2 = len(df2)
                to_yeu2 = len(df2[df2["xep_loai"] == _XEP_LOAI_YEU]) if "xep_loai" in df2.columns else 0
                to_tot2 = len(df2[df2["xep_loai"] == _XEP_LOAI_TOT]) if "xep_loai" in df2.columns else 0
                diem_tb2 = df2["tong_diem"].mean() if "tong_diem" in df2.columns and not df2["tong_diem"].isna().all() else 0
                
                # 4 st.metric với delta
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Tổng Tổ", fmt_so(tong_to), delta=f"{tong_to-tong_to2:+d}".replace(",","."))
                m2.metric("Tổ Yếu", fmt_so(to_yeu), delta=f"{to_yeu-to_yeu2:+d}".replace(",","."))
                m3.metric("Tổ Tốt", fmt_so(to_tot), delta=f"{to_tot-to_tot2:+d}".replace(",","."))
                m4.metric("Điểm TB", f"{diem_tb:.2f}", delta=f"{diem_tb - diem_tb2:+.2f}")
                
                # Bar chart nhóm xếp loại
                if "xep_loai" in df.columns and "xep_loai" in df2.columns:
                    # Tạo dữ liệu cho biểu đồ
                    thang1_counts = df["xep_loai"].value_counts()
                    thang2_counts = df2["xep_loai"].value_counts()
                    
                    xep_loai_list = [_XEP_LOAI_TOT, _XEP_LOAI_KHA, _XEP_LOAI_TB, _XEP_LOAI_YEU]
                    
                    chart_data = []
                    for xl in xep_loai_list:
                        chart_data.append({
                            "Xếp loại": xl,
                            "Tháng": thang_chon,
                            "Số lượng": thang1_counts.get(xl, 0)
                        })
                        chart_data.append({
                            "Xếp loại": xl,
                            "Tháng": thang_so_sanh,
                            "Số lượng": thang2_counts.get(xl, 0)
                        })
                    
                    chart_df = pd.DataFrame(chart_data)
                    
                    fig = px.bar(
                        chart_df,
                        x="Xếp loại",
                        y="Số lượng",
                        color="Tháng",
                        barmode="group",
                        title="So sánh xếp loại 2 tháng"
                    )
                    
                    # Update colors for xếp loại categories
                    fig.update_traces(marker_color="#1f77b4")  # Default blue for comparison
                    
                    st.plotly_chart(fig, use_container_width=True)
                
        except Exception as e:
            logger.error("Lỗi trong khối except: %s", e, exc_info=True)
            st.warning(f"Lỗi đọc dữ liệu tháng so sánh: {e}")

    # Xuất tổ không đạt tiêu chí (sau phần so sánh 2 tháng)
    _render_xuat_to_khong_dat_tieu_chi(df, username, thang_chon)


def _sub_ban_do_chat_luong(username: str, cdto_mode: str, pgd_user: str) -> None:
    """Sub-tab 4: Bản đồ Chất lượng"""
    st.markdown("##### 🗺️ Bản đồ Chất lượng Tổ TK&VV")
    
    ds = ds_thang_nam()
    if not ds:
        st.info("Chưa có file chấm điểm nào. Hãy upload ở tab Upload trước.")
        return

    thang_chon = st.selectbox("Chọn tháng", ds, key="cdto4_thang")
    
    try:
        df_raw = doc_cdtotkvv(thang_chon)
        if df_raw is None or df_raw.empty:
            st.warning(f"Không đọc được dữ liệu tháng {thang_chon}.")
            return
        
        df = _loc_df(df_raw, cdto_mode, pgd_user)
        if df.empty:
            st.warning("Không có dữ liệu cho PGD này.")
            return
            
    except Exception as e:
        logger.error("Lỗi trong khối except: %s", e, exc_info=True)
        st.warning(f"Lỗi đọc dữ liệu: {e}")
        return

    # Section A — Treemap PGD → Xã → Tổ
    st.markdown("**Treemap phân cấp**")
    
    if all(col in df.columns for col in ["ten_dv", "ten_xa", "ma_to", "tong_diem", "xep_loai"]):
        # Xác định path theo mode
        if cdto_mode == "pgd":
            path = ["ten_xa", "ma_to"]  # Ẩn cấp PGD
        else:
            path = ["ten_dv", "ten_xa", "ma_to"]
            
        # Chỉ giữ lại các hàng có đầy đủ dữ liệu cho treemap
        df_tree = df.dropna(subset=path + ["tong_diem", "xep_loai"]).copy()
        
        if not df_tree.empty:
            color_map = {
                _XEP_LOAI_TOT: "#2e7d32",
                _XEP_LOAI_KHA: "#66bb6a", 
                _XEP_LOAI_TB: "#f9a825",
                _XEP_LOAI_YEU: "#c62828"
            }
            
            fig_tree = px.treemap(
                df_tree,
                path=path,
                values="tong_diem",
                color="xep_loai",
                color_discrete_map=color_map,
                height=420,
                title="Kích vào ô để drill-down · Đỏ = Tổ Yếu cần chấn chỉnh"
            )
            
            st.plotly_chart(fig_tree, use_container_width=True)
        else:
            st.warning("Không có dữ liệu đầy đủ để vẽ treemap.")
    else:
        st.warning("Thiếu cột cần thiết để vẽ treemap.")

    st.divider()

    # Section B — Heatmap Table
    st.markdown("**Bảng heatmap theo đơn vị**")
    
    if cdto_mode == "pgd":
        # Chỉ hiện 1 PGD → dùng st.metric
        if "xep_loai" in df.columns:
            counts = df["xep_loai"].value_counts()
            tong_to = len(df)
            to_yeu = counts.get(_XEP_LOAI_YEU, 0)
            ty_le_yeu = to_yeu / tong_to * 100 if tong_to > 0 else 0
            
            m1, m2, m3, m4, m5 = st.columns(5)
            m1.metric("Tổng Tổ", fmt_so(tong_to))
            m2.metric("Tốt", fmt_so(counts.get(_XEP_LOAI_TOT, 0)))
            m3.metric("Khá", fmt_so(counts.get(_XEP_LOAI_KHA, 0)))
            m4.metric("Trung bình", fmt_so(counts.get(_XEP_LOAI_TB, 0)))
            m5.metric("Yếu", fmt_so(to_yeu), delta=f"{vn(ty_le_yeu,1)}%")
    else:
        # Hiển thị bảng đầy đủ các PGD
        if "ten_dv" in df.columns and "xep_loai" in df.columns:
            pivot = df.groupby("ten_dv")["xep_loai"].value_counts().unstack(fill_value=0)
            
            # Đảm bảo đủ 4 cột
            for xl in [_XEP_LOAI_TOT, _XEP_LOAI_KHA, _XEP_LOAI_TB, _XEP_LOAI_YEU]:
                if xl not in pivot.columns:
                    pivot[xl] = 0
            
            # Sắp xếp lại cột theo thứ tự
            pivot = pivot[[_XEP_LOAI_TOT, _XEP_LOAI_KHA, _XEP_LOAI_TB, _XEP_LOAI_YEU]]
            
            # Thêm cột tổng và tỷ lệ yếu
            pivot["tong_to"] = pivot.sum(axis=1)
            pivot["ty_le_yeu"] = (pivot[_XEP_LOAI_YEU] / pivot["tong_to"] * 100).round(1).fillna(0)
            
            # Áp dụng styling
            def style_heatmap(df: pd.DataFrame) -> pd.DataFrame.style:
                """Tô màu bảng heatmap thuần CSS, không cần matplotlib."""

                def mau_theo_nguong(val, col):
                    try:
                        v = float(val)
                    except (ValueError, TypeError):
                        return ""

                    # Cột % Yếu: cao = đỏ đậm, thấp = xanh nhạt
                    if col in ("ty_le_yeu", "to_yeu"):
                        if v == 0:
                            return "background-color:#e8f5e9; color:#1b5e20"
                        if v <= 5:
                            return "background-color:#f1f8e9; color:#33691e"
                        if v <= 15:
                            return "background-color:#fff9c4; color:#f57f17"
                        if v <= 25:
                            return "background-color:#ffe0b2; color:#e65100"
                        return "background-color:#ffcdd2; color:#b71c1c; font-weight:600"

                    # Cột % Tốt / số Tốt: cao = xanh đậm
                    if col in ("ty_le_tot", "to_tot"):
                        if v >= 80:
                            return "background-color:#1b5e20; color:#fff"
                        if v >= 60:
                            return "background-color:#388e3c; color:#fff"
                        if v >= 40:
                            return "background-color:#81c784; color:#1b5e20"
                        if v >= 20:
                            return "background-color:#c8e6c9; color:#1b5e20"
                        return ""

                    # Cột điểm TB: gradient xanh->vàng->đỏ
                    if col == "tong_diem_tb":
                        if v >= 90:
                            return "background-color:#e8f5e9; color:#1b5e20"
                        if v >= 80:
                            return "background-color:#f1f8e9; color:#33691e"
                        if v >= 70:
                            return "background-color:#fff9c4; color:#f57f17"
                        return "background-color:#ffcdd2; color:#b71c1c"

                    return ""

                def style_row(row):
                    return [mau_theo_nguong(row[c], c)
                            if c in row.index else ""
                            for c in row.index]

                return df.style.apply(style_row, axis=1)
            
            hien_thi_dataframe_phan_trang(
                style_heatmap(pivot),
                key="cdtotkvv_heatmap_pivot",
                hide_index=False,
            )

    st.divider()

    # Section C — Top Tổ Yếu
    st.markdown("**Top Tổ Yếu cần chấn chỉnh**")
    
    if "xep_loai" in df.columns:
        df_yeu = df[df["xep_loai"] == _XEP_LOAI_YEU].copy()
        
        if not df_yeu.empty:
            # Sắp xếp theo điểm tăng dần (yếu nhất trước)
            if "tong_diem" in df_yeu.columns:
                df_yeu = df_yeu.sort_values("tong_diem")
            
            # Thêm cột liên tiếp yếu
            df_yeu["Liên tiếp Yếu"] = "🟡 Tháng này"
            
            # Kiểm tra tháng liền trước
            ds_sorted = sorted(ds_thang_nam())
            try:
                idx_current = ds_sorted.index(thang_chon)
                if idx_current > 0:
                    thang_truoc = ds_sorted[idx_current - 1]
                    df_truoc = doc_cdtotkvv(thang_truoc)
                    if df_truoc is not None:
                        df_truoc_loc = _loc_df(df_truoc, cdto_mode, pgd_user)
                        ma_to_yeu_truoc = set(df_truoc_loc[df_truoc_loc["xep_loai"] == _XEP_LOAI_YEU]["ma_to"].astype(str))
                        
                        # Cập nhật cột liên tiếp yếu
                        for idx in df_yeu.index:
                            ma_to = str(df_yeu.loc[idx, "ma_to"])
                            if ma_to in ma_to_yeu_truoc:
                                df_yeu.loc[idx, "Liên tiếp Yếu"] = "🔴 2+ tháng"
            except Exception as e:
                logger.error("kiem_tra_lien_tiep_yeu: %s", e, exc_info=True)
            
            # Hiển thị bảng
            cols_hien = []
            col_mapping = {
                "ten_dv": "PGD",
                "ten_xa": "Xã", 
                "ma_to": "Mã Tổ",
                "tinh_trang": "Tình trạng",
                "tong_diem": "Điểm",
                "Liên tiếp Yếu": "Liên tiếp Yếu"
            }
            
            for col, label in col_mapping.items():
                if col in df_yeu.columns:
                    cols_hien.append(col)
            
            df_display = df_yeu[cols_hien].copy()
            df_display.index = range(1, len(df_display) + 1)  # STT từ 1
            
            # Đổi tên cột
            rename_dict = {col: col_mapping.get(col, col) for col in df_display.columns}
            df_display = df_display.rename(columns=rename_dict)
            
            hien_thi_dataframe_phan_trang(
                df_display,
                key="cdtotkvv_top_to_yeu",
                hide_index=True,
            )
            
            # Nút xuất Excel
            col_xuat, _ = st.columns([1, 2])
            with col_xuat:
                if st.button("⬇️ Xuất Excel Top Tổ Yếu", key="cdto4_xuat_yeu"):
                    try:
                        state = SCMStateManager()
                        state.downloads.set(
                            "cdtotkvv_to_yeu_excel",
                            xuat_excel({"To_Yeu": df_yeu}),
                            ten_file_xuat(f"ToYeu_{thang_chon}"),
                        )
                        db.ghi_audit(username, "xuat_excel_to_yeu", f"thang={thang_chon}")
                        st.cache_data.clear()
                        st.success("✅ Đã tạo file Excel!")
                    except Exception as e:
                        logger.error("Lỗi trong khối except: %s", e, exc_info=True)
                        st.error(f"Lỗi xuất Excel: {e}")

                state = SCMStateManager()
                if state.downloads.has("cdtotkvv_to_yeu_excel"):
                    if st.download_button(
                        label="📥 Tải file Excel",
                        data=state.downloads.get_bytes("cdtotkvv_to_yeu_excel"),
                        file_name=state.downloads.get_filename("cdtotkvv_to_yeu_excel") or ten_file_xuat(f"ToYeu_{thang_chon}"),
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key="cdto4_download_yeu"
                    ):
                        state.downloads.clear("cdtotkvv_to_yeu_excel")
        else:
            st.success("✅ Không có Tổ nào xếp loại Yếu!")
    else:
        st.warning("Không tìm thấy cột xếp loại.")

def _sub_xu_huong(username: str, cdto_mode: str, pgd_user: str) -> None:
    """Sub-tab 5: Xu hướng"""
    st.markdown("##### 📈 Xu hướng Chất lượng Tổ TK&VV")
    
    # Load tất cả tháng
    ds_thang = sorted(ds_thang_nam())  # Sort tăng dần để vẽ timeline
    if not ds_thang:
        st.info("Chưa có file chấm điểm nào. Hãy upload ở tab Upload trước.")
        return
    
    records = []
    for thang in ds_thang:
        try:
            df_t = doc_cdtotkvv(thang)
            if df_t is None or df_t.empty:
                continue
                
            df_t_loc = _loc_df(df_t, cdto_mode, pgd_user)
            if df_t_loc.empty:
                continue
                
            # Tính tổng hợp
            th = tong_hop_theo_pgd(df_t_loc)
            if th.empty:
                continue
                
            # Tổng hợp toàn bộ
            tong_to = th["tong_to"].sum()
            to_tot = th["to_tot"].sum() 
            to_kha = th["to_kha"].sum()
            to_tb = th["to_tb"].sum()
            to_yeu = th["to_yeu"].sum()
            diem_tb = th["tong_diem_tb"].mean()
            
            records.append({
                "thang": thang,
                "tong_to": tong_to,
                "to_tot": to_tot,
                "to_kha": to_kha, 
                "to_tb": to_tb,
                "to_yeu": to_yeu,
                "diem_tb": diem_tb
            })
        except Exception as e:
            logger.error("Lỗi trong khối except: %s", e, exc_info=True)
            st.warning(f"Lỗi xử lý tháng {thang}: {e}")
            continue
    
    if not records:
        st.warning("Không có dữ liệu xu hướng.")
        return
        
    df_trend = pd.DataFrame(records)

    # Section A — Line chart xếp loại theo tháng
    st.markdown("**Xu hướng xếp loại theo tháng**")
    
    fig_line = go.Figure()
    
    # 4 đường xếp loại
    colors = {
        "to_tot": "#2e7d32",
        "to_kha": "#66bb6a",
        "to_tb": "#f9a825", 
        "to_yeu": "#c62828"
    }
    
    labels = {
        "to_tot": "Tốt",
        "to_kha": "Khá", 
        "to_tb": "Trung bình",
        "to_yeu": "Yếu"
    }
    
    for col, color in colors.items():
        fig_line.add_trace(go.Scatter(
            x=df_trend["thang"],
            y=df_trend[col], 
            mode="lines+markers",
            name=labels[col],
            line=dict(color=color, width=3),
            marker=dict(size=8)
        ))
    
    # Annotation tại điểm cao nhất đường Yếu
    max_yeu_idx = df_trend["to_yeu"].idxmax()
    max_yeu = df_trend.loc[max_yeu_idx, "to_yeu"]
    max_yeu_thang = df_trend.loc[max_yeu_idx, "thang"]
    
    fig_line.add_annotation(
        x=max_yeu_thang,
        y=max_yeu,
        text=f"Max: {max_yeu}",
        showarrow=True,
        arrowhead=2,
        arrowcolor="#c62828",
        bgcolor="#ffebee",
        bordercolor="#c62828"
    )
    
    fig_line.update_layout(
        height=400,
        xaxis_title="Tháng",
        yaxis_title="Số Tổ", 
        legend=dict(orientation="h", y=1.02),
        hovermode="x unified"
    )
    
    st.plotly_chart(fig_line, use_container_width=True)

    st.divider()

    # Section B — Điểm TB từng PGD qua tháng (chỉ hiện nếu mode == "cn")
    if cdto_mode == "cn":
        st.markdown("**Điểm trung bình từng PGD qua tháng**")
        
        # Tính dữ liệu PGD theo tháng
        pgd_records = []
        for thang in ds_thang:
            try:
                df_t = doc_cdtotkvv(thang)
                if df_t is None or df_t.empty:
                    continue
                    
                th_pgd = tong_hop_theo_pgd(df_t)
                for _, row in th_pgd.iterrows():
                    pgd_records.append({
                        "thang": thang,
                        "pgd": row["ten_dv"],
                        "diem_tb": row["tong_diem_tb"]
                    })
            except Exception as e:
                logger.error("xu_huong_pgd_thang: %s", e, exc_info=True)
                continue

        if pgd_records:
            df_pgd_trend = pd.DataFrame(pgd_records)
            
            # Lấy 5 PGD có điểm TB thấp nhất tháng gần nhất làm mặc định
            thang_gan_nhat = ds_thang[-1]
            df_gan_nhat = df_pgd_trend[df_pgd_trend["thang"] == thang_gan_nhat]
            top5_pgd = df_gan_nhat.nsmallest(5, "diem_tb")["pgd"].tolist()
            
            ds_pgd_all = sorted(df_pgd_trend["pgd"].unique())
            chon_pgd = st.multiselect(
                "Chọn PGD để hiển thị xu hướng",
                ds_pgd_all,
                default=top5_pgd,
                key="cdto5_pgd_select"
            )
            
            if chon_pgd:
                df_pgd_filtered = df_pgd_trend[df_pgd_trend["pgd"].isin(chon_pgd)]
                
                fig_pgd = px.line(
                    df_pgd_filtered,
                    x="thang",
                    y="diem_tb",
                    color="pgd",
                    markers=True,
                    title="Điểm trung bình theo PGD"
                )
                
                fig_pgd.update_layout(height=400)
                st.plotly_chart(fig_pgd, use_container_width=True)

        st.divider()

    # Section C — Cảnh báo xu hướng xấu
    st.markdown("**Cảnh báo xu hướng xấu**")
    
    if len(df_trend) >= 3:  # Cần ít nhất 3 tháng để phát hiện xu hướng
        # Lấy 3 tháng gần nhất
        df_recent = df_trend.tail(3).reset_index(drop=True)
        
        canh_bao = []
        
        if cdto_mode == "cn":
            # Cảnh báo cho từng PGD
            if 'pgd_records' in locals() and pgd_records:
                df_pgd_recent = df_pgd_trend[df_pgd_trend["thang"].isin(df_recent["thang"].tolist())]
                
                for pgd in df_pgd_recent["pgd"].unique():
                    pgd_data = df_pgd_recent[df_pgd_recent["pgd"] == pgd].sort_values("thang")
                    if len(pgd_data) >= 2:
                        # Kiểm tra điểm giảm 2 tháng liên tiếp
                        diem_values = pgd_data["diem_tb"].tolist()
                        if len(diem_values) >= 2 and diem_values[-1] < diem_values[-2]:
                            if len(diem_values) >= 3 and diem_values[-2] < diem_values[-3]:
                                canh_bao.append(f"🔴 {pgd}: điểm giảm liên tiếp")
                
                # Kiểm tra Tổ Yếu tăng từ dữ liệu tháng
                for pgd in df_pgd_trend["pgd"].unique():
                    pgd_yeu_counts = []
                    for thang in df_recent["thang"].tolist():
                        try:
                            df_t = doc_cdtotkvv(thang)
                            if df_t is not None:
                                pgd_data = df_t[df_t["ten_dv"] == pgd]
                                yeu_count = len(pgd_data[pgd_data["xep_loai"] == _XEP_LOAI_YEU])
                                pgd_yeu_counts.append(yeu_count)
                        except Exception as e:
                            logger.error("canh_bao_to_yeu: %s", e, exc_info=True)
                            continue

                    if len(pgd_yeu_counts) >= 2:
                        if pgd_yeu_counts[-1] > pgd_yeu_counts[-2]:
                            if len(pgd_yeu_counts) >= 3 and pgd_yeu_counts[-2] > pgd_yeu_counts[-3]:
                                canh_bao.append(f"⚠️ {pgd}: Tổ Yếu tăng liên tiếp")
        else:
            # Cảnh báo chỉ cho PGD hiện tại
            if len(df_recent) >= 2:
                if df_recent.loc[2, "diem_tb"] < df_recent.loc[1, "diem_tb"] < df_recent.loc[0, "diem_tb"]:
                    canh_bao.append(f"🔴 {pgd_user}: điểm giảm liên tiếp")
                
                if df_recent.loc[2, "to_yeu"] > df_recent.loc[1, "to_yeu"] > df_recent.loc[0, "to_yeu"]:
                    canh_bao.append(f"⚠️ {pgd_user}: Tổ Yếu tăng liên tiếp")
        
        if canh_bao:
            for cb in canh_bao:
                if cb.startswith("🔴"):
                    st.warning(cb)
                else:
                    st.error(cb)
        else:
            st.success("✅ Không có xu hướng xấu nào được phát hiện.")
    else:
        st.info("Cần ít nhất 3 tháng dữ liệu để phát hiện xu hướng.")


def _render_danh_sach_co_khong_vay_von(
    df_raw: "pd.DataFrame | None",
    key_prefix: str = "cdto_cn_",
) -> None:
    """
    Chia danh sách Tổ trưởng TK&VV làm 2 phần tách bạch:
      Nhóm 1 — Tổ trưởng CÓ hồ sơ vay vốn tại VBSP (Method C trùng tên HSTD → ngày sinh thật).
      Nhóm 2 — Tổ trưởng CHƯA CÓ hồ sơ vay vốn hoặc tên tổ trưởng không trùng với KH trong HSTD (Method 3 ước tính TB xã).
    """
    st.markdown("##### 📂 Danh sách Tổ trưởng — Chia thành 2 nhóm CÓ / KHÔNG vay vốn")
    st.caption(
        "🔎 Phân loại dựa trên: Tên tổ trưởng có trùng khớp với Tên Khách hàng (Cột Tên KH) trong HSTD của "
        "Chi nhánh Đồng Nai hiện có hay không. Nếu trùng thì đánh dấu 'CÓ hồ sơ vay vốn', "
        "nếu không thì rơi vào nhóm 'Chưa có / Không xác định' (không tìm thấy hợp đồng vay vốn nào dưới tên tổ trưởng)."
    )
    if df_raw is None or df_raw.empty:
        st.warning("⚠️ Chưa có dữ liệu CDTOTKVV. Vui lòng upload dữ liệu trước.")
        return

    # Xác định cột chuẩn Tên tổ trưởng / PGD / Xã
    _tt_col = next(
        (c for c in ("Tên tổ trưởng", "ten_to_truong", "Tổ trưởng", "Họ tên tổ trưởng") if c in df_raw.columns),
        None,
    )
    _pgd_col = next((c for c in ("PGD", "ten_pgd_std") if c in df_raw.columns), None)
    _xa_col = next((c for c in ("Xã/Phường", "ten_xa_std", "Xã") if c in df_raw.columns), None)
    if not _tt_col:
        st.error("❌ Dữ liệu CDTO thiếu cột Tên tổ trưởng — không thể phân loại CÓ / KHÔNG vay vốn.")
        return

    # Đọc flag _co_vay_von & _nguon_chi_tiet từ enrich helper (services/cdtotkvv_service.py)
    _cv_raw = df_raw.get("_co_vay_von", pd.Series(pd.NA, index=df_raw.index, dtype="Int64"))
    if isinstance(_cv_raw, pd.Series) and len(_cv_raw) == len(df_raw):
        _cv = _cv_raw.copy()
    else:
        _cv = pd.Series(pd.NA, index=df_raw.index, dtype="Int64")
    # Tuổi số
    _tuoi_num = pd.to_numeric(df_raw.get("tuoi_to_truong"), errors="coerce") if "tuoi_to_truong" in df_raw.columns else pd.Series(pd.NA, index=df_raw.index)
    # Nguồn chi tiết
    _ng_ct_col = "_nguon_chi_tiet"
    _ng_ct = df_raw.get(_ng_ct_col, pd.Series("", index=df_raw.index, dtype="string"))
    if isinstance(_ng_ct, pd.Series) and len(_ng_ct) == len(df_raw):
        _ng_ct = _ng_ct.astype("string").fillna("")
    else:
        _ng_ct = pd.Series("", index=df_raw.index, dtype="string")

    # --- Tính KPI 2 nhóm ---
    _n_total = len(df_raw)
    _cv_num = pd.to_numeric(_cv, errors="coerce")
    _upload_mask = _cv_num.isna() & _ng_ct.str.contains("Upload thật", case=False, na=False)
    _mask_co = _cv_num.eq(1).fillna(False)
    _mask_na = _upload_mask.fillna(False)
    _mask_khong = (_cv_num.eq(0).fillna(False) | (_cv_num.isna() & ~_mask_na)).fillna(False)

    _so_co = int(_mask_co.sum())
    _so_khong = int(_mask_khong.sum())
    _so_na = int(_mask_na.sum())
    _pct_co = float(_so_co / _n_total * 100.0) if _n_total > 0 else 0.0
    _pct_khong = float(_so_khong / _n_total * 100.0) if _n_total > 0 else 0.0
    _pct_na = float(_so_na / _n_total * 100.0) if _n_total > 0 else 0.0

    # Helper KPI row tóm tắt tuổi
    def _kpi_tuoi(_mask: "pd.Series") -> dict:
        _v = _tuoi_num[_mask].dropna()
        return {
            "n": int(len(_v)),
            "tb": round(float(_v.mean()), 1) if len(_v) else None,
            "med": float(_v.median()) if len(_v) else None,
            "min": int(_v.min()) if len(_v) else None,
            "max": int(_v.max()) if len(_v) else None,
            "ge70": int((_v >= 70).sum()) if len(_v) else 0,
            "ge60": int((_v >= 60).sum()) if len(_v) else 0,
        }

    _k_co = _kpi_tuoi(_mask_co)
    _k_khong = _kpi_tuoi(_mask_khong)
    _k_na = _kpi_tuoi(_mask_na)

    # --- Hiển thị 3 KPI row tổng quan 2 nhóm ---
    _kpi_cols = st.columns(3, gap="medium")
    with _kpi_cols[0]:
        st.metric(
            label=f"💳 Nhóm 1: CÓ hồ sơ vay vốn",
            value=f"{_so_co:,} tổ",
            delta=f"{_pct_co:.1f}% tổng",
            delta_color="normal",
        )
        st.caption(
            f"Tuổi TB: **{_k_co['tb'] if _k_co['tb'] is not None else '—'}** · "
            f"Median: **{int(_k_co['med']) if _k_co['med'] is not None else '—'}** · "
            f"{_k_co['min'] if _k_co['min'] is not None else '—'} → "
            f"{_k_co['max'] if _k_co['max'] is not None else '—'} tuổi · "
            f"≥60: **{_k_co['ge60']:,}** · ≥70: **{_k_co['ge70']:,}** tổ."
        )
        st.caption(
            "✅ Độ tin cậy CAO: Tên tổ trưởng trùng với KH trong HSTD → Ngày sinh thật từ Hồ sơ gốc KH, "
            "đã xác định được hợp đồng vay vốn tại VBSP."
        )
    with _kpi_cols[1]:
        st.metric(
            label=f"⚠️ Nhóm 2: CHƯA CÓ / KHÔNG xác định vay vốn",
            value=f"{_so_khong:,} tổ",
            delta=f"{_pct_khong:.1f}% tổng",
            delta_color="off",
        )
        st.caption(
            f"Tuổi TB ƯỚC TÍNH: **{_k_khong['tb'] if _k_khong['tb'] is not None else '—'}** · "
            f"Median ước tính: **{int(_k_khong['med']) if _k_khong['med'] is not None else '—'}** · "
            f"{_k_khong['min'] if _k_khong['min'] is not None else '—'} → "
            f"{_k_khong['max'] if _k_khong['max'] is not None else '—'} tuổi · "
            f"≥60 ước tính: **{_k_khong['ge60']:,}** · ≥70 ước tính: **{_k_khong['ge70']:,}** tổ."
        )
        st.caption(
            "⚠️ Độ tin cậy THẤP: Không tìm thấy hợp đồng vay vốn nào dưới tên tổ trưởng trong HSTD tháng 07/2026 "
            "(tổ trưởng có thể KHÔNG vay vốn, hợp đồng đã đóng nợ, tên viết sai chính tả / thiếu họ / viết tắt, "
            "hoặc vay vốn ở thời điểm khác)."
        )
    with _kpi_cols[2]:
        _label = "📤 Upload thật (chưa kiểm tra)" if _so_na > 0 else "📤 Không có upload thật phân loại"
        st.metric(
            label=_label,
            value=f"{_so_na:,} tổ",
            delta=f"{_pct_na:.1f}% tổng",
            delta_color="inverse" if _so_na > 0 else "off",
        )
        st.caption(
            f"Tuổi TB: **{_k_na['tb'] if _k_na['tb'] is not None else '—'}** · "
            f"Median: **{int(_k_na['med']) if _k_na['med'] is not None else '—'}** · "
            f"{_k_na['min'] if _k_na['min'] is not None else '—'} → "
            f"{_k_na['max'] if _k_na['max'] is not None else '—'} tuổi · "
            f"≥60: **{_k_na['ge60']:,}** · ≥70: **{_k_na['ge70']:,}** tổ."
        )
        st.caption(
            "📑 Độ tin cậy TUYỆT ĐỐI nếu PGD nhập thủ công Ngày sinh tổ trưởng vào file Excel upload (≥30% tổ có tuổi). "
            "Hệ thống KHÔNG kiểm tra tự động vay vốn hay không — PGD đối chiếu thủ công nếu cần."
        )

    # Helper render 1 danh sách dataframe cho 1 nhóm
    def _render_list(
        _mask: "pd.Series",
        title_exp: str,
        expanded_default: bool,
        _kpi: dict,
        _tag_note: str,
        _exp_key: str,
    ) -> None:
        with st.expander(title_exp, expanded=expanded_default):
            _so_n = int(_mask.sum())
            if _so_n == 0:
                st.info("Không có tổ nào rơi vào nhóm này.")
                return
            # Lọc cột hiển thị đẹp (chỉ giữ cột hữu ích người dùng)
            _cols_show = []
            if _pgd_col:
                _cols_show.append(_pgd_col)
            if _xa_col:
                _cols_show.append(_xa_col)
            _cols_show.append(_tt_col)
            if "tuoi_to_truong" in df_raw.columns:
                _cols_show.append("tuoi_to_truong")
            _cols_show.append(_ng_ct_col if _ng_ct_col in df_raw.columns else None)
            _cols_show = [c for c in _cols_show if c]
            _df_sub = df_raw.loc[_mask, _cols_show].copy()
            # Rename column header tiếng Việt đẹp
            _rename_map = {}
            if _pgd_col:
                _rename_map[_pgd_col] = "PGD"
            if _xa_col:
                _rename_map[_xa_col] = "Xã / Phường"
            _rename_map[_tt_col] = "Họ tên Tổ trưởng"
            if "tuoi_to_truong" in _df_sub.columns:
                _rename_map["tuoi_to_truong"] = "Tuổi tổ trưởng"
            if _ng_ct_col in _df_sub.columns:
                _rename_map[_ng_ct_col] = "Nguồn dữ liệu / Phân loại"
            _df_sub = _df_sub.rename(columns=_rename_map)
            # Sort theo PGD → Xã → Tên tổ
            _sort_by = [c for c in ("PGD", "Xã / Phường", "Họ tên Tổ trưởng") if c in _df_sub.columns]
            if _sort_by:
                _df_sub = _df_sub.sort_values(_sort_by, ascending=True, kind="mergesort").reset_index(drop=True)
            # KPI row đầu expander
            st.caption(
                f"{_tag_note} · {_so_n:,} tổ · "
                f"Tuổi TB: **{_kpi['tb'] if _kpi['tb'] is not None else '—'}** · "
                f"Median: **{int(_kpi['med']) if _kpi['med'] is not None else '—'}** · "
                f"Min: **{_kpi['min'] if _kpi['min'] is not None else '—'}** · Max: **{_kpi['max'] if _kpi['max'] is not None else '—'}** tuổi · "
                f"≥60 tuổi: **{_kpi['ge60']:,}** · ≥70 tuổi: **{_kpi['ge70']:,}**."
            )
            # Hiển thị bảng phân trang với st.dataframe
            st.dataframe(
                _df_sub,
                width="stretch",
                hide_index=True,
                column_config={
                    "Tuổi tổ trưởng": st.column_config.NumberColumn(
                        "Tuổi tổ trưởng",
                        format="%d",
                        step=1,
                    ),
                },
                height=500 if _so_n >= 100 else None,
                key=f"{key_prefix}{_exp_key}_tbl",
            )

    st.divider()
    _render_list(
        _mask=_mask_co,
        title_exp=f"✅ Nhóm 1 — Tổ trưởng CÓ hồ sơ vay vốn tại VBSP ({_so_co:,} tổ = {_pct_co:.1f}%)",
        expanded_default=True,
        _kpi=_k_co,
        _tag_note="✅ Xác minh từ HSTD — Tên tổ trùng tên KH → ngày sinh thật",
        _exp_key="nhom_co_vay",
    )
    _render_list(
        _mask=_mask_khong,
        title_exp=f"⚠️ Nhóm 2 — Tổ trưởng CHƯA CÓ / KHÔNG tìm thấy hồ sơ vay vốn ({_so_khong:,} tổ = {_pct_khong:.1f}%)",
        expanded_default=False,
        _kpi=_k_khong,
        _tag_note="⚠️ Tuổi được ước tính bằng Trung bình Xã + 8 năm — chưa xác minh ngày sinh thật",
        _exp_key="nhom_khong_vay",
    )
    if _so_na > 0:
        _render_list(
            _mask=_mask_na,
            title_exp=f"📤 Nhóm 3 — Upload thật (chưa kiểm tra vay vốn) ({_so_na:,} tổ = {_pct_na:.1f}%)",
            expanded_default=False,
            _kpi=_k_na,
            _tag_note="📤 Tuổi nhập thủ công từ Excel CDTO — PGD tự kiểm tra có vay vốn hay không",
            _exp_key="nhom_upload_thuc",
        )
    st.divider()
    st.caption(
        "💡 **Hướng dẫn bổ sung cho nhóm 2 (Chưa có / Không xác định):**\n"
        " 1. Mở file Excel `cdtotkvv_latest.xlsx` của PGD\n"
        " 2. Sau cột G (Tên tổ trưởng) → thêm cột H: `Ngày sinh tổ trưởng` (dd/mm/yyyy) hoặc cột I: `Tuổi tổ trưởng` (số nguyên)\n"
        " 3. Hoặc nhập chính xác Họ tên tổ trưởng (đầy đủ họ + chữ lót + tên, không viết tắt) → tỷ lệ trùng HSTD sẽ tăng lên 80-85% nhóm 1."
    )
    return


def _sub_thong_ke_tuoi_to_truong(
    username: str,
    cdto_mode: str,
    pgd_user: str,
    df_cdto: "pd.DataFrame | None" = None,
) -> None:
    """
    Sub-tab: 👥 Thống kê Tuổi Tổ trưởng theo (a) PGD và (b) Xã/phường.
    Hiển thị 6 bins nhóm tuổi: <30 / 30-39 / 40-49 / 50-59 / 60-69 / ≥70 tuổi,
    kèm summary tổng (Số tổ có dữ liệu / TB tuổi / Min / Max / Median).
    """
    st.markdown("### 👥 Thống kê Tuổi Tổ trưởng TK&VV")
    st.caption(
        "Phân bổ số lượng Tổ trưởng theo nhóm tuổi (dữ liệu đọc từ file Chấm điểm Tổ "
        "TK&VV: cột Ngày sinh / Tuổi tổ trưởng; nếu chỉ có ngày sinh thì hệ thống tự "
        "tính tuổi. Nếu thiếu cột này → số liệu sẽ hiển thị 0 & hướng dẫn bổ sung)."
    )
    st.divider()

    # 1) Lấy dữ liệu CDTO + Fallback enrich tuổi từ HSTD nếu thiếu
    _nguon_dl_msg = "Không có dữ liệu"
    _so_fill_hstd = 0
    if df_cdto is None:
        _cdto = load_cdto_toan_cn()
        df_raw = _cdto.get("df_raw") if isinstance(_cdto, dict) else None
    else:
        df_raw = df_cdto.copy() if df_cdto is not None else None
    if df_raw is not None and not df_raw.empty:
        df_raw = _loc_df(df_raw, cdto_mode, pgd_user or "")
    if df_raw is not None and not df_raw.empty:
        df_raw, _nguon_dl_msg, _so_fill_hstd = _enrich_tuoi_hstd(df_raw)

    # 2) Xác định chế độ hiển thị
    if cdto_mode == "cn" and la_phan_he_cn(normalize_role(
        st.session_state.get("role", "") if "role" in st.session_state else ""
    )):
        _labels_view = ["Theo Phòng Giao dịch (PGD)", "Theo Xã / Phường", "📂 Danh sách: Tổ CÓ / KHÔNG vay vốn"]
    else:
        _labels_view = ["Theo Xã / Phường (PGD hiện tại)", "📂 Danh sách: Tổ CÓ / KHÔNG vay vốn"]
    _view_key_prefix = f"cdto_{cdto_mode}_{(pgd_user or 'cn').replace(' ', '_')}_"
    _view_sel = st.radio(
        "Chế độ xem",
        range(len(_labels_view)),
        format_func=lambda i: _labels_view[i],
        horizontal=True,
        key=f"{_view_key_prefix}tuoi_view_mode",
        label_visibility="collapsed",
    )
    st.divider()

    # Hiển thị nguồn dữ liệu đang dùng + cảnh báo nếu fallback HSTD
    st.caption(f"📊 Nguồn dữ liệu: {_nguon_dl_msg}")
    st.caption(
        "ℹ️ Thống kê theo PGD / Xã **CHỈ LẤY các Tổ trưởng CÓ dữ liệu thật**: "
        "(1) Tổ trưởng được PGD nhập thủ công Tuổi/Ngày sinh trong file Excel upload thật; "
        "HOẶC (2) Tên tổ trùng khớp với KH CÓ HỒ SƠ VAY VỐN tại VBSP (xác minh từ HSTD). "
        "Tổ không có dữ liệu (không vay vốn / tên không trùng / ước tính TB xã) sẽ được đánh dấu "
        "🔴 \"Chưa có dữ liệu\" — **KHÔNG** dùng số liệu ƯỚC TÍNH cho thống kê PGD/Xã."
    )

    # ------ VIEW MỚI: "📂 Danh sách 2 nhóm Tổ CÓ / KHÔNG vay vốn" ------
    # (mode mới cuối, index cuối luôn)
    _danh_sach_view_index = len(_labels_view) - 1
    if int(_view_sel) == _danh_sach_view_index:
        _render_danh_sach_co_khong_vay_von(df_raw, key_prefix=_view_key_prefix)
        return

    # Thông báo nếu có tổ trưởng ≥70 tuổi (xác định từ ngày sinh HSTD HOẶC upload thật)
    _so_ge60 = 0
    _so_ge70 = 0
    _top_nguoi_gia = None
    if df_raw is not None and not df_raw.empty and "tuoi_to_truong" in df_raw.columns:
        # Filter CHỈ các tổ có vay vốn hoặc upload thật (giống _df_chi_tiet_so_huu_tuoi logic) — để st.info không báo cáo số ước tính
        _cv_raw2 = df_raw.get("_co_vay_von")
        if isinstance(_cv_raw2, pd.Series) and len(_cv_raw2) == len(df_raw):
            _cv2 = _cv_raw2.copy()
        else:
            _cv2 = pd.Series(pd.NA, index=df_raw.index, dtype="Int64")
        _nc_raw2 = df_raw.get("_nguon_chi_tiet")
        if isinstance(_nc_raw2, pd.Series) and len(_nc_raw2) == len(df_raw):
            _nc2 = _nc_raw2.astype("string").fillna("")
        else:
            _nc2 = pd.Series("", index=df_raw.index, dtype="string")
        _mask_covay_info = (_cv2 == 1) | _nc2.str.contains("Upload thật", na=False, case=False)
        # Nếu _co_vay_von chưa có giá trị nào hết (chưa enrich) → dùng hết (backward compat)
        if not _cv2.notna().any() and not _nc2.str.contains("Upload thật", na=False, case=False).any():
            _mask_covay_info = pd.Series(True, index=df_raw.index)
        _t_num = pd.to_numeric(df_raw["tuoi_to_truong"], errors="coerce")
        _t_num_filtered = _t_num.where(_mask_covay_info, pd.NA)
        _t_val = _t_num_filtered[_t_num_filtered.notna() & _t_num_filtered.between(18, 100)]
        _so_ge60 = int((_t_val >= 60).sum())
        _so_ge70 = int((_t_val >= 70).sum())
        if _so_ge70 > 0 and ("Tên tổ trưởng" in df_raw.columns or "ten_to_truong" in df_raw.columns) and ("PGD" in df_raw.columns or "ten_pgd_std" in df_raw.columns):
            try:
                _tt_col = "Tên tổ trưởng" if "Tên tổ trưởng" in df_raw.columns else "ten_to_truong"
                _pgd_col = "PGD" if "PGD" in df_raw.columns else "ten_pgd_std"
                _df_gia = df_raw.loc[_mask_covay_info & (_t_num >= 70), [_tt_col, _pgd_col]].assign(_tuoi=_t_num)
                _df_gia = _df_gia.sort_values("_tuoi", ascending=False).head(1)
                if not _df_gia.empty:
                    _top_nguoi_gia = {
                        "ten": str(_df_gia.iloc[0][_tt_col]),
                        "tuoi": int(_df_gia.iloc[0]["_tuoi"]),
                        "pgd": str(_df_gia.iloc[0][_pgd_col]),
                    }
            except Exception:
                _top_nguoi_gia = None

    if _so_ge70 > 0:
        _top_msg = ""
        if _top_nguoi_gia:
            _top_msg = f" — cao nhất **{_top_nguoi_gia['ten']}** ({_top_nguoi_gia['tuoi']} tuổi, PGD {_top_nguoi_gia['pgd']})"
        _ge60_msg = f" (trong đó ≥60 tuổi: {_so_ge60:,} tổ)" if _so_ge60 > _so_ge70 else ""
        st.info(
            f"💡 Có **{_so_ge70:,} tổ trưởng ≥70 tuổi**"
            f"{_ge60_msg}{_top_msg}. Dữ liệu được xác định từ ngày sinh trong "
            f"Hồ sơ gốc khách hàng (HSTD) của VBSP."
        )

    if "ước tính" in str(_nguon_dl_msg).lower():
        st.warning(
            "⚠️ Một phần dữ liệu đang **ƯỚC TÍNH** theo TB tuổi KH xã + 8 năm (những tổ không link được tên vào HSTD).\n\n"
            "💡 **Nếu muốn số liệu CHÍNH XÁC 100% từ Chấm điểm Tổ:**\n"
            "1. Mở file Excel `cdtotkvv_latest.xlsx` của PGD tại thư mục upload\n"
            "2. Sau cột **G: Tên tổ trưởng**, thêm 2 cột:\n"
            "   • Cột **H**: Header `Ngày sinh tổ trưởng` (định dạng dd/mm/yyyy)\n"
            "   • Cột **I**: Header `Tuổi tổ trưởng` (tùy chọn, hệ thống tự tính nếu trống)\n"
            "3. Lưu file, upload lại tab **📤 Upload** → hệ thống ưu tiên dùng nguồn chính xác này."
        )
    st.divider()

    # 3) Kiểm tra tính sẵn sàng dữ liệu tuổi
    _co_cot_tuoi = False
    _co_cot_ngay_sinh = False
    if df_raw is not None and not df_raw.empty:
        _co_cot_tuoi = any(
            _c in df_raw.columns
            for _c in ["tuoi_to_truong", "tuoi", "tuoi_to", "Tuổi tổ trưởng", "Tuổi"]
        )
        _co_cot_ngay_sinh = any(
            _c in df_raw.columns
            for _c in ["ngay_sinh_to_truong", "Ngày sinh tổ trưởng", "Ngày sinh", "ns"]
        )
    if df_raw is None or df_raw.empty:
        st.warning("⚠️ Chưa có dữ liệu Chấm điểm Tổ TK&VV. Vui lòng upload dữ liệu trước.")
        st.info(
            "💡 Sau khi upload, thêm 2 cột **tuỳ chọn** sau cột G (Tên tổ trưởng) trong file Excel:\n"
            "   • Cột H: **Ngày sinh tổ trưởng** (định dạng dd/mm/yyyy)\n"
            "   • Cột I: **Tuổi tổ trưởng** (số nguyên, nếu không điền hệ thống tự tính từ ngày sinh)"
        )
        return
    if not _co_cot_tuoi and not _co_cot_ngay_sinh:
        st.warning(
            "⚠️ Dữ liệu Chấm điểm Tổ TK&VV hiện chưa có **Ngày sinh / Tuổi tổ trưởng** "
            "→ Thống kê chưa hiển thị được số liệu."
        )
        st.info(
            "💡 **Cách bổ sung (PGD làm thủ công trong Excel):**\n"
            "1. Mở file `cdtotkvv_latest.xlsx` tại thư mục upload của PGD\n"
            "2. Sau cột **G: Tên tổ trưởng**, thêm:\n"
            "   • Cột **H**: header `Ngày sinh tổ trưởng`, mỗi dòng nhập ngày sinh (vd: 01/01/1985)\n"
            "   • Cột **I**: header `Tuổi tổ trưởng` (tùy chọn, hệ thống tự tính nếu trống)\n"
            "3. Lưu file, upload lại tab **📤 Upload** → hệ thống đọc & tự tạo thống kê này.\n\n"
            "Hoặc chỉ cần 1 trong 2 cột cũng đủ (hệ thống tự tính tuổi từ ngày sinh)."
        )

    # 4) Summary chung (KPI row 4 thẻ)
    if _view_sel == 0 and len(_labels_view) > 1:
        df_bins, summary = _tk_tuoi_pgd(df_raw)
        _scope_title = "Tổng quan toàn Chi nhánh"
    elif len(_labels_view) > 1:
        df_bins, summary = _tk_tuoi_xa(df_raw, pgd_loc=None)
        _scope_title = "Tổng quan toàn Chi nhánh (theo xã)"
    else:
        df_bins, summary = _tk_tuoi_xa(df_raw, pgd_loc=(pgd_user or None))
        _scope_title = (
            f"Địa bàn **{pgd_user}** (theo xã)"
            if pgd_user else "Tổng quan toàn Chi nhánh (theo xã)"
        )

    _tong_so = int(summary.get("tong_to_tong_so") or 0)
    _co_dl = int(summary.get("tong_to") or 0)
    _khong_co = int(summary.get("khong_co_du_lieu") or 0)
    _tb = summary.get("tb_tuoi")
    _med = summary.get("median_tuoi")
    _mn = summary.get("min_tuoi")
    _mx = summary.get("max_tuoi")
    k1, k2, k3, k4 = st.columns(4)
    k1.metric(
        f"🧾 Tổng số Tổ (scope)",
        f"{_tong_so:,}" if _tong_so else "—",
    )
    k2.metric(
        f"✅ Có dữ liệu tuổi",
        f"{_co_dl:,}" if _co_dl else "—",
        (
            f"{_co_dl / _tong_so * 100:.1f}%"
            if (_co_dl and _tong_so > 0)
            else None
        ),
    )
    k3.metric(
        "🔴 Chưa có dữ liệu",
        f"{_khong_co:,}" if _khong_co else "—",
        (
            f"-{_khong_co / _tong_so * 100:.1f}%"
            if (_khong_co and _tong_so > 0)
            else None
        ),
    )
    _tb_txt = f"{_tb:.1f}" if _tb is not None else "—"
    _range_txt = (
        f"{_mn} - {_mx}" if (_mn is not None and _mx is not None) else "—"
    )
    k4.metric(
        "📊 Tuổi TB (Range)",
        _tb_txt,
        delta=f"Range {_range_txt} · Median {_med:.1f}" if _med is not None else None,
    )
    st.caption(f"📍 {_scope_title}")
    st.divider()

    # 5) Hiển thị bins detail
    if df_bins is None or df_bins.empty:
        st.caption("⚠️ Chưa có dòng nào có dữ liệu tuổi tổ trưởng hợp lệ (18-100 tuổi).")
    else:
        # Sắp xếp lại cột
        _bin_order = [
            "Dưới 30 tuổi",
            "30 - 39 tuổi",
            "40 - 49 tuổi",
            "50 - 59 tuổi",
            "60 - 69 tuổi",
            "Từ 70 tuổi trở lên",
        ]
        _present_bins = [b for b in _bin_order if b in df_bins.columns]
        _id_cols = [c for c in ["PGD", "Xã/Phường"] if c in df_bins.columns]
        df_show = df_bins[_id_cols + _present_bins + ["Tổng tổ trưởng có dữ liệu"]].copy()

        # Tổng hợp dòng Cộng (Total) nếu có nhiều hơn 1 dòng
        if len(df_show) > 1:
            total_row: dict = {c: ("—" if c in _id_cols else 0) for c in df_show.columns}
            for _c in _present_bins + ["Tổng tổ trưởng có dữ liệu"]:
                if _c in df_show.columns:
                    total_row[_c] = int(df_show[_c].sum())
            df_show = pd.concat([df_show, pd.DataFrame([total_row])], ignore_index=True)
            # Gán tên dòng tổng
            if "PGD" in df_show.columns:
                df_show.loc[df_show.index[-1], "PGD"] = "🌐 TỔNG CỘNG"
                if "Xã/Phường" in df_show.columns:
                    df_show.loc[df_show.index[-1], "Xã/Phường"] = "—"

        st.markdown(f"**📋 Bảng phân bổ theo nhóm tuổi — {len(df_show)-1 if len(df_show) > 1 else len(df_show)} dòng**")
        # Dùng st.dataframe với TextColumn format số nguyên
        _n_cols: dict = {}
        for _c in list(df_show.columns):
            if _c in ("PGD", "Xã/Phường"):
                _n_cols[_c] = st.column_config.TextColumn(_c, width="medium")
            else:
                _n_cols[_c] = st.column_config.NumberColumn(
                    _c,
                    format="%d",
                    width="small",
                )
        st.dataframe(
            df_show,
            width="stretch",
            hide_index=True,
            height=min(600, 60 + 36 * max(1, len(df_show))),
            column_config=_n_cols,
        )

        # Xuất Excel (nếu có dòng)
        _bytes = xuat_excel({"Thống kê Tuổi Tổ trưởng": df_show})
        st.download_button(
            "📥 Tải bảng này (.xlsx)",
            data=_bytes,
            file_name=ten_file_xuat(
                f"Thong_ke_tuoi_To_Truong_"
                f"{'PGD' if (_view_sel == 0 and len(_labels_view) > 1) else 'XA'}"
                f"_{pgd_user or 'Toan_CN'}.xlsx"
            ),
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            width="stretch",
            key=f"{_view_key_prefix}download_excel_tuoi",
        )

        # Xuất Word + PDF (báo cáo căn lề đẹp)
        st.divider()
        st.markdown("**📄 Báo cáo (Word / PDF)**")
        st.caption(
            "Xuất báo cáo căn lề chuẩn hành chính (Times New Roman 13pt, tiêu đề trung tâm, "
            "tóm tắt 4 thẻ KPI, bảng chi tiết + dòng TỔNG CỘNG, footer ký tên)."
        )
        _mode_chedo = "theo_pgd" if (_view_sel == 0 and len(_labels_view) > 1) else "theo_xa"
        _base_ten = (
            f"BC_ThongKeTuoi_ToTruong_"
            f"{'PGD' if _mode_chedo == 'theo_pgd' else 'XA'}"
            f"_{pgd_user or 'Toan_CN'}"
        )
        _wp_key = f"{_view_key_prefix}tuoi_wp_report"
        if st.button(
            "📝 Chuẩn bị báo cáo (Word + PDF)",
            width="stretch",
            key=f"{_view_key_prefix}prepare_wp",
        ):
            try:
                with st.spinner("Đang tạo báo cáo Word (5-15s)..."):
                    _word_bytes = _tao_word_thong_ke_tuoi_to_truong(
                        df_bins=df_show,
                        summary=summary,
                        che_do_xem=_mode_chedo,
                        tieu_de_pham_vi=_scope_title,
                        ten_pgd=(pgd_user if pgd_user else None),
                    )
                _nut_tai_wp(_word_bytes, _base_ten, _wp_key)
                st.success("✅ Đã chuẩn bị xong. Nhấn nút bên dưới để tải Word / PDF.")
            except Exception as _e:
                logger.error("_sub_thong_ke_tuoi_to_truong: tao word/pdf failed — %s", _e, exc_info=True)
                st.error(f"❌ Lỗi tạo báo cáo: {_e}")
        _hien_thi_nut_tai(_wp_key)


def render(tab: DeltaGenerator | None = None, **kwargs) -> None:
    """
    Render tab Chấm điểm Tổ TK&VV.

    Args:
        tab: Streamlit DeltaGenerator cho tab này
        **kwargs: Chứa role, username, cdto_mode, pgd_user
    """
    role: str = normalize_role(str(kwargs.get("role", "")))
    username: str = str(kwargs.get("username", "unknown"))
    cdto_mode: str = str(kwargs.get("cdto_mode", "cn"))  # "cn" hoặc "pgd"
    pgd_user: str = str(kwargs.get("pgd_user", ""))

    _tab_ctx = tab if tab is not None else __import__('streamlit').container()
    with _tab_ctx:
        # Kiểm tra phân quyền — chỉ cho phép CN và PGD roles
        if not la_phan_he_cn(role) and not la_phan_he_pgd(role):
            st.error("Bạn không có quyền truy cập trang này.")
            return

        # Tiêu đề khác nhau theo mode
        if cdto_mode == "pgd":
            st.subheader("🏘️ Tổ TK&VV")
            st.caption(f"Quản lý chấm điểm Tổ Tiết kiệm & Vay vốn - {pgd_user}")
        else:
            st.subheader("🏘️ Mạng lưới Tổ TK&VV")
            st.caption("Quản lý và xem tổng hợp chấm điểm Tổ Tiết kiệm & Vay vốn toàn chi nhánh")

        # Tạo 5→6 sub-tabs (CN) và 3→4 sub-tabs (PGD), tab cuối: Thống kê Tuổi Tổ trưởng
        if cdto_mode == "cn" and la_phan_he_cn(role):
            _cdto_labels = ["📤 Upload", "📊 Tổng hợp", "📋 Phân tích Chất lượng",
                            "🗺️ Bản đồ Chất lượng", "📈 Xu hướng", "👥 Thống kê Tuổi"]
        else:
            _cdto_labels = ["📋 Phân tích Chất lượng", "🗺️ Bản đồ Chất lượng",
                            "📈 Xu hướng", "👥 Thống kê Tuổi"]
        _cdto_sel = st.radio("", range(len(_cdto_labels)), format_func=lambda i: _cdto_labels[i],
                             horizontal=True, key="cdto_sub_tab", label_visibility="collapsed")
        st.divider()
        if cdto_mode == "cn" and la_phan_he_cn(role):
            if _cdto_sel == 0:   _sub_upload(role, username)
            elif _cdto_sel == 1: _sub_tong_hop(username)
            elif _cdto_sel == 2: _sub_phan_tich_chat_luong(username, cdto_mode, pgd_user)
            elif _cdto_sel == 3: _sub_ban_do_chat_luong(username, cdto_mode, pgd_user)
            elif _cdto_sel == 4: _sub_xu_huong(username, cdto_mode, pgd_user)
            elif _cdto_sel == 5: _sub_thong_ke_tuoi_to_truong(username, cdto_mode, pgd_user)
        else:
            if _cdto_sel == 0:   _sub_phan_tich_chat_luong(username, cdto_mode, pgd_user)
            elif _cdto_sel == 1: _sub_ban_do_chat_luong(username, cdto_mode, pgd_user)
            elif _cdto_sel == 2: _sub_xu_huong(username, cdto_mode, pgd_user)
            elif _cdto_sel == 3: _sub_thong_ke_tuoi_to_truong(username, cdto_mode, pgd_user)
