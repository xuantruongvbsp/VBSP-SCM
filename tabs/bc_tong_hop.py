"""Báo cáo tổng hợp Quản lý Công việc & Nhiệm vụ."""

from __future__ import annotations

from datetime import date

import streamlit as st
import pandas as pd
import plotly.express as px

import db
from auth import normalize_role, la_phan_he_cn
from tabs.base_tab import TabContext
from config import DS_PGD, LOAI_CONG_VIEC, UU_TIEN_CV
from services import tien_do_service
from utils import fmt_so, fmt_ngay, hien_thi_dataframe_phan_trang, xuat_excel
from services import bc_tongquan_service
from logger import get_logger

logger = get_logger(__name__)

# Map tên hiển thị → value DB
_MAP_TRANG_THAI_TD = {
    "Đang theo dõi": "dang_theo_doi",
    "Đã hoàn thành": "hoan_thanh",
    "Tạm dừng": "tam_dung",
}
_MAP_TRANG_THAI_NV = {
    "Chờ thực hiện": "cho_thuc_hien",
    "Đang thực hiện": "dang_thuc_hien",
    "Đã hoàn thành": "da_hoan_thanh",
}
_MAP_UU_TIEN = {
    "Khẩn cấp": "khan_cap",
    "Quan trọng": "quan_trong",
    "Bình thường": "binh_thuong",
}


def _lay_kpi_tien_do(
    filter_nam: int,
    filter_quy: int | None,
    filter_thang: int | None,
    filter_trang_thai: list[str],
    filter_uu_tien: list[str],
) -> dict:
    """Tính KPI Tiến độ Công việc từ SQLite với filter."""
    try:
        hom_nay = date.today().isoformat()

        # Build WHERE clause cho filter thời gian trên ngay_deadline
        where_parts = []
        params = []

        # Filter năm từ ngay_deadline (yyyy-mm-dd)
        where_parts.append("substr(ngay_deadline, 1, 4) = ?")
        params.append(str(filter_nam))

        if filter_thang:
            where_parts.append("substr(ngay_deadline, 6, 2) = ?")
            params.append(f"{filter_thang:02d}")
        elif filter_quy:
            # Quý 1: tháng 1-3, Quý 2: 4-6, Quý 3: 7-9, Quý 4: 10-12
            thang_dau = (filter_quy - 1) * 3 + 1
            thang_cuoi = filter_quy * 3
            where_parts.append("CAST(substr(ngay_deadline, 6, 2) AS INTEGER) BETWEEN ? AND ?")
            params.extend([thang_dau, thang_cuoi])

        if filter_trang_thai:
            vals = [_MAP_TRANG_THAI_TD.get(t, t) for t in filter_trang_thai]
            placeholders = ",".join("?" * len(vals))
            where_parts.append(f"trang_thai IN ({placeholders})")
            params.extend(vals)
        else:
            where_parts.append("trang_thai = 'dang_theo_doi'")

        if filter_uu_tien:
            vals = [_MAP_UU_TIEN.get(u, u) for u in filter_uu_tien]
            placeholders = ",".join("?" * len(vals))
            where_parts.append(f"uu_tien IN ({placeholders})")
            params.extend(vals)

        where_sql = " AND ".join(where_parts)

        with db.get_conn() as conn:
            tasks = [dict(r) for r in conn.execute(
                f"SELECT * FROM tien_do_task WHERE {where_sql} ORDER BY ngay_deadline",
                params,
            ).fetchall()]

        if not tasks:
            return {"tong_task": 0, "tong_xa": 0, "xong": 0, "tre": 0, "pct_ht": 0, "ds_task": []}

        tong_xa = 0
        tong_xong = 0
        tong_tre = 0

        for t in tasks:
            kq = tien_do_service.doc_ketqua_task(t["id"])
            tong_xa += len(kq)
            for r in kq:
                if r["trang_thai"] == "da_hoan_thanh":
                    tong_xong += 1
                elif r["trang_thai"] == "chua_thuc_hien" and (t.get("ngay_deadline") or "") < hom_nay:
                    tong_tre += 1

        pct_ht = round(tong_xong / tong_xa * 100) if tong_xa > 0 else 0

        return {
            "tong_task": len(tasks),
            "tong_xa": tong_xa,
            "xong": tong_xong,
            "tre": tong_tre,
            "pct_ht": pct_ht,
            "ds_task": tasks,
        }

    except Exception as e:
        logger.error("_lay_kpi_tien_do: %s", e, exc_info=True)
        return {"tong_task": 0, "tong_xa": 0, "xong": 0, "tre": 0, "pct_ht": 0, "ds_task": []}


