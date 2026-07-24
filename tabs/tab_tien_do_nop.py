"""Tiến độ nộp báo cáo định kỳ của các PGD — đọc từ Google Sheets."""


from __future__ import annotations

from logger import get_logger
logger = get_logger(__name__)

from pathlib import Path

import pandas as pd
import streamlit as st
from streamlit.delta_generator import DeltaGenerator

from auth import la_phan_he_cn, normalize_role
from tabs.base_tab import TabContext
from tabs.tab_tien_do_nop_archive import render_archive
from tabs.tab_tien_do_nop_list import render_submission_list
from tabs.tab_tien_do_nop_manual import render_manual_override
from tabs.tab_tien_do_nop_settings import render_settings
from utils import xuat_excel

# ── Import từ service lõi (single source of truth) ──
from services.report_submission_service import (
    DS_PGD_ALL,
    doc_du_lieu_gsheet,
    doc_deadline_config,
    doc_luu_tru_config,
    loc_deadline_dang_hoat_dong,
    loc_du_lieu_luu_tru,
    kiem_tra_ket_noi_gsheet,
    lay_loi_doc_gsheet_gan_nhat,
    tao_ma_tran_tien_do,
    tong_hop_bao_cao_dieu_hanh,
    xay_dung_danh_muc_theo_doi,
)

# ── UI constants ──
_EMOJI_STRIP = ("🟢", "🟡", "🔴", "⚪", "⚠️", "📝")

def _clean_trang_thai(val: str) -> str:
    """Bỏ emoji + badge cho PDF — thiếu file / trễ hạn."""
    if "⚠️" in str(val):
        return "Thiếu file"
    text = str(val)
    for ch in _EMOJI_STRIP:
        text = text.replace(ch, "")
    return text.replace("*", "").strip()

def _clear_export_cache():
    """Xóa bytes export cũ khi user đổi filter — tránh tải nhầm file."""
    for k in ["_don_doc_bytes", "_don_doc_ten",
              "_dd_pdf_bytes", "_dd_pdf_bytes__ten",
              "_dd_pdf_dv_bytes", "_dd_pdf_dv_bytes__ten"]:
        st.session_state.pop(k, None)


# ── GSheet data (cached wrapper) ────────────────────────────────────────────

@st.cache_data(ttl=300)
def _doc_du_lieu() -> pd.DataFrame:
    """Đọc dữ liệu GSheet có cache 5 phút — dùng trong UI."""
    return doc_du_lieu_gsheet()


def _fmt_pct_vn(rate: float) -> str:
    """Format tỷ lệ phần trăm theo kiểu VN."""
    try:
        return f"{rate * 100:.1f}".replace(".", ",") + "%"
    except Exception:
        return "0,0%"


def _chon_cot_chi_tiet(df: pd.DataFrame) -> pd.DataFrame:
    """Lấy các cột nghiệp vụ gọn để hiển thị/xuất báo cáo điều hành."""
    cols = [
        "Đơn vị",
        "Loại báo cáo",
        "Trạng thái",
        "Thời hạn",
        "Ngày nộp cuối",
        "Kỳ báo cáo",
        "Nguồn trạng thái",
        "Có file",
        "Quá hạn (ngày)",
        "Nhóm hành động",
        "Ghi chú",
    ]
    cols = [c for c in cols if c in df.columns]
    return df[cols].copy()


