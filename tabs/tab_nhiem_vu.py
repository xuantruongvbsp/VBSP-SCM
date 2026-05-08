"""
Tab Quản lý Nhiệm vụ (Tháng / Quý / Năm)
──────────────────────────────────────────
Dành cho:
  - manager / admin : tạo nhiệm vụ, xem danh sách, hậu kiểm duyệt kết quả
  - user (CBTD)     : xem nhiệm vụ được giao, nhập & cập nhật kết quả
"""
import streamlit as st
import db
from datetime import datetime


# ── Ánh xạ nhãn trạng thái ────────────────────────────────────────────────
_NHAN_TRANG_THAI_NV: dict[str, str] = {
    "cho_thuc_hien":  "⏳ Chờ thực hiện",
    "dang_thuc_hien": "🔄 Đang thực hiện",
    "da_hoan_thanh":  "✅ Đã hoàn thành",
}
_NHAN_TRANG_THAI_KQ: dict[str, str] = {
    "cho_duyet":   "⏳ Chờ duyệt",
    "da_duyet":    "✅ Đã duyệt",
    "yeu_cau_sua": "🔁 Yêu cầu sửa",
}
_NHAN_CHU_KY: dict[str, str] = {
    "thang": "Tháng",
    "quy":   "Quý",
    "nam":   "Năm",
}


# ── Hàm tiện ích ──────────────────────────────────────────────────────────
def _tao_ky(chu_ky: str) -> list[str]:
    """Tạo danh sách nhãn kỳ tương ứng với chu kỳ đã chọn."""
    nam = datetime.now().year
    if chu_ky == "thang":
        return [f"{nam}-T{m:02d}" for m in range(1, 13)]
    if chu_ky == "quy":
        return [f"{nam}-Q{q}" for q in range(1, 5)]
    if chu_ky == "nam":
        return [str(y) for y in range(nam - 1, nam + 2)]
    return []


