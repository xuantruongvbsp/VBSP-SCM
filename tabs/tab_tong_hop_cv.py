"""Dashboard tổng hợp — kết hợp Tiến độ Công việc + Nhiệm vụ định kỳ."""
from __future__ import annotations

from datetime import date, timedelta

import streamlit as st
import db
from config import LOAI_CONG_VIEC, UU_TIEN_CV
from services import tien_do_service
from tabs.base_tab import TabContext
from utils import fmt_ngay


_NGUONG_CANH_BAO = 3   # ngày


def _lay_canh_bao_deadline(nguong_ngay: int = _NGUONG_CANH_BAO) -> dict:
    """Trả về {'tien_do': [...], 'nhiem_vu': [...]} sắp hết hạn trong nguong_ngay ngày."""
    hom_nay = date.today()
    moc = (hom_nay + timedelta(days=nguong_ngay)).isoformat()
    hom_nay_str = hom_nay.isoformat()

    canh_bao: dict = {"tien_do": [], "nhiem_vu": []}
    try:
        ds_task = tien_do_service.doc_tasks(chi_dang_theo_doi=True)
        canh_bao["tien_do"] = [
            t for t in ds_task
            if t.get("ngay_deadline") and hom_nay_str <= t["ngay_deadline"] <= moc
        ]
    except Exception:
        pass
    try:
        with db.get_conn() as conn:
            rows = conn.execute(
                """SELECT id, tieu_de, ngay_deadline, trang_thai, pgd
                   FROM nhiem_vu
                   WHERE ngay_deadline IS NOT NULL
                     AND trang_thai NOT IN ('da_hoan_thanh')
                     AND ngay_deadline BETWEEN ? AND ?
                   ORDER BY ngay_deadline""",
                (hom_nay_str, moc),
            ).fetchall()
        canh_bao["nhiem_vu"] = [dict(r) for r in rows]
    except Exception:
        pass
    return canh_bao


def _kpi_tien_do() -> dict:
    """Tính KPI cho module Tiến độ Công việc."""
    try:
        ds_task = tien_do_service.doc_tasks(chi_dang_theo_doi=True)
        hom_nay = date.today().isoformat()
        tong_task = len(ds_task)
        tong_xa = 0
        tong_xong = 0
        tong_tre = 0
        for t in ds_task:
            kq = tien_do_service.doc_ketqua_task(t["id"])
            tong_xa += len(kq)
            for r in kq:
                if r["trang_thai"] == "da_hoan_thanh":
                    tong_xong += 1
                elif r["trang_thai"] == "chua_thuc_hien" and t["ngay_deadline"] < hom_nay:
                    tong_tre += 1
        pct = round(tong_xong / tong_xa * 100) if tong_xa else 0
        return {"tong": tong_task, "xong": tong_xong, "tong_xa": tong_xa,
                "tre": tong_tre, "pct": pct}
    except Exception:
        return {"tong": 0, "xong": 0, "tong_xa": 0, "tre": 0, "pct": 0}


def _kpi_nhiem_vu() -> dict:
    """Tính KPI cho module Nhiệm vụ định kỳ."""
    try:
        with db.get_conn() as conn:
            row = conn.execute(
                """SELECT
                     COUNT(*)                                          AS tong,
                     SUM(trang_thai = 'da_hoan_thanh')                AS xong,
                     SUM(trang_thai = 'dang_thuc_hien')               AS dang,
                     SUM(trang_thai = 'cho_thuc_hien')                AS cho
                   FROM nhiem_vu"""
            ).fetchone()
            cho_duyet = conn.execute(
                "SELECT COUNT(*) FROM nhiem_vu_ketqua WHERE trang_thai = 'cho_duyet'"
            ).fetchone()[0]
        return {
            "tong":      int(row["tong"] or 0),
            "xong":      int(row["xong"] or 0),
            "dang":      int(row["dang"] or 0),
            "cho":       int(row["cho"] or 0),
            "cho_duyet": int(cho_duyet or 0),
        }
    except Exception:
        return {"tong": 0, "xong": 0, "dang": 0, "cho": 0, "cho_duyet": 0}


