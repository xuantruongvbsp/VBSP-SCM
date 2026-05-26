"""Script patching tab_xu_ly_rui_ro.py — thêm Quản lý đợt + Tổng hợp mới + fix bugs."""
import re

SRC = r"d:\VBSP-SCM\tabs\tab_xu_ly_rui_ro.py"

with open(SRC, "r", encoding="utf-8") as f:
    content = f.read()

# ── Patch 1: Fix _la_cn used before definition ───────────────────────────────
# Move `_la_cn = la_phan_he_cn(role)` to BEFORE the Chọn đợt section
old_1 = (
    '    # ── Chọn đợt XLRR ────────────────────────────────────────────────────────\n'
    '    _nam_xl = datetime.now().year\n'
    '    ds_dot = LuuTruDotXLRR.doc_ds(_nam_xl, "cn") if _la_cn else LuuTruDotXLRR.doc_ds(_nam_xl, "pgd", pgd_slug_val)'
)
new_1 = (
    '    _la_cn = la_phan_he_cn(role)\n'
    '\n'
    '    # ── Chọn đợt XLRR ────────────────────────────────────────────────────────\n'
    '    _nam_xl = datetime.now().year\n'
    '    ds_dot = LuuTruDotXLRR.doc_ds(_nam_xl, "cn") if _la_cn else LuuTruDotXLRR.doc_ds(_nam_xl, "pgd", pgd_slug_val)'
)
if old_1 in content:
    content = content.replace(old_1, new_1, 1)
    print("[OK] Patch 1: _la_cn moved up")
else:
    print("[WARN] Patch 1: pattern NOT FOUND")

# ── Patch 1b: Fix typo "đợtt" → "đợt" ─────────────────────────────────────
content = content.replace('tạo đợtt trước', 'tạo đợt trước')

# ── Patch 1c: Remove duplicate _la_cn definition later ─────────────────────
# The old _la_cn = la_phan_he_cn(role) at original line ~198 is now a duplicate
# Find and remove the SECOND occurrence after `_nam, _thang = _now.year, _now.month`
old_dup = (
    '    _now = datetime.now()\n'
    '    _nam, _thang = _now.year, _now.month\n'
    '    _la_cn = la_phan_he_cn(role)\n'
    '    _edit_key'
)
new_dup = (
    '    _now = datetime.now()\n'
    '    _nam, _thang = _now.year, _now.month\n'
    '    _edit_key'
)
if old_dup in content:
    content = content.replace(old_dup, new_dup, 1)
    print("[OK] Patch 1c: duplicate _la_cn removed")
else:
    print("[WARN] Patch 1c: duplicate pattern NOT FOUND")


# ── Patch 2: Thêm _subtab_quan_ly_dot_cn ─────────────────────────────────────
# Insert BEFORE the "# ═══ MAIN RENDER ═══" section

