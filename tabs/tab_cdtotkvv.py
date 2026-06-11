"""
Tab Chấm điểm Tổ TK&VV — chỉ admin/manager.

Sub-tab 1: Upload file Excel chấm điểm theo tháng.
Sub-tab 2: Tổng hợp theo Phòng giao dịch với KPI và xuất Excel.
Sub-tab 3: Phân tích Chất lượng - KPI và bảng tiêu chí bị trừ điểm.
Sub-tab 4: Bản đồ Chất lượng - Treemap và Heatmap không dùng folium.
Sub-tab 5: Xu hướng - Timeline và cảnh báo xu hướng xấu.
"""


from __future__ import annotations

from logger import get_logger
logger = get_logger(__name__)

import re
import socket
from datetime import datetime
from typing import TYPE_CHECKING

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

import db
from auth import la_phan_he_cn, la_phan_he_pgd, normalize_role
from config import DS_PGD
from utils import fmt_so, vn, xuat_excel, ten_file_xuat, hien_thi_dataframe_phan_trang
from state_manager import SCMStateManager
from services.cdtotkvv_service import (
    bang_trang_thai_cdtotkvv as _bang_trang_thai_cdtotkvv,
    loc_df as _loc_df,
    cdtotkvv_ten_sheet_excel as _cdtotkvv_ten_sheet_excel,
    fmt_xuat_to_khong_dat_vn as _fmt_xuat_to_khong_dat_vn,
)
from services.tongquan_cdto_service import load_cdto_toan_cn
from data.cdtotkvv import (

    doc_cdtotkvv, ds_thang_nam, tong_hop_theo_pgd,
    _XEP_LOAI_TOT, _XEP_LOAI_KHA, _XEP_LOAI_TB, _XEP_LOAI_YEU
)

# Điểm tối đa / nhãn tiêu chí — dùng chung bảng phân tích & xuất Excel Tổ không đạt
_CDTOTKVV_DIEM_TOI_DA: dict[str, int] = {
    "diem_gdtx": 20,
    "diem_thu_no": 15,
    "diem_thu_lai": 20,
    "diem_tv_tiengui": 5,
    "diem_ds_tg": 10,
    "diem_nqh": 30,
}
_CDTOTKVV_TEN_HIEN_THI: dict[str, str] = {
    "diem_gdtx": "Giao dịch tại xã",
    "diem_thu_no": "Thu nợ đến hạn",
    "diem_thu_lai": "Tỷ lệ thu lãi",
    "diem_tv_tiengui": "Tổ viên tham gia tiền gửi",
    "diem_ds_tg": "Số dư tiền gửi tăng thêm",
    "diem_nqh": "Tỷ lệ nợ quá hạn",
}


