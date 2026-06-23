"""Tab Tra cứu hồ sơ — Phiên bản 2.0.

Bố cục:
- Bộ lọc đa tiêu chí qua render_filter_panel (tích hợp search + expander nâng cao)
- KPI chuẩn bằng kpi_row() + xuất Excel/PDF
- Bảng kết quả native (st.dataframe, chọn 1 dòng)
- Chi tiết hồ sơ mở bằng modal st.dialog
"""

from __future__ import annotations

import streamlit as st
import pandas as pd
from typing import TYPE_CHECKING

from config import (
    COT_TEN_KH, COT_MA_KH, COT_SO_KU, COT_CMND, COT_SDT,
    COT_TEN_PGD, COT_TEN_XA,
    COT_TEN_CT, COT_NGUON_VON, COT_NGAY_VAY,
    COT_DU_NO_TH, COT_DU_NO_QH, COT_TONG_DU_NO, COT_DU_NO_KHOANH,
    COT_THOI_HAN, COT_LAI_SUAT, COT_MUC_VAY, COT_LAI_DA_TRA,
    COT_GOC_TRA, COT_NGAY_SINH,
    COT_NOI_CAP_CMND, COT_NGAY_CAP_CMND, COT_TINH_TRANG,
    COT_TEN_TO, COT_TEN_VC, COT_TEN_HSSV, COT_DIA_CHI,
    COT_LAI_TON, COT_SO_DU_TG,
)
from utils import fmt_tien, fmt_ty, xuat_excel
from tabs.base_tab import TabContext
from components.filter_panel import render_filter_panel
from components.delta_card import kpi_row
from components.export_pdf import xuat_pdf_co_chart, download_pdf_button
from data import doc_nq11_toan_cn_pgd, doc_gqvl_toan_cn

if TYPE_CHECKING:
    from streamlit.delta_generator import DeltaGenerator


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


def _load_nq11_gqvl_data() -> tuple[pd.DataFrame | None, pd.DataFrame | None]:
    """Load NQ11 và GQVL từ cache (fallback khi app.py chưa nạp sẵn)."""
    df_nq11 = None
    df_gqvl = None
    try:
        df_nq11 = doc_nq11_toan_cn_pgd()
    except Exception:
        pass
    try:
        df_gqvl = doc_gqvl_toan_cn()
    except Exception:
        pass
    return df_nq11, df_gqvl



def _so_khac_nhau(df_kia: pd.DataFrame | None, so_ku: str) -> bool:
    """Hồ sơ Số KU có thuộc bảng NQ11/GQVL không."""
    if df_kia is None or df_kia.empty:
        return False
    col = "Số khế ước" if "Số khế ước" in df_kia.columns else COT_SO_KU
    if col not in df_kia.columns:
        return False
    return str(so_ku).strip() in set(df_kia[col].dropna().astype(str).str.strip())


def _render_chi_tiet_phu(df_kia: pd.DataFrame, so_ku: str, money_kw: tuple[str, ...]) -> None:
    """Render chi tiết NQ11/GQVL của 1 hồ sơ dạng 2 cột gọn."""
    col = "Số khế ước" if "Số khế ước" in df_kia.columns else COT_SO_KU
    match = df_kia[df_kia[col].astype(str).str.strip() == str(so_ku).strip()]
    if match.empty:
        return
    row = match.iloc[0]
    skip = {"số khế ước", "mã kh", "mã khách hàng", "tên kh", "tên khách hàng"}
    items: list[tuple[str, str]] = []
    for c in match.columns:
        if c.lower().strip() in skip:
            continue
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
) -> None:
    """Modal hiển thị chi tiết 1 hồ sơ."""
    so_ku = str(hs.get(COT_SO_KU, "")).strip()
    st.markdown(f"### {hs.get(COT_TEN_KH, '—')}")
    pdf_state_key = f"tc_pdf_hoso_{so_ku}"

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
                    info_data.append((label, str(value)))
        if info_data:
            st.dataframe(
                pd.DataFrame(info_data, columns=["Thông tin", "Giá trị"]),
                hide_index=True, use_container_width=True,
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
                hide_index=True, use_container_width=True,
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

    st.divider()
    excel_data = xuat_excel({f"HS_{so_ku}": hs.to_frame().T})
    col_xl, col_pdf = st.columns(2)
    with col_xl:
        st.download_button(
            "📥 Xuất Excel hồ sơ",
            data=excel_data,
            file_name=f"ho_so_{so_ku}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            key=f"tc_dialog_export_{so_ku}",
        )
    with col_pdf:
        if st.button("📄 Xuất PDF hồ sơ", use_container_width=True, key=f"tc_make_pdf_{so_ku}"):
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
                key=f"tc_dialog_pdf_{so_ku}",
            )


