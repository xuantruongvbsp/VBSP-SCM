"""Tab Quản lý Công văn — ROADMAP §2.4

Tìm kiếm full-text, thêm/sửa/xóa, gắn tag & phân loại, xuất Excel.
"""
from __future__ import annotations

from datetime import date, datetime

import streamlit as st
import pandas as pd
from streamlit.delta_generator import DeltaGenerator

from logger import get_logger
from tabs.base_tab import TabContext
from services.onedrive_service import upload_cong_van, kiem_tra_ket_noi, _kiem_tra_config
from services.cong_van_service import (
    LOAI_CONG_VAN, TRANG_THAI_CV, TAG_GOP_Y,
    them_cv, cap_nhat_cv, xoa_cv, doc_cv, tim_kiem_cv,
    thong_ke_cv_theo_loai, thong_ke_cv_theo_trang_thai,
    xuat_danh_sach_cv, ds_cv_sap_den_han,
)

logger = get_logger(__name__)


def _form_them_cv(username: str) -> None:
    """Form thêm công văn mới."""
    st.markdown("#### ➕ Thêm công văn mới")
    with st.form("cv_form_them", border=True):
        col1, col2 = st.columns(2)
        with col1:
            so_hieu = st.text_input("Số hiệu *", placeholder="VD: 123/QĐ-NHCS", key="cv_f_so")
            ngay_bh = st.date_input("Ngày ban hành *", value=date.today(), format="DD/MM/YYYY", key="cv_f_ngay_bh")
            loai = st.selectbox("Loại *", options=list(LOAI_CONG_VAN.keys()), format_func=lambda x: LOAI_CONG_VAN[x], key="cv_f_loai")
            tag = st.multiselect("Tag", options=TAG_GOP_Y, key="cv_f_tag")
            file_upload = st.file_uploader("File đính kèm", type=["pdf", "docx", "xlsx"], key="cv_f_file")
        with col2:
            trich_yeu = st.text_area("Trích yếu *", placeholder="Nội dung trích yếu...", height=80, key="cv_f_trich_yeu")
            ngay_nhan = st.date_input("Ngày nhận *", value=date.today(), format="DD/MM/YYYY", key="cv_f_ngay_nhan")
            co_quan = st.text_input("Cơ quan ban hành", placeholder="VD: NHCSXH TW", key="cv_f_coquan")
            nguoi_ky = st.text_input("Người ký", key="cv_f_nguoi_ky")
        noi_dung = st.text_area("Nội dung tóm tắt", height=60, key="cv_f_noi_dung")
        trang_thai = st.selectbox("Trạng thái", options=list(TRANG_THAI_CV.keys()), format_func=lambda x: TRANG_THAI_CV[x], key="cv_f_tt")

        if st.form_submit_button("💾 Lưu công văn", type="primary", use_container_width=True):
            if not so_hieu.strip() or not trich_yeu.strip():
                st.error("⚠️ Số hiệu và Trích yếu là bắt buộc.")
                return
            import os
            file_path = ""
            onedrive_url = ""
            if file_upload:
                upload_dir = os.path.join("cache", "cong_van")
                os.makedirs(upload_dir, exist_ok=True)
                file_path = os.path.join(upload_dir, f"{so_hieu.replace('/', '_')}_{file_upload.name}")
                with open(file_path, "wb") as f:
                    f.write(file_upload.getvalue())

                # Push lên OneDrive (fallback graceful nếu chưa cấu hình hoặc lỗi)
                ket_qua_od = upload_cong_van(
                    file_bytes=file_upload.getvalue(),
                    file_name=file_upload.name,
                    so_hieu=so_hieu.strip(),
                    ngay_ban_hanh=ngay_bh,
                )
                if ket_qua_od.thanh_cong:
                    onedrive_url = ket_qua_od.url
                else:
                    st.warning(f"⚠️ Không thể upload OneDrive: {ket_qua_od.loi}. File đã lưu local.")

            them_cv(
                so_hieu=so_hieu.strip(),
                trich_yeu=trich_yeu.strip(),
                ngay_ban_hanh=ngay_bh.isoformat(),
                ngay_nhan=ngay_nhan.isoformat(),
                loai=loai,
                co_quan=co_quan.strip(),
                nguoi_ky=nguoi_ky.strip(),
                tag=", ".join(tag),
                noi_dung=noi_dung.strip(),
                file_path=file_path,
                onedrive_url=onedrive_url,
                trang_thai=trang_thai,
                username=username,
            )
            st.toast(f"✅ Đã thêm công văn '{so_hieu}'", icon="📋")
            st.rerun()


