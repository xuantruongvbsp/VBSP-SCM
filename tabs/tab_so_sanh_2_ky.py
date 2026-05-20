"""So sánh số liệu giữa 2 kỳ snapshot bất kỳ (từ bảng hstd_snapshot).

Khác tab_so_sanh_ky.py (so sánh df hiện tại vs baseline 31/12):
- Không phụ thuộc df upload, không cần file baseline Excel
- Người dùng chọn Kỳ 1 và Kỳ 2 tự do từ lịch sử snapshot
- Hiển thị song song: Kỳ 1 | Kỳ 2 | Δ | % thay đổi
- Áp dụng cho cả 3 phân hệ (Phòng KH-NV, BGĐ, PGD)
"""
from __future__ import annotations

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from streamlit.delta_generator import DeltaGenerator

from auth import normalize_role, la_phan_he_pgd
from utils import get_tab_context, fmt_ty, fmt_so, xuat_excel
import db
from snapshot_service import danh_sach_ky, doc_snapshot


# ──────────────────────────────────────────────
# HELPER
# ──────────────────────────────────────────────

def _agg(df: pd.DataFrame) -> dict:
    """Tổng hợp các chỉ tiêu từ snapshot DataFrame (đã aggregate sẵn theo PGD)."""
    zero = {k: 0.0 for k in
            ["tong_du_no", "du_no_th", "du_no_qh", "du_no_khoanh", "so_ho", "so_ku", "gn_nam"]}
    if df is None or df.empty:
        return zero
    return {
        "tong_du_no":   float(df["tong_du_no"].sum()),
        "du_no_th":     float(df["du_no_th"].sum()),
        "du_no_qh":     float(df["du_no_qh"].sum()),
        "du_no_khoanh": float(df["du_no_khoanh"].sum()),
        "so_ho":        float(df["so_ho"].sum()),
        "so_ku":        float(df["so_ku"].sum()),
        "gn_nam":       float(df["gn_nam"].sum()),
    }


def _delta_fmt(delta: float, unit: str = "tien") -> str:
    """Format ±delta kiểu VN."""
    sign = "+" if delta >= 0 else ""
    if unit == "tien":
        return f"{sign}{fmt_ty(delta)}"
    if unit == "so":
        return f"{sign}{fmt_so(int(round(delta)))}"
    # unit == "pct"
    return f"{sign}{abs(delta):.2f}".replace(".", ",") + "%" if delta >= 0 \
        else f"-{abs(delta):.2f}".replace(".", ",") + "%"


def _pct_change(v1: float, v2: float) -> str:
    """Tính % thay đổi, trả '—' nếu v1 = 0."""
    if v1 == 0:
        return "—"
    pct = (v2 - v1) / abs(v1) * 100
    sign = "+" if pct >= 0 else ""
    return f"{sign}{pct:.1f}".replace(".", ",") + "%"


def _tl_nqh(agg: dict) -> float:
    """Tỷ lệ NQH (%)."""
    return agg["du_no_qh"] / agg["tong_du_no"] * 100 if agg["tong_du_no"] else 0.0


def _fmt_pct(x: float) -> str:
    return f"{x:.2f}".replace(".", ",") + "%"


def _mau_delta(delta: float, inverse: bool = False) -> str:
    """Màu HTML cho delta (xanh tốt, đỏ xấu)."""
    if delta == 0:
        return "#6b7280"
    good = delta > 0
    if inverse:
        good = not good
    return "#16a34a" if good else "#dc2626"


# ──────────────────────────────────────────────
# RENDER KPI CARDS
# ──────────────────────────────────────────────

