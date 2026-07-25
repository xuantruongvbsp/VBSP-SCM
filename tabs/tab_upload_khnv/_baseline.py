"""Upload file mốc 31/12 (per-PGD, 4 loại) + tổng hợp thủ công."""
from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import streamlit as st

import db
from config import (
    DS_PGD, DON_VI_CHI_NHANH,
    LOAI_BASELINE,
    baseline_pgd_path_loai,
    danh_sach_nam_baseline_pgd,
    trang_thai_baseline_pgd_loai,
)
from logger import get_logger
from services.file_detection_service import (
    md5_bytes as _md5_bytes,
    md5_file as _md5_file,
    chuan_hoa_ten as _chuan_hoa_ten,
    nhan_dien_loai_tu_noi_dung as _nhan_dien_loai_tu_noi_dung,
    tim_ten_pgd_tu_noi_dung as _tim_ten_pgd_tu_noi_dung,
)
from services.upload_service import merge_baseline_toan_cn

logger = get_logger(__name__)

_NHAN_BASELINE = {
    "hstd":     "📊 HSTD",
    "nq11":     "📑 NQ11",
    "gqvl":     "📋 GQVL",
    "cdtotkvv": "🏆 CDTOTKVV",
}


def render(username: str) -> None:
    """Upload file mốc 31/12 (4 loại) per-PGD — bulk upload + tổng hợp thủ công."""
    from datetime import date as _date
    nam_mac_dinh = _date.today().year - 1

    chon_nam = st.number_input(
        "Năm cần upload (31/12/năm)",
        min_value=2020, max_value=_date.today().year,
        value=nam_mac_dinh, step=1,
        key="upload_baseline_nam",
    )
    nam = int(chon_nam)

    _tt_loai_key = f"_blcache_tt_loai_{nam}"
    if _tt_loai_key not in st.session_state:
        st.session_state[_tt_loai_key] = {
            loai: trang_thai_baseline_pgd_loai(nam, loai) for loai in LOAI_BASELINE
        }
    tt_loai = st.session_state[_tt_loai_key]
    tong = len([DON_VI_CHI_NHANH] + DS_PGD)

    cols_tt = st.columns(4)
    for col, loai in zip(cols_tt, LOAI_BASELINE):
        da_co = sum(1 for v in tt_loai[loai].values() if v)
        nhan = _NHAN_BASELINE[loai]
        if da_co == tong:
            col.success(f"{nhan}\n\n✅ {da_co}/{tong}")
        elif da_co > 0:
            col.warning(f"{nhan}\n\n⏳ {da_co}/{tong}")
        else:
            col.info(f"{nhan}\n\n❌ 0/{tong}")

    st.divider()
    st.markdown("**📦 Import hàng loạt** — hệ thống tự nhận diện loại và PGD từ nội dung file")

    tab_file, tab_folder = st.tabs(["📂 Chọn file", "📁 Quét thư mục"])

    with tab_file:
        st.info(
            "**Cách chọn nhiều file:**  \n"
            "• Windows: giữ **Ctrl** rồi click từng file  \n"
            "• Mac: giữ **⌘ Cmd** rồi click từng file  \n"
            "• Hỗ trợ tối đa 88 file (22 PGD × 4 loại)"
        )
        _bl_ver = st.session_state.setdefault("bl_bulk_ver", 0)
        uploaded = st.file_uploader(
            "Chọn file baseline",
            type=["xlsx", "xls"],
            accept_multiple_files=True,
            key=f"bl_bulk_{nam}_{_bl_ver}",
            label_visibility="collapsed",
        )
        if uploaded:
            _bl_ids_now = [(f.name, f.size) for f in uploaded]
            if st.session_state.get("_bl_ids") != _bl_ids_now:
                st.session_state["_bl_ids"] = _bl_ids_now
                st.session_state["_bl_bytes"] = {f.name: f.read() for f in uploaded}

    with tab_folder:
        st.caption("Nhập đường dẫn thư mục chứa 4 loại file baseline 31/12 trên máy tính.")
        thu_muc = st.text_input(
            "Đường dẫn thư mục",
            placeholder=r"Ví dụ: D:\Data\Baseline_3112_2025",
            key="bl_folder_path",
            label_visibility="collapsed",
        )
        if st.button("🔍 Quét thư mục", key="btn_bl_scan_folder"):
            if not thu_muc or not os.path.isdir(thu_muc):
                st.error("❌ Thư mục không tồn tại.")
            else:
                files = [f for f in Path(thu_muc).iterdir()
                         if f.suffix.lower() in (".xlsx", ".xls")]
                if not files:
                    st.warning("⚠️ Không có file Excel nào trong thư mục.")
                else:
                    _bm: dict[str, bytes] = {}
                    for f in files:
                        try:
                            _bm[f.name] = f.read_bytes()
                        except Exception as e:
                            logger.error("bl scan: %s", e, exc_info=True)
                    st.session_state["_bl_bytes"] = _bm
                    st.session_state["_bl_ids"] = [(k, len(v)) for k, v in _bm.items()]
                    st.success(f"✅ Tìm thấy {len(_bm)} file.")
                    st.rerun()

    bytes_map: dict[str, bytes] = st.session_state.get("_bl_bytes", {})
    if not bytes_map:
        st.caption("Chưa có file nào.")
        _render_tong_hop_thu_cong(username, nam)
        return

    buoc_import = st.checkbox(
        "🔁 Bắt buộc import lại (kể cả file giống hệt trên đĩa)",
        value=False,
        key="bl_force_import",
    )

    rows: list[dict] = []
    ds_don_vi_chuan = set([DON_VI_CHI_NHANH] + DS_PGD)
    seen: dict[str, int] = {}

    with st.spinner("🔍 Đang nhận diện file..."):
        for ten_file, data in bytes_map.items():
            loai = _nhan_dien_loai_tu_noi_dung(data)
            if loai is None:
                rows.append({
                    "ten_file": ten_file, "loai": "❓",
                    "ten_pgd": "—", "nhan_dien": False,
                    "trang_thai": "❓ Không rõ loại",
                    "so_sanh": "—", "co_the_import": False, "data": data,
                })
                continue

            ten_pgd = _tim_ten_pgd_tu_noi_dung(data, loai)
            if ten_pgd:
                ten_pgd = _chuan_hoa_ten(ten_pgd)
            if not ten_pgd or ten_pgd not in ds_don_vi_chuan:
                rows.append({
                    "ten_file": ten_file, "loai": loai.upper(),
                    "ten_pgd": ten_pgd or "❓", "nhan_dien": False,
                    "trang_thai": "❓ Không rõ PGD",
                    "so_sanh": "—", "co_the_import": False, "data": data,
                })
                continue

            dk = f"{ten_pgd}|{loai}"
            if dk in seen:
                rows[seen[dk]]["trang_thai"] = "⚠️ Trùng — bỏ qua (giữ file sau)"
                rows[seen[dk]]["co_the_import"] = False
                tt = "⚠️ Trùng — sẽ import (file này)"
            else:
                tt = "✅ Sẵn sàng"

            dest = baseline_pgd_path_loai(ten_pgd, nam, loai)
            if not os.path.exists(dest):
                so_sanh = "🆕 Chưa có"
                md5_ok = True
            else:
                giong = _md5_bytes(data) == _md5_file(dest)
                if giong:
                    so_sanh = "🔁 Ghi đè" if buoc_import else "✅ Giống hệt"
                    md5_ok = buoc_import
                else:
                    so_sanh = "🔄 Có thay đổi"
                    md5_ok = True

            co_the_import = tt in ("✅ Sẵn sàng", "⚠️ Trùng — sẽ import (file này)") and md5_ok
            seen[dk] = len(rows)
            rows.append({
                "ten_file": ten_file, "loai": loai.upper(), "ten_pgd": ten_pgd,
                "nhan_dien": True, "trang_thai": tt, "so_sanh": so_sanh,
                "co_the_import": co_the_import, "data": data,
            })

    so_trung = sum(1 for r in rows if "Trùng" in r.get("trang_thai", ""))
    if so_trung:
        st.warning(f"⚠️ Có **{so_trung}** file trùng — hệ thống giữ file cuối.")

    def _style_tt(v: str) -> str:
        if v.startswith("✅"): return "background-color:#d4edda;color:#155724;font-weight:bold"
        if v.startswith("⚠️"): return "background-color:#fff3cd;color:#856404"
        if v.startswith("❓"): return "background-color:#f8d7da;color:#721c24"
        return ""

    def _style_ss(v: str) -> str:
        if v.startswith("🆕"): return "background-color:#d4edda;color:#155724;font-weight:bold"
        if v.startswith("🔄"): return "background-color:#fff3cd;color:#856404;font-weight:bold"
        if v.startswith("🔁"): return "background-color:#cce5ff;color:#004085;font-weight:bold"
        if v.startswith("✅"): return "background-color:#e9ecef;color:#495057"
        return ""

    df_preview = pd.DataFrame([
        {
            "Loại": r["loai"], "Tên file": r["ten_file"],
            "Đơn vị": r["ten_pgd"], "So sánh": r["so_sanh"],
            "Trạng thái": r["trang_thai"],
        }
        for r in rows
    ])
    st.dataframe(
        df_preview.style.map(_style_tt, subset=["Trạng thái"]).map(_style_ss, subset=["So sánh"]),
        use_container_width=True, hide_index=True,
    )

    co_the_import_list = [r for r in rows if r["co_the_import"]]
    khong_nd  = [r for r in rows if not r["nhan_dien"]]
    giong_het = [r for r in rows if r["nhan_dien"] and not r["co_the_import"]
                 and r.get("so_sanh", "").startswith("✅")]
    st.caption(
        f"📊 Tổng **{len(rows)}** file · "
        f"✅ Sẵn sàng **{len(co_the_import_list)}** · "
        f"⏩ Giống hệt **{len(giong_het)}** · "
        f"❓ Không nhận diện **{len(khong_nd)}**"
    )

    if not co_the_import_list:
        st.warning("⚠️ Không có file nào hợp lệ để import.")
    elif st.button(
        f"📥 Import {len(co_the_import_list)} file baseline {nam}",
        type="primary",
        key="btn_luu_bulk_baseline",
    ):
        thanh_cong, that_bai = 0, []
        for r in co_the_import_list:
            dest = baseline_pgd_path_loai(r["ten_pgd"], nam, r["loai"].lower())
            try:
                Path(dest).parent.mkdir(parents=True, exist_ok=True)
                with open(dest, "wb") as fh:
                    fh.write(r["data"])
                mb = len(r["data"]) / 1024 / 1024
                db.ghi_audit(
                    username, "upload_baseline",
                    f"{r['loai']} 31/12/{nam} — {r['ten_pgd']} ({mb:.1f} MB)",
                )
                thanh_cong += 1
            except Exception as e:
                logger.error("bl import: %s", e, exc_info=True)
                that_bai.append(f"{r['ten_pgd']} {r['loai']}: {e}")

        st.cache_data.clear()
        if thanh_cong:
            st.success(f"✅ Đã lưu **{thanh_cong}/{len(co_the_import_list)}** file baseline {nam}.")
        if that_bai:
            st.error("❌ Lỗi:\n" + "\n".join(that_bai))

        st.session_state["bl_bulk_ver"] = st.session_state.get("bl_bulk_ver", 0) + 1
        st.session_state.pop("_bl_ids", None)
        st.session_state.pop("_bl_bytes", None)
        for _k in [k for k in st.session_state if k.startswith("_blcache_")]:
            st.session_state.pop(_k, None)
        st.rerun()

    st.divider()
    _render_tong_hop_thu_cong(username, nam)


