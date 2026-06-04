"""Tab Báo cáo KHNV — Số liệu & Xuất báo cáo cho phòng KH-NV.

Tích hợp 3 chế độ:
- 📊 HSTD:     Tổng hợp từ dữ liệu chi tiết
- 📡 Điện báo: Số liệu từ file Điện báo CN
- 🔄 So sánh:  Đối chiếu HSTD vs Điện báo
- 📥 Xuất:     Excel / Word
"""
from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

import streamlit as st
import pandas as pd

from logger import get_logger
from services.khnv_bao_cao_service import (
    tong_hop_so_lieu_thang,
    tong_hop_tu_dienbao,
    so_sanh_hstd_vs_dienbao,
    lay_danh_sach_mau,
    doc_noi_dung_mau,
    xuat_excel_bao_cao_khnv,
    xuat_word_bao_cao_khnv,
)
from components.delta_card import kpi_row
from config import DB_HT_CACHE, FILE_PATH_DB
import os

if TYPE_CHECKING:
    from streamlit.delta_generator import DeltaGenerator

logger = get_logger(__name__)


def render(tab: DeltaGenerator | None = None, **kwargs) -> None:
    ctx = tab if tab is not None else st.container()

    df_full = kwargs.get("df_full")
    if df_full is None:
        df_full = kwargs.get("df")
    role = kwargs.get("role", "")
    username = kwargs.get("username", "unknown")

    with ctx:
        st.subheader("📄 Báo cáo KHNV")
        st.caption("Tổng hợp số liệu & xuất báo cáo — HSTD + Điện báo")

        st.markdown("---")

        col1, col2 = st.columns(2)
        with col1:
            thang = st.selectbox("Tháng", list(range(1, 13)), index=date.today().month - 1, key="khnv_bc_thang")
        with col2:
            nam = st.selectbox("Năm", list(range(2024, 2031)), index=1, key="khnv_bc_nam")

        # ── Chọn nguồn dữ liệu ──
        st.markdown("---")
        nguon = st.radio(
            "📡 Nguồn dữ liệu:",
            ["📊 HSTD (dữ liệu chi tiết)", "📡 Điện báo (file tổng hợp CN)", "🔄 So sánh HSTD vs Điện báo"],
            horizontal=True,
            key="khnv_bc_nguon",
        )

        st.markdown("---")

        # ── Tổng hợp số liệu ──
        so_lieu = {}
        so_lieu_db = {}
        chenh_lech = []

        if nguon == "📊 HSTD (dữ liệu chi tiết)":
            if df_full is None or df_full.empty:
                st.warning("⚠️ Chưa có dữ liệu HSTD. Vui lòng upload dữ liệu trước.")
                return
            so_lieu = tong_hop_so_lieu_thang(df_full, thang=thang, nam=nam)

        elif nguon == "📡 Điện báo (file tổng hợp CN)":
            fp_db = DB_HT_CACHE if os.path.exists(DB_HT_CACHE) else (
                FILE_PATH_DB if os.path.exists(FILE_PATH_DB) else None
            )
            if not fp_db:
                st.warning("⚠️ Chưa có file Điện báo. Vui lòng upload tại tab 📡 Điện Báo.")
                st.info("Vào workspace Phòng KH-NV → 📡 Điện báo → Upload file Điện báo hiện tại.")
                return

            st.caption(f"📂 File: `{os.path.basename(fp_db)}`")

            # Chọn sheet
            try:
                from data.hstd import liet_ke_sheet_dienbao
                ds_sheet = liet_ke_sheet_dienbao(fp_db)
                sheet_options = [s["sheet"] for s in ds_sheet]
                sheet_info = {s["sheet"]: s for s in ds_sheet}

                chon_sheet = st.selectbox(
                    "Chọn sheet dữ liệu",
                    sheet_options,
                    key="khnv_bc_sheet",
                    format_func=lambda s: f"{s} ({sheet_info[s]['format']}, {sheet_info[s]['rows']} dòng, {sheet_info[s]['ngay'][:40]})"
                )
            except Exception:
                chon_sheet = "DB1"

            so_lieu_db = tong_hop_tu_dienbao(sheet_name=chon_sheet)
            if "error" in so_lieu_db:
                st.error(so_lieu_db["error"])
                return
            so_lieu = so_lieu_db  # dùng chung

        elif nguon == "🔄 So sánh HSTD vs Điện báo":
            if df_full is None or df_full.empty:
                st.warning("⚠️ Chưa có dữ liệu HSTD.")
                return

            fp_db = DB_HT_CACHE if os.path.exists(DB_HT_CACHE) else (
                FILE_PATH_DB if os.path.exists(FILE_PATH_DB) else None
            )
            if not fp_db:
                st.warning("⚠️ Chưa có file Điện báo.")
                return

            so_lieu = tong_hop_so_lieu_thang(df_full, thang=thang, nam=nam)
            so_lieu_db = tong_hop_tu_dienbao(sheet_name="DB1")

            if "error" not in so_lieu_db:
                chenh_lech = so_sanh_hstd_vs_dienbao(so_lieu, so_lieu_db)
                so_lieu["nguon"] = "HSTD + Điện báo"

        if not so_lieu:
            st.info("Không có dữ liệu để hiển thị.")
            return

        # ── Hiển thị KPI ──
        st.markdown("### 📊 Số liệu tổng hợp")

        if so_lieu.get("nguon", "").startswith("Điện báo"):
            kpi_row([
                {"label": "Tổng dư nợ", "value": so_lieu.get("tong_du_no", 0), "icon": "💰", "suffix": "đồng", "precision": 0},
                {"label": "Dư nợ KHA", "value": so_lieu.get("du_no_kha", 0), "icon": "📋", "suffix": "đồng", "precision": 0},
                {"label": "Dư nợ KHB", "value": so_lieu.get("du_no_khb", 0), "icon": "📋", "suffix": "đồng", "precision": 0},
                {"label": "NQH (KHA+KHB)", "value": (so_lieu.get("du_no_qua_han_kha", 0) + so_lieu.get("du_no_qua_han_khb", 0)), "icon": "⚠️", "suffix": "đồng", "precision": 0},
            ], num_columns=4)

            kpi_row([
                {"label": "Vốn TW (KHA)", "value": so_lieu.get("nguon_tw_kha", 0), "icon": "🏦", "suffix": "đồng", "precision": 0},
                {"label": "Huy động vốn", "value": so_lieu.get("huy_dong_von", 0), "icon": "💵", "suffix": "đồng", "precision": 0},
                {"label": "UTĐT ĐP", "value": so_lieu.get("utdt_dp", 0), "icon": "🤝", "suffix": "đồng", "precision": 0},
                {"label": "Vốn An toàn", "value": so_lieu.get("von_an_toan", 0), "icon": "🛡️", "suffix": "đồng", "precision": 0},
            ], num_columns=4)
        else:
            kpi_row([
                {"label": "Tổng dư nợ", "value": so_lieu.get("tong_du_no", 0), "icon": "💰", "suffix": "đồng", "precision": 0},
                {"label": "Nợ quá hạn", "value": so_lieu.get("du_no_qua_han", 0), "icon": "⚠️", "suffix": "đồng", "precision": 0,
                 "delta": so_lieu.get("ty_le_no_qua_han", 0), "delta_label": "%", "delta_color": "inverse"},
                {"label": "Số KH", "value": so_lieu.get("so_khach_hang", 0), "icon": "👥", "suffix": "", "precision": 0},
                {"label": "Giải ngân tháng", "value": so_lieu.get("giai_ngan_trong_thang", 0), "icon": "📤", "suffix": "đồng", "precision": 0},
            ], num_columns=4)

        # ── Đối chiếu (nếu có) ──
        if chenh_lech:
            st.markdown("---")
            st.markdown("### 🔄 Đối chiếu HSTD vs Điện báo")
            df_cl = pd.DataFrame(chenh_lech)
            st.dataframe(df_cl, use_container_width=True, hide_index=True)

        st.markdown("---")

        # ── Bảng chi tiết ──
        bang_pgd = so_lieu.get("bang_pgd", pd.DataFrame())
        bang_ct = so_lieu.get("bang_chuong_trinh", pd.DataFrame())
        bang_uy_thac = so_lieu.get("bang_uy_thac", pd.DataFrame())
        bang_dienbao = so_lieu.get("bang_theo_dv", pd.DataFrame())

        tab_labels = []
        if not bang_pgd.empty:
            tab_labels.append("📋 Theo PGD")
        if not bang_ct.empty:
            tab_labels.append("📑 Chương trình")
        if not bang_uy_thac.empty:
            tab_labels.append("🤝 Ủy thác")
        if not bang_dienbao.empty:
            tab_labels.append("📡 Điện báo theo ĐV")
        if so_lieu.get("units"):
            tab_labels.append("🗺️ Ma trận Điện báo")

        if tab_labels:
            tabs = st.tabs(tab_labels)
            tab_idx = 0

            if not bang_pgd.empty:
                with tabs[tab_idx]:
                    st.dataframe(bang_pgd, use_container_width=True, hide_index=True)
                tab_idx += 1

            if not bang_ct.empty:
                with tabs[tab_idx]:
                    st.dataframe(bang_ct, use_container_width=True, hide_index=True)
                tab_idx += 1

            if not bang_uy_thac.empty:
                with tabs[tab_idx]:
                    st.dataframe(bang_uy_thac, use_container_width=True, hide_index=True)
                tab_idx += 1

            if not bang_dienbao.empty:
                with tabs[tab_idx]:
                    st.dataframe(bang_dienbao, use_container_width=True, hide_index=True)
                tab_idx += 1

            if so_lieu.get("units"):
                with tabs[tab_idx]:
                    matrix = so_lieu.get("matrix", {})
                    units = so_lieu.get("units", [])
                    if matrix and units:
                        dv_chon = st.multiselect(
                            "Chọn đơn vị",
                            units,
                            default=units[:5] if len(units) >= 5 else units,
                            key="khnv_bc_matrix_dv",
                        )
                        if dv_chon:
                            data_rows = []
                            ct_quan_tam = ["Tổng dư nợ", "Dư nợ Kế hoạch A", "Dư nợ Kế hoạch B",
                                           "Dư nợ Quá hạn KHA", "Dư nợ Quá hạn KHB"]
                            for ct in ct_quan_tam:
                                if ct in matrix:
                                    row_data = {"Chỉ tiêu": ct}
                                    for dv in dv_chon:
                                        row_data[dv] = matrix[ct].get(dv, 0)
                                    data_rows.append(row_data)
                            df_view = pd.DataFrame(data_rows)
                            st.dataframe(df_view, use_container_width=True, hide_index=True)

        # ── Xuất báo cáo ──
        st.markdown("---")
        st.markdown("### 📥 Xuất báo cáo")

        # Chọn mẫu
        ds_mau = lay_danh_sach_mau()
        mau_options = [m["ten_hien_thi"] for m in ds_mau]
        if not mau_options:
            mau_options = ["Không tìm thấy mẫu"]
        ten_mau_chon = st.selectbox("Mẫu báo cáo", mau_options, key="khnv_bc_mau")

        che_do = st.radio(
            "Chế độ xuất:",
            ["📊 Xuất số liệu Excel", "📄 Sinh Word hoàn chỉnh", "📋 Cả hai"],
            horizontal=True,
            key="khnv_bc_che_do",
        )

        col_x1, col_x2 = st.columns(2)
        file_name_base = f"BC_KHNV_T{thang:02d}_{nam}"

        with col_x1:
            if che_do in ["📊 Xuất số liệu Excel", "📋 Cả hai"]:
                try:
                    excel_bytes = xuat_excel_bao_cao_khnv(
                        so_lieu, bang_pgd, bang_ct, bang_uy_thac,
                        bang_dienbao=bang_dienbao if not bang_dienbao.empty else None,
                        chenh_lech=chenh_lech,
                    )
                    st.download_button(
                        f"⬇️ Tải Excel ({file_name_base}.xlsx)",
                        data=excel_bytes,
                        file_name=f"{file_name_base}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key="khnv_bc_dl_excel",
                        use_container_width=True,
                    )
                except Exception as e:
                    logger.error("Excel: %s", e, exc_info=True)
                    st.error(f"❌ Lỗi: {e}")

        with col_x2:
            if che_do in ["📄 Sinh Word hoàn chỉnh", "📋 Cả hai"]:
                try:
                    word_bytes = xuat_word_bao_cao_khnv(
                        so_lieu, ten_mau_chon, bang_pgd, bang_ct,
                        bang_dienbao=bang_dienbao if not bang_dienbao.empty else None,
                        chenh_lech=chenh_lech,
                    )
                    st.download_button(
                        f"⬇️ Tải Word ({file_name_base}.docx)",
                        data=word_bytes,
                        file_name=f"{file_name_base}.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        key="khnv_bc_dl_word",
                        use_container_width=True,
                    )
                except Exception as e:
                    logger.error("Word: %s", e, exc_info=True)
                    st.error(f"❌ Lỗi: {e}")

        # ── Xem nội dung mẫu ──
        if ds_mau and ten_mau_chon != "Không tìm thấy mẫu":
            mau_info = next((m for m in ds_mau if m["ten_hien_thi"] == ten_mau_chon), None)
            if mau_info:
                with st.expander("📖 Xem nội dung mẫu", expanded=False):
                    nd = doc_noi_dung_mau(mau_info["ten_file"])
                    if nd:
                        st.markdown(nd[:3000] + ("\n\n...(còn tiếp)" if len(nd) > 3000 else ""))

        st.markdown("---")
        st.caption(
            "💡 **Mẹo**: Đặt file .md mẫu vào `docs/MAU BAO CAO KHNV/` để tự động hiển thị. "
            "Upload Điện báo tại tab 📡 Điện Báo trước khi dùng chế độ Điện báo."
        )
