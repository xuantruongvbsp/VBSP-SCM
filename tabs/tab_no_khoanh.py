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
    COT_CMND,
    COT_DIA_CHI,
    COT_DU_NO_KHOANH,
    COT_DU_NO_QH,
    COT_DVUT,
    COT_MA_KH,
    COT_NGAY_CAP_CMND,
    COT_NGAY_DH,
    COT_NGAY_HH_KHOANH,
    COT_NGAY_SINH,
    COT_NOI_CAP_CMND,
    COT_SDT,
    COT_SO_KU,
    COT_TEN_CT,
    COT_TEN_KH,
    COT_TEN_PGD,
    COT_TEN_TO,
    COT_TEN_XA,
    COT_TONG_DU_NO,
    DON_VI_CHI_NHANH,
    DS_PGD,
    LY_DO_KHOANH_QD62,
    LY_DO_KHOANH_LABEL,
)
from utils import fmt_so, fmt_ty, get_tab_context, hien_thi_dataframe_phan_trang, xuat_excel
from tabs import tab_qlnk_dashboard
import db
from datetime import datetime
_fmt_dong = lambda x: fmt_so(float(x)) + " đồng" if x not in (None, "", float("nan")) else "0 đồng"


# ─── Cached DB wrappers (TTL 60s) ────────────────────────────────────────────

@st.cache_data(ttl=60, show_spinner=False)
def _cached_ket_qua_kiem_tra(ten_pgd, trang_thai=None):
    return db.doc_ket_qua_kiem_tra(ten_pgd=ten_pgd, trang_thai=trang_thai)

@st.cache_data(ttl=60, show_spinner=False)
def _cached_ke_hoach_kiem_tra(ten_pgd, trang_thai=None, nam=None):
    return db.doc_ke_hoach_kiem_tra(ten_pgd=ten_pgd, trang_thai=trang_thai, nam=nam)

@st.cache_data(ttl=60, show_spinner=False)
def _cached_mau_bieu_cv368(ten_pgd=None, loai_mau=None, nam=None):
    return db.doc_mau_bieu_cv368(ten_pgd=ten_pgd, loai_mau=loai_mau, nam=nam)

@st.cache_data(ttl=30, show_spinner=False)
def _cached_bo_sung_mon_vay(ma_mon_vay):
    return db.doc_bo_sung_mon_vay(ma_mon_vay)


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
    _COL_DN = "Dư nợ khoanh (triệu đồng)"
    nhom[_COL_DN] = nhom["du_no_khoanh"].apply(fmt_ty)
    nhom = nhom.rename(columns={"so_mon": "Số món"})
    return nhom[[nhom_col, "Số món", _COL_DN, "Tỷ trọng%"]]


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
    st.plotly_chart(fig, use_container_width=True, key=key)


def _heatmap_dao_han(df: pd.DataFrame, key: str) -> None:
    """Bar chart phân bổ khoanh theo năm hết hạn khoanh nợ."""
    try:
        import plotly.graph_objects as go
    except ImportError:
        return

    if COT_NGAY_HH_KHOANH not in df.columns or df.empty:
        return

    ngay_hh = pd.to_datetime(df[COT_NGAY_HH_KHOANH], errors="coerce", dayfirst=True)
    df = df.copy()
    df["_du_kh"] = pd.to_numeric(df[COT_DU_NO_KHOANH], errors="coerce").fillna(0)
    df["_ym"] = ngay_hh.dt.to_period("Y").astype(str)  # nhóm theo năm

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
        xaxis_title="Năm hết hạn khoanh nợ",
        yaxis_title="Số khoản khoanh",
        height=260,
        margin=dict(t=10, b=30, l=40, r=20),
    )
    st.markdown("**📅 Phân bổ theo năm hết hạn khoanh nợ**")
    st.plotly_chart(fig, use_container_width=True, key=key)


from tabs.pdf_no_khoanh import (
    _REPORTLAB_READY, _VBSP_GREEN, _VBSP_GREEN_LIGHT, _ROW_ALT, _BORDER_COLOR, _HEADER_BG, _RED,
    _FN, _FB,
    _dang_ky_font_qlnk, _tim_logo_qlnk,
    _qlnk_add_months, _qlnk_fmt_k, _qlnk_fmt_dong,
    _style_bank_name, _style_bank_branch, _style_doc_title, _style_doc_sub,
    _style_body, _style_body_bold, _style_italic,
    _style_table_header, _style_table_cell, _style_table_cell_left,
    _style_sig_title, _style_sig_sub, _style_date_right, _style_meta_label,
    _ve_header_pdf, _ve_footer_pdf, _dong_ten_nd,
    _xuat_pdf_mau_kh, _xuat_pdf_mau_01qlnk, _xuat_pdf_mau_02qlnk,
    _xuat_pdf_mau_03qlnk, _xuat_pdf_mau_04qlnk,
    _xuat_pdf_bb_kt_cv368, _xuat_pdf_qlnk_06,
    _xuat_pdf_m10, _xuat_pdf_ke_hoach_kt,
)

# ─────────────────────────────────────────────────────────────────────────────
#  CV 368: Drill-down module — 3 mẫu biểu (Mẫu 01 / 02 / 03)
# ─────────────────────────────────────────────────────────────────────────────

def _render_mau01_cv368(
    df_kh: pd.DataFrame,
    pgd: str,
    pgd_slug_val: str,
    nam: int,
    username: str,
    key_prefix: str,
    xem_id: int | None,
) -> None:
    """Mẫu 01 — Kế hoạch kiểm tra nợ khoanh."""
    st.markdown("#### 📋 Mẫu 01 — Kế hoạch kiểm tra")

    # ── Chế độ xem lại ───────────────────────────────────────────────────────
    if xem_id is not None:
        rec = db.doc_mau_bieu_cv368_by_id(xem_id)
        if rec is None:
            st.error("Không tìm thấy bản ghi.")
            return
        nd = rec["noi_dung"]
        st.info(f"🗒️ Đang xem Mẫu 01 — Đợt {rec.get('dot')}/{rec.get('nam')} — ID #{rec['id']}")
        c1, c2, c3 = st.columns(3)
        c1.text_input("PGD", value=rec.get("ten_pgd", ""), disabled=True, key=f"{key_prefix}m01v_pgd")
        c2.number_input("Năm", value=int(rec.get("nam", nam)), disabled=True, key=f"{key_prefix}m01v_nam", step=1)
        c3.number_input("Đợt", value=int(rec.get("dot", 1)), disabled=True, key=f"{key_prefix}m01v_dot", step=1)
        tp_v = nd.get("thanh_phan_doan") or []
        if tp_v:
            st.markdown("**Thành phần đoàn:**")
            st.dataframe(pd.DataFrame(tp_v), use_container_width=True, hide_index=True)
        ds_mon_v = nd.get("ds_mon") or []
        if ds_mon_v:
            st.markdown("**Danh sách món vay:**")
            hien_thi_dataframe_phan_trang(pd.DataFrame(ds_mon_v), key=f"{key_prefix}m01v_tbl", height=320)
        if st.button("📄 In lại PDF Mẫu 01", key=f"{key_prefix}m01v_pdf_btn", type="primary"):
            if not _REPORTLAB_READY:
                st.error("❌ Cần cài reportlab.")
            else:
                try:
                    noi_dung_pdf = {
                        "ten_pgd": rec.get("ten_pgd", pgd),
                        "nam": int(rec.get("nam", nam)),
                        "dot": int(rec.get("dot", 1)),
                        "thanh_phan": nd.get("thanh_phan_doan") or [],
                        "ds_mon": nd.get("ds_mon") or [],
                    }
                    pdf_b = _xuat_pdf_ke_hoach_kt(noi_dung_pdf)
                    st.session_state[f"{key_prefix}m01_pdf_buf"] = pdf_b
                    st.session_state[f"{key_prefix}m01_pdf_fn"] = (
                        f"Mau01_KH_KiemTra_{pgd_slug_val}_{rec.get('nam')}_Dot{rec.get('dot', 1)}.pdf"
                    )
                except Exception as _e:
                    st.error(f"❌ Lỗi tạo PDF: {_e}")
        if st.session_state.get(f"{key_prefix}m01_pdf_buf"):
            st.download_button(
                "⬇️ Tải PDF Mẫu 01",
                data=st.session_state[f"{key_prefix}m01_pdf_buf"],
                file_name=st.session_state.get(f"{key_prefix}m01_pdf_fn", "Mau01.pdf"),
                mime="application/pdf",
                key=f"{key_prefix}m01v_dl",
            )
        return

    # ── Lọc món cần kiểm tra ────────────────────────────────────────────────
    da_co_mau02: set[str] = {
        item.get("so_ku", "")
        for r in _cached_mau_bieu_cv368(ten_pgd=pgd, loai_mau="MAU_02")
        for item in (r["noi_dung"].get("ds_mon") or [{"so_ku": r["noi_dung"].get("so_ku", "")}])
    }
    df_mon_kh = df_kh.copy()
    if COT_NGAY_HH_KHOANH in df_mon_kh.columns:
        _hh_s = pd.to_datetime(df_mon_kh[COT_NGAY_HH_KHOANH], dayfirst=True, errors="coerce")
        df_mon_kh = df_mon_kh[_hh_s.dt.year == nam].copy()
    if COT_SO_KU in df_mon_kh.columns and da_co_mau02:
        df_mon_kh = df_mon_kh[~df_mon_kh[COT_SO_KU].isin(da_co_mau02)].copy()

    st.metric("📦 Số món cần kiểm tra", f"{len(df_mon_kh)} món")

    if df_mon_kh.empty:
        st.info(f"ℹ️ Không có món vay nào hết hạn khoanh trong năm {nam} (hoặc đã có Mẫu 02 đầy đủ).")
        return

    # ── Form header ───────────────────────────────────────────────────────────
    c1, c2, c3 = st.columns(3)
    c1.text_input("PGD", value=pgd, disabled=True, key=f"{key_prefix}m01_pgd")
    c2.number_input("Năm", value=nam, disabled=True, key=f"{key_prefix}m01_nam", step=1)
    c3.text_input("Cán bộ lập", value=username, disabled=True, key=f"{key_prefix}m01_canbo")

    c4, c5 = st.columns(2)
    dot_kh = c4.number_input("Đợt kiểm tra *", min_value=1, max_value=12, value=1, step=1, key=f"{key_prefix}m01_dot")
    ngay_lap_kh = c5.date_input("Ngày lập dự kiến", value=datetime.now().date(), key=f"{key_prefix}m01_ngay_lap")

    st.markdown("**Thành phần đoàn kiểm tra**")
    df_tp = st.data_editor(
        pd.DataFrame([{"Họ và tên": username, "Chức vụ": "CBTD"}, {"Họ và tên": "", "Chức vụ": ""}]),
        num_rows="dynamic", key=f"{key_prefix}m01_tp_doan",
        use_container_width=True, hide_index=True,
    )
    ghi_chu_m01 = st.text_area("Ghi chú", key=f"{key_prefix}m01_ghi_chu", max_chars=500)

    # ── Bảng chọn món vay ─────────────────────────────────────────────────────
    st.markdown("**Danh sách món vay cần kiểm tra**")
    _cols_fix = [c for c in [COT_TEN_TO, COT_TEN_XA, COT_TEN_KH, COT_SO_KU, COT_DU_NO_KHOANH, COT_NGAY_HH_KHOANH]
                 if c in df_mon_kh.columns]
    df_edit = df_mon_kh[_cols_fix].copy().reset_index(drop=True)
    if COT_DU_NO_KHOANH in df_edit.columns:
        df_edit[COT_DU_NO_KHOANH] = pd.to_numeric(df_edit[COT_DU_NO_KHOANH], errors="coerce").fillna(0).apply(_fmt_dong)
    df_edit.insert(0, "✓ Chọn", True)
    df_edit["Ngày KT dự kiến"] = ""
    df_edit["Ghi chú KT"] = ""

    df_edited = st.data_editor(
        df_edit,
        key=f"{key_prefix}m01_bchon",
        use_container_width=True,
        height=min(45 + len(df_edit) * 35, 520),
        disabled=_cols_fix,
        column_config={
            "✓ Chọn": st.column_config.CheckboxColumn("✓", default=True, width="small"),
            "Ngày KT dự kiến": st.column_config.TextColumn(
                "Ngày KT dự kiến",
                help="Nhập dd/mm/yyyy. Phải trong vòng 120 ngày trước hết hạn khoanh.",
                max_chars=12,
            ),
        },
        hide_index=True,
    )

    # Validate ngày KT
    for _, _rv in df_edited.iterrows():
        if not _rv.get("✓ Chọn", False):
            continue
        _ngay_kt_s = str(_rv.get("Ngày KT dự kiến", "") or "").strip()
        _ngay_hh_s = str(_rv.get(COT_NGAY_HH_KHOANH, "") or "").strip()
        if _ngay_kt_s and _ngay_hh_s:
            try:
                _dkt = pd.to_datetime(_ngay_kt_s, dayfirst=True, errors="coerce")
                _dhh = pd.to_datetime(_ngay_hh_s, dayfirst=True, errors="coerce")
                if pd.notna(_dkt) and pd.notna(_dhh):
                    _delta = (_dhh - _dkt).days
                    if not (0 <= _delta <= 120):
                        st.warning(f"⚠️ {_rv.get(COT_TEN_KH, '')}: Ngày KT cách HH khoanh {_delta} ngày (ngoài 0–120)")
            except Exception:
                pass

    col_b1, col_b2, _ = st.columns([1, 1, 4])
    luu_m01 = col_b1.button("💾 Lưu Mẫu 01", key=f"{key_prefix}m01_luu", use_container_width=True)
    xuat_m01 = col_b2.button("📄 Xuất PDF", key=f"{key_prefix}m01_xuat", use_container_width=True)

    if luu_m01 or xuat_m01:
        ds_mon_save = [
            {
                "so_ku": str(_re.get(COT_SO_KU, "") or ""),
                "ten_kh": str(_re.get(COT_TEN_KH, "") or ""),
                "ten_xa": str(_re.get(COT_TEN_XA, "") or ""),
                "ten_to": str(_re.get(COT_TEN_TO, "") or ""),
                "du_no_khoanh": str(_re.get(COT_DU_NO_KHOANH, "") or ""),
                "ngay_hh_khoanh": str(_re.get(COT_NGAY_HH_KHOANH, "") or ""),
                "ngay_kt_du_kien": str(_re.get("Ngày KT dự kiến", "") or ""),
                "ghi_chu": str(_re.get("Ghi chú KT", "") or ""),
            }
            for _, _re in df_edited.iterrows()
            if _re.get("✓ Chọn", False)
        ]
        tp_list = df_tp[df_tp["Họ và tên"].str.strip() != ""].to_dict("records") if not df_tp.empty else []
        noi_dung_save = {
            "ten_pgd": pgd, "nam": nam, "dot": int(dot_kh),
            "ngay_lap": ngay_lap_kh.isoformat(),
            "thanh_phan_doan": tp_list,
            "ghi_chu": ghi_chu_m01,
            "ds_mon": ds_mon_save,
        }
        if luu_m01:
            _mb_id = db.luu_mau_bieu_cv368("MAU_01", pgd, nam, int(dot_kh), noi_dung_save, username, ghi_chu_m01)
            st.session_state[f"{key_prefix}mau01_mb_id"] = _mb_id
            st.success(f"✅ Đã lưu Mẫu 01 — Đợt {dot_kh}/{nam} (ID #{_mb_id})")
            st.rerun()
        if xuat_m01:
            if not _REPORTLAB_READY:
                st.error("❌ Cần cài reportlab.")
            else:
                try:
                    noi_dung_pdf = {**noi_dung_save, "thanh_phan": tp_list}
                    _pdf_b = _xuat_pdf_ke_hoach_kt(noi_dung_pdf)
                    st.session_state[f"{key_prefix}m01_pdf_buf"] = _pdf_b
                    st.session_state[f"{key_prefix}m01_pdf_fn"] = (
                        f"Mau01_KH_KiemTra_{pgd_slug_val}_{nam}_Dot{int(dot_kh)}.pdf"
                    )
                except Exception as _e:
                    st.error(f"❌ Lỗi tạo PDF: {_e}")

    if st.session_state.get(f"{key_prefix}m01_pdf_buf"):
        st.download_button(
            "⬇️ Tải PDF Mẫu 01",
            data=st.session_state[f"{key_prefix}m01_pdf_buf"],
            file_name=st.session_state.get(f"{key_prefix}m01_pdf_fn", "Mau01.pdf"),
            mime="application/pdf",
            key=f"{key_prefix}m01_dl",
        )