def _render_kpi(agg1: dict, agg2: dict, ky1: str, ky2: str) -> None:
    tl1 = _tl_nqh(agg1)
    tl2 = _tl_nqh(agg2)

    r1c1, r1c2, r1c3 = st.columns(3)
    r2c1, r2c2, r2c3 = st.columns(3)

    r1c1.metric(
        "Tổng dư nợ (triệu đ)",
        fmt_ty(agg2["tong_du_no"]),
        delta=_delta_fmt(agg2["tong_du_no"] - agg1["tong_du_no"], "tien"),
        help=f"Kỳ {ky1}: {fmt_ty(agg1['tong_du_no'])} triệu đồng",
    )
    r1c2.metric(
        "Dư nợ quá hạn (triệu đ)",
        fmt_ty(agg2["du_no_qh"]),
        delta=_delta_fmt(agg2["du_no_qh"] - agg1["du_no_qh"], "tien"),
        delta_color="inverse",
        help=f"Kỳ {ky1}: {fmt_ty(agg1['du_no_qh'])} triệu đồng",
    )
    r1c3.metric(
        "Tỷ lệ NQH",
        _fmt_pct(tl2),
        delta=_delta_fmt(tl2 - tl1, "pct"),
        delta_color="inverse",
        help=f"Kỳ {ky1}: {_fmt_pct(tl1)}",
    )
    r2c1.metric(
        "Dư nợ khoanh (triệu đ)",
        fmt_ty(agg2["du_no_khoanh"]),
        delta=_delta_fmt(agg2["du_no_khoanh"] - agg1["du_no_khoanh"], "tien"),
        delta_color="inverse",
        help=f"Kỳ {ky1}: {fmt_ty(agg1['du_no_khoanh'])} triệu đồng",
    )
    r2c2.metric(
        "Số hộ vay",
        fmt_so(int(agg2["so_ho"])),
        delta=_delta_fmt(agg2["so_ho"] - agg1["so_ho"], "so"),
        help=f"Kỳ {ky1}: {fmt_so(int(agg1['so_ho']))} hộ",
    )
    r2c3.metric(
        "Số khế ước",
        fmt_so(int(agg2["so_ku"])),
        delta=_delta_fmt(agg2["so_ku"] - agg1["so_ku"], "so"),
        help=f"Kỳ {ky1}: {fmt_so(int(agg1['so_ku']))} khế ước",
    )


# ──────────────────────────────────────────────
# BẢNG CHI TIẾT
# ──────────────────────────────────────────────

def _render_bang_chi_tiet(agg1: dict, agg2: dict, ky1: str, ky2: str) -> None:
    tl1 = _tl_nqh(agg1)
    tl2 = _tl_nqh(agg2)

    rows = [
        # (nhãn, v1, v2, inverse)
        ("Tổng dư nợ (triệu đồng)",     agg1["tong_du_no"],   agg2["tong_du_no"],   False, "tien"),
        ("Dư nợ trong hạn (triệu đồng)", agg1["du_no_th"],     agg2["du_no_th"],     False, "tien"),
        ("Dư nợ quá hạn (triệu đồng)",   agg1["du_no_qh"],     agg2["du_no_qh"],     True,  "tien"),
        ("Dư nợ khoanh (triệu đồng)",    agg1["du_no_khoanh"], agg2["du_no_khoanh"], True,  "tien"),
        ("Tỷ lệ NQH (%)",                tl1,                  tl2,                  True,  "pct"),
        ("Số hộ vay",                    agg1["so_ho"],        agg2["so_ho"],        False, "so"),
        ("Số khế ước",                   agg1["so_ku"],        agg2["so_ku"],        False, "so"),
        ("Giải ngân trong năm (tr.đ)",   agg1["gn_nam"],       agg2["gn_nam"],       False, "tien"),
    ]

    def _fmt_val(v: float, unit: str) -> str:
        if unit == "tien":
            return fmt_ty(v)
        if unit == "so":
            return fmt_so(int(round(v)))
        return _fmt_pct(v)

    rows_html = ""
    for label, v1, v2, inv, unit in rows:
        delta = v2 - v1
        mau = _mau_delta(delta, inverse=inv)
        d_str = _delta_fmt(delta, unit)
        p_str = _pct_change(v1, v2) if unit != "pct" else _delta_fmt(delta, "pct")
        rows_html += (
            f"<tr style='border-bottom:1px solid #e5e7eb'>"
            f"<td style='padding:8px 12px;font-weight:500'>{label}</td>"
            f"<td style='padding:8px 12px;text-align:right'>{_fmt_val(v1, unit)}</td>"
            f"<td style='padding:8px 12px;text-align:right;font-weight:600'>{_fmt_val(v2, unit)}</td>"
            f"<td style='padding:8px 12px;text-align:right;color:{mau};font-weight:600'>{d_str}</td>"
            f"<td style='padding:8px 12px;text-align:right;color:{mau}'>{p_str}</td>"
            f"</tr>"
        )

    st.markdown(
        f"""<div style="overflow-x:auto;border-radius:8px;border:1px solid #e5e7eb">
        <table style="width:100%;border-collapse:collapse;font-size:0.93rem">
          <thead>
            <tr style="background:#1e3a5f;color:white">
              <th style="padding:10px 12px;text-align:left">Chỉ tiêu</th>
              <th style="padding:10px 12px;text-align:right">Kỳ {ky1}</th>
              <th style="padding:10px 12px;text-align:right">Kỳ {ky2}</th>
              <th style="padding:10px 12px;text-align:right">Chênh lệch</th>
              <th style="padding:10px 12px;text-align:right">% thay đổi</th>
            </tr>
          </thead>
          <tbody>{rows_html}</tbody>
        </table></div>""",
        unsafe_allow_html=True,
    )


