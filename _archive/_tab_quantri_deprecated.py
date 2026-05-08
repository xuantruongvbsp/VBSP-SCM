"""
Tab Quản lý Hệ thống — chỉ admin/manager
──────────────────────────────────────────
Chức năng:
  1. Upload file dữ liệu tập trung (HSTD, NQ11, Điện báo)
  2. Quản lý tài khoản người dùng
  3. Trạng thái hệ thống
"""
import os
import streamlit as st
from datetime import datetime

from config import BASE_DIR, THU_MUC_DATA, CACHE_DIR, FILE_USERS
from data import ts_file
from utils import fmt_so, vn, hien_thi_dataframe_phan_trang
from auth import la_phan_he_cn
from services import (
    kiem_tra_file_he_thong,
    luu_file_he_thong,
    FILES_HE_THONG,
    lay_meta_chat_luong,
)


def _trang_thai_file():
    """Hiển thị trạng thái từng file dữ liệu."""
    from data.pgd import lay_trang_thai_upload_pgd
    from config import DS_PGD, DON_VI_CHI_NHANH
    import pandas as pd

    # ── Phần 1: Trạng thái 22 đơn vị (nguồn chính) ─────────────────────────
    ds_don_vi = [DON_VI_CHI_NHANH] + DS_PGD
    st.markdown("**📋 Trạng thái upload — 22 đơn vị (nguồn chính)**")
    df_tt = lay_trang_thai_upload_pgd(ds_don_vi)

    def style_tt(val):
        v = str(val)
        if v.startswith("✅"):
            return "background-color:#d4edda;color:#155724"
        if v.startswith("⚠️"):
            return "background-color:#fff3cd;color:#856404"
        if v.startswith("❌"):
            return "background-color:#f8d7da;color:#721c24"
        return ""

    cols_loai = ["HSTD", "NQ11", "GQVL", "CDTOTKVV"]
    hien_thi_dataframe_phan_trang(
        df_tt.style.map(style_tt, subset=cols_loai),
        key="quantri_dep_tt_upload",
        height=400,
    )

    # ── Phần 2: File hệ thống gốc (nguồn dự phòng) ─────────────────────────
    with st.expander("📂 File hệ thống gốc (dự phòng)", expanded=False):
        st.caption(
            "Các file này chỉ dùng khi chưa có đủ dữ liệu từ 22 đơn vị. "
            "Hệ thống ưu tiên dùng dữ liệu từ pgd_data/ trước."
        )

        rows = []
        for ten, info in FILES_HE_THONG.items():
            path = info["path"]
            if os.path.exists(path):
                ngay = datetime.fromtimestamp(ts_file(path))
                mb = os.path.getsize(path) / 1024 / 1024
                con_han = (datetime.today() - ngay).days
                icon = "✅" if con_han == 0 else ("⚠️" if con_han <= 3 else "🔴")
                trang_thai = "Hôm nay" if con_han == 0 else f"{con_han} ngày trước"
                rows.append({
                    "File": ten,
                    "Mô tả": info["mo_ta"],
                    "Cập nhật": ngay.strftime("%d/%m/%Y %H:%M"),
                    "Tình trạng": f"{icon} {trang_thai}",
                    "Dung lượng": f"{mb:.1f} MB",
                })
            else:
                rows.append({
                    "File": ten,
                    "Mô tả": info["mo_ta"],
                    "Cập nhật": "—",
                    "Tình trạng": "❌ Chưa có file",
                    "Dung lượng": "—",
                })

        hien_thi_dataframe_phan_trang(
            pd.DataFrame(rows),
            key="quantri_dep_files_he_thong",
        )


def _trang_thai_he_thong():
    """Thống kê nhanh hệ thống."""
    st.markdown("**⚙️ Thông tin hệ thống**")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Thư mục gốc", str(BASE_DIR.name))
    # Dung lượng thư mục data/
    size_data = sum(
        os.path.getsize(os.path.join(dp, f))
        for dp, _, fs in os.walk(str(THU_MUC_DATA))
        for f in fs
    ) / 1024 / 1024
    c2.metric("Thư mục data/", f"{size_data:.1f} MB")
    # Dung lượng cache
    size_cache = sum(
        os.path.getsize(os.path.join(dp, f))
        for dp, _, fs in os.walk(str(CACHE_DIR))
        for f in fs
    ) / 1024 / 1024 if CACHE_DIR.exists() else 0
    c3.metric("Cache", f"{size_cache:.1f} MB")
    # Số user
    import db
    try:
        with db.get_conn() as conn:
            n_users = conn.execute(
                "SELECT COUNT(*) FROM users"
            ).fetchone()[0]
    except Exception:
        n_users = 0
    c4.metric("Tài khoản", f"{n_users}")


