"""
Không gian Điều hành (Management View)
───────────────────────────────────────
Dành cho Lãnh đạo phòng KH-NV — Giám sát NQH theo địa bàn,
quản lý chỉ tiêu, cân đối nguồn vốn.
"""
import os
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from config import (
    COT_TEN_PGD, COT_MA_KH, COT_SO_KU, COT_TEN_KH,
    COT_DU_NO_QH, COT_TONG_DU_NO, COT_DU_NO_TH, COT_TEN_CT,
    COT_NGAY_DH, COT_TINH_TRANG, COT_SDT,
    COT_LAI_TON, COT_LAI_THANG, COT_DVUT, COT_MUC_VAY,
    COT_NGAY_VAY, COT_THOI_HAN, COT_LAI_SUAT,
    TEMPLATES_DIR, TAG_MAP,
)
from auth import is_cn_role, is_pgd_role, get_permissions
from data import (
    danh_dau_khong_hd, tong_hop_khong_hd,
    ds_chi_tiet_khong_hd, canh_bao_migration,
)
from utils import (
    fmt,
    fmt_so,
    vn,
    xuat_excel,
    quet_templates,
    auto_fill_klgb,
    auto_fill_document,
    hien_thi_dataframe_phan_trang,
)
from tabs import (
    tab_tongquan, tab_baocao, tab_nq11,
    tab_candoi, tab_cbtd, tab_khtd, tab_kehoach,
    tab_nhiem_vu, tab_cdtotkvv, tab_khtd_giao_dc, tab_kiem_soat,
    tab_ban_dai_dien,
    tab_uy_thac,
)
from tabs import tab_upload_khnv
from tabs import tab_quan_ly_dgd


def _render_canh_bao(df: pd.DataFrame, ds_pgd_all: list):
    """
    Tab Cảnh báo sớm — Migration & 3 tháng không hoạt động.
    Hiển thị bảng Top đơn vị cần chấn chỉnh + xuất KL giao ban.
    """
    st.subheader("🚨 Cảnh báo sớm — Phân loại nợ & 3 tháng không HĐ")

    if df is None or df.empty:
        st.warning("Chưa có dữ liệu HSTD."); return

    # Đánh dấu 3 tháng không hoạt động
    df_kh = danh_dau_khong_hd(df)

    # ── KPI nhanh ──────────────────────────────────────────────────────────
    tong_mon    = len(df_kh)
    khd_tong    = int(df_kh["is_3m_inactive"].sum()) if "is_3m_inactive" in df_kh.columns else 0
    df_amber    = canh_bao_migration(df_kh)
    amber_tong  = len(df_amber)
    tl_khd      = khd_tong / tong_mon * 100 if tong_mon > 0 else 0

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Tổng món vay",              fmt_so(tong_mon))
    k2.metric("3 tháng không HĐ 🔴",       fmt_so(khd_tong),
              delta=f"{tl_khd:.1f}% tổng món",
              delta_color="inverse" if tl_khd > 2 else "off")
    k3.metric("Sắp chuyển 3 tháng KHĐ ⚠️", fmt_so(amber_tong),
              help="Lãi tồn 2–3 tháng, chưa đủ 3 tháng không hoạt động — cần đôn đốc ngay")
    tong_lai_khd = df_kh[df_kh.get("is_3m_inactive", False)][COT_LAI_TON].sum() \
                   if COT_LAI_TON in df_kh.columns else 0
    k4.metric("Lãi tồn 3m KHĐ (tr.đ)",    vn(tong_lai_khd/1e6, 1))

    st.divider()

    # ── Bảng Top đơn vị cần chấn chỉnh ───────────────────────────────────
    st.markdown("**📋 Tổng hợp theo PGD**")
    nhom_pgd = tong_hop_khong_hd(df_kh, nhom_theo=COT_TEN_PGD)
    if not nhom_pgd.empty:
        hien_thi_dataframe_phan_trang(
            nhom_pgd,
            key="mgmt_khd_nhom_pgd",
            height=300,
        )

    st.markdown("**📋 Tổng hợp theo Hội đoàn thể (ĐVUT)**")
    nhom_dvut = tong_hop_khong_hd(df_kh, nhom_theo="Tên ĐVUT")
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
                st.download_button(
                    f"⬇️ Tải KL giao ban — {pgd_kl}",
                    data=data, file_name=fname,
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    key="kl_dl",
                )
                st.success("✅ Đã tạo xong — nhấn nút trên để tải về.")
            except Exception as e:
                st.error(f"Lỗi tạo KL giao ban: {e}")


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
                        
                    except Exception as e:
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
                    except Exception as e:
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
                
            except Exception as e:
                st.error(f"❌ Lỗi test template: {e}")
                st.exception(e)  # Debug info


def render(**kwargs):
    _wl = st.session_state.pop("_data_load_warning", None)
    if _wl:
        st.warning(_wl)

    role       = kwargs.get("role")
    df         = kwargs.get("df")
    df_full    = kwargs.get("df_full", df)
    ds_pgd_all = kwargs.get("ds_pgd_all", [])

    st.title("📋 Phòng KH-NV")
    st.caption("Giám sát chỉ tiêu · Cân đối vốn · Quản lý NQH · GQVL · Quản lý CBTD")

    # Tạo danh sách tabs dựa trên role
    tab_names = [
        "📊 Tổng quan", "📈 Báo cáo chi tiết", "🔍 Kiểm soát CN",
        "🗓️ KH Tín dụng Năm",
        "📤 Giao KH theo Đợt",
        "📡 Điện Báo",
        "🎯 KH vs Thực hiện",
        "👔 Quản lý CBTD",
        "📍 Điểm GD & Tổ TK&VV",
        "🚨 Cảnh báo sớm",
        "✅ Nhiệm vụ",
        "🏛️ Ban Đại Diện",
        "🤝 Ủy thác",
    ]
    
    # Chỉ admin/manager mới thấy tab Quản lý Template
    if get_permissions(role)["can_upload"]:
        tab_names.extend(["📁 Quản lý Template", "📤 Upload KH-NV"])
    else:
        tab_names.append("📤 Upload KH-NV")

    tabs = st.tabs(tab_names)

    tab_tongquan.render(tabs[0], **kwargs)
    tab_baocao.render(tabs[1], **kwargs)
    with tabs[2]:
        tab_kiem_soat.render_tab(df_full, role, kwargs.get("username", "unknown"))
    tab_khtd.render(tabs[3], **dict(kwargs, khtd_mode="cn"))
    tab_khtd_giao_dc.render(tabs[4], **kwargs)
    tab_candoi.render(tabs[5], **kwargs)
    tab_kehoach.render(tabs[6], **kwargs)
    tab_cbtd.render(tabs[7], **kwargs)
    with tabs[8]:
        _sub1, _sub2 = st.tabs(["📍 Điểm Giao Dịch", "🏘️ Tổ TK&VV"])
        tab_quan_ly_dgd.render(_sub1, **kwargs)
        tab_cdtotkvv.render(_sub2, **dict(kwargs, cdto_mode="cn"))
    with tabs[9]:
        _render_canh_bao(df_full, ds_pgd_all)
    tab_nhiem_vu.render(tabs[10], **kwargs)
    tab_ban_dai_dien.render(tabs[11], cap="tinh", **kwargs)
    tab_uy_thac.render(tabs[12], **kwargs)
    if get_permissions(role)["can_upload"]:
        with tabs[13]:
            _render_quan_ly_template(df_full)
        tab_upload_khnv.render(tabs[14], **kwargs)
    else:
        tab_upload_khnv.render(tabs[13], **kwargs)