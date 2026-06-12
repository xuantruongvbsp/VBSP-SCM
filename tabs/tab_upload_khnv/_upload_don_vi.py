"""Upload dữ liệu từng đơn vị — form đơn và import hàng loạt."""
from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd
import streamlit as st

import db
from config import DS_PGD, DON_VI_CHI_NHANH
from data.pgd import duong_dan_pgd, kiem_tra_file_ton_tai_pgd
from logger import get_logger
from services.file_detection_service import (
    DS_DON_VI,
    md5_bytes as _md5_bytes,
    md5_file as _md5_file,
    chuan_hoa_ten as _chuan_hoa_ten,
    nhan_dien_loai_tu_noi_dung as _nhan_dien_loai_tu_noi_dung,
    tim_ten_pgd_tu_noi_dung as _tim_ten_pgd_tu_noi_dung,
    kiem_tra_don_vi as _kiem_tra_don_vi,
)
from services.upload_service import KetQuaUpload, kiem_tra_file, danh_gia_chat_luong_file_upload
from ._state import them_vao_hang_cho, xoa_cache_trang_thai

logger = get_logger(__name__)

_PREFIX_MAP = {
    "hstd":     ("HSTD", "CT_CDTO"),
    "nq11":     ("NQ11", "SAO_KE_CT"),
    "cdtotkvv": ("CDTOTKVV", "CT_CDTOTKVV"),
}


def _nhan_dien_loai_ten_file(ten_file: str) -> str | None:
    upper = ten_file.upper()
    for loai, prefixes in _PREFIX_MAP.items():
        if any(upper.startswith(p.upper()) for p in prefixes):
            return loai
    return None


# ── Xử lý 1 file (chạy trong thread) ────────────────────────────────────────

def _xu_ly_mot_file(
    loai: str,
    ten_file: str,
    ten_hien: str,
    file_bytes: bytes,
    ten_dv: str,
) -> tuple[str, KetQuaUpload, bool, tuple[str, str] | None]:
    """Kiểm tra → DQ → lưu file. Thread-safe, không gọi st.*."""
    from data.pgd import luu_file_pgd as _luu_pgd

    mb = len(file_bytes) / 1024 / 1024

    ok_kt, msg_kt = kiem_tra_file(ten_file, file_bytes)
    if not ok_kt:
        return loai, KetQuaUpload(False, msg_kt), False, None

    khop, msg_khop = _kiem_tra_don_vi(file_bytes, loai, ten_dv)
    if not khop:
        return loai, KetQuaUpload(False, msg_khop), False, None

    hop_le_dq, _msg_dq, bao_cao_dq = danh_gia_chat_luong_file_upload(loai, file_bytes)
    dq_pct = bao_cao_dq.get("ti_le_dat_chuan", 0)

    # Block nếu có lỗi tài chính nghiêm trọng (dư nợ âm > 5%)
    if bao_cao_dq.get("co_loi_critical"):
        loi_str = "; ".join(bao_cao_dq.get("canh_bao_critical", []))
        return loai, KetQuaUpload(False, f"❌ DQ Critical: {loi_str}"), False, None

    try:
        if loai == "cdtotkvv":
            from data.cdtotkvv import doc_thang_nam_tu_file
            from data.pgd import luu_file_pgd_voi_lich_su

            thang = doc_thang_nam_tu_file(file_bytes)
            if thang:
                luu_file_pgd_voi_lich_su(ten_dv, loai, file_bytes, thang)
                msg = f"✅ {ten_hien} ({mb:.1f} MB) · Tháng {thang} · DQ {dq_pct}%"
            else:
                _luu_pgd(ten_dv, loai, file_bytes)
                msg = (
                    f"✅ {ten_hien} ({mb:.1f} MB) "
                    f"· ⚠️ Không đọc được tháng · DQ {dq_pct}%"
                )
            audit = (
                "upload_pgd_khnv",
                f"CDTOTKVV — {ten_dv} tháng={thang or 'unknown'} ({mb:.1f} MB)",
            )
            return loai, KetQuaUpload(True, msg), False, audit
        else:
            loai_luu = "hstd_khnv" if loai == "hstd" else loai
            _luu_pgd(ten_dv, loai_luu, file_bytes)
            can_merge = loai in ("hstd", "nq11", "gqvl")
            msg = f"✅ {ten_hien} ({mb:.1f} MB) · DQ {dq_pct}%"
            audit = ("upload_pgd_khnv", f"{loai.upper()} — {ten_dv} ({mb:.1f} MB)")
            return loai, KetQuaUpload(True, msg), can_merge, audit
    except Exception as e:
        logger.error("_xu_ly_mot_file: %s", e, exc_info=True)
        return loai, KetQuaUpload(False, f"Lỗi lưu: {e}"), False, None