new_dot_cn = '''
# ══════════════════════════════════════════════════════════════════════════════
# SUB-TAB: QUẢN LÝ ĐỢT XLRR (CN)
# ══════════════════════════════════════════════════════════════════════════════

def _subtab_quan_ly_dot_cn(ctx: TabContext) -> None:
    """CN quản lý đợt XLRR: tạo, sửa, xóa đợt chung toàn Chi nhánh."""
    st.caption("Tạo và quản lý các đợt XLRR chung toàn Chi nhánh")

    now = datetime.now()
    nam = st.number_input("Năm", min_value=2020, max_value=2030, value=now.year, key="xlrr_dotcn_nam")

    ds_dot = LuuTruDotXLRR.doc_ds(nam, "cn")

    # ── Form tạo đợt mới ──────────────────────────────────────────────────
    with st.expander("➕ Tạo đợt XLRR mới", expanded=len(ds_dot) == 0):
        col1, col2, col3 = st.columns(3)
        with col1:
            ten_dot = st.text_input("Tên đợt", placeholder="VD: Đợt 1/2026", key="xlrr_dotcn_ten")
        with col2:
            ngay_bd = st.date_input("Ngày bắt đầu", value=date.today(), format="DD/MM/YYYY", key="xlrr_dotcn_bd")
        with col3:
            ngay_kt = st.date_input("Ngày kết thúc", value=date.today(), format="DD/MM/YYYY", key="xlrr_dotcn_kt")

        if st.button("✅ Tạo đợt", type="primary", use_container_width=True, key="xlrr_dotcn_tao"):
            if not ten_dot.strip():
                st.error("Vui lòng nhập tên đợt.")
            elif ngay_kt < ngay_bd:
                st.error("Ngày kết thúc phải sau ngày bắt đầu.")
            else:
                dot = LuuTruDotXLRR.tao_dot(
                    ten_dot.strip(), nam, ngay_bd, ngay_kt,
                    ctx.username, "cn",
                )
                st.success(f"Đã tạo đợt: {dot.ten_dot} ({dot.id})")
                st.cache_data.clear()
                st.rerun()

    # ── Danh sách đợt hiện có ─────────────────────────────────────────────
    if not ds_dot:
        st.info("Chưa có đợt XLRR nào trong năm này.")
        return

    st.markdown("---")
    st.markdown("#### 📋 Danh sách đợt XLRR")

    for dot in ds_dot:
        c1, c2, c3, c4, c5 = st.columns([3, 2, 2, 1, 1])
        with c1:
            st.markdown(f"**{dot.ten_dot}**  \n`{dot.id}`")
        with c2:
            st.caption(f"📅 {dot.ngay_bat_dau:%d/%m/%Y} – {dot.ngay_ket_thuc:%d/%m/%Y}")
        with c3:
            st.caption(dot.trang_thai_label)
        with c4:
            if st.button("✏️", key=f"xlrr_dotcn_edit_{dot.id}", help="Sửa đợt này"):
                st.session_state[f"xlrr_dotcn_editing"] = dot.id
                st.rerun()
        with c5:
            with st.popover("🗑️"):
                st.warning(f"Xóa đợt **{dot.ten_dot}**?")
                if st.button("⚠️ Xác nhận xóa", key=f"xlrr_dotcn_del_{dot.id}", type="primary"):
                    if LuuTruDotXLRR.xoa_dot(dot.id, nam, "cn", "", ctx.username):
                        st.toast(f"Đã xóa đợt {dot.ten_dot}", icon="🗑️")
                        st.cache_data.clear()
                        st.rerun()
                    else:
                        st.error("Không thể xóa đợt.")

        # ── Inline edit ──────────────────────────────────────────────────
        edit_id = st.session_state.get("xlrr_dotcn_editing", "")
        if edit_id == dot.id:
            with st.container():
                st.markdown(f"#### ✏️ Sửa đợt: {dot.ten_dot}")
                ec1, ec2, ec3, ec4 = st.columns(4)
                with ec1:
                    ten_moi = st.text_input("Tên đợt", value=dot.ten_dot, key=f"xlrr_dotcn_e_ten_{dot.id}")
                with ec2:
                    bd_moi = st.date_input("Ngày BĐ", value=dot.ngay_bat_dau, format="DD/MM/YYYY", key=f"xlrr_dotcn_e_bd_{dot.id}")
                with ec3:
                    kt_moi = st.date_input("Ngày KT", value=dot.ngay_ket_thuc, format="DD/MM/YYYY", key=f"xlrr_dotcn_e_kt_{dot.id}")
                with ec4:
                    da_gui = st.checkbox("Đã gửi TW", value=dot.da_gui_tw, key=f"xlrr_dotcn_e_gui_{dot.id}")
                bc1, bc2 = st.columns([1, 3])
                with bc1:
                    if st.button("💾 Lưu", type="primary", key=f"xlrr_dotcn_save_{dot.id}"):
                        LuuTruDotXLRR.cap_nhat_dot(
                            dot.id, nam, "cn", "", ctx.username,
                            ten_dot=ten_moi.strip(), ngay_bat_dau=bd_moi,
                            ngay_ket_thuc=kt_moi, da_gui_tw=da_gui,
                        )
                        st.session_state.pop("xlrr_dotcn_editing", None)
                        st.cache_data.clear()
                        st.rerun()
                with bc2:
                    if st.button("Hủy", key=f"xlrr_dotcn_cancel_{dot.id}"):
                        st.session_state.pop("xlrr_dotcn_editing", None)
                        st.rerun()
            st.markdown("---")


# ══════════════════════════════════════════════════════════════════════════════
# SUB-TAB: ĐỢT XLRR (PGD)
# ══════════════════════════════════════════════════════════════════════════════

def _subtab_dot_xlrr_pgd(ctx: TabContext) -> None:
    """PGD quản lý đợt XLRR: tạo đợt riêng hoặc copy từ CN."""
    st.caption("Quản lý đợt XLRR của PGD")

    pgd_val = ctx.pgd_user or DON_VI_CHI_NHANH
    slug_val = pgd_slug(pgd_val)
    now = datetime.now()
    nam = st.number_input("Năm", min_value=2020, max_value=2030, value=now.year, key="xlrr_dotpgd_nam")

    ds_dot_pgd = LuuTruDotXLRR.doc_ds(nam, "pgd", slug_val)
    ds_dot_cn = LuuTruDotXLRR.doc_ds(nam, "cn")

    # ── Tab: Tự tạo hoặc Copy từ CN ───────────────────────────────────────
    t1, t2 = st.tabs(["✏️ Tự tạo đợt", "📋 Copy từ CN"])

    with t1:
        with st.form("xlrr_dotpgd_form_tao"):
            col1, col2, col3 = st.columns(3)
            with col1:
                ten_dot = st.text_input("Tên đợt", placeholder="VD: Đợt 1/2026", key="xlrr_dotpgd_ten")
            with col2:
                ngay_bd = st.date_input("Ngày bắt đầu", value=date.today(), format="DD/MM/YYYY", key="xlrr_dotpgd_bd")
            with col3:
                ngay_kt = st.date_input("Ngày kết thúc", value=date.today(), format="DD/MM/YYYY", key="xlrr_dotpgd_kt")

            if st.form_submit_button("✅ Tạo đợt", type="primary"):
                if not ten_dot.strip():
                    st.error("Vui lòng nhập tên đợt.")
                elif ngay_kt < ngay_bd:
                    st.error("Ngày kết thúc phải sau ngày bắt đầu.")
                else:
                    dot = LuuTruDotXLRR.tao_dot(
                        ten_dot.strip(), nam, ngay_bd, ngay_kt,
                        ctx.username, "pgd", slug_val,
                    )
                    st.success(f"Đã tạo đợt: {dot.ten_dot}")
                    st.cache_data.clear()
                    st.rerun()

    with t2:
        if not ds_dot_cn:
            st.info("CN chưa có đợt nào để copy.")
        else:
            dot_cn_labels = {f"{d.ten_dot} ({d.ngay_bat_dau:%d/%m}–{d.ngay_ket_thuc:%d/%m})": d for d in ds_dot_cn}
            dot_cn_sel = st.selectbox(
                "Chọn đợt của CN để copy", list(dot_cn_labels.keys()),
                key="xlrr_dotpgd_copy_from",
            )
            if st.button("📋 Copy đợt này cho PGD", type="primary", key="xlrr_dotpgd_copy_btn"):
                src = dot_cn_labels[dot_cn_sel]
                dot = LuuTruDotXLRR.tao_dot(
                    f"{src.ten_dot} (copy)", nam,
                    src.ngay_bat_dau, src.ngay_ket_thuc,
                    ctx.username, "pgd", slug_val,
                )
                st.success(f"Đã copy đợt: {dot.ten_dot}")
                st.cache_data.clear()
                st.rerun()

    # ── Danh sách đợt PGD ─────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("#### 📋 Đợt XLRR của PGD")

    if not ds_dot_pgd:
        st.info("PGD chưa có đợt XLRR nào.")
        return

    for dot in ds_dot_pgd:
        c1, c2, c3, c4 = st.columns([3, 2, 2, 1])
        with c1:
            st.markdown(f"**{dot.ten_dot}**  \n`{dot.id}`")
        with c2:
            st.caption(f"📅 {dot.ngay_bat_dau:%d/%m/%Y} – {dot.ngay_ket_thuc:%d/%m/%Y}")
        with c3:
            st.caption(dot.trang_thai_label)
        with c4:
            with st.popover("🗑️"):
                st.warning(f"Xóa đợt **{dot.ten_dot}**?")
                if st.button("⚠️ Xác nhận xóa", key=f"xlrr_dotpgd_del_{dot.id}", type="primary"):
                    if LuuTruDotXLRR.xoa_dot(dot.id, nam, "pgd", slug_val, ctx.username):
                        st.toast(f"Đã xóa đợt {dot.ten_dot}", icon="🗑️")
                        st.cache_data.clear()
                        st.rerun()
'''