def _lay_kpi_nhiem_vu(
    filter_nam: int,
    filter_quy: int | None,
    filter_thang: int | None,
    filter_trang_thai: list[str],
) -> dict:
    """Tính KPI Nhiệm vụ định kỳ từ SQLite với filter."""
    try:
        where_parts = []
        params = []

        where_parts.append("(substr(ngay_deadline, 1, 4) = ? OR ngay_deadline IS NULL)")
        params.append(str(filter_nam))

        if filter_thang:
            where_parts.append("substr(ngay_deadline, 6, 2) = ?")
            params.append(f"{filter_thang:02d}")
        elif filter_quy:
            thang_dau = (filter_quy - 1) * 3 + 1
            thang_cuoi = filter_quy * 3
            where_parts.append("CAST(substr(ngay_deadline, 6, 2) AS INTEGER) BETWEEN ? AND ?")
            params.extend([thang_dau, thang_cuoi])

        if filter_trang_thai:
            vals = [_MAP_TRANG_THAI_NV.get(t, t) for t in filter_trang_thai]
            placeholders = ",".join("?" * len(vals))
            where_parts.append(f"trang_thai IN ({placeholders})")
            params.extend(vals)

        where_sql = " AND ".join(where_parts)

        with db.get_conn() as conn:
            row = conn.execute(
                f"""SELECT
                      COUNT(*)                                    AS tong,
                      SUM(trang_thai = 'da_hoan_thanh')          AS xong,
                      SUM(trang_thai = 'dang_thuc_hien')         AS dang,
                      SUM(trang_thai = 'cho_thuc_hien')          AS cho
                    FROM nhiem_vu WHERE {where_sql}""",
                params,
            ).fetchone()

            cho_duyet = conn.execute(
                """SELECT COUNT(*) FROM nhiem_vu_ketqua kq
                   JOIN nhiem_vu nv ON nv.id = kq.nhiem_vu_id
                   WHERE kq.trang_thai = 'cho_duyet'
                     AND substr(nv.ngay_deadline, 1, 4) = ?""",
                (str(filter_nam),),
            ).fetchone()[0]

        return {
            "tong":      int(row["tong"] or 0),
            "xong":      int(row["xong"] or 0),
            "dang":      int(row["dang"] or 0),
            "cho":       int(row["cho"] or 0),
            "cho_duyet": int(cho_duyet or 0),
        }

    except Exception as e:
        logger.error("_lay_kpi_nhiem_vu: %s", e, exc_info=True)
        return {"tong": 0, "xong": 0, "dang": 0, "cho": 0, "cho_duyet": 0}


def _lay_ma_tran_pgd(ds_task: list[dict]) -> pd.DataFrame:
    """Tạo ma trận PGD × Công việc (1 query duy nhất, tránh N+1)."""
    try:
        if not ds_task:
            return pd.DataFrame()

        task_ids = [t["id"] for t in ds_task]
        deadline_map = {t["id"]: t.get("ngay_deadline", "") for t in ds_task}
        hom_nay = date.today().isoformat()

        placeholders = ",".join("?" * len(task_ids))
        with db.get_conn() as conn:
            all_kq = conn.execute(
                f"SELECT task_id, pgd, trang_thai FROM tien_do_ketqua WHERE task_id IN ({placeholders})",
                task_ids,
            ).fetchall()

        # Gom kết quả theo PGD
        pgd_stats: dict[str, dict] = {pgd: {"tong": 0, "xong": 0, "tre": 0} for pgd in DS_PGD}

        for r in all_kq:
            pgd = r["pgd"]
            if pgd not in pgd_stats:
                continue
            pgd_stats[pgd]["tong"] += 1
            if r["trang_thai"] == "da_hoan_thanh":
                pgd_stats[pgd]["xong"] += 1
            elif r["trang_thai"] == "chua_thuc_hien":
                dl = deadline_map.get(r["task_id"], "")
                if dl and dl < hom_nay:
                    pgd_stats[pgd]["tre"] += 1

        rows = []
        for pgd in DS_PGD:
            s = pgd_stats[pgd]
            pct = round(s["xong"] / s["tong"] * 100) if s["tong"] > 0 else 0
            rows.append({
                "PGD": pgd,
                "Tổng KQ": s["tong"],
                "Hoàn thành": s["xong"],
                "Trễ hạn": s["tre"],
                "% HT": f"{pct}%",
            })

        return pd.DataFrame(rows)

    except Exception as e:
        logger.error("_lay_ma_tran_pgd: %s", e, exc_info=True)
        return pd.DataFrame()


