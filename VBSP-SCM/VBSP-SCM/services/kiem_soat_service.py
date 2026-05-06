"""
Kiểm soát Chi nhánh — registry báo cáo + render từng loại.
Mở rộng: thêm hàm render_*(cache, ...) và một dòng BAO_CAO_REGISTRY;
có thể bổ sung khóa vào cache trong render (lưu cache["ten_key_moi"]).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable

import pandas as pd
import streamlit as st

from config import (
    COT_TEN_PGD,
    COT_TEN_XA,
    COT_TEN_THON,
    COT_DVUT,
    COT_DU_NO_TH,
    COT_DU_NO_QH,
    COT_TONG_DU_NO,
    COT_SO_KU,
    COT_TEN_KH,
    COT_TEN_CT,
    COT_NGAY_DH,
    COT_MA_KH,
    COT_LAI_TON,
    COT_TINH_TRANG,
    COT_NGAY_VAY,
    COT_THOI_HAN,
    COT_NGUON_VON,
    COT_MA_CHUONG_TRINH,
)
from pdf_service import xuat_pdf
from services.report_service import ten_file_bao_cao
from utils import fmt_so, xuat_excel, hien_thi_dataframe_phan_trang

DUOI_TV = 5
TREN_TV = 60

_COT_NGAY_DH_GH = "Ngày ĐH theo Gia hạn"
_COT_MA_QD = "Mã Quyết định"
_COT_TEN_DTTH = "Tên ĐTTH"
_COT_NGAY_RT = "Ngày ra trường"
_COT_NGAY_GN1 = "Ngày GN đầu tiên"

# ── Nhóm báo cáo (thứ tự hiển thị) ─────────────────────────────────────────
NHOM_BAO_CAO: dict[str, str] = {
    "rui_ro": "🔴 Rủi ro tín dụng",
    "tien_do": "📊 Tiến độ hoạt động",
    "kiem_toan": "🔍 Giám sát nội bộ",
    "ke_hoach": "🎯 Kế hoạch — Thực hiện",
    "khac": "📁 Khác",
}


@dataclass
class BaoCaoMeta:
    ma: str
    ten: str
    nhom: str
    mo_ta: str
    render_fn: Callable[[dict[str, Any], str, str, bool], None]
    cols_tien: list[str]
    prefix_pdf: str


def chon_pgd_filter(df: pd.DataFrame, key_suffix: str) -> str:
    """Selectbox chọn PGD — 'Tất cả' hoặc tên PGD."""
    key = f"ks_pgd_{key_suffix}"
    if df is None or df.empty or COT_TEN_PGD not in df.columns:
        return "Tất cả"
    ds = sorted(
        str(x).strip()
        for x in df[COT_TEN_PGD].dropna().unique()
        if str(x).strip()
    )
    options = ["Tất cả"] + ds
    chon = st.selectbox(
        "Lọc PGD",
        options=options,
        key=key,
    )
    return chon


def _tinh_to_sai_so_tv(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Tổ TK&VV có số thành viên ngoài khoảng [DUOI_TV, TREN_TV].
    Trả về (df_vi_pham, df_to_all) — df_to_all là tổng hợp mọi tổ hợp lệ.
    """
    empty = pd.DataFrame(), pd.DataFrame()
    if df is None or df.empty or COT_TONG_DU_NO not in df.columns:
        return empty

    du_no = pd.to_numeric(df[COT_TONG_DU_NO], errors="coerce").fillna(0)

    if COT_TINH_TRANG not in df.columns:
        df_active = df[du_no > 0].copy()
    else:
        tt = df[COT_TINH_TRANG].astype(str).str.strip()
        mask_1 = (tt != "CLOSE") & (du_no > 0)
        mask_2 = (tt == "CLOSE") & (du_no == 0)
        p1, p2 = df.loc[mask_1], df.loc[mask_2]
        parts = [p for p in (p1, p2) if not p.empty]
        if not parts:
            df_active = pd.DataFrame(columns=df.columns)
        else:
            df_active = pd.concat(parts, ignore_index=True)

    # Loại món vay trực tiếp (không qua tổ TK&VV): cần có "Tên tổ" hoặc ĐVUT
    co_ten_to = "Tên tổ" in df_active.columns
    co_ten_dvut = COT_DVUT in df_active.columns
    if co_ten_to and co_ten_dvut:
        ten_ok = df_active["Tên tổ"].notna() & (
            df_active["Tên tổ"].astype(str).str.strip() != ""
        )
        dvut_ok = df_active[COT_DVUT].notna() & (
            df_active[COT_DVUT].astype(str).str.strip() != ""
        )
        mask_co_to = ten_ok | dvut_ok
        df_active = df_active.loc[mask_co_to]
    elif co_ten_to:
        df_active = df_active.loc[
            df_active["Tên tổ"].notna()
            & (df_active["Tên tổ"].astype(str).str.strip() != "")
        ]
    elif co_ten_dvut:
        df_active = df_active.loc[
            df_active[COT_DVUT].notna()
            & (df_active[COT_DVUT].astype(str).str.strip() != "")
        ]

    if df_active.empty:
        return pd.DataFrame(), pd.DataFrame()

    gb_keys = [
        c
        for c in (
            COT_TEN_PGD,
            COT_TEN_XA,
            COT_TEN_THON,
            "Tên tổ",
            COT_DVUT,
        )
        if c in df_active.columns
    ]
    if not gb_keys:
        return pd.DataFrame(), pd.DataFrame()

    col_nunique = COT_MA_KH if COT_MA_KH in df_active.columns else (
        COT_SO_KU if COT_SO_KU in df_active.columns else None
    )
    if col_nunique is None:
        return pd.DataFrame(), pd.DataFrame()

    agg_map: dict[str, tuple] = {
        "Số_thành_viên": (col_nunique, "nunique"),
        "Tổng_dư_nợ": (COT_TONG_DU_NO, "sum"),
    }
    if COT_DU_NO_TH in df_active.columns:
        agg_map["Dư_nợ_TH"] = (COT_DU_NO_TH, "sum")
    if COT_DU_NO_QH in df_active.columns:
        agg_map["Dư_nợ_QH"] = (COT_DU_NO_QH, "sum")

    df_to = df_active.groupby(gb_keys, dropna=False).agg(**agg_map).reset_index()
    if "Dư_nợ_TH" not in df_to.columns:
        df_to["Dư_nợ_TH"] = 0.0
    if "Dư_nợ_QH" not in df_to.columns:
        df_to["Dư_nợ_QH"] = 0.0

    m = df_to["Số_thành_viên"]
    df_vi_pham = df_to[~m.between(DUOI_TV, TREN_TV)].copy()
    df_vi_pham["Mô tả"] = df_vi_pham["Số_thành_viên"].apply(
        lambda x: (
            f"Thiếu thành viên (< {DUOI_TV})"
            if x < DUOI_TV
            else f"Vượt thành viên (> {TREN_TV})"
        )
    )
    return df_vi_pham, df_to