def _hien_thi_bang_cv(ds: list[dict], username: str) -> None:
    """Hiển thị bảng danh sách công văn với nút sửa/xóa."""
    if not ds:
        st.info("ℹ️ Không tìm thấy công văn nào.")
        return

    for cv in ds:
        with st.container():
            c1, c2, c3, c4 = st.columns([5, 1.5, 0.6, 0.6])
            loai_icon = LOAI_CONG_VAN.get(cv.get("loai", ""), "📋")
            with c1:
                tag_html = ""
                if cv.get("tag"):
                    tags = [t.strip() for t in cv.get("tag", "").split(",") if t.strip()]
                    tag_spans = " ".join(
                        f'<span style="background:#E8F5E9;color:#2E7D32;padding:1px 6px;border-radius:4px;font-size:11px;margin-right:4px">{t}</span>'
                        for t in tags[:5]
                    )
                    tag_html = f'<div style="margin-top:2px">{tag_spans}</div>'
                link_html = ""
                if cv.get("onedrive_url"):
                    link_html = (
                        f' <a href="{cv["onedrive_url"]}" target="_blank"'
                        f' style="color:#42A5F5;text-decoration:none;font-size:12px">'
                        f'📎 Xem file</a>'
                    )
                st.markdown(
                    f"**{loai_icon} {cv.get('so_hieu', '')}**"
                    f" — {cv.get('trich_yeu', '')[:80]}"
                    f"{link_html}"
                    f"{tag_html}",
                    unsafe_allow_html=True,
                )
            with c2:
                ngay_bh = (cv.get("ngay_ban_hanh", "") or "")[:10]
                st.caption(f"📅 BH: {ngay_bh}")
                tt_label = TRANG_THAI_CV.get(cv.get("trang_thai", ""), cv.get("trang_thai", ""))
                st.caption(tt_label)
            with c3:
                if st.button("✏️", key=f"cv_edit_{cv['id']}", help="Sửa"):
                    st.session_state["cv_edit_id"] = cv["id"]
                    st.rerun()
            with c4:
                with st.popover("🗑️"):
                    st.warning(f"Xóa công văn **{cv.get('so_hieu', '')}**?")
                    if st.button("⚠️ Xác nhận xóa", key=f"cv_del_ok_{cv['id']}", type="primary"):
                        xoa_cv(cv["id"], username)
                        st.toast(f"🗑️ Đã xóa công văn {cv.get('so_hieu', '')}", icon="🗑️")
                        st.rerun()


