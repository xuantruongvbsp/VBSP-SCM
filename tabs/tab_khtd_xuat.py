"""Xuất báo cáo / export cho tab Kế hoạch Tín dụng."""
from __future__ import annotations

import os
from datetime import datetime
from io import BytesIO

import pandas as pd
import streamlit as st
from openpyxl.styles import Font, PatternFill

from config import TEN_CHINH_THUC_CT, CHUONG_TRINH_KHTD, DS_PGD, COT_TEN_PGD, CACHE_HSTD, CACHE_GQVL, XA_TO_PGD, PGD_XA_MAP, DON_VI_CHI_NHANH
from data.core import ts_file


@st.cache_data(show_spinner=False)
def _doc_hstd_cached(_ts: float = 0) -> pd.DataFrame:
    try:
        return pd.read_parquet(CACHE_HSTD)
    except Exception:
        return pd.DataFrame()


@st.cache_data(show_spinner=False)
def _doc_gqvl_cached(_ts: float = 0) -> pd.DataFrame:
    try:
        return pd.read_parquet(CACHE_GQVL)
    except Exception:
        return pd.DataFrame()
from pdf_service import xuat_pdf
from utils import hien_thi_dataframe_phan_trang, xuat_excel, ten_file_xuat

from tabs.tab_khtd import (
    KV_KEY_CN,
    KV_KEY_XA,
    MA_KEYS_CO_KHTD,
    _doc_kv,
    _fvn,
    _fmt_vn,
    _fmt_vn_signed,
    _ma_key_tu_ma_ct_nv,
    _nv_int_tu_ma_key,
    _ten_ct_base,
    _tinh_thuc_hien_theo_ct,
    GQVL_SUB_NHOM,
)


