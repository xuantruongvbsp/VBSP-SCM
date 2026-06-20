"""Trung tâm Tự động hóa Văn bản — điền mẫu Word hàng loạt từ dữ liệu HSTD."""
from __future__ import annotations

from datetime import datetime

import streamlit as st
import pandas as pd
from streamlit.delta_generator import DeltaGenerator

from config import (
    COT_TEN_PGD, COT_TEN_XA, COT_TEN_KH, COT_SO_KU, COT_MA_KH,
    TEMPLATES_DIR, TAG_MAP,
    danh_sach_nam_baseline, danh_sach_nam_baseline_pgd,
)
from auth import is_pgd_role
from utils import quet_templates, auto_fill_document, auto_fill_batch
from logger import get_logger

logger = get_logger(__name__)


def _init_session(df: pd.DataFrame, role: str, pgd_user: str | None) -> None:
    """Khởi tạo st.session_state gb2_xa / gb2_nam để các tab giao ban dùng chung."""
    if df is None or df.empty:
        return
    if is_pgd_role(role) and pgd_user and COT_TEN_PGD in df.columns:
        df = df[df[COT_TEN_PGD] == pgd_user].copy()
    if COT_TEN_XA not in df.columns:
        return
    ds_xa = sorted(df[COT_TEN_XA].dropna().unique().tolist())
    if not ds_xa:
        return
    if "gb2_xa" not in st.session_state or st.session_state.gb2_xa not in ds_xa:
        st.session_state.gb2_xa = ds_xa[0]
    ds_nam = danh_sach_nam_baseline_pgd() or danh_sach_nam_baseline()
    if ds_nam and (
        "gb2_nam" not in st.session_state or st.session_state.gb2_nam not in ds_nam
    ):
        st.session_state.gb2_nam = ds_nam[0]


