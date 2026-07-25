"""Tab Tra cứu hồ sơ — nâng cao."""

from __future__ import annotations



import unicodedata

from typing import TYPE_CHECKING



import duckdb

import streamlit as st

import pandas as pd



from config import (

    COT_TEN_PGD, COT_MA_KH, COT_TEN_KH, COT_SO_KU,

    COT_NGAY_VAY, COT_NGAY_DH, COT_THOI_HAN, COT_LAI_SUAT,

    COT_MUC_VAY, COT_DU_NO_TH, COT_DU_NO_QH, COT_TONG_DU_NO,

    COT_TEN_CT, COT_TINH_TRANG, COT_DIA_CHI, COT_SDT, COT_GOC_TRA,

    COT_CMND, COT_NGAY_SINH, COT_NGAY_CAP_CMND, COT_NOI_CAP_CMND,

    COT_TEN_TO, COT_TEN_XA, COT_TEN_THON,

    COT_NGUON_VON, COT_MA_NHA_DAU_TU, COT_MA_CHUONG_TRINH,

    COT_TEN_HSSV, COT_TEN_VC,

    NGUON_VON_LABEL,

)

from utils import fmt_so, fmt_tien, vn, xuat_excel, hien_thi_dataframe_phan_trang

from pdf_service import nut_xuat_pdf



if TYPE_CHECKING:

    from streamlit.delta_generator import DeltaGenerator





# ═══════════════════════════════════════════════════════════════════════════════

# HELPERS

# ═══════════════════════════════════════════════════════════════════════════════



def _bo_dau(s: str) -> str:

    """Loại bỏ dấu tiếng Việt để tìm kiếm không phân biệt dấu."""

    if s is None:
        return ""

    text = str(s).strip().casefold().replace("đ", "d")

    text = unicodedata.normalize("NFD", text)

    text = "".join(c for c in text if unicodedata.category(c) != "Mn")

    return " ".join(text.split())





def _tim_mem(df: pd.DataFrame, cols: list[str], tu_khoa: str) -> pd.Series:

    """

    Tìm kiếm mềm: không phân biệt hoa/thường, có dấu/không dấu.

    

    Args:

        df: DataFrame chứa dữ liệu cần tìm

        cols: Danh sách tên cột cần tìm kiếm

        tu_khoa: Từ khóa tìm kiếm

    

    Returns:

        pd.Series boolean mask cho các dòng khớp từ khóa

    """

    kw = str(tu_khoa or "").strip().lower()

    kw_bdau = _bo_dau(tu_khoa)

    mask = pd.Series(False, index=df.index)

    if not kw:

        return mask

    for col in cols:

        if col not in df.columns:

            continue

        s_raw = df[col].fillna("").astype(str)

        s = s_raw.str.lower()

        # Bỏ dấu cho toàn cột, bao gồm cả Đ/đ -> D/d.

        s_bdau = s_raw.map(_bo_dau)

        mask |= s.str.contains(kw, regex=False, na=False)

        mask |= s_bdau.str.contains(kw_bdau, regex=False, na=False)

    return mask





def _xay_nq11_set(df_nq11: pd.DataFrame | None) -> set[str]:

    """

    Xây dựng tập hợp Số khế ước thuộc NQ11 có dư nợ > 0 (từ sao kê NQ11).

    

    Args:

        df_nq11: DataFrame sao kê NQ11

    

    Returns:

        Set chứa các Số khế ước có dư nợ NQ11 > 0

    """

    if df_nq11 is None or len(df_nq11) == 0:

        return set()

    col_ku = "Số khế ước"

    col_dno = "DNO NQ11"

    if col_ku not in df_nq11.columns or col_dno not in df_nq11.columns:

        return set()

    mask = pd.to_numeric(df_nq11[col_dno], errors="coerce").fillna(0) > 0

    return set(df_nq11.loc[mask, col_ku].astype(str).str.strip())





