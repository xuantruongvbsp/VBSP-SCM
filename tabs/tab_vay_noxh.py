"""Tab Giao quản lý NOXH trực tiếp — theo dõi món vay nhà ở xã hội (chương trình 12).

Nguồn dữ liệu: HSTD (`df_full`), chỉ giữ Hình thức vay = 1, Mã CT = 12 và còn dư nợ.
Phạm vi: PGD role chỉ thấy PGD mình (fail-closed); CN role thấy toàn Chi nhánh.
Trạng thái giao/theo dõi lưu kv_store key `phan_cong_vay_truc_tiep`, index theo số khế ước.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING, Any

import pandas as pd
import streamlit as st

import db
from auth import la_phan_he_pgd, la_quan_ly_cn, normalize_role
from config import (
    COT_DU_NO_QH, COT_HINH_THUC_VAY, COT_MA_CHUONG_TRINH, COT_MA_KH,
    COT_NGAY_DH, COT_NGAY_VAY, COT_SO_KU, COT_TEN_KH, COT_TEN_PGD,
    COT_TEN_XA, COT_TONG_DU_NO,
)
from data.khtd import doc_cbtd
from logger import get_logger
from state_manager import SCMStateManager
from utils import fmt_so, hien_thi_dataframe_phan_trang, xuat_excel

if TYPE_CHECKING:
    from streamlit.delta_generator import DeltaGenerator

logger = get_logger(__name__)

_NOXH_MA_CHUONG_TRINH = 12
_NOXH_PHAN_CONG_KEY = "phan_cong_vay_truc_tiep"
_NOXH_SO_NGAY_QUA_HAN_THEO_DOI = 30
_NOXH_TRANG_THAI = ["Chưa kiểm tra", "Đang theo dõi", "Cần xử lý", "Đã cập nhật"]


def _pgd_slug_ma(pgd: str) -> str:
    # Giữ chữ có dấu (Unicode) để slug key widget/store không bị rỗng hoặc trùng.
    return re.sub(r"\W+", "_", str(pgd).upper().strip()).strip("_") or "CN"


def _num0(value: Any) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return 0.0
    return 0.0 if pd.isna(result) else result


def _fmt_tien(x: Any) -> str:
    """VND → triệu đồng, không số lẻ."""
    try:
        x = float(x)
        if abs(x) > 0:
            return f"{x/1_000_000:,.0f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return "—"
    except (TypeError, ValueError):
        return "—"


def _noxh_text(value: Any) -> str:
    """Chuẩn hóa ô HSTD/KV về text, kể cả pandas.NA."""
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value).strip()


def _noxh_date(value: Any) -> date | None:
    if value is None or str(value).strip() in {"", "nan", "NaT", "None"}:
        return None
    parsed = pd.to_datetime(value, errors="coerce", dayfirst=True)
    if pd.isna(parsed):
        return None
    return parsed.date()


def _noxh_date_text(value: Any) -> str:
    parsed = _noxh_date(value)
    return parsed.strftime("%d/%m/%Y") if parsed else ""


def _loc_vay_truc_tiep_noxh(df_hstd: pd.DataFrame | None) -> pd.DataFrame:
    """Chỉ giữ món NOXH vay trực tiếp còn dư nợ."""
    if df_hstd is None or df_hstd.empty:
        return pd.DataFrame()
    required = {COT_HINH_THUC_VAY, COT_MA_CHUONG_TRINH, COT_TONG_DU_NO}
    if not required.issubset(df_hstd.columns):
        return pd.DataFrame()

    hinh_thuc = pd.to_numeric(df_hstd[COT_HINH_THUC_VAY], errors="coerce")
    ma_ct = pd.to_numeric(df_hstd[COT_MA_CHUONG_TRINH], errors="coerce")
    du_no = pd.to_numeric(df_hstd[COT_TONG_DU_NO], errors="coerce").fillna(0)
    return df_hstd.loc[
        hinh_thuc.eq(1) & ma_ct.eq(_NOXH_MA_CHUONG_TRINH) & du_no.gt(0)
    ].copy()


def _gioi_han_noxh_theo_pgd(df_noxh: pd.DataFrame, pgd_scope: Any) -> pd.DataFrame:
    """Giới hạn đúng một PGD; thiếu cột địa bàn thì trả rỗng để không lộ dữ liệu."""
    if df_noxh is None or df_noxh.empty:
        return pd.DataFrame()
    scope = _noxh_text(pgd_scope)
    if not scope:
        return df_noxh.copy()
    if COT_TEN_PGD not in df_noxh.columns:
        return df_noxh.iloc[0:0].copy()
    pgd_values = df_noxh[COT_TEN_PGD].astype("string").str.strip().str.casefold()
    return df_noxh.loc[pgd_values.eq(scope.casefold()).fillna(False)].copy()


def _co_quyen_quan_ly_noxh(role: str) -> bool:
    """Chỉ quản lý Chi nhánh được giao/gỡ và cập nhật theo dõi NOXH."""
    return la_quan_ly_cn(normalize_role(str(role or "user")))


def _noxh_qua_han_theo_doi(record: dict, today: date | None = None) -> bool:
    """Cảnh báo khi quá lịch hẹn hoặc quá 30 ngày chưa có lần kiểm tra/cập nhật."""
    if not isinstance(record, dict) or not str(record.get("ma_cb") or "").strip():
        return False
    today = today or date.today()
    ngay_hen = _noxh_date(record.get("ngay_hen_tiep"))
    if ngay_hen and ngay_hen <= today:
        return True
    moc = (
        _noxh_date(record.get("ngay_kiem_tra"))
        or _noxh_date(record.get("cap_nhat_luc"))
        or _noxh_date(record.get("ngay_giao"))
    )
    return bool(moc and (today - moc).days > _NOXH_SO_NGAY_QUA_HAN_THEO_DOI)


def _noxh_cbtd_label(ma_cb: str, cbtd_data: dict) -> str:
    ma = str(ma_cb or "").strip()
    if not ma:
        return "—"
    info = (cbtd_data or {}).get(ma, {}) or {}
    ho_ten = str(info.get("ho_ten") or "").strip()
    pgd = str(info.get("pgd") or "").strip()
    suffix = " / ".join(x for x in (ho_ten, pgd) if x)
    return f"{ma} — {suffix}" if suffix else ma


def _tao_bang_theo_doi_noxh(
    df_noxh: pd.DataFrame,
    phan_cong: dict,
    cbtd_data: dict,
    *,
    today: date | None = None,
) -> pd.DataFrame:
    """Ghép HSTD NOXH với thông tin phân công/theo dõi đã lưu trong KV."""
    if df_noxh is None or df_noxh.empty:
        return pd.DataFrame()
    phan_cong = phan_cong if isinstance(phan_cong, dict) else {}
    rows: list[dict[str, Any]] = []
    for _, row in df_noxh.iterrows():
        key = _noxh_text(row.get(COT_SO_KU))
        record = phan_cong.get(key, {}) if key else {}
        record = record if isinstance(record, dict) else {}
        ma_cb = _noxh_text(record.get("ma_cb"))
        qua_han = _noxh_qua_han_theo_doi(record, today=today)
        rows.append({
            "_key": key,
            "_ma_cb": ma_cb,
            "_da_giao": bool(ma_cb),
            "_qua_han": qua_han,
            "Số khế ước": key,
            "Mã KH": _noxh_text(row.get(COT_MA_KH)),
            "Tên KH": _noxh_text(row.get(COT_TEN_KH)),
            "PGD": _noxh_text(row.get(COT_TEN_PGD)),
            "Xã/phường": _noxh_text(row.get(COT_TEN_XA)),
            "Ngày vay": _noxh_date_text(row.get(COT_NGAY_VAY)),
            "Ngày đến hạn": _noxh_date_text(row.get(COT_NGAY_DH)),
            "Dư nợ": _num0(row.get(COT_TONG_DU_NO)),
            "Dư nợ QH": _num0(row.get(COT_DU_NO_QH)),
            "CBTD theo dõi": _noxh_cbtd_label(ma_cb, cbtd_data),
            "Trạng thái": str(record.get("trang_thai") or ("Chưa kiểm tra" if ma_cb else "Chưa giao")),
            "Ngày giao": str(record.get("ngay_giao") or ""),
            "Kiểm tra gần nhất": _noxh_date_text(record.get("ngay_kiem_tra")),
            "Hẹn tiếp": _noxh_date_text(record.get("ngay_hen_tiep")),
            "Cảnh báo": "Quá hạn theo dõi" if qua_han else "",
            "Kết quả": str(record.get("ket_qua") or ""),
            "Ghi chú": str(record.get("ghi_chu") or ""),
        })
    result = pd.DataFrame(rows)
    return result.sort_values(
        ["_qua_han", "_da_giao", "Dư nợ"],
        ascending=[False, True, False],
        kind="stable",
    ).reset_index(drop=True)


def _chuan_bi_pdf_noxh(df_theo_doi: pd.DataFrame) -> pd.DataFrame:
    """Rút gọn bảng theo dõi NOXH để in rõ trên PDF A4 ngang."""
    columns = [
        "Số khế ước", "Tên KH", "PGD", "Dư nợ", "Dư nợ QH", "CBTD theo dõi",
        "Trạng thái", "Kiểm tra gần nhất", "Hẹn tiếp", "Cảnh báo",
    ]
    if df_theo_doi is None or df_theo_doi.empty:
        return pd.DataFrame(columns=["TT"] + columns)

    result = df_theo_doi.reindex(columns=columns).copy()
    result.insert(0, "TT", range(1, len(result) + 1))
    for col in ("Dư nợ", "Dư nợ QH"):
        result[col] = pd.to_numeric(result[col], errors="coerce").fillna(0).div(1_000_000)
    return result.rename(columns={
        "Dư nợ": "Dư nợ (tr)",
        "Dư nợ QH": "Dư nợ QH (tr)",
    })


def render(tab: DeltaGenerator = None, **kwargs) -> None:
    df       = kwargs.get("df")
    df_full  = kwargs.get("df_full", df)
    role     = normalize_role(str(kwargs.get("role", "user") or "user"))
    username = kwargs.get("username", "unknown")
    pgd_user = str(kwargs.get("pgd_user", "") or "").strip()
    state = SCMStateManager()
    _kp = f"pgd_{_pgd_slug_ma(pgd_user)}_" if pgd_user else "cn_"

    ctx = tab if tab is not None else st.container()
    with ctx:
        st.subheader("🏠 Giao quản lý NOXH trực tiếp")
        st.caption(
            "Chương trình 12 — Cho vay nhà ở xã hội theo Nghị định 100; "
            "chỉ hiển thị món vay trực tiếp còn dư nợ."
        )

        # Fail-closed: role PGD mà không xác định được đơn vị → không hiển thị dữ liệu.
        if la_phan_he_pgd(role) and not pgd_user:
            st.warning("⚠️ Không xác định được PGD của tài khoản nên chưa thể hiển thị dữ liệu NOXH.")
            return

        if df_full is None or df_full.empty:
            st.warning("⚠️ Chưa có dữ liệu HSTD để lọc món vay trực tiếp NOXH.")
            return

        cbtd_data_raw: dict = doc_cbtd() or {}
        _x4_df = _gioi_han_noxh_theo_pgd(_loc_vay_truc_tiep_noxh(df_full), pgd_user)

        if _x4_df.empty:
            st.info("ℹ️ Chưa có món vay trực tiếp NOXH còn dư nợ trong phạm vi được xem.")
            return

        _x4_pc = db.doc_kv(_NOXH_PHAN_CONG_KEY, {}) or {}
        if not isinstance(_x4_pc, dict):
            _x4_pc = {}
        _x4_bang = _tao_bang_theo_doi_noxh(_x4_df, _x4_pc, cbtd_data_raw)
        _x4_n = int(len(_x4_bang))
        _x4_n_giao = int(_x4_bang["_da_giao"].sum())
        _x4_n_chua = _x4_n - _x4_n_giao
        _x4_n_qua_han = int(_x4_bang["_qua_han"].sum())
        _x4_tdn = float(_x4_bang["Dư nợ"].sum())

        k1, k2, k3, k4, k5 = st.columns(5)
        k1.metric("Dư nợ NOXH (tỷ)", f"{_x4_tdn/1e9:,.2f}")
        k2.metric("Số món", fmt_so(_x4_n))
        k3.metric("Đã giao", fmt_so(_x4_n_giao))
        k4.metric("Chưa giao", fmt_so(_x4_n_chua))
        k5.metric("Quá hạn theo dõi", fmt_so(_x4_n_qua_han))

        _f1, _f2, _f3, _f4 = st.columns([1.2, 1.2, 1.6, 2.0])
        _x4_pgds = sorted(x for x in _x4_bang["PGD"].dropna().astype(str).unique() if x)
        _x4_pgd = _f1.selectbox("PGD", ["Tất cả"] + _x4_pgds, key=f"{_kp}noxh_pgd")
        _x4_tt = _f2.selectbox(
            "Tình trạng",
            ["Tất cả", "Chưa giao", "Đã giao", "Quá hạn theo dõi", "Cần xử lý"],
            key=f"{_kp}noxh_tt",
        )
        _x4_ma_cb_opts = sorted(x for x in _x4_bang["_ma_cb"].unique() if x)
        _x4_cb = _f3.selectbox(
            "CBTD theo dõi",
            ["Tất cả"] + _x4_ma_cb_opts,
            format_func=lambda x: x if x == "Tất cả" else _noxh_cbtd_label(x, cbtd_data_raw),
            key=f"{_kp}noxh_cbtd",
        )
        _x4_tim = _f4.text_input("Tìm KH / khế ước", key=f"{_kp}noxh_tim").strip().casefold()

        _x4_loc = _x4_bang.copy()
        if _x4_pgd != "Tất cả":
            _x4_loc = _x4_loc[_x4_loc["PGD"] == _x4_pgd]
        if _x4_cb != "Tất cả":
            _x4_loc = _x4_loc[_x4_loc["_ma_cb"] == _x4_cb]
        if _x4_tt == "Chưa giao":
            _x4_loc = _x4_loc[~_x4_loc["_da_giao"]]
        elif _x4_tt == "Đã giao":
            _x4_loc = _x4_loc[_x4_loc["_da_giao"]]
        elif _x4_tt == "Quá hạn theo dõi":
            _x4_loc = _x4_loc[_x4_loc["_qua_han"]]
        elif _x4_tt == "Cần xử lý":
            _x4_loc = _x4_loc[_x4_loc["Trạng thái"] == "Cần xử lý"]
        if _x4_tim:
            _x4_haystack = (
                _x4_loc[["Số khế ước", "Mã KH", "Tên KH"]]
                .fillna("").astype(str).agg(" ".join, axis=1).str.casefold()
            )
            _x4_loc = _x4_loc[_x4_haystack.str.contains(_x4_tim, regex=False)]

        _x4_hanh_dong = _x4_bang.copy()
        if _x4_pgd != "Tất cả":
            _x4_hanh_dong = _x4_hanh_dong[_x4_hanh_dong["PGD"] == _x4_pgd]

        if _x4_loc.empty:
            st.info("Không có món NOXH phù hợp bộ lọc.")
        else:
            _x4_hien_thi = _x4_loc.drop(
                columns=["_key", "_ma_cb", "_da_giao", "_qua_han"],
                errors="ignore",
            ).copy()
            _x4_hien_thi["Dư nợ (tr)"] = _x4_hien_thi.pop("Dư nợ").div(1_000_000).round(0)
            _x4_hien_thi["Dư nợ QH (tr)"] = _x4_hien_thi.pop("Dư nợ QH").div(1_000_000).round(0)
            hien_thi_dataframe_phan_trang(_x4_hien_thi, key=f"{_kp}noxh_ds", height=460)

        _x4_export = _x4_loc.drop(
            columns=["_key", "_ma_cb", "_da_giao", "_qua_han"],
            errors="ignore",
        ).rename(columns={"Dư nợ": "Dư nợ (VND)", "Dư nợ QH": "Dư nợ QH (VND)"})
        _x4_pdf_df = _chuan_bi_pdf_noxh(_x4_loc)
        _x4_pdf_store_key = f"cbtd_noxh_pdf_{_pgd_slug_ma(pgd_user or 'toan_cn')}"
        _x4_scope_label = _x4_pgd if _x4_pgd != "Tất cả" else (pgd_user or "TOÀN CHI NHÁNH")
        _x4_dl_excel, _x4_tao_pdf = st.columns(2)
        with _x4_dl_excel:
            st.download_button(
                "⬇ Tải Excel danh sách NOXH",
                data=xuat_excel({"NOXH_theo_doi": _x4_export}),
                file_name=f"Theo_doi_NOXH_{datetime.today().strftime('%d%m%Y')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key=f"{_kp}noxh_excel",
            )
        with _x4_tao_pdf:
            if st.button(
                "🖨️ In PDF danh sách NOXH",
                key=f"{_kp}noxh_btn_pdf",
                type="primary",
                disabled=_x4_pdf_df.empty,
            ):
                try:
                    from components.export_pdf import xuat_pdf_co_chart
                    _x4_pdf_bytes = xuat_pdf_co_chart(
                        _x4_pdf_df,
                        tieu_de=f"THEO DÕI VAY TRỰC TIẾP NOXH — {_x4_scope_label}",
                        nguoi_xuat=username or "system",
                        cols_tien=["Dư nợ (tr)", "Dư nợ QH (tr)"],
                        don_vi_tien="triệu đồng",
                        prefix_file="Theo_doi_NOXH",
                        them_dong_tong=True,
                    )
                    if _x4_pdf_bytes:
                        state.downloads.set(
                            _x4_pdf_store_key,
                            _x4_pdf_bytes,
                            f"Theo_doi_NOXH_{datetime.today().strftime('%d%m%Y')}.pdf",
                        )
                        db.ghi_audit(
                            username,
                            "xuat_pdf_theo_doi_noxh",
                            f"pham_vi={_x4_scope_label}; so_dong={len(_x4_pdf_df)}",
                        )
                        st.success("Đã tạo PDF danh sách NOXH.")
                    else:
                        st.error("Lỗi tạo PDF (thiếu thư viện reportlab?).")
                except Exception as e:
                    logger.error("Xuất PDF theo dõi NOXH — %s", e, exc_info=True)
                    st.error(f"Lỗi tạo PDF: {e}")
            if state.downloads.has(_x4_pdf_store_key):
                st.download_button(
                    "⬇ Tải file PDF",
                    data=state.downloads.get_bytes(_x4_pdf_store_key),
                    file_name=(
                        state.downloads.get_filename(_x4_pdf_store_key)
                        or "Theo_doi_NOXH.pdf"
                    ),
                    mime="application/pdf",
                    key=f"{_kp}noxh_pdf_download",
                )

        if not _co_quyen_quan_ly_noxh(role):
            st.caption(
                "Chế độ chỉ đọc. Chỉ Quản lý Chi nhánh được giao, gỡ và cập nhật theo dõi NOXH."
            )
            return

        st.divider()
        st.markdown("##### Giao CBTD theo dõi")
        _x4_pgd_giao = _x4_pgd if _x4_pgd != "Tất cả" else (
            _x4_pgds[0] if len(_x4_pgds) == 1 else ""
        )
        _x4_cbtd_giao = {
            ma: info for ma, info in cbtd_data_raw.items()
            if _noxh_text(info.get("pgd")).casefold() == _x4_pgd_giao.casefold()
        } if _x4_pgd_giao else {}
        _x4_chua_df = _x4_hanh_dong[
            (~_x4_hanh_dong["_da_giao"]) & _x4_hanh_dong["_key"].ne("")
        ]
        _x4_chua = list(dict.fromkeys(_x4_chua_df["_key"].tolist()))
        _x4_label_ku = {
            str(r["_key"]): (
                f"{r['Số khế ước']} — {r['Tên KH']} — {_fmt_tien(r['Dư nợ'])} tr"
            )
            for _, r in _x4_chua_df.iterrows()
        }
        if not _x4_pgd_giao:
            st.info("Chọn một PGD ở bộ lọc phía trên trước khi giao CBTD theo dõi.")
        elif not _x4_cbtd_giao:
            st.warning(f"Chưa có CBTD thuộc {_x4_pgd_giao} để giao theo dõi.")
        elif not _x4_chua:
            st.success("Toàn bộ món NOXH trong phạm vi đã được giao theo dõi.")
        else:
            _g1, _g2 = st.columns([2, 1])
            _x4_sel_ku = _g1.multiselect(
                f"Chọn món chưa giao ({len(_x4_chua)})",
                _x4_chua,
                format_func=lambda x: _x4_label_ku.get(x, x),
                key=f"{_kp}noxh_sel_ku",
            )
            _x4_cbs = sorted(_x4_cbtd_giao.keys())
            _x4_sel_cb = _g2.selectbox(
                "Giao cho CBTD",
                _x4_cbs,
                format_func=lambda x: _noxh_cbtd_label(x, cbtd_data_raw),
                key=f"{_kp}noxh_sel_cb",
            )
            if st.button(
                "Giao theo dõi",
                type="primary",
                key=f"{_kp}noxh_btn_giao",
                disabled=not _x4_sel_ku,
            ):
                _now = datetime.now().strftime("%d/%m/%Y %H:%M")
                _x4_pc_moi = dict(_x4_pc)
                for _k in _x4_sel_ku:
                    _x4_pc_moi[_k] = {
                        "ma_cb": _x4_sel_cb,
                        "ngay_giao": _now,
                        "nguoi_giao": username,
                        "trang_thai": "Chưa kiểm tra",
                        "ngay_kiem_tra": "",
                        "ngay_hen_tiep": "",
                        "ket_qua": "",
                        "ghi_chu": "",
                    }
                db.ghi_kv(
                    _NOXH_PHAN_CONG_KEY,
                    _x4_pc_moi,
                    username,
                    note=f"Giao {len(_x4_sel_ku)} món NOXH cho {_x4_sel_cb}",
                )
                db.ghi_audit(
                    username,
                    "giao_noxh_cbtd",
                    f"Giao {len(_x4_sel_ku)} món NOXH cho CBTD {_x4_sel_cb}",
                )
                st.cache_data.clear()
                st.success(f"Đã giao {len(_x4_sel_ku)} món cho {_x4_sel_cb}.")
                st.rerun()

        _x4_da_df = _x4_hanh_dong[
            _x4_hanh_dong["_da_giao"] & _x4_hanh_dong["_key"].ne("")
        ]
        _x4_da = list(dict.fromkeys(_x4_da_df["_key"].tolist()))
        if not _x4_da:
            return

        st.markdown("##### Cập nhật kết quả theo dõi")
        _x4_cap_nhat_ku = st.selectbox(
            "Chọn món đã giao",
            _x4_da,
            format_func=lambda x: next(
                (
                    f"{r['Số khế ước']} — {r['Tên KH']} — {r['CBTD theo dõi']}"
                    for _, r in _x4_da_df.iterrows() if r["_key"] == x
                ),
                x,
            ),
            key=f"{_kp}noxh_cap_nhat_ku",
        )
        _x4_record = dict(_x4_pc.get(_x4_cap_nhat_ku, {}) or {})
        _x4_status = str(_x4_record.get("trang_thai") or "Chưa kiểm tra")
        if _x4_status not in _NOXH_TRANG_THAI:
            _x4_status = "Chưa kiểm tra"
        _x4_slug = re.sub(r"[^A-Za-z0-9]+", "_", _x4_cap_nhat_ku)[:60]
        _u1, _u2, _u3 = st.columns(3)
        _x4_status_moi = _u1.selectbox(
            "Trạng thái",
            _NOXH_TRANG_THAI,
            index=_NOXH_TRANG_THAI.index(_x4_status),
            key=f"{_kp}noxh_status_{_x4_slug}",
        )
        _x4_ngay_kt = _u2.date_input(
            "Ngày kiểm tra",
            value=_noxh_date(_x4_record.get("ngay_kiem_tra")) or date.today(),
            format="DD/MM/YYYY",
            key=f"{_kp}noxh_ngay_kt_{_x4_slug}",
        )
        _x4_ngay_hen = _u3.date_input(
            "Ngày theo dõi tiếp",
            value=_noxh_date(_x4_record.get("ngay_hen_tiep")) or (date.today() + timedelta(days=30)),
            format="DD/MM/YYYY",
            key=f"{_kp}noxh_ngay_hen_{_x4_slug}",
        )
        _x4_ket_qua = st.text_area(
            "Kết quả kiểm tra",
            value=str(_x4_record.get("ket_qua") or ""),
            key=f"{_kp}noxh_ket_qua_{_x4_slug}",
        )
        _x4_ghi_chu = st.text_area(
            "Ghi chú / việc cần làm",
            value=str(_x4_record.get("ghi_chu") or ""),
            key=f"{_kp}noxh_ghi_chu_{_x4_slug}",
        )
        if st.button(
            "Lưu kết quả theo dõi",
            type="primary",
            key=f"{_kp}noxh_btn_luu_{_x4_slug}",
        ):
            _x4_pc_moi = dict(_x4_pc)
            _x4_record.update({
                "trang_thai": _x4_status_moi,
                "ngay_kiem_tra": _x4_ngay_kt.strftime("%d/%m/%Y"),
                "ngay_hen_tiep": _x4_ngay_hen.strftime("%d/%m/%Y"),
                "ket_qua": _x4_ket_qua.strip(),
                "ghi_chu": _x4_ghi_chu.strip(),
                "nguoi_cap_nhat": username,
                "cap_nhat_luc": datetime.now().strftime("%d/%m/%Y %H:%M"),
            })
            _x4_pc_moi[_x4_cap_nhat_ku] = _x4_record
            db.ghi_kv(
                _NOXH_PHAN_CONG_KEY,
                _x4_pc_moi,
                username,
                note=f"Cập nhật theo dõi NOXH {_x4_cap_nhat_ku}",
            )
            db.ghi_audit(
                username,
                "cap_nhat_theo_doi_noxh",
                f"Khế ước {_x4_cap_nhat_ku}: {_x4_status_moi}",
            )
            st.cache_data.clear()
            st.success("Đã lưu kết quả theo dõi.")
            st.rerun()

        with st.expander(f"Gỡ giao ({len(_x4_da)} món đã giao)", expanded=False):
            _x4_sel_da = st.multiselect(
                "Chọn món cần gỡ", _x4_da, key=f"{_kp}noxh_sel_go"
            )
            if st.button(
                "Gỡ giao",
                key=f"{_kp}noxh_btn_go",
                disabled=not _x4_sel_da,
            ):
                _x4_pc_moi = dict(_x4_pc)
                for _k in _x4_sel_da:
                    _x4_pc_moi.pop(_k, None)
                db.ghi_kv(
                    _NOXH_PHAN_CONG_KEY,
                    _x4_pc_moi,
                    username,
                    note=f"Gỡ giao {len(_x4_sel_da)} món NOXH",
                )
                db.ghi_audit(
                    username,
                    "go_giao_noxh_cbtd",
                    f"Gỡ {len(_x4_sel_da)} món NOXH",
                )
                st.cache_data.clear()
                st.success(f"Đã gỡ {len(_x4_sel_da)} món.")
                st.rerun()
