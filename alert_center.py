"""
alert_center.py
Tổng hợp và hiển thị cảnh báo tự động trong sidebar.
Mỗi lần gọi render_alert_sidebar() sẽ đọc dữ liệu thực
từ kv_store + parquet, không cache để luôn mới nhất.

Phân mức cảnh báo:
  🔴 KHAN      — cần xử lý ngay (nợ khoanh sắp hết hạn ≤30 ngày, data trễ nặng)
  🟠 CANH_BAO  — cần theo dõi (sắp hết hạn ≤180 ngày, 3 tháng KHĐ, upload trễ)
  🟡 LUU_Y     — thông tin cần lưu ý (nhắc nhở, thống kê)
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal
import hashlib
import streamlit as st
import db
from logger import get_logger

logger = get_logger(__name__)
from config import (
    CACHE_GQVL,
    COT_DU_NO_KHOANH,
    COT_DU_NO_QH,
    COT_NGAY_DH,
    COT_NGAY_HH_KHOANH,
    COT_SO_KU,
    COT_TEN_KH,
    COT_TEN_PGD,
    COT_TEN_TO_TRUONG,
    COT_TEN_XA,
    COT_TONG_DU_NO,
)


# ═══════════════════════════════════════════════════════════════════════════════
# AlertItem — đơn vị cảnh báo có phân mức
# ═══════════════════════════════════════════════════════════════════════════════

MUC_KHAN     = "khan"       # 🔴
MUC_CANH_BAO = "canh_bao"  # 🟠
MUC_LUU_Y    = "luu_y"     # 🟡

_MUC_ICON  = {MUC_KHAN: "🔴", MUC_CANH_BAO: "🟠", MUC_LUU_Y: "🟡"}
_MUC_LABEL = {MUC_KHAN: "KHẨN", MUC_CANH_BAO: "CẢNH BÁO", MUC_LUU_Y: "LƯU Ý"}
_MUC_ORDER = {MUC_KHAN: 0, MUC_CANH_BAO: 1, MUC_LUU_Y: 2}


@dataclass
class AlertItem:
    muc: Literal["khan", "canh_bao", "luu_y"]
    tieu_de: str
    mo_ta: str = ""
    jump_fn: object = field(default=None, repr=False)  # callable hoặc None

    @property
    def alert_id(self) -> str:
        """Hash ổn định từ (muc, tieu_de) — dùng làm key đã-đọc."""
        raw = f"{self.muc}|{self.tieu_de}"
        return hashlib.md5(raw.encode()).hexdigest()[:12]

    @property
    def icon(self) -> str:
        return _MUC_ICON.get(self.muc, "⚪")

    @property
    def label_muc(self) -> str:
        return _MUC_LABEL.get(self.muc, self.muc.upper())


# ═══════════════════════════════════════════════════════════════════════════════
# Đã đọc — lưu vào kv_store
# ═══════════════════════════════════════════════════════════════════════════════

_KV_READ_KEY = "alert_read_ids"
_ALERT_DA_DOC_SS_KEY = "_alert_da_doc_ss"  # session_state key cho in-memory cache
_ALERT_DA_DOC_TTL = 60  # giây — reload từ DB mỗi 60s


def _lay_da_doc() -> set[str]:
    """Đọc tập hợp alert_id đã đọc — cache 60s trong session_state để tránh DB read mỗi rerun."""
    now = datetime.now()
    cached = st.session_state.get(_ALERT_DA_DOC_SS_KEY)
    if cached and (now - cached["ts"]).total_seconds() < _ALERT_DA_DOC_TTL:
        return set(cached["ids"])
    try:
        data = db.doc_kv(_KV_READ_KEY, {})
        ids = set(data.get("ids", []))
    except Exception as e:
        logger.error(f"Lỗi đọc danh sách đã đọc: {e}", exc_info=True)
        ids = set()
    st.session_state[_ALERT_DA_DOC_SS_KEY] = {"ids": ids, "ts": now}
    return set(ids)


def _luu_da_doc(ids: set[str]) -> None:
    """Lưu tập hợp alert_id đã đọc vào kv_store và cập nhật session cache."""
    try:
        username = st.session_state.get("username", "system")
        db.ghi_kv(_KV_READ_KEY, {"ids": list(ids)}, username=username)
        db.ghi_audit(username, "alert_danh_dau_da_doc", f"Đã đọc {len(ids)} cảnh báo")
        # Cập nhật session cache ngay sau khi ghi để rerun tiếp theo không cần đọc lại DB
        st.session_state[_ALERT_DA_DOC_SS_KEY] = {"ids": set(ids), "ts": datetime.now()}
    except Exception as e:
        logger.error(f"Lỗi lưu danh sách đã đọc: {e}", exc_info=True)


def _danh_dau_da_doc(alert_ids: list[str]) -> None:
    """Thêm các alert_id vào danh sách đã đọc."""
    da_doc = _lay_da_doc()
    da_doc.update(alert_ids)
    _luu_da_doc(da_doc)


def _xoa_da_doc_cu(active_ids: set[str]) -> None:
    """Xóa các alert_id không còn active — chỉ ghi DB khi set thực sự bị thu nhỏ."""
    try:
        da_doc = _lay_da_doc()
        pruned = da_doc & active_ids
        if pruned != da_doc:  # Chỉ tốn I/O khi có id cũ cần xóa
            _luu_da_doc(pruned)
    except Exception as e:
        logger.error(f"Lỗi xóa đã đọc cũ: {e}", exc_info=True)


# ═══════════════════════════════════════════════════════════════════════════════
# Nguồn cảnh báo
# ═══════════════════════════════════════════════════════════════════════════════

NGUONG_NGAY_UPLOAD_CU = 3   # cảnh báo nếu file chưa merge quá 3 ngày
_NGUONG_UPLOAD_KHAN   = 7   # 🔴 nếu trễ ≥ 7 ngày

_NGUONG_NQH_KHAN    = 3.0   # NQH% > 3% → 🔴
_NGUONG_NQH_CANH_BAO = 1.0  # NQH% > 1% → 🟠

_NGUONG_DH_30_KHAN    = 50   # ≥ 50 món đến hạn trong 30 ngày → 🔴
_NGUONG_DH_30_TY_KHAN = 5.0  # hoặc tổng ≥ 5 tỷ → 🔴

_KHD_CACHE_TTL = 1800  # 30 phút


def _kiem_tra_upload_tre() -> list[AlertItem]:
    """Trả về list AlertItem cho file chưa được merge đúng hạn.
    Cache vào st.session_state["merge_meta_cache"], invalidate sau 60 giây."""
    now = datetime.now()
    cache = st.session_state.get("merge_meta_cache")
    if cache and (now - cache["timestamp"]).total_seconds() < 60:
        return cache["data"]

    items: list[AlertItem] = []
    for loai in ["hstd", "nq11", "gqvl"]:
        meta = db.doc_kv(f"merge_meta_{loai}")
        if not meta:
            items.append(AlertItem(
                muc=MUC_KHAN,
                tieu_de=f"Chưa có dữ liệu {loai.upper()}",
                mo_ta="Chưa từng merge — cần upload ngay",
            ))
            continue
        try:
            thoi_gian = datetime.fromisoformat(meta["thoi_gian"])
            delta = (now - thoi_gian).days
            if delta >= _NGUONG_UPLOAD_KHAN:
                items.append(AlertItem(
                    muc=MUC_KHAN,
                    tieu_de=f"{loai.upper()} chưa cập nhật {delta} ngày",
                    mo_ta=f"Lần cuối: {thoi_gian.strftime('%d/%m/%Y %H:%M')}",
                ))
            elif delta >= NGUONG_NGAY_UPLOAD_CU:
                items.append(AlertItem(
                    muc=MUC_CANH_BAO,
                    tieu_de=f"{loai.upper()} cần cập nhật ({delta} ngày)",
                    mo_ta=f"Lần cuối: {thoi_gian.strftime('%d/%m/%Y %H:%M')}",
                ))
        except Exception as e:
            logger.error(f"Lỗi kiểm tra upload trễ {loai}: {e}", exc_info=True)

    st.session_state["merge_meta_cache"] = {"data": items, "timestamp": now}
    return items


def _kiem_tra_khong_hoat_dong(df_full, pgd_filter: str | None = None) -> list[AlertItem]:
    """
    Trả về list AlertItem cho hộ 3 tháng không hoạt động.
    Kết quả cache 5 phút trong session_state.
    """
    if df_full is None or df_full.empty:
        return []

    cache_key = f"_alert_khd_{pgd_filter or 'all'}"
    now = datetime.now()
    cached = st.session_state.get(cache_key)
    if cached and (now - cached["ts"]).total_seconds() < _KHD_CACHE_TTL:
        return cached["data"]

    try:
        import os
        from data.hstd import tong_hop_khong_hd_cached
        from config import COT_TEN_PGD as _COT_TEN_PGD, CACHE_HSTD
        _ts = os.path.getmtime(CACHE_HSTD) if os.path.exists(CACHE_HSTD) else 0.0
        # Cache toàn CN, filter sau — tránh tạo nhiều bản cache theo PGD
        tong_hop = tong_hop_khong_hd_cached(df_full, nhom_theo=_COT_TEN_PGD, ts=_ts)
        if pgd_filter and _COT_TEN_PGD in tong_hop.columns:
            tong_hop = tong_hop[tong_hop[_COT_TEN_PGD] == pgd_filter]
        if tong_hop.empty:
            result: list[AlertItem] = []
        else:
            tong_mon = int(tong_hop["Món_3m_KHĐ"].sum())
            result = [
                AlertItem(
                    muc=MUC_CANH_BAO,
                    tieu_de=f"{tong_mon} món vay ≥ 3 tháng không hoạt động",
                    mo_ta="Kiểm tra tab Cảnh báo tín dụng → 3 tháng KHĐ",
                )
            ] if tong_mon > 0 else []
    except Exception as e:
        logger.error(f"Lỗi kiểm tra không hoạt động: {e}", exc_info=True)
        result = []

    st.session_state[cache_key] = {"data": result, "ts": now}
    return result


def canh_bao_no_khoanh_sap_het_han(df_kh) -> dict:
    """Tính số món sắp hết hạn khoanh.

    df_kh: DataFrame đã lọc những món có Dư nợ khoanh > 0.
    """
    import pandas as pd
    from datetime import date

    if df_kh is None or df_kh.empty or COT_NGAY_HH_KHOANH not in df_kh.columns:
        return {'so_khan': 0, 'so_canh_bao': 0, 'chi_tiet_khan': [], 'chi_tiet_canh_bao': []}

    df = df_kh.copy()
    df['_ngay_het'] = pd.to_datetime(
        df[COT_NGAY_HH_KHOANH], errors='coerce', dayfirst=True, format='mixed',
    )
    df = df.dropna(subset=['_ngay_het'])

    today = pd.Timestamp(date.today())
    df['con_lai'] = (df['_ngay_het'] - today).dt.days

    khan = df[df['con_lai'] <= 30]
    canh_bao = df[(df['con_lai'] > 30) & (df['con_lai'] <= 180)]

    cols = [COT_SO_KU, COT_TEN_PGD, COT_TEN_XA, COT_TEN_KH,
            COT_DU_NO_KHOANH, COT_NGAY_HH_KHOANH, COT_TEN_TO_TRUONG, 'con_lai']
    cols = [c for c in cols if c in df.columns]

    return {
        'so_khan': len(khan),
        'so_canh_bao': len(canh_bao),
        'chi_tiet_khan': khan[cols].to_dict('records') if not khan.empty else [],
        'chi_tiet_canh_bao': canh_bao[cols].to_dict('records') if not canh_bao.empty else [],
    }



def _jump_to_khoanh():
    """Set session state để nhảy đến tab Nợ khoanh phù hợp workspace hiện tại."""
    from state_manager import SCMStateManager

    st.session_state._qlnk_filter = "sap_het_han"
    ws = st.session_state.get("workspace", "operation")
    state = SCMStateManager()
    if ws == "management":
        state.nav_ws_mgmt_jump = "🔒 Quản lý Nợ Khoanh theo CV 368"
    elif ws == "executive":
        st.session_state.ws_exec_jump = "📊 Tổng hợp nợ khoanh"
    else:
        state.nav_ws_op_nhom = "kiem_soat_rr"
        state.nav_ws_op_jump_tab = 7


def _kiem_tra_nqh_cao(df_full, pgd_filter: str | None = None) -> list[AlertItem]:
    """Cảnh báo nếu tỷ lệ NQH vượt ngưỡng. Cache 30 phút."""
    import pandas as pd

    if df_full is None or df_full.empty:
        return []
    if COT_DU_NO_QH not in df_full.columns or COT_TONG_DU_NO not in df_full.columns:
        return []

    cache_key = f"_alert_nqh_{pgd_filter or 'all'}"
    now = datetime.now()
    cached = st.session_state.get(cache_key)
    if cached and (now - cached["ts"]).total_seconds() < _KHD_CACHE_TTL:
        return cached["data"]

    try:
        if COT_TEN_PGD in df_full.columns and pgd_filter:
            df = df_full[df_full[COT_TEN_PGD] == pgd_filter]
        else:
            df = df_full

        tong_dn = pd.to_numeric(df[COT_TONG_DU_NO], errors="coerce").fillna(0).sum()
        if tong_dn <= 0:
            result: list[AlertItem] = []
        else:
            tong_nqh = pd.to_numeric(df[COT_DU_NO_QH], errors="coerce").fillna(0).sum()
            ty_le = tong_nqh / tong_dn * 100
            scope = pgd_filter or "toàn Chi nhánh"
            ty_le_str = f"{ty_le:.2f}".replace(".", ",") + "%"
            if ty_le >= _NGUONG_NQH_KHAN:
                result = [AlertItem(
                    muc=MUC_KHAN,
                    tieu_de=f"NQH {scope} cao: {ty_le_str}",
                    mo_ta="Vượt ngưỡng 3% — cần xử lý ngay, tab Cảnh báo NQH",
                )]
            elif ty_le >= _NGUONG_NQH_CANH_BAO:
                result = [AlertItem(
                    muc=MUC_CANH_BAO,
                    tieu_de=f"NQH {scope}: {ty_le_str}",
                    mo_ta="Theo dõi chặt — tab Cảnh báo NQH",
                )]
            else:
                result = []
    except Exception as e:
        logger.error("_kiem_tra_nqh_cao: %s", e, exc_info=True)
        result = []

    st.session_state[cache_key] = {"data": result, "ts": now}
    return result


def _kiem_tra_no_den_han(df_full, pgd_filter: str | None = None) -> list[AlertItem]:
    """Cảnh báo nếu có nhiều món đến hạn trong 30 ngày tới. Cache 30 phút."""
    import pandas as pd

    if df_full is None or df_full.empty or COT_NGAY_DH not in df_full.columns:
        return []

    cache_key = f"_alert_den_han_{pgd_filter or 'all'}"
    now = datetime.now()
    cached = st.session_state.get(cache_key)
    if cached and (now - cached["ts"]).total_seconds() < _KHD_CACHE_TTL:
        return cached["data"]

    try:
        df = df_full.copy()
        if pgd_filter and COT_TEN_PGD in df.columns:
            df = df[df[COT_TEN_PGD] == pgd_filter]

        df["_ngay_dh"] = pd.to_datetime(df[COT_NGAY_DH], errors="coerce", dayfirst=True)
        today = pd.Timestamp("today").normalize()
        den_han = df[(df["_ngay_dh"] >= today) & (df["_ngay_dh"] <= today + pd.Timedelta(days=30))]

        if den_han.empty:
            result = []
        else:
            so_mon = len(den_han)
            tong_ty = pd.to_numeric(den_han[COT_TONG_DU_NO], errors="coerce").fillna(0).sum() / 1e9
            tong_str = f"{tong_ty:.1f}".replace(".", ",") + " tỷ"
            if so_mon >= _NGUONG_DH_30_KHAN or tong_ty >= _NGUONG_DH_30_TY_KHAN:
                muc = MUC_KHAN
            else:
                muc = MUC_CANH_BAO
            result = [AlertItem(
                muc=muc,
                tieu_de=f"{so_mon} món đến hạn trong 30 ngày",
                mo_ta=f"Tổng: {tong_str} — xem tab Phân tích Đến hạn",
            )]
    except Exception as e:
        logger.error("_kiem_tra_no_den_han: %s", e, exc_info=True)
        result = []

    st.session_state[cache_key] = {"data": result, "ts": now}
    return result


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


# ═══════════════════════════════════════════════════════════════════════════════
# Công văn quá hạn xử lý
# ═══════════════════════════════════════════════════════════════════════════════

def _kiem_tra_cong_van_den_han() -> list[AlertItem]:
    """Cảnh báo công văn chưa xử lý quá 7/14 ngày kể từ ngày nhận."""
    try:
        from services.cong_van_service import ds_cv_sap_den_han
        from datetime import date, timedelta

        ngay_hom_nay = date.today()
        cv_khan = ds_cv_sap_den_han((ngay_hom_nay - timedelta(days=14)).isoformat())
        cv_tat_ca = ds_cv_sap_den_han((ngay_hom_nay - timedelta(days=7)).isoformat())
        ids_khan = {cv["id"] for cv in cv_khan}
        cv_canh_bao = [cv for cv in cv_tat_ca if cv["id"] not in ids_khan]
    except Exception:
        return []

    items: list[AlertItem] = []
    if cv_khan:
        items.append(AlertItem(
            muc=MUC_KHAN,
            tieu_de=f"{len(cv_khan)} công văn quá hạn xử lý (>14 ngày)",
            mo_ta="Cần xử lý ngay — tab Quản lý Công văn",
        ))
    if cv_canh_bao:
        items.append(AlertItem(
            muc=MUC_CANH_BAO,
            tieu_de=f"{len(cv_canh_bao)} công văn chưa xử lý (7–14 ngày)",
            mo_ta="Kiểm tra và xử lý — tab Quản lý Công văn",
        ))
    return items


# ═══════════════════════════════════════════════════════════════════════════════
# Health check tự động
# ═══════════════════════════════════════════════════════════════════════════════

_HC_STALE_HOURS = 25  # Cảnh báo nếu health check chưa chạy trong 25h

def _kiem_tra_health_check() -> list[AlertItem]:
    """Đọc kết quả health check tự động từ kv_store, trả về alerts nếu có lỗi."""
    items: list[AlertItem] = []
    try:
        result = db.doc_kv("health_check_result")
        if result is None:
            items.append(AlertItem(
                muc=MUC_LUU_Y,
                tieu_de="Health check chưa chạy lần nào",
                mo_ta="Chạy: python health_check.py — hoặc đặt lịch tự động 6:30 sáng",
            ))
            return items

        ts_str  = result.get("ts", "")
        failed  = result.get("failed", 0)
        labels  = result.get("failed_labels", [])
        total   = result.get("total", 0)

        # Cảnh báo nếu lần chạy cuối đã quá _HC_STALE_HOURS
        if ts_str:
            try:
                ts = datetime.fromisoformat(ts_str)
                age_h = (datetime.now() - ts).total_seconds() / 3600
                if age_h > _HC_STALE_HOURS:
                    items.append(AlertItem(
                        muc=MUC_LUU_Y,
                        tieu_de=f"Health check chưa chạy {int(age_h)}h",
                        mo_ta="Kiểm tra Task Scheduler hoặc chạy thủ công: python health_check.py",
                    ))
            except ValueError:
                pass

        if failed == 0:
            return items  # Tất cả OK — không hiện gì

        # Có lỗi — hiện cảnh báo
        ts_disp = ts_str[:16].replace("T", " ") if ts_str else "?"
        mo_ta   = f"Lần kiểm tra: {ts_disp} | {failed}/{total} checks lỗi"
        if labels:
            mo_ta += " — " + "; ".join(labels[:3])
            if len(labels) > 3:
                mo_ta += f" (+{len(labels) - 3} mục khác)"

        muc = MUC_KHAN if failed >= 3 else MUC_CANH_BAO
        items.append(AlertItem(
            muc=muc,
            tieu_de=f"⚙ Hệ thống: {failed} vấn đề cần kiểm tra",
            mo_ta=mo_ta,
        ))
    except Exception as e:
        logger.error("_kiem_tra_health_check: %s", e, exc_info=True)
    return items


# ═══════════════════════════════════════════════════════════════════════════════
# Build danh sách alert tổng hợp
# ═══════════════════════════════════════════════════════════════════════════════

def _build_alert_items(
    df_full,
    role: str,
    pgd_user: str | None,
) -> list[AlertItem]:
    """Thu thập toàn bộ cảnh báo thành list[AlertItem], sắp xếp theo mức."""
    from auth import la_phan_he_cn, la_phan_he_pgd

    items: list[AlertItem] = []

    # Upload trễ — chỉ CN thấy
    if la_phan_he_cn(role):
        items += _kiem_tra_upload_tre()

    # 3 tháng không hoạt động
    pgd_filter = pgd_user if la_phan_he_pgd(role) else None
    items += _kiem_tra_khong_hoat_dong(df_full, pgd_filter)

    # NQH cao
    items += _kiem_tra_nqh_cao(df_full, pgd_filter)

    # Nợ đến hạn trong 30 ngày
    items += _kiem_tra_no_den_han(df_full, pgd_filter)

    # Công văn quá hạn xử lý — chỉ CN thấy
    if la_phan_he_cn(role):
        items += _kiem_tra_cong_van_den_han()

    # Health check tự động (kết quả lần chạy gần nhất)
    if la_phan_he_cn(role):
        items += _kiem_tra_health_check()

    # Nợ khoanh sắp hết hạn
    khoanh_data = _get_khoanh_alert_data(df_full)
    if khoanh_data["so_khan"] > 0:
        items.append(AlertItem(
            muc=MUC_KHAN,
            tieu_de=f"{khoanh_data['so_khan']} món nợ khoanh hết hạn (≤30 ngày)",
            mo_ta="Cần kiểm tra ngay — tab Nợ Khoanh",
            jump_fn=_jump_to_khoanh,
        ))
    if khoanh_data["so_canh_bao"] > 0:
        items.append(AlertItem(
            muc=MUC_CANH_BAO,
            tieu_de=f"{khoanh_data['so_canh_bao']} món sắp hết hạn khoanh (≤180 ngày)",
            mo_ta="Xem chi tiết — tab Nợ Khoanh",
            jump_fn=_jump_to_khoanh,
        ))

    # Sắp xếp: 🔴 → 🟠 → 🟡
    items.sort(key=lambda a: _MUC_ORDER.get(a.muc, 99))
    return items


# ═══════════════════════════════════════════════════════════════════════════════
# Render sidebar
# ═══════════════════════════════════════════════════════════════════════════════

def render_alert_sidebar(
    df_full=None,
    role: str = "user",
    pgd_user: str | None = None,
) -> None:
    """
    Hiển thị cảnh báo phân mức trong sidebar.
    Gọi sau render_status_compact() trong app.py.

    - Badge tổng số cảnh báo chưa đọc
    - Phân nhóm 🔴/🟠/🟡
    - Button "Đánh dấu đã đọc tất cả"
    - Trạng thái đã đọc lưu vào kv_store
    """
    all_items = _build_alert_items(df_full, role, pgd_user)
    if not all_items:
        return

    # Lấy set đã đọc + dọn id cũ
    active_ids = {a.alert_id for a in all_items}
    _xoa_da_doc_cu(active_ids)
    da_doc = _lay_da_doc()
    chua_doc = [a for a in all_items if a.alert_id not in da_doc]

    st.divider()

    # Badge header
    n_chua_doc = len(chua_doc)
    n_khan = sum(1 for a in chua_doc if a.muc == MUC_KHAN)
    if n_khan > 0:
        badge_txt = f"🔴 **{n_chua_doc} cảnh báo chưa đọc**"
    elif n_chua_doc > 0:
        badge_txt = f"🟠 **{n_chua_doc} cảnh báo chưa đọc**"
    else:
        badge_txt = "🟢 Đã xem hết"
    st.markdown(f"🔔 {badge_txt}")

    # Hiển thị từng alert theo mức
    for muc in [MUC_KHAN, MUC_CANH_BAO, MUC_LUU_Y]:
        nhom = [a for a in all_items if a.muc == muc]
        if not nhom:
            continue
        icon = _MUC_ICON[muc]
        for alert in nhom:
            is_read = alert.alert_id in da_doc
            if alert.jump_fn is not None:
                btn_key = f"alert_jump_{alert.alert_id}"
                if is_read:
                    st.caption(f"{icon} {alert.tieu_de} ✓")
                elif st.button(f"{icon} {alert.tieu_de}", key=btn_key, use_container_width=True):
                    _danh_dau_da_doc([alert.alert_id])
                    alert.jump_fn()
                    st.rerun()
            else:
                if is_read:
                    st.caption(f"{icon} ~~{alert.tieu_de}~~ ✓")
                elif muc == MUC_KHAN:
                    st.error(
                        f"{icon} **{alert.tieu_de}**"
                        + (f"\n\n{alert.mo_ta}" if alert.mo_ta else "")
                    )
                elif muc == MUC_CANH_BAO:
                    st.warning(
                        f"{icon} **{alert.tieu_de}**"
                        + (f"\n\n{alert.mo_ta}" if alert.mo_ta else "")
                    )
                else:
                    st.info(
                        f"{icon} {alert.tieu_de}"
                        + (f"\n\n{alert.mo_ta}" if alert.mo_ta else "")
                    )

    # Button đánh dấu tất cả đã đọc
    if chua_doc:
        if st.button(
            "✅ Đánh dấu đã đọc tất cả",
            key="alert_mark_all_read",
            use_container_width=True,
        ):
            _danh_dau_da_doc([a.alert_id for a in chua_doc])
            st.rerun()