def _render_mau02_cv368(
    df_kh: pd.DataFrame,
    pgd: str,
    pgd_slug_val: str,
    nam: int,
    username: str,
    key_prefix: str,
    xem_id: int | None,
) -> None:
    """Mẫu 02 — Cam kết trả nợ."""
    st.markdown("#### ✍️ Mẫu 02 — Cam kết trả nợ")

    # ── Chế độ xem lại ───────────────────────────────────────────────────────
    if xem_id is not None:
        rec = db.doc_mau_bieu_cv368_by_id(xem_id)
        if rec is None:
            st.error("Không tìm thấy bản ghi.")
            return
        nd = rec["noi_dung"]
        st.info(f"🗒️ Đang xem Mẫu 02 — {nd.get('ten_kh', '')} — ID #{rec['id']}")
        c1, c2 = st.columns(2)
        c1.text_input("Khách hàng", value=nd.get("ten_kh", ""), disabled=True, key=f"{key_prefix}m02v_kh")
        c1.text_input("Số KU", value=nd.get("so_ku", ""), disabled=True, key=f"{key_prefix}m02v_ku")
        c2.text_input("Số tiền cam kết", value=nd.get("so_tien_cam_ket", ""), disabled=True, key=f"{key_prefix}m02v_tien")
        c2.text_input("Thời hạn", value=nd.get("thoi_han", ""), disabled=True, key=f"{key_prefix}m02v_han")
        c2.text_input("Phương thức", value=nd.get("phuong_thuc", ""), disabled=True, key=f"{key_prefix}m02v_pt")
        if st.button("📄 In lại PDF Mẫu 02", key=f"{key_prefix}m02v_pdf_btn", type="primary"):
            if not _REPORTLAB_READY:
                st.error("❌ Cần cài reportlab.")
            else:
                try:
                    _pdf_b = _xuat_pdf_mau_02qlnk(
                        nd,
                        so_tien_cam_ket=nd.get("so_tien_cam_ket", ""),
                        thoi_han=nd.get("thoi_han", ""),
                        phuong_thuc=nd.get("phuong_thuc", ""),
                    )
                    st.session_state[f"{key_prefix}m02_pdf_buf"] = _pdf_b
                    _slug_kh = "".join(c for c in nd.get("ten_kh", "KH") if c.isalnum() or c == "_")
                    st.session_state[f"{key_prefix}m02_pdf_fn"] = f"Mau02_CamKet_{_slug_kh}.pdf"
                except Exception as _e:
                    st.error(f"❌ Lỗi tạo PDF: {_e}")
        if st.session_state.get(f"{key_prefix}m02_pdf_buf"):
            st.download_button(
                "⬇️ Tải PDF Mẫu 02",
                data=st.session_state[f"{key_prefix}m02_pdf_buf"],
                file_name=st.session_state.get(f"{key_prefix}m02_pdf_fn", "Mau02.pdf"),
                mime="application/pdf",
                key=f"{key_prefix}m02v_dl",
            )
        return

    # ── Danh sách đã có Mẫu 02 ───────────────────────────────────────────────
    da_co_mau02: set[str] = {
        item.get("so_ku", "")
        for r in _cached_mau_bieu_cv368(ten_pgd=pgd, loai_mau="MAU_02")
        for item in (r["noi_dung"].get("ds_mon") or [{"so_ku": r["noi_dung"].get("so_ku", "")}])
    }

    if df_kh.empty or COT_SO_KU not in df_kh.columns:
        st.info("ℹ️ Chưa có dữ liệu nợ khoanh.")
        return

    options_ku = {
        f"{r.get(COT_TEN_KH, '')} — {r.get(COT_SO_KU, '')}" + (
            "  ✓ đã có Mẫu 02" if str(r.get(COT_SO_KU, "")) in da_co_mau02 else ""
        ): dict(r)
        for _, r in df_kh.iterrows()
        if r.get(COT_SO_KU)
    }
    if not options_ku:
        st.info("ℹ️ Không có món vay nào.")
        return

    chon_label = st.selectbox("Chọn khách hàng / số khế ước", list(options_ku.keys()), key=f"{key_prefix}m02_sel")
    row_chon = options_ku[chon_label]

    st.markdown("**Thông tin khách hàng** *(từ HSTD)*")
    c1, c2 = st.columns(2)
    c1.text_input("Họ tên KH", value=str(row_chon.get(COT_TEN_KH, "") or ""), disabled=True, key=f"{key_prefix}m02_ten_kh")
    c1.text_input("Số CMND/CCCD", value=str(row_chon.get(COT_CMND, "") or ""), disabled=True, key=f"{key_prefix}m02_cmnd")
    c1.text_input("Tổ TK&VV", value=str(row_chon.get(COT_TEN_TO, "") or ""), disabled=True, key=f"{key_prefix}m02_ten_to")
    c1.text_input("Số KU", value=str(row_chon.get(COT_SO_KU, "") or ""), disabled=True, key=f"{key_prefix}m02_so_ku")
    c2.text_input("Ngày sinh", value=str(row_chon.get(COT_NGAY_SINH, "") or ""), disabled=True, key=f"{key_prefix}m02_ngaysinh")
    c2.text_input("Địa chỉ", value=str(row_chon.get(COT_DIA_CHI, "") or ""), disabled=True, key=f"{key_prefix}m02_diachi")
    _dn_kh_v = float(pd.to_numeric(row_chon.get(COT_DU_NO_KHOANH, 0), errors="coerce") or 0)
    c2.text_input("Dư nợ khoanh", value=_fmt_dong(_dn_kh_v), disabled=True, key=f"{key_prefix}m02_dnkh")
    c2.text_input("Ngày HH khoanh", value=str(row_chon.get(COT_NGAY_HH_KHOANH, "") or ""), disabled=True, key=f"{key_prefix}m02_hh")

    st.markdown("**Cam kết trả nợ**")
    c3, c4, c5 = st.columns(3)
    so_tien_ck = c3.text_input("Số tiền cam kết (đồng)", key=f"{key_prefix}m02_tien_ck")
    thoi_han_ck = c4.text_input("Thời hạn cam kết", placeholder="VD: 6 tháng kể từ...", key=f"{key_prefix}m02_thoi_han")
    phuong_thuc_ck = c5.text_input("Phương thức trả", placeholder="VD: Trả 1 lần", key=f"{key_prefix}m02_pt")
    ghi_chu_m02 = st.text_area("Ghi chú", key=f"{key_prefix}m02_ghi_chu", max_chars=500)

    col_b1, col_b2, _ = st.columns([1, 1, 4])
    luu_m02 = col_b1.button("💾 Lưu Mẫu 02", key=f"{key_prefix}m02_luu", use_container_width=True)
    xuat_m02 = col_b2.button("📄 Xuất PDF", key=f"{key_prefix}m02_xuat", use_container_width=True)

    if luu_m02 or xuat_m02:
        so_ku_val = str(row_chon.get(COT_SO_KU, "") or "")
        ten_kh_val = str(row_chon.get(COT_TEN_KH, "") or "")
        noi_dung_save = {
            "so_ku": so_ku_val, "ten_kh": ten_kh_val,
            "ten_xa": str(row_chon.get(COT_TEN_XA, "") or ""),
            "ten_to": str(row_chon.get(COT_TEN_TO, "") or ""),
            "ten_pgd": pgd,
            COT_CMND: str(row_chon.get(COT_CMND, "") or ""),
            COT_NGAY_SINH: str(row_chon.get(COT_NGAY_SINH, "") or ""),
            COT_DIA_CHI: str(row_chon.get(COT_DIA_CHI, "") or ""),
            COT_DU_NO_KHOANH: _dn_kh_v,
            COT_NGAY_HH_KHOANH: str(row_chon.get(COT_NGAY_HH_KHOANH, "") or ""),
            COT_TEN_TO: str(row_chon.get(COT_TEN_TO, "") or ""),
            COT_DVUT: str(row_chon.get(COT_DVUT, "") or ""),
            COT_TEN_CT: str(row_chon.get(COT_TEN_CT, "") or ""),
            "so_tien_cam_ket": so_tien_ck,
            "thoi_han": thoi_han_ck,
            "phuong_thuc": phuong_thuc_ck,
            "ghi_chu": ghi_chu_m02,
            "ds_mon": [{"so_ku": so_ku_val}],
        }
        if luu_m02:
            _mb_id = db.luu_mau_bieu_cv368("MAU_02", pgd, nam, 1, noi_dung_save, username, ghi_chu_m02)
            st.success(f"✅ Đã lưu Mẫu 02 — KH: {ten_kh_val} (ID #{_mb_id})")
            st.rerun()
        if xuat_m02:
            if not _REPORTLAB_READY:
                st.error("❌ Cần cài reportlab.")
            else:
                try:
                    row_pdf = {**dict(row_chon), **noi_dung_save}
                    _pdf_b = _xuat_pdf_mau_02qlnk(row_pdf, so_tien_cam_ket=so_tien_ck, thoi_han=thoi_han_ck, phuong_thuc=phuong_thuc_ck)
                    st.session_state[f"{key_prefix}m02_pdf_buf"] = _pdf_b
                    _slug_kh = "".join(c for c in ten_kh_val if c.isalnum() or c == "_")
                    ngay_str = datetime.now().strftime("%d%m%Y")
                    st.session_state[f"{key_prefix}m02_pdf_fn"] = f"Mau02_CamKet_{_slug_kh}_{ngay_str}.pdf"
                except Exception as _e:
                    st.error(f"❌ Lỗi tạo PDF: {_e}")

    if st.session_state.get(f"{key_prefix}m02_pdf_buf"):
        st.download_button(
            "⬇️ Tải PDF Mẫu 02",
            data=st.session_state[f"{key_prefix}m02_pdf_buf"],
            file_name=st.session_state.get(f"{key_prefix}m02_pdf_fn", "Mau02.pdf"),
            mime="application/pdf",
            key=f"{key_prefix}m02_dl",
        )