def _bang_can_chu_y() -> list[dict]:
    """Đầu việc trễ hạn hoặc sắp trễ (trong 7 ngày)."""
    try:
        hom_nay = date.today().isoformat()
        moc_7 = (date.today() + timedelta(days=7)).isoformat()
        ds_task = tien_do_service.doc_tasks(chi_dang_theo_doi=True)
        result = []
        for t in ds_task:
            dl = t.get("ngay_deadline", "")
            if dl <= moc_7:
                kq = tien_do_service.doc_ketqua_task(t["id"])
                so_xa = len(kq)
                so_xong = sum(1 for r in kq if r["trang_thai"] == "da_hoan_thanh")
                pct_all = [int(r.get("pct_hoan_thanh") or 0) for r in kq]
                pct_avg = round(sum(pct_all) / len(pct_all)) if pct_all else 0
                pct_hien = pct_avg if pct_avg > 0 else (round(so_xong / so_xa * 100) if so_xa else 0)
                result.append({
                    "Đầu việc": t["tieu_de"],
                    "Deadline": fmt_ngay(dl),
                    "% HT": pct_hien,
                    "Xong/Tổng": f"{so_xong}/{so_xa}",
                    "Trạng thái": "🔴 Trễ" if dl < hom_nay else "🟡 Sắp trễ",
                })
        return sorted(result, key=lambda x: x["Deadline"])
    except Exception:
        return []


def _bang_nhiem_vu_cho_duyet() -> list[dict]:
    """Kết quả nhiệm vụ đang chờ duyệt."""
    try:
        with db.get_conn() as conn:
            rows = conn.execute(
                """SELECT nv.tieu_de, kq.pgd, kq.ngay_nhap, kq.trang_thai
                   FROM nhiem_vu_ketqua kq
                   JOIN nhiem_vu nv ON nv.id = kq.nhiem_vu_id
                   WHERE kq.trang_thai = 'cho_duyet'
                   ORDER BY kq.ngay_nhap DESC
                   LIMIT 30"""
            ).fetchall()
        return [
            {
                "Nhiệm vụ": r["tieu_de"],
                "PGD": r["pgd"],
                "Ngày nộp": (r["ngay_nhap"] or "")[:10],
            }
            for r in rows
        ]
    except Exception:
        return []


def _hien_thi_ket_qua_search(tu_khoa: str) -> None:
    """Tìm kiếm full-text trên cả tien_do_task lẫn nhiem_vu."""
    pattern = f"%{tu_khoa}%"
    td_rows, nv_rows = [], []
    try:
        with db.get_conn() as conn:
            td_rows = [
                dict(r) for r in conn.execute(
                    """SELECT id, tieu_de, mo_ta, ngay_deadline, trang_thai, loai, uu_tien
                       FROM tien_do_task
                       WHERE (tieu_de LIKE ? OR mo_ta LIKE ?) AND trang_thai = 'dang_theo_doi'
                       ORDER BY ngay_deadline
                       LIMIT 20""",
                    (pattern, pattern),
                ).fetchall()
            ]
            nv_rows = [
                dict(r) for r in conn.execute(
                    """SELECT id, tieu_de, mo_ta, chu_ky, ky, trang_thai, pgd, ngay_deadline
                       FROM nhiem_vu
                       WHERE (tieu_de LIKE ? OR mo_ta LIKE ?)
                       ORDER BY ngay_deadline DESC
                       LIMIT 20""",
                    (pattern, pattern),
                ).fetchall()
            ]
    except Exception:
        pass

    if not td_rows and not nv_rows:
        st.info(f"Không tìm thấy kết quả nào khớp với **{tu_khoa}**.")
        return

    c_td, c_nv = st.columns(2)
    with c_td:
        st.markdown(f"**📅 Đầu việc** ({len(td_rows)} kết quả)")
        if td_rows:
            import pandas as pd
            from config import LOAI_CONG_VIEC, UU_TIEN_CV
            df_td = pd.DataFrame([
                {
                    "Tiêu đề": r["tieu_de"],
                    "Loại": LOAI_CONG_VIEC.get(r.get("loai", ""), r.get("loai", "")),
                    "Ưu tiên": UU_TIEN_CV.get(r.get("uu_tien", ""), ""),
                    "Deadline": fmt_ngay(r.get("ngay_deadline", "")),
                }
                for r in td_rows
            ])
            st.dataframe(df_td, use_container_width=True, hide_index=True)
        else:
            st.caption("—")

    with c_nv:
        st.markdown(f"**📌 Nhiệm vụ** ({len(nv_rows)} kết quả)")
        if nv_rows:
            import pandas as pd
            from tabs.tab_nhiem_vu import _NHAN_TRANG_THAI_NV, _NHAN_CHU_KY
            df_nv = pd.DataFrame([
                {
                    "Tiêu đề": r["tieu_de"],
                    "Kỳ": r.get("ky", ""),
                    "PGD": r.get("pgd") or "Tất cả",
                    "Trạng thái": _NHAN_TRANG_THAI_NV.get(r.get("trang_thai", ""), ""),
                }
                for r in nv_rows
            ])
            st.dataframe(df_nv, use_container_width=True, hide_index=True)
        else:
            st.caption("—")


