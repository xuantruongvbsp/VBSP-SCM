"""Theo dõi kế hoạch và kết quả công việc nội bộ Phòng KH-NV qua Google Forms."""

from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd
import streamlit as st
from streamlit.delta_generator import DeltaGenerator

from auth import la_phan_he_cn, la_quan_ly_cn, normalize_role
from config import KE_HOACH_CV_KHNV_DAU_VIEC, KE_HOACH_CV_KHNV_NHOM
from logger import get_logger
from services import ke_hoach_cv_khnv_service as svc
from services.excel_service import xuat_excel_chuyen_nghiep, ten_file_xuat as excel_ten_file
from tabs.base_tab import TabContext
from utils import xuat_excel

logger = get_logger(__name__)

KEY_PREFIX = "khnv_cv_"


@st.cache_data(ttl=300)
def _doc_ke_hoach_cached() -> pd.DataFrame:
    return svc.doc_ke_hoach()


@st.cache_data(ttl=300)
def _doc_ket_qua_cached() -> pd.DataFrame:
    return svc.doc_ket_qua()


@st.cache_data(ttl=300)
def _doc_nhiem_vu_gsheet_cached() -> pd.DataFrame:
    return svc.doc_nhiem_vu_gsheet()


def _fmt_date(value: Any) -> str:
    if pd.isna(value):
        return ""
    try:
        return pd.to_datetime(value).strftime("%d/%m/%Y")
    except Exception:
        return str(value or "")


def _fmt_pct_vn(rate: float) -> str:
    try:
        return f"{float(rate) * 100:.1f}".replace(".", ",") + "%"
    except Exception:
        return "0,0%"


def _danh_muc_dau_viec(cfg: dict[str, Any]) -> list[str]:
    configured = [
        str(item).strip()
        for item in cfg.get("dau_viec_custom", [])
        if str(item).strip()
    ]
    source = configured if configured else KE_HOACH_CV_KHNV_DAU_VIEC
    result: list[str] = []
    for item in source:
        if item not in result:
            result.append(item)
    return result


def _display_df(df: pd.DataFrame, date_cols: list[str]) -> pd.DataFrame:
    result = df.copy()
    for col in date_cols:
        if col in result.columns:
            result[col] = result[col].apply(_fmt_date)
    if "thoi_gian" in result.columns:
        result["thoi_gian"] = result["thoi_gian"].apply(
            lambda value: pd.to_datetime(value).strftime("%d/%m/%Y %H:%M")
            if not pd.isna(value)
            else ""
        )
    return result


def _unique_text(df: pd.DataFrame, col: str) -> list[str]:
    if df.empty or col not in df.columns:
        return []
    return sorted({str(x).strip() for x in df[col].dropna() if str(x).strip()})


def _unique_weeks(*frames: pd.DataFrame) -> list[date]:
    weeks: set[date] = set()
    for df in frames:
        if isinstance(df, pd.DataFrame) and "tuan" in df.columns:
            weeks.update({x for x in df["tuan"].dropna().tolist() if isinstance(x, date)})
    return sorted(weeks, reverse=True)


def _unique_dates(df: pd.DataFrame, col: str) -> list[date]:
    if df.empty:
        return []
    if "tuan" in df.columns:
        return _unique_weeks(df)
    if col not in df.columns:
        return []
    parsed = pd.to_datetime(df[col], dayfirst=True, errors="coerce")
    return sorted({x.date() for x in parsed.dropna()}, reverse=True)


def _filter_common(
    df: pd.DataFrame,
    *,
    key_prefix: str,
    week_col: str,
    text_filters: list[tuple[str, str]],
) -> pd.DataFrame:
    if df.empty:
        return df

    result = df.copy()
    weeks = _unique_dates(result, week_col)
    col_week, *cols = st.columns([1.3] + [1] * len(text_filters))
    with col_week:
        week_choice = st.selectbox(
            "Tuần",
            options=["Tất cả"] + weeks,
            key=f"{key_prefix}week",
            format_func=lambda value: "Tất cả" if value == "Tất cả" else _fmt_date(value),
        )
    if week_choice != "Tất cả" and "tuan" in result.columns:
        result = result[result["tuan"] == week_choice]
    elif week_choice != "Tất cả" and week_col in result.columns:
        parsed = pd.to_datetime(result[week_col], dayfirst=True, errors="coerce").dt.date
        result = result[parsed == week_choice]

    for col_ui, (field, label) in zip(cols, text_filters):
        with col_ui:
            options = ["Tất cả"] + _unique_text(result, field)
            choice = st.selectbox(label, options, key=f"{key_prefix}{field}")
        if choice != "Tất cả" and field in result.columns:
            result = result[result[field] == choice]

    return result