def _hien_thi_bang_cn_readonly(
    kh_cn: dict,
    th_cn: dict[str, float] | None = None,
    ds_ct_loc: list[str] | None = None,
    df_loc: "pd.DataFrame | None" = None,
    username: str = "",
) -> None:
    """Bảng tóm tắt KHTD Chi nhánh — HTML thuần: STT | Chỉ tiêu | KH (triệu đồng) | TH (triệu đồng) | TL% | Trạng thái."""
    from tabs.tab_khtd_nhap import _tinh_th_gqvl_phan_tang

    kh_d = dict(kh_cn or {})
    th_d = dict(th_cn or {})

    df_gqvl = _doc_gqvl_cached(ts_file(CACHE_GQVL))
    th_gqvl = _tinh_th_gqvl_phan_tang(df_gqvl)
    for sk, sv in th_gqvl.items():
        if sv:
            th_d[sk] = sv

    if ds_ct_loc:
        loc_set = set(ds_ct_loc)
        kh_d = {k: v for k, v in kh_d.items() if k in loc_set}
        th_d = {k: v for k, v in th_d.items() if k in loc_set}

    if not kh_d and not th_d:
        st.info("Chưa có dữ liệu.")
        return

    sub_key_3_dp_xa = "3_DP_XA"

    seen_ma_ct: set[int] = set()
    order_ma_ct: list[int] = []
    for mk, ma_ct, _ten, _nv, *_ in CHUONG_TRINH_KHTD:
        mci = int(ma_ct)
        if mci not in seen_ma_ct:
            seen_ma_ct.add(mci)
            order_ma_ct.append(mci)

    BD = "#d1d5db"
    H_BG = "#003D7A"
    NHOM_BG = "#e8f0f8"
    TONG_BG = "#E8F4FD"
    WHITE = "#ffffff"
    ALT = "#F8FAFC"
    RED = "#DC2626"
    AMBER = "#D97706"
    GREEN = "#16A34A"

    tong_kh = 0.0
    tong_th = 0.0
    so_ct_co_kh = 0
    tong_ct = len(order_ma_ct)
    stt_i = 0

    html_rows: list[str] = []
    nhom_hien = ""

    def _tl_color(tl: float | None) -> str:
        if tl is None:
            return "#9ca3af"
        if tl >= 100:
            return GREEN
        if tl >= 95:
            return AMBER
        return RED

    def _tl_text(tl: float | None) -> str:
        if tl is None:
            return "—"
        if tl >= 100:
            return "🟢 Đạt"
        if tl >= 95:
            return "🟡 Đang thực hiện"
        return "🔴 Chậm"

    def _td(v: str, align: str = "right", color: str = "", bg: str = "", fw: str = "") -> str:
        s = f'text-align:{align};padding:5px 8px;border:1px solid {BD};font-size:0.82rem;white-space:nowrap'
        if color:
            s += f";color:{color}"
        if bg:
            s += f";background:{bg}"
        if fw:
            s += f";font-weight:{fw}"
        return f"<td style='{s}'>{v}</td>"

    def _add_group_hdr(label: str) -> None:
        nonlocal nhom_hien
        nhom_hien = label
        tds = (
            _td("", "center", "", NHOM_BG, "bold")
            + _td(label, "left", "#fff", H_BG, "bold")
            + _td("", "right", "", NHOM_BG)
            + _td("", "right", "", NHOM_BG)
            + _td("", "right", "", NHOM_BG)
            + _td("", "right", "", NHOM_BG)
        )
        html_rows.append(f"<tr>{tds}</tr>")

    def _add_row(
        stt: str, ten: str, kh_vnd: float, th_vnd: float, indent: str = ""
    ) -> None:
        nonlocal tong_kh, tong_th, so_ct_co_kh, stt_i
        kh_v = kh_vnd / 1e6
        th_v = th_vnd / 1e6
        tl = th_v / kh_v * 100 if kh_v > 0 else None

        if kh_v > 0 or th_v > 0:
            tong_kh += kh_vnd
            tong_th += th_vnd
            if kh_v > 0:
                so_ct_co_kh += 1

        bg = WHITE if stt_i % 2 == 0 else ALT
        stt_i += 1

        kh_str = _fvn(kh_v, 3) if kh_v > 0 else ("—" if indent else _fvn(kh_v, 3))
        if kh_vnd == 0:
            kh_str = "—"

        th_str = _fvn(th_v, 3) if th_v > 0 else "—"
        tl_str = f"{_fvn(tl, 1)}%" if tl is not None else "—"
        tl_c = _tl_color(tl)
        stt_s = _tl_text(tl)

        tds = (
            _td(stt, "center", "", "", "") +
            _td(f"{indent}{ten}", "left", "", "", "") +
            _td(kh_str, "right", "", "", "") +
            _td(th_str, "right", "", "", "") +
            _td(tl_str, "right", tl_c, "", "") +
            _td(stt_s, "left", tl_c, "", "")
        )
        html_rows.append(f"<tr>{tds}</tr>")

    def _add_gqvl_sub_ten(sub_key: str, sub_ten: str, sub_nv: str) -> None:
        nonlocal tong_kh, tong_th, so_ct_co_kh, stt_i
        kh_vnd = float(kh_d.get(sub_key, 0.0))
        th_vnd = float(th_d.get(sub_key, 0.0))

        kh_v = kh_vnd / 1e6
        th_v = th_vnd / 1e6
        tl = th_v / kh_v * 100 if kh_v > 0 else None

        if kh_v > 0 or th_v > 0:
            tong_kh += kh_vnd
            tong_th += th_vnd
            if kh_v > 0:
                so_ct_co_kh += 1

        bg = WHITE if stt_i % 2 == 0 else ALT
        stt_i += 1

        kh_str = "—" if sub_key == sub_key_3_dp_xa else (_fvn(kh_v, 3) if kh_v > 0 else _fvn(kh_v, 3))
        th_str = _fvn(th_v, 3) if th_v > 0 else "—"
        tl_str = f"{_fvn(tl, 1)}%" if tl is not None else "—"
        tl_c = _tl_color(tl)
        stt_s = _tl_text(tl)

        tds = (
            _td("", "center") +
            _td(f"    {sub_ten}", "left") +
            _td(kh_str, "right") +
            _td(th_str, "right") +
            _td(tl_str, "right", tl_c) +
            _td(stt_s, "left", tl_c)
        )
        html_rows.append(f"<tr style='background:{bg}'>{tds}</tr>")

    for ma_ct in order_ma_ct:
        mk_tw = _ma_key_tu_ma_ct_nv(ma_ct, 1)
        mk_dp = _ma_key_tu_ma_ct_nv(ma_ct, 2)

        kh_tw = float(kh_d.get(mk_tw, 0.0))
        th_tw = float(th_d.get(mk_tw, 0.0))
        kh_dp = float(kh_d.get(mk_dp, 0.0))
        th_dp = float(th_d.get(mk_dp, 0.0))

        ten_base = _ten_ct_base(ma_ct, {})

        if ma_ct == 3:
            nhom_moi = "I. Trung ương"
            if nhom_hien != nhom_moi:
                _add_group_hdr(nhom_moi)
            for sub_key, sub_ten, sub_nv in GQVL_SUB_NHOM:
                _add_gqvl_sub_ten(sub_key, sub_ten, sub_nv)
        else:
            show_tw = (kh_tw > 0 or th_tw > 0) and mk_tw in MA_KEYS_CO_KHTD
            show_dp = (kh_dp > 0 or th_dp > 0) and mk_dp in MA_KEYS_CO_KHTD
            if not show_tw and not show_dp:
                continue

            kh_tong = kh_tw + kh_dp
            th_tong = th_tw + th_dp

            if kh_tw > 0 or th_tw > 0:
                nhom_moi = "I. Nguồn vốn Trung ương"
            else:
                nhom_moi = "II. Nguồn vốn Địa phương"

            if nhom_hien != nhom_moi:
                _add_group_hdr(nhom_moi)

            _add_row(str(len([r for r in html_rows if "<td" in r]) + 1), ten_base, kh_tong, th_tong, "  ")

    tong_tl = tong_th / tong_kh * 100 if tong_kh > 0 else None

    tds_tong = (
        _td("", "center", "", TONG_BG, "bold") +
        _td("TỔNG CỘNG", "left", "", TONG_BG, "bold") +
        _td(_fvn(tong_kh / 1e6, 3), "right", "", TONG_BG, "bold") +
        _td(_fvn(tong_th / 1e6, 3), "right", "", TONG_BG, "bold") +
        _td(f"{_fvn(tong_tl, 1)}%" if tong_tl is not None else "—", "right", _tl_color(tong_tl), TONG_BG, "bold") +
        _td(_tl_text(tong_tl), "left", _tl_color(tong_tl), TONG_BG, "bold")
    )
    html_rows.append(f"<tr>{tds_tong}</tr>")

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Tổng KH (triệu đồng)", f"{_fvn(tong_kh / 1e6, 3)}")
    k2.metric("Tổng TH (triệu đồng)", f"{_fvn(tong_th / 1e6, 3)}")
    k3.metric(
        "Tỷ lệ đạt KH",
        f"{_fvn(tong_tl, 1)}%" if tong_tl is not None else "—",
    )
    k4.metric("Số CT có KH / tổng", f"{so_ct_co_kh}/{tong_ct}")

    headers = ["STT", "Chỉ tiêu", "KH (triệu đồng)", "TH (triệu đồng)", "TL%", "Trạng thái"]
    thead = "".join(
        f'<th style="background:{H_BG};color:#fff;text-align:{"center" if i==0 else "left" if i==1 else "right"};'
        f'padding:6px 8px;border:1px solid {BD};font-size:0.82rem;white-space:nowrap">{h}</th>'
        for i, h in enumerate(headers)
    )

    html = f"""
<div style="overflow-x:auto;margin:8px 0">
<table style="border-collapse:collapse;width:100%;font-family:'Inter','Segoe UI',sans-serif;font-size:0.82rem">
  <thead><tr>{thead}</tr></thead>
  <tbody>{"".join(html_rows)}</tbody>
</table>
<p style="font-size:0.78rem;color:#6B7280;margin:4px 0 0 0">
  * Đơn vị: triệu đồng · KH từ nhập liệu, TH từ Tổng dư nợ HSTD + GQVL phân tầng<br>
  <span style="color:{GREEN}">🟢</span> TL ≥ 100% &nbsp;
  <span style="color:{AMBER}">🟡</span> TL ≥ 95% &nbsp;
  <span style="color:{RED}">🔴</span> TL &lt; 95%
</p>
</div>
"""
    st.markdown(html, unsafe_allow_html=True)