def render(tab=None, **kwargs) -> None:
    _ctx = TabContext(tab, **kwargs)
    with _ctx:
        st.subheader("� Dashboard Tổng quan Công việc")

        # ── Cảnh báo deadline ────────────────────────────────────────────
        alert_key = "_tong_hop_alert_dismissed"
        if not st.session_state.get(alert_key):
            canh_bao = _lay_canh_bao_deadline()
            ds_alert = canh_bao["tien_do"] + canh_bao["nhiem_vu"]
            if ds_alert:
                with st.container():
                    c_msg, c_btn = st.columns([5, 1])
                    with c_msg:
                        ten_list = ", ".join(
                            f"**{x.get('tieu_de', '')}**" for x in ds_alert[:3]
                        )
                        suffix = f" và {len(ds_alert) - 3} mục khác" if len(ds_alert) > 3 else ""
                        st.warning(
                            f"🔴 **{len(ds_alert)} mục sắp hết hạn trong {_NGUONG_CANH_BAO} ngày tới:** "
                            f"{ten_list}{suffix}"
                        )
                    with c_btn:
                        if st.button("✕ Ẩn", key="_tong_hop_dismiss_alert", use_container_width=True):
                            st.session_state[alert_key] = True
                            st.rerun()

        # ── KPI row ──────────────────────────────────────────────────────
        kpi_td = _kpi_tien_do()
        kpi_nv = _kpi_nhiem_vu()

        st.markdown("##### 📊 Tiến độ Công việc")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Đầu việc đang theo dõi", kpi_td["tong"])
        c2.metric("✅ % Hoàn thành", f"{kpi_td['pct']}%",
                  f"{kpi_td['xong']}/{kpi_td['tong_xa']} xã/PGD")
        c3.metric("🔴 Trễ hạn", kpi_td["tre"], delta_color="inverse")
        c4.metric("⬜ Chưa báo cáo",
                  kpi_td["tong_xa"] - kpi_td["xong"] - kpi_td["tre"])

        st.markdown("##### 📌 Nhiệm vụ định kỳ")
        c5, c6, c7, c8 = st.columns(4)
        c5.metric("Tổng nhiệm vụ", kpi_nv["tong"])
        c6.metric("✅ Hoàn thành", kpi_nv["xong"])
        c7.metric("🔄 Đang thực hiện", kpi_nv["dang"])
        c8.metric("⏳ Chờ duyệt kết quả", kpi_nv["cho_duyet"],
                  delta_color="off" if kpi_nv["cho_duyet"] == 0 else "inverse")

        st.divider()

        # ── Tìm kiếm xuyên suốt ──────────────────────────────────────────
        tu_khoa = st.text_input(
            "🔍 Tìm kiếm đầu việc & nhiệm vụ...",
            placeholder="Nhập từ khoá — tìm cả Tiến độ Công việc lẫn Nhiệm vụ định kỳ",
            key="_tong_hop_global_search",
            label_visibility="collapsed",
        )
        if tu_khoa and tu_khoa.strip():
            _hien_thi_ket_qua_search(tu_khoa.strip())
            st.divider()

        # ── Bảng cần chú ý ───────────────────────────────────────────────
        tab_td, tab_nv = st.tabs([
            "⚠️ Đầu việc cần chú ý",
            "📋 Nhiệm vụ chờ duyệt",
        ])

        with tab_td:
            rows_td = _bang_can_chu_y()
            if rows_td:
                import pandas as pd
                st.dataframe(
                    pd.DataFrame(rows_td),
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                st.success("✅ Không có đầu việc trễ hạn hoặc sắp trễ.")

        with tab_nv:
            rows_nv = _bang_nhiem_vu_cho_duyet()
            if rows_nv:
                import pandas as pd
                st.dataframe(
                    pd.DataFrame(rows_nv),
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                st.info("Không có kết quả nhiệm vụ chờ duyệt.")