def _render_huong_dan(cfg: dict[str, Any]) -> None:
    st.markdown("### Quy trình")
    st.write("Đăng ký kế hoạch vào đầu tuần hoặc đầu tháng, sau đó báo cáo kết quả vào cuối kỳ.")
    st.write("Dữ liệu đi theo luồng Google Form → Google Sheets → VBSP-SCM, cache 5 phút.")

    form_kh = str(cfg.get("form_ke_hoach_url", "") or "").strip()
    form_kq = str(cfg.get("form_ket_qua_url", "") or "").strip()
    form_nv = str(cfg.get("form_nhiem_vu_url", "") or "").strip()
    c1, c2, c3 = st.columns(3)
    with c1:
        if form_kh:
            st.link_button("Mở Form đăng ký kế hoạch", form_kh, use_container_width=True)
        else:
            st.info("Chưa cấu hình URL Form đăng ký kế hoạch.")
    with c2:
        if form_kq:
            st.link_button("Mở Form báo cáo kết quả", form_kq, use_container_width=True)
        else:
            st.info("Chưa cấu hình URL Form báo cáo kết quả.")
    with c3:
        if form_nv:
            st.link_button("Mở Form nhiệm vụ giao", form_nv, use_container_width=True)
        else:
            st.info("Chưa cấu hình URL Form nhiệm vụ giao.")

    st.divider()
    st.markdown("### Cấu trúc Google Forms")
    st.write("Ba Form dùng cấu trúc phẳng, không branching. Các Form cùng ghi vào một Spreadsheet.")
    st.dataframe(
        pd.DataFrame(
            [
                {"Tab Sheet": "KhHoach", "Dữ liệu": "Đăng ký kế hoạch công việc"},
                {"Tab Sheet": "KetQua", "Dữ liệu": "Báo cáo kết quả công việc"},
                {"Tab Sheet": "NhiemVuGiao", "Dữ liệu": "Nhiệm vụ lãnh đạo phòng giao"},
            ]
        ),
        hide_index=True,
        use_container_width=True,
    )


def _render_cai_dat(cfg: dict[str, Any], username: str) -> None:
    st.markdown("### Cấu hình nguồn Google Sheets")

    with st.form(f"{KEY_PREFIX}config_form"):
        sheet_id = st.text_input(
            "Google Spreadsheet ID",
            value=str(cfg.get("sheet_id", "") or ""),
            key=f"{KEY_PREFIX}sheet_id",
        )
        form_ke_hoach_url = st.text_input(
            "URL Form đăng ký kế hoạch",
            value=str(cfg.get("form_ke_hoach_url", "") or ""),
            key=f"{KEY_PREFIX}form_kh",
        )
        form_ket_qua_url = st.text_input(
            "URL Form báo cáo kết quả",
            value=str(cfg.get("form_ket_qua_url", "") or ""),
            key=f"{KEY_PREFIX}form_kq",
        )
        form_nhiem_vu_url = st.text_input(
            "URL Form nhiệm vụ lãnh đạo giao",
            value=str(cfg.get("form_nhiem_vu_url", "") or ""),
            key=f"{KEY_PREFIX}form_nv",
        )

        st.markdown("### Danh mục gợi ý")
        st.caption("Filter thực tế vẫn đọc distinct value từ Sheet; danh mục này chỉ để đối chiếu khi tạo Form.")
        st.write("Nhóm công tác")
        st.dataframe(
            pd.DataFrame({"Nhóm công tác": KE_HOACH_CV_KHNV_NHOM}),
            hide_index=True,
            use_container_width=True,
        )

        dau_viec_df = pd.DataFrame({"Đầu việc": _danh_muc_dau_viec(cfg)})
        edited = st.data_editor(
            dau_viec_df,
            hide_index=True,
            num_rows="dynamic",
            use_container_width=True,
            key=f"{KEY_PREFIX}dau_viec_editor",
        )
        submitted = st.form_submit_button("Lưu cấu hình", type="primary")

    if submitted:
        dau_viec_custom = (
            edited["Đầu việc"].dropna().astype(str).str.strip().replace("", pd.NA).dropna().tolist()
            if "Đầu việc" in edited.columns
            else []
        )
        svc.luu_config(
            {
                "sheet_id": sheet_id,
                "form_ke_hoach_url": form_ke_hoach_url,
                "form_ket_qua_url": form_ket_qua_url,
                "form_nhiem_vu_url": form_nhiem_vu_url,
                "dau_viec_custom": dau_viec_custom,
            },
            username,
        )
        st.cache_data.clear()
        st.success("Đã lưu cấu hình kế hoạch/kết quả công việc KH-NV.")
        st.rerun()

    st.divider()
    col_test, _ = st.columns([1.4, 4])
    with col_test:
        if st.button("Kiểm tra kết nối", key=f"{KEY_PREFIX}test", use_container_width=True):
            ok, msg = svc.kiem_tra_ket_noi()
            if ok:
                st.success(msg)
            else:
                st.error(msg)