def _tab_canh_bao_chenh_lech() -> None:
    st.subheader("⚠️ Cảnh báo Chênh lệch Phân bổ KHTD")
    st.caption(
        "So sánh kế hoạch chi nhánh (tổng) với tổng kế hoạch đã phân bổ xuống xã "
        "theo từng chương trình tín dụng."
    )

    kh_cn = _doc_kv(KV_KEY_CN)
    kh_xa = _doc_kv(KV_KEY_XA)

    if not kh_cn:
        st.info("Chưa có dữ liệu kế hoạch Chi nhánh. Vui lòng nhập ở tab **KHTD Chi nhánh**.")
        return

    # ── Tổng hợp tổng xã theo từng mã CT ─────────────────────────────────
    tong_xa_theo_ct: dict[str, float] = {}
    for khoa, gia_tri in kh_xa.items():
        phan = khoa.split("|")
        if len(phan) != 2:
            continue
        _, ma_ct = phan
        tong_xa_theo_ct[ma_ct] = tong_xa_theo_ct.get(ma_ct, 0.0) + float(gia_tri)

    # ── Xây dựng bảng so sánh ─────────────────────────────────────────────
    rows = []
    co_canh_bao_do = False
    co_canh_bao_vang = False

    keys_all = sorted(
        set(kh_cn.keys()) | set(tong_xa_theo_ct.keys()),
        key=lambda k: (
            _nv_int_tu_ma_key(k) or 9,
            int(k.split("_", 1)[0]) if "_" in k and k.split("_", 1)[0].isdigit()
            else (int(k.split("|", 1)[0]) if "|" in k and k.split("|", 1)[0].isdigit() else 9_999),
            k,
        ),
    )
    for ma_key in keys_all:
        ten_ct = TEN_CHINH_THUC_CT.get(ma_key, ma_key)
        nv_int = _nv_int_tu_ma_key(ma_key)
        nguon_von = "Trung ương" if nv_int == 1 else ("Địa phương" if nv_int == 2 else "—")
        gia_tri_cn = float(kh_cn.get(ma_key, 0.0))
        gia_tri_xa = tong_xa_theo_ct.get(ma_key, 0.0)

        if gia_tri_cn == 0 and gia_tri_xa == 0:
            continue

        chenh_lech = gia_tri_xa - gia_tri_cn
        ty_le_phan_bo = (gia_tri_xa / gia_tri_cn * 100) if gia_tri_cn > 0 else None

        if gia_tri_xa > gia_tri_cn:
            co_canh_bao_do = True
            trang_thai = "🔴 Vượt CN"
        elif ty_le_phan_bo is not None and ty_le_phan_bo < 95:
            co_canh_bao_vang = True
            trang_thai = "🟡 Chưa đủ 95%"
        else:
            trang_thai = "🟢 Đạt"

        rows.append({
            "Chương trình": ten_ct,
            "Nguồn vốn": nguon_von,
            "Chi nhánh (triệu)": round(gia_tri_cn / 1_000_000, 1),
            "Tổng xã (triệu)": round(gia_tri_xa / 1_000_000, 1),
            "Chênh lệch (triệu)": round(chenh_lech / 1_000_000, 1),
            "Tỷ lệ phân bổ %": round(ty_le_phan_bo, 1) if ty_le_phan_bo is not None else None,
            "Trạng thái": trang_thai,
        })

    if not rows:
        st.info("Không có dữ liệu để so sánh.")
        return

    # ── Hiển thị cảnh báo tổng quan ──────────────────────────────────────
    if co_canh_bao_do:
        st.error(
            "🔴 **Cảnh báo nghiêm trọng:** Một số chương trình có tổng kế hoạch xã "
            "**vượt quá** kế hoạch Chi nhánh đã duyệt!"
        )
    if co_canh_bao_vang:
        st.warning(
            "🟡 **Lưu ý:** Một số chương trình chưa phân bổ đủ 95% kế hoạch Chi nhánh "
            "xuống cấp xã."
        )
    if not co_canh_bao_do and not co_canh_bao_vang:
        st.success("🟢 Tất cả chương trình đã phân bổ đạt yêu cầu (≥ 95% và không vượt CN).")

    st.divider()

    # ── Metrics tổng ─────────────────────────────────────────────────────
    df = pd.DataFrame(rows)
    tong_cn_all = df["Chi nhánh (triệu)"].sum()
    tong_xa_all = df["Tổng xã (triệu)"].sum()
    ty_le_all = (tong_xa_all / tong_cn_all * 100) if tong_cn_all > 0 else 0.0

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Tổng KH Chi nhánh (triệu)", _fmt_vn(tong_cn_all, 1))
    m2.metric("Tổng KH Xã (triệu)", _fmt_vn(tong_xa_all, 1))
    m3.metric("Chênh lệch (triệu)", _fmt_vn_signed(tong_xa_all - tong_cn_all, 1))
    m4.metric("Tỷ lệ phân bổ tổng", f"{_fmt_vn(ty_le_all, 1)}%")

    st.divider()

    # ── Tô màu bảng theo trạng thái ──────────────────────────────────────
    def _to_mau_hang(row: pd.Series) -> list[str]:
        if "🔴" in str(row.get("Trạng thái", "")):
            return ["background-color: #ffd6d6"] * len(row)
        if "🟡" in str(row.get("Trạng thái", "")):
            return ["background-color: #fff9d6"] * len(row)
        return [""] * len(row)

    # Column config cho bảng cảnh báo
    column_config_cb: dict[str, st.column_config.Column] = {
        "Chi nhánh (triệu)": st.column_config.NumberColumn(
            "Chi nhánh (triệu)",
            format=",.1f",
            help="Kế hoạch Chi nhánh (triệu đồng)"
        ),
        "Tổng xã (triệu)": st.column_config.NumberColumn(
            "Tổng xã (triệu)",
            format=",.1f",
            help="Tổng kế hoạch xã (triệu đồng)"
        ),
        "Chênh lệch (triệu)": st.column_config.NumberColumn(
            "Chênh lệch (triệu)",
            format=",.1f",
            help="Chênh lệch (triệu đồng)"
        ),
        "Tỷ lệ phân bổ %": st.column_config.NumberColumn(
            "Tỷ lệ phân bổ %",
            format=".1f",
            help="Tỷ lệ phân bổ %"
        ),
    }

    hien_thi_dataframe_phan_trang(
        df.style.apply(_to_mau_hang, axis=1),
        key="khtd_cbtd_view",
        column_config=column_config_cb,
        height=450,
    )

    # ── Xuất Excel ────────────────────────────────────────────────────────
    st.divider()
    if st.button("📥 Xuất báo cáo chênh lệch", key="btn_xuat_chenh_lech"):
        buf = BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Chênh lệch KHTD")
        st.session_state["_bytes_khtd_cl"] = buf.getvalue()
        st.session_state["_file_khtd_cl"] = f"CanhBao_KHTD_{datetime.today().strftime('%d%m%Y')}.xlsx"

    if st.session_state.get("_bytes_khtd_cl"):
        st.download_button(
            label="⬇ Tải file Excel",
            data=st.session_state["_bytes_khtd_cl"],
            file_name=st.session_state["_file_khtd_cl"],
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="dl_chenh_lech_excel",
        )


