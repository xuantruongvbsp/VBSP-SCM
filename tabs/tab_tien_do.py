from __future__ import annotations

import json
from datetime import date, datetime
from io import BytesIO

import pandas as pd
import plotly.express as px
import streamlit as st

import db
from config import DON_VI_CHI_NHANH, DS_PGD, ROLES_PHAN_HE_CN
from utils import fmt_so, xuat_excel, ten_file_xuat


_TS_TASK_DANG_THEO_DOI = "dang_theo_doi"
_TS_TASK_DA_KET_THUC = "da_ket_thuc"

_TS_KQ_CHUA_THUC_HIEN = "chua_thuc_hien"
_TS_KQ_DA_HOAN_THANH = "da_hoan_thanh"
_TS_KQ_TRE_HAN = "tre_han"
_TS_KQ_KHONG_AP_DUNG = "khong_ap_dung"


def _ds_don_vi() -> list[str]:
    return [DON_VI_CHI_NHANH] + list(DS_PGD)


def _parse_ds_pgd(v: str | None) -> list[str]:
    if not v:
        return []
    try:
        ds = json.loads(v)
        return [str(x) for x in ds] if isinstance(ds, list) else []
    except Exception:
        return []


def _task_applies(ds_pgd: list[str], pgd: str) -> bool:
    return (not ds_pgd) or (pgd in ds_pgd)