def _lay_ds_nhiem_vu_cho_duyet(filter_nam: int) -> pd.DataFrame:
    """Lấy danh sách nhiệm vụ đang chờ duyệt."""
    try:
        with db.get_conn() as conn:
            rows = conn.execute(
                """SELECT nv.tieu_de AS 'Nhiệm vụ',
                          kq.pgd    AS 'PGD',
                          nv.chu_ky AS 'Chu kỳ',
                          nv.ky     AS 'Kỳ',
                          kq.ngay_nhap AS 'Ngày nộp'
                   FROM nhiem_vu_ketqua kq
                   JOIN nhiem_vu nv ON nv.id = kq.nhiem_vu_id
                   WHERE kq.trang_thai = 'cho_duyet'
                     AND substr(nv.ngay_deadline, 1, 4) = ?
                   ORDER BY kq.ngay_nhap DESC
                   LIMIT 50""",
                (str(filter_nam),),
            ).fetchall()
        df = pd.DataFrame([dict(r) for r in rows])
        if not df.empty and "Ngày nộp" in df.columns:
            df["Ngày nộp"] = df["Ngày nộp"].apply(lambda x: (x or "")[:10])
        return df

    except Exception as e:
        logger.error("_lay_ds_nhiem_vu_cho_duyet: %s", e, exc_info=True)
        return pd.DataFrame()