# ──────────────────────────────────────────────
# BẢNG THEO PGD (CN only)
# ──────────────────────────────────────────────

def _render_bang_pgd(df1: pd.DataFrame, df2: pd.DataFrame,
                     ky1: str, ky2: str) -> None:
    """Bảng biến động dư nợ / NQH theo từng PGD."""
    m1 = df1[["ten_pgd", "tong_du_no", "du_no_qh", "so_ho"]].rename(columns={
        "tong_du_no": "dn1", "du_no_qh": "nqh1", "so_ho": "ho1",
    })
    m2 = df2[["ten_pgd", "tong_du_no", "du_no_qh", "so_ho"]].rename(columns={
        "tong_du_no": "dn2", "du_no_qh": "nqh2", "so_ho": "ho2",
    })
    jn = pd.merge(m1, m2, on="ten_pgd", how="outer").fillna(0)
    jn["delta_dn"]  = jn["dn2"]  - jn["dn1"]
    jn["delta_nqh"] = jn["nqh2"] - jn["nqh1"]
    jn["delta_ho"]  = jn["ho2"]  - jn["ho1"]
    jn["tl_nqh1"]   = jn.apply(lambda r: r["nqh1"] / r["dn1"] * 100 if r["dn1"] else 0, axis=1)
    jn["tl_nqh2"]   = jn.apply(lambda r: r["nqh2"] / r["dn2"] * 100 if r["dn2"] else 0, axis=1)

    # Hàng tổng
    tong = {
        "ten_pgd": "⬛ Tổng Chi nhánh",
        "dn1": jn["dn1"].sum(), "dn2": jn["dn2"].sum(),
        "delta_dn": jn["delta_dn"].sum(),
        "nqh1": jn["nqh1"].sum(), "nqh2": jn["nqh2"].sum(),
        "delta_nqh": jn["delta_nqh"].sum(),
        "ho1": jn["ho1"].sum(), "ho2": jn["ho2"].sum(),
        "delta_ho": jn["delta_ho"].sum(),
        "tl_nqh1": jn["nqh1"].sum() / jn["dn1"].sum() * 100 if jn["dn1"].sum() else 0,
        "tl_nqh2": jn["nqh2"].sum() / jn["dn2"].sum() * 100 if jn["dn2"].sum() else 0,
    }
    jn = pd.concat([jn.sort_values("delta_dn", ascending=False),
                    pd.DataFrame([tong])], ignore_index=True)

    rows_html = ""
    for _, r in jn.iterrows():
        is_tong = str(r["ten_pgd"]).startswith("⬛")
        bold = "font-weight:700;" if is_tong else ""
        bg   = "background:#f0f4f8;" if is_tong else ""
        mau_dn  = _mau_delta(r["delta_dn"],  False)
        mau_nqh = _mau_delta(r["tl_nqh2"] - r["tl_nqh1"], True)
        rows_html += (
            f"<tr style='border-bottom:1px solid #e5e7eb;{bg}'>"
            f"<td style='padding:7px 10px;{bold}'>{r['ten_pgd']}</td>"
            f"<td style='padding:7px 10px;text-align:right'>{fmt_ty(r['dn1'])}</td>"
            f"<td style='padding:7px 10px;text-align:right;{bold}'>{fmt_ty(r['dn2'])}</td>"
            f"<td style='padding:7px 10px;text-align:right;color:{mau_dn};{bold}'>"
            f"{_delta_fmt(r['delta_dn'], 'tien')}</td>"
            f"<td style='padding:7px 10px;text-align:right;{bold}'>{_fmt_pct(r['tl_nqh1'])}</td>"
            f"<td style='padding:7px 10px;text-align:right;{bold}'>{_fmt_pct(r['tl_nqh2'])}</td>"
            f"<td style='padding:7px 10px;text-align:right;color:{mau_nqh};{bold}'>"
            f"{_delta_fmt(r['tl_nqh2'] - r['tl_nqh1'], 'pct')}</td>"
            f"<td style='padding:7px 10px;text-align:right'>{fmt_so(int(r['ho2']))}</td>"
            f"<td style='padding:7px 10px;text-align:right;color:{_mau_delta(r['delta_ho'], False)}'>"
            f"{_delta_fmt(r['delta_ho'], 'so')}</td>"
            f"</tr>"
        )

    st.markdown(
        f"""<div style="overflow-x:auto;border-radius:8px;border:1px solid #e5e7eb;margin-top:8px">
        <table style="width:100%;border-collapse:collapse;font-size:0.88rem">
          <thead>
            <tr style="background:#1e3a5f;color:white">
              <th style="padding:9px 10px;text-align:left">Đơn vị</th>
              <th style="padding:9px 10px;text-align:right">DN kỳ {ky1}</th>
              <th style="padding:9px 10px;text-align:right">DN kỳ {ky2}</th>
              <th style="padding:9px 10px;text-align:right">Δ Dư nợ</th>
              <th style="padding:9px 10px;text-align:right">NQH% {ky1}</th>
              <th style="padding:9px 10px;text-align:right">NQH% {ky2}</th>
              <th style="padding:9px 10px;text-align:right">Δ NQH%</th>
              <th style="padding:9px 10px;text-align:right">Số hộ {ky2}</th>
              <th style="padding:9px 10px;text-align:right">Δ Hộ</th>
            </tr>
          </thead>
          <tbody>{rows_html}</tbody>
        </table></div>""",
        unsafe_allow_html=True,
    )


