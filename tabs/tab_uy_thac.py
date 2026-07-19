"""Tab Ủy thác — Theo dõi Hội đoàn thể và các mẫu biểu kiểm tra."""


from __future__ import annotations
from logger import get_logger
logger = get_logger(__name__)

import os, uuid
from datetime import date, datetime
import pandas as pd
import streamlit as st
from streamlit.delta_generator import DeltaGenerator

import db
from auth import normalize_role
from data.core import ts_file
from data.pgd import pgd_slug
from config import (
    COT_TEN_PGD, COT_MA_KH, COT_TEN_KH, COT_SO_KU, COT_TEN_CT,
    COT_TONG_DU_NO, COT_DU_NO_QH, COT_LAI_TON, COT_LAI_TON_QH,
    COT_NGAY_VAY, COT_TEN_TO, COT_DVUT,
    COT_TEN_XA,
    TEN_CHI_NHANH_HIEN_THI, DS_PGD, CACHE_HSTD,
)
from utils import fmt, fmt_ngay, fmt_so, fmt_ty, lay_ngay_so_lieu, xuat_excel
from services.uy_thac_service import (
    build_payload_bc_th,
    cap_nhat_trang_thai_bien_ban,
    danh_sach_to_co_lai_ton,
    danh_sach_to_da_hoi,
    doc_bien_ban_theo_nam,
    loc_chi_tiet_uy_thac,
    tao_bang_theo_doi_kien_nghi,
    tao_canh_bao_trong_diem,
    tinh_bien_dong_snapshot,
    tong_hop_uy_thac_theo,
    tong_hop_kien_nghi,
    tong_quan_dieu_hanh_uy_thac,
    tong_quan_uy_thac,
    tao_bao_cao_dieu_hanh_uy_thac,
    xep_hang_chat_luong_uy_thac,
)
from snapshot_service import (
    danh_sach_ky_uy_thac,
    doc_uy_thac_snapshot_hoi_cn,
    doc_uy_thac_snapshot_hoi_pgd,
    doc_uy_thac_snapshot_multi,
    ky_baseline,
)
from services.template_service import docx_bytes_to_pdf, tao_word_uythac_bc_th
from services.uy_thac_pdf_service import (
    tao_pdf_bao_cao_dang_xem,
    tao_pdf_dieu_hanh_uy_thac,
)

# ── Hằng số ──────────────────────────────────────────────────────────────────
DVUT_ORDER = [
    "Hội nông dân",
    "Hội liên hiệp phụ nữ",
    "Hội cựu chiến binh",
    "Đoàn thanh niên",
]



# ══════════════════════════════════════════════════════════════════════════════
# CACHE FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

@st.cache_data(show_spinner=False, ttl=300)
def _doc_hstd_cached(_ts: float = 0) -> pd.DataFrame:
    try:
        return pd.read_parquet(CACHE_HSTD)
    except Exception as e:
        logger.error("Lỗi trong khối except: %s", e, exc_info=True)
        return pd.DataFrame()


# ══════════════════════════════════════════════════════════════════════════════
# UI HELPERS
# ══════════════════════════════════════════════════════════════════════════════


def _download_word_pdf_pair(docx_bytes: bytes, ten_file: str, key_prefix: str) -> None:
    col1, col2 = st.columns(2)
    with col1:
        st.download_button(
            "⬇️ Tai Word (.docx)",
            data=docx_bytes,
            file_name=ten_file + ".docx",
            mime="application/vnd.openxmlformats-officedocument"
                 ".wordprocessingml.document",
            key=f"{key_prefix}docx",
        )
    with col2:
        with st.spinner("Dang tao PDF..."):
            pdf_bytes = docx_bytes_to_pdf(docx_bytes)
        if pdf_bytes:
            st.download_button(
                "⬇️ Tai PDF",
                data=pdf_bytes,
                file_name=ten_file + ".pdf",
                mime="application/pdf",
                key=f"{key_prefix}pdf",
            )
        else:
            st.caption("⚠️ PDF khong kha dung — can MS Word tren server")


def _chon_pham_vi_uy_thac(
    df: pd.DataFrame,
    pgd_user: str | None,
    key_prefix: str,
) -> tuple[str | None, pd.DataFrame]:
    if df is None or df.empty:
        return pgd_user, pd.DataFrame()

    if pgd_user:
        st.info(f"Phạm vi dữ liệu: **{pgd_user}**")
        if COT_TEN_PGD in df.columns:
            return pgd_user, df[df[COT_TEN_PGD] == pgd_user].copy()
        return pgd_user, df.copy()

    ds_pgd = (
        sorted(df[COT_TEN_PGD].dropna().unique().tolist())
        if COT_TEN_PGD in df.columns else DS_PGD
    )
    pgd_opt = st.selectbox(
        "Phạm vi PGD",
        options=["(Tất cả)"] + ds_pgd,
        key=f"{key_prefix}pham_vi_pgd",
    )
    pgd_chon = None if pgd_opt == "(Tất cả)" else pgd_opt
    if pgd_chon and COT_TEN_PGD in df.columns:
        return pgd_chon, df[df[COT_TEN_PGD] == pgd_chon].copy()
    return None, df.copy()


def _format_pct_value(x: object) -> str:
    try:
        return f"{float(x):.2f}%".replace(".", ",")
    except Exception:
        return "0,00%"


def _format_decimal_value(x: object, precision: int = 1) -> str:
    try:
        return f"{float(x):,.{precision}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return f"{0:.{precision}f}".replace(".", ",")


def _numeric_series_or_zero(df: pd.DataFrame, col: str) -> pd.Series:
    if df is None or df.empty or col not in df.columns:
        return pd.Series(0.0, index=df.index if df is not None else pd.Index([]), dtype="float64")
    return pd.to_numeric(df[col], errors="coerce").fillna(0)


def _index_of_option(options: list[str], value: str | None) -> int:
    if not value:
        return 0
    try:
        return options.index(value)
    except ValueError:
        return 0


