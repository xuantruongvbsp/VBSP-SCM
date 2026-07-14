"""Tab Ủy thác — Theo dõi Hội đoàn thể và các mẫu biểu kiểm tra."""


from __future__ import annotations
from logger import get_logger
logger = get_logger(__name__)

import io, os, pickle, uuid
from datetime import date, datetime, timedelta
import pandas as pd
import streamlit as st
from streamlit.delta_generator import DeltaGenerator

import db
from auth import la_phan_he_cn, normalize_role
from data.core import ts_file
from data.pgd import pgd_slug
from config import (
    COT_TEN_PGD, COT_MA_KH, COT_TEN_KH, COT_SO_KU, COT_TEN_CT,
    COT_TONG_DU_NO, COT_DU_NO_QH, COT_LAI_TON, COT_LAI_TON_QH,
    COT_SO_DU_TG, COT_NGAY_VAY, COT_TEN_TO, COT_DVUT,
    COT_TEN_XA, COT_TEN_THON, COT_MUC_VAY,
    TEN_CHI_NHANH_HIEN_THI, DS_PGD, PGD_XA_MAP, CACHE_HSTD,
)
from utils import fmt, fmt_bang_ty, fmt_ngay, fmt_so, fmt_ty, lay_ngay_so_lieu, xuat_excel
from services.uy_thac_service import (
    build_payload_bc_th,
    build_payload_bb_xac_minh,
    build_payload_ke_hoach,
    build_payload_mau06,
    build_payload_mau15,
    build_payload_mau16,
    cap_nhat_trang_thai_bien_ban,
    co_du_lieu_to,
    danh_sach_to_co_lai_ton,
    danh_sach_to_da_hoi,
    doc_bien_ban_theo_nam,
    doc_ds_bien_ban,
    kv_key_bb_ct_cx,
    loc_mau06,
    loc_mau15,
    loc_chi_tiet_uy_thac,
    luu_bien_ban,
    tao_bang_theo_doi_kien_nghi,
    tao_canh_bao_trong_diem,
    tinh_bien_dong_snapshot,
    tong_hop_uy_thac_theo,
    tong_hop_kien_nghi,
    tong_quan_dieu_hanh_uy_thac,
    tong_quan_uy_thac,
    tao_bao_cao_dieu_hanh_uy_thac,
    tinh_theo_dvut,
    xep_hang_chat_luong_uy_thac,
)
from snapshot_service import (
    danh_sach_ky_uy_thac,
    doc_uy_thac_snapshot_hoi_cn,
    doc_uy_thac_snapshot_hoi_pgd,
    doc_uy_thac_snapshot_multi,
)
from services.template_service import (
    docx_bytes_to_pdf,
    tao_word_uythac_bb_ct_cx,
    tao_word_uythac_bb_xac_minh,
    tao_word_uythac_bc_th,
    tao_word_uythac_ke_hoach,
    tao_word_uythac_mau06,
    tao_word_uythac_mau15,
    tao_word_uythac_mau16,
)
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
def _tinh_theo_dvut(_df_bytes: bytes) -> bytes:
    df = pickle.loads(_df_bytes)
    t = tinh_theo_dvut(df, dvut_order=DVUT_ORDER)
    return pickle.dumps(t)


@st.cache_data(show_spinner=False, ttl=300)
def _loc_mau06(_df_bytes: bytes, ngay_tu: str, ngay_den: str) -> bytes:
    df = pickle.loads(_df_bytes)
    result = loc_mau06(df, ngay_tu=ngay_tu, ngay_den=ngay_den)
    return pickle.dumps(result)