def _tinh_ngaygh_dp(row: pd.Series) -> pd.Timestamp:
    """
    Tính ngày gia hạn tối đa được phép theo quy định NHCSXH.
    Trả về pd.NaT nếu không đủ dữ liệu hoặc không áp dụng.
    Nguồn: SQL MS11 INTELLECT + quy định gia hạn nội bộ NHCSXH.
    """
    ma_ct = str(row.get(COT_MA_CHUONG_TRINH, "")).strip()
    ma_qd = str(row.get(_COT_MA_QD, "")).strip()
    ten_dtth = str(row.get(_COT_TEN_DTTH, "")).strip()
    ngay_dh = pd.to_datetime(row.get(COT_NGAY_DH), dayfirst=True, errors="coerce")
    thoi_han = pd.to_numeric(row.get(COT_THOI_HAN), errors="coerce")

    if pd.isna(ngay_dh):
        return pd.NaT

    if ma_ct == "02":
        ngay_rt = pd.to_datetime(row.get(_COT_NGAY_RT), dayfirst=True, errors="coerce")
        ngay_gn1 = pd.to_datetime(row.get(_COT_NGAY_GN1), dayfirst=True, errors="coerce")
        if pd.isna(ngay_rt) or pd.isna(ngay_gn1):
            return pd.NaT
        so_thang_vay = (ngay_rt.year - ngay_gn1.year) * 12 + (
            ngay_rt.month - ngay_gn1.month
        )
        if so_thang_vay <= 0:
            return pd.NaT
        return ngay_dh + pd.DateOffset(months=int(so_thang_vay / 2))

    if ma_ct == "17":
        return ngay_dh + pd.DateOffset(months=30)

    if "29" in ma_qd or "54" in ma_qd:
        if ten_dtth == "Hộ mới thoát nghèo":
            return ngay_dh
        if ten_dtth == "Hộ nghèo":
            return ngay_dh + pd.DateOffset(months=30)

    if pd.isna(thoi_han):
        return pd.NaT
    if thoi_han <= 12:
        return ngay_dh + pd.DateOffset(months=12)
    return ngay_dh + pd.DateOffset(months=int(thoi_han / 2))


