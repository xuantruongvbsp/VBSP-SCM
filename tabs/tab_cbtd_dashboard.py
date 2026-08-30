"""
Tab Dashboard CBTD & Địa bàn — Tổng quan nhóm CBTD + ĐGD + Tổ TK&VV (NÂNG CẤP).

Hiển thị:
  - Row 1 : KPI cards (số CBTD, ĐGD, Tổ, điểm TB, %, workload)
  - Row 1b: Bộ lọc tương tác PGD / Xã / CBTD
  - Row 2 : Cảnh báo thông minh (7 loại) + bộ lọc loại cảnh báo
  - Row 3 : 4 Biểu đồ Plotly nâng cao
  - Row 4 : Bảng xếp hạng CBTD (scorecard)
  - Row 5 : Bảng pivot CBTD → ĐGD → Tổ → điểm
  - Row 6 : Xuất báo cáo cross-mảng (Excel nhiều sheet + xếp hạng CBTD)
"""
from __future__ import annotations

from io import BytesIO
from datetime import datetime
from typing import TYPE_CHECKING

import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

import db
from logger import get_logger
from auth import la_phan_he_cn, la_executive, normalize_role
from components.delta_card import kpi_row
from data.khtd import doc_cbtd
from tabs.base_tab import TabContext
from utils import fmt_so, fmt_ty, hien_thi_dataframe_phan_trang, xuat_excel
from services.cbtd_dia_ban_service import (
    canh_bao_cbtd_dia_ban,
    lay_to_theo_cbtd,
    tom_tat_kpi,
    xep_hang_cbtd,
    danh_gia_workload_cbtd,
    phan_tich_xu_huong_to,
)

logger = get_logger(__name__)

if TYPE_CHECKING:
    from streamlit.delta_generator import DeltaGenerator

_VBSP_GREEN = "#1B5E20"
_VBSP_GREEN_LIGHT = "#C8E6C9"
_VBSP_ACCENT = "#4CAF50"
_VBSP_RED = "#C62828"
_VBSP_ORANGE = "#EF6C00"
_VBSP_GREY = "#757575"


def _doc_cdtotkvv_moi_nhat() -> "pd.DataFrame | None":
    """Đọc file CDTOTKVV tháng gần nhất (tập trung từ pgd_data)."""
    try:
        from services.cdtotkvv_service import tong_hop_tu_pgd_data
        return tong_hop_tu_pgd_data()
    except Exception as e:
        logger.error("_doc_cdtotkvv_moi_nhat: lỗi đọc CDTOTKVV — %s", e, exc_info=True)
        return None


def _doc_cdtotkvv_ky_goc() -> "pd.DataFrame | None":
    """Đọc CDTOTKVV kỳ gốc: tháng 12 năm trước, fallback kỳ cũ nhất."""
    try:
        from data.cdtotkvv import doc_cdtotkvv, ds_thang_nam

        def _sort_key(s: str) -> tuple:
            try:
                mm, yyyy = s.split("/")
                return (int(yyyy), int(mm))
            except (ValueError, IndexError):
                return (0, 0)

        ds = sorted(ds_thang_nam(), key=_sort_key)
        if not ds:
            return None
        latest = ds[-1]
        try:
            mm_l, yyyy_l = latest.split("/")
            moc = f"12/{int(yyyy_l) - 1}"
        except (ValueError, IndexError):
            return doc_cdtotkvv(ds[0])
        if moc in ds:
            return doc_cdtotkvv(moc)
        for ky in reversed(ds):
            try:
                mm_k, yyyy_k = ky.split("/")
                if (int(yyyy_k), int(mm_k)) <= (int(yyyy_l) - 1, 12):
                    return doc_cdtotkvv(ky)
            except (ValueError, IndexError):
                continue
        return doc_cdtotkvv(ds[0])
    except Exception as e:
        logger.error("_doc_cdtotkvv_ky_goc: %s", e, exc_info=True)
        return None


def _ds_cdtotkvv_multi_ky() -> "tuple[list[pd.DataFrame], list[str]]":
    """Lấy 3 kỳ gần nhất CDTOTKVV cho phân tích xu hướng."""
    try:
        from data.cdtotkvv import doc_cdtotkvv, ds_thang_nam

        def _sort_key(s: str) -> tuple:
            try:
                mm, yyyy = s.split("/")
                return (int(yyyy), int(mm))
            except (ValueError, IndexError):
                return (0, 0)

        ds = sorted(ds_thang_nam(), key=_sort_key)
        if not ds:
            return [], []
        recent_3 = ds[-3:]
        dfs: list[pd.DataFrame] = []
        labels: list[str] = []
        for ky in recent_3:
            try:
                d = doc_cdtotkvv(ky)
                if d is not None and not d.empty:
                    dfs.append(d)
                    labels.append(ky)
            except Exception:
                continue
        return dfs, labels
    except Exception as e:
        logger.error("_ds_cdtotkvv_multi_ky: %s", e, exc_info=True)
        return [], []


def _loc_cbtd_data(cbtd_data: dict, loc_pgd: str, loc_cb: str) -> dict:
    """Lọc cbtd_data theo PGD và mã CBTD."""
    out: dict = {}
    for ma, info in cbtd_data.items():
        if loc_pgd != "(Tất cả)" and info.get("pgd", "") != loc_pgd:
            continue
        if loc_cb != "(Tất cả)" and ma != loc_cb:
            continue
        out[ma] = info
    return out


def _build_bang_pivot(
    cbtd_data: dict,
    dgd_map: dict,
    to_theo_cbtd: dict[str, list[dict]],
) -> pd.DataFrame:
    """
    Pivot CBTD → ĐGD → Tổ → điểm thành DataFrame phẳng.
    """
    rows = []
    wl = danh_gia_workload_cbtd(cbtd_data, dgd_map)
    for ma_cb, info in cbtd_data.items():
        pgd_cb = info.get("pgd", "—")
        ho_ten = info.get("ho_ten", "")
        ds_dgd = info.get("ds_dgd", [])
        so_to = len(to_theo_cbtd.get(ma_cb, []))
        to_yeu = sum(
            1 for t in to_theo_cbtd.get(ma_cb, [])
            if t.get("xep_loai") in ("Yếu", "Trung bình")
        )
        diem_list = [
            t["tong_diem"] for t in to_theo_cbtd.get(ma_cb, [])
            if t.get("tong_diem") is not None and isinstance(t.get("tong_diem"), (int, float))
        ]
        diem_tb_cb = round(sum(diem_list) / len(diem_list), 1) if diem_list else None
        wl_info = wl.get(ma_cb, {})
        wl_loai = wl_info.get("loai", "")
        wl_label = ""
        if wl_loai == "quatai":
            wl_label = "🔴 Quá tải"
        elif wl_loai == "thieutai":
            wl_label = "⚠️ Thiếu tải"
        else:
            wl_label = "✅ Cân bằng"
        rows.append({
            "Mã CBTD": ma_cb,
            "Họ tên": ho_ten,
            "PGD": pgd_cb,
            "Số ĐGD": len(ds_dgd),
            "Số ấp": wl_info.get("so_ap", 0),
            "Số Tổ TK&VV": so_to,
            "Tổ TB/Yếu": to_yeu,
            "Điểm TB Tổ": f"{diem_tb_cb:.1f}" if diem_tb_cb is not None else "—",
            "Workload": wl_label,
            "Trạng thái": (
                "🔴 Có Tổ TB/Yếu" if to_yeu > 0
                else ("✅ Tốt" if so_to > 0 else "⚠️ Chưa dữ liệu")
            ),
        })
    return pd.DataFrame(rows) if rows else pd.DataFrame()


