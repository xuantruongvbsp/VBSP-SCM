from __future__ import annotations

import json
from datetime import datetime, date
from io import BytesIO

import pandas as pd
import plotly.express as px
import streamlit as st

import db
from config import DS_PGD, DON_VI_CHI_NHANH, PGD_XA_MAP, ROLES_PHAN_HE_CN
from utils import get_tab_context

DS_PGD_ALL = [DON_VI_CHI_NHANH] + DS_PGD

LOAI_TASK = {
    "chung":            "Công việc chung",
    "ho_so_rui_ro":     "Hồ sơ rủi ro",
    "khao_sat_nhu_cau": "Khảo sát nhu cầu vay vốn",
    "bao_cao":          "Báo cáo",
    "tap_huan":         "Tập huấn",
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


def _khoi_tao_ketqua_task(task_id: int, ds_pgd_task: list[str]) -> None:
    rows = []
    for pgd in ds_pgd_task:
        for xa in PGD_XA_MAP.get(pgd, []):
            rows.append((task_id, pgd, xa))
    with db.get_conn() as conn:
        conn.executemany(
            """INSERT OR IGNORE INTO tien_do_ketqua
               (task_id, pgd, ten_xa, trang_thai)
               VALUES (?, ?, ?, 'chua_thuc_hien')""",
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
    with get_tab_context(tab):
        st.subheader("📊 Tổng quan tiến độ")

        c1, c2 = st.columns([2, 1])
        with c1:
            ngay_loc = st.date_input("Deadline đến ngày",
                                     value=date.today(), key="td_ngay")
        with c2:
            loai_loc = st.selectbox("Lọc loại", ["Tất cả"] + list(LOAI_TASK.values()),
                                    key="td_loai")

        hom_nay = date.today().isoformat()
        ds_task = _doc_tasks()
        ds_task = [t for t in ds_task
                   if t["ngay_deadline"] <= ngay_loc.isoformat()]
        if loai_loc != "Tất cả":
            loai_key = next((k for k, v in LOAI_TASK.items() if v == loai_loc), None)
            ds_task = [t for t in ds_task if loai_key and t["loai"] == loai_key]

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
        c2.metric("Lượt xã hoàn thành",
                  f"{tong_xong}/{tong_xa}",
                  f"{round(tong_xong/tong_xa*100) if tong_xa else 0}%")
        c3.metric("🔴 Xã trễ hạn", tong_tre, delta_color="inverse")
        c4.metric("⬜ Chưa báo cáo", tong_xa - tong_xong - tong_tre)

        st.divider()

        st.markdown("#### 🗺️ Bảng tiến độ theo PGD")
        st.caption("Số trong ô = Xã hoàn thành / Tổng xã. 🔴 = có xã trễ hạn.")

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
                "Deadline": t["ngay_deadline"],
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
                    f"Hoàn thành: **{xong}/{len(kq_xa)} xã** · "
                    f"Deadline: {task_sel['ngay_deadline']}"
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
    with tab:
        st.subheader("➕ Tạo đầu việc mới")

        with st.form("form_tao_task", clear_on_submit=True):
            tieu_de = st.text_input("Tên đầu việc *",
                                    placeholder="VD: Nộp hồ sơ rủi ro tháng 5/2026")
            mo_ta = st.text_area("Mô tả / Hướng dẫn")

            c1, c2 = st.columns(2)
            with c1:
                loai = st.selectbox("Loại", list(LOAI_TASK.keys()),
                                    format_func=lambda x: LOAI_TASK[x])
                uu_tien = st.selectbox("Ưu tiên", list(UU_TIEN.keys()),
                                       format_func=lambda x: UU_TIEN[x], index=2)
            with c2:
                deadline = st.date_input("Hạn hoàn thành *", value=date.today())
                pgd_chon = st.multiselect(
                    "Áp dụng cho đơn vị",
                    DS_PGD_ALL, default=DS_PGD_ALL,
                    placeholder="Mặc định: tất cả 22 đơn vị",
                )

            ds_preview = pgd_chon or DS_PGD_ALL
            tong_xa_preview = sum(len(PGD_XA_MAP.get(p, [])) for p in ds_preview)
            st.caption(f"📍 {len(ds_preview)} đơn vị · {tong_xa_preview} xã/phường")
            with st.expander(f"Xem chi tiết {tong_xa_preview} xã sẽ áp dụng", expanded=False):
                for pgd in ds_preview:
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
                            uu_tien, nguoi_tao, ngay_tao, trang_thai, ghi_chu)
                           VALUES (?,?,?,?,?,?,?,?,'dang_theo_doi',?)""",
                        (tieu_de.strip(), mo_ta.strip() or None,
                         deadline.isoformat(), ds_pgd_json,
                         loai, uu_tien, username,
                         datetime.now().isoformat(),
                         ghi_chu.strip() or None),
                    )
                    task_id = cur.lastrowid
                    conn.commit()

                _khoi_tao_ketqua_task(task_id, pgd_luu)

                db.ghi_audit(username, "tien_do_tao_task",
                             f"'{tieu_de}' · deadline={deadline} · "
                             f"{len(pgd_luu)} PGD · "
                             f"{sum(len(PGD_XA_MAP.get(p, [])) for p in pgd_luu)} xã")
                st.toast(f"✅ Đã tạo: {tieu_de}")
                st.rerun()
            except Exception as e:
                st.error(f"Lỗi: {e}")


def _render_cap_nhat(tab, **kwargs):
    username = kwargs.get("username", "")
    role = kwargs.get("role", "user")
    pgd_user = kwargs.get("pgd_user") or ""
    la_manager = role in ROLES_PHAN_HE_CN

    with tab:
        st.subheader("📋 Cập nhật tiến độ theo xã")

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

        if la_manager:
            ds_pgd_task = json.loads(task.get("ds_pgd") or "[]") or DS_PGD_ALL
            pgd_sel = st.selectbox("Chọn đơn vị", ds_pgd_task, key="td_cu_pgd")
        else:
            pgd_sel = pgd_user
            if not pgd_sel:
                st.warning("Tài khoản chưa được gán đơn vị.")
                return

        st.caption(
            f"**{task['tieu_de']}** · {LOAI_TASK.get(task['loai'], task['loai'])} · "
            f"Deadline: **{task['ngay_deadline']}** · {UU_TIEN.get(task['uu_tien'], '')}"
        )
        if task.get("mo_ta"):
            st.info(task["mo_ta"])

        kq_list = [r for r in _doc_ketqua_task(task_id) if r["pgd"] == pgd_sel]
        if not kq_list:
            st.warning(f"Không tìm thấy dữ liệu xã cho {pgd_sel}. "
                       "Thử tạo lại đầu việc.")
            return

        xong = sum(1 for r in kq_list if r["trang_thai"] == "da_hoan_thanh")
        st.progress(xong / len(kq_list),
                    text=f"Hoàn thành: {xong}/{len(kq_list)} xã")

        def _parse_date(val):
            if not val:
                return None
            try:
                return pd.to_datetime(val).date()
            except Exception:
                return None

        df_edit = pd.DataFrame([
            {
                "Xã / Phường": r["ten_xa"],
                "Trạng thái": r["trang_thai"],
                "Ngày HT": _parse_date(r.get("ngay_hoan_thanh")),
                "Ghi chú": r.get("ghi_chu") or "",
            }
            for r in kq_list
        ])
        # Convert cột "Ngày HT" sang datetime.date, thay thế None bằng NaT để DateColumn hoạt động
        df_edit["Ngày HT"] = pd.to_datetime(df_edit["Ngày HT"], errors="coerce").dt.date

        edited = st.data_editor(
            df_edit,
            column_config={
                "Xã / Phường": st.column_config.TextColumn(disabled=True, width="medium"),
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
                ten_xa = df_edit.iloc[i]["Xã / Phường"]
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


def _render_xuat(tab, **kwargs):
    SS_KEY = "_td_xuat_excel"
    with tab:
        st.subheader("📤 Xuất báo cáo tiến độ")

        c1, c2 = st.columns(2)
        with c1:
            tu_ngay = st.date_input("Deadline từ", value=date.today(), key="td_x1")
        with c2:
            den_ngay = st.date_input("Deadline đến", value=date.today(), key="td_x2")

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
                    "Deadline":      t["ngay_deadline"],
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
                        "Deadline": t["ngay_deadline"],
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



def render(tab, **kwargs):
    role = kwargs.get("role")
    pgd_user = kwargs.get("pgd_user")

    can_manage = (role in ROLES_PHAN_HE_CN) and (role != "executive")
    is_exec = role == "executive"
    is_pgd_view = (role not in ROLES_PHAN_HE_CN) and bool(pgd_user)

    with get_tab_context(tab):
        st.subheader("📅 Tiến độ Công việc Hàng ngày")

        if is_exec or is_pgd_view:
            _render_tong_quan(tab, **kwargs)
            return

        if not can_manage:
            _render_tong_quan(tab, **kwargs)
            return

        t1, t2, t3, t4 = st.tabs([
            "📊 Tổng quan", "➕ Tạo đầu việc",
            "📋 Cập nhật tiến độ", "📤 Xuất báo cáo",
        ])
        with t1:
            _render_tong_quan(t1, **kwargs)
        with t2:
            _render_tao_task(t2, **kwargs)
        with t3:
            _render_cap_nhat(t3, **kwargs)
        with t4:
            _render_xuat(t4, **kwargs)


def render_tong_quan_only(tab, **kwargs):
    with tab:
        st.subheader("📅 Tiến độ Công việc Hàng ngày")
        _render_tong_quan(tab, **kwargs)