def _xay_gqvl_nq11_set(df_sk_gqvl: pd.DataFrame | None) -> set[str]:

    """

    Xây dựng tập hợp Số khế ước có ghi chú NQ11 từ file sao kê GQVL.

    Dùng để xác định nhãn NQ11 cho các món vay dư nợ = 0.

    

    Args:

        df_sk_gqvl: DataFrame sao kê GQVL

    

    Returns:

        Set chứa các Số khế ước có ghi chú NQ11

    """

    if df_sk_gqvl is None or len(df_sk_gqvl) == 0:

        return set()

    col_ku = "Số khế ước"

    col_nq = "NQ11"

    if col_ku not in df_sk_gqvl.columns or col_nq not in df_sk_gqvl.columns:

        return set()

    mask = df_sk_gqvl[col_nq].astype(str).str.strip() == "NQ11"

    return set(df_sk_gqvl.loc[mask, col_ku].astype(str).str.strip())



def _kiem_tra_nq11(

    so_ku: str,

    tong_du_no: float,

    nq11_so_ku_set: set[str],

    gqvl_nq11_set: set[str]

) -> bool:

    """

    Kiểm tra món vay có thuộc NQ11 không.

    

    Logic:

    - Nếu dư nợ > 0: so khớp với tập hợp từ sao kê NQ11 (DNO NQ11 > 0).

    - Nếu dư nợ = 0: so khớp với tập hợp từ sao kê GQVL (cột NQ11 = 'NQ11').

    

    Args:

        so_ku: Số khế ước cần kiểm tra

        tong_du_no: Tổng dư nợ hiện tại

        nq11_so_ku_set: Set Số KU từ sao kê NQ11 có dư nợ > 0

        gqvl_nq11_set: Set Số KU từ sao kê GQVL có ghi chú NQ11

    

    Returns:

        True nếu món vay thuộc NQ11

    """

    ku = str(so_ku).strip()

    if tong_du_no > 0:

        return ku in nq11_so_ku_set

    return ku in gqvl_nq11_set





def _nv_str(val) -> str:

    """Chuyển mã nguồn vốn thành tên hiển thị."""

    if pd.isna(val):

        return "—"

    return NGUON_VON_LABEL.get(val, NGUON_VON_LABEL.get(str(val), str(val)))





_NHOM_TRUONG = {

    "👤 Khách hàng": [

        "Họ tên khách hàng", "Mã khách hàng", "CMND/CCCD",

        COT_NGAY_SINH, COT_NGAY_CAP_CMND, COT_NOI_CAP_CMND,

        "Giới tính", "Số điện thoại", "Địa chỉ", "Dân tộc",

        "Tên HSSV", "Tên vợ/chồng",

    ],

    "📄 Khoản vay": [

        "Số khế ước", "Mã khế ước", "Ngày vay", "Ngày ĐH theo Gia hạn",

        "Ngày ĐH theo hợp đồng", "Ngày đáo hạn", "Thời hạn vay",

        "Lãi suất", "Mức vay", "Mã món vay", "Số tiền giải ngân",

    ],

    "💰 Dư nợ & Tài chính": [

        "Tổng dư nợ", "Dư nợ trong hạn", "Dư nợ quá hạn",

        "Dư nợ khoanh", "Gốc đã trả", "Lãi đã trả",

        "Lãi tồn", "Lãi DT trong tháng", "Lãi tồn TH",

        "Giải ngân trong năm", "Thu nợ trong năm",

    ],

    "📋 Đơn vị & Chương trình": [

        "Tên PGD", "Tên xã", "Tên thôn", "Tên ĐVUT", "Tên tổ",

        "Tên chương trình", "Mã chương trình", "Nguồn vốn",

        "Mã nhà đầu tư", "Tên cấp QLV",

    ],

    "⚙️ Trạng thái & Phân loại": [

        "Tình trạng món vay", "Phân loại", "Phân loại NV",

        "Ngày số liệu", "Ngày giao dịch gần nhất",

    ],

}





