"""Upload NQ11 / GQVL / CDTOTKVV toàn Chi nhánh."""
from __future__ import annotations

from io import BytesIO

import pandas as pd
import streamlit as st

import db
from config import DS_PGD, DON_VI_CHI_NHANH
from data.pgd import kiem_tra_file_ton_tai_pgd
from logger import get_logger
from services.upload_service import merge_du_lieu_toan_cn
from ._state import them_vao_hang_cho, xoa_cache_trang_thai

logger = get_logger(__name__)


def render_cdto_toan_cn(username: str) -> None:
    """Upload 1 file CDTOTKVV tổng hợp toàn CN → tự tách và lưu 22 PGD."""
    st.info(
        "Upload 1 file CDTOTKVV tổng hợp của toàn CN — hệ thống tự tách và "
        "lưu cho từng PGD (không cần upload 22 lần riêng lẻ)."
    )

    _ver = st.session_state.setdefault("cdto_cn_ver", 0)
    uploaded = st.file_uploader(
        "Chọn file CDTOTKVV toàn CN",
        type=["xlsx", "xls"],
        key=f"cdto_cn_uploader_{_ver}",
        label_visibility="collapsed",
    )

    _SS_BYTES   = "cdto_cn_bytes"
    _SS_PREVIEW = "cdto_cn_preview"
    _SS_FILE_ID = "cdto_cn_file_id"

    if uploaded is not None:
        file_id = (uploaded.name, uploaded.size)
        if st.session_state.get(_SS_FILE_ID) != file_id:
            st.session_state[_SS_FILE_ID] = file_id
            st.session_state[_SS_BYTES]   = uploaded.read()
            st.session_state.pop(_SS_PREVIEW, None)

    if _SS_BYTES not in st.session_state:
        return

    file_bytes: bytes = st.session_state[_SS_BYTES]

    if _SS_PREVIEW not in st.session_state:
        with st.spinner("🔍 Đang phân tích file..."):
            try:
                from data.cdtotkvv import (
                    tach_file_cdto_toan_cn,
                    doc_thang_tu_cdto_toan_cn,
                    doc_thang_nam_tu_file,
                )

                pgd_map = tach_file_cdto_toan_cn(file_bytes)
                thang   = doc_thang_nam_tu_file(file_bytes) or doc_thang_tu_cdto_toan_cn(file_bytes)
                ds_tat_ca = [DON_VI_CHI_NHANH] + DS_PGD
                thieu = [dv for dv in ds_tat_ca if dv not in pgd_map]

                preview_rows = []
                for ten_pgd, pgd_bytes in sorted(pgd_map.items()):
                    so_to: int | str = "?"
                    try:
                        df_tmp = pd.read_excel(
                            BytesIO(pgd_bytes), engine="openpyxl",
                            header=None, skiprows=10,
                        )
                        so_to = int(pd.to_numeric(
                            df_tmp.iloc[:, 0], errors="coerce"
                        ).notna().sum())
                    except Exception:
                        pass

                    da_co = kiem_tra_file_ton_tai_pgd(ten_pgd, "cdtotkvv")
                    preview_rows.append({
                        "Đơn vị": ten_pgd,
                        "Số tổ": so_to,
                        "Hiện tại": "🔄 Cập nhật" if da_co else "🆕 Mới",
                        "Trạng thái": "✅ Sẵn sàng",
                    })

                st.session_state[_SS_PREVIEW] = {
                    "rows": preview_rows, "thang": thang,
                    "thieu": thieu, "so_dv": len(pgd_map),
                }
            except ValueError as e:
                st.error(f"❌ {e}")
                return
            except Exception as e:
                logger.error("render_cdto_toan_cn: lỗi phân tích — %s", e, exc_info=True)
                st.error(f"❌ Lỗi phân tích file: {e}")
                return

    preview = st.session_state.get(_SS_PREVIEW)
    if not preview:
        return

    thang = preview["thang"]
    c1, c2 = st.columns(2)
    c1.metric("Tháng báo cáo", thang or "⚠️ Không đọc được")
    c2.metric("Số đơn vị nhận diện", preview["so_dv"])

    if preview["thieu"]:
        st.warning(
            f"⚠️ Thiếu **{len(preview['thieu'])}** đơn vị: "
            + ", ".join(preview["thieu"])
        )

    def _style_ht(v: str) -> str:
        if v.startswith("🆕"):
            return "background-color:#d4edda;color:#155724;font-weight:bold"
        if v.startswith("🔄"):
            return "background-color:#fff3cd;color:#856404"
        return ""

    df_prev = pd.DataFrame(preview["rows"])
    st.dataframe(
        df_prev.style.map(_style_ht, subset=["Hiện tại"]),
        use_container_width=True, hide_index=True,
        height=min(600, 60 + len(preview["rows"]) * 35),
    )

    if preview["so_dv"] < 2:
        st.error("❌ File phải có ít nhất 2 đơn vị — đây có thể là file 1 PGD.")
        return

    if st.button(
        f"📤 Upload {preview['so_dv']} đơn vị",
        type="primary",
        key="btn_cdto_cn_upload",
    ):
        with st.spinner("⏳ Đang tách và lưu từng PGD..."):
            from services.upload_service import xu_ly_cdto_toan_cn
            ket_qua = xu_ly_cdto_toan_cn(file_bytes)

        if "_loi_doc" in ket_qua:
            st.error(ket_qua["_loi_doc"].thong_bao)
            return

        for ten_pgd, kq in ket_qua.items():
            if kq.thanh_cong:
                db.ghi_audit(
                    username, "upload_cdto_toan_cn",
                    f"CDTOTKVV toàn CN — {ten_pgd} · tháng {thang or 'unknown'}",
                )

        so_ok = sum(1 for v in ket_qua.values() if v.thanh_cong)
        if so_ok:
            st.success(f"✅ Đã lưu **{so_ok}** đơn vị thành công")
        for ten_pgd, kq in ket_qua.items():
            if not kq.thanh_cong:
                st.warning(f"⚠️ {ten_pgd}: {kq.thong_bao}")

        st.cache_data.clear()
        for _k in (_SS_PREVIEW, _SS_BYTES, _SS_FILE_ID):
            st.session_state.pop(_k, None)
        xoa_cache_trang_thai()
        st.session_state["cdto_cn_ver"] = _ver + 1
        st.rerun()