def _render_bao_cao_dieu_hanh(bao_cao: dict) -> None:
    """Khối báo cáo điều hành gọn cho tab Tổng quan."""
    df_chi_tiet = bao_cao.get("df_chi_tiet", pd.DataFrame())
    metrics = bao_cao.get("metrics", {})
    if df_chi_tiet.empty:
        st.info("Chưa có danh mục deadline để tổng hợp báo cáo điều hành.")
        return

    st.markdown("### 📌 Báo cáo điều hành")
    st.caption(
        f"Phạm vi theo dõi: **{metrics.get('tong_don_vi', 0)} đơn vị** × "
        f"**{metrics.get('tong_loai', 0)} loại báo cáo** = "
        f"**{metrics.get('tong_nghia_vu', 0)} nghĩa vụ**"
    )

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Tỷ lệ hoàn thành", _fmt_pct_vn(metrics.get("ty_le_hoan_thanh", 0.0)))
    c2.metric("Đơn vị hoàn thành 100%", metrics.get("so_don_vi_hoan_thanh_100", 0))
    c3.metric("Đơn vị còn thiếu", metrics.get("so_don_vi_con_thieu", 0))
    c4.metric("Quá hạn chưa nộp", metrics.get("so_qua_han_chua_nop", 0))
    c5.metric("Sắp đến hạn ≤ 3 ngày", metrics.get("so_sap_den_han", 0))

    for nhan_dinh in bao_cao.get("nhan_dinh", []):
        st.write(f"- {nhan_dinh}")

    tab_dv, tab_loai, tab_xuly = st.tabs(
        ["🏢 Đơn vị cần đôn đốc", "🗂 Loại báo cáo trọng điểm", "📌 Cần xử lý hôm nay"]
    )

    with tab_dv:
        df_dv = bao_cao.get("df_top_don_vi", pd.DataFrame()).head(10).copy()
        if df_dv.empty:
            st.info("Không có đơn vị nào cần đôn đốc.")
        else:
            df_dv["ty_le_hoan_thanh"] = df_dv["ty_le_hoan_thanh"].apply(_fmt_pct_vn)
            df_dv = df_dv.rename(
                columns={
                    "chua_hoan_thanh": "Cần xử lý",
                    "tre_han": "Đã nộp trễ",
                    "thieu_file": "Thiếu file",
                    "qua_han_max": "Quá hạn max (ngày)",
                    "ty_le_hoan_thanh": "Tỷ lệ hoàn thành",
                    "tong_nghia_vu": "Tổng nghĩa vụ",
                }
            )
            st.dataframe(
                df_dv[
                    [
                        "Đơn vị",
                        "Tổng nghĩa vụ",
                        "Cần xử lý",
                        "Đã nộp trễ",
                        "Thiếu file",
                        "Quá hạn max (ngày)",
                        "Tỷ lệ hoàn thành",
                    ]
                ],
                hide_index=True,
                use_container_width=True,
            )

    with tab_loai:
        df_loai = bao_cao.get("df_top_loai", pd.DataFrame()).head(10).copy()
        if df_loai.empty:
            st.info("Không có loại báo cáo nào cần lưu ý.")
        else:
            df_loai["ty_le_hoan_thanh"] = df_loai["ty_le_hoan_thanh"].apply(_fmt_pct_vn)
            df_loai = df_loai.rename(
                columns={
                    "chua_hoan_thanh": "Cần xử lý",
                    "tre_han": "Đã nộp trễ",
                    "thieu_file": "Thiếu file",
                    "qua_han_max": "Quá hạn max (ngày)",
                    "ty_le_hoan_thanh": "Tỷ lệ hoàn thành",
                    "tong_nghia_vu": "Tổng nghĩa vụ",
                }
            )
            st.dataframe(
                df_loai[
                    [
                        "Loại báo cáo",
                        "Tổng nghĩa vụ",
                        "Cần xử lý",
                        "Đã nộp trễ",
                        "Thiếu file",
                        "Quá hạn max (ngày)",
                        "Tỷ lệ hoàn thành",
                    ]
                ],
                hide_index=True,
                use_container_width=True,
            )

    with tab_xuly:
        df_xu_ly = _chon_cot_chi_tiet(bao_cao.get("df_can_xu_ly", pd.DataFrame()).head(20))
        if df_xu_ly.empty:
            st.success("Không còn nghĩa vụ nào cần xử lý ngay.")
        else:
            st.dataframe(df_xu_ly, hide_index=True, use_container_width=True)


# ── Tab 1: Tổng quan ──────────────────────────────────────────────────────────