def _bao_cao_chat_luong_du_lieu() -> None:
    """Hiển thị báo cáo chất lượng dữ liệu lần merge gần nhất."""
    st.markdown("**🧪 Báo cáo chất lượng dữ liệu**")
    rows: list[dict] = []
    for loai in ("hstd", "nq11", "gqvl"):
        meta = lay_meta_chat_luong(loai) or {}
        if not meta:
            rows.append(
                {
                    "Loại": loai.upper(),
                    "Thời gian": "—",
                    "Tổng dòng": 0,
                    "Tổng lỗi": 0,
                    "Đánh giá": "Chưa có dữ liệu",
                }
            )
            continue
        tong_loi = int(meta.get("tong_so_loi", 0))
        tong_dong = int(meta.get("tong_dong", 0))
        tg = str(meta.get("thoi_gian", "—"))[:19].replace("T", " ")
        danh_gia = "Đạt" if tong_loi == 0 else ("Cần rà soát" if tong_loi < 10 else "Rủi ro cao")
        rows.append(
            {
                "Loại": loai.upper(),
                "Thời gian": tg,
                "Tổng dòng": fmt_so(tong_dong),
                "Tổng lỗi": tong_loi,
                "Đánh giá": danh_gia,
            }
        )
    import pandas as pd
    hien_thi_dataframe_phan_trang(
        pd.DataFrame(rows),
        key="quantri_dep_chat_luong",
    )