def render(tab=None, **kwargs) -> None:
    """Render báo cáo tổng hợp Công việc & Nhiệm vụ."""
    username = kwargs.get("username", "unknown")
    role_raw = kwargs.get("role", "user")
    role = normalize_role(str(role_raw) if role_raw else "user")

    ctx = TabContext(tab, **kwargs)
    with ctx:
        st.subheader("📋 Báo cáo Quản lý Công việc & Nhiệm vụ")

        # ① CHỌN MẢNG BÁO CÁO
        mang = st.radio(
            "📊 Chọn loại báo cáo:",
            ["📊 Tổng hợp KPI", "📈 Phân tích chi tiết", "🗂️ So sánh CV vs NV"],
            horizontal=True,
            key="bc_cq_mang",
        )

        st.divider()

        # ② FILTER NÂNG CAO
        with st.expander("🔍 Bộ lọc nâng cao", expanded=False):
            col1, col2, col3 = st.columns(3)

            with col1:
                nam = st.number_input("Năm", min_value=2020, value=2026, key="bc_cq_nam")
            with col2:
                quy_opts = {None: "Cả năm", 1: "Quý 1", 2: "Quý 2", 3: "Quý 3", 4: "Quý 4"}
                quy_sel = st.selectbox("Quý", list(quy_opts.keys()), format_func=lambda x: quy_opts[x], key="bc_cq_quy")
            with col3:
                thang_opts = {None: "Tất cả tháng", **{i: f"Tháng {i}" for i in range(1, 13)}}
                thang_sel = st.selectbox("Tháng", list(thang_opts.keys()), format_func=lambda x: thang_opts[x], key="bc_cq_thang")

            col1, col2 = st.columns(2)
            with col1:
                trang_thai = st.multiselect(
                    "Trạng thái Công việc",
                    list(_MAP_TRANG_THAI_TD.keys()),
                    key="bc_cq_trang_thai",
                )
            with col2:
                uu_tien = st.multiselect(
                    "Ưu tiên",
                    list(_MAP_UU_TIEN.keys()),
                    key="bc_cq_uu_tien",
                )

            col_btn1, col_btn2 = st.columns([1, 1])
            with col_btn1:
                st.button("🔄 Áp dụng", key="bc_cq_apply")
            with col_btn2:
                if st.button("✖️ Xóa lọc", key="bc_cq_clear"):
                    for k in ["bc_cq_nam", "bc_cq_quy", "bc_cq_thang", "bc_cq_trang_thai", "bc_cq_uu_tien"]:
                        if k in st.session_state:
                            del st.session_state[k]
                    st.rerun()

        # ③ KPI METRICS
        try:
            kpi_td = _lay_kpi_tien_do(
                filter_nam=int(nam),
                filter_quy=quy_sel,
                filter_thang=thang_sel,
                filter_trang_thai=trang_thai,
                filter_uu_tien=uu_tien,
            )
            kpi_nv = _lay_kpi_nhiem_vu(
                filter_nam=int(nam),
                filter_quy=quy_sel,
                filter_thang=thang_sel,
                filter_trang_thai=[],
            )

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("📋 Đầu việc", fmt_so(kpi_td["tong_task"]))
            c2.metric("✅ % HT CV", f"{kpi_td['pct_ht']}%", f"{kpi_td['xong']}/{kpi_td['tong_xa']} điểm")
            c3.metric("🔴 Trễ hạn", fmt_so(kpi_td["tre"]), delta_color="inverse")
            c4.metric("⏳ NV Chờ duyệt", fmt_so(kpi_nv["cho_duyet"]))

            st.divider()

            # ④ BIỂU ĐỒ & BẢNG (tabs theo mảng)
            if mang == "📊 Tổng hợp KPI":
                _render_tong_hop_kpi(kpi_td, kpi_nv, username)
            elif mang == "📈 Phân tích chi tiết":
                _render_phan_tich(kpi_td, kpi_nv, int(nam))
            else:
                _render_so_sanh(kpi_td, kpi_nv)

            st.divider()

            # ⑤ XUẤT BÁO CÁO
            col_x1, col_x2, col_x3 = st.columns(3)

            with col_x1:
                if st.button("📥 Xuất Excel", key="bc_cq_xuat_excel"):
                    try:
                        df_td_list = _build_df_tien_do(kpi_td["ds_task"])
                        df_nv_cho = _lay_ds_nhiem_vu_cho_duyet(int(nam))
                        sheets = {
                            "Tổng hợp CV": _build_df_tong_hop(kpi_td, kpi_nv),
                            "Ma trận PGD": _lay_ma_tran_pgd(kpi_td["ds_task"]),
                            "Chi tiết CV": df_td_list,
                            "NV Chờ duyệt": df_nv_cho,
                        }
                        bytes_excel = bc_tongquan_service.xuat_excel_bc(
                            sheets, f"BC_CV_NV_{nam}_{quy_sel or 'HK'}", username
                        )
                        if bytes_excel:
                            st.download_button(
                                "⬇️ Tải file Excel",
                                data=bytes_excel,
                                file_name=f"BC_CV_NV_{nam}_{quy_sel or 'HK'}.xlsx",
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                key="dl_bc_excel",
                            )
                    except Exception as e:
                        logger.error("xuat_excel_bc: %s", e, exc_info=True)
                        st.error(f"❌ Xuất Excel thất bại: {e}")

            with col_x2:
                if st.button("📄 Xuất PDF", key="bc_cq_xuat_pdf"):
                    try:
                        sheets = {
                            "Tổng hợp": _build_df_tong_hop(kpi_td, kpi_nv),
                            "Chi tiết CV": _build_df_tien_do(kpi_td["ds_task"]),
                        }
                        tieu_de = f"Báo cáo Công việc & Nhiệm vụ — {nam}/{quy_sel or 'HK'}"
                        bytes_pdf = bc_tongquan_service.xuat_pdf_bc(sheets, tieu_de, username)
                        if bytes_pdf:
                            st.download_button(
                                "⬇️ Tải file PDF",
                                data=bytes_pdf,
                                file_name=f"BC_CV_NV_{nam}_{quy_sel or 'HK'}.pdf",
                                mime="application/pdf",
                                key="dl_bc_pdf",
                            )
                    except Exception as e:
                        logger.error("xuat_pdf_bc: %s", e, exc_info=True)
                        st.error(f"❌ Xuất PDF thất bại: {e}")

            with col_x3:
                if st.button("📌 Xuất danh sách", key="bc_cq_xuat_list"):
                    try:
                        bytes_list = xuat_excel({
                            "Chi tiết Công việc": _build_df_tien_do(kpi_td["ds_task"]),
                            "NV Chờ duyệt": _lay_ds_nhiem_vu_cho_duyet(int(nam)),
                        })
                        if bytes_list:
                            st.download_button(
                                "⬇️ Tải danh sách",
                                data=bytes_list,
                                file_name=f"DS_CV_NV_{nam}_{quy_sel or 'HK'}.xlsx",
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                key="dl_list",
                            )
                    except Exception as e:
                        logger.error("xuat_list: %s", e, exc_info=True)
                        st.error(f"❌ Xuất danh sách thất bại: {e}")

        except Exception as e:
            logger.error("bc_tong_hop render: %s", e, exc_info=True)
            st.error(f"❌ Lỗi tính toán: {e}")


