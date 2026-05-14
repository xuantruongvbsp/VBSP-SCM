from __future__ import annotations

import json
from datetime import datetime, date
from io import BytesIO

import pandas as pd
import plotly.express as px
import streamlit as st

import db
from auth import normalize_role
from config import DS_PGD, DON_VI_CHI_NHANH, PGD_XA_MAP, ROLES_PHAN_HE_CN
from utils import get_tab_context

DS_PGD_ALL = [DON_VI_CHI_NHANH] + DS_PGD

LOAI_TASK = {
    "chung":            "📋 Công việc chung",
    "chi_tieu_khtd":    "🎯 Chỉ tiêu KHTD",
    "ho_so_rui_ro":     "🗂️ Hồ sơ rủi ro",
    "khao_sat_nhu_cau": "📊 Khảo sát nhu cầu vay vốn",
    "bao_cao":          "📄 Báo cáo",
    "tap_huan":         "🎓 Tập huấn",
    "giao_dich_xa":     "📅 Giao dịch xã",
    "uy_thac":          "🤝 Hoạt động ủy thác",
    "nguon_von":        "💰 Nguồn vốn",
    "ban_dai_dien":     "📑 Ban đại diện HĐQT",
    "khac":             "Khác",
}
UU_TIEN = {
    "khan_cap":    "🔴 Khẩn cấp",
    "quan_trong":  "🟡 Quan trọng",
    "binh_thuong": "🟢 Bình thường",
}
TS_KQ_LABEL = {
    "chua_thuc_hien": "⬜ Chưa",
    "da_hoan_thanh":  "✅ Xong",
    "khong_ap_dung":  "➖ N/A",
}
UU_TIEN_ORDER = {"khan_cap": 0, "quan_trong": 1, "binh_thuong": 2}


def _doc_tasks(chi_dang_theo_doi: bool = True) -> list[dict]:
    with db.get_conn() as conn:
        sql = "SELECT * FROM tien_do_task"
        if chi_dang_theo_doi:
            sql += " WHERE trang_thai = 'dang_theo_doi'"
        sql += " ORDER BY ngay_deadline ASC"
        return [dict(r) for r in conn.execute(sql).fetchall()]


def _doc_ketqua_task(task_id: int) -> list[dict]:
    with db.get_conn() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM tien_do_ketqua WHERE task_id=? ORDER BY pgd, ten_xa",
            (task_id,),
        ).fetchall()]


def _khoi_tao_ketqua_task(task_id: int, ds_pgd_task: list[str],
                           cap_theo_doi: str = "xa",
                           loai_noi_dung: str = "chi_tiet_xa") -> None:
    rows = []
    if cap_theo_doi == "pgd":
        for pgd in ds_pgd_task:
            rows.append((task_id, pgd, pgd, loai_noi_dung))
    else:
        for pgd in ds_pgd_task:
            for xa in PGD_XA_MAP.get(pgd, []):
                rows.append((task_id, pgd, xa, loai_noi_dung))
    with db.get_conn() as conn:
        conn.executemany(
            """INSERT OR IGNORE INTO tien_do_ketqua
               (task_id, pgd, ten_xa, trang_thai, loai_noi_dung)
               VALUES (?, ?, ?, 'chua_thuc_hien', ?)""",
            rows,
        )
        conn.commit()


def _upsert_ketqua_xa(
    task_id: int, ten_xa: str, pgd: str,
    trang_thai: str, ngay_ht: str | None,
    ghi_chu: str | None, username: str,
) -> None:
    now = datetime.now().isoformat()
    with db.get_conn() as conn:
        conn.execute(
            """INSERT INTO tien_do_ketqua
               (task_id, pgd, ten_xa, trang_thai, ngay_hoan_thanh,
                ghi_chu, nguoi_nhap, ngay_nhap)
               VALUES (?,?,?,?,?,?,?,?)
               ON CONFLICT(task_id, ten_xa) DO UPDATE SET
                 trang_thai      = excluded.trang_thai,
                 ngay_hoan_thanh = excluded.ngay_hoan_thanh,
                 ghi_chu         = excluded.ghi_chu,
                 nguoi_nhap      = excluded.nguoi_nhap,
                 ngay_nhap       = excluded.ngay_nhap""",
            (task_id, pgd, ten_xa, trang_thai,
             ngay_ht, ghi_chu, username, now),
        )
        conn.commit()


