"""
alert_center.py
Tổng hợp và hiển thị cảnh báo tự động trong sidebar.
Mỗi lần gọi render_alert_sidebar() sẽ đọc dữ liệu thực
từ kv_store + parquet, không cache để luôn mới nhất.
"""
from __future__ import annotations
from datetime import datetime, timedelta
from pathlib import Path
import streamlit as st
import db
from config import CACHE_GQVL

NGUONG_NGAY_UPLOAD_CU = 3   # cảnh báo nếu file chưa merge quá 3 ngày


def _kiem_tra_upload_tre() -> list[str]:
    """Trả về danh sách loại file chưa được merge trong NGUONG_NGAY_UPLOAD_CU ngày.
    Cache vào st.session_state["merge_meta_cache"], invalidate sau 60 giây."""
    now = datetime.now()
    cache = st.session_state.get("merge_meta_cache")
    if cache and (now - cache["timestamp"]).total_seconds() < 60:
        return cache["data"]

    canh_bao = []
    for loai in ["hstd", "nq11", "gqvl"]:
        meta = db.doc_kv(f"merge_meta_{loai}")
        if not meta:
            canh_bao.append(f"Chưa có dữ liệu **{loai.upper()}**")
            continue
        try:
            thoi_gian = datetime.fromisoformat(meta["thoi_gian"])
            delta = (now - thoi_gian).days
            if delta >= NGUONG_NGAY_UPLOAD_CU:
                canh_bao.append(
                    f"**{loai.upper()}** chưa cập nhật ({delta} ngày trước)"
                )
        except Exception:
            pass

    st.session_state["merge_meta_cache"] = {"data": canh_bao, "timestamp": now}
    return canh_bao


_KHD_CACHE_TTL = 300  # 5 phút


def _kiem_tra_khong_hoat_dong(df_full, pgd_filter: str | None = None) -> list[str]:
    """
    Trả về danh sách cảnh báo hộ 3 tháng không hoạt động.
    Kết quả cache 5 phút trong session_state — tránh tính lại toàn bộ HSTD mỗi rerun.
    """
    if df_full is None or df_full.empty:
        return []

    cache_key = f"_alert_khd_{pgd_filter or 'all'}"
    now = datetime.now()
    cached = st.session_state.get(cache_key)
    if cached and (now - cached["ts"]).total_seconds() < _KHD_CACHE_TTL:
        return cached["data"]

    try:
        from hstd import tong_hop_khong_hd
        from config import COT_TEN_PGD
        df_loc = df_full
        if pgd_filter and COT_TEN_PGD in df_full.columns:
            df_loc = df_full[df_full[COT_TEN_PGD] == pgd_filter]
        tong_hop = tong_hop_khong_hd(df_loc, nhom_theo=COT_TEN_PGD)
        if tong_hop.empty:
            result: list[str] = []
        else:
            tong_mon = int(tong_hop["Món_3m_KHĐ"].sum())
            result = [f"**{tong_mon} món vay** ≥ 3 tháng không hoạt động"] if tong_mon > 0 else []
    except Exception:
        result = []

    st.session_state[cache_key] = {"data": result, "ts": now}
    return result


def canh_bao_no_khoanh_sap_het_han(df_kh: pd.DataFrame) -> dict:
    """Tính số món sắp hết hạn khoanh.

    df_kh: DataFrame đã lọc những món có Dư nợ khoanh > 0.
    """
    import pandas as pd
    from datetime import date

    if df_kh is None or df_kh.empty or 'Ngày hết hạn Khoanh' not in df_kh.columns:
        return {'so_khan': 0, 'so_canh_bao': 0, 'chi_tiet_khan': [], 'chi_tiet_canh_bao': []}

    df = df_kh.copy()
    df['_ngay_het'] = pd.to_datetime(
        df['Ngày hết hạn Khoanh'], errors='coerce', dayfirst=True,
    )
    df = df.dropna(subset=['_ngay_het'])

    today = pd.Timestamp(date.today())
    df['con_lai'] = (df['_ngay_het'] - today).dt.days

    khan = df[df['con_lai'] <= 30]
    canh_bao = df[(df['con_lai'] > 30) & (df['con_lai'] <= 180)]

    cols = ['Số khế ước', 'Tên PGD', 'Tên xã', 'Tên KH', 'Ngày hết hạn Khoanh', 'con_lai']
    cols = [c for c in cols if c in df.columns]

    return {
        'so_khan': len(khan),
        'so_canh_bao': len(canh_bao),
        'chi_tiet_khan': khan[cols].to_dict('records') if not khan.empty else [],
        'chi_tiet_canh_bao': canh_bao[cols].to_dict('records') if not canh_bao.empty else [],
    }


