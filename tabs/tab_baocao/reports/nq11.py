"""Báo cáo NQ11 — tổng quan, cơ cấu, địa bàn và chi tiết khoản vay."""
from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd
import plotly.express as px
import streamlit as st

from auth import la_phan_he_pgd
from config import (
    COT_DNO_NQ11,
    COT_NGUON_VON,
    COT_NQ11_DEN_HAN_SC,
    COT_NQ11_MA_KH,
    COT_NQ11_NGAY_BC,
    COT_NQ11_NO_QH,
    COT_NQ11_NO_TH,
    COT_NQ11_TEN_KH,
    COT_SDT,
    COT_SO_KU,
    COT_TEN_CT,
    COT_TEN_PGD,
    COT_TEN_XA,
)
from utils import fmt_so, hien_thi_dataframe_phan_trang, vn

from ..components.export_panel import render_export_panel
from ..components.inline_filter import (
    render_inline_filter,
    render_nguon_von_filter,
    render_quick_search,
)
from ..components.sticky_table import render_bang_chi_tiet_html

if TYPE_CHECKING:
    from streamlit.delta_generator import DeltaGenerator


_NHOM_KHONG_XAC_DINH = "Chưa xác định"
_COT_SO_KU_DEM = "_nq11_so_ku_dem"
_COT_MA_KH_DEM = "_nq11_ma_kh_dem"
_GIA_TRI_MA_RONG = {"", "nan", "none", "null", "<na>"}


def _tap_so_khe_uoc(values) -> set[str]:
    """Chuẩn hóa một tập Số khế ước để đối chiếu giữa hai nguồn."""
    if values is None:
        return set()
    result: set[str] = set()
    for value in values:
        if pd.isna(value):
            continue
        if isinstance(value, float) and value.is_integer():
            text = str(int(value))
        else:
            text = str(value).strip()
        if text and text.casefold() not in _GIA_TRI_MA_RONG:
            result.add(text)
    return result


def _doi_chieu_so_khe_uoc_nq11(
    df_hstd_full: pd.DataFrame | None,
    nq11_ids,
) -> dict[str, int | list[str]]:
    """Đối chiếu danh sách NQ11 với toàn bộ HSTD, kể cả món đã tất toán."""
    ids_nq11 = _tap_so_khe_uoc(nq11_ids)
    ids_hstd = (
        _tap_so_khe_uoc(df_hstd_full[COT_SO_KU])
        if df_hstd_full is not None
        and not df_hstd_full.empty
        and COT_SO_KU in df_hstd_full.columns
        else set()
    )
    chua_khop = sorted(ids_nq11 - ids_hstd)
    return {
        "tong_nq11": len(ids_nq11),
        "da_khop": len(ids_nq11) - len(chua_khop),
        "chua_khop": chua_khop,
    }


def _render_doi_chieu_nq11(ctx, doi_chieu: dict | None) -> None:
    """Hiển thị trạng thái và danh sách khế ước NQ11 chưa có trong HSTD."""
    if not doi_chieu or not doi_chieu.get("tong_nq11"):
        return

    tong_nq11 = int(doi_chieu["tong_nq11"])
    da_khop = int(doi_chieu["da_khop"])
    chua_khop = list(doi_chieu.get("chua_khop") or [])
    if not chua_khop:
        ctx.success(
            f"✅ Đối chiếu nguồn NQ11 ↔ HSTD: đã khớp đủ "
            f"**{fmt_so(da_khop)}/{fmt_so(tong_nq11)} số khế ước**."
        )
        return

    ctx.warning(
        f"⚠️ Đối chiếu nguồn NQ11 ↔ HSTD: đã khớp "
        f"**{fmt_so(da_khop)}/{fmt_so(tong_nq11)} số khế ước**; còn "
        f"**{fmt_so(len(chua_khop))} số chưa tìm thấy trong HSTD**."
    )
    with ctx.expander(f"🔎 Xem {fmt_so(len(chua_khop))} số khế ước chưa khớp"):
        ctx.dataframe(
            pd.DataFrame({"Số khế ước chưa có trong HSTD": chua_khop}),
            hide_index=True,
            width="stretch",
            height=min(420, 38 + 35 * min(len(chua_khop), 10)),
        )
        ctx.caption(
            "Kiểm tra lại định dạng Số khế ước, kỳ HSTD đang dùng hoặc upload/merge "
            "HSTD mới nhất. Các món đã tất toán vẫn được tính là khớp nếu còn trong HSTD đầy đủ."
        )