# ──────────────────────────────────────────────
# BIỂU ĐỒ (CN only)
# ──────────────────────────────────────────────

def _render_bieu_do(df1: pd.DataFrame, df2: pd.DataFrame,
                    ky1: str, ky2: str) -> None:
    """Horizontal bar chart biến động dư nợ theo PGD."""
    m1 = df1[["ten_pgd", "tong_du_no"]].rename(columns={"tong_du_no": "dn1"})
    m2 = df2[["ten_pgd", "tong_du_no"]].rename(columns={"tong_du_no": "dn2"})
    jn = pd.merge(m1, m2, on="ten_pgd", how="outer").fillna(0)
    jn["delta"] = jn["dn2"] - jn["dn1"]
    jn = jn[~jn["ten_pgd"].str.startswith("__")].sort_values("delta")

    if jn.empty:
        return

    colors = ["#16a34a" if d >= 0 else "#dc2626" for d in jn["delta"]]
    labels = [_delta_fmt(d, "tien") for d in jn["delta"]]

    fig = go.Figure(go.Bar(
        y=jn["ten_pgd"].astype(str),
        x=jn["delta"],
        orientation="h",
        marker_color=colors,
        text=labels,
        textposition="outside",
    ))
    fig.update_layout(
        title=dict(text=f"Biến động dư nợ: {ky1} → {ky2}", font_size=14),
        height=max(280, len(jn) * 36 + 80),
        margin=dict(t=40, b=20, l=10, r=100),
        xaxis_title="Triệu đồng",
        yaxis_title="",
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True, key="ss2k_chart_dn")


