"""
Tab Chấm điểm Tổ TK&VV — ws_operation: chỉ dữ liệu upload của PGD (pgd_data).
"""
from __future__ import annotations

import os
import re
import socket
from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import db
from config import CDTOTKVV_COLS
from data.cdtotkvv import (
    doc_cdtotkvv_pgd,
    doc_cdtotkvv_path,
    doc_thang_nam_tu_file,
    tong_hop_theo_pgd,
    _XEP_LOAI_KHA,
    _XEP_LOAI_TB,
    _XEP_LOAI_TOT,
    _XEP_LOAI_YEU,
)
from data.core import ts_file
from data.pgd import duong_dan_pgd, luu_file_pgd_voi_lich_su
from utils import fmt, fmt_so, hien_thi_dataframe_phan_trang, ten_file_xuat, xuat_excel

if TYPE_CHECKING:
    from streamlit.delta_generator import DeltaGenerator


def _sort_label_thang(label: str) -> tuple[int, int]:
    mm, yyyy = label.split("/")
    return int(yyyy), int(mm)


def _doc_df(pgd_user: str) -> pd.DataFrame | None:
    """Đọc cdtotkvv_latest.xlsx của PGD. Trả về None nếu chưa có file."""
    path = duong_dan_pgd(pgd_user, "cdtotkvv")
    if not path or not os.path.exists(path):
        return None
    return doc_cdtotkvv_pgd(pgd_user, ts_file(path))


def _doc_lich_su(pgd_user: str) -> dict[str, pd.DataFrame]:
    """
    Quét pgd_data/{pgd}/ tìm các file cdtotkvv_{yyyy}_{mm}.xlsx.
    Trả về dict {"MM/YYYY": DataFrame} sort tăng dần theo thời gian.
    """
    thu_muc = Path(duong_dan_pgd(pgd_user, "cdtotkvv")).parent
    pat = re.compile(r"cdtotkvv_(\d{4})_(\d{2})\.xlsx$", re.IGNORECASE)
    ket_qua: dict[str, pd.DataFrame] = {}
    if not thu_muc.exists():
        return ket_qua
    for f in sorted(thu_muc.iterdir()):
        if not f.is_file():
            continue
        m = pat.match(f.name)
        if not m:
            continue
        yyyy, mm = m.group(1), m.group(2)
        label = f"{int(mm):02d}/{yyyy}"
        try:
            df = doc_cdtotkvv_path(str(f), ts_file(str(f)))
        except Exception:
            continue
        if df is None or df.empty:
            continue
        ket_qua[label] = df
    return dict(sorted(ket_qua.items(), key=lambda kv: _sort_label_thang(kv[0])))


def _sub_upload(pgd_user: str, username: str) -> None:
    st.markdown(f"##### 📤 Upload file Chấm điểm Tổ TK&VV — {pgd_user}")

    path = duong_dan_pgd(pgd_user, "cdtotkvv")
    if path and os.path.exists(path):
        import datetime

        ts = os.path.getmtime(path)
        ngay = datetime.datetime.fromtimestamp(ts).strftime("%d/%m/%Y %H:%M")
        st.success(f"✅ Đã có file · Cập nhật lần cuối: {ngay}")
    else:
        st.warning("⚠️ Chưa có file CDTOTKVV. Vui lòng upload.")

    st.divider()

    f = st.file_uploader(
        "Chọn file Excel Chấm điểm Tổ TK&VV",
        type=["xlsx", "xls"],
        key="cdtotkvv_pgd_uploader",
    )
    if f is not None:
        if st.button("📤 Upload", type="primary", key="cdtotkvv_pgd_btn"):
            file_bytes = f.read()

            # Đọc tháng từ nội dung file
            thang_tu_file = doc_thang_nam_tu_file(file_bytes)

            if thang_tu_file:
                # Lưu song song latest + lịch sử yyyy_mm
                path = luu_file_pgd_voi_lich_su(pgd_user, "cdtotkvv", file_bytes, thang_tu_file)
                db.ghi_audit(username, "upload_cdtotkvv_pgd",
                             f"{pgd_user} · tháng {thang_tu_file}")
                st.success(f"✅ Đã lưu · Tháng {thang_tu_file} · Đã lưu lịch sử")
            else:
                # Fallback: chỉ lưu latest nếu không đọc được tháng
                from data.pgd import luu_file_pgd

                path = luu_file_pgd(pgd_user, "cdtotkvv", file_bytes)
                db.ghi_audit(username, "upload_cdtotkvv_pgd", pgd_user)
                st.warning("⚠️ Đã lưu nhưng không đọc được tháng từ file — "
                           "không lưu lịch sử. Kiểm tra lại file.")

            st.cache_data.clear()
            st.rerun()