def _render_tong_hop_thu_cong(username: str, nam: int) -> None:
    st.markdown("**🔄 Tổng hợp thủ công** — gộp file baseline 22 đơn vị thành dữ liệu chung")
    st.caption("Dùng sau khi upload đủ file baseline, hoặc khi cần rebuild cache 31/12.")

    loai_bl_chon = st.multiselect(
        "Chọn loại cần tổng hợp",
        options=list(LOAI_BASELINE),
        default=["hstd", "nq11", "gqvl"],
        format_func=lambda x: _NHAN_BASELINE.get(x, x.upper()),
        key="bl_manual_merge_loai",
    )
    if st.button(
        "🔄 Tổng hợp baseline ngay",
        type="primary",
        key="btn_bl_manual_merge",
        disabled=not loai_bl_chon,
    ):
        tong_buoc = len(loai_bl_chon)
        progress_bar = st.progress(0, text="⏳ Chuẩn bị tổng hợp baseline...")
        for idx, loai in enumerate(loai_bl_chon):
            progress_bar.progress(
                idx / tong_buoc,
                text=f"🔄 Tổng hợp **{_NHAN_BASELINE.get(loai, loai.upper())}** "
                     f"31/12/{nam} ({idx + 1}/{tong_buoc})...",
            )
            kq = merge_baseline_toan_cn(loai, nam)
            progress_bar.progress((idx + 1) / tong_buoc)
            if kq.thanh_cong:
                st.success(kq.thong_bao)
            else:
                st.error(f"❌ {_NHAN_BASELINE.get(loai, loai.upper())}: {kq.thong_bao}")

        progress_bar.progress(1.0, text="✅ Hoàn tất!")
        st.cache_data.clear()
        db.ghi_audit(username, "manual_merge_baseline", f"loai={loai_bl_chon} nam={nam}")
        st.toast("✅ Tổng hợp baseline hoàn tất!", icon="✅")
        st.rerun()