def _render_full_record(hs: pd.Series) -> None:

    """

    Hiển thị toàn bộ trường dữ liệu gốc của 1 hồ sơ,

    phân nhóm theo nghiệp vụ VBSP.

    """

    da_hien = set()

    nhom_con_lai = {}



    for ten_nhom, cac_cot in _NHOM_TRUONG.items():

        cac_cot_ton_tai = []

        for cot in cac_cot:

            tim = _tim_cot_trong_series(hs, cot)

            if tim:

                cac_cot_ton_tai.append(tim)

                da_hien.add(tim)

        if cac_cot_ton_tai:

            nhom_con_lai[ten_nhom] = cac_cot_ton_tai



    # Thu thập các cột chưa phân nhóm

    cac_cot_khac = [c for c in hs.index if c not in da_hien and pd.notna(hs[c]) and str(hs[c]).strip() not in ("", "nan")]

    if cac_cot_khac:

        nhom_con_lai["📋 Khác"] = cac_cot_khac



    for ten_nhom, cac_cot in nhom_con_lai.items():

        st.markdown(f"**{ten_nhom}**")

        rows = []

        for cot in cac_cot:

            v = hs.get(cot)

            if pd.isna(v) or str(v).strip() in ("", "nan"):

                continue

            s = str(v).strip()

            if len(s) > 80:

                s = s[:80] + "..."

            rows.append((cot, s))



        if rows:

            html = '<div style="display:grid;grid-template-columns:140px 1fr;gap:2px 10px;font-size:0.82rem;padding:4px 0 10px 8px">'

            for lbl, val in rows:

                html += (

                    f'<span style="color:#94A3B8;font-weight:500">{lbl}</span>'

                    f'<span style="color:#E0E6ED">{val}</span>'

                )

            html += "</div>"

            st.markdown(html, unsafe_allow_html=True)





def _tim_cot_trong_series(hs: pd.Series, cot_mong_muon: str) -> str | None:

    """Tìm cột trong Series: khớp chính xác trước, sau đó fuzzy."""

    if cot_mong_muon in hs.index:

        return cot_mong_muon

    kl = cot_mong_muon.lower().replace(" ", "").replace("_", "")

    for c in hs.index:

        cl = c.lower().replace(" ", "").replace("_", "")

        if cl == kl or cot_mong_muon.lower() in c.lower() or c.lower() in cot_mong_muon.lower():

            return c

    return None





# ═══════════════════════════════════════════════════════════════════════════════

# CARD CHI TIẾT

# ═══════════════════════════════════════════════════════════════════════════════