def _render_xuat_to_khong_dat_tieu_chi(
    df: pd.DataFrame,
    username: str,
    thang_chon: str,
) -> None:
    """
    Xuất danh sách tổ chưa đạt điểm tối đa theo tiêu chí (đúng cột `CDTOTKVV_COLS` / diem_*).
    Lọc PGD: bỏ trống = toàn bộ. Excel qua `xuat_excel`, PDF qua `pdf_service.xuat_pdf_bang` nếu có.
    """
    st.divider()
    st.markdown("**📤 Xuất danh sách Tổ chưa đạt tiêu chí**")

    tieu_chi_co_san = [k for k in _CDTOTKVV_DIEM_TOI_DA if k in df.columns]
    if not tieu_chi_co_san:
        st.caption("Không có cột tiêu chí chấm điểm trong dữ liệu tháng đã chọn.")
        return

    hostname = socket.gethostname()
    col1, col2 = st.columns([3, 2])
    with col1:
        tieu_chi_chon = st.multiselect(
            "Chọn tiêu chí (có thể chọn nhiều)",
            options=tieu_chi_co_san,
            default=[tieu_chi_co_san[0]],
            format_func=lambda x: _CDTOTKVV_TEN_HIEN_THI.get(x, x),
            key="xuat_tc_chon",
        )
    with col2:
        ds_pgd = sorted(df["ten_dv"].dropna().astype(str).unique()) if "ten_dv" in df.columns else []
        pgd_loc = st.multiselect(
            "Lọc PGD (bỏ trống = tất cả)",
            options=ds_pgd,
            default=[],
            key="xuat_tc_pgd",
        )

    if not tieu_chi_chon:
        st.info("Chọn ít nhất 1 tiêu chí để xuất.")
        return

    cot_noi_bo_doi_ten: list[tuple[str, str]] = [
        ("ten_dv", "PGD"),
        ("ten_xa", "Xã"),
        ("ma_to", "Mã Tổ"),
        ("ten_to_truong", "Tổ trưởng"),
        ("tong_diem", "Tổng điểm"),
        ("xep_loai", "Xếp loại"),
        ("du_no", "Dư nợ"),
        ("so_du_tk", "Số dư TK"),
    ]

    try:
        df_loc = (
            df[df["ten_dv"].isin(pgd_loc)].copy()
            if pgd_loc and "ten_dv" in df.columns
            else df.copy()
        )

        sheets: dict[str, pd.DataFrame] = {}
        tong_khong_dat = 0

        for tc in tieu_chi_chon:
            diem_max = _CDTOTKVV_DIEM_TOI_DA[tc]
            ten = _CDTOTKVV_TEN_HIEN_THI[tc]

            diem = pd.to_numeric(df_loc[tc], errors="coerce").fillna(0)
            df_nd = df_loc[diem < diem_max].copy()
            if df_nd.empty:
                continue
            df_nd["_diem"] = diem.loc[df_nd.index]

            cot_trong = [
                c for c, _ in cot_noi_bo_doi_ten
                if c in df_nd.columns and c != tc
            ]
            out = df_nd[cot_trong].rename(
                columns={s: d for s, d in cot_noi_bo_doi_ten if s in cot_trong}
            )
            out.insert(0, "Tiêu chí", ten)
            out.insert(1, "Điểm tối đa", diem_max)
            out.insert(2, "Điểm đạt được", df_nd["_diem"].values)
            out.insert(3, "Thiếu", diem_max - df_nd["_diem"].values)
            out = out.sort_values("Điểm đạt được", ascending=True)

            da_dung = set(sheets.keys())
            sheet_name = _cdtotkvv_ten_sheet_excel(ten, da_dung)
            sheets[sheet_name] = out
            tong_khong_dat += len(out)

        if not sheets:
            st.success("🎉 Tất cả các tổ đều đạt các tiêu chí đã chọn!")
            db.ghi_audit(
                username,
                "export_to_khong_dat_tieu_chi",
                f"[{hostname}] thang={thang_chon} tieu_chi={','.join(tieu_chi_chon)} so_to=0",
            )
            return

        c1, c2, c3, c4 = st.columns(4)
        c1.metric(
            "Tổng tổ không đạt",
            tong_khong_dat,
            help="Gộp theo các tiêu chí đã chọn (một tổ có thể đếm nhiều lần nếu không đạt nhiều tiêu chí)",
        )
        c2.metric("Số tiêu chí có dữ liệu xuất", len(sheets))
        c3.metric(
            "Số PGD",
            df_loc["ten_dv"].nunique() if "ten_dv" in df_loc.columns else "—",
        )
        c4.metric(
            "Tỷ lệ",
            f"{tong_khong_dat / len(df_loc) * 100:.1f}%" if len(df_loc) else "—",
        )

        for ten_sheet, df_s in sheets.items():
            with st.expander(f"{ten_sheet} — {len(df_s)} tổ", expanded=False):
                a, b, c = st.columns(3)
                a.metric("Điểm TB", f"{df_s['Điểm đạt được'].mean():.1f}")
                b.metric("Điểm thấp nhất", f"{df_s['Điểm đạt được'].min():.1f}")
                c.metric("Điểm cao nhất", f"{df_s['Điểm đạt được'].max():.1f}")
                st.dataframe(df_s.head(20), use_container_width=True, height=360)
                if len(df_s) > 20:
                    st.caption(f"Hiển thị 20/{len(df_s)} tổ, tải Excel/PDF để xem đầy đủ.")

        sheets_xuat = {k: _fmt_xuat_to_khong_dat_vn(v) for k, v in sheets.items()}
        excel_bytes = xuat_excel(sheets_xuat)
        slug = tieu_chi_chon[0] if len(tieu_chi_chon) == 1 else f"{len(tieu_chi_chon)}tc"
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")

        col_ex, col_pdf = st.columns(2)
        with col_ex:
            st.download_button(
                label=f"📥 Xuất Excel ({tong_khong_dat} dòng, {len(sheets)} sheet)",
                data=excel_bytes,
                file_name=ten_file_xuat(f"To_khong_dat_{slug}"),
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
                key="xuat_tc_excel",
            )
        with col_pdf:
            try:
                from pdf_service import xuat_pdf

                df_all = pd.concat(sheets.values(), ignore_index=True)
                cols_tien = [c for c in ("Dư nợ", "Số dư TK") if c in df_all.columns]
                pdf_bytes = xuat_pdf(
                    df=df_all,
                    tieu_de=f"Tổ chưa đạt tiêu chí — Tháng {thang_chon}",
                    nguoi_xuat=username,
                    cols_tien=cols_tien,
                    prefix_file="CDTOTKVV",
                )
                st.download_button(
                    label="📄 Xuất PDF",
                    data=pdf_bytes,
                    file_name=f"To_khong_dat_{slug}_{ts}.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                    key="xuat_tc_pdf",
                )
            except Exception as e_pdf:
                logger.error("Lỗi trong khối except: %s", e_pdf, exc_info=True)
                st.button(
                    "📄 Xuất PDF",
                    disabled=True,
                    help=f"Không tạo được PDF: {e_pdf}",
                    use_container_width=True,
                    key="xuat_tc_pdf_na",
                )

        db.ghi_audit(
            username,
            "export_to_khong_dat_tieu_chi",
            f"[{hostname}] thang={thang_chon} tieu_chi={','.join(tieu_chi_chon)} "
            f"so_to={tong_khong_dat} pgd={pgd_loc or 'all'}",
        )

    except Exception as e:
        logger.error("Lỗi trong khối except: %s", e, exc_info=True)
        import traceback


        st.error(f"❌ Lỗi khi xử lý xuất tổ không đạt tiêu chí: {e}")
        with st.expander("Chi tiết lỗi (debug)", expanded=False):
            st.code(traceback.format_exc())
        db.ghi_audit(
            username,
            "loi_he_thong",
            f"[{hostname}] export_to_khong_dat_tieu_chi thang={thang_chon} error={str(e)[:200]}",
        )


def _sub_upload(role: str, username: str) -> None:
    st.markdown("##### Trạng thái Upload CDTOTKVV")
    
    # Banner thông báo
    st.info(
        "📌 **Dữ liệu CDTOTKVV được upload tập trung tại Upload Dữ liệu — Phòng KH-NV. "
        "Tab này chỉ hiển thị trạng thái tổng hợp.**"
    )
    
    st.divider()
    
    # Tạo bảng trạng thái
    df_trang_thai = _bang_trang_thai_cdtotkvv()
    
    # Thống kê tổng hợp
    so_da_co = len([row for _, row in df_trang_thai.iterrows() if "✅" in row["Trạng thái"]])
    so_chua_co = 22 - so_da_co
    
    # Danh sách đơn vị còn thiếu
    dv_chua_co = [
        row["Đơn vị"] 
        for _, row in df_trang_thai.iterrows() 
        if "❌" in row["Trạng thái"]
    ]
    
    # Thông báo tổng hợp
    if so_chua_co == 0:
        st.success(f"**Đã có dữ liệu: {so_da_co} / 22 đơn vị**")
    else:
        st.warning(f"**Đã có dữ liệu: {so_da_co} / 22 đơn vị  |  ⚠️ Chưa tổng hợp: {so_chua_co} đơn vị**")
        if dv_chua_co:
            danh_sach_thieu = ", ".join(dv_chua_co)
            st.caption(f"Còn thiếu: {danh_sach_thieu}")
    
    st.divider()
    
    # Hiển thị bảng trạng thái
    st.markdown("**Bảng trạng thái từng đơn vị:**")
    hien_thi_dataframe_phan_trang(df_trang_thai, key="cdtotkvv_trang_thai_dv")

