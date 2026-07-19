"""
Tab Dashboard CBTD & Địa bàn — Tổng quan nhóm CBTD + ĐGD + Tổ TK&VV.

Hiển thị:
  - Row 1 : KPI cards (số CBTD, ĐGD, Tổ, điểm TB, %)
  - Row 2 : Cảnh báo thông minh (ĐGD thiếu CBTD, CBTD QH cao, Tổ TB/Yếu liên tiếp)
  - Row 3 : Bảng pivot CBTD → ĐGD → Tổ → điểm
  - Row 4 : Xuất báo cáo cross-mảng (Excel nhiều sheet)
"""
from __future__ import annotations

from io import BytesIO
from datetime import datetime
from typing import TYPE_CHECKING

import pandas as pd
import streamlit as st

import db
from logger import get_logger
from auth import la_phan_he_cn, la_executive, normalize_role
from components.delta_card import kpi_row
from data.khtd import doc_cbtd
from tabs.base_tab import TabContext
from utils import fmt_so, hien_thi_dataframe_phan_trang
from services.cbtd_dia_ban_service import (
    canh_bao_cbtd_dia_ban,
    lay_to_theo_cbtd,
    tom_tat_kpi,
)

logger = get_logger(__name__)

if TYPE_CHECKING:
    from streamlit.delta_generator import DeltaGenerator


def _doc_cdtotkvv_moi_nhat() -> "pd.DataFrame | None":
    """Đọc file CDTOTKVV tháng gần nhất (tập trung từ pgd_data)."""
    try:
        from services.cdtotkvv_service import tong_hop_tu_pgd_data
        return tong_hop_tu_pgd_data()
    except Exception as e:
        logger.error("_doc_cdtotkvv_moi_nhat: lỗi đọc CDTOTKVV — %s", e, exc_info=True)
        return None


def _doc_cdtotkvv_ky_goc() -> "pd.DataFrame | None":
    """Đọc CDTOTKVV kỳ gốc: tháng 12 năm trước, fallback kỳ cũ nhất."""
    try:
        from data.cdtotkvv import doc_cdtotkvv, ds_thang_nam

        def _sort_key(s: str) -> tuple:
            try:
                mm, yyyy = s.split("/")
                return (int(yyyy), int(mm))
            except (ValueError, IndexError):
                return (0, 0)

        ds = sorted(ds_thang_nam(), key=_sort_key)
        if not ds:
            return None
        latest = ds[-1]
        try:
            mm_l, yyyy_l = latest.split("/")
            moc = f"12/{int(yyyy_l) - 1}"
        except (ValueError, IndexError):
            return doc_cdtotkvv(ds[0])
        if moc in ds:
            return doc_cdtotkvv(moc)
        for ky in reversed(ds):
            try:
                mm_k, yyyy_k = ky.split("/")
                if (int(yyyy_k), int(mm_k)) <= (int(yyyy_l) - 1, 12):
                    return doc_cdtotkvv(ky)
            except (ValueError, IndexError):
                continue
        return doc_cdtotkvv(ds[0])
    except Exception as e:
        logger.error("_doc_cdtotkvv_ky_goc: %s", e, exc_info=True)
        return None