def _render_tong_quan(
    df_kh: pd.DataFrame,
    df_kq: pd.DataFrame,
    df_nv: pd.DataFrame,
    username: str = "unknown",
) -> None:
    tong_hop = svc.tinh_tong_hop(df_kh, df_kq)
    tong_hop_nv = svc.tinh_tong_hop_nhiem_vu(df_nv)
    metrics = tong_hop["metrics"]
    tuan_ht = tong_hop["tuan_hien_tai"]

    st.caption(f"Tuần hiện tại bắt đầu ngày {_fmt_date(tuan_ht)}")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Tổng KH tuần hiện tại", metrics["tong_kh_tuan"])
    c2.metric("Đã báo cáo", metrics["da_bao_cao"])
    c3.metric("Hoàn thành", metrics["hoan_thanh"])
    c4.metric("Tỷ lệ hoàn thành", _fmt_pct_vn(metrics["ty_le_hoan_thanh"]))
    c5.metric("NV đang mở", tong_hop_nv["dang_mo"], delta=f"{tong_hop_nv['qua_han']} quá hạn")

    st.divider()
    st.markdown("### Ma trận cán bộ × tuần")
    matrix = tong_hop["matrix"]
    if matrix.empty:
        st.info("Chưa có dữ liệu để lập ma trận.")
    else:
        st.dataframe(matrix, hide_index=True, use_container_width=True)

    st.divider()
    st.markdown("### Phân bổ theo đầu việc")
    chart = tong_hop["chart_dau_viec"]
    if chart.empty:
        st.info("Chưa có dữ liệu đầu việc.")
    else:
        st.bar_chart(chart.set_index("dau_viec"))

    # Xuất Excel tổng quan
    if not matrix.empty or not chart.empty:
        st.divider()
        kpi_items = [
            ("Tổng KH tuần hiện tại", metrics["tong_kh_tuan"], "dòng"),
            ("Đã báo cáo", metrics["da_bao_cao"], "dòng"),
            ("Hoàn thành", metrics["hoan_thanh"], "dòng"),
            ("Tỷ lệ hoàn thành", _fmt_pct_vn(metrics["ty_le_hoan_thanh"]), ""),
        ]
        matrix_clean = matrix.copy() if not matrix.empty else pd.DataFrame()
        chart_display = chart.rename(columns={"dau_viec": "Đầu việc", "Số kế hoạch": "Số kế hoạch"}) if not chart.empty else pd.DataFrame()

        extra: list[tuple[str, pd.DataFrame]] = []
        if not chart_display.empty:
            extra.append(("Đầu việc", chart_display))

        main_df = matrix_clean if not matrix_clean.empty else chart_display
        cols_excel = [(c, c, "text") for c in main_df.columns] if not main_df.empty else []

        try:
            excel_bytes = xuat_excel_chuyen_nghiep(
                main_df,
                title="Tổng quan Kế hoạch Công việc — Phòng KH-NV",
                nguoi_xuat=username,
                subtitle=f"Tuần {_fmt_date(tuan_ht)}",
                columns=cols_excel if cols_excel else None,
                kpi_items=kpi_items,
                extra_sheets=extra if extra else None,
            )
            st.download_button(
                "📥 Xuất Excel tổng quan",
                data=excel_bytes,
                file_name=excel_ten_file("khnv_tong_quan_cv"),
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key=f"{KEY_PREFIX}tq_excel",
                use_container_width=False,
            )
        except Exception as e:
            logger.error("_render_tong_quan: lỗi tạo Excel tổng quan — %s", e, exc_info=True)
            st.warning(f"Không thể tạo Excel tổng quan: {e}")