def _format_bao_cao_uy_thac(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()

    hien = df.copy()
    cols_int = {
        "so_hoi",
        "so_to",
        "so_kh",
        "Số hội",
        "Số Tổ",
        "Số KH",
        "Số hội đoàn thể",
        "Số Tổ TK&VV",
        "Số Tổ có NQH",
        "Số Tổ có lãi tồn",
    }
    cols_pct = {
        "ty_le_nqh",
        "Tỷ lệ NQH",
        "Tỷ lệ NQH (%)",
        "Tỷ trọng dư nợ (%)",
        "Tỷ lệ Tổ có NQH (%)",
        "Tỷ lệ Tổ có lãi tồn (%)",
    }
    cols_decimal = {"KH BQ/Tổ"}
    for col in hien.columns:
        if col in cols_int:
            hien[col] = hien[col].apply(lambda x: fmt_so(pd.to_numeric(x, errors="coerce")))
        elif col in cols_pct:
            hien[col] = hien[col].apply(_format_pct_value)
        elif col in cols_decimal:
            hien[col] = hien[col].apply(_format_decimal_value)
        elif col in {"tong_dn", "nqh", "lai_ton", "so_du_tg"} or "(triệu đồng)" in str(col):
            hien[col] = hien[col].apply(lambda x: fmt_ty(pd.to_numeric(x, errors="coerce")))
    return hien


def _tao_excel_bao_cao_uy_thac(
    tong_quan: dict[str, object],
    sheets: dict[str, pd.DataFrame],
) -> bytes:
    df_tong_quan = pd.DataFrame([
        {
            "Số hội đoàn thể": tong_quan.get("so_hoi", 0),
            "Số PGD": tong_quan.get("so_pgd", 0),
            "Số xã": tong_quan.get("so_xa", 0),
            "Số Tổ TK&VV": tong_quan.get("so_to", 0),
            "Số KH": tong_quan.get("so_kh", 0),
            "Tổng dư nợ": tong_quan.get("tong_dn", 0),
            "Nợ quá hạn": tong_quan.get("nqh", 0),
            "Lãi tồn": tong_quan.get("lai_ton", 0),
            "Số dư tiền gửi": tong_quan.get("so_du_tg", 0),
            "Tỷ lệ NQH (%)": tong_quan.get("ty_le_nqh", 0),
        }
    ])
    xls_sheets = {"TongQuanUyThac": df_tong_quan}
    xls_sheets.update({k: v for k, v in sheets.items() if v is not None and not v.empty})
    return xuat_excel(xls_sheets)


def _loc_diem_nong_xa(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    result = df[
        (_numeric_series_or_zero(df, "NQH (triệu đồng)") > 0)
        | (_numeric_series_or_zero(df, "Lãi tồn (triệu đồng)") > 0)
        | (_numeric_series_or_zero(df, "Số Tổ có NQH") > 0)
    ].copy()
    if result.empty:
        return result
    return result.sort_values(
        ["Tỷ lệ NQH", "NQH (triệu đồng)", "Lãi tồn (triệu đồng)", "Tỷ lệ Tổ có NQH (%)"],
        ascending=[False, False, False, False],
    ).reset_index(drop=True)


def _loc_diem_nong_to(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    result = df[
        (_numeric_series_or_zero(df, "NQH (triệu đồng)") > 0)
        | (_numeric_series_or_zero(df, "Lãi tồn (triệu đồng)") > 0)
    ].copy()
    if result.empty:
        return result
    return result.sort_values(
        ["Tỷ lệ NQH", "NQH (triệu đồng)", "Lãi tồn (triệu đồng)"],
        ascending=[False, False, False],
    ).reset_index(drop=True)


def _bang_top_hien_thi(
    df: pd.DataFrame,
    rename_map: dict[str, str],
    top_n: int = 5,
    sort_col: str = "tong_dn",
    ascending: bool = False,
) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    hien = df.sort_values(sort_col, ascending=ascending).head(top_n).rename(columns=rename_map)
    return _format_bao_cao_uy_thac(hien)


def _hien_thi_bang_theo_doi(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    hien = df.copy()
    if "Ngày KT" in hien.columns:
        hien["Ngày KT"] = hien["Ngày KT"].apply(fmt_ngay)
    if "Hạn hoàn thành" in hien.columns:
        hien["Hạn hoàn thành"] = hien["Hạn hoàn thành"].apply(fmt_ngay)
    if "Trạng thái" in hien.columns:
        hien["Trạng thái"] = hien["Trạng thái"].map(
            {
                "cho_xu_ly": "🔴 Chờ xử lý",
                "da_xu_ly": "✅ Đã xử lý",
                "khong_ton_tai": "⚪ Không tồn tại",
            }
        ).fillna(hien["Trạng thái"])
    return hien


def _chon_cot_hien_thi(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    return df[[col for col in columns if col in df.columns]].copy()


def _render_tong_quan_uy_thac(df: pd.DataFrame, pgd_user: str | None) -> None:
    st.markdown("#### 📊 Tổng quan Ủy thác")
    st.caption(
        "Ưu tiên hiển thị bức tranh số liệu ủy thác theo HSTD, "
        "kèm các điểm nóng cần theo dõi ngay."
    )
    if df is None or df.empty:
        st.warning("Chưa có dữ liệu.")
        return

    scope_key = f"uyt_overview_{pgd_slug(pgd_user) if pgd_user else 'cn'}_"
    pgd_scope, df_src = _chon_pham_vi_uy_thac(df, pgd_user, scope_key)
    if df_src.empty:
        st.info("Không có dữ liệu trong phạm vi đã chọn.")
        return

    tong_quan = tong_quan_uy_thac(df_src)
    df_hoi = tong_hop_uy_thac_theo(df_src, [COT_DVUT], dvut_order=DVUT_ORDER)
    df_pgd = tong_hop_uy_thac_theo(df_src, [COT_TEN_PGD]) if COT_TEN_PGD in df_src.columns else pd.DataFrame()
    dia_ban_cols = [COT_TEN_PGD] if COT_TEN_PGD in df_src.columns and not pgd_scope else []
    if COT_TEN_XA in df_src.columns:
        dia_ban_cols.append(COT_TEN_XA)
    if not dia_ban_cols and COT_TEN_PGD in df_src.columns:
        dia_ban_cols = [COT_TEN_PGD]
    df_dia_ban = tong_hop_uy_thac_theo(df_src, dia_ban_cols)
    ds_to_lai_ton = danh_sach_to_co_lai_ton(df_src)
    ds_to_da_hoi = danh_sach_to_da_hoi(df_src)
    so_to_da_hoi = len(ds_to_da_hoi)
    dn_bq_to = float(tong_quan.get("tong_dn", 0) or 0) / max(int(tong_quan.get("so_to", 0) or 0), 1)
    dn_bq_kh = float(tong_quan.get("tong_dn", 0) or 0) / max(int(tong_quan.get("so_kh", 0) or 0), 1)
    kh_bq_to = float(tong_quan.get("so_kh", 0) or 0) / max(int(tong_quan.get("so_to", 0) or 0), 1)
    tg_bq_kh = float(tong_quan.get("so_du_tg", 0) or 0) / max(int(tong_quan.get("so_kh", 0) or 0), 1)
    hoi_lon_nhat = ""
    ty_trong_lon_nhat = 0.0
    if not df_hoi.empty and float(tong_quan.get("tong_dn", 0) or 0) > 0:
        top_row = df_hoi.sort_values("tong_dn", ascending=False).iloc[0]
        hoi_lon_nhat = str(top_row.get(COT_DVUT, "") or "")
        ty_trong_lon_nhat = float(top_row.get("tong_dn", 0) or 0) / float(tong_quan["tong_dn"]) * 100.0
    pham_vi_label = pgd_scope or TEN_CHI_NHANH_HIEN_THI

    tt_col, nd_col = st.columns([1.1, 1.9])
    with tt_col:
        st.markdown("**Thông tin phạm vi**")
        df_thong_tin = pd.DataFrame(
            {
                "Chỉ tiêu": [
                    "Phạm vi",
                    "Hội chiếm tỷ trọng lớn nhất",
                    "Tỷ trọng hội lớn nhất",
                    "Tổ đa hội",
                ],
                "Giá trị": [
                    pham_vi_label,
                    hoi_lon_nhat or "Chưa xác định",
                    _format_pct_value(ty_trong_lon_nhat),
                    fmt_so(so_to_da_hoi),
                ],
            }
        )
        st.dataframe(df_thong_tin, use_container_width=True, hide_index=True)
    with nd_col:
        st.markdown("**Nhận định nhanh**")
        ds_nhan_dinh = [
            f"- Dư nợ bình quân đang ở mức **{fmt_ty(dn_bq_to)} triệu đồng/Tổ** và **{fmt_ty(dn_bq_kh)} triệu đồng/KH**.",
            f"- Bình quân mỗi Tổ đang quản lý khoảng **{_format_decimal_value(kh_bq_to)} KH**; tiền gửi bình quân khoảng **{fmt_ty(tg_bq_kh)} triệu đồng/KH**.",
            f"- Hội đang chiếm tỷ trọng dư nợ lớn nhất là **{hoi_lon_nhat or 'chưa xác định'}** với **{_format_pct_value(ty_trong_lon_nhat)}**.",
        ]
        for item in ds_nhan_dinh:
            st.markdown(item)

    ds_canh_bao: list[str] = []
    if float(tong_quan.get("ty_le_nqh", 0) or 0) >= 1.0:
        ds_canh_bao.append("🔴 Tỷ lệ NQH đang ở mức cần lưu ý.")
    if float(tong_quan.get("lai_ton", 0) or 0) > 0:
        ds_canh_bao.append("🟠 Có phát sinh lãi tồn trong phạm vi đang xem.")
    if so_to_da_hoi > 0:
        ds_canh_bao.append(f"⚠️ Có {fmt_so(so_to_da_hoi)} Tổ xuất hiện ở hơn 1 Hội trong HSTD.")
    if ds_canh_bao:
        st.warning("  \n".join(ds_canh_bao))
        if not ds_to_lai_ton.empty:
            with st.expander(
                f"🟠 Chi tiết {fmt_so(len(ds_to_lai_ton))} Tổ/Hội có lãi tồn",
                expanded=True,
            ):
                hien_lai_ton = ds_to_lai_ton.rename(
                    columns={
                        COT_TEN_PGD: "PGD",
                        COT_TEN_XA: "Xã/Phường",
                        COT_DVUT: "Hội đoàn thể",
                        COT_TEN_TO: "Tổ TK&VV",
                        "so_kh": "Số KH",
                        "tong_dn": "Dư nợ (triệu đồng)",
                        "lai_ton": "Lãi tồn (triệu đồng)",
                    }
                )
                st.dataframe(
                    _format_bao_cao_uy_thac(hien_lai_ton),
                    use_container_width=True,
                    hide_index=True,
                    height=min(360, 38 + len(hien_lai_ton) * 35),
                )
                st.caption("Lãi tồn = Lãi tồn + Lãi tồn quá hạn trong HSTD; danh sách sắp theo lãi tồn giảm dần.")
        if not ds_to_da_hoi.empty:
            with st.expander(
                f"⚠️ Chi tiết {fmt_so(len(ds_to_da_hoi))} Tổ xuất hiện ở hơn 1 Hội",
                expanded=True,
            ):
                hien_da_hoi = ds_to_da_hoi.rename(
                    columns={
                        COT_TEN_PGD: "PGD",
                        COT_TEN_XA: "Xã/Phường",
                        COT_TEN_TO: "Tổ TK&VV",
                        "so_hoi": "Số Hội",
                        "ds_hoi": "Các Hội xuất hiện trong HSTD",
                    }
                )
                st.dataframe(
                    _format_bao_cao_uy_thac(hien_da_hoi),
                    use_container_width=True,
                    hide_index=True,
                    height=min(260, 38 + len(hien_da_hoi) * 35),
                )
                st.caption("Tổ được đối chiếu theo bộ PGD + Xã/Phường + Tên Tổ; cần kiểm tra lại Hội nhận ủy thác trong HSTD.")
    else:
        st.success("Chưa thấy cảnh báo trọng yếu trong phạm vi đang xem.")

    st.markdown("**Quy mô ủy thác**")
    qm1, qm2, qm3, qm4, qm5 = st.columns(5)
    qm1.metric("Hội đoàn thể", fmt_so(tong_quan.get("so_hoi", 0)))
    qm2.metric("PGD/Xã", f"{fmt_so(tong_quan.get('so_pgd', 0))}/{fmt_so(tong_quan.get('so_xa', 0))}")
    qm3.metric("Tổ TK&VV", fmt_so(tong_quan.get("so_to", 0)))
    qm4.metric("Khách hàng", fmt_so(tong_quan.get("so_kh", 0)))
    qm5.metric("Tổng dư nợ (triệu đồng)", fmt_ty(tong_quan.get("tong_dn", 0)))

    st.markdown("**Chất lượng và rủi ro**")
    cl1, cl2, cl3, cl4 = st.columns(4)
    cl1.metric("NQH (triệu đồng)", fmt_ty(tong_quan.get("nqh", 0)))
    cl2.metric("Lãi tồn (triệu đồng)", fmt_ty(tong_quan.get("lai_ton", 0)))
    cl3.metric("Tỷ lệ NQH", _format_pct_value(tong_quan.get("ty_le_nqh", 0)))
    cl4.metric("Tổ đa hội", fmt_so(so_to_da_hoi))

    st.markdown("**Chỉ số bình quân**")
    bq1, bq2, bq3, bq4 = st.columns(4)
    bq1.metric("Dư nợ BQ/Tổ (triệu đồng)", fmt_ty(dn_bq_to))
    bq2.metric("Dư nợ BQ/KH (triệu đồng)", fmt_ty(dn_bq_kh))
    bq3.metric("KH BQ/Tổ", _format_decimal_value(kh_bq_to))
    bq4.metric("TG BQ/KH (triệu đồng)", fmt_ty(tg_bq_kh))

    tab_hoi, tab_dia_ban, tab_top = st.tabs(
        ["Theo Hội đoàn thể", "Theo địa bàn", "Top trọng điểm"]
    )

    with tab_hoi:
        if df_hoi.empty:
            st.info("Không có dữ liệu theo Hội đoàn thể.")
        else:
            hien_hoi = _chon_cot_hien_thi(
                _format_bao_cao_uy_thac(
                    df_hoi.rename(
                        columns={
                            COT_DVUT: "Hội đoàn thể",
                            "so_to": "Số Tổ",
                            "so_kh": "Số KH",
                            "tong_dn": "Dư nợ (triệu đồng)",
                            "nqh": "NQH (triệu đồng)",
                            "lai_ton": "Lãi tồn (triệu đồng)",
                            "so_du_tg": "TG TK (triệu đồng)",
                            "ty_le_nqh": "Tỷ lệ NQH",
                        }
                    )
                ),
                [
                    "Hội đoàn thể",
                    "Số Tổ",
                    "Số KH",
                    "Dư nợ (triệu đồng)",
                    "NQH (triệu đồng)",
                    "Lãi tồn (triệu đồng)",
                    "TG TK (triệu đồng)",
                    "Tỷ lệ NQH",
                ],
            )
            st.caption("Bảng cơ cấu theo Hội đoàn thể để nhìn nhanh quy mô, nợ quá hạn và lãi tồn.")
            st.dataframe(hien_hoi, use_container_width=True, hide_index=True, height=320)

    with tab_dia_ban:
        if df_dia_ban.empty:
            st.info("Không có dữ liệu địa bàn.")
        else:
            rename_map = {
                "so_hoi": "Số hội",
                "so_to": "Số Tổ",
                "so_kh": "Số KH",
                "tong_dn": "Dư nợ (triệu đồng)",
                "nqh": "NQH (triệu đồng)",
                "lai_ton": "Lãi tồn (triệu đồng)",
                "so_du_tg": "TG TK (triệu đồng)",
                "ty_le_nqh": "Tỷ lệ NQH",
            }
            st.caption("Địa bàn được sắp theo thứ tự bảng tổng hợp, thuận tiện để rà nhanh PGD/Xã đang phát sinh vấn đề.")
            st.dataframe(
                _chon_cot_hien_thi(
                    _format_bao_cao_uy_thac(df_dia_ban.rename(columns=rename_map).head(12)),
                    [
                        "PGD",
                        "Xã/Phường",
                        "Số hội",
                        "Số Tổ",
                        "Số KH",
                        "Dư nợ (triệu đồng)",
                        "NQH (triệu đồng)",
                        "Lãi tồn (triệu đồng)",
                        "TG TK (triệu đồng)",
                        "Tỷ lệ NQH",
                    ],
                ),
                use_container_width=True,
                hide_index=True,
                height=320,
            )

    with tab_top:
        top1, top2, top3 = st.columns(3)
        with top1:
            st.markdown("**Top PGD dư nợ cao**")
            if df_pgd.empty:
                st.info("Không có dữ liệu PGD.")
            else:
                st.dataframe(
                    _chon_cot_hien_thi(
                        _bang_top_hien_thi(
                            df_pgd,
                            rename_map={
                                COT_TEN_PGD: "PGD",
                                "so_to": "Số Tổ",
                                "so_kh": "Số KH",
                                "tong_dn": "Dư nợ (triệu đồng)",
                                "nqh": "NQH (triệu đồng)",
                                "ty_le_nqh": "Tỷ lệ NQH",
                            },
                        ),
                        ["PGD", "Số Tổ", "Số KH", "Dư nợ (triệu đồng)", "NQH (triệu đồng)", "Tỷ lệ NQH"],
                    ),
                    use_container_width=True,
                    hide_index=True,
                )
        with top2:
            st.markdown("**Top địa bàn NQH cao**")
            if df_dia_ban.empty:
                st.info("Không có dữ liệu địa bàn.")
            else:
                st.dataframe(
                    _chon_cot_hien_thi(
                        _bang_top_hien_thi(
                            df_dia_ban,
                            rename_map={
                                COT_TEN_PGD: "PGD",
                                COT_TEN_XA: "Xã/Phường",
                                "so_kh": "Số KH",
                                "nqh": "NQH (triệu đồng)",
                                "tong_dn": "Dư nợ (triệu đồng)",
                                "ty_le_nqh": "Tỷ lệ NQH",
                            },
                            sort_col="nqh",
                        ),
                        ["PGD", "Xã/Phường", "Số KH", "NQH (triệu đồng)", "Dư nợ (triệu đồng)", "Tỷ lệ NQH"],
                    ),
                    use_container_width=True,
                    hide_index=True,
                )
        with top3:
            st.markdown("**Top Hội tỷ lệ NQH cao**")
            if df_hoi.empty:
                st.info("Không có dữ liệu Hội đoàn thể.")
            else:
                st.dataframe(
                    _chon_cot_hien_thi(
                        _bang_top_hien_thi(
                            df_hoi,
                            rename_map={
                                COT_DVUT: "Hội đoàn thể",
                                "so_to": "Số Tổ",
                                "so_kh": "Số KH",
                                "nqh": "NQH (triệu đồng)",
                                "tong_dn": "Dư nợ (triệu đồng)",
                                "ty_le_nqh": "Tỷ lệ NQH",
                            },
                            sort_col="ty_le_nqh",
                        ),
                        ["Hội đoàn thể", "Số Tổ", "Số KH", "NQH (triệu đồng)", "Dư nợ (triệu đồng)", "Tỷ lệ NQH"],
                    ),
                    use_container_width=True,
                    hide_index=True,
                )


def _render_bao_cao_so_lieu(
    df: pd.DataFrame,
    pgd_user: str | None,
    username: str,
) -> None:
    st.markdown("#### 📑 Báo cáo số liệu Ủy thác")
    st.caption(
        "Trung tâm báo cáo của tab Ủy thác: xem nhanh, drill-down và xuất Excel "
        "theo Hội đoàn thể, địa bàn, chương trình và danh sách chi tiết."
    )
    if df is None or df.empty:
        st.warning("Chưa có dữ liệu.")
        return

    scope_key = f"uyt_report_{pgd_slug(pgd_user) if pgd_user else 'cn'}_"
    pgd_scope, df_src = _chon_pham_vi_uy_thac(df, pgd_user, scope_key)
    if df_src.empty:
        st.info("Không có dữ liệu trong phạm vi đã chọn.")
        return

    df_loc = df_src.copy()
    bo_loc_ct: dict[str, object] = {}
    f1, f2, f3, f4 = st.columns(4)
    if COT_TEN_PGD in df_src.columns and not pgd_user:
        ds_pgd = ["(Tất cả)"] + sorted(df_src[COT_TEN_PGD].dropna().unique().tolist())
        bo_loc_ct[COT_TEN_PGD] = f1.selectbox("Lọc PGD", ds_pgd, key=f"{scope_key}pgd")
    if COT_DVUT in df_src.columns:
        ds_dvut = ["(Tất cả)"] + sorted(df_src[COT_DVUT].dropna().unique().tolist())
        bo_loc_ct[COT_DVUT] = f2.selectbox("Lọc Hội đoàn thể", ds_dvut, key=f"{scope_key}dvut")
    if COT_TEN_XA in df_src.columns:
        ds_xa = ["(Tất cả)"] + sorted(df_src[COT_TEN_XA].dropna().unique().tolist())
        bo_loc_ct[COT_TEN_XA] = f3.selectbox("Lọc xã/phường", ds_xa, key=f"{scope_key}xa")
    if COT_TEN_CT in df_src.columns:
        ds_ct = ["(Tất cả)"] + sorted(df_src[COT_TEN_CT].dropna().unique().tolist())
        bo_loc_ct[COT_TEN_CT] = f4.selectbox("Lọc chương trình", ds_ct, key=f"{scope_key}ct")

    opt1, opt2 = st.columns(2)
    chi_nqh = opt1.checkbox("Chỉ hiện khoản có NQH", key=f"{scope_key}chi_nqh")
    chi_lai_ton = opt2.checkbox("Chỉ hiện khoản có lãi tồn", key=f"{scope_key}chi_lai_ton")

    df_chi_tiet = loc_chi_tiet_uy_thac(df_src, bo_loc_ct)
    if chi_nqh and COT_DU_NO_QH in df_chi_tiet.columns:
        df_chi_tiet = df_chi_tiet[pd.to_numeric(df_chi_tiet[COT_DU_NO_QH], errors="coerce").fillna(0) > 0].copy()
    if chi_lai_ton and "Nợ lãi" in df_chi_tiet.columns:
        df_chi_tiet = df_chi_tiet[pd.to_numeric(df_chi_tiet["Nợ lãi"], errors="coerce").fillna(0) > 0].copy()
    df_loc = df_chi_tiet.copy()
    tong_quan = tong_quan_uy_thac(df_loc)
    tong_quan_dh = tong_quan_dieu_hanh_uy_thac(df_loc)

    report_type = st.radio(
        "Loại báo cáo",
        [
            "Theo Hội đoàn thể",
            "Theo PGD",
            "Điều hành theo PGD",
            "Điều hành theo Hội",
            "Theo xã/phường",
            "Theo PGD và Hội",
            "Theo chương trình",
            "Theo Tổ TK&VV",
            "Điểm nóng xã/Tổ",
            "Danh sách chi tiết",
            "Xếp hạng chất lượng",
            "Cảnh báo trọng điểm",
            "Biến động nhiều kỳ",
        ],
        horizontal=True,
        key=f"{scope_key}report_type",
    )

    current_name = "BaoCaoUyThac"
    current_export = pd.DataFrame()
    current_show = pd.DataFrame()
    df_hoi = tong_hop_uy_thac_theo(df_loc, [COT_DVUT], dvut_order=DVUT_ORDER)
    df_pgd = tong_hop_uy_thac_theo(df_loc, [COT_TEN_PGD]) if COT_TEN_PGD in df_loc.columns else pd.DataFrame()
    group_xa = [COT_TEN_XA] if pgd_user or COT_TEN_PGD not in df_loc.columns else [COT_TEN_PGD, COT_TEN_XA]
    df_xa = tong_hop_uy_thac_theo(df_loc, group_xa) if COT_TEN_XA in df_loc.columns else pd.DataFrame()
    group_pgd_hoi = [c for c in [COT_TEN_PGD, COT_DVUT] if c in df_loc.columns]
    df_pgd_hoi = tong_hop_uy_thac_theo(df_loc, group_pgd_hoi) if group_pgd_hoi else pd.DataFrame()
    df_ct = tong_hop_uy_thac_theo(df_loc, [COT_TEN_CT]) if COT_TEN_CT in df_loc.columns else pd.DataFrame()
    group_to = [c for c in [COT_TEN_PGD, COT_TEN_XA, COT_DVUT, COT_TEN_TO] if c in df_loc.columns]
    df_to = tong_hop_uy_thac_theo(df_loc, group_to) if COT_TEN_TO in df_loc.columns and group_to else pd.DataFrame()
    df_pgd_dh = tao_bao_cao_dieu_hanh_uy_thac(df_loc, [COT_TEN_PGD]) if COT_TEN_PGD in df_loc.columns else pd.DataFrame()
    df_hoi_dh = tao_bao_cao_dieu_hanh_uy_thac(df_loc, [COT_DVUT], dvut_order=DVUT_ORDER) if COT_DVUT in df_loc.columns else pd.DataFrame()
    df_xa_dh = tao_bao_cao_dieu_hanh_uy_thac(df_loc, group_xa) if COT_TEN_XA in df_loc.columns else pd.DataFrame()
    df_to_dh = (
        tao_bao_cao_dieu_hanh_uy_thac(df_loc, group_to)
        if COT_TEN_TO in df_loc.columns and group_to
        else pd.DataFrame()
    )

    so_to_nqh = int(tong_quan_dh.get("so_to_nqh", 0) or 0)
    so_to_lai_ton = int(tong_quan_dh.get("so_to_lai_ton", 0) or 0)
    ty_le_to_nqh = float(tong_quan_dh.get("ty_le_to_nqh", 0.0) or 0.0)
    tg_bq_kh = float(tong_quan_dh.get("tg_bq_kh", 0.0) or 0.0)

    q1, q2, q3, q4 = st.columns(4)
    q1.metric("Tổ có NQH", fmt_so(so_to_nqh))
    q2.metric("Tổ có lãi tồn", fmt_so(so_to_lai_ton))
    q3.metric("Tỷ lệ Tổ có NQH", _format_pct_value(ty_le_to_nqh))
    q4.metric("TG BQ/KH (triệu đồng)", fmt_ty(tg_bq_kh))

    dvut_pref = bo_loc_ct.get(COT_DVUT)
    dvut_pref = dvut_pref if isinstance(dvut_pref, str) and dvut_pref not in ("", "(Tất cả)") else None
    xa_pref = bo_loc_ct.get(COT_TEN_XA)
    xa_pref = xa_pref if isinstance(xa_pref, str) and xa_pref not in ("", "(Tất cả)") else None
    pgd_pref = bo_loc_ct.get(COT_TEN_PGD)
    pgd_pref = pgd_pref if isinstance(pgd_pref, str) and pgd_pref not in ("", "(Tất cả)") else None

    report_pgd_dh = df_pgd_dh.rename(
        columns={
            COT_TEN_PGD: "PGD",
            "so_hoi": "Số hội",
            "so_to": "Số Tổ",
            "so_kh": "Số KH",
            "tong_dn": "Dư nợ (triệu đồng)",
            "ty_trong_dn": "Tỷ trọng dư nợ (%)",
            "nqh": "NQH (triệu đồng)",
            "lai_ton": "Lãi tồn (triệu đồng)",
            "so_du_tg": "TG TK (triệu đồng)",
            "dn_bq_to": "Dư nợ BQ/Tổ (triệu đồng)",
            "dn_bq_kh": "Dư nợ BQ/KH (triệu đồng)",
            "tg_bq_kh": "TG BQ/KH (triệu đồng)",
            "kh_bq_to": "KH BQ/Tổ",
            "so_to_nqh": "Số Tổ có NQH",
            "so_to_lai_ton": "Số Tổ có lãi tồn",
            "ty_le_to_nqh": "Tỷ lệ Tổ có NQH (%)",
            "ty_le_to_lai_ton": "Tỷ lệ Tổ có lãi tồn (%)",
            "ty_le_nqh": "Tỷ lệ NQH",
        }
    )
    report_hoi_dh = df_hoi_dh.rename(
        columns={
            COT_DVUT: "Hội đoàn thể",
            "so_to": "Số Tổ",
            "so_kh": "Số KH",
            "tong_dn": "Dư nợ (triệu đồng)",
            "ty_trong_dn": "Tỷ trọng dư nợ (%)",
            "nqh": "NQH (triệu đồng)",
            "lai_ton": "Lãi tồn (triệu đồng)",
            "so_du_tg": "TG TK (triệu đồng)",
            "dn_bq_to": "Dư nợ BQ/Tổ (triệu đồng)",
            "dn_bq_kh": "Dư nợ BQ/KH (triệu đồng)",
            "tg_bq_kh": "TG BQ/KH (triệu đồng)",
            "kh_bq_to": "KH BQ/Tổ",
            "so_to_nqh": "Số Tổ có NQH",
            "so_to_lai_ton": "Số Tổ có lãi tồn",
            "ty_le_to_nqh": "Tỷ lệ Tổ có NQH (%)",
            "ty_le_to_lai_ton": "Tỷ lệ Tổ có lãi tồn (%)",
            "ty_le_nqh": "Tỷ lệ NQH",
        }
    )
    report_xa_diem_nong = df_xa_dh.rename(
        columns={
            COT_TEN_PGD: "PGD",
            COT_TEN_XA: "Xã/Phường",
            "so_hoi": "Số hội",
            "so_to": "Số Tổ",
            "so_kh": "Số KH",
            "tong_dn": "Dư nợ (triệu đồng)",
            "ty_trong_dn": "Tỷ trọng dư nợ (%)",
            "nqh": "NQH (triệu đồng)",
            "lai_ton": "Lãi tồn (triệu đồng)",
            "so_du_tg": "TG TK (triệu đồng)",
            "dn_bq_to": "Dư nợ BQ/Tổ (triệu đồng)",
            "dn_bq_kh": "Dư nợ BQ/KH (triệu đồng)",
            "tg_bq_kh": "TG BQ/KH (triệu đồng)",
            "kh_bq_to": "KH BQ/Tổ",
            "so_to_nqh": "Số Tổ có NQH",
            "so_to_lai_ton": "Số Tổ có lãi tồn",
            "ty_le_to_nqh": "Tỷ lệ Tổ có NQH (%)",
            "ty_le_to_lai_ton": "Tỷ lệ Tổ có lãi tồn (%)",
            "ty_le_nqh": "Tỷ lệ NQH",
        }
    )
    report_to_diem_nong = df_to_dh.rename(
        columns={
            COT_TEN_PGD: "PGD",
            COT_TEN_XA: "Xã/Phường",
            COT_DVUT: "Hội đoàn thể",
            COT_TEN_TO: "Tổ TK&VV",
            "so_kh": "Số KH",
            "tong_dn": "Dư nợ (triệu đồng)",
            "ty_trong_dn": "Tỷ trọng dư nợ (%)",
            "nqh": "NQH (triệu đồng)",
            "lai_ton": "Lãi tồn (triệu đồng)",
            "so_du_tg": "TG TK (triệu đồng)",
            "dn_bq_kh": "Dư nợ BQ/KH (triệu đồng)",
            "tg_bq_kh": "TG BQ/KH (triệu đồng)",
            "so_to_nqh": "Số Tổ có NQH",
            "so_to_lai_ton": "Số Tổ có lãi tồn",
            "ty_le_to_nqh": "Tỷ lệ Tổ có NQH (%)",
            "ty_le_to_lai_ton": "Tỷ lệ Tổ có lãi tồn (%)",
            "ty_le_nqh": "Tỷ lệ NQH",
        }
    )
    report_xa_diem_nong = _loc_diem_nong_xa(report_xa_diem_nong)
    report_to_diem_nong = _loc_diem_nong_to(report_to_diem_nong)

    report_xh_bundle = xep_hang_chat_luong_uy_thac(
        df_loc,
        [COT_TEN_PGD] if COT_TEN_PGD in df_loc.columns else ([COT_DVUT] if COT_DVUT in df_loc.columns else []),
    )
    report_xh_bundle = report_xh_bundle.rename(columns={
        "xep_hang": "Xếp hạng",
        COT_TEN_PGD: "PGD",
        COT_TEN_XA: "Xã/Phường",
        COT_DVUT: "Hội đoàn thể",
        "so_to": "Số Tổ",
        "so_kh": "Số KH",
        "tong_dn": "Dư nợ (triệu đồng)",
        "nqh": "NQH (triệu đồng)",
        "lai_ton": "Lãi tồn (triệu đồng)",
        "ty_le_nqh": "Tỷ lệ NQH",
        "lai_ton_tren_dn": "Lãi tồn/Dư nợ (%)",
        "dn_bq_to": "Dư nợ BQ/Tổ (triệu đồng)",
        "kh_bq_to": "KH BQ/Tổ",
        "diem_rui_ro": "Điểm rủi ro",
    })
    report_cb_bundle = tao_canh_bao_trong_diem(
        df_loc,
        doc_bien_ban_theo_nam(nam=date.today().year, pgd_user=pgd_scope or pgd_user),
        ngay_ref=date.today(),
    )
    _ky_all_pdf = danh_sach_ky_uy_thac()
    _bl_pdf = ky_baseline(_ky_all_pdf, _ky_all_pdf[0]) if _ky_all_pdf else None
    _ky_6_pdf = _ky_all_pdf[:6]
    if _bl_pdf and _bl_pdf not in _ky_6_pdf:
        _ky_6_pdf = sorted(set(_ky_6_pdf + [_bl_pdf]), reverse=True)[:6]
    report_bd_bundle = tinh_bien_dong_snapshot(
        doc_uy_thac_snapshot_multi(tuple(list(reversed(_ky_6_pdf))), ten_pgd=pgd_scope or pgd_user)
    ).rename(columns={
        "ky": "Kỳ",
        "tong_du_no": "Tổng dư nợ (triệu đồng)",
        "du_no_qh": "NQH (triệu đồng)",
        "so_ho": "Số KH",
        "so_ku": "Số món vay",
        "so_to": "Số Tổ",
        "lai_ton": "Lãi tồn (triệu đồng)",
        "so_du_tg": "Tiền gửi (triệu đồng)",
        "ty_le_nqh": "Tỷ lệ NQH",
        "delta_tong_du_no": "Δ Dư nợ (triệu đồng)",
        "delta_du_no_qh": "Δ NQH (triệu đồng)",
        "delta_so_ho": "Δ Số KH",
        "delta_so_ku": "Δ Số món vay",
        "delta_so_to": "Δ Số Tổ",
        "delta_lai_ton": "Δ Lãi tồn (triệu đồng)",
        "delta_so_du_tg": "Δ Tiền gửi (triệu đồng)",
    })
    report_hoi_pdf = df_hoi.rename(columns={
        COT_DVUT: "Hội đoàn thể",
        "so_to": "Số Tổ",
        "so_kh": "Số KH",
        "tong_dn": "Dư nợ (triệu đồng)",
        "nqh": "NQH (triệu đồng)",
        "lai_ton": "Lãi tồn (triệu đồng)",
        "so_du_tg": "TG TK (triệu đồng)",
        "ty_le_nqh": "Tỷ lệ NQH",
    })
    report_to_da_hoi_pdf = danh_sach_to_da_hoi(df_loc).rename(columns={
        COT_TEN_PGD: "PGD",
        COT_TEN_XA: "Xã/Phường",
        COT_TEN_TO: "Tổ TK&VV",
        "so_hoi": "Số Hội",
        "ds_hoi": "Các Hội xuất hiện trong HSTD",
    })

    if report_type == "Theo Hội đoàn thể":
        current_name = "TheoHoiDoanThe"
        current_export = df_hoi.rename(
            columns={
                COT_DVUT: "Hội đoàn thể",
                "so_to": "Số Tổ",
                "so_kh": "Số KH",
                "tong_dn": "Dư nợ (triệu đồng)",
                "nqh": "NQH (triệu đồng)",
                "lai_ton": "Lãi tồn (triệu đồng)",
                "so_du_tg": "TG TK (triệu đồng)",
                "ty_le_nqh": "Tỷ lệ NQH",
            }
        )
        current_show = _format_bao_cao_uy_thac(current_export)
    elif report_type == "Theo PGD":
        current_name = "TheoPGD"
        current_export = df_pgd.rename(
            columns={
                COT_TEN_PGD: "PGD",
                "so_hoi": "Số hội",
                "so_to": "Số Tổ",
                "so_kh": "Số KH",
                "tong_dn": "Dư nợ (triệu đồng)",
                "nqh": "NQH (triệu đồng)",
                "lai_ton": "Lãi tồn (triệu đồng)",
                "so_du_tg": "TG TK (triệu đồng)",
                "ty_le_nqh": "Tỷ lệ NQH",
            }
        )
        current_show = _format_bao_cao_uy_thac(current_export)
    elif report_type == "Điều hành theo PGD":
        current_name = "DieuHanhTheoPGD"
        current_export = report_pgd_dh.copy()
        current_show = _format_bao_cao_uy_thac(current_export)
        st.caption("Bảng điều hành bổ sung tỷ trọng dư nợ, dư nợ bình quân và tỷ lệ Tổ có vấn đề để ưu tiên rà soát theo PGD.")
    elif report_type == "Điều hành theo Hội":
        current_name = "DieuHanhTheoHoi"
        current_export = report_hoi_dh.copy()
        current_show = _format_bao_cao_uy_thac(current_export)
        st.caption("Bảng điều hành theo Hội giúp nhìn nhanh cơ cấu dư nợ, bình quân/Tổ và mức độ phát sinh NQH, lãi tồn của từng Hội.")
    elif report_type == "Theo xã/phường":
        current_name = "TheoXa"
        current_export = df_xa.rename(
            columns={
                COT_TEN_PGD: "PGD",
                COT_TEN_XA: "Xã/Phường",
                "so_hoi": "Số hội",
                "so_to": "Số Tổ",
                "so_kh": "Số KH",
                "tong_dn": "Dư nợ (triệu đồng)",
                "nqh": "NQH (triệu đồng)",
                "lai_ton": "Lãi tồn (triệu đồng)",
                "so_du_tg": "TG TK (triệu đồng)",
                "ty_le_nqh": "Tỷ lệ NQH",
            }
        )
        current_show = _format_bao_cao_uy_thac(current_export)
    elif report_type == "Theo PGD và Hội":
        current_name = "TheoPGD_Hoi"
        current_export = df_pgd_hoi.rename(
            columns={
                COT_TEN_PGD: "PGD",
                COT_DVUT: "Hội đoàn thể",
                "so_to": "Số Tổ",
                "so_kh": "Số KH",
                "tong_dn": "Dư nợ (triệu đồng)",
                "nqh": "NQH (triệu đồng)",
                "lai_ton": "Lãi tồn (triệu đồng)",
                "so_du_tg": "TG TK (triệu đồng)",
                "ty_le_nqh": "Tỷ lệ NQH",
            }
        )
        current_show = _format_bao_cao_uy_thac(current_export)
    elif report_type == "Theo chương trình":
        current_name = "TheoChuongTrinh"
        current_export = df_ct.rename(
            columns={
                COT_TEN_CT: "Chương trình",
                "so_hoi": "Số hội",
                "so_to": "Số Tổ",
                "so_kh": "Số KH",
                "tong_dn": "Dư nợ (triệu đồng)",
                "nqh": "NQH (triệu đồng)",
                "lai_ton": "Lãi tồn (triệu đồng)",
                "so_du_tg": "TG TK (triệu đồng)",
                "ty_le_nqh": "Tỷ lệ NQH",
            }
        )
        current_show = _format_bao_cao_uy_thac(current_export)
    elif report_type == "Theo Tổ TK&VV":
        current_name = "TheoToTKVV"
        current_export = df_to.rename(
            columns={
                COT_TEN_PGD: "PGD",
                COT_TEN_XA: "Xã/Phường",
                COT_DVUT: "Hội đoàn thể",
                COT_TEN_TO: "Tổ TK&VV",
                "so_kh": "Số KH",
                "tong_dn": "Dư nợ (triệu đồng)",
                "nqh": "NQH (triệu đồng)",
                "lai_ton": "Lãi tồn (triệu đồng)",
                "so_du_tg": "TG TK (triệu đồng)",
                "ty_le_nqh": "Tỷ lệ NQH",
            }
        )
        current_show = _format_bao_cao_uy_thac(current_export)
    elif report_type == "Điểm nóng xã/Tổ":
        cap_diem_nong = st.selectbox(
            "Cấp điểm nóng",
            ["Xã/phường", "Tổ TK&VV"],
            key=f"{scope_key}cap_diem_nong",
        )
        if cap_diem_nong == "Xã/phường":
            current_name = "DiemNongXa"
            current_export = report_xa_diem_nong.copy()
        else:
            current_name = "DiemNongToTKVV"
            current_export = report_to_diem_nong.copy()
        current_show = _format_bao_cao_uy_thac(current_export)
        st.caption("Điểm nóng ưu tiên các địa bàn/tổ có NQH, lãi tồn hoặc tỷ lệ Tổ có vấn đề cao để phục vụ giao ban và kiểm tra.")
    elif report_type == "Danh sách chi tiết":
        current_name = "DanhSachChiTiet"
        current_export = df_chi_tiet.rename(
            columns={
                COT_TEN_PGD: "PGD",
                COT_DVUT: "Hội đoàn thể",
                COT_TEN_XA: "Xã/Phường",
                COT_TEN_TO: "Tổ TK&VV",
                COT_TEN_KH: "Khách hàng",
                COT_SO_KU: "Số khế ước",
                COT_TEN_CT: "Chương trình",
                COT_TONG_DU_NO: "Dư nợ (triệu đồng)",
                COT_DU_NO_QH: "NQH (triệu đồng)",
                COT_SO_DU_TG: "TG TK (triệu đồng)",
            }
        )
        current_show = _format_bao_cao_uy_thac(current_export)
    elif report_type == "Xếp hạng chất lượng":
        current_name = "XepHangChatLuong"
        cap_xh = st.selectbox(
            "Cấp xếp hạng",
            ["PGD", "Xã/phường", "Hội đoàn thể"],
            key=f"{scope_key}cap_xep_hang",
        )
        if cap_xh == "PGD":
            group_xh = [COT_TEN_PGD] if COT_TEN_PGD in df_loc.columns else []
        elif cap_xh == "Xã/phường":
            group_xh = [c for c in [COT_TEN_PGD, COT_TEN_XA] if c in df_loc.columns]
        else:
            group_xh = [COT_DVUT] if COT_DVUT in df_loc.columns else []
        df_xh = xep_hang_chat_luong_uy_thac(df_loc, group_xh) if group_xh else pd.DataFrame()
        current_export = df_xh.rename(columns={
            "xep_hang": "Xếp hạng",
            COT_TEN_PGD: "PGD",
            COT_TEN_XA: "Xã/Phường",
            COT_DVUT: "Hội đoàn thể",
            "so_to": "Số Tổ",
            "so_kh": "Số KH",
            "tong_dn": "Dư nợ (triệu đồng)",
            "nqh": "NQH (triệu đồng)",
            "lai_ton": "Lãi tồn (triệu đồng)",
            "ty_le_nqh": "Tỷ lệ NQH",
            "lai_ton_tren_dn": "Lãi tồn/Dư nợ (%)",
            "dn_bq_to": "Dư nợ BQ/Tổ (triệu đồng)",
            "kh_bq_to": "KH BQ/Tổ",
            "diem_rui_ro": "Điểm rủi ro",
        })
        current_show = _format_bao_cao_uy_thac(current_export)
        st.caption("Điểm rủi ro là chỉ báo tương đối: 50% NQH, 30% lãi tồn/dư nợ, 20% KH bình quân/Tổ; không thay thế xếp loại nghiệp vụ.")
    elif report_type == "Cảnh báo trọng điểm":
        current_name = "CanhBaoTrongDiem"
        records_cb = doc_bien_ban_theo_nam(
            nam=date.today().year,
            pgd_user=pgd_scope or pgd_user,
        )
        df_cb = tao_canh_bao_trong_diem(df_loc, records_cb, ngay_ref=date.today())
        current_export = df_cb
        current_show = df_cb.copy()
        if not current_show.empty:
            current_show["Giá trị"] = current_show.apply(
                lambda r: fmt_ty(r["Giá trị"])
                if r["Nhóm cảnh báo"] in {"Nợ quá hạn", "Lãi tồn"}
                else fmt_so(r["Giá trị"]),
                axis=1,
            )
            current_show["Tỷ lệ (%)"] = current_show["Tỷ lệ (%)"].apply(_format_pct_value)
        st.caption("Danh sách đã được sắp theo mức độ và giá trị để ưu tiên hành động; Tổ đa hội là cảnh báo kiểm tra dữ liệu.")
    else:
        ky_all = danh_sach_ky_uy_thac()
        _bl_ut = ky_baseline(ky_all, ky_all[0]) if ky_all else None
        _ky_6 = ky_all[:6]
        if _bl_ut and _bl_ut not in _ky_6:
            _ky_6 = sorted(set(_ky_6 + [_bl_ut]), reverse=True)[:6]
        ky_chon = list(reversed(_ky_6))
        cap_bd_options = ["Tổng phạm vi", "Theo Xã/phường"]
        if not (pgd_scope or pgd_user):
            cap_bd_options.insert(1, "Theo Hội đoàn thể")
        cap_bd = st.selectbox(
            "Cấp biến động",
            options=cap_bd_options,
            key=f"{scope_key}cap_bien_dong",
        )

        pgd_snap = pgd_scope or pgd_user
        ten_doi_tuong = pgd_snap or TEN_CHI_NHANH_HIEN_THI
        current_name = "BienDongNhieuKy"

        if cap_bd == "Theo Hội đoàn thể":
            if pgd_snap:
                pgd_bd_hoi = pgd_snap
            else:
                ds_pgd_bd_hoi = sorted(df_src[COT_TEN_PGD].dropna().unique().tolist()) if COT_TEN_PGD in df_src.columns else []
                pgd_bd_hoi_opt = st.selectbox(
                    "Phạm vi Hội đoàn thể",
                    options=["(Toàn Chi nhánh)"] + ds_pgd_bd_hoi,
                    index=0 if not pgd_pref else _index_of_option(["(Toàn Chi nhánh)"] + ds_pgd_bd_hoi, pgd_pref),
                    key=f"{scope_key}bd_hoi_pgd",
                )
                pgd_bd_hoi = None if pgd_bd_hoi_opt == "(Toàn Chi nhánh)" else pgd_bd_hoi_opt

            if pgd_bd_hoi and COT_TEN_PGD in df_src.columns:
                df_scope_hoi = df_src[df_src[COT_TEN_PGD] == pgd_bd_hoi].copy()
            else:
                df_scope_hoi = df_src
            ds_hoi = sorted(df_scope_hoi[COT_DVUT].dropna().unique().tolist()) if COT_DVUT in df_scope_hoi.columns else []
            if not ds_hoi:
                df_snap_ut = pd.DataFrame()
            else:
                hoi_chon = st.selectbox(
                    "Chọn Hội đoàn thể",
                    options=ds_hoi,
                    index=_index_of_option(ds_hoi, dvut_pref),
                    key=f"{scope_key}bd_hoi",
                )
                ten_doi_tuong = f"{pgd_bd_hoi} - {hoi_chon}" if pgd_bd_hoi else hoi_chon
                current_name = "BienDongTheoHoi"
                if pgd_bd_hoi:
                    df_snap_ut = doc_uy_thac_snapshot_hoi_pgd(
                        tuple(ky_chon), pgd_bd_hoi, hoi_chon
                    )
                else:
                    df_snap_ut = doc_uy_thac_snapshot_hoi_cn(tuple(ky_chon), hoi_chon)
        elif cap_bd == "Theo Xã/phường":
            ds_pgd_bd = []
            if pgd_snap:
                ds_pgd_bd = [pgd_snap]
                pgd_bd = pgd_snap
            else:
                ds_pgd_bd = sorted(df_src[COT_TEN_PGD].dropna().unique().tolist()) if COT_TEN_PGD in df_src.columns else []
                if ds_pgd_bd:
                    pgd_bd = st.selectbox(
                        "Chọn PGD để xem Xã/phường",
                        options=ds_pgd_bd,
                        index=_index_of_option(ds_pgd_bd, pgd_pref),
                        key=f"{scope_key}bd_pgd",
                    )
                else:
                    pgd_bd = None
            df_scope_xa = df_src[df_src[COT_TEN_PGD] == pgd_bd].copy() if pgd_bd and COT_TEN_PGD in df_src.columns else df_src
            ds_xa_bd = sorted(df_scope_xa[COT_TEN_XA].dropna().unique().tolist()) if COT_TEN_XA in df_scope_xa.columns else []
            if not ds_xa_bd:
                df_snap_ut = pd.DataFrame()
            else:
                xa_chon = st.selectbox(
                    "Chọn Xã/phường",
                    options=ds_xa_bd,
                    index=_index_of_option(ds_xa_bd, xa_pref),
                    key=f"{scope_key}bd_xa",
                )
                ten_doi_tuong = f"{pgd_bd} - {xa_chon}" if pgd_bd else xa_chon
                current_name = "BienDongTheoXa"
                df_snap_ut = doc_uy_thac_snapshot_multi(
                    tuple(ky_chon),
                    ten_pgd=pgd_bd,
                    cap_tong_hop="XA",
                    ten_xa=xa_chon,
                )
        else:
            df_snap_ut = doc_uy_thac_snapshot_multi(tuple(ky_chon), ten_pgd=pgd_snap)

        df_bd = tinh_bien_dong_snapshot(df_snap_ut)
        current_export = df_bd.rename(columns={
            "ky": "Kỳ",
            "tong_du_no": "Tổng dư nợ (triệu đồng)",
            "du_no_qh": "NQH (triệu đồng)",
            "so_ho": "Số KH",
            "so_ku": "Số món vay",
            "so_to": "Số Tổ",
            "lai_ton": "Lãi tồn (triệu đồng)",
            "so_du_tg": "Tiền gửi (triệu đồng)",
            "ty_le_nqh": "Tỷ lệ NQH",
            "delta_tong_du_no": "Δ Dư nợ (triệu đồng)",
            "delta_du_no_qh": "Δ NQH (triệu đồng)",
            "delta_so_ho": "Δ Số KH",
            "delta_so_ku": "Δ Số món vay",
            "delta_so_to": "Δ Số Tổ",
            "delta_lai_ton": "Δ Lãi tồn (triệu đồng)",
            "delta_so_du_tg": "Δ Tiền gửi (triệu đồng)",
        })
        if not current_export.empty:
            current_export.insert(1, "Đối tượng", ten_doi_tuong)
        keep_cols = [c for c in [
            "Kỳ", "Đối tượng", "Tổng dư nợ (triệu đồng)", "Δ Dư nợ (triệu đồng)",
            "NQH (triệu đồng)", "Δ NQH (triệu đồng)", "Tỷ lệ NQH",
            "Lãi tồn (triệu đồng)", "Δ Lãi tồn (triệu đồng)",
            "Tiền gửi (triệu đồng)", "Δ Tiền gửi (triệu đồng)",
            "Số Tổ", "Δ Số Tổ", "Số KH", "Δ Số KH", "Số món vay", "Δ Số món vay",
        ] if c in current_export.columns]
        current_export = current_export[keep_cols] if keep_cols else pd.DataFrame()
        current_show = _format_bao_cao_uy_thac(current_export)
        st.caption("Nguồn: snapshot ủy thác tự động tạo sau mỗi lần merge HSTD thành công.")
        if current_name == "BienDongTheoHoi" and 0 < len(df_snap_ut) < len(ky_chon):
            st.caption(
                "⚠️ Một số kỳ cũ có thể chưa có snapshot `Hội trong PGD`; "
                "chuỗi biến động hiện chỉ hiển thị các kỳ đã có dữ liệu phù hợp."
            )
        if len(ky_chon) < 2:
            st.info("Cần tối thiểu 2 kỳ snapshot để tính biến động.")

    st.markdown(
        f"**Tổng quan nhanh sau lọc:** {fmt_so(len(df_chi_tiet))} dòng chi tiết, "
        f"{fmt_so(tong_quan.get('so_to', 0))} tổ, "
        f"{fmt_so(tong_quan.get('so_kh', 0))} KH, "
        f"{fmt_ty(tong_quan.get('tong_dn', 0))} triệu đồng dư nợ."
    )
    if current_show.empty:
        st.info("Không có dữ liệu để hiển thị theo bộ lọc hiện tại.")
    else:
        st.dataframe(current_show, use_container_width=True, hide_index=True, height=420)

    with st.expander("🔎 Drill-down danh sách chi tiết theo bộ lọc hiện tại", expanded=False):
        if df_chi_tiet.empty:
            st.info("Không có dòng chi tiết phù hợp.")
        else:
            st.dataframe(
                _format_bao_cao_uy_thac(
                    df_chi_tiet.rename(
                        columns={
                            COT_TEN_PGD: "PGD",
                            COT_DVUT: "Hội đoàn thể",
                            COT_TEN_XA: "Xã/Phường",
                            COT_TEN_TO: "Tổ TK&VV",
                            COT_TEN_KH: "Khách hàng",
                            COT_SO_KU: "Số khế ước",
                            COT_TEN_CT: "Chương trình",
                            COT_TONG_DU_NO: "Dư nợ (triệu đồng)",
                            COT_DU_NO_QH: "NQH (triệu đồng)",
                            COT_SO_DU_TG: "TG TK (triệu đồng)",
                        }
                    ).head(300)
                ),
                use_container_width=True,
                hide_index=True,
                height=320,
            )

    c_export_1, c_export_2 = st.columns(2)
    buf_key = f"_{scope_key}{current_name}_buf"
    all_key = f"_{scope_key}all_reports_buf"
    with c_export_1:
        if st.button("📤 Tạo Excel báo cáo đang xem", key=f"{scope_key}gen_current"):
            st.session_state[buf_key] = xuat_excel({current_name: current_export})
        if st.session_state.get(buf_key):
            if st.download_button(
                "📥 Tải Excel báo cáo đang xem",
                data=st.session_state[buf_key],
                file_name=f"{current_name}_{date.today().strftime('%d%m%Y')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key=f"{scope_key}dl_current",
            ):
                db.ghi_audit(username, "xuat_bieu_cn", f"Báo cáo Ủy thác đang xem — {current_name}")
    with c_export_2:
        if st.button("📦 Tạo bộ báo cáo Excel", key=f"{scope_key}gen_all"):
            st.session_state[all_key] = _tao_excel_bao_cao_uy_thac(
                tong_quan=tong_quan,
                sheets={
                    "TheoHoi": df_hoi,
                    "TheoPGD": df_pgd,
                    "DieuHanhPGD": report_pgd_dh,
                    "DieuHanhHoi": report_hoi_dh,
                    "TheoXa": df_xa,
                    "TheoPGD_Hoi": df_pgd_hoi,
                    "TheoChuongTrinh": df_ct,
                    "TheoToTKVV": df_to,
                    "DiemNongXa": report_xa_diem_nong,
                    "DiemNongTo": report_to_diem_nong,
                    "XepHangChatLuong": report_xh_bundle,
                    "CanhBaoTrongDiem": report_cb_bundle,
                    "BienDongNhieuKy": current_export if current_name.startswith("BienDong") else report_bd_bundle,
                    "DanhSachChiTiet": df_chi_tiet,
                },
            )
        if st.session_state.get(all_key):
            if st.download_button(
                "📥 Tải bộ báo cáo Excel",
                data=st.session_state[all_key],
                file_name=f"BaoCaoUyThac_{date.today().strftime('%d%m%Y')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key=f"{scope_key}dl_all",
            ):
                db.ghi_audit(username, "xuat_bieu_cn", "Bộ báo cáo số liệu Ủy thác")

    st.markdown("**Xuất PDF**")
    st.caption(
        "PDF được tạo trực tiếp bằng ReportLab, không phụ thuộc Microsoft Word; "
        "các cột tiền được quy đổi đúng từ VND sang triệu đồng."
    )
    pham_vi_pdf = pgd_scope or pgd_user or TEN_CHI_NHANH_HIEN_THI
    ngay_so_lieu_pdf = lay_ngay_so_lieu(df_src)
    bo_loc_pdf: list[str] = []
    filter_labels = {
        COT_TEN_PGD: "PGD",
        COT_DVUT: "Hội đoàn thể",
        COT_TEN_XA: "Xã/Phường",
        COT_TEN_CT: "Chương trình",
    }
    for col, value in bo_loc_ct.items():
        if value not in (None, "", "(Tất cả)"):
            bo_loc_pdf.append(f"{filter_labels.get(col, col)}: {value}")
    if chi_nqh:
        bo_loc_pdf.append("Chỉ khoản có NQH")
    if chi_lai_ton:
        bo_loc_pdf.append("Chỉ khoản có lãi tồn")
    pdf_context = "|".join([
        current_name,
        pham_vi_pdf,
        *bo_loc_pdf,
        str(len(df_loc)),
        str(float(tong_quan.get("tong_dn", 0) or 0)),
    ])
    pdf_token = uuid.uuid5(uuid.NAMESPACE_URL, pdf_context).hex[:12]
    pdf_current_key = f"_{scope_key}{current_name}_{pdf_token}_pdf_buf"
    pdf_all_key = f"_{scope_key}dieu_hanh_{pdf_token}_pdf_buf"

    pdf_col_1, pdf_col_2 = st.columns(2)
    with pdf_col_1:
        if st.button(
            "📄 Tạo PDF báo cáo đang xem",
            key=f"{scope_key}gen_current_pdf",
            disabled=current_export.empty,
            use_container_width=True,
        ):
            try:
                with st.spinner("Đang tạo PDF báo cáo đang xem..."):
                    st.session_state[pdf_current_key] = tao_pdf_bao_cao_dang_xem(
                        df=current_export,
                        ten_bao_cao=report_type,
                        tong_quan=tong_quan_dh,
                        pham_vi=pham_vi_pdf,
                        ngay_so_lieu=ngay_so_lieu_pdf,
                        nguoi_xuat=username,
                        bo_loc=bo_loc_pdf,
                    )
                st.success("Đã tạo PDF báo cáo đang xem.")
            except Exception as e:
                logger.error("_render_bao_cao_so_lieu: tạo PDF đang xem thất bại — %s", e, exc_info=True)
                st.error(f"❌ Không thể tạo PDF báo cáo đang xem: {e}")
        if st.session_state.get(pdf_current_key):
            if st.download_button(
                "📥 Tải PDF báo cáo đang xem",
                data=st.session_state[pdf_current_key],
                file_name=f"{current_name}_{date.today().strftime('%d%m%Y')}.pdf",
                mime="application/pdf",
                key=f"{scope_key}dl_current_pdf",
                use_container_width=True,
            ):
                db.ghi_audit(username, "xuat_bieu_cn", f"PDF Ủy thác đang xem — {current_name}")
    with pdf_col_2:
        if st.button(
            "📚 Tạo PDF điều hành Ủy thác",
            key=f"{scope_key}gen_dieu_hanh_pdf",
            disabled=df_loc.empty,
            use_container_width=True,
        ):
            try:
                with st.spinner("Đang tổng hợp PDF điều hành nhiều phần..."):
                    st.session_state[pdf_all_key] = tao_pdf_dieu_hanh_uy_thac(
                        tong_quan=tong_quan_dh,
                        pham_vi=pham_vi_pdf,
                        ngay_so_lieu=ngay_so_lieu_pdf,
                        nguoi_xuat=username,
                        bo_loc=bo_loc_pdf,
                        theo_hoi=report_hoi_pdf,
                        dieu_hanh_pgd=report_pgd_dh,
                        diem_nong_xa=report_xa_diem_nong,
                        diem_nong_to=report_to_diem_nong,
                        canh_bao=report_cb_bundle,
                        to_da_hoi=report_to_da_hoi_pdf,
                        bien_dong=report_bd_bundle,
                    )
                st.success("Đã tạo bộ PDF điều hành Ủy thác.")
            except Exception as e:
                logger.error("_render_bao_cao_so_lieu: tạo PDF điều hành thất bại — %s", e, exc_info=True)
                st.error(f"❌ Không thể tạo PDF điều hành: {e}")
        if st.session_state.get(pdf_all_key):
            if st.download_button(
                "📥 Tải PDF điều hành Ủy thác",
                data=st.session_state[pdf_all_key],
                file_name=f"BaoCaoDieuHanhUyThac_{date.today().strftime('%d%m%Y')}.pdf",
                mime="application/pdf",
                key=f"{scope_key}dl_dieu_hanh_pdf",
                use_container_width=True,
            ):
                db.ghi_audit(username, "xuat_bieu_cn", "PDF điều hành Ủy thác")


# ══════════════════════════════════════════════════════════════════════════════
# SUB-TAB RENDERERS
# ══════════════════════════════════════════════════════════════════════════════

def _render_theo_doi_bc_th(pgd_user: str | None,
                            username: str, role: str) -> None:
    """Sub-tab 7 — Theo dõi tiến độ xử lý kiến nghị + xuất Mẫu 04/BC-TH."""
    st.markdown("#### 📊 Theo dõi tiến độ & Báo cáo tổng hợp (Mẫu 04/BC-TH)")
    slug = pgd_slug(pgd_user) if pgd_user else "cn"
    key_prefix = f"uyt_td_{slug}_"

    # ── Section 1: Theo dõi ────────────────────────────────────────────────
    st.markdown("##### I. Theo dõi tiến độ xử lý kiến nghị")

    tc1, tc2, tc3 = st.columns(3)
    nam_td = int(tc1.number_input(
        "Năm", value=date.today().year,
        min_value=2020, max_value=2035, step=1, key=f"{key_prefix}nam",
    ))
    loai_td = tc2.selectbox(
        "Loại", ["Tất cả", "BB-CT (cấp tỉnh)", "BB-CX (cấp xã)"], key=f"{key_prefix}loai"
    )
    tt_td = tc3.selectbox(
        "Trạng thái",
        ["Tất cả", "Chờ xử lý", "Đã xử lý", "Không tồn tại"],
        key=f"{key_prefix}tt",
    )
    don_vi_filter = st.text_input(
        "Tìm đơn vị được kiểm tra",
        placeholder="Nhập tên đơn vị hoặc cụm từ cần lọc",
        key=f"{key_prefix}don_vi_filter",
    ).strip().lower()

    # Load records
    all_records: list[dict] = doc_bien_ban_theo_nam(nam=nam_td, pgd_user=pgd_user)

    # Filter theo loại
    if "BB-CT" in loai_td:
        all_records = [r for r in all_records if r.get("loai") == "CT"]
    elif "BB-CX" in loai_td:
        all_records = [r for r in all_records if r.get("loai") == "CX"]

    # Filter theo trạng thái
    tt_map = {"Chờ xử lý": "cho_xu_ly", "Đã xử lý": "da_xu_ly",
              "Không tồn tại": "khong_ton_tai"}
    if tt_td != "Tất cả":
        all_records = [r for r in all_records if r.get("trang_thai") == tt_map.get(tt_td)]
    if don_vi_filter:
        all_records = [
            r for r in all_records
            if don_vi_filter in str(r.get("ten_don_vi", "") or "").lower()
        ]

    if not all_records:
        st.info("Chưa có biên bản nào trong kỳ này.")
    else:
        tong_hop_td = tong_hop_kien_nghi(all_records, ngay_ref=date.today())
        k1, k2, k3, k4, k5 = st.columns(5)
        k1.metric("Tổng biên bản", fmt_so(tong_hop_td["tong"]))
        k2.metric("Chờ xử lý", fmt_so(tong_hop_td["cho_xu_ly"]))
        k3.metric("Đã xử lý", fmt_so(tong_hop_td["da_xu_ly"]))
        k4.metric("Quá hạn", fmt_so(tong_hop_td["qua_han"]))
        k5.metric("Sắp đến hạn", fmt_so(tong_hop_td["sap_den_han"]))

        df_td_raw = tao_bang_theo_doi_kien_nghi(all_records, ngay_ref=date.today())
        df_td = _hien_thi_bang_theo_doi(df_td_raw)
        st.dataframe(
            df_td.drop(columns=["ID"]),
            use_container_width=True, hide_index=True,
        )

        td_buf_key = f"_{key_prefix}theo_doi_buf"
        if st.button("📤 Tạo Excel theo dõi kiến nghị", key=f"{key_prefix}gen_td_excel"):
            st.session_state[td_buf_key] = xuat_excel(
                {"TheoDoiKienNghi": df_td_raw.drop(columns=["KV Key", "Loại"], errors="ignore")}
            )
        if st.session_state.get(td_buf_key):
            if st.download_button(
                "📥 Tải Excel theo dõi kiến nghị",
                data=st.session_state[td_buf_key],
                file_name=f"TheoDoiKienNghi_{nam_td}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key=f"{key_prefix}dl_td_excel",
            ):
                db.ghi_audit(username, "xuat_bieu_cn", f"Theo dõi kiến nghị Ủy thác năm {nam_td}")

        # Cập nhật trạng thái (chỉ CN role)
        if la_phan_he_cn(role):
            st.markdown("**Cập nhật trạng thái xử lý:**")
            cho_xu_ly = [r for r in all_records if r.get("trang_thai") == "cho_xu_ly"]
            if not cho_xu_ly:
                st.success("✅ Tất cả kiến nghị đã được xử lý.")
            else:
                opt_map = {
                    f"{fmt_ngay(r.get('ngay_kt',''))} — {r.get('ten_don_vi','')} [{r.get('id','')}]": r
                    for r in cho_xu_ly
                }
                chon_label = st.selectbox(
                    "Chọn biên bản cần cập nhật",
                    options=[""] + list(opt_map.keys()),
                    key=f"{key_prefix}chon_label",
                )
                if chon_label:
                    target = opt_map[chon_label]
                    ket_qua_xl = st.text_area(
                        "Kết quả xử lý", height=60, key=f"{key_prefix}kq_xl"
                    )
                    if st.button("✅ Đánh dấu đã xử lý", key=f"{key_prefix}btn_xl"):
                        kv_key_t = target.get("kv_key", "")
                        if kv_key_t:
                            ok = cap_nhat_trang_thai_bien_ban(
                                kv_key=kv_key_t,
                                rec_id=str(target.get("id", "")),
                                ket_qua_xu_ly=ket_qua_xl,
                                username=username,
                                ten_don_vi=str(target.get("ten_don_vi", "") or ""),
                            )
                            if ok:
                                st.success("✅ Đã cập nhật trạng thái!")
                                st.rerun()
                            else:
                                st.error("⚠️ Không tìm thấy biên bản để cập nhật (dữ liệu có thể đã thay đổi).")

    st.divider()

    # ── Section 2: Xuất BC-TH ──────────────────────────────────────────────
    st.markdown("##### II. Xuất Báo cáo tổng hợp (Mẫu 04/BC-TH)")

    all_for_bc: list[dict] = []
    all_for_bc = doc_bien_ban_theo_nam(nam=nam_td, pgd_user=pgd_user)

    if not all_for_bc:
        st.info("Không có biên bản nào để lập báo cáo tổng hợp.")
        return

    opt_bc = {
        f"[{'02/BB-CT' if r.get('loai')=='CT' else '03/BB-CX'}] "
        f"{fmt_ngay(r.get('ngay_kt',''))} — {r.get('ten_don_vi','')}": r
        for r in all_for_bc
    }
    chon_bc = st.multiselect(
        "Chọn biên bản đưa vào báo cáo tổng hợp",
        options=list(opt_bc.keys()), key=f"{key_prefix}bcth_chon",
    )
    if not chon_bc:
        st.info("Chọn ít nhất 1 biên bản để tạo báo cáo.")
        return

    ds_chon = [opt_bc[k] for k in chon_bc]

    with st.form(f"{key_prefix}form_bc_th"):
        st.markdown("**Thông tin báo cáo:**")
        bc1, bc2 = st.columns(2)
        don_vi_kt_bc  = bc1.text_input("Đơn vị kiểm tra", key=f"{key_prefix}bcth_dvkt")
        truong_doan_bc = bc1.text_input("Trưởng đoàn kiểm tra", key=f"{key_prefix}bcth_td")
        cap_uy        = bc1.text_input("Cấp ủy, chính quyền tham dự (nếu có)", key=f"{key_prefix}bcth_capuy")
        dia_danh_bc   = bc2.text_input("Địa danh ký", placeholder="Biên Hòa", key=f"{key_prefix}bcth_dd")
        ngay_bc       = bc2.date_input(
            "Ngày báo cáo",
            value=date.today(),
            format="DD/MM/YYYY",
            key=f"{key_prefix}bcth_ngay",
        )
        noi_dung_kt   = st.text_area(
            "III. Nội dung kiểm tra",
            value="Theo Phụ lục I văn bản số 727/HD-NHCS ngày 11/02/2026.",
            height=60, key=f"{key_prefix}bcth_ndkt",
        )
        st.markdown("**IV. Đánh giá & Kiến nghị:**")
        r1, r2 = st.columns(2)
        nx_ctxh    = r1.text_area("Nhận xét đối với CT-XH",       height=60, key=f"{key_prefix}bcth_nx_ctxh")
        nx_to      = r2.text_area("Nhận xét đối với Tổ TK&VV",    height=60, key=f"{key_prefix}bcth_nx_to")
        nx_to_vien = r1.text_area("Nhận xét đối với tổ viên",     height=60, key=f"{key_prefix}bcth_nx_tov")
        kn_ctxh    = r2.text_area("Kiến nghị với CT-XH",          height=60, key=f"{key_prefix}bcth_kn_ctxh")
        kn_nhcs    = r1.text_area("Kiến nghị với NHCSXH",         height=60, key=f"{key_prefix}bcth_kn_nhcs")
        kn_cap_tren = r2.text_area("Kiến nghị với CT-XH cấp trên", height=60, key=f"{key_prefix}bcth_kn_ct")
        submitted_bc = st.form_submit_button("📄 Tạo Báo cáo tổng hợp Word", type="primary")

    if submitted_bc:
        du_lieu_bc, ten_file = build_payload_bc_th(
            don_vi_kt=don_vi_kt_bc, truong_doan=truong_doan_bc,
            cap_uy=cap_uy, dia_danh=dia_danh_bc, ngay_bc=ngay_bc,
            noi_dung_kt=noi_dung_kt,
            nx_ctxh=nx_ctxh, nx_to=nx_to, nx_to_vien=nx_to_vien,
            kn_ctxh=kn_ctxh, kn_nhcs=kn_nhcs, kn_cap_tren=kn_cap_tren,
            nam_td=nam_td,
        )
        with st.spinner("Đang tạo file..."):
            docx_bytes = tao_word_uythac_bc_th(du_lieu_bc, ds_chon)
        _download_word_pdf_pair(docx_bytes, ten_file, f"{key_prefix}bcth_")
        db.ghi_audit(username, "xuat_bc_th",
                      f"Báo cáo tổng hợp năm {nam_td} — {len(ds_chon)} biên bản")


# ══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

from tabs.base_tab import TabContext


def render(tab: DeltaGenerator | None = None, **kwargs) -> None:
    """Entry point — dùng chung cho ws_operation và ws_management."""
    ctx = TabContext(tab, **kwargs)
    _df_full = kwargs.get("df_full")
    df_full = _df_full if isinstance(_df_full, pd.DataFrame) else None
    df = kwargs.get("df")
    if (df is None or getattr(df, "empty", True)) and df_full is not None and not df_full.empty:
        df = df_full
    if (df is None or getattr(df, "empty", True)) and os.path.exists(CACHE_HSTD):
        df_cache = _doc_hstd_cached(ts_file(CACHE_HSTD))
        df = df_cache
    pgd_user = ctx.pgd_user
    username = kwargs.get("username", "unknown")
    role     = normalize_role(str(kwargs.get("role", "user") or "user"))

    with ctx:
        st.subheader("🤝 Ủy thác — Hội đoàn thể")
        st.caption(
            f"Thiết kế lại theo hướng ưu tiên báo cáo số liệu ủy thác cho "
            f"{TEN_CHI_NHANH_HIEN_THI}; các mẫu biểu kiểm tra được gom về khu riêng."
        )
        if df is None or df.empty:
            if os.path.exists(CACHE_HSTD):
                df_cache2 = _doc_hstd_cached(ts_file(CACHE_HSTD))
                if df_cache2 is not None and not df_cache2.empty and len(df_cache2.columns) < 15:
                    st.error(
                        f"⚠️ Dữ liệu HSTD cache chưa đầy đủ (chỉ {len(df_cache2.columns)} cột) — "
                        "cần upload/merge HSTD lại để dùng các chức năng Ủy thác."
                    )
        _ut_labels = [
            "📊 Tổng quan Ủy thác",
            "📑 Báo cáo số liệu",
            "📌 Theo dõi kiến nghị",
        ]
        _ut_sel = st.radio("", range(len(_ut_labels)), format_func=lambda i: _ut_labels[i],
                           horizontal=True, key="ut_sub_tab", label_visibility="collapsed")
        st.divider()
        if _ut_sel == 0:
            _render_tong_quan_uy_thac(df, pgd_user)
        elif _ut_sel == 1:
            _render_bao_cao_so_lieu(df, pgd_user, username)
        elif _ut_sel == 2:
            _render_theo_doi_bc_th(pgd_user, username, role)