# ──────────────────────────────────────────────
# XUẤT EXCEL
# ──────────────────────────────────────────────

def _render_export(agg1: dict, agg2: dict,
                   df1: pd.DataFrame, df2: pd.DataFrame,
                   ky1: str, ky2: str,
                   pgd_mode: bool, username: str) -> None:
    tl1 = _tl_nqh(agg1)
    tl2 = _tl_nqh(agg2)

    rows_tq = [
        ("Tổng dư nợ (triệu đồng)",      fmt_ty(agg1["tong_du_no"]),   fmt_ty(agg2["tong_du_no"]),
         _delta_fmt(agg2["tong_du_no"] - agg1["tong_du_no"], "tien"),
         _pct_change(agg1["tong_du_no"], agg2["tong_du_no"])),
        ("Dư nợ trong hạn (triệu đồng)", fmt_ty(agg1["du_no_th"]),     fmt_ty(agg2["du_no_th"]),
         _delta_fmt(agg2["du_no_th"] - agg1["du_no_th"], "tien"),
         _pct_change(agg1["du_no_th"], agg2["du_no_th"])),
        ("Dư nợ quá hạn (triệu đồng)",   fmt_ty(agg1["du_no_qh"]),     fmt_ty(agg2["du_no_qh"]),
         _delta_fmt(agg2["du_no_qh"] - agg1["du_no_qh"], "tien"),
         _pct_change(agg1["du_no_qh"], agg2["du_no_qh"])),
        ("Dư nợ khoanh (triệu đồng)",    fmt_ty(agg1["du_no_khoanh"]), fmt_ty(agg2["du_no_khoanh"]),
         _delta_fmt(agg2["du_no_khoanh"] - agg1["du_no_khoanh"], "tien"),
         _pct_change(agg1["du_no_khoanh"], agg2["du_no_khoanh"])),
        ("Tỷ lệ NQH (%)",                _fmt_pct(tl1),                _fmt_pct(tl2),
         _delta_fmt(tl2 - tl1, "pct"), "—"),
        ("Số hộ vay",                    fmt_so(int(agg1["so_ho"])),   fmt_so(int(agg2["so_ho"])),
         _delta_fmt(agg2["so_ho"] - agg1["so_ho"], "so"),
         _pct_change(agg1["so_ho"], agg2["so_ho"])),
        ("Số khế ước",                   fmt_so(int(agg1["so_ku"])),   fmt_so(int(agg2["so_ku"])),
         _delta_fmt(agg2["so_ku"] - agg1["so_ku"], "so"),
         _pct_change(agg1["so_ku"], agg2["so_ku"])),
        ("Giải ngân trong năm (tr.đ)",   fmt_ty(agg1["gn_nam"]),       fmt_ty(agg2["gn_nam"]),
         _delta_fmt(agg2["gn_nam"] - agg1["gn_nam"], "tien"),
         _pct_change(agg1["gn_nam"], agg2["gn_nam"])),
    ]
    df_tq = pd.DataFrame(rows_tq, columns=["Chỉ tiêu", f"Kỳ {ky1}", f"Kỳ {ky2}", "Chênh lệch", "% thay đổi"])

    sheets: dict = {"Tổng quan": df_tq}

    if not pgd_mode and not df1.empty and not df2.empty:
        m1 = df1[["ten_pgd", "tong_du_no", "du_no_qh", "so_ho"]].copy()
        m2 = df2[["ten_pgd", "tong_du_no", "du_no_qh", "so_ho"]].copy()
        m1.columns = ["Đơn vị", f"DN {ky1}", f"NQH {ky1}", f"Hộ {ky1}"]
        m2.columns = ["Đơn vị", f"DN {ky2}", f"NQH {ky2}", f"Hộ {ky2}"]
        df_pgd = pd.merge(m1, m2, on="Đơn vị", how="outer").fillna(0)
        df_pgd["Δ Dư nợ"] = df_pgd[f"DN {ky2}"] - df_pgd[f"DN {ky1}"]
        sheets["Theo PGD"] = df_pgd

    xl = xuat_excel(sheets)
    st.download_button(
        "📥 Xuất Excel",
        data=xl,
        file_name=f"so_sanh_{ky1}_vs_{ky2}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key="ss2k_dl_excel",
        use_container_width=True,
    )
    db.ghi_audit(username, "xuat_bieu_cn",
                 f"Xuất Excel so sánh 2 kỳ: {ky1} vs {ky2}")