def _render_nhiem_vu_giao(
    df_nv_app: pd.DataFrame,
    df_nv_gsheet: pd.DataFrame,
    *,
    can_config: bool,
    username: str,
    cfg: dict[str, Any],
) -> None:
    st.markdown("### Nhiệm vụ lãnh đạo phòng giao")
    df_nv = svc.gop_nhiem_vu(df_nv_app, df_nv_gsheet)
    metrics = svc.tinh_tong_hop_nhiem_vu(df_nv)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Tổng nhiệm vụ", metrics["tong"])
    c2.metric("Đang mở", metrics["dang_mo"])
    c3.metric("Hoàn thành", metrics["hoan_thanh"])
    c4.metric("Quá hạn", metrics["qua_han"])

    if can_config:
        st.divider()
        st.markdown("#### Giao nhiệm vụ trong VBSP-SCM")
        with st.form(f"{KEY_PREFIX}nv_form", clear_on_submit=True):
            c_ngay, c_han, c_uu_tien, c_trang_thai = st.columns([1, 1, 1, 1])
            with c_ngay:
                ngay_giao = st.date_input(
                    "Ngày giao",
                    value=date.today(),
                    format="DD/MM/YYYY",
                    key=f"{KEY_PREFIX}nv_ngay_giao",
                )
            with c_han:
                han_hoan_thanh = st.date_input(
                    "Hạn hoàn thành",
                    value=date.today(),
                    format="DD/MM/YYYY",
                    key=f"{KEY_PREFIX}nv_han",
                )
            with c_uu_tien:
                uu_tien = st.selectbox("Ưu tiên", svc.UU_TIEN_NHIEM_VU, key=f"{KEY_PREFIX}nv_uu_tien")
            with c_trang_thai:
                trang_thai = st.selectbox("Trạng thái", svc.TRANG_THAI_NHIEM_VU, key=f"{KEY_PREFIX}nv_trang_thai")

            c_giao, c_nhan = st.columns(2)
            with c_giao:
                nguoi_giao = st.text_input(
                    "Người giao",
                    value=username,
                    key=f"{KEY_PREFIX}nv_nguoi_giao",
                )
            with c_nhan:
                can_bo_nhan = st.text_input(
                    "Cán bộ nhận",
                    placeholder="VD: Nguyễn Văn A; Trần Thị B",
                    key=f"{KEY_PREFIX}nv_can_bo_nhan",
                )

            nhom = st.selectbox("Nhóm công tác", KE_HOACH_CV_KHNV_NHOM, key=f"{KEY_PREFIX}nv_nhom")
            noi_dung = st.text_area("Nội dung nhiệm vụ", height=90, key=f"{KEY_PREFIX}nv_noi_dung")
            san_pham = st.text_area(
                "Sản phẩm/Yêu cầu đầu ra",
                height=70,
                key=f"{KEY_PREFIX}nv_san_pham",
            )
            ghi_chu = st.text_area("Ghi chú", height=70, key=f"{KEY_PREFIX}nv_ghi_chu")
            submitted = st.form_submit_button("Giao nhiệm vụ", type="primary")

        if submitted:
            try:
                svc.them_nhiem_vu_app(
                    {
                        "ngay_giao": ngay_giao,
                        "nguoi_giao": nguoi_giao,
                        "can_bo_nhan": can_bo_nhan,
                        "nhom_cong_tac": nhom,
                        "noi_dung": noi_dung,
                        "san_pham": san_pham,
                        "han_hoan_thanh": han_hoan_thanh,
                        "uu_tien": uu_tien,
                        "trang_thai": trang_thai,
                        "ghi_chu": ghi_chu,
                    },
                    username,
                )
                st.cache_data.clear()
                st.success("Đã giao nhiệm vụ.")
                st.rerun()
            except Exception as e:
                logger.error("_render_nhiem_vu_giao: thêm nhiệm vụ lỗi — %s", e, exc_info=True)
                st.error(f"Không thể giao nhiệm vụ: {e}")

    st.divider()
    st.markdown("#### Danh sách nhiệm vụ")
    form_nv = str(cfg.get("form_nhiem_vu_url", "") or "").strip()
    if form_nv:
        st.link_button("Mở Form nhiệm vụ giao", form_nv, use_container_width=False)

    if df_nv.empty:
        st.info("Chưa có nhiệm vụ lãnh đạo giao.")
        return

    filtered = _filter_common(
        df_nv,
        key_prefix=f"{KEY_PREFIX}nv_",
        week_col="han_hoan_thanh",
        text_filters=[
            ("can_bo_nhan", "Cán bộ nhận"),
            ("trang_thai", "Trạng thái"),
            ("uu_tien", "Ưu tiên"),
            ("nguon", "Nguồn"),
        ],
    )
    display = _display_df(filtered, ["ngay_giao", "han_hoan_thanh"])
    display = display.rename(
        columns={
            "thoi_gian": "Thời gian ghi nhận",
            "ma_nhiem_vu": "Mã nhiệm vụ",
            "ngay_giao": "Ngày giao",
            "nguoi_giao": "Người giao",
            "can_bo_nhan": "Cán bộ nhận",
            "nhom_cong_tac": "Nhóm công tác",
            "noi_dung": "Nội dung",
            "san_pham": "Sản phẩm/Yêu cầu",
            "han_hoan_thanh": "Hạn hoàn thành",
            "uu_tien": "Ưu tiên",
            "trang_thai": "Trạng thái",
            "ghi_chu": "Ghi chú",
            "nguon": "Nguồn",
            "qua_han": "Quá hạn",
        }
    )
    display = display.drop(columns=[c for c in ["han", "tuan"] if c in display.columns])
    st.dataframe(display, hide_index=True, use_container_width=True)

    if can_config:
        app_codes = sorted(_unique_text(df_nv_app, "ma_nhiem_vu"))
        if app_codes:
            with st.expander("Cập nhật trạng thái nhiệm vụ nhập trong app"):
                ma_chon = st.selectbox("Mã nhiệm vụ", app_codes, key=f"{KEY_PREFIX}nv_update_code")
                trang_thai_moi = st.selectbox(
                    "Trạng thái mới",
                    svc.TRANG_THAI_NHIEM_VU,
                    key=f"{KEY_PREFIX}nv_update_status",
                )
                ghi_chu_moi = st.text_area("Ghi chú cập nhật", key=f"{KEY_PREFIX}nv_update_note")
                c_up, c_del = st.columns(2)
                with c_up:
                    if st.button("Cập nhật", key=f"{KEY_PREFIX}nv_update_btn", use_container_width=True):
                        if svc.cap_nhat_trang_thai_nhiem_vu_app(ma_chon, trang_thai_moi, ghi_chu_moi, username):
                            st.cache_data.clear()
                            st.success("Đã cập nhật nhiệm vụ.")
                            st.rerun()
                with c_del:
                    if st.button("Xóa nhiệm vụ", key=f"{KEY_PREFIX}nv_delete_btn", use_container_width=True):
                        if svc.xoa_nhiem_vu_app(ma_chon, username):
                            st.cache_data.clear()
                            st.success("Đã xóa nhiệm vụ.")
                            st.rerun()

    try:
        excel_bytes = xuat_excel_chuyen_nghiep(
            display,
            title="Nhiệm vụ Lãnh đạo Phòng giao — KH-NV",
            nguoi_xuat=username,
            subtitle=f"Xuất ngày {date.today().strftime('%d/%m/%Y')}",
            columns=[(c, c, "text") for c in display.columns],
            kpi_items=[
                ("Tổng nhiệm vụ", metrics["tong"], "nhiệm vụ"),
                ("Đang mở", metrics["dang_mo"], "nhiệm vụ"),
                ("Hoàn thành", metrics["hoan_thanh"], "nhiệm vụ"),
                ("Quá hạn", metrics["qua_han"], "nhiệm vụ"),
            ],
        )
    except Exception as e:
        logger.warning("_render_nhiem_vu_giao: fallback Excel thường — %s", e, exc_info=True)
        excel_bytes = xuat_excel({"Nhiệm vụ giao": display})
    st.download_button(
        "📥 Tải Excel nhiệm vụ giao",
        data=excel_bytes,
        file_name=excel_ten_file("khnv_nhiem_vu_giao"),
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key=f"{KEY_PREFIX}nv_excel",
        use_container_width=False,
    )