def _form_sua_cv(username: str) -> None:
    """Form sửa công văn."""
    edit_id = st.session_state.get("cv_edit_id")
    if not edit_id:
        return
    cv = doc_cv(edit_id)
    if not cv:
        st.session_state.pop("cv_edit_id", None)
        return

    st.markdown(f"#### ✏️ Sửa công văn: **{cv.get('so_hieu', '')}**")
    with st.form(f"cv_form_sua_{edit_id}", border=True):
        col1, col2 = st.columns(2)
        with col1:
            so_hieu = st.text_input("Số hiệu *", value=cv.get("so_hieu", ""), key=f"cv_s_so_{edit_id}")
            ngay_bh_raw = cv.get("ngay_ban_hanh", "")
            try:
                ngay_bh_def = date.fromisoformat(ngay_bh_raw[:10])
            except Exception:
                ngay_bh_def = date.today()
            ngay_bh = st.date_input("Ngày ban hành *", value=ngay_bh_def, format="DD/MM/YYYY", key=f"cv_s_ngay_bh_{edit_id}")
            _loai_val = cv.get("loai", "cong_van") if cv.get("loai", "cong_van") in LOAI_CONG_VAN else "cong_van"
            loai_idx = list(LOAI_CONG_VAN.keys()).index(_loai_val)
            loai = st.selectbox("Loại *", options=list(LOAI_CONG_VAN.keys()), format_func=lambda x: LOAI_CONG_VAN[x], index=loai_idx, key=f"cv_s_loai_{edit_id}")
            tag_cur = [t.strip() for t in cv.get("tag", "").split(",") if t.strip()]
            tag = st.multiselect("Tag", options=TAG_GOP_Y, default=tag_cur, key=f"cv_s_tag_{edit_id}")
        with col2:
            trich_yeu = st.text_area("Trích yếu *", value=cv.get("trich_yeu", ""), height=80, key=f"cv_s_ty_{edit_id}")
            ngay_nhan_raw = cv.get("ngay_nhan", "")
            try:
                ngay_nhan_def = date.fromisoformat(ngay_nhan_raw[:10])
            except Exception:
                ngay_nhan_def = date.today()
            ngay_nhan = st.date_input("Ngày nhận *", value=ngay_nhan_def, format="DD/MM/YYYY", key=f"cv_s_nn_{edit_id}")
            co_quan = st.text_input("Cơ quan ban hành", value=cv.get("co_quan_ban_hanh", ""), key=f"cv_s_cq_{edit_id}")
            nguoi_ky = st.text_input("Người ký", value=cv.get("nguoi_ky", ""), key=f"cv_s_nk_{edit_id}")
        noi_dung = st.text_area("Nội dung tóm tắt", value=cv.get("noi_dung_tom_tat", ""), height=60, key=f"cv_s_nd_{edit_id}")
        _tt_val = cv.get("trang_thai", "chua_xu_ly") if cv.get("trang_thai", "chua_xu_ly") in TRANG_THAI_CV else "chua_xu_ly"
        tt_idx = list(TRANG_THAI_CV.keys()).index(_tt_val)
        trang_thai = st.selectbox("Trạng thái", options=list(TRANG_THAI_CV.keys()), format_func=lambda x: TRANG_THAI_CV[x], index=tt_idx, key=f"cv_s_tt_{edit_id}")

        col_save, col_cancel = st.columns(2)
        with col_save:
            if st.form_submit_button("💾 Cập nhật", type="primary", use_container_width=True):
                cap_nhat_cv(
                    edit_id, so_hieu=so_hieu.strip(), trich_yeu=trich_yeu.strip(),
                    ngay_ban_hanh=ngay_bh.isoformat(), ngay_nhan=ngay_nhan.isoformat(),
                    loai=loai, co_quan=co_quan.strip(), nguoi_ky=nguoi_ky.strip(),
                    tag=", ".join(tag), noi_dung=noi_dung.strip(), trang_thai=trang_thai,
                    username=username,
                )
                st.session_state.pop("cv_edit_id", None)
                st.toast(f"✅ Đã cập nhật công văn", icon="✏️")
                st.rerun()
        with col_cancel:
            if st.form_submit_button("↩️ Hủy", type="secondary", use_container_width=True):
                st.session_state.pop("cv_edit_id", None)
                st.rerun()


