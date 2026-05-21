"""Phân tích Nợ khoanh — danh mục khoản vay đang trong giai đoạn khoanh nợ QĐ 62.

Port từ VSPPRO Khoanh.tsx.
KPI cards + breakdown theo Chương trình / Xã / ĐVUT + danh sách chi tiết.
"""


from __future__ import annotations

from logger import get_logger
logger = get_logger(__name__)

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
from services.no_khoanh_service import (
    loc_khoanh as _loc_khoanh,
    bang_theo_nhom as _bang_theo_nhom,
)
import db
from datetime import datetime
_fmt_dong = lambda x: fmt_so(float(x)) + " đồng" if x not in (None, "", float("nan")) else "0 đồng"


# ─── Cached DB wrappers (TTL 60s) ────────────────────────────────────────────

@st.cache_data(ttl=60, show_spinner=False)
def _cached_ket_qua_kiem_tra(ten_pgd, trang_thai=None):
    return db.doc_ket_qua_kiem_tra(ten_pgd=ten_pgd, trang_thai=trang_thai)

@st.cache_data(ttl=60, show_spinner=False)
def _cached_mau_bieu_cv368(ten_pgd=None, loai_mau=None, nam=None):
    return db.doc_mau_bieu_cv368(ten_pgd=ten_pgd, loai_mau=loai_mau, nam=nam)

@st.cache_data(ttl=30, show_spinner=False)
def _cached_bo_sung_mon_vay(ma_mon_vay):
    return db.doc_bo_sung_mon_vay(ma_mon_vay)


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


from services.pdf_no_khoanh_service import (

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
                    logger.error("Lỗi trong khối except: %s", _e, exc_info=True)
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
                logger.error("Lỗi trong khối except: %s", e, exc_info=True)
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
                    logger.error("Lỗi trong khối except: %s", _e, exc_info=True)
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
                    logger.error("Lỗi trong khối except: %s", _e, exc_info=True)
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
                    logger.error("Lỗi trong khối except: %s", _e, exc_info=True)
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
                    logger.error("Lỗi trong khối except: %s", _e, exc_info=True)
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
                    logger.error("Lỗi trong khối except: %s", _e, exc_info=True)
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
    _df_full = kwargs.get("df_full")
    df_full  = df if _df_full is None else _df_full
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
            _render_cv368_kt(
                df_kh=df_kh,
                role=role,
                pgd_user=pgd_user,
                username=username,
                key_prefix=key_prefix,
            )

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
                                logger.error("Lỗi trong khối except: %s", e, exc_info=True)
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
                                logger.error("Lỗi trong khối except: %s", e, exc_info=True)
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