def _render_tong_quan(tab, **kwargs):
    import streamlit as _st
    _tab_ctx = tab if tab is not None else _st.container()
    with _tab_ctx:
        st.subheader("📊 Tổng quan tiến độ")

        c1, c2, c3 = st.columns([2, 1, 1])
        with c1:
            ngay_loc = st.date_input("Thời hạn đến ngày",
                                     value=date.today(), key="td_ngay")
        with c2:
            loai_loc = st.selectbox("Lọc loại", ["Tất cả"] + list(LOAI_TASK.values()),
                                    key="td_loai")
        with c3:
            nd_loc = st.selectbox("Loại nhiệm vụ",
                                  ["Tất cả", "Chung PGD", "Chi tiết xã"],
                                  key="td_nd")

        hom_nay = date.today().isoformat()
        ds_task = _doc_tasks()
        ds_task = [t for t in ds_task
                   if t["ngay_deadline"] <= ngay_loc.isoformat()]
        if loai_loc != "Tất cả":
            loai_key = next((k for k, v in LOAI_TASK.items() if v == loai_loc), None)
            ds_task = [t for t in ds_task if loai_key and t["loai"] == loai_key]
        if nd_loc != "Tất cả":
            nd_map = {"Chung PGD": "pgd", "Chi tiết xã": "xa"}
            ds_task = [t for t in ds_task if t.get("cap_theo_doi") == nd_map.get(nd_loc)]

        if not ds_task:
            st.info("Không có đầu việc nào trong khoảng thời gian đã chọn.")
            return

        all_kq = {t["id"]: _doc_ketqua_task(t["id"]) for t in ds_task}
        tong_xa = sum(len(v) for v in all_kq.values())
        tong_xong = sum(
            sum(1 for r in v if r["trang_thai"] == "da_hoan_thanh")
            for v in all_kq.values()
        )
        tong_tre = 0
        for t in ds_task:
            kq = all_kq.get(t["id"], [])
            for r in kq:
                if r["trang_thai"] == "chua_thuc_hien" and t["ngay_deadline"] < hom_nay:
                    tong_tre += 1

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Đầu việc", len(ds_task))
        c2.metric("✅ Hoàn thành",
                  f"{tong_xong}/{tong_xa}",
                  f"{round(tong_xong/tong_xa*100) if tong_xa else 0}%")
        c3.metric("🔴 Trễ hạn", tong_tre, delta_color="inverse")
        c4.metric("⬜ Chưa báo cáo", tong_xa - tong_xong - tong_tre)

        st.divider()

        st.markdown("#### 🗺️ Bảng tiến độ theo PGD")
        st.caption("Ô trong bảng = Hoàn thành / Tổng số. 🔴 = có đơn vị trễ hạn.")

        bang_rows = []
        for pgd in DS_PGD_ALL:
            row = {"Đơn vị": pgd}
            for t in ds_task:
                kq_pgd = [r for r in all_kq.get(t["id"], []) if r["pgd"] == pgd]
                if not kq_pgd:
                    row[t["tieu_de"][:18]] = "—"
                    continue
                xong = sum(1 for r in kq_pgd if r["trang_thai"] == "da_hoan_thanh")
                tre = sum(1 for r in kq_pgd
                          if r["trang_thai"] == "chua_thuc_hien"
                          and t["ngay_deadline"] < hom_nay)
                tong = len(kq_pgd)
                ky_hieu = "🔴 " if tre > 0 else ("✅ " if xong == tong else "")
                row[t["tieu_de"][:18]] = f"{ky_hieu}{xong}/{tong}"
            bang_rows.append(row)

        df_pgd = pd.DataFrame(bang_rows)
        st.dataframe(df_pgd, use_container_width=True, hide_index=True, height=620)

        st.divider()

        st.markdown("#### 📈 Tỷ lệ hoàn thành theo đầu việc")
        chart_rows = []
        for t in ds_task:
            kq = all_kq.get(t["id"], [])
            xong = sum(1 for r in kq if r["trang_thai"] == "da_hoan_thanh")
            tong = len(kq)
            chart_rows.append({
                "Đầu việc": t["tieu_de"][:35],
                "% Hoàn thành": round(xong / tong * 100) if tong else 0,
                "Ưu tiên": UU_TIEN.get(t["uu_tien"], ""),
                "Thời hạn": t["ngay_deadline"],
            })
        df_chart = pd.DataFrame(chart_rows)
        color_map = {
            "🔴 Khẩn cấp": "#ef4444",
            "🟡 Quan trọng": "#f59e0b",
            "🟢 Bình thường": "#22c55e",
        }
        fig = px.bar(
            df_chart, x="% Hoàn thành", y="Đầu việc",
            orientation="h", color="Ưu tiên",
            color_discrete_map=color_map,
            text="% Hoàn thành", range_x=[0, 100],
            height=max(300, len(ds_task) * 50),
        )
        fig.update_traces(texttemplate="%{text}%", textposition="outside")
        fig.update_layout(margin=dict(l=10, r=40, t=30, b=10))
        st.plotly_chart(fig, use_container_width=True, key="td_chart_tongquan")

        st.divider()

        st.markdown("#### 🔍 Drill-down theo PGD")
        col_pgd, col_task = st.columns(2)
        with col_pgd:
            pgd_dd = st.selectbox("Chọn đơn vị", DS_PGD_ALL, key="td_dd_pgd")
        with col_task:
            task_dd_options = {t["id"]: t["tieu_de"] for t in ds_task}
            task_dd_id = st.selectbox(
                "Chọn đầu việc",
                options=list(task_dd_options.keys()),
                format_func=lambda x: task_dd_options[x],
                key="td_dd_task",
            )

        if pgd_dd and task_dd_id:
            kq_xa = [r for r in all_kq.get(task_dd_id, []) if r["pgd"] == pgd_dd]
            task_sel = next((t for t in ds_task if t["id"] == task_dd_id), None)

            if not kq_xa or task_sel is None:
                st.info(f"{pgd_dd} không có xã nào trong đầu việc này.")
            else:
                xong = sum(1 for r in kq_xa if r["trang_thai"] == "da_hoan_thanh")
                st.caption(
                    f"**{pgd_dd}** — {task_sel['tieu_de']} · "
                    f"Hoàn thành: **{xong}/{len(kq_xa)}** · "
                    f"Thời hạn: {task_sel['ngay_deadline']}"
                )
                df_xa = pd.DataFrame([
                    {
                        "Xã / Phường": r["ten_xa"],
                        "Trạng thái": TS_KQ_LABEL.get(r["trang_thai"], r["trang_thai"]),
                        "Ngày HT": r.get("ngay_hoan_thanh") or "—",
                        "Ghi chú": r.get("ghi_chu") or "",
                        "Người nhập": r.get("nguoi_nhap") or "",
                    }
                    for r in kq_xa
                ])
                st.dataframe(df_xa, use_container_width=True, hide_index=True)