def _huong_dan_onedrive() -> None:
    """Tab hướng dẫn cấu hình và kiểm tra kết nối OneDrive."""

    # ── Trạng thái kết nối ─────────────────────────────────────────────────────
    da_cau_hinh = _kiem_tra_config()
    if da_cau_hinh:
        st.success("✅ **Đã cấu hình credentials** — OneDrive sẵn sàng hoạt động")
    else:
        st.warning("⚠️ **Chưa cấu hình** — File công văn sẽ chỉ lưu local. Làm theo hướng dẫn dưới đây để bật OneDrive.")

    # ── Nút kiểm tra kết nối ──────────────────────────────────────────────────
    if da_cau_hinh:
        if st.button("🔌 Kiểm tra kết nối OneDrive", key="cv_od_test", type="primary"):
            with st.spinner("Đang kết nối..."):
                ket_qua = kiem_tra_ket_noi()
            if ket_qua["ok"]:
                st.success(f"✅ Kết nối thành công!")
                col_a, col_b, col_c = st.columns(3)
                col_a.metric("Drive", ket_qua.get("drive_name", "—"))
                col_b.metric("Chủ sở hữu", ket_qua.get("owner", "—"))
                col_c.metric("Đã dùng", f"{ket_qua.get('quota_used_gb', 0):.1f} / {ket_qua.get('quota_total_gb', 0):.0f} GB")
                if ket_qua.get("drive_url"):
                    st.markdown(f"[🔗 Mở OneDrive]({ket_qua['drive_url']})", unsafe_allow_html=False)
            else:
                st.error(f"❌ Kết nối thất bại: `{ket_qua.get('loi', '')}`")
                st.info("Kiểm tra lại tenant_id, client_id, client_secret trong secrets.toml và đảm bảo đã Grant admin consent.")

    st.divider()

    # ── Hướng dẫn thiết lập ───────────────────────────────────────────────────
    st.markdown("## 📖 Hướng dẫn cấu hình OneDrive")
    st.caption("Thực hiện 1 lần bởi quản trị viên hệ thống. Sau khi cấu hình, file công văn sẽ tự đồng bộ lên OneDrive.")

    # Bước 1
    with st.expander("**Bước 1 — Tạo App Registration trên Azure Portal**", expanded=not da_cau_hinh):
        st.markdown("""
1. Đăng nhập **[https://portal.azure.com](https://portal.azure.com)** bằng tài khoản Microsoft 365 của đơn vị (cần quyền Global Admin hoặc Application Admin)

2. Tìm kiếm **"Microsoft Entra ID"** → chọn mục đó

3. Menu bên trái → **App registrations** → **+ New registration**

4. Điền thông tin:
   - **Name:** `VBSP-SCM OneDrive`
   - **Supported account types:** *Accounts in this organizational directory only*
   - Không cần Redirect URI
   → Nhấn **Register**

5. Sau khi tạo xong, trang **Overview** hiển thị:
   - **Application (client) ID** → copy → điền vào `client_id`
   - **Directory (tenant) ID** → copy → điền vào `tenant_id`
""")
        st.info("💡 Ghi lại 2 giá trị này ngay — sẽ cần ở Bước 5")

    # Bước 2
    with st.expander("**Bước 2 — Tạo Client Secret**", expanded=not da_cau_hinh):
        st.markdown("""
1. Trong app vừa tạo → menu trái → **Certificates & secrets**

2. Tab **Client secrets** → **+ New client secret**

3. Điền:
   - **Description:** `VBSP-SCM`
   - **Expires:** chọn 24 months (hoặc theo chính sách đơn vị)
   → Nhấn **Add**

4. Cột **Value** xuất hiện → **Copy ngay giá trị này** → điền vào `client_secret`

> ⚠️ **Quan trọng:** Giá trị Secret chỉ hiển thị 1 lần duy nhất. Nếu tắt trang rồi mới copy thì phải tạo lại secret mới.
""")

    # Bước 3
    with st.expander("**Bước 3 — Cấp quyền truy cập OneDrive**", expanded=not da_cau_hinh):
        st.markdown("""
1. Menu trái → **API permissions** → **+ Add a permission**

2. Chọn **Microsoft Graph** → **Application permissions**

3. Tìm kiếm `Files` → mở rộng → tích chọn **`Files.ReadWrite.All`**
   → Nhấn **Add permissions**

4. Nhấn **✅ Grant admin consent for [tên tổ chức]** → Confirm

5. Cột Status chuyển sang ✅ *Granted for [tên tổ chức]* là thành công
""")
        st.warning("🔑 Bước Grant admin consent bắt buộc phải do Global Admin thực hiện. Nếu không có quyền, liên hệ IT của đơn vị.")

    # Bước 4
    with st.expander("**Bước 4 — Lấy Drive ID**", expanded=not da_cau_hinh):
        st.markdown("""
Có 2 cách để xác định drive lưu file:

---

#### Cách A — Dùng `user_id` (đơn giản hơn)

Dùng địa chỉ email của người dùng OneDrive làm `user_id`.

**Ví dụ:** `nhanvien@nhcsxh.vn`

> File sẽ được lưu vào OneDrive của người dùng đó, thư mục `VBSP-SCM/CongVan/`

---

#### Cách B — Dùng `drive_id` (chính xác hơn, khuyến nghị)

1. Truy cập **[Graph Explorer](https://developer.microsoft.com/en-us/graph/graph-explorer)** — đăng nhập tài khoản admin

2. Gọi API:
   ```
   GET https://graph.microsoft.com/v1.0/users/{email}/drive
   ```
   Thay `{email}` bằng email người dùng OneDrive

3. Trong kết quả JSON, tìm trường `"id"` ở cấp cao nhất → đây là `drive_id`

**Ví dụ response:**
```json
{
  "id": "b!AbCdEfGh1234...",
  "name": "OneDrive",
  "driveType": "business",
  ...
}
```

→ Copy giá trị `id` → điền vào `drive_id`
""")

    # Bước 5
    with st.expander("**Bước 5 — Cấu hình trong hệ thống**", expanded=not da_cau_hinh):
        st.markdown("""
Mở file **`.streamlit/secrets.toml`** trong thư mục cài đặt hệ thống và điền các giá trị đã thu thập:
""")
        st.code("""[onedrive]
tenant_id     = "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"   # Bước 1
client_id     = "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"   # Bước 1
client_secret = "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"   # Bước 2
drive_id      = "b!AbCdEfGh1234..."                      # Bước 4 cách B (ưu tiên)
user_id       = ""                                       # Bước 4 cách A (nếu không có drive_id)
""", language="toml")
        st.info("📁 File này nằm tại: `D:\\VBSP-SCM\\.streamlit\\secrets.toml`  \nFile đã được thêm vào `.gitignore` — an toàn, không bị commit lên GitHub.")

        st.markdown("""
Sau khi lưu file:
1. **Khởi động lại Streamlit** (Ctrl+C → `streamlit run app.py`)
2. Quay lại tab này → nhấn **"Kiểm tra kết nối OneDrive"**
""")

    st.divider()

    # ── Câu hỏi thường gặp ────────────────────────────────────────────────────
    st.markdown("#### ❓ Câu hỏi thường gặp")
    with st.expander("Nếu OneDrive lỗi thì file công văn có bị mất không?"):
        st.markdown("""
**Không.** File luôn được lưu local trước (`cache/cong_van/`) — OneDrive chỉ là bản sao thêm.
Nếu upload OneDrive thất bại, hệ thống sẽ hiện cảnh báo màu vàng nhưng vẫn lưu công văn thành công vào cơ sở dữ liệu.
""")
    with st.expander("Công văn đã thêm trước khi cấu hình có được đồng bộ lên OneDrive không?"):
        st.markdown("""
**Không tự động.** Các công văn cũ chỉ có file local, không có link OneDrive.
Chỉ công văn **thêm mới sau khi cấu hình** mới được tự động upload OneDrive.
Nếu cần đồng bộ hàng loạt, liên hệ quản trị viên hệ thống để chạy script riêng.
""")
    with st.expander("Link 'Xem file' trong danh sách có bảo mật không?"):
        st.markdown("""
Link được tạo với kiểu **view + scope organization** — chỉ những người có tài khoản Microsoft 365 trong cùng tổ chức mới mở được.
Người ngoài tổ chức (không có tài khoản đăng nhập) **không thể truy cập**.
""")
    with st.expander("Có thể dùng SharePoint thay vì OneDrive cá nhân không?"):
        st.markdown("""
Có. Cần lấy `drive_id` của thư viện tài liệu SharePoint:
```
GET https://graph.microsoft.com/v1.0/sites/{site_id}/drives
```
Tìm drive có `driveType = "documentLibrary"` → lấy `id` → điền vào `drive_id`.
""")