def _xu_ly_upload(
    ten_dv: str,
    username: str,
    f_hstd, f_nq11, f_gqvl, f_cdtotkvv,
    prefix: str,
) -> None:
    """Upload song song 4 file, thêm vào pending queue, ghi audit."""
    danh_sach_file = [
        ("hstd",     f_hstd,     "📊 HSTD"),
        ("nq11",     f_nq11,     "📑 NQ11"),
        ("gqvl",     f_gqvl,     "📋 GQVL"),
        ("cdtotkvv", f_cdtotkvv, "🏆 CDTOTKVV"),
    ]
    file_data = [
        (loai, f_obj.name, ten_hien, f_obj.read())
        for loai, f_obj, ten_hien in danh_sach_file
        if f_obj is not None
    ]

    ket_qua_upload: dict[str, KetQuaUpload] = {}
    audit_records: list[tuple[str, str]] = []

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {
            executor.submit(_xu_ly_mot_file, loai, ten_file, ten_hien, fbytes, ten_dv): loai
            for loai, ten_file, ten_hien, fbytes in file_data
        }
        for future in as_completed(futures):
            loai_r, kq_r, can_merge_r, audit_r = future.result()
            ket_qua_upload[loai_r] = kq_r
            if can_merge_r and kq_r.thanh_cong:
                them_vao_hang_cho(loai_r)
            if audit_r:
                audit_records.append(audit_r)

    for action, detail in audit_records:
        db.ghi_audit(username, action, detail)

    # Hiển thị kết quả 4 cột
    cols = st.columns(4)
    for col, loai, nhan in zip(
        cols,
        ["hstd", "nq11", "gqvl", "cdtotkvv"],
        ["📊 HSTD", "📑 NQ11", "📋 GQVL", "🏆 CDTOTKVV"],
    ):
        kq = ket_qua_upload.get(loai)
        if kq is None:
            col.info(f"**{nhan}**\n\nKhông có file")
        elif kq.thanh_cong:
            col.success(f"**{nhan}**\n\n{kq.thong_bao}")
        else:
            col.warning(f"**{nhan}**\n\n{kq.thong_bao}")

    if any(v.thanh_cong for v in ket_qua_upload.values()):
        st.session_state[f"{prefix}_upload_ver"] = (
            st.session_state.get(f"{prefix}_upload_ver", 0) + 1
        )
        xoa_cache_trang_thai()

    hang_cho = [
        loai for loai in ("hstd", "nq11", "gqvl")
        if loai in ket_qua_upload and ket_qua_upload[loai].thanh_cong
    ]
    if hang_cho:
        st.info(
            f"⏳ **{', '.join(hang_cho).upper()}** đã lưu. "
            "Chuyển sang tab **📊 Tổng quan** → bấm **🔄 Merge toàn CN**."
        )

    st.rerun()


# ── Form upload từng đơn vị ──────────────────────────────────────────────────

def render_upload_don_vi(username: str) -> None:
    """Form upload 4 file cho 1 đơn vị — thêm vào pending queue, không merge ngay."""
    ds_don_vi = [DON_VI_CHI_NHANH] + DS_PGD
    ten_dv = st.selectbox(
        "Chọn đơn vị",
        ds_don_vi,
        key="upload_dv_chon",
    )

    prefix = f"dv_{ten_dv.replace(' ', '_')[:20]}"
    _ver = st.session_state.setdefault(f"{prefix}_upload_ver", 0)

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.caption("📊 HSTD Chi tiết")
        f_hstd = st.file_uploader(
            "HSTD", type=["xlsx", "xls"],
            key=f"{prefix}_hstd_{_ver}", label_visibility="collapsed",
        )
    with c2:
        st.caption("📑 Sao kê NQ11")
        f_nq11 = st.file_uploader(
            "NQ11", type=["xlsx", "xls"],
            key=f"{prefix}_nq11_{_ver}", label_visibility="collapsed",
        )
    with c3:
        st.caption("📋 Sao kê GQVL")
        f_gqvl = st.file_uploader(
            "GQVL", type=["xlsx", "xls"],
            key=f"{prefix}_gqvl_{_ver}", label_visibility="collapsed",
        )
    with c4:
        st.caption("🏆 Chấm điểm Tổ TK&VV")
        f_cdtotkvv = st.file_uploader(
            "CDTOTKVV", type=["xlsx", "xls"],
            key=f"{prefix}_cdtotkvv_{_ver}", label_visibility="collapsed",
        )

    if not any(f is not None for f in [f_hstd, f_nq11, f_gqvl, f_cdtotkvv]):
        st.info("Chọn ít nhất 1 file để bắt đầu upload.")
        return

    if st.button("📤 Lưu & thêm vào hàng chờ", type="primary", key=f"{prefix}_btn_upload"):
        with st.spinner("⏳ Đang upload..."):
            _xu_ly_upload(ten_dv, username, f_hstd, f_nq11, f_gqvl, f_cdtotkvv, prefix)