def _sub_tong_hop(username: str) -> None:
    st.markdown("##### Tổng hợp dữ liệu từ hệ thống tập trung")

    cdto = load_cdto_toan_cn()
    df = cdto["df_raw"]
    kpi = cdto["kpi"]
    thang_hien = cdto["thang_hien"]

    if df is None or df.empty:
        st.info("Chưa có dữ liệu CDTOTKVV nào từ hệ thống tập trung. Hãy kiểm tra tab Upload để xem trạng thái.")
        return

    th = tong_hop_theo_pgd(df)

    if cdto["so_pgd_thieu"] > 0:
        ten_thieu = ", ".join(cdto["ds_pgd_thieu"][:5])
        duoi = f" và {cdto['so_pgd_thieu'] - 5} đơn vị khác" if cdto["so_pgd_thieu"] > 5 else ""
        st.info(
            f"📊 Dữ liệu từ **{cdto['so_pgd_co']}/{len(DS_PGD)} PGD** · "
            f"Thiếu: **{ten_thieu}{duoi}**"
        )
    if thang_hien:
        st.caption(f"📅 Kỳ: Tháng {thang_hien}")

    if kpi is None:
        st.info("Không tính được KPI từ dữ liệu hiện có.")
        return

    tong_to = kpi["tong_to"]
    tong_tot = kpi["to_tot"]
    tong_kha = kpi["to_kha"]
    tong_tb = kpi["to_tb"]
    tong_yeu = kpi["to_yeu"]
    diem_tb = kpi["diem_tb"]
    ty_le_dat = ((tong_tot + tong_kha) / tong_to * 100) if tong_to else 0.0
    ty_le_yeu_kem = (tong_yeu / tong_to * 100) if tong_to else 0.0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Tổng số Tổ", fmt_so(tong_to))
    c2.metric("Điểm TB toàn CN", f"{diem_tb:.2f}")
    c3.metric("% Đạt (Tốt+Khá)", f"{ty_le_dat:.1f}%")
    c4.metric("% Yếu+Kém", f"{ty_le_yeu_kem:.1f}%")

    def _render_xep_loai_card(col, label: str, count: int, bg: str, color: str) -> None:
        pct = (count / tong_to * 100) if tong_to else 0.0
        card_html = f"""
        <div style="background:{bg}; border-left:4px solid {color};
                    border-radius:8px; padding:12px 16px; text-align:center">
          <div style="font-size:11px; color:{color}; font-weight:600">{label}</div>
          <div style="font-size:24px; font-weight:700; color:{color}">{count}</div>
          <div style="font-size:13px; color:{color}">{pct:.1f}%</div>
        </div>
        """
        with col:
            st.markdown(card_html, unsafe_allow_html=True)

    c5, c6, c7, c8 = st.columns(4)
    _render_xep_loai_card(c5, "Tốt (≥90đ)", tong_tot, "#E8F5E9", "#2E7D32")
    _render_xep_loai_card(c6, "Khá (80-89)", tong_kha, "#F1F8E9", "#558B2F")
    _render_xep_loai_card(c7, "TB (70-79)", tong_tb, "#FFF8E1", "#F57F17")
    _render_xep_loai_card(c8, "Yếu (<70)", tong_yeu, "#FFEBEE", "#C62828")

    st.divider()
    fig_pie = go.Figure(go.Pie(
        labels=["Tốt", "Khá", "Trung bình", "Yếu"],
        values=[tong_tot, tong_kha, tong_tb, tong_yeu],
        marker_colors=["#2E7D32", "#66BB6A", "#F9A825", "#C62828"],
        textinfo="label+percent",
        textfont_size=12,
        hole=0.4,
        pull=[0, 0, 0, 0.08],
    ))
    fig_pie.update_layout(
        title="Phân bổ xếp loại Tổ TK&VV toàn Chi nhánh",
        height=320,
        margin=dict(t=40, b=10, l=10, r=10),
        legend=dict(orientation="h", y=-0.1),
        paper_bgcolor="rgba(0,0,0,0)",
    )

    col_pie, col_bang = st.columns([1, 2])
    with col_pie:
        st.plotly_chart(fig_pie, use_container_width=True)
    with col_bang:
        st.markdown("**Bảng tổng hợp theo Phòng giao dịch**")
        hien_thi_dataframe_phan_trang(
            th,
            key="cdtotkvv_tong_hop_pgd",
            column_config={
                "ma_dv":          st.column_config.TextColumn("Mã DV"),
                "ten_dv":         st.column_config.TextColumn("Tên đơn vị"),
                "tong_to":        st.column_config.NumberColumn("Tổng Tổ"),
                "tong_diem_tb":   st.column_config.NumberColumn("Điểm TB", format="%.1f"),
                "to_tot":         st.column_config.NumberColumn("Tốt"),
                "to_kha":         st.column_config.NumberColumn("Khá"),
                "to_tb":          st.column_config.NumberColumn("Trung bình"),
                "to_yeu":         st.column_config.NumberColumn("Yếu"),
                "to_tinh_trang_a": st.column_config.NumberColumn("TT A"),
                "to_tinh_trang_b": st.column_config.NumberColumn("TT B"),
                "to_tinh_trang_c": st.column_config.NumberColumn("TT C"),
            },
        )
    
    # Thông tin số đơn vị đã tổng hợp
    so_don_vi_co_data = len(th)
    st.caption(f"Đã tổng hợp: {so_don_vi_co_data} / 22 đơn vị")

    xlsx_bytes = xuat_excel({"Tong hop": th})
    st.download_button(
        label="⬇️ Xuất Excel",
        data=xlsx_bytes,
        file_name=ten_file_xuat("CDTOTKVV_TH_TapTrung"),
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key="cd_dl_excel",
    )
    db.ghi_audit(username, "xuat_excel_cdtotkvv", "tu_pgd_data")

