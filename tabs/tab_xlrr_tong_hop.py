import streamlit as st
import pandas as pd
from datetime import datetime
from io import BytesIO
import db
from config import DS_PGD, DON_VI_CHI_NHANH
from data.pgd import pgd_slug
from utils import fmt_ty, fmt_so, get_tab_context

TRANG_THAI_QD62 = {
    "cho_duyet": "🟡 Chờ duyệt",
    "da_duyet":  "🟢 Đã duyệt",
    "tu_choi":   "🔴 Không duyệt",
}


def _doc_tat_ca_qd62() -> pd.DataFrame:
    """Đọc toàn bộ hồ sơ QĐ62 từ tất cả PGD."""
    ds_all = []
    for ten_pgd in [DON_VI_CHI_NHANH] + DS_PGD:
        slug = pgd_slug(ten_pgd)
        data = db.doc_kv(f"qd62_pgd_{slug}")
        ds = []
        if isinstance(data, list):
            ds = data
        elif isinstance(data, dict) and "danh_sach" in data:
            ds = data["danh_sach"]
        for r in ds:
            r["pgd"] = ten_pgd
        ds_all.extend(ds)
    if not ds_all:
        return pd.DataFrame()
    return pd.DataFrame(ds_all)


def _doc_tat_ca_no_rr() -> pd.DataFrame:
    """Đọc toàn bộ hồ sơ nợ RR từ tất cả PGD (kv_store no_rui_ro_*)."""
    ds_all = []
    for ten_pgd in [DON_VI_CHI_NHANH] + DS_PGD:
        slug = pgd_slug(ten_pgd)
        now = datetime.now()
        for delta in range(12):
            thang = now.month - delta
            nam = now.year
            if thang <= 0:
                thang += 12
                nam -= 1
            key = f"no_rui_ro_{slug}_{nam}_{thang:02d}"
            data = db.doc_kv(key)
            if data and isinstance(data, list):
                for r in data:
                    r["pgd"] = ten_pgd
                    r["ky"] = f"{nam}-T{thang:02d}"
                ds_all.extend(data)
    if not ds_all:
        return pd.DataFrame()
    return pd.DataFrame(ds_all)


def _render_tong_quan(df_qd62: pd.DataFrame, df_no_rr: pd.DataFrame) -> None:
    """Tab 1: Metrics tổng quan toàn CN."""
    st.subheader("📊 Tổng quan XLRR toàn Chi nhánh")

    st.markdown("##### 📋 Hồ sơ QĐ62")
    c1, c2, c3, c4 = st.columns(4)
    if not df_qd62.empty:
        tong_hs = len(df_qd62)
        cho_duyet = (
            len(df_qd62[df_qd62["trang_thai"] == "cho_duyet"])
            if "trang_thai" in df_qd62.columns
            else 0
        )
        da_duyet = (
            len(df_qd62[df_qd62["trang_thai"] == "da_duyet"])
            if "trang_thai" in df_qd62.columns
            else 0
        )
        tong_goc = df_qd62["du_no_goc"].sum() if "du_no_goc" in df_qd62.columns else 0
        c1.metric("Tổng hồ sơ", fmt_so(tong_hs))
        c2.metric("🟡 Chờ duyệt", fmt_so(cho_duyet))
        c3.metric("🟢 Đã duyệt", fmt_so(da_duyet))
        c4.metric("💰 Tổng dư nợ gốc", fmt_ty(tong_goc))
    else:
        c1.metric("Tổng hồ sơ", "0")
        c2.metric("🟡 Chờ duyệt", "0")
        c3.metric("🟢 Đã duyệt", "0")
        c4.metric("💰 Tổng dư nợ gốc", "0")

    st.divider()

    st.markdown("##### 💳 Nợ rủi ro từ HSTD")
    c5, c6, c7 = st.columns(3)
    if not df_no_rr.empty:
        tong_hs_rr = len(df_no_rr)
        tong_du_no = df_no_rr["du_no"].sum() if "du_no" in df_no_rr.columns else 0
        so_pgd = df_no_rr["pgd"].nunique() if "pgd" in df_no_rr.columns else 0
        c5.metric("Tổng hồ sơ", fmt_so(tong_hs_rr))
        c6.metric("💰 Tổng dư nợ", fmt_ty(tong_du_no))
        c7.metric("🏢 Số PGD có hồ sơ", fmt_so(so_pgd))
    else:
        c5.metric("Tổng hồ sơ", "0")
        c6.metric("💰 Tổng dư nợ", "0")
        c7.metric("🏢 Số PGD có hồ sơ", "0")

    st.markdown("##### 📊 Chi tiết theo PGD")
    ds_rows = []
    for ten_pgd in [DON_VI_CHI_NHANH] + DS_PGD:
        qd62_pgd = (
            df_qd62[df_qd62["pgd"] == ten_pgd]
            if (not df_qd62.empty and "pgd" in df_qd62.columns)
            else pd.DataFrame()
        )
        rr_pgd = (
            df_no_rr[df_no_rr["pgd"] == ten_pgd]
            if (not df_no_rr.empty and "pgd" in df_no_rr.columns)
            else pd.DataFrame()
        )
        ds_rows.append({
            "Đơn vị": ten_pgd,
            "HS QĐ62": len(qd62_pgd),
            "Chờ duyệt": (
                len(qd62_pgd[qd62_pgd["trang_thai"] == "cho_duyet"])
                if (not qd62_pgd.empty and "trang_thai" in qd62_pgd.columns)
                else 0
            ),
            "Dư nợ QĐ62 (tỷ)": (
                fmt_ty(qd62_pgd["du_no_goc"].sum())
                if (not qd62_pgd.empty and "du_no_goc" in qd62_pgd.columns)
                else "—"
            ),
            "HS Nợ RR": len(rr_pgd),
            "Dư nợ RR (tỷ)": (
                fmt_ty(rr_pgd["du_no"].sum())
                if (not rr_pgd.empty and "du_no" in rr_pgd.columns)
                else "—"
            ),
        })
    df_pgd = pd.DataFrame(ds_rows)
    st.dataframe(df_pgd, hide_index=True, use_container_width=True)


