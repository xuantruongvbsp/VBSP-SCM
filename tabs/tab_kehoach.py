"""Tab Kế hoạch Chi nhánh vs Thực hiện"""


from logger import get_logger
logger = get_logger(__name__)

import streamlit as st
import pandas as pd
import plotly.express as px
from io import BytesIO
from datetime import datetime
import os

from config import *
from data import doc_dienbao, db_lookup, ts_file
from data.khtd import doc_kehoach, luu_kehoach
from data.pgd import duong_dan_pgd, pgd_slug
from services import kiem_tra_file
from auth import la_phan_he_cn, la_executive, normalize_role
from utils import (
    fmt,
    fmt_tien,
    fmt_ty,
    fmt_cl,
    fmt_pct,
    fmt_so,
    xuat_excel,
    hien_thi_dataframe_phan_trang,
)


from tabs.base_tab import TabContext


def render(tab, **kwargs):
    ctx = TabContext(tab, **kwargs)
    role      = ctx.role_norm
    pgd_user  = ctx.pgd_user
    pgd_mode  = kwargs.get("pgd_mode", False)
    if pgd_mode and not pgd_user:
        with ctx:
            st.error("Không xác định được PGD.")
        return
    # prefix duy nhất theo mode — tránh DuplicateElementKey khi render nhiều workspace
    prefix = (
        f"pgd_{pgd_slug(pgd_user)}_kh"
        if pgd_mode
        else kwargs.get("khtd_mode", kwargs.get("mode", "kh"))
    )

    with ctx:
        st.subheader("🎯 Kế hoạch Chi nhánh vs Thực hiện")
        st.caption("📌 So sánh kế hoạch nhập tay với số liệu Điện báo hiện tại")

        with st.expander("📖 Hướng dẫn Điện báo", expanded=False):
            from pathlib import Path

            path = Path(__file__).resolve().parent.parent / "docs" / "HUONG_DAN_DIEN_BAO.md"
            if path.exists():
                st.markdown(path.read_text(encoding="utf-8"))

        # ── Định dạng số ──────────────────────────────────────────────────
        def vn_kh(x, d=1):
            try:
                x = float(x)
                s = f"{x:,.{d}f}".replace(",","X").replace(".",",").replace("X",".")
                return s.rstrip("0").rstrip(",") if "," in s else s
            except: return "—"

        def fmt_kh(x):
            try:
                x = float(x)
                if abs(x) > 0:
                    trieu = x / 1_000_000
                    return f"{trieu:,.0f}".replace(",","X").replace(".",",").replace("X",".")
                return "—"
            except: return "—"

        # ── Đọc file Điện báo hiện tại (dùng cache đã upload ở tab Cân đối) ──
        if pgd_mode:
            path_ht = duong_dan_pgd(pgd_user, "dienbao_ht")
        else:
            path_dienbao_override = kwargs.get("path_dienbao_ht")
            if path_dienbao_override:
                path_ht = (
                    path_dienbao_override
                    if os.path.exists(path_dienbao_override)
                    else None
                )
            else:
                path_ht = DB_HT_CACHE if os.path.exists(DB_HT_CACHE) else FILE_PATH_DB
        db_ht_rows = None
        if path_ht and os.path.exists(path_ht):
            try:
                db_ht_rows = doc_dienbao(path_ht, ts_file(path_ht))
            except Exception as e:
                logger.error("Lỗi trong khối except: %s", e, exc_info=True)
                st.error(f"Lỗi đọc file Điện báo: {e}")

        if db_ht_rows is None:
            if pgd_mode:
                st.warning(
                    "Vui lòng upload Điện báo PGD ở cuối trang tab Điện Báo trước"
                )
            else:
                st.warning("⚠️ Chưa có file Điện báo hiện tại.")
                st.info(
                    "Vui lòng upload file Điện báo ở cuối trang (mục Upload) trước."
                )
            st.stop()

        # Lấy danh sách chỉ tiêu (bỏ dòng NQH con)
        ds_chi_tieu = [r["ten"] for r in db_ht_rows if not r["la_nqh_con"]]

        # ── Đọc kế hoạch đã lưu ──────────────────────────────────────────
        kh_data = doc_kehoach(ten_pgd=pgd_user if pgd_mode else None)

        # ── Upload / Nhập kế hoạch ────────────────────────────────────────
        col_up, col_nhap = st.columns(2)

        with col_up:
            st.markdown("**📤 Upload file kế hoạch Excel**")
            if not la_phan_he_cn(role) or la_executive(role):
                st.info("Chỉ Quản lý trở lên mới upload được.")
            else:
                st.caption("Cấu trúc: Cột A = Tên chỉ tiêu, Cột B = Giá trị (đồng)")
                f_kh = st.file_uploader("Chọn file Excel kế hoạch",
                                        type=["xlsx","xls"], key=f"{prefix}_upload_kh")
                if f_kh:
                    file_bytes = f_kh.read()
                    ok, msg = kiem_tra_file(f_kh.name, file_bytes)
                    if not ok:
                        st.error(msg)
                    else:
                        try:
                            df_up = pd.read_excel(BytesIO(file_bytes), header=None)
                            new_kh = {}
                            for _, row in df_up.iterrows():
                                ten = str(row.iloc[0]).strip()
                                val_raw = row.iloc[1]
                                if ten in ("", "nan", "Chỉ tiêu"): continue
                                try:
                                    new_kh[ten] = float(val_raw) if pd.notna(val_raw) else 0.0
                                except:
                                    new_kh[ten] = 0.0
                            luu_kehoach(
                                new_kh,
                                ten_pgd=pgd_user if pgd_mode else None,
                            )
                            kh_data = new_kh
                            st.success(f"✅ Đã tải {len(new_kh)} chỉ tiêu kế hoạch!")
                        except Exception as e:
                            logger.error("Lỗi trong khối except: %s", e, exc_info=True)
                            st.error(f"Lỗi đọc file: {e}")

        with col_nhap:
            st.markdown("**✏️ Nhập kế hoạch thủ công**")
            if not la_phan_he_cn(role) or la_executive(role):
                st.caption("Chỉ Quản lý trở lên mới nhập được.")
            else:
                with st.form(f"nhap_kh_{prefix}"):
                    chon_ct = st.selectbox("Chọn chỉ tiêu", ds_chi_tieu, key=f"{prefix}_kh_ct")
                    val_kh  = st.number_input("Giá trị kế hoạch (đồng)",
                                              min_value=0.0, step=1e8,
                                              format="%.0f")
                    if st.form_submit_button("💾 Lưu", type="primary"):
                        kh_data[chon_ct] = val_kh
                        luu_kehoach(
                            kh_data,
                            ten_pgd=pgd_user if pgd_mode else None,
                        )
                        st.success(f"✅ Đã lưu: {chon_ct}")
                        st.rerun()

        # Tải file mẫu
        st.divider()
        if st.button("⬇ Tải file mẫu kế hoạch Excel", key=f"{prefix}_btn_mau_kh"):
            buf = BytesIO()
            rows_mau = [{"Chỉ tiêu": ten, "Kế hoạch (đồng)": 0}
                        for ten in ds_chi_tieu]
            with pd.ExcelWriter(buf, engine="openpyxl") as w:
                pd.DataFrame(rows_mau).to_excel(w, index=False, sheet_name="Ke hoach")
            st.session_state[f"_bytes_{prefix}_mau_kh"] = buf.getvalue()
            st.session_state[f"_file_{prefix}_mau_kh"] = "mau_ke_hoach.xlsx"

        if st.session_state.get(f"_bytes_{prefix}_mau_kh"):
            st.download_button("⬇ Tải ngay",
                data=st.session_state[f"_bytes_{prefix}_mau_kh"],
                file_name=st.session_state[f"_file_{prefix}_mau_kh"],
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key=f"{prefix}_dl_mau_kh")

        st.divider()

        # ── Bảng so sánh KH vs TH ─────────────────────────────────────────
        if not kh_data:
            st.info("📝 Chưa có kế hoạch. Upload file hoặc nhập thủ công ở trên.")
            return

        st.markdown("**📊 Bảng so sánh Kế hoạch vs Thực hiện**")

        rows_ss = []
        for r in db_ht_rows:
            if r["la_nqh_con"]: continue
            ten = r["ten"]
            th  = r["val"]                          # thực hiện từ Điện báo
            kh  = kh_data.get(ten, 0)               # kế hoạch đã nhập
            con_lai = kh - th
            tl  = (th / kh * 100) if kh > 0 else None
            rows_ss.append({
                "Chỉ tiêu":  ten,
                "Kế hoạch":  fmt_kh(kh),
                "Thực hiện": fmt_kh(th),
                "Còn lại":   fmt_kh(con_lai) if kh > 0 else "—",
                "Tỷ lệ %":   f"{vn_kh(tl,1)}%" if tl is not None else "—",
                "_tl": tl or 0,
                "_kh": kh,
                "_th": th,
                "_cl": con_lai,
            })

        df_ss = pd.DataFrame(rows_ss)
        if df_ss.empty:
            st.info("📝 Không có dữ liệu để hiển thị.")
            return

        # Metrics tóm tắt
        if "_kh" in df_ss.columns:
            co_kh = df_ss[df_ss["_kh"] > 0]
            if len(co_kh):
                avg_tl = co_kh["_tl"].mean()
                dat_kh = len(co_kh[co_kh["_tl"] >= 100])
                chua   = len(co_kh[co_kh["_tl"] < 100])
                s1, s2, s3 = st.columns(3)
                s1.metric("Tỷ lệ TH bình quân",    f"{vn_kh(avg_tl,1)}%")
                s2.metric("Chỉ tiêu đạt KH (≥100%)", str(dat_kh))
                s3.metric("Chỉ tiêu chưa đạt",       str(chua))

        cols_hien = ["Chỉ tiêu", "Kế hoạch", "Thực hiện", "Còn lại", "Tỷ lệ %"]
        hien_thi_dataframe_phan_trang(
            df_ss[cols_hien],
            key=f"{prefix}_kehoach_ss_chitieu",
            height=450,
        )

        # Biểu đồ top 10 chưa đạt
        chua_dat = pd.DataFrame()
        if "_kh" in df_ss.columns and "_tl" in df_ss.columns:
            chua_dat = df_ss[(df_ss["_kh"] > 0) & (df_ss["_tl"] < 100)].nsmallest(10, "_tl")
        if len(chua_dat):
            st.divider()
            st.markdown("**📉 Top 10 chỉ tiêu thực hiện thấp nhất**")
            fig = px.bar(chua_dat, x="_tl", y="Chỉ tiêu",
                orientation="h", text="Tỷ lệ %",
                color="_tl", color_continuous_scale="RdYlGn", range_color=[0, 100])
            fig.update_traces(textposition="outside")
            fig.update_layout(
                height=350, margin=dict(l=0,r=40,t=10,b=10),
                xaxis=dict(title="Tỷ lệ thực hiện (%)", range=[0, 120]),
                yaxis=dict(title="", autorange="reversed"),
                coloraxis_showscale=False,
                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            )
            st.plotly_chart(fig, use_container_width=True)

        # Xuất Excel
        st.divider()
        if st.button("📥 Xuất báo cáo KH vs TH", key=f"{prefix}_btn_xuat_khvsth"):
            buf = BytesIO()
            rows_ex = [{"Chỉ tiêu": r["Chỉ tiêu"],
                        "Kế hoạch (đồng)":  df_ss.loc[i, "_kh"],
                        "Thực hiện (đồng)": df_ss.loc[i, "_th"],
                        "Chênh lệch":       df_ss.loc[i, "_cl"],
                        "Tỷ lệ %":          round(df_ss.loc[i, "_tl"], 2)}
                       for i, r in df_ss.iterrows()]
            with pd.ExcelWriter(buf, engine="openpyxl") as w:
                pd.DataFrame(rows_ex).to_excel(w, index=False, sheet_name="KH vs TH")
            st.session_state[f"_bytes_{prefix}_khvsth"] = buf.getvalue()
            st.session_state[f"_file_{prefix}_khvsth"] = f"KHvsTH_{datetime.today().strftime('%d%m%Y')}.xlsx"

        if st.session_state.get(f"_bytes_{prefix}_khvsth"):
            st.download_button("⬇ Tải báo cáo",
                data=st.session_state[f"_bytes_{prefix}_khvsth"],
                file_name=st.session_state[f"_file_{prefix}_khvsth"],
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key=f"{prefix}_dl_khvsth")
