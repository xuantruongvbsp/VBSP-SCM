"""Phân tích Nợ khoanh — danh mục khoản vay đang trong giai đoạn khoanh nợ QĐ 62.

Port từ VSPPRO Khoanh.tsx.
KPI cards + breakdown theo Chương trình / Xã / ĐVUT + danh sách chi tiết.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st
from streamlit.delta_generator import DeltaGenerator

from auth import la_phan_he_cn, normalize_role, get_permissions, co_quyen_upload_pgd
from config import (
    COT_DU_NO_QH,
    COT_DVUT,
    COT_MA_KH,
    COT_NGAY_DH,
    COT_SO_KU,
    COT_TEN_CT,
    COT_TEN_KH,
    COT_TEN_PGD,
    COT_TEN_XA,
    COT_TONG_DU_NO,
    DS_PGD,
    LY_DO_KHOANH_QD62,
    LY_DO_KHOANH_LABEL,
)
from utils import fmt_so, fmt_ty, hien_thi_dataframe_phan_trang, xuat_excel
import db

COT_DU_NO_KHOANH = "Dư nợ khoanh"
COT_NGAY_HH_KHOANH = "Ngày hết hạn Khoanh"
COT_TEN_TO = "Tên tổ"


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _loc_khoanh(df: pd.DataFrame) -> pd.DataFrame:
    """Lọc các món vay đang khoanh nợ (Dư nợ khoanh > 0)."""
    if COT_DU_NO_KHOANH not in df.columns:
        return pd.DataFrame()
    du_kh = pd.to_numeric(df[COT_DU_NO_KHOANH], errors="coerce").fillna(0)
    return df[du_kh > 0].copy()


def _bang_theo_nhom(df: pd.DataFrame, nhom_col: str) -> pd.DataFrame:
    """Bảng tổng hợp: nhóm | Số món | Dư nợ khoanh | Tỷ trọng%."""
    if nhom_col not in df.columns or df.empty:
        return pd.DataFrame()

    du_kh = pd.to_numeric(df[COT_DU_NO_KHOANH], errors="coerce").fillna(0)
    df = df.copy()
    df["_du_kh"] = du_kh

    nhom = (
        df.groupby(nhom_col)
        .agg(so_mon=(COT_SO_KU, "nunique"), du_no_khoanh=("_du_kh", "sum"))
        .reset_index()
        .sort_values("du_no_khoanh", ascending=False)
    )

    tong = nhom["du_no_khoanh"].sum()
    nhom["Tỷ trọng%"] = (nhom["du_no_khoanh"] / tong * 100).round(1).apply(
        lambda x: f"{x:.1f}".replace(".", ",") + "%"
    ) if tong > 0 else "0%"
    nhom[COT_DU_NO_KHOANH] = nhom["du_no_khoanh"].apply(fmt_ty)
    nhom = nhom.rename(columns={"so_mon": "Số món"})
    return nhom[[nhom_col, "Số món", COT_DU_NO_KHOANH, "Tỷ trọng%"]]


def _chart_nhom(df: pd.DataFrame, nhom_col: str, key: str) -> None:
    """Horizontal bar chart: top 15 nhóm theo dư nợ khoanh."""
    try:
        import plotly.express as px
    except ImportError:
        return

    if df.empty or nhom_col not in df.columns:
        return

    du_kh = pd.to_numeric(df[COT_DU_NO_KHOANH], errors="coerce").fillna(0)
    df = df.copy()
    df["_du_kh"] = du_kh

    nhom = df.groupby(nhom_col)["_du_kh"].sum().reset_index()
    nhom.columns = [nhom_col, "_val"]
    nhom = nhom[nhom["_val"] > 0].sort_values("_val", ascending=True).tail(15)
    if nhom.empty:
        return

    nhom["Label"] = nhom["_val"].apply(fmt_ty)

    fig = px.bar(
        nhom, y=nhom_col, x="_val",
        orientation="h",
        text="Label",
        color="_val",
        color_continuous_scale=["#fff3e0", "#e65100"],
    )
    fig.update_traces(textposition="outside")
    fig.update_layout(
        height=max(260, len(nhom) * 28 + 80),
        margin=dict(t=10, b=20, l=10, r=70),
        coloraxis_showscale=False,
        xaxis_title="Dư nợ khoanh (VND)",
        yaxis_title="",
    )
    st.plotly_chart(fig, width='stretch', key=key)


def _heatmap_dao_han(df: pd.DataFrame, key: str) -> None:
    """Bar chart phân bổ khoanh theo tháng đáo hạn."""
    try:
        import plotly.graph_objects as go
    except ImportError:
        return

    if COT_NGAY_DH not in df.columns or df.empty:
        return

    ngay_dh = pd.to_datetime(df[COT_NGAY_DH], errors="coerce", dayfirst=True)
    df = df.copy()
    df["_du_kh"] = pd.to_numeric(df[COT_DU_NO_KHOANH], errors="coerce").fillna(0)
    df["_ym"] = ngay_dh.dt.to_period("Y").astype(str)  # nhóm theo năm

    nhom = (
        df.groupby("_ym")
        .agg(so_mon=("_ym", "count"), du_no=("_du_kh", "sum"))
        .reset_index()
        .sort_values("_ym")
    )
    nhom = nhom[nhom["_ym"].str.match(r"\d{4}")]  # loại NaT

    if nhom.empty:
        return

    fig = go.Figure(go.Bar(
        x=nhom["_ym"],
        y=nhom["so_mon"],
        name="Số món",
        marker_color="#e64a19",
        text=nhom["so_mon"].astype(str),
        textposition="outside",
        hovertext=nhom["du_no"].apply(fmt_ty),
        hoverinfo="x+text",
    ))
    fig.update_layout(
        xaxis_title="Năm đáo hạn",
        yaxis_title="Số khoản khoanh",
        height=260,
        margin=dict(t=10, b=30, l=40, r=20),
    )
    st.markdown("**📅 Phân bổ theo năm đáo hạn**")
    st.plotly_chart(fig, width='stretch', key=key)


# ─── Render ───────────────────────────────────────────────────────────────────

def render(tab: DeltaGenerator = None, **kwargs) -> None:
    """
    Render tab Phân tích Nợ khoanh.

    Dùng được ở cả phân hệ CN (truyền df_full) và PGD.
    """
    df       = kwargs.get("df")
    df_full  = kwargs.get("df_full", df)
    role_raw = str(kwargs.get("role", "user") or "user")
    role     = normalize_role(role_raw)
    pgd_user = kwargs.get("pgd_user")

    ctx = tab if tab is not None else st.container()
    with ctx:
        st.subheader("🔒 Phân tích Nợ khoanh")
        st.caption(
            "Khoản vay đang trong giai đoạn khoanh nợ theo QĐ 62/2015/QĐ-TTg. "
            "Phân tích theo Chương trình / Xã / Hội đoàn thể."
        )

        use_df = df_full if la_phan_he_cn(role) else df
        if use_df is None or use_df.empty:
            st.warning("⚠️ Chưa có dữ liệu HSTD.")
            return

        if COT_DU_NO_KHOANH not in use_df.columns:
            st.info(
                f"ℹ️ Dữ liệu không có cột '{COT_DU_NO_KHOANH}'. "
                "Cần upload HSTD có cột Dư nợ khoanh."
            )
            return

        df_kh = _loc_khoanh(use_df)

        # ── KPI tổng quan ─────────────────────────────────────────────────
        tong_du_no = (
            pd.to_numeric(use_df[COT_TONG_DU_NO], errors="coerce").sum()
            if COT_TONG_DU_NO in use_df.columns else 0
        )
        tong_khoanh = (
            pd.to_numeric(use_df[COT_DU_NO_KHOANH], errors="coerce").fillna(0).sum()
        )
        so_mon = (
            df_kh[COT_SO_KU].nunique() if (not df_kh.empty and COT_SO_KU in df_kh.columns)
            else len(df_kh)
        )
        so_ho = (
            df_kh[COT_MA_KH].nunique() if (not df_kh.empty and COT_MA_KH in df_kh.columns)
            else 0
        )
        tl_khoanh = tong_khoanh / tong_du_no * 100 if tong_du_no > 0 else 0

        k1, k2, k3, k4 = st.columns(4)
        k1.metric("🔒 Số món khoanh", fmt_so(so_mon))
        k2.metric("👤 Số hộ", fmt_so(so_ho))
        k3.metric("💰 Tổng dư nợ khoanh", fmt_ty(tong_khoanh))
        k4.metric(
            "📊 Tỷ lệ khoanh / tổng DN",
            f"{tl_khoanh:.2f}".replace(".", ",") + "%",
            delta=f"{tl_khoanh:.2f}".replace(".", ",") + "%" if tl_khoanh > 0 else None,
            delta_color="inverse" if tl_khoanh > 2 else "off",
        )

        if df_kh.empty:
            st.success("✅ Hiện không có món vay nào đang khoanh nợ.")
            return

        st.divider()

        # ── Lọc PGD (CN only) ─────────────────────────────────────────────
        key_prefix = "cn_"
        if la_phan_he_cn(role):
            col_f, _ = st.columns([2, 4])
            with col_f:
                pgd_chon = st.selectbox(
                    "🔍 Lọc PGD",
                    ["Tất cả"] + DS_PGD,
                    key="khoanh_pgd_loc",
                )
            if pgd_chon != "Tất cả" and COT_TEN_PGD in df_kh.columns:
                df_kh = df_kh[df_kh[COT_TEN_PGD] == pgd_chon]
        else:
            from data.pgd import pgd_slug
            key_prefix = f"pgd_{pgd_slug(pgd_user)}_" if pgd_user else "pgd_"

        # ── Heatmap đáo hạn ───────────────────────────────────────────────
        _heatmap_dao_han(df_kh, key=f"{key_prefix}khoanh_hm")

        st.divider()

        # ── Sub-tabs ──────────────────────────────────────────────────────
        d1, d2, d3, d4, d5, d6, d7 = st.tabs([
            "📋 Theo Chương trình",
            "🏘️ Theo Xã",
            "🤝 Theo Hội đoàn thể",
            "📄 Danh sách chi tiết",
            "📅 Kế hoạch",
            "✏️ Kiểm tra",
            "📊 Báo cáo",
        ])

        for dtab, nhom_col, tag, label in [
            (d1, COT_TEN_CT,  "ct",   "Chương trình"),
            (d2, COT_TEN_XA,  "xa",   "Xã"),
            (d3, COT_DVUT,    "dvut", "Hội đoàn thể"),
        ]:
            with dtab:
                if nhom_col not in df_kh.columns:
                    st.info(f"Không có cột {label} trong dữ liệu.")
                    continue
                c_chart, c_table = st.columns([3, 2])
                with c_chart:
                    _chart_nhom(df_kh, nhom_col, key=f"{key_prefix}khoanh_{tag}_chart")
                with c_table:
                    bng = _bang_theo_nhom(df_kh, nhom_col)
                    if not bng.empty:
                        hien_thi_dataframe_phan_trang(
                            bng, key=f"{key_prefix}khoanh_{tag}_tbl", height=320
                        )

        with d4:
            cols_hien = [c for c in [
                COT_TEN_PGD, COT_TEN_XA, COT_DVUT, COT_TEN_KH, COT_SO_KU,
                COT_TEN_CT, COT_DU_NO_KHOANH, COT_DU_NO_QH, COT_NGAY_DH,
            ] if c in df_kh.columns]

            df_hien = df_kh[cols_hien].copy()
            if COT_DU_NO_KHOANH in df_hien.columns:
                df_hien[COT_DU_NO_KHOANH] = (
                    pd.to_numeric(df_hien[COT_DU_NO_KHOANH], errors="coerce")
                    .apply(fmt_ty)
                )
            if COT_DU_NO_QH in df_hien.columns:
                df_hien[COT_DU_NO_QH] = (
                    pd.to_numeric(df_hien[COT_DU_NO_QH], errors="coerce")
                    .apply(fmt_ty)
                )

            hien_thi_dataframe_phan_trang(
                df_hien, key=f"{key_prefix}khoanh_chitiet", height=420
            )

            if st.button(
                f"📥 Xuất Excel ({len(df_kh)} món)",
                key=f"{key_prefix}khoanh_xuat",
            ):
                st.session_state[f"_{key_prefix}khoanh_buf"] = xuat_excel(
                    {"Nợ khoanh": df_hien}
                )
            if st.session_state.get(f"_{key_prefix}khoanh_buf"):
                st.download_button(
                    "⬇️ Tải về Excel",
                    data=st.session_state[f"_{key_prefix}khoanh_buf"],
                    file_name="NoKhoanh.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key=f"{key_prefix}khoanh_dl",
                )

        with d5:
            perms = get_permissions(role)
            co_quyen_nhap  = perms.get("upload") or perms.get("nhap_ke_hoach")
            co_quyen_duyet = la_phan_he_cn(role) or co_quyen_upload_pgd(role)
            pgd_filter_kh  = None if la_phan_he_cn(role) else pgd_user

            # ── A: Form lập kế hoạch ──────────────────────────────────────────
            with st.expander("➕ Lập kế hoạch kiểm tra mới", expanded=False):
                if not co_quyen_nhap:
                    st.warning("⚠️ Bạn không có quyền lập kế hoạch kiểm tra.")
                else:
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        # Danh sách xã từ df_kh (đã lọc du_no_khoanh > 0)
                        ds_xa = sorted(df_kh[COT_TEN_XA].dropna().unique().tolist()) \
                                if COT_TEN_XA in df_kh.columns else []
                        xa_chon = st.selectbox(
                            "Xã/Phường *",
                            ["— Chọn —"] + ds_xa,
                            key=f"{key_prefix}kh_xa",
                        )
                    with c2:
                        # Lọc tổ TK&VV theo xã đã chọn
                        if xa_chon != "— Chọn —" and COT_TEN_TO in df_kh.columns:
                            ds_to = sorted(
                                df_kh[df_kh[COT_TEN_XA] == xa_chon][COT_TEN_TO]
                                .dropna().unique().tolist()
                            )
                        else:
                            ds_to = []
                        to_chon = st.selectbox(
                            "Tổ TK&VV",
                            ["— Tất cả —"] + ds_to,
                            key=f"{key_prefix}kh_to",
                        )
                    with c3:
                        ngay_kh = st.date_input(
                            "Ngày kiểm tra dự kiến *",
                            key=f"{key_prefix}kh_ngay",
                        )

                    # Thành phần đoàn kiểm tra
                    st.markdown("**Thành phần đoàn kiểm tra**")
                    df_tp_default = pd.DataFrame([
                        {"Họ và tên": username, "Chức vụ/Đơn vị": "CBTD"},
                        {"Họ và tên": "",       "Chức vụ/Đơn vị": ""},
                    ])
                    df_tp = st.data_editor(
                        df_tp_default,
                        num_rows="dynamic",
                        key=f"{key_prefix}kh_thanh_phan",
                        use_container_width=True,
                    )

                    # Chọn món vay đưa vào kế hoạch
                    st.markdown("**Chọn món vay kiểm tra**")
                    df_loc_kh = df_kh.copy()
                    if xa_chon != "— Chọn —" and COT_TEN_XA in df_loc_kh.columns:
                        df_loc_kh = df_loc_kh[df_loc_kh[COT_TEN_XA] == xa_chon]
                    if to_chon != "— Tất cả —" and COT_TEN_TO in df_loc_kh.columns:
                        df_loc_kh = df_loc_kh[df_loc_kh[COT_TEN_TO] == to_chon]

                    if df_loc_kh.empty or COT_SO_KU not in df_loc_kh.columns:
                        st.info("ℹ️ Không có món vay khoanh nào trong phạm vi đã chọn.")
                        ds_chon = []
                    else:
                        # Label: "TênKH — SốKU — LýDoKhoanh"
                        def _label_mon(row):
                            bs = db.doc_bo_sung_mon_vay(str(row.get(COT_SO_KU, "")))
                            ly_do_ma = bs.get("ly_do_khoanh", "") if bs else ""
                            ly_do_str = LY_DO_KHOANH_LABEL.get(ly_do_ma, "Chưa xác định lý do")
                            return (
                                f"{row.get(COT_TEN_KH, '')} — "
                                f"{row.get(COT_SO_KU, '')} — "
                                f"{ly_do_str}"
                            )
                        options_mon = df_loc_kh.apply(_label_mon, axis=1).tolist()
                        ku_list     = df_loc_kh[COT_SO_KU].tolist()
                        label_to_ku = dict(zip(options_mon, ku_list))

                        chon_labels = st.multiselect(
                            f"Chọn món vay ({len(df_loc_kh)} món trong phạm vi)",
                            options=options_mon,
                            key=f"{key_prefix}kh_ds_mon",
                        )
                        ds_chon = [label_to_ku[l] for l in chon_labels]

                    ghi_chu_kh = st.text_area(
                        "Ghi chú",
                        key=f"{key_prefix}kh_ghi_chu",
                        max_chars=500,
                    )

                    col_b1, col_b2, _ = st.columns([1, 1, 4])
                    with col_b1:
                        luu_kh_btn = st.button(
                            "💾 Lưu kế hoạch",
                            key=f"{key_prefix}kh_luu",
                            use_container_width=True,
                        )
                    with col_b2:
                        duyet_kh_btn = st.button(
                            "✅ Duyệt luôn",
                            key=f"{key_prefix}kh_duyet_luon",
                            disabled=not co_quyen_duyet,
                            use_container_width=True,
                        )

                    if luu_kh_btn or duyet_kh_btn:
                        loi_kh = []
                        if xa_chon == "— Chọn —":
                            loi_kh.append("Chưa chọn xã")
                        if not ngay_kh:
                            loi_kh.append("Chưa nhập ngày kiểm tra")
                        if not ds_chon:
                            loi_kh.append("Chưa chọn món vay nào")
                        if loi_kh:
                            for l in loi_kh:
                                st.error(f"❌ {l}")
                        else:
                            thanh_phan_list = df_tp[
                                df_tp["Họ và tên"].str.strip() != ""
                            ].to_dict("records")
                            ten_pgd_kh = (
                                str(df_kh[df_kh[COT_TEN_XA] == xa_chon][COT_TEN_PGD].iloc[0])
                                if (COT_TEN_PGD in df_kh.columns and xa_chon != "— Chọn —"
                                    and not df_kh[df_kh[COT_TEN_XA] == xa_chon].empty)
                                else (pgd_user or "")
                            )
                            data_kh = {
                                "ten_pgd":       ten_pgd_kh,
                                "ten_xa":        xa_chon,
                                "ten_to_tkv":    to_chon if to_chon != "— Tất cả —" else "",
                                "ngay_kiem_tra": str(ngay_kh),
                                "thanh_phan":    thanh_phan_list,
                                "ds_mon_vay":    ds_chon,
                                "ghi_chu":       ghi_chu_kh,
                                "trang_thai":    "cho_duyet",
                            }
                            try:
                                kh_id = db.luu_ke_hoach_kiem_tra(data_kh, username)
                                if duyet_kh_btn:
                                    db.duyet_ke_hoach(kh_id, username)
                                st.cache_data.clear()
                                label_kh = "lưu và duyệt" if duyet_kh_btn else "lưu"
                                st.success(f"✅ Đã {label_kh} kế hoạch kiểm tra.")
                                st.rerun()
                            except Exception as e:
                                st.error(f"❌ Lỗi: {e}")

            # ── B: Danh sách kế hoạch đã lập ─────────────────────────────────
            st.markdown("### 📋 Danh sách kế hoạch kiểm tra")

            col_fkh, _ = st.columns([2, 4])
            with col_fkh:
                loc_tt_kh = st.selectbox(
                    "Trạng thái",
                    ["Tất cả", "Chờ duyệt", "Đã duyệt"],
                    key=f"{key_prefix}kh_loc_tt",
                )
            tt_map_kh = {
                "Tất cả":   None,
                "Chờ duyệt": "cho_duyet",
                "Đã duyệt":  "da_duyet",
            }

            rows_kh = db.doc_ke_hoach_kiem_tra(
                ten_pgd=pgd_filter_kh,
                trang_thai=tt_map_kh[loc_tt_kh],
            )

            if not rows_kh:
                st.info("ℹ️ Chưa có kế hoạch nào.")
            else:
                df_kh_list = pd.DataFrame([{
                    "ID":          r["id"],
                    "PGD":         r["ten_pgd"],
                    "Xã":          r["ten_xa"],
                    "Tổ TK&VV":    r.get("ten_to_tkv", ""),
                    "Ngày KT":     r["ngay_kiem_tra"],
                    "Số món":      len(r.get("ds_mon_vay") or []),
                    "Trạng thái":  r["trang_thai"],
                    "Người lập":   r["nguoi_lap"],
                    "Người duyệt": r.get("nguoi_duyet", ""),
                } for r in rows_kh])

                hien_thi_dataframe_phan_trang(
                    df_kh_list,
                    key=f"{key_prefix}kh_list_tbl",
                    height=320,
                )

                if co_quyen_duyet:
                    st.markdown("**Duyệt kế hoạch theo ID:**")
                    kh_id_action = st.number_input(
                        "ID kế hoạch",
                        min_value=1, step=1,
                        key=f"{key_prefix}kh_action_id",
                    )
                    if st.button(
                        "✅ Duyệt kế hoạch này",
                        key=f"{key_prefix}kh_duyet_id",
                        use_container_width=False,
                    ):
                        ok = db.duyet_ke_hoach(int(kh_id_action), username)
                        st.success("Đã duyệt.") if ok else st.error("Không thể duyệt.")
                        st.rerun()

        with d6:
            perms = get_permissions(role)
            co_quyen_nhap = perms.get("can_upload")
            co_quyen_duyet = la_phan_he_cn(role) or co_quyen_upload_pgd(role)

            with st.expander("➕ Nhập kết quả kiểm tra mới", expanded=False):
                if not co_quyen_nhap:
                    st.warning("⚠️ Bạn không có quyền nhập kết quả kiểm tra.")
                else:
                    c1, c2 = st.columns(2)
                    with c1:
                        if not df_kh.empty and COT_SO_KU in df_kh.columns:
                            options_ku = sorted(df_kh[COT_SO_KU].dropna().unique().tolist())
                            chon_ku = st.selectbox(
                                "Số khế ước *",
                                ["— Chọn —"] + options_ku,
                                key=f"{key_prefix}kt_ku",
                            )
                            row_chon = (
                                df_kh[df_kh[COT_SO_KU] == chon_ku].iloc[0]
                                if chon_ku != "— Chọn —" else None
                            )
                        else:
                            chon_ku = st.text_input(
                                "Số khế ước *", key=f"{key_prefix}kt_ku_txt"
                            )
                            row_chon = None

                        ten_kh_hien = (
                            str(row_chon.get(COT_TEN_KH, "")) if row_chon is not None else ""
                        )
                        st.text_input(
                            "Tên khách hàng",
                            value=ten_kh_hien,
                            disabled=True,
                            key=f"{key_prefix}kt_ten_kh",
                        )

                    with c2:
                        ngay_kt = st.date_input(
                            "Ngày kiểm tra *", key=f"{key_prefix}kt_ngay"
                        )
                        can_bo = st.text_input(
                            "Cán bộ kiểm tra",
                            value=username,
                            key=f"{key_prefix}kt_canbo",
                        )

                    st.markdown("**Thông tin khoanh** *(bổ sung 1 lần nếu chưa có)*")
                    bs_data = (
                        db.doc_bo_sung_mon_vay(chon_ku)
                        if chon_ku and chon_ku != "— Chọn —" else None
                    )
                    c3, c4, c5 = st.columns(3)
                    with c3:
                        ngay_bdk = st.text_input(
                            "Ngày bắt đầu khoanh (dd/mm/yyyy)",
                            value=bs_data.get("ngay_bat_dau_khoanh", "") if bs_data else "",
                            key=f"{key_prefix}kt_bdk",
                        )
                    with c4:
                        so_thang_kh = st.number_input(
                            "Số tháng khoanh",
                            min_value=0, max_value=120, step=1,
                            value=int(bs_data.get("so_thang_khoanh") or 0) if bs_data else 0,
                            key=f"{key_prefix}kt_sothang",
                        )
                    with c5:
                        so_qd = st.text_input(
                            "Số QĐ khoanh",
                            value=bs_data.get("so_quyet_dinh_khoanh", "") if bs_data else "",
                            key=f"{key_prefix}kt_soqd",
                        )

                    st.markdown("**Theo dõi tại ngân hàng** *(prefill từ HSTD, có thể sửa)*")
                    c6, c7, c8 = st.columns(3)
                    with c6:
                        du_no_goc = st.number_input(
                            "Dư nợ gốc (đồng)",
                            min_value=0.0, step=1_000_000.0, format="%.0f",
                            value=float(pd.to_numeric(
                                row_chon.get(COT_TONG_DU_NO, 0), errors="coerce"
                            ) or 0) if row_chon is not None else 0.0,
                            key=f"{key_prefix}kt_no_goc",
                        )
                    with c7:
                        du_no_goc_kh = st.number_input(
                            "Dư nợ gốc khoanh (đồng)",
                            min_value=0.0, step=1_000_000.0, format="%.0f",
                            value=float(pd.to_numeric(
                                row_chon.get(COT_DU_NO_KHOANH, 0), errors="coerce"
                            ) or 0) if row_chon is not None else 0.0,
                            key=f"{key_prefix}kt_no_goc_kh",
                        )
                    with c8:
                        lai_con_no = st.number_input(
                            "Lãi còn nợ NH (đồng)",
                            min_value=0.0, step=100_000.0, format="%.0f",
                            key=f"{key_prefix}kt_lai_con",
                        )

                    st.markdown("**Kiểm tra thực tế tại khách hàng**")
                    c9, c10, c11 = st.columns(3)
                    with c9:
                        du_no_goc_tt = st.number_input(
                            "Dư nợ gốc (thực tế)",
                            min_value=0.0, step=1_000_000.0, format="%.0f",
                            key=f"{key_prefix}kt_tt_goc",
                        )
                    with c10:
                        du_no_kh_tt = st.number_input(
                            "Dư nợ khoanh (thực tế)",
                            min_value=0.0, step=1_000_000.0, format="%.0f",
                            key=f"{key_prefix}kt_tt_kh",
                        )
                    with c11:
                        lai_tt = st.number_input(
                            "Lãi (thực tế)",
                            min_value=0.0, step=100_000.0, format="%.0f",
                            key=f"{key_prefix}kt_tt_lai",
                        )

                    chenh_lech = du_no_goc_kh - du_no_kh_tt
                    ly_do_cl = ""
                    if chenh_lech != 0:
                        st.info(
                            f"⚠️ Chênh lệch dư nợ khoanh: "
                            f"**{fmt_so(abs(chenh_lech))} đồng**"
                        )
                        ly_do_cl = st.text_area(
                            "Lý do chênh lệch *",
                            max_chars=250,
                            key=f"{key_prefix}kt_lydo_cl",
                        )

                    st.markdown("**Đánh giá (Mẫu 01/QLNK)**")
                    thuc_trang = st.text_area(
                        "Thực trạng dự án/phương án vay vốn (cột 12)",
                        max_chars=250,
                        help="Tối thiểu 5 ký tự. Chương trình NS&VSMTNT, HSSV, Nhà ở không bắt buộc.",
                        key=f"{key_prefix}kt_thuc_trang",
                    )
                    tinh_hinh_kh = st.text_area(
                        "Tình hình thực tế của khách hàng (cột 13)",
                        max_chars=250,
                        key=f"{key_prefix}kt_tinh_hinh",
                    )
                    kha_nang = st.radio(
                        "Khả năng trả nợ (cột 14)",
                        options=["co", "chua_co", "khong_co"],
                        format_func=lambda x: {
                            "co": "Có khả năng trả nợ",
                            "chua_co": "Chưa có khả năng trả nợ",
                            "khong_co": "Không có khả năng trả nợ",
                        }[x],
                        horizontal=True,
                        key=f"{key_prefix}kt_kha_nang",
                    )
                    cam_ket = None
                    if kha_nang == "co":
                        cam_ket = st.radio(
                            "Cam kết trả nợ (cột 15)",
                            options=["co_cam_ket", "khong_cam_ket", "khong_thuc_hien"],
                            format_func=lambda x: {
                                "co_cam_ket": "Có cam kết",
                                "khong_cam_ket": "Không cam kết",
                                "khong_thuc_hien": "Không thực hiện cam kết",
                            }[x],
                            horizontal=True,
                            key=f"{key_prefix}kt_cam_ket",
                        )

                    col_btn1, col_btn2, _ = st.columns([1, 1, 4])
                    with col_btn1:
                        luu_tam_btn = st.button(
                            "💾 Lưu tạm",
                            key=f"{key_prefix}kt_luu_tam",
                            use_container_width=True,
                        )
                    with col_btn2:
                        phe_duyet_btn = st.button(
                            "✅ Phê duyệt",
                            key=f"{key_prefix}kt_phe_duyet",
                            disabled=not co_quyen_duyet,
                            use_container_width=True,
                        )

                    if luu_tam_btn or phe_duyet_btn:
                        loi = []
                        if not chon_ku or chon_ku == "— Chọn —":
                            loi.append("Chưa chọn số khế ước")
                        if not ngay_kt:
                            loi.append("Chưa nhập ngày kiểm tra")
                        if chenh_lech != 0 and not ly_do_cl.strip():
                            loi.append("Có chênh lệch nhưng chưa nhập lý do")

                        if loi:
                            for l in loi:
                                st.error(f"❌ {l}")
                        else:
                            trang_thai_luu = "da_phe_duyet" if phe_duyet_btn else "luu_tam"
                            ten_pgd_v = (
                                str(row_chon.get(COT_TEN_PGD, pgd_user or ""))
                                if row_chon is not None else (pgd_user or "")
                            )
                            data_dict = {
                                "ma_mon_vay": chon_ku if chon_ku != "— Chọn —" else "",
                                "ten_pgd": ten_pgd_v,
                                "ten_xa": str(row_chon.get(COT_TEN_XA, ""))
                                          if row_chon is not None else "",
                                "ten_to_tkv": str(row_chon.get(COT_TEN_TO, ""))
                                              if row_chon is not None else "",
                                "ten_kh": ten_kh_hien,
                                "ngay_bat_dau_khoanh": ngay_bdk,
                                "so_thang_khoanh": so_thang_kh or None,
                                "so_quyet_dinh_khoanh": so_qd,
                                "ngay_kiem_tra": str(ngay_kt),
                                "can_bo_kiem_tra": can_bo,
                                "du_no_goc": du_no_goc,
                                "du_no_goc_khoanh": du_no_goc_kh,
                                "so_tien_lai_con_no": lai_con_no,
                                "du_no_goc_thuc_te": du_no_goc_tt,
                                "du_no_khoanh_thuc_te": du_no_kh_tt,
                                "so_tien_lai_thuc_te": lai_tt,
                                "chenh_lech": chenh_lech,
                                "ly_do_chenh_lech": ly_do_cl,
                                "thuc_trang_du_an": thuc_trang,
                                "tinh_hinh_khach_hang": tinh_hinh_kh,
                                "kha_nang_tra_no": kha_nang,
                                "cam_ket_tra_no": cam_ket,
                                "trang_thai": trang_thai_luu,
                            }
                            try:
                                db.luu_ket_qua_kiem_tra(data_dict, username)
                                if ngay_bdk or so_qd:
                                    db.luu_bo_sung_mon_vay(
                                        data_dict["ma_mon_vay"],
                                        ten_pgd_v,
                                        {
                                            "ngay_bat_dau_khoanh": ngay_bdk,
                                            "so_thang_khoanh": so_thang_kh,
                                            "so_quyet_dinh_khoanh": so_qd,
                                        },
                                        username,
                                    )
                                st.cache_data.clear()
                                label = "phê duyệt" if phe_duyet_btn else "lưu tạm"
                                st.success(f"✅ Đã {label} kết quả kiểm tra.")
                                st.rerun()
                            except Exception as e:
                                st.error(f"❌ Lỗi khi lưu: {e}")

            st.markdown("### 📋 Kết quả kiểm tra đã lưu")

            col_f1, col_f2, _ = st.columns([2, 2, 4])
            with col_f1:
                loc_tt = st.selectbox(
                    "Trạng thái",
                    ["Tất cả", "Lưu tạm", "Đã phê duyệt", "Mở phê duyệt"],
                    key=f"{key_prefix}kt_loc_tt",
                )
            tt_map = {
                "Tất cả": None,
                "Lưu tạm": "luu_tam",
                "Đã phê duyệt": "da_phe_duyet",
                "Mở phê duyệt": "mo_phe_duyet",
            }
            pgd_filter = None if la_phan_he_cn(role) else pgd_user

            rows_kt = db.doc_ket_qua_kiem_tra(
                ten_pgd=pgd_filter,
                trang_thai=tt_map[loc_tt],
            )

            if not rows_kt:
                st.info("ℹ️ Chưa có kết quả kiểm tra nào được lưu.")
            else:
                df_kt = pd.DataFrame(rows_kt)
                col_rename = {
                    "id": "ID",
                    "ma_mon_vay": "Số KU",
                    "ten_pgd": "PGD",
                    "ten_kh": "Khách hàng",
                    "ngay_kiem_tra": "Ngày KT",
                    "kha_nang_tra_no": "Khả năng TN",
                    "cam_ket_tra_no": "Cam kết",
                    "trang_thai": "Trạng thái",
                    "nguoi_nhap": "Người nhập",
                }
                df_hien_kt = df_kt.rename(columns=col_rename)
                cols_show = [c for c in col_rename.values() if c in df_hien_kt.columns]
                hien_thi_dataframe_phan_trang(
                    df_hien_kt[cols_show],
                    key=f"{key_prefix}kt_list_tbl",
                    height=360,
                )

                if co_quyen_duyet:
                    st.markdown("**Thao tác theo ID:**")
                    chon_id = st.number_input(
                        "ID bản ghi",
                        min_value=1, step=1,
                        key=f"{key_prefix}kt_action_id",
                    )
                    ca1, ca2, _ = st.columns([1, 1, 4])
                    with ca1:
                        if st.button(
                            "✅ Phê duyệt",
                            key=f"{key_prefix}kt_phe_duyet_id",
                            use_container_width=True,
                        ):
                            ok = db.phe_duyet_ket_qua(int(chon_id), username)
                            (st.success("Đã phê duyệt.") if ok
                             else st.error("Không thể phê duyệt."))
                            st.rerun()
                    with ca2:
                        if st.button(
                            "🔓 Mở phê duyệt",
                            key=f"{key_prefix}kt_mo_pd_id",
                            use_container_width=True,
                        ):
                            ok = db.mo_phe_duyet(int(chon_id), username)
                            (st.success("Đã mở phê duyệt.") if ok
                             else st.error("Không thể mở."))
                            st.rerun()

        with d7:
            st.markdown("### 📊 Báo cáo Quản lý Nợ khoanh")

            pgd_filter_bc = None if la_phan_he_cn(role) else pgd_user
            rows_all_kt = db.doc_ket_qua_kiem_tra(ten_pgd=pgd_filter_bc)
            da_kiem_tra_set = {r["ma_mon_vay"] for r in rows_all_kt}

            with st.expander(
                "📋 M08 — Danh sách món vay chưa kiểm tra", expanded=True
            ):
                if COT_SO_KU in df_kh.columns:
                    df_chua_kt = df_kh[~df_kh[COT_SO_KU].isin(da_kiem_tra_set)].copy()
                else:
                    df_chua_kt = df_kh.copy()

                st.metric("Số món chưa kiểm tra", fmt_so(len(df_chua_kt)))

                if not df_chua_kt.empty:
                    cols_m08 = [c for c in [
                        COT_TEN_PGD, COT_TEN_XA, COT_TEN_KH, COT_SO_KU,
                        COT_DU_NO_KHOANH, COT_NGAY_HH_KHOANH,
                    ] if c in df_chua_kt.columns]
                    hien_thi_dataframe_phan_trang(
                        df_chua_kt[cols_m08],
                        key=f"{key_prefix}bc_m08_tbl",
                        height=320,
                    )
                    if st.button("📥 Xuất M08 Excel", key=f"{key_prefix}bc_m08_xuat"):
                        st.session_state[f"_{key_prefix}m08_buf"] = xuat_excel(
                            {"M08_ChuaKiemTra": df_chua_kt[cols_m08]}
                        )
                    if st.session_state.get(f"_{key_prefix}m08_buf"):
                        st.download_button(
                            "⬇️ Tải M08",
                            data=st.session_state[f"_{key_prefix}m08_buf"],
                            file_name="M08_ChuaKiemTra.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            key=f"{key_prefix}bc_m08_dl",
                        )

            with st.expander("📋 M09 — Danh sách món vay có khả năng trả nợ"):
                rows_m09 = [
                    r for r in rows_all_kt
                    if r.get("trang_thai") == "da_phe_duyet"
                    and r.get("kha_nang_tra_no") == "co"
                ]
                df_m09 = pd.DataFrame(rows_m09)
                st.metric("Số món có KN trả nợ", fmt_so(len(df_m09)))
                if not df_m09.empty:
                    cols_m09 = [c for c in [
                        "ma_mon_vay", "ten_pgd", "ten_kh",
                        "ngay_kiem_tra", "cam_ket_tra_no", "nguoi_nhap",
                    ] if c in df_m09.columns]
                    hien_thi_dataframe_phan_trang(
                        df_m09[cols_m09],
                        key=f"{key_prefix}bc_m09_tbl",
                        height=300,
                    )
                    if st.button("📥 Xuất M09 Excel", key=f"{key_prefix}bc_m09_xuat"):
                        st.session_state[f"_{key_prefix}m09_buf"] = xuat_excel(
                            {"M09_CoKNTraNo": df_m09[cols_m09]}
                        )
                    if st.session_state.get(f"_{key_prefix}m09_buf"):
                        st.download_button(
                            "⬇️ Tải M09",
                            data=st.session_state[f"_{key_prefix}m09_buf"],
                            file_name="M09_CoKNTraNo.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            key=f"{key_prefix}bc_m09_dl",
                        )

            with st.expander("📋 M10 — Danh sách chưa nhập kết quả (lưu tạm)"):
                rows_m10 = [
                    r for r in rows_all_kt
                    if r.get("trang_thai") == "luu_tam"
                ]
                df_m10 = pd.DataFrame(rows_m10)
                st.metric("Số bản ghi lưu tạm", fmt_so(len(df_m10)))
                if not df_m10.empty:
                    cols_m10 = [c for c in [
                        "id", "ma_mon_vay", "ten_pgd", "ten_kh",
                        "ngay_kiem_tra", "nguoi_nhap",
                    ] if c in df_m10.columns]
                    hien_thi_dataframe_phan_trang(
                        df_m10[cols_m10],
                        key=f"{key_prefix}bc_m10_tbl",
                        height=300,
                    )
                    if st.button("📥 Xuất M10 Excel", key=f"{key_prefix}bc_m10_xuat"):
                        st.session_state[f"_{key_prefix}m10_buf"] = xuat_excel(
                            {"M10_LuuTam": df_m10[cols_m10]}
                        )
                    if st.session_state.get(f"_{key_prefix}m10_buf"):
                        st.download_button(
                            "⬇️ Tải M10",
                            data=st.session_state[f"_{key_prefix}m10_buf"],
                            file_name="M10_LuuTam.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            key=f"{key_prefix}bc_m10_dl",
                        )

            with st.expander("📊 Tiến độ kiểm tra theo PGD"):
                if not rows_all_kt:
                    st.info("ℹ️ Chưa có dữ liệu kiểm tra.")
                else:
                    df_td = pd.DataFrame(rows_all_kt)

                    if COT_TEN_PGD in df_kh.columns and COT_SO_KU in df_kh.columns:
                        tong_kh_pgd = (
                            df_kh.groupby(COT_TEN_PGD)[COT_SO_KU]
                            .nunique()
                            .rename("Tổng món KH")
                        )
                    else:
                        tong_kh_pgd = pd.Series(dtype=int, name="Tổng món KH")

                    da_pd = df_td[df_td["trang_thai"] == "da_phe_duyet"]
                    da_kt_pgd = (
                        da_pd.groupby("ten_pgd")["ma_mon_vay"]
                        .nunique()
                        .rename("Đã KT (PD)")
                    )

                    df_td_pgd = pd.concat([tong_kh_pgd, da_kt_pgd], axis=1).fillna(0)
                    df_td_pgd = df_td_pgd.astype(int)
                    df_td_pgd["Tỷ lệ%"] = df_td_pgd.apply(
                        lambda r: (
                            f"{r['Đã KT (PD)'] / r['Tổng món KH'] * 100:.1f}%".replace(".", ",")
                            if r["Tổng món KH"] > 0 else "—"
                        ),
                        axis=1,
                    )
                    df_td_pgd = df_td_pgd.reset_index().rename(
                        columns={"index": "PGD", "ten_pgd": "PGD"}
                    )

                    hien_thi_dataframe_phan_trang(
                        df_td_pgd,
                        key=f"{key_prefix}bc_td_pgd_tbl",
                        height=340,
                    )
                    if st.button(
                        "📥 Xuất tiến độ Excel",
                        key=f"{key_prefix}bc_td_xuat",
                    ):
                        st.session_state[f"_{key_prefix}td_buf"] = xuat_excel(
                            {"TienDoKiemTra": df_td_pgd}
                        )
                    if st.session_state.get(f"_{key_prefix}td_buf"):
                        st.download_button(
                            "⬇️ Tải tiến độ",
                            data=st.session_state[f"_{key_prefix}td_buf"],
                            file_name="TienDoKiemTraNK.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            key=f"{key_prefix}bc_td_dl",
                        )