# ── Import hàng loạt ─────────────────────────────────────────────────────────

def _xu_ly_import_folder(danh_sach: list[dict], username: str) -> None:
    """Import song song theo 3 bước: đọc → ghi → thêm vào pending queue."""
    from data.pgd import luu_file_pgd as _ghi_file_pgd

    danh_sach_import = [r for r in danh_sach if r.get("co_the_import", False)]
    if not danh_sach_import:
        st.info("✅ Không có file nào cần import")
        return

    thanh_cong: list[dict] = []
    that_bai: list[str] = []
    loai_da_luu: set[str] = set()

    def _doc_file(r: dict) -> tuple[dict, bytes | None, str | None]:
        try:
            return r, Path(r["path"]).read_bytes(), None
        except Exception as e:
            logger.error("_doc_file: %s", e, exc_info=True)
            return r, None, str(e)

    progress = st.progress(0.0, text="⏳ Đang đọc file...")
    tat_ca_bytes: list[tuple[dict, bytes]] = []

    with ThreadPoolExecutor(max_workers=8) as ex:
        futures = {ex.submit(_doc_file, r): r for r in danh_sach_import}
        for i, future in enumerate(as_completed(futures)):
            r, data, err = future.result()
            if err:
                that_bai.append(f"{r['ten_file']}: {err}")
            elif data is not None:
                tat_ca_bytes.append((r, data))
            progress.progress(
                ((i + 1) / len(danh_sach_import)) * 0.5,
                text=f"⏳ Đọc file {i + 1}/{len(danh_sach_import)}...",
            )

    def _ghi(r: dict, data: bytes) -> tuple[dict, str | None, tuple[str, str] | None]:
        try:
            if r["loai"] == "cdtotkvv":
                from data.cdtotkvv import doc_thang_nam_tu_file
                from data.pgd import luu_file_pgd_voi_lich_su

                thang = doc_thang_nam_tu_file(data)
                if thang:
                    _ghi_file_pgd(r["ten_pgd"], r["loai"], data)
                    luu_file_pgd_voi_lich_su(r["ten_pgd"], r["loai"], data, thang)
                    audit = (
                        "folder_import_file",
                        f"CDTOTKVV — {r['ten_pgd']} tháng={thang} ({r['ten_file']})",
                    )
                else:
                    _ghi_file_pgd(r["ten_pgd"], r["loai"], data)
                    r["canh_bao"] = "⚠️ Không đọc được tháng — chỉ lưu latest"
                    audit = (
                        "folder_import_file",
                        f"CDTOTKVV — {r['ten_pgd']} tháng=unknown ({r['ten_file']})",
                    )
            else:
                loai_luu = "hstd_khnv" if r["loai"] == "hstd" else r["loai"]
                _ghi_file_pgd(r["ten_pgd"], loai_luu, data)
                audit = (
                    "folder_import_file",
                    f"{r['loai'].upper()} — {r['ten_pgd']} ({r['ten_file']})",
                )
            return r, None, audit
        except Exception as e:
            logger.error("_ghi: %s", e, exc_info=True)
            return r, str(e), None

    if tat_ca_bytes:
        audit_records: list[tuple[str, str]] = []
        with ThreadPoolExecutor(max_workers=8) as ex:
            futures = {ex.submit(_ghi, r, data): r for r, data in tat_ca_bytes}
            for i, future in enumerate(as_completed(futures)):
                r, err, audit = future.result()
                if err:
                    that_bai.append(f"{r['ten_file']}: {err}")
                else:
                    thanh_cong.append(r)
                    loai_da_luu.add(r["loai"])
                    if audit:
                        audit_records.append(audit)
                progress.progress(
                    0.5 + ((i + 1) / len(tat_ca_bytes)) * 0.5,
                    text=f"💾 Lưu file {i + 1}/{len(tat_ca_bytes)}...",
                )
        for action, detail in audit_records:
            db.ghi_audit(username, action, detail)

    progress.empty()

    # Thêm các loại cần merge vào pending queue
    for loai in sorted(loai_da_luu & {"hstd", "nq11", "gqvl"}):
        them_vao_hang_cho(loai)

    db.ghi_audit(
        username, "folder_import_batch",
        f"{len(thanh_cong)} file thành công, {len(that_bai)} lỗi",
    )

    st.cache_data.clear()
    xoa_cache_trang_thai()

    # Reset uploader
    st.session_state["khnv_bulk_uploader_ver"] = (
        st.session_state.get("khnv_bulk_uploader_ver", 0) + 1
    )
    st.session_state.pop("khnv_bulk_bytes", None)
    st.session_state.pop("khnv_bulk_ids", None)

    st.success(f"✅ Import thành công **{len(thanh_cong)}** file")
    st.toast("✅ Import hoàn tất!", icon="✅")
    if that_bai:
        st.warning("⚠️ Lỗi:\n" + "\n".join(that_bai))

    loai_cho = sorted(loai_da_luu & {"hstd", "nq11", "gqvl"})
    if loai_cho:
        st.info(
            f"⏳ **{', '.join(loai_cho).upper()}** đã lưu. "
            "Chuyển sang tab **📊 Tổng quan** → bấm **🔄 Merge toàn CN**."
        )
    st.rerun()