def _render_qd62(df_qd62: pd.DataFrame) -> None:
    """Tab 2: Danh sách hồ sơ QĐ62 toàn CN + duyệt."""
    st.subheader("📋 Hồ sơ QĐ62 toàn Chi nhánh")
    if df_qd62.empty:
        st.info("Chưa có hồ sơ QĐ62 nào.")
        return

    col_f1, col_f2 = st.columns(2)
    with col_f1:
        pgd_chon = st.multiselect(
            "PGD", ["Tất cả"] + DS_PGD,
            default=["Tất cả"], key="xlrr_qd62_pgd"
        )
    with col_f2:
        tt_chon = st.selectbox(
            "Trạng thái",
            ["Tất cả"] + list(TRANG_THAI_QD62.keys()),
            format_func=lambda x: TRANG_THAI_QD62.get(x, x) if x != "Tất cả" else "Tất cả",
            key="xlrr_qd62_tt"
        )

    df_loc = df_qd62.copy()
    if "Tất cả" not in pgd_chon and pgd_chon:
        df_loc = df_loc[df_loc["pgd"].isin(pgd_chon)]
    if tt_chon != "Tất cả" and "trang_thai" in df_loc.columns:
        df_loc = df_loc[df_loc["trang_thai"] == tt_chon]

    df_show = df_loc.copy()
    if "trang_thai" in df_show.columns:
        df_show["trang_thai"] = df_show["trang_thai"].map(TRANG_THAI_QD62)
    if "du_no_goc" in df_show.columns:
        df_show["du_no_goc"] = df_show["du_no_goc"].apply(lambda x: fmt_ty(x) if x else "—")
    if "du_no_lai" in df_show.columns:
        df_show["du_no_lai"] = df_show["du_no_lai"].apply(lambda x: fmt_ty(x) if x else "—")

    cot_hien = [
        c for c in [
            "pgd", "ho_ten", "xa", "chuong_trinh",
            "du_no_goc", "du_no_lai", "ly_do",
            "trang_thai", "ngay_lap"
        ] if c in df_show.columns
    ]
    st.dataframe(df_show[cot_hien], hide_index=True, use_container_width=True, height=400)
    st.caption(
        f"Tổng: **{len(df_loc)}** hồ sơ | "
        f"Dư nợ gốc: **{fmt_ty(df_loc['du_no_goc'].sum() if 'du_no_goc' in df_loc.columns else 0)}**"
    )


