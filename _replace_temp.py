import re

path = r"d:\VBSP-SCM\tabs\tab_xu_ly_rui_ro.py"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

old = '''    # ── Nhập dữ liệu từ PGD ────────────────────────────────────────────       
    st.markdown("---")
    st.markdown("#### 📥 Nhập dữ liệu từ PGD")

    uploaded_files = st.file_uploader(
        "Chọn file Excel từ các PGD (có thể chọn nhiều file)",
        type=['xlsx'],
        accept_multiple_files=True,
        key="xlrr_th_upload",
    )

    if uploaded_files:
        ds_all = []
        errors = []

        for file in uploaded_files:
            try:
                ds_hs = nhap_danh_sach_rui_ro_excel(file.read())
                ds_all.extend(ds_hs)
            except Exception as e:
                logger.error("import_xlrr_excel: %s — %s", file.name, e, exc_info=True)
                errors.append(f"{file.name}: {str(e)}")

        if errors:
            st.error("❌ Lỗi khi đọc file:")
            for err in errors:
                st.write(f"- {err}")

        if ds_all:
            # Preview dữ liệu
            st.markdown("**📋 Preview dữ liệu:**")
            import pandas as pd
            preview_df = pd.DataFrame([{
                "Tên KH": hs.ten_kh,
                "PGD": hs.ten_pgd,
                "Số KU": hs.so_ku,
                "Biện pháp": "Khoanh" if hs.bien_phap == "khoanh" else "Xóa",
                "Dư nợ gốc": fmt_ty(hs.du_no_goc),
            } for hs in ds_all])
            st.dataframe(preview_df, use_container_width=True, hide_index=True)

            col_merge = st.columns([1, 3])
            with col_merge[0]:
                if st.button("💾 Merge vào CN", type="primary", use_container_width=True):
                    count, errs = merge_du_lieu_pgd_vao_cn(ds_all, int(nam), thang, ctx.username)
                    if errs:
                        st.error(f"❌ Lỗi: {', '.join(errs)}")
                    else:
                        st.success(f"✅ Đã nhập {count} hồ sơ vào CN!")
                        st.rerun()
            with col_merge[1]:
                st.caption("Dữ liệu sẽ được merge vào database CN và ghi đè nếu trùng ID.")
    
    st.markdown("---")

    # Metrics
    metrics = TongHopXLRR.tong_hop_toan_cn(int(nam), thang)

    st.markdown("#### 📊 Tổng quan")
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Tổng hồ sơ", metrics["tong_ho_so"])
    c2.metric("PGD có hồ sơ", metrics["so_pgd_co_hs"])
    c3.metric("Khoanh nợ", metrics["so_khoanh"])
    c4.metric("Xóa nợ", metrics["so_xoa"])
    c5.metric("TW", fmt_ty(metrics["tw_tien"]))
    c6.metric("ĐP", fmt_ty(metrics["dp_tien"]))
    
    # Bảng tổng hợp theo PGD
    st.markdown("#### 🏢 Chi tiết theo PGD")
    df_pgd = TongHopXLRR.tong_hop_theo_pgd(int(nam), thang)
    if df_pgd.empty:
        st.info("ℹ️ Chưa có dữ liệu.")
    else:
        st.dataframe(df_pgd, use_container_width=True, hide_index=True)

    # Bảng tổng hợp theo chương trình
    st.markdown("#### 📋 Theo chương trình tín dụng")
    df_ct = TongHopXLRR.tong_hop_theo_chuong_trinh(int(nam), thang)
    if df_ct.empty:
        st.info("ℹ️ Chưa có dữ liệu.")
    else:
        st.dataframe(df_ct, use_container_width=True, hide_index=True)'''