def _render_tao_task(tab, **kwargs):
    username = kwargs.get("username", "")
    _tab_ctx = tab if tab is not None else __import__('streamlit').container()
    with _tab_ctx:
        st.subheader("➕ Tạo đầu việc mới")

        with st.expander("📖 Hướng dẫn tạo đầu việc", expanded=False):
            st.markdown("""
**1. Tên đầu việc** — Đặt tên ngắn gọn, rõ ràng.  
VD: *Nộp hồ sơ rủi ro tháng 5/2026*, *Khảo sát nhu cầu vay vốn Q2*

**2. Mô tả / Hướng dẫn** — Ghi rõ nội dung cần thực hiện, tài liệu tham khảo,
lưu ý đặc biệt để PGD/CBTD biết cần làm gì.

**3. Loại** — Phân loại đầu việc:
- 📋 Công việc chung — việc hành chính, tổng hợp
- 🎯 Chỉ tiêu KHTD — giao/điều chỉnh chỉ tiêu tín dụng cho PGD/xã
- 🗂️ Hồ sơ rủi ro — liên quan nợ xấu, NQH, xử lý rủi ro
- 📊 Khảo sát nhu cầu — điều tra nhu cầu vay vốn
- 📄 Báo cáo — các loại báo cáo định kỳ, thống kê
- 🎓 Tập huấn — đào tạo, hướng dẫn nghiệp vụ
- 📅 Giao dịch xã — tổ chức, kiểm tra hoạt động giao dịch xã
- 🤝 Hoạt động ủy thác — kiểm tra, giám sát 4 tổ chức CT-XH
- 💰 Nguồn vốn — theo dõi quỹ, điện báo xin vốn, huy động
- 📑 Ban đại diện HĐQT — phiên họp, nghị quyết, kiểm tra giám sát

**4. Loại theo dõi** — Quan trọng!
- 📍 **Chi tiết từng xã** — hệ thống tạo 1 dòng theo dõi cho mỗi xã/phường  
  → Dùng khi cần biết xã nào đã làm, xã nào chưa
- 🏢 **Chung PGD** — hệ thống tạo 1 dòng theo dõi cho mỗi PGD  
  → Dùng khi chỉ cần biết PGD đã hoàn thành chưa

**5. Ưu tiên** — 🔴 Khẩn cấp / 🟡 Quan trọng / 🟢 Bình thường  
Ảnh hưởng màu sắc hiển thị trong biểu đồ tổng quan.

**6. Ngày bắt đầu & Hạn hoàn thành** — Xác định khung thời gian.  
Sau thời hạn hệ thống tự đánh dấu 🔴 trễ hạn.

**7. Áp dụng cho đơn vị** — Mặc định tất cả 22 đơn vị.  
Bỏ chọn nếu chỉ áp dụng cho một số PGD cụ thể.

**8. Người phụ trách** — Ghi tên cán bộ chịu trách nhiệm theo dõi đầu việc này.
            """)

        with st.form("form_tao_task", clear_on_submit=True):
            tieu_de = st.text_input("Tên đầu việc *",
                                    placeholder="VD: Nộp hồ sơ rủi ro tháng 5/2026")
            mo_ta = st.text_area("Mô tả / Hướng dẫn")

            c1, c2 = st.columns(2)
            with c1:
                loai = st.selectbox("Loại", list(LOAI_TASK.keys()),
                                    format_func=lambda x: LOAI_TASK[x])
                loai_theo_doi = st.radio(
                    "Loại theo dõi",
                    options=["xa", "pgd"],
                    format_func=lambda x: "📍 Chi tiết từng xã" if x == "xa" else "🏢 Chung PGD",
                    horizontal=True,
                    key="td_tao_loai_theo_doi",
                )
                uu_tien = st.selectbox("Ưu tiên", list(UU_TIEN.keys()),
                                       format_func=lambda x: UU_TIEN[x], index=2)
                nguoi_phu_trach = st.text_input(
                    "Người phụ trách",
                    placeholder="Tên người phụ trách chính",
                )
            with c2:
                deadline = st.date_input("Thời hạn hoàn thành *", value=date.today())
                ngay_bat_dau = st.date_input(
                    "Ngày bắt đầu",
                    value=date.today(),
                    key="td_ngay_bat_dau",
                )
                pgd_chon = st.multiselect(
                    "Áp dụng cho đơn vị",
                    DS_PGD_ALL, default=DS_PGD_ALL,
                    placeholder="Mặc định: tất cả 22 đơn vị",
                )

            ds_preview = pgd_chon or DS_PGD_ALL
            if loai_theo_doi == "pgd":
                st.caption(f"🏢 {len(ds_preview)} đơn vị — theo dõi cấp PGD")
            else:
                tong_xa_preview = sum(
                    len(PGD_XA_MAP.get(p, [])) for p in ds_preview
                )
                st.caption(
                    f"📍 {len(ds_preview)} đơn vị · {tong_xa_preview} xã/phường"
                )
            with st.expander(f"Xem chi tiết sẽ áp dụng", expanded=False):
                for pgd in ds_preview:
                    if loai_theo_doi == "pgd":
                        st.markdown(f"**{pgd}**")
                    else:
                        ds_xa = PGD_XA_MAP.get(pgd, [])
                        if ds_xa:
                            st.markdown(f"**{pgd}** ({len(ds_xa)} xã)")
                            st.write(" — ".join(ds_xa))

            ghi_chu = st.text_input("Ghi chú thêm")
            submitted = st.form_submit_button("💾 Tạo đầu việc", type="primary")

        if submitted:
            if not tieu_de.strip():
                st.error("Vui lòng nhập tên đầu việc.")
                return
            pgd_luu = pgd_chon or DS_PGD_ALL
            ds_pgd_json = json.dumps(pgd_luu, ensure_ascii=False)
            try:
                with db.get_conn() as conn:
                    cur = conn.execute(
                        """INSERT INTO tien_do_task
                           (tieu_de, mo_ta, ngay_deadline, ds_pgd, loai,
                            uu_tien, nguoi_tao, ngay_tao, trang_thai, ghi_chu,
                            cap_theo_doi, ngay_bat_dau, nguoi_phu_trach)
                           VALUES (?,?,?,?,?,?,?,?,'dang_theo_doi',?,?,?,?)""",
                        (tieu_de.strip(), mo_ta.strip() or None,
                         deadline.isoformat(), ds_pgd_json,
                         loai, uu_tien, username,
                         datetime.now().isoformat(),
                         ghi_chu.strip() or None,
                         loai_theo_doi,
                         ngay_bat_dau.isoformat(),
                         nguoi_phu_trach.strip() or None),
                    )
                    task_id = cur.lastrowid
                    conn.commit()

                loai_noi_dung = "chung_pgd" if loai_theo_doi == "pgd" else "chi_tiet_xa"
                _khoi_tao_ketqua_task(task_id, pgd_luu, loai_theo_doi, loai_noi_dung)

                so_xa = (
                    sum(len(PGD_XA_MAP.get(p, [])) for p in pgd_luu)
                    if loai_theo_doi == "xa" else len(pgd_luu)
                )
                db.ghi_audit(username, "tien_do_tao_task",
                             f"'{tieu_de}' · thời hạn={deadline} · "
                             f"{len(pgd_luu)} PGD · "
                             f"{so_xa} đơn vị {loai_theo_doi} · "
                             f"cap_theo_doi={loai_theo_doi}")
                st.toast(f"✅ Đã tạo: {tieu_de}")
                st.rerun()
            except Exception as e:
                st.error(f"Lỗi: {e}")


