"""Tab Tra cứu hồ sơ — Phiên bản 2.0.

Bố cục:
- Bộ lọc đa tiêu chí qua render_filter_panel (tích hợp search + expander nâng cao)
- KPI chuẩn bằng kpi_row() + xuất Excel/PDF
- Bảng kết quả native (st.dataframe, chọn 1 dòng)
- Chi tiết hồ sơ mở bằng modal st.dialog
"""

from __future__ import annotations

import hashlib
import re
import streamlit as st
import pandas as pd
from collections import deque
from datetime import datetime
from typing import TYPE_CHECKING

import db
from auth import normalize_role
import plotly.graph_objects as go

from config import (
    COT_TEN_KH, COT_MA_KH, COT_SO_KU, COT_CMND, COT_SDT,
    COT_TEN_PGD, COT_TEN_XA,
    COT_TEN_CT, COT_NGUON_VON, COT_NGAY_VAY,
    COT_DU_NO_TH, COT_DU_NO_QH, COT_TONG_DU_NO, COT_DU_NO_KHOANH,
    COT_THOI_HAN, COT_LAI_SUAT, COT_MUC_VAY, COT_LAI_DA_TRA,
    COT_GOC_TRA, COT_NGAY_SINH,
    COT_NOI_CAP_CMND, COT_NGAY_CAP_CMND, COT_TINH_TRANG,
    COT_TEN_TO, COT_TEN_VC, COT_TEN_HSSV, COT_DIA_CHI,
    COT_LAI_TON, COT_SO_DU_TG, COT_PHAN_LOAI, COT_NGAY_DH,
    COT_LAI_TON_QH, COT_SO_LAN_GH, COT_MA_NHA_DAU_TU, COT_NGAY_HH_KHOANH,
)
from utils import fmt_tien, fmt_ty, xuat_excel
from tabs.base_tab import TabContext
from components.filter_panel import render_filter_panel
from components.delta_card import kpi_row
from components.export_pdf import xuat_pdf_co_chart, download_pdf_button
from data import doc_nq11_toan_cn_pgd, doc_gqvl_toan_cn
from logger import get_logger

if TYPE_CHECKING:
    from streamlit.delta_generator import DeltaGenerator


logger = get_logger(__name__)


# Role được phép ghi ghi chú CBTD (executive/user_pgd chỉ đọc).
_ROLE_GHI_CHU = {"admin_cn", "manager_cn", "chuyenvien_cn", "admin_pgd", "manager_pgd"}


# Cột tiền (đơn vị VND, hiển thị bằng fmt_ty → triệu đồng)
_MONEY_COLS = [
    COT_DU_NO_TH, COT_DU_NO_QH, COT_TONG_DU_NO,
    COT_MUC_VAY, COT_GOC_TRA, COT_LAI_DA_TRA, COT_DU_NO_KHOANH,
    COT_LAI_TON, COT_SO_DU_TG,
]

_MAX_EXPORT_EXCEL = 2000
_MAX_EXPORT_PDF = 200