def _render_ke_hoach(df_kh: pd.DataFrame, username: str = "unknown") -> None:
    st.markdown("### Kế hoạch đăng ký")
    if df_kh.empty:
        st.info("Chưa có dữ liệu kế hoạch từ Google Sheets.")
        return

    filtered = _filter_common(
        df_kh,
        key_prefix=f"{KEY_PREFIX}kh_",
        week_col="tuan_ke_hoach",
        text_filters=[
            ("ho_ten", "Cán bộ"),
            ("dau_viec", "Đầu việc"),
            ("uu_tien", "Ưu tiên"),
        ],
    )
    display = _display_df(filtered, ["tuan_ke_hoach"])
    display = display.rename(
        columns={
            "thoi_gian": "Thời gian gửi",
            "ho_ten": "Họ tên",
            "tuan_ke_hoach": "Tuần kế hoạch",
            "nhom_cong_tac": "Nhóm công tác",
            "dau_viec": "Đầu việc",
            "mo_ta": "Mô tả",
            "thoi_gian_du_kien": "Thời gian dự kiến",
            "uu_tien": "Ưu tiên",
            "ghi_chu": "Ghi chú",
        }
    )
    display = display.drop(columns=[c for c in ["tuan"] if c in display.columns])
    st.dataframe(display, hide_index=True, use_container_width=True)

    n_total = len(filtered)
    n_tuan = filtered["tuan"].nunique() if "tuan" in filtered.columns else 0
    n_can_bo = filtered["ho_ten"].nunique() if "ho_ten" in filtered.columns else 0
    kpi_items = [
        ("Tổng kế hoạch (bộ lọc hiện tại)", n_total, "dòng"),
        ("Số tuần", n_tuan, "tuần"),
        ("Số cán bộ", n_can_bo, "người"),
    ]
    cols_excel = [(c, c, "text") for c in display.columns]
    try:
        excel_bytes = xuat_excel_chuyen_nghiep(
            display,
            title="Kế hoạch Công việc — Phòng KH-NV",
            nguoi_xuat=username,
            subtitle=f"Xuất ngày {date.today().strftime('%d/%m/%Y')}",
            columns=cols_excel,
            kpi_items=kpi_items,
        )
    except Exception as e:
        logger.warning("_render_ke_hoach: fallback Excel thường — %s", e, exc_info=True)
        excel_bytes = xuat_excel({"Kế hoạch": display})

    c_xl, c_pdf = st.columns(2)
    with c_xl:
        st.download_button(
            "📥 Tải Excel kế hoạch",
            data=excel_bytes,
            file_name=excel_ten_file("khnv_ke_hoach_cv"),
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key=f"{KEY_PREFIX}kh_excel",
            use_container_width=True,
        )
    with c_pdf:
        if st.button("📄 Tạo PDF kế hoạch", key=f"{KEY_PREFIX}kh_pdf_btn", use_container_width=True):
            try:
                from components.export_pdf import xuat_pdf_co_chart
                pdf = xuat_pdf_co_chart(
                    display,
                    tieu_de="Kế hoạch Công việc — Phòng KH-NV",
                    nguoi_xuat=username,
                )
                st.session_state[f"{KEY_PREFIX}kh_pdf"] = pdf
            except Exception as e:
                logger.error("_render_ke_hoach: lỗi tạo PDF — %s", e, exc_info=True)
                st.error(f"❌ Lỗi tạo PDF: {e}")
        if st.session_state.get(f"{KEY_PREFIX}kh_pdf"):
            from components.export_pdf import download_pdf_button
            download_pdf_button(
                st.session_state[f"{KEY_PREFIX}kh_pdf"],
                filename=excel_ten_file("khnv_ke_hoach_cv", "pdf"),
                label="📥 Tải PDF kế hoạch",
                key=f"{KEY_PREFIX}kh_pdf_dl",
            )