def _render_quan_ly_task(tab, **kwargs):
    username = kwargs.get("username", "")
    role_raw = str(kwargs.get("role", "user") or "user")
    role = normalize_role(role_raw)

    _tab_ctx = tab if tab is not None else __import__("streamlit").container()
    with _tab_ctx:
        st.subheader("✏️ Quản lý đầu việc")

        ds_task = _doc_tasks(chi_dang_theo_doi=False)
        if not ds_task:
            st.info("Chưa có đầu việc nào.")
            return

        task_map = {t["id"]: t for t in ds_task}

        def _fmt_task(task_id: int) -> str:
            t = task_map.get(task_id) or {}
            stt = "[ĐANG]" if t.get("trang_thai") == "dang_theo_doi" else "[ĐÓNG]"
            return f"{stt} {t.get('tieu_de','')} · {t.get('ngay_deadline','')}"

        task_id = st.selectbox(
            "Chọn đầu việc",
            options=list(task_map.keys()),
            format_func=_fmt_task,
            key="td_ql_task",
        )
        task = task_map.get(task_id)
        if not task:
            return

        try:
            deadline_default = date.fromisoformat(str(task.get("ngay_deadline") or date.today().isoformat()))
        except Exception:
            deadline_default = date.today()

        loai_keys = list(LOAI_TASK.keys())
        uu_tien_keys = list(UU_TIEN.keys())

        try:
            loai_index = loai_keys.index(task.get("loai")) if task.get("loai") in loai_keys else 0
        except Exception:
            loai_index = 0

        try:
            uu_tien_index = uu_tien_keys.index(task.get("uu_tien")) if task.get("uu_tien") in uu_tien_keys else 2
        except Exception:
            uu_tien_index = 2

        with st.form("form_sua_task"):
            tieu_de = st.text_input(
                "Tên đầu việc *",
                value=str(task.get("tieu_de") or ""),
                key=f"td_sua_tieu_de_{task_id}",
            )
            mo_ta = st.text_area(
                "Mô tả / Hướng dẫn",
                value=str(task.get("mo_ta") or ""),
                key=f"td_sua_mo_ta_{task_id}",
            )
            loai = st.selectbox(
                "Loại",
                options=loai_keys,
                format_func=lambda x: LOAI_TASK.get(x, x),
                index=loai_index,
                key=f"td_sua_loai_{task_id}",
            )
            uu_tien = st.selectbox(
                "Ưu tiên",
                options=uu_tien_keys,
                format_func=lambda x: UU_TIEN.get(x, x),
                index=uu_tien_index,
                key=f"td_sua_uu_tien_{task_id}",
            )
            deadline = st.date_input(
                "Thời hạn hoàn thành *",
                value=deadline_default,
                key=f"td_sua_deadline_{task_id}",
            )
            ghi_chu = st.text_input(
                "Ghi chú thêm",
                value=str(task.get("ghi_chu") or ""),
                key=f"td_sua_ghi_chu_{task_id}",
            )

            st.caption(
                "Danh sách PGD không thể thay đổi sau khi tạo. Nếu cần, hãy đóng đầu việc này và tạo mới."
            )

            submitted = st.form_submit_button("💾 Lưu thay đổi", type="primary")

        if submitted:
            if not str(tieu_de or "").strip():
                st.error("Vui lòng nhập tên đầu việc.")
                return
            try:
                with db.get_conn() as conn:
                    conn.execute(
                        """UPDATE tien_do_task
                           SET tieu_de=?, mo_ta=?, ngay_deadline=?, loai=?,
                               uu_tien=?, ghi_chu=?
                           WHERE id=?""",
                        (
                            str(tieu_de).strip(),
                            str(mo_ta).strip() or None,
                            deadline.isoformat(),
                            loai,
                            uu_tien,
                            str(ghi_chu).strip() or None,
                            task_id,
                        ),
                    )
                    conn.commit()
                db.ghi_audit(
                    username,
                    "tien_do_sua_task",
                    f"ID={task_id} · '{str(tieu_de).strip()}' · thời hạn={deadline}",
                )
                st.toast("✅ Đã lưu thay đổi.")
                st.rerun()
            except Exception as e:
                st.error(f"Lỗi: {e}")

        c1, c2, c3 = st.columns([1.2, 1.2, 1.6])
        with c1:
            if task.get("trang_thai") == "dang_theo_doi":
                if st.button("🔒 Đóng đầu việc", key=f"td_dong_{task_id}", use_container_width=True):
                    try:
                        with db.get_conn() as conn:
                            conn.execute(
                                "UPDATE tien_do_task SET trang_thai=? WHERE id=?",
                                ("da_dong", task_id),
                            )
                            conn.commit()
                        db.ghi_audit(
                            username,
                            "tien_do_doi_trang_thai",
                            f"ID={task_id} · '{task.get('tieu_de')}' → da_dong",
                        )
                        st.toast("✅ Đã cập nhật trạng thái.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Lỗi: {e}")
            else:
                if st.button("🔓 Mở lại", key=f"td_mo_lai_{task_id}", use_container_width=True):
                    try:
                        with db.get_conn() as conn:
                            conn.execute(
                                "UPDATE tien_do_task SET trang_thai=? WHERE id=?",
                                ("dang_theo_doi", task_id),
                            )
                            conn.commit()
                        db.ghi_audit(
                            username,
                            "tien_do_doi_trang_thai",
                            f"ID={task_id} · '{task.get('tieu_de')}' → dang_theo_doi",
                        )
                        st.toast("✅ Đã cập nhật trạng thái.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Lỗi: {e}")

        if role == "admin_cn":
            confirm_key = f"_td_xoa_confirm_{task_id}"
            with c3:
                if not st.session_state.get(confirm_key):
                    if st.button("🗑️ Xóa vĩnh viễn", key=f"td_xoa_{task_id}", use_container_width=True):
                        st.session_state[confirm_key] = True
                        st.rerun()
                else:
                    st.warning("⚠️ Hành động này không thể hoàn tác.")
                    if st.button("Xác nhận xóa", key=f"td_xoa_ok_{task_id}", type="primary", use_container_width=True):
                        try:
                            with db.get_conn() as conn:
                                conn.execute("DELETE FROM tien_do_ketqua WHERE task_id=?", (task_id,))
                                conn.execute("DELETE FROM tien_do_task WHERE id=?", (task_id,))
                                conn.commit()
                            db.ghi_audit(
                                username,
                                "tien_do_xoa_task",
                                f"ID={task_id} · '{task.get('tieu_de')}'",
                            )
                            st.session_state.pop(confirm_key, None)
                            st.toast("🗑️ Đã xóa đầu việc.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Lỗi: {e}")