def _build_df_tong_hop(kpi_td: dict, kpi_nv: dict) -> pd.DataFrame:
    """Tạo DataFrame tổng hợp KPI để xuất."""
    rows = [
        {"Chỉ tiêu": "Tổng đầu việc (CV)", "Giá trị": kpi_td["tong_task"], "Đơn vị": "đầu việc"},
        {"Chỉ tiêu": "Tổng điểm KQ", "Giá trị": kpi_td["tong_xa"], "Đơn vị": "điểm"},
        {"Chỉ tiêu": "Hoàn thành", "Giá trị": kpi_td["xong"], "Đơn vị": "điểm"},
        {"Chỉ tiêu": "Trễ hạn", "Giá trị": kpi_td["tre"], "Đơn vị": "điểm"},
        {"Chỉ tiêu": "% Hoàn thành", "Giá trị": f"{kpi_td['pct_ht']}%", "Đơn vị": ""},
        {"Chỉ tiêu": "---", "Giá trị": "", "Đơn vị": ""},
        {"Chỉ tiêu": "Tổng nhiệm vụ", "Giá trị": kpi_nv["tong"], "Đơn vị": "nhiệm vụ"},
        {"Chỉ tiêu": "Đã hoàn thành", "Giá trị": kpi_nv["xong"], "Đơn vị": "nhiệm vụ"},
        {"Chỉ tiêu": "Đang thực hiện", "Giá trị": kpi_nv["dang"], "Đơn vị": "nhiệm vụ"},
        {"Chỉ tiêu": "Chờ duyệt (kết quả)", "Giá trị": kpi_nv["cho_duyet"], "Đơn vị": "kết quả"},
    ]
    return pd.DataFrame(rows)


def _build_df_tien_do(ds_task: list[dict]) -> pd.DataFrame:
    """Tạo DataFrame chi tiết công việc để xuất."""
    if not ds_task:
        return pd.DataFrame()
    rows = [
        {
            "Tiêu đề": t.get("tieu_de", ""),
            "Loại": LOAI_CONG_VIEC.get(t.get("loai", ""), t.get("loai", "")),
            "Ưu tiên": UU_TIEN_CV.get(t.get("uu_tien", ""), ""),
            "Thời hạn": fmt_ngay(t.get("ngay_deadline", "")),
            "Trạng thái": t.get("trang_thai", ""),
            "Người phụ trách": t.get("nguoi_phu_trach") or "",
            "Ghi chú": t.get("ghi_chu") or "",
        }
        for t in ds_task
    ]
    return pd.DataFrame(rows)