def _render_ket_qua(df_kq: pd.DataFrame, username: str = "unknown") -> None:
    st.markdown("### Kết quả báo cáo")
    if df_kq.empty:
        st.info("Chưa có dữ liệu kết quả từ Google Sheets.")
        return

    filtered = _filter_common(
        df_kq,
        key_prefix=f"{KEY_PREFIX}kq_",
        week_col="tuan_bao_cao",
        text_filters=[
            ("ho_ten", "Cán bộ"),
            ("trang_thai", "Trạng thái"),
        ],
    )
    display = _display_df(filtered, ["tuan_bao_cao"])
    display = display.rename(
        columns={
            "thoi_gian": "Thời gian gửi",
            "ho_ten": "Họ tên",
            "tuan_bao_cao": "Tuần báo cáo",
            "nhom_cong_tac": "Nhóm công tác",
            "dau_viec": "Đầu việc",
            "mo_ta_cv": "Mô tả công việc",
            "trang_thai": "Trạng thái",
            "ket_qua": "Kết quả/Ghi chú",
        }
    )
    display = display.drop(columns=[c for c in ["tuan"] if c in display.columns])

    by_person = pd.DataFrame()
    if not filtered.empty:
        by_person = (
            filtered.assign(_done=filtered["trang_thai"].astype(str).str.contains("Hoàn thành", case=False, na=False))
            .groupby("ho_ten")
            .agg(Tổng=("ho_ten", "size"), Hoàn_thành=("_done", "sum"))
            .reset_index()
        )
        by_person["Tỷ lệ hoàn thành"] = by_person.apply(
            lambda row: _fmt_pct_vn(row["Hoàn_thành"] / row["Tổng"] if row["Tổng"] else 0),
            axis=1,
        )
        by_person = by_person.rename(columns={"ho_ten": "Cán bộ", "Hoàn_thành": "Hoàn thành"})
        st.dataframe(by_person, hide_index=True, use_container_width=True)

    st.dataframe(display, hide_index=True, use_container_width=True)

    n_total = len(filtered)
    n_hoan_thanh = int(filtered["trang_thai"].astype(str).str.contains("Hoàn thành", case=False, na=False).sum()) if "trang_thai" in filtered.columns else 0
    ty_le = n_hoan_thanh / n_total if n_total else 0.0
    kpi_items = [
        ("Tổng báo cáo (bộ lọc hiện tại)", n_total, "dòng"),
        ("Hoàn thành", n_hoan_thanh, "dòng"),
        ("Tỷ lệ hoàn thành", _fmt_pct_vn(ty_le), ""),
    ]
    cols_excel = [(c, c, "text") for c in display.columns]
    extra_sheets = [("Tổng hợp cán bộ", by_person)] if not by_person.empty else None
    try:
        excel_bytes = xuat_excel_chuyen_nghiep(
            display,
            title="Kết quả Công việc — Phòng KH-NV",
            nguoi_xuat=username,
            subtitle=f"Xuất ngày {date.today().strftime('%d/%m/%Y')}",
            columns=cols_excel,
            kpi_items=kpi_items,
            extra_sheets=extra_sheets,
        )
    except Exception as e:
        logger.warning("_render_ket_qua: fallback Excel thường — %s", e, exc_info=True)
        excel_bytes = xuat_excel({"Kết quả": display})

    c_xl, c_pdf = st.columns(2)
    with c_xl:
        st.download_button(
            "📥 Tải Excel kết quả",
            data=excel_bytes,
            file_name=excel_ten_file("khnv_ket_qua_cv"),
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key=f"{KEY_PREFIX}kq_excel",
            use_container_width=True,
        )
    with c_pdf:
        if st.button("📄 Tạo PDF kết quả", key=f"{KEY_PREFIX}kq_pdf_btn", use_container_width=True):
            try:
                from components.export_pdf import xuat_pdf_co_chart
                pdf = xuat_pdf_co_chart(
                    display,
                    tieu_de="Kết quả Công việc — Phòng KH-NV",
                    nguoi_xuat=username,
                )
                st.session_state[f"{KEY_PREFIX}kq_pdf"] = pdf
            except Exception as e:
                logger.error("_render_ket_qua: lỗi tạo PDF — %s", e, exc_info=True)
                st.error(f"❌ Lỗi tạo PDF: {e}")
        if st.session_state.get(f"{KEY_PREFIX}kq_pdf"):
            from components.export_pdf import download_pdf_button
            download_pdf_button(
                st.session_state[f"{KEY_PREFIX}kq_pdf"],
                filename=excel_ten_file("khnv_ket_qua_cv", "pdf"),
                label="📥 Tải PDF kết quả",
                key=f"{KEY_PREFIX}kq_pdf_dl",
            )