# ──────────────────────────────────────────────
# RENDER CHÍNH
# ──────────────────────────────────────────────

def render(tab: DeltaGenerator = None, **kwargs) -> None:
    """So sánh 2 kỳ snapshot bất kỳ.

    Kwargs:
        role, username, pgd_user, pgd_mode (bool)
    Không cần df/df_full — lấy dữ liệu từ hstd_snapshot.
    """
    ctx = get_tab_context(tab)
    role     = normalize_role(str(kwargs.get("role", "user")))
    username = kwargs.get("username", "unknown")
    pgd_user = kwargs.get("pgd_user")
    pgd_mode = bool(kwargs.get("pgd_mode", False)) or (
        pgd_user is not None and la_phan_he_pgd(role)
    )

    with ctx:
        st.subheader("🔄 So sánh 2 kỳ")

        # ── Kiểm tra snapshot ──
        ds_ky = danh_sach_ky()
        if len(ds_ky) < 2:
            st.warning(
                "⚠️ Cần ít nhất **2 kỳ snapshot** để so sánh. "
                "Hãy upload và merge dữ liệu ít nhất 2 tháng để hệ thống tạo snapshot tự động."
            )
            return

        # ── Chọn 2 kỳ ──
        col_k1, col_k2 = st.columns(2)
        ky1 = col_k1.selectbox(
            "📅 Kỳ 1 — mốc gốc",
            ds_ky,
            index=min(1, len(ds_ky) - 1),
            key="ss2k_ky1",
            help="Kỳ dùng làm mốc so sánh (thường là kỳ cũ hơn)",
        )
        ky2 = col_k2.selectbox(
            "📅 Kỳ 2 — kỳ so sánh",
            ds_ky,
            index=0,
            key="ss2k_ky2",
            help="Kỳ muốn đánh giá biến động (thường là kỳ mới hơn)",
        )

        if ky1 == ky2:
            st.warning("⚠️ Vui lòng chọn **2 kỳ khác nhau**.")
            return

        # ── Tải dữ liệu ──
        df1 = doc_snapshot(ky1)
        df2 = doc_snapshot(ky2)

        if df1.empty or df2.empty:
            st.warning("⚠️ Một hoặc cả hai kỳ chưa có dữ liệu snapshot.")
            return

        # ── Lọc PGD (nếu cần) ──
        if pgd_mode and pgd_user:
            df1 = df1[df1["ten_pgd"] == pgd_user].reset_index(drop=True)
            df2 = df2[df2["ten_pgd"] == pgd_user].reset_index(drop=True)

            if df1.empty or df2.empty:
                st.warning(f"⚠️ Chưa có dữ liệu snapshot cho **{pgd_user}** trong kỳ đã chọn.")
                return

        agg1 = _agg(df1)
        agg2 = _agg(df2)

        st.caption(
            f"So sánh **{ky1}** → **{ky2}** "
            + (f"· {pgd_user}" if pgd_mode and pgd_user else "· Toàn Chi nhánh")
        )
        st.divider()

        # ── KPI cards ──
        _render_kpi(agg1, agg2, ky1, ky2)

        st.divider()

        # ── Bảng chi tiết ──
        st.markdown("**📊 Bảng so sánh chi tiết**")
        _render_bang_chi_tiet(agg1, agg2, ky1, ky2)

        # ── Bảng & biểu đồ theo PGD (CN only) ──
        if not pgd_mode:
            st.divider()
            st.markdown("**🏢 Biến động theo đơn vị**")
            _render_bang_pgd(df1, df2, ky1, ky2)

            st.divider()
            _render_bieu_do(df1, df2, ky1, ky2)

        # ── Xuất Excel ──
        st.divider()
        _render_export(agg1, agg2, df1, df2, ky1, ky2, pgd_mode, username)
