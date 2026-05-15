import sys
sys.stdout.reconfigure(encoding='utf-8')

with open('tabs/tab_tien_do.py', 'r', encoding='utf-8') as f:
    content = f.read()

start = content.find('def _render_cap_nhat(tab, **kwargs):')
end = content.find('\n\ndef _render_xuat(tab, **kwargs):')

old_func = content[start:end]

new_func = r'''def _render_cap_nhat(tab, **kwargs):
    username = kwargs.get("username", "")
    role = kwargs.get("role", "user")
    pgd_user = kwargs.get("pgd_user") or ""

    _tab_ctx = tab if tab is not None else __import__('streamlit').container()
    with _tab_ctx:
        ds_task = _doc_tasks()
        if not ds_task:
            st.info("Chưa có đầu việc nào đang theo dõi.")
            return

        # ── Khối 1: CHỌN ĐẦU VIỆC ────────────────────────────────────────
        with st.container(border=True):
            st.markdown("**① CHỌN ĐẦU VIỆC**")

            task_opts = {t["id"]: f"{t['tieu_de']} · ⏰ {t['ngay_deadline']}"
                         for t in ds_task}
            task_id = st.selectbox(
                "Đầu việc",
                list(task_opts.keys()),
                format_func=lambda x: task_opts[x],
                key="td_cu_task",
            )
            task = next((t for t in ds_task if t["id"] == task_id), None)
            if task is None:
                return

            cap_theo_doi = task.get("cap_theo_doi", "xa")
            tag_nd = "🏢 Chung PGD" if cap_theo_doi == "pgd" else "🏘️ Chi tiết xã"
            nguoi_pt = task.get("nguoi_phu_trach") or ""
            ngay_bd = task.get("ngay_bat_dau") or ""

            # Badge deadline màu
            hom_nay = date.today()
            try:
                deadline_date = date.fromisoformat(task["ngay_deadline"])
                if deadline_date < hom_nay:
                    badge = "🔴 Quá hạn"
                elif (deadline_date - hom_nay).days <= 3:
                    badge = "🟠 Sắp hết hạn (≤ 3 ngày)"
                else:
                    badge = "🟢 Còn hạn"
            except Exception:
                badge = ""

            st.caption(
                f"**{task['tieu_de']}** · {tag_nd} · "
                f"{LOAI_TASK.get(task['loai'], task['loai'])} · "
                f"Thời hạn: **{task['ngay_deadline']}** · "
                f"{UU_TIEN.get(task['uu_tien'], '')}"
                + (f" · Người PT: {nguoi_pt}" if nguoi_pt else "")
                + (f" · Từ: {ngay_bd}" if ngay_bd else "")
            )
            if badge:
                st.markdown(f"**{badge}**")
            if task.get("mo_ta"):
                st.info(task["mo_ta"])

        pgd_user_val = kwargs.get("pgd_user") or ""
        la_pgd_role = bool(pgd_user_val) and role not in ROLES_PHAN_HE_CN

        # ── Khối 2: CHỌN PHẠM VI ─────────────────────────────────────────
        if cap_theo_doi == "xa":
            if la_pgd_role:
                pgd_sel = pgd_user_val
            else:
                with st.container(border=True):
                    st.markdown("**② CHỌN PHẠM VI**")
                    ds_pgd_task = json.loads(task.get("ds_pgd") or "[]") or DS_PGD_ALL
                    pgd_sel = st.selectbox(
                        "Đơn vị PGD",
                        options=ds_pgd_task,
                        key=f"td_cap_nhat_pgd_{task_id}",
                    )
                    if pgd_sel:
                        st.caption(f"🏘️ Đang xem: **{pgd_sel}**")
            if not pgd_sel:
                st.warning("Tài khoản chưa được gán đơn vị.")
                return
            kq_list = [r for r in _doc_ketqua_task(task_id) if r["pgd"] == pgd_sel]
            ten_cot = "Xã / Phường"
            label_dv = "xã"
        else:
            kq_list = _doc_ketqua_task(task_id)
            if la_pgd_role:
                kq_list = [r for r in kq_list if r["pgd"] == pgd_user_val]
            pgd_sel = "__ALL__"
            ten_cot = "Đơn vị PGD"
            label_dv = "PGD"
            st.caption(f"🏢 Theo dõi chung **{len(kq_list)}** {label_dv}")

        if not kq_list:
            st.warning(f"Không tìm thấy dữ liệu {label_dv}. Thử tạo lại đầu việc.")
            return

        xong = sum(1 for r in kq_list if r["trang_thai"] == "da_hoan_thanh")
        tong = len(kq_list)
        pct = round(xong / tong * 100) if tong else 0

        # ── Khối 3: CẬP NHẬT TIẾN ĐỘ ─────────────────────────────────────
        with st.container(border=True):
            st.markdown("**③ CẬP NHẬT TIẾN ĐỘ**")

            # Progress + thống kê
            st.progress(
                xong / tong,
                text=f"✅ **{xong}/{tong}** {label_dv} hoàn thành  ·  "
                     f"⬜ **{tong - xong}** chưa thực hiện  ·  **{pct}%**",
            )

            confirm_key = f"_td_confirm_save_{task_id}_{pgd_sel}"
            editor_key = f"td_editor_{task_id}_{pgd_sel}"

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
                    "Trạng thái": TS_KQ_LABEL.get(r["trang_thai"], r["trang_thai"]),
                    "Hoàn thành": r["trang_thai"] == "da_hoan_thanh",
                    "Ngày hoàn thành": _parse_date(r.get("ngay_hoan_thanh")),
                    "Ghi chú": r.get("ghi_chu") or "",
                }
                for r in kq_list
            ])

            # Action bar: Lưu + Hoàn tác + thống kê
            c_save, c_reset, c_info = st.columns([1.5, 1, 4])
            with c_save:
                if st.session_state.get(confirm_key):
                    st.warning("⚠️ Xác nhận lưu?")
                    c_ok, c_huy = st.columns(2)
                    with c_ok:
                        if st.button("✅ Xác nhận", type="primary", use_container_width=True,
                                     key=f"{confirm_key}_ok"):
                            edited = st.session_state.get(f"{editor_key}_data")
                            if edited is None or len(edited) == 0:
                                st.session_state.pop(confirm_key, None)
                                st.rerun()
                            count = 0
                            for i in range(len(edited)):
                                ten_xa_dv = edited.iloc[i][ten_cot]
                                trang_thai = "da_hoan_thanh" if edited.iloc[i]["Hoàn thành"] else "chua_thuc_hien"
                                ngay_val = edited.iloc[i]["Ngày hoàn thành"]
                                ngay_ht = None
                                if pd.notna(ngay_val) and ngay_val:
                                    try:
                                        ngay_ht = pd.to_datetime(ngay_val).date().isoformat()
                                    except Exception:
                                        ngay_ht = None
                                pgd_val = ten_xa_dv if cap_theo_doi == "pgd" else pgd_sel
                                try:
                                    _upsert_ketqua_xa(
                                        task_id, ten_xa_dv, pgd_val,
                                        trang_thai, ngay_ht,
                                        str(edited.iloc[i]["Ghi chú"]).strip() or None,
                                        username,
                                    )
                                    count += 1
                                except Exception as e:
                                    st.warning(f"Lỗi {ten_xa_dv}: {e}")
                            db.ghi_audit(username, "tien_do_cap_nhat_xa",
                                         f"Task '{task['tieu_de']}' · {count} {label_dv}")
                            st.session_state.pop(confirm_key, None)
                            st.session_state.pop(f"{editor_key}_data", None)
                            st.toast(f"✅ Đã lưu {count} {label_dv}.")
                            st.rerun()
                    with c_huy:
                        if st.button("❌ Hủy", use_container_width=True,
                                     key=f"{confirm_key}_cancel"):
                            st.session_state.pop(confirm_key, None)
                            st.rerun()
                else:
                    if st.button("💾 Lưu thay đổi", type="primary", use_container_width=True,
                                 key=f"{confirm_key}_btn"):
                        st.session_state[confirm_key] = True
                        st.rerun()
            with c_reset:
                if st.button("↩️ Hoàn tác", use_container_width=True,
                             key=f"_td_undo_{task_id}_{pgd_sel}"):
                    for k in list(st.session_state.keys()):
                        if k.startswith(editor_key) or k.startswith(confirm_key) or k.endswith("_data"):
                            st.session_state.pop(k, None)
                    st.rerun()
            with c_info:
                st.caption(f"✅ {xong} · ⬜ {tong - xong} · {pct}% · "
                           f"Tick ☑ để đánh dấu hoàn thành")

            # Data editor — cache dữ liệu vào session_state để nút lưu dùng được
            edited = st.data_editor(
                df_edit,
                column_config={
                    ten_cot: st.column_config.TextColumn(ten_cot, disabled=True),
                    "Trạng thái": st.column_config.TextColumn(
                        "Trạng thái", disabled=True, width="small",
                    ),
                    "Hoàn thành": st.column_config.CheckboxColumn("✅ Hoàn thành"),
                    "Ngày hoàn thành": st.column_config.DateColumn(
                        "Ngày hoàn thành", format="DD/MM/YYYY", default=None,
                    ),
                    "Ghi chú": st.column_config.TextColumn(width="large"),
                },
                hide_index=True,
                use_container_width=True,
                key=editor_key,
            )
            st.session_state[f"{editor_key}_data"] = edited'''

content = content[:start] + new_func + content[end:]

with open('tabs/tab_tien_do.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Done. New function written.")
print(f"Old lines: {old_func.count(chr(10))} New lines: {new_func.count(chr(10))}")