def render_badge_no_khoanh_sap_het_han(df_full) -> None:
    """Hiển thị badge cảnh báo nợ khoanh sắp hết hạn trên sidebar."""
    import pandas as pd

    if df_full is None or df_full.empty:
        return
    if 'Dư nợ khoanh' not in df_full.columns:
        return

    du_kh = pd.to_numeric(df_full['Dư nợ khoanh'], errors='coerce').fillna(0)
    df_kh = df_full[du_kh > 0]

    data = canh_bao_no_khoanh_sap_het_han(df_kh)

    if data['so_khan'] > 0:
        if st.sidebar.button(
            f"🔴 {data['so_khan']} món hết hạn khoanh",
            key="alert_khoanh_khan",
        ):
            st.session_state.ws_mgmt_jump = "🔒 Nợ khoanh"
            st.session_state._qlnk_filter = "sap_het_han"
            st.rerun()

    if data['so_canh_bao'] > 0:
        if st.sidebar.button(
            f"🟠 {data['so_canh_bao']} món sắp hết hạn khoanh",
            key="alert_khoanh_canh_bao",
        ):
            st.session_state.ws_mgmt_jump = "🔒 Nợ khoanh"
            st.session_state._qlnk_filter = "sap_het_han"
            st.rerun()


_KHOANH_ALERT_CACHE_TTL = 600


def _get_khoanh_alert_data(df_full):
    cache_key = "_alert_khoanh_cache"
    now = datetime.now()
    cached = st.session_state.get(cache_key)
    if cached and (now - cached["ts"]).total_seconds() < _KHOANH_ALERT_CACHE_TTL:
        return cached["data"]
    import pandas as pd
    if df_full is None or df_full.empty or 'Dư nợ khoanh' not in df_full.columns:
        return {'so_khan': 0, 'so_canh_bao': 0, 'chi_tiet_khan': [], 'chi_tiet_canh_bao': []}
    du_kh = pd.to_numeric(df_full['Dư nợ khoanh'], errors='coerce').fillna(0)
    df_kh = df_full[du_kh > 0]
    data = canh_bao_no_khoanh_sap_het_han(df_kh)
    st.session_state[cache_key] = {"data": data, "ts": now}
    return data


def render_alert_sidebar(
    df_full=None,
    role: str = "user",
    pgd_user: str | None = None,
) -> None:
    """
    Hiển thị cảnh báo trong sidebar.
    Gọi sau render_status_compact() trong app.py.

    Chỉ hiển thị nếu có ít nhất 1 cảnh báo.
    """
    canh_bao: list[str] = []

    # Cảnh báo upload trễ — chỉ admin/manager mới thấy
    from auth import is_cn_role, is_pgd_role
    if is_cn_role(role) or role in ["admin", "manager"]:
        canh_bao += _kiem_tra_upload_tre()

    # Cảnh báo 3 tháng không hoạt động
    pgd_filter = pgd_user if is_pgd_role(role) else None
    canh_bao += _kiem_tra_khong_hoat_dong(df_full, pgd_filter)

    # Cảnh báo nợ khoanh sắp hết hạn
    khoanh_data = _get_khoanh_alert_data(df_full)
    co_khoanh = khoanh_data['so_khan'] > 0 or khoanh_data['so_canh_bao'] > 0

    if not canh_bao and not co_khoanh:
        return

    st.divider()
    st.markdown("🔔 **Cảnh báo**")
    for msg in canh_bao:
        st.warning(msg, icon="⚠️")

    if co_khoanh:
        if khoanh_data['so_khan'] > 0:
            if st.button(
                f"🔴 {khoanh_data['so_khan']} món hết hạn khoanh",
                key="alert_khoanh_khan",
            ):
                st.session_state.ws_mgmt_jump = "🔒 Nợ khoanh"
                st.session_state._qlnk_filter = "sap_het_han"
                st.rerun()

        if khoanh_data['so_canh_bao'] > 0:
            if st.button(
                f"🟠 {khoanh_data['so_canh_bao']} món sắp hết hạn khoanh",
                key="alert_khoanh_canh_bao",
            ):
                st.session_state.ws_mgmt_jump = "🔒 Nợ khoanh"
                st.session_state._qlnk_filter = "sap_het_han"
                st.rerun()