def _render_no_rr(df_no_rr: pd.DataFrame) -> None:
    """Tab 3: Danh sách nợ RR từ HSTD."""
    st.subheader("💳 Nợ rủi ro từ HSTD")
    if df_no_rr.empty:
        st.info("Chưa có hồ sơ nợ rủi ro nào.")
        return

    col_f1, col_f2 = st.columns(2)
    with col_f1:
        pgd_chon = st.multiselect(
            "PGD", ["Tất cả"] + DS_PGD,
            default=["Tất cả"], key="xlrr_rr_pgd"
        )
    with col_f2:
        ky_chon = st.selectbox(
            "Kỳ",
            (["Tất cả"] + sorted(df_no_rr["ky"].unique().tolist(), reverse=True))
            if "ky" in df_no_rr.columns else ["Tất cả"],
            key="xlrr_rr_ky"
        )

    df_loc = df_no_rr.copy()
    if "Tất cả" not in pgd_chon and pgd_chon:
        df_loc = df_loc[df_loc["pgd"].isin(pgd_chon)]
    if ky_chon != "Tất cả" and "ky" in df_loc.columns:
        df_loc = df_loc[df_loc["ky"] == ky_chon]

    df_show = df_loc.copy()
    if "du_no" in df_show.columns:
        df_show["du_no"] = df_show["du_no"].apply(lambda x: fmt_ty(x) if x else "—")

    cot_hien = [
        c for c in [
            "pgd", "ky", "ten_kh", "ten_ct", "du_no",
            "bien_phap", "nguyen_nhan", "ngay_rr"
        ] if c in df_show.columns
    ]
    st.dataframe(df_show[cot_hien], hide_index=True, use_container_width=True, height=400)
    st.caption(
        f"Tổng: **{len(df_loc)}** hồ sơ | "
        f"Dư nợ: **{fmt_ty(df_loc['du_no'].sum() if 'du_no' in df_loc.columns else 0)}**"
    )


def _render_xuat_bao_cao(df_qd62: pd.DataFrame, df_no_rr: pd.DataFrame) -> None:
    """Tab 4: Xuất báo cáo Excel tổng hợp."""
    st.subheader("📤 Xuất báo cáo XLRR")

    if st.button("⬇️ Xuất Excel tổng hợp", type="primary", key="xlrr_xuat_excel"):
        if df_qd62.empty and df_no_rr.empty:
            st.warning("Không có dữ liệu để xuất.")
        else:
            buf = BytesIO()
            with pd.ExcelWriter(buf, engine="openpyxl") as writer:
                if not df_qd62.empty:
                    df_qd62.to_excel(writer, sheet_name="QĐ62", index=False)
                    if "trang_thai" in df_qd62.columns:
                        df_qd62[df_qd62["trang_thai"] == "cho_duyet"].to_excel(
                            writer, sheet_name="QĐ62_Chờ duyệt", index=False
                        )
                if not df_no_rr.empty:
                    df_no_rr.to_excel(writer, sheet_name="Nợ RR HSTD", index=False)
            buf.seek(0)
            ten_file = f"XLRR_tong_hop_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
            st.download_button(
                "💾 Tải về Excel",
                data=buf.getvalue(),
                file_name=ten_file,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="xlrr_dl_excel"
            )


def render(tab=None, **kwargs) -> None:
    """Render Dashboard XLRR tổng hợp."""
    role = kwargs.get("role")
    if role not in ("admin", "admin_cn", "manager", "manager_cn"):
        _ctx = get_tab_context(tab)
        with _ctx:
            st.warning("Bạn không có quyền truy cập Dashboard XLRR tổng hợp.")
        return

    _ctx = get_tab_context(tab)
    with _ctx:
        st.title("🔴 Quản lý Xử lý Rủi ro (XLRR)")
        st.caption("Tổng hợp hồ sơ QĐ62 và nợ rủi ro từ HSTD toàn Chi nhánh.")

        df_qd62 = _doc_tat_ca_qd62()
        df_no_rr = _doc_tat_ca_no_rr()

        t1, t2, t3, t4 = st.tabs([
            "📊 Tổng quan",
            "📋 Hồ sơ QĐ62",
            "💳 Nợ RR HSTD",
            "📤 Xuất báo cáo",
        ])
        with t1:
            _render_tong_quan(df_qd62, df_no_rr)
        with t2:
            _render_qd62(df_qd62)
        with t3:
            _render_no_rr(df_no_rr)
        with t4:
            _render_xuat_bao_cao(df_qd62, df_no_rr)