def _render_card(

    hs: pd.Series,

    df_nq11: pd.DataFrame | None,

    nq11_so_ku_set: set[str],

    gqvl_nq11_set: set[str]

) -> None:

    """

    Hiển thị card chi tiết hồ sơ khách hàng.

    

    Args:

        hs: Series chứa thông tin một hồ sơ

        df_nq11: DataFrame sao kê NQ11 để hiển thị chi tiết

        nq11_so_ku_set: Set Số KU NQ11 (dư nợ > 0)

        gqvl_nq11_set: Set Số KU NQ11 (dư nợ = 0)

    """

    so_ku       = str(hs.get(COT_SO_KU, "")).strip()

    tong_du_no  = float(hs.get(COT_TONG_DU_NO, 0) or 0)

    nq11        = _kiem_tra_nq11(so_ku, tong_du_no, nq11_so_ku_set, gqvl_nq11_set)

    ten_ct  = str(hs.get(COT_TEN_CT, ""))

    dqh     = float(hs.get(COT_DU_NO_QH, 0) or 0)

    nv_val  = hs.get(COT_NGUON_VON)

    la_dp   = str(nv_val) in ("2", "2.0") or nv_val == 2



    # Tiêu đề

    ten_kh   = str(hs.get(COT_TEN_KH, "—"))

    badge_nq = ' <span style="background:#1B5E20;color:#81C784;border:1px solid #2E7D32;border-radius:10px;padding:1px 7px;font-size:.75rem;font-weight:700">✨ NQ11</span>' if nq11 else ""

    badge_qh = ' <span style="background:#2D0D14;color:#EF9A9A;border:1px solid #C62828;border-radius:10px;padding:1px 7px;font-size:.75rem;font-weight:700">⚠️ Quá hạn</span>' if dqh > 0 else ""

    border   = "#EF5350" if dqh > 0 else "#42A5F5"



    st.markdown(

        f'<div style="background:#1E2130;border-radius:12px;padding:14px 18px;'

        f'border-left:4px solid {border};margin-bottom:6px">'

        f'<span style="font-size:1.05rem;font-weight:700">{ten_kh}</span>'

        f'{badge_nq}{badge_qh}</div>',

        unsafe_allow_html=True,

    )



    c1, c2, c3 = st.columns(3)



    with c1:

        st.markdown("**👤 Khách hàng**")

        for lbl, col in [("Mã KH", COT_MA_KH), ("CMND/CCCD", COT_CMND),

                          ("SĐT", COT_SDT), ("Địa chỉ", COT_DIA_CHI),

                          ("Tổ", COT_TEN_TO), ("Xã", COT_TEN_XA), ("PGD", COT_TEN_PGD)]:

            v = hs.get(col)

            if pd.notna(v) and str(v).strip() not in ("", "nan"):

                st.caption(f"**{lbl}:** {v}")

        for lbl, col in [("Tên HSSV", COT_TEN_HSSV), ("Vợ/chồng", COT_TEN_VC)]:

            v = hs.get(col)

            if pd.notna(v) and str(v).strip() not in ("", "nan"):

                st.caption(f"**{lbl}:** {v}")



    with c2:

        st.markdown("**📄 Khoản vay**")

        ct_html = ten_ct + (badge_nq if nq11 else "")

        st.markdown(f"**Chương trình:** {ct_html}", unsafe_allow_html=True)

        nv_color = "#FFB74D" if la_dp else "#42A5F5"

        st.markdown(

            f'**Nguồn vốn:** <span style="color:{nv_color};font-weight:600">{_nv_str(nv_val)}</span>',

            unsafe_allow_html=True,

        )

        if la_dp:

            ma_ndt = hs.get(COT_MA_NHA_DAU_TU)

            if pd.notna(ma_ndt) and str(ma_ndt).strip() not in ("", "nan"):

                st.caption(f"**Mã NĐT:** {ma_ndt}")

        for lbl, col in [("Số khế ước", COT_SO_KU), ("Ngày vay", COT_NGAY_VAY),

                          ("Đến hạn", COT_NGAY_DH), ("Thời hạn", COT_THOI_HAN),

                          ("Lãi suất", COT_LAI_SUAT), ("Tình trạng", COT_TINH_TRANG)]:

            v = hs.get(col)

            if pd.notna(v) and str(v).strip() not in ("", "nan"):

                st.caption(f"**{lbl}:** {v}")

        v_mv = hs.get(COT_MUC_VAY)

        if pd.notna(v_mv):

            st.caption(f"**Mức vay:** {fmt_tien(v_mv)}")



    with c3:

        st.markdown("**💰 Dư nợ**")

        for lbl, col in [("Tổng dư nợ", COT_TONG_DU_NO),

                          ("Dư nợ trong hạn", COT_DU_NO_TH),

                          ("Gốc đã trả", COT_GOC_TRA)]:

            v = hs.get(col)

            if pd.notna(v):

                st.caption(f"**{lbl}:** {fmt_tien(v)}")

        # NQH — tô đỏ

        if dqh > 0:

            st.markdown(

                f'<div style="background:#2D0D14;border-radius:8px;padding:6px 10px;margin-top:4px">'

                f'⚠️ <b>Dư nợ quá hạn:</b> '

                f'<span style="color:#EF9A9A;font-weight:700">{fmt_tien(dqh)}</span></div>',

                unsafe_allow_html=True,

            )

        else:

            st.caption("**Dư nợ quá hạn:** —")



    # ── Xem toàn bộ hồ sơ gốc ─────────────────────────────────────────

    with st.expander("📋 Xem toàn bộ hồ sơ gốc (tất cả trường dữ liệu)", expanded=False):

        _render_full_record(hs)



    # Chi tiết NQ11 từ file NQ11

    if nq11 and df_nq11 is not None and len(df_nq11):

        so_ku = str(hs.get(COT_SO_KU, ""))

        row_nq = None

        for col_nq in ["Số khế ước", "Mã khách hàng"]:

            if col_nq in df_nq11.columns:

                val_tim = so_ku if col_nq == "Số khế ước" else str(hs.get(COT_MA_KH, ""))

                tim = df_nq11[df_nq11[col_nq].astype(str) == val_tim]

                if not tim.empty:

                    row_nq = tim.iloc[0]

                    break

        if row_nq is not None:

            with st.expander("✨ Chi tiết số dư NQ11", expanded=False):

                nc1, nc2 = st.columns(2)

                for i, (lbl, col) in enumerate([

                    ("Dư nợ NQ11", "DNO NQ11"),

                    ("Nợ trong hạn", "Nợ trong hạn"),

                    ("Nợ quá hạn", "Nợ quá hạn"),

                    ("Đến hạn sau cùng", "Đến hạn sau cùng"),

                ]):

                    if col in row_nq.index:

                        cell = nc1 if i % 2 == 0 else nc2

                        v = row_nq[col]

                        cell.metric(lbl, fmt_tien(v) if col != "Đến hạn sau cùng" else str(v))