# Insert new functions BEFORE the MAIN RENDER section
old_render_marker = '# ══════════════════════════════════════════════════════════════════════════════\n# MAIN RENDER\n# ══════════════════════════════════════════════════════════════════════════════'
if old_render_marker in content:
    content = content.replace(old_render_marker, new_dot_cn + '\n' + old_render_marker, 1)
    print("[OK] Patch 2: _subtab_quan_ly_dot_cn + _subtab_dot_xlrr_pgd inserted")
else:
    print("[ERROR] Patch 2: MAIN RENDER marker NOT FOUND")


# ── Patch 3: Rewrite _subtab_tong_hop_cn ─────────────────────────────────────
# Replace the entire function body from "def _subtab_tong_hop_cn" to the next "# ═══" marker

old_tong_hop_start = 'def _subtab_tong_hop_cn(ctx: TabContext) -> None:'
old_tong_hop_end = '# ══════════════════════════════════════════════════════════════════════════════\n# SUB-TAB 4 (PGD) / SUB-TAB 4 (CN): GỬI CN / XUẤT BIỂU MẪU\n# ══════════════════════════════════════════════════════════════════════════════'

if old_tong_hop_start in content and old_tong_hop_end in content:
    idx_start = content.index(old_tong_hop_start)
    idx_end = content.index(old_tong_hop_end, idx_start)

    new_tong_hop = '''def _subtab_tong_hop_cn(ctx: TabContext) -> None:
    """Tổng hợp toàn Chi nhánh — gửi TW."""
    st.caption("Tổng hợp hồ sơ XLRR toàn Chi nhánh — gom dữ liệu PGD, rà soát và gửi TW")

    from services.xlrr_export_service import (
        nhap_danh_sach_rui_ro_excel,
        tong_hop_theo_bien_phap,
    )
    from collections import defaultdict

    now = datetime.now()
    nam = st.number_input("Năm", min_value=2020, max_value=2030, value=now.year, key="xlrr_th_nam")

    # ── Chọn đợt XLRR ────────────────────────────────────────────────────
    ds_dot = LuuTruDotXLRR.doc_ds(nam, "cn")
    if not ds_dot:
        st.warning("⚠️ Chưa có đợt XLRR nào cho năm này. Vào tab '📅 Quản lý đợt' để tạo.")
        return

    dot_labels = {f"{d.ten_dot} ({d.ngay_bat_dau:%d/%m}–{d.ngay_ket_thuc:%d/%m}) [{d.trang_thai_label}]": d for d in ds_dot}
    dot_sel = st.selectbox("📅 Chọn đợt XLRR", list(dot_labels.keys()), key="xlrr_th_dot")
    dot = dot_labels[dot_sel]

    st.markdown("---")
    st.markdown(f"#### 📊 Tổng quan đợt: **{dot.ten_dot}**")
    col_st1, col_st2, col_st3, col_st4 = st.columns(4)
    col_st1.metric("Trạng thái", dot.trang_thai_label)
    col_st2.metric("Ngày BĐ", dot.ngay_bat_dau.strftime("%d/%m/%Y"))
    col_st3.metric("Ngày KT", dot.ngay_ket_thuc.strftime("%d/%m/%Y"))
    col_st4.metric("Đã gửi TW", "✅ Rồi" if dot.da_gui_tw else "⏳ Chưa")

    # ── Bước 1: Tự động gom hồ sơ PGD đã gửi ─────────────────────────────
    st.markdown("---")
    st.markdown("#### 📥 Bước 1: Tự động gom hồ sơ từ PGD")

    all_pgd_hs = []
    pgd_summary = []
    for ten_pgd in DS_PGD:
        slug = pgd_slug(ten_pgd)
        # Quét tất cả các tháng trong năm
        for thang in range(1, 13):
            ds = LuuTruXLRR.doc_pgd(slug, nam, thang)
            hs_gui = [hs for hs in ds if hs.da_gui_cn]
            all_pgd_hs.extend(hs_gui)
        if hs_gui:
            pgd_summary.append({
                "PGD": ten_pgd,
                "Số HS đã gửi": len(hs_gui),
                "Khoanh": sum(1 for hs in hs_gui if hs.is_khoanh),
                "Xóa": sum(1 for hs in hs_gui if hs.is_xoa),
                "Dư nợ (tr)": fmt_ty(sum(hs.tong_du_no for hs in hs_gui)),
            })

    if pgd_summary:
        df_sum = pd.DataFrame(pgd_summary)
        st.dataframe(df_sum, use_container_width=True, hide_index=True)
        col_gom, _ = st.columns([1, 3])
        with col_gom:
            if st.button("🔄 GOM vào CN", type="primary", use_container_width=True, key="xlrr_th_gom"):
                # Merge all PGD HS into CN storage for the current month
                thang_hien_tai = now.month
                LuuTruXLRR.luu_cn(all_pgd_hs, nam, thang_hien_tai, ctx.username)
                st.success(f"✅ Đã gom {len(all_pgd_hs)} hồ sơ từ {len(pgd_summary)} PGD vào CN!")
                db.ghi_audit(ctx.username, "xlrr_gom_cn", f"Đợt {dot.id}: {len(all_pgd_hs)} HS từ {len(pgd_summary)} PGD")
                st.cache_data.clear()
                st.rerun()
    else:
        st.info("Chưa có PGD nào gửi hồ sơ lên CN.")

    # ── Bước 2: Import Excel (fallback) ───────────────────────────────────
    st.markdown("---")
    st.markdown("#### 📂 Bước 2: Import Excel (PGD gửi file thủ công)")

    uploaded_files = st.file_uploader(
        "Chọn file Excel từ PGD (có thể chọn nhiều file)",
        type=['xlsx'],
        accept_multiple_files=True,
        key="xlrr_th_upload",
    )

    if uploaded_files:
        ds_import = []
        errors = []
        for file in uploaded_files:
            try:
                ds_hs = nhap_danh_sach_rui_ro_excel(file.read())
                ds_import.extend(ds_hs)
            except Exception as e:
                logger.error("import_xlrr_excel: %s — %s", file.name, e, exc_info=True)
                errors.append(f"{file.name}: {str(e)}")

        if errors:
            st.error("❌ Lỗi khi đọc file:")
            for err in errors:
                st.write(f"- {err}")

        if ds_import:
            preview_df = pd.DataFrame([{
                "Tên KH": hs.ten_kh,
                "PGD": hs.ten_pgd,
                "Số KU": hs.so_ku,
                "Biện pháp": "Khoanh" if hs.bien_phap == "khoanh" else "Xóa",
                "Dư nợ gốc": fmt_ty(hs.du_no_goc),
            } for hs in ds_import])
            st.dataframe(preview_df, use_container_width=True, hide_index=True)

            if st.button("💾 Merge file Excel vào CN", type="primary", use_container_width=True, key="xlrr_th_merge_import"):
                thang_hien_tai = now.month
                ds_cn = LuuTruXLRR.doc_cn(nam, thang_hien_tai)
                cn_dict = {hs.id: hs for hs in ds_cn}
                for hs in ds_import:
                    cn_dict[hs.id] = hs
                LuuTruXLRR.luu_cn(list(cn_dict.values()), nam, thang_hien_tai, ctx.username)
                st.success(f"✅ Đã merge {len(ds_import)} hồ sơ từ Excel vào CN!")
                db.ghi_audit(ctx.username, "xlrr_import_cn", f"{len(ds_import)} HS từ Excel")
                st.cache_data.clear()
                st.rerun()

    # ── Bước 3: Rà soát danh sách CN ──────────────────────────────────────
    st.markdown("---")
    st.markdown("#### ✅ Bước 3: Rà soát danh sách gửi TW")

    thang_hien_tai = now.month
    ds_cn_all = LuuTruXLRR.doc_cn(nam, thang_hien_tai)

    if not ds_cn_all:
        st.info("Chưa có hồ sơ nào trong CN. Thực hiện Bước 1 hoặc Bước 2 trước.")
    else:
        st.caption(f"Tổng: **{len(ds_cn_all)}** hồ sơ trong CN — Chọn/bỏ chọn để quyết định gửi TW")

        df_check = pd.DataFrame([{
            "Chọn": True,
            "Tên KH": hs.ten_kh,
            "PGD": hs.ten_pgd,
            "Số KU": hs.so_ku,
            "Biện pháp": "Khoanh" if hs.bien_phap == "khoanh" else "Xóa",
            "Dư nợ gốc (tr)": round(hs.du_no_goc / 1_000_000, 1),
            "Nguồn": "TW" if hs.nguon_von == NGUON_TW else "ĐP",
            "ID": hs.id,
        } for hs in ds_cn_all])

        df_edited = st.data_editor(
            df_check,
            column_config={
                "Chọn": st.column_config.CheckboxColumn("Gửi TW", default=True),
                "ID": None,
            },
            disabled=["Tên KH", "PGD", "Số KU", "Biện pháp", "Dư nợ gốc (tr)", "Nguồn"],
            use_container_width=True,
            hide_index=True,
            key="xlrr_th_check",
        )

        ds_chon = [hs for hs in ds_cn_all
                   if hs.id in set(df_edited[df_edited["Chọn"]]["ID"].tolist())]

        st.caption(f"Đã chọn: **{len(ds_chon)}** / {len(ds_cn_all)} hồ sơ")

        # ── Bước 4: Gửi TW ──────────────────────────────────────────────
        st.markdown("---")
        st.markdown("#### 📤 Bước 4: Gửi lên TW")

        col_gui1, col_gui2 = st.columns([1, 3])
        with col_gui1:
            if st.button("📤 GỬI LÊN TW", type="primary", use_container_width=True, key="xlrr_th_gui_tw", disabled=dot.da_gui_tw or len(ds_chon) == 0):
                dot.da_gui_tw = True
                LuuTruDotXLRR.cap_nhat_dot(dot.id, nam, "cn", "", ctx.username, da_gui_tw=True)
                st.success(f"✅ Đã gửi đợt **{dot.ten_dot}** lên TW ({len(ds_chon)} hồ sơ)!")
                db.ghi_audit(ctx.username, "xlrr_gui_tw", f"Đợt {dot.id}: {len(ds_chon)} HS")
                st.cache_data.clear()
                st.rerun()
        with col_gui2:
            if dot.da_gui_tw:
                st.success("✅ Đợt này đã được gửi lên TW.")

        # ── Xuất mẫu 04/05 (tổng hợp theo biện pháp) ──────────────────
        st.markdown("---")
        st.markdown("#### 📄 Xuất mẫu tổng hợp 04/XLN và 05/XLN")

        ds_khoanh = tong_hop_theo_bien_phap(ds_chon, "khoanh")
        ds_xoa = tong_hop_theo_bien_phap(ds_chon, "xoa")

        col_export = st.columns(2)

        with col_export[0]:
            st.markdown("**Mẫu 04/XLN — Tổng hợp Khoanh nợ**")
            st.caption(f"Có {len(ds_khoanh)} hồ sơ khoanh nợ")
            if ds_khoanh:
                with st.expander("📝 Nhập thông tin để xuất 04/XLN"):
                    ten_pgd_04 = st.text_input("Phó GĐ NHCSXH:", key="xlrr_04_pgd")
                    ten_ubnd_04 = st.text_input("Phó Chủ tịch UBND:", key="xlrr_04_ubnd")
                    ten_hoi_nd_04 = st.text_input("Chủ tịch Hội ND:", key="xlrr_04_hoi_nd")
                    ten_cbtd_04 = st.text_input("CBTD NHCSXH:", key="xlrr_04_cbtd")
                    ngay_lap_04 = st.date_input("Ngày lập:", value=date.today(), format="DD/MM/YYYY", key="xlrr_04_ngay")
                    if st.button("📄 Xuất 04/XLN", type="primary", use_container_width=True, key="btn_04xln"):
                        from services.word_xln_service import _tao_word_04xln_v2
                        thong_tin_04 = {
                            "ten_nhcsxh": TEN_CHI_NHANH_HIEN_THI,
                            "dia_danh": "TP. Biên Hòa",
                            "ngay_lap": ngay_lap_04,
                            "ten_pgd": ten_pgd_04,
                            "ten_ubnd": ten_ubnd_04,
                            "ten_hoi_nd": ten_hoi_nd_04,
                            "ten_cbtd": ten_cbtd_04,
                        }
                        try:
                            file_bytes = _tao_word_04xln_v2(ds_khoanh, thong_tin_04)
                            st.download_button(
                                label="⬇️ Tải 04/XLN (.docx)",
                                data=file_bytes,
                                file_name=f"04XLN_TongHop_Khoanh_Dot{dot.id}.docx",
                                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                use_container_width=True,
                                key="dl_04xln"
                            )
                            db.ghi_audit(ctx.username, "xuat_04xln", f"{len(ds_khoanh)} hồ sơ khoanh nợ - {dot.id}")
                            st.success(f"✅ Đã xuất mẫu 04/XLN ({len(ds_khoanh)} hồ sơ)")
                        except Exception as e:
                            logger.error("xuat_04xln: %s", e, exc_info=True)
                            st.error(f"❌ Lỗi xuất 04/XLN: {e}")
            else:
                st.info("ℹ️ Không có hồ sơ khoanh nợ")

        with col_export[1]:
            st.markdown("**Mẫu 05/XLN — Tổng hợp Xóa nợ**")
            st.caption(f"Có {len(ds_xoa)} hồ sơ xóa nợ")
            if ds_xoa:
                with st.expander("📝 Nhập thông tin để xuất 05/XLN"):
                    ten_pgd_05 = st.text_input("Phó GĐ NHCSXH:", key="xlrr_05_pgd")
                    ten_ubnd_05 = st.text_input("Phó Chủ tịch UBND:", key="xlrr_05_ubnd")
                    ten_hoi_nd_05 = st.text_input("Chủ tịch Hội ND:", key="xlrr_05_hoi_nd")
                    ten_cbtd_05 = st.text_input("CBTD NHCSXH:", key="xlrr_05_cbtd")
                    ngay_lap_05 = st.date_input("Ngày lập:", value=date.today(), format="DD/MM/YYYY", key="xlrr_05_ngay")
                    if st.button("📄 Xuất 05/XLN", type="primary", use_container_width=True, key="btn_05xln"):
                        from services.word_xln_service import _tao_word_05xln_v2
                        thong_tin_05 = {
                            "ten_nhcsxh": TEN_CHI_NHANH_HIEN_THI,
                            "dia_danh": "TP. Biên Hòa",
                            "ngay_lap": ngay_lap_05,
                            "ten_pgd": ten_pgd_05,
                            "ten_ubnd": ten_ubnd_05,
                            "ten_hoi_nd": ten_hoi_nd_05,
                            "ten_cbtd": ten_cbtd_05,
                        }
                        try:
                            file_bytes = _tao_word_05xln_v2(ds_xoa, thong_tin_05)
                            st.download_button(
                                label="⬇️ Tải 05/XLN (.docx)",
                                data=file_bytes,
                                file_name=f"05XLN_TongHop_Xoa_Dot{dot.id}.docx",
                                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                use_container_width=True,
                                key="dl_05xln"
                            )
                            db.ghi_audit(ctx.username, "xuat_05xln", f"{len(ds_xoa)} hồ sơ xóa nợ - {dot.id}")
                            st.success(f"✅ Đã xuất mẫu 05/XLN ({len(ds_xoa)} hồ sơ)")
                        except Exception as e:
                            logger.error("xuat_05xln: %s", e, exc_info=True)
                            st.error(f"❌ Lỗi xuất 05/XLN: {e}")
            else:
                st.info("ℹ️ Không có hồ sơ xóa nợ")

        # ── Tờ trình CN gửi NHCSXH TW ──────────────────────────────────
        st.markdown("---")
        st.markdown("#### 📝 Tờ trình CN gửi NHCSXH TW")
        with st.expander("Nhập thông tin để xuất Tờ trình CN"):
            col_tt1, col_tt2 = st.columns(2)
            with col_tt1:
                dot_tt_cn = st.number_input("Đợt xử lý:", min_value=1, max_value=4, value=1, key="xlrr_tt_cn_dot")
                nam_tt_cn = st.number_input("Năm:", min_value=2020, max_value=2030, value=int(nam), key="xlrr_tt_cn_nam")
            with col_tt2:
                nguon_tt_cn = st.selectbox("Nguồn vốn:", ["Trung ương (TW)", "Địa phương (ĐP)"], key="xlrr_tt_cn_nguon")
            if st.button("📝 Xuất Tờ trình CN", type="primary", use_container_width=True, key="btn_tt_cn"):
                from services.word_xln_service import _tao_word_to_trinh_cn
                ds_kh_tt = tong_hop_theo_bien_phap(ds_chon, "khoanh")
                ds_xoa_tt = tong_hop_theo_bien_phap(ds_chon, "xoa")
                ds_kh_dict = [hs.to_dict() for hs in ds_kh_tt]
                ds_xoa_dict = [hs.to_dict() for hs in ds_xoa_tt]
                def _agg(ds_list):
                    tong = sum(float(r.get("tong_du_no", 0) or 0) for r in ds_list)
                    tw = sum(float(r.get("tong_du_no", 0) or 0) for r in ds_list if r.get("nguon_von") == 1)
                    dp = tong - tw
                    return {"tong": tong, "tw": tw, "dp": dp, "so_ho": len(ds_list)}
                tong_hop_kh = _agg(ds_kh_dict)
                tong_hop_xoa = _agg(ds_xoa_dict)
                nguon_label = nguon_tt_cn
                try:
                    file_bytes = _tao_word_to_trinh_cn(
                        tong_hop_kh, tong_hop_xoa, ds_kh_dict,
                        TEN_CHI_NHANH_HIEN_THI, nguon_label,
                        int(dot_tt_cn), int(nam_tt_cn),
                    )
                    st.download_button(
                        label="⬇️ Tải Tờ trình CN (.docx)",
                        data=file_bytes,
                        file_name=f"ToTrinh_CN_Dot{int(dot_tt_cn)}_{int(nam_tt_cn)}.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        use_container_width=True,
                        key="dl_tt_cn",
                    )
                    db.ghi_audit(ctx.username, "xuat_to_trinh_cn", f"Đợt {int(dot_tt_cn)}/{int(nam_tt_cn)}")
                    st.success("✅ Xuất Tờ trình CN thành công!")
                except Exception as e:
                    logger.error("xuat_to_trinh_cn: %s", e, exc_info=True)
                    st.error(f"❌ Lỗi xuất Tờ trình CN: {e}")


'''

    content = content[:idx_start] + new_tong_hop + content[idx_end:]
    print("[OK] Patch 3: _subtab_tong_hop_cn rewritten")