def _render_tong_quan(
    df: pd.DataFrame,
    deadline_cfg: dict,
    is_cn: bool,
    pgd_user: str | None,
    username: str,
    can_config: bool,
    bao_cao_tien_do: dict,
) -> None:
    if df.empty:
        st.info("Chưa có dữ liệu từ Google Sheets.")
        return

    if not deadline_cfg:
        st.info("ℹ️ Chưa có thời hạn hoàn thành nào được cài đặt. Vào tab **⚙️ Cài đặt thời hạn** để thêm.")
        return

    ds_loai_gsheet_hint = sorted(df["loai_bao_cao"].dropna().unique().tolist()) if not df.empty else []
    dm = xay_dung_danh_muc_theo_doi(deadline_cfg, ds_loai_gsheet_hint)
    ds_loai = dm["display_keys"]
    ds_lech = phat_hien_ten_lech_ten(deadline_cfg, ds_loai_gsheet_hint)
    if ds_lech and can_config:
        n_co_goi_y = sum(1 for x in ds_lech if x.get("ten_form"))
        st.warning(
            f"⚠️ **{len(ds_lech)}** loại đang theo dõi chưa khớp tên Google Form"
            + (f" ({n_co_goi_y} có gợi ý liên kết)" if n_co_goi_y else "")
            + " — hệ thống đang tự ghép tạm theo tên Form khi đủ rõ, nhưng vẫn nên vào **⚙️ Cài đặt thời hạn** để **🔗 Liên kết**."
        )

    ds_pgd_scope = [pgd_user] if (not is_cn and pgd_user) else DS_PGD_ALL
    rows, metrics = tao_ma_tran_tien_do(df, deadline_cfg, ds_pgd_scope)
    dung_han = metrics["dung_han"]
    tre = metrics["tre"]
    chua_nop = metrics["chua_nop"]
    thieu_file = metrics.get("thieu_file", 0)
    da_nop = metrics["da_nop"]

    _render_bao_cao_dieu_hanh(bao_cao_tien_do)

    st.divider()
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Đã nộp (đơn vị × loại)", da_nop)
    c2.metric("🟢 Đúng hạn", dung_han)
    c3.metric("🟡 Trễ hạn", tre)
    c4.metric("⚠️ Thiếu file", thieu_file)
    c5.metric("🔴 Chưa nộp", chua_nop)

    st.markdown("**Ma trận trạng thái — PGD × Loại báo cáo**")
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
    st.caption("* Ghi đè thủ công  ·  📝 Có ghi chú")

    st.divider()
    st.markdown("### 📥 Xuất báo cáo điều hành")

    loai_xuat = st.radio(
        "Chọn loại danh sách để xuất",
        ["Tất cả", "Đã hoàn thành", "Chưa hoàn thành"],
        horizontal=True,
        key="tq_loai_xuat",
        on_change=_clear_export_cache,
    )

    if loai_xuat == "Tất cả":
        df_xuat_full = bao_cao_tien_do.get("df_chi_tiet", pd.DataFrame()).copy()
    elif loai_xuat == "Đã hoàn thành":
        df_xuat_full = bao_cao_tien_do.get("df_da_hoan_thanh", pd.DataFrame()).copy()
    else:
        df_xuat_full = bao_cao_tien_do.get("df_chua_hoan_thanh", pd.DataFrame()).copy()

    df_xuat_full = _chon_cot_chi_tiet(df_xuat_full)

    if df_xuat_full.empty:
        st.info(f"Không có báo cáo **{loai_xuat.lower()}**.")
    else:
        if loai_xuat == "Chưa hoàn thành":
            st.warning(f"⚠️ **{len(df_xuat_full)} báo cáo chưa hoàn thành**")
        else:
            st.caption(f"📋 {len(df_xuat_full)} báo cáo — **{loai_xuat}**")

        ds_pgd_thieu = ["Tất cả"] + sorted(df_xuat_full["Đơn vị"].unique().tolist())
        pgd_xuat = st.selectbox(
            "Lọc đơn vị trước khi xuất",
            ds_pgd_thieu,
            key="dd_pgd_xuat",
            on_change=_clear_export_cache,
        )
        df_xuat = df_xuat_full if pgd_xuat == "Tất cả" else df_xuat_full[df_xuat_full["Đơn vị"] == pgd_xuat]

        st.dataframe(df_xuat, hide_index=True, use_container_width=True)

        _slug_map = {"Tất cả": "tat_ca", "Đã hoàn thành": "da_hoan_thanh", "Chưa hoàn thành": "chua_hoan_thanh"}
        ten_file_goc = f"tien_do_{_slug_map.get(loai_xuat, 'xuat')}"
        username_xuat = st.session_state.get("username", "unknown")

        from pdf_service import xuat_pdf, xuat_pdf_group_header

        df_pdf_base = df_xuat.copy()
        if "Trạng thái" in df_pdf_base.columns:
            df_pdf_base["Trạng thái"] = df_pdf_base["Trạng thái"].apply(_clean_trang_thai)

        df_excel = df_xuat.copy()
        if "Trạng thái" in df_excel.columns:
            df_excel["Trạng thái"] = df_excel["Trạng thái"].apply(_clean_trang_thai)

        def _pdf_button(col, btn_label, btn_key, dl_key, file_name, generator_fn):
            """Helper dùng chung: nút generate → lưu session_state → nút download."""
            _ten_key = f"{dl_key}__ten"
            with col:
                if st.button(btn_label, key=btn_key, use_container_width=True, type="primary"):
                    try:
                        with st.spinner("Đang tạo PDF..."):
                            pdf_bytes = generator_fn()
                        st.session_state[dl_key] = pdf_bytes
                        st.session_state[_ten_key] = file_name
                    except Exception as e:
                        logger.error("%s: %s", btn_key, e, exc_info=True)
                        st.error(f"❌ Lỗi PDF: {e}")
                if st.session_state.get(dl_key):
                    st.download_button(
                        "⬇ Tải PDF",
                        data=st.session_state[dl_key],
                        file_name=st.session_state.get(_ten_key, file_name),
                        mime="application/pdf",
                        key=f"dl_{dl_key}",
                    )

        col_excel, col_pdf, col_pdf_dv, _ = st.columns([1, 1, 1.2, 3])

        with col_excel:
            if st.button("📥 Excel", key="btn_dd_excel", use_container_width=True, type="primary"):
                with st.spinner("Đang tạo Excel..."):
                    st.session_state["_don_doc_bytes"] = xuat_excel({f"Tiến độ — {loai_xuat}": df_excel})
                    st.session_state["_don_doc_ten"] = f"{ten_file_goc}.xlsx"
            if st.session_state.get("_don_doc_bytes"):
                st.download_button(
                    "⬇ Tải Excel",
                    data=st.session_state["_don_doc_bytes"],
                    file_name=st.session_state["_don_doc_ten"],
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="dl_don_doc",
                )

        _pdf_button(
            col=col_pdf,
            btn_label="📄 PDF",
            btn_key="btn_dd_pdf",
            dl_key="_dd_pdf_bytes",
            file_name=f"{ten_file_goc}.pdf",
            generator_fn=lambda: xuat_pdf(
                df_pdf_base,
                f"Tiến độ nộp báo cáo — {loai_xuat}",
                username_xuat,
                cols_tien=[],
                them_dong_tong=False,
            ),
        )

        _pdf_button(
            col=col_pdf_dv,
            btn_label="📊 PDF theo đơn vị",
            btn_key="btn_dd_pdf_dv",
            dl_key="_dd_pdf_dv_bytes",
            file_name=f"{ten_file_goc}_theo_don_vi.pdf",
            generator_fn=lambda: xuat_pdf_group_header(
                df_pdf_base,
                tieu_de=f"DANH SÁCH TIẾN ĐỘ NỘP BÁO CÁO — {loai_xuat.upper()}",
                nhom_theo="Đơn vị",
                nguoi_xuat=username_xuat,
                loai_van_ban="DANH SÁCH",
            ),
        )

    render_manual_override(df, ds_pgd_scope, ds_loai, username, can_config)


