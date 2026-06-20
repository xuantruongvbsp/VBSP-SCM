"""Stress test danh mục tín dụng — mô phỏng kịch bản rủi ro."""
from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st
from streamlit.delta_generator import DeltaGenerator

from auth import la_phan_he_cn, normalize_role
from config import (
    COT_DU_NO_QH,
    COT_MA_KH,
    COT_TEN_CT,
    COT_TEN_PGD,
    COT_TONG_DU_NO,
    DON_VI_CHI_NHANH,
    DS_PGD,
)
from utils import fmt_so, fmt_ty


# ── Hằng số ──────────────────────────────────────────────────────────────────

_PHUONG_PHAP = {
    "proportional": "Phân bổ đều theo PGD (random)",
    "worst_first":  "Ưu tiên KH dư nợ lớn nhất",
    "best_first":   "Ưu tiên KH dư nợ nhỏ nhất",
}

_NGUONG_NQH_PCT = 3.0  # % NQH an toàn


# ── Logic tính toán ───────────────────────────────────────────────────────────

def _run_stress(
    df: pd.DataFrame,
    ty_le_mat_kn: float,
    phuong_phap: str,
    seed: int = 42,
) -> dict:
    """
    Mô phỏng kịch bản: ty_le_mat_kn% KH mất khả năng trả nợ.
    Trả về dict kết quả tổng hợp và chi tiết theo PGD.
    """
    rng = np.random.default_rng(seed)

    # Chỉ lấy KH còn dư nợ
    df_kh = df[pd.to_numeric(df[COT_TONG_DU_NO], errors="coerce").fillna(0) > 0].copy()
    df_kh[COT_TONG_DU_NO] = pd.to_numeric(df_kh[COT_TONG_DU_NO], errors="coerce").fillna(0)
    df_kh[COT_DU_NO_QH]   = pd.to_numeric(df_kh[COT_DU_NO_QH],   errors="coerce").fillna(0)

    so_kh_total = len(df_kh)
    so_kh_xau   = max(1, int(round(so_kh_total * ty_le_mat_kn / 100)))

    # Chọn KH theo phương pháp
    if phuong_phap == "worst_first":
        idx_selected = df_kh[COT_TONG_DU_NO].nlargest(so_kh_xau).index
    elif phuong_phap == "best_first":
        idx_selected = df_kh[COT_TONG_DU_NO].nsmallest(so_kh_xau).index
    else:  # proportional / random
        idx_selected = df_kh.sample(n=min(so_kh_xau, len(df_kh)), random_state=int(rng.integers(1e6))).index

    df_xau = df_kh.loc[idx_selected]

    # Tổng dư nợ hiện tại
    dn_hien_tai  = df_kh[COT_TONG_DU_NO].sum()
    nqh_hien_tai = df_kh[COT_DU_NO_QH].sum()

    # Dư nợ thêm chuyển sang NQH (giả định toàn bộ dư nợ của KH mất KN)
    dn_them_nqh   = df_xau[COT_TONG_DU_NO].sum()
    nqh_du_kien   = nqh_hien_tai + dn_them_nqh
    ty_le_nqh_ht  = nqh_hien_tai  / dn_hien_tai * 100 if dn_hien_tai > 0 else 0
    ty_le_nqh_dk  = nqh_du_kien   / dn_hien_tai * 100 if dn_hien_tai > 0 else 0

    # Chi tiết theo PGD
    pgd_rows = []
    for pgd in df_kh[COT_TEN_PGD].dropna().unique():
        if pgd == DON_VI_CHI_NHANH:
            continue
        df_pgd     = df_kh[df_kh[COT_TEN_PGD] == pgd]
        df_pgd_xau = df_xau[df_xau[COT_TEN_PGD] == pgd] if COT_TEN_PGD in df_xau.columns else pd.DataFrame()
        dn_pgd     = df_pgd[COT_TONG_DU_NO].sum()
        nqh_pgd    = df_pgd[COT_DU_NO_QH].sum()
        them_pgd   = df_pgd_xau[COT_TONG_DU_NO].sum() if not df_pgd_xau.empty else 0
        nqh_dk_pgd = nqh_pgd + them_pgd
        tl_ht      = nqh_pgd   / dn_pgd * 100 if dn_pgd > 0 else 0
        tl_dk      = nqh_dk_pgd / dn_pgd * 100 if dn_pgd > 0 else 0
        pgd_rows.append({
            "PGD":              pgd,
            "Dư nợ (tr.đ)":    dn_pgd   / 1e6,
            "NQH hiện tại":     nqh_pgd  / 1e6,
            "NQH dự kiến":      nqh_dk_pgd / 1e6,
            "Thêm NQH":         them_pgd / 1e6,
            "Tỷ lệ NQH HT (%)": tl_ht,
            "Tỷ lệ NQH DK (%)": tl_dk,
            "Vượt ngưỡng":      tl_dk >= _NGUONG_NQH_PCT,
        })

    df_pgd_result = pd.DataFrame(pgd_rows).sort_values("Tỷ lệ NQH DK (%)", ascending=False)

    # Chi tiết theo CT
    ct_rows = []
    for ct, grp in df_kh.groupby(COT_TEN_CT, dropna=True):
        df_ct_xau = df_xau[df_xau[COT_TEN_CT] == ct] if COT_TEN_CT in df_xau.columns else pd.DataFrame()
        dn_ct     = grp[COT_TONG_DU_NO].sum()
        nqh_ct    = grp[COT_DU_NO_QH].sum()
        them_ct   = df_ct_xau[COT_TONG_DU_NO].sum() if not df_ct_xau.empty else 0
        ct_rows.append({
            "Chương trình":      ct,
            "Dư nợ (tr.đ)":     dn_ct  / 1e6,
            "NQH dự kiến (tr.đ)": (nqh_ct + them_ct) / 1e6,
            "Tỷ lệ NQH DK (%)": (nqh_ct + them_ct) / dn_ct * 100 if dn_ct > 0 else 0,
        })
    df_ct_result = pd.DataFrame(ct_rows).sort_values("Tỷ lệ NQH DK (%)", ascending=False)

    return {
        "so_kh_total":    so_kh_total,
        "so_kh_xau":      so_kh_xau,
        "dn_hien_tai":    dn_hien_tai,
        "nqh_hien_tai":   nqh_hien_tai,
        "dn_them_nqh":    dn_them_nqh,
        "nqh_du_kien":    nqh_du_kien,
        "ty_le_nqh_ht":   ty_le_nqh_ht,
        "ty_le_nqh_dk":   ty_le_nqh_dk,
        "df_pgd":         df_pgd_result,
        "df_ct":          df_ct_result,
    }