def _sub_phan_tich_chat_luong(username: str, cdto_mode: str, pgd_user: str) -> None:
    """Sub-tab 3: Phân tích Chất lượng"""
    st.markdown("##### 📋 Phân tích Chất lượng Tổ TK&VV")
    
    ds = ds_thang_nam()
    if not ds:
        st.info("Chưa có file chấm điểm nào. Hãy upload ở tab Upload trước.")
        return

    thang_chon = st.selectbox("Chọn tháng", ds, key="cdto3_thang")
    
    try:
        df_raw = doc_cdtotkvv(thang_chon)
        if df_raw is None or df_raw.empty:
            st.warning(f"Không đọc được dữ liệu tháng {thang_chon}.")
            return
        
        df = _loc_df(df_raw, cdto_mode, pgd_user)
        if df.empty:
            st.warning("Không có dữ liệu cho PGD này.")
            return
            
    except Exception as e:
        logger.error("Lỗi trong khối except: %s", e, exc_info=True)
        st.warning(f"Lỗi đọc dữ liệu: {e}")
        return

    # Section A — 4 KPI cards
    tong_to = len(df)
    to_tot = len(df[df["xep_loai"] == _XEP_LOAI_TOT]) if "xep_loai" in df.columns else 0
    to_yeu = len(df[df["xep_loai"] == _XEP_LOAI_YEU]) if "xep_loai" in df.columns else 0
    diem_tb = df["tong_diem"].mean() if "tong_diem" in df.columns and not df["tong_diem"].isna().all() else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Tổng số Tổ", fmt_so(tong_to))
    c2.metric("% Tốt", f"{to_tot/tong_to*100:.1f}%" if tong_to else "—")
    c3.metric("% Yếu", f"{to_yeu/tong_to*100:.1f}%" if tong_to else "—")
    c4.metric("Điểm TB", f"{diem_tb:.2f}")

    st.divider()

    # Section B — Bảng tiêu chí bị trừ điểm
    st.markdown("**Tiêu chí bị trừ điểm**")

    tieu_chi_data = []
    for col, diem_max in _CDTOTKVV_DIEM_TOI_DA.items():
        if col not in df.columns:
            continue
        series = pd.to_numeric(df[col], errors="coerce").fillna(0)
        diem_tb = series.mean()
        bi_tru = round(diem_max - diem_tb, 2)
        so_to_khong_dat = len(series[series < diem_max])
        ty_le = so_to_khong_dat / tong_to * 100 if tong_to > 0 else 0
        if ty_le >= 50:
            muc_do = "🔴 Nghiêm trọng"
        elif ty_le >= 20:
            muc_do = "🟡 Cần cải thiện"
        else:
            muc_do = "🟢 Tốt"
        tieu_chi_data.append(
            {
                "Tiêu chí": _CDTOTKVV_TEN_HIEN_THI.get(col, col),
                "Điểm tối đa": diem_max,
                "Điểm TB": round(diem_tb, 2),
                "Bị trừ TB": bi_tru,
                "Số Tổ chưa đạt": so_to_khong_dat,
                "% Tổ chưa đạt": round(ty_le, 1),
                "Mức độ": muc_do,
            }
        )

    df_tc = pd.DataFrame(tieu_chi_data)
    df_tc = df_tc.sort_values("Bị trừ TB", ascending=False)

    ser_bi_tru = df_tc["Bị trừ TB"].copy()

    def highlight_rows(row):
        if ser_bi_tru.loc[row.name] > 2:
            return ["background-color: #ffebee"] * len(row)
        elif ser_bi_tru.loc[row.name] <= 0:
            return [""] * len(row)
        return [""] * len(row)

    df_tc["Điểm TB"] = df_tc["Điểm TB"].map(
        lambda x: f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    )
    df_tc["Bị trừ TB"] = df_tc["Bị trừ TB"].map(
        lambda x: f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    )
    df_tc["% Tổ chưa đạt"] = df_tc["% Tổ chưa đạt"].map(
        lambda x: f"{x:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".") + "%"
    )
    df_tc["Số Tổ chưa đạt"] = df_tc["Số Tổ chưa đạt"].map(
        lambda x: f"{int(x):,}".replace(",", ".")
    )

    if not df_tc.empty:
        hien_thi_dataframe_phan_trang(
            df_tc.style.apply(highlight_rows, axis=1),
            key="cdtotkvv_tieu_chi_tru_diem",
            column_config={
                "Tiêu chí": st.column_config.TextColumn("Tiêu chí"),
                "Điểm tối đa": st.column_config.NumberColumn("Điểm tối đa", format=",.0f"),
            },
        )
    else:
        st.info("Không có dữ liệu tiêu chí.")

    st.divider()

    # Section C — So sánh 2 tháng
    st.markdown("**So sánh 2 tháng**")
    
    thang_so_sanh = st.selectbox(
        "Chọn tháng so sánh",
        [t for t in ds if t != thang_chon],
        key="cdto3_thang2"
    )
    
    if thang_so_sanh:
        try:
            df2_raw = doc_cdtotkvv(thang_so_sanh)
            if df2_raw is not None and not df2_raw.empty:
                df2 = _loc_df(df2_raw, cdto_mode, pgd_user)
                
                # Tính chỉ số tháng 2
                tong_to2 = len(df2)
                to_yeu2 = len(df2[df2["xep_loai"] == _XEP_LOAI_YEU]) if "xep_loai" in df2.columns else 0
                to_tot2 = len(df2[df2["xep_loai"] == _XEP_LOAI_TOT]) if "xep_loai" in df2.columns else 0
                diem_tb2 = df2["tong_diem"].mean() if "tong_diem" in df2.columns and not df2["tong_diem"].isna().all() else 0
                
                # 4 st.metric với delta
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Tổng Tổ", fmt_so(tong_to), delta=f"{tong_to-tong_to2:+d}".replace(",","."))
                m2.metric("Tổ Yếu", fmt_so(to_yeu), delta=f"{to_yeu-to_yeu2:+d}".replace(",","."))
                m3.metric("Tổ Tốt", fmt_so(to_tot), delta=f"{to_tot-to_tot2:+d}".replace(",","."))
                m4.metric("Điểm TB", f"{diem_tb:.2f}", delta=f"{diem_tb - diem_tb2:+.2f}")
                
                # Bar chart nhóm xếp loại
                if "xep_loai" in df.columns and "xep_loai" in df2.columns:
                    # Tạo dữ liệu cho biểu đồ
                    thang1_counts = df["xep_loai"].value_counts()
                    thang2_counts = df2["xep_loai"].value_counts()
                    
                    xep_loai_list = [_XEP_LOAI_TOT, _XEP_LOAI_KHA, _XEP_LOAI_TB, _XEP_LOAI_YEU]
                    
                    chart_data = []
                    for xl in xep_loai_list:
                        chart_data.append({
                            "Xếp loại": xl,
                            "Tháng": thang_chon,
                            "Số lượng": thang1_counts.get(xl, 0)
                        })
                        chart_data.append({
                            "Xếp loại": xl,
                            "Tháng": thang_so_sanh,
                            "Số lượng": thang2_counts.get(xl, 0)
                        })
                    
                    chart_df = pd.DataFrame(chart_data)
                    
                    fig = px.bar(
                        chart_df,
                        x="Xếp loại",
                        y="Số lượng",
                        color="Tháng",
                        barmode="group",
                        title="So sánh xếp loại 2 tháng"
                    )
                    
                    # Update colors for xếp loại categories
                    fig.update_traces(marker_color="#1f77b4")  # Default blue for comparison
                    
                    st.plotly_chart(fig, use_container_width=True)
                
        except Exception as e:
            logger.error("Lỗi trong khối except: %s", e, exc_info=True)
            st.warning(f"Lỗi đọc dữ liệu tháng so sánh: {e}")

    # Xuất tổ không đạt tiêu chí (sau phần so sánh 2 tháng)
    _render_xuat_to_khong_dat_tieu_chi(df, username, thang_chon)