def _render_cap_nhat(tab, **kwargs):
    username = kwargs.get("username", "")
    role = kwargs.get("role", "user")
    pgd_user = kwargs.get("pgd_user") or ""
    la_manager = role in ROLES_PHAN_HE_CN

    _tab_ctx = tab if tab is not None else __import__('streamlit').container()
    with _tab_ctx:
        ds_task = _doc_tasks()
        if not ds_task:
            st.info("Chưa có đầu việc nào đang theo dõi.")
            return

        task_opts = {t["id"]: f"{t['tieu_de']} · ⏰ {t['ngay_deadline']}"
                     for t in ds_task}
        task_id = st.selectbox("Chọn đầu việc",
                               list(task_opts.keys()),
                               format_func=lambda x: task_opts[x],
                               key="td_cu_task")
        task = next((t for t in ds_task if t["id"] == task_id), None)
        if task is None:
            return

        cap_theo_doi = task.get("cap_theo_doi", "xa")
        label_dv = "PGD" if cap_theo_doi == "pgd" else "xã"
        st.subheader(f"📋 Cập nhật tiến độ theo {label_dv}")

        if la_manager:
            ds_pgd_task = json.loads(task.get("ds_pgd") or "[]") or DS_PGD_ALL
            pgd_sel = st.selectbox("Chọn đơn vị", ds_pgd_task, key="td_cu_pgd")
        else:
            pgd_sel = pgd_user
            if not pgd_sel:
                st.warning("Tài khoản chưa được gán đơn vị.")
                return

        tag_nd = "🏢 Chung PGD" if cap_theo_doi == "pgd" else "🏘️ Chi tiết xã"
        st.caption(
            f"**{task['tieu_de']}** · {tag_nd} · "
            f"{LOAI_TASK.get(task['loai'], task['loai'])} · "
            f"Thời hạn: **{task['ngay_deadline']}** · {UU_TIEN.get(task['uu_tien'], '')}"
        )
        if task.get("mo_ta"):
            st.info(task["mo_ta"])

        kq_list = [r for r in _doc_ketqua_task(task_id) if r["pgd"] == pgd_sel]
        if not kq_list:
            st.warning(f"Không tìm thấy dữ liệu {label_dv} cho {pgd_sel}. "
                       "Thử tạo lại đầu việc.")
            return

        xong = sum(1 for r in kq_list if r["trang_thai"] == "da_hoan_thanh")
        st.progress(xong / len(kq_list),
                    text=f"Hoàn thành: {xong}/{len(kq_list)} {label_dv}")

        ten_cot = "Đơn vị PGD" if cap_theo_doi == "pgd" else "Xã / Phường"

        def _parse_date(val):
            if not val:
                return None
            try:
                return pd.to_datetime(val).date()
            except Exception:
                return None

        df_edit = pd.DataFrame([
            {
                ten_cot: r["ten_xa"],
                "Trạng thái": r["trang_thai"],
                "Ngày HT": _parse_date(r.get("ngay_hoan_thanh")),
                "Ghi chú": r.get("ghi_chu") or "",
            }
            for r in kq_list
        ])
        df_edit["Ngày HT"] = pd.to_datetime(df_edit["Ngày HT"], errors="coerce").dt.date

        edited = st.data_editor(
            df_edit,
            column_config={
                ten_cot: st.column_config.TextColumn(
                    ten_cot, disabled=True, width="medium"
                ),
                "Trạng thái": st.column_config.SelectboxColumn(
                    options=list(TS_KQ_LABEL.keys()),
                    width="small",
                ),
                "Ngày HT": st.column_config.DateColumn(
                    "Ngày HT", format="YYYY-MM-DD", width="small",
                    default=None,
                ),
                "Ghi chú": st.column_config.TextColumn(width="large"),
            },
            hide_index=True,
            use_container_width=True,
            key=f"td_editor_{task_id}_{pgd_sel}",
        )

        if st.button("💾 Lưu", type="primary", key=f"td_luu_{task_id}_{pgd_sel}"):
            count = 0
            for i in range(len(edited)):
                ten_xa = df_edit.iloc[i][ten_cot]
                ngay_val = edited.iloc[i]["Ngày HT"]
                ngay_ht = None
                if pd.notna(ngay_val) and str(ngay_val) not in ("", "NaT"):
                    try:
                        ngay_ht = pd.to_datetime(ngay_val).date().isoformat()
                    except Exception:
                        ngay_ht = None
                try:
                    _upsert_ketqua_xa(
                        task_id, ten_xa, pgd_sel,
                        str(edited.iloc[i]["Trạng thái"]),
                        ngay_ht,
                        str(edited.iloc[i]["Ghi chú"]).strip() or None,
                        username,
                    )
                    count += 1
                except Exception as e:
                    st.warning(f"Lỗi {ten_xa}: {e}")
            db.ghi_audit(username, "tien_do_cap_nhat_xa",
                         f"Task '{task['tieu_de']}' · {pgd_sel} · {count} xã")
            st.toast(f"✅ Đã lưu {count} xã.")
            st.rerun()

        kq_all = _doc_ketqua_task(task_id)
        if st.button("📄 Xuất PDF tiến độ", key=f"td_pdf_{task_id}"):
            pdf_bytes = _xuat_pdf_tien_do(task, kq_all, username)
            if pdf_bytes:
                ten_file = (
                    f"TienDo_{task['tieu_de'][:20].replace(' ', '_')}_"
                    f"{date.today().isoformat()}.pdf"
                )
                st.download_button(
                    "⬇ Tải PDF",
                    data=pdf_bytes,
                    file_name=ten_file,
                    mime="application/pdf",
                    key=f"td_pdf_dl_{task_id}",
                )
                db.ghi_audit(
                    username, "tien_do_xuat_pdf",
                    f"Task '{task['tieu_de']}'"
                )