def _ky_mac_dinh(chu_ky: str, ds_ky: list[str]) -> str:
    """Trả về kỳ mặc định phù hợp với tháng / quý hiện tại."""
    if not ds_ky:
        return ""
    thang_hien = datetime.now().month
    if chu_ky == "thang":
        return ds_ky[thang_hien - 1]
    if chu_ky == "quy":
        return ds_ky[(thang_hien - 1) // 3]
    return ds_ky[-1]  # năm hiện tại (phần tử giữa danh sách 3 năm)


def _nhan_nv(ts: str) -> str:
    return _NHAN_TRANG_THAI_NV.get(ts, ts)


def _nhan_kq(ts: str) -> str:
    return _NHAN_TRANG_THAI_KQ.get(ts, ts)


# ── Truy vấn DB ───────────────────────────────────────────────────────────
def _doc_nhiem_vu(chu_ky: str, ky: str, pgd: str | None) -> list[dict]:
    """Đọc danh sách nhiệm vụ theo chu kỳ + kỳ + PGD (NULL = tất cả)."""
    with db.get_conn() as conn:
        if pgd:
            rows = conn.execute(
                """SELECT * FROM nhiem_vu
                   WHERE chu_ky=? AND ky=? AND (pgd=? OR pgd IS NULL)
                   ORDER BY id DESC""",
                (chu_ky, ky, pgd),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM nhiem_vu WHERE chu_ky=? AND ky=? ORDER BY id DESC",
                (chu_ky, ky),
            ).fetchall()
    return [dict(r) for r in rows]


def _doc_ket_qua(nhiem_vu_id: int) -> list[dict]:
    """Đọc tất cả kết quả của một nhiệm vụ."""
    with db.get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM nhiem_vu_ketqua WHERE nhiem_vu_id=? ORDER BY ngay_nhap DESC",
            (nhiem_vu_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def _doc_ket_qua_pgd(nhiem_vu_id: int, pgd: str) -> dict | None:
    """Đọc kết quả của một PGD cụ thể cho một nhiệm vụ."""
    with db.get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM nhiem_vu_ketqua WHERE nhiem_vu_id=? AND pgd=?",
            (nhiem_vu_id, pgd),
        ).fetchone()
    return dict(row) if row else None


def _upsert_ket_qua(
    nhiem_vu_id: int,
    pgd: str,
    noi_dung_th: str | None,
    so_lieu: str | None,
    username: str,
) -> None:
    """Chèn mới hoặc cập nhật kết quả theo (nhiem_vu_id, pgd)."""
    now = datetime.now().isoformat()
    with db.get_conn() as conn:
        conn.execute(
            """INSERT INTO nhiem_vu_ketqua
               (nhiem_vu_id, pgd, noi_dung_th, so_lieu, trang_thai, nguoi_nhap, ngay_nhap)
               VALUES (?, ?, ?, ?, 'cho_duyet', ?, ?)
               ON CONFLICT(nhiem_vu_id, pgd) DO UPDATE SET
                 noi_dung_th = excluded.noi_dung_th,
                 so_lieu     = excluded.so_lieu,
                 trang_thai  = 'cho_duyet',
                 nguoi_nhap  = excluded.nguoi_nhap,
                 ngay_nhap   = excluded.ngay_nhap""",
            (nhiem_vu_id, pgd, noi_dung_th, so_lieu, username, now),
        )
        conn.commit()


# ── Widget lọc chu kỳ / kỳ (dùng chung) ──────────────────────────────────
def _bo_loc_ky(key_prefix: str, hien_pgd: bool = False, ds_pgd: list | None = None):
    """Render bộ lọc chu_ky + ky (+ pgd tuỳ chọn). Trả về (chu_ky, ky, pgd|None)."""
    cols = st.columns(3) if hien_pgd else st.columns(2)

    with cols[0]:
        chu_ky = st.selectbox(
            "Chu kỳ",
            ["thang", "quy", "nam"],
            format_func=lambda x: _NHAN_CHU_KY[x],
            key=f"{key_prefix}_chu_ky",
        )

    ds_ky = _tao_ky(chu_ky)
    ky_default = _ky_mac_dinh(chu_ky, ds_ky)
    idx_default = ds_ky.index(ky_default) if ky_default in ds_ky else 0

    with cols[1]:
        ky = st.selectbox("Kỳ", ds_ky, index=idx_default, key=f"{key_prefix}_ky")

    pgd_chon = None
    if hien_pgd and ds_pgd is not None:
        with cols[2]:
            pgd_sel = st.selectbox(
                "PGD", ["Tất cả PGD"] + ds_pgd, key=f"{key_prefix}_pgd"
            )
        pgd_chon = None if pgd_sel == "Tất cả PGD" else pgd_sel

    return chu_ky, ky, pgd_chon


# ══════════════════════════════════════════════════════════════════════════
# NHÓM MANAGER / ADMIN
# ══════════════════════════════════════════════════════════════════════════

def _render_danh_sach_manager(tab, **kwargs):
    """📥 Danh sách nhiệm vụ — manager / admin xem tổng hợp kết quả từng PGD."""
    ds_pgd_all: list = kwargs.get("ds_pgd_all", [])

    with tab:
        st.subheader("📥 Danh sách nhiệm vụ")
        chu_ky, ky, pgd_loc = _bo_loc_ky("mgr_ds", hien_pgd=True, ds_pgd=ds_pgd_all)

        ds_nv = _doc_nhiem_vu(chu_ky, ky, pgd_loc)

        if not ds_nv:
            st.info("Chưa có nhiệm vụ nào trong kỳ này.")
            return

        st.caption(f"Tổng cộng: **{len(ds_nv)}** nhiệm vụ")
        st.divider()

        for nv in ds_nv:
            pgd_nhan   = nv["pgd"] if nv["pgd"] else "Tất cả PGD"
            deadline   = f" · ⏰ {nv['ngay_deadline']}" if nv.get("ngay_deadline") else ""
            nhan_ts    = _nhan_nv(nv["trang_thai"])

            with st.expander(
                f"**{nv['tieu_de']}** — {nhan_ts} · {pgd_nhan}{deadline}",
                expanded=False,
            ):
                if nv.get("mo_ta"):
                    st.markdown(f"_{nv['mo_ta']}_")
                st.caption(
                    f"Người tạo: **{nv['nguoi_tao']}** · Ngày tạo: {nv['ngay_tao'][:10]}"
                )
                if nv.get("ghi_chu_kh"):
                    st.info(nv["ghi_chu_kh"])

                ds_kq = _doc_ket_qua(nv["id"])
                if ds_kq:
                    st.markdown("**Kết quả các PGD đã nhập:**")
                    for kq in ds_kq:
                        icon = _nhan_kq(kq["trang_thai"])
                        y_kien = f" — _{kq['y_kien_duyet']}_" if kq.get("y_kien_duyet") else ""
                        st.markdown(
                            f"- **{kq['pgd']}** · {icon} · "
                            f"Nội dung: *{kq.get('noi_dung_th') or 'chưa nhập'}* · "
                            f"Số liệu: **{kq.get('so_lieu') or '—'}** · "
                            f"Ngày nhập: {kq['ngay_nhap'][:10]}"
                            + y_kien
                        )
                else:
                    st.info("Chưa có PGD nào nhập kết quả.")


def _render_nhap_moi(tab, **kwargs):
    """➕ Nhập nhiệm vụ mới — manager / admin tạo nhiệm vụ cho PGD."""
    username: str  = kwargs.get("username", "")
    ds_pgd_all: list = kwargs.get("ds_pgd_all", [])

    with tab:
        st.subheader("➕ Nhập nhiệm vụ mới")

        # chu_ky đặt NGOÀI form để kỳ cập nhật động khi người dùng đổi chu kỳ
        chu_ky = st.selectbox(
            "Chu kỳ *",
            ["thang", "quy", "nam"],
            format_func=lambda x: _NHAN_CHU_KY[x],
            key="nhap_moi_chu_ky",
        )
        ds_ky = _tao_ky(chu_ky)
        ky_default = _ky_mac_dinh(chu_ky, ds_ky)

        with st.form("form_nhap_nhiem_vu_moi"):
            tieu_de = st.text_input(
                "Tiêu đề nhiệm vụ *",
                placeholder="Ví dụ: Tổng hợp dư nợ NOXH tháng 4",
            )
            mo_ta = st.text_area(
                "Mô tả chi tiết",
                placeholder="Nêu rõ yêu cầu, nội dung cần thực hiện...",
            )

            c1, c2 = st.columns(2)
            with c1:
                ky = st.selectbox(
                    "Kỳ *",
                    ds_ky,
                    index=ds_ky.index(ky_default) if ky_default in ds_ky else 0,
                    key="nhap_moi_ky",
                )
            with c2:
                pgd_chon = st.selectbox(
                    "Giao cho PGD",
                    ["Tất cả PGD"] + ds_pgd_all,
                    key="nhap_moi_pgd",
                )

            c3, c4 = st.columns(2)
            with c3:
                ngay_deadline = st.date_input(
                    "Ngày deadline", value=None, key="nhap_moi_deadline"
                )
            with c4:
                st.markdown("<br>", unsafe_allow_html=True)

            ghi_chu = st.text_area("Ghi chú kế hoạch (tuỳ chọn)")
            submitted = st.form_submit_button("💾 Lưu nhiệm vụ", type="primary")

        if submitted:
            if not tieu_de.strip():
                st.error("⚠️ Vui lòng nhập tiêu đề nhiệm vụ!")
            else:
                pgd_luu = None if pgd_chon == "Tất cả PGD" else pgd_chon
                deadline_str = str(ngay_deadline) if ngay_deadline else None
                try:
                    with db.get_conn() as conn:
                        conn.execute(
                            """INSERT INTO nhiem_vu
                               (tieu_de, mo_ta, chu_ky, ky, pgd, trang_thai,
                                nguoi_tao, ngay_tao, ngay_deadline, ghi_chu_kh)
                               VALUES (?, ?, ?, ?, ?, 'cho_thuc_hien', ?, ?, ?, ?)""",
                            (
                                tieu_de.strip(),
                                mo_ta.strip() or None,
                                chu_ky, ky,
                                pgd_luu,
                                username,
                                datetime.now().isoformat(),
                                deadline_str,
                                ghi_chu.strip() or None,
                            ),
                        )
                        conn.commit()
                    db.ghi_audit(
                        username, "nhiem_vu_tao",
                        f"Tạo NV: '{tieu_de}' · chu_ky={chu_ky} · ky={ky} · pgd={pgd_luu}",
                    )
                    st.toast(f"✅ Đã tạo nhiệm vụ: {tieu_de}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Lỗi khi lưu nhiệm vụ: {e}")


def _render_hau_kiem(tab, **kwargs):
    """🔍 Hậu kiểm kết quả — manager duyệt hoặc yêu cầu sửa kết quả PGD."""
    username: str    = kwargs.get("username", "")
    ds_pgd_all: list = kwargs.get("ds_pgd_all", [])

    with tab:
        st.subheader("🔍 Hậu kiểm kết quả")
        chu_ky, ky, pgd_loc = _bo_loc_ky("hk", hien_pgd=True, ds_pgd=ds_pgd_all)

        ds_nv = _doc_nhiem_vu(chu_ky, ky, pgd_loc)
        if not ds_nv:
            st.info("Không có nhiệm vụ nào trong kỳ này.")
            return

        co_cho_duyet = False

        for nv in ds_nv:
            ds_kq_cho_duyet = [
                kq for kq in _doc_ket_qua(nv["id"])
                if kq["trang_thai"] == "cho_duyet"
            ]
            if not ds_kq_cho_duyet:
                continue
            co_cho_duyet = True

            with st.expander(
                f"**{nv['tieu_de']}** · {len(ds_kq_cho_duyet)} kết quả chờ duyệt",
                expanded=True,
            ):
                for kq in ds_kq_cho_duyet:
                    st.markdown(f"**PGD: {kq['pgd']}**")
                    st.markdown(
                        f"- Nội dung: *{kq.get('noi_dung_th') or 'chưa nhập'}*\n"
                        f"- Số liệu: **{kq.get('so_lieu') or '—'}**"
                    )
                    st.caption(
                        f"Người nhập: {kq['nguoi_nhap']} · "
                        f"Ngày nhập: {kq['ngay_nhap'][:10]}"
                    )

                    with st.form(key=f"form_duyet_{kq['id']}"):
                        y_kien = st.text_area(
                            "Ý kiến duyệt (tuỳ chọn)",
                            key=f"yk_{kq['id']}",
                            placeholder="Nhập ý kiến hoặc để trống...",
                        )
                        col_d, col_s = st.columns(2)
                        with col_d:
                            btn_duyet = st.form_submit_button("✅ Duyệt", type="primary")
                        with col_s:
                            btn_sua = st.form_submit_button("🔁 Yêu cầu sửa")

                    if btn_duyet or btn_sua:
                        ts_moi = "da_duyet" if btn_duyet else "yeu_cau_sua"
                        try:
                            with db.get_conn() as conn:
                                conn.execute(
                                    """UPDATE nhiem_vu_ketqua SET
                                       trang_thai=?, nguoi_duyet=?,
                                       ngay_duyet=?, y_kien_duyet=?
                                       WHERE id=?""",
                                    (
                                        ts_moi, username,
                                        datetime.now().isoformat(),
                                        y_kien.strip() or None,
                                        kq["id"],
                                    ),
                                )
                                conn.commit()
                            db.ghi_audit(
                                username, f"nhiem_vu_ketqua_{ts_moi}",
                                f"KQ id={kq['id']} · NV '{nv['tieu_de']}' · PGD {kq['pgd']}",
                            )
                            st.toast(f"✅ Đã cập nhật: {_nhan_kq(ts_moi)}")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Lỗi cập nhật: {e}")

                    st.divider()

        if not co_cho_duyet:
            st.success("✅ Không có kết quả nào đang chờ duyệt trong kỳ này.")


# ══════════════════════════════════════════════════════════════════════════
# NHÓM USER (CBTD)
# ══════════════════════════════════════════════════════════════════════════

def _render_nhiem_vu_duoc_giao(tab, **kwargs):
    """📥 Nhiệm vụ được giao — CBTD xem nhiệm vụ và trạng thái kết quả."""
    pgd_user: str = kwargs.get("pgd_user") or ""

    with tab:
        st.subheader("📥 Nhiệm vụ được giao")
        if not pgd_user:
            st.warning("Tài khoản chưa được gán PGD. Liên hệ quản trị viên.")
            return

        chu_ky, ky, _ = _bo_loc_ky("user_ds")
        ds_nv = _doc_nhiem_vu(chu_ky, ky, pgd_user)

        if not ds_nv:
            st.info("Chưa có nhiệm vụ nào được giao trong kỳ này.")
            return

        st.caption(f"Tổng cộng: **{len(ds_nv)}** nhiệm vụ")
        st.divider()

        for nv in ds_nv:
            kq = _doc_ket_qua_pgd(nv["id"], pgd_user)
            ts_kq   = _nhan_kq(kq["trang_thai"]) if kq else "📝 Chưa nhập"
            deadline = f" · ⏰ {nv['ngay_deadline']}" if nv.get("ngay_deadline") else ""

            with st.expander(
                f"**{nv['tieu_de']}** — {ts_kq}{deadline}", expanded=False
            ):
                if nv.get("mo_ta"):
                    st.markdown(f"_{nv['mo_ta']}_")
                st.caption(
                    f"Kỳ: {nv['ky']} · "
                    f"Giao cho: {nv['pgd'] or 'Tất cả PGD'}"
                )

                if kq:
                    st.markdown("**Kết quả đã nhập:**")
                    st.markdown(
                        f"- Nội dung: *{kq.get('noi_dung_th') or 'chưa nhập'}*\n"
                        f"- Số liệu: **{kq.get('so_lieu') or '—'}**\n"
                        f"- Ngày nhập: {kq['ngay_nhap'][:10]}"
                    )
                    if kq.get("y_kien_duyet"):
                        if kq["trang_thai"] == "yeu_cau_sua":
                            st.warning(f"🔁 Ý kiến duyệt: _{kq['y_kien_duyet']}_")
                        else:
                            st.success(f"✅ Ý kiến duyệt: _{kq['y_kien_duyet']}_")
                else:
                    st.info("Chưa nhập kết quả. Vào tab **✏️ Nhập kết quả** để thực hiện.")


def _render_nhap_ket_qua(tab, **kwargs):
    """✏️ Nhập kết quả — CBTD nhập / sửa kết quả thực hiện nhiệm vụ."""
    username: str = kwargs.get("username", "")
    pgd_user: str = kwargs.get("pgd_user") or ""

    with tab:
        st.subheader("✏️ Nhập kết quả nhiệm vụ")
        if not pgd_user:
            st.warning("Tài khoản chưa được gán PGD. Liên hệ quản trị viên.")
            return

        chu_ky, ky, _ = _bo_loc_ky("user_nkq")
        ds_nv = _doc_nhiem_vu(chu_ky, ky, pgd_user)

        if not ds_nv:
            st.info("Chưa có nhiệm vụ nào được giao trong kỳ này.")
            return

        for nv in ds_nv:
            nv_id = nv["id"]
            kq    = _doc_ket_qua_pgd(nv_id, pgd_user)
            ts_hien = kq["trang_thai"] if kq else None

            with st.expander(
                f"**{nv['tieu_de']}** — {_nhan_kq(ts_hien) if ts_hien else '📝 Chưa nhập'}",
                expanded=(ts_hien == "yeu_cau_sua"),
            ):
                if nv.get("mo_ta"):
                    st.markdown(f"_{nv['mo_ta']}_")

                # Đã duyệt → chỉ đọc
                if ts_hien == "da_duyet":
                    st.success("✅ Kết quả đã được duyệt — không thể chỉnh sửa.")
                    st.markdown(
                        f"- Nội dung: *{kq.get('noi_dung_th') or '—'}*\n"
                        f"- Số liệu: **{kq.get('so_lieu') or '—'}**"
                    )
                else:
                    # Yêu cầu sửa → hiển thị cảnh báo trước khi cho nhập lại
                    if ts_hien == "yeu_cau_sua":
                        st.warning(
                            f"🔁 **Yêu cầu sửa:** "
                            f"_{kq.get('y_kien_duyet') or 'Không có ý kiến cụ thể'}_"
                        )

                    val_noi_dung = kq.get("noi_dung_th") or "" if kq else ""
                    val_so_lieu  = kq.get("so_lieu") or "" if kq else ""

                    with st.form(key=f"form_{nv_id}"):
                        noi_dung_th = st.text_area(
                            "Nội dung đã thực hiện",
                            value=val_noi_dung,
                        )
                        so_lieu = st.text_input(
                            "Số liệu kết quả",
                            value=val_so_lieu,
                            placeholder="Ví dụ: 1,250 triệu đồng / 45 hộ",
                        )
                        submitted = st.form_submit_button(
                            "💾 Lưu kết quả", type="primary"
                        )

                    if submitted:
                        try:
                            _upsert_ket_qua(
                                nv_id, pgd_user,
                                noi_dung_th.strip() or None,
                                so_lieu.strip() or None,
                                username,
                            )
                            db.ghi_audit(
                                username, "nhiem_vu_nhap_ketqua",
                                f"NV id={nv_id} '{nv['tieu_de']}' · PGD {pgd_user}",
                            )
                            st.toast("✅ Đã lưu kết quả — đang chờ duyệt.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Lỗi khi lưu kết quả: {e}")


# ══════════════════════════════════════════════════════════════════════════
# HÀM RENDER CHÍNH
# ══════════════════════════════════════════════════════════════════════════

def render(tab, **kwargs):
    """Render tab Quản lý Nhiệm vụ — phân nhánh theo role."""
    role: str = kwargs.get("role", "user")

    with tab:
        if role in ("admin", "manager", "admin_cn", "manager_cn"):
            t1, t2, t3 = st.tabs([
                "📥 Danh sách nhiệm vụ",
                "➕ Nhập nhiệm vụ mới",
                "🔍 Hậu kiểm kết quả",
            ])
            _render_danh_sach_manager(t1, **kwargs)
            _render_nhap_moi(t2, **kwargs)
            _render_hau_kiem(t3, **kwargs)
        else:
            t1, t2 = st.tabs([
                "📥 Nhiệm vụ được giao",
                "✏️ Nhập kết quả",
            ])
            _render_nhiem_vu_duoc_giao(t1, **kwargs)
            _render_nhap_ket_qua(t2, **kwargs)