def _deadline_to_date(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return date.fromisoformat(str(s)[:10])
    except Exception:
        return None


def _trang_thai_hien_thi(trang_thai: str, deadline: date | None) -> str:
    if trang_thai in (_TS_KQ_DA_HOAN_THANH, _TS_KQ_KHONG_AP_DUNG):
        return trang_thai
    if deadline and deadline < date.today():
        return _TS_KQ_TRE_HAN
    return _TS_KQ_CHUA_THUC_HIEN


def _doc_tasks(include_ket_thuc: bool) -> list[dict]:
    with db.get_conn() as conn:
        if include_ket_thuc:
            rows = conn.execute(
                "SELECT * FROM tien_do_task ORDER BY id DESC"
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM tien_do_task WHERE trang_thai=? ORDER BY id DESC",
                (_TS_TASK_DANG_THEO_DOI,),
            ).fetchall()
    return [dict(r) for r in rows]


def _doc_ket_qua_map(task_ids: list[int]) -> dict[tuple[int, str], dict]:
    if not task_ids:
        return {}
    placeholders = ",".join("?" * len(task_ids))
    with db.get_conn() as conn:
        rows = conn.execute(
            f"SELECT * FROM tien_do_ketqua WHERE task_id IN ({placeholders})",
            task_ids,
        ).fetchall()
    return {(int(r["task_id"]), str(r["pgd"])): dict(r) for r in rows}


def _tao_task(
    tieu_de: str,
    mo_ta: str | None,
    ngay_deadline: date | None,
    ds_pgd: list[str],
    loai: str,
    uu_tien: str,
    username: str,
) -> int:
    now = datetime.now().isoformat()
    ds_pgd_json = json.dumps(ds_pgd, ensure_ascii=False)
    with db.get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO tien_do_task
               (tieu_de, mo_ta, ngay_deadline, ds_pgd, loai, uu_tien, nguoi_tao, ngay_tao, trang_thai, ghi_chu)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                tieu_de,
                mo_ta or None,
                ngay_deadline.isoformat() if ngay_deadline else None,
                ds_pgd_json,
                loai,
                uu_tien,
                username,
                now,
                _TS_TASK_DANG_THEO_DOI,
                None,
            ),
        )
        task_id = int(cur.lastrowid)

        ds_all = _ds_don_vi()
        ds_ap_dung = ds_all if not ds_pgd else ds_pgd
        for pgd in ds_all:
            ts = _TS_KQ_CHUA_THUC_HIEN if pgd in ds_ap_dung else _TS_KQ_KHONG_AP_DUNG
            conn.execute(
                """INSERT OR IGNORE INTO tien_do_ketqua
                   (task_id, pgd, trang_thai, ngay_hoan_thanh, ghi_chu, nguoi_nhap, ngay_nhap)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (task_id, pgd, ts, None, None, username, now),
            )
        conn.commit()

    db.ghi_audit(username, "tien_do_task_create", f"task_id={task_id} tieu_de={tieu_de}")
    return task_id


def _cap_nhat_ket_qua(task_id: int, df_new: pd.DataFrame, username: str) -> None:
    now = datetime.now().isoformat()
    with db.get_conn() as conn:
        for _, r in df_new.iterrows():
            pgd = str(r["PGD"])
            ts_ui = str(r["Trạng thái"])
            ts = _TS_KQ_CHUA_THUC_HIEN if ts_ui == _TS_KQ_TRE_HAN else ts_ui
            ngay_ht = r.get("Ngày hoàn thành")
            if ts == _TS_KQ_DA_HOAN_THANH:
                if pd.isna(ngay_ht) or ngay_ht is None:
                    ngay_ht_s = date.today().isoformat()
                else:
                    try:
                        ngay_ht_s = pd.to_datetime(ngay_ht).date().isoformat()
                    except Exception:
                        ngay_ht_s = date.today().isoformat()
            else:
                ngay_ht_s = None

            ghi_chu = r.get("Ghi chú")
            if pd.isna(ghi_chu):
                ghi_chu = None

            conn.execute(
                """UPDATE tien_do_ketqua
                   SET trang_thai=?, ngay_hoan_thanh=?, ghi_chu=?, nguoi_nhap=?, ngay_nhap=?
                   WHERE task_id=? AND pgd=?""",
                (ts, ngay_ht_s, ghi_chu, username, now, int(task_id), pgd),
            )
        conn.commit()
    db.ghi_audit(username, "tien_do_ketqua_update", f"task_id={task_id} rows={len(df_new)}")


def _build_dashboard(tasks: list[dict], kq_map: dict[tuple[int, str], dict]) -> tuple[pd.DataFrame, pd.DataFrame]:
    ds_dv = _ds_don_vi()
    cols = [str(t["tieu_de"]) for t in tasks]
    mat = pd.DataFrame(index=ds_dv, columns=cols)
    raw = []
    for t in tasks:
        task_id = int(t["id"])
        deadline = _deadline_to_date(t.get("ngay_deadline"))
        ds_pgd = _parse_ds_pgd(t.get("ds_pgd"))
        for pgd in ds_dv:
            if not _task_applies(ds_pgd, pgd):
                ts_show = _TS_KQ_KHONG_AP_DUNG
            else:
                kq = kq_map.get((task_id, pgd))
                ts = str(kq.get("trang_thai")) if kq else _TS_KQ_CHUA_THUC_HIEN
                ts_show = _trang_thai_hien_thi(ts, deadline)
            raw.append(
                {
                    "task_id": task_id,
                    "task": str(t["tieu_de"]),
                    "pgd": pgd,
                    "deadline": t.get("ngay_deadline"),
                    "trang_thai": ts_show,
                }
            )

    df_raw = pd.DataFrame(raw)
    if not df_raw.empty:
        piv = df_raw.pivot(index="pgd", columns="task", values="trang_thai").reindex(ds_dv)
        mat = piv.reindex(columns=cols)

    symbol = {
        _TS_KQ_DA_HOAN_THANH: "✅",
        _TS_KQ_TRE_HAN: "🔴",
        _TS_KQ_CHUA_THUC_HIEN: "⬜",
        _TS_KQ_KHONG_AP_DUNG: "⬜",
    }
    df_show = mat.fillna(_TS_KQ_CHUA_THUC_HIEN).applymap(lambda x: symbol.get(str(x), "⬜"))
    df_show.index.name = "PGD"
    return df_show, df_raw


def _render_tong_quan(tab, *, read_only: bool, **kwargs) -> None:
    role = kwargs.get("role")
    pgd_user = kwargs.get("pgd_user")
    username = kwargs.get("username", "unknown")

    include_ket_thuc = st.checkbox("Hiện cả đầu việc đã kết thúc", value=False, key="tien_do_show_closed")
    tasks = _doc_tasks(include_ket_thuc=include_ket_thuc)
    if not tasks:
        st.info("Chưa có đầu việc nào.")
        return

    if role not in ROLES_PHAN_HE_CN and pgd_user:
        ds_task_loc = []
        for t in tasks:
            ds_pgd = _parse_ds_pgd(t.get("ds_pgd"))
            if _task_applies(ds_pgd, pgd_user):
                ds_task_loc.append(t)
        tasks = ds_task_loc
        if not tasks:
            st.info("Không có đầu việc nào giao cho đơn vị của bạn.")
            return

    task_ids = [int(t["id"]) for t in tasks]
    kq_map = _doc_ket_qua_map(task_ids)
    df_show, df_raw = _build_dashboard(tasks, kq_map)

    if role not in ROLES_PHAN_HE_CN and pgd_user:
        df_show = df_show.loc[[pgd_user]] if pgd_user in df_show.index else df_show.iloc[0:0]
        if not df_raw.empty:
            df_raw = df_raw[df_raw["pgd"] == pgd_user]

    df_app = df_raw[df_raw["trang_thai"] != _TS_KQ_KHONG_AP_DUNG] if not df_raw.empty else df_raw
    tong_o = int(len(df_app)) if df_app is not None else 0
    da_ht = int((df_app["trang_thai"] == _TS_KQ_DA_HOAN_THANH).sum()) if tong_o else 0
    tre_han = int((df_app["trang_thai"] == _TS_KQ_TRE_HAN).sum()) if tong_o else 0
    ti_le = (da_ht / tong_o * 100.0) if tong_o else 0.0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Số đầu việc", fmt_so(len(tasks)))
    c2.metric("Ô áp dụng", fmt_so(tong_o))
    c3.metric("% hoàn thành", f"{ti_le:.1f}%")
    c4.metric("Trễ hạn", fmt_so(tre_han))

    st.dataframe(df_show, use_container_width=True)

    if not df_raw.empty:
        grp = (
            df_raw[df_raw["trang_thai"] != _TS_KQ_KHONG_AP_DUNG]
            .groupby("task")
            .agg(
                tong=("trang_thai", "count"),
                da_ht=("trang_thai", lambda s: int((s == _TS_KQ_DA_HOAN_THANH).sum())),
            )
            .reset_index()
        )
        grp["ti_le"] = grp.apply(lambda r: (r["da_ht"] / r["tong"] * 100.0) if r["tong"] else 0.0, axis=1)
        fig = px.bar(
            grp.sort_values("ti_le", ascending=True),
            x="ti_le",
            y="task",
            orientation="h",
            text=grp["ti_le"].map(lambda v: f"{v:.1f}%"),
            labels={"ti_le": "% hoàn thành", "task": "Đầu việc"},
        )
        fig.update_layout(height=min(650, 80 + 28 * len(grp)))
        fig.update_traces(textposition="outside")
        st.plotly_chart(fig, use_container_width=True)

    if read_only:
        return

    st.divider()
    with st.expander("Kết thúc / mở lại đầu việc", expanded=False):
        ds_nv = [(int(t["id"]), str(t["tieu_de"])) for t in tasks]
        task_sel = st.selectbox(
            "Chọn đầu việc",
            options=ds_nv,
            format_func=lambda x: f"#{x[0]} — {x[1]}",
            key="tien_do_close_sel",
        )
        ts_new = st.selectbox(
            "Trạng thái",
            options=[_TS_TASK_DANG_THEO_DOI, _TS_TASK_DA_KET_THUC],
            key="tien_do_close_status",
        )
        if st.button("Lưu", type="primary", use_container_width=True, key="tien_do_close_save"):
            with db.get_conn() as conn:
                conn.execute(
                    "UPDATE tien_do_task SET trang_thai=? WHERE id=?",
                    (ts_new, int(task_sel[0])),
                )
                conn.commit()
            db.ghi_audit(username, "tien_do_task_set_status", f"task_id={int(task_sel[0])} trang_thai={ts_new}")
            st.success("Đã lưu.")
            st.rerun()


def _render_tao_dau_viec(tab, **kwargs) -> None:
    username = kwargs.get("username", "unknown")

    tieu_de = st.text_input("Tiêu đề", key="tien_do_new_title")
    mo_ta = st.text_area("Mô tả", key="tien_do_new_desc")
    loai = st.selectbox(
        "Loại",
        options=["thuong_xuyen", "dot_xuat", "bao_cao"],
        key="tien_do_new_type",
    )
    uu_tien = st.selectbox(
        "Ưu tiên",
        options=["thap", "trung_binh", "cao"],
        key="tien_do_new_prio",
    )
    ngay_deadline = st.date_input(
        "Deadline",
        value=None,
        key="tien_do_new_deadline",
    )
    ds_pgd = st.multiselect(
        "Đơn vị áp dụng (bỏ trống = tất cả 22 đơn vị)",
        options=_ds_don_vi(),
        default=[],
        key="tien_do_new_units",
    )

    if st.button("Tạo đầu việc", type="primary", use_container_width=True, key="tien_do_new_create"):
        if not tieu_de.strip():
            st.error("Thiếu tiêu đề.")
            return
        task_id = _tao_task(
            tieu_de=tieu_de.strip(),
            mo_ta=mo_ta.strip() if mo_ta else None,
            ngay_deadline=ngay_deadline,
            ds_pgd=ds_pgd,
            loai=loai,
            uu_tien=uu_tien,
            username=username,
        )
        st.success(f"Đã tạo đầu việc #{task_id}.")
        st.rerun()


def _render_cap_nhat_tien_do(tab, **kwargs) -> None:
    username = kwargs.get("username", "unknown")

    tasks = _doc_tasks(include_ket_thuc=True)
    if not tasks:
        st.info("Chưa có đầu việc nào.")
        return

    ds_nv = [(int(t["id"]), str(t["tieu_de"])) for t in tasks]
    task_sel = st.selectbox(
        "Chọn đầu việc",
        options=ds_nv,
        format_func=lambda x: f"#{x[0]} — {x[1]}",
        key="tien_do_edit_sel",
    )
    task = next((t for t in tasks if int(t["id"]) == int(task_sel[0])), None)
    if not task:
        st.warning("Không tìm thấy đầu việc.")
        return

    ds_dv = _ds_don_vi()
    deadline = _deadline_to_date(task.get("ngay_deadline"))
    ds_ap_dung = _parse_ds_pgd(task.get("ds_pgd"))

    with db.get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM tien_do_ketqua WHERE task_id=?",
            (int(task_sel[0]),),
        ).fetchall()
    kq_map = {str(r["pgd"]): dict(r) for r in rows}

    data = []
    for pgd in ds_dv:
        if not _task_applies(ds_ap_dung, pgd):
            ts_show = _TS_KQ_KHONG_AP_DUNG
        else:
            ts = str(kq_map.get(pgd, {}).get("trang_thai", _TS_KQ_CHUA_THUC_HIEN))
            ts_show = _trang_thai_hien_thi(ts, deadline)
        ngay_ht = kq_map.get(pgd, {}).get("ngay_hoan_thanh")
        data.append(
            {
                "PGD": pgd,
                "Trạng thái": ts_show,
                "Ngày hoàn thành": ngay_ht,
                "Ghi chú": kq_map.get(pgd, {}).get("ghi_chu"),
            }
        )
    df0 = pd.DataFrame(data)

    editor = st.data_editor(
        df0,
        use_container_width=True,
        hide_index=True,
        num_rows="fixed",
        column_config={
            "PGD": st.column_config.TextColumn(disabled=True),
            "Trạng thái": st.column_config.SelectboxColumn(
                options=[
                    _TS_KQ_CHUA_THUC_HIEN,
                    _TS_KQ_DA_HOAN_THANH,
                    _TS_KQ_TRE_HAN,
                    _TS_KQ_KHONG_AP_DUNG,
                ]
            ),
            "Ngày hoàn thành": st.column_config.DateColumn(),
            "Ghi chú": st.column_config.TextColumn(),
        },
        key="tien_do_editor",
    )

    if st.button("Lưu tiến độ", type="primary", use_container_width=True, key="tien_do_edit_save"):
        _cap_nhat_ket_qua(int(task_sel[0]), editor, username=username)
        st.success("Đã lưu tiến độ.")
        st.rerun()


def _render_xuat_bao_cao(tab, **kwargs) -> None:
    role = kwargs.get("role")
    pgd_user = kwargs.get("pgd_user")

    include_ket_thuc = st.checkbox("Hiện cả đầu việc đã kết thúc", value=False, key="tien_do_export_closed")
    tasks = _doc_tasks(include_ket_thuc=include_ket_thuc)
    if not tasks:
        st.info("Chưa có đầu việc nào.")
        return

    if role not in ROLES_PHAN_HE_CN and pgd_user:
        tasks = [t for t in tasks if _task_applies(_parse_ds_pgd(t.get("ds_pgd")), pgd_user)]
        if not tasks:
            st.info("Không có đầu việc nào giao cho đơn vị của bạn.")
            return

    task_ids = [int(t["id"]) for t in tasks]
    kq_map = _doc_ket_qua_map(task_ids)
    df_show, df_raw = _build_dashboard(tasks, kq_map)

    if role not in ROLES_PHAN_HE_CN and pgd_user:
        df_show = df_show.loc[[pgd_user]] if pgd_user in df_show.index else df_show.iloc[0:0]
        if not df_raw.empty:
            df_raw = df_raw[df_raw["pgd"] == pgd_user]

    df_task = pd.DataFrame(tasks)
    if not df_task.empty:
        df_task["ds_pgd"] = df_task["ds_pgd"].apply(_parse_ds_pgd).apply(lambda x: ", ".join(x) if x else "(Tất cả)")

    out = BytesIO()
    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        df_show.reset_index().to_excel(writer, sheet_name="Ma tran", index=False)
        if not df_task.empty:
            df_task.to_excel(writer, sheet_name="Danh sach dau viec", index=False)
        if not df_raw.empty:
            df_raw.to_excel(writer, sheet_name="Chi tiet", index=False)

    st.download_button(
        label="⬇ Tải Excel báo cáo",
        data=out.getvalue(),
        file_name=ten_file_xuat("TienDoCongViec"),
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
        key="tien_do_export_dl",
    )


def render(tab, **kwargs: dict) -> None:
    role = kwargs.get("role")
    pgd_user = kwargs.get("pgd_user")

    can_manage = (role in ROLES_PHAN_HE_CN) and (role != "executive")
    is_exec = role == "executive"
    is_pgd_view = (role not in ROLES_PHAN_HE_CN) and bool(pgd_user)

    with tab:
        st.subheader("📅 Tiến độ Công việc Hàng ngày")

        if is_exec or is_pgd_view:
            _render_tong_quan(tab, read_only=True, **kwargs)
            return

        if not can_manage:
            _render_tong_quan(tab, read_only=True, **kwargs)
            return

        t1, t2, t3, t4 = st.tabs(["📊 Tổng quan", "➕ Tạo đầu việc", "📋 Cập nhật tiến độ", "📤 Xuất báo cáo"])
        with t1:
            _render_tong_quan(t1, read_only=False, **kwargs)
        with t2:
            _render_tao_dau_viec(t2, **kwargs)
        with t3:
            _render_cap_nhat_tien_do(t3, **kwargs)
        with t4:
            _render_xuat_bao_cao(t4, **kwargs)


def render_tong_quan_only(tab, **kwargs: dict) -> None:
    with tab:
        st.subheader("📅 Tiến độ Công việc Hàng ngày")
        _render_tong_quan(tab, read_only=True, **kwargs)

