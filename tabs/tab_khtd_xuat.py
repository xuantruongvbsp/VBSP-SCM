"""Xuất báo cáo / export cho tab Kế hoạch Tín dụng."""
from __future__ import annotations

from datetime import datetime
from io import BytesIO

import pandas as pd
import streamlit as st
from openpyxl.styles import Font, PatternFill

from config import TEN_CHINH_THUC_CT, CHUONG_TRINH_KHTD
from pdf_service import xuat_pdf
from utils import hien_thi_dataframe_phan_trang

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
)


def _hien_thi_bang_cn_readonly(
    kh_cn: dict,
    th_cn: dict[str, float] | None = None,
    ds_ct_loc: list[str] | None = None,
    df_loc: "pd.DataFrame | None" = None,
    username: str = "",
) -> None:
    """Bảng tóm tắt KHTD Chi nhánh — KH/TH/CPTH (triệu) dạng chuỗi _fvn, KPI VND → tỷ qua /1e12."""
    _ = df_loc
    kh_d = kh_cn or {}
    th_d = th_cn or {}
    if not kh_d and not th_d:
        st.info("Chưa có dữ liệu.")
        return

    tong_kh_tw = sum(
        float(kh_d.get(mk, 0.0))
        for mk, _mc, _t, nv, _tm in CHUONG_TRINH_KHTD
        if nv == "TW"
    )
    tong_kh_dp = sum(
        float(kh_d.get(mk, 0.0))
        for mk, _mc, _t, nv, _tm in CHUONG_TRINH_KHTD
        if nv == "DP"
    )
    tong_th_tw = sum(
        float(th_d.get(mk, 0.0))
        for mk, _mc, _t, nv, _tm in CHUONG_TRINH_KHTD
        if nv == "TW"
    )
    tong_th_dp = sum(
        float(th_d.get(mk, 0.0))
        for mk, _mc, _t, nv, _tm in CHUONG_TRINH_KHTD
        if nv == "DP"
    )
    tong_kh = tong_kh_tw + tong_kh_dp
    tong_th = tong_th_tw + tong_th_dp
    pct_tong_kpi = round(tong_th / tong_kh * 100, 1) if tong_kh > 0 else None
    so_ct_co_kh = sum(
        1
        for mk, _a, _b, _c, _d in CHUONG_TRINH_KHTD
        if float(kh_d.get(mk, 0.0)) > 0
    )

    k1, k2, k3, k4 = st.columns(4)
    # VND → đơn vị hiển thị “tỷ” trong tab: chia 1e12 (không dùng 1e9)
    k1.metric("Tổng kế hoạch", f"{_fvn(tong_kh / 1e12, 3)} tỷ đồng")
    k2.metric("Tổng thực hiện", f"{_fvn(tong_th / 1e12, 3)} tỷ đồng")
    k3.metric(
        "Tỷ lệ đạt kế hoạch",
        (f"{_fvn(pct_tong_kpi, 1)}%") if pct_tong_kpi is not None else "—",
    )
    k4.metric(
        "Số chương trình có KH",
        f"{so_ct_co_kh}/26 chương trình",
    )

    ds_ct_hien_thi = [mk for mk, *_ in CHUONG_TRINH_KHTD]
    if ds_ct_loc:
        ds_loc_set = set(ds_ct_loc)
        ds_ct_hien_thi = [mk for mk in ds_ct_hien_thi if mk in ds_loc_set]
    if not ds_ct_hien_thi:
        st.info("Không có dữ liệu để hiển thị.")
        return

    loc_set = set(ds_ct_hien_thi)

    seen_ma_ct: set[int] = set()
    order_ma_ct: list[int] = []
    for mk, ma_ct, _ten, nv, *_ in CHUONG_TRINH_KHTD:
        if mk not in loc_set:
            continue
        mci = int(ma_ct)
        if mci in seen_ma_ct:
            continue
        mk_tw = _ma_key_tu_ma_ct_nv(mci, 1)
        mk_dp = _ma_key_tu_ma_ct_nv(mci, 2)
        show_tw = mk_tw in MA_KEYS_CO_KHTD and mk_tw in loc_set
        show_dp = mk_dp in MA_KEYS_CO_KHTD and mk_dp in loc_set
        if not show_tw and not show_dp:
            continue
        seen_ma_ct.add(mci)
        order_ma_ct.append(mci)

    COT_XUAT = [
        "STT",
        "Chỉ tiêu",
        "KH TW",
        "KH ĐP",
        "KH Tổng",
        "TH TW",
        "TH ĐP",
        "Còn TW",
        "Còn ĐP",
        "TL TW%",
        "TL ĐP%",
    ]
    data_rows: list[dict] = []

    def _row(
        nhom: str,
        stt: str,
        chi_tieu: str,
        cells: tuple[str, ...] | None,
    ) -> None:
        r: dict[str, str] = {"STT": stt, "Chỉ tiêu": chi_tieu, "_nhom": nhom}
        if cells is None:
            for c in COT_XUAT[2:]:
                r[c] = ""
        else:
            for c, v in zip(COT_XUAT[2:], cells, strict=True):
                r[c] = v
        data_rows.append(r)

    def _fmt_amt(v: float) -> str:
        return _fmt_vn(v, 0)

    def _fmt_con(kh: float, th: float) -> str:
        if kh <= 0:
            return "—"
        return _fmt_vn(kh - th, 0)

    def _fmt_tl_pct(th: float, kh: float) -> str:
        if kh <= 0:
            return "—"
        return f"{_fmt_vn(th / kh * 100, 1)}%"

    _row("A", "A", "KẾ HOẠCH", None)
    _row("I", "I", "Nguồn vốn Trung ương", None)

    sum_kh_tw = sum_th_tw = 0.0
    sum_kh_dp = sum_th_dp = 0.0
    stt_i = 1

    for ma_ct in order_ma_ct:
        mk_tw = _ma_key_tu_ma_ct_nv(ma_ct, 1)
        mk_dp = _ma_key_tu_ma_ct_nv(ma_ct, 2)
        show_tw = mk_tw in MA_KEYS_CO_KHTD and mk_tw in loc_set
        show_dp = mk_dp in MA_KEYS_CO_KHTD and mk_dp in loc_set

        kh_tw = float(kh_d.get(mk_tw, 0.0)) / 1_000_000
        th_tw = float(th_d.get(mk_tw, 0.0)) / 1_000_000
        kh_dp = float(kh_d.get(mk_dp, 0.0)) / 1_000_000
        th_dp = float(th_d.get(mk_dp, 0.0)) / 1_000_000
        kh_tong = kh_tw + kh_dp

        if show_tw:
            sum_kh_tw += kh_tw
            sum_th_tw += th_tw
        if show_dp:
            sum_kh_dp += kh_dp
            sum_th_dp += th_dp

        ten_h = _ten_ct_base(ma_ct, {})
        _row(
            "con",
            str(stt_i),
            f"  {ten_h}",
            (
                _fmt_amt(kh_tw),
                _fmt_amt(kh_dp),
                _fmt_amt(kh_tong),
                _fmt_amt(th_tw),
                _fmt_amt(th_dp),
                _fmt_con(kh_tw, th_tw),
                _fmt_con(kh_dp, th_dp),
                _fmt_tl_pct(th_tw, kh_tw),
                _fmt_tl_pct(th_dp, kh_dp),
            ),
        )
        stt_i += 1

    _row(
        "tong_tw",
        "",
        "  Tổng Trung ương",
        (
            _fmt_amt(sum_kh_tw),
            "",
            _fmt_amt(sum_kh_tw),
            _fmt_amt(sum_th_tw),
            "",
            _fmt_con(sum_kh_tw, sum_th_tw),
            "",
            _fmt_tl_pct(sum_th_tw, sum_kh_tw),
            "",
        ),
    )

    _row("II", "II", "Nguồn vốn Địa phương", None)

    _row(
        "tong_dp",
        "",
        "  Tổng Địa phương",
        (
            "",
            _fmt_amt(sum_kh_dp),
            _fmt_amt(sum_kh_dp),
            "",
            _fmt_amt(sum_th_dp),
            "",
            _fmt_con(sum_kh_dp, sum_th_dp),
            "",
            _fmt_tl_pct(sum_th_dp, sum_kh_dp),
        ),
    )

    all_kh_tw = sum_kh_tw
    all_kh_dp = sum_kh_dp
    all_kh = all_kh_tw + all_kh_dp
    all_th_tw = sum_th_tw
    all_th_dp = sum_th_dp
    _row(
        "tong_all",
        "",
        "🔹 TỔNG CỘNG",
        (
            _fmt_amt(all_kh_tw),
            _fmt_amt(all_kh_dp),
            _fmt_amt(all_kh),
            _fmt_amt(all_th_tw),
            _fmt_amt(all_th_dp),
            _fmt_con(all_kh_tw, all_th_tw),
            _fmt_con(all_kh_dp, all_th_dp),
            _fmt_tl_pct(all_th_tw, all_kh_tw),
            _fmt_tl_pct(all_th_dp, all_kh_dp),
        ),
    )

    df = pd.DataFrame(data_rows)
    if df.empty:
        st.info("Không có dữ liệu để hiển thị.")
        return

    BD = "#c8d8e8"
    H1 = "#1a3a5c"
    H2 = "#2d5986"

    header1 = (
        f'<th rowspan="2" style="background:{H1};color:#fff;text-align:center;'
        f'padding:6px 4px;border:1px solid {BD};font-size:0.82rem;vertical-align:middle">'
        f"STT</th>"
        f'<th rowspan="2" style="background:{H1};color:#fff;text-align:center;'
        f'padding:6px 4px;border:1px solid {BD};font-size:0.82rem;vertical-align:middle">'
        f"Chỉ tiêu</th>"
        f'<th colspan="3" style="background:{H1};color:#fff;text-align:center;'
        f'padding:6px 4px;border:1px solid {BD};font-size:0.82rem">'
        f"KẾ HOẠCH</th>"
        f'<th colspan="2" style="background:{H1};color:#fff;text-align:center;'
        f'padding:6px 4px;border:1px solid {BD};font-size:0.82rem">'
        f"THỰC HIỆN</th>"
        f'<th colspan="2" style="background:{H1};color:#fff;text-align:center;'
        f'padding:6px 4px;border:1px solid {BD};font-size:0.82rem">'
        f"CÒN PHẢI TH</th>"
        f'<th colspan="2" style="background:{H1};color:#fff;text-align:center;'
        f'padding:6px 4px;border:1px solid {BD};font-size:0.82rem">'
        f"TỶ LỆ TH</th>"
    )
    sub_names = [
        "KH TW",
        "KH ĐP",
        "KH Tổng",
        "TH TW",
        "TH ĐP",
        "Còn TW",
        "Còn ĐP",
        "TL TW%",
        "TL ĐP%",
    ]
    header2 = "".join(
        f'<th style="background:{H2};color:#fff;text-align:center;'
        f'padding:5px 4px;border:1px solid {BD};font-size:0.78rem;white-space:nowrap">'
        f"{sn}</th>"
        for sn in sub_names
    )

    rows_html = ""
    for i, rdict in enumerate(data_rows):
        nhom = str(rdict.get("_nhom", ""))
        if nhom in ("A", "I", "II"):
            bg = "#e8f0f8"
            fw = "bold"
        elif nhom in ("tong_tw", "tong_dp", "tong_all"):
            bg = "#e8f0f8"
            fw = "700"
        else:
            bg = "#f5f8fc" if i % 2 == 0 else "#ffffff"
            fw = "normal"
        tds = []
        for col in COT_XUAT:
            raw = rdict.get(col, "")
            align = (
                "left"
                if col == "Chỉ tiêu"
                else ("center" if col == "STT" else "right")
            )
            tds.append(
                f'<td style="padding:6px 8px;border:1px solid {BD};text-align:{align};'
                f'font-weight:{fw};font-size:0.82rem;white-space:nowrap">{raw}</td>'
            )
        rows_html += f'<tr style="background:{bg}">{"".join(tds)}</tr>\n'

    html_table = f"""
<div style="overflow-x:auto;margin:8px 0">
<table style="border-collapse:collapse;width:100%;font-family:'Inter','Segoe UI',sans-serif;font-size:0.82rem">
  <thead>
    <tr>{header1}</tr>
    <tr>{header2}</tr>
  </thead>
  <tbody>{rows_html}</tbody>
</table>
<p style="font-size:0.78rem;color:#6B7280;margin:4px 0 0 0">
  * Đơn vị: triệu đồng · Thực hiện lấy theo Tổng dư nợ (HSTD)
</p>
</div>
"""
    st.markdown(html_table, unsafe_allow_html=True)

    df_pdf = df.drop(columns=["_nhom"], errors="ignore").copy()

    if st.button("📄 Xuất PDF", key="btn_pdf_khtd_cn"):
        with st.spinner("Đang tạo PDF..."):
            pdf_bytes = xuat_pdf(
                df_pdf,
                tieu_de="BÁO CÁO KẾ HOẠCH TÍN DỤNG CHI NHÁNH",
                nguoi_xuat=username or "—",
                cols_tien=[],
                prefix_file="KHTD_CN",
            )
        st.session_state["_pdf_bytes_khtd_cn"] = pdf_bytes
        st.session_state["_pdf_file_khtd_cn"]  = f"KHTD_CN_{datetime.today().strftime('%d%m%Y')}.pdf"
    if st.session_state.get("_pdf_bytes_khtd_cn"):
        st.download_button(
            label="⬇ Tải PDF",
            data=st.session_state["_pdf_bytes_khtd_cn"],
            file_name=st.session_state.get("_pdf_file_khtd_cn", "KHTD_CN.pdf"),
            mime="application/pdf",
            key="dl_pdf_khtd_cn",
        )

    if st.button("📥 Xuất Excel", key="btn_xuat_khtd_cn_matrix"):
        ten_file = f"KHTD_CN_{datetime.today().strftime('%d%m%Y')}.xlsx"
        buf = BytesIO()
        df_xuat = df.drop(columns=["_nhom"], errors="ignore").copy()
        n_col = len(COT_XUAT)
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            df_xuat.to_excel(writer, index=False, sheet_name="KHTD_CN_Matrix")
            ws = writer.book["KHTD_CN_Matrix"]
            fill_grp = PatternFill(fill_type="solid", fgColor="E8F0F8")
            fill_head = PatternFill(fill_type="solid", fgColor="D6E4F0")
            for cell in ws[1]:
                cell.font = Font(bold=True)
                cell.fill = fill_head
            for ridx, nhom in enumerate(df["_nhom"].tolist(), start=2):
                if nhom in ("A", "I", "II", "tong_tw", "tong_dp", "tong_all"):
                    for cidx in range(1, n_col + 1):
                        c = ws.cell(row=ridx, column=cidx)
                        c.fill = fill_grp
                        c.font = Font(bold=(nhom in ("A", "I", "II")))
            widths = [7, 34, 11, 11, 12, 11, 11, 11, 11, 10, 10]
            for i, w in enumerate(widths, start=1):
                if i <= n_col:
                    ws.column_dimensions[
                        ws.cell(row=1, column=i).column_letter
                    ].width = w
        st.download_button(
            label="⬇️ Tải Excel",
            data=buf.getvalue(),
            file_name=ten_file,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="dl_khtd_cn_matrix",
        )


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
            format="%.1f",
            help="Kế hoạch Chi nhánh (triệu đồng)"
        ),
        "Tổng xã (triệu)": st.column_config.NumberColumn(
            "Tổng xã (triệu)",
            format="%.1f",
            help="Tổng kế hoạch xã (triệu đồng)"
        ),
        "Chênh lệch (triệu)": st.column_config.NumberColumn(
            "Chênh lệch (triệu)",
            format="%.1f",
            help="Chênh lệch (triệu đồng)"
        ),
        "Tỷ lệ phân bổ %": st.column_config.NumberColumn(
            "Tỷ lệ phân bổ %",
            format="%.1f%%",
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
        st.download_button(
            label="⬇ Tải file Excel",
            data=buf.getvalue(),
            file_name=f"CanhBao_KHTD_{datetime.today().strftime('%d%m%Y')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="dl_chenh_lech_excel",
        )


def render_xuat_baocao() -> None:
    _tab_canh_bao_chenh_lech()