def _chuan_bi_nq11(df: pd.DataFrame | None) -> pd.DataFrame:
    """Chuẩn hóa NQ11 và chỉ giữ một dòng cho mỗi khế ước hợp lệ."""
    if df is None or df.empty:
        return pd.DataFrame() if df is None else df.copy()

    out = df.copy()
    for col in (COT_DNO_NQ11, COT_NQ11_NO_TH, COT_NQ11_NO_QH):
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0)

    if COT_SO_KU in out.columns:
        so_ku = out[COT_SO_KU].astype("string").str.strip()
        hop_le = so_ku.notna() & ~so_ku.str.lower().isin(
            {"", "nan", "none", "null", "<na>"}
        )
        out = out.loc[hop_le].copy()
        out[COT_SO_KU] = so_ku.loc[hop_le]
        out = out.drop_duplicates(subset=[COT_SO_KU], keep="first")
        out[_COT_SO_KU_DEM] = out[COT_SO_KU]
    else:
        out[_COT_SO_KU_DEM] = out.index.astype(str)

    if COT_NQ11_MA_KH in out.columns:
        ma_kh = out[COT_NQ11_MA_KH].astype("string").str.strip()
        ma_kh = ma_kh.mask(
            ma_kh.str.lower().isin({"", "nan", "none", "null", "<na>"})
        )
        out[_COT_MA_KH_DEM] = ma_kh
    else:
        out[_COT_MA_KH_DEM] = out[_COT_SO_KU_DEM]
    return out.reset_index(drop=True)


def _fmt_df_trieu(df: pd.DataFrame) -> pd.DataFrame:
    """Format cột tiền sang triệu đồng."""
    d = df.copy()
    tien_cols = [
        COT_DNO_NQ11,
        COT_NQ11_NO_TH,
        COT_NQ11_NO_QH,
        "Dư nợ NQ11",
        "Nợ trong hạn",
        "Nợ quá hạn",
        "DNO_NQ11",
        "Nợ_trong_hạn",
        "Nợ_quá_hạn",
    ]
    for col in tien_cols:
        if col in d.columns:
            d[col] = pd.to_numeric(d[col], errors="coerce").apply(
                lambda x: vn(x / 1_000_000, 0) if pd.notna(x) else "—"
            )
    return d


def _tinh_chi_so_nq11(df: pd.DataFrame) -> dict[str, float | int]:
    """Tính KPI từ đúng phạm vi NQ11 đang hiển thị."""
    if df is None or df.empty:
        return {
            "so_mon": 0,
            "so_kh": 0,
            "du_no": 0.0,
            "no_qh": 0.0,
            "so_mon_qh": 0,
            "ty_le_qh": 0.0,
            "du_no_bq_mon": 0.0,
        }

    du_no = float(df[COT_DNO_NQ11].sum()) if COT_DNO_NQ11 in df.columns else 0.0
    no_qh = float(df[COT_NQ11_NO_QH].sum()) if COT_NQ11_NO_QH in df.columns else 0.0
    so_mon = int(df[_COT_SO_KU_DEM].nunique())
    so_kh = int(df[_COT_MA_KH_DEM].nunique())
    so_mon_qh = (
        int(df.loc[df[COT_NQ11_NO_QH] > 0, _COT_SO_KU_DEM].nunique())
        if COT_NQ11_NO_QH in df.columns
        else 0
    )
    return {
        "so_mon": so_mon,
        "so_kh": so_kh,
        "du_no": du_no,
        "no_qh": no_qh,
        "so_mon_qh": so_mon_qh,
        "ty_le_qh": no_qh / du_no * 100 if du_no > 0 else 0.0,
        "du_no_bq_mon": du_no / so_mon if so_mon > 0 else 0.0,
    }