def _sub_ban_do_chat_luong(username: str, cdto_mode: str, pgd_user: str) -> None:
    """Sub-tab 4: Bản đồ Chất lượng"""
    st.markdown("##### 🗺️ Bản đồ Chất lượng Tổ TK&VV")
    
    ds = ds_thang_nam()
    if not ds:
        st.info("Chưa có file chấm điểm nào. Hãy upload ở tab Upload trước.")
        return

    thang_chon = st.selectbox("Chọn tháng", ds, key="cdto4_thang")
    
    try:
        df_raw = doc_cdtotkvv(thang_chon)
        if df_raw is None or df_raw.empty:
            st.warning(f"Không đọc được dữ liệu tháng {thang_chon}.")
            return
        
        df = _loc_df(df_raw, cdto_mode, pgd_user)
        if df.empty:
            st.warning("Không có dữ liệu cho PGD này.")
            return
            
    except Exception as e:
        logger.error("Lỗi trong khối except: %s", e, exc_info=True)
        st.warning(f"Lỗi đọc dữ liệu: {e}")
        return

    # Section A — Treemap PGD → Xã → Tổ
    st.markdown("**Treemap phân cấp**")
    
    if all(col in df.columns for col in ["ten_dv", "ten_xa", "ma_to", "tong_diem", "xep_loai"]):
        # Xác định path theo mode
        if cdto_mode == "pgd":
            path = ["ten_xa", "ma_to"]  # Ẩn cấp PGD
        else:
            path = ["ten_dv", "ten_xa", "ma_to"]
            
        # Chỉ giữ lại các hàng có đầy đủ dữ liệu cho treemap
        df_tree = df.dropna(subset=path + ["tong_diem", "xep_loai"]).copy()
        
        if not df_tree.empty:
            color_map = {
                _XEP_LOAI_TOT: "#2e7d32",
                _XEP_LOAI_KHA: "#66bb6a", 
                _XEP_LOAI_TB: "#f9a825",
                _XEP_LOAI_YEU: "#c62828"
            }
            
            fig_tree = px.treemap(
                df_tree,
                path=path,
                values="tong_diem",
                color="xep_loai",
                color_discrete_map=color_map,
                height=420,
                title="Kích vào ô để drill-down · Đỏ = Tổ Yếu cần chấn chỉnh"
            )
            
            st.plotly_chart(fig_tree, use_container_width=True)
        else:
            st.warning("Không có dữ liệu đầy đủ để vẽ treemap.")
    else:
        st.warning("Thiếu cột cần thiết để vẽ treemap.")

    st.divider()

    # Section B — Heatmap Table
    st.markdown("**Bảng heatmap theo đơn vị**")
    
    if cdto_mode == "pgd":
        # Chỉ hiện 1 PGD → dùng st.metric
        if "xep_loai" in df.columns:
            counts = df["xep_loai"].value_counts()
            tong_to = len(df)
            to_yeu = counts.get(_XEP_LOAI_YEU, 0)
            ty_le_yeu = to_yeu / tong_to * 100 if tong_to > 0 else 0
            
            m1, m2, m3, m4, m5 = st.columns(5)
            m1.metric("Tổng Tổ", fmt_so(tong_to))
            m2.metric("Tốt", fmt_so(counts.get(_XEP_LOAI_TOT, 0)))
            m3.metric("Khá", fmt_so(counts.get(_XEP_LOAI_KHA, 0)))
            m4.metric("Trung bình", fmt_so(counts.get(_XEP_LOAI_TB, 0)))
            m5.metric("Yếu", fmt_so(to_yeu), delta=f"{vn(ty_le_yeu,1)}%")
    else:
        # Hiển thị bảng đầy đủ các PGD
        if "ten_dv" in df.columns and "xep_loai" in df.columns:
            pivot = df.groupby("ten_dv")["xep_loai"].value_counts().unstack(fill_value=0)
            
            # Đảm bảo đủ 4 cột
            for xl in [_XEP_LOAI_TOT, _XEP_LOAI_KHA, _XEP_LOAI_TB, _XEP_LOAI_YEU]:
                if xl not in pivot.columns:
                    pivot[xl] = 0
            
            # Sắp xếp lại cột theo thứ tự
            pivot = pivot[[_XEP_LOAI_TOT, _XEP_LOAI_KHA, _XEP_LOAI_TB, _XEP_LOAI_YEU]]
            
            # Thêm cột tổng và tỷ lệ yếu
            pivot["tong_to"] = pivot.sum(axis=1)
            pivot["ty_le_yeu"] = (pivot[_XEP_LOAI_YEU] / pivot["tong_to"] * 100).round(1).fillna(0)
            
            # Áp dụng styling
            def style_heatmap(df: pd.DataFrame) -> pd.DataFrame.style:
                """Tô màu bảng heatmap thuần CSS, không cần matplotlib."""

                def mau_theo_nguong(val, col):
                    try:
                        v = float(val)
                    except (ValueError, TypeError):
                        return ""

                    # Cột % Yếu: cao = đỏ đậm, thấp = xanh nhạt
                    if col in ("ty_le_yeu", "to_yeu"):
                        if v == 0:
                            return "background-color:#e8f5e9; color:#1b5e20"
                        if v <= 5:
                            return "background-color:#f1f8e9; color:#33691e"
                        if v <= 15:
                            return "background-color:#fff9c4; color:#f57f17"
                        if v <= 25:
                            return "background-color:#ffe0b2; color:#e65100"
                        return "background-color:#ffcdd2; color:#b71c1c; font-weight:600"

                    # Cột % Tốt / số Tốt: cao = xanh đậm
                    if col in ("ty_le_tot", "to_tot"):
                        if v >= 80:
                            return "background-color:#1b5e20; color:#fff"
                        if v >= 60:
                            return "background-color:#388e3c; color:#fff"
                        if v >= 40:
                            return "background-color:#81c784; color:#1b5e20"
                        if v >= 20:
                            return "background-color:#c8e6c9; color:#1b5e20"
                        return ""

                    # Cột điểm TB: gradient xanh->vàng->đỏ
                    if col == "tong_diem_tb":
                        if v >= 90:
                            return "background-color:#e8f5e9; color:#1b5e20"
                        if v >= 80:
                            return "background-color:#f1f8e9; color:#33691e"
                        if v >= 70:
                            return "background-color:#fff9c4; color:#f57f17"
                        return "background-color:#ffcdd2; color:#b71c1c"

                    return ""

                def style_row(row):
                    return [mau_theo_nguong(row[c], c)
                            if c in row.index else ""
                            for c in row.index]

                return df.style.apply(style_row, axis=1)
            
            hien_thi_dataframe_phan_trang(
                style_heatmap(pivot),
                key="cdtotkvv_heatmap_pivot",
                hide_index=False,
            )

    st.divider()

    # Section C — Top Tổ Yếu
    st.markdown("**Top Tổ Yếu cần chấn chỉnh**")
    
    if "xep_loai" in df.columns:
        df_yeu = df[df["xep_loai"] == _XEP_LOAI_YEU].copy()
        
        if not df_yeu.empty:
            # Sắp xếp theo điểm tăng dần (yếu nhất trước)
            if "tong_diem" in df_yeu.columns:
                df_yeu = df_yeu.sort_values("tong_diem")
            
            # Thêm cột liên tiếp yếu
            df_yeu["Liên tiếp Yếu"] = "🟡 Tháng này"
            
            # Kiểm tra tháng liền trước
            ds_sorted = sorted(ds_thang_nam())
            try:
                idx_current = ds_sorted.index(thang_chon)
                if idx_current > 0:
                    thang_truoc = ds_sorted[idx_current - 1]
                    df_truoc = doc_cdtotkvv(thang_truoc)
                    if df_truoc is not None:
                        df_truoc_loc = _loc_df(df_truoc, cdto_mode, pgd_user)
                        ma_to_yeu_truoc = set(df_truoc_loc[df_truoc_loc["xep_loai"] == _XEP_LOAI_YEU]["ma_to"].astype(str))
                        
                        # Cập nhật cột liên tiếp yếu
                        for idx in df_yeu.index:
                            ma_to = str(df_yeu.loc[idx, "ma_to"])
                            if ma_to in ma_to_yeu_truoc:
                                df_yeu.loc[idx, "Liên tiếp Yếu"] = "🔴 2+ tháng"
            except Exception as e:
                logger.error("kiem_tra_lien_tiep_yeu: %s", e, exc_info=True)
            
            # Hiển thị bảng
            cols_hien = []
            col_mapping = {
                "ten_dv": "PGD",
                "ten_xa": "Xã", 
                "ma_to": "Mã Tổ",
                "tinh_trang": "Tình trạng",
                "tong_diem": "Điểm",
                "Liên tiếp Yếu": "Liên tiếp Yếu"
            }
            
            for col, label in col_mapping.items():
                if col in df_yeu.columns:
                    cols_hien.append(col)
            
            df_display = df_yeu[cols_hien].copy()
            df_display.index = range(1, len(df_display) + 1)  # STT từ 1
            
            # Đổi tên cột
            rename_dict = {col: col_mapping.get(col, col) for col in df_display.columns}
            df_display = df_display.rename(columns=rename_dict)
            
            hien_thi_dataframe_phan_trang(
                df_display,
                key="cdtotkvv_top_to_yeu",
                hide_index=True,
            )
            
            # Nút xuất Excel
            col_xuat, _ = st.columns([1, 2])
            with col_xuat:
                if st.button("⬇️ Xuất Excel Top Tổ Yếu", key="cdto4_xuat_yeu"):
                    try:
                        state = SCMStateManager()
                        state.downloads.set(
                            "cdtotkvv_to_yeu_excel",
                            xuat_excel({"To_Yeu": df_yeu}),
                            ten_file_xuat(f"ToYeu_{thang_chon}"),
                        )
                        db.ghi_audit(username, "xuat_excel_to_yeu", f"thang={thang_chon}")
                        st.cache_data.clear()
                        st.success("✅ Đã tạo file Excel!")
                    except Exception as e:
                        logger.error("Lỗi trong khối except: %s", e, exc_info=True)
                        st.error(f"Lỗi xuất Excel: {e}")

                state = SCMStateManager()
                if state.downloads.has("cdtotkvv_to_yeu_excel"):
                    if st.download_button(
                        label="📥 Tải file Excel",
                        data=state.downloads.get_bytes("cdtotkvv_to_yeu_excel"),
                        file_name=state.downloads.get_filename("cdtotkvv_to_yeu_excel") or ten_file_xuat(f"ToYeu_{thang_chon}"),
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key="cdto4_download_yeu"
                    ):
                        state.downloads.clear("cdtotkvv_to_yeu_excel")
        else:
            st.success("✅ Không có Tổ nào xếp loại Yếu!")
    else:
        st.warning("Không tìm thấy cột xếp loại.")

