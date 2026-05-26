"""Add da_gui_cn button to _subtab_gui_cn_pgd"""
SRC = r"d:\VBSP-SCM\tabs\tab_xu_ly_rui_ro.py"
with open(SRC, "r", encoding="utf-8") as f:
    content = f.read()

# Insert after "Bước 3: Xuất biểu mẫu từng hồ sơ" marker
old = '''        st.markdown("---")
        st.markdown("#### 📄 Bước 3: Xuất biểu mẫu từng hồ sơ")

    # ── Chọn hồ sơ ───────────────────────────────────────────────────'''

new = '''        st.markdown("---")
        st.markdown("#### 📄 Bước 3: Xuất biểu mẫu từng hồ sơ")

        # ── Bước 4: Đánh dấu đã gửi CN ──────────────────────────────
        st.markdown("---")
        st.markdown("#### 📤 Bước 4: Đánh dấu đã gửi CN")
        da_gui = all(hs.da_gui_cn for hs in ds_hs)
        if da_gui:
            st.success("✅ Tất cả hồ sơ kỳ này đã được đánh dấu gửi CN.")
        else:
            so_chua_gui = sum(1 for hs in ds_hs if not hs.da_gui_cn)
            st.info(f"📋 Còn {so_chua_gui}/{len(ds_hs)} hồ sơ chưa đánh dấu gửi CN.")
            if st.button("📤 ĐÁNH DẤU ĐÃ GỬI CN", type="primary", use_container_width=True, key="xlrr_pgd_gui_danh_dau"):
                for hs in ds_hs:
                    hs.da_gui_cn = True
                LuuTruXLRR.luu_pgd(ds_hs, pgd_slug(pgd_user), int(nam_xuat), thang_xuat, ctx.username)
                db.ghi_audit(ctx.username, "xlrr_gui_cn", f"{pgd_user}: {len(ds_hs)} HS T{thang_xuat}/{int(nam_xuat)}")
                st.success(f"✅ Đã đánh dấu {len(ds_hs)} hồ sơ gửi CN!")
                st.cache_data.clear()
                st.rerun()

    # ── Chọn hồ sơ ───────────────────────────────────────────────────'''

if old in content:
    content = content.replace(old, new, 1)
    print("[OK] da_gui_cn button added to _subtab_gui_cn_pgd")
else:
    print("[ERROR] marker NOT FOUND")

# Also fix the "mmục" typo in dashboard
content = content.replace('"mmục này"', '"mục này"')

with open(SRC, "w", encoding="utf-8") as f:
    f.write(content)

print("Done")