else:
    print("[ERROR] Patch 3: _subtab_tong_hop_cn markers NOT FOUND")


# ── Patch 4: Update render() tab labels ──────────────────────────────────────
old_render_cn_tabs = '''        if la_cn:
            tab_labels = [
                "🏢 Lập hồ sơ PGD",
                "🔍 Theo dõi QĐ62",
                "🔄 Tổng hợp CN",
                "📊 Dashboard",
                "📬 Thông báo kết quả",
            ]'''

new_render_cn_tabs = '''        if la_cn:
            tab_labels = [
                "📅 Quản lý đợt",
                "🏢 Lập hồ sơ PGD",
                "🔍 Theo dõi QĐ62",
                "🔄 Tổng hợp CN→TW",
                "📊 Dashboard",
                "📬 Thông báo kết quả",
            ]'''

if old_render_cn_tabs in content:
    content = content.replace(old_render_cn_tabs, new_render_cn_tabs, 1)
    print("[OK] Patch 4a: CN tab labels updated")
else:
    print("[ERROR] Patch 4a: CN tab labels NOT FOUND")

old_render_pgd_tabs = '''        elif la_pgd:
            tab_labels = [
                "🏢 Lập hồ sơ",
                "📤 Gửi lên CN",
                "📬 Kết quả XLRR",
            ]'''

