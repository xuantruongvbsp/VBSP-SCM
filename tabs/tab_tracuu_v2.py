"""Tab Tra cứu hồ sơ — Phiên bản 2.0 (nâng cấp).

Tính năng mới:
- Bộ lọc nâng cao đa chiều (địa bàn, chương trình, dư nợ, ngày tháng)
- Giao diện card hiện đại với badge NQ11/GQVL/Quá hạn
- Preview nhanh và chi tiết drawer
- Phân trang và xuất báo cáo
"""

from __future__ import annotations

import streamlit as st
import pandas as pd
from typing import TYPE_CHECKING

from config import (
    COT_TEN_KH, COT_MA_KH, COT_SO_KU, COT_CMND, COT_SDT,
    COT_TEN_PGD, COT_TEN_XA,
    COT_TEN_CT, COT_NGUON_VON, COT_NGAY_VAY, COT_NGAY_DH,
    COT_DU_NO_TH, COT_DU_NO_QH, COT_TONG_DU_NO, COT_DU_NO_KHOANH,
    COT_THOI_HAN, COT_LAI_SUAT, COT_MUC_VAY, COT_LAI_DA_TRA,
    COT_GOC_TRA, COT_NGAY_SINH,
    COT_NOI_CAP_CMND, COT_NGAY_CAP_CMND, COT_TINH_TRANG,
    COT_TEN_TO, COT_TEN_VC, COT_TEN_HSSV, COT_DIA_CHI,
)
from utils import fmt_tien, fmt_so, xuat_excel, vn
from tabs.base_tab import TabContext
from components.filter_panel import render_filter_panel
from components.result_card import render_result_grid
from components.export_pdf import xuat_pdf_co_chart, download_pdf_button
from data import doc_nq11_toan_cn_pgd, doc_gqvl_toan_cn

if TYPE_CHECKING:
    from streamlit.delta_generator import DeltaGenerator


def _load_nq11_gqvl_data() -> tuple[pd.DataFrame | None, pd.DataFrame | None]:
    """Load NQ11 and GQVL data from cache."""
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