def _render_xuat(tab, **kwargs):
    SS_KEY = "_td_xuat_excel"
    _tab_ctx = tab if tab is not None else __import__('streamlit').container()
    with _tab_ctx:
        st.subheader("📤 Xuất báo cáo tiến độ")

        c1, c2 = st.columns(2)
        with c1:
            tu_ngay = st.date_input("Thời hạn từ", value=date.today(), key="td_x1")
        with c2:
            den_ngay = st.date_input("Thời hạn đến", value=date.today(), key="td_x2")

        if st.button("📥 Tạo Excel", type="primary", key="td_btn_tao"):
            ds_task = _doc_tasks(chi_dang_theo_doi=False)
            ds_task = [t for t in ds_task
                       if tu_ngay.isoformat() <= t["ngay_deadline"] <= den_ngay.isoformat()]

            if not ds_task:
                st.session_state.pop(SS_KEY, None)
                st.info("Không có đầu việc trong khoảng thời gian đã chọn.")
                st.stop()

            hom_nay = date.today().isoformat()

            # Sheet 0: Tổng hợp đầu việc
            summary_rows = []
            for i, t in enumerate(ds_task, 1):
                kq = _doc_ketqua_task(t["id"])
                xong  = sum(1 for r in kq if r["trang_thai"] == "da_hoan_thanh")
                chua  = sum(1 for r in kq if r["trang_thai"] == "chua_thuc_hien")
                tre   = sum(1 for r in kq
                            if r["trang_thai"] == "chua_thuc_hien"
                            and t["ngay_deadline"] < hom_nay)
                na    = sum(1 for r in kq if r["trang_thai"] == "khong_ap_dung")
                tong  = len(kq)
                ds_p  = json.loads(t.get("ds_pgd") or "[]")
                summary_rows.append({
                    "STT":           i,
                    "Đầu việc":      t["tieu_de"],
                    "Loại":          LOAI_TASK.get(t["loai"], t["loai"]),
                    "Ưu tiên":       UU_TIEN.get(t["uu_tien"], t["uu_tien"]).replace("🔴","").replace("🟡","").replace("🟢","").strip(),
                    "Thời hạn":      t["ngay_deadline"],
                    "Số PGD":        len(ds_p),
                    "Tổng xã":       tong,
                    "Đã hoàn thành": xong,
                    "Chưa thực hiện": chua - tre,
                    "Trễ hạn":       tre,
                    "N/A":           na,
                    "Tỷ lệ HT%":    round(xong / tong * 100, 1) if tong else 0,
                })
            df_tonghop = pd.DataFrame(summary_rows)

            # Sheet 1: Ma trận PGD × đầu việc
            bang_rows = []
            for pgd in DS_PGD_ALL:
                row = {"Đơn vị": pgd}
                for t in ds_task:
                    kq = [r for r in _doc_ketqua_task(t["id"]) if r["pgd"] == pgd]
                    xong = sum(1 for r in kq if r["trang_thai"] == "da_hoan_thanh")
                    tre = sum(1 for r in kq
                              if r["trang_thai"] == "chua_thuc_hien"
                              and t["ngay_deadline"] < hom_nay)
                    row[f"{t['tieu_de'][:18]} (#{t['id']})"] = f"{xong}/{len(kq)}" + ("🔴" if tre else "")
                bang_rows.append(row)
            df_matran = pd.DataFrame(bang_rows)

            # Sheet 2: Chi tiết theo xã
            rows_ct = []
            for t in ds_task:
                kq = _doc_ketqua_task(t["id"])
                for r in kq:
                    rows_ct.append({
                        "Task ID": t["id"],
                        "Đầu việc": t["tieu_de"],
                        "Thời hạn": t["ngay_deadline"],
                        "PGD": r["pgd"],
                        "Xã / Phường": r["ten_xa"],
                        "Trạng thái": TS_KQ_LABEL.get(r["trang_thai"], r["trang_thai"]),
                        "Ngày hoàn thành": r.get("ngay_hoan_thanh") or "",
                        "Ghi chú": r.get("ghi_chu") or "",
                    })
            df_ct = pd.DataFrame(rows_ct)

            out = BytesIO()
            with pd.ExcelWriter(out, engine="openpyxl") as writer:
                df_tonghop.to_excel(writer, sheet_name="Tổng hợp", index=False)
                df_matran.to_excel(writer, sheet_name="Ma trận PGD", index=False)
                df_ct.to_excel(writer, sheet_name="Chi tiết xã", index=False)

            st.session_state[SS_KEY] = {
                "data": out.getvalue(),
                "filename": f"TienDoCongViec_{date.today().isoformat()}.xlsx",
                "n_task": len(ds_task),
                "n_ct": len(df_ct),
                "n_th": len(df_tonghop),
            }
            st.rerun()

        if SS_KEY in st.session_state:
            payload = st.session_state[SS_KEY]
            col_dl, col_clear = st.columns([4, 1])
            with col_dl:
                st.download_button(
                    label="⬇ Tải file Excel",
                    data=payload["data"],
                    file_name=payload["filename"],
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                    key="td_xuat_dl",
                )
            with col_clear:
                if st.button("✕", key="td_xuat_clear", help="Tạo lại"):
                    del st.session_state[SS_KEY]
                    st.rerun()
            st.success(f"Đã xuất {payload['n_task']} đầu việc · "
                       f"{payload['n_ct']} dòng chi tiết · "
                       f"{payload['n_th']} đầu việc tổng hợp.")