def _tao_tong_hop_nq11(df: pd.DataFrame, cot_nhom: str) -> pd.DataFrame:
    """Tổng hợp NQ11 theo một chiều, bảo toàn số tiền và nhóm rỗng."""
    cot_ket_qua = [
        cot_nhom,
        "Số KH",
        "Số món",
        "Dư nợ NQ11",
        "Nợ trong hạn",
        "Nợ quá hạn",
        "Tỷ lệ QH (%)",
        "Tỷ trọng (%)",
    ]
    if df is None or df.empty or cot_nhom not in df.columns:
        return pd.DataFrame(columns=cot_ket_qua)

    out = df.copy()
    nhom = out[cot_nhom].astype("string").str.strip()
    out[cot_nhom] = nhom.mask(nhom.isna() | nhom.eq(""), _NHOM_KHONG_XAC_DINH)

    agg = {
        "Số KH": (_COT_MA_KH_DEM, "nunique"),
        "Số món": (_COT_SO_KU_DEM, "nunique"),
        "Dư nợ NQ11": (COT_DNO_NQ11, "sum"),
    }
    if COT_NQ11_NO_TH in out.columns:
        agg["Nợ trong hạn"] = (COT_NQ11_NO_TH, "sum")
    if COT_NQ11_NO_QH in out.columns:
        agg["Nợ quá hạn"] = (COT_NQ11_NO_QH, "sum")

    result = out.groupby(cot_nhom, dropna=False).agg(**agg).reset_index()
    for col in ("Nợ trong hạn", "Nợ quá hạn"):
        if col not in result.columns:
            result[col] = 0.0
    result["Tỷ lệ QH (%)"] = (
        result["Nợ quá hạn"]
        / result["Dư nợ NQ11"].replace(0, float("nan"))
        * 100
    ).fillna(0)
    tong_du_no = float(result["Dư nợ NQ11"].sum())
    result["Tỷ trọng (%)"] = (
        result["Dư nợ NQ11"] / tong_du_no * 100 if tong_du_no > 0 else 0.0
    )
    return (
        result[cot_ket_qua]
        .sort_values("Dư nợ NQ11", ascending=False)
        .reset_index(drop=True)
    )


def _ngay_bao_cao(df: pd.DataFrame) -> str:
    """Lấy ngày báo cáo mới nhất, trả nhãn Việt Nam an toàn."""
    if COT_NQ11_NGAY_BC not in df.columns:
        return "chưa xác định"
    ngay = pd.to_datetime(df[COT_NQ11_NGAY_BC], dayfirst=True, errors="coerce")
    if ngay.notna().any():
        return ngay.max().strftime("%d/%m/%Y")
    return "chưa xác định"