def _sub_xu_huong(username: str, cdto_mode: str, pgd_user: str) -> None:
    """Sub-tab 5: Xu hướng"""
    st.markdown("##### 📈 Xu hướng Chất lượng Tổ TK&VV")
    
    # Load tất cả tháng
    ds_thang = sorted(ds_thang_nam())  # Sort tăng dần để vẽ timeline
    if not ds_thang:
        st.info("Chưa có file chấm điểm nào. Hãy upload ở tab Upload trước.")
        return
    
    records = []
    for thang in ds_thang:
        try:
            df_t = doc_cdtotkvv(thang)
            if df_t is None or df_t.empty:
                continue
                
            df_t_loc = _loc_df(df_t, cdto_mode, pgd_user)
            if df_t_loc.empty:
                continue
                
            # Tính tổng hợp
            th = tong_hop_theo_pgd(df_t_loc)
            if th.empty:
                continue
                
            # Tổng hợp toàn bộ
            tong_to = th["tong_to"].sum()
            to_tot = th["to_tot"].sum() 
            to_kha = th["to_kha"].sum()
            to_tb = th["to_tb"].sum()
            to_yeu = th["to_yeu"].sum()
            diem_tb = th["tong_diem_tb"].mean()
            
            records.append({
                "thang": thang,
                "tong_to": tong_to,
                "to_tot": to_tot,
                "to_kha": to_kha, 
                "to_tb": to_tb,
                "to_yeu": to_yeu,
                "diem_tb": diem_tb
            })
        except Exception as e:
            logger.error("Lỗi trong khối except: %s", e, exc_info=True)
            st.warning(f"Lỗi xử lý tháng {thang}: {e}")
            continue
    
    if not records:
        st.warning("Không có dữ liệu xu hướng.")
        return
        
    df_trend = pd.DataFrame(records)

    # Section A — Line chart xếp loại theo tháng
    st.markdown("**Xu hướng xếp loại theo tháng**")
    
    fig_line = go.Figure()
    
    # 4 đường xếp loại
    colors = {
        "to_tot": "#2e7d32",
        "to_kha": "#66bb6a",
        "to_tb": "#f9a825", 
        "to_yeu": "#c62828"
    }
    
    labels = {
        "to_tot": "Tốt",
        "to_kha": "Khá", 
        "to_tb": "Trung bình",
        "to_yeu": "Yếu"
    }
    
    for col, color in colors.items():
        fig_line.add_trace(go.Scatter(
            x=df_trend["thang"],
            y=df_trend[col], 
            mode="lines+markers",
            name=labels[col],
            line=dict(color=color, width=3),
            marker=dict(size=8)
        ))
    
    # Annotation tại điểm cao nhất đường Yếu
    max_yeu_idx = df_trend["to_yeu"].idxmax()
    max_yeu = df_trend.loc[max_yeu_idx, "to_yeu"]
    max_yeu_thang = df_trend.loc[max_yeu_idx, "thang"]
    
    fig_line.add_annotation(
        x=max_yeu_thang,
        y=max_yeu,
        text=f"Max: {max_yeu}",
        showarrow=True,
        arrowhead=2,
        arrowcolor="#c62828",
        bgcolor="#ffebee",
        bordercolor="#c62828"
    )
    
    fig_line.update_layout(
        height=400,
        xaxis_title="Tháng",
        yaxis_title="Số Tổ", 
        legend=dict(orientation="h", y=1.02),
        hovermode="x unified"
    )
    
    st.plotly_chart(fig_line, use_container_width=True)

    st.divider()

    # Section B — Điểm TB từng PGD qua tháng (chỉ hiện nếu mode == "cn")
    if cdto_mode == "cn":
        st.markdown("**Điểm trung bình từng PGD qua tháng**")
        
        # Tính dữ liệu PGD theo tháng
        pgd_records = []
        for thang in ds_thang:
            try:
                df_t = doc_cdtotkvv(thang)
                if df_t is None or df_t.empty:
                    continue
                    
                th_pgd = tong_hop_theo_pgd(df_t)
                for _, row in th_pgd.iterrows():
                    pgd_records.append({
                        "thang": thang,
                        "pgd": row["ten_dv"],
                        "diem_tb": row["tong_diem_tb"]
                    })
            except Exception as e:
                logger.error("xu_huong_pgd_thang: %s", e, exc_info=True)
                continue

        if pgd_records:
            df_pgd_trend = pd.DataFrame(pgd_records)
            
            # Lấy 5 PGD có điểm TB thấp nhất tháng gần nhất làm mặc định
            thang_gan_nhat = ds_thang[-1]
            df_gan_nhat = df_pgd_trend[df_pgd_trend["thang"] == thang_gan_nhat]
            top5_pgd = df_gan_nhat.nsmallest(5, "diem_tb")["pgd"].tolist()
            
            ds_pgd_all = sorted(df_pgd_trend["pgd"].unique())
            chon_pgd = st.multiselect(
                "Chọn PGD để hiển thị xu hướng",
                ds_pgd_all,
                default=top5_pgd,
                key="cdto5_pgd_select"
            )
            
            if chon_pgd:
                df_pgd_filtered = df_pgd_trend[df_pgd_trend["pgd"].isin(chon_pgd)]
                
                fig_pgd = px.line(
                    df_pgd_filtered,
                    x="thang",
                    y="diem_tb",
                    color="pgd",
                    markers=True,
                    title="Điểm trung bình theo PGD"
                )
                
                fig_pgd.update_layout(height=400)
                st.plotly_chart(fig_pgd, use_container_width=True)

        st.divider()

    # Section C — Cảnh báo xu hướng xấu
    st.markdown("**Cảnh báo xu hướng xấu**")
    
    if len(df_trend) >= 3:  # Cần ít nhất 3 tháng để phát hiện xu hướng
        # Lấy 3 tháng gần nhất
        df_recent = df_trend.tail(3).reset_index(drop=True)
        
        canh_bao = []
        
        if cdto_mode == "cn":
            # Cảnh báo cho từng PGD
            if 'pgd_records' in locals() and pgd_records:
                df_pgd_recent = df_pgd_trend[df_pgd_trend["thang"].isin(df_recent["thang"].tolist())]
                
                for pgd in df_pgd_recent["pgd"].unique():
                    pgd_data = df_pgd_recent[df_pgd_recent["pgd"] == pgd].sort_values("thang")
                    if len(pgd_data) >= 2:
                        # Kiểm tra điểm giảm 2 tháng liên tiếp
                        diem_values = pgd_data["diem_tb"].tolist()
                        if len(diem_values) >= 2 and diem_values[-1] < diem_values[-2]:
                            if len(diem_values) >= 3 and diem_values[-2] < diem_values[-3]:
                                canh_bao.append(f"🔴 {pgd}: điểm giảm liên tiếp")
                
                # Kiểm tra Tổ Yếu tăng từ dữ liệu tháng
                for pgd in df_pgd_trend["pgd"].unique():
                    pgd_yeu_counts = []
                    for thang in df_recent["thang"].tolist():
                        try:
                            df_t = doc_cdtotkvv(thang)
                            if df_t is not None:
                                pgd_data = df_t[df_t["ten_dv"] == pgd]
                                yeu_count = len(pgd_data[pgd_data["xep_loai"] == _XEP_LOAI_YEU])
                                pgd_yeu_counts.append(yeu_count)
                        except Exception as e:
                            logger.error("canh_bao_to_yeu: %s", e, exc_info=True)
                            continue

                    if len(pgd_yeu_counts) >= 2:
                        if pgd_yeu_counts[-1] > pgd_yeu_counts[-2]:
                            if len(pgd_yeu_counts) >= 3 and pgd_yeu_counts[-2] > pgd_yeu_counts[-3]:
                                canh_bao.append(f"⚠️ {pgd}: Tổ Yếu tăng liên tiếp")
        else:
            # Cảnh báo chỉ cho PGD hiện tại
            if len(df_recent) >= 2:
                if df_recent.loc[2, "diem_tb"] < df_recent.loc[1, "diem_tb"] < df_recent.loc[0, "diem_tb"]:
                    canh_bao.append(f"🔴 {pgd_user}: điểm giảm liên tiếp")
                
                if df_recent.loc[2, "to_yeu"] > df_recent.loc[1, "to_yeu"] > df_recent.loc[0, "to_yeu"]:
                    canh_bao.append(f"⚠️ {pgd_user}: Tổ Yếu tăng liên tiếp")
        
        if canh_bao:
            for cb in canh_bao:
                if cb.startswith("🔴"):
                    st.warning(cb)
                else:
                    st.error(cb)
        else:
            st.success("✅ Không có xu hướng xấu nào được phát hiện.")
    else:
        st.info("Cần ít nhất 3 tháng dữ liệu để phát hiện xu hướng.")

