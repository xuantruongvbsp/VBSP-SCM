"""UI quản lý snapshot dữ liệu.

Màn này thuộc luồng Upload dữ liệu: chạy lại snapshot kỳ hiện tại, bơm snapshot
kỳ cũ và kiểm tra/xóa snapshot đã lưu.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import streamlit as st

import db
from logger import get_logger
from snapshot_service import (
    danh_sach_ky,
    validate_snapshot,
    xoa_snapshot,
)


logger = get_logger(__name__)


_SNAPSHOT_META = {
    "HSTD": ("hstd_snapshot", "ngay_so_lieu"),
    "Thôn": ("thon_snapshot", "ngay_so_lieu"),
    "Ủy thác": ("uy_thac_snapshot", "ngay_so_lieu"),
    "NQ11": ("nq11_snapshot", "ngay_bc"),
    "GQVL": ("gqvl_snapshot", None),
    "CDTOTKVV": ("cdtotkvv_snapshot", None),
    "CBTD–Tổ": ("cbtd_to_tkvv_snapshot", None),
}


def _doc_snapshot_inventory() -> list[dict]:
    rows_out: list[dict] = []
    try:
        with db.get_conn() as conn:
            for label, (table, date_col) in _SNAPSHOT_META.items():
                date_expr = f"MAX({date_col})" if date_col else "NULL"
                rows = conn.execute(
                    f"""SELECT ky, COUNT(*) AS so_dong, MAX(created_at) AS ngay_tao,
                               {date_expr} AS ngay_so_lieu
                        FROM {table}
                        GROUP BY ky
                        ORDER BY ky DESC"""
                ).fetchall()
                for row in rows:
                    rows_out.append({
                        "Loại": label,
                        "Kỳ": row["ky"],
                        "Số dòng": row["so_dong"],
                        "Ngày tạo": row["ngay_tao"] or "",
                        "Ngày số liệu": row["ngay_so_lieu"] or "",
                    })
    except Exception as e:
        logger.error("_doc_snapshot_inventory: lỗi đọc danh sách snapshot — %s", e, exc_info=True)
        st.error(f"❌ Lỗi đọc danh sách snapshot: {e}")
    return rows_out


def _build_matrix_ky_loai(rows: list[dict]) -> "pd.DataFrame | None":
    """Dựng ma trận Kỳ × Loại (ô = số dòng snapshot) từ inventory."""
    if not rows:
        return None
    try:
        import pandas as pd

        df = pd.DataFrame(rows)
        matrix = (
            df.pivot_table(index="Kỳ", columns="Loại", values="Số dòng", aggfunc="sum")
            .reindex(columns=[lbl for lbl in _SNAPSHOT_META if lbl in set(df["Loại"])])
            .sort_index(ascending=False)
        )
        return matrix
    except Exception as e:
        logger.error("_build_matrix_ky_loai: %s", e, exc_info=True)
        return None


def _render_chay_lai_snapshot(username: str) -> None:
    """Chạy lại các snapshot HSTD kỳ hiện tại từ cache hiện hành."""
    _upload_ver = st.session_state.setdefault("ql_snap_bom_upload_ver", 0)
    st.markdown("#### 🔁 Chạy lại snapshot HSTD kỳ hiện tại")
    st.caption(
        "Đọc `cache/hstd.parquet` và ghi lại HSTD / Thôn / Ủy thác. "
        "CDTOTKVV / CBTD–Tổ được tạo theo kỳ chấm điểm khi upload CDTOTKVV, "
        "không dùng kỳ HSTD. Không ghi đè cache."
    )
    if st.button("🔁 Chạy lại snapshot HSTD kỳ hiện tại", key="ql_snap_rerun_btn", use_container_width=True):
        from services.upload_service import chay_lai_snapshot_ky_hien_tai

        progress = st.progress(0.0, text="Đang chuẩn bị…")

        def _cb(pct: float, msg: str) -> None:
            progress.progress(min(max(pct, 0.0), 1.0), text=msg)

        kq = chay_lai_snapshot_ky_hien_tai(username, progress_cb=_cb)
        progress.empty()
        if kq.thanh_cong:
            st.success(kq.thong_bao)
        else:
            st.error(kq.thong_bao)
        st.session_state["ql_snap_bom_upload_ver"] = _upload_ver + 1
        st.rerun()


def _ky_la_thang_12(ky: str) -> bool:
    """True nếu kỳ hợp lệ dạng YYYY-12 (mốc baseline 31/12)."""
    s = (ky or "").strip()
    return len(s) == 7 and s[:4].isdigit() and s[4:] == "-12"


def _render_bom_snapshot_ky_cu(username: str) -> None:
    """Bơm snapshot cho một kỳ cũ từ file từng đơn vị, không đụng cache hiện hành."""
    _upload_ver = st.session_state.setdefault("ql_snap_bom_upload_ver", 0)
    st.markdown("#### 📥 Bơm snapshot kỳ cũ")
    st.caption(
        "Khôi phục mốc so sánh (tháng trước / 31-12 năm trước) mà **không phải upload lại "
        "kỳ mới nhất**. Chỉ ghi snapshot cho kỳ nhập bên dưới; không đổi dữ liệu hiện hành "
        "của app. Ngày số liệu trong file phải đúng ngày cuối kỳ."
    )

    loai_dl = st.radio(
        "Loại dữ liệu",
        ["HSTD (dư nợ theo CBTD)", "CDTOTKVV (chấm điểm Tổ TK&VV)"],
        horizontal=True,
        key="ql_snap_bom_loai",
    )
    la_hstd = loai_dl.startswith("HSTD")

    ky = st.text_input(
        "Kỳ cần bơm (YYYY-MM)", value="", placeholder="2026-07",
        key="ql_snap_bom_ky",
    )

    la_thang_12 = _ky_la_thang_12(ky)
    xac_nhan_baseline = True
    if la_thang_12:
        _nam_bl = ky.strip()[:4]
        st.warning(
            f"⚠️ Kỳ **{ky.strip()}** là mốc **baseline 31/12**. Nên dùng luồng "
            "**Upload baseline chính thống** để ghi CẢ baseline cache lẫn snapshot "
            "nhất quán cho mọi báo cáo (giao ban, KHTD, CBTD). Bơm tại đây CHỈ ghi "
            "snapshot, KHÔNG ghi baseline cache → có thể lệch nếu file khác baseline."
        )
        if la_hstd and _nam_bl.isdigit():
            from config import baseline_cache_loai

            _cache_bl = baseline_cache_loai(int(_nam_bl), "hstd")
            if Path(_cache_bl).exists():
                st.info(
                    f"ℹ️ Baseline cache HSTD {_nam_bl} **ĐÃ có** (`{Path(_cache_bl).name}`) — "
                    "nên cập nhật qua luồng baseline để nhất quán."
                )
            else:
                st.info(f"ℹ️ Baseline cache HSTD {_nam_bl} **CHƯA có**.")
        xac_nhan_baseline = st.checkbox(
            f"Tôi hiểu rủi ro và vẫn muốn bơm snapshot kỳ {ky.strip()} tại đây",
            key="ql_snap_bom_xac_nhan_baseline",
        )

    nguon = st.radio(
        "Nguồn file", ["Upload file", "Quét thư mục"], horizontal=True,
        key="ql_snap_bom_nguon",
    )

    label_file = (
        "file HSTD của các đơn vị" if la_hstd
        else "file CDTOTKVV (1 file toàn CN hoặc nhiều file từng đơn vị)"
    )
    files_bytes: dict[str, bytes] = {}
    if nguon == "Upload file":
        uploaded = st.file_uploader(
            f"Chọn {label_file} (có thể chọn nhiều file)",
            type=["xlsx", "xls"], accept_multiple_files=True,
            key=f"ql_snap_bom_files_{_upload_ver}",
        )
        for uf in uploaded or []:
            try:
                files_bytes[uf.name] = uf.getvalue()
            except Exception as e:
                logger.error("_render_bom_snapshot_ky_cu: đọc file %s — %s", uf.name, e, exc_info=True)
                st.warning(f"⚠️ Không đọc được `{uf.name}`: {e}")
    else:
        thu_muc = st.text_input(
            "Đường dẫn thư mục chứa file", value="",
            placeholder="D:\\HSTD_2026-07", key="ql_snap_bom_thumuc",
        )
        if thu_muc:
            p = Path(thu_muc)
            if not p.exists() or not p.is_dir():
                st.warning("⚠️ Thư mục không tồn tại.")
            else:
                files_excel = sorted(
                    (
                        f for f in p.iterdir()
                        if f.is_file() and f.suffix.lower() in {".xlsx", ".xls"}
                    ),
                    key=lambda f: f.name.casefold(),
                )
                for f in files_excel:
                    if f.name.startswith("~$"):
                        continue
                    try:
                        files_bytes[f.name] = f.read_bytes()
                    except Exception as e:
                        logger.error("_render_bom_snapshot_ky_cu: đọc %s — %s", f, e, exc_info=True)
                        st.warning(f"⚠️ Không đọc được `{f.name}`: {e}")

    if not files_bytes:
        return

    if not la_hstd:
        st.caption(
            f"Đã nạp **{len(files_bytes)}** file. Đơn vị được đọc tự động từ nội dung file "
            "(hỗ trợ 1 file toàn CN tự tách 22 đơn vị, hoặc nhiều file từng đơn vị)."
        )
        if st.button(
            "📥 Bơm snapshot Tổ TK&VV kỳ này", key="ql_snap_bom_cdto_btn",
            disabled=not ky.strip() or (la_thang_12 and not xac_nhan_baseline),
            use_container_width=True,
        ):
            from services.upload_service import bom_snapshot_cdtotkvv_ky_cu

            with st.spinner(f"Đang bơm snapshot Tổ TK&VV kỳ {ky.strip()}…"):
                kq = bom_snapshot_cdtotkvv_ky_cu(ky.strip(), files_bytes, username)
            if kq.thanh_cong:
                st.success(kq.thong_bao)
            else:
                st.error(kq.thong_bao)
            st.session_state["ql_snap_bom_upload_ver"] = _upload_ver + 1
            st.rerun()
        return

    from config import DON_VI_CHI_NHANH, DS_PGD
    from services.file_detection_service import tim_ten_pgd_tu_noi_dung

    ds_don_vi = [DON_VI_CHI_NHANH] + DS_PGD
    ds_hop_le = set(ds_don_vi)
    ung_vien: dict[str, list[tuple[str, bytes]]] = {}
    nhan_dien_theo_file: dict[str, str | None] = {}
    for ten_file, data in files_bytes.items():
        try:
            ten_dv = tim_ten_pgd_tu_noi_dung(data, "hstd")
        except Exception as e:
            logger.error("_render_bom_snapshot_ky_cu: nhận diện %s — %s", ten_file, e, exc_info=True)
            ten_dv = None
        nhan_dien_theo_file[ten_file] = ten_dv
        if ten_dv in ds_hop_le:
            ung_vien.setdefault(ten_dv, []).append((ten_file, data))

    files_theo_don_vi: dict[str, bytes] = {}
    file_duoc_chon: dict[str, str] = {}
    file_trung_giong_het: set[str] = set()
    don_vi_co_nhieu_ban_khac: list[str] = []
    for ten_dv in ds_don_vi:
        ds_ung_vien = ung_vien.get(ten_dv, [])
        if not ds_ung_vien:
            continue
        if len(ds_ung_vien) == 1:
            ten_file_chon, data_chon = ds_ung_vien[0]
        else:
            hashes = {
                hashlib.sha256(data).hexdigest()
                for _, data in ds_ung_vien
            }
            if len(hashes) == 1:
                ten_file_chon, data_chon = ds_ung_vien[0]
                file_trung_giong_het.update(ten for ten, _ in ds_ung_vien[1:])
            else:
                don_vi_co_nhieu_ban_khac.append(ten_dv)
                ten_file_chon = st.selectbox(
                    f"Chọn file dùng cho {ten_dv}",
                    [ten for ten, _ in ds_ung_vien],
                    key=f"ql_snap_chon_{hashlib.sha1(ten_dv.encode('utf-8')).hexdigest()[:10]}",
                )
                data_chon = next(data for ten, data in ds_ung_vien if ten == ten_file_chon)
        files_theo_don_vi[ten_dv] = data_chon
        file_duoc_chon[ten_dv] = ten_file_chon

    preview: list[dict] = []
    for ten_file in files_bytes:
        ten_dv = nhan_dien_theo_file.get(ten_file)
        if not ten_dv:
            trang_thai = "Bỏ qua — không nhận diện"
        elif ten_dv not in ds_hop_le:
            trang_thai = "Bỏ qua — ngoài danh mục"
        elif file_duoc_chon.get(ten_dv) == ten_file:
            trang_thai = "Sử dụng"
        elif ten_file in file_trung_giong_het:
            trang_thai = "Bỏ qua — bản sao giống hệt"
        else:
            trang_thai = "Bỏ qua — không được chọn"
        preview.append({
            "File": ten_file,
            "Đơn vị nhận diện": ten_dv or "❓ KHÔNG nhận diện",
            "Xử lý": trang_thai,
        })

    st.markdown("**Nhận diện đơn vị:**")
    st.dataframe(preview, use_container_width=True, hide_index=True)
    n_dv = len(files_theo_don_vi)
    thieu = sorted(ds_hop_le - set(files_theo_don_vi))
    st.caption(
        f"Đã chọn **{n_dv}/22** đơn vị."
        + (f" Thiếu {len(thieu)} đơn vị: {', '.join(thieu[:8])}{'…' if len(thieu) > 8 else ''}." if thieu else " Đủ tất cả đơn vị.")
    )
    if don_vi_co_nhieu_ban_khac:
        st.info(
            "Có nhiều file khác nhau cho: " + ", ".join(don_vi_co_nhieu_ban_khac)
            + ". Hệ thống chỉ dùng file được chọn ở trên."
        )

    ky_da_ton_tai = bool(ky.strip() and ky.strip() in set(danh_sach_ky()))
    xac_nhan_thay_the = True
    if ky_da_ton_tai:
        st.warning(
            f"Kỳ **{ky.strip()}** đã có dữ liệu. Thao tác này sẽ thay thế trọn kỳ "
            "HSTD / Thôn / Ủy thác sau khi đủ 22 đơn vị được kiểm tra."
        )
        xac_nhan_thay_the = st.checkbox(
            f"Tôi xác nhận thay thế trọn snapshot kỳ {ky.strip()}",
            key="ql_snap_bom_xac_nhan_thay_the",
        )

    if st.button(
        "📥 Bơm snapshot kỳ này", key="ql_snap_bom_btn",
        disabled=(
            not ky.strip()
            or set(files_theo_don_vi) != ds_hop_le
            or (la_thang_12 and not xac_nhan_baseline)
            or not xac_nhan_thay_the
        ),
        use_container_width=True,
    ):
        from services.upload_service import bom_snapshot_ky_cu

        with st.spinner(f"Đang bơm snapshot kỳ {ky.strip()}…"):
            kq = bom_snapshot_ky_cu(ky.strip(), files_theo_don_vi, username, loai="hstd")
        if kq.thanh_cong:
            st.success(kq.thong_bao)
        else:
            st.error(kq.thong_bao)
        st.session_state["ql_snap_bom_upload_ver"] = _upload_ver + 1
        st.rerun()


def render_snapshot_management(username: str) -> None:
    """Render màn quản lý snapshot trong luồng Upload dữ liệu."""
    st.subheader("🧭 Quản lý Snapshot")
    rows = _doc_snapshot_inventory()
    if rows:
        with st.expander("📋 Danh sách chi tiết (loại × kỳ)", expanded=False):
            st.dataframe(rows, use_container_width=True, hide_index=True)
        matrix = _build_matrix_ky_loai(rows)
        if matrix is not None:
            st.markdown("**Trạng thái kỳ × loại** (ô = số dòng, trống = chưa có):")
            st.dataframe(matrix, use_container_width=True)
    else:
        st.info("ℹ️ Chưa có snapshot nào.")

    st.divider()
    _render_chay_lai_snapshot(username)
    st.divider()
    _render_bom_snapshot_ky_cu(username)

    ds_ky = danh_sach_ky()
    if not ds_ky:
        return

    st.divider()
    col_val, col_del = st.columns(2)
    with col_val:
        ky_val = st.selectbox("Kỳ cần kiểm tra", ds_ky, key="ql_snap_validate_ky")
        if st.button("✅ Validate HSTD snapshot", key="ql_snap_validate_btn", use_container_width=True):
            result = validate_snapshot(ky_val)
            if result.get("ok"):
                st.success(f"Snapshot HSTD kỳ {ky_val} hợp lệ.")
            else:
                st.warning("Snapshot cần kiểm tra:")
                for issue in result.get("issues", []):
                    st.write(f"- {issue}")

    with col_del:
        ky_xoa = st.selectbox("Kỳ cần xóa", ds_ky, key="ql_snap_delete_ky")
        confirm = st.checkbox(f"Tôi xác nhận xóa toàn bộ snapshot kỳ {ky_xoa}", key="ql_snap_delete_confirm")
        if st.button("🗑️ Xóa snapshot kỳ này", key="ql_snap_delete_btn", disabled=not confirm, use_container_width=True):
            xoa_snapshot(ky_xoa, username)
            st.success(f"Đã xóa snapshot kỳ {ky_xoa}.")
            st.rerun()