new = '''    # ── Chọn đợt XLRR ─────────────────────────────────────────────────────
    ds_dot_tw = LuuTruDotXLRR.doc_ds(nam, "cn")
    ds_dot_tw = [d for d in ds_dot_tw if not d.da_gui_tw]
    dot_opts = {f"{d.ten_dot} ({d.ngay_bat_dau:%d/%m}–{d.ngay_ket_thuc:%d/%m})": d.id for d in ds_dot_tw}

    dot_id = ""
    if dot_opts:
        lbl = st.selectbox("📅 Chọn đợt XLRR cần tổng hợp", list(dot_opts.keys()), key="xlrr_th_dot")
        dot_id = dot_opts[lbl]
    else:
        st.info("✅ Tất cả các đợt đã gửi TW hoặc chưa có đợt.")
        st.markdown("---")

    if not dot_id:
        st.markdown("#### 📊 Dữ liệu CN đã gửi TW")
        metrics = TongHopXLRR.tong_hop_toan_cn(int(nam), thang)
        c1, c2, c3, c4, c5, c6 = st.columns(6)
        c1.metric("Tổng hồ sơ", metrics["tong_ho_so"])
        c2.metric("PGD có hồ sơ", metrics["so_pgd_co_hs"])
        c3.metric("Khoanh nợ", metrics["so_khoanh"])
        c4.metric("Xóa nợ", metrics["so_xoa"])
        c5.metric("TW", fmt_ty(metrics["tw_tien"]))
        c6.metric("ĐP", fmt_ty(metrics["dp_tien"]))
        df_pgd = TongHopXLRR.tong_hop_theo_pgd(int(nam), thang)
        if not df_pgd.empty:
            st.dataframe(df_pgd, use_container_width=True, hide_index=True)
        return

    # ── Bước 1: Hồ sơ PGD đã gửi lên ─────────────────────────────────────
    st.markdown("---")
    st.markdown("#### 📥 Bước 1: Hồ sơ từ PGD đã gửi lên")
    hs_tu_pgd = []
    for slug in [pgd_slug(p) for p in DS_PGD]:
        hs_list = LuuTruXLRR.doc_pgd(slug, nam, thang)
        hs_tu_pgd.extend([h for h in hs_list if h.dot_id == dot_id and h.da_gui_cn])
    if not hs_tu_pgd:
        st.info("ℹ️ Chưa có PGD nào gửi hồ sơ cho đợt này.")

    # ── Bước 2: Import Excel fallback ─────────────────────────────────────
    st.markdown("---")
    st.markdown("#### 📤 Bước 2: Import Excel (PGD chưa kịp lập)")
    uploaded_files = st.file_uploader(
        "Chọn file Excel từ PGD (nhiều file)", type=['xlsx'],
        accept_multiple_files=True, key="xlrr_th_upload",
    )
    hs_import = []
    if uploaded_files:
        for file in uploaded_files:
            try:
                ds_hs = nhap_danh_sach_rui_ro_excel(file.read())
                for h in ds_hs:
                    h.dot_id = dot_id
                hs_import.extend(ds_hs)
            except Exception as e:
                logger.error("import_xlrr_excel: %s — %s", file.name, e, exc_info=True)
                st.error(f"❌ {file.name}: {e}")

    # ── Bước 3: Rà soát + Checkboxes ─────────────────────────────────────
    st.markdown("---")
    st.markdown("#### ✅ Bước 3: Rà soát và chọn hồ sơ gửi TW")
    tat_ca_hs = hs_tu_pgd + hs_import
    if not tat_ca_hs:
        st.info("ℹ️ Chưa có hồ sơ nào. Đợi PGD gửi lên hoặc import Excel.")
        return

    hs_theo_pgd = defaultdict(list)
    for h in tat_ca_hs:
        hs_theo_pgd[h.ten_pgd or "Không rõ PGD"].append(h)

    hs_chon = []
    for pgd_name, hs_list_pgd in sorted(hs_theo_pgd.items()):
        with st.expander(f"🏢 **{pgd_name}** ({len(hs_list_pgd)} hồ sơ)", expanded=True):
            data_rows = []
            for h in hs_list_pgd:
                data_rows.append({
                    "Chọn": False,
                    "ID": h.id,
                    "Tên KH": h.ten_kh,
                    "Số KU": h.so_ku,
                    "Biện pháp": "Khoanh" if h.bien_phap == "khoanh" else "Xóa",
                    "Dư nợ gốc": fmt_ty(h.du_no_goc),
                    "Nguồn vốn": "TW" if h.nguon_von == NGUON_TW else "ĐP",
                })
            df_chon = pd.DataFrame(data_rows)
            edited = st.data_editor(
                df_chon, use_container_width=True, hide_index=True,
                column_config={
                    "Chọn": st.column_config.CheckboxColumn(default=False),
                    "ID": None,
                    "Dư nợ gốc": st.column_config.TextColumn("Dư nợ gốc (tr.đ)", disabled=True),
                },
                disabled=["Tên KH", "Số KU", "Biện pháp", "Nguồn vốn", "Dư nợ gốc"],
                key=f"xlrr_th_chon_{pgd_slug(pgd_name)}",
            )
            for _, row in edited.iterrows():
                if row["Chọn"]:
                    hs_chon.append(next(h for h in hs_list_pgd if h.id == row["ID"]))

    # ── Bước 4: Gửi TW ───────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("#### 📤 Bước 4: Gửi TW")
    st.caption(f"Đã chọn **{len(hs_chon)}/{len(tat_ca_hs)}** hồ sơ")
    if hs_chon:
        if st.button("📤 Gửi TW", type="primary", use_container_width=True, key="xlrr_th_gui_tw"):
            try:
                for h in hs_chon:
                    LuuTruXLRR.luu_hs_cn(h, nam, thang, ctx.username)
                dot = next(d for d in ds_dot_tw if d.id == dot_id)
                dot.da_gui_tw = True
                LuuTruDotXLRR.cap_nhat_dot(dot, ctx.username)
                db.ghi_audit(ctx.username, "xlrr_gui_tw", f"Đợt {dot.ten_dot}: {len(hs_chon)} hồ sơ")
                st.success(f"✅ Đã gửi {len(hs_chon)} hồ sơ lên TW!")
                st.cache_data.clear()
                st.rerun()
            except Exception as e:
                logger.error("gui_tw: %s", e, exc_info=True)
                st.error(f"❌ Lỗi gửi TW: {e}")
    else:
        st.warning("⚠️ Chưa chọn hồ sơ nào. Đánh dấu checkbox ở bước 3.")

    # ── Tổng quan ─────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("#### 📊 Dữ liệu CN đã gửi TW")
    metrics = TongHopXLRR.tong_hop_toan_cn(int(nam), thang)
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Tổng hồ sơ", metrics["tong_ho_so"])
    c2.metric("PGD có hồ sơ", metrics["so_pgd_co_hs"])
    c3.metric("Khoanh nợ", metrics["so_khoanh"])
    c4.metric("Xóa nợ", metrics["so_xoa"])
    c5.metric("TW", fmt_ty(metrics["tw_tien"]))
    c6.metric("ĐP", fmt_ty(metrics["dp_tien"]))
    df_pgd = TongHopXLRR.tong_hop_theo_pgd(int(nam), thang)
    if not df_pgd.empty:
        st.dataframe(df_pgd, use_container_width=True, hide_index=True)'''

if old in content:
    content = content.replace(old, new)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"OK: replaced successfully (old len={len(old)}, new len={len(new)})")
else:
    print("FAIL: old section not found")
    # Debug: find where it differs
    idx = content.find("Nhập dữ liệu từ PGD")
    if idx >= 0:
        print(f"Found 'Nhập dữ liệu từ PGD' at offset {idx}")
        print(f"Context: ...{content[idx-10:idx+50]}...")