def _sub_phan_tich(pgd_user: str, username: str) -> None:
    st.markdown("##### 📋 Phân tích Chất lượng Tổ TK&VV")

    df = _doc_df(pgd_user)
    if df is None or df.empty:
        st.info("Chưa có dữ liệu. Vui lòng upload file CDTOTKVV ở tab Upload.")
        return

    lich_su = _doc_lich_su(pgd_user)
    ds_thang = sorted(lich_su.keys(), key=_sort_label_thang)

    # —— 4 KPI ——
    tong_to = len(df)
    to_tot = len(df[df["xep_loai"] == _XEP_LOAI_TOT]) if "xep_loai" in df.columns else 0
    to_yeu = len(df[df["xep_loai"] == _XEP_LOAI_YEU]) if "xep_loai" in df.columns else 0
    diem_tb = (
        df["tong_diem"].mean()
        if "tong_diem" in df.columns and not df["tong_diem"].isna().all()
        else 0
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Tổng số Tổ", fmt_so(tong_to))
    c2.metric("% Tốt", f"{to_tot / tong_to * 100:.1f}%" if tong_to else "—")
    c3.metric("% Yếu", f"{to_yeu / tong_to * 100:.1f}%" if tong_to else "—")
    c4.metric("Điểm TB", f"{diem_tb:.2f}")

    st.divider()

    # —— Tiêu chí trừ điểm ——
    st.markdown("**Tiêu chí bị trừ điểm**")

    cot_tru_diem: list[str] = []
    for col in df.columns:
        if col in CDTOTKVV_COLS and col not in [
            "stt",
            "ma_dv",
            "ten_dv",
            "ma_xa",
            "ten_xa",
            "ma_to",
            "ten_to_truong",
            "dvut",
            "loai_to",
            "du_no",
            "so_du_tk",
            "tong_diem",
            "xep_loai",
            "tinh_trang",
        ]:
            try:
                col_sum = pd.to_numeric(df[col], errors="coerce").sum()
                col_lower = str(col).lower()
                if col_sum < 0 or "tru" in col_lower or "phat" in col_lower:
                    cot_tru_diem.append(col)
            except Exception:
                continue

    if cot_tru_diem:
        tieu_chi_data = []
        for col in cot_tru_diem:
            df_numeric = pd.to_numeric(df[col], errors="coerce").fillna(0)
            so_to_bi_anh_huong = len(df[df_numeric != 0])
            tong_diem_tru = float(df_numeric.sum())
            ty_le_anh_huong = so_to_bi_anh_huong / tong_to * 100 if tong_to > 0 else 0

            tieu_chi_data.append(
                {
                    "Tiêu chí": col,
                    "Số Tổ bị ảnh hưởng": so_to_bi_anh_huong,
                    "Tổng điểm trừ": tong_diem_tru,
                    "% Tổ bị ảnh hưởng": ty_le_anh_huong,
                }
            )

        df_tieu_chi = pd.DataFrame(tieu_chi_data)
        df_tieu_chi = df_tieu_chi.sort_values("Số Tổ bị ảnh hưởng", ascending=False)

        def highlight_rows(row: pd.Series):
            if row["% Tổ bị ảnh hưởng"] > 20:
                return ["background-color: #ffebee"] * len(row)
            return [""] * len(row)

        hien_thi_dataframe_phan_trang(
            df_tieu_chi.style.apply(highlight_rows, axis=1),
            key="cdtotkvv_pgd_tieu_chi_tru_diem",
        )
    else:
        st.info("Không tìm thấy cột điểm trừ nào.")

    st.divider()

    # —— So sánh 2 kỳ (từ lịch sử file theo tháng) ——
    st.markdown("**So sánh 2 tháng**")
    if len(ds_thang) >= 2:
        thang_chon = st.selectbox("Tháng thứ nhất", ds_thang, key="cdtotkvv_pgd_thang1")
        thang2_opts = [t for t in ds_thang if t != thang_chon]
        thang_so_sanh = st.selectbox(
            "Chọn tháng so sánh",
            thang2_opts,
            key="cdtotkvv_pgd_thang2",
        )
        df_raw = lich_su.get(thang_chon)
        df2_raw = lich_su.get(thang_so_sanh)
        if df_raw is not None and df2_raw is not None and not df_raw.empty and not df2_raw.empty:
            tong_to1 = len(df_raw)
            to_yeu1 = (
                len(df_raw[df_raw["xep_loai"] == _XEP_LOAI_YEU])
                if "xep_loai" in df_raw.columns
                else 0
            )
            to_tot1 = (
                len(df_raw[df_raw["xep_loai"] == _XEP_LOAI_TOT])
                if "xep_loai" in df_raw.columns
                else 0
            )
            diem_tb1 = (
                df_raw["tong_diem"].mean()
                if "tong_diem" in df_raw.columns and not df_raw["tong_diem"].isna().all()
                else 0
            )

            tong_to2 = len(df2_raw)
            to_yeu2 = (
                len(df2_raw[df2_raw["xep_loai"] == _XEP_LOAI_YEU])
                if "xep_loai" in df2_raw.columns
                else 0
            )
            to_tot2 = (
                len(df2_raw[df2_raw["xep_loai"] == _XEP_LOAI_TOT])
                if "xep_loai" in df2_raw.columns
                else 0
            )
            diem_tb2 = (
                df2_raw["tong_diem"].mean()
                if "tong_diem" in df2_raw.columns and not df2_raw["tong_diem"].isna().all()
                else 0
            )

            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Tổng Tổ", fmt_so(tong_to1), delta=f"{tong_to1 - tong_to2:+d}")
            m2.metric("Tổ Yếu", fmt_so(to_yeu1), delta=f"{to_yeu1 - to_yeu2:+d}")
            m3.metric("Tổ Tốt", fmt_so(to_tot1), delta=f"{to_tot1 - to_tot2:+d}")
            m4.metric("Điểm TB", f"{diem_tb1:.2f}", delta=f"{diem_tb1 - diem_tb2:+.2f}")

            if "xep_loai" in df_raw.columns and "xep_loai" in df2_raw.columns:
                thang1_counts = df_raw["xep_loai"].value_counts()
                thang2_counts = df2_raw["xep_loai"].value_counts()
                xep_loai_list = [_XEP_LOAI_TOT, _XEP_LOAI_KHA, _XEP_LOAI_TB, _XEP_LOAI_YEU]
                chart_data = []
                for xl in xep_loai_list:
                    chart_data.append(
                        {"Xếp loại": xl, "Tháng": thang_chon, "Số lượng": thang1_counts.get(xl, 0)}
                    )
                    chart_data.append(
                        {
                            "Xếp loại": xl,
                            "Tháng": thang_so_sanh,
                            "Số lượng": thang2_counts.get(xl, 0),
                        }
                    )
                chart_df = pd.DataFrame(chart_data)
                fig = px.bar(
                    chart_df,
                    x="Xếp loại",
                    y="Số lượng",
                    color="Tháng",
                    barmode="group",
                    title="So sánh xếp loại 2 tháng",
                )
                fig.update_traces(marker_color="#1f77b4")
                st.plotly_chart(fig, use_container_width=True)
    else:
        st.info(
            "Cần ít nhất **2 tháng** đã lưu trong lịch sử upload (file cdtotkvv_YYYY_MM.xlsx) "
            "để so sánh hai kỳ."
        )

    st.divider()

    # —— Top Tổ Yếu (theo file mới nhất) ——
    st.markdown("**Top Tổ Yếu cần chấn chỉnh**")
    if "xep_loai" in df.columns:
        df_yeu = df[df["xep_loai"] == _XEP_LOAI_YEU].copy()
        if not df_yeu.empty:
            if "tong_diem" in df_yeu.columns:
                df_yeu = df_yeu.sort_values("tong_diem")
            df_yeu["Liên tiếp Yếu"] = "🟡 Tháng này"

            if len(ds_thang) >= 1:
                thang_truoc = ds_thang[-1]
                df_truoc = lich_su.get(thang_truoc)
                if df_truoc is not None and not df_truoc.empty:
                    df_truoc_yeu = df_truoc[df_truoc["xep_loai"] == _XEP_LOAI_YEU]
                    if "ma_to" in df_truoc_yeu.columns:
                        ma_to_yeu_truoc = set(df_truoc_yeu["ma_to"].astype(str))
                        for idx in df_yeu.index:
                            ma_to = str(df_yeu.loc[idx, "ma_to"])
                            if ma_to in ma_to_yeu_truoc:
                                df_yeu.loc[idx, "Liên tiếp Yếu"] = "🔴 2+ tháng"

            col_mapping = {
                "ten_dv": "PGD",
                "ten_xa": "Xã",
                "ma_to": "Mã Tổ",
                "tinh_trang": "Tình trạng",
                "tong_diem": "Điểm",
                "Liên tiếp Yếu": "Liên tiếp Yếu",
            }
            cols_hien = [c for c in col_mapping if c in df_yeu.columns]
            df_display = df_yeu[cols_hien].copy()
            df_display.index = range(1, len(df_display) + 1)
            df_display = df_display.rename(columns={c: col_mapping[c] for c in df_display.columns})

            hien_thi_dataframe_phan_trang(
                df_display,
                key="cdtotkvv_pgd_top_to_yeu",
                hide_index=True,
            )

            col_xuat, _ = st.columns([1, 2])
            with col_xuat:
                if st.button("⬇️ Xuất Excel Top Tổ Yếu", key="cdtotkvv_pgd_xuat_yeu"):
                    try:
                        xlsx_bytes = xuat_excel({"To_Yeu": df_yeu})
                        st.download_button(
                            label="📥 Tải file Excel",
                            data=xlsx_bytes,
                            file_name=ten_file_xuat(f"ToYeu_{pgd_user}"),
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            key="cdtotkvv_pgd_download_yeu",
                        )
                        hostname = socket.gethostname()
                        db.ghi_audit(
                            username,
                            "xuat_excel_to_yeu",
                            f"[{hostname}] cdtotkvv_pgd {pgd_user}",
                        )
                        st.success("✅ Đã tạo file Excel!")
                    except Exception as e:
                        st.error(f"Lỗi xuất Excel: {e}")
        else:
            st.success("✅ Không có Tổ nào xếp loại Yếu!")
    else:
        st.warning("Không tìm thấy cột xếp loại.")


def _sub_xu_huong(pgd_user: str, _username: str) -> None:
    st.markdown("##### 📈 Xu hướng theo tháng")

    lich_su = _doc_lich_su(pgd_user)
    if len(lich_su) < 2:
        st.info(
            "Cần ít nhất 2 tháng dữ liệu để xem xu hướng. "
            "Hãy upload file các tháng trước ở tab Upload (hệ thống lưu cdtotkvv_YYYY_MM.xlsx)."
        )
        return

    records = []
    for thang in sorted(lich_su.keys(), key=_sort_label_thang):
        try:
            df_t = lich_su[thang]
            if df_t is None or df_t.empty:
                continue
            th = tong_hop_theo_pgd(df_t)
            if th.empty:
                continue
            tong_to = int(th["tong_to"].sum())
            to_tot = int(th["to_tot"].sum())
            to_kha = int(th["to_kha"].sum())
            to_tb = int(th["to_tb"].sum())
            to_yeu = int(th["to_yeu"].sum())
            diem_tb = float(th["tong_diem_tb"].mean())
            pct_tot = round(to_tot / tong_to * 100, 2) if tong_to else 0.0
            pct_yeu = round(to_yeu / tong_to * 100, 2) if tong_to else 0.0
            records.append(
                {
                    "thang": thang,
                    "tong_to": tong_to,
                    "to_tot": to_tot,
                    "to_kha": to_kha,
                    "to_tb": to_tb,
                    "to_yeu": to_yeu,
                    "diem_tb": diem_tb,
                    "pct_tot": pct_tot,
                    "pct_yeu": pct_yeu,
                }
            )
        except Exception as e:
            st.warning(f"Lỗi xử lý tháng {thang}: {e}")
            continue

    if not records:
        st.warning("Không có dữ liệu xu hướng.")
        return

    df_trend = pd.DataFrame(records)

    st.markdown("**Xu hướng xếp loại theo tháng**")
    fig_line = go.Figure()
    colors = {
        "to_tot": "#2e7d32",
        "to_kha": "#66bb6a",
        "to_tb": "#f9a825",
        "to_yeu": "#c62828",
    }
    labels = {
        "to_tot": "Tốt",
        "to_kha": "Khá",
        "to_tb": "Trung bình",
        "to_yeu": "Yếu",
    }
    for col, color in colors.items():
        fig_line.add_trace(
            go.Scatter(
                x=df_trend["thang"],
                y=df_trend[col],
                mode="lines+markers",
                name=labels[col],
                line=dict(color=color, width=3),
                marker=dict(size=8),
            )
        )
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
        bordercolor="#c62828",
    )
    fig_line.update_layout(
        height=400,
        xaxis_title="Tháng",
        yaxis_title="Số Tổ",
        legend=dict(orientation="h", y=1.02),
        hovermode="x unified",
    )
    st.plotly_chart(fig_line, use_container_width=True)

    st.divider()
    st.markdown("**Điểm trung bình & tỷ lệ Tốt / Yếu theo tháng**")
    fig_ty = go.Figure()
    fig_ty.add_trace(
        go.Scatter(
            x=df_trend["thang"],
            y=df_trend["diem_tb"],
            name="Điểm TB",
            mode="lines+markers",
            line=dict(color="#1565c0", width=3),
            yaxis="y",
        )
    )
    fig_ty.add_trace(
        go.Scatter(
            x=df_trend["thang"],
            y=df_trend["pct_tot"],
            name="% Tốt",
            mode="lines+markers",
            line=dict(color="#2e7d32", width=2, dash="dot"),
            yaxis="y2",
        )
    )
    fig_ty.add_trace(
        go.Scatter(
            x=df_trend["thang"],
            y=df_trend["pct_yeu"],
            name="% Yếu",
            mode="lines+markers",
            line=dict(color="#c62828", width=2, dash="dot"),
            yaxis="y2",
        )
    )
    fig_ty.update_layout(
        height=420,
        xaxis_title="Tháng",
        yaxis=dict(title="Điểm TB", side="left", showgrid=True),
        yaxis2=dict(
            title="Tỷ lệ %",
            overlaying="y",
            side="right",
            showgrid=False,
            range=[0, 100],
        ),
        legend=dict(orientation="h", y=1.05),
        hovermode="x unified",
    )
    st.plotly_chart(fig_ty, use_container_width=True)

    st.divider()
    st.markdown("**Cảnh báo xu hướng xấu**")
    if len(df_trend) >= 3:
        df_recent = df_trend.tail(3).reset_index(drop=True)
        canh_bao: list[str] = []
        if len(df_recent) >= 2:
            if (
                df_recent.loc[2, "diem_tb"]
                < df_recent.loc[1, "diem_tb"]
                < df_recent.loc[0, "diem_tb"]
            ):
                canh_bao.append(f"🔴 {pgd_user}: điểm giảm liên tiếp")
            if (
                df_recent.loc[2, "to_yeu"]
                > df_recent.loc[1, "to_yeu"]
                > df_recent.loc[0, "to_yeu"]
            ):
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