def _tab_tien_do_kh_th() -> None:
    """Dashboard cảnh báo tiến độ KH vs TH thực hiện theo PGD."""
    from tabs.tab_khtd_nhap import _tinh_th_gqvl_phan_tang

    st.subheader("🎯 Tiến độ Kế hoạch vs Thực hiện")
    st.caption(
        "So sánh KH đã nhập với TH thực tế từ HSTD + GQVL. "
        "Cảnh báo 🔴 khi PGD đạt < 95% KH."
    )

    kh_cn = _doc_kv(KV_KEY_CN)
    if not kh_cn:
        st.warning("⚠️ Chưa có KH Chi nhánh. Vào tab **🏛️ KHTD Chi nhánh** nhập trước.")
        return

    df_hstd = _doc_hstd_cached(ts_file(CACHE_HSTD))
    if df_hstd.empty:
        st.warning("⚠️ Chưa có dữ liệu HSTD. Upload file trước.")
        return

    th_cn = _tinh_thuc_hien_theo_ct(df_hstd)

    df_gqvl = _doc_gqvl_cached(ts_file(CACHE_GQVL))

    th_gqvl = _tinh_th_gqvl_phan_tang(df_gqvl)
    for sub_key, val in th_gqvl.items():
        th_cn[sub_key] = val

    tong_kh = sum(float(v) for v in kh_cn.values())
    tong_th = sum(float(th_cn.get(mk, 0))
                  for mk, *_ in CHUONG_TRINH_KHTD)
    tl_cn = tong_th / tong_kh * 100 if tong_kh > 0 else 0

    so_dat = sum(1 for mk, *_ in CHUONG_TRINH_KHTD
                 if float(kh_cn.get(mk, 0)) > 0
                 and float(th_cn.get(mk, 0)) / float(kh_cn.get(mk, 1)) >= 0.7)
    so_chua = sum(1 for mk, *_ in CHUONG_TRINH_KHTD
                  if float(kh_cn.get(mk, 0)) > 0
                  and float(th_cn.get(mk, 0)) / float(kh_cn.get(mk, 1)) < 0.7)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Tổng KH (triệu đồng)", f"{_fvn(tong_kh/1e6, 0)}")
    c2.metric("Tổng TH (triệu đồng)", f"{_fvn(tong_th/1e6, 0)}")
    c3.metric("Tỷ lệ CN", f"{_fvn(tl_cn, 1)}%",
              delta=f"{'✅' if tl_cn >= 95 else '⚠️'}")
    c4.metric("CT chưa đạt 95%", str(so_chua),
              delta_color="inverse" if so_chua > 0 else "off")

    st.divider()

    st.markdown("#### 📋 Chi tiết theo Chương trình")

    rows_ct = []
    nhom_hien = ""
    for mk, _ma_ct, ten_ct, nv, *_ in CHUONG_TRINH_KHTD:
        kh_val = float(kh_cn.get(mk, 0))
        th_val = float(th_cn.get(mk, 0))
        tl_val = th_val / kh_val * 100 if kh_val > 0 else None

        nhom_moi = "I. Trung ương" if nv == "TW" else "II. Địa phương"
        if nhom_moi != nhom_hien:
            nhom_hien = nhom_moi
            rows_ct.append({
                "STT": nhom_hien,
                "Chỉ tiêu": nhom_hien,
                "KH (triệu đồng)": None, "TH (triệu đồng)": None, "TL%": None,
                "Trạng thái": "", "_nhom": True,
            })

        if kh_val == 0 and th_val == 0:
            continue

        if tl_val is None:
            trang_thai = "—"
        elif tl_val >= 100:
            trang_thai = "🟢 Đạt"
        elif tl_val >= 95:
            trang_thai = "🟡 Đang thực hiện"
        else:
            trang_thai = "🔴 Chậm"

        rows_ct.append({
            "STT": "",
            "Chỉ tiêu": f"  {ten_ct}",
            "KH (triệu đồng)": round(kh_val/1e6, 0) if kh_val else None,
            "TH (triệu đồng)": round(th_val/1e6, 0) if th_val else None,
            "TL%": round(tl_val, 1) if tl_val is not None else None,
            "Trạng thái": trang_thai,
            "_nhom": False,
        })

    rows_ct.append({
        "STT": "", "Chỉ tiêu": "TỔNG CỘNG",
        "KH (triệu đồng)": round(tong_kh/1e6, 0),
        "TH (triệu đồng)": round(tong_th/1e6, 0),
        "TL%": round(tl_cn, 1),
        "Trạng thái": "🟢 Đạt" if tl_cn >= 95 else "🔴 Chậm",
        "_nhom": False,
    })

    df_ct = pd.DataFrame(rows_ct)

    def _to_mau_ct(row):
        if row.get("_nhom"):
            return ["background-color: #D9E1F2; font-weight: bold"] * len(row)
        if "🔴" in str(row.get("Trạng thái", "")):
            return ["background-color: #ffd6d6"] * len(row)
        if "🟡" in str(row.get("Trạng thái", "")):
            return ["background-color: #fff9d6"] * len(row)
        return [""] * len(row)

    cols_show = ["Chỉ tiêu", "KH (triệu đồng)", "TH (triệu đồng)", "TL%", "Trạng thái"]
    hien_thi_dataframe_phan_trang(
        df_ct[cols_show].style.apply(_to_mau_ct, axis=1),
        key="khtd_tien_do_ct",
        height=480,
        column_config={
            "KH (triệu đồng)": st.column_config.NumberColumn(format=",.0f"),
            "TH (triệu đồng)": st.column_config.NumberColumn(format=",.0f"),
            "TL%":     st.column_config.ProgressColumn(
                           min_value=0, max_value=100, format=".1f"),
        },
    )

    st.divider()
    st.markdown("#### 🔴 Cảnh báo PGD chậm tiến độ (< 95% KH)")

    if COT_TEN_PGD not in df_hstd.columns:
        st.info("Không có cột PGD trong HSTD.")
        return

    rows_pgd = []
    for ten_pgd in DS_PGD:
        df_pgd = df_hstd[df_hstd[COT_TEN_PGD] == ten_pgd]
        th_pgd = _tinh_thuc_hien_theo_ct(df_pgd)

        try:
            df_gqvl_pgd = df_gqvl[df_gqvl[COT_TEN_PGD] == ten_pgd] \
                if not df_gqvl.empty and COT_TEN_PGD in df_gqvl.columns \
                else pd.DataFrame()
        except Exception:
            df_gqvl_pgd = pd.DataFrame()
        th_gqvl_pgd = _tinh_th_gqvl_phan_tang(df_gqvl_pgd)
        for sk, sv in th_gqvl_pgd.items():
            th_pgd[sk] = sv

        tong_kh_pgd = tong_kh
        tong_th_pgd = sum(float(th_pgd.get(mk, 0))
                          for mk, *_ in CHUONG_TRINH_KHTD)
        tl_pgd = tong_th_pgd / tong_kh_pgd * 100 if tong_kh_pgd > 0 else 0

        if tl_pgd < 95:
            rows_pgd.append({
                "PGD": ten_pgd,
                "TH (triệu đồng)": round(tong_th_pgd/1e6, 0),
                "KH CN (triệu đồng)": round(tong_kh_pgd/1e6, 0),
                "TL%": round(tl_pgd, 1),
            })

    if rows_pgd:
        df_pgd_cb = pd.DataFrame(rows_pgd).sort_values("TL%")
        st.dataframe(
            df_pgd_cb,
            use_container_width=True,
            hide_index=True,
            column_config={
                "TL%": st.column_config.ProgressColumn(
                    min_value=0, max_value=100, format=".1f"),
            },
        )
    else:
        st.success("🟢 Tất cả PGD đang đạt ≥ 95% KH Chi nhánh.")

    st.divider()
    col_ex, col_pdf = st.columns(2)

    with col_ex:
        _ss_ex = "_excel_tien_do_kh_th"
        if st.button("📥 Xuất Excel", key="btn_xuat_tien_do_excel"):
            try:
                buf = xuat_excel({
                    "KH vs TH": df_ct[cols_show],
                    "PGD chậm": pd.DataFrame(rows_pgd) if rows_pgd else pd.DataFrame(),
                })
                st.session_state[_ss_ex] = buf
            except Exception as e:
                st.error(f"❌ Lỗi: {e}")
        if st.session_state.get(_ss_ex):
            st.download_button(
                "⬇ Tải Excel",
                data=st.session_state[_ss_ex],
                file_name=ten_file_xuat("TienDo_KH_TH"),
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="dl_tien_do_excel",
            )

    with col_pdf:
        _ss_pdf = "_pdf_tien_do_kh_th"
        if st.button("📄 Xuất PDF", key="btn_xuat_tien_do_pdf", type="primary"):
            try:
                with st.spinner("⏳ Đang tạo PDF..."):
                    pdf_bytes = xuat_pdf(
                        df_ct[cols_show].dropna(subset=["KH (triệu đồng)"]),
                        "Báo cáo Tiến độ Kế hoạch vs Thực hiện",
                        username="VBSP-SCM",
                        cols_tien=["KH (triệu đồng)", "TH (triệu đồng)"],
                    )
                st.session_state[_ss_pdf] = pdf_bytes
                st.session_state["_pdf_file_tien_do"] = ten_file_xuat("TienDo_KH_TH", ext=".pdf")
            except Exception as e:
                st.error(f"❌ Lỗi PDF: {e}")
        if st.session_state.get(_ss_pdf):
            st.download_button(
                "⬇ Tải PDF",
                data=st.session_state[_ss_pdf],
                file_name=st.session_state.get("_pdf_file_tien_do", "TienDo_KH_TH.pdf"),
                mime="application/pdf",
                key="dl_tien_do_pdf",
            )