def render(tab: DeltaGenerator = None, **kwargs) -> None:
    """Trung tâm tự động hóa văn bản — điền mẫu Word, xuất hàng loạt."""
    df      = kwargs.get("df")
    df_nq11 = kwargs.get("df_nq11")
    role    = kwargs.get("role")
    pgd_user = kwargs.get("pgd_user")

    _init_session(df, role, pgd_user)

    ctx = tab if tab is not None else st.container()
    with ctx:
        st.subheader("📄 Trung tâm Tự động hóa Văn bản")
        st.caption("Chọn hồ sơ → Chọn mẫu biểu → Tải về bản hoàn thiện tự động")

        templates = quet_templates(TEMPLATES_DIR)
        if not templates:
            st.warning(f"⚠️ Chưa có file mẫu nào trong thư mục `templates/`")
            st.info(
                "**Cách thêm mẫu biểu:**\n"
                f"1. Tạo file Word `.docx` với các tag như `{{{{ten_kh}}}}`, `{{{{so_ku}}}}` ...\n"
                f"2. Copy vào thư mục: `{TEMPLATES_DIR}`\n"
                "3. Reload trang là xuất hiện trong danh sách\n\n"
                "**Các tag hỗ trợ sẵn:**\n"
                + "\n".join(f"- `{tag}` → cột *{col}*" for tag, col in TAG_MAP.items())
            )
            return

        st.success(f"✅ Có **{len(templates)}** mẫu biểu sẵn sàng")

        st.markdown("**① Chọn đối tượng**")
        doi_tuong = st.radio(
            "Chọn đối tượng xuất văn bản",
            ["Từng hồ sơ khách hàng", "Theo Xã/Phường (xuất hàng loạt)"],
            horizontal=True, key="op_dh_doi_tuong", label_visibility="collapsed",
        )

        df_chon = None

        if doi_tuong == "Từng hồ sơ khách hàng":
            kw = st.text_input("🔍 Tìm khách hàng",
                               placeholder="Tên KH hoặc Số khế ước...", key="op_dh_kw")
            if kw:
                mask = (df[[c for c in [COT_TEN_KH, COT_SO_KU, COT_MA_KH] if c in df.columns]]
                        .astype(str).apply(lambda c: c.str.contains(kw, case=False, na=False)).any(axis=1))
                df_tim = df[mask]
                if df_tim.empty:
                    st.warning("Không tìm thấy.")
                else:
                    opts = ((df_tim[COT_TEN_KH].astype(str) + "  —  " +
                             df_tim[COT_SO_KU].astype(str)) if COT_SO_KU in df_tim.columns
                            else df_tim[COT_TEN_KH].astype(str))
                    chon = st.multiselect("Chọn hồ sơ (có thể chọn nhiều)",
                                          opts.tolist(), key="op_dh_hs_sel")
                    if chon:
                        idx_list = [opts.tolist().index(c) for c in chon]
                        df_chon  = df_tim.iloc[idx_list].reset_index(drop=True)
                        st.info(f"Đã chọn **{len(df_chon)}** hồ sơ")
        else:
            if COT_TEN_XA in df.columns:
                ds_xa   = sorted(df[COT_TEN_XA].dropna().unique().tolist())
                chon_xa = st.selectbox("Chọn Xã/Phường", ds_xa, key="op_dh_xa")
                df_chon = df[df[COT_TEN_XA] == chon_xa].copy()
                st.info(f"Xã **{chon_xa}**: **{len(df_chon)}** hồ sơ")
            else:
                st.warning("Không tìm thấy cột Tên xã trong dữ liệu.")

        if df_chon is None or len(df_chon) == 0:
            st.info("👆 Chọn hồ sơ hoặc xã/phường để tiếp tục.")
            return

        st.markdown("**② Chọn mẫu biểu**")
        ten_mau_list  = [t[0] for t in templates]
        path_mau_list = [t[1] for t in templates]
        chon_mau_list = st.multiselect("Chọn 1 hoặc nhiều mẫu biểu",
                                       ten_mau_list, key="op_dh_mau_sel")

        with st.expander("📋 Xem tất cả mẫu biểu & tag hỗ trợ"):
            for ten, path in templates:
                st.markdown(f"**📄 {ten}**  `{path.name}`")
            st.markdown(
                "**📋 Biên bản giao ban xã** — `BB_giao_ban_xa_template.docx` "
                "(xuất Word tại sub-tab **📋 Biên bản giao ban**)."
            )
            st.divider()
            st.markdown("**Tag hỗ trợ trong file Word:**")
            for tag, col in TAG_MAP.items():
                st.caption(f"`{tag}` → {col}")

        if not chon_mau_list:
            st.info("👆 Chọn ít nhất 1 mẫu biểu.")
            return

        st.markdown("**③ Xuất văn bản**")
        che_do_xuat = st.radio(
            "Chế độ xuất",
            ["Mỗi hồ sơ 1 file riêng", "Gộp tất cả vào 1 file (hàng loạt)"],
            horizontal=True, key="op_dh_xuat_mode",
        ) if len(df_chon) > 1 else "Mỗi hồ sơ 1 file riêng"

        dh_ss_key = "_dh_docx_hub"
        if st.button("🖨️ Tạo văn bản", type="primary", key="dh_btn_xuat"):
            results = []
            for ten_mau in chon_mau_list:
                idx_mau  = ten_mau_list.index(ten_mau)
                path_mau = path_mau_list[idx_mau]
                if not path_mau.exists():
                    st.error(f"Không tìm thấy file: {path_mau}"); continue
                try:
                    if che_do_xuat == "Mỗi hồ sơ 1 file riêng":
                        for i, (_, row) in enumerate(df_chon.iterrows()):
                            ten_kh = str(row.get(COT_TEN_KH, f"hs_{i+1}"))
                            fname  = f"{path_mau.stem}_{ten_kh}_{datetime.today().strftime('%d%m%Y')}.docx"
                            data   = auto_fill_document(row, str(path_mau), TAG_MAP)
                            results.append((f"{ten_mau} — {ten_kh}", data, fname, f"dl_{ten_mau}_{i}"))
                    else:
                        fname = f"{path_mau.stem}_batch_{datetime.today().strftime('%d%m%Y')}.docx"
                        data  = auto_fill_batch(df_chon, str(path_mau), TAG_MAP)
                        results.append((f"⬇ {ten_mau} — {len(df_chon)} hồ sơ (gộp)", data, fname, f"dl_batch_{ten_mau}"))
                    st.success(f"✅ Đã tạo: **{ten_mau}**")
                except Exception as e:
                    logger.error("tab_doc_hub auto_fill: %s", e, exc_info=True)
                    st.error(f"Lỗi tạo {ten_mau}: {e}")
            st.session_state[dh_ss_key] = results

        if st.session_state.get(dh_ss_key):
            for label, data, fname, key in st.session_state[dh_ss_key]:
                st.download_button(
                    f"⬇ {label}", data=data, file_name=fname,
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    key=key,
                )