@st.cache_data(show_spinner=False, ttl=300)
def _tinh_no_den_han(_df_bytes: bytes, ngay_tu: str, ngay_den: str) -> bytes:
    import pickle, pandas as pd
    df = pickle.loads(_df_bytes)
    from config import COT_NGAY_DH, COT_TEN_TO, COT_DVUT
    from config import COT_TEN_KH, COT_SO_KU, COT_TEN_CT, COT_TONG_DU_NO
    cols_can = [COT_TEN_TO, COT_DVUT, COT_TEN_KH,
                COT_SO_KU, COT_TEN_CT, COT_NGAY_DH, COT_TONG_DU_NO]
    cols_co  = [c for c in cols_can if c in df.columns]
    if COT_NGAY_DH not in df.columns:
        return pickle.dumps(pd.DataFrame())
    ngay_dh = pd.to_datetime(df[COT_NGAY_DH], errors="coerce")
    mask    = (ngay_dh >= pd.Timestamp(ngay_tu)) & \
              (ngay_dh <= pd.Timestamp(ngay_den))
    result  = df.loc[mask, cols_co].copy()
    result  = result.sort_values(COT_NGAY_DH)
    return pickle.dumps(result)


def render(tab: DeltaGenerator, **kwargs) -> None:
    role = kwargs.get("role", "user")
    username = kwargs.get("username", "unknown")
    pgd_user = kwargs.get("pgd_user", "")

    with tab:
        if role not in ("admin", "manager", "user",
                        "admin_cn", "manager_cn",
                        "admin_pgd", "manager_pgd", "user_pgd"):
            st.error("Bạn không có quyền truy cập trang này.")
            return

        if not pgd_user:
            st.warning("Không xác định được PGD. Liên hệ Admin.")
            return

        st.subheader(f"🏘️ Tổ TK&VV — {pgd_user}")
        st.caption("Dữ liệu từ file upload riêng của PGD · Độc lập với hệ thống tập trung")

        sub1, sub2, sub3, sub_ndh = st.tabs(
            [
                "📤 Upload",
                "📋 Phân tích Chất lượng",
                "📈 Xu hướng",
                "📅 Nợ đến hạn",
            ]
        )
        with sub1:
            _sub_upload(pgd_user, username)
        with sub2:
            _sub_phan_tich(pgd_user, username)
        with sub3:
            _sub_xu_huong(pgd_user, username)
        with sub_ndh:
            import pickle
            from datetime import date, timedelta
            from config import COT_NGAY_DH, COT_TEN_TO, COT_TONG_DU_NO

            st.markdown("#### 📅 Nợ đến hạn trong 30 ngày tới")

            so_ngay = st.slider("Xem trong", 7, 60, 30,
                          key="ndh_so_ngay", format="%d ngày")
            ngay_tu  = date.today()
            ngay_den = date.today() + timedelta(days=so_ngay)
            st.caption(
                f"Từ {ngay_tu.strftime('%d/%m/%Y')} "
                f"đến {ngay_den.strftime('%d/%m/%Y')}"
            )

            # Lấy df — đã lọc theo PGD ở cấp ws_operation
            df_src = kwargs.get("df") if kwargs else None
            if df_src is None or df_src.empty:
                st.warning("Chưa có dữ liệu HSTD.")
            elif COT_NGAY_DH not in df_src.columns:
                st.warning(f"Không tìm thấy cột ngày đến hạn.")
            else:
                try:
                    raw    = _tinh_no_den_han(
                                 pickle.dumps(df_src),
                                 str(ngay_tu), str(ngay_den))
                    df_ndh = pickle.loads(raw)
                except Exception as e:
                    st.error(f"Lỗi: {e}")
                    df_ndh = pd.DataFrame()

                if df_ndh.empty:
                    st.success(
                        f"✅ Không có món vay nào đến hạn "
                        f"trong {so_ngay} ngày tới.")
                else:
                    tong_dn = df_ndh[COT_TONG_DU_NO].sum() \
                              if COT_TONG_DU_NO in df_ndh.columns else 0
                    c1, c2 = st.columns(2)
                    c1.metric("Số món đến hạn", fmt_so(len(df_ndh)))
                    c2.metric("Tổng dư nợ (tr.đ)", fmt(tong_dn))

                    st.dataframe(df_ndh, use_container_width=True,
                                 hide_index=True)

                    # Xuất Excel
                    ten_file = (f"NoDenHan_"
                                f"{ngay_tu.strftime('%d%m%Y')}.xlsx")
                    buf = xuat_excel({"NoDenHan": df_ndh})
                    st.download_button(
                        f"⬇️ Xuất Excel ({len(df_ndh)} món)",
                        data=buf, file_name=ten_file,
                        mime="application/vnd.openxmlformats-"
                             "officedocument.spreadsheetml.sheet",
                        key="ndh_xuat_excel",
                    )