@st.cache_data(show_spinner=False, ttl=300)
def _loc_mau15(_df_bytes: bytes, ten_to: str) -> bytes:
    df = pickle.loads(_df_bytes)
    df_to = loc_mau15(df, ten_to=ten_to)
    return pickle.dumps(df_to)


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
            "⬇️ Tải Word (.docx)",
            data=docx_bytes,
            file_name=ten_file + ".docx",
            mime="application/vnd.openxmlformats-officedocument"
                 ".wordprocessingml.document",
            key=f"{key_prefix}docx",
        )
    with col2:
        with st.spinner("Đang tạo PDF..."):
            pdf_bytes = docx_bytes_to_pdf(docx_bytes)
        if pdf_bytes:
            st.download_button(
                "⬇️ Tải PDF",
                data=pdf_bytes,
                file_name=ten_file + ".pdf",
                mime="application/pdf",
                key=f"{key_prefix}pdf",
            )
        else:
            st.caption("⚠️ PDF không khả dụng — cần MS Word trên server")


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
    report_bd_bundle = tinh_bien_dong_snapshot(
        doc_uy_thac_snapshot_multi(tuple(list(reversed(danh_sach_ky_uy_thac()[:6]))), ten_pgd=pgd_scope or pgd_user)
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
        ky_chon = list(reversed(ky_all[:6]))
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

def _render_theo_dvut(df: pd.DataFrame) -> None:
    st.markdown("#### 📊 Thống kê theo Hội đoàn thể")
    if df is None or df.empty:
        st.warning("Chưa có dữ liệu."); return
    try:
        t = pickle.loads(_tinh_theo_dvut(pickle.dumps(df)))
    except Exception as e:
        logger.error("_render_theo_dvut: lỗi tính thống kê DVUT — %s", e, exc_info=True)
        st.error("⚠️ Có lỗi khi tính thống kê theo Hội đoàn thể.")
        return
    if t.empty:
        st.info("Không có dữ liệu."); return

    tong_to_unique: int | None = None
    tong_kh_unique: int | None = None
    tong_dn_unique: float | None = None
    so_to_da_hoi: int | None = None
    try:
        df_hoi = df.copy()
        if COT_DVUT in df_hoi.columns:
            df_hoi[COT_DVUT] = df_hoi[COT_DVUT].astype("string").str.strip().replace("", pd.NA)
            df_hoi = df_hoi[df_hoi[COT_DVUT].notna()].copy()

        kh_col = COT_MA_KH if COT_MA_KH in df_hoi.columns else (
            COT_SO_KU if COT_SO_KU in df_hoi.columns else None
        )
        if kh_col and not df_hoi.empty:
            kh_s = df_hoi[kh_col].astype("string").str.strip().replace("", pd.NA)
            tong_kh_unique = int(kh_s.dropna().nunique())
        if COT_TONG_DU_NO in df_hoi.columns and not df_hoi.empty:
            tong_dn_unique = float(pd.to_numeric(df_hoi[COT_TONG_DU_NO], errors="coerce").fillna(0).sum())

        if COT_TEN_TO in df.columns:
            if COT_TEN_PGD in df.columns and COT_TEN_XA in df.columns:
                to_cols = [COT_TEN_PGD, COT_TEN_XA, COT_TEN_TO]
            elif COT_TEN_PGD in df.columns:
                to_cols = [COT_TEN_PGD, COT_TEN_TO]
            elif COT_TEN_XA in df.columns:
                to_cols = [COT_TEN_XA, COT_TEN_TO]
            else:
                to_cols = [COT_TEN_TO]

            df_to = df_hoi[to_cols].copy() if not df_hoi.empty else pd.DataFrame(columns=to_cols)
            for col in to_cols:
                df_to[col] = df_to[col].astype("string").str.strip().replace("", pd.NA)
            tong_to_unique = int(df_to.dropna().drop_duplicates().shape[0])

            if COT_DVUT in df_hoi.columns:
                amb_cols = to_cols + [COT_DVUT]
                df_amb = df_hoi[amb_cols].copy()
                for col in amb_cols:
                    df_amb[col] = df_amb[col].astype("string").str.strip().replace("", pd.NA)
                amb = (
                    df_amb.dropna()
                    .drop_duplicates(amb_cols)
                    .groupby(to_cols)[COT_DVUT]
                    .nunique()
                )
                so_to_da_hoi = int((amb > 1).sum())
    except Exception as e:
        logger.error("_render_theo_dvut: lỗi tính metric tổng unique — %s", e, exc_info=True)

    tong_kh_theo_hoi = int(t.get("so_kh", pd.Series([0])).sum())
    tong_kh_hien_thi = tong_kh_unique if tong_kh_unique is not None else tong_kh_theo_hoi
    tong_dn_theo_hoi = float(t.get("tong_dn", pd.Series([0])).sum())
    tong_dn_hien_thi = tong_dn_unique if tong_dn_unique is not None else tong_dn_theo_hoi
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Hội đoàn thể", len(t))
    c2.metric(
        "Tổng Tổ TK&VV",
        fmt_so(tong_to_unique) if tong_to_unique is not None else fmt_so(int(t.get("so_to", pd.Series([0])).sum())),
    )
    c3.metric("Tổng KH", fmt_so(tong_kh_hien_thi))
    c4.metric("Tổng dư nợ (triệu đồng)", fmt(tong_dn_hien_thi))
    if so_to_da_hoi:
        st.caption(
            f"⚠️ Có {so_to_da_hoi} Tổ xuất hiện với hơn 1 Hội trong HSTD "
            "→ tổng theo từng Hội có thể lớn hơn tổng Tổ unique."
        )
    st.divider()
    hien = t.rename(columns={
        COT_DVUT: "Hội đoàn thể", "so_to": "Số Tổ",
        "so_kh": "Số KH", "tong_dn": "Dư nợ (tỷ)",
        "nqh": "NQH (tỷ)", "lai_ton": "Lãi tồn (tỷ)",
    })
    for col in ["Dư nợ (tỷ)", "NQH (tỷ)", "Lãi tồn (tỷ)"]:
        if col in hien.columns:
            hien[col] = hien[col].apply(fmt_bang_ty)
    st.dataframe(hien, use_container_width=True, hide_index=True)


def _render_ke_hoach(df: pd.DataFrame, pgd_user: str, role: str) -> None:
    st.markdown("#### 📋 Kế hoạch kiểm tra giám sát ủy thác")
    st.caption("Hội đoàn thể cấp xã lập (PGD) hoặc cấp tỉnh lập (CN). "
               "Danh sách Tổ TK&VV tự động lấy từ hệ thống.")

    if df is None or df.empty:
        st.warning("Chưa có dữ liệu.")
        return

    if (not la_phan_he_cn(role)) and not pgd_user:
        st.error("Không xác định được PGD.")
        return

    key_prefix_base = f"uyt_kh_{pgd_slug(pgd_user) if pgd_user else 'cn'}_"

    if pgd_user and not la_phan_he_cn(role):
        st.info(f"PGD: **{pgd_user}**")
        pgd_chon = pgd_user
    else:
        if COT_TEN_PGD in df.columns:
            ds_pgd = sorted(df[COT_TEN_PGD].dropna().unique().tolist())
        else:
            ds_pgd = DS_PGD
        pgd_opt = st.selectbox(
            "Chọn PGD",
            options=["(Tất cả)"] + ds_pgd,
            key=f"{key_prefix_base}pgd",
        )
        pgd_chon = None if pgd_opt == "(Tất cả)" else pgd_opt

    key_prefix = (
        f"{key_prefix_base}{pgd_slug(pgd_chon) if pgd_chon else 'all'}_"
    )

    df_src = df
    if pgd_chon and COT_TEN_PGD in df.columns:
        df_src = df[df[COT_TEN_PGD] == pgd_chon].copy()

    # Lấy danh sách Tổ từ df đã lọc
    ds_to = []
    grp = [c for c in [COT_DVUT, COT_TEN_XA, COT_TEN_TO] if c in df_src.columns]
    if grp:
        ds_to = (
            df_src[grp]
            .drop_duplicates()
            .sort_values(grp)
            .to_dict("records")
        )

    with st.form(f"{key_prefix}form"):
        c1, c2 = st.columns(2)
        don_vi_kt = c1.selectbox(
            "Hội đoàn thể kiểm tra",
            options=DVUT_ORDER,
            key=f"{key_prefix}don_vi_kt",
        )
        so_vb = c1.text_input(
            "Số văn bản",
            placeholder="VD: 12/KH-HND",
            key=f"{key_prefix}so_vb",
        )
        ds_xa_df = (
            sorted(df_src[COT_TEN_XA].dropna().unique().tolist())
            if COT_TEN_XA in df_src.columns
            else []
        )
        ds_xa_map = (
            list(PGD_XA_MAP.get(pgd_chon, []))
            if pgd_chon
            else [xa for ds in PGD_XA_MAP.values() for xa in ds]
        )
        ds_xa_kh = sorted(set(ds_xa_df) | set(ds_xa_map))
        if ds_xa_kh:
            dia_danh = c1.selectbox(
                "Địa danh (xã/phường)",
                options=ds_xa_kh,
                key=f"{key_prefix}dia_danh",
                help="Xã/phường nơi Hội đóng trụ sở — dùng làm địa danh ký văn bản",
            )
        else:
            dia_danh = c1.text_input(
                "Địa danh (xã/phường)",
                placeholder="Nhập xã/phường...",
                key=f"{key_prefix}dia_danh_txt",
            )
        nam_kh     = c2.number_input("Năm kế hoạch",
                                      value=date.today().year,
                                      min_value=2020, max_value=2035, step=1,
                                      key=f"{key_prefix}nam_kh")
        ngay_ky = c2.date_input(
            "Ngày ký",
            value=date.today(),
            format="DD/MM/YYYY",
            key=f"{key_prefix}ngay_ky",
        )
        chu_tich = c2.text_input(
            "Chủ tịch ký",
            placeholder="Họ và tên Chủ tịch Hội",
            key=f"{key_prefix}chu_tich",
        )

        st.markdown("**I. Mục đích, yêu cầu**")
        muc_dich   = st.text_area("Mục đích", height=70, key=f"{key_prefix}muc_dich")
        yeu_cau    = st.text_area("Yêu cầu", height=70, key=f"{key_prefix}yeu_cau")

        st.markdown("**II. Kế hoạch kiểm tra**")
        noi_dung_kt = st.text_area(
            "Nội dung, thời hiệu kiểm tra",
            height=70,
            key=f"{key_prefix}noi_dung_kt",
        )
        thanh_phan  = st.text_area(
            "Thành phần Đoàn kiểm tra",
            height=60,
            key=f"{key_prefix}thanh_phan",
        )
        st.info(f"📋 Hệ thống tìm thấy **{len(ds_to)}** Tổ TK&VV "
                f"— sẽ tự động điền vào bảng Đối tượng kiểm tra.")

        st.markdown("**III. Kế hoạch giám sát**")
        noi_dung_gs  = st.text_area(
            "Nội dung, thời hiệu giám sát",
            height=70,
            key=f"{key_prefix}noi_dung_gs",
        )
        phan_cong_gs = st.text_area(
            "Phân công cán bộ giám sát",
            height=60,
            key=f"{key_prefix}phan_cong_gs",
        )

        st.markdown("**IV. Tổ chức thực hiện**")
        to_chuc = st.text_area("Tổ chức thực hiện", height=60, key=f"{key_prefix}to_chuc")

        submitted = st.form_submit_button("📄 Tạo Word")

    if submitted:
        context, ten_file = build_payload_ke_hoach(
            don_vi_kt=don_vi_kt, so_vb=so_vb, dia_danh=dia_danh,
            nam_kh=int(nam_kh), ngay_ky=ngay_ky, chu_tich=chu_tich,
            muc_dich=muc_dich, yeu_cau=yeu_cau,
            noi_dung_kt=noi_dung_kt, thanh_phan=thanh_phan,
            noi_dung_gs=noi_dung_gs, phan_cong_gs=phan_cong_gs,
            to_chuc=to_chuc, ds_to=ds_to,
        )
        with st.spinner("Đang tạo file..."):
            docx_bytes = tao_word_uythac_ke_hoach(context, ds_to)
        _download_word_pdf_pair(docx_bytes, ten_file, f"{key_prefix}kh_")


def _render_mau06(df: pd.DataFrame, pgd_user: str | None) -> None:
    st.markdown("#### 📋 Mẫu 06/TD & 06A/TD — Phiếu kiểm tra sử dụng vốn")
    st.caption("Quy định: kiểm tra 100% món vay trong 30 ngày sau giải ngân. "
               "Thời điểm kiểm tra cụ thể do CBTD nhập khi đi thực địa.")
    key_prefix_base = f"uyt_m06_{pgd_slug(pgd_user) if pgd_user else 'cn'}_"
    if df is None or df.empty:
        st.warning("Chưa có dữ liệu HSTD."); return
    if len(df.columns) < 15:
        st.error(
            f"⚠️ Dữ liệu HSTD chưa đầy đủ (chỉ {len(df.columns)} cột) — không thể lập Mẫu 06/TD.\n\n"
            "Cần upload/merge lại file HSTD đúng để tạo cache đầy đủ."
        )
        return
    if COT_NGAY_VAY not in df.columns:
        st.warning(f"Thiếu cột '{COT_NGAY_VAY}' trong dữ liệu HSTD — không thể lọc giải ngân để lập Mẫu 06/TD.")
        return

    if pgd_user:
        st.info(f"PGD: **{pgd_user}**")
        pgd_chon = pgd_user
    else:
        ds_pgd = (
            sorted(df[COT_TEN_PGD].dropna().unique().tolist())
            if COT_TEN_PGD in df.columns
            else DS_PGD
        )
        pgd_opt = st.selectbox(
            "Chọn PGD",
            options=["(Tất cả)"] + ds_pgd,
            key=f"{key_prefix_base}pgd",
        )
        pgd_chon = None if pgd_opt == "(Tất cả)" else pgd_opt

    key_prefix = (
        f"{key_prefix_base}{pgd_slug(pgd_chon) if pgd_chon else 'all'}_"
    )

    df_src = df
    if pgd_chon and COT_TEN_PGD in df.columns:
        df_src = df[df[COT_TEN_PGD] == pgd_chon].copy()

    c1, c2 = st.columns(2)
    loai_mau = c1.radio("Loại mẫu", ["06/TD (bảng nhiều KH)",
                                       "06A/TD (từng KH riêng)"],
                        key=f"{key_prefix}loai")
    so_ngay  = c2.slider("Giải ngân trong N ngày qua", 7, 30, 30,
                         key=f"{key_prefix}ngay")
    st.caption("Ngày kiểm tra thực tế do Cán bộ hội đi kiểm tra ghi vào mẫu.")

    ngay_den = date.today()
    ngay_tu  = date.today() - timedelta(days=so_ngay)
    st.caption(f"📅 {ngay_tu.strftime('%d/%m/%Y')} → {ngay_den.strftime('%d/%m/%Y')}")

    try:
        raw    = _loc_mau06(pickle.dumps(df_src), str(ngay_tu), str(ngay_den))
        df_m06 = pickle.loads(raw)
    except Exception as e:
        logger.error("_render_mau06: lỗi lọc dữ liệu Mẫu 06 — %s", e, exc_info=True)
        st.error("⚠️ Có lỗi khi lọc dữ liệu Mẫu 06/TD.")
        return

    if df_m06.empty:
        st.success("✅ Không có món vay nào cần kiểm tra."); return

    tong_dn = df_m06[COT_TONG_DU_NO].sum() \
              if COT_TONG_DU_NO in df_m06.columns else 0
    ca, cb  = st.columns(2)
    ca.metric("Số món cần KT", fmt_so(len(df_m06)))
    cb.metric("Tổng dư nợ (triệu đồng)", fmt(tong_dn))
    st.dataframe(df_m06, use_container_width=True,
                 hide_index=True, height=300)

    # Form thông tin người kiểm tra
    with st.form(f"{key_prefix}form"):
        st.markdown("**Thông tin xuất mẫu:**")
        f1, f2 = st.columns(2)
        don_vi_kt = f1.selectbox(
            "Hội đoàn thể kiểm tra",
            options=DVUT_ORDER,
            key=f"{key_prefix}don_vi_kt"
        )
        ds_xa_m06 = [""] + sorted(df_m06[COT_TEN_XA].dropna().unique().tolist()) \
                    if COT_TEN_XA in df_m06.columns else [""]
        ten_xa = f1.selectbox(
            "Xã/Phường",
            options=ds_xa_m06,
            key=f"{key_prefix}ten_xa"
        )
        # Lọc Tổ theo Xã đã chọn (dùng session_state vì trong form)
        ten_xa_filter = st.session_state.get(f"{key_prefix}ten_xa", "")
        df_to_filter = df_m06[df_m06[COT_TEN_XA] == ten_xa_filter] \
                       if ten_xa_filter and COT_TEN_XA in df_m06.columns else df_m06
        ds_to_m06 = [""] + sorted(df_to_filter[COT_TEN_TO].dropna().unique().tolist()) \
                    if COT_TEN_TO in df_to_filter.columns else [""]
        ten_to = f1.selectbox(
            "Tổ TK&VV",
            options=ds_to_m06,
            key=f"{key_prefix}chon_to"
        )
        dia_ban = f1.text_input("Địa bàn kiểm tra",
                                placeholder="Ấp..., xã...",
                                key=f"{key_prefix}dia_ban")
        ngay_kt = f1.date_input(
            "Ngày kiểm tra",
            value=date.today(),
            format="DD/MM/YYYY",
            key=f"{key_prefix}ngay_kt",
        )

        can_bo_1  = f2.text_input("Cán bộ kiểm tra 1", key=f"{key_prefix}can_bo_1")
        chuc_vu_1 = f2.text_input("Chức vụ 1", key=f"{key_prefix}chuc_vu_1")
        can_bo_2  = f2.text_input("Cán bộ kiểm tra 2 (nếu có)", key=f"{key_prefix}can_bo_2")
        chuc_vu_2 = f2.text_input("Chức vụ 2 (nếu có)", key=f"{key_prefix}chuc_vu_2")

        st.markdown("**Nội dung nhận xét:**")
        nx1, nx2 = st.columns(2)
        nhan_xet_chung = nx1.text_area(
            "1. Tình hình thực hiện phương án vay vốn",
            key=f"{key_prefix}nx_chung", height=80,
        )
        so_kh_dung    = nx2.text_input("Số KH đúng mục đích", key=f"{key_prefix}so_kh_dung")
        so_tien_dung  = nx2.text_input("Số tiền đúng MĐ (triệu đ)", key=f"{key_prefix}tien_dung")
        ty_trong_dung = nx2.text_input("Tỷ trọng đúng MĐ (%)", key=f"{key_prefix}ty_dung")
        so_kh_sai     = nx2.text_input("Số KH sai mục đích", key=f"{key_prefix}so_kh_sai")
        so_tien_sai   = nx2.text_input("Số tiền sai MĐ (triệu đ)", key=f"{key_prefix}tien_sai")
        ty_trong_sai  = nx2.text_input("Tỷ trọng sai MĐ (%)", key=f"{key_prefix}ty_sai")
        bien_phap     = st.text_area("Biện pháp xử lý", key=f"{key_prefix}bien_phap", height=60)

        submitted = st.form_submit_button("📄 Tạo Word")

    if submitted:
        loai_word = "06" if "06/TD" in loai_mau else "06A"
        du_lieu_word, df_xuat, ten_file = build_payload_mau06(
            don_vi_kt=don_vi_kt, ten_xa=ten_xa, ten_to=ten_to,
            can_bo_1=can_bo_1, chuc_vu_1=chuc_vu_1,
            can_bo_2=can_bo_2, chuc_vu_2=chuc_vu_2,
            dia_ban=dia_ban, ngay_kt=ngay_kt,
            nhan_xet_chung=nhan_xet_chung,
            so_kh_dung=so_kh_dung, so_tien_dung=so_tien_dung,
            ty_trong_dung=ty_trong_dung,
            so_kh_sai=so_kh_sai, so_tien_sai=so_tien_sai,
            ty_trong_sai=ty_trong_sai,
            bien_phap=bien_phap,
            df_m06=df_m06,
            pgd_scope=pgd_chon or pgd_user or "ToanCN",
        )
        with st.spinner("Đang tạo file..."):
            docx_bytes = tao_word_uythac_mau06(du_lieu_word, df_xuat, loai=loai_word)
        _download_word_pdf_pair(docx_bytes, ten_file, f"{key_prefix}06_")


def _render_mau15(df: pd.DataFrame, pgd_user: str | None) -> None:
    st.markdown("#### 📋 Mẫu 15/TD — Danh sách đối chiếu số dư")
    st.caption("Đối chiếu nợ gốc, nợ lãi, số dư tiền gửi TK từng tổ viên.")
    key_prefix_base = f"uyt_m15_{pgd_slug(pgd_user) if pgd_user else 'cn'}_"
    if df is None or df.empty:
        st.warning("Chưa có dữ liệu HSTD."); return
    if len(df.columns) < 15:
        st.error(
            f"⚠️ Dữ liệu HSTD cache chưa đầy đủ (chỉ {len(df.columns)} cột) — "
            "không thể lập Mẫu 15/TD.\n\n"
            "Cần upload/merge lại file HSTD đúng để tạo cache đầy đủ."
        )
        return
    if COT_TEN_TO not in df.columns:
        st.warning(f"Thiếu cột '{COT_TEN_TO}' trong dữ liệu HSTD — không thể lập Mẫu 15/TD.")
        return

    if pgd_user:
        st.info(f"PGD: **{pgd_user}**")
        pgd_chon = pgd_user
    else:
        ds_pgd = (
            sorted(df[COT_TEN_PGD].dropna().unique().tolist())
            if COT_TEN_PGD in df.columns
            else DS_PGD
        )
        pgd_opt = st.selectbox(
            "Chọn PGD",
            options=["(Tất cả)"] + ds_pgd,
            key=f"{key_prefix_base}pgd",
        )
        pgd_chon = None if pgd_opt == "(Tất cả)" else pgd_opt

    key_prefix = (
        f"{key_prefix_base}{pgd_slug(pgd_chon) if pgd_chon else 'all'}_"
    )

    df_src = df
    if pgd_chon and COT_TEN_PGD in df.columns:
        df_src = df[df[COT_TEN_PGD] == pgd_chon].copy()

    # Chọn Tổ TK&VV
    if not co_du_lieu_to(df_src):
        st.warning(f"Không có dữ liệu '{COT_TEN_TO}' trong phạm vi đã chọn.")
        return
    ds_to = (
        sorted(
            df_src[COT_TEN_TO]
            .dropna()
            .astype(str)
            .str.strip()
            .replace("", pd.NA)
            .dropna()
            .unique()
            .tolist()
        )
        if COT_TEN_TO in df_src.columns
        else []
    )
    if not ds_to:
        st.warning("Không có dữ liệu Tổ TK&VV."); return

    c1, c2 = st.columns(2)
    chon_dvut = c1.selectbox("Hội đoàn thể", ["Tất cả"] + DVUT_ORDER,
                              key=f"{key_prefix}dvut")
    # Lọc Tổ theo DVUT
    df_filter = df_src.copy()
    if chon_dvut != "Tất cả" and COT_DVUT in df_filter.columns:
        df_filter = df_filter[df_filter[COT_DVUT] == chon_dvut]
    ds_to_filter = sorted(df_filter[COT_TEN_TO].dropna().unique().tolist()) \
                   if COT_TEN_TO in df_filter.columns else []
    chon_to = c2.selectbox("Tổ TK&VV", ds_to_filter, key=f"{key_prefix}to")

    if not chon_to:
        st.info("Chọn Tổ TK&VV để xem dữ liệu."); return

    try:
        df_to = pickle.loads(_loc_mau15(pickle.dumps(df_src), chon_to))
    except Exception as e:
        logger.error("_render_mau15: lỗi lọc dữ liệu Mẫu 15 — %s", e, exc_info=True)
        st.error("⚠️ Có lỗi khi lọc dữ liệu Mẫu 15/TD.")
        return

    if df_to.empty:
        st.info(f"Không có dữ liệu cho Tổ **{chon_to}**."); return

    # KPI
    tong_goc = df_to[COT_TONG_DU_NO].sum() if COT_TONG_DU_NO in df_to.columns else 0
    tong_lai = df_to["Nợ lãi"].sum() if "Nợ lãi" in df_to.columns else 0
    tong_tg  = df_to[COT_SO_DU_TG].sum() if COT_SO_DU_TG in df_to.columns else 0
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Số KH", fmt_so(len(df_to)))
    k2.metric("Tổng nợ gốc (triệu đồng)", fmt(tong_goc))
    k3.metric("Tổng nợ lãi (triệu đồng)", fmt(tong_lai))
    k4.metric("Tổng TG TK (triệu đồng)", fmt(tong_tg))
    st.dataframe(df_to, use_container_width=True, hide_index=True, height=350)

    # Tự động lấy xã và tổ trưởng từ Tổ đang chọn
    xa_cua_to = ""
    ten_to_truong = ""
    if chon_to:
        if COT_TEN_XA in df_src.columns and COT_TEN_TO in df_src.columns:
            s_xa = df_src[df_src[COT_TEN_TO] == chon_to][COT_TEN_XA].dropna()
            xa_cua_to = s_xa.iloc[0] if not s_xa.empty else ""
        for cot in ["Tên Tổ trưởng", "Tổ trưởng", "Họ tên Tổ trưởng"]:
            if cot in df_src.columns:
                s_tt = df_src[df_src[COT_TEN_TO] == chon_to][cot].dropna()
                ten_to_truong = str(s_tt.iloc[0]) if not s_tt.empty else ""
                break

    # Form xuất Word
    with st.form(f"{key_prefix}form"):
        st.markdown("**Thông tin xuất mẫu:**")
        f1, f2 = st.columns(2)
        pgd = f1.text_input(
            "PGD",
            value=pgd_chon or pgd_user or "",
            disabled=True,
            key=f"{key_prefix}pgd"
        )
        ten_xa = f1.text_input(
            "Xã/Phường",
            value=xa_cua_to,
            disabled=True,
            help="Tự động lấy theo Tổ TK&VV đã chọn",
            key=f"{key_prefix}ten_xa"
        )
        to_truong = f1.text_input(
            "Tổ trưởng",
            value=ten_to_truong,
            help="Tự động lấy từ HSTD, có thể sửa lại nếu cần",
            key=f"{key_prefix}to_truong"
        )
        ma_to     = f1.text_input("Mã Tổ")
        dia_chi   = f2.text_input("Địa chỉ Tổ")
        can_bo_kt = f2.text_input("Cán bộ đối chiếu")
        ngay_chot = f2.date_input(
            "Ngày chốt số liệu",
            value=date.today(),
            format="DD/MM/YYYY",
            key=f"{key_prefix}ngay_chot",
        )
        submitted = st.form_submit_button("📄 Tạo Word")

    if submitted:
        with st.spinner("Đang tạo file..."):
            du_lieu_word, ten_file = build_payload_mau15(
                pgd=pgd, ten_xa=ten_xa, ten_to=chon_to,
                to_truong=to_truong, ma_to=ma_to,
                dia_chi=dia_chi, can_bo_kt=can_bo_kt,
                ngay_chot=ngay_chot, pgd_scope=pgd_chon or pgd_user or "",
            )
            docx_bytes = tao_word_uythac_mau15(du_lieu_word, df_to)
        _download_word_pdf_pair(docx_bytes, ten_file, f"{key_prefix}15_")


def _render_bien_ban(df: pd.DataFrame, pgd_user: str | None) -> None:
    st.markdown("#### 📋 Biên bản kiểm tra & Xác minh")
    key_prefix_base = f"uyt_bb_{pgd_slug(pgd_user) if pgd_user else 'cn'}_"
    loai = st.radio(
        "Loại biểu mẫu",
        [
            "📋 Mẫu 16/TD — Kiểm tra CT-XH Tổ TK&VV",
            "📄 Biên bản xác minh nợ chiếm dụng",
        ],
        horizontal=True,
        key=f"{key_prefix_base}loai",
    )

    if pgd_user:
        st.info(f"PGD: **{pgd_user}**")
        pgd_chon = pgd_user
    else:
        if df is not None and (not df.empty) and COT_TEN_PGD in df.columns:
            ds_pgd = sorted(df[COT_TEN_PGD].dropna().unique().tolist())
        else:
            ds_pgd = DS_PGD
        pgd_opt = st.selectbox(
            "Chọn PGD",
            options=["(Tất cả)"] + ds_pgd,
            key=f"{key_prefix_base}pgd",
        )
        pgd_chon = None if pgd_opt == "(Tất cả)" else pgd_opt

    key_prefix = f"{key_prefix_base}{pgd_slug(pgd_chon) if pgd_chon else 'all'}_"

    if loai.startswith("📄"):
        df_src = pd.DataFrame()
    else:
        if df is None or df.empty:
            st.warning("Chưa có dữ liệu HSTD.")
            return
        df_src = df
        if pgd_chon and COT_TEN_PGD in df.columns:
            df_src = df[df[COT_TEN_PGD] == pgd_chon].copy()

    if loai.startswith("📋"):
        with st.form(f"{key_prefix}form_m16"):
            c1, c2 = st.columns(2)
            don_vi_kt = c1.selectbox("Hội đoàn thể kiểm tra", DVUT_ORDER, key=f"{key_prefix}dvkt")
            ds_xa_bb = (
                sorted(df_src[COT_TEN_XA].dropna().unique().tolist())
                if COT_TEN_XA in df_src.columns else []
            )
            ten_xa = c1.selectbox("Xã/Phường", [""] + ds_xa_bb, key=f"{key_prefix}xa")
            ten_xa_cur = st.session_state.get(f"{key_prefix}xa", "")
            df_to_filter = (
                df_src[df_src[COT_TEN_XA] == ten_xa_cur]
                if ten_xa_cur and COT_TEN_XA in df_src.columns else df_src
            )
            ds_to_bb = (
                sorted(df_to_filter[COT_TEN_TO].dropna().unique().tolist())
                if COT_TEN_TO in df_to_filter.columns else []
            )
            ten_to = c1.selectbox("Tổ TK&VV", [""] + ds_to_bb, key=f"{key_prefix}to")
            ten_thon = c1.text_input(
                "Thôn/tổ dân phố",
                help="Địa chỉ thôn của Tổ TK&VV",
                key=f"{key_prefix}thon",
            )

            # Auto-detect tổ trưởng và hội đoàn thể từ df
            _to_truong_auto = ""
            _hoi_auto = ""
            if ten_to and COT_TEN_TO in df_src.columns:
                s_tt = df_src[df_src[COT_TEN_TO] == ten_to]
                for cot_tt in ["Tên Tổ trưởng", "Tổ trưởng", "Họ tên Tổ trưởng"]:
                    if cot_tt in df_src.columns:
                        v = s_tt[cot_tt].dropna()
                        if not v.empty:
                            _to_truong_auto = str(v.iloc[0])
                            break
                if COT_DVUT in df_src.columns:
                    v = s_tt[COT_DVUT].dropna()
                    if not v.empty:
                        _hoi_auto = str(v.iloc[0])

            hoi_doan_the = c1.text_input(
                "Tổ thuộc Hội", value=_hoi_auto, key=f"{key_prefix}hoi",
                help="Hội quản lý tổ (tự điền từ dữ liệu, có thể sửa)",
            )
            to_truong = c2.text_input(
                "Tổ trưởng Tổ TK&VV", value=_to_truong_auto, key=f"{key_prefix}totruong",
            )
            to_pho = c2.text_input("Tổ phó (nếu có)", key=f"{key_prefix}topho")
            can_bo_1 = c2.text_input("Cán bộ kiểm tra 1", key=f"{key_prefix}cb1")
            chuc_vu_1 = c2.text_input("Chức vụ 1", key=f"{key_prefix}cv1")
            can_bo_2 = c2.text_input("Cán bộ kiểm tra 2 (nếu có)", key=f"{key_prefix}cb2")
            chuc_vu_2 = c2.text_input("Chức vụ 2", key=f"{key_prefix}cv2")
            ngay_kt = c2.date_input(
                "Ngày kiểm tra",
                value=date.today(),
                format="DD/MM/YYYY",
                key=f"{key_prefix}ngay",
            )

            st.markdown("**Phần I — Tình hình chung (để trống = lấy từ HSTD)**")
            pi1, pi2 = st.columns(2)
            ty_le_nqh = pi1.text_input(
                "Tỷ lệ NQH (%)", placeholder="VD: 0,0 (để trống = tự tính)",
                key=f"{key_prefix}tylnqh",
            )
            xep_loai_to = pi2.text_input(
                "Kết quả xếp loại Tổ", placeholder="VD: Loại Tốt", key=f"{key_prefix}xeploai",
            )

            st.markdown("**Phần III — Đánh giá, nhận xét**")
            so_kh_kt = st.text_input(
                "Số KH kiểm tra thực tế", placeholder="VD: 05", key=f"{key_prefix}sokh",
            )
            t1, t2 = st.columns(2)
            uu_diem  = t1.text_area("1. Ưu điểm", height=80, key=f"{key_prefix}uudiem")
            ton_tai  = t2.text_area("2. Tồn tại", height=80, key=f"{key_prefix}tontai")
            kien_nghi = st.text_area("3. Kiến nghị (nếu có)", height=70, key=f"{key_prefix}kiennghi")
            so_phieu = st.text_input(
                "Số phiếu kiểm tra kèm theo", placeholder="VD: 05", key=f"{key_prefix}sophieu",
            )
            submitted_m16 = st.form_submit_button("📄 Tạo Word", type="primary")

        if submitted_m16:
            du_lieu, df_xuat, ten_file = build_payload_mau16(
                don_vi_kt=don_vi_kt, ten_xa=ten_xa, ten_thon=ten_thon,
                ten_to=ten_to, hoi_doan_the=hoi_doan_the,
                to_truong=to_truong, to_pho=to_pho,
                can_bo_1=can_bo_1, chuc_vu_1=chuc_vu_1,
                can_bo_2=can_bo_2, chuc_vu_2=chuc_vu_2,
                ngay_kt=ngay_kt,
                ty_le_nqh=ty_le_nqh, xep_loai_to=xep_loai_to,
                so_kh_kt_thuc_te=so_kh_kt,
                uu_diem=uu_diem, ton_tai=ton_tai,
                kien_nghi=kien_nghi, so_phieu_kem_theo=so_phieu,
                df_src=df_src,
            )
            with st.spinner("Đang tạo file..."):
                docx_bytes = tao_word_uythac_mau16(du_lieu, df_xuat)
            _download_word_pdf_pair(docx_bytes, ten_file, f"{key_prefix}m16_")

        return

    if loai.startswith("📄"):
        with st.form(f"{key_prefix}form_xm"):
            c1, c2 = st.columns(2)
            ten_kh = c1.text_input("Họ tên khách hàng", key=f"{key_prefix}xm_kh")
            so_ku = c1.text_input("Số khế ước", key=f"{key_prefix}xm_sku")
            so_tien = c1.number_input(
                "Số tiền chiếm dụng (triệu đồng)",
                min_value=0.0,
                step=0.1,
                key=f"{key_prefix}xm_sotien",
            )
            can_bo_lap = c2.text_input("Cán bộ lập biên bản", key=f"{key_prefix}xm_cb")
            ngay_lap = c2.date_input(
                "Ngày lập",
                value=date.today(),
                format="DD/MM/YYYY",
                key=f"{key_prefix}xm_ngay",
            )
            ly_do = st.text_area("Lý do / Hoàn cảnh", height=80, key=f"{key_prefix}xm_lydo")
            bien_phap = st.text_area("Biện pháp xử lý", height=80, key=f"{key_prefix}xm_bien_phap")
            submitted_xm = st.form_submit_button("📄 Tạo Word", type="primary")

        if submitted_xm:
            du_lieu, ten_file = build_payload_bb_xac_minh(
                ten_kh=ten_kh, so_ku=so_ku, so_tien=so_tien,
                ly_do=ly_do, bien_phap=bien_phap,
                can_bo_lap=can_bo_lap, ngay_lap=ngay_lap,
                pgd_scope=pgd_chon or pgd_user or "ToanCN",
            )
            with st.spinner("Đang tạo file..."):
                docx_bytes = tao_word_uythac_bb_xac_minh(du_lieu)
            _download_word_pdf_pair(docx_bytes, ten_file, f"{key_prefix}xm_")
        return


def _render_bb_ct_cx(df: pd.DataFrame, pgd_user: str | None,
                     username: str, role: str) -> None:
    """Sub-tab 3 — Nhập + lưu Mẫu 02/BB-CT và 03/BB-CX với theo dõi tiến độ."""
    st.markdown("#### 📝 Biên bản kiểm tra tổ chức CT-XH (Mẫu 02/BB-CT & 03/BB-CX)")
    st.caption(
        "Nhập kết quả kiểm tra và lưu vào hệ thống để theo dõi tiến độ xử lý kiến nghị. "
        "Xuất Word/PDF trực tiếp từ dữ liệu đã lưu."
    )

    key_prefix_base = f"uyt_bbctx_{pgd_slug(pgd_user) if pgd_user else 'cn'}_"
    loai_sel = st.radio(
        "Loại biên bản",
        ["02/BB-CT — Tổ chức CT-XH cấp tỉnh", "03/BB-CX — Tổ chức CT-XH cấp xã"],
        horizontal=True, key=f"{key_prefix_base}loai",
    )
    cap = "tinh" if "CT" in loai_sel else "xa"

    c_nam, c_pgd = st.columns(2)
    nam = int(c_nam.number_input(
        "Năm", value=date.today().year,
        min_value=2020, max_value=2035, step=1, key=f"{key_prefix_base}nam",
    ))

    if pgd_user:
        scope = pgd_user
        c_pgd.info(f"Đơn vị: **{pgd_user}**")
    else:
        scope = c_pgd.selectbox(
            "PGD / Đơn vị quản lý hồ sơ",
            options=DS_PGD, key=f"{key_prefix_base}pgd_sel",
        )

    key_prefix = f"{key_prefix_base}{pgd_slug(scope) if scope else 'cn'}_"
    kv_key = kv_key_bb_ct_cx(cap=cap, scope=scope, nam=nam)

    ds_luu: list = doc_ds_bien_ban(kv_key)

    # ── Danh sách biên bản đã lưu ──────────────────────────────────────────
    if ds_luu:
        so_hieu_mau = "02/BB-CT" if cap == "tinh" else "03/BB-CX"
        st.markdown(f"##### Biên bản {so_hieu_mau} đã lưu — {scope} ({nam})")
        for bb in reversed(ds_luu):
            tt = bb.get("trang_thai", "cho_xu_ly")
            tt_label = {
                "cho_xu_ly": "🔴 Chờ xử lý",
                "da_xu_ly": "✅ Đã xử lý",
                "khong_ton_tai": "🟢 Không tồn tại",
            }.get(tt, tt)
            ngay_str = bb.get("ngay_kt", "")
            ngay_hien_thi = fmt_ngay(ngay_str)
            ten_dv = bb.get("ten_don_vi", "")
            with st.expander(
                f"[{so_hieu_mau}] {ngay_hien_thi} — {ten_dv} | {tt_label}"
            ):
                col_i1, col_i2 = st.columns(2)
                col_i1.markdown(f"**Đơn vị KT:** {bb.get('don_vi_kt', '')}")
                col_i1.markdown(f"**Trưởng đoàn:** {bb.get('truong_doan', '')}")
                col_i2.markdown(f"**Đại diện được KT:** {bb.get('dai_dien_dc', '')}")
                col_i2.markdown(f"**Hạn hoàn thành:** {fmt_ngay(bb.get('han_hoan_thanh', ''))}")
                if bb.get("kien_nghi"):
                    st.markdown(f"**Kiến nghị:** {bb['kien_nghi']}")
                if bb.get("ket_qua_xu_ly"):
                    st.markdown(f"**Kết quả xử lý:** {bb['ket_qua_xu_ly']}")

                rec_id = bb.get("id", "")
                ten_file = (
                    f"{'BB_CT' if cap == 'tinh' else 'BB_CX'}"
                    f"_{ten_dv[:20].replace(' ', '_')}"
                    f"_{ngay_str.replace('-', '')}"
                )
                ss_key = f"bbct_bytes_{rec_id}"
                if st.button("📄 Tạo Word / PDF", key=f"{key_prefix}gen_{rec_id}"):
                    st.session_state[ss_key] = tao_word_uythac_bb_ct_cx(
                        bb, cap=bb.get("loai_cap", cap)
                    )
                if ss_key in st.session_state:
                    docx_b = st.session_state[ss_key]
                    col_e1, col_e2 = st.columns(2)
                    with col_e1:
                        st.download_button(
                            "⬇️ Tải Word",
                            data=docx_b,
                            file_name=ten_file + ".docx",
                            mime="application/vnd.openxmlformats-officedocument"
                                 ".wordprocessingml.document",
                            key=f"{key_prefix}dl_{rec_id}",
                        )
                    with col_e2:
                        with st.spinner("Đang tạo PDF..."):
                            pdf_b = docx_bytes_to_pdf(docx_b)
                        if pdf_b:
                            st.download_button(
                                "⬇️ Tải PDF",
                                data=pdf_b,
                                file_name=ten_file + ".pdf",
                                mime="application/pdf",
                                key=f"{key_prefix}pdf_{rec_id}",
                            )
                        else:
                            st.caption("⚠️ PDF không khả dụng — cần MS Word trên server")
        st.divider()

    # ── Form nhập biên bản mới ─────────────────────────────────────────────
    so_hieu_label = "02/BB-CT" if cap == "tinh" else "03/BB-CX"
    st.markdown(f"##### Nhập biên bản {so_hieu_label} mới")

    with st.form(f"{key_prefix}form_{cap}_moi", clear_on_submit=True):
        st.markdown("**Thông tin chung**")
        fc1, fc2 = st.columns(2)
        dvut      = fc1.selectbox("Hội đoàn thể kiểm tra", DVUT_ORDER,  key=f"{key_prefix}dvut_{cap}")
        don_vi_kt = fc1.text_input("Tên đơn vị kiểm tra (đầy đủ)",      key=f"{key_prefix}dvkt_{cap}")
        ten_don_vi = fc1.text_input("Đơn vị được kiểm tra",              key=f"{key_prefix}dvdc_{cap}",
                                    placeholder="Hội ... xã/tỉnh ...")
        ngay_kt    = fc2.date_input(
            "Ngày kiểm tra",
            value=date.today(),
            format="DD/MM/YYYY",
            key=f"{key_prefix}ngay_{cap}",
        )
        truong_doan = fc2.text_input("Trưởng đoàn kiểm tra",             key=f"{key_prefix}td_{cap}")
        can_bo_2   = fc2.text_input("Cán bộ kiểm tra 2 (nếu có)",       key=f"{key_prefix}cb2_{cap}")
        dai_dien_dc = fc2.text_input("Đại diện đơn vị được kiểm tra",   key=f"{key_prefix}dddc_{cap}")
        chuc_vu_dc = fc2.text_input("Chức vụ đại diện",                  key=f"{key_prefix}cvdc_{cap}")

        st.markdown("**II. Kết quả thực hiện (theo Phụ lục I VB 727)**")
        muc_list = [
            ("tuyen_truyen",    "1. Công tác tuyên truyền, vận động"),
            ("kiem_tra_giam_sat", "2. Công tác kiểm tra, giám sát"),
            ("tap_huan",        "3. Công tác tập huấn"),
            ("phoi_hop_nhcs",   "4. Hoạt động phối hợp với NHCSXH"),
        ]
        if cap == "tinh":
            muc_list.append(("trach_nhiem", "5. Trách nhiệm của tổ chức CT-XH cấp tỉnh"))

        nd_results: dict[str, dict] = {}
        for field_key, ten_muc in muc_list:
            st.markdown(f"*{ten_muc}*")
            mc1, mc2 = st.columns(2)
            kq = mc1.text_area("a) Kết quả", height=60, key=f"{key_prefix}{field_key}_kq_{cap}")
            tt_nd = mc2.text_area("b) Tồn tại", height=60, key=f"{key_prefix}{field_key}_tt_{cap}")
            nd_results[field_key] = {"ket_qua": kq, "ton_tai": tt_nd}

        st.markdown("**III. Đánh giá, Nhận xét & Kiến nghị**")
        ek1, ek2 = st.columns(2)
        uu_diem     = ek1.text_area("Ưu điểm",        height=80, key=f"{key_prefix}uu_{cap}")
        ton_tai_ch  = ek2.text_area("Tồn tại chung",  height=80, key=f"{key_prefix}tt_{cap}")
        kien_nghi   = st.text_area("Kiến nghị",       height=80, key=f"{key_prefix}kn_{cap}")

        hk1, hk2 = st.columns(2)
        han_ht = hk1.date_input(
            "Hạn hoàn thành kiến nghị",
            value=date.today(),
            format="DD/MM/YYYY",
            key=f"{key_prefix}han_{cap}",
        )
        tt_sel = hk2.selectbox(
            "Trạng thái tồn tại",
            options=["cho_xu_ly", "khong_ton_tai"],
            format_func=lambda x: {
                "cho_xu_ly": "🔴 Có tồn tại — chờ xử lý",
                "khong_ton_tai": "🟢 Không có tồn tại",
            }.get(x, x),
            key=f"{key_prefix}tt_select_{cap}",
        )
        y_kien = st.text_area("IV. Ý kiến đơn vị được kiểm tra", height=60,
                               key=f"{key_prefix}ykien_{cap}")
        submitted = st.form_submit_button("💾 Lưu biên bản", type="primary")

    if submitted:
        new_id = uuid.uuid4().hex[:8]
        record = {
            "id":           new_id,
            "kv_key":       kv_key,
            "loai":         "CT" if cap == "tinh" else "CX",
            "loai_cap":     cap,
            "ngay_kt":      ngay_kt.strftime("%Y-%m-%d"),
            "dvut":         dvut,
            "don_vi_kt":    don_vi_kt,
            "ten_don_vi":   ten_don_vi,
            "truong_doan":  truong_doan,
            "can_bo_2":     can_bo_2,
            "dai_dien_dc":  dai_dien_dc,
            "chuc_vu_dc":   chuc_vu_dc,
            "dia_danh":     scope,
            **nd_results,
            "uu_diem":       uu_diem,
            "ton_tai_chung": ton_tai_ch,
            "kien_nghi":     kien_nghi,
            "han_hoan_thanh": han_ht.strftime("%Y-%m-%d"),
            "trang_thai":    tt_sel,
            "y_kien_don_vi_dc": y_kien,
            "ket_qua_xu_ly": "",
            "ngay_cap_nhat": date.today().strftime("%Y-%m-%d"),
            "nguoi_cap_nhat": username,
        }
        luu_bien_ban(kv_key=kv_key, ds_hien_tai=ds_luu, record=record, username=username)
        st.success(
            f"✅ Đã lưu biên bản {'02/BB-CT' if cap == 'tinh' else '03/BB-CX'} — {ten_don_vi}"
        )
        st.rerun()


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