def render(tab: DeltaGenerator | None = None, **kwargs) -> None:
    ctx = TabContext(tab, **kwargs)
    username = ctx.username

    with ctx:
        st.title("📋 Quản lý Công văn")
        st.caption("Tìm kiếm full-text, thêm/sửa/xóa, gắn tag & phân loại công văn đến/đi")

        # ── KPI row ──
        df_loai = thong_ke_cv_theo_loai()
        df_tt = thong_ke_cv_theo_trang_thai()
        tong_cv = df_loai["so_luong"].sum() if not df_loai.empty else 0
        chua_xl = int(df_tt[df_tt["trang_thai"] == "chua_xu_ly"]["so_luong"].sum()) if not df_tt.empty else 0

        c1, c2, c3 = st.columns(3)
        c1.metric("📋 Tổng công văn", tong_cv)
        c2.metric("⏳ Chưa xử lý", chua_xl)

        ds_tre = ds_cv_sap_den_han()
        c3.metric("⚠️ Quá hạn 7 ngày", len(ds_tre))

        # ── Sub-tabs ──
        _od_badge = "🟢" if _kiem_tra_config() else "🔴"
        t1, t2, t3, t4 = st.tabs([
            "🔍 Tìm kiếm & Danh sách",
            "➕ Thêm mới",
            "📤 Xuất Excel",
            f"{_od_badge} OneDrive",
        ])

        with t1:
            st.markdown("#### 🔍 Tìm kiếm công văn")
            col_kw, col_loai, col_tag, col_tt = st.columns(4)
            with col_kw:
                keyword = st.text_input("Từ khóa (số hiệu, trích yếu, nội dung...)", key="cv_kw")
            with col_loai:
                loai_filter = st.selectbox("Loại", ["Tất cả"] + list(LOAI_CONG_VAN.keys()),
                                           format_func=lambda x: "Tất cả" if x == "Tất cả" else LOAI_CONG_VAN.get(x, x), key="cv_f_loai_filter")
            with col_tag:
                tag_filter = st.selectbox("Tag", ["Tất cả"] + TAG_GOP_Y, key="cv_f_tag_filter")
            with col_tt:
                tt_filter = st.selectbox("Trạng thái", ["Tất cả"] + list(TRANG_THAI_CV.keys()),
                                         format_func=lambda x: "Tất cả" if x == "Tất cả" else TRANG_THAI_CV.get(x, x), key="cv_f_tt_filter")

            ds = tim_kiem_cv(
                keyword=keyword,
                loai=None if loai_filter == "Tất cả" else loai_filter,
                tag=None if tag_filter == "Tất cả" else tag_filter,
                trang_thai=None if tt_filter == "Tất cả" else tt_filter,
            )

            # Sửa inline
            if st.session_state.get("cv_edit_id"):
                _form_sua_cv(username)
                st.divider()

            st.caption(f"Tìm thấy **{len(ds)}** công văn")
            _hien_thi_bang_cv(ds, username)

        with t2:
            _form_them_cv(username)

        with t3:
            st.markdown("#### 📤 Xuất danh sách công văn")
            st.caption("Xuất Excel với bộ lọc hiện tại")
            if st.button("📥 Xuất Excel", type="primary", use_container_width=True, key="cv_xuat_excel"):
                try:
                    # keyword/loai_filter/tag_filter/tt_filter luôn được định nghĩa ở t1 (Streamlit chạy cả 3 tab mỗi rerun)
                    data = xuat_danh_sach_cv(
                        keyword=keyword,
                        loai=None if loai_filter == "Tất cả" else loai_filter,
                        tag=None if tag_filter == "Tất cả" else tag_filter,
                        trang_thai=None if tt_filter == "Tất cả" else tt_filter,
                    )
                    st.download_button(
                        "⬇️ Tải Excel",
                        data=data,
                        file_name=f"DanhSach_CongVan_{datetime.now().strftime('%Y%m%d')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True,
                        key="cv_dl_excel",
                    )
                except Exception as e:
                    logger.error("xuat_excel_cv: %s", e, exc_info=True)
                    st.error(f"❌ Lỗi xuất Excel: {e}")

        with t4:
            _huong_dan_onedrive()


__all__ = ["render"]