def _fmt_pct(x: float) -> str:
    return f"{x:.2f}".replace(".", ",") + "%"


def _color_row(row) -> list[str]:
    """Tô màu dòng vượt ngưỡng NQH."""
    if row.get("Vượt ngưỡng", False):
        return ["background-color: #3D1010; color: #FFCDD2"] * len(row)
    return [""] * len(row)


# ── UI ───────────────────────────────────────────────────────────────────────

def render(tab: DeltaGenerator = None, **kwargs) -> None:
    """Stress test danh mục tín dụng."""
    df_full  = kwargs.get("df_full")
    if df_full is None:
        df_full = kwargs.get("df")
    role_raw = str(kwargs.get("role", "user") or "user")
    role     = normalize_role(role_raw)

    ctx = tab if tab is not None else st.container()
    with ctx:
        st.subheader("🧪 Stress Test Danh mục Tín dụng")
        st.caption(
            "Mô phỏng kịch bản rủi ro: nếu X% khách hàng mất khả năng trả nợ → "
            "NQH toàn danh mục sẽ ở mức nào?"
        )

        if df_full is None or df_full.empty:
            st.warning("⚠️ Chưa có dữ liệu HSTD.")
            return

        # Lọc bỏ Hội sở
        df = df_full[df_full[COT_TEN_PGD] != DON_VI_CHI_NHANH].copy() if COT_TEN_PGD in df_full.columns else df_full.copy()

        # ── Bảng điều khiển ───────────────────────────────────────────────────
        st.divider()
        c1, c2, c3 = st.columns([2, 2, 1])
        with c1:
            ty_le = st.select_slider(
                "Tỷ lệ KH mất khả năng trả nợ (%)",
                options=[0.5, 1.0, 2.0, 3.0, 5.0, 7.0, 10.0, 15.0, 20.0],
                value=3.0,
                key="st_ty_le",
            )
        with c2:
            phuong_phap = st.selectbox(
                "Phương pháp chọn KH",
                options=list(_PHUONG_PHAP.keys()),
                format_func=lambda k: _PHUONG_PHAP[k],
                key="st_pp",
            )
        with c3:
            seed = st.number_input("Seed (random)", value=42, min_value=0, max_value=9999,
                                   key="st_seed", help="Thay đổi để chạy kịch bản khác nhau")
            btn_run = st.button("▶ Chạy Kịch bản", use_container_width=True, key="st_run",
                                type="primary")

        if not btn_run and "st_result" not in st.session_state:
            st.info("👆 Chọn tham số và nhấn **▶ Chạy Kịch bản** để bắt đầu mô phỏng.")
            return

        if btn_run:
            with st.spinner("Đang mô phỏng..."):
                st.session_state["st_result"] = _run_stress(df, ty_le, phuong_phap, int(seed))
                st.session_state["st_params"]  = (ty_le, phuong_phap, seed)

        res = st.session_state.get("st_result")
        if not res:
            return

        ty_le_used, pp_used, seed_used = st.session_state.get("st_params", (ty_le, phuong_phap, seed))

        # ── KPI tổng hợp ───────────────────────────────────────────────────────
        st.divider()
        st.markdown(
            f"**Kịch bản:** {ty_le_used}% KH mất khả năng trả nợ "
            f"→ **{fmt_so(res['so_kh_xau'])} / {fmt_so(res['so_kh_total'])} KH** bị ảnh hưởng"
        )

        k1, k2, k3, k4 = st.columns(4)
        tl_ht_str  = _fmt_pct(res["ty_le_nqh_ht"])
        tl_dk_str  = _fmt_pct(res["ty_le_nqh_dk"])
        tang_str   = _fmt_pct(res["ty_le_nqh_dk"] - res["ty_le_nqh_ht"])
        canh_bao   = res["ty_le_nqh_dk"] >= _NGUONG_NQH_PCT

        k1.metric("Dư nợ hiện tại",  fmt_ty(res["dn_hien_tai"]) + " tr.đ")
        k2.metric("NQH hiện tại",    tl_ht_str,  delta=None)
        k3.metric(
            "NQH dự kiến",
            tl_dk_str,
            delta=f"↑ {tang_str}",
            delta_color="inverse",
        )
        k4.metric("Thêm NQH",        fmt_ty(res["dn_them_nqh"]) + " tr.đ")

        if canh_bao:
            st.error(
                f"🔴 **Cảnh báo:** NQH dự kiến {tl_dk_str} vượt ngưỡng an toàn {_fmt_pct(_NGUONG_NQH_PCT)}. "
                "Cần có phương án dự phòng rủi ro."
            )
        else:
            st.success(
                f"✅ NQH dự kiến {tl_dk_str} — vẫn trong ngưỡng an toàn {_fmt_pct(_NGUONG_NQH_PCT)}."
            )

        # ── Bảng theo PGD ──────────────────────────────────────────────────────
        st.divider()
        st.markdown("#### Tác động theo PGD")

        df_pgd = res["df_pgd"].copy()
        so_vuot = int(df_pgd["Vượt ngưỡng"].sum())
        if so_vuot:
            st.warning(f"⚠️ {so_vuot} PGD có NQH dự kiến vượt ngưỡng {_fmt_pct(_NGUONG_NQH_PCT)}")

        # Hiển thị bảng dạng HTML để tránh NumberColumn kiểu Mỹ
        fmt_cols = ["Dư nợ (tr.đ)", "NQH hiện tại", "NQH dự kiến", "Thêm NQH"]
        df_show  = df_pgd.drop(columns=["Vượt ngưỡng"]).copy()
        for col in fmt_cols:
            df_show[col] = df_show[col].apply(lambda x: fmt_ty(x * 1e6))
        df_show["Tỷ lệ NQH HT (%)"] = df_show["Tỷ lệ NQH HT (%)"].apply(_fmt_pct)
        df_show["Tỷ lệ NQH DK (%)"] = df_pgd["Tỷ lệ NQH DK (%)"].apply(_fmt_pct)

        # Tô màu dòng vượt ngưỡng
        def _style(r):
            idx = df_pgd.index[df_show.index.get_loc(r.name)]
            if df_pgd.loc[idx, "Vượt ngưỡng"]:
                return ["background-color:#3D1010;color:#FFCDD2"] * len(r)
            return [""] * len(r)

        st.dataframe(
            df_show.style.apply(_style, axis=1),
            use_container_width=True,
            hide_index=True,
        )

        # ── Bảng theo Chương trình ─────────────────────────────────────────────
        st.divider()
        st.markdown("#### Tác động theo Chương trình Tín dụng")
        df_ct = res["df_ct"].copy()
        df_ct["Dư nợ (tr.đ)"]          = df_ct["Dư nợ (tr.đ)"].apply(lambda x: fmt_ty(x * 1e6))
        df_ct["NQH dự kiến (tr.đ)"]     = df_ct["NQH dự kiến (tr.đ)"].apply(lambda x: fmt_ty(x * 1e6))
        df_ct["Tỷ lệ NQH DK (%)"]       = res["df_ct"]["Tỷ lệ NQH DK (%)"].apply(_fmt_pct)
        st.dataframe(df_ct, use_container_width=True, hide_index=True)

        # ── Chú thích phương pháp ──────────────────────────────────────────────
        with st.expander("ℹ️ Giả định & Phương pháp"):
            st.markdown(f"""
**Giả định:**
- {ty_le_used}% trong tổng số **{fmt_so(res['so_kh_total'])} KH** còn dư nợ sẽ mất khả năng trả nợ
- **Toàn bộ dư nợ** của những KH này chuyển sang NQH (kịch bản bi quan nhất)
- Không tính phần thu hồi tài sản bảo đảm

**Phương pháp chọn KH:** {_PHUONG_PHAP[ty_le_used if isinstance(ty_le_used, str) else pp_used]}

**Seed:** {seed_used} — Thay đổi seed để kiểm tra độ nhạy của mô hình

**Ngưỡng an toàn:** NQH ≤ {_fmt_pct(_NGUONG_NQH_PCT)} (theo quy định nội bộ)
""")