def xuat_khtd_theo_xa(role: str, username: str, df_full: "pd.DataFrame | None" = None) -> bytes:
    """Xuất Excel Kế hoạch Tín dụng theo Xã — ma trận Xã × Chương trình."""
    kh_xa = _doc_kv(KV_KEY_XA)
    kh_cn = _doc_kv(KV_KEY_CN)

    ds_xa = sorted(XA_TO_PGD.keys())

    ct_tw = [(mk, ten) for mk, _, ten, nv, _ in CHUONG_TRINH_KHTD if nv == "TW"]
    ct_dp = [(mk, ten) for mk, _, ten, nv, _ in CHUONG_TRINH_KHTD if nv == "DP"]

    def _lookup(ten_xa: str, ma_key: str) -> float:
        val = kh_xa.get(f"{ten_xa}|{ma_key}", None)
        if val is not None:
            return float(val)
        return 0.0

    def _cn_val(ma_key: str) -> float:
        return float(kh_cn.get(ma_key, 0.0))

    rows_data = []
    so_xa_co_kh = 0
    for ten_xa in ds_xa:
        pgd = XA_TO_PGD.get(ten_xa, "")
        row = {"Xã/Phường": ten_xa, "PGD": pgd}
        tong_xa = 0.0
        for mk, ten_ct in ct_tw + ct_dp:
            trieu = round(_lookup(ten_xa, mk) / 1_000_000, 1)
            row[ten_ct] = trieu
            tong_xa += trieu
        row["Tổng"] = round(tong_xa, 1)
        if tong_xa > 0:
            so_xa_co_kh += 1
        rows_data.append(row)

    row_tong_cn = {"Xã/Phường": "TỔNG CHI NHÁNH", "PGD": ""}
    tong_cn_all = 0.0
    for mk, ten_ct in ct_tw + ct_dp:
        trieu = round(_cn_val(mk) / 1_000_000, 1)
        row_tong_cn[ten_ct] = trieu
        tong_cn_all += trieu
    row_tong_cn["Tổng"] = round(tong_cn_all, 1)
    rows_data.append(row_tong_cn)

    col_order = ["Xã/Phường", "PGD"] + [ten for _, ten in ct_tw + ct_dp] + ["Tổng"]
    df_xa = pd.DataFrame(rows_data, columns=col_order)

    # ── Dùng xuat_excel() từ utils.py để build multi-sheet (23 sheet) ──────
    DS_TT_22 = [DON_VI_CHI_NHANH] + DS_PGD

    sheets: dict[str, pd.DataFrame] = {}

    # Sheet 1: Tổng hợp toàn CN (giữ cả dòng TỔNG CHI NHÁNH)
    sheets["Tổng hợp CN"] = df_xa

    # Sheet 2..23: từng đơn vị trong DS_TT_22 (22 đơn vị)
    df_xa_chi = df_xa[df_xa["Xã/Phường"] != "TỔNG CHI NHÁNH"].copy()

    for ten_dv in DS_TT_22:
        ds_xa_dv = PGD_XA_MAP.get(ten_dv, [])
        if not ds_xa_dv:
            continue
        df_dv = df_xa_chi[df_xa_chi["Xã/Phường"].isin(ds_xa_dv)].copy()
        if df_dv.empty:
            continue

        # Thêm dòng tổng đơn vị
        row_tong: dict = {"Xã/Phường": f"TỔNG {ten_dv}", "PGD": ""}
        for col in col_order[2:]:  # bỏ 2 cột đầu Xã/Phường và PGD
            row_tong[col] = round(float(df_dv[col].sum()), 1)
        df_dv = pd.concat(
            [df_dv, pd.DataFrame([row_tong])],
            ignore_index=True
        )

        # Tên sheet: tối đa 31 ký tự (giới hạn Excel)
        ten_sheet = (
            ten_dv.replace("Hội sở Chi nhánh tỉnh", "Hội sở CN tỉnh")
                  .replace("PGD ", "")
                  .strip()[:31]
        )
        sheets[ten_sheet] = df_dv

    return xuat_excel(sheets)