# ── Tab Hướng dẫn với Mockup ───────────────────────────────────────────────────

def _render_huong_dan_mockup() -> None:
    """Hiển thị hướng dẫn sử dụng và mockup luồng xử lý."""
    st.markdown("## 📖 Hướng dẫn sử dụng")
    
    col1, col2 = st.columns(2)
    with col1:
        st.info("""
        **👤 Dành cho PGD**
        
        1. Nhận **link Google Form** từ Phòng KH-NV
        2. Truy cập Form → điền đầy đủ thông tin
        3. Upload file báo cáo lên **Google Drive**
        4. **Set quyền "Anyone with the link can view"** cho file trên Drive
        5. Copy link Drive dán vào Form
        6. Bấm **"Gửi báo cáo"**
        7. Đợi ~5 phút, kiểm tra tab *Danh sách nộp*
        """)
    with col2:
        st.success("""
        **👔 Dành cho Phòng KH-NV**
        
        1. **Cài đặt thời hạn hoàn thành** trước mỗi kỳ báo cáo
        2. Theo dõi tiến độ qua tab *Tổng quan*
        3. Xem ma trận PGD × Loại báo cáo
        4. Danh sách 🔴 Chưa nộp tự động hiện
        5. Xuất Excel/PDF để **đôn đốc** các PGD
        6. Gọi điện/Zalo nhắc nhở đơn vị trễ hạn
        """)
    
    st.divider()
    st.markdown("### 🔄 Quy trình xử lý")
    
    # Flow diagram bằng HTML
    flow_html = """
    <div style="display: flex; align-items: center; justify-content: center; gap: 15px;
                flex-wrap: wrap; padding: 20px; background: var(--background-color, transparent);
                border: 1px solid var(--border-color, #ddd); border-radius: 12px;">
        <div style="text-align: center; padding: 15px; border: 1px solid var(--border-color, #ccc);
                    border-radius: 10px; min-width: 120px;">
            <div style="font-size: 32px;">📝</div>
            <div style="font-weight: 600; font-size: 13px; margin-top: 5px;">PGD nộp Form</div>
        </div>
        <div style="font-size: 24px;">→</div>
        <div style="text-align: center; padding: 15px; border: 1px solid var(--border-color, #ccc);
                    border-radius: 10px; min-width: 120px;">
            <div style="font-size: 32px;">📊</div>
            <div style="font-weight: 600; font-size: 13px; margin-top: 5px;">Lưu Sheets</div>
        </div>
        <div style="font-size: 24px;">→</div>
        <div style="text-align: center; padding: 15px; border: 1px solid var(--border-color, #ccc);
                    border-radius: 10px; min-width: 120px;">
            <div style="font-size: 32px;">⚙️</div>
            <div style="font-weight: 600; font-size: 13px; margin-top: 5px;">VBSP đọc (5 phút)</div>
        </div>
        <div style="font-size: 24px;">→</div>
        <div style="text-align: center; padding: 15px; border: 1px solid var(--border-color, #ccc);
                    border-radius: 10px; min-width: 120px;">
            <div style="font-size: 32px;">📈</div>
            <div style="font-weight: 600; font-size: 13px; margin-top: 5px;">KH-NV theo dõi</div>
        </div>
    </div>
    """
    st.html(flow_html)
    
    st.caption("💡 Dữ liệu từ Form → Sheets là **tức thời** | Sheets → VBSP-SCM có độ trễ **5 phút** (do cache)")
    
    st.divider()
    st.markdown("### 📋 Các trạng thái báo cáo")
    
    status_cols = st.columns(4)
    with status_cols[0]:
        st.metric("🟢 Đúng hạn", "Nộp ≤ thời hạn")
    with status_cols[1]:
        st.metric("🟡 Trễ hạn", "Nộp > thời hạn")
    with status_cols[2]:
        st.metric("🔴 Chưa nộp", "Quá hạn, chưa có data")
    with status_cols[3]:
        st.metric("⚪ Chưa nộp", "Chưa có thời hạn")
    
    st.divider()
    with st.expander("📊 Xem mockup chi tiết (Google Form mẫu)", expanded=False):
        try:
            mockup_path = Path(__file__).parent.parent / "docs" / "mockup_bc_tu_pgd.html"
            if mockup_path.exists():
                with open(mockup_path, "r", encoding="utf-8") as f:
                    mockup_content = f.read()
                # Chỉ lấy phần body và giới hạn chiều cao
                st.components.v1.html(
                    f'<div style="height: 600px; overflow-y: auto; border: 1px solid #ddd; border-radius: 8px;">{mockup_content}</div>',
                    height=620,
                    scrolling=True
                )
            else:
                st.info("File mockup chưa được tạo. Vui lòng kiểm tra docs/mockup_bc_tu_pgd.html")
        except Exception as e:
            logger.error("render mockup html: %s", e, exc_info=True)
            st.error(f"Không thể tải mockup: {e}")