def render(tab: DeltaGenerator | None = None, **kwargs) -> None:
    """
    Render tab Chấm điểm Tổ TK&VV.

    Args:
        tab: Streamlit DeltaGenerator cho tab này
        **kwargs: Chứa role, username, cdto_mode, pgd_user
    """
    role: str = normalize_role(str(kwargs.get("role", "")))
    username: str = str(kwargs.get("username", "unknown"))
    cdto_mode: str = str(kwargs.get("cdto_mode", "cn"))  # "cn" hoặc "pgd"
    pgd_user: str = str(kwargs.get("pgd_user", ""))

    _tab_ctx = tab if tab is not None else __import__('streamlit').container()
    with _tab_ctx:
        # Kiểm tra phân quyền — chỉ cho phép CN và PGD roles
        if not la_phan_he_cn(role) and not la_phan_he_pgd(role):
            st.error("Bạn không có quyền truy cập trang này.")
            return

        # Tiêu đề khác nhau theo mode
        if cdto_mode == "pgd":
            st.subheader("🏘️ Tổ TK&VV")
            st.caption(f"Quản lý chấm điểm Tổ Tiết kiệm & Vay vốn - {pgd_user}")
        else:
            st.subheader("🏘️ Mạng lưới Tổ TK&VV")
            st.caption("Quản lý và xem tổng hợp chấm điểm Tổ Tiết kiệm & Vay vốn toàn chi nhánh")

        # Tạo 5 sub-tabs
        if cdto_mode == "cn" and la_phan_he_cn(role):
            _cdto_labels = ["📤 Upload", "📊 Tổng hợp", "📋 Phân tích Chất lượng",
                            "🗺️ Bản đồ Chất lượng", "📈 Xu hướng"]
        else:
            _cdto_labels = ["📋 Phân tích Chất lượng", "🗺️ Bản đồ Chất lượng", "📈 Xu hướng"]
        _cdto_sel = st.radio("", range(len(_cdto_labels)), format_func=lambda i: _cdto_labels[i],
                             horizontal=True, key="cdto_sub_tab", label_visibility="collapsed")
        st.divider()
        if cdto_mode == "cn" and la_phan_he_cn(role):
            if _cdto_sel == 0:   _sub_upload(role, username)
            elif _cdto_sel == 1: _sub_tong_hop(username)
            elif _cdto_sel == 2: _sub_phan_tich_chat_luong(username, cdto_mode, pgd_user)
            elif _cdto_sel == 3: _sub_ban_do_chat_luong(username, cdto_mode, pgd_user)
            elif _cdto_sel == 4: _sub_xu_huong(username, cdto_mode, pgd_user)
        else:
            if _cdto_sel == 0:   _sub_phan_tich_chat_luong(username, cdto_mode, pgd_user)
            elif _cdto_sel == 1: _sub_ban_do_chat_luong(username, cdto_mode, pgd_user)
            elif _cdto_sel == 2: _sub_xu_huong(username, cdto_mode, pgd_user)