def render(tab: DeltaGenerator = None, **kwargs) -> None:
    ctx = TabContext(tab, **kwargs)
    role = normalize_role(str(kwargs.get("role", "user") or "user"))
    username = kwargs.get("username", st.session_state.get("username", "unknown"))
    can_config = la_quan_ly_cn(role)

    with ctx:
        st.subheader("Kế hoạch & Kết quả Công việc — Phòng KH-NV")
        st.caption("Dữ liệu từ Google Forms · Google Sheets · cache 5 phút")

        role_is_cn = la_phan_he_cn(role)
        if not role_is_cn:
            st.warning("Chức năng này dành cho phân hệ Chi nhánh.")
            return

        cfg = svc.doc_config()
        col_refresh, _ = st.columns([1, 6])
        with col_refresh:
            if st.button("Làm mới", key=f"{KEY_PREFIX}refresh", use_container_width=True):
                st.cache_data.clear()
                st.rerun()

        if not str(cfg.get("sheet_id", "") or "").strip():
            st.info("Chưa cấu hình Spreadsheet ID. Admin/manager vào tab Cài đặt để nhập Sheet ID.")

        df_kh = _doc_ke_hoach_cached()
        df_kq = _doc_ket_qua_cached()
        df_nv_gsheet = _doc_nhiem_vu_gsheet_cached()
        df_nv_app = svc.doc_nhiem_vu_app()
        loi = svc.lay_loi_doc_gsheet_gan_nhat()
        if loi:
            st.warning(f"Không đọc được Google Sheets: {loi}")

        if can_config:
            t0, t1, t2, t3, t4, t5 = st.tabs(
                ["Hướng dẫn", "Cài đặt", "Tổng quan", "Nhiệm vụ giao", "Kế hoạch đăng ký", "Kết quả báo cáo"]
            )
        else:
            t0, t2, t3, t4, t5 = st.tabs(
                ["Hướng dẫn", "Tổng quan", "Nhiệm vụ giao", "Kế hoạch đăng ký", "Kết quả báo cáo"]
            )
            t1 = None

        with t0:
            _render_huong_dan(cfg)
        if t1 is not None:
            with t1:
                _render_cai_dat(cfg, username)
        with t2:
            _render_tong_quan(df_kh, df_kq, svc.gop_nhiem_vu(df_nv_app, df_nv_gsheet), username)
        with t3:
            _render_nhiem_vu_giao(
                df_nv_app,
                df_nv_gsheet,
                can_config=can_config,
                username=username,
                cfg=cfg,
            )
        with t4:
            _render_ke_hoach(df_kh, username)
        with t5:
            _render_ket_qua(df_kq, username)