def _xuat_pdf_tien_do(task, ds_kq, username):
    try:
        from itertools import groupby
        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, HRFlowable,
        )
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        import os

        FONT_NORMAL = "Helvetica"
        FONT_BOLD = "Helvetica-Bold"

        arial_path = "C:/Windows/Fonts/arial.ttf"
        arialbd_path = "C:/Windows/Fonts/arialbd.ttf"
        if os.path.exists(arial_path):
            pdfmetrics.registerFont(TTFont("ArialUni", arial_path))
            FONT_NORMAL = "ArialUni"
        if os.path.exists(arialbd_path):
            pdfmetrics.registerFont(TTFont("ArialUni-Bold", arialbd_path))
            FONT_BOLD = "ArialUni-Bold"

        kq_theo_pgd = {}
        for r in sorted(ds_kq, key=lambda x: x["pgd"]):
            kq_theo_pgd.setdefault(r["pgd"], []).append(r)

        pgd_order = sorted(kq_theo_pgd.keys())

        TS_LABEL = {
            "chua_thuc_hien": "○",
            "da_hoan_thanh": "✓",
            "khong_ap_dung": "—",
        }

        buf = BytesIO()
        doc = SimpleDocTemplate(
            buf, pagesize=A4,
            leftMargin=28, rightMargin=28,
            topMargin=20, bottomMargin=20,
        )

        story = []
        styles = getSampleStyleSheet()

        title_style = ParagraphStyle(
            "Title_VN", parent=styles["Title"],
            fontName=FONT_BOLD, fontSize=14,
            alignment=TA_CENTER, spaceAfter=2, leading=18,
        )
        subtitle_style = ParagraphStyle(
            "Sub_VN", parent=styles["Normal"],
            fontName=FONT_BOLD, fontSize=12,
            alignment=TA_CENTER, spaceAfter=4, leading=16,
        )
        header_style = ParagraphStyle(
            "Header_VN", parent=styles["Normal"],
            fontName=FONT_BOLD, fontSize=11,
            alignment=TA_CENTER, spaceAfter=6, leading=15,
        )
        normal_style = ParagraphStyle(
            "Normal_VN", parent=styles["Normal"],
            fontName=FONT_NORMAL, fontSize=9, leading=13,
        )
        pgd_header_style = ParagraphStyle(
            "PGDHeader", parent=styles["Normal"],
            fontName=FONT_BOLD, fontSize=10, leading=14,
            spaceBefore=6, spaceAfter=2,
        )
        xa_style = ParagraphStyle(
            "XaStyle", parent=styles["Normal"],
            fontName=FONT_NORMAL, fontSize=9, leading=12, leftIndent=12,
        )
        summary_style = ParagraphStyle(
            "Summary", parent=styles["Normal"],
            fontName=FONT_BOLD, fontSize=10, leading=14,
            spaceBefore=8, spaceAfter=4,
        )

        story.append(Paragraph(
            "NGÂN HÀNG CHÍNH SÁCH XÃ HỘI VIỆT NAM", title_style))
        story.append(Paragraph("CHI NHÁNH TỈNH ĐỒNG NAI", subtitle_style))
        story.append(Spacer(1, 6))
        story.append(Paragraph("BÁO CÁO TIẾN ĐỘ CÔNG VIỆC", header_style))
        story.append(Paragraph(task.get("tieu_de", ""), header_style))
        story.append(Spacer(1, 4))

        loai = LOAI_TASK.get(task.get("loai", ""), task.get("loai", ""))
        uu_tien = UU_TIEN.get(task.get("uu_tien", ""), task.get("uu_tien", ""))
        deadline = task.get("ngay_deadline", "")
        now = datetime.now()
        ngay_xuat = now.strftime("%d/%m/%Y %H:%M")

        story.append(Paragraph(
            f"Loại: {loai} | Ưu tiên: {uu_tien} | Thời hạn: {deadline}",
            normal_style,
        ))
        story.append(Paragraph(
            f"Ngày xuất: {ngay_xuat} | Người xuất: {username}",
            normal_style,
        ))

        story.append(HRFlowable(
            width="100%", thickness=0.5, color=colors.grey))
        story.append(Spacer(1, 4))

        tong_dv = 0
        tong_dv_ht = 0
        tong_xa_all = 0
        tong_xa_xong_all = 0

        for pgd in pgd_order:
            items = kq_theo_pgd[pgd]
            tong = len(items)
            xong = sum(1 for r in items if r["trang_thai"] == "da_hoan_thanh")
            tong_xa_all += tong
            tong_xa_xong_all += xong
            pct = round(xong / tong * 100) if tong > 0 else 0

            story.append(Paragraph(
                f"<b>{pgd}</b>  ({xong}/{tong} xã — {pct}%)",
                pgd_header_style,
            ))

            for r in items:
                symbol = TS_LABEL.get(r["trang_thai"], "?")
                ten_xa = r["ten_xa"]
                ngay_ht = r.get("ngay_hoan_thanh") or ""

                if r["trang_thai"] == "da_hoan_thanh":
                    try:
                        ngay_ht = datetime.strptime(
                            ngay_ht[:10], "%Y-%m-%d"
                        ).strftime("%d/%m/%Y")
                    except Exception:
                        pass
                    status_text = ngay_ht
                elif r["trang_thai"] == "khong_ap_dung":
                    status_text = "N/A"
                else:
                    status_text = "Chưa thực hiện"

                dots = "." * max(2, 45 - len(ten_xa) - len(status_text))
                line = f"{symbol} {ten_xa} {dots} {status_text}"
                story.append(Paragraph(line, xa_style))

            story.append(Spacer(1, 2))

            tong_dv += 1
            if xong == tong and tong > 0:
                tong_dv_ht += 1

        story.append(HRFlowable(
            width="100%", thickness=0.5, color=colors.grey))
        story.append(Spacer(1, 6))

        tong_pct = (
            round(tong_xa_xong_all / tong_xa_all * 100)
            if tong_xa_all > 0 else 0
        )
        story.append(Paragraph(
            f"TỔNG KẾT: {tong_dv_ht}/{tong_dv} đơn vị hoàn thành"
            f" | {tong_pct}% toàn Chi nhánh",
            summary_style,
        ))

        doc.build(story)
        buf.seek(0)
        return buf

    except Exception as e:
        st.error(f"Lỗi tạo PDF: {e}")
        return None