def render_xuat_baocao(role: str = "", username: str = "", df_full: "pd.DataFrame | None" = None) -> None:
    sub1, sub2 = st.tabs(["📊 Chênh lệch phân bổ", "🎯 Tiến độ KH vs TH"])
    with sub1:
        _tab_canh_bao_chenh_lech()
    with sub2:
        _tab_tien_do_kh_th()

    st.divider()
    st.subheader("📍 Xuất KHTD theo Xã")
    st.caption("Bảng tổng hợp kế hoạch tín dụng phân bổ đến từng xã/phường — đơn vị: triệu đồng")

    with st.expander("👁️ Xem trước dữ liệu", expanded=False):
        try:
            kh_xa_prev = _doc_kv(KV_KEY_XA)
            if not kh_xa_prev:
                st.info("Chưa có dữ liệu kế hoạch xã.")
            else:
                ct_all = [(mk, ten) for mk, _, ten, nv, _ in CHUONG_TRINH_KHTD]
                rows_prev = []
                for ten_xa, ten_dv in sorted(XA_TO_PGD.items()):
                    row = {"Xã/Phường": ten_xa, "Đơn vị": ten_dv}
                    tong = 0.0
                    for mk, ten_ct in ct_all:
                        v = round(float(kh_xa_prev.get(f"{ten_xa}|{mk}", 0)) / 1e6, 1)
                        row[ten_ct] = v
                        tong += v
                    row["Tổng"] = round(tong, 1)
                    if tong > 0:
                        rows_prev.append(row)
                if rows_prev:
                    col_order_prev = ["Xã/Phường", "Đơn vị"] + [t for _, t in ct_all] + ["Tổng"]
                    df_prev = pd.DataFrame(rows_prev, columns=col_order_prev)
                    so_xa = len(df_prev)
                    tong_all = df_prev["Tổng"].sum()
                    st.caption(
                        f"**{so_xa}** xã/phường có kế hoạch · "
                        f"Tổng: **{tong_all:,.1f}** triệu đồng"
                    )
                    st.dataframe(df_prev, use_container_width=True,
                                 hide_index=True, height=300)
                else:
                    st.info("Chưa có xã/phường nào được giao kế hoạch.")
        except Exception as e:
            st.warning(f"Không thể xem trước: {e}")

    col1, col2 = st.columns([1, 3])
    with col1:
        if st.button("📥 Xuất Excel KHTD/Xã", key="btn_xuat_khtd_xa"):
            with st.spinner("Đang tạo file..."):
                try:
                    excel_bytes = xuat_khtd_theo_xa(role, username, df_full)
                    ten_file = ten_file_xuat("KHTD_theo_Xa")
                    st.session_state["_bytes_khtd_xa"] = excel_bytes
                    st.session_state["_file_khtd_xa"] = ten_file
                    st.success(f"✅ Đã tạo: {ten_file}")
                except Exception as e:
                    st.error(f"❌ Lỗi khi tạo file: {e}")

    if st.session_state.get("_bytes_khtd_xa"):
        st.download_button(
            label="⬇️ Tải file Excel",
            data=st.session_state["_bytes_khtd_xa"],
            file_name=st.session_state.get("_file_khtd_xa", "KHTD_theo_Xa.xlsx"),
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="dl_khtd_xa",
        )