def render_import_hang_loat(role: str, username: str) -> None:
    """Upload hàng loạt qua trình duyệt."""
    _ = role
    st.info(
        "**Cách chọn nhiều file:**  \n"
        "• Windows: giữ **Ctrl** rồi click từng file, hoặc **Ctrl+A**  \n"
        "• Mac: giữ **⌘ Cmd** rồi click từng file  \n"
        "• Hỗ trợ tối đa 66 file (22 PGD × HSTD + NQ11 + GQVL)"
    )

    _ver = st.session_state.setdefault("khnv_bulk_uploader_ver", 0)
    uploaded = st.file_uploader(
        "Chọn file",
        type=["xlsx", "xls"],
        accept_multiple_files=True,
        key=f"khnv_bulk_upload_{_ver}",
        label_visibility="collapsed",
    )

    if not uploaded:
        st.caption("Chưa có file nào được chọn.")
        return

    buoc_import = st.checkbox(
        "🔁 Bắt buộc import lại (kể cả file giống hệt trên đĩa)",
        value=False,
        key="khnv_force_import",
    )

    cache_key = "khnv_bulk_bytes"
    file_ids_now = [(f.name, f.size) for f in uploaded]
    if st.session_state.get("khnv_bulk_ids") != file_ids_now:
        st.session_state["khnv_bulk_ids"] = file_ids_now
        st.session_state[cache_key] = {f.name: f.read() for f in uploaded}

    bytes_map: dict[str, bytes] = st.session_state.get(cache_key, {})

    rows: list[dict] = []
    seen: dict[str, int] = {}

    with st.spinner("🔍 Đang nhận diện file..."):
        for ten_file, data in bytes_map.items():
            loai = _nhan_dien_loai_tu_noi_dung(data)
            if loai is None:
                loai = _nhan_dien_loai_ten_file(ten_file)
            if loai is None:
                rows.append({
                    "ten_file": ten_file, "loai": "❓",
                    "ten_pgd": "—", "nhan_dien": False,
                    "trang_thai": "❓ Không rõ loại",
                    "co_the_import": False, "data": data,
                })
                continue

            ten_pgd = _tim_ten_pgd_tu_noi_dung(data, loai)
            if ten_pgd:
                ten_pgd = _chuan_hoa_ten(ten_pgd)
            if ten_pgd is None or ten_pgd not in DS_DON_VI:
                rows.append({
                    "ten_file": ten_file, "loai": loai.upper(),
                    "ten_pgd": "❓ Không nhận diện được",
                    "nhan_dien": False,
                    "trang_thai": "❓ Không rõ PGD",
                    "co_the_import": False, "data": data,
                })
                continue

            dk = f"{ten_pgd}|{loai}"
            if dk in seen:
                rows[seen[dk]]["trang_thai"] = "⚠️ Trùng — bỏ qua (giữ file sau)"
                rows[seen[dk]]["co_the_import"] = False
                trang_thai = "⚠️ Trùng — sẽ import (file này)"
            else:
                trang_thai = "✅ Sẵn sàng"

            co_the_import = trang_thai in (
                "✅ Sẵn sàng", "⚠️ Trùng — sẽ import (file này)",
            )

            loai_so_sanh = "hstd_khnv" if loai.lower() == "hstd" else loai.lower()
            path_ht = duong_dan_pgd(ten_pgd, loai_so_sanh)
            if not os.path.exists(path_ht):
                so_sanh = "🆕 Chưa có"
                md5_ok = True
            else:
                da_giong = _md5_bytes(data) == _md5_file(path_ht)
                if da_giong:
                    so_sanh = "🔁 Ghi đè" if buoc_import else "✅ Giống hệt"
                    md5_ok = buoc_import
                else:
                    so_sanh = "🔄 Có thay đổi"
                    md5_ok = True

            co_the_import = co_the_import and md5_ok
            idx = len(rows)
            seen[dk] = idx
            rows.append({
                "ten_file": ten_file, "loai": loai.upper(),
                "ten_pgd": ten_pgd, "nhan_dien": True,
                "trang_thai": trang_thai, "co_the_import": co_the_import,
                "so_sanh": so_sanh, "data": data,
            })

    so_trung = sum(1 for r in rows if "Trùng" in r.get("trang_thai", ""))
    if so_trung > 0:
        st.warning(
            f"⚠️ Có **{so_trung}** file trùng. "
            "Hệ thống giữ file xuất hiện sau cùng. Kiểm tra cột **Trạng thái**."
        )

    def _style_preview(val: str) -> str:
        if val.startswith("✅"):
            return "background-color:#d4edda;color:#155724;font-weight:bold"
        if val.startswith("⚠️"):
            return "background-color:#fff3cd;color:#856404"
        if val.startswith("❓"):
            return "background-color:#f8d7da;color:#721c24"
        return ""

    def _style_so_sanh(val: str) -> str:
        if val.startswith("🆕"):
            return "background-color:#d4edda;color:#155724;font-weight:bold"
        if val.startswith("🔄"):
            return "background-color:#fff3cd;color:#856404;font-weight:bold"
        if val.startswith("🔁"):
            return "background-color:#cce5ff;color:#004085;font-weight:bold"
        if val.startswith("✅"):
            return "background-color:#e9ecef;color:#495057"
        return ""

    df_preview = pd.DataFrame([
        {
            "Loại": r["loai"], "Tên file": r["ten_file"],
            "PGD": r["ten_pgd"], "So sánh": r.get("so_sanh", "—"),
            "Trạng thái": r["trang_thai"],
        }
        for r in rows
    ])
    st.dataframe(
        df_preview.style
            .map(_style_preview, subset=["Trạng thái"])
            .map(_style_so_sanh, subset=["So sánh"]),
        use_container_width=True, hide_index=True,
    )

    co_the_import_list = [r for r in rows if r["co_the_import"]]
    khong_nhan_dien = [r for r in rows if not r["nhan_dien"]]
    trung = [r for r in rows if "Trùng" in r.get("trang_thai", "") and not r["co_the_import"]]
    giong_het = [r for r in rows if r.get("nhan_dien") and not r["co_the_import"]
                 and r.get("so_sanh", "").startswith("✅")]
    st.caption(
        f"📊 Tổng **{len(rows)}** file · "
        f"✅ Sẵn sàng **{len(co_the_import_list)}** · "
        f"⏩ Giống hệt **{len(giong_het)}** · "
        f"❓ Không nhận diện **{len(khong_nhan_dien)}** · "
        f"⚠️ Trùng bỏ qua **{len(trung)}**"
    )

    if not co_the_import_list:
        st.warning("⚠️ Không có file nào hợp lệ để import.")
        return

    if st.button(
        f"📥 Import {len(co_the_import_list)} file → hàng chờ",
        type="primary",
        key="btn_bulk_import",
    ):
        import tempfile

        danh_sach_for_import: list[dict] = []
        tmp_files: list[str] = []
        try:
            for r in co_the_import_list:
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx")
                tmp.write(r["data"])
                tmp.close()
                tmp_files.append(tmp.name)
                danh_sach_for_import.append({
                    "path": tmp.name,
                    "ten_file": r["ten_file"],
                    "ten_pgd": r["ten_pgd"],
                    "loai": r["loai"].lower(),
                    "phuong_phap": "nội dung",
                    "nhan_dien": True,
                    "co_the_import": True,
                })
            _xu_ly_import_folder(danh_sach_for_import, username)
        finally:
            for p in tmp_files:
                try:
                    os.unlink(p)
                except Exception as e:
                    logger.error("unlink tmp: %s", e)