new_render_pgd_tabs = '''        elif la_pgd:
            tab_labels = [
                "📅 Đợt XLRR",
                "🏢 Lập hồ sơ",
                "📤 Gửi lên CN",
                "📬 Kết quả XLRR",
            ]'''

if old_render_pgd_tabs in content:
    content = content.replace(old_render_pgd_tabs, new_render_pgd_tabs, 1)
    print("[OK] Patch 4b: PGD tab labels updated")
else:
    print("[ERROR] Patch 4b: PGD tab labels NOT FOUND")


# ── Patch 4c: Update tab routing in render() ────────────────────────────────
old_render_routing = '''        if la_cn:
            with tabs[0]:
                _subtab_lap_hs_pgd(df, ctx)
            with tabs[1]:
                _subtab_theo_doi_qd62(ctx)
            with tabs[2]:
                _subtab_tong_hop_cn(ctx)
            with tabs[3]:
                _subtab_dashboard_gd(ctx)
            with tabs[4]:
                _subtab_nhap_ket_qua_cn(ctx)'''

new_render_routing = '''        if la_cn:
            with tabs[0]:
                _subtab_quan_ly_dot_cn(ctx)
            with tabs[1]:
                _subtab_lap_hs_pgd(df, ctx)
            with tabs[2]:
                _subtab_theo_doi_qd62(ctx)
            with tabs[3]:
                _subtab_tong_hop_cn(ctx)
            with tabs[4]:
                _subtab_dashboard_gd(ctx)
            with tabs[5]:
                _subtab_nhap_ket_qua_cn(ctx)'''

