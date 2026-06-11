"""
Không gian Điều hành (Management View)
───────────────────────────────────────
Dành cho Lãnh đạo phòng KH-NV — Giám sát NQH theo địa bàn,
quản lý chỉ tiêu, cân đối nguồn vốn.
"""


from logger import get_logger
logger = get_logger(__name__)

import os
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st
import db

from state_manager import SCMStateManager
from config import (
    COT_TEN_PGD, COT_MA_KH, COT_SO_KU, COT_TEN_KH,
    COT_DU_NO_QH, COT_TONG_DU_NO, COT_DU_NO_TH, COT_TEN_CT,
    COT_NGAY_DH, COT_TINH_TRANG, COT_SDT,
    COT_LAI_TON, COT_LAI_TON_QH, COT_LAI_THANG, COT_DVUT, COT_MUC_VAY,
    COT_NGAY_VAY, COT_THOI_HAN, COT_LAI_SUAT,
    TEMPLATES_DIR, TAG_MAP,
)
from auth import is_cn_role, is_pgd_role, get_permissions, normalize_role, la_phan_he_cn
from data import (
    danh_dau_khong_hd, danh_dau_khong_hd_cached,
    tong_hop_khong_hd, tong_hop_khong_hd_cached,
    ds_chi_tiet_khong_hd, canh_bao_migration, canh_bao_migration_cached,
)
from utils import (
    fmt,
    fmt_so,
    fmt_ty,
    vn,
    xuat_excel,
    quet_templates,
    auto_fill_klgb,
    auto_fill_document,
    hien_thi_dataframe_phan_trang,
    lazy_tabs,
)
from services.excel_service import xuat_excel_chuyen_nghiep, ten_file_xuat as excel_ten_file
from pdf_service import render_huong_dan, xuat_pdf_group_header
from components.delta_card import delta_card, kpi_row
from components.loan_drawer import loan_detail_drawer
from components.filter_bar import filter_bar, apply_filters
from components.export_pdf import download_pdf_button, xuat_pdf_co_chart


@st.cache_resource
def _get_tab(name: str):
    """Import tab module — dùng sys.modules cache của Python, tự invalidate khi Streamlit hot-reload."""
    import importlib
    try:
        return importlib.import_module(f"tabs.{name}")
    except ModuleNotFoundError:
        import tabs
        return getattr(tabs, name)


def _render_canh_bao(df: pd.DataFrame, ds_pgd_all: list):
    """
    Tab Cảnh báo sớm — Migration & 3 tháng không hoạt động.
    Hiển thị bảng Top đơn vị cần chấn chỉnh + xuất KL giao ban.
    """
    from tabs.tab_den_han import render as render_den_han

    st.subheader("🚨 Cảnh báo sớm — Phân loại nợ & 3 tháng không HĐ")

    if df is None or df.empty:
        st.warning("Chưa có dữ liệu HSTD."); return

    # Đánh dấu 3 tháng không hoạt động
    df_kh = danh_dau_khong_hd_cached(df)

    # ── KPI nhanh ──────────────────────────────────────────────────────────
    tong_mon    = len(df_kh)
    khd_tong    = int(df_kh["is_3m_inactive"].sum()) if "is_3m_inactive" in df_kh.columns else 0
    df_amber    = canh_bao_migration_cached(df_kh)
    amber_tong  = len(df_amber)
    tl_khd      = khd_tong / tong_mon * 100 if tong_mon > 0 else 0
    tong_lai_khd = 0.0
    if not df_kh.empty and "is_3m_inactive" in df_kh.columns:
        df_khd = df_kh[df_kh["is_3m_inactive"]]
        for col in (COT_LAI_TON, COT_LAI_TON_QH):
            if col in df_kh.columns:
                tong_lai_khd += pd.to_numeric(df_khd[col], errors="coerce").fillna(0).sum()

    kpi_row([
        {"label": "Tổng món vay", "value": tong_mon, "icon": "📊", "suffix": "", "precision": 0,
         "help": "Tổng số món vay toàn chi nhánh"},
        {"label": "3 tháng KHĐ", "value": khd_tong, "icon": "🔴", "suffix": "", "precision": 0,
         "delta": tl_khd, "delta_label": "% tổng món", "delta_color": "inverse" if tl_khd > 2 else "off",
         "help": "Số món 3 tháng không hoạt động"},
        {"label": "Sắp chuyển KHĐ", "value": amber_tong, "icon": "⚠️", "suffix": "", "precision": 0,
         "delta_color": "off", "help": "Lãi tồn 2-3 tháng, cần đôn đốc ngay"},
        {"label": "Lãi tồn KHĐ", "value": tong_lai_khd, "icon": "💰", "suffix": "đồng", "precision": 0,
          "help": "Tổng lãi tồn các món 3 tháng KHĐ"},
     ], num_columns=4)

    st.divider()

    # ── Bảng Top đơn vị cần chấn chỉnh ───────────────────────────────────
    st.markdown("**📋 Tổng hợp theo PGD**")
    nhom_pgd = tong_hop_khong_hd_cached(df_kh, nhom_theo=COT_TEN_PGD)
    if not nhom_pgd.empty:
        hien_thi_dataframe_phan_trang(
            nhom_pgd,
            key="mgmt_khd_nhom_pgd",
            height=300,
        )

    st.markdown("**📋 Tổng hợp theo Hội đoàn thể (ĐVUT)**")
    nhom_dvut = tong_hop_khong_hd_cached(df_kh, nhom_theo=COT_DVUT)
    if not nhom_dvut.empty:
        hien_thi_dataframe_phan_trang(
            nhom_dvut,
            key="mgmt_khd_nhom_dvut",
            height=220,
        )

    st.divider()

    # ── Vùng Amber — cảnh báo sớm migration ──────────────────────────────
    st.markdown("**⚠️ Danh sách sắp chuyển 03 tháng không hoạt động — Đang tồn lãi 2–3 tháng (cần đôn đốc ngay)**")
    if not df_amber.empty:
        col_amber_loc, col_amber_xuat = st.columns([2, 1])
        with col_amber_loc:
            loc_pgd_a = st.selectbox(
                "Lọc PGD", ["Tất cả"] + ds_pgd_all, key="cb_amber_pgd")
        with col_amber_xuat:
            st.markdown("<br>", unsafe_allow_html=True)
            df_amber_loc = df_amber if loc_pgd_a == "Tất cả" \
                           else df_amber[df_amber[COT_TEN_PGD] == loc_pgd_a]
            buf_a = xuat_excel({"SapChuyen3mKHD": df_amber_loc})
            st.download_button(
                f"⬇️ Xuất Excel Amber ({len(df_amber_loc)} món)",
                data=buf_a,
                file_name=f"SapChuyen3mKHD_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="cb_xuat_amber",
            )
        cols_hien = [c for c in [
            COT_TEN_PGD, "Tên xã", COT_DVUT, COT_TEN_KH,
            COT_SO_KU, COT_TEN_CT, COT_LAI_TON, COT_LAI_THANG,
            "so_thang_ton_uoc", "muc_canh_bao",
        ] if c in df_amber_loc.columns]
        hien_thi_dataframe_phan_trang(
            df_amber_loc[cols_hien],
            key="mgmt_amber_ds",
            height=320,
        )
    else:
        st.success("✅ Không có món vay nào sắp chuyển 03 tháng không hoạt động.")

    st.divider()

    # ── Xuất KL giao ban tự động ──────────────────────────────────────────
    st.markdown("**📄 Xuất Thông báo KL Giao ban (Bảng II tự động điền)**")
    templates = quet_templates(TEMPLATES_DIR)
    mau_klgb  = [(t, p) for t, p in templates
                 if "giao" in t.lower() or "kl" in t.lower() or "thong bao" in t.lower()]

    if not mau_klgb:
        st.info("⚠️ Chưa có mẫu KL giao ban trong thư mục `templates/`. "
                "Đặt file `.docx` vào thư mục đó và reload.")
    else:
        # Nút 1-click: tự động dùng template đầu tiên, toàn CN
        if st.button("⚡ Xuất nhanh KL Giao ban Toàn CN", key="kl_nhanh_btn"):
            try:
                path_mau_nhanh = mau_klgb[0][1]
                data_nhanh = auto_fill_klgb(df_kh, str(path_mau_nhanh), "")
                fname_nhanh = f"KL_GiaoBan_ToanCN_{datetime.now().strftime('%d%m%Y')}.docx"
                state_n = SCMStateManager()
                state_n.downloads.set("kl_giao_ban_docx", data_nhanh, fname_nhanh)
                st.success("✅ Đã tạo xong — nhấn nút bên dưới để tải về.")
            except Exception as e:  # conv: skip
                logger.error("kl_nhanh_btn: %s", e, exc_info=True)
                st.error(f"Lỗi xuất nhanh: {e}")

        col_pgd_kl, col_mau_kl = st.columns(2)
        with col_pgd_kl:
            pgd_kl = st.selectbox("Chọn PGD", ["Toàn CN"] + ds_pgd_all, key="kl_pgd")
        with col_mau_kl:
            ten_mau_kl = st.selectbox(
                "Mẫu biểu", [t[0] for t in mau_klgb], key="kl_mau")

        if st.button("🖨️ Tạo KL giao ban", type="primary", key="kl_btn"):
            try:
                df_kl = df_kh if pgd_kl == "Toàn CN" \
                        else df_kh[df_kh[COT_TEN_PGD] == pgd_kl]
                idx_mau = [t[0] for t in mau_klgb].index(ten_mau_kl)
                path_mau = mau_klgb[idx_mau][1]
                ten_pgd_str = "" if pgd_kl == "Toàn CN" else pgd_kl
                data = auto_fill_klgb(df_kl, str(path_mau), ten_pgd_str)
                fname = f"KL_GiaoBan_{pgd_kl}_{datetime.now().strftime('%d%m%Y')}.docx"
                state = SCMStateManager()
                state.downloads.set("kl_giao_ban_docx", data, fname)
                st.success("✅ Đã tạo xong — nhấn nút bên dưới để tải về.")
            except Exception as e:  # conv: skip
                logger.error("Lỗi trong khối except: %s", e, exc_info=True)
                st.error(f"Lỗi tạo KL giao ban: {e}")

        state = SCMStateManager()
        if state.downloads.has("kl_giao_ban_docx"):
            fname = state.downloads.get_filename("kl_giao_ban_docx") or "KL_GiaoBan.docx"
            if st.download_button(
                f"⬇️ Tải KL giao ban — {fname}",
                data=state.downloads.get_bytes("kl_giao_ban_docx"),
                file_name=fname,
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                key="kl_dl",
            ):
                state.downloads.clear("kl_giao_ban_docx")