def _build_bang_pivot(
    cbtd_data: dict,
    dgd_map: dict,
    to_theo_cbtd: dict[str, list[dict]],
) -> pd.DataFrame:
    """
    Pivot CBTD → ĐGD → Tổ → điểm thành DataFrame phẳng.
    """
    rows = []
    for ma_cb, info in cbtd_data.items():
        pgd_cb   = info.get("pgd", "—")
        ho_ten   = info.get("ho_ten", "")
        ds_dgd   = info.get("ds_dgd", [])
        so_to    = len(to_theo_cbtd.get(ma_cb, []))
        to_yeu   = sum(
            1 for t in to_theo_cbtd.get(ma_cb, [])
            if t.get("xep_loai") in ("Yếu", "Trung bình")
        )
        diem_list = [
            t["tong_diem"] for t in to_theo_cbtd.get(ma_cb, [])
            if t.get("tong_diem") is not None
        ]
        diem_tb_cb = round(sum(diem_list) / len(diem_list), 1) if diem_list else None
        rows.append({
            "Mã CBTD":      ma_cb,
            "Họ tên":       ho_ten,
            "PGD":          pgd_cb,
            "Số ĐGD":       len(ds_dgd),
            "Số Tổ TK&VV":  so_to,
            "Tổ TB/Yếu":    to_yeu,
            "Điểm TB Tổ":   f"{diem_tb_cb:.1f}" if diem_tb_cb is not None else "—",
            "Trạng thái":   (
                "🔴 Có Tổ TB/Yếu" if to_yeu > 0
                else ("✅ Tốt" if so_to > 0 else "⚠️ Chưa dữ liệu")
            ),
        })
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def _xuat_excel_cross(
    cbtd_data: dict,
    dgd_map: dict,
    to_theo_cbtd: dict[str, list[dict]],
    canh_baos: list[dict],
    df_pivot: pd.DataFrame,
) -> bytes:
    """Xuất Excel nhiều sheet: Summary, Chi tiết CBTD, Tổ TB/Yếu, Cảnh báo."""
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        if not df_pivot.empty:
            df_pivot.to_excel(w, index=False, sheet_name="Tổng hợp CBTD")

        for ma_cb, tos in to_theo_cbtd.items():
            if not tos:
                continue
            info = cbtd_data.get(ma_cb, {})
            df_cb = pd.DataFrame(tos)
            df_cb.insert(0, "Mã CBTD", ma_cb)
            df_cb.insert(1, "Họ tên", info.get("ho_ten", ""))
            sheet_name = f"CB_{ma_cb}"[:31]
            df_cb.to_excel(w, index=False, sheet_name=sheet_name)

        rows_yeu = [
            t | {"ma_cb": ma_cb, "ho_ten": cbtd_data.get(ma_cb, {}).get("ho_ten", "")}
            for ma_cb, tos in to_theo_cbtd.items()
            for t in tos
            if t.get("xep_loai") in ("Yếu", "Trung bình")
        ]
        if rows_yeu:
            pd.DataFrame(rows_yeu).to_excel(w, index=False, sheet_name="Tổ TB_Yếu")

        if canh_baos:
            df_cb_list = pd.DataFrame([
                {"Mức độ": c["muc_do"], "Loại": c["loai"], "Nội dung": c["noi_dung"]}
                for c in canh_baos
            ])
            df_cb_list.to_excel(w, index=False, sheet_name="Cảnh báo")

    return buf.getvalue()