# ═══════════════════════════════════════════════════════════════════════════════

# BẢNG RÚT GỌN

# ═══════════════════════════════════════════════════════════════════════════════



def _render_bang(

    df_kq: pd.DataFrame,

    nq11_so_ku_set: set[str],

    gqvl_nq11_set: set[str]

) -> None:

    """

    Hiển thị bảng rút gọn kết quả tra cứu.

    

    Args:

        df_kq: DataFrame kết quả tìm kiếm

        nq11_so_ku_set: Set Số KU NQ11 (dư nợ > 0)

        gqvl_nq11_set: Set Số KU NQ11 (dư nợ = 0)

    """

    COLS_HIEN = [

        COT_TEN_KH, COT_CMND, COT_TEN_CT, COT_TONG_DU_NO,

        COT_DU_NO_QH, COT_TEN_TO, COT_TEN_XA, COT_NGAY_DH,

        COT_NGUON_VON, COT_MA_NHA_DAU_TU

    ]

    cols = [c for c in COLS_HIEN if c in df_kq.columns]

    df_hien = df_kq[cols].copy()



    # Thêm badge NQ11 vào tên chương trình

    if COT_TEN_CT in df_kq.columns and COT_SO_KU in df_kq.columns:

        def them_badge(row: pd.Series) -> str:

            ten = str(row[COT_TEN_CT])

            so_ku = str(row[COT_SO_KU]).strip()

            tong_dn = (float(row.get(COT_TONG_DU_NO, 0) or 0)
                if COT_TONG_DU_NO in row.index else 0.0)

            la_nq11 = _kiem_tra_nq11(so_ku, tong_dn, nq11_so_ku_set, gqvl_nq11_set)

            return ten + (" ✨NQ11" if la_nq11 else "")

        df_hien[COT_TEN_CT] = df_kq.apply(them_badge, axis=1)



    # Xây dựng column_config cho st.dataframe

    column_config: dict[str, st.column_config.Column] = {}

    

    if COT_TONG_DU_NO in df_hien.columns:

        column_config[COT_TONG_DU_NO] = st.column_config.NumberColumn(

            "Tổng dư nợ",

            format="%.0f",

            help="Tổng dư nợ hiện tại"

        )

    

    if COT_DU_NO_QH in df_hien.columns:

        column_config[COT_DU_NO_QH] = st.column_config.NumberColumn(

            "Dư nợ quá hạn",

            format="%.0f",

            help="Dư nợ quá hạn (sẽ tô đỏ nếu > 0)"

        )

    

    if COT_MA_NHA_DAU_TU in df_hien.columns:

        column_config[COT_MA_NHA_DAU_TU] = st.column_config.TextColumn("Mã NĐT")

    

    # Highlight NQH đỏ bằng style

    def hl(row: pd.Series) -> list[str]:

        styles = [""] * len(row)

        if COT_DU_NO_QH in df_hien.columns:

            idx = list(df_hien.columns).index(COT_DU_NO_QH)

            try:

                raw = df_kq.iloc[row.name][COT_DU_NO_QH]

                if float(raw) > 0:

                    styles[idx] = "color:#EF9A9A;font-weight:700"

            except Exception:

                pass

        return styles



    hien_thi_dataframe_phan_trang(

        df_hien.reset_index(drop=True).style.apply(hl, axis=1),

        key="tracuu_ket_qua",

        column_config=column_config,

        height=min(420, 60 + len(df_hien) * 36),

    )