# ── Entry point ───────────────────────────────────────────────────────────────

_CACHE_VER = "v2"

def render(tab: DeltaGenerator = None, **kwargs) -> None:
    role_raw = str(kwargs.get("role", "user") or "user")
    role_n = normalize_role(role_raw)
    is_cn = la_phan_he_cn(role_n)
    pgd_user = kwargs.get("pgd_user")
    username = kwargs.get("username", st.session_state.get("username", "unknown"))

    ctx = TabContext(tab, **kwargs)
    with ctx:
        ok, msg = kiem_tra_ket_noi_gsheet()
        if not ok:
            st.error(f"🔴 **GSheet lỗi:** {msg}")
        else:
            st.success(f"🟢 **GSheet OK** — {msg}")

        st.subheader("📋 Tiến độ Báo cáo của PGD")
        st.caption("Dữ liệu từ Google Form · Tự động cập nhật mỗi 5 phút")

        col_r, _ = st.columns([1, 7])
        with col_r:
            if st.button("🔄 Làm mới", key="tdn_refresh"):
                st.cache_data.clear()
                st.rerun()

        df = _doc_du_lieu()
        if df.empty:
            loi_gs = lay_loi_doc_gsheet_gan_nhat()
            if loi_gs:
                st.warning(f"⚠️ Không đọc được Google Sheets: {loi_gs}")
            else:
                st.warning("⚠️ Chưa có dữ liệu từ Google Sheets. Thử nhấn 🔄 Làm mới.")
        deadline_cfg = doc_deadline_config()
        archive_cfg = doc_luu_tru_config()
        deadline_cfg = loc_deadline_dang_hoat_dong(deadline_cfg, archive_cfg)

        # PGD role: chỉ thấy dữ liệu của PGD mình
        if not is_cn and pgd_user:
            df = df[df["ten_pgd"] == pgd_user]

        can_config = role_n in ("admin_cn", "manager_cn", "admin", "manager")
        df_hoat_dong = loc_du_lieu_luu_tru(df, archive_cfg, archived=False)
        ds_pgd_scope = [pgd_user] if (not is_cn and pgd_user) else DS_PGD_ALL
        bao_cao_tien_do = tong_hop_bao_cao_dieu_hanh(
            df_hoat_dong,
            deadline_cfg,
            ds_pgd_scope,
        )

        # Tab hướng dẫn hiển thị cho tất cả users
        if can_config:
            # Thứ tự tab theo quy trình vận hành trong hướng dẫn:
            # Bước 1: Cài đặt thời hạn → Bước 2: Tổng quan → Bước 4: Danh sách nộp
            t0, t1, t2, t3, t4 = st.tabs([
                "📖 Hướng dẫn PGD gửi BC về CN",
                "⚙️ Cài đặt thời hạn",
                "📊 Tổng quan",
                "📋 Danh sách nộp",
                "🗃️ Đã lưu trữ",
            ])
        else:
            t0, t2, t3, t4 = st.tabs([
                "📖 Hướng dẫn PGD gửi BC về CN",
                "📊 Tổng quan",
                "📋 Danh sách nộp",
                "🗃️ Đã lưu trữ",
            ])
            t1 = None

        with t0:
            _render_huong_dan_mockup()

        if t1 is not None:
            with t1:
                render_settings(df_hoat_dong, deadline_cfg, username)

        with t2:
            _render_tong_quan(
                df_hoat_dong,
                deadline_cfg,
                is_cn,
                pgd_user,
                username,
                can_config,
                bao_cao_tien_do,
            )

        with t3:
            render_submission_list(
                df_hoat_dong,
                deadline_cfg,
                is_cn,
                pgd_user,
                bao_cao_tien_do,
            )

        with t4:
            render_archive(df, archive_cfg, username, can_config)