def render(tab: "DeltaGenerator | None" = None, **kwargs) -> None:
    df       = kwargs.get("df")
    role_raw = str(kwargs.get("role", "user") or "user")
    role     = normalize_role(role_raw)
    username = kwargs.get("username", "unknown")

    ctx = TabContext(tab, **kwargs)
    with ctx:
        st.subheader("📊 Dashboard CBTD & Địa bàn")
        st.caption("Tổng quan liên kết: Cán bộ tín dụng — Điểm giao dịch — Tổ TK&VV")

        cbtd_data: dict = doc_cbtd()
        dgd_map: dict   = db.doc_dgd_map() or {}

        # Dữ liệu Tổ TK&VV
        df_cdto = _doc_cdtotkvv_moi_nhat()
        df_cdto_truoc = _doc_cdtotkvv_ky_goc()

        # ── KPI Row ───────────────────────────────────────────────────────────
        kpi = tom_tat_kpi(cbtd_data, dgd_map, df_cdto)

        kpi_row(
            cols=[
                {
                    "label":  "Số CBTD",
                    "value":  fmt_so(kpi["so_cbtd"]),
                    "icon":   "👔",
                },
                {
                    "label":  "Tổng ĐGD",
                    "value":  fmt_so(kpi["so_dgd_tong"]),
                    "suffix": f" (⚠️ {kpi['so_dgd_chua_phan']} chưa phân)" if kpi["so_dgd_chua_phan"] else "",
                    "icon":   "📍",
                },
                {
                    "label":  "Tổng Tổ TK&VV",
                    "value":  fmt_so(kpi["so_to_tong"]),
                    "icon":   "🏘️",
                },
                {
                    "label":  "Điểm TB Tổ",
                    "value":  f"{kpi['diem_tb']:.1f}" if kpi["so_to_tong"] else "—",
                    "icon":   "⭐",
                },
                {
                    "label":  "% Tổ đạt (Tốt+Khá)",
                    "value":  f"{kpi['pct_to_dat']:.1f}%" if kpi["so_to_tong"] else "—",
                    "icon":   "✅",
                },
                {
                    "label":  "Tổ TB/Yếu",
                    "value":  fmt_so(kpi["so_to_tb_yeu"]),
                    "icon":   "🔴" if kpi["so_to_tb_yeu"] > 0 else "🟢",
                },
            ],
            num_columns=6,
        )

        st.divider()

        # ── Cảnh báo thông minh ───────────────────────────────────────────────
        canh_baos = canh_bao_cbtd_dia_ban(
            cbtd_data, dgd_map, df, df_cdto, df_cdto_truoc
        )

        so_canh_bao = len(canh_baos)
        header_cb = (
            f"🔔 Cảnh báo ({so_canh_bao})" if so_canh_bao
            else "✅ Không có cảnh báo"
        )
        with st.expander(header_cb, expanded=(so_canh_bao > 0)):
            if not canh_baos:
                st.success("Mọi ĐGD đã có CBTD, không có CBTD QH cao, không có Tổ TB/Yếu liên tiếp.")
            else:
                nhom_dgd    = [c for c in canh_baos if c["loai"] == "dgd_thieu_cbtd"]
                nhom_qh     = [c for c in canh_baos if c["loai"] == "cbtd_qh_cao"]
                nhom_to     = [c for c in canh_baos if c["loai"] == "to_yeu_lien_tiep"]

                if nhom_dgd:
                    st.markdown(f"**⚠️ ĐGD chưa có CBTD ({len(nhom_dgd)})**")
                    for c in nhom_dgd:
                        st.caption(f"• {c['noi_dung']}")
                if nhom_qh:
                    st.markdown(f"**🔴 CBTD có tỷ lệ QH cao ({len(nhom_qh)})**")
                    for c in nhom_qh:
                        st.warning(c["noi_dung"])
                if nhom_to:
                    st.markdown(f"**🔴 Tổ TB/Yếu liên tiếp 2+ tháng ({len(nhom_to)})**")
                    for c in nhom_to:
                        st.error(c["noi_dung"])

        st.divider()

        # ── Bảng pivot CBTD → ĐGD → Tổ ──────────────────────────────────────
        st.markdown("**📋 Bảng tổng hợp CBTD → Tổ TK&VV**")

        to_theo_cbtd = lay_to_theo_cbtd(cbtd_data, dgd_map, df_cdto)
        df_pivot = _build_bang_pivot(cbtd_data, dgd_map, to_theo_cbtd)

        if df_pivot.empty:
            st.info("Chưa có dữ liệu CBTD hoặc chưa cấu hình ĐGD.")
        else:
            hien_thi_dataframe_phan_trang(
                df_pivot,
                key="cbtd_db_pivot",
                column_config={
                    "Tổ TB/Yếu": st.column_config.NumberColumn(
                        "Tổ TB/Yếu", help="Số Tổ xếp loại Trung bình hoặc Yếu"
                    ),
                    "Điểm TB Tổ": st.column_config.TextColumn("Điểm TB Tổ"),
                },
            )

        # ── Xuất báo cáo cross-mảng ───────────────────────────────────────────
        st.divider()
        st.markdown("**📥 Xuất báo cáo tổng hợp cross-mảng**")
        st.caption("Excel gồm: Tổng hợp CBTD · Chi tiết từng CBTD · Tổ TB/Yếu · Cảnh báo")

        if st.button("📊 Tạo báo cáo tổng hợp", key="cbtd_db_btn_xuat"):
            try:
                excel_bytes = _xuat_excel_cross(
                    cbtd_data, dgd_map, to_theo_cbtd, canh_baos, df_pivot
                )
                st.session_state["_cbtd_db_excel"] = excel_bytes
                st.session_state["_cbtd_db_fname"] = (
                    f"BC_CBTD_DiaBan_{datetime.today().strftime('%d%m%Y')}.xlsx"
                )
                db.ghi_audit(username, "xuat_bc_cbtd_dia_ban",
                             f"so_cbtd={len(cbtd_data)} canh_bao={so_canh_bao}")
                st.success("✅ Đã tạo file Excel!")
            except Exception as e:
                logger.error("xuat_bc_cbtd: lỗi tạo Excel — %s", e, exc_info=True)
                st.error(f"❌ Lỗi tạo báo cáo: {e}")

        if st.session_state.get("_cbtd_db_excel"):
            st.download_button(
                "⬇ Tải Excel",
                data=st.session_state["_cbtd_db_excel"],
                file_name=st.session_state.get("_cbtd_db_fname", "BC_CBTD.xlsx"),
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="cbtd_db_dl_excel",
            )
