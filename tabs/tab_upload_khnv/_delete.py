"""Xóa dữ liệu PGD — chỉ admin/manager."""
from __future__ import annotations

import socket
from pathlib import Path

import streamlit as st

import db
from auth import la_phan_he_cn, normalize_role
from config import DS_PGD, DON_VI_CHI_NHANH
from data.pgd import duong_dan_pgd, kiem_tra_file_ton_tai_pgd
from logger import get_logger
from services.file_detection_service import DS_DON_VI
from services.upload_service import merge_du_lieu_toan_cn, lay_meta_merge
from utils import fmt_so
from ._state import xoa_cache_trang_thai

logger = get_logger(__name__)


def _xoa_mot_pgd(ten_pgd: str, loai: str, username: str) -> tuple[bool, str]:
    """Xóa file gốc + cache parquet của 1 PGD cho 1 loại."""
    hostname = socket.gethostname()
    paths_can_xoa = [Path(duong_dan_pgd(ten_pgd, loai))]
    if loai == "hstd":
        paths_can_xoa.append(Path(duong_dan_pgd(ten_pgd, "hstd_khnv")))

    if not any(p.exists() for p in paths_can_xoa):
        return False, f"Không tìm thấy file {loai.upper()} của {ten_pgd}"

    try:
        for p in paths_can_xoa:
            if p.exists():
                p.unlink()
            pq = p.with_suffix(".parquet")
            if pq.exists():
                pq.unlink()
        db.ghi_audit(username, "xoa_du_lieu_pgd", f"[{hostname}] {loai.upper()} — {ten_pgd}")
        return True, f"✅ Đã xóa {loai.upper()} — {ten_pgd}"
    except Exception as e:
        logger.error("_xoa_mot_pgd: %s", e, exc_info=True)
        db.ghi_audit(username, "loi_xoa_du_lieu_pgd",
                     f"[{hostname}] {loai.upper()} — {ten_pgd}: {e}")
        return False, f"❌ Lỗi xóa: {e}"


def _thuc_hien_xoa(ds_don_vi: list[str], loai_xoa: list[str], username: str) -> None:
    ket_qua = []
    can_merge_loai: set[str] = set()

    with st.spinner("🗑️ Đang xóa dữ liệu..."):
        for ten_pgd in ds_don_vi:
            for loai in loai_xoa:
                ok, msg = _xoa_mot_pgd(ten_pgd, loai, username)
                ket_qua.append((ten_pgd, loai, ok, msg))
                if ok and loai in ("hstd", "nq11", "gqvl"):
                    can_merge_loai.add(loai)

    so_thanh_cong = sum(1 for _, _, ok, _ in ket_qua if ok)
    so_loi = len(ket_qua) - so_thanh_cong

    if so_thanh_cong:
        st.success(
            f"✅ Đã xóa **{so_thanh_cong}** file thành công"
            + (f" · ⚠️ {so_loi} lỗi" if so_loi else "")
        )
    for _, _, ok, msg in ket_qua:
        if not ok:
            st.warning(msg)

    if can_merge_loai:
        st.divider()
        for loai in sorted(can_merge_loai):
            with st.spinner(f"🔄 Đang rebuild CACHE {loai.upper()}..."):
                try:
                    kq_merge = merge_du_lieu_toan_cn(loai)
                    if kq_merge.thanh_cong:
                        meta = lay_meta_merge(loai)
                        so_pgd  = (meta or {}).get("so_pgd", "?")
                        so_dong = (meta or {}).get("so_dong", 0)
                        st.success(
                            f"✅ Rebuild **{loai.upper()}** — "
                            f"**{so_pgd}** đơn vị · **{fmt_so(so_dong)}** dòng"
                        )
                    else:
                        st.warning(f"⚠️ Rebuild {loai.upper()}: {kq_merge.thong_bao}")
                except Exception as e:
                    logger.error("rebuild: %s", e, exc_info=True)
                    st.error(f"❌ Lỗi rebuild {loai.upper()}: {e}")

    st.cache_data.clear()
    xoa_cache_trang_thai()
    st.rerun()


def render(role: str, username: str) -> None:
    """Xóa dữ liệu PGD — chỉ admin/manager."""
    if not la_phan_he_cn(role) or normalize_role(role) == "executive":
        st.error("🔒 Chức năng này chỉ dành cho admin/manager.")
        return

    st.caption(
        "Xóa file pgd_data/ của PGD — hệ thống tự động rebuild CACHE sau khi xóa."
    )

    che_do = st.radio(
        "Chế độ xóa",
        ["Xóa từng PGD", "Xóa tất cả 22 đơn vị"],
        horizontal=True,
        key="xoa_pgd_che_do",
    )

    loai_xoa = st.multiselect(
        "Loại dữ liệu cần xóa",
        options=["hstd", "nq11", "gqvl", "cdtotkvv"],
        default=["hstd", "nq11", "gqvl"],
        format_func=lambda x: x.upper(),
        key="xoa_pgd_loai",
    )

    if not loai_xoa:
        st.info("Chọn ít nhất 1 loại dữ liệu cần xóa.")
        return

    if che_do == "Xóa từng PGD":
        pgd_co_file = [
            dv for dv in DS_DON_VI
            if any(kiem_tra_file_ton_tai_pgd(dv, l) for l in loai_xoa)
        ]
        if not pgd_co_file:
            st.info("ℹ️ Không có đơn vị nào có dữ liệu để xóa.")
            return

        ten_pgd_chon = st.selectbox("Chọn đơn vị cần xóa", pgd_co_file, key="xoa_pgd_chon_dv")

        st.markdown("**File sẽ bị xóa:**")
        cols_prev = st.columns(4)
        for col, loai in zip(cols_prev, ["hstd", "nq11", "gqvl", "cdtotkvv"]):
            co = kiem_tra_file_ton_tai_pgd(ten_pgd_chon, loai)
            se_xoa = loai in loai_xoa and co
            col.markdown(
                f"**{loai.upper()}**  \n"
                f"{'🗑️ Sẽ xóa' if se_xoa else ('⬜ Không có' if not co else '⏩ Bỏ qua')}"
            )

        st.warning(
            f"⚠️ Sẽ xóa **{', '.join(l.upper() for l in loai_xoa)}** "
            f"của **{ten_pgd_chon}** và rebuild CACHE."
        )
        if st.button(f"🗑️ Xác nhận xóa — {ten_pgd_chon}", type="primary", key="btn_xoa_1dv"):
            _thuc_hien_xoa([ten_pgd_chon], loai_xoa, username)

    else:
        st.error(
            f"⚠️ **CẢNH BÁO:** Sẽ xóa **{', '.join(l.upper() for l in loai_xoa)}** "
            f"của **TẤT CẢ {len(DS_DON_VI)} đơn vị** và rebuild CACHE từ đầu."
        )
        xac_nhan = st.checkbox("Tôi hiểu hành động này không thể hoàn tác", key="xoa_all_xac_nhan")
        if xac_nhan:
            if st.button("🗑️ Xóa tất cả và rebuild CACHE", type="primary", key="btn_xoa_all"):
                _thuc_hien_xoa(DS_DON_VI, loai_xoa, username)