def render(tab, **kwargs):
    role = kwargs.get("role")
    pgd_user = kwargs.get("pgd_user")

    role_n = normalize_role(str(role or "user"))
    can_manage = (role_n in ROLES_PHAN_HE_CN) and (role_n != "executive")
    is_exec = role_n == "executive"
    is_pgd_view = (role_n not in ROLES_PHAN_HE_CN) and bool(pgd_user)

    import streamlit as _st
    _tab_ctx = tab if tab is not None else _st.container()
    with _tab_ctx:
        st.subheader("📅 Tiến độ Công việc Hàng ngày")

        if is_exec or is_pgd_view:
            _render_tong_quan(tab, **kwargs)
            return

        if not can_manage:
            _render_tong_quan(tab, **kwargs)
            return

        t1, t2, t3, t4, t5 = st.tabs([
            "📊 Tổng quan", "➕ Tạo đầu việc", "✏️ Quản lý đầu việc",
            "📋 Cập nhật tiến độ", "📤 Xuất báo cáo",
        ])
        with t1:
            _render_tong_quan(t1, **kwargs)
        with t2:
            _render_tao_task(t2, **kwargs)
        with t3:
            _render_quan_ly_task(t3, **kwargs)
        with t4:
            _render_cap_nhat(t4, **kwargs)
        with t5:
            _render_xuat(t5, **kwargs)


def render_tong_quan_only(tab, **kwargs):
    _tab_ctx = tab if tab is not None else __import__('streamlit').container()
    with _tab_ctx:
        st.subheader("📅 Tiến độ Công việc Hàng ngày")
        _render_tong_quan(tab, **kwargs)