def _render_canh_bao_no(df_full: pd.DataFrame, ds_pgd_all: list, role: str, username: str):
    """Cảnh báo Tín dụng — gọi tab_canh_bao_nqh tập trung."""
    from tabs.tab_canh_bao_nqh import render
    render(role=role, username=username, df_full=df_full, ds_pgd_all=ds_pgd_all)


def _render_canh_bao_no_sub(
    df_full: pd.DataFrame,
    ds_pgd_all: list,
    role: str,
    username: str,
    idx: int,
) -> None:
    """Render 1 trong 5 nhánh con Cảnh báo Tín dụng theo idx."""
    from tabs.tab_canh_bao_nqh import render
    render(role=role, username=username, df_full=df_full, ds_pgd_all=ds_pgd_all)


def _render_cbtd_dia_ban(tab_parent=None, **kw):
    """Nhóm CBTD & Địa bàn — 4 sub-tab: Dashboard · CBTD · ĐGD · Tổ TK&VV."""
    if tab_parent is not None:
        ctx = tab_parent
    else:
        ctx = st.container()
    with ctx:
        lazy_tabs(
            ["📊 Dashboard", "👔 Cán bộ tín dụng", "📍 Điểm Giao Dịch", "🏘️ Tổ TK&VV"],
            [
                lambda c: _get_tab("tab_cbtd_dashboard").render(c, **kw),
                lambda c: _get_tab("tab_cbtd").render(c, **kw),
                lambda c: _get_tab("tab_quan_ly_dgd").render(c, **kw),
                lambda c: _get_tab("tab_cdtotkvv").render(c, **dict(kw, cdto_mode="cn")),
            ],
            key="mgmt_cbtd",
        )


def _render_ndt_dp(role: str, username: str) -> None:
    """Tab quản lý Mã Nhà đầu tư Địa phương — dùng phân tầng GQVL ĐP."""
    from db import doc_ndt_dp_list, ghi_kv, ghi_audit

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

Danh sách này ảnh hưởng trực tiếp đến báo cáo **phân tầng GQVL** và tab **Phân tích** bên dưới.

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
- Hiển thị ngay tác động lên dữ liệu GQVL đang có trong cache:
  3 metric tổng quan + bảng chi tiết từng mã (số món, dư nợ trong hạn, dư nợ quá hạn)

---

### Sau khi thêm / sửa / xóa mã

> ⚠️ Thay đổi danh sách **chưa tự động cập nhật** dữ liệu phân tầng cũ.
> Để áp dụng: upload lại file GQVL **hoặc** nhấn **🔄 Làm mới** để tải lại cache,
> sau đó vào tab **📊 Phân tích** kiểm tra kết quả.

---

### Ai được làm gì?