def _render_kpi_va_xuat(
    df_f: pd.DataFrame,
    nq11_count: int,
    gqvl_count: int,
    qh_count: int,
    tong_no: float,
    username: str,
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
            st.download_button(
                "📊 Excel",
                data=xuat_excel({"KetQua_TraCuu": df_f}),
                file_name="ket_qua_tra_cuu.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
                key="tc_export_excel",
            )
        else:
            st.button(
                f"📊 Excel ({len(df_f):,} — lọc thêm)",
                disabled=True, use_container_width=True, key="tc_export_excel",
            )

    with col_pdf:
        pdf_done = False
        if not df_f.empty and len(df_f) <= _MAX_EXPORT_PDF:
            pdf_cols = [c for c in [
                COT_SO_KU, COT_TEN_KH, COT_TEN_PGD, COT_TEN_CT,
                COT_NGAY_VAY, COT_DU_NO_TH, COT_DU_NO_QH, COT_TONG_DU_NO, COT_TINH_TRANG,
            ] if c in df_f.columns]
            cols_tien = [c for c in [COT_DU_NO_TH, COT_DU_NO_QH, COT_TONG_DU_NO] if c in pdf_cols]
            try:
                pdf_bytes = xuat_pdf_co_chart(
                    df=df_f[pdf_cols],
                    tieu_de="KẾT QUẢ TRA CỨU HỒ SƠ",
                    nguoi_xuat=username,
                    cols_tien=cols_tien,
                    them_dong_tong=False,
                )
                if pdf_bytes:
                    download_pdf_button(pdf_bytes, filename="ket_qua_tra_cuu.pdf", label="📄 PDF", key="tc_export_pdf")
                    pdf_done = True
            except Exception:
                pass
        if not pdf_done:
            lbl = f"📄 PDF ({len(df_f):,} — lọc thêm)" if len(df_f) > _MAX_EXPORT_PDF else "📄 PDF"
            st.button(lbl, disabled=True, use_container_width=True, key="tc_export_pdf")


def _build_bang_ket_qua(df_f: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """Tạo DataFrame hiển thị (cột chọn lọc, tiền đã format) + Series Số KU theo vị trí."""
    view_cols = [
        (COT_SO_KU, "Số khế ước"),
        (COT_TEN_KH, "Tên KH"),
        (COT_TEN_PGD, "PGD"),
        (COT_TEN_XA, "Xã/Phường"),
        (COT_TEN_TO, "Tên tổ"),
        (COT_TEN_CT, "Chương trình"),
        (COT_TONG_DU_NO, "Tổng dư nợ (triệu đồng)"),
        (COT_LAI_TON, "Lãi tồn (triệu đồng)"),
        (COT_SO_DU_TG, "Số dư TK 105 (triệu đồng)"),
        (COT_TINH_TRANG, "Tình trạng"),
    ]
    data: dict[str, list] = {}
    for src, label in view_cols:
        if src not in df_f.columns:
            continue
        if src in {COT_TONG_DU_NO, COT_LAI_TON, COT_SO_DU_TG}:
            data[label] = pd.to_numeric(df_f[src], errors="coerce").apply(fmt_ty).reset_index(drop=True)
        else:
            data[label] = df_f[src].astype(str).replace({"nan": "", "None": ""}).reset_index(drop=True)

    df_view = pd.DataFrame(data)
    if "Tên tổ" not in df_view.columns:
        df_view["Tên tổ"] = ""
    ku_series = (df_f[COT_SO_KU].astype(str).reset_index(drop=True)
                 if COT_SO_KU in df_f.columns else pd.Series([""] * len(df_f)))
    return df_view, ku_series


def render(tab: "DeltaGenerator", **kwargs) -> None:
    """Render tab Tra cứu hồ sơ v2 (thiết kế lại)."""
    df = kwargs.get("df")
    username = kwargs.get("username", "unknown")
    pgd_user = kwargs.get("pgd_user")

    # NQ11/GQVL — ưu tiên từ kwargs (app.py nạp sẵn), fallback tự load
    df_nq11 = kwargs.get("df_nq11")
    df_gqvl = kwargs.get("df_gqvl")
    if df_nq11 is None and df_gqvl is None:
        df_nq11, df_gqvl = _load_nq11_gqvl_data()
    elif df_nq11 is None:
        df_nq11, _ = _load_nq11_gqvl_data()
    elif df_gqvl is None:
        _, df_gqvl = _load_nq11_gqvl_data()
    ts_hstd = float(kwargs.get("ts_hstd", 0.0))

    ctx = TabContext(tab, **kwargs)
    with ctx:
        if df is None or df.empty:
            st.warning("⚠️ Chưa có dữ liệu HSTD để tra cứu.")
            return

        st.subheader("🔍 Tra cứu hồ sơ khách hàng")

        # ── Bộ lọc (render_filter_panel tự có search bar + expander nâng cao) ──
        df_f = render_filter_panel(
            df=df,
            df_nq11=df_nq11,
            df_gqvl=df_gqvl,
            pgd_user=pgd_user,
            ts_hstd=ts_hstd,
        )

        # ── Số liệu tổng hợp ──────────────────────────────────────────────
        tong_no = float(pd.to_numeric(df_f.get(COT_TONG_DU_NO, 0), errors="coerce").fillna(0).sum()) \
            if COT_TONG_DU_NO in df_f.columns else 0.0
        qh_count = int((pd.to_numeric(df_f.get(COT_DU_NO_QH, 0), errors="coerce").fillna(0) > 0).sum()) \
            if COT_DU_NO_QH in df_f.columns else 0
        nq11_count = int(df_f["__is_nq11"].fillna(False).sum()) if "__is_nq11" in df_f.columns else 0
        gqvl_count = int(df_f["__is_gqvl"].fillna(False).sum()) if "__is_gqvl" in df_f.columns else 0

        st.divider()
        _render_kpi_va_xuat(df_f, nq11_count, gqvl_count, qh_count, tong_no, username)

        # ── Bảng kết quả (native, chọn 1 dòng) ────────────────────────────
        st.divider()
        if df_f.empty:
            st.info("Không có hồ sơ phù hợp. Thử nới bộ lọc hoặc đổi từ khóa tìm kiếm.")
            return

        st.caption("💡 Bấm chọn một dòng để xem chi tiết hồ sơ.")
        df_view, ku_series = _build_bang_ket_qua(df_f)
        event = st.dataframe(
            df_view,
            hide_index=True,
            use_container_width=True,
            height=460,
            key="tc_table",
            on_select="rerun",
            selection_mode="single-row",
        )

        # ── Mở modal chi tiết khi chọn dòng mới ───────────────────────────
        rows = []
        if event and getattr(event, "selection", None):
            rows = event.selection.get("rows", [])
        if rows:
            pos = rows[0]
            so_ku = str(ku_series.iat[pos]) if pos < len(ku_series) else ""
            if so_ku and so_ku != st.session_state.get("tc_last_ku"):
                st.session_state["tc_last_ku"] = so_ku
                mask = df[COT_SO_KU].astype(str).str.strip() == so_ku.strip()
                df_match = df[mask]
                if not df_match.empty:
                    _detail_dialog(df_match.iloc[0], df_nq11, df_gqvl, username)
        else:
            st.session_state["tc_last_ku"] = None


# Backward compatibility
render_tab = render