def _render_tong_hop_kpi(kpi_td: dict, kpi_nv: dict, username: str) -> None:
    """Render mảng Tổng hợp KPI: Ma trận + Pie chart."""
    try:
        subtabs = st.tabs(["📊 Ma trận PGD", "📈 Biểu đồ trạng thái", "📌 Chờ duyệt NV"])

        with subtabs[0]:
            st.subheader("Ma trận PGD × Tiến độ Công việc")
            st.caption("Hiển thị Hoàn thành / Tổng kết quả theo từng đơn vị")
            df_ma_tran = _lay_ma_tran_pgd(kpi_td["ds_task"])
            if not df_ma_tran.empty:
                hien_thi_dataframe_phan_trang(df_ma_tran, key="bc_ma_tran")
            else:
                st.info("Chưa có dữ liệu kết quả.")

        with subtabs[1]:
            st.subheader("Phân bố trạng thái Công việc")
            total = kpi_td["tong_xa"]
            dang = total - kpi_td["xong"] - kpi_td["tre"]
            if total > 0:
                pie_data = pd.DataFrame({
                    "Trạng thái": ["Hoàn thành", "Trễ hạn", "Đang thực hiện"],
                    "Số lượng": [kpi_td["xong"], kpi_td["tre"], max(0, dang)],
                })
                fig = px.pie(
                    pie_data, names="Trạng thái", values="Số lượng",
                    color_discrete_map={
                        "Hoàn thành": "#22c55e",
                        "Trễ hạn": "#ef4444",
                        "Đang thực hiện": "#3b82f6",
                    },
                )
                st.plotly_chart(fig, use_container_width=True, key="bc_pie_status")

                # Bar chart nhiệm vụ
                if kpi_nv["tong"] > 0:
                    st.subheader("Phân bố Nhiệm vụ định kỳ")
                    nv_data = pd.DataFrame({
                        "Trạng thái": ["Đã hoàn thành", "Đang thực hiện", "Chờ thực hiện"],
                        "Số lượng": [kpi_nv["xong"], kpi_nv["dang"], kpi_nv["cho"]],
                    })
                    fig2 = px.bar(
                        nv_data, x="Trạng thái", y="Số lượng", text="Số lượng",
                        color="Trạng thái",
                        color_discrete_map={
                            "Đã hoàn thành": "#22c55e",
                            "Đang thực hiện": "#3b82f6",
                            "Chờ thực hiện": "#f59e0b",
                        },
                    )
                    fig2.update_traces(textposition="outside")
                    st.plotly_chart(fig2, use_container_width=True, key="bc_bar_nhiem_vu")
            else:
                st.info("Chưa có dữ liệu để vẽ biểu đồ.")

        with subtabs[2]:
            st.subheader("Nhiệm vụ đang chờ duyệt")
            df_cho_duyet = _lay_ds_nhiem_vu_cho_duyet(
                int(nam) if nam else 2026
            )
            if not df_cho_duyet.empty:
                st.caption(f"Hiển thị {len(df_cho_duyet)} kết quả (tối đa 50)")
                hien_thi_dataframe_phan_trang(df_cho_duyet, key="bc_cho_duyet")
            else:
                st.info("Không có kết quả nào đang chờ duyệt.")

    except Exception as e:
        logger.error("_render_tong_hop_kpi: %s", e, exc_info=True)
        st.error(f"❌ Lỗi hiển thị Tổng hợp KPI: {e}")