def _hien_thi_nguon_von(value) -> str:
    """Chuẩn hóa hiển thị nguồn vốn từ mã số sang nhãn nghiệp vụ."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    s = str(value).strip()
    if s in {"1", "01", "1.0", "01.0", "TW"}:
        return "Trung ương"
    if s in {"2", "02", "2.0", "02.0", "ĐP", "DP"}:
        return "Địa phương"
    return s


def _mask_cmnd(v) -> str:
    """Che CMND/CCCD: giữ 3 đầu + 3 cuối."""
    s = str(v or "").strip()
    if not s or s in {"nan", "None", "NaT"}:
        return ""
    if len(s) <= 6:
        return s[0] + "*" * (len(s) - 1)
    return s[:3] + "*" * (len(s) - 6) + s[-3:]


def _mask_sdt(v) -> str:
    """Che SĐT: giữ 2 đầu + 2 cuối."""
    s = str(v or "").strip()
    if not s or s in {"nan", "None", "NaT"}:
        return ""
    if len(s) <= 4:
        return s[0] + "*" * (len(s) - 1)
    return s[:2] + "*" * (len(s) - 4) + s[-2:]


def _mask_pii_col(col: str, v) -> str:
    """Che PII theo loại cột (chỉ CMND/SĐT)."""
    if col == COT_CMND:
        return _mask_cmnd(v)
    if col == COT_SDT:
        return _mask_sdt(v)
    return str(v)


def _record_identity(row: pd.Series) -> str:
    """Định danh ổn định cho một hồ sơ trong state/UI key."""
    raw = "\x1f".join(
        str(row.get(col, "") or "").strip()
        for col in (COT_MA_KH, COT_SO_KU, COT_TEN_PGD, COT_NGAY_VAY)
    )
    raw = f"{row.name}\x1f{raw}"
    return hashlib.blake2s(raw.encode("utf-8", errors="ignore"), digest_size=8).hexdigest()


def _selection_default_for_page(
    selected_idx: int | None, start: int, end: int
) -> dict | None:
    """Đổi index tuyệt đối thành selection mặc định tương đối của trang hiện tại."""
    if selected_idx is None or not start <= selected_idx < end:
        return None
    return {"selection": {"rows": [selected_idx - start]}}


def _clamp_page(page: int, total_pages: int) -> int:
    return max(1, min(int(page), max(1, int(total_pages))))


def _change_page(delta: int, total_pages: int) -> None:
    current = int(st.session_state.get("tc2_page", 1) or 1)
    st.session_state["tc2_page"] = _clamp_page(current + delta, total_pages)


def _ui_scope(*parts) -> str:
    raw = repr(parts).encode("utf-8", errors="ignore")
    return hashlib.blake2s(raw, digest_size=10).hexdigest()


def _load_nq11_gqvl_data() -> tuple[pd.DataFrame | None, pd.DataFrame | None]:
    """Load NQ11 và GQVL từ cache (fallback khi app.py chưa nạp sẵn)."""
    df_nq11 = None
    df_gqvl = None
    try:
        df_nq11 = doc_nq11_toan_cn_pgd()
    except Exception:
        logger.error("Không đọc được dữ liệu NQ11 cho tab tra cứu", exc_info=True)
    try:
        df_gqvl = doc_gqvl_toan_cn()
    except Exception:
        logger.error("Không đọc được dữ liệu GQVL cho tab tra cứu", exc_info=True)
    return df_nq11, df_gqvl



def _so_khac_nhau(df_kia: pd.DataFrame | None, so_ku: str) -> bool:
    """Hồ sơ Số KU có thuộc bảng NQ11/GQVL không."""
    if df_kia is None or df_kia.empty:
        return False
    col = "Số khế ước" if "Số khế ước" in df_kia.columns else COT_SO_KU
    if col not in df_kia.columns:
        return False
    return str(so_ku).strip() in set(df_kia[col].dropna().astype(str).str.strip())


# Whitelist cột NQ11/GQVL hiển thị trong dialog (C6 — tránh dump 30+ cột gây tràn).
_CT_PHU_WHITELIST = (
    "dư nợ", "nợ", "vốn", "tiền", "gốc", "lãi", "giải ngân", "khoanh",
    "quá hạn", "đến hạn", "ngày", "chương trình", "mục đích", "địa chỉ",
    "xã", "huyện", "tỉnh", "mã", "số", "tình trạng", "trạng thái",
)
_CT_PHU_MAX_COLS = 12


def _render_chi_tiet_phu(df_kia: pd.DataFrame, so_ku: str, money_kw: tuple[str, ...]) -> None:
    """Render chi tiết NQ11/GQVL của 1 hồ sơ dạng 2 cột gọn (whitelist — C6)."""
    col = "Số khế ước" if "Số khế ước" in df_kia.columns else COT_SO_KU
    match = df_kia[df_kia[col].astype(str).str.strip() == str(so_ku).strip()]
    if match.empty:
        return
    row = match.iloc[0]
    skip = {"số khế ước", "mã kh", "mã khách hàng", "tên kh", "tên khách hàng"}
    # Ưu tiên cột theo whitelist; nếu không khớp → giữ cột đầu tiên (cap).
    all_cols = [c for c in match.columns if c.lower().strip() not in skip]
    wl_cols = [c for c in all_cols if any(kw in c.lower() for kw in _CT_PHU_WHITELIST)]
    show_cols = (wl_cols or all_cols)[:_CT_PHU_MAX_COLS]
    items: list[tuple[str, str]] = []
    for c in show_cols:
        val = row.get(c)
        if val is None or (isinstance(val, float) and pd.isna(val)):
            continue
        if any(kw in c.lower() for kw in money_kw):
            try:
                items.append((c, fmt_tien(float(val))))
            except (ValueError, TypeError):
                items.append((c, str(val)))
        else:
            items.append((c, str(val)))
    if items:
        c1, c2 = st.columns(2)
        for i, (k, v) in enumerate(items):
            (c1 if i % 2 == 0 else c2).markdown(f"**{k}:** {v}")
        if len(all_cols) > len(show_cols):
            st.caption(f"… và {len(all_cols) - len(show_cols)} trường khác (ẩn để gọn giao diện).")



def _tao_pdf_ho_so(
    hs: pd.Series,
    info_data: list[tuple[str, str]],
    loan_data: list[tuple[str, str]],
    username: str,
) -> bytes:
    """Tạo PDF gọn cho một hồ sơ tra cứu."""
    so_ku = str(hs.get(COT_SO_KU, "")).strip()
    ten_kh = str(hs.get(COT_TEN_KH, "—") or "—").strip()
    rows = list(info_data)
    if rows and loan_data:
        rows.append(("", ""))
    rows.extend(loan_data)
    df_pdf = pd.DataFrame(rows, columns=["Thông tin", "Giá trị"])
    return xuat_pdf_co_chart(
        df=df_pdf,
        tieu_de=f"HỒ SƠ KHÁCH HÀNG — {ten_kh}",
        nguoi_xuat=username,
        them_dong_tong=False,
        prefix_file=f"HS_{so_ku}",
    )


@st.dialog("📋 Chi tiết hồ sơ", width="large")
def _detail_dialog(
    hs: pd.Series,
    df_nq11: pd.DataFrame | None,
    df_gqvl: pd.DataFrame | None,
    username: str,
    role: str = "user",
    df_full: pd.DataFrame | None = None,
    mask_pii: bool = False,
) -> None:
    """Modal hiển thị chi tiết 1 hồ sơ."""
    so_ku = str(hs.get(COT_SO_KU, "")).strip()
    ma_kh = str(hs.get(COT_MA_KH, "")).strip()
    st.markdown(f"### {hs.get(COT_TEN_KH, '—')}")
    _record_key = _record_identity(hs)
    pdf_state_key = f"tc2_pdf_hoso_{_record_key}"

    col1, col2 = st.columns([2, 1])

    with col1:
        st.markdown("**👤 Thông tin khách hàng**")
        fields = [
            ("Mã KH", COT_MA_KH),
            ("Tên KH", COT_TEN_KH),
            ("CMND/CCCD", COT_CMND),
            ("Ngày sinh", COT_NGAY_SINH),
            ("Ngày cấp CMND", COT_NGAY_CAP_CMND),
            ("Nơi cấp CMND", COT_NOI_CAP_CMND),
            ("Số điện thoại", COT_SDT),
            ("Địa chỉ", COT_DIA_CHI),
            ("Tổ", COT_TEN_TO),
            ("Xã/Phường", COT_TEN_XA),
            ("PGD", COT_TEN_PGD),
            ("Vợ/Chồng", COT_TEN_VC),
            ("HSSV", COT_TEN_HSSV),
        ]
        info_data = []
        for label, col in fields:
            if col in hs.index:
                value = hs[col]
                if pd.notna(value) and str(value).strip():
                    info_data.append((label, _mask_pii_col(col, value) if mask_pii else str(value)))
        if info_data:
            st.dataframe(
                pd.DataFrame(info_data, columns=["Thông tin", "Giá trị"]),
                hide_index=True, width="stretch",
            )

    with col2:
        st.markdown("**💰 Thông tin khoản vay**")
        loan_fields = [
            ("Số khế ước", COT_SO_KU),
            ("Chương trình", COT_TEN_CT),
            ("Nguồn vốn", COT_NGUON_VON),
            ("Ngày vay", COT_NGAY_VAY),
            ("Thời hạn (tháng)", COT_THOI_HAN),
            ("Lãi suất (%)", COT_LAI_SUAT),
            ("Mức vay (triệu đồng)", COT_MUC_VAY),
            ("Dư nợ trong hạn (triệu đồng)", COT_DU_NO_TH),
            ("Dư nợ quá hạn (triệu đồng)", COT_DU_NO_QH),
            ("Tổng dư nợ (triệu đồng)", COT_TONG_DU_NO),
            ("Lãi tồn (triệu đồng)", COT_LAI_TON),
            ("Số dư TK 105 (triệu đồng)", COT_SO_DU_TG),
            ("Gốc đã trả (triệu đồng)", COT_GOC_TRA),
            ("Lãi đã trả (triệu đồng)", COT_LAI_DA_TRA),
            ("Tình trạng", COT_TINH_TRANG),
        ]
        loan_data = []
        for label, col in loan_fields:
            if col in hs.index:
                value = hs[col]
                if pd.notna(value):
                    if col in _MONEY_COLS:
                        formatted = fmt_ty(value)
                    elif col == COT_NGUON_VON:
                        formatted = _hien_thi_nguon_von(value)
                    else:
                        formatted = str(value)
                    loan_data.append((label, formatted))
        if loan_data:
            st.dataframe(
                pd.DataFrame(loan_data, columns=["Thông tin", "Giá trị"]),
                hide_index=True, width="stretch",
            )

    # NQ11 / GQVL
    if _so_khac_nhau(df_nq11, so_ku):
        st.success("✨ Hồ sơ thuộc Nghị Quyết 11")
        with st.expander("Chi tiết NQ11", expanded=True):
            _render_chi_tiet_phu(df_nq11, so_ku, ("dư nợ", "nợ", "vốn", "tiền", "dno", "gốc", "lãi"))

    if _so_khac_nhau(df_gqvl, so_ku):
        st.info("📋 Hồ sơ thuộc GQVL (Giải quyết Việc làm)")
        with st.expander("Chi tiết GQVL", expanded=True):
            _render_chi_tiet_phu(df_gqvl, so_ku, ("dư nợ", "nợ", "vốn", "tiền", "giải ngân", "gốc", "lãi"))

    # Ghi chú CBTD
    st.divider()
    st.markdown("**📝 Ghi chú CBTD**")
    _note = db.doc_ghi_chu_kv(so_ku) if so_ku else None
    if _note:
        st.info(f"✏️ {_note.get('ghi_chu', '')}  \n*— {_note.get('username', '')} · {_note.get('updated_at', '')}*")
    else:
        st.caption("Chưa có ghi chú.")
    if normalize_role(role) in _ROLE_GHI_CHU:
        _ghi_chu_moi = st.text_area(
            "Nội dung ghi chú",
            value=_note.get("ghi_chu", "") if _note else "",
            key=f"tc2_ghi_chu_{_record_key}",
            height=90,
        )
        if st.button("💾 Lưu ghi chú", key=f"tc2_luu_ghi_chu_{_record_key}"):
            if db.luu_ghi_chu_kv(so_ku, _ghi_chu_moi.strip(), username):
                st.success("Đã lưu ghi chú.")
                st.rerun()
            else:
                st.error("Không lưu được ghi chú.")
    else:
        st.caption("🔒 Bạn chỉ có quyền xem ghi chú.")

    # Các khế ước khác cùng khách hàng
    if df_full is not None and not df_full.empty and ma_kh and COT_MA_KH in df_full.columns:
        _other = df_full[df_full[COT_MA_KH].astype(str).str.strip() == ma_kh]
        _other = _other[_other[COT_SO_KU].astype(str).str.strip() != so_ku] if COT_SO_KU in _other.columns else _other
        if not _other.empty:
            st.markdown(f"**🏦 Các khế ước khác của khách hàng này ({len(_other)})**")
            _other_cols = [c for c in [COT_SO_KU, COT_TEN_CT, COT_NGAY_VAY, COT_TONG_DU_NO, COT_TINH_TRANG] if c in _other.columns]
            st.dataframe(_other[_other_cols], hide_index=True, width="stretch")

    st.divider()
    _df_excel_hs = hs.to_frame().T
    if mask_pii:
        _df_excel_hs = _mask_df_pii(_df_excel_hs)
    excel_data = xuat_excel({f"HS_{so_ku or 'khach_hang'}": _df_excel_hs})
    col_xl, col_pdf = st.columns(2)
    with col_xl:
        st.download_button(
            "📥 Xuất Excel hồ sơ",
            data=excel_data,
            file_name=f"ho_so_{so_ku}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            width="stretch",
            key=f"tc2_dialog_export_{_record_key}",
        )
    with col_pdf:
        if st.button("📄 Xuất PDF hồ sơ", width="stretch", key=f"tc2_make_pdf_{_record_key}"):
            try:
                with st.spinner("Đang tạo PDF hồ sơ..."):
                    st.session_state[pdf_state_key] = _tao_pdf_ho_so(hs, info_data, loan_data, username)
                st.success("Đã tạo PDF hồ sơ. Bấm nút tải bên dưới để tải file.")
            except Exception:
                st.session_state.pop(pdf_state_key, None)
                st.error("Không tạo được PDF hồ sơ.")
        pdf_bytes = st.session_state.get(pdf_state_key)
        if pdf_bytes:
            download_pdf_button(
                pdf_bytes=pdf_bytes,
                filename=f"ho_so_{so_ku}.pdf",
                label="📥 Tải PDF hồ sơ",
                key=f"tc2_dialog_pdf_{_record_key}",
            )


def _render_kpi_va_xuat(
    df_f: pd.DataFrame,
    nq11_count: int,
    gqvl_count: int,
    qh_count: int,
    tong_no: float,
    username: str,
    mask_pii: bool = False,
    chart_figs: list | None = None,
) -> None:
    """KPI hàng đầu + nút xuất Excel/PDF."""
    kpi_row(
        [
            {"label": "Hồ sơ", "value": len(df_f), "icon": "📁"},
            {"label": "Tổng dư nợ", "value": fmt_ty(tong_no), "suffix": "tr", "icon": "💰",
             "help": "Tổng dư nợ kết quả lọc (đơn vị: triệu đồng)"},
            {"label": "NQ11", "value": nq11_count, "icon": "✨"},
            {"label": "GQVL", "value": gqvl_count, "icon": "📋"},
            {"label": "Quá hạn (món)", "value": qh_count, "icon": "⚠️",
             "help": "Đơn vị: món vay có dư nợ quá hạn > 0, không phải số khách hàng."},
        ],
        num_columns=5,
    )

    col_xl, col_pdf, _ = st.columns([1, 1, 3])

    with col_xl:
        if not df_f.empty and len(df_f) <= _MAX_EXPORT_EXCEL:
            def _make_excel() -> bytes:
                # Mask PII khi toggle bật (3.6) + sheet "Ghi chú bảo mật".
                df_xuat = _mask_df_pii(df_f) if mask_pii else df_f
                sheets = {"KetQua_TraCuu": df_xuat}
                sheets["Ghi_chu_bao_mat"] = pd.DataFrame(
                    [
                        ("Người xuất", username),
                        ("Thời điểm", datetime.now().strftime("%d/%m/%Y %H:%M:%S")),
                        ("Số dòng", f"{len(df_xuat):,}"),
                        ("Ẩn CMND/SĐT", "Có" if mask_pii else "Không"),
                    ],
                    columns=["Mục", "Giá trị"],
                )
                return xuat_excel(sheets)

            st.download_button(
                "📊 Excel",
                data=_make_excel,
                file_name="ket_qua_tra_cuu.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                width="stretch",
                key="tc2_export_excel",
            )
        else:
            st.button(
                f"📊 Excel ({len(df_f):,} — lọc thêm)",
                disabled=True, width="stretch", key="tc2_export_excel",
            )

    with col_pdf:
        if not df_f.empty and len(df_f) <= _MAX_EXPORT_PDF:
            pdf_cols = [c for c in [
                COT_SO_KU, COT_TEN_KH, COT_TEN_PGD, COT_TEN_CT,
                COT_NGAY_VAY, COT_DU_NO_TH, COT_DU_NO_QH, COT_TONG_DU_NO, COT_TINH_TRANG,
            ] if c in df_f.columns]
            cols_tien = [c for c in [COT_DU_NO_TH, COT_DU_NO_QH, COT_TONG_DU_NO] if c in pdf_cols]

            def _make_pdf() -> bytes:
                # Lazy: chỉ tạo PDF khi user bấm tải (tránh tạo PDF mỗi rerun — B3).
                # Biểu đồ cũng chỉ dựng tại thời điểm tải nếu expander chưa mở.
                pdf_figs = chart_figs if chart_figs is not None else _build_charts(df_f)
                return xuat_pdf_co_chart(
                    df=df_f[pdf_cols],
                    tieu_de="KẾT QUẢ TRA CỨU HỒ SƠ",
                    nguoi_xuat=username,
                    figs=pdf_figs,
                    cols_tien=cols_tien,
                    them_dong_tong=False,
                )

            st.download_button(
                "📄 PDF",
                data=_make_pdf,
                file_name="ket_qua_tra_cuu.pdf",
                mime="application/pdf",
                width="stretch",
                key="tc2_export_pdf",
            )
        else:
            lbl = f"📄 PDF ({len(df_f):,} — lọc thêm)" if len(df_f) > _MAX_EXPORT_PDF else "📄 PDF"
            st.button(lbl, disabled=True, width="stretch", key="tc2_export_pdf")



# Danh mục cột hiển thị: (cột nguồn, nhãn, is_money) — is_money → chia 1e6 giữ numeric
_VIEW_CATALOG = [
    (COT_SO_KU, "Số khế ước", False),
    (COT_TEN_KH, "Tên KH", False),
    (COT_TEN_PGD, "PGD", False),
    (COT_TEN_XA, "Xã/Phường", False),
    (COT_TEN_TO, "Tên tổ", False),
    (COT_TEN_CT, "Chương trình", False),
    (COT_TONG_DU_NO, "Tổng dư nợ (triệu)", True),
    (COT_LAI_TON, "Lãi tồn (triệu)", True),
    (COT_DU_NO_QH, "Dư nợ QH (triệu)", True),
    (COT_LAI_TON_QH, "Lãi tồn QH (triệu)", True),
    (COT_DU_NO_KHOANH, "Dư nợ khoanh (triệu)", True),
    (COT_SO_DU_TG, "Số dư TK 105 (triệu)", True),
    (COT_MUC_VAY, "Mức vay (triệu)", True),
    (COT_PHAN_LOAI, "Phân loại", False),
    (COT_NGAY_VAY, "Ngày vay", False),
    (COT_NGAY_DH, "Ngày đến hạn", False),
    (COT_NGAY_HH_KHOANH, "Ngày HH khoanh", False),
    (COT_SO_LAN_GH, "Số lần GH", False),
    (COT_NGUON_VON, "Nguồn vốn", False),
    (COT_MA_NHA_DAU_TU, "Mã NĐT", False),
    (COT_TINH_TRANG, "Tình trạng", False),
]

_DEFAULT_VISIBLE = {
    COT_SO_KU, COT_TEN_KH, COT_TEN_PGD, COT_TEN_XA, COT_TEN_TO, COT_TEN_CT,
    COT_TONG_DU_NO, COT_LAI_TON, COT_SO_DU_TG, COT_TINH_TRANG,
}

# Preset cột (3.3): mỗi preset = tập cột nguồn bổ sung vào bộ cơ bản.
_COLUMN_PRESETS: dict[str, set] = {
    "Cơ bản": set(_DEFAULT_VISIBLE),
    "Đến hạn": set(_DEFAULT_VISIBLE) | {COT_NGAY_VAY, COT_NGAY_DH, COT_SO_LAN_GH},
    "Quá hạn": set(_DEFAULT_VISIBLE) | {COT_DU_NO_QH, COT_LAI_TON_QH, COT_PHAN_LOAI},
    "NQ11 / GQVL": set(_DEFAULT_VISIBLE) | {COT_NGUON_VON, COT_MA_NHA_DAU_TU},
    "Huy động": set(_DEFAULT_VISIBLE) | {COT_SO_DU_TG, COT_LAI_TON},
    "Khoanh nợ": set(_DEFAULT_VISIBLE) | {COT_DU_NO_KHOANH, COT_NGAY_HH_KHOANH},
}


def _sort_mac_dinh(df_x: pd.DataFrame) -> pd.DataFrame:
    """Sắp xếp mặc định: Dư nợ QH DESC, Tổng dư nợ DESC (3.3).

    Giữ nguyên index gốc để map vị trí dòng → hồ sơ không đổi.
    """
    by: list[str] = []
    asc: list[bool] = []
    tmp = df_x
    if COT_DU_NO_QH in tmp.columns:
        tmp = tmp.assign(__qh=pd.to_numeric(tmp[COT_DU_NO_QH], errors="coerce").fillna(0))
        by.append("__qh")
        asc.append(False)
    if COT_TONG_DU_NO in tmp.columns:
        tmp = tmp.assign(__dn=pd.to_numeric(tmp[COT_TONG_DU_NO], errors="coerce").fillna(0))
        by.append("__dn")
        asc.append(False)
    if not by:
        return df_x
    return tmp.sort_values(by=by, ascending=asc, kind="mergesort").drop(columns=by)


def _mask_df_pii(df_x: pd.DataFrame) -> pd.DataFrame:
    """Che CMND/SĐT trên bản sao DataFrame trước khi xuất Excel (3.6)."""
    out = df_x.copy()
    if COT_CMND in out.columns:
        out[COT_CMND] = out[COT_CMND].map(_mask_cmnd)
    if COT_SDT in out.columns:
        out[COT_SDT] = out[COT_SDT].map(_mask_sdt)
    return out



def _build_bang_ket_qua(df_f: pd.DataFrame, visible_cols: set | None = None) -> tuple[pd.DataFrame, list[str]]:
    """Tạo DataFrame hiển thị — cột tiền giữ numeric (triệu) để sort số được.

    Returns: (df_view, money_labels) — money_labels để gắn NumberColumn.
    """
    if visible_cols is None:
        visible_cols = _DEFAULT_VISIBLE
    data: dict[str, list] = {}
    money_labels: list[str] = []
    for src, label, is_money in _VIEW_CATALOG:
        if src not in df_f.columns or src not in visible_cols:
            continue
        if is_money:
            data[label] = (pd.to_numeric(df_f[src], errors="coerce").fillna(0) / 1_000_000.0).reset_index(drop=True)
            money_labels.append(label)
        else:
            data[label] = df_f[src].astype(str).replace({"nan": "", "None": ""}).reset_index(drop=True)
    df_view = pd.DataFrame(data)
    return df_view, money_labels


def _mask_kw_for_audit(kw: str) -> str:
    """Che mọi chuỗi số giống CMND/CCCD/SĐT, kể cả trong từ khóa nhiều token."""
    s = str(kw or "").strip()
    def _replace(match: re.Match) -> str:
        value = match.group(0)
        if value.startswith("0") and len(value) in (10, 11):
            return _mask_sdt(value)
        return _mask_cmnd(value)

    return re.sub(r"(?<!\d)\d{9,12}(?!\d)", _replace, s)


def _them_tra_cuu_gan_day(kw: str, n: int, ten_kh_dau: str = "") -> None:
    """Thêm từ khóa vào lịch sử tra cứu gần đây (chỉ session, không persist)."""
    s = str(kw or "").strip()
    if not s:
        return
    recent = st.session_state.setdefault("tc2_recent", deque(maxlen=10))
    # bỏ trùng nếu đã có
    for i, item in enumerate(recent):
        if item.get("kw") == s:
            del recent[i]
            break
    recent.appendleft({
        "kw": s,
        "n": n,
        "ts": datetime.now().strftime("%H:%M %d/%m/%Y"),
        "ten_kh_dau": str(ten_kh_dau or "").strip(),
    })
    st.session_state["tc2_recent"] = recent


def _render_tra_cuu_gan_day() -> None:
    """Popover lịch sử tra cứu gần đây — bấm để nạp lại từ khóa."""
    recent = st.session_state.get("tc2_recent")
    if not recent:
        return
    with st.popover("🕘 Tra cứu gần đây"):
        st.caption("Bấm để tra lại:")
        for item in list(recent):
            _first = f" · {item['ten_kh_dau']}" if item.get("ten_kh_dau") else ""
            _lbl = f"{item['kw']} · {item['n']} hs{_first}"
            if st.button(_lbl, key=f"tc2_recent_{item['kw']}", width="stretch"):
                st.session_state.tracuu_filters["search_keyword"] = item["kw"]
                st.rerun()


def _build_charts(df_f: pd.DataFrame) -> list[tuple["go.Figure", str]]:
    """Dựng 4 biểu đồ phân bố (3.7) — trả về list (fig, tiêu đề) để render + đính kèm PDF."""
    figs: list[tuple[go.Figure, str]] = []
    if df_f.empty or COT_TONG_DU_NO not in df_f.columns:
        return figs
    _dn = pd.to_numeric(df_f[COT_TONG_DU_NO], errors="coerce").fillna(0)
    _base = df_f.assign(_dn=_dn)

    if COT_TEN_CT in df_f.columns:
        _g = _base.groupby(COT_TEN_CT)["_dn"].sum().sort_values(ascending=False).head(10)
        if len(_g):
            fig = go.Figure(go.Bar(x=_g.values, y=_g.index, orientation="h"))
            fig.update_layout(height=320, margin=dict(l=10, r=10, t=36, b=10), title="Dư nợ theo Chương trình")
            figs.append((fig, "Dư nợ theo Chương trình"))

    if COT_TEN_PGD in df_f.columns:
        _g = _base.groupby(COT_TEN_PGD)["_dn"].sum().sort_values(ascending=True)
        if len(_g):
            fig = go.Figure(go.Bar(x=_g.values, y=_g.index, orientation="h"))
            fig.update_layout(height=320, margin=dict(l=10, r=10, t=36, b=10), title="Dư nợ theo PGD")
            figs.append((fig, "Dư nợ theo PGD"))

    if COT_NGUON_VON in df_f.columns:
        _nv = _base.assign(_nv=df_f[COT_NGUON_VON].map(_hien_thi_nguon_von))
        _g = _nv.groupby("_nv")["_dn"].sum()
        _g = _g[_g.index != ""]
        if len(_g):
            fig = go.Figure(go.Pie(labels=_g.index, values=_g.values, hole=0.45))
            fig.update_layout(height=320, margin=dict(l=10, r=10, t=36, b=10), title="Dư nợ theo Nguồn vốn")
            figs.append((fig, "Dư nợ theo Nguồn vốn"))

    if COT_NGAY_VAY in df_f.columns:
        _yrs = pd.to_datetime(df_f[COT_NGAY_VAY], errors="coerce").dt.year.dropna().astype(int)
        if len(_yrs):
            fig = go.Figure(go.Histogram(x=_yrs, nbinsx=min(20, _yrs.nunique())))
            fig.update_layout(height=320, margin=dict(l=10, r=10, t=36, b=10), title="Phân bố theo năm vay")
            figs.append((fig, "Phân bố theo năm vay"))

    return figs


def _render_charts(df_f: pd.DataFrame, chart_figs: list | None = None) -> None:
    """Render 4 biểu đồ theo lưới 2×2 (dùng plotly)."""
    figs = chart_figs if chart_figs is not None else _build_charts(df_f)
    if not figs:
        st.caption("Không có dữ liệu để vẽ biểu đồ.")
        return
    c1, c2 = st.columns(2)
    for i, (fig, _title) in enumerate(figs):
        (c1 if i % 2 == 0 else c2).plotly_chart(fig, width="stretch")



def _build_theo_khach_hang(df_f: pd.DataFrame) -> pd.DataFrame:
    """Gom theo KHÁCH HÀNG: mỗi dòng = 1 KH, tổng dư nợ + số món vay."""
    if COT_MA_KH not in df_f.columns:
        return pd.DataFrame()
    _num_cols = [c for c in [COT_TONG_DU_NO, COT_DU_NO_QH, COT_LAI_TON, COT_SO_DU_TG] if c in df_f.columns]
    _first_cols = [c for c in [COT_TEN_KH, COT_CMND, COT_SDT, COT_TEN_XA, COT_TEN_PGD] if c in df_f.columns]
    _tmp = df_f.copy()
    for c in _num_cols:
        _tmp[c] = pd.to_numeric(_tmp[c], errors="coerce").fillna(0)
    _first = _tmp.groupby(COT_MA_KH)[_first_cols].first() if _first_cols else pd.DataFrame(index=_tmp[COT_MA_KH].unique())
    _sums = _tmp.groupby(COT_MA_KH)[_num_cols].sum().rename(columns={c: f"{c} (tổng)" for c in _num_cols}) if _num_cols else pd.DataFrame()
    _cnt = _tmp.groupby(COT_MA_KH).size().rename("Số món vay")
    _out = _first
    if not _sums.empty:
        _out = _out.join(_sums)
    _out = _out.join(_cnt)
    return _out.reset_index()


@st.dialog("Khế ước của khách hàng", width="large")
def _customer_loans_dialog(
    ma_kh: str,
    loans: pd.DataFrame,
    mask_pii: bool = False,
) -> None:
    """Hiển thị danh sách khế ước con của một khách hàng."""
    ten_kh = ""
    if COT_TEN_KH in loans.columns and not loans.empty:
        ten_kh = str(loans.iloc[0].get(COT_TEN_KH, "") or "").strip()
    st.markdown(f"### {ten_kh or 'Khách hàng'}")
    st.caption(f"Mã KH: {ma_kh} · {len(loans):,} khế ước")
    cols = [
        c for c in (
            COT_SO_KU, COT_TEN_CT, COT_NGAY_VAY, COT_NGAY_DH,
            COT_TONG_DU_NO, COT_DU_NO_QH, COT_TINH_TRANG,
        ) if c in loans.columns
    ]
    shown = _mask_df_pii(loans[cols]) if mask_pii else loans[cols]
    money_cfg = {
        c: st.column_config.NumberColumn(format="%,.0f")
        for c in (COT_TONG_DU_NO, COT_DU_NO_QH) if c in shown.columns
    }
    st.dataframe(shown, hide_index=True, column_config=money_cfg or None)


def _render_detail_cards(
    df_f: pd.DataFrame,
    df_nq11: pd.DataFrame | None,
    df_gqvl: pd.DataFrame | None,
    username: str,
    role: str,
    df_full: pd.DataFrame | None,
    mask_pii: bool,
) -> None:
    """Render tối đa 20 thẻ hồ sơ bằng component native, không hardcode màu."""
    limited = _sort_mac_dinh(df_f).head(20)
    st.caption(f"Hiển thị {len(limited):,}/{len(df_f):,} hồ sơ ưu tiên theo quá hạn và dư nợ.")
    columns = st.columns(2)
    for card_no, (_, row) in enumerate(limited.iterrows()):
        token = _record_identity(row)
        with columns[card_no % 2]:
            with st.container(border=True):
                st.markdown(f"**{row.get(COT_TEN_KH, 'Hồ sơ')}**")
                cmnd = row.get(COT_CMND, "")
                sdt = row.get(COT_SDT, "")
                if mask_pii:
                    cmnd, sdt = _mask_cmnd(cmnd), _mask_sdt(sdt)
                st.caption(
                    f"Mã KH: {row.get(COT_MA_KH, '')} · KU: {row.get(COT_SO_KU, '')}"
                )
                c1, c2 = st.columns(2)
                c1.metric("Tổng dư nợ", fmt_ty(row.get(COT_TONG_DU_NO, 0)))
                c2.metric("Dư nợ quá hạn", fmt_ty(row.get(COT_DU_NO_QH, 0)))
                if cmnd or sdt:
                    st.caption(f"CMND/CCCD: {cmnd or '—'} · SĐT: {sdt or '—'}")
                if st.button(
                    "Chi tiết", icon=":material/open_in_new:",
                    key=f"tc2_card_open_{token}", width="stretch",
                ):
                    _detail_dialog(
                        row, df_nq11, df_gqvl, username, role=role,
                        df_full=df_full, mask_pii=mask_pii,
                    )


def render(tab: "DeltaGenerator", **kwargs) -> None:
    """Render tab Tra cứu hồ sơ v2 (thiết kế lại)."""
    df = kwargs.get("df")
    username = kwargs.get("username", "unknown")
    pgd_user = kwargs.get("pgd_user")
    role = str(kwargs.get("role", "user") or "user")
    role_norm = normalize_role(role)

    # NQ11/GQVL — ưu tiên từ kwargs (app.py nạp sẵn), fallback tự load
    # app.py luôn truyền key (có thể là DataFrame rỗng) → chỉ load khi thật sự None,
    # tránh đọc lại file vô ích khi dữ liệu đã nạp (kể cả rỗng).
    df_nq11 = kwargs.get("df_nq11")
    df_gqvl = kwargs.get("df_gqvl")
    if df_nq11 is None or df_gqvl is None:
        _nq, _gq = _load_nq11_gqvl_data()
        if df_nq11 is None:
            df_nq11 = _nq
        if df_gqvl is None:
            df_gqvl = _gq
    ts_hstd = float(kwargs.get("ts_hstd", 0.0))

    ctx = TabContext(tab, **kwargs)
    with ctx:
        # Nguồn dữ liệu: df = chỉ hồ sơ còn dư nợ (CN), df_full = toàn bộ (kể cả tất toán).
        # Với role CN, df_full khác df → cho phép tra cứu hồ sơ đã tất toán (A1).
        df_full = kwargs.get("df_full")
        df_nguon = df
        if not ctx.is_pgd and df_full is not None and not df_full.empty:
            bao_gom_tat_toan = st.toggle(
                "🔎 Bao gồm hồ sơ đã tất toán (dư nợ = 0)",
                value=st.session_state.get("tc2_bao_gom_tat_toan", True),
                key="tc2_bao_gom_tat_toan",
                help="Bật: tra cứu trên toàn bộ hồ sơ (kể cả đã tất toán). Tắt: chỉ hồ sơ còn dư nợ.",
            )
            df_nguon = df_full if bao_gom_tat_toan else df

        # PII: ẩn CMND/SĐT (mặc định bật cho executive — chỉ đọc)
        _mac_dinh_mask = role_norm == "executive"
        mask_pii = st.toggle(
            "🕶️ Ẩn thông tin nhạy cảm (CMND/SĐT)",
            value=st.session_state.get("tc2_mask_pii", _mac_dinh_mask),
            key="tc2_mask_pii",
            help="Bật: che CMND/CCCD và SĐT trên bảng kết quả, dialog và file xuất.",
        )

        if df_nguon is None or df_nguon.empty:
            st.warning("⚠️ Chưa có dữ liệu HSTD để tra cứu.")
            return

        st.subheader("🔍 Tra cứu hồ sơ khách hàng")

        # Lịch sử tra cứu gần đây
        _render_tra_cuu_gan_day()

        # ── Bộ lọc (render_filter_panel tự có search bar + expander nâng cao) ──
        with st.spinner("Đang tra cứu..."):
            df_f = render_filter_panel(
                df=df_nguon,
                df_nq11=df_nq11,
                df_gqvl=df_gqvl,
                pgd_user=pgd_user,
                ts_hstd=ts_hstd,
            )

        # Audit tra cứu (chỉ khi có từ khóa, debounce theo keyword) + lịch sử gần đây
        _search_kw = str(st.session_state.get("tracuu_filters", {}).get("search_keyword", "") or "").strip()
        if _search_kw:
            _kw_masked = _mask_kw_for_audit(_search_kw)
            if _kw_masked and _kw_masked != st.session_state.get("tc2_last_audited"):
                db.ghi_audit(
                    username,
                    "tra_cuu_kh",
                    f"kw={_kw_masked}; n={len(df_f)}; pgd={pgd_user or 'toan_cn'}",
                )
                st.session_state["tc2_last_audited"] = _kw_masked
            _ten_kh_dau = ""
            if not df_f.empty and COT_TEN_KH in df_f.columns:
                _ten_kh_dau = str(df_f.iloc[0].get(COT_TEN_KH, "") or "").strip()
            _them_tra_cuu_gan_day(_search_kw, len(df_f), _ten_kh_dau)

        # ── Số liệu tổng hợp ──────────────────────────────────────────────
        tong_no = float(pd.to_numeric(df_f.get(COT_TONG_DU_NO, 0), errors="coerce").fillna(0).sum()) \
            if COT_TONG_DU_NO in df_f.columns else 0.0
        qh_count = int((pd.to_numeric(df_f.get(COT_DU_NO_QH, 0), errors="coerce").fillna(0) > 0).sum()) \
            if COT_DU_NO_QH in df_f.columns else 0
        nq11_count = int(df_f["__is_nq11"].fillna(False).sum()) if "__is_nq11" in df_f.columns else 0
        gqvl_count = int(df_f["__is_gqvl"].fillna(False).sum()) if "__is_gqvl" in df_f.columns else 0

        st.divider()
        _render_kpi_va_xuat(
            df_f, nq11_count, gqvl_count, qh_count, tong_no, username,
            mask_pii=mask_pii, chart_figs=None,
        )

        # ── Bảng kết quả ────────────────────────────────────────────────
        st.divider()
        if df_f.empty:
            st.info("Không có hồ sơ phù hợp. Thử nới bộ lọc hoặc đổi từ khóa tìm kiếm.")
            return

        _mode = st.segmented_control(
            "Chế độ xem",
            options=["Theo khế ước", "Theo khách hàng", "Thẻ chi tiết"],
            default="Theo khế ước",
            required=True,
            key="tc2_mode",
        )

        chart_expander = st.expander(
            "📊 Phân bố kết quả",
            expanded=False,
            key="tc2_chart_expander",
            on_change="rerun",
        )
        if chart_expander.open:
            with chart_expander:
                _render_charts(df_f, _build_charts(df_f))


        # ── Chế độ "Theo khách hàng" ────────────────────────────────────
        if _mode == "Theo khách hàng":
            _df_kh = _build_theo_khach_hang(df_f)
            if _df_kh.empty:
                st.info("Không gom được theo khách hàng (thiếu cột Mã KH).")
                return
            st.caption(f"💡 {len(_df_kh):,} khách hàng — bấm chọn để xem danh sách khế ước.")
            _kh_scope = _ui_scope(
                ts_hstd, pgd_user, len(df_f), st.session_state.get("tracuu_filters", {})
            )
            if st.session_state.get("tc2_customer_table_scope") != _kh_scope:
                st.session_state["tc2_customer_table_scope"] = _kh_scope
                st.session_state.pop("tc2_table_kh", None)
                st.session_state["tc2_last_customer_sel"] = None
            _df_kh_show = _mask_df_pii(_df_kh) if mask_pii else _df_kh
            _ev = st.dataframe(
                _df_kh_show, hide_index=True, width="stretch", height=460,
                key="tc2_table_kh", on_select="rerun", selection_mode="single-row",
            )
            _rows = _ev.selection.get("rows", []) if _ev and getattr(_ev, "selection", None) else []
            if _rows:
                _ma_kh_sel = str(_df_kh.iloc[_rows[0]][COT_MA_KH]).strip()
                _ds_ku = df_f[df_f[COT_MA_KH].astype(str).str.strip() == _ma_kh_sel]
                _customer_token = _ui_scope(_kh_scope, _ma_kh_sel)
                if _customer_token != st.session_state.get("tc2_last_customer_sel"):
                    st.session_state["tc2_last_customer_sel"] = _customer_token
                    _customer_loans_dialog(_ma_kh_sel, _ds_ku, mask_pii=mask_pii)
            return

        if _mode == "Thẻ chi tiết":
            _render_detail_cards(
                df_f, df_nq11, df_gqvl, username, role, df_full, mask_pii
            )
            return

        # ── Chế độ "Theo khế ước": preset cột + sắp xếp mặc định ──────────
        _avail_src = [src for src, _l, _m in _VIEW_CATALOG if src in df_f.columns]
        _preset_names = [
            p for p in _COLUMN_PRESETS
            if any(s in _avail_src for s in _COLUMN_PRESETS[p])
        ] + ["Tùy chỉnh"]
        _preset = st.selectbox("Preset cột", options=_preset_names, index=0, key="tc2_preset")
        if _preset == "Tùy chỉnh":
            _all_labels = {src: label for src, label, _ in _VIEW_CATALOG if src in df_f.columns}
            _def_labels = [label for src, label, _ in _VIEW_CATALOG if src in _DEFAULT_VISIBLE and src in df_f.columns]
            _sel_labels = st.multiselect(
                "Cột hiển thị",
                options=list(_all_labels.values()),
                default=_def_labels,
                key="tc2_cols",
            )
            _visible = {src for src, label, _ in _VIEW_CATALOG if label in _sel_labels}
        else:
            _visible = {src for src in _COLUMN_PRESETS[_preset] if src in df_f.columns}

        # Sắp xếp mặc định: Dư nợ QH DESC, Tổng dư nợ DESC (3.3) — dùng cho cả bảng lẫn map dòng.
        df_tab = _sort_mac_dinh(df_f)

        st.caption("💡 Bấm chọn một dòng để xem chi tiết hồ sơ.")
        df_view, money_labels = _build_bang_ket_qua(df_tab, _visible)

        if df_view.empty:
            st.info("Không có cột nào để hiển thị. Chọn ít nhất 1 cột.")
            return

        # ── Phân trang + selection tuyệt đối ──
        table_scope = _ui_scope(
            ts_hstd,
            pgd_user,
            len(df_tab),
            _preset,
            sorted(_visible),
            st.session_state.get("tracuu_filters", {}),
        )
        if st.session_state.get("tc2_table_scope") != table_scope:
            st.session_state["tc2_table_scope"] = table_scope
            st.session_state["tc2_page"] = 1
            st.session_state["tc2_selected_idx"] = None
            st.session_state["tc2_last_sel"] = None
            st.session_state.pop("tc2_table", None)

        st.session_state.setdefault("tc2_page_size", 200)
        page_size = int(st.selectbox(
            "Số dòng mỗi trang",
            options=[100, 200, 500],
            key="tc2_page_size",
            width=180,
        ))
        total_rows = len(df_view)
        total_pages = max(1, (total_rows + page_size - 1) // page_size)
        current_page = _clamp_page(st.session_state.get("tc2_page", 1), total_pages)
        if st.session_state.get("tc2_page") != current_page:
            st.session_state["tc2_page"] = current_page

        if total_pages > 1:
            c_prev, c_pg, c_next, c_info = st.columns([1, 2, 1, 5])
            with c_prev:
                st.button(
                    "‹", key="tc2_page_prev", help="Trang trước",
                    disabled=current_page <= 1, width="stretch",
                    on_click=_change_page, args=(-1, total_pages),
                )
            with c_pg:
                page = int(st.number_input(
                    "Trang", min_value=1, max_value=total_pages,
                    step=1, key="tc2_page",
                ))
            with c_next:
                st.button(
                    "›", key="tc2_page_next", help="Trang sau",
                    disabled=current_page >= total_pages, width="stretch",
                    on_click=_change_page, args=(1, total_pages),
                )
            with c_info:
                st.caption(
                    f"Hiển thị {(page-1)*page_size+1:,}–"
                    f"{min(page*page_size, total_rows):,} / {total_rows:,} dòng"
                )
        else:
            page = 1
            st.session_state["tc2_page"] = 1

        start = (page - 1) * page_size
        end = min(start + page_size, total_rows)
        chunk = df_view.iloc[start:end]
        page_changed = (
            st.session_state.get("tc2_table_page") != page
            or st.session_state.get("tc2_table_page_size") != page_size
        )
        if page_changed:
            st.session_state["tc2_table_page"] = page
            st.session_state["tc2_table_page_size"] = page_size
            st.session_state.pop("tc2_table", None)

        selected_idx = st.session_state.get("tc2_selected_idx")
        selection_default = _selection_default_for_page(selected_idx, start, end)

        _col_cfg = {m: st.column_config.NumberColumn(format="%,.0f") for m in money_labels}
        event = st.dataframe(
            chunk,
            hide_index=True,
            width="stretch",
            height=460,
            key="tc2_table",
            on_select="rerun",
            selection_mode="single-row",
            selection_default=selection_default,
            column_config=(_col_cfg if _col_cfg else None),
        )

        # ── Mở modal chi tiết khi chọn dòng mới ───────────────────────────
        rows = []
        if event and getattr(event, "selection", None):
            rows = event.selection.get("rows", [])
        if rows:
            pos = rows[0] + start  # map vị trí chunk → vị trí trong df_tab (đã sort)
            if pos < len(df_tab):
                # Map theo vị trí của df_tab (không theo Số KU) — tránh mở sai hồ sơ
                # khi Số KU trùng hoặc rỗng (A4/A5). df_tab cùng thứ tự với df_view.
                hs_selected = df_tab.iloc[pos]
                so_ku = str(hs_selected.get(COT_SO_KU, "") or "").strip()
                ten_selected = str(hs_selected.get(COT_TEN_KH, "") or "").strip()
                col_info, col_open = st.columns([4, 1])
                with col_info:
                    st.caption(
                        f"Đã chọn: **{ten_selected or 'Hồ sơ'}**"
                        f"{f' · Số KU: `{so_ku}`' if so_ku else ''}"
                    )
                st.session_state["tc2_selected_idx"] = pos
                should_auto_open = pos != st.session_state.get("tc2_last_sel")
                should_open_again = col_open.button(
                    "📋 Chi tiết",
                    key=f"tc2_open_selected_{pos}",
                    width="stretch",
                )
                if should_auto_open or should_open_again:
                    st.session_state["tc2_last_sel"] = pos
                    _detail_dialog(hs_selected, df_nq11, df_gqvl, username, role=role, df_full=df_full, mask_pii=mask_pii)
        elif not page_changed:
            st.session_state["tc2_selected_idx"] = None
            st.session_state["tc2_last_sel"] = None


# Backward compatibility
render_tab = render