def _render_mau03_cv368(
    df_kh: pd.DataFrame,
    pgd: str,
    pgd_slug_val: str,
    nam: int,
    username: str,
    key_prefix: str,
    xem_id: int | None,
) -> None:
    """Mẫu 03 — Biên bản kiểm tra nợ khoanh."""
    st.markdown("#### 📄 Mẫu 03 — Biên bản kiểm tra")

    # ── Chế độ xem lại ───────────────────────────────────────────────────────
    if xem_id is not None:
        rec = db.doc_mau_bieu_cv368_by_id(xem_id)
        if rec is None:
            st.error("Không tìm thấy bản ghi.")
            return
        nd = rec["noi_dung"]
        st.info(f"🗒️ Đang xem Mẫu 03 — Đợt {rec.get('dot')}/{rec.get('nam')} — ID #{rec['id']}")
        ds_mon_v = nd.get("ds_mon") or []
        if ds_mon_v:
            hien_thi_dataframe_phan_trang(pd.DataFrame(ds_mon_v), key=f"{key_prefix}m03v_tbl", height=320)
        if st.button("📄 In lại PDF Mẫu 03", key=f"{key_prefix}m03v_pdf_btn", type="primary"):
            if not _REPORTLAB_READY:
                st.error("❌ Cần cài reportlab.")
            else:
                try:
                    _pdf_b = _xuat_pdf_bb_kt_cv368(nd)
                    st.session_state[f"{key_prefix}m03_pdf_buf"] = _pdf_b
                    st.session_state[f"{key_prefix}m03_pdf_fn"] = (
                        f"Mau03_BB_KiemTra_{pgd_slug_val}_{rec.get('nam')}_Dot{rec.get('dot', 1)}.pdf"
                    )
                except Exception as _e:
                    st.error(f"❌ Lỗi tạo PDF: {_e}")
        if st.session_state.get(f"{key_prefix}m03_pdf_buf"):
            st.download_button(
                "⬇️ Tải PDF Mẫu 03",
                data=st.session_state[f"{key_prefix}m03_pdf_buf"],
                file_name=st.session_state.get(f"{key_prefix}m03_pdf_fn", "Mau03.pdf"),
                mime="application/pdf",
                key=f"{key_prefix}m03v_dl",
            )
        return

    # ── Load Mẫu 01 đã lưu ───────────────────────────────────────────────────
    rows_mau01 = db.doc_mau_bieu_cv368(ten_pgd=pgd, loai_mau="MAU_01", nam=nam)
    if not rows_mau01:
        st.warning("⚠️ Cần lập Mẫu 01 trước. Chưa có Mẫu 01 nào được lưu cho năm này.")
        return

    options_m01 = {
        f"Đợt {r.get('dot')}/{r.get('nam')} — ID #{r['id']} — {str(r.get('created_at', ''))[:10]}": r
        for r in rows_mau01
    }
    chon_m01_label = st.selectbox("Chọn Mẫu 01 tham chiếu", list(options_m01.keys()), key=f"{key_prefix}m03_sel_m01")
    mau01_sel = options_m01[chon_m01_label]
    nd_m01 = mau01_sel.get("noi_dung") or {}
    ds_mon_m01 = nd_m01.get("ds_mon") or []
    dot_from_m01 = mau01_sel.get("dot", 1)

    if not ds_mon_m01:
        st.warning("⚠️ Mẫu 01 này không có danh sách món vay.")
        return

    c1, c2, c3 = st.columns(3)
    c1.text_input("PGD", value=pgd, disabled=True, key=f"{key_prefix}m03_pgd")
    c2.number_input("Năm", value=nam, disabled=True, key=f"{key_prefix}m03_nam", step=1)
    c3.number_input("Đợt", value=int(dot_from_m01), disabled=True, key=f"{key_prefix}m03_dot", step=1)
    ngay_kt_thuc_te = st.date_input("Ngày kiểm tra thực tế *", value=datetime.now().date(), key=f"{key_prefix}m03_ngay_kt")

    st.markdown("**Thành phần đoàn**")
    tp_default = nd_m01.get("thanh_phan_doan") or [{"Họ và tên": username, "Chức vụ": "CBTD"}]
    df_tp_m03 = st.data_editor(
        pd.DataFrame(tp_default),
        num_rows="dynamic", key=f"{key_prefix}m03_tp_doan",
        use_container_width=True, hide_index=True,
    )
    ghi_chu_m03 = st.text_area("Ghi chú", key=f"{key_prefix}m03_ghi_chu", max_chars=500)

    st.markdown("**Kết quả kiểm tra từng món vay**")
    _cols_fix_m03 = ["Tên tổ", "Tên KH", "Số KU", "Dư nợ khoanh", "Ngày HH khoanh"]
    df_mon_edit = pd.DataFrame([{
        "✓ KT": True,
        "Tên tổ": item.get("ten_to", ""),
        "Tên KH": item.get("ten_kh", ""),
        "Số KU": item.get("so_ku", ""),
        "Dư nợ khoanh": item.get("du_no_khoanh", ""),
        "Ngày HH khoanh": item.get("ngay_hh_khoanh", ""),
        "Kết quả KT": "",
        "Khả năng TN": "",
        "Cam kết TN": "",
        "Ghi chú": "",
    } for item in ds_mon_m01])

    df_mon_edited = st.data_editor(
        df_mon_edit,
        key=f"{key_prefix}m03_bmon",
        use_container_width=True,
        height=min(45 + len(df_mon_edit) * 35, 560),
        disabled=_cols_fix_m03,
        column_config={
            "✓ KT": st.column_config.CheckboxColumn("✓ KT", default=True, width="small"),
            "Kết quả KT": st.column_config.SelectboxColumn(
                "Kết quả KT",
                options=["Đủ điều kiện", "Không đủ ĐK", "Vắng mặt", "Khác"],
                required=False,
            ),
            "Khả năng TN": st.column_config.SelectboxColumn(
                "Khả năng TN",
                options=["Có", "Không", "Chưa xác định"],
                required=False,
            ),
        },
        hide_index=True,
    )

    col_b1, col_b2, _ = st.columns([1, 1, 4])
    luu_m03 = col_b1.button("💾 Lưu Mẫu 03", key=f"{key_prefix}m03_luu", use_container_width=True)
    xuat_m03 = col_b2.button("📄 Xuất PDF", key=f"{key_prefix}m03_xuat", use_container_width=True)

    if luu_m03 or xuat_m03:
        ds_mon_kq = [
            {
                "ten_to": str(_re.get("Tên tổ", "") or ""),
                "ten_kh": str(_re.get("Tên KH", "") or ""),
                "so_ku": str(_re.get("Số KU", "") or ""),
                "du_no_khoanh": str(_re.get("Dư nợ khoanh", "") or ""),
                "ngay_hh_khoanh": str(_re.get("Ngày HH khoanh", "") or ""),
                "ket_qua_kt": str(_re.get("Kết quả KT", "") or ""),
                "kha_nang_tn": str(_re.get("Khả năng TN", "") or ""),
                "cam_ket_tn": str(_re.get("Cam kết TN", "") or ""),
                "ghi_chu": str(_re.get("Ghi chú", "") or ""),
            }
            for _, _re in df_mon_edited.iterrows()
            if _re.get("✓ KT", True)
        ]
        tp_m03_list = df_tp_m03[df_tp_m03["Họ và tên"].str.strip() != ""].to_dict("records") if not df_tp_m03.empty else []
        noi_dung_save = {
            "ten_pgd": pgd, "nam": nam, "dot": int(dot_from_m01),
            "ngay_kiem_tra": str(ngay_kt_thuc_te),
            "thanh_phan_doan": tp_m03_list,
            "ghi_chu": ghi_chu_m03,
            "ds_mon": ds_mon_kq,
            "mau01_id": mau01_sel.get("id"),
        }
        if luu_m03:
            _mb_id = db.luu_mau_bieu_cv368("MAU_03", pgd, nam, int(dot_from_m01), noi_dung_save, username, ghi_chu_m03)
            st.success(f"✅ Đã lưu Mẫu 03 — Đợt {dot_from_m01}/{nam} (ID #{_mb_id})")
            st.rerun()
        if xuat_m03:
            if not _REPORTLAB_READY:
                st.error("❌ Cần cài reportlab.")
            else:
                try:
                    _pdf_b = _xuat_pdf_bb_kt_cv368(noi_dung_save)
                    st.session_state[f"{key_prefix}m03_pdf_buf"] = _pdf_b
                    st.session_state[f"{key_prefix}m03_pdf_fn"] = (
                        f"Mau03_BB_KiemTra_{pgd_slug_val}_{nam}_Dot{int(dot_from_m01)}.pdf"
                    )
                except Exception as _e:
                    st.error(f"❌ Lỗi tạo PDF: {_e}")

    if st.session_state.get(f"{key_prefix}m03_pdf_buf"):
        st.download_button(
            "⬇️ Tải PDF Mẫu 03",
            data=st.session_state[f"{key_prefix}m03_pdf_buf"],
            file_name=st.session_state.get(f"{key_prefix}m03_pdf_fn", "Mau03.pdf"),
            mime="application/pdf",
            key=f"{key_prefix}m03_dl",
        )