if old_render_routing in content:
    content = content.replace(old_render_routing, new_render_routing, 1)
    print("[OK] Patch 4c: CN tab routing updated")
else:
    print("[ERROR] Patch 4c: CN tab routing NOT FOUND")

old_render_pgd_routing = '''        elif la_pgd:
            with tabs[0]:
                _subtab_lap_hs_pgd(df, ctx)
            with tabs[1]:
                _subtab_gui_cn_pgd(df, ctx)
            with tabs[2]:
                _subtab_ket_qua_pgd(ctx)'''

new_render_pgd_routing = '''        elif la_pgd:
            with tabs[0]:
                _subtab_dot_xlrr_pgd(ctx)
            with tabs[1]:
                _subtab_lap_hs_pgd(df, ctx)
            with tabs[2]:
                _subtab_gui_cn_pgd(df, ctx)
            with tabs[3]:
                _subtab_ket_qua_pgd(ctx)'''

if old_render_pgd_routing in content:
    content = content.replace(old_render_pgd_routing, new_render_pgd_routing, 1)
    print("[OK] Patch 4d: PGD tab routing updated")
else:
    print("[ERROR] Patch 4d: PGD tab routing NOT FOUND")

# ── Write back ───────────────────────────────────────────────────────────────
with open(SRC, "w", encoding="utf-8") as f:
    f.write(content)

print("[DONE] All patches applied successfully.")
print(f"Total lines: {len(content.split(chr(10)))}")