def render_nq11(
    tab: DeltaGenerator | None = None,
    df_nq11: pd.DataFrame | None = None,
    df_hstd_full: pd.DataFrame | None = None,
    role: str = "",
    pgd_user: str = "",
    username: str = "",
    **kwargs,
) -> None:
    """Render báo cáo NQ11 theo luồng tổng quan → phân tích → chi tiết."""
    ctx = tab if tab is not None else st

    ctx.markdown("### 📑 Báo cáo Nghị quyết 11")
    doi_chieu = None
    if not la_phan_he_pgd(role) and df_hstd_full is not None:
        from data.hstd import doc_so_khe_uoc_nq11

        doi_chieu = _doi_chieu_so_khe_uoc_nq11(
            df_hstd_full,
            doc_so_khe_uoc_nq11(),
        )
        _render_doi_chieu_nq11(ctx, doi_chieu)

    if df_nq11 is None or df_nq11.empty:
        if doi_chieu and doi_chieu.get("tong_nq11"):
            ctx.error("❌ Chưa có món NQ11 nào khớp với HSTD hiện hành.")
        else:
            ctx.warning("⚠️ Chưa có dữ liệu NQ11.")
            ctx.info("Vui lòng upload file NQ11 qua tab Upload dữ liệu.")
        return

    df_nq11 = _chuan_bi_nq11(df_nq11)
    if df_nq11.empty or COT_DNO_NQ11 not in df_nq11.columns:
        ctx.warning("⚠️ Dữ liệu NQ11 không có khế ước/dư nợ hợp lệ.")
        return

    # NQ11 là các món có DNO NQ11 dương; các dòng 0 chỉ là dữ liệu nền của file nguồn.
    df_scope = df_nq11.loc[df_nq11[COT_DNO_NQ11] > 0].copy()
    if la_phan_he_pgd(role) and pgd_user and COT_TEN_PGD in df_scope.columns:
        df_scope = df_scope.loc[df_scope[COT_TEN_PGD].eq(pgd_user)].copy()
        if df_scope.empty:
            ctx.warning(f"⚠️ Không có dư nợ NQ11 của {pgd_user}.")
            return

    ctx.caption(
        f"Số liệu đến ngày **{_ngay_bao_cao(df_scope)}** · "
        "Đơn vị tiền hiển thị trong bảng: **triệu đồng**"
    )

    ctx.markdown("#### 🔎 Phạm vi báo cáo")
    filter_cols: list[str] = []
    if not la_phan_he_pgd(role) and COT_TEN_PGD in df_scope.columns:
        filter_cols.append(COT_TEN_PGD)
    filter_cols.extend(c for c in (COT_TEN_XA, COT_TEN_CT) if c in df_scope.columns)
    if filter_cols:
        df_scope = render_inline_filter(
            df_scope,
            filter_cols,
            key="nq11_scope",
            container=ctx,
        )
    if COT_NGUON_VON in df_scope.columns:
        df_scope = render_nguon_von_filter(df_scope, key="nq11_scope", container=ctx)
    if df_scope.empty:
        ctx.warning("⚠️ Không có món NQ11 phù hợp với bộ lọc hiện tại.")
        return

    chi_so = _tinh_chi_so_nq11(df_scope)
    c1, c2, c3, c4 = ctx.columns(4)
    c1.metric("Dư nợ NQ11", f"{vn(chi_so['du_no'] / 1e9, 1)} tỷ")
    c2.metric("Số món", fmt_so(chi_so["so_mon"]))
    c3.metric("Số khách hàng", fmt_so(chi_so["so_kh"]))
    c4.metric(
        "Tỷ lệ quá hạn",
        f"{vn(chi_so['ty_le_qh'], 3)}%",
        delta=f"{vn(chi_so['no_qh'] / 1e6, 0)} triệu đồng",
        delta_color="inverse",
    )
    ctx.caption(
        f"Bình quân **{vn(chi_so['du_no_bq_mon'] / 1e6, 1)} triệu đồng/món** · "
        f"Nợ trong hạn **{vn((chi_so['du_no'] - chi_so['no_qh']) / 1e9, 1)} tỷ đồng**"
    )

    if chi_so["no_qh"] > 0:
        ctx.warning(
            f"⚠️ Có **{fmt_so(chi_so['so_mon_qh'])} món quá hạn**, tổng "
            f"**{vn(chi_so['no_qh'] / 1e6, 0)} triệu đồng** trong phạm vi đang xem."
        )
    else:
        ctx.success("✅ Không có nợ quá hạn NQ11 trong phạm vi đang xem.")

    tab_tong_quan, tab_chuong_trinh, tab_dia_ban, tab_chi_tiet = ctx.tabs([
        "📊 Tổng quan",
        "📌 Theo chương trình",
        "🏢 Theo địa bàn",
        "📋 Chi tiết khoản vay",
    ])

    with tab_tong_quan:
        _render_tong_quan(df_scope)
    with tab_chuong_trinh:
        _render_tong_hop(
            ctx=st,
            df=df_scope,
            cot_nhom=COT_TEN_CT,
            username=username,
            key="ct",
        )
    with tab_dia_ban:
        _render_dia_ban(ctx=st, df=df_scope, role=role, username=username)
    with tab_chi_tiet:
        _render_chi_tiet(ctx=st, df=df_scope, username=username)