| Thao tác | Admin CN | Manager CN | Xem |
|---|:---:|:---:|:---:|
| Xem danh sách & phân tích | ✅ | ✅ | ✅ |
| Thêm / Sửa / Xóa mã | ✅ | — | — |
| Xuất Excel | ✅ | ✅ | ✅ |
        """)

    ds       = doc_ndt_dp_list()   # list[dict] {"ma", "ghi_chu", "cap"}
    can_edit = normalize_role(str(role or "user")) == "admin_cn"

    ds_tinh = [x for x in ds if x.get("cap", "tinh") == "tinh"]
    ds_xa   = [x for x in ds if x.get("cap", "tinh") == "xa"]

    _CAP_OPTS = ["Cấp Tỉnh 🏛️", "Cấp Xã/Khác 🏘️"]
    _CAP_TO   = {"Cấp Tỉnh 🏛️": "tinh", "Cấp Xã/Khác 🏘️": "xa"}
    _CAP_FROM = {"tinh": "Cấp Tỉnh 🏛️", "xa": "Cấp Xã/Khác 🏘️"}

    _t1, _t2, _t3, _t4, _t5 = st.tabs([
        "🏛️ Cấp Tỉnh",
        "🏘️ Cấp Xã/Khác",
        "➕ Thêm mới",
        "✏️ Chỉnh sửa / Xóa",
        "📊 Phân tích",
    ])

    # ── Tab 1: Cấp Tỉnh (đọc) ────────────────────────────────────────────────
    with _t1:
        if ds_tinh:
            for item in ds_tinh:
                c1, c2 = st.columns([3, 5])
                c1.code(item["ma"])
                c2.markdown(item.get("ghi_chu", ""))
        else:
            st.info("Chưa có mã nào ở cấp Tỉnh.")

    # ── Tab 2: Cấp Xã/Khác (đọc) ─────────────────────────────────────────────
    with _t2:
        if ds_xa:
            for item in ds_xa:
                c1, c2 = st.columns([3, 5])
                c1.code(item["ma"])
                c2.markdown(item.get("ghi_chu", ""))
        else:
            st.info("Chưa có mã nào được đăng ký ở cấp Xã/Khác.")

    # ── Tab 3: Thêm mới ───────────────────────────────────────────────────────
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
                ghi_chu_them = st.text_input(
                    "Ghi chú",
                    placeholder="VD: UBND tỉnh Đồng Nai",
                    key="ndt_gc_them",
                )
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
                    ghi_kv("ndt_dp_list", ds_moi, username)
                    ghi_audit(username, "them_ndt_dp",
                              f"Thêm mã {ma_them} — {ghi_chu_them} ({cap_them})")
                    st.success(f"✅ Đã thêm mã **{ma_them}** vào {cap_them}")
                    st.rerun()

    # ── Tab 4: Chỉnh sửa / Xóa ───────────────────────────────────────────────
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
                gc_edit = c2.text_input(
                    "Ghi chú",
                    value=item.get("ghi_chu", "") or "",
                    key=f"ndt_gc_{i}",
                    label_visibility="collapsed",
                )
                cap_current = _CAP_FROM.get(item.get("cap", "tinh"), _CAP_OPTS[0])
                cap_edit = c3.selectbox(
                    "Cấp",
                    _CAP_OPTS,
                    index=_CAP_OPTS.index(cap_current),
                    key=f"ndt_cap_{i}",
                    label_visibility="collapsed",
                )
                if c4.button("💾", key=f"luu_ndt_{i}", help="Lưu thay đổi"):
                    ds_moi = [dict(x) for x in ds]
                    ds_moi[i]["ghi_chu"] = (gc_edit or "").strip()
                    ds_moi[i]["cap"]     = _CAP_TO[cap_edit]
                    ghi_kv("ndt_dp_list", ds_moi, username)
                    ghi_audit(username, "sua_ndt_dp",
                              f"Sửa mã {item['ma']} → ghi chú: {gc_edit}, cấp: {cap_edit}")
                    st.rerun()
                if c5.button("🗑️", key=f"xoa_ndt_{i}",
                             disabled=(len(ds) <= 1),
                             help="Không thể xóa khi chỉ còn 1 mã"):
                    ds_moi = [x for j, x in enumerate(ds) if j != i]
                    ghi_kv("ndt_dp_list", ds_moi, username)
                    ghi_audit(username, "xoa_ndt_dp", f"Xóa mã {item['ma']}")
                    st.rerun()

    # ── Tab 5: Phân tích ─────────────────────────────────────────────────────
    with _t5:
        try:
            from pathlib import Path
            from config import CACHE_DIR, COT_MA_NDT, COT_NGUON_VON, COT_DU_NO_TH, COT_DU_NO_QH

            gqvl_path = Path(CACHE_DIR) / "gqvl.parquet"
            if not gqvl_path.exists():
                st.info("Chưa có dữ liệu GQVL. Upload file để xem phân tích.")
            else:
                df_gqvl = pd.read_parquet(gqvl_path)
                if (COT_NGUON_VON not in df_gqvl.columns) or (COT_MA_NDT not in df_gqvl.columns):
                    st.warning("File GQVL không có đủ cột để phân tích.")
                elif df_gqvl[COT_NGUON_VON].isna().all():
                    st.warning(
                        "⚠️ Cột 'Nguồn vốn' trong cache GQVL toàn NaN — "
                        "dữ liệu cũ bị lỗi định dạng. Vui lòng upload lại file GQVL."
                    )
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
        except Exception as e:  # conv: skip
            logger.error("Lỗi trong khối except: %s", e, exc_info=True)
            st.warning(f"Không thể phân tích tác động GQVL: {e}")

    # ── Xuất Excel + Làm mới ─────────────────────────────────────────────────
    col_xl, col_rf = st.columns([3, 1])
    with col_xl:
        if st.button("📥 Xuất danh sách Excel", key="export_ndt_dp"):
            import io
            df_export = pd.DataFrame([
                {"Mã NĐT": x["ma"],
                 "Ghi chú": x.get("ghi_chu", ""),
                 "Phân loại cấp": _CAP_FROM.get(x.get("cap", "tinh"), "Cấp Tỉnh 🏛️")}
                for x in ds
            ])
            buf = io.BytesIO()
            df_export.to_excel(buf, index=False)
            st.download_button(
                "💾 Tải về",
                data=buf.getvalue(),
                file_name="danh_sach_ndt_dp.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="dl_ndt_dp",
            )
    with col_rf:
        if st.button("🔄 Làm mới", key="btn_refresh_ndt_dp", use_container_width=True,
                     help="Xóa cache và tải lại dữ liệu GQVL"):
            st.cache_data.clear()
            st.rerun()


def _render_quan_ly_template(df: pd.DataFrame):
    """
    Sub-tab Quản lý Template — Upload, xem, xóa file .docx và test mẫu.
    Chỉ dành cho role admin/manager.
    """
    st.subheader("📁 Quản lý Template Word")
    st.caption("Upload, quản lý và test các mẫu biểu .docx cho báo cáo tự động")

    # Tạo thư mục templates nếu chưa có
    templates_path = Path(TEMPLATES_DIR)
    templates_path.mkdir(exist_ok=True)

    tab_upload, tab_danh_sach, tab_test = st.tabs([
        "📤 Upload mẫu mới", "📋 Danh sách Template", "🧪 Test Template"
    ])

    # ══════════════════════════════════════════════════════════════════════════════
    # TAB 1: UPLOAD MẪU MỚI
    # ══════════════════════════════════════════════════════════════════════════════
    with tab_upload:
        st.markdown("**📤 Upload file template Word (.docx)**")
        
        uploaded_file = st.file_uploader(
            "Chọn file .docx",
            type=['docx'],
            help="Chỉ chấp nhận file .docx. Tên file nên mô tả rõ ràng mục đích sử dụng.",
            key="template_uploader"
        )
        
        if uploaded_file is not None:
            col1, col2 = st.columns([3, 1])
            
            with col1:
                # Hiển thị thông tin file
                st.info(f"📄 **{uploaded_file.name}**")
                st.text(f"Kích thước: {fmt_so(len(uploaded_file.getvalue()))} bytes")
                
                # Tùy chọn đổi tên file
                ten_file_moi = st.text_input(
                    "Tên file (để trống = giữ tên gốc)", 
                    value="",
                    help="VD: 'Mau_To_trinh_cho_vay_NOXH' (không cần .docx)",
                    key="template_new_name"
                )
            
            with col2:
                st.markdown("<br><br>", unsafe_allow_html=True)
                if st.button("💾 Lưu Template", type="primary", key="save_template"):
                    try:
                        # Xác định tên file
                        if ten_file_moi.strip():
                            # Loại bỏ .docx nếu user nhập
                            ten_file = ten_file_moi.strip().replace('.docx', '') + '.docx'
                        else:
                            ten_file = uploaded_file.name
                        
                        # Kiểm tra tên file hợp lệ
                        if not ten_file.lower().endswith('.docx'):
                            ten_file += '.docx'
                        
                        # Đường dẫn lưu
                        file_path = templates_path / ten_file
                        
                        # Kiểm tra file đã tồn tại
                        if file_path.exists():
                            st.warning(f"⚠️ File **{ten_file}** đã tồn tại!")
                            ghi_de = st.checkbox("✅ Ghi đè file cũ", key="overwrite_template")
                            if not ghi_de:
                                st.stop()
                        
                        # Lưu file
                        with open(file_path, 'wb') as f:
                            f.write(uploaded_file.getvalue())
                        
                        st.success(f"✅ Đã lưu template: **{ten_file}**")
                        st.balloons()
                        
                        # Reload để hiển thị file mới
                        st.rerun()
                        
                    except Exception as e:  # conv: skip
                        logger.error("Lỗi trong khối except: %s", e, exc_info=True)
                        st.error(f"❌ Lỗi lưu file: {e}")

    # ══════════════════════════════════════════════════════════════════════════════
    # TAB 2: DANH SÁCH TEMPLATE
    # ══════════════════════════════════════════════════════════════════════════════
    with tab_danh_sach:
        st.markdown("**📋 Danh sách Template hiện có**")
        
        # Quét danh sách template
        templates = quet_templates(TEMPLATES_DIR)
        
        if not templates:
            st.info("📭 Chưa có template nào. Hãy upload file .docx ở tab bên trái.")
        else:
            # Tạo DataFrame để hiển thị
            template_data = []
            for ten_hienthi, file_path in templates:
                file_stat = file_path.stat()
                template_data.append({
                    'Tên hiển thị': ten_hienthi,
                    'Tên file': file_path.name,
                    'Kích thước (KB)': f"{file_stat.st_size / 1024:.1f}",
                    'Ngày tạo': datetime.fromtimestamp(file_stat.st_ctime).strftime("%d/%m/%Y %H:%M"),
                    'Ngày sửa': datetime.fromtimestamp(file_stat.st_mtime).strftime("%d/%m/%Y %H:%M"),
                    'Đường dẫn': str(file_path)
                })
            
            df_templates = pd.DataFrame(template_data)
            hien_thi_dataframe_phan_trang(
                df_templates.drop(columns=['Đường dẫn']),
                key="mgmt_template_danh_sach",
            )
            
            st.divider()
            
            # Chức năng xóa template
            st.markdown("**🗑️ Xóa Template**")
            col_chon, col_xoa = st.columns([3, 1])
            
            with col_chon:
                chon_xoa = st.selectbox(
                    "Chọn template để xóa",
                    options=[f"{row['Tên hiển thị']} ({row['Tên file']})" for _, row in df_templates.iterrows()],
                    key="template_delete_select"
                )
            
            with col_xoa:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("🗑️ Xóa", type="secondary", key="delete_template"):
                    # Tìm file tương ứng
                    idx = [f"{row['Tên hiển thị']} ({row['Tên file']})" for _, row in df_templates.iterrows()].index(chon_xoa)
                    file_to_delete = Path(df_templates.iloc[idx]['Đường dẫn'])
                    
                    try:
                        file_to_delete.unlink()  # Xóa file
                        st.success(f"✅ Đã xóa: {file_to_delete.name}")
                        st.rerun()
                    except Exception as e:  # conv: skip
                        logger.error("Lỗi trong khối except: %s", e, exc_info=True)
                        st.error(f"❌ Không thể xóa file: {e}")

    # ══════════════════════════════════════════════════════════════════════════════
    # TAB 3: TEST TEMPLATE
    # ══════════════════════════════════════════════════════════════════════════════
    with tab_test:
        st.markdown("**🧪 Test Template với dữ liệu mẫu**")
        
        if df is None or df.empty:
            st.warning("⚠️ Không có dữ liệu HSTD để test. Hãy upload dữ liệu trước.")
            return
        
        templates = quet_templates(TEMPLATES_DIR)
        if not templates:
            st.info("📭 Không có template để test.")
            return
        
        # Chọn template và hồ sơ
        col_template, col_hoso = st.columns(2)
        
        with col_template:
            chon_template = st.selectbox(
                "Chọn Template",
                options=[t[0] for t in templates],
                key="test_template_select"
            )
        
        with col_hoso:
            # Lấy 10 hồ sơ đầu làm mẫu
            df_sample = df.head(10) if len(df) >= 10 else df
            ds_khach_hang = [
                f"{row.get(COT_MA_KH, 'N/A')} - {row.get(COT_TEN_KH, 'Không tên')[:20]}"
                for _, row in df_sample.iterrows()
            ]
            
            chon_hoso = st.selectbox(
                "Chọn hồ sơ test",
                options=ds_khach_hang,
                key="test_hoso_select"
            )
        
        # Hiển thị thông tin hồ sơ được chọn
        idx_hoso = ds_khach_hang.index(chon_hoso)
        row_test = df_sample.iloc[idx_hoso]
        
        with st.expander("📄 Thông tin hồ sơ test", expanded=True):
            col1, col2 = st.columns(2)
            with col1:
                st.write(f"**Mã KH:** {row_test.get(COT_MA_KH, 'N/A')}")
                st.write(f"**Tên KH:** {row_test.get(COT_TEN_KH, 'N/A')}")
                st.write(f"**Số khoản vay:** {row_test.get(COT_SO_KU, 'N/A')}")
                st.write(f"**Mức vay:** {fmt(row_test.get(COT_MUC_VAY, 0))} đồng")
            with col2:
                st.write(f"**Dư nợ:** {fmt(row_test.get(COT_TONG_DU_NO, 0))} đồng")
                st.write(f"**Ngày vay:** {row_test.get(COT_NGAY_VAY, 'N/A')}")
                st.write(f"**Thời hạn:** {row_test.get(COT_THOI_HAN, 'N/A')} tháng")
                st.write(f"**Lãi suất:** {row_test.get(COT_LAI_SUAT, 'N/A')}%")
        
        # Nút test
        if st.button("🚀 Test Template", type="primary", key="test_template_btn"):
            try:
                # Tìm template được chọn
                template_path = None
                for ten, path in templates:
                    if ten == chon_template:
                        template_path = path
                        break
                
                if template_path is None:
                    st.error("❌ Không tìm thấy template!")
                    return
                
                # Tạo dữ liệu bổ sung cho test
                extra_data = {
                    "{{nguoi_ky}}": "Nguyễn Văn Test Manager",
                    "{{chuc_vu}}": "Phó Giám đốc Chi nhánh",
                    "{{so_quyet_dinh}}": "001/QĐ-CN",
                }
                
                # Gọi hàm auto_fill_document
                doc_bytes = auto_fill_document(
                    data_row=row_test,
                    template_path=str(template_path),
                    tag_map=TAG_MAP,
                    extra=extra_data
                )
                
                # Download button
                file_name = f"Test_{chon_template.replace(' ', '_')}_{datetime.now().strftime('%d%m%Y_%H%M')}.docx"
                
                st.download_button(
                    label="⬇️ Tải file Word đã test",
                    data=doc_bytes,
                    file_name=file_name,
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    key="download_test_doc"
                )
                
                st.success("✅ Test thành công! Nhấn nút trên để tải file Word.")
                
            except Exception as e:  # conv: skip
                logger.error("Lỗi trong khối except: %s", e, exc_info=True)
                st.error(f"❌ Lỗi test template: {e}")
                st.exception(e)  # Debug info


def _banner_pgd_chua_upload(ds_pgd: list, threshold_days: int = 7) -> None:
    """Banner cảnh báo PGD chưa upload file HSTD trong threshold_days ngày gần nhất."""
    from pathlib import Path as _Path
    from config import PGD_DATA_DIR as _PGD_DATA_DIR
    from data.pgd import pgd_slug as _pgd_slug

    now = datetime.now()
    pgd_chua = []
    pgd_cu = []

    for pgd in ds_pgd:
        slug = _pgd_slug(pgd)
        p = _Path(_PGD_DATA_DIR) / slug / "hstd_latest.xlsx"
        if not p.exists():
            pgd_chua.append(pgd)
        else:
            age = (now - datetime.fromtimestamp(p.stat().st_mtime)).days
            if age >= threshold_days:
                pgd_cu.append((pgd, age))

    total = len(pgd_chua) + len(pgd_cu)
    if total == 0:
        return

    with st.expander(f"⚠️ {total} PGD chưa cập nhật dữ liệu trong {threshold_days} ngày qua", expanded=False):
        if pgd_chua:
            st.markdown(f"**❌ Chưa upload lần nào ({len(pgd_chua)} PGD):**")
            st.markdown("  ".join(f"`{p}`" for p in pgd_chua))
        if pgd_cu:
            st.markdown(f"**🕐 Upload đã lâu ({len(pgd_cu)} PGD):**")
            _rows = [{"PGD": p, "Số ngày từ lần upload cuối": d} for p, d in sorted(pgd_cu, key=lambda x: -x[1])]
            st.dataframe(pd.DataFrame(_rows), use_container_width=True, height=min(240, len(_rows) * 45 + 50))


@st.cache_data(show_spinner=False, ttl=300)
def _doc_nqh_delta_snapshot() -> pd.DataFrame:
    """Lấy delta NQH giữa 2 kỳ gần nhất từ hstd_snapshot."""
    import sqlite3
    from db import get_conn
    with get_conn() as conn:
        ky_list = [r[0] for r in conn.execute(
            "SELECT DISTINCT ky FROM hstd_snapshot ORDER BY ky DESC LIMIT 2"
        ).fetchall()]
    if len(ky_list) < 2:
        return pd.DataFrame()
    ky_curr, ky_prev = ky_list[0], ky_list[1]
    with get_conn() as conn:
        df_curr = pd.read_sql_query(
            "SELECT ten_pgd, SUM(du_no_qh) as qh_curr, SUM(tong_du_no) as dn_curr "
            "FROM hstd_snapshot WHERE ky=? GROUP BY ten_pgd",
            conn, params=(ky_curr,),
        )
        df_prev = pd.read_sql_query(
            "SELECT ten_pgd, SUM(du_no_qh) as qh_prev, SUM(tong_du_no) as dn_prev "
            "FROM hstd_snapshot WHERE ky=? GROUP BY ten_pgd",
            conn, params=(ky_prev,),
        )
    df = df_curr.merge(df_prev, on="ten_pgd", how="left").fillna(0)
    df["delta_qh"] = df["qh_curr"] - df["qh_prev"]
    df["pct_qh"] = df["delta_qh"] / df["qh_prev"].replace(0, float("nan")) * 100
    df["ky_curr"] = ky_curr
    df["ky_prev"] = ky_prev
    return df


def _render_nqh_tang_dot_bien(key_prefix: str = "nqh_db_") -> None:
    """Hiển thị bảng NQH tăng đột biến dựa trên hstd_snapshot."""
    from utils import fmt_ty as _fmt_ty, fmt_so as _fmt_so

    df = _doc_nqh_delta_snapshot()
    if df.empty:
        st.info("ℹ️ Chưa đủ 2 kỳ snapshot để so sánh. Hãy merge HSTD ít nhất 2 lần.")
        return

    ky_curr = df["ky_curr"].iloc[0]
    ky_prev = df["ky_prev"].iloc[0]
    st.caption(f"So sánh kỳ **{ky_curr}** vs **{ky_prev}**")

    df_show = df[df["ten_pgd"] != "Hội sở Chi nhánh tỉnh"].copy() if len(df) > 1 else df.copy()
    df_show = df_show.sort_values("delta_qh", ascending=False)

    tang = df_show[df_show["delta_qh"] > 0]
    giam = df_show[df_show["delta_qh"] < 0]

    c1, c2 = st.columns(2)
    c1.metric("PGD có NQH tăng", len(tang), delta=f"{len(tang)} đơn vị", delta_color="inverse" if len(tang) else "off")
    c2.metric("PGD có NQH giảm", len(giam), delta=f"{len(giam)} đơn vị", delta_color="normal" if len(giam) else "off")

    cols_display = {
        "ten_pgd": "PGD",
        "qh_prev": f"NQH kỳ {ky_prev} (triệu)",
        "qh_curr": f"NQH kỳ {ky_curr} (triệu)",
        "delta_qh": "Tăng/Giảm (triệu)",
        "pct_qh": "% thay đổi",
    }
    df_out = df_show[list(cols_display.keys())].rename(columns=cols_display).copy()
    for col in [f"NQH kỳ {ky_prev} (triệu)", f"NQH kỳ {ky_curr} (triệu)", "Tăng/Giảm (triệu)"]:
        if col in df_out.columns:
            df_out[col] = df_out[col].apply(_fmt_ty)
    df_out["% thay đổi"] = df_out["% thay đổi"].apply(
        lambda x: f"+{x:.1f}".replace(".", ",") + "%" if x > 0 else (f"{x:.1f}".replace(".", ",") + "%" if not pd.isna(x) else "—")
    )
    st.dataframe(df_out, use_container_width=True, height=500)


def _build_all_items(role: str, username: str, **kwargs) -> list:
    """Xây danh sách ALL_ITEMS — dùng chung cho sidebar và render."""
    # Đảm bảo mọi lambda dùng **kwargs đều có đủ role và username
    kwargs.setdefault("role", role)
    kwargs.setdefault("username", username)
    df_full = kwargs.get("df_full")
    ds_pgd_all = kwargs.get("ds_pgd_all", [])
    can_upload = kwargs.get("can_upload", False)
    role_n = normalize_role(str(role or "user"))

    ALL_ITEMS = [
        {"group": "Thông tin chung", "label": "📊 Thông tin chung", "icon": "info-circle", "fn": lambda: _get_tab("tab_tongquan").render(None, **kwargs)},
        {"group": "Thông tin chung", "label": "🏢 Toàn cảnh 22 PGD", "icon": "grid", "fn": lambda: _get_tab("tab_pgd_cards").render(None, **kwargs)},
        {"group": "Thông tin chung", "label": "🔍 Tra cứu Khách hàng", "icon": "search", "fn": lambda: _get_tab("tab_tracuu_v2").render(None, **kwargs)},
        {"group": "Phối hợp với PGD", "label": "📋 Quản lý Công văn", "icon": "file-text", "fn": lambda: _get_tab("tab_quan_ly_cong_van").render(None, **kwargs)},
        {"group": "Phối hợp với PGD", "label": "📊 Quản lý Công việc & Nhiệm vụ", "icon": "layout", "fn": lambda: _get_tab("tab_quan_ly_cv").render(None, **kwargs)},
        {"group": "Phối hợp với PGD", "label": "🗂️ Nội bộ Phòng KH-NV", "icon": "users", "fn": lambda: _get_tab("tab_khnv_noi_bo").render(None, **kwargs)},
        {"group": "Phối hợp với PGD", "label": "📋 Giao & ĐC KHTD", "icon": "upload", "fn": lambda: _get_tab("tab_khtd_giao_dc").render(None, **kwargs)},
        {"group": "Phối hợp với PGD", "label": "🔭 Xây dựng KHTD 1-3-5 năm", "icon": "calendar-plus", "fn": lambda: _get_tab("tab_xay_dung_khtd").render(None, **kwargs)},
        {"group": "Phối hợp với PGD", "label": "🏦 Nguồn vốn địa phương", "icon": "bank", "fn": lambda: _get_tab("tab_hhi").render(None, **kwargs)},
        {
            "group": "Giám sát",
            "label": "Cảnh báo Tín dụng",
            "icon": "alert-triangle",
            "fn": lambda: _render_canh_bao_no(df_full, ds_pgd_all, role, username),
        },
        {"group": "Giám sát",     "label": "📊 So sánh kỳ",            "icon": "chart-line", "fn": lambda: _get_tab("tab_so_sanh_ky").render(None, **kwargs)},
        {"group": "Giám sát",     "label": "🔴 NQH tăng đột biến",    "icon": "trending-up",  "fn": lambda: _render_nqh_tang_dot_bien()},
        {"group": "Giám sát",     "label": "🛡️ Chất lượng Dữ liệu",  "icon": "shield-check", "fn": lambda: _get_tab("tab_data_quality").render(None, **kwargs)},
        {"group": "Kiểm soát",     "label": "Kiểm soát nội bộ",    "icon": "search",         "fn": lambda: _get_tab("tab_kiem_soat").render_tab(df_full, role, kwargs.get("username", "unknown"))},
        {"group": "Kiểm soát",     "label": "🔍 Kiểm toán Nội bộ (KTNB)", "icon": "file-search", "fn": lambda: _get_tab("tab_ktnb").render(None, **kwargs)},
        {"group": "Kiểm soát",     "label": "Xử lý Rủi ro",   "icon": "alert-circle",   "fn": lambda: _get_tab("tab_xu_ly_rui_ro").render(None, **kwargs)},
        {
            "group": "Kiểm soát",
            "label": "🔒 Chuyên Đề Nợ Khoanh",
            "icon": "lock",
            "children": [
                {"label": "📊 Tổng quan Nợ Khoanh",          "fn": lambda: _get_tab("tab_no_khoanh").render(None, **{**kwargs, "nhom": "tongquan"})},
                {"label": "🔒 Quản lý Nợ Khoanh theo CV 368", "fn": lambda: _get_tab("tab_no_khoanh").render(None, **{**kwargs, "nhom": "cv368"})},
            ],
        },
        {"group": "Kế hoạch và Thực hiện KHTD", "label": "Kế hoạch tín dụng", "icon": "file-text",  "fn": lambda: _get_tab("tab_khtd").render(None, **dict(kwargs, khtd_mode="cn"))},
        {"group": "Kế hoạch và Thực hiện KHTD", "label": "📡 Điện báo & KH vs TH", "icon": "antenna",   "fn": lambda: _get_tab("tab_candoi").render(None, **kwargs)},
        {"group": "Kế hoạch và Thực hiện KHTD", "label": "Xuất báo cáo KHTD",  "icon": "file-export", "fn": lambda: _get_tab("tab_khtd_xuat").render_xuat_baocao(role=kwargs.get("role", ""), username=kwargs.get("username", ""), df_full=kwargs.get("df"))},
        {"group": "Phân tích", "label": "🏷️ Phân loại Khách hàng", "icon": "tag", "fn": lambda: _get_tab("tab_phan_loai_kh").render(None, **kwargs)},
        {
            "group": "Báo cáo",
            "label": "Báo cáo tín dụng",
            "icon": "file",
            "children": [
                {"label": "📊 Báo cáo tín dụng", "fn": lambda: _get_tab("tab_baocao").render(None, **kwargs)},
                {"label": "⏰ Nợ Đến Hạn",        "fn": lambda df_full=df_full, ds_pgd_all=ds_pgd_all, role=role, username=kwargs.get("username", "unknown"), idx=0: _render_canh_bao_no_sub(df_full, ds_pgd_all, role, username, idx)},
            ],
        },
        {"group": "Báo cáo", "label": "📅 Báo cáo định kỳ", "icon": "calendar", "fn": lambda: _get_tab("tab_bao_cao_dinh_ky").render(None, **kwargs)},
        {"group": "Báo cáo", "label": "📄 Báo cáo KHNV", "icon": "file-report", "fn": lambda: _get_tab("tab_khnv_bao_cao").render(None, **kwargs)},
        {"group": "Ủy Thác",       "label": "🏛️ Ban Đại Diện", "icon": "building",       "fn": lambda: _get_tab("tab_ban_dai_dien").render(None, cap="tinh", **kwargs)},
        {"group": "Ủy Thác",       "label": "🤝 Ủy thác", "icon": "handshake", "fn": lambda: _get_tab("tab_uy_thac").render(None, **kwargs)},
        {"group": "Ủy Thác",       "label": "👔 CBTD & Địa bàn",  "icon": "user",  "fn": lambda: _render_cbtd_dia_ban(None, **kwargs)},
    ]

    if can_upload:
        ALL_ITEMS.append({"group": "Hệ thống", "label": "Template văn bản", "icon": "template", "fn": lambda: _render_quan_ly_template(df_full)})
    if role_n in ("admin_cn", "manager_cn"):
        ALL_ITEMS.append({"group": "Hệ thống", "label": "Mã NĐT địa phương", "icon": "building-bank", "fn": lambda: _render_ndt_dp(role_n, kwargs.get("username", "unknown"))})
    if role_n == "admin_cn":
        ALL_ITEMS.append({"group": "Hệ thống", "label": "Nhật ký hệ thống", "icon": "list", "fn": lambda: _get_tab("tab_audit_log").render(None, **kwargs)})
        ALL_ITEMS.append({"group": "Hệ thống", "label": "🔐 Quản lý bảo mật", "icon": "shield", "fn": lambda: _get_tab("tab_security").render(None, **kwargs)})
    ALL_ITEMS.append({"group": "Hệ thống", "label": "🔍 Trạng thái hệ thống", "icon": "pulse", "fn": lambda: _get_tab("tab_trang_thai_nguon").render(None, **kwargs)})
    ALL_ITEMS.append({"group": "Hệ thống", "label": "Upload dữ liệu", "icon": "upload", "fn": lambda: _get_tab("tab_upload_khnv").render(None, **kwargs)})
    ALL_ITEMS.append({"group": "Hệ thống", "label": "📖 Hướng dẫn", "icon": "book", "fn": lambda: render_huong_dan()})

    return ALL_ITEMS


def render_sidebar_menu(role: str, username: str, **kwargs):
    """Render menu ĐIỀU HÀNH — gọi từ app.py bên trong with st.sidebar.
    Tối ưu: dùng st.radio() theo nhóm thay cho ~25 st.button() riêng lẻ."""

    state = SCMStateManager()
    GROUP_COLORS = {
        "Giám sát":                    {"bg": "#0D2137", "border": "#64B5F6", "text": "#90CAF9"},
        "Kiểm soát":                   {"bg": "#2D0D14", "border": "#EF9A9A", "text": "#F48FB1"},
        "Kế hoạch và Thực hiện KHTD": {"bg": "#0D2818", "border": "#A5D6A7", "text": "#A5D6A7"},
        "Báo cáo":                     {"bg": "#2D1F0D", "border": "#FFCC80", "text": "#FFD54F"},
        "Ủy Thác":                     {"bg": "#1A1040", "border": "#CE93D8", "text": "#CE93D8"},
        "Phối hợp với PGD":            {"bg": "#0D2818", "border": "#80CBC4", "text": "#80CBC4"},
        "Thông tin chung":             {"bg": "#0D2137", "border": "#90CAF9", "text": "#90CAF9"},
        "Hệ thống":                    {"bg": "#1E2130", "border": "#94A3B8", "text": "#B0BEC5"},
    }

    all_items = _build_all_items(role, username, **kwargs)
    if not all_items:
        return

    valid_labels = [x["label"] for x in all_items] + [
        c["label"] for x in all_items for c in x.get("children", [])
    ]

    default_label = all_items[0]["label"]
    active_label = state.nav_ws_mgmt_menu
    if active_label not in valid_labels:
        state.nav_ws_mgmt_menu = default_label
        active_label = default_label

    st.divider()

    st.markdown(
        "<p style='font-size:14px;font-weight:700;"
        "color:#94A3B8;margin-bottom:6px'>MENU ĐIỀU HÀNH</p>",
        unsafe_allow_html=True
    )

    groups = []
    current_grp = None
    cur_flat = []
    cur_acc = []
    for item in all_items:
        g = item["group"]
        if g != current_grp:
            if cur_flat or cur_acc:
                groups.append((current_grp, cur_flat, cur_acc))
            current_grp = g
            cur_flat = []
            cur_acc = []
        if item.get("children"):
            cur_acc.append(item)
        else:
            cur_flat.append(item)
    if cur_flat or cur_acc:
        groups.append((current_grp, cur_flat, cur_acc))

    for grp_name, flat_items, acc_items in groups:
        clr = GROUP_COLORS.get(grp_name, {"bg": "#F1EFE8", "border": "#888", "text": "#444"})

        st.markdown(
            f"<p style='font-size:11px;font-weight:700;"
            f"color:{clr['text']};text-transform:uppercase;"
            f"letter-spacing:0.06em;padding:12px 4px 4px;margin:0'>"
            f"{grp_name}</p>",
            unsafe_allow_html=True,
        )

        if flat_items:
            for item in flat_items:
                is_active = item["label"] == active_label
                if is_active:
                    st.markdown(
                        f"<div style='"
                        f"background:#E65100;"
                        f"border-left:3px solid #BF360C;"
                        f"color:#FFFFFF;"
                        f"font-size:14px;font-weight:700;"
                        f"padding:10px 12px 10px 14px;"
                        f"border-radius:0 6px 6px 0;"
                        f"margin-bottom:4px'>"
                        f"{item['label']}</div>",
                        unsafe_allow_html=True,
                    )
                else:
                    if st.button(
                        item["label"],
                        key=f"menu_btn_{item['label']}",
                        use_container_width=True,
                    ):
                        state.nav_ws_mgmt_menu = item["label"]
                        st.rerun()

        for item in acc_items:
            children = item.get("children", [])
            child_labels = [c["label"] for c in children]
            is_child_active = active_label in child_labels
            open_key = f"ws_mgmt_acc_{item['label']}"

            if is_child_active and not st.session_state.get(open_key):
                st.session_state[open_key] = True

            is_open = st.session_state.get(open_key, False)

            if is_child_active:
                st.markdown(
                    f"<div style='"
                    f"background:#E65100;"
                    f"border-left:3px solid #BF360C;"
                    f"color:#FFFFFF;"
                    f"font-size:14px;font-weight:700;"
                    f"padding:10px 12px 10px 14px;"
                    f"border-radius:0 6px 6px 0;"
                    f"margin-bottom:4px'>"
                    f"\u25be {item['label']}</div>",
                    unsafe_allow_html=True,
                )
            else:
                arrow = "\u25be" if is_open else "\u25b8"
                if st.button(
                    f"{arrow} {item['label']}",
                    key=f"menu_acc_{item['label']}",
                    use_container_width=True,
                ):
                    st.session_state[open_key] = not is_open
                    st.rerun()

            if is_open:
                for child in children:
                    is_child_sel = active_label == child["label"]
                    if is_child_sel:
                        st.markdown(
                            f"<div style='background:#E65100;"
                            f"border-left:4px solid #BF360C;"
                            f"color:#FFFFFF;font-size:13px;font-weight:700;"
                            f"padding:8px 10px 8px 22px;"
                            f"border-radius:0 6px 6px 0;margin-bottom:3px'>"
                            f"\u25cf {child['label']}</div>",
                            unsafe_allow_html=True,
                        )
                    else:
                        _, col = st.columns([0.06, 0.94])
                        with col:
                            if st.button(
                                f"\u21b3 {child['label']}",
                                key=f"menu_child_{child['label']}",
                                use_container_width=True,
                            ):
                                state.nav_ws_mgmt_menu = child["label"]
                                st.rerun()

def render(**kwargs):
    _wl = st.session_state.pop("_data_load_warning", None)
    if _wl:
        st.warning(_wl)

    def _tab_so_sanh_ky_fn(**kw):
        _get_tab("tab_so_sanh_ky").render(None, **kw)

    role       = kwargs.get("role")
    username   = kwargs.get("username", "unknown")
    df         = kwargs.get("df")
    df_full    = kwargs.get("df_full", df)
    ds_pgd_all = kwargs.get("ds_pgd_all", [])
    role_n = normalize_role(str(role or "user"))
    can_upload = get_permissions(role_n)["can_upload"]
    can_manage_users = get_permissions(role_n)["can_manage_users"]

    st.title("📋 Phòng KH-NV")
    st.caption("Giám sát chỉ tiêu · Cân đối vốn · Quản lý NQH · GQVL · Quản lý CBTD")

    from config import DS_PGD as _DS_PGD
    _banner_pgd_chua_upload([p for p in _DS_PGD if p != "Hội sở Chi nhánh tỉnh"])

    filtered_kw = {k: v for k, v in kwargs.items()
                   if k not in ("role", "username", "df", "df_full", "ds_pgd_all")}
    _data_id = id(df_full)
    if "_mgmt_all_items_cache" not in st.session_state or st.session_state.get("_mgmt_all_items_data_id") != _data_id:
        ALL_ITEMS = _build_all_items(
            role, username,
            df=df, df_full=df_full, ds_pgd_all=ds_pgd_all,
            can_upload=can_upload, **filtered_kw
        )
        st.session_state["_mgmt_all_items_cache"] = ALL_ITEMS
        st.session_state["_mgmt_all_items_data_id"] = _data_id
    else:
        ALL_ITEMS = st.session_state["_mgmt_all_items_cache"]

    # ── Navigation: điều hướng hoàn toàn qua sidebar (render_sidebar_menu) ──
    valid_labels = [x["label"] for x in ALL_ITEMS] + [
        c["label"] for x in ALL_ITEMS for c in x.get("children", [])
    ]

    # Handle jump từ shortcut / nút điều hướng ngoài ws_management
    state = SCMStateManager()
    jump_label = state.nav_ws_mgmt_jump
    if jump_label and jump_label in valid_labels:
        state.nav_ws_mgmt_menu = jump_label
        st.toast(f"✨ Đã chuyển tới: {jump_label}", icon="👆")

    # Khởi tạo / validate ws_mgmt_menu — khôi phục từ kv_store nếu session mới
    active_label = state.nav_ws_mgmt_menu
    _mem_key = f"nav_ws_mgmt_{username}"
    if not active_label or active_label not in valid_labels:
        _saved = db.doc_kv(_mem_key)
        if _saved and _saved in valid_labels:
            active_label = _saved
        else:
            active_label = ALL_ITEMS[0]["label"]
        state.nav_ws_mgmt_menu = active_label
    else:
        _prev_saved = db.doc_kv(_mem_key)
        if _prev_saved != active_label:
            db.ghi_kv(_mem_key, active_label, username)

    # ── Render DUY NHẤT mục đang chọn ────────────────────────────────────
    active_item = next((x for x in ALL_ITEMS if x["label"] == active_label), None)
    if active_item and active_item.get("fn"):
        try:
            active_item["fn"]()
        except Exception as e:  # conv: skip
            logger.error("Lỗi trong khối except: %s", e, exc_info=True)
            import traceback
            st.error(f"❌ Lỗi render **{active_label}**: {e}")
            st.code(traceback.format_exc())
    else:
        # Tìm trong children (accordion)
        found_child = False
        for parent in ALL_ITEMS:
            for child in parent.get("children", []):
                if child["label"] == active_label:
                    try:
                        child["fn"]()
                    except Exception as e:  # conv: skip
                        logger.error("Lỗi trong khối except: %s", e, exc_info=True)
                        import traceback

                        st.error(f"❌ Lỗi render **{active_label}**: {e}")
                        st.code(traceback.format_exc())
                    found_child = True
                    break
            if found_child:
                break
        if not found_child:
            st.info(f"Tính năng **{active_label}** đang được phát triển.")