def render_nq11_toan_cn(username: str) -> None:
    """Upload file NQ11 một lần để lấy danh sách mã khế ước.
    Sau khi lưu, thêm 'nq11' vào pending queue để merge."""
    meta = db.doc_kv("nq11_meta") or {}
    if meta:
        c1, c2, c3 = st.columns(3)
        c1.metric("Số mã khế ước đã lưu", f"{meta.get('so_luong', 0):,}".replace(",", "."))
        c2.metric("Ngày cập nhật", meta.get("ngay_upload", "—"))
        c3.metric("Người upload", meta.get("nguoi_upload", "—"))
    else:
        st.info(
            "ℹ️ Chưa có danh sách mã khế ước NQ11. "
            "Upload file NQ11 một lần để hệ thống nhận biết món vay NQ11 trong HSTD."
        )

    st.caption(
        "Vì các khoản vay NQ11 đã ngừng phát sinh mới, chỉ cần upload 1 lần. "
        "Hệ thống lưu danh sách **Số khế ước** để gắn nhãn NQ11 vào HSTD."
    )

    _ver = st.session_state.setdefault("nq11_ids_ver", 0)
    uploaded = st.file_uploader(
        "Chọn file sao kê NQ11 (.xlsx)",
        type=["xlsx", "xls"],
        key=f"nq11_ids_uploader_{_ver}",
        label_visibility="collapsed",
    )

    if uploaded is None:
        return

    btn_label = "🔄 Cập nhật danh sách" if meta else "💾 Lưu danh sách mã khế ước"
    if st.button(btn_label, type="primary", key="btn_nq11_luu_ids"):
        with st.spinner("⏳ Đang đọc file và lưu danh sách..."):
            from data.hstd import luu_so_khe_uoc_nq11
            try:
                file_bytes = uploaded.read()
                so_luong, err = luu_so_khe_uoc_nq11(file_bytes, username)
            except Exception as e:
                logger.error("render_nq11_toan_cn: lỗi lưu IDs — %s", e, exc_info=True)
                st.error(f"❌ Lỗi: {e}")
                return

        if err:
            st.error(f"❌ {err}")
            return

        st.success(f"✅ Đã lưu **{so_luong:,}** mã khế ước NQ11.".replace(",", "."))
        # Thêm vào pending queue để merge HSTD với nhãn NQ11 mới
        them_vao_hang_cho("nq11")
        st.info("⏳ Chuyển sang tab **📊 Tổng quan** → bấm **🔄 Merge toàn CN** để áp dụng.")
        st.cache_data.clear()
        st.session_state["nq11_ids_ver"] = _ver + 1
        st.rerun()