def _render_detail_drawer(
    df: pd.DataFrame,
    so_ku: str,
    df_nq11: pd.DataFrame | None,
    df_gqvl: pd.DataFrame | None,
) -> None:
    """Render detail drawer for selected hồ sơ."""
    if so_ku is None or so_ku == "":
        return
    
    # Find hồ sơ
    if COT_SO_KU not in df.columns:
        st.error("Không có cột Số khế ước trong dữ liệu")
        return
    
    mask = df[COT_SO_KU].astype(str).str.strip() == str(so_ku).strip()
    df_match = df[mask]
    
    if df_match.empty:
        st.warning(f"Không tìm thấy hồ sơ với Số KU: {so_ku}")
        return
    
    hs = df_match.iloc[0]
    
    # Drawer header
    st.markdown("---")
    st.markdown(f"### 📋 Chi tiết hồ sơ — {hs.get(COT_TEN_KH, '—')}")
    
    # Two columns layout
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown("**👤 Thông tin khách hàng**")
        info_data = []
        
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
        
        for label, col in fields:
            if col in hs.index:
                value = hs[col]
                if pd.notna(value) and str(value).strip():
                    info_data.append((label, str(value)))
        
        if info_data:
            info_df = pd.DataFrame(info_data, columns=["Thông tin", "Giá trị"])
            st.dataframe(info_df, hide_index=True, use_container_width=True)
    
    with col2:
        st.markdown("**💰 Thông tin khoản vay**")
        loan_data = []
        
        loan_fields = [
            ("Số khế ước", COT_SO_KU),
            ("Chương trình", COT_TEN_CT),
            ("Nguồn vốn", COT_NGUON_VON),
            ("Ngày vay", COT_NGAY_VAY),
            ("Thời hạn (tháng)", COT_THOI_HAN),
            ("Lãi suất (%)", COT_LAI_SUAT),
            ("Mức vay", COT_MUC_VAY),
            ("Dư nợ trong hạn", COT_DU_NO_TH),
            ("Dư nợ quá hạn", COT_DU_NO_QH),
            ("Tổng dư nợ", COT_TONG_DU_NO),
            ("Gốc đã trả", COT_GOC_TRA),
            ("Lãi đã trả", COT_LAI_DA_TRA),
            ("Tình trạng", COT_TINH_TRANG),
        ]
        
        for label, col in loan_fields:
            if col in hs.index:
                value = hs[col]
                if pd.notna(value):
                    # Format money fields
                    if col in [COT_DU_NO_TH, COT_DU_NO_QH, COT_TONG_DU_NO, COT_MUC_VAY, COT_GOC_TRA, COT_LAI_DA_TRA]:
                        formatted = fmt_tien(value)
                    else:
                        formatted = str(value)
                    loan_data.append((label, formatted))
        
        if loan_data:
            loan_df = pd.DataFrame(loan_data, columns=["Thông tin", "Giá trị"])
            st.dataframe(loan_df, hide_index=True, use_container_width=True)
        
        # Chi tiết NQ11 / GQVL (format đẹp thay vì raw dataframe)
        if df_nq11 is not None and "Số khế ước" in df_nq11.columns:
            nq11_match = df_nq11[df_nq11["Số khế ước"].astype(str).str.strip() == str(so_ku).strip()]
            if not nq11_match.empty:
                st.success("✨ Hồ sơ thuộc Nghị Quyết 11")
                with st.expander("Chi tiết NQ11", expanded=True):
                    row_nq = nq11_match.iloc[0]
                    _skip = {"số khế ước", "mã kh", "mã khách hàng", "tên kh", "tên khách hàng"}
                    _money_kw = ("dư nợ", "nợ", "vốn", "tiền", "dno", "gốc", "lãi")
                    _items: list[tuple[str, str]] = []
                    for col in nq11_match.columns:
                        if col.lower().strip() in _skip:
                            continue
                        val = row_nq.get(col)
                        if val is None or (isinstance(val, float) and pd.isna(val)):
                            continue
                        if any(kw in col.lower() for kw in _money_kw):
                            try:
                                _items.append((col, fmt_tien(float(val))))
                            except (ValueError, TypeError):
                                _items.append((col, str(val)))
                        else:
                            _items.append((col, str(val)))
                    if _items:
                        _nc1, _nc2 = st.columns(2)
                        for i, (k, v) in enumerate(_items):
                            (_nc1 if i % 2 == 0 else _nc2).markdown(f"**{k}:** {v}")

        if df_gqvl is not None and "Số khế ước" in df_gqvl.columns:
            gqvl_match = df_gqvl[df_gqvl["Số khế ước"].astype(str).str.strip() == str(so_ku).strip()]
            if not gqvl_match.empty:
                st.info("📋 Hồ sơ thuộc GQVL (Giải quyết Việc làm)")
                with st.expander("Chi tiết GQVL", expanded=True):
                    row_gq = gqvl_match.iloc[0]
                    _skip_g = {"số khế ước", "mã kh", "mã khách hàng", "tên kh", "tên khách hàng"}
                    _money_kw_g = ("dư nợ", "nợ", "vốn", "tiền", "giải ngân", "gốc", "lãi")
                    _items_g: list[tuple[str, str]] = []
                    for col in gqvl_match.columns:
                        if col.lower().strip() in _skip_g:
                            continue
                        val = row_gq.get(col)
                        if val is None or (isinstance(val, float) and pd.isna(val)):
                            continue
                        if any(kw in col.lower() for kw in _money_kw_g):
                            try:
                                _items_g.append((col, fmt_tien(float(val))))
                            except (ValueError, TypeError):
                                _items_g.append((col, str(val)))
                        else:
                            _items_g.append((col, str(val)))
                    if _items_g:
                        _gc1, _gc2 = st.columns(2)
                        for i, (k, v) in enumerate(_items_g):
                            (_gc1 if i % 2 == 0 else _gc2).markdown(f"**{k}:** {v}")
    
    # Action buttons
    st.divider()
    col_export, col_close = st.columns([1, 3])
    
    with col_export:
        # Export single record
        export_data = hs.to_frame().T
        excel_data = xuat_excel({f"HS_{so_ku}": export_data})
        st.download_button(
            "📥 Xuất Excel",
            data=excel_data,
            file_name=f"ho_so_{so_ku}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
    
    with col_close:
        if st.button("✖️ Đóng", use_container_width=True, type="secondary"):
            st.session_state.pop("tc_selected_ku", None)
            st.rerun()


def _render_results_header(
    df_filtered: pd.DataFrame,
    df_original: pd.DataFrame,
    nq11_count: int = 0,
    gqvl_count: int = 0,
    username: str = "unknown",
) -> None:
    """Render results summary header."""
    total = len(df_original)
    filtered = len(df_filtered)

    _co_db = nq11_count > 0 or gqvl_count > 0
    if _co_db:
        col1, col2, col3, col4, col5 = st.columns([2, 1, 1, 1, 1])
    else:
        col1, col2, col3, col4 = st.columns([2, 1, 1, 1])

    with col1:
        st.markdown(f"**📊 Kết quả:** {filtered:,} / {total:,} hồ sơ")

    with col2:
        if COT_TONG_DU_NO in df_filtered.columns:
            tong_no = df_filtered[COT_TONG_DU_NO].sum()
            st.markdown(f"💰 **Tổng DN:** {fmt_tien(tong_no)}")

    _MAX_EXPORT = 2000
    with col3:
        if not df_filtered.empty:
            if len(df_filtered) <= _MAX_EXPORT:
                excel_data = xuat_excel({"KetQua_TraCuu": df_filtered})
                st.download_button(
                    "📊 Excel",
                    data=excel_data,
                    file_name="ket_qua_tra_cuu.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                    key="tc_export_excel",
                )
            else:
                st.button(
                    f"📊 Excel ({len(df_filtered):,} — lọc thêm)",
                    disabled=True,
                    use_container_width=True,
                    key="tc_export_excel",
                )

    _MAX_PDF = 200
    with col4:
        _pdf_rendered = False
        if not df_filtered.empty and len(df_filtered) <= _MAX_PDF:
            _PDF_COLS = [c for c in [
                COT_SO_KU, COT_TEN_KH, COT_TEN_PGD, COT_TEN_CT,
                COT_NGAY_VAY, COT_DU_NO_TH, COT_DU_NO_QH, COT_TONG_DU_NO, COT_TINH_TRANG,
            ] if c in df_filtered.columns]
            _cols_tien_pdf = [c for c in [COT_DU_NO_TH, COT_DU_NO_QH, COT_TONG_DU_NO] if c in _PDF_COLS]
            try:
                _pdf_bytes = xuat_pdf_co_chart(
                    df=df_filtered[_PDF_COLS],
                    tieu_de="KẾT QUẢ TRA CỨU HỒ SƠ",
                    nguoi_xuat=username,
                    cols_tien=_cols_tien_pdf,
                    them_dong_tong=False,
                )
                if _pdf_bytes:
                    download_pdf_button(_pdf_bytes, filename="ket_qua_tra_cuu.pdf", label="📄 PDF", key="tc_export_pdf")
                    _pdf_rendered = True
            except Exception:
                pass
        if not _pdf_rendered:
            _lbl = f"📄 PDF ({len(df_filtered):,} — lọc thêm)" if len(df_filtered) > _MAX_PDF else "📄 PDF"
            st.button(_lbl, disabled=True, use_container_width=True, key="tc_export_pdf")

    if _co_db:
        with col5:
            _parts = []
            if nq11_count:
                _parts.append(f"✨ NQ11: **{nq11_count:,}**")
            if gqvl_count:
                _parts.append(f"📋 GQVL: **{gqvl_count:,}**")
            st.markdown(" · ".join(_parts))


def render(tab: "DeltaGenerator", **kwargs) -> None:
    """
    Render tab Tra cứu hồ sơ v2.
    
    Args:
        tab: Streamlit container/tab object
        **kwargs: Must include 'df', 'role', 'username', 'pgd_user', 'hstd_path'
    """
    df = kwargs.get("df")
    df_full = kwargs.get("df_full")
    role = kwargs.get("role", "user")
    username = kwargs.get("username", "unknown")
    pgd_user = kwargs.get("pgd_user")
    hstd_path = kwargs.get("hstd_path")
    
    if df is None or df.empty:
        st.warning("⚠️ Chưa có dữ liệu HSTD để tra cứu.")
        return
    
    # Load NQ11/GQVL data
    df_nq11, df_gqvl = _load_nq11_gqvl_data()
    ts_hstd = float(kwargs.get("ts_hstd", 0.0))

    # Tab context
    ctx = TabContext(tab, **kwargs)

    with ctx:
        st.subheader("🔍 Tra cứu hồ sơ khách hàng")
        st.caption("Tìm kiếm nâng cao với bộ lọc đa chiều — NQ11 · GQVL · Quá hạn")

        # Filter panel
        df_filtered = render_filter_panel(
            df=df,
            df_nq11=df_nq11,
            df_gqvl=df_gqvl,
            pgd_user=pgd_user,
            ts_hstd=ts_hstd,
        )
        
        # Đếm NQ11/GQVL trong kết quả — dùng cột enriched nếu có
        if "__is_nq11" in df_filtered.columns:
            _so_nq11_r = int(df_filtered["__is_nq11"].fillna(False).sum())
        elif df_nq11 is not None and not df_nq11.empty and COT_SO_KU in df_filtered.columns:
            _nq11_ku_col = "Số khế ước" if "Số khế ước" in df_nq11.columns else COT_SO_KU
            _so_nq11_r = int(df_filtered[COT_SO_KU].astype(str).str.strip().isin(
                set(df_nq11[_nq11_ku_col].dropna().astype(str).str.strip())
            ).sum()) if _nq11_ku_col in df_nq11.columns else 0
        else:
            _so_nq11_r = 0

        if "__is_gqvl" in df_filtered.columns:
            _so_gqvl_r = int(df_filtered["__is_gqvl"].fillna(False).sum())
        elif df_gqvl is not None and not df_gqvl.empty and COT_SO_KU in df_filtered.columns:
            _gqvl_ku_col = "Số khế ước" if "Số khế ước" in df_gqvl.columns else COT_SO_KU
            _so_gqvl_r = int(df_filtered[COT_SO_KU].astype(str).str.strip().isin(
                set(df_gqvl[_gqvl_ku_col].dropna().astype(str).str.strip())
            ).sum()) if _gqvl_ku_col in df_gqvl.columns else 0
        else:
            _so_gqvl_r = 0

        # Results header
        st.divider()
        _render_results_header(df_filtered, df, _so_nq11_r, _so_gqvl_r, username)
        
        # Results grid
        st.divider()
        
        # Pagination
        if "tc_page" not in st.session_state:
            st.session_state.tc_page = 0
        
        page_size = 12
        total_pages = (len(df_filtered) + page_size - 1) // page_size if not df_filtered.empty else 0
        
        # Page navigation
        if total_pages > 1:
            col_nav1, col_nav2, col_nav3 = st.columns([1, 2, 1])
            with col_nav1:
                if st.button("← Trước", disabled=st.session_state.tc_page <= 0, use_container_width=True, key="tc_prev"):
                    st.session_state.tc_page = max(0, st.session_state.tc_page - 1)
                    st.rerun()
            with col_nav2:
                st.markdown(f"<div style='text-align:center'>Trang **{st.session_state.tc_page + 1}** / {total_pages}</div>", unsafe_allow_html=True)
            with col_nav3:
                if st.button("Tiếp →", disabled=st.session_state.tc_page >= total_pages - 1, use_container_width=True, key="tc_next"):
                    st.session_state.tc_page = min(total_pages - 1, st.session_state.tc_page + 1)
                    st.rerun()
        
        # Slice data for current page
        if not df_filtered.empty:
            start_idx = st.session_state.tc_page * page_size
            end_idx = min(start_idx + page_size, len(df_filtered))
            df_page = df_filtered.iloc[start_idx:end_idx]
            
            # Render grid
            render_result_grid(
                df=df_page,
                df_nq11=df_nq11,
                df_gqvl=df_gqvl,
                columns=2 if st.session_state.get("tc_view_mode") == "compact" else 1,
                on_detail_click="tc_selected_ku",
            )
        
        # Detail drawer
        selected_ku = st.session_state.get("tc_selected_ku")
        if selected_ku:
            _render_detail_drawer(df_filtered, selected_ku, df_nq11, df_gqvl)


# Backward compatibility
render_tab = render