# ── Chart builders (Plotly) ──────────────────────────────────────────────────

def _chart_phan_bo_dgd_to(df_pivot: pd.DataFrame) -> go.Figure:
    """Bar chart: Phân bố số ĐGD & Tổ theo từng CBTD."""
    if df_pivot.empty:
        return go.Figure()
    fig = go.Figure()
    df_sorted = df_pivot.sort_values("Số ĐGD", ascending=True).tail(20)
    fig.add_trace(go.Bar(
        y=df_sorted["Mã CBTD"] + " - " + df_sorted["Họ tên"],
        x=df_sorted["Số ĐGD"],
        name="Số ĐGD",
        orientation="h",
        marker_color=_VBSP_GREEN,
        text=df_sorted["Số ĐGD"],
        textposition="outside",
    ))
    fig.add_trace(go.Bar(
        y=df_sorted["Mã CBTD"] + " - " + df_sorted["Họ tên"],
        x=df_sorted["Số Tổ TK&VV"],
        name="Số Tổ TK&VV",
        orientation="h",
        marker_color=_VBSP_ACCENT,
        text=df_sorted["Số Tổ TK&VV"],
        textposition="outside",
    ))
    fig.update_layout(
        title="📊 Phân bố ĐGD & Tổ theo CBTD (Top 20)",
        barmode="group",
        height=max(420, 35 * len(df_sorted)),
        margin=dict(l=20, r=20, t=50, b=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return fig


def _chart_donut_xep_loai_to(to_theo_cbtd: dict[str, list[dict]]) -> go.Figure:
    """Donut chart: % Tổ đạt (Tốt+Khá) / TB / Yếu."""
    counts = {"Tốt": 0, "Khá": 0, "Trung bình": 0, "Yếu": 0, "Chưa xếp": 0}
    for tos in to_theo_cbtd.values():
        for t in tos:
            xl = t.get("xep_loai")
            if xl in counts:
                counts[xl] += 1
            else:
                counts["Chưa xếp"] += 1
    labels = list(counts.keys())
    values = list(counts.values())
    colors = [_VBSP_GREEN, _VBSP_ACCENT, _VBSP_ORANGE, _VBSP_RED, _VBSP_GREY]
    fig = go.Figure(data=[go.Pie(
        labels=labels,
        values=values,
        hole=0.55,
        marker_colors=colors[:len(labels)],
        textinfo="label+percent+value",
        pull=[0.03] * len(labels),
    )])
    fig.update_layout(
        title="🍩 Phân bố xếp loại Tổ TK&VV",
        height=420,
        margin=dict(l=20, r=20, t=50, b=20),
        legend=dict(orientation="h", yanchor="bottom", y=-0.1),
    )
    return fig


def _chart_heatmap_chat_luong_to(df_pivot: pd.DataFrame) -> go.Figure:
    """Heatmap: Chất lượng Tổ theo PGD × CBTD (màu % Tổ đạt)."""
    if df_pivot.empty or "PGD" not in df_pivot.columns:
        return go.Figure()
    tmp = df_pivot.copy()
    tmp["% Tổ đạt"] = 0.0
    so_to = pd.to_numeric(tmp["Số Tổ TK&VV"], errors="coerce").fillna(0)
    so_tb = pd.to_numeric(tmp["Tổ TB/Yếu"], errors="coerce").fillna(0)
    dat = so_to - so_tb
    mask = so_to > 0
    tmp.loc[mask, "% Tổ đạt"] = (dat[mask] / so_to[mask] * 100).round(1)
    tmp = tmp[tmp["PGD"].notna() & (tmp["PGD"] != "")]
    if tmp.empty:
        return go.Figure()
    pivot = tmp.pivot_table(
        index="PGD", columns="Mã CBTD", values="% Tổ đạt",
        aggfunc="mean", fill_value=-1,
    )
    # Filter PGDs and CBs with data only
    pivot = pivot.loc[:, (pivot != -1).any(axis=0)]
    pivot = pivot.loc[(pivot != -1).any(axis=1), :]
    if pivot.empty:
        return go.Figure()
    # Replace -1 with NaN for visual holes
    pivot_display = pivot.replace(-1, float("nan"))
    fig = px.imshow(
        pivot_display,
        text_auto=".0f",
        aspect="auto",
        color_continuous_scale="Greens",
        range_color=[0, 100],
        labels=dict(x="CBTD", y="PGD", color="% Tổ đạt"),
        title="🔥 Heatmap: % Tổ đạt theo PGD × CBTD",
        height=max(420, 45 * len(pivot_display)),
    )
    fig.update_layout(margin=dict(l=20, r=20, t=50, b=20))
    return fig


def _chart_top10_qh(df_xep_hang: pd.DataFrame) -> go.Figure:
    """Bar chart Top 10 CBTD có tỷ lệ QH cao nhất."""
    if df_xep_hang.empty or "TL_QH_pct" not in df_xep_hang.columns:
        return go.Figure()
    tmp = df_xep_hang.copy()
    tmp["TL_QH_pct"] = pd.to_numeric(tmp["TL_QH_pct"], errors="coerce").fillna(0)
    tmp = tmp[tmp["TL_QH_pct"] > 0].sort_values("TL_QH_pct", ascending=False).head(10)
    if tmp.empty:
        return go.Figure()
    colors = [_VBSP_RED if v >= 3 else (_VBSP_ORANGE if v >= 2 else _VBSP_ACCENT)
              for v in tmp["TL_QH_pct"]]
    fig = go.Figure(go.Bar(
        x=tmp["TL_QH_pct"],
        y=tmp["Ma_CBTD"] + " - " + tmp["Ho_ten"],
        orientation="h",
        marker_color=colors,
        text=tmp["TL_QH_pct"].round(2).astype(str) + "%",
        textposition="outside",
    ))
    fig.update_layout(
        title="🔴 Top CBTD có tỷ lệ QH cao nhất",
        height=max(400, 35 * len(tmp)),
        margin=dict(l=20, r=20, t=50, b=20),
        xaxis_title="Tỷ lệ QH (%)",
    )
    # Thêm đường kẻ ngưỡng cảnh báo 2% QH
    fig.add_vline(x=2, line_dash="dash", line_color=_VBSP_GREEN,
                  annotation_text="Ngưỡng 2%", annotation_position="top right")
    return fig


def _chart_xu_huong_3ky(xh: dict) -> go.Figure:
    """Dual-axis line chart xu hướng % Tổ đạt & Điểm TB qua 3 kỳ gần nhất."""
    summary = xh.get("summary", {})
    kys = summary.get("ky", [])
    if not kys:
        return go.Figure()
    pct = summary.get("pct_dat", [])
    diem = summary.get("diem_tb", [])
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(
        go.Scatter(x=kys, y=pct, name="% Tổ đạt", mode="lines+markers",
                   line=dict(color=_VBSP_GREEN, width=3),
                   marker=dict(size=10)),
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(x=kys, y=diem, name="Điểm TB Tổ", mode="lines+markers",
                   line=dict(color=_VBSP_ACCENT, width=3, dash="dash"),
                   marker=dict(size=10)),
        secondary_y=True,
    )
    fig.update_layout(
        title="📈 Xu hướng chất lượng Tổ qua các kỳ gần nhất",
        height=360,
        margin=dict(l=20, r=20, t=50, b=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    fig.update_yaxes(title_text="% Tổ đạt", secondary_y=False, range=[0, 100])
    fig.update_yaxes(title_text="Điểm TB", secondary_y=True)
    return fig


# ── Export builders ──────────────────────────────────────────────────────────

def _xuat_excel_cross(
    cbtd_data: dict,
    dgd_map: dict,
    to_theo_cbtd: dict[str, list[dict]],
    canh_baos: list[dict],
    df_pivot: pd.DataFrame,
    df_xep_hang: pd.DataFrame,
    xh: dict,
) -> bytes:
    """Xuất Excel nhiều sheet: Tổng hợp, Xếp hạng, Chi tiết từng CBTD, Tổ TB/Yếu, Cảnh báo, Xu hướng."""
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        if not df_pivot.empty:
            df_pivot.to_excel(w, index=False, sheet_name="Tổng hợp CBTD")
        if not df_xep_hang.empty:
            df_xep_hang.to_excel(w, index=False, sheet_name="Xếp hạng CBTD")

        for ma_cb, tos in to_theo_cbtd.items():
            if not tos:
                continue
            info = cbtd_data.get(ma_cb, {})
            df_cb = pd.DataFrame(tos)
            df_cb.insert(0, "Mã CBTD", ma_cb)
            df_cb.insert(1, "Họ tên", info.get("ho_ten", ""))
            sheet_name = f"CB_{ma_cb}"[:31]
            df_cb.to_excel(w, index=False, sheet_name=sheet_name)

        rows_yeu = [
            dict(t, ma_cb=ma_cb, ho_ten=cbtd_data.get(ma_cb, {}).get("ho_ten", ""))
            for ma_cb, tos in to_theo_cbtd.items()
            for t in tos
            if t.get("xep_loai") in ("Yếu", "Trung bình")
        ]
        if rows_yeu:
            pd.DataFrame(rows_yeu).to_excel(w, index=False, sheet_name="Tổ TB_Yếu")

        if canh_baos:
            df_cb_list = pd.DataFrame([
                {"Mức độ": c["muc_do"], "Loại": c["loai"], "Nội dung": c["noi_dung"]}
                for c in canh_baos
            ])
            df_cb_list.to_excel(w, index=False, sheet_name="Cảnh báo")

        xh_s = xh.get("summary", {})
        if xh_s and xh_s.get("ky"):
            pd.DataFrame({
                "Kỳ": xh_s.get("ky", []),
                "Số Tổ": xh_s.get("so_to", []),
                "% Tổ đạt": xh_s.get("pct_dat", []),
                "Điểm TB": xh_s.get("diem_tb", []),
            }).to_excel(w, index=False, sheet_name="Xu hướng")

        dtb = xh.get("to_duoi_tb_lien_tiep", [])
        if dtb:
            pd.DataFrame(dtb).to_excel(w, index=False, sheet_name="Tổ dưới TB 2+ kỳ")

        ttl = xh.get("to_tang_ty_le", [])
        if ttl:
            pd.DataFrame(ttl).to_excel(w, index=False, sheet_name="Tổ cải thiện mạnh")

    return buf.getvalue()


# ── Main render ──────────────────────────────────────────────────────────────

def render(tab: "DeltaGenerator | None" = None, **kwargs) -> None:
    df = kwargs.get("df")
    df_full = kwargs.get("df_full", df)
    role_raw = str(kwargs.get("role", "user") or "user")
    role = normalize_role(role_raw)
    username = kwargs.get("username", "unknown")
    pgd_user = kwargs.get("pgd_user", "")
    _kp = f"pgd_{pgd_user.strip().lower().replace(' ', '_')}_" if pgd_user else "cn_"

    ctx = TabContext(tab, **kwargs)
    with ctx:
        st.subheader("📊 Dashboard CBTD & Địa bàn")
        st.caption("Tổng quan liên kết: Cán bộ tín dụng — Điểm giao dịch — Tổ TK&VV")

        with st.spinner("🔄 Đang tải dữ liệu CBTD, ĐGD & Tổ TK&VV..."):
            cbtd_data_raw: dict = doc_cbtd()
            if pgd_user:
                cbtd_data_raw = {k: v for k, v in cbtd_data_raw.items()
                                 if str(v.get("pgd", "")).strip().lower() == pgd_user.strip().lower()}
            dgd_map: dict = db.doc_dgd_map() or {}

            # Dữ liệu Tổ TK&VV
            df_cdto = _doc_cdtotkvv_moi_nhat()
            df_cdto_truoc = _doc_cdtotkvv_ky_goc()
            ds_dfs_ky, ds_nhan_ky = _ds_cdtotkvv_multi_ky()
            xh = phan_tich_xu_huong_to(ds_dfs_ky, ds_nhan_ky) if ds_dfs_ky else {}

        # ── Bộ lọc tương tác ────────────────────────────────────────────────
        with st.container(border=True):
            st.caption("**🔎 Bộ lọc dữ liệu** (áp dụng cho KPI, Bảng, Xếp hạng, Biểu đồ)")
            pgd_opts = ["(Tất cả)"] + sorted({v.get("pgd", "") for v in cbtd_data_raw.values()
                                               if v.get("pgd", "")})
            def_loc_pgd = pgd_opts.index(pgd_user) if pgd_user and pgd_user in pgd_opts else 0
            loc_pgd = st.selectbox("Lọc theo PGD", pgd_opts, index=def_loc_pgd,
                                   key=f"{_kp}loc_pgd")

            cbtd_data_filtered_1 = (
                cbtd_data_raw if loc_pgd == "(Tất cả)"
                else {k: v for k, v in cbtd_data_raw.items() if v.get("pgd", "") == loc_pgd}
            )
            cb_opts = ["(Tất cả)"] + sorted(cbtd_data_filtered_1.keys())
            loc_cb = st.selectbox("Lọc theo CBTD", cb_opts, key=f"{_kp}loc_cb")

            cbtd_data = _loc_cbtd_data(cbtd_data_raw, loc_pgd, loc_cb)

            # Lọc cảnh báo
            with st.expander("⚙️ Tinh chỉnh cảnh báo"):
                c1, c2, c3 = st.columns(3)
                with c1:
                    nguong_qh = st.slider("Ngưỡng QH (%)", 0.5, 10.0, 2.0, 0.5,
                                          key=f"{_kp}nguong_qh")
                with c2:
                    nguong_dgd_qt = st.number_input("Ngưỡng ĐGD quá tải", 2, 10, 5,
                                                    key=f"{_kp}nguong_dgd_qt")
                with c3:
                    nguong_ap_qt = st.number_input("Ngưỡng ấp quá tải", 5, 100, 30,
                                                   key=f"{_kp}nguong_ap_qt")

        # ── KPI Row ─────────────────────────────────────────────────────────
        kpi = tom_tat_kpi(cbtd_data, dgd_map, df_cdto)

        kpi_row(
            cols=[
                {
                    "label": "Số CBTD",
                    "value": fmt_so(kpi["so_cbtd"]),
                    "icon": "👔",
                },
                {
                    "label": "Tổng ĐGD",
                    "value": fmt_so(kpi["so_dgd_tong"]),
                    "suffix": f" (⚠️ {kpi['so_dgd_chua_phan']} chưa phân)" if kpi["so_dgd_chua_phan"] else "",
                    "icon": "📍",
                },
                {
                    "label": "Tổng Tổ TK&VV",
                    "value": fmt_so(kpi["so_to_tong"]),
                    "icon": "🏘️",
                },
                {
                    "label": "Điểm TB Tổ",
                    "value": f"{kpi['diem_tb']:.1f}" if kpi["so_to_tong"] else "—",
                    "icon": "⭐",
                },
                {
                    "label": "% Tổ đạt (Tốt+Khá)",
                    "value": f"{kpi['pct_to_dat']:.1f}%" if kpi["so_to_tong"] else "—",
                    "icon": "✅",
                },
                {
                    "label": "Tổ TB/Yếu",
                    "value": fmt_so(kpi["so_to_tb_yeu"]),
                    "icon": "🔴" if kpi["so_to_tb_yeu"] > 0 else "🟢",
                },
                {
                    "label": "CBTD quá tải",
                    "value": fmt_so(kpi.get("so_cbtd_quatai", 0)),
                    "icon": "🔥" if kpi.get("so_cbtd_quatai", 0) > 0 else "💚",
                },
                {
                    "label": "CBTD thiếu tải",
                    "value": fmt_so(kpi.get("so_cbtd_thieutai", 0)),
                    "icon": "⚠️" if kpi.get("so_cbtd_thieutai", 0) > 0 else "💚",
                },
            ],
            num_columns=4,
        )

        st.divider()

        # ── Xu hướng 3 kỳ ──────────────────────────────────────────────────
        if xh:
            with st.container(border=True):
                st.plotly_chart(_chart_xu_huong_3ky(xh), use_container_width=True,
                                key=f"{_kp}chart_xu_huong")
                if xh.get("to_tang_ty_le"):
                    st.caption(f"🌟 **{len(xh['to_tang_ty_le'])} Tổ** cải thiện mạnh mẽ (điểm +≥5) qua {len(ds_nhan_ky)} kỳ gần nhất")
                if xh.get("to_duoi_tb_lien_tiep"):
                    st.caption(f"⚠️ **{len(xh['to_duoi_tb_lien_tiep'])} Tổ** dưới Điểm TB liên tiếp ≥ 2 kỳ (cần can thiệp)")
            st.divider()

        # ── Cảnh báo thông minh ─────────────────────────────────────────────
        canh_baos = canh_bao_cbtd_dia_ban(
            cbtd_data, dgd_map, df_full, df_cdto, df_cdto_truoc,
            nguong_qh_pct=nguong_qh,
            nguong_dgd_quatai=nguong_dgd_qt,
            nguong_ap_quatai=nguong_ap_qt,
        )

        # Bộ lọc loại cảnh báo
        loai_hien_co = sorted({c["loai"] for c in canh_baos})
        with st.container():
            f1, f2 = st.columns([2, 3])
            with f1:
                loc_loai_cb = st.multiselect(
                    "Lọc theo loại cảnh báo", loai_hien_co, default=loai_hien_co,
                    key=f"{_kp}loc_loai_cb",
                    format_func=lambda x: {
                        "dgd_thieu_cbtd": "⚠️ ĐGD thiếu CBTD",
                        "cbtd_qh_cao": "🔴 CBTD QH cao",
                        "to_yeu_lien_tiep": "🔴 Tổ TB/Yếu 2+ kỳ",
                        "cbtd_quatai": "🔴 CBTD quá tải",
                        "cbtd_thieutai": "⚠️ CBTD thiếu tải",
                        "to_giam_diem_2ky": "⚠️ Tổ điểm giảm",
                        "dgd_khong_co_hs": "⚠️ ĐGD chưa có hồ sơ",
                    }.get(x, x),
                )
            with f2:
                loc_muc_do = st.multiselect(
                    "Lọc theo mức độ", ["🔴", "⚠️"], default=["🔴", "⚠️"],
                    key=f"{_kp}loc_muc_do",
                )
        canh_baos_loc = [c for c in canh_baos
                         if c["loai"] in loc_loai_cb and c["muc_do"] in loc_muc_do]

        so_canh_bao = len(canh_baos_loc)
        so_red = sum(1 for c in canh_baos_loc if c["muc_do"] == "🔴")
        header_cb = (
            f"🔔 Cảnh báo ({so_canh_bao})  —  🔴 {so_red} / ⚠️ {so_canh_bao - so_red}"
            if so_canh_bao else "✅ Không có cảnh báo phù hợp bộ lọc"
        )
        with st.expander(header_cb, expanded=(so_canh_bao > 0)):
            if not canh_baos_loc:
                st.success("Mọi ĐGD đã có CBTD, không có CBTD QH cao, không có Tổ TB/Yếu liên tiếp.")
            else:
                nhom_dgd = [c for c in canh_baos_loc if c["loai"] == "dgd_thieu_cbtd"]
                nhom_qh = [c for c in canh_baos_loc if c["loai"] == "cbtd_qh_cao"]
                nhom_to = [c for c in canh_baos_loc if c["loai"] == "to_yeu_lien_tiep"]
                nhom_wl_qt = [c for c in canh_baos_loc if c["loai"] == "cbtd_quatai"]
                nhom_wl_tt = [c for c in canh_baos_loc if c["loai"] == "cbtd_thieutai"]
                nhom_giam = [c for c in canh_baos_loc if c["loai"] == "to_giam_diem_2ky"]
                nhom_kohs = [c for c in canh_baos_loc if c["loai"] == "dgd_khong_co_hs"]

                if nhom_dgd:
                    st.markdown(f"**⚠️ ĐGD chưa có CBTD ({len(nhom_dgd)})**")
                    for c in nhom_dgd:
                        st.caption(f"• {c['noi_dung']}")
                if nhom_qh:
                    st.markdown(f"**🔴 CBTD có tỷ lệ QH cao ({len(nhom_qh)})**")
                    for c in nhom_qh:
                        st.warning(c["noi_dung"])
                if nhom_to:
                    st.markdown(f"**🔴 Tổ TB/Yếu liên tiếp 2+ tháng ({len(nhom_to)})**")
                    for c in nhom_to:
                        st.error(c["noi_dung"])
                if nhom_wl_qt:
                    st.markdown(f"**🔴 CBTD quá tải ({len(nhom_wl_qt)})**")
                    for c in nhom_wl_qt:
                        st.error(c["noi_dung"])
                if nhom_wl_tt:
                    st.markdown(f"**⚠️ CBTD thiếu tải ({len(nhom_wl_tt)})**")
                    for c in nhom_wl_tt:
                        st.caption(f"• {c['noi_dung']}")
                if nhom_giam:
                    st.markdown(f"**⚠️ Tổ điểm giảm 2 kỳ ({len(nhom_giam)})**")
                    for c in nhom_giam:
                        st.warning(c["noi_dung"])
                if nhom_kohs:
                    st.markdown(f"**⚠️ ĐGD chưa có hồ sơ vay ({len(nhom_kohs)})**")
                    for c in nhom_kohs:
                        st.caption(f"• {c['noi_dung']}")

        st.divider()

        # ── 4 Biểu đồ nâng cao ──────────────────────────────────────────────
        to_theo_cbtd = lay_to_theo_cbtd(cbtd_data, dgd_map, df_cdto)
        df_pivot = _build_bang_pivot(cbtd_data, dgd_map, to_theo_cbtd)
        df_xep_hang = xep_hang_cbtd(cbtd_data, dgd_map, df_full, df_cdto, to_theo_cbtd)

        g1, g2 = st.columns(2)
        with g1:
            st.plotly_chart(_chart_phan_bo_dgd_to(df_pivot), use_container_width=True,
                            key=f"{_kp}chart_phan_bo")
        with g2:
            st.plotly_chart(_chart_donut_xep_loai_to(to_theo_cbtd), use_container_width=True,
                            key=f"{_kp}chart_donut")

        st.plotly_chart(_chart_heatmap_chat_luong_to(df_pivot), use_container_width=True,
                        key=f"{_kp}chart_heatmap")
        st.plotly_chart(_chart_top10_qh(df_xep_hang), use_container_width=True,
                        key=f"{_kp}chart_top10_qh")

        st.divider()

        # ── Bảng xếp hạng CBTD ─────────────────────────────────────────────
        st.markdown("**🏆 Bảng xếp hạng CBTD (Scorecard 0-100)**")
        if df_xep_hang.empty:
            st.info("Chưa có dữ liệu CBTD hoặc chưa cấu hình ĐGD.")
        else:
            rename_map = {
                "Hang": "Hạng", "Ma_CBTD": "Mã CBTD", "Ho_ten": "Họ tên",
                "So_DGD": "Số ĐGD", "So_ap": "Số ấp", "So_KH": "Số KH",
                "Du_no_TY": "Dư nợ (tỷ)", "TL_QH_pct": "TL QH (%)",
                "So_to": "Số Tổ", "Pct_to_dat": "% Tổ đạt",
                "Diem_TB_to": "Điểm TB Tổ", "Diem_Tong": "Điểm tổng",
                "Xep_Loai": "Xếp loại",
            }
            df_renamed = df_xep_hang.rename(columns={k: v for k, v in rename_map.items()
                                                     if k in df_xep_hang.columns})
            def _mau_xep_loai(val: str) -> str:
                if val == "Xuất sắc": return f"background-color:{_VBSP_GREEN_LIGHT};color:{_VBSP_GREEN};font-weight:bold"
                if val == "Tốt": return f"background-color:#E8F5E9;color:{_VBSP_GREEN}"
                if val == "Khá": return "background-color:#FFF9C4;color:#F57F17"
                if val == "Trung bình": return "background-color:#FFF3E0;color:#E65100"
                if val == "Yếu": return f"background-color:#FFEBEE;color:{_VBSP_RED};font-weight:bold"
                return ""
            styled = df_renamed.style.map(_mau_xep_loai, subset=["Xếp loại"])
            hien_thi_dataframe_phan_trang(
                df_renamed,
                key=f"{_kp}cbtd_xep_hang",
                column_config={
                    "Hạng": st.column_config.NumberColumn("Hạng", format="%d"),
                    "Số KH": st.column_config.NumberColumn("Số KH", format=",.0f"),
                    "Dư nợ (tỷ)": st.column_config.NumberColumn("Dư nợ (tỷ)", format=",.2f"),
                    "TL QH (%)": st.column_config.NumberColumn("TL QH (%)", format=",.2f"),
                    "% Tổ đạt": st.column_config.NumberColumn("% Tổ đạt", format=",.1f"),
                    "Điểm TB Tổ": st.column_config.NumberColumn("Điểm TB Tổ", format=",.1f"),
                    "Điểm tổng": st.column_config.NumberColumn("Điểm tổng", format=",.1f"),
                },
            )

        st.divider()

        # ── Bảng pivot CBTD → ĐGD → Tổ ─────────────────────────────────────
        st.markdown("**📋 Bảng tổng hợp CBTD → Tổ TK&VV**")

        if df_pivot.empty:
            st.info("Chưa có dữ liệu CBTD hoặc chưa cấu hình ĐGD.")
        else:
            hien_thi_dataframe_phan_trang(
                df_pivot,
                key=f"{_kp}cbtd_db_pivot",
                column_config={
                    "Tổ TB/Yếu": st.column_config.NumberColumn(
                        "Tổ TB/Yếu", help="Số Tổ xếp loại Trung bình hoặc Yếu"
                    ),
                    "Điểm TB Tổ": st.column_config.TextColumn("Điểm TB Tổ"),
                },
            )

        # ── Drill-down: Xem hồ sơ vay theo địa bàn CBTD (NEW Gói 7) ────────
        st.divider()
        st.markdown("**🔍 Drill-down: Hồ sơ vay theo Địa bàn CBTD**")
        st.caption("Chọn một CBTD → Xem danh sách các hồ sơ vay tại địa bàn được phụ trách → Mở hộp thoại chi tiết.")
        dd_cbtd_opts = ["— Chọn CBTD để xem hồ sơ —"] + list(cbtd_data.keys())
        dd_ma_cb = st.selectbox(
            "Chọn CBTD phụ trách", dd_cbtd_opts, key=f"{_kp}cbtd_dd_ma_cb",
            format_func=lambda k: f"{k} — {cbtd_data[k]['ho_ten']} / {cbtd_data[k].get('pgd','?')}"
                                  if k != dd_cbtd_opts[0] else k,
        )
        if dd_ma_cb != dd_cbtd_opts[0] and df_full is not None and not df_full.empty:
            info_dd = cbtd_data.get(dd_ma_cb, {})
            try:
                from data.khtd import gan_cbtd_vao_df
                df_dd_full = gan_cbtd_vao_df(df_full, {dd_ma_cb: info_dd}, dgd_map)
                df_dd = df_dd_full[df_dd_full["CBTD"] == dd_ma_cb].copy()
                if "Hình thức vay" in df_dd.columns or COT_HINH_THUC_VAY in df_dd.columns:
                    col_ht = COT_HINH_THUC_VAY if COT_HINH_THUC_VAY in df_dd.columns else "Hình thức vay"
                    df_dd = df_dd[pd.to_numeric(df_dd[col_ht], errors="coerce") != 1]
                if df_dd.empty:
                    st.info("ℹ️ Không tìm thấy hồ sơ vay nào khớp với địa bàn CBTD này "
                            "(kiểm tra lại cấu hình ĐGD gán thôn/ấp).")
                else:
                    dn_col = COT_TONG_DU_NO if COT_TONG_DU_NO in df_dd.columns else None
                    qh_col = COT_DU_NO_QH if COT_DU_NO_QH in df_dd.columns else None
                    ma_kh_col = COT_MA_KH if COT_MA_KH in df_dd.columns else None
                    so_ku_col = COT_SO_KU if COT_SO_KU in df_dd.columns else None
                    xa_col = COT_TEN_XA if COT_TEN_XA in df_dd.columns else None
                    thon_col = COT_TEN_THON if COT_TEN_THON in df_dd.columns else None

                    tong_kh_dd = int(df_dd[ma_kh_col].nunique()) if ma_kh_col else len(df_dd)
                    tong_ku_dd = int(df_dd[so_ku_col].nunique()) if so_ku_col else len(df_dd)
                    tong_dn_dd = float(pd.to_numeric(df_dd[dn_col], errors="coerce").fillna(0).sum()) if dn_col else 0.0
                    tong_qh_dd = float(pd.to_numeric(df_dd[qh_col], errors="coerce").fillna(0).sum()) if qh_col else 0.0
                    tl_dd = (tong_qh_dd / tong_dn_dd * 100) if tong_dn_dd else 0.0

                    m1, m2, m3, m4 = st.columns(4)
                    m1.metric("Số KH", f"{tong_kh_dd:,}")
                    m2.metric("Số món vay", f"{tong_ku_dd:,}")
                    m3.metric("Tổng dư nợ (tỷ)", f"{tong_dn_dd / 1_000_000_000:,.2f}")
                    m4.metric("Tỷ lệ QH", f"{tl_dd:.2f}%", delta=None,
                              delta_color="inverse" if tl_dd >= 2 else "normal")

                    # Hiển thị top 50 hồ sơ lớn nhất theo dư nợ
                    if dn_col:
                        df_hien = df_dd.sort_values(dn_col, ascending=False).head(50).reset_index(drop=True)
                    else:
                        df_hien = df_dd.head(50).reset_index(drop=True)
                    cols_hien = [c for c in [ma_kh_col, xa_col, thon_col, "Tên CBTD",
                                              so_ku_col, dn_col, qh_col] if c and c in df_hien.columns]
                    rename_map = {}
                    if dn_col: rename_map[dn_col] = "Dư nợ (triệu)"
                    if qh_col: rename_map[qh_col] = "Dư nợ QH (triệu)"
                    st.caption(f"📋 Hiển thị **top {len(df_hien)}** hồ sơ dư nợ lớn nhất.")
                    # Format cột tiền nếu có
                    tmp = df_hien[cols_hien].rename(columns=rename_map).copy()
                    for col in tmp.columns:
                        if "triệu" in str(col) or "Dư nợ" in str(col):
                            tmp[col] = pd.to_numeric(tmp[col], errors="coerce").fillna(0).apply(
                                lambda x: f"{x/1_000_000:,.0f}".replace(",", ".")
                            )
                    hien_thi_dataframe_phan_trang(tmp, key=f"{_kp}cbtd_dd_tbl_{dd_ma_cb}", height=320)

                    # Nút mở loan detail drawer cho dòng top 1
                    if len(df_hien) > 0:
                        dd_btn1, dd_btn2, _ = st.columns([2, 2, 3])
                        with dd_btn1:
                            if st.button("🔎 Mở hồ sơ mẫu (top 1)",
                                         key=f"{_kp}cbtd_dd_btn_drawer_{dd_ma_cb}"):
                                from components.loan_drawer import loan_detail_drawer
                                row_sample = df_hien.iloc[0]
                                with st.spinner(f"Đang mở chi tiết hồ sơ {row_sample.get(ma_kh_col, '?')}…"):
                                    loan_detail_drawer(
                                        row=row_sample,
                                        title=f"🏠 Hồ sơ vay mẫu — địa bàn {dd_ma_cb}",
                                        username=username,
                                    )
                        with dd_btn2:
                            # Cross-link sang tab Quản lý CBTD (tự động select CBTD khi có state; không thể đổi tab trong Streamlit dễ, nên chỉ ghi chú)
                            st.info(f"💡 Để xem chi tiết CBTD → qua tab 👔 **Quản lý CBTD**, "
                                    f"sub-tab **🔎 Chi tiết** → chọn mã `{dd_ma_cb}`.")
            except Exception as e_dd:
                logger.error("tab_cbtd_dashboard drill-down loan — %s", e_dd, exc_info=True)
                st.error(f"❌ Lỗi drill-down hồ sơ: {e_dd}")

        # ── Xuất báo cáo cross-mảng (Excel + PDF) ────────────────────────────
        st.divider()
        st.markdown("**📥 Xuất báo cáo tổng hợp cross-mảng (Excel / PDF)**")
        st.caption(
            "Excel 8 sheet: Tổng hợp · Xếp hạng · Chi tiết từng CBTD "
            "· Tổ TB/Yếu · Cảnh báo · Xu hướng · Tổ dưới TB · Tổ cải thiện. "
            "PDF: Bảng xếp hạng CBTD (định dạng màu VBSP)."
        )

        # --- PDF builder for Xếp hạng CBTD (NEW Gói 5) ---
        def _xuat_pdf_rank_cbtd(xh_df: pd.DataFrame, kpi_loc: dict) -> bytes | None:
            """Tạo PDF A4 bảng xếp hạng CBTD theo chuẩn VBSP (màu xanh lá, Times New Roman)."""
            try:
                from services.pdf_service import (
                    _register_vbsp_fonts, _VBSP_GREEN, _VBSP_GREEN_LIGHT, _VBSP_ACCENT,
                    _MARGIN,
                )
                from config import TEN_CHI_NHANH_HIEN_THI
                from reportlab.lib.pagesizes import A4
                from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
                from reportlab.lib.units import mm, cm
                from reportlab.lib import colors
                from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
                from reportlab.platypus import (
                    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable,
                )
                _register_vbsp_fonts()
                buf = BytesIO()
                page_w, page_h = A4
                ngay_str = datetime.today().strftime("%d/%m/%Y")

                def _on_page(canvas, doc):
                    canvas.saveState()
                    canvas.setStrokeColor(_VBSP_GREEN)
                    canvas.setLineWidth(1.4)
                    canvas.line(_MARGIN, page_h - _MARGIN + 4, page_w - _MARGIN, page_h - _MARGIN + 4)
                    canvas.setFont("Times-Bold", 9)
                    canvas.setFillColor(_VBSP_GREEN)
                    canvas.drawString(_MARGIN, page_h - _MARGIN + 10,
                                      TEN_CHI_NHANH_HIEN_THI or "Ngân hàng Chính sách Xã hội - CN Đồng Nai")
                    canvas.setFont("Times-Roman", 8)
                    canvas.setFillColor(colors.black)
                    canvas.drawRightString(page_w - _MARGIN, page_h - _MARGIN + 10,
                                           f"Ngày in: {ngay_str}")
                    canvas.setStrokeColor(_VBSP_ACCENT)
                    canvas.setLineWidth(0.6)
                    canvas.line(_MARGIN, _MARGIN - 10, page_w - _MARGIN, _MARGIN - 10)
                    canvas.setFont("Times-Roman", 7.5)
                    canvas.drawString(_MARGIN, _MARGIN - 22,
                                      "Bảng xếp hạng CBTD — Hệ thống Quản trị Tín dụng Nội bộ")
                    canvas.drawRightString(page_w - _MARGIN, _MARGIN - 22,
                                           f"Trang {doc.page}    |    {datetime.today().strftime('%d/%m/%Y %H:%M')}")
                    canvas.restoreState()

                doc = SimpleDocTemplate(
                    buf, pagesize=A4,
                    leftMargin=_MARGIN, rightMargin=_MARGIN,
                    topMargin=_MARGIN + 14, bottomMargin=_MARGIN + 6,
                    title="Bang xep hang CBTD", author="VBSP DN SCM",
                )
                styles = getSampleStyleSheet()
                title_s = ParagraphStyle("T", parent=styles["Title"], fontName="Times-Bold",
                                         fontSize=16, textColor=_VBSP_GREEN,
                                         alignment=TA_CENTER, spaceAfter=2)
                sub_s = ParagraphStyle("S", parent=styles["Normal"], fontName="Times-Italic",
                                       fontSize=10, alignment=TA_CENTER, textColor=colors.grey,
                                       spaceAfter=6)
                h3 = ParagraphStyle("H3", parent=styles["Heading2"], fontName="Times-Bold",
                                    fontSize=11, textColor=_VBSP_GREEN, spaceBefore=4, spaceAfter=3)
                th_s = ParagraphStyle("TH", parent=styles["Normal"], fontName="Times-Bold",
                                      fontSize=9, textColor=colors.white, alignment=TA_CENTER, leading=13)
                td_s = ParagraphStyle("TD", parent=styles["Normal"], fontName="Times-Roman",
                                      fontSize=9, alignment=TA_CENTER, leading=13)
                td_l = ParagraphStyle("TL", parent=td_s, alignment=TA_LEFT)
                td_r = ParagraphStyle("TR", parent=td_s, alignment=TA_RIGHT)

                story = []
                story.append(Paragraph("BẢNG XẾP HẠNG CÁN BỘ TÍN DỤNG", title_s))
                story.append(Paragraph(
                    f"Scorecard 0-100 • Tổng {len(xh_df)} CBTD • Ngày {ngay_str}", sub_s))
                story.append(HRFlowable(width="100%", thickness=1.2, color=_VBSP_GREEN,
                                        spaceBefore=0, spaceAfter=6))

                # --- KPI row ---
                story.append(Paragraph("📊 Tổng quan", h3))
                tong_cb = kpi_loc.get("tong_cbtd", 0) or len(xh_df)
                so_qt = kpi_loc.get("so_cbtd_quatai", 0)
                so_tt = kpi_loc.get("so_cbtd_thieutai", 0)
                tl_qh_tb = round(float(xh_df["TL_QH_pct"].mean()), 2) if "TL_QH_pct" in xh_df.columns and not xh_df.empty else 0.0
                kpi_row_data = [[
                    Paragraph("Tổng CBTD", th_s),
                    Paragraph("🔴 Quá tải", th_s),
                    Paragraph("⚠️ Thiếu tải", th_s),
                    Paragraph("TB % QH toàn hệ thống", th_s),
                ], [
                    Paragraph(str(tong_cb), td_s),
                    Paragraph(str(so_qt), td_s),
                    Paragraph(str(so_tt), td_s),
                    Paragraph(f"{tl_qh_tb:,.2f} %".replace(",", "X").replace(".", ",").replace("X", "."), td_s),
                ]]
                tbl_kpi = Table(kpi_row_data,
                                colWidths=[(page_w-2*_MARGIN)/4]*4, hAlign="CENTER")
                tbl_kpi.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), _VBSP_GREEN),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ("BACKGROUND", (0, 1), (-1, 1), _VBSP_GREEN_LIGHT),
                ]))
                story.append(tbl_kpi)
                story.append(Spacer(1, 6))

                # --- Bảng xếp hạng chi tiết ---
                story.append(Paragraph("🏆 Chi tiết xếp hạng", h3))
                cols_show = [
                    "Hang", "Ma_CBTD", "Ho_ten", "PGD", "So_DGD", "So_ap",
                    "Du_no_TY", "TL_QH_pct", "Pct_to_dat", "Diem_TB_to", "Diem_Tong", "Xep_Loai",
                ]
                col_header = [
                    "Hạng", "Mã CBTD", "Họ tên", "PGD", "Số ĐGD", "Số ấp",
                    "Dư nợ (tỷ)", "% QH", "% Tổ đạt", "Điểm TB Tổ", "Tổng", "Xếp loại",
                ]
                # Align: STT, mã, số, tiền: TRUNG; Họ tên, PGD: TRÁI; Tiền, %: PHẢI; Xếp loại: CENTER
                col_widths = [
                    1.0*cm, 2.8*cm, 4.2*cm, 2.8*cm, 1.2*cm, 1.2*cm,
                    2.0*cm, 1.6*cm, 1.8*cm, 1.9*cm, 1.3*cm, 2.0*cm,
                ]
                header_row = [Paragraph(c, th_s) for c in col_header]
                body_rows = [header_row]
                def _fmt_f_vn(x: Any, decimals: int = 2) -> str:
                    try:
                        v = float(x)
                        s = f"{v:,.{decimals}f}"
                        return s.replace(",", "X").replace(".", ",").replace("X", ".")
                    except Exception:
                        return str(x or "—")
                for _, r in xh_df.iterrows():
                    xl = r.get("Xep_Loai", "")
                    row_cells = [
                        Paragraph(str(r.get("Hang", "")), td_s),
                        Paragraph(str(r.get("Ma_CBTD", "")), td_s),
                        Paragraph(str(r.get("Ho_ten", "")), td_l),
                        Paragraph(str(r.get("PGD", "")), td_l),
                        Paragraph(str(r.get("So_DGD", 0)), td_s),
                        Paragraph(str(r.get("So_ap", 0)), td_s),
                        Paragraph(_fmt_f_vn(r.get("Du_no_TY", 0), 2), td_r),
                        Paragraph(_fmt_f_vn(r.get("TL_QH_pct", 0), 2) + " %", td_r),
                        Paragraph(_fmt_f_vn(r.get("Pct_to_dat", 0), 1) + " %", td_r),
                        Paragraph(_fmt_f_vn(r.get("Diem_TB_to", 0), 1), td_r),
                        Paragraph(_fmt_f_vn(r.get("Diem_Tong", 0), 1), td_r),
                        Paragraph(f"<b>{xl}</b>", td_s),
                    ]
                    body_rows.append(row_cells)
                # Tổng cộng
                if "Du_no_TY" in xh_df.columns and not xh_df.empty:
                    dn_tot = xh_df["Du_no_TY"].sum()
                    qh_avg = float(xh_df["TL_QH_pct"].mean())
                    d_avg = float(xh_df["Diem_Tong"].mean())
                    body_rows.append([
                        Paragraph("", td_s),
                        Paragraph("<b>TỔNG CỘNG</b>", td_s),
                        Paragraph("", td_s),
                        Paragraph("", td_s),
                        Paragraph("", td_s),
                        Paragraph("", td_s),
                        Paragraph(f"<b>{_fmt_f_vn(dn_tot,2)}</b>", td_r),
                        Paragraph(f"<b>{_fmt_f_vn(qh_avg,2)} %</b>", td_r),
                        Paragraph("", td_s),
                        Paragraph("", td_s),
                        Paragraph(f"<b>{_fmt_f_vn(d_avg,1)}</b>", td_r),
                        Paragraph("", td_s),
                    ])
                tbl_rank = Table(body_rows, colWidths=col_widths, repeatRows=1, hAlign="LEFT")
                t_style = TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), _VBSP_GREEN),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("GRID", (0, 0), (-1, -1), 0.35, colors.grey),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                    ("LEFTPADDING", (0, 0), (-1, -1), 4),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                    ("ROWBACKGROUNDS", (0, 1), (-2, -2), [colors.white, _VBSP_GREEN_LIGHT]),
                ])
                # Highlight theo xếp loại (col Xếp loại index 11)
                for i in range(1, len(body_rows)-1):
                    try:
                        xl_val = str(xh_df.iloc[i-1].get("Xep_Loai", ""))
                    except Exception:
                        xl_val = ""
                    if xl_val == "Xuất sắc":
                        t_style.add("BACKGROUND", (0, i), (-1, i), "#E8F5E9")
                    elif xl_val == "Yếu":
                        t_style.add("BACKGROUND", (0, i), (-1, i), "#FFEBEE")
                        t_style.add("TEXTCOLOR", (11, i), (11, i), _VBSP_RED)
                    elif xl_val == "Trung bình":
                        t_style.add("BACKGROUND", (0, i), (-1, i), "#FFF8E1")
                # Highlight dòng tổng cộng (index -1)
                t_style.add("BACKGROUND", (0, -1), (-1, -1), _VBSP_GREEN_LIGHT)
                t_style.add("FONTNAME", (0, -1), (-1, -1), "Times-Bold")
                tbl_rank.setStyle(t_style)
                story.append(tbl_rank)

                story.append(Spacer(1, 16))
                # Khối ký tên 3 vị trí
                k1 = ParagraphStyle("k1", parent=styles["Normal"], fontName="Times-Bold",
                                    fontSize=10.5, alignment=TA_CENTER)
                k2 = ParagraphStyle("k2", parent=styles["Normal"], fontName="Times-Italic",
                                    fontSize=9.5, alignment=TA_CENTER, textColor=colors.grey,
                                    leading=13)
                ky_h = [[
                    Paragraph("Người lập", k1),
                    Paragraph("Kiểm đốc / Đội trưởng", k1),
                    Paragraph("Giám đốc Chi nhánh", k1),
                ]]
                ky_s = [[Paragraph("(Ký, ghi rõ họ tên)", k2) for _ in range(3)]]
                ky_sp = [[Paragraph("&nbsp;<br/>&nbsp;<br/>&nbsp;<br/>&nbsp;", k2) for _ in range(3)]]
                tbl_ky = Table(ky_h + ky_sp + ky_s,
                               colWidths=[(page_w-2*_MARGIN)/3]*3, hAlign="CENTER")
                tbl_ky.setStyle(TableStyle([
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ]))
                story.append(tbl_ky)

                doc.build(story, onFirstPage=_on_page, onLaterPages=_on_page)
                return buf.getvalue()
            except Exception as e_pdf:
                logger.error("_xuat_pdf_rank_cbtd error — %s", e_pdf, exc_info=True)
                return None

        col_pdf, col_xl, col_info = st.columns([2, 3, 2])
        with col_pdf:
            if st.button("🏆 Tạo PDF Xếp hạng", key=f"{_kp}cbtd_db_btn_pdf_rank"):
                try:
                    kpi_for_pdf = {
                        "tong_cbtd": tong_cbtd,
                        "so_cbtd_quatai": so_quatai,
                        "so_cbtd_thieutai": so_thieutai,
                    }
                    pdf_rank_bytes = _xuat_pdf_rank_cbtd(df_xep_hang, kpi_for_pdf)
                    if pdf_rank_bytes:
                        st.session_state[f"{_kp}_cbtd_db_pdf_rank"] = pdf_rank_bytes
                        st.session_state[f"{_kp}_cbtd_db_pdf_rank_name"] = (
                            f"XepHang_CBTD_{datetime.today().strftime('%d%m%Y')}.pdf"
                        )
                        db.ghi_audit(username, "xuat_pdf_xep_hang_cbtd",
                                     f"so_cbtd={len(df_xep_hang)}")
                        st.success("✅ Đã tạo PDF xếp hạng!")
                    else:
                        st.error("❌ Lỗi tạo PDF xếp hạng (xem log).")
                except Exception as e:
                    logger.error("xuat_pdf_rank_cbtd main — %s", e, exc_info=True)
                    st.error(f"❌ Lỗi: {e}")
            if st.session_state.get(f"{_kp}_cbtd_db_pdf_rank"):
                from components.export_pdf import download_pdf_button
                download_pdf_button(
                    pdf_bytes=st.session_state[f"{_kp}_cbtd_db_pdf_rank"],
                    ten_file_mau=st.session_state.get(f"{_kp}_cbtd_db_pdf_rank_name",
                                                    "XepHang_CBTD.pdf"),
                    label_tai="⬇ Tải PDF",
                    nut_bam_key=f"{_kp}cbtd_db_dl_pdf_rank",
                    container=st,
                )

        with col_xl:
            if st.button("📊 Tạo báo cáo tổng hợp", key=f"{_kp}cbtd_db_btn_xuat", type="primary"):
                try:
                    excel_bytes = _xuat_excel_cross(
                        cbtd_data, dgd_map, to_theo_cbtd, canh_baos_loc, df_pivot,
                        df_xep_hang, xh,
                    )
                    st.session_state[f"{_kp}_cbtd_db_excel"] = excel_bytes
                    st.session_state[f"{_kp}_cbtd_db_fname"] = (
                        f"BC_CBTD_DiaBan_{datetime.today().strftime('%d%m%Y')}.xlsx"
                    )
                    db.ghi_audit(username, "xuat_bc_cbtd_dia_ban",
                                 f"so_cbtd={len(cbtd_data)} canh_bao={so_canh_bao}")
                    st.success("✅ Đã tạo file Excel!")
                except Exception as e:
                    logger.error("xuat_bc_cbtd: lỗi tạo Excel — %s", e, exc_info=True)
                    st.error(f"❌ Lỗi tạo báo cáo: {e}")

            if st.session_state.get(f"{_kp}_cbtd_db_excel"):
                st.download_button(
                    "⬇ Tải Excel",
                    data=st.session_state[f"{_kp}_cbtd_db_excel"],
                    file_name=st.session_state.get(f"{_kp}_cbtd_db_fname", "BC_CBTD.xlsx"),
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key=f"{_kp}cbtd_db_dl_excel",
                )
        with col_info:
            st.info(
                "**📋 Nội dung:**\n\n"
                "**🏆 PDF Xếp hạng:**\n"
                "• Cover + 4 KPI tổng quan\n"
                "• Bảng xếp hạng chi tiết (Hạng, Dư nợ, % QH, Điểm)\n"
                "• Row highlight theo Xếp loại (Xanh Tốt/Đỏ Yếu)\n"
                "• Khối ký tên 3 vị trí\n\n"
                "**📊 Excel (8 sheet):**\n"
                "Tổng hợp · Xếp hạng · CB_{Mã} · Tổ TB_Yếu\n"
                "· Cảnh báo · Xu hướng · Tổ dưới TB 2+ kỳ · Tổ cải thiện mạnh"
            )