def _render_cv368_kt(
    df_kh: pd.DataFrame,
    role: str,
    pgd_user: str | None,
    username: str,
    key_prefix: str,
) -> None:
    """UI drill-down 3 mẫu biểu theo CV 368/NHCS-QLN."""
    from data.pgd import pgd_slug as _pgd_slug_fn
    nam_hien = datetime.now().year

    # ── Xác định PGD hiện tại ─────────────────────────────────────────────────
    if la_phan_he_cn(role):
        pgd_hien_tai = st.selectbox(
            "📍 Chọn PGD",
            ["— Chọn —"] + DS_PGD,
            key=f"{key_prefix}cv368_pgd",
        )
        if pgd_hien_tai == "— Chọn —":
            st.info("ℹ️ Chọn PGD để bắt đầu.")
            return
    else:
        pgd_hien_tai = pgd_user or ""
        if not pgd_hien_tai:
            st.warning("⚠️ Không xác định được PGD.")
            return
        st.info(f"PGD: **{pgd_hien_tai}**")

    # Lọc df_kh theo PGD
    if pgd_hien_tai and COT_TEN_PGD in df_kh.columns:
        df_kh_pgd = df_kh[df_kh[COT_TEN_PGD] == pgd_hien_tai].copy()
    else:
        df_kh_pgd = df_kh.copy()

    pgd_slug_val = _pgd_slug_fn(pgd_hien_tai)

    if df_kh_pgd.empty:
        st.info("ℹ️ Chưa có dữ liệu nợ khoanh cho PGD này.")
        return

    # ── Layout 2 cột ──────────────────────────────────────────────────────────
    col_left, col_right = st.columns([3, 7])

    with col_left:
        st.markdown("#### 🗂️ Chọn mẫu biểu")
        loai_mau_label = st.radio(
            "Chọn mẫu",
            [
                "📋 Mẫu 01 — Kế hoạch kiểm tra",
                "✍️ Mẫu 02 — Cam kết trả nợ",
                "📄 Mẫu 03 — Biên bản kiểm tra",
            ],
            key=f"{key_prefix}chon_loai_mau",
            label_visibility="collapsed",
        )
        _loai_map = {
            "📋 Mẫu 01 — Kế hoạch kiểm tra": "MAU_01",
            "✍️ Mẫu 02 — Cam kết trả nợ": "MAU_02",
            "📄 Mẫu 03 — Biên bản kiểm tra": "MAU_03",
        }
        loai_mau_hien = _loai_map[loai_mau_label]

        # Reset xem_id khi đổi mẫu
        if st.session_state.get(f"{key_prefix}_prev_loai") != loai_mau_hien:
            st.session_state.pop(f"{key_prefix}mb_xem_id", None)
            st.session_state[f"{key_prefix}_prev_loai"] = loai_mau_hien

        st.markdown("---")
        st.markdown("##### 📋 Lịch sử")
        if st.button("➕ Tạo mới", key=f"{key_prefix}ls_moi", use_container_width=True):
            st.session_state.pop(f"{key_prefix}mb_xem_id", None)
            st.rerun()

        lich_su = db.doc_mau_bieu_cv368(ten_pgd=pgd_hien_tai, loai_mau=loai_mau_hien)
        if not lich_su:
            st.caption("Chưa có bản ghi nào.")
        else:
            _cur_xem = st.session_state.get(f"{key_prefix}mb_xem_id")
            for _r in lich_su[:10]:
                _ngay = str(_r.get("created_at", ""))[:10]
                _lbl = f"Đợt {_r.get('dot')}/{_r.get('nam')} — {_ngay}"
                if st.button(
                    f"{'🔵' if _cur_xem == _r['id'] else '🗒️'} {_lbl}",
                    key=f"{key_prefix}ls_btn_{_r['id']}",
                    use_container_width=True,
                ):
                    st.session_state[f"{key_prefix}mb_xem_id"] = _r["id"]
                    st.rerun()
            if len(lich_su) > 10:
                st.caption(f"+ {len(lich_su) - 10} bản ghi khác")

    with col_right:
        _xem_id = st.session_state.get(f"{key_prefix}mb_xem_id")
        if loai_mau_hien == "MAU_01":
            _render_mau01_cv368(df_kh_pgd, pgd_hien_tai, pgd_slug_val, nam_hien, username, key_prefix, _xem_id)
        elif loai_mau_hien == "MAU_02":
            _render_mau02_cv368(df_kh_pgd, pgd_hien_tai, pgd_slug_val, nam_hien, username, key_prefix, _xem_id)
        else:
            _render_mau03_cv368(df_kh_pgd, pgd_hien_tai, pgd_slug_val, nam_hien, username, key_prefix, _xem_id)


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
    username = kwargs.get("username", "unknown")

    ctx = get_tab_context(tab)
    with ctx:
        st.subheader("🔒 Chuyên Đề Nợ Khoanh")
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

        # Chuẩn hóa tên PGD: alias cũ trong data → tên nội bộ chuẩn
        if COT_TEN_PGD in df_kh.columns:
            _pgd_alias = {
                "Đồng Nai": DON_VI_CHI_NHANH,
                "Chi nhánh Đồng Nai": DON_VI_CHI_NHANH,
                "CN Đồng Nai": DON_VI_CHI_NHANH,
                "Hội sở": DON_VI_CHI_NHANH,
            }
            df_kh[COT_TEN_PGD] = df_kh[COT_TEN_PGD].replace(_pgd_alias)

        if df_kh.empty:
            st.success("✅ Hiện không có món vay nào đang khoanh nợ.")
            return

        st.divider()

        # ── Lọc PGD (CN only) — thực hiện TRƯỚC khi tính KPI ─────────────
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

        # ── KPI tổng quan — tính từ df_kh (đã qua filter PGD) ─────────────
        # tong_du_no: toàn bộ dư nợ cùng scope — lọc use_df theo PGD đã chọn
        _pgd_filter_kpi = (
            st.session_state.get("khoanh_pgd_loc")
            if la_phan_he_cn(role) else pgd_user
        )
        if _pgd_filter_kpi and _pgd_filter_kpi != "Tất cả" and COT_TEN_PGD in use_df.columns:
            use_df_scope = use_df[use_df[COT_TEN_PGD] == _pgd_filter_kpi]
        else:
            use_df_scope = use_df

        tong_du_no = (
            pd.to_numeric(use_df_scope[COT_TONG_DU_NO], errors="coerce").sum()
            if COT_TONG_DU_NO in use_df_scope.columns else 0
        )
        tong_khoanh = (
            pd.to_numeric(df_kh[COT_DU_NO_KHOANH], errors="coerce").fillna(0).sum()
        )
        so_mon = (
            df_kh[COT_SO_KU].nunique() if COT_SO_KU in df_kh.columns
            else len(df_kh)
        )
        so_ho = (
            df_kh[COT_MA_KH].nunique() if COT_MA_KH in df_kh.columns
            else 0
        )
        tl_khoanh = tong_khoanh / tong_du_no * 100 if tong_du_no > 0 else 0

        k1, k2, k3, k4 = st.columns(4)
        k1.metric("🔒 Số món khoanh", fmt_so(so_mon) + " món")
        k2.metric("👤 Số hộ", fmt_so(so_ho) + " hộ")
        k3.metric("💰 Tổng dư nợ khoanh", fmt_ty(tong_khoanh))
        k4.metric(
            "📊 Tỷ lệ khoanh / tổng DN",
            f"{tl_khoanh:.2f}".replace(".", ",") + "%",
            delta=f"{tl_khoanh:.2f}".replace(".", ",") + "%" if tl_khoanh > 0 else None,
            delta_color="inverse" if tl_khoanh > 2 else "off",
        )

        # ── Heatmap đáo hạn ───────────────────────────────────────────────
        _heatmap_dao_han(df_kh, key=f"{key_prefix}khoanh_hm")

        st.divider()

        # ── Lọc món sắp hết hạn khoanh (từ sidebar badge) ────────────────
        _qlnk_filter = st.session_state.pop('_qlnk_filter', None)
        if _qlnk_filter == 'sap_het_han':
            from alert_center import canh_bao_no_khoanh_sap_het_han
            data_hh = canh_bao_no_khoanh_sap_het_han(df_kh)
            ds_hh = data_hh['chi_tiet_khan'] + data_hh['chi_tiet_canh_bao']
            if ds_hh:
                st.markdown("#### 🔍 Sắp hết hạn khoanh (M03)")
                st.caption(
                    f"🔴 {data_hh['so_khan']} món hết hạn ≤30 ngày · "
                    f"🟠 {data_hh['so_canh_bao']} món sắp hết hạn ≤180 ngày"
                )
                df_show = pd.DataFrame(ds_hh)
                if 'con_lai' in df_show.columns:
                    df_show = df_show.sort_values('con_lai')
                    df_show['Hạn còn (ngày)'] = df_show['con_lai']
                    df_show = df_show.drop(columns=['con_lai'], errors='ignore')
                st.dataframe(
                    df_show, use_container_width=True, hide_index=True,
                )
            else:
                st.success("✅ Không có món nào sắp hết hạn khoanh.")

        # ── Sub-tabs ──────────────────────────────────────────────────────
        # nhom="tongquan" | "cv368" | None (hiện cả 7 tab khi gọi standalone)
        nhom = kwargs.get("nhom")
        pgd_filter_bc = None if la_phan_he_cn(role) else pgd_user
        rows_all_kt = _cached_ket_qua_kiem_tra(ten_pgd=pgd_filter_bc)
        da_kiem_tra_set = {r["ma_mon_vay"] for r in rows_all_kt}

        if nhom != "cv368":
            d0, d1, d2, d3, d4 = st.tabs([
                "📊 Tổng quan",
                "📋 Theo Chương trình",
                "🏘️ Theo Xã",
                "🤝 Theo Hội đoàn thể",
                "📄 Danh sách chi tiết",
            ])
        else:
            d0 = d1 = d2 = d3 = d4 = None

        if nhom != "tongquan":
            d_kt, d_bc = st.tabs([
                "📋 Kiểm tra nợ khoanh (theo CV 368)",
                "📊 Báo cáo",
            ])
        else:
            d_kt = d_bc = None

        if d0 is not None:
            with d0:
                tab_qlnk_dashboard.render(d0, **kwargs)

        for dtab, nhom_col, tag, label in [
            (d1, COT_TEN_CT,  "ct",   "Chương trình"),
            (d2, COT_TEN_XA,  "xa",   "Xã"),
            (d3, COT_DVUT,    "dvut", "Hội đoàn thể"),
        ]:
            if dtab is None:
                continue
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

        if d4 is not None:
            with d4:
                cols_hien = [c for c in [
                    COT_TEN_PGD, COT_TEN_XA, COT_DVUT, COT_TEN_KH, COT_SO_KU,
                    COT_TEN_CT, COT_DU_NO_KHOANH, COT_DU_NO_QH, COT_NGAY_DH,
                ] if c in df_kh.columns]

                df_hien = df_kh[cols_hien].copy()
                if COT_DU_NO_KHOANH in df_hien.columns:
                    df_hien[COT_DU_NO_KHOANH] = (
                        pd.to_numeric(df_hien[COT_DU_NO_KHOANH], errors="coerce")
                        .fillna(0).apply(_fmt_dong)
                    )
                if COT_DU_NO_QH in df_hien.columns:
                    df_hien[COT_DU_NO_QH] = (
                        pd.to_numeric(df_hien[COT_DU_NO_QH], errors="coerce")
                        .fillna(0).apply(_fmt_dong)
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

        if nhom == "tongquan":
            return

        with d_kt:
            perms = get_permissions(role)
            co_quyen_nhap  = perms.get("can_upload") or perms.get("upload")
            co_quyen_duyet = la_phan_he_cn(role) or co_quyen_upload_pgd(role)
            pgd_filter_kh  = None if la_phan_he_cn(role) else pgd_user

            # ── A: Form lập kế hoạch cả năm ──────────────────────────────────
            with st.expander("➕ Lập / cập nhật kế hoạch kiểm tra cả năm", expanded=False):
                if not co_quyen_nhap:
                    st.warning("⚠️ Bạn không có quyền lập kế hoạch kiểm tra.")
                else:
                    c1, c2 = st.columns([1, 2])
                    with c1:
                        nam_kh = st.number_input(
                            "Năm kế hoạch *",
                            min_value=2020, max_value=2035,
                            value=datetime.now().year, step=1,
                            key=f"{key_prefix}kh_nam",
                        )
                    with c2:
                        if la_phan_he_cn(role):
                            pgd_kh = st.selectbox(
                                "PGD *", ["— Chọn —"] + DS_PGD,
                                key=f"{key_prefix}kh_pgd",
                            )
                        else:
                            pgd_kh = pgd_user or ""
                            st.info(f"PGD: **{pgd_kh}**")

                    # Lọc toàn bộ món khoanh hết hạn trong năm đã chọn
                    df_kh_form = df_kh.copy()
                    if la_phan_he_cn(role) and pgd_kh != "— Chọn —":
                        if COT_TEN_PGD in df_kh_form.columns:
                            df_kh_form = df_kh_form[df_kh_form[COT_TEN_PGD] == pgd_kh]
                    elif not la_phan_he_cn(role) and pgd_user:
                        if COT_TEN_PGD in df_kh_form.columns:
                            df_kh_form = df_kh_form[df_kh_form[COT_TEN_PGD] == pgd_user]

                    if COT_NGAY_HH_KHOANH in df_kh_form.columns:
                        _hh_s = pd.to_datetime(
                            df_kh_form[COT_NGAY_HH_KHOANH], dayfirst=True, errors="coerce"
                        )
                        df_kh_form = df_kh_form[_hh_s.dt.year == int(nam_kh)].copy()

                    if df_kh_form.empty:
                        _pgd_s = f" của {pgd_kh}" if (la_phan_he_cn(role) and pgd_kh != "— Chọn —") else ""
                        st.info(f"ℹ️ Không có món vay khoanh nào hết hạn trong năm {int(nam_kh)}{_pgd_s}.")
                    else:
                        st.info(
                            f"📋 **{len(df_kh_form)} món vay** hết hạn khoanh trong năm {int(nam_kh)}. "
                            "Điền **Ngày KT dự kiến** cho từng món "
                            "(bắt buộc trong vòng **120 ngày** trước ngày hết hạn khoanh)."
                        )

                        # Bảng phân công — data_editor (chỉ 2 cột được chỉnh)
                        _cols_co_dinh = [c for c in [
                            COT_TEN_XA, COT_TEN_TO, COT_TEN_KH,
                            COT_SO_KU, COT_DU_NO_KHOANH, COT_NGAY_HH_KHOANH,
                        ] if c in df_kh_form.columns]

                        df_edit = df_kh_form[_cols_co_dinh].copy().reset_index(drop=True)
                        df_edit[COT_DU_NO_KHOANH] = (
                            pd.to_numeric(df_edit[COT_DU_NO_KHOANH], errors="coerce")
                            .fillna(0).apply(_fmt_dong)
                        )
                        df_edit["Ngày KT dự kiến"] = ""
                        df_edit["Ghi chú"]         = ""

                        df_edited = st.data_editor(
                            df_edit,
                            key=f"{key_prefix}kh_phan_cong",
                            use_container_width=True,
                            height=min(45 + len(df_edit) * 35, 520),
                            disabled=_cols_co_dinh,
                            column_config={
                                "Ngày KT dự kiến": st.column_config.TextColumn(
                                    "Ngày KT dự kiến",
                                    help="Nhập dạng dd/mm/yyyy. Phải ≤ 120 ngày trước HH khoanh.",
                                    max_chars=12,
                                ),
                            },
                        )

                        # Thành phần đoàn
                        st.markdown("**Thành phần đoàn kiểm tra**")
                        df_tp = st.data_editor(
                            pd.DataFrame([
                                {"Họ và tên": username, "Chức vụ": "CBTD"},
                                {"Họ và tên": "",       "Chức vụ": ""},
                            ]),
                            num_rows="dynamic",
                            key=f"{key_prefix}kh_tp_doan",
                            use_container_width=True,
                        )

                        ghi_chu_kh = st.text_area(
                            "Ghi chú chung", key=f"{key_prefix}kh_ghi_chu", max_chars=500,
                        )

                        col_b1, col_b2, _ = st.columns([1, 1, 4])
                        with col_b1:
                            luu_kh_btn = st.button(
                                "💾 Lưu kế hoạch", key=f"{key_prefix}kh_luu",
                                use_container_width=True,
                            )
                        with col_b2:
                            duyet_kh_btn = st.button(
                                "✅ Duyệt luôn", key=f"{key_prefix}kh_duyet_luon",
                                disabled=not co_quyen_duyet, use_container_width=True,
                            )

                        if luu_kh_btn or duyet_kh_btn:
                            loi_kh = []
                            if la_phan_he_cn(role) and pgd_kh == "— Chọn —":
                                loi_kh.append("Chưa chọn PGD")

                            # Build ds_phan_cong
                            ku_hh_map = {}
                            if COT_SO_KU in df_kh_form.columns and COT_NGAY_HH_KHOANH in df_kh_form.columns:
                                ku_hh_map = {
                                    str(r[COT_SO_KU] or ""): str(r[COT_NGAY_HH_KHOANH] or "")
                                    for _, r in df_kh_form.iterrows()
                                }
                            ds_phan_cong = []
                            for _, row_e in df_edited.iterrows():
                                so_ku     = str(row_e.get(COT_SO_KU, "") or "")
                                ngay_kt_s = str(row_e.get("Ngày KT dự kiến", "") or "").strip()
                                hh_raw    = ku_hh_map.get(so_ku, "")
                                ds_phan_cong.append({
                                    "so_ku":           so_ku,
                                    "ten_kh":          str(row_e.get(COT_TEN_KH, "") or ""),
                                    "ten_xa":          str(row_e.get(COT_TEN_XA, "") or ""),
                                    "ten_to":          str(row_e.get(COT_TEN_TO, "") or ""),
                                    "ngay_hh_khoanh":  hh_raw,
                                    "du_no_khoanh":    str(row_e.get(COT_DU_NO_KHOANH, "") or ""),
                                    "ngay_kt_du_kien": ngay_kt_s,
                                    "ghi_chu":         str(row_e.get("Ghi chú", "") or ""),
                                })

                            if loi_kh:
                                for _l in loi_kh:
                                    st.error(f"❌ {_l}")
                            else:
                                tp_list    = df_tp[df_tp["Họ và tên"].str.strip() != ""].to_dict("records")
                                ten_pgd_kh = pgd_kh if la_phan_he_cn(role) else (pgd_user or "")
                                data_kh = {
                                    "ten_pgd":         ten_pgd_kh,
                                    "nam":             int(nam_kh),
                                    "thanh_phan_doan": tp_list,
                                    "ds_phan_cong":    ds_phan_cong,
                                    "ghi_chu":         ghi_chu_kh,
                                }
                                try:
                                    kh_id = db.luu_ke_hoach_kiem_tra(data_kh, username)
                                    if duyet_kh_btn:
                                        db.duyet_ke_hoach(kh_id, username)
                                    label_kh = "lưu và duyệt" if duyet_kh_btn else "lưu"
                                    st.success(f"✅ Đã {label_kh} kế hoạch kiểm tra năm {int(nam_kh)}.")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"❌ Lỗi: {e}")

                        # ── Thành phần tham gia + Xuất PDF ───────────────────
                        st.markdown("---")
                        st.markdown("**📋 Thành phần tham gia kiểm tra**")
                        _to_list_str = (
                            ", ".join(sorted(
                                df_kh_form[COT_TEN_TO].dropna().unique().tolist()
                            ))
                            if COT_TEN_TO in df_kh_form.columns else ""
                        )
                        c_tp1, c_tp2 = st.columns(2)
                        with c_tp1:
                            dai_dien_nhcsxh = st.text_input(
                                "Đại diện NHCSXH", value=username,
                                key=f"{key_prefix}kh_dd_nhcsxh",
                            )
                            dai_dien_ct_xh = st.text_input(
                                "Đại diện tổ chức CT-XH",
                                placeholder="Hội Phụ nữ / Hội Nông dân / ...",
                                key=f"{key_prefix}kh_dd_ctxh",
                            )
                            truong_thon = st.text_input(
                                "Trưởng thôn", value="Ông/Bà ............",
                                key=f"{key_prefix}kh_truong_thon",
                            )
                        with c_tp2:
                            to_tkv = st.text_input(
                                "Đại diện Ban quản lý Tổ TK&VV", value=_to_list_str,
                                key=f"{key_prefix}kh_to_tkv",
                            )
                            ubnd_xa = st.text_input(
                                "Đại diện UBND xã", value="",
                                key=f"{key_prefix}kh_ubnd_xa",
                            )

                        ten_pgd_kh_cur = pgd_kh if la_phan_he_cn(role) else (pgd_user or "")
                        _rows_kh_pdf = []
                        if not (la_phan_he_cn(role) and pgd_kh == "— Chọn —"):
                            _rows_kh_pdf = _cached_ke_hoach_kiem_tra(
                                ten_pgd=ten_pgd_kh_cur, nam=int(nam_kh),
                            )

                        if _rows_kh_pdf or not df_kh_form.empty:
                            if st.button(
                                "📄 Xuất PDF Kế hoạch", key=f"{key_prefix}kh_pdf_btn",
                                type="primary",
                            ):
                                if not _REPORTLAB_READY:
                                    st.error("❌ Cần cài reportlab để xuất PDF.")
                                else:
                                    if _rows_kh_pdf:
                                        _ds_pc_pdf = _rows_kh_pdf[0].get("ds_phan_cong") or []
                                    else:
                                        _ku_hh_map_pdf = {}
                                        if (COT_SO_KU in df_kh_form.columns
                                                and COT_NGAY_HH_KHOANH in df_kh_form.columns):
                                            _ku_hh_map_pdf = {
                                                str(r[COT_SO_KU] or ""): str(r[COT_NGAY_HH_KHOANH] or "")
                                                for _, r in df_kh_form.iterrows()
                                            }
                                        _ds_pc_pdf = [
                                            {
                                                "so_ku":           str(re_.get(COT_SO_KU, "") or ""),
                                                "ten_kh":          str(re_.get(COT_TEN_KH, "") or ""),
                                                "ten_xa":          str(re_.get(COT_TEN_XA, "") or ""),
                                                "ten_to":          str(re_.get(COT_TEN_TO, "") or ""),
                                                "ngay_hh_khoanh":  _ku_hh_map_pdf.get(str(re_.get(COT_SO_KU, "") or ""), ""),
                                                "du_no_khoanh":    str(re_.get(COT_DU_NO_KHOANH, "") or ""),
                                                "ngay_kt_du_kien": str(re_.get("Ngày KT dự kiến", "") or ""),
                                                "ghi_chu":         str(re_.get("Ghi chú", "") or ""),
                                            }
                                            for _, re_ in df_edited.iterrows()
                                        ]
                                    _thanh_phan_pdf = {
                                        "dai_dien_nhcsxh": dai_dien_nhcsxh,
                                        "to_tkv":          to_tkv,
                                        "ct_xh":           dai_dien_ct_xh,
                                        "truong_thon":     truong_thon,
                                        "ubnd_xa":         ubnd_xa,
                                    }
                                    try:
                                        st.session_state[f"{key_prefix}kh_pdf_buf"] = (
                                            _xuat_pdf_ke_hoach_kt(
                                                {}, _ds_pc_pdf, _thanh_phan_pdf,
                                                ten_pgd_kh_cur, int(nam_kh),
                                            )
                                        )
                                    except Exception as _e_kh_pdf:
                                        st.error(f"❌ Lỗi tạo PDF: {_e_kh_pdf}")

                            if st.session_state.get(f"{key_prefix}kh_pdf_buf"):
                                st.download_button(
                                    "⬇️ Tải PDF Kế hoạch",
                                    data=st.session_state[f"{key_prefix}kh_pdf_buf"],
                                    file_name=(
                                        f"KH_KiemTra_NK_{ten_pgd_kh_cur}_{int(nam_kh)}.pdf"
                                    ),
                                    mime="application/pdf",
                                    key=f"{key_prefix}kh_pdf_dl",
                                )

            # ── B: Danh sách kế hoạch đã lập ─────────────────────────────────
            st.markdown("### 📋 Danh sách kế hoạch đã lập")

            cf1, cf2, _ = st.columns([1, 2, 3])
            with cf1:
                nam_loc = st.number_input(
                    "Năm", min_value=2020, max_value=2035,
                    value=datetime.now().year, step=1,
                    key=f"{key_prefix}kh_loc_nam",
                )
            with cf2:
                loc_tt_kh = st.selectbox(
                    "Trạng thái",
                    ["Tất cả", "Chờ duyệt", "Đã duyệt"],
                    key=f"{key_prefix}kh_loc_tt",
                )
            tt_map_kh = {"Tất cả": None, "Chờ duyệt": "luu_tam", "Đã duyệt": "da_duyet"}

            rows_kh = _cached_ke_hoach_kiem_tra(
                ten_pgd=pgd_filter_kh,
                trang_thai=tt_map_kh[loc_tt_kh],
                nam=int(nam_loc),
            )

            if not rows_kh:
                st.info("ℹ️ Chưa có kế hoạch nào.")
            else:
                df_kh_list = pd.DataFrame([{
                    "ID":            r["id"],
                    "PGD":           r["ten_pgd"],
                    "Năm":           r.get("nam", ""),
                    "Tổng món":      len(r.get("ds_phan_cong") or []),
                    "Đã điền ngày":  sum(
                        1 for x in (r.get("ds_phan_cong") or [])
                        if x.get("ngay_kt_du_kien", "").strip()
                    ),
                    "Trạng thái":    r["trang_thai"],
                    "Người lập":     r["nguoi_lap"],
                    "Người duyệt":   r.get("nguoi_duyet", ""),
                    "Ngày duyệt":    r.get("ngay_duyet", ""),
                } for r in rows_kh])

                hien_thi_dataframe_phan_trang(
                    df_kh_list, key=f"{key_prefix}kh_list_tbl", height=320,
                )

                if co_quyen_duyet:
                    st.markdown("**Duyệt kế hoạch theo ID:**")
                    kh_id_action = st.number_input(
                        "ID kế hoạch", min_value=1, step=1,
                        key=f"{key_prefix}kh_action_id",
                    )
                    if st.button("✅ Duyệt kế hoạch này", key=f"{key_prefix}kh_duyet_id"):
                        ok = db.duyet_ke_hoach(int(kh_id_action), username)
                        st.success("Đã duyệt.") if ok else st.error("Không thể duyệt.")
                        st.rerun()

        with d_kt:
            st.divider()
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
                            _cached_bo_sung_mon_vay(chon_ku)
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
                                "ngay_het_han_khoanh": (
                                    str(row_chon.get(COT_NGAY_HH_KHOANH, "") or "")
                                    if row_chon is not None else ""
                                ),
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

            rows_kt = _cached_ket_qua_kiem_tra(
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

        with d_bc:
            st.markdown("### 📊 Báo cáo Quản lý Nợ khoanh")

            with st.expander(
                "📋 M08 — Danh sách món vay chưa kiểm tra", expanded=True
            ):
                if COT_SO_KU in df_kh.columns:
                    df_chua_kt = df_kh[~df_kh[COT_SO_KU].isin(da_kiem_tra_set)].copy()
                else:
                    df_chua_kt = df_kh.copy()

                st.metric("Số món chưa kiểm tra", fmt_so(len(df_chua_kt)) + " món")

                if not df_chua_kt.empty:
                    cols_m08 = [c for c in [
                        COT_TEN_PGD, COT_TEN_XA, COT_TEN_KH, COT_SO_KU,
                        COT_DU_NO_KHOANH, COT_NGAY_HH_KHOANH,
                    ] if c in df_chua_kt.columns]
                    df_m08_display = df_chua_kt[cols_m08].copy()
                    if COT_DU_NO_KHOANH in df_m08_display.columns:
                        df_m08_display[COT_DU_NO_KHOANH] = (
                            pd.to_numeric(df_m08_display[COT_DU_NO_KHOANH], errors="coerce")
                            .fillna(0).apply(_fmt_dong)
                        )
                    hien_thi_dataframe_phan_trang(
                        df_m08_display,
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
                st.metric("Số món có KN trả nợ", fmt_so(len(df_m09)) + " món")
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

            with st.expander("📊 QLNK_06 — Báo cáo kết quả kiểm tra nợ khoanh", expanded=False):
                st.markdown("**Bộ lọc**")
                col_f1, col_f2, col_f3 = st.columns(3)
                with col_f1:
                    pgd_f06 = st.selectbox(
                        "PGD",
                        options=["— Tất cả —"] + (
                            sorted([r.get("ten_pgd", "") for r in rows_all_kt
                                    if r.get("ten_pgd")]) if rows_all_kt else []
                        ),
                        key=f"{key_prefix}bc_06_pgd",
                    )
                with col_f2:
                    ngay_tu_06 = st.text_input(
                        "Từ ngày (dd/mm/yyyy)",
                        key=f"{key_prefix}bc_06_tu",
                    )
                with col_f3:
                    ngay_den_06 = st.text_input(
                        "Đến ngày (dd/mm/yyyy)",
                        key=f"{key_prefix}bc_06_den",
                    )

                # Lọc dữ liệu
                df_06 = pd.DataFrame(rows_all_kt) if rows_all_kt else pd.DataFrame()
                if not df_06.empty:
                    if pgd_f06 != "— Tất cả —":
                        df_06 = df_06[df_06["ten_pgd"] == pgd_f06]

                    # Lọc ngày nếu có
                    if ngay_tu_06 or ngay_den_06:
                        from datetime import datetime as dt
                        try:
                            if ngay_tu_06:
                                tu_dt = dt.strptime(ngay_tu_06.strip(), "%d/%m/%Y").date()
                                df_06 = df_06[
                                    (df_06["ngay_kiem_tra"] >= str(tu_dt)) |
                                    (df_06["ngay_kiem_tra"].isna())
                                ]
                            if ngay_den_06:
                                den_dt = dt.strptime(ngay_den_06.strip(), "%d/%m/%Y").date()
                                df_06 = df_06[
                                    (df_06["ngay_kiem_tra"] <= str(den_dt)) |
                                    (df_06["ngay_kiem_tra"].isna())
                                ]
                        except ValueError:
                            st.warning("⚠️ Định dạng ngày không hợp lệ (dd/mm/yyyy)")

                if df_06.empty:
                    st.info("ℹ️ Không có dữ liệu kiểm tra phù hợp.")
                else:
                    st.metric("Số bản ghi", fmt_so(len(df_06)) + " bản ghi")

                    cols_06 = [c for c in [
                        "ma_mon_vay", "ten_pgd", "ten_kh", "ten_ct",
                        "du_no_goc", "du_no_goc_khoanh", "du_no_goc_thuc_te",
                        "du_no_khoanh_thuc_te", "chenh_lech",
                        "thuc_trang_du_an", "tinh_hinh_khach_hang",
                        "kha_nang_tra_no", "cam_ket_tra_no",
                        "trang_thai", "ngay_kiem_tra", "can_bo_kiem_tra",
                        "nguoi_nhap", "nguoi_phe_duyet",
                    ] if c in df_06.columns]

                    df_06_display = df_06[cols_06].copy()
                    for col in ["du_no_goc", "du_no_goc_khoanh", "du_no_goc_thuc_te",
                                "du_no_khoanh_thuc_te", "chenh_lech"]:
                        if col in df_06_display.columns:
                            df_06_display[col] = (
                                df_06_display[col]
                                .apply(lambda x: _fmt_dong(float(x)) if x else "0 đồng")
                            )

                    hien_thi_dataframe_phan_trang(
                        df_06_display,
                        key=f"{key_prefix}bc_06_tbl",
                        height=350,
                    )

                    col_06_1, col_06_2 = st.columns(2)
                    with col_06_1:
                        if st.button("📥 Xuất QLNK_06 Excel", key=f"{key_prefix}bc_06_xuat"):
                            st.session_state[f"_{key_prefix}qlnk06_buf"] = xuat_excel(
                                {"QLNK_06": df_06[cols_06]}
                            )
                    with col_06_2:
                        if st.button("📄 Xuất QLNK_06 PDF", key=f"{key_prefix}bc_06_pdf"):
                            try:
                                pgd_pdf_06 = (pgd_f06 if pgd_f06 != "— Tất cả —" else "")
                                pdf_06 = _xuat_pdf_qlnk_06(
                                    df_06.to_dict("records"),
                                    ten_pgd=pgd_pdf_06,
                                    ngay_tu=ngay_tu_06,
                                    ngay_den=ngay_den_06
                                )
                                st.session_state[f"_{key_prefix}qlnk06_pdf"] = pdf_06
                            except Exception as e:
                                st.error(f"❌ Lỗi xuất PDF: {e}")

                    if st.session_state.get(f"_{key_prefix}qlnk06_buf"):
                        st.download_button(
                            "⬇️ Tải QLNK_06 Excel",
                            data=st.session_state[f"_{key_prefix}qlnk06_buf"],
                            file_name="QLNK_06.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            key=f"{key_prefix}bc_06_dl",
                        )
                    if st.session_state.get(f"_{key_prefix}qlnk06_pdf"):
                        st.download_button(
                            "⬇️ Tải QLNK_06 PDF",
                            data=st.session_state[f"_{key_prefix}qlnk06_pdf"],
                            file_name="QLNK_06.pdf",
                            mime="application/pdf",
                            key=f"{key_prefix}bc_06_pdf_dl",
                        )

            with st.expander("📋 M10_QLNK — Danh sách món vay chưa nhập kết quả kiểm tra"):
                rows_m10 = [
                    r for r in rows_all_kt
                    if r.get("trang_thai") == "luu_tam"
                ]
                df_m10 = pd.DataFrame(rows_m10) if rows_m10 else pd.DataFrame()
                st.metric("Số bản ghi lưu tạm", fmt_so(len(df_m10)) + " bản ghi")
                if not df_m10.empty:
                    # Chỉ show các cột quan trọng, format tiền và ngày
                    cols_m10 = [c for c in [
                        "ma_mon_vay", "ten_pgd", "ten_kh", "so_ku",
                        "du_no_goc_khoanh", "ngay_kiem_tra", "nguoi_nhap",
                    ] if c in df_m10.columns]

                    df_m10_display = df_m10[cols_m10].copy()
                    if "du_no_goc_khoanh" in df_m10_display.columns:
                        df_m10_display["du_no_goc_khoanh"] = (
                            df_m10_display["du_no_goc_khoanh"]
                            .apply(lambda x: _fmt_dong(float(x)) if x else "0 đồng")
                        )

                    hien_thi_dataframe_phan_trang(
                        df_m10_display,
                        key=f"{key_prefix}bc_m10_tbl",
                        height=300,
                    )

                    col_ex1, col_ex2 = st.columns(2)
                    with col_ex1:
                        if st.button("📥 Xuất M10 Excel", key=f"{key_prefix}bc_m10_xuat"):
                            st.session_state[f"_{key_prefix}m10_buf"] = xuat_excel(
                                {"M10_LuuTam": df_m10[cols_m10]}
                            )
                    with col_ex2:
                        if st.button("📄 Xuất M10 PDF", key=f"{key_prefix}bc_m10_pdf"):
                            pgd_pdf = pgd_filter_bc or ""
                            try:
                                pdf_m10 = _xuat_pdf_m10(
                                    df_m10.to_dict("records"), ten_pgd=pgd_pdf
                                )
                                st.session_state[f"_{key_prefix}m10_pdf"] = pdf_m10
                            except Exception as e:
                                st.error(f"❌ Lỗi xuất PDF: {e}")

                    if st.session_state.get(f"_{key_prefix}m10_buf"):
                        st.download_button(
                            "⬇️ Tải M10 Excel",
                            data=st.session_state[f"_{key_prefix}m10_buf"],
                            file_name="M10_LuuTam.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            key=f"{key_prefix}bc_m10_dl",
                        )
                    if st.session_state.get(f"_{key_prefix}m10_pdf"):
                        st.download_button(
                            "⬇️ Tải M10 PDF",
                            data=st.session_state[f"_{key_prefix}m10_pdf"],
                            file_name="M10_LuuTam.pdf",
                            mime="application/pdf",
                            key=f"{key_prefix}bc_m10_pdf_dl",
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

        with d_kt:
            # ── Xuất mẫu biểu (lazy-load) ────────────────────────────────
            st.divider()
            show_mb = st.checkbox(
                "📄 Hiện mẫu biểu xuất PDF (bấm để tải)",
                value=False,
                key=f"{key_prefix}show_mb",
                help="Tải mẫu biểu QLNK: Kế hoạch, Phiếu KT, Cam kết, Danh sách HH, Thông báo HH",
            )
            if show_mb:
                st.markdown("### 📄 Xuất mẫu biểu theo CV 368")
    
                pgd_f = pgd_filter_bc
    
                with st.expander("📝 Kế hoạch kiểm tra nợ khoanh", expanded=False):
                    rows_kh_mb = _cached_ke_hoach_kiem_tra(ten_pgd=pgd_f)
                    if not rows_kh_mb:
                        st.info("ℹ️ Chưa có kế hoạch nào. Nhập kế hoạch ở phần trên.")
                    else:
                        options_kh_mb = {
                            f"ID {r['id']} — {r['ten_xa']} — {r['ngay_kiem_tra']} "
                            f"({r['trang_thai']})": r
                            for r in rows_kh_mb
                        }
                        chon_kh_mb = st.selectbox(
                            "Chọn kế hoạch",
                            list(options_kh_mb.keys()),
                            key=f"{key_prefix}mb_kh_sel",
                        )
                        kh_sel = options_kh_mb[chon_kh_mb]
                        ds_mon_kh = kh_sel.get("ds_mon_vay") or []
                        ds_mon_detail = []
                        for ku in ds_mon_kh:
                            rows_hstd_ku = (
                                df_kh[df_kh[COT_SO_KU] == ku]
                                if COT_SO_KU in df_kh.columns else pd.DataFrame()
                            )
                            bs_ku = _cached_bo_sung_mon_vay(str(ku)) or {}
                            if not rows_hstd_ku.empty:
                                r_ku = rows_hstd_ku.iloc[0]
                                ds_mon_detail.append({
                                    "ten_kh":              str(r_ku.get(COT_TEN_KH, "")),
                                    "ten_to_truong":       str(r_ku.get(COT_TEN_TO, "")),
                                    "ten_ct":              str(r_ku.get(COT_TEN_CT, "")),
                                    "ngay_bat_dau_khoanh": bs_ku.get("ngay_bat_dau_khoanh", ""),
                                    "so_thang_khoanh":     bs_ku.get("so_thang_khoanh", ""),
                                    "ly_do_khoanh":        bs_ku.get("ly_do_khoanh", ""),
                                })
                        c_kh1, c_kh2 = st.columns(2)
                        with c_kh1:
                            can_bo_kt_kh = st.text_input(
                                "Cán bộ kiểm tra", username,
                                key=f"{key_prefix}mb_kh_cb",
                            )
                        with c_kh2:
                            noi_dung_kh = st.text_area(
                                "Nội dung bổ sung", max_chars=300,
                                key=f"{key_prefix}mb_kh_nd",
                            )
                        st.caption(
                            f"� {len(ds_mon_detail)} món vay trong kế hoạch "
                            f"tại {kh_sel.get('ten_xa', '')}"
                        )
                        if st.button("📥 Xuất PDF Kế hoạch KT",
                                     key=f"{key_prefix}mb_kh_tao", type="primary"):
                            try:
                                pdf_kh = _xuat_pdf_mau_kh(
                                    kh_sel, ds_mon_detail,
                                    can_bo_kt=can_bo_kt_kh, noi_dung=noi_dung_kh,
                                )
                                st.session_state[f"{key_prefix}mb_kh_pdf"] = pdf_kh
                                st.session_state[f"{key_prefix}mb_kh_fn"] = (
                                    f"QLNK_KH_{kh_sel.get('ten_xa', '')}_"
                                    f"{kh_sel.get('ngay_kiem_tra', '')}.pdf"
                                )
                            except Exception as e_kh:
                                st.error(f"❌ Lỗi tạo PDF: {e_kh}")
                        pdf_kh_data = st.session_state.get(f"{key_prefix}mb_kh_pdf")
                        if pdf_kh_data:
                            st.download_button(
                                "⬇️ Tải PDF",
                                data=pdf_kh_data,
                                file_name=st.session_state.get(f"{key_prefix}mb_kh_fn",
                                                               "QLNK_KH.pdf"),
                                mime="application/pdf",
                                key=f"{key_prefix}mb_kh_dl",
                            )
    
                with st.expander("📝 Mẫu 01/QLNK — Phiếu kiểm tra nợ khoanh", expanded=False):
                    rows_kh_01 = _cached_ke_hoach_kiem_tra(ten_pgd=pgd_f, trang_thai="da_duyet")
                    if not rows_kh_01:
                        st.info("ℹ️ Chưa có kế hoạch đã duyệt.")
                    else:
                        options_kh_01 = {
                            f"ID {r['id']} — {r['ten_xa']} — {r['ngay_kiem_tra']}": r
                            for r in rows_kh_01
                        }
                        chon_kh_01 = st.selectbox(
                            "Chọn kế hoạch",
                            list(options_kh_01.keys()),
                            key=f"{key_prefix}mb_01_sel",
                        )
                        kh_01    = options_kh_01[chon_kh_01]
                        ds_ku_01 = kh_01.get("ds_mon_vay") or []
                        rows_kq_01 = [
                            r for r in _cached_ket_qua_kiem_tra(
                                ten_pgd=pgd_f, trang_thai="da_phe_duyet"
                            )
                            if r.get("ma_mon_vay") in ds_ku_01
                        ]
                        st.info(f"Số món đã có kết quả KT: {len(rows_kq_01)}/{len(ds_ku_01)}")
                        ket_luan_01 = st.text_area(
                            "Kết luận bổ sung", max_chars=500,
                            key=f"{key_prefix}mb_01_kl",
                        )
                        if st.button("� Xuất PDF Mẫu 01/QLNK",
                                     key=f"{key_prefix}mb_01_tao", type="primary"):
                            try:
                                pdf_01 = _xuat_pdf_mau_01qlnk(kh_01, rows_kq_01,
                                                               ket_luan=ket_luan_01)
                                st.session_state[f"{key_prefix}mb_01_pdf"] = pdf_01
                                st.session_state[f"{key_prefix}mb_01_fn"] = (
                                    f"QLNK_01_{kh_01.get('ten_xa', '')}_"
                                    f"{kh_01.get('ngay_kiem_tra', '')}.pdf"
                                )
                            except Exception as e_01:
                                st.error(f"❌ Lỗi tạo PDF: {e_01}")
                        pdf_01_data = st.session_state.get(f"{key_prefix}mb_01_pdf")
                        if pdf_01_data:
                            st.download_button(
                                "⬇️ Tải PDF",
                                data=pdf_01_data,
                                file_name=st.session_state.get(f"{key_prefix}mb_01_fn",
                                                               "QLNK_01.pdf"),
                                mime="application/pdf",
                                key=f"{key_prefix}mb_01_dl",
                            )
    
                with st.expander("📝 Mẫu 02/QLNK — Cam kết trả nợ", expanded=False):
                    rows_co_kn = [
                        r for r in _cached_ket_qua_kiem_tra(
                            ten_pgd=pgd_f, trang_thai="da_phe_duyet"
                        )
                        if r.get("kha_nang_tra_no") == "co"
                    ]
                    if not rows_co_kn:
                        st.info("ℹ️ Chưa có khách hàng nào được xác nhận có khả năng trả nợ.")
                    else:
                        options_02 = {
                            f"{r.get('ten_kh', '')} — {r.get('ma_mon_vay', '')} "
                            f"— {r.get('ngay_kiem_tra', '')}": r
                            for r in rows_co_kn
                        }
                        chon_02 = st.selectbox(
                            "Chọn khách hàng",
                            list(options_02.keys()),
                            key=f"{key_prefix}mb_02_sel",
                        )
                        row_02 = options_02[chon_02]
                        bs_02  = _cached_bo_sung_mon_vay(row_02.get("ma_mon_vay", "")) or {}
                        ku_02  = row_02.get("ma_mon_vay", "")
                        rows_hstd_02 = (
                            df_kh[df_kh[COT_SO_KU] == ku_02].iloc[0].to_dict()
                            if (COT_SO_KU in df_kh.columns
                                and not df_kh[df_kh[COT_SO_KU] == ku_02].empty)
                            else {}
                        )
                        row_02_merged = {**rows_hstd_02, **bs_02, **row_02}
                        c02a, c02b, c02c = st.columns(3)
                        with c02a:
                            tien_ck = st.text_input(
                                "Số tiền cam kết", key=f"{key_prefix}mb_02_tien",
                            )
                        with c02b:
                            han_ck = st.text_input(
                                "Thời hạn", key=f"{key_prefix}mb_02_han",
                            )
                        with c02c:
                            pt_ck = st.selectbox(
                                "Phương thức",
                                ["Trả 1 lần", "Trả góp", "Khác"],
                                key=f"{key_prefix}mb_02_pt",
                            )
                        if st.button("📥 Xuất PDF Mẫu 02/QLNK",
                                     key=f"{key_prefix}mb_02_tao", type="primary"):
                            try:
                                pdf_02 = _xuat_pdf_mau_02qlnk(
                                    row_02_merged,
                                    so_tien_cam_ket=tien_ck,
                                    thoi_han=han_ck,
                                    phuong_thuc=pt_ck,
                                )
                                ngay_str_02 = str(row_02.get("ngay_kiem_tra", "")).replace("/", "")
                                st.session_state[f"{key_prefix}mb_02_pdf"] = pdf_02
                                st.session_state[f"{key_prefix}mb_02_fn"] = (
                                    f"QLNK_02_{row_02.get('ten_kh', '')}_{ngay_str_02}.pdf"
                                )
                            except Exception as e_02:
                                st.error(f"❌ Lỗi tạo PDF: {e_02}")
                        pdf_02_data = st.session_state.get(f"{key_prefix}mb_02_pdf")
                        if pdf_02_data:
                            st.download_button(
                                "⬇️ Tải PDF",
                                data=pdf_02_data,
                                file_name=st.session_state.get(f"{key_prefix}mb_02_fn",
                                                               "QLNK_02.pdf"),
                                mime="application/pdf",
                                key=f"{key_prefix}mb_02_dl",
                            )
    
                with st.expander(
                    "📝 Mẫu 03/QLNK — Danh sách hết thời gian khoanh nợ", expanded=False
                ):
                    if df_kh.empty:
                        st.info("ℹ️ Không có dữ liệu nợ khoanh.")
                    else:
                        col_p03, col_t03 = st.columns(2)
                        with col_p03:
                            ds_pgd_03 = (
                                sorted(df_kh[COT_TEN_PGD].dropna().unique().tolist())
                                if (la_phan_he_cn(role) and COT_TEN_PGD in df_kh.columns)
                                else [pgd_user or ""]
                            )
                            pgd_03 = (
                                st.selectbox("PGD", ds_pgd_03, key=f"{key_prefix}mb_03_pgd")
                                if len(ds_pgd_03) > 1 else ds_pgd_03[0]
                            )
                        with col_t03:
                            df_03 = (
                                df_kh[df_kh[COT_TEN_PGD] == pgd_03]
                                if (COT_TEN_PGD in df_kh.columns and pgd_03)
                                else df_kh
                            )
                            ds_to_03 = (
                                sorted(df_03[COT_TEN_TO].dropna().unique().tolist())
                                if COT_TEN_TO in df_03.columns else []
                            )
                            to_03 = st.selectbox(
                                "Tổ TK&VV",
                                ["— Tất cả —"] + ds_to_03,
                                key=f"{key_prefix}mb_03_to",
                            )
                        if to_03 != "— Tất cả —" and COT_TEN_TO in df_03.columns:
                            df_03 = df_03[df_03[COT_TEN_TO] == to_03]
    
                        # Lọc < 120 ngày trước hết hạn
                        col_nd03, col_ck03 = st.columns([2, 3])
                        with col_nd03:
                            ngay_tinh_03 = st.date_input(
                                "Ngày tính",
                                value=datetime.now().date(),
                                key=f"{key_prefix}mb_03_ngay",
                            )
                        with col_ck03:
                            loc_120 = st.checkbox(
                                "Chỉ lấy món hết hạn trong vòng 120 ngày",
                                value=True,
                                key=f"{key_prefix}mb_03_loc120",
                            )
                        if loc_120 and COT_NGAY_HH_KHOANH in df_03.columns:
                            _ref = pd.Timestamp(ngay_tinh_03)
                            _hh  = pd.to_datetime(df_03[COT_NGAY_HH_KHOANH], dayfirst=True, errors="coerce")
                            df_03 = df_03[(_hh - _ref).dt.days < 120].copy()
    
                        st.info(f"**{len(df_03)} món** trong phạm vi đã chọn.")
    
                        # Thông tin bổ sung cho mẫu
                        c03a, c03b = st.columns(2)
                        with c03a:
                            tu_ngay_03  = st.text_input("Từ ngày", placeholder="dd/mm/yyyy",
                                                        key=f"{key_prefix}mb_03_tu")
                            ma_to_03    = st.text_input("Mã tổ", key=f"{key_prefix}mb_03_ma_to")
                        with c03b:
                            den_ngay_03 = st.text_input("Đến ngày", placeholder="dd/mm/yyyy",
                                                        key=f"{key_prefix}mb_03_den")
                            dvut_03     = st.text_input("Đơn vị ủy thác",
                                                        key=f"{key_prefix}mb_03_dvut")
    
                        if st.button("📄 Xuất PDF Mẫu 03/QLNK",
                                     key=f"{key_prefix}mb_03_tao", type="primary"):
                            try:
                                ten_to_03 = to_03 if to_03 != "— Tất cả —" else ""
                                pdf_03 = _xuat_pdf_mau_03qlnk(
                                    pgd_03 or "", ten_to_03,
                                    df_03.to_dict("records"),
                                    tu_ngay=tu_ngay_03,
                                    den_ngay=den_ngay_03,
                                    ma_to=ma_to_03,
                                    don_vi_uy_thac=dvut_03,
                                )
                                st.session_state[f"{key_prefix}mb_03_pdf"] = pdf_03
                                st.session_state[f"{key_prefix}mb_03_fn"] = (
                                    f"QLNK_03_{pgd_03}_{ten_to_03}.pdf"
                                )
                            except Exception as e_03:
                                st.error(f"❌ Lỗi tạo PDF: {e_03}")
                        pdf_03_data = st.session_state.get(f"{key_prefix}mb_03_pdf")
                        if pdf_03_data:
                            st.download_button(
                                "⬇️ Tải PDF",
                                data=pdf_03_data,
                                file_name=st.session_state.get(f"{key_prefix}mb_03_fn",
                                                               "QLNK_03.pdf"),
                                mime="application/pdf",
                                key=f"{key_prefix}mb_03_dl",
                            )
    
                with st.expander(
                    "📝 Mẫu 04/QLNK — Thông báo hết thời gian khoanh nợ", expanded=False
                ):
                    if df_kh.empty or COT_SO_KU not in df_kh.columns:
                        st.info("ℹ️ Không có dữ liệu nợ khoanh.")
                    else:
                        options_04 = {
                            f"{r.get(COT_TEN_KH, '')} — {r.get(COT_SO_KU, '')}": r.to_dict()
                            for _, r in df_kh.iterrows()
                            if r.get(COT_SO_KU)
                        }
                        chon_04 = st.selectbox(
                            "Chọn khách hàng",
                            list(options_04.keys()),
                            key=f"{key_prefix}mb_04_sel",
                        )
                        row_04_hstd = options_04[chon_04]
                        ku_04 = str(row_04_hstd.get(COT_SO_KU, ""))
                        bs_04 = _cached_bo_sung_mon_vay(ku_04) or {}
                        ten_pgd_04 = (
                            str(row_04_hstd.get(COT_TEN_PGD, pgd_user or ""))
                            if COT_TEN_PGD in row_04_hstd else (pgd_user or "")
                        )
                        noi_dung_04 = st.text_area(
                            "Nội dung thông báo bổ sung", max_chars=500,
                            key=f"{key_prefix}mb_04_nd",
                        )
                        han_cuoi_04 = st.text_input(
                            "Hạn cuối trả nợ",
                            key=f"{key_prefix}mb_04_hc",
                        )
                        if st.button("� Xuất PDF Mẫu 04/QLNK",
                                     key=f"{key_prefix}mb_04_tao", type="primary"):
                            try:
                                pdf_04 = _xuat_pdf_mau_04qlnk(
                                    row_04_hstd, bs_04, ten_pgd_04,
                                    noi_dung=noi_dung_04, han_cuoi=han_cuoi_04,
                                )
                                st.session_state[f"{key_prefix}mb_04_pdf"] = pdf_04
                                st.session_state[f"{key_prefix}mb_04_fn"] = (
                                    f"QLNK_04_{row_04_hstd.get(COT_TEN_KH, '')}_{ku_04}.pdf"
                                )
                            except Exception as e_04:
                                st.error(f"❌ Lỗi tạo PDF: {e_04}")
                        pdf_04_data = st.session_state.get(f"{key_prefix}mb_04_pdf")
                        if pdf_04_data:
                            st.download_button(
                                "⬇️ Tải PDF",
                                data=pdf_04_data,
                                file_name=st.session_state.get(f"{key_prefix}mb_04_fn",
                                                               "QLNK_04.pdf"),
                                mime="application/pdf",
                                key=f"{key_prefix}mb_04_dl",
                            )