# ═══════════════════════════════════════════════════════════════════════════════

# ENTRY POINT

# ═══════════════════════════════════════════════════════════════════════════════



def render(tab: DeltaGenerator | None = None, **kwargs: dict) -> None:

    """

    Render tab Tra cứu hồ sơ.



    Args:

        tab: Streamlit DeltaGenerator cho tab này

        **kwargs: Chứa df (HSTD), df_nq11 (sao kê NQ11), df_sk_gqvl (sao kê GQVL)

    """

    df          = kwargs.get("df")

    df_nq11     = kwargs.get("df_nq11")

    df_sk_gqvl  = kwargs.get("df_sk_gqvl")

    hstd_path   = kwargs.get("hstd_path")

    ts_hstd     = kwargs.get("ts_hstd", 0.0)

    pgd_user    = kwargs.get("pgd_user")          # None = CN role



    # Tập hợp Số khế ước NQ11 có dư nợ > 0 (từ sao kê NQ11)

    nq11_so_ku_set  = _xay_nq11_set(df_nq11)

    # Tập hợp Số khế ước có ghi chú NQ11 trong sao kê GQVL (dùng cho món dư nợ = 0)

    gqvl_nq11_set   = _xay_gqvl_nq11_set(df_sk_gqvl)



    # Chỉ giữ cột cần thiết → tiết kiệm RAM.

    # CN role: đọc thẳng từ Parquet (bỏ qua active_only filter) để tra cứu được

    # cả khách hàng đã tất toán (Tổng dư nợ = 0).

    # PGD role: dùng df đã lọc theo PGD — không mở rộng phạm vi dữ liệu.

    COLS_CAN = [

        COT_TEN_PGD, COT_MA_KH, COT_TEN_KH, COT_CMND,

        COT_NGAY_SINH, COT_NGAY_CAP_CMND, COT_NOI_CAP_CMND,

        COT_SO_KU, COT_SDT, COT_DIA_CHI, COT_TEN_TO, COT_TEN_XA, COT_TEN_THON,

        COT_TEN_HSSV, COT_TEN_VC,

        COT_NGAY_VAY, COT_NGAY_DH, COT_THOI_HAN, COT_LAI_SUAT,

        COT_MUC_VAY, COT_DU_NO_TH, COT_DU_NO_QH, COT_TONG_DU_NO, COT_GOC_TRA,

        COT_TEN_CT, COT_MA_CHUONG_TRINH, COT_TINH_TRANG,

        COT_NGUON_VON, COT_MA_NHA_DAU_TU,

    ]

    _use_parquet = hstd_path and not pgd_user   # chỉ CN role mới đọc full parquet

    _tc_cache_key = f"tc_df_{ts_hstd}"

    if _use_parquet and st.session_state.get("_tc_cache_key") == _tc_cache_key:

        df_work = st.session_state["_tc_df_work"]

    elif _use_parquet:

        _schema = duckdb.query(

            f"SELECT column_name FROM (DESCRIBE SELECT * FROM read_parquet('{hstd_path}'))"

        ).df()["column_name"].tolist()

        _cols_exist = [c for c in COLS_CAN if c in _schema]

        _cols_sql = ", ".join(f'"{c}"' for c in _cols_exist)

        df_work = duckdb.query(

            f"SELECT {_cols_sql} FROM read_parquet('{hstd_path}')"

        ).df()

        st.session_state["_tc_df_work"] = df_work

        st.session_state["_tc_cache_key"] = _tc_cache_key

    else:

        df_work = df[[c for c in COLS_CAN if c in df.columns]].copy()



    _tab_ctx = tab if tab is not None else __import__('streamlit').container()

    with _tab_ctx:

        st.subheader("🔍 Tra cứu hồ sơ khách hàng")



        # ── Search box ──────────────────────────────────────────────────────

        sb1, sb2 = st.columns([5, 1])

        with sb1:

            tu_khoa = st.text_input(

                "keyword", label_visibility="collapsed",

                placeholder="🔍  Tên KH · CMND/CCCD · Số khế ước · Tên HSSV · Tên vợ/chồng...",

                key="tracuu_keyword",

            )

        with sb2:

            st.button("Tìm", type="primary", use_container_width=True, key="tracuu_btn_tim")



        # ── Filter buttons ──────────────────────────────────────────────────

        f_opts = ["Tất cả", "Nguồn TW", "Nguồn ĐP", "NQ11", "Quá hạn", "Mã NĐT"]

        if "tc_filter" not in st.session_state:

            st.session_state.tc_filter = "Tất cả"



        fc = st.columns(len(f_opts))

        for i, f in enumerate(f_opts):

            is_active = st.session_state.tc_filter == f

            label = f"**{f}**" if is_active else f

            if fc[i].button(label, key=f"tracuu_filter_btn_{i}", use_container_width=True):

                st.session_state.tc_filter = f

                st.rerun()

        active_filter = st.session_state.tc_filter

        st.divider()



        # ── Thực hiện tìm kiếm & lọc ───────────────────────────────────────

        if not tu_khoa.strip() and active_filter == "Tất cả":

            st.info("💡 Nhập từ khóa hoặc chọn bộ lọc nhanh bên trên.")

            return



        if tu_khoa.strip():

            COLS_TIM = [COT_TEN_KH, COT_CMND, COT_SO_KU,

                        COT_TEN_HSSV, COT_TEN_VC, COT_MA_KH]

            mask    = _tim_mem(df_work, COLS_TIM, tu_khoa)

            df_kq   = df_work[mask].copy()

        else:

            df_kq = df_work.copy()



        # Áp filter nhanh

        if active_filter == "Nguồn TW" and COT_NGUON_VON in df_kq.columns:

            df_kq = df_kq[df_kq[COT_NGUON_VON].astype(str).isin(["1","1.0"])]

        elif active_filter == "Nguồn ĐP" and COT_NGUON_VON in df_kq.columns:

            df_kq = df_kq[df_kq[COT_NGUON_VON].astype(str).isin(["2","2.0"])]

        elif active_filter == "NQ11" and COT_SO_KU in df_kq.columns:

            mask_ku = df_kq[COT_SO_KU].astype(str).str.strip()

            mask_dn_co = (df_kq[COT_TONG_DU_NO].fillna(0) > 0 if COT_TONG_DU_NO in df_kq.columns
                          else pd.Series(True, index=df_kq.index))

            mask_nq11 = ((mask_dn_co & mask_ku.isin(nq11_so_ku_set)) |
                         (~mask_dn_co & mask_ku.isin(gqvl_nq11_set)))

            df_kq = df_kq[mask_nq11]

        elif active_filter == "Quá hạn" and COT_DU_NO_QH in df_kq.columns:

            df_kq = df_kq[df_kq[COT_DU_NO_QH].fillna(0) > 0]

        elif active_filter == "Mã NĐT" and COT_MA_NHA_DAU_TU in df_kq.columns:

            df_kq = df_kq[df_kq[COT_MA_NHA_DAU_TU].notna() &

                          (df_kq[COT_MA_NHA_DAU_TU].astype(str).str.strip() != "")]



        # ── Kết quả ─────────────────────────────────────────────────────────

        if len(df_kq) == 0:

            st.warning("Không tìm thấy hồ sơ nào phù hợp.")

            return



        # Metrics tóm tắt

        n_qh   = int((df_kq[COT_DU_NO_QH].fillna(0) > 0).sum()) if COT_DU_NO_QH in df_kq.columns else 0

        if COT_SO_KU in df_kq.columns:

            _ku = df_kq[COT_SO_KU].astype(str).str.strip()

            _dn = (df_kq[COT_TONG_DU_NO].fillna(0) > 0 if COT_TONG_DU_NO in df_kq.columns
                   else pd.Series(True, index=df_kq.index))

            n_nq11 = int(((_dn & _ku.isin(nq11_so_ku_set)) |

                          (~_dn & _ku.isin(gqvl_nq11_set))).sum())

        else:

            n_nq11 = 0

        n_dp   = int(df_kq[COT_NGUON_VON].astype(str).isin(["2","2.0"]).sum()) if COT_NGUON_VON in df_kq.columns else 0



        m1, m2, m3, m4 = st.columns(4)

        m1.metric("Kết quả",  f"{fmt_so(len(df_kq))} kết quả")

        m2.metric("⚠️ Quá hạn", str(n_qh),

                  delta="cần xử lý" if n_qh > 0 else None, delta_color="inverse")

        m3.metric("✨ NQ11",    str(n_nq11))

        m4.metric("Vốn ĐP",    str(n_dp))



        # Chế độ xem

        mode = st.radio("Chế độ xem", ["📋 Bảng rút gọn", "🃏 Card chi tiết"],

                        horizontal=True, key="tracuu_mode")

        st.divider()



        if mode == "📋 Bảng rút gọn":

            _render_bang(df_kq, nq11_so_ku_set, gqvl_nq11_set)

            # Xem card từ bảng

            if len(df_kq) <= 200 and COT_TEN_KH in df_kq.columns:

                st.divider()

                st.markdown("**🔎 Xem chi tiết một hồ sơ**")

                opts = ((df_kq[COT_TEN_KH].astype(str) + "  —  " +
                         df_kq[COT_SO_KU].astype(str)) if COT_SO_KU in df_kq.columns
                        else df_kq[COT_TEN_KH].astype(str))

                chon = st.selectbox("Chọn hồ sơ", opts.tolist(), key="tracuu_select_ho_so")

                _render_card(df_kq.iloc[opts.tolist().index(chon)],

                             df_nq11, nq11_so_ku_set, gqvl_nq11_set)



        else:  # Card chi tiết

            if len(df_kq) > 20:

                st.warning(f"Có {fmt_so(len(df_kq))} kết quả — hiển thị 20 hồ sơ đầu. "

                           "Thu hẹp từ khóa để xem chính xác hơn.")

                df_kq = df_kq.head(20)

            for i in range(len(df_kq)):

                _render_card(df_kq.iloc[i], df_nq11, nq11_so_ku_set, gqvl_nq11_set)

                if i < len(df_kq) - 1:

                    st.divider()



        # ── Xuất Excel / PDF ──

        st.divider()

        cols_xuat = st.columns([1, 1, 5])

        with cols_xuat[0]:

            if st.button("📥 Xuất Excel", key="tracuu_btn_xuat_excel", use_container_width=True, type="primary"):

                sheets = {"Kết quả tra cứu": df_kq}

                excel_bytes = xuat_excel(sheets)

                st.session_state["_excel_tracuu_bytes"] = excel_bytes

                st.session_state["_excel_tracuu_ten"] = f"tra_cuu_{len(df_kq)}_ket_qua.xlsx"



        if st.session_state.get("_excel_tracuu_bytes"):

            st.download_button(

                "⬇ Tải Excel",

                data=st.session_state["_excel_tracuu_bytes"],

                file_name=st.session_state["_excel_tracuu_ten"],

                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",

                key="tracuu_dl_excel",

            )



        with cols_xuat[1]:

            nut_xuat_pdf(

                df_kq,

                "Kết quả tra cứu hồ sơ vay vốn",

                st.session_state.get("txt_username", "unknown"),

                cols_tien=[c for c in df_kq.columns if "tiền" in c.lower() or "dư nợ" in c.lower() or "số tiền" in c.lower() or "gn_" in c.lower() or "tn_" in c.lower()],

                prefix_file="TraCuu",

                key="tracuu_xuat_pdf",

            )