def _render_tong_quan(df: pd.DataFrame) -> None:
    """Biểu đồ cơ cấu dư nợ theo chương trình và địa bàn."""
    st.markdown("#### Cơ cấu dư nợ NQ11")
    cot_trai, cot_phai = st.columns(2)

    if COT_TEN_CT in df.columns:
        theo_ct = _tao_tong_hop_nq11(df, COT_TEN_CT).head(10).sort_values("Dư nợ NQ11")
        fig_ct = px.bar(
            theo_ct,
            x="Dư nợ NQ11",
            y=COT_TEN_CT,
            orientation="h",
            labels={"Dư nợ NQ11": "Dư nợ (đồng)", COT_TEN_CT: ""},
        )
        fig_ct.update_layout(
            height=360,
            margin=dict(l=8, r=8, t=36, b=8),
            showlegend=False,
        )
        cot_trai.markdown("**Theo chương trình**")
        cot_trai.plotly_chart(fig_ct, width="stretch", key="nq11_chart_ct")
    else:
        cot_trai.info("Không có dữ liệu chương trình.")

    cot_dia_ban = (
        COT_TEN_PGD
        if COT_TEN_PGD in df.columns and df[COT_TEN_PGD].nunique() > 1
        else COT_TEN_XA
    )
    if cot_dia_ban in df.columns:
        theo_dia_ban = (
            _tao_tong_hop_nq11(df, cot_dia_ban)
            .head(10)
            .sort_values("Dư nợ NQ11")
        )
        fig_db = px.bar(
            theo_dia_ban,
            x="Dư nợ NQ11",
            y=cot_dia_ban,
            orientation="h",
            labels={"Dư nợ NQ11": "Dư nợ (đồng)", cot_dia_ban: ""},
        )
        fig_db.update_layout(
            height=360,
            margin=dict(l=8, r=8, t=36, b=8),
            showlegend=False,
        )
        cot_phai.markdown(f"**Top 10 theo {cot_dia_ban.lower()}**")
        cot_phai.plotly_chart(fig_db, width="stretch", key="nq11_chart_dia_ban")
    else:
        cot_phai.info("Không có dữ liệu địa bàn.")

    if COT_NQ11_NO_QH in df.columns and (df[COT_NQ11_NO_QH] > 0).any():
        st.markdown("#### Các món cần ưu tiên xử lý")
        cols = [c for c in [
            COT_TEN_PGD,
            COT_TEN_XA,
            COT_NQ11_TEN_KH,
            COT_SO_KU,
            COT_TEN_CT,
            COT_DNO_NQ11,
            COT_NQ11_NO_QH,
        ] if c in df.columns]
        uu_tien = df.loc[df[COT_NQ11_NO_QH] > 0, cols].nlargest(10, COT_NQ11_NO_QH)
        hien_thi_dataframe_phan_trang(_fmt_df_trieu(uu_tien), key="nq11_uu_tien")


def _render_tong_hop(
    ctx,
    df: pd.DataFrame,
    cot_nhom: str,
    username: str,
    key: str,
) -> None:
    """Render một bảng tổng hợp NQ11 chuẩn, có tổng cộng và xuất file."""
    if cot_nhom not in df.columns:
        ctx.error(f"❌ Không có cột {cot_nhom}.")
        return
    df_th = _tao_tong_hop_nq11(df, cot_nhom)
    ctx.markdown(f"#### {cot_nhom} · {fmt_so(len(df_th))} nhóm")

    df_hien_thi = df_th.copy()
    for col in ("Dư nợ NQ11", "Nợ trong hạn", "Nợ quá hạn"):
        df_hien_thi[col] = df_hien_thi[col] / 1_000_000
    tong_du_no = float(df_th["Dư nợ NQ11"].sum())
    tong_no_qh = float(df_th["Nợ quá hạn"].sum())
    dong_tong = {
        cot_nhom: "TỔNG CỘNG",
        "Số KH": int(df[_COT_MA_KH_DEM].nunique()),
        "Số món": int(df[_COT_SO_KU_DEM].nunique()),
        "Dư nợ NQ11": tong_du_no / 1_000_000,
        "Nợ trong hạn": float(df_th["Nợ trong hạn"].sum()) / 1_000_000,
        "Nợ quá hạn": tong_no_qh / 1_000_000,
        "Tỷ lệ QH (%)": tong_no_qh / tong_du_no * 100 if tong_du_no > 0 else 0.0,
        "Tỷ trọng (%)": 100.0 if tong_du_no > 0 else 0.0,
    }
    render_bang_chi_tiet_html(
        df_hien_thi,
        key=f"nq11_th_{key}",
        cot_ten=cot_nhom,
        cot_dem=["Số KH", "Số món"],
        cot_tien=["Dư nợ NQ11", "Nợ trong hạn", "Nợ quá hạn"],
        cot_bar="Tỷ trọng (%)",
        cot_badge="Tỷ lệ QH (%)",
        dong_tong=dong_tong,
        container=ctx,
    )
    with ctx.expander("📥 Xuất bảng tổng hợp"):
        render_export_panel(
            df_th,
            cot_nhom[:31],
            f"Báo cáo NQ11 theo {cot_nhom}",
            username,
            f"BC_NQ11_{key.upper()}",
            st,
            f"nq11_{key}",
        )