def _render_baseline_upload():
    from config import baseline_path, baseline_cache, danh_sach_nam_baseline

    st.subheader("📁 Quản lý Dữ liệu mốc 31/12")
    st.caption("Upload file HSTD ngày 31/12 theo từng năm — lưu vĩnh viễn, "
               "dùng làm mốc so sánh tăng trưởng toàn hệ thống.")

    # Danh sách năm đã có
    ds_nam = danh_sach_nam_baseline()
    if ds_nam:
        st.success(f"✅ Đã có mốc: {', '.join(str(n) for n in ds_nam)}")
    else:
        st.info("Chưa có file mốc nào.")

    st.divider()

    # Upload file mới
    nam_upload = st.number_input("Năm mốc", min_value=2020,
                                  max_value=2030,
                                  value=2025, step=1,
                                  key="baseline_nam")
    f = st.file_uploader(f"File HSTD_3112_{nam_upload}.XLSX",
                          type=["xlsx","XLSX"], key="baseline_file")
    if f and st.button("💾 Lưu mốc", type="primary", key="baseline_save"):
        fp = baseline_path(int(nam_upload))
        cp = baseline_cache(int(nam_upload))
        try:
            with open(fp, "wb") as out:
                out.write(f.read())
            # Xóa cache cũ nếu có
            if os.path.exists(cp):
                os.remove(cp)
            st.cache_data.clear()
            username = st.session_state.get("username", "unknown")
            import db
            db.ghi_audit(username, "upload_baseline",
                         f"HSTD mốc 31/12/{int(nam_upload)}")
            st.success(f"✅ Đã lưu mốc 31/12/{int(nam_upload)}")
            st.rerun()
        except Exception as e:
            st.error(f"❌ Lỗi: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

def render(tab, **kwargs):
    role     = kwargs.get("role")
    username = kwargs.get("username")
    df_full  = kwargs.get("df_full")

    with tab:
        # Chỉ admin/manager được vào
        if not la_phan_he_cn(role) or role == "executive":
            st.error("🔒 Bạn không có quyền truy cập trang này.")
            return

        if role in ("admin", "manager", "admin_cn", "manager_cn"):
            tab_chinh, tab_baseline = st.tabs([
                "⚙️ Upload & hệ thống",
                "📁 Dữ liệu mốc 31/12",
            ])
            with tab_chinh:
                st.subheader("⚙️ Quản lý Hệ thống")
                st.caption(f"Đường dẫn gốc: `{BASE_DIR}`")

                # ── Trạng thái tổng quan ──────────────────────────────────────────
                _trang_thai_he_thong()
                st.divider()
                _trang_thai_file()
                st.divider()
                _bao_cao_chat_luong_du_lieu()
                st.divider()

                # ── Upload file dữ liệu ───────────────────────────────────────────
                st.markdown("**📤 Upload file dữ liệu**")
                st.caption(
                    "Kéo thả hoặc chọn file · Hệ thống tự động lưu đè và làm mới "
                    "cache cho tất cả người dùng ngay lập tức"
                )

                # Hiển thị tên file hợp lệ để người dùng biết
                with st.expander("📋 Tên file hợp lệ"):
                    for ten, info in FILES_HE_THONG.items():
                        st.caption(f"• `{ten}` — {info['mo_ta']}")

                # Upload widget — hỗ trợ nhiều file cùng lúc
                files_up = st.file_uploader(
                    "Chọn file Excel",
                    type=["xlsx", "xls"],
                    accept_multiple_files=True,
                    key="qt_upload",
                    help="Tên file phải khớp chính xác với danh sách trên",
                )

                if files_up:
                    st.markdown(f"**{len(files_up)} file được chọn:**")
                    ket_qua = []

                    for f_up in files_up:
                        ten_file   = f_up.name
                        file_bytes = f_up.read()

                        ok, msg = kiem_tra_file_he_thong(ten_file, file_bytes)
                        if not ok:
                            ket_qua.append(("❌", ten_file, msg))
                        else:
                            ket_qua.append(("✅", ten_file, "Sẵn sàng lưu"))

                    # Hiển thị kết quả kiểm tra
                    for icon, ten, msg in ket_qua:
                        st.caption(f"{icon} `{ten}` — {msg}")

                    co_loi = any(r[0] == "❌" for r in ket_qua)

                    if not co_loi:
                        if st.button("💾 Lưu tất cả file",
                                     type="primary", key="qt_btn_luu"):
                            for f_up in files_up:
                                f_up.seek(0)
                                kq = luu_file_he_thong(f_up.name, f_up.read())
                                kq.hien_thi()
                            st.info("🔄 Dữ liệu mới đã sẵn sàng cho toàn bộ người dùng.")
                            st.rerun()
                    else:
                        st.warning("⚠️ Sửa lỗi trên trước khi lưu.")

                st.divider()

                # ── Xóa cache thủ công ────────────────────────────────────────────
                st.markdown("**🗑️ Xóa cache thủ công**")
                st.caption("Dùng khi cần làm mới dữ liệu mà không upload file mới")
                if st.button("🔄 Xóa toàn bộ cache", key="qt_xoa_cache"):
                    st.cache_data.clear()
                    # Xóa file parquet cache
                    for f in CACHE_DIR.glob("*.parquet"):
                        f.unlink()
                    st.success("✅ Đã xóa cache — tất cả user sẽ thấy dữ liệu mới nhất.")

                st.divider()

                # ── Cấu hình Điểm Giao dịch (admin/manager) ──────────────────────────
                if role in ("admin", "manager", "admin_cn", "manager_cn"):
                    _render_cau_hinh_dgd(username, df_full)
                    st.divider()

                # ── Quản lý người dùng (chỉ admin) ───────────────────────────────
                if role == "admin":
                    st.markdown("**👥 Quản lý người dùng**")
                    from auth import doc_users
                    users = doc_users()
                    if users:
                        import pandas as pd
                        rows_u = [{
                            "Tên đăng nhập": u,
                            "Họ tên": info["ho_ten"],
                            "Quyền": {"admin":"⭐ Admin","manager":"🔑 Manager",
                                       "user":"👤 Nhân viên"}.get(info["role"], info["role"]),
                            "PGD": info.get("pgd") or "Tất cả",
                            "Ngày tạo": info.get("ngay_tao", "—"),
                        } for u, info in users.items()]
                        hien_thi_dataframe_phan_trang(
                            pd.DataFrame(rows_u),
                            key="quantri_dep_users",
                        )
                        st.caption(f"Tổng: **{len(users)}** tài khoản · "
                                   f"Quản lý chi tiết tại tab 👥 trong phân hệ Điều hành")

            with tab_baseline:
                _render_baseline_upload()


def _render_cau_hinh_dgd(username: str, df_full) -> None:
    """Render giao diện kiểm tra coverage Điểm giao dịch cho admin/manager (chỉ xem)."""
    from config import DS_PGD
    import db
    import pandas as pd
    
    st.markdown("**🗺️ Kiểm tra Coverage Điểm Giao dịch**")
    st.caption("Theo dõi trạng thái phân bổ thôn/ấp vào điểm giao dịch (chỉ xem)")
    
    if df_full is None or df_full.empty:
        st.warning("⚠️ Chưa có dữ liệu HSTD. Cần upload HSTD để kiểm tra coverage.")
        return
    
    if "Tên PGD" not in df_full.columns or "Tên thôn" not in df_full.columns or "Tên xã" not in df_full.columns:
        st.warning("⚠️ Dữ liệu HSTD thiếu cột 'Tên PGD', 'Tên xã' hoặc 'Tên thôn'.")
        return
    
    # Chọn PGD để kiểm tra
    ds_pgd_co_data = sorted(df_full["Tên PGD"].dropna().unique().tolist())
    if not ds_pgd_co_data:
        st.warning("Không có dữ liệu PGD trong HSTD.")
        return
    
    st_pgd_check = st.selectbox("Chọn PGD để kiểm tra", ds_pgd_co_data, key="dgd_check_pgd")
    
    # Lọc dữ liệu theo PGD
    df_pgd = df_full[df_full["Tên PGD"] == st_pgd_check].copy()
    
    # Lấy tất cả thôn/ấp của PGD này
    ds_thon_pgd = df_pgd.groupby(["Tên xã", "Tên thôn"]).size().reset_index(name="So_ho")
    
    if ds_thon_pgd.empty:
        st.warning(f"PGD {st_pgd_check} không có dữ liệu thôn/ấp.")
        return
    
    # Đọc mapping hiện tại
    dgd_map = db.doc_dgd_map()
    
    # Tạo reverse mapping: thôn → điểm GD
    thon_to_dgd = {}
    if st_pgd_check in dgd_map:
        for xa, dgd_dict in dgd_map[st_pgd_check].items():
            for ten_dgd, ds_thon in dgd_dict.items():
                for thon in ds_thon:
                    thon_to_dgd[f"{xa}|{thon}"] = ten_dgd
    
    # Tạo bảng kiểm tra coverage
    rows_coverage = []
    for _, row in ds_thon_pgd.iterrows():
        xa = row["Tên xã"]
        thon = row["Tên thôn"]
        so_ho = row["So_ho"]
        
        key_thon = f"{xa}|{thon}"
        if key_thon in thon_to_dgd:
            dgd_gan = thon_to_dgd[key_thon]
            trang_thai = "✅ Đã gán"
        else:
            dgd_gan = "—"
            trang_thai = "⚠️ Chưa gán"
        
        rows_coverage.append({
            "Xã": xa,
            "Tên thôn": thon,
            "Số hộ": so_ho,
            "Điểm GD đã gán": dgd_gan,
            "Trạng thái": trang_thai,
        })
    
    # KPI nhanh
    tong_thon = len(rows_coverage)
    da_gan = sum(1 for r in rows_coverage if r["Trạng thái"].startswith("✅"))
    chua_gan = tong_thon - da_gan
    
    kpi1, kpi2, kpi3 = st.columns(3)
    kpi1.metric("Tổng thôn/ấp", f"{tong_thon}")
    kpi2.metric("Đã gán", f"{da_gan}", delta=f"{da_gan/tong_thon*100:.1f}%" if tong_thon > 0 else "0%")
    kpi3.metric("Chưa gán", f"{chua_gan}", 
                delta=f"{chua_gan/tong_thon*100:.1f}%" if tong_thon > 0 else "0%",
                delta_color="inverse" if chua_gan > 0 else "off")
    
    # Hiển thị bảng
    st.markdown("**📋 Trạng thái coverage theo thôn/ấp**")
    df_coverage = pd.DataFrame(rows_coverage)
    
    # Tô màu theo trạng thái
    def highlight_status(val):
        if "✅" in str(val):
            return 'background-color: #d4edda; color: #155724'  # Xanh lá nhạt
        elif "⚠️" in str(val):
            return 'background-color: #fff3cd; color: #856404'  # Vàng nhạt
        return ''
    
    styled_df = df_coverage.style.map(highlight_status, subset=['Trạng thái'])
    hien_thi_dataframe_phan_trang(styled_df, key="quantri_dep_dgd_coverage")
    
    # Thống kê tổng hợp
    if chua_gan > 0:
        st.warning(f"⚠️ Còn **{chua_gan}** thôn/ấp chưa được phân bổ vào điểm giao dịch.")
        st.caption("💡 CBTD cần vào **tab Báo cáo Giao ban** → **⚙️ Cấu hình điểm giao dịch** để thiết lập.")
    else:
        st.success(f"🎉 PGD **{st_pgd_check}** đã phân bổ đầy đủ tất cả thôn/ấp vào điểm giao dịch!")
    
    # Thống kê theo điểm GD (nếu có)
    if da_gan > 0:
        st.markdown("**📊 Thống kê theo Điểm Giao dịch**")
        dgd_stats = {}
        for row in rows_coverage:
            if row["Trạng thái"].startswith("✅"):
                dgd = row["Điểm GD đã gán"]
                if dgd not in dgd_stats:
                    dgd_stats[dgd] = {"thon": 0, "ho": 0}
                dgd_stats[dgd]["thon"] += 1
                dgd_stats[dgd]["ho"] += row["Số hộ"]
        
        rows_dgd_stats = []
        for dgd, stats in dgd_stats.items():
            rows_dgd_stats.append({
                "Điểm GD": dgd,
                "Số thôn": stats["thon"],
                "Số hộ": stats["ho"],
            })
        
        df_dgd_stats = pd.DataFrame(rows_dgd_stats)
        hien_thi_dataframe_phan_trang(df_dgd_stats, key="quantri_dep_dgd_stats")


# Thêm vào cuối file để import được gọi
if __name__ == "__main__":
    # Import cần thiết vào đây để tránh circular import
    pass
