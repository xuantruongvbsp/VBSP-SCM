"""Panel Merge toàn CN — pending queue + progress + rebuild cache."""
from __future__ import annotations

import streamlit as st

import db
from logger import get_logger
from services.upload_service import merge_nhieu_loai_toan_cn
from utils import fmt_so
from ._state import lay_hang_cho, xoa_hang_cho, xoa_cache_trang_thai, lam_moi_du_lieu_app

logger = get_logger(__name__)

_NHAN_LOAI = {"hstd": "📊 HSTD", "nq11": "📑 NQ11", "gqvl": "📋 GQVL"}


def _thuc_hien_merge(loai_merge: list[str], username: str) -> list[dict]:
    tong = len(loai_merge)
    bar = st.progress(0.0, text="⏳ Bắt đầu merge...")
    bar.progress(0.1, text=f"🔄 Đang merge {', '.join(x.upper() for x in loai_merge)}...")
    ket_qua = merge_nhieu_loai_toan_cn(loai_merge)
    bar.progress(1.0, text="✅ Hoàn tất!")
    return ket_qua


def _hien_thi_ket_qua_merge(ket_qua: list[dict]) -> None:
    if not ket_qua:
        return
    st.markdown("##### Kết quả merge")
    cols = st.columns(len(ket_qua))
    for col, row in zip(cols, ket_qua):
        loai_m = str(row.get("loai", "")).upper()
        sp = row.get("so_pgd")
        sd = row.get("so_dong")
        if row.get("thanh_cong"):
            col.success(
                f"**{loai_m}**\n\n"
                + (f"**{sp}** đơn vị" if sp else "")
                + (f" · **{fmt_so(sd)}** dòng" if sd else "")
            )
        else:
            col.warning(f"**{loai_m}**\n\n{row.get('thong_bao', '')}")


def render(username: str) -> None:
    """Panel Merge toàn CN: pending queue và rebuild cache."""
    hang_cho = lay_hang_cho()

    # ── Pending queue ────────────────────────────────────────────────────
    if hang_cho:
        loai_str = ", ".join(sorted(hang_cho)).upper()
        st.info(
            f"⏳ **{len(hang_cho)} loại đang chờ merge:** {loai_str}  \n"
            "Bấm nút bên dưới để tổng hợp dữ liệu toàn Chi nhánh."
        )
        if st.button(
            f"🔄 Merge toàn CN ({loai_str})",
            type="primary",
            key="btn_merge_pending",
        ):
            ket_qua = _thuc_hien_merge(sorted(hang_cho), username)
            xoa_hang_cho()
            _hien_thi_ket_qua_merge(ket_qua)
            if any(row.get("thanh_cong") for row in ket_qua):
                lam_moi_du_lieu_app()
            xoa_cache_trang_thai()
            db.ghi_audit(username, "merge_toan_cn",
                         f"Merge thành công: {loai_str}")
            st.toast("✅ Merge hoàn tất!", icon="✅")
            st.rerun()
    else:
        st.success("✅ Không có dữ liệu nào chờ merge.")

    # ── Rebuild cache thủ công ───────────────────────────────────────────
    st.divider()
    st.markdown("**🔄 Rebuild Cache thủ công**")
    st.caption("Dùng khi cần đồng bộ lại dữ liệu toàn Chi nhánh mà không upload lại file.")

    loai_chon = st.multiselect(
        "Chọn loại cần rebuild:",
        options=["hstd", "nq11", "gqvl"],
        default=["hstd", "nq11", "gqvl"],
        format_func=lambda x: _NHAN_LOAI.get(x, x.upper()),
        key="rebuild_cache_loai_chon",
    )
    if st.button(
        "🔄 Rebuild Cache",
        type="secondary",
        key="btn_rebuild_cache",
        disabled=not loai_chon,
    ):
        if loai_chon:
            ket_qua = _thuc_hien_merge(loai_chon, username)
            _hien_thi_ket_qua_merge(ket_qua)
            if any(row.get("thanh_cong") for row in ket_qua):
                lam_moi_du_lieu_app()
            xoa_cache_trang_thai()
            db.ghi_audit(username, "merge_toan_cn",
                         f"Rebuild cache: {', '.join(loai_chon)}")
            st.toast("✅ Rebuild hoàn tất!", icon="✅")
            st.rerun()