def _tinh_gia_han_vuot(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    need = [COT_NGUON_VON, COT_NGAY_DH, _COT_NGAY_DH_GH, COT_DU_NO_TH]
    if not all(c in df.columns for c in need):
        return pd.DataFrame()

    d = df.copy()
    nv = d[COT_NGUON_VON]
    m_nv = (nv.astype(str).str.strip() == "1") | (
        pd.to_numeric(nv, errors="coerce") == 1
    )
    d = d.loc[m_nv].copy()
    if d.empty:
        return pd.DataFrame()

    du_th = pd.to_numeric(d[COT_DU_NO_TH], errors="coerce").fillna(0)
    m_dn = du_th > 0
    if COT_TINH_TRANG in d.columns:
        tt = d[COT_TINH_TRANG].astype(str).str.strip()
        m_dn = m_dn & (tt != "CLOSE")
    d = d.loc[m_dn].copy()
    if d.empty:
        return pd.DataFrame()

    n_dh_gh = pd.to_datetime(d[_COT_NGAY_DH_GH], dayfirst=True, errors="coerce")
    n_dh = pd.to_datetime(d[COT_NGAY_DH], dayfirst=True, errors="coerce")
    m_gh = n_dh_gh.notna() & n_dh.notna() & (n_dh_gh > n_dh)
    d = d.loc[m_gh].copy()
    if d.empty:
        return pd.DataFrame()

    d[COT_NGAY_DH] = pd.to_datetime(d[COT_NGAY_DH], dayfirst=True, errors="coerce")
    d[_COT_NGAY_DH_GH] = pd.to_datetime(
        d[_COT_NGAY_DH_GH], dayfirst=True, errors="coerce"
    )
    for _c in (_COT_NGAY_RT, _COT_NGAY_GN1):
        if _c in d.columns:
            d[_c] = pd.to_datetime(d[_c], dayfirst=True, errors="coerce")

    d = d.copy()
    d["Ngày GH được phép"] = d.apply(_tinh_ngaygh_dp, axis=1)
    d = d[d["Ngày GH được phép"].notna()].copy()
    if d.empty:
        return pd.DataFrame()

    m_vp = d[_COT_NGAY_DH_GH] > d["Ngày GH được phép"]
    d = d.loc[m_vp].copy()
    if d.empty:
        return pd.DataFrame()

    d["Vượt (tháng)"] = (
        (d[_COT_NGAY_DH_GH] - d["Ngày GH được phép"]).dt.days / 30
    ).round(1)
    d = d.sort_values("Vượt (tháng)", ascending=False)

    cols_out = [
        COT_TEN_PGD,
        COT_MA_KH,
        COT_TEN_KH,
        COT_SO_KU,
        COT_TEN_CT,
        COT_MA_CHUONG_TRINH,
        _COT_MA_QD,
        _COT_TEN_DTTH,
        COT_NGAY_VAY,
        COT_THOI_HAN,
        COT_NGAY_DH,
        _COT_NGAY_DH_GH,
        "Ngày GH được phép",
        "Vượt (tháng)",
        COT_TONG_DU_NO,
        COT_DU_NO_TH,
    ]
    cols_ok = [c for c in cols_out if c in d.columns]
    return d[cols_ok].copy()


def _tong_hop_vp_theo_pgd(df_vp: pd.DataFrame) -> pd.DataFrame:
    """Bảng tổng hợp vi phạm theo PGD."""
    if df_vp is None or df_vp.empty or COT_TEN_PGD not in df_vp.columns:
        return pd.DataFrame()
    ten_to = "Tên tổ"
    rows: list[dict] = []
    for pgd, grp in df_vp.groupby(COT_TEN_PGD, dropna=False):
        n_to = (
            int(grp[ten_to].nunique())
            if ten_to in grp.columns
            else len(grp)
        )
        rows.append(
            {
                COT_TEN_PGD: pgd,
                "Số_tổ_vi_phạm": n_to,
                "Tổ_thiếu_TV": int((grp["Số_thành_viên"] < DUOI_TV).sum()),
                "Tổ_vượt_TV": int((grp["Số_thành_viên"] > TREN_TV).sum()),
                "Tổng_dư_nợ": grp["Tổng_dư_nợ"].sum(),
            }
        )
    return pd.DataFrame(rows)


def _tong_hop_ghv_theo_pgd(df_gv: pd.DataFrame) -> pd.DataFrame:
    """Bảng tổng hợp gia hạn vượt theo PGD."""
    if (
        df_gv is None
        or df_gv.empty
        or COT_TEN_PGD not in df_gv.columns
        or "Vượt (tháng)" not in df_gv.columns
        or COT_DU_NO_TH not in df_gv.columns
    ):
        return pd.DataFrame()
    return (
        df_gv.groupby(COT_TEN_PGD, dropna=False)
        .agg(
            Số_món=(COT_DU_NO_TH, "size"),
            Dư_nợ_TH=(COT_DU_NO_TH, "sum"),
            Vượt_max=("Vượt (tháng)", "max"),
        )
        .reset_index()
    )


def _ks_html_metric_card(
    title: str,
    value: str,
    subtitle: str,
    bg: str,
    border: str,
    value_color: str,
) -> str:
    return f"""<div style="background:{bg};border-left:4px solid {border};border-radius:8px;padding:16px;">
    <div style="font-size:13px;color:#666">{title}</div>
    <div style="font-size:28px;font-weight:bold;color:{value_color}">{value}</div>
    <div style="font-size:11px;color:#888">{subtitle}</div>
</div>"""


def _fmt_so_cell(v: Any) -> str:
    """Ô hiển thị số nguyên/đồng — fmt_so, không dùng f-string thủ công."""
    return fmt_so(v) if pd.notna(v) else "—"


def _style_tonghop_pgd(df: pd.DataFrame) -> Any:
    """Header xanh; dòng Tổ_vượt_TV > 0 / Tổ_thiếu_TV > 0 (trên df số gốc)."""
    styles = [
        {
            "selector": "thead th",
            "props": [
                ("background-color", "#2E7D32"),
                ("color", "white"),
            ],
        }
    ]
    styler = df.style.set_table_styles(styles)

    def _row_colors(row: pd.Series) -> list[str]:
        n = len(row)
        try:
            tv = int(row["Tổ_vượt_TV"]) if "Tổ_vượt_TV" in row.index else 0
        except (TypeError, ValueError):
            tv = 0
        try:
            tt = int(row["Tổ_thiếu_TV"]) if "Tổ_thiếu_TV" in row.index else 0
        except (TypeError, ValueError):
            tt = 0
        if tv > 0:
            return ["background-color: #FFEBEE"] * n
        if tt > 0:
            return ["background-color: #FFF3E0"] * n
        return [""] * n

    return styler.apply(_row_colors, axis=1)


def _style_chitiet(row: pd.Series) -> list[str]:
    mo = str(row.get("Mô tả", ""))
    n = len(row)
    if mo.startswith("Vượt"):
        return ["background-color: #FFEBEE"] * n
    if mo.startswith("Thiếu"):
        return ["background-color: #FFF3E0"] * n
    return [""] * n


def _style_ghv_tonghop_row(row: pd.Series) -> list[str]:
    n = len(row)
    try:
        raw = row.get("Vượt_max")
        vm = float(raw) if pd.notna(raw) else 0.0
    except (TypeError, ValueError):
        vm = 0.0
    if vm > 12:
        return ["background-color: #FFEBEE"] * n
    if vm >= 6:
        return ["background-color: #FFF3E0"] * n
    return [""] * n


def _style_ghv_chitiet_row(row: pd.Series) -> list[str]:
    n = len(row)
    cols = list(row.index)
    if "Vượt (tháng)" not in cols:
        return [""] * n
    j = cols.index("Vượt (tháng)")
    styles = [""] * n
    vuot = row.get("Vượt (tháng)")
    try:
        v = float(vuot) if pd.notna(vuot) else None
    except (TypeError, ValueError):
        v = None
    if v is None:
        return styles
    if v > 12:
        styles[j] = "background-color: #FFEBEE"
    elif v >= 6:
        styles[j] = "background-color: #FFF3E0"
    else:
        styles[j] = "background-color: #FFFDE7"
    return styles


def _xuat_excel_btn(
    df: pd.DataFrame,
    ten_file_prefix: str,
    key: str,
    readonly: bool,
    sheet_name: str = "Du_lieu",
) -> None:
    """Render nút Xuất Excel — ẩn khi readonly."""
    if readonly or df is None or df.empty:
        return
    buf = xuat_excel({sheet_name[:31]: df})
    st.download_button(
        label="⬇️ Xuất Excel",
        data=buf,
        file_name=ten_file_bao_cao(ten_file_prefix, "xlsx"),
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key=key,
    )


def _xuat_pdf_btn(
    df: pd.DataFrame,
    tieu_de: str,
    username: str,
    cols_tien: list[str],
    prefix_pdf: str,
    key: str,
    readonly: bool,
) -> None:
    """Render Xuất PDF (xuat_pdf) — ẩn khi readonly."""
    if readonly or df is None or df.empty:
        return
    if st.button("📄 Xuất PDF", key=key, type="secondary"):
        try:
            with st.spinner("Đang tạo PDF..."):
                pdf_bytes = xuat_pdf(
                    df,
                    tieu_de,
                    username,
                    cols_tien,
                    prefix_file=prefix_pdf,
                )
            ten_file = f"{prefix_pdf}_{datetime.now().strftime('%d%m%Y_%H%M')}.pdf"
            st.download_button(
                label="⬇ Tải file PDF",
                data=pdf_bytes,
                file_name=ten_file,
                mime="application/pdf",
                key=f"{key}_dl",
            )
        except Exception as e:
            st.error(f"❌ Lỗi tạo PDF: {e}")


def render_3m_khd(
    cache: dict[str, Any],
    pgd_chon: str,
    username: str,
    readonly: bool,
) -> None:
    """3 tháng không hoạt động — tổng hợp PGD + chi tiết (từ cache)."""
    df_khd_pgd = cache["df_khd_pgd"]
    df_khd_chi = cache["df_khd_chi"]
    if df_khd_pgd is None or df_khd_pgd.empty:
        st.success("Không có hồ sơ 3 tháng không hoạt động.")
        return

    if pgd_chon != "Tất cả" and COT_TEN_PGD in df_khd_pgd.columns:
        df_th = df_khd_pgd[df_khd_pgd[COT_TEN_PGD] == pgd_chon].copy()
        df_chi = df_khd_chi[df_khd_chi[COT_TEN_PGD] == pgd_chon].copy()
    else:
        df_th = df_khd_pgd.copy()
        df_chi = df_khd_chi.copy()

    if df_th.empty:
        st.success("Không có hồ sơ 3 tháng không hoạt động trong phạm vi đã lọc.")
        return

    st.markdown("**Tổng hợp theo PGD**")
    hien_thi_dataframe_phan_trang(df_th, key="ks_khd_th_pgd", height=320)

    ds_pgd_ct = [str(x) for x in df_th[COT_TEN_PGD].tolist() if pd.notna(x)]
    chon_ct = st.selectbox(
        "Chi tiết theo PGD",
        options=ds_pgd_ct,
        key="ks_khd_chon_ct",
    )
    df_ct = df_chi[df_chi[COT_TEN_PGD] == chon_ct].copy()

    st.markdown(f"**Chi tiết — {chon_ct}** ({len(df_ct)} dòng)")
    hien_thi_dataframe_phan_trang(df_ct, key="ks_khd_ct", height=400)

    c1, c2 = st.columns(2)
    with c1:
        _xuat_excel_btn(
            df_ct,
            "KSD_KHD",
            key="ks_khd_xlsx",
            readonly=readonly,
            sheet_name="KHD_3m",
        )
    with c2:
        _xuat_pdf_btn(
            df_ct,
            f"3 tháng không hoạt động — {chon_ct}",
            username,
            [COT_TONG_DU_NO, COT_LAI_TON],
            "KSD_KHD",
            key="ks_khd_pdf",
            readonly=readonly,
        )


def render_nqh(
    cache: dict[str, Any],
    pgd_chon: str,
    username: str,
    readonly: bool,
) -> None:
    """Nợ quá hạn phát sinh — tổng hợp PGD + chi tiết (từ cache)."""
    df_nqh_pgd = cache["df_nqh_pgd"]
    df_nqh_chi = cache["df_nqh_chi"]

    if df_nqh_chi is None or df_nqh_chi.empty:
        if COT_DU_NO_QH not in cache["df_kh"].columns:
            st.warning("Thiếu cột dư nợ quá hạn trong dữ liệu.")
        else:
            st.success("Không có hồ sơ nợ quá hạn > 0.")
        return

    if pgd_chon != "Tất cả" and COT_TEN_PGD in df_nqh_pgd.columns:
        df_th = df_nqh_pgd[df_nqh_pgd[COT_TEN_PGD] == pgd_chon].copy()
        df_chi = df_nqh_chi[df_nqh_chi[COT_TEN_PGD] == pgd_chon].copy()
    else:
        df_th = df_nqh_pgd.copy() if df_nqh_pgd is not None else pd.DataFrame()
        df_chi = df_nqh_chi.copy()

    if df_th.empty:
        st.success("Không có hồ sơ nợ quá hạn > 0 trong phạm vi đã lọc.")
        return

    st.markdown("**Tổng hợp theo PGD**")
    hien_thi_dataframe_phan_trang(df_th, key="ks_nqh_th", height=320)

    ds_pgd_ct = [str(x) for x in df_th[COT_TEN_PGD].tolist() if pd.notna(x)]
    chon_ct = st.selectbox(
        "Chi tiết theo PGD",
        options=ds_pgd_ct,
        key="ks_nqh_chon_ct",
    )
    cols = [
        c
        for c in [
            COT_TEN_KH,
            COT_SO_KU,
            COT_TEN_CT,
            COT_DU_NO_QH,
            COT_TONG_DU_NO,
            COT_NGAY_DH,
            COT_MA_KH,
            COT_TEN_PGD,
        ]
        if c in df_chi.columns
    ]
    df_ct = df_chi[df_chi[COT_TEN_PGD] == chon_ct][cols].copy()

    st.markdown(f"**Chi tiết — {chon_ct}** ({len(df_ct)} dòng)")
    hien_thi_dataframe_phan_trang(df_ct, key="ks_nqh_ct", height=400)

    c1, c2 = st.columns(2)
    with c1:
        _xuat_excel_btn(
            df_ct,
            "KSD_NQH",
            key="ks_nqh_xlsx",
            readonly=readonly,
            sheet_name="NQH",
        )
    with c2:
        _xuat_pdf_btn(
            df_ct,
            f"Nợ quá hạn phát sinh — {chon_ct}",
            username,
            [COT_DU_NO_QH, COT_TONG_DU_NO],
            "KSD_NQH",
            key="ks_nqh_pdf",
            readonly=readonly,
        )


def render_to_sai_so_tv(
    cache: dict[str, Any],
    pgd_chon: str,
    username: str,
    readonly: bool,
) -> None:
    """Tổ có số thành viên không đúng quy định (< DUOI_TV hoặc > TREN_TV)."""
    if "to_sai_tv" not in cache:
        cache["to_sai_tv"] = _tinh_to_sai_so_tv(cache["df_kh"])
        st.session_state["ks_cache"] = cache
    df_vi_pham, df_to_all = cache["to_sai_tv"]

    n_thieu = (
        int((df_vi_pham["Số_thành_viên"] < DUOI_TV).sum())
        if not df_vi_pham.empty
        else 0
    )
    n_vuot = (
        int((df_vi_pham["Số_thành_viên"] > TREN_TV).sum())
        if not df_vi_pham.empty
        else 0
    )

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(
            _ks_html_metric_card(
                "Tổng số tổ",
                fmt_so(len(df_to_all)),
                "Tổ TK&VV đủ điều kiện nhóm",
                "#E8F5E9",
                "#2E7D32",
                "#2E7D32",
            ),
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            _ks_html_metric_card(
                "Số tổ vi phạm",
                fmt_so(len(df_vi_pham)),
                f"Ngoài khoảng {DUOI_TV}–{TREN_TV} TV",
                "#FFEBEE",
                "#C62828",
                "#C62828",
            ),
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown(
            _ks_html_metric_card(
                f"Tổ thiếu TV (< {DUOI_TV})",
                fmt_so(n_thieu),
                "Dưới ngưỡng tối thiểu",
                "#FFF3E0",
                "#E65100",
                "#E65100",
            ),
            unsafe_allow_html=True,
        )
    with c4:
        st.markdown(
            _ks_html_metric_card(
                f"Tổ vượt TV (> {TREN_TV})",
                fmt_so(n_vuot),
                "Vượt ngưỡng tối đa",
                "#FCE4EC",
                "#AD1457",
                "#AD1457",
            ),
            unsafe_allow_html=True,
        )

    df_tong_hop_pgd = _tong_hop_vp_theo_pgd(df_vi_pham)
    st.markdown("**Tổng hợp Tổ TK&VV không đạt yêu cầu theo PGD**")
    if df_tong_hop_pgd is None or df_tong_hop_pgd.empty:
        st.info("Chưa có dữ liệu tổng hợp theo PGD.")
    else:
        df_hien_thi_tonghop = df_tong_hop_pgd.copy()
        styler_th = _style_tonghop_pgd(df_hien_thi_tonghop)
        _cols_fmt_th = [
            c
            for c in (
                "Tổng_dư_nợ",
                "Số_tổ_vi_phạm",
                "Tổ_thiếu_TV",
                "Tổ_vượt_TV",
            )
            if c in df_hien_thi_tonghop.columns
        ]
        if _cols_fmt_th:
            styler_th = styler_th.format(
                _fmt_so_cell,
                subset=_cols_fmt_th,
                na_rep="—",
            )
        hien_thi_dataframe_phan_trang(
            styler_th,
            key="ks_to_vp_th_pgd",
            height=280,
        )
        col_xl_th, col_pdf_th = st.columns([1, 1])
        cols_pdf_th = [
            c for c in ("Tổng_dư_nợ",) if c in df_tong_hop_pgd.columns
        ]
        with col_xl_th:
            _xuat_excel_btn(
                df_tong_hop_pgd,
                "KSD_TO_TONGHOP",
                key="xl_to_tonghop",
                readonly=readonly,
            )
        with col_pdf_th:
            _xuat_pdf_btn(
                df_tong_hop_pgd,
                "TỔNG HỢP TỔ TK&VV KHÔNG ĐẠT YÊU CẦU THEO PGD",
                username,
                cols_pdf_th,
                "KSD_TO_TONGHOP",
                key="pdf_to_tonghop",
                readonly=readonly,
            )

    if df_vi_pham.empty:
        st.success("Không có tổ vi phạm số thành viên.")
        return

    df_vp_scope = df_vi_pham
    if pgd_chon != "Tất cả" and COT_TEN_PGD in df_vi_pham.columns:
        df_vp_scope = df_vi_pham[df_vi_pham[COT_TEN_PGD] == pgd_chon].copy()

    if df_vp_scope.empty:
        st.info("Không có tổ vi phạm trong phạm vi PGD đã lọc.")
        return

    if pgd_chon != "Tất cả" and COT_TEN_PGD in df_vp_scope.columns:
        chon_detail = pgd_chon
    else:
        ds_pgd = sorted(
            str(x) for x in df_vp_scope[COT_TEN_PGD].dropna().unique()
        )
        chon_detail = st.selectbox(
            "Chi tiết theo PGD",
            options=ds_pgd,
            key="ks_to_saitv_chon_pgd",
        )

    df_hien_thi = df_vp_scope[
        df_vp_scope[COT_TEN_PGD] == chon_detail
    ].copy()

    cols_hi = [
        c
        for c in [
            COT_TEN_PGD,
            COT_TEN_XA,
            COT_TEN_THON,
            COT_DVUT,
            "Tên tổ",
            "Số_thành_viên",
            "Tổng_dư_nợ",
            "Dư_nợ_TH",
            "Dư_nợ_QH",
            "Lãi tồn",
            "Mô tả",
        ]
        if c in df_hien_thi.columns
    ]
    df_out = df_hien_thi[cols_hi]

    key_detail = str(chon_detail).replace(" ", "_").replace("/", "-")
    key_pgd_f = str(pgd_chon).replace(" ", "_").replace("/", "-")
    st.markdown(
        f"**Chi tiết — {pgd_chon} ({len(df_hien_thi)} tổ)**"
    )
    if df_out.empty:
        st.info("Không có dòng chi tiết.")
    else:
        df_hien_thi_chitiet = df_hien_thi.copy()
        df_view = df_hien_thi_chitiet[cols_hi]
        styler_ct = df_view.style.apply(_style_chitiet, axis=1)
        _cols_fmt_ct = [
            c
            for c in (
                "Tổng_dư_nợ",
                "Dư_nợ_TH",
                "Dư_nợ_QH",
                "Lãi tồn",
                "Số_thành_viên",
            )
            if c in df_view.columns
        ]
        if _cols_fmt_ct:
            styler_ct = styler_ct.format(
                _fmt_so_cell,
                subset=_cols_fmt_ct,
                na_rep="—",
            )
        hien_thi_dataframe_phan_trang(
            styler_ct,
            key=f"dt_chitiet_{key_pgd_f}_{key_detail}",
            height=400,
        )

    cols_pdf_ct = [
        c
        for c in ("Tổng_dư_nợ", "Dư_nợ_TH", "Dư_nợ_QH")
        if c in df_hien_thi.columns
    ]

    col_xl, col_pdf = st.columns([1, 1])
    _key_ct_xp = f"{key_pgd_f}_{key_detail}"
    with col_xl:
        _xuat_excel_btn(
            df_hien_thi,
            "KSD_TO_SAITV",
            key=f"xl_to_saitv_{_key_ct_xp}",
            readonly=readonly,
        )
    with col_pdf:
        _xuat_pdf_btn(
            df_hien_thi,
            f"TỔ TK&VV KHÔNG ĐẠT YÊU CẦU — {str(pgd_chon).upper()}",
            username,
            cols_pdf_ct,
            "KSD_TO_SAITV",
            key=f"pdf_to_saitv_{_key_ct_xp}",
            readonly=readonly,
        )


def render_gia_han_vuot(
    cache: dict[str, Any],
    pgd_chon: str,
    username: str,
    readonly: bool,
) -> None:
    """Món vay có ngày ĐH sau gia hạn vượt thời gian GH tối đa theo chương trình."""
    if "gia_han_vuot" not in cache:
        cache["gia_han_vuot"] = _tinh_gia_han_vuot(cache["df_kh"])
        st.session_state["ks_cache"] = cache
    df_gv = cache["gia_han_vuot"]

    if df_gv is None or df_gv.empty:
        st.success("Không có món vay gia hạn vượt quy định.")
        return

    tong_dn_th = (
        pd.to_numeric(df_gv[COT_DU_NO_TH], errors="coerce").fillna(0).sum()
        if COT_DU_NO_TH in df_gv.columns
        else 0.0
    )
    so_pgd = (
        int(df_gv[COT_TEN_PGD].nunique())
        if COT_TEN_PGD in df_gv.columns
        else 0
    )

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(
            _ks_html_metric_card(
                "Tổng số vi phạm",
                fmt_so(len(df_gv)),
                "Số món",
                "#FFEBEE",
                "#C62828",
                "#C62828",
            ),
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            _ks_html_metric_card(
                "Tổng dư nợ",
                fmt_so(tong_dn_th),
                "Dư nợ trong hạn",
                "#FFF3E0",
                "#E65100",
                "#E65100",
            ),
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown(
            _ks_html_metric_card(
                "Số PGD có vi phạm",
                fmt_so(so_pgd),
                "Đơn vị",
                "#E8F5E9",
                "#2E7D32",
                "#2E7D32",
            ),
            unsafe_allow_html=True,
        )

    df_th = _tong_hop_ghv_theo_pgd(df_gv)
    st.markdown("**Tổng hợp theo PGD**")
    if df_th is not None and not df_th.empty:
        styler_th = (
            df_th.style.set_table_styles(
                [
                    {
                        "selector": "thead th",
                        "props": [
                            ("background-color", "#2E7D32"),
                            ("color", "white"),
                        ],
                    }
                ]
            )
            .apply(_style_ghv_tonghop_row, axis=1)
        )
        _cols_fmt_th = [c for c in ("Số_món", "Dư_nợ_TH") if c in df_th.columns]
        if _cols_fmt_th:
            styler_th = styler_th.format(
                _fmt_so_cell,
                subset=_cols_fmt_th,
                na_rep="—",
            )
        hien_thi_dataframe_phan_trang(
            styler_th,
            key="ks_ghv_th_pgd",
            height=280,
        )
    else:
        st.info("Chưa có dữ liệu tổng hợp theo PGD.")

    df_chi = df_gv.copy()
    if pgd_chon != "Tất cả" and COT_TEN_PGD in df_chi.columns:
        df_chi = df_chi[df_chi[COT_TEN_PGD] == pgd_chon].copy()

    st.markdown(f"**Chi tiết** ({len(df_chi)} dòng)")
    if df_chi.empty:
        st.info("Không có dòng chi tiết trong phạm vi PGD đã lọc.")
    else:
        df_view = df_chi.copy()
        styler_ct = (
            df_view.style.set_table_styles(
                [
                    {
                        "selector": "thead th",
                        "props": [
                            ("background-color", "#2E7D32"),
                            ("color", "white"),
                        ],
                    }
                ]
            )
            .apply(_style_ghv_chitiet_row, axis=1)
        )
        _cols_fmt_ct = [
            c for c in (COT_DU_NO_TH, COT_TONG_DU_NO) if c in df_view.columns
        ]
        if _cols_fmt_ct:
            styler_ct = styler_ct.format(
                _fmt_so_cell,
                subset=_cols_fmt_ct,
                na_rep="—",
            )
        hien_thi_dataframe_phan_trang(
            styler_ct,
            key="ks_ghv_ct",
            height=400,
        )

    st.caption(
        "⚠️ Lưu ý: Chương trình địa phương (nguồn vốn ĐP) đã loại trừ. "
        "TG khoanh nợ và nghĩa vụ quân sự chưa được tính vào ngày GH được phép."
    )

    col_xl, col_pdf = st.columns(2)
    with col_xl:
        _xuat_excel_btn(
            df_chi,
            "KSD_GH_VUOT",
            key="ks_ghv_xlsx_ghv",
            readonly=readonly,
            sheet_name="GH_Vuot",
        )
    with col_pdf:
        _xuat_pdf_btn(
            df_chi,
            "GIA HẠN VƯỢT QUY ĐỊNH",
            username,
            [COT_DU_NO_TH, COT_TONG_DU_NO],
            "KSD_GH_VUOT",
            key="ks_ghv_pdf_ghv",
            readonly=readonly,
        )


BAO_CAO_REGISTRY: dict[str, BaoCaoMeta] = {
    "khd_3thang": BaoCaoMeta(
        ma="khd_3thang",
        ten="3 tháng không hoạt động",
        nhom="rui_ro",
        mo_ta="Hồ sơ có lãi tồn > 3 tháng lãi dự thu",
        render_fn=render_3m_khd,
        cols_tien=[COT_TONG_DU_NO, COT_LAI_TON],
        prefix_pdf="KSD_KHD",
    ),
    "nqh_moi": BaoCaoMeta(
        ma="nqh_moi",
        ten="Nợ quá hạn phát sinh",
        nhom="rui_ro",
        mo_ta="Hồ sơ có dư nợ quá hạn > 0",
        render_fn=render_nqh,
        cols_tien=[COT_DU_NO_QH, COT_TONG_DU_NO],
        prefix_pdf="KSD_NQH",
    ),
    "to_sai_so_tv": BaoCaoMeta(
        ma="to_sai_so_tv",
        ten="Tổ có số thành viên không đúng quy định",
        nhom="kiem_toan",
        mo_ta="Tổ TK&VV có số thành viên < 5 hoặc > 60",
        render_fn=render_to_sai_so_tv,
        cols_tien=[COT_TONG_DU_NO, COT_DU_NO_TH, COT_DU_NO_QH],
        prefix_pdf="KSD_TO_SAITV",
    ),
    "gia_han_vuot": BaoCaoMeta(
        ma="gia_han_vuot",
        ten="Gia hạn vượt quy định",
        nhom="kiem_toan",
        mo_ta=(
            "Món vay có ngày ĐH sau gia hạn vượt quá thời gian tối đa "
            "theo quy định từng chương trình. "
            "Không bao gồm chương trình nguồn vốn địa phương."
        ),
        render_fn=render_gia_han_vuot,
        cols_tien=[COT_TONG_DU_NO, COT_DU_NO_TH],
        prefix_pdf="KSD_GH_VUOT",
    ),
}
