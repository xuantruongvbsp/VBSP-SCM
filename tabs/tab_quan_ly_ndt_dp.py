"""Quản lý Mã Nhà đầu tư Địa phương — dành cho Admin/Manager CN."""
from __future__ import annotations

from io import BytesIO
from pathlib import Path

import streamlit as st
import pandas as pd
from streamlit.delta_generator import DeltaGenerator

import db
from auth import normalize_role
from config import CACHE_DIR, COT_MA_NDT, COT_NGUON_VON, COT_DU_NO_TH, COT_DU_NO_QH
from utils import fmt_so, fmt_ty
from logger import get_logger

logger = get_logger(__name__)


def render(tab: DeltaGenerator = None, **kwargs) -> None:
    """CRUD Mã NĐT địa phương — phân tầng GQVL ĐP."""
    role     = kwargs.get("role", "user")
    username = kwargs.get("username", "unknown")

    ctx = tab if tab is not None else st.container()
    with ctx:
        st.subheader("🏦 Mã Nhà đầu tư Địa phương")
        st.info(
            "ℹ️ Mã NĐT lấy chính xác từ cột **'Mã nhà đầu tư'** trong file sao kê GQVL — "
            "món vay khớp với danh sách **Cấp Tỉnh** → xếp vào GQVL ĐP Cấp tỉnh, còn lại → Cấp xã/khác. "
            "Chỉ **Admin CN** mới có thể thêm / sửa / xóa."
        )

        with st.expander("📖 Hướng dẫn sử dụng", expanded=False):
            st.markdown("""
### Mục đích

Hệ thống phân loại mỗi món vay **Nguồn vốn ĐP (Địa phương)** thành 2 tầng:

| Tầng | Điều kiện | Ví dụ |
|---|---|---|
| **GQVL ĐP — Cấp tỉnh** | Mã NĐT của món vay **có trong danh sách Cấp Tỉnh** | UBND tỉnh Đồng Nai |
| **GQVL ĐP — Cấp xã/khác** | Mã NĐT **không có** trong danh sách | Vốn huyện, xã, tổ chức khác |

---

### Các tab chức năng

**🏛️ Cấp Tỉnh** — Xem danh sách mã đang được xếp vào nhóm Cấp tỉnh.

**🏘️ Cấp Xã/Khác** — Xem danh sách mã đang được xếp vào nhóm Cấp xã/khác.

**➕ Thêm mới** *(chỉ Admin CN)*
1. Mở file sao kê GQVL → tìm cột **"Mã nhà đầu tư"**
2. Copy chính xác mã (dạng `INV` + dãy số, ví dụ `INV0802140002662`)
3. Dán vào ô **Mã NĐT đầy đủ**, điền ghi chú, chọn **Phân loại cấp** rồi nhấn **➕ Thêm**

**✏️ Chỉnh sửa / Xóa** *(chỉ Admin CN)*
- Sửa ghi chú hoặc đổi phân loại cấp → nhấn 💾 để lưu từng dòng
- Nhấn 🗑️ để xóa (không thể xóa khi chỉ còn 1 mã)

**📊 Phân tích**
- Hiển thị ngay tác động lên dữ liệu GQVL đang có trong cache
            """)

        ds       = db.doc_ndt_dp_list()
        can_edit = normalize_role(str(role or "user")) == "admin_cn"

        ds_tinh = [x for x in ds if x.get("cap", "tinh") == "tinh"]
        ds_xa   = [x for x in ds if x.get("cap", "tinh") == "xa"]

        _CAP_OPTS = ["Cấp Tỉnh 🏛️", "Cấp Xã/Khác 🏘️"]
        _CAP_TO   = {"Cấp Tỉnh 🏛️": "tinh", "Cấp Xã/Khác 🏘️": "xa"}
        _CAP_FROM = {"tinh": "Cấp Tỉnh 🏛️", "xa": "Cấp Xã/Khác 🏘️"}

        _t1, _t2, _t3, _t4, _t5 = st.tabs([
            "🏛️ Cấp Tỉnh", "🏘️ Cấp Xã/Khác", "➕ Thêm mới", "✏️ Chỉnh sửa / Xóa", "📊 Phân tích",
        ])

        with _t1:
            if ds_tinh:
                for item in ds_tinh:
                    c1, c2 = st.columns([3, 5])
                    c1.code(item["ma"])
                    c2.markdown(item.get("ghi_chu", ""))
            else:
                st.info("Chưa có mã nào ở cấp Tỉnh.")

        with _t2:
            if ds_xa:
                for item in ds_xa:
                    c1, c2 = st.columns([3, 5])
                    c1.code(item["ma"])
                    c2.markdown(item.get("ghi_chu", ""))
            else:
                st.info("Chưa có mã nào được đăng ký ở cấp Xã/Khác.")

        with _t3:
            if not can_edit:
                st.warning("⚠️ Chỉ Admin CN mới có thể thêm mã.")
            else:
                with st.form("form_them_ndt", clear_on_submit=True):
                    ma_them = st.text_input(
                        "Mã NĐT đầy đủ",
                        placeholder="VD: INV0802140002662",
                        help="Lấy chính xác từ cột 'Mã nhà đầu tư' trong file GQVL",
                        key="ndt_ma_them",
                    )
                    ghi_chu_them = st.text_input("Ghi chú", placeholder="VD: UBND tỉnh Đồng Nai", key="ndt_gc_them")
                    cap_them = st.selectbox(
                        "Phân loại cấp",
                        _CAP_OPTS,
                        help="Cấp Tỉnh: vốn UBND tỉnh/ủy thác đầu tư cấp tỉnh. Cấp Xã/Khác: vốn cấp huyện/xã.",
                        key="ndt_cap_them",
                    )
                    submitted_them = st.form_submit_button("➕ Thêm", type="primary")

                if submitted_them:
                    ma_them = ma_them.strip()
                    if not ma_them:
                        st.error("Vui lòng nhập mã NĐT.")
                    elif any(x["ma"] == ma_them for x in ds):
                        st.warning(f"Mã **{ma_them}** đã có trong danh sách.")
                    else:
                        cap_val = _CAP_TO[cap_them]
                        ds_moi  = ds + [{"ma": ma_them, "ghi_chu": ghi_chu_them.strip(), "cap": cap_val}]
                        db.ghi_kv("ndt_dp_list", ds_moi, username)
                        db.ghi_audit(username, "them_ndt_dp",
                                     f"Thêm mã {ma_them} — {ghi_chu_them} ({cap_them})")
                        st.success(f"✅ Đã thêm mã **{ma_them}** vào {cap_them}")
                        st.rerun()

        with _t4:
            if not can_edit:
                st.warning("⚠️ Chỉ Admin CN mới có thể chỉnh sửa / xóa mã.")
            elif not ds:
                st.info("Chưa có mã nào.")
            else:
                st.caption("Chỉnh sửa ghi chú hoặc đổi phân loại cấp, nhấn 💾 để lưu từng dòng.")
                for i, item in enumerate(ds):
                    c1, c2, c3, c4, c5 = st.columns([3, 3, 2, 1, 1])
                    c1.code(item["ma"])
                    gc_edit = c2.text_input("Ghi chú", value=item.get("ghi_chu", "") or "",
                                            key=f"ndt_gc_{i}", label_visibility="collapsed")
                    cap_current = _CAP_FROM.get(item.get("cap", "tinh"), _CAP_OPTS[0])
                    cap_edit = c3.selectbox("Cấp", _CAP_OPTS, index=_CAP_OPTS.index(cap_current),
                                            key=f"ndt_cap_{i}", label_visibility="collapsed")
                    if c4.button("💾", key=f"luu_ndt_{i}", help="Lưu thay đổi"):
                        ds_moi = [dict(x) for x in ds]
                        ds_moi[i]["ghi_chu"] = (gc_edit or "").strip()
                        ds_moi[i]["cap"]     = _CAP_TO[cap_edit]
                        db.ghi_kv("ndt_dp_list", ds_moi, username)
                        db.ghi_audit(username, "sua_ndt_dp",
                                     f"Sửa mã {item['ma']} → ghi chú: {gc_edit}, cấp: {cap_edit}")
                        st.rerun()
                    if c5.button("🗑️", key=f"xoa_ndt_{i}", disabled=(len(ds) <= 1),
                                 help="Không thể xóa khi chỉ còn 1 mã"):
                        ds_moi = [x for j, x in enumerate(ds) if j != i]
                        db.ghi_kv("ndt_dp_list", ds_moi, username)
                        db.ghi_audit(username, "xoa_ndt_dp", f"Xóa mã {item['ma']}")
                        st.rerun()

        with _t5:
            try:
                gqvl_path = Path(CACHE_DIR) / "gqvl.parquet"
                if not gqvl_path.exists():
                    st.info("Chưa có dữ liệu GQVL. Upload file để xem phân tích.")
                else:
                    df_gqvl = pd.read_parquet(gqvl_path)
                    if (COT_NGUON_VON not in df_gqvl.columns) or (COT_MA_NDT not in df_gqvl.columns):
                        st.warning("File GQVL không có đủ cột để phân tích.")
                    elif df_gqvl[COT_NGUON_VON].isna().all():
                        st.warning("⚠️ Cột 'Nguồn vốn' trong cache GQVL toàn NaN — dữ liệu cũ bị lỗi. Vui lòng upload lại file GQVL.")
                    else:
                        df_dp         = df_gqvl[df_gqvl[COT_NGUON_VON] == "ĐP"].copy()
                        ma_ndt_str    = df_dp[COT_MA_NDT].astype(str).str.strip()
                        ndt_tinh_list = [x["ma"] for x in ds_tinh]
                        mask_tinh     = ma_ndt_str.isin(ndt_tinh_list)
                        ghi_chu_map   = {x["ma"]: x.get("ghi_chu", "") for x in ds}

                        p1, p2, p3 = st.columns(3)
                        p1.metric("Tổng món ĐP",       fmt_so(len(df_dp)))
                        p2.metric("→ Cấp tỉnh 🏛️",    fmt_so(int(mask_tinh.sum())))
                        p3.metric("→ Cấp xã/khác 🏘️", fmt_so(int((~mask_tinh).sum())))

                        st.divider()
                        agg_kw: dict = {"Số món": ("Nhóm", "count")}
                        if COT_DU_NO_TH in df_dp.columns:
                            agg_kw["Dư nợ TH (tỷ)"] = (COT_DU_NO_TH, "sum")
                        if COT_DU_NO_QH in df_dp.columns:
                            agg_kw["Dư nợ QH (tỷ)"] = (COT_DU_NO_QH, "sum")
                        df_pv = (
                            df_dp
                            .assign(Nhóm=ma_ndt_str.where(mask_tinh, "— Cấp xã/khác"))
                            .groupby("Nhóm")
                            .agg(**agg_kw)
                            .reset_index()
                        )
                        for col in ("Dư nợ TH (tỷ)", "Dư nợ QH (tỷ)"):
                            if col in df_pv.columns:
                                df_pv[col] = df_pv[col].apply(fmt_ty)
                        df_pv["Ghi chú"] = df_pv["Nhóm"].map(lambda m: ghi_chu_map.get(m, ""))
                        st.dataframe(df_pv, hide_index=True, use_container_width=True)
            except Exception as e:
                logger.error("tab_quan_ly_ndt_dp phan_tich: %s", e, exc_info=True)
                st.warning(f"Không thể phân tích tác động GQVL: {e}")

        col_xl, col_rf = st.columns([3, 1])
        with col_xl:
            if st.button("📥 Xuất danh sách Excel", key="export_ndt_dp"):
                df_export = pd.DataFrame([
                    {"Mã NĐT": x["ma"], "Ghi chú": x.get("ghi_chu", ""),
                     "Phân loại cấp": _CAP_FROM.get(x.get("cap", "tinh"), "Cấp Tỉnh 🏛️")}
                    for x in ds
                ])
                buf = BytesIO()
                df_export.to_excel(buf, index=False)
                st.download_button("💾 Tải về", data=buf.getvalue(),
                                   file_name="danh_sach_ndt_dp.xlsx",
                                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                   key="dl_ndt_dp")
        with col_rf:
            if st.button("🔄 Làm mới", key="btn_refresh_ndt_dp", use_container_width=True,
                         help="Xóa cache và tải lại dữ liệu GQVL"):
                st.cache_data.clear()
                st.rerun()