def _render_phan_tich(kpi_td: dict, kpi_nv: dict, filter_nam: int) -> None:
    """Render mảng Phân tích chi tiết."""
    try:
        subtabs = st.tabs(["📋 Đầu việc", "📈 Tiến độ theo loại", "📌 Nhiệm vụ"])

        with subtabs[0]:
            st.subheader("Danh sách Đầu việc")
            df_td = _build_df_tien_do(kpi_td["ds_task"])
            if not df_td.empty:
                hien_thi_dataframe_phan_trang(df_td, key="bc_chi_tiet_td")
            else:
                st.info("Chưa có dữ liệu đầu việc.")

        with subtabs[1]:
            st.subheader("Tiến độ theo Loại công việc")
            if kpi_td["ds_task"]:
                loai_data: dict[str, int] = {}
                for t in kpi_td["ds_task"]:
                    loai = LOAI_CONG_VIEC.get(t.get("loai", ""), t.get("loai", "Khác"))
                    loai_data[loai] = loai_data.get(loai, 0) + 1

                df_loai = pd.DataFrame(
                    {"Loại": list(loai_data.keys()), "Số lượng": list(loai_data.values())}
                ).sort_values("Số lượng", ascending=True)

                fig = px.bar(
                    df_loai, x="Số lượng", y="Loại", orientation="h",
                    text="Số lượng", height=max(300, len(df_loai) * 40),
                )
                fig.update_traces(textposition="outside")
                st.plotly_chart(fig, use_container_width=True, key="bc_bar_loai")
            else:
                st.info("Chưa có dữ liệu đầu việc.")

        with subtabs[2]:
            st.subheader("Nhiệm vụ định kỳ")
            try:
                with db.get_conn() as conn:
                    rows = conn.execute(
                        """SELECT tieu_de AS 'Nhiệm vụ', pgd AS 'PGD',
                                  chu_ky AS 'Chu kỳ', ky AS 'Kỳ',
                                  trang_thai AS 'Trạng thái',
                                  ngay_deadline AS 'Deadline'
                           FROM nhiem_vu
                           WHERE substr(ngay_deadline, 1, 4) = ?
                           ORDER BY ngay_deadline DESC
                           LIMIT 100""",
                        (str(filter_nam),),
                    ).fetchall()
                df_nv = pd.DataFrame([dict(r) for r in rows])
                if not df_nv.empty:
                    df_nv["Deadline"] = df_nv["Deadline"].apply(lambda x: (x or "")[:10])
                    hien_thi_dataframe_phan_trang(df_nv, key="bc_nhiem_vu_chi_tiet")
                else:
                    st.info("Chưa có dữ liệu nhiệm vụ.")
            except Exception as e:
                logger.error("query nhiem_vu: %s", e, exc_info=True)
                st.error(f"❌ Lỗi đọc nhiệm vụ: {e}")

    except Exception as e:
        logger.error("_render_phan_tich: %s", e, exc_info=True)
        st.error(f"❌ Lỗi hiển thị Phân tích chi tiết: {e}")


def _render_so_sanh(kpi_td: dict, kpi_nv: dict) -> None:
    """Render mảng So sánh Công việc vs Nhiệm vụ."""
    try:
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("📋 Tiến độ Công việc")
            st.metric("Tổng đầu việc", fmt_so(kpi_td["tong_task"]))
            st.metric("Tổng kết quả cần theo dõi", fmt_so(kpi_td["tong_xa"]))
            st.metric("Đã hoàn thành", fmt_so(kpi_td["xong"]))
            st.metric("Trễ hạn", fmt_so(kpi_td["tre"]))

        with col2:
            st.subheader("📌 Nhiệm vụ định kỳ")
            st.metric("Tổng nhiệm vụ", fmt_so(kpi_nv["tong"]))
            st.metric("Đã hoàn thành", fmt_so(kpi_nv["xong"]))
            st.metric("Đang thực hiện", fmt_so(kpi_nv["dang"]))
            st.metric("Chờ duyệt", fmt_so(kpi_nv["cho_duyet"]))

        st.markdown("---")
        st.subheader("📊 So sánh tổng quan")

        compare_data = pd.DataFrame({
            "Danh mục": ["Đầu việc", "Kết quả cần theo dõi", "Nhiệm vụ"],
            "Tổng số": [kpi_td["tong_task"], kpi_td["tong_xa"], kpi_nv["tong"]],
        })

        fig = px.bar(
            compare_data, x="Danh mục", y="Tổng số", text="Tổng số",
            color="Danh mục",
            color_discrete_map={
                "Đầu việc": "#3b82f6",
                "Kết quả cần theo dõi": "#8b5cf6",
                "Nhiệm vụ": "#f59e0b",
            },
        )
        fig.update_traces(textposition="outside")
        st.plotly_chart(fig, use_container_width=True, key="bc_so_sanh_chart")

    except Exception as e:
        logger.error("_render_so_sanh: %s", e, exc_info=True)
        st.error(f"❌ Lỗi hiển thị So sánh: {e}")