def _render_dia_ban(ctx, df: pd.DataFrame, role: str, username: str) -> None:
    """Cho phép chuyển nhanh giữa tổng hợp theo PGD và theo xã."""
    options: list[str] = []
    if not la_phan_he_pgd(role) and COT_TEN_PGD in df.columns:
        options.append(COT_TEN_PGD)
    if COT_TEN_XA in df.columns:
        options.append(COT_TEN_XA)
    if not options:
        ctx.error("❌ Không có cột địa bàn để tổng hợp.")
        return
    cot_nhom = ctx.radio(
        "Cấp tổng hợp",
        options,
        horizontal=True,
        key="nq11_cap_dia_ban",
    )
    _render_tong_hop(
        ctx,
        df,
        cot_nhom,
        username,
        "pgd" if cot_nhom == COT_TEN_PGD else "xa",
    )


def _render_chi_tiet(ctx, df: pd.DataFrame, username: str) -> None:
    """Render danh sách chi tiết có lọc nhanh theo tình trạng và tìm kiếm."""
    trang_thai = ctx.radio(
        "Tình trạng khoản vay",
        ["Tất cả món", "Có nợ quá hạn"],
        horizontal=True,
        key="nq11_trang_thai_chi_tiet",
    )
    df_chi_tiet = df
    if trang_thai == "Có nợ quá hạn" and COT_NQ11_NO_QH in df.columns:
        df_chi_tiet = df.loc[df[COT_NQ11_NO_QH] > 0].copy()

    search_cols = [c for c in [
        COT_NQ11_MA_KH,
        COT_NQ11_TEN_KH,
        COT_SO_KU,
        COT_SDT,
    ] if c in df_chi_tiet.columns]
    if search_cols:
        df_chi_tiet = render_quick_search(
            df_chi_tiet,
            search_cols,
            key="nq11_detail",
            placeholder="🔍 Tìm tên KH, mã KH, số khế ước hoặc điện thoại...",
            container=ctx,
        )

    cols = [c for c in [
        COT_TEN_PGD,
        COT_TEN_XA,
        COT_NQ11_MA_KH,
        COT_NQ11_TEN_KH,
        COT_SDT,
        COT_SO_KU,
        COT_TEN_CT,
        COT_DNO_NQ11,
        COT_NQ11_NO_TH,
        COT_NQ11_NO_QH,
        COT_NQ11_DEN_HAN_SC,
    ] if c in df_chi_tiet.columns]
    df_xuat = df_chi_tiet[cols].copy()
    ctx.markdown(f"#### Danh sách khoản vay · {fmt_so(len(df_xuat))} món")
    with ctx.expander("📥 Xuất danh sách chi tiết"):
        render_export_panel(
            df_xuat,
            "Chi tiet NQ11",
            "Báo cáo chi tiết khoản vay NQ11",
            username,
            "BC_NQ11_CHI_TIET",
            st,
            "nq11_chi_tiet",
        )
    if df_xuat.empty:
        ctx.info("📭 Không có khoản vay phù hợp với điều kiện đang chọn.")
        return
    hien_thi_dataframe_phan_trang(_fmt_df_trieu(df_xuat), key="nq11_chi_tiet")