def render_gqvl_toan_cn(username: str, df_hstd=None) -> None:
    """Upload 1 file GQVL tổng hợp toàn CN → tự tách và lưu 22 PGD."""
    st.info(
        "Upload 1 file GQVL tổng hợp của toàn CN — hệ thống dùng **Số khế ước** "
        "đối chiếu với HSTD để tự động phân bổ về từng PGD.  \n"
        "Số KU không khớp với HSTD sẽ được gán về **Hội sở Chi nhánh tỉnh**."
    )

    if df_hstd is None or df_hstd.empty:
        st.warning(
            "⚠️ Chưa có dữ liệu HSTD — không thể phân bổ GQVL về PGD. "
            "Hãy upload và merge HSTD trước, sau đó quay lại tab này."
        )
        return

    _SS_BYTES   = "gqvl_cn_bytes"
    _SS_PREVIEW = "gqvl_cn_preview"
    _SS_FILE_ID = "gqvl_cn_file_id"
    _ver = st.session_state.setdefault("gqvl_cn_ver", 0)

    uploaded = st.file_uploader(
        "Chọn file GQVL toàn CN",
        type=["xlsx", "xls"],
        key=f"gqvl_cn_uploader_{_ver}",
        label_visibility="collapsed",
    )

    if uploaded is not None:
        file_id = (uploaded.name, uploaded.size)
        if st.session_state.get(_SS_FILE_ID) != file_id:
            st.session_state[_SS_FILE_ID] = file_id
            st.session_state[_SS_BYTES]   = uploaded.read()
            st.session_state.pop(_SS_PREVIEW, None)

    if _SS_BYTES not in st.session_state:
        return

    file_bytes: bytes = st.session_state[_SS_BYTES]

    if _SS_PREVIEW not in st.session_state:
        with st.spinner("🔍 Đang phân tích file GQVL & đối chiếu HSTD..."):
            try:
                from services.upload_service import tach_file_gqvl_toan_cn
                pgd_map = tach_file_gqvl_toan_cn(file_bytes, df_hstd=df_hstd)
            except ValueError as e:
                st.error(f"❌ {e}")
                return
            except Exception as e:
                logger.error("render_gqvl_toan_cn: lỗi phân tích — %s", e, exc_info=True)
                st.error(f"❌ Lỗi phân tích file: {e}")
                return

            ds_tat_ca = [DON_VI_CHI_NHANH] + DS_PGD
            thieu = [dv for dv in ds_tat_ca if dv not in pgd_map]

            preview_rows = []
            for ten_pgd in ds_tat_ca:
                if ten_pgd in pgd_map:
                    try:
                        df_tmp = pd.read_excel(BytesIO(pgd_map[ten_pgd]), engine="openpyxl", header=7)
                        so_dong_val = len(df_tmp.dropna(how="all"))
                    except Exception:
                        so_dong_val = "?"
                else:
                    so_dong_val = 0
                da_co = kiem_tra_file_ton_tai_pgd(ten_pgd, "gqvl")
                preview_rows.append({
                    "Đơn vị": ten_pgd,
                    "Số dòng": so_dong_val,
                    "Hiện tại": "🔄 Cập nhật" if da_co else ("—" if so_dong_val == 0 else "🆕 Mới"),
                    "Trạng thái": "✅ Sẵn sàng" if ten_pgd in pgd_map else "⚠️ Thiếu trong file",
                })

            st.session_state[_SS_PREVIEW] = {
                "rows": preview_rows, "thieu": thieu,
                "so_dv": len(pgd_map), "pgd_map": pgd_map,
            }

    preview = st.session_state.get(_SS_PREVIEW)
    if not preview:
        return

    c1, c2 = st.columns(2)
    c1.metric("Số đơn vị có GQVL", preview["so_dv"])
    c2.metric("Tổng số đơn vị CN", len([DON_VI_CHI_NHANH] + DS_PGD))

    if preview["thieu"]:
        st.warning(
            f"⚠️ **{len(preview['thieu'])}** đơn vị không có dữ liệu GQVL: "
            + ", ".join(preview["thieu"])
        )

    def _style_ht(v: str) -> str:
        if v.startswith("🆕"):
            return "background-color:#d4edda;color:#155724;font-weight:bold"
        if v.startswith("🔄"):
            return "background-color:#fff3cd;color:#856404"
        return ""

    df_prev = pd.DataFrame(preview["rows"])
    st.dataframe(
        df_prev.style.map(_style_ht, subset=["Hiện tại"]),
        use_container_width=True, hide_index=True,
        height=min(600, 60 + len(preview["rows"]) * 35),
    )

    if st.button(
        f"📤 Upload {preview['so_dv']} đơn vị → hàng chờ",
        type="primary",
        key="btn_gqvl_cn_upload",
    ):
        with st.spinner("⏳ Đang tách và lưu từng PGD..."):
            from services.upload_service import xu_ly_gqvl_toan_cn
            ket_qua = xu_ly_gqvl_toan_cn(file_bytes, df_hstd=df_hstd)

        if "_loi_doc" in ket_qua:
            st.error(ket_qua["_loi_doc"].thong_bao)
            return

        for ten_pgd, kq in ket_qua.items():
            if kq.thanh_cong:
                db.ghi_audit(username, "upload_gqvl_toan_cn", f"GQVL toàn CN — {ten_pgd}")

        so_ok = sum(1 for v in ket_qua.values() if v.thanh_cong)
        if so_ok:
            st.success(f"✅ Đã lưu **{so_ok}** đơn vị thành công")
            them_vao_hang_cho("gqvl")
            st.info("⏳ Chuyển sang tab **📊 Tổng quan** → bấm **🔄 Merge toàn CN**.")
        for ten_pgd, kq in ket_qua.items():
            if not kq.thanh_cong:
                st.warning(f"⚠️ {ten_pgd}: {kq.thong_bao}")

        st.cache_data.clear()
        for _k in (_SS_PREVIEW, _SS_BYTES, _SS_FILE_ID):
            st.session_state.pop(_k, None)
        xoa_cache_trang_thai()
        st.session_state["gqvl_cn_ver"] = _ver + 1
        st.rerun()
