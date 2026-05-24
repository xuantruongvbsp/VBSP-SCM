"""Tab CBTD — Quản lý Cán bộ Tín dụng theo ĐGD.

Schema mới (v2):
    cbtd_data[ma_cb] = {
        "ho_ten":     str,
        "pgd":        str,          # PGD trực thuộc (không chéo PGD)
        "ds_dgd":     list[str],    # Tên ĐGD phụ trách (2-4 ĐGD)
        "dien_thoai": str,
        "ghi_chu":    str,
        "ngay_cap":   str,
    }
Thôn/ấp được suy ra động từ dgd_map[pgd][xa][dgd] — không lưu trực tiếp.
"""
from __future__ import annotations

from io import BytesIO
from datetime import datetime
from typing import TYPE_CHECKING

import streamlit as st
import pandas as pd

import db
from config import (
    COT_HINH_THUC_VAY, COT_MA_KH, COT_SO_KU, COT_TEN_THON, COT_TEN_XA,
    COT_TONG_DU_NO, COT_DU_NO_QH, DS_PGD, DON_VI_CHI_NHANH, lay_dgd_cho_pgd,
)
from auth import la_phan_he_cn, la_executive, normalize_role
from state_manager import SCMStateManager
from utils import xuat_excel, hien_thi_dataframe_phan_trang, fmt_so
from data.khtd import doc_cbtd, luu_cbtd, lay_ap_tu_dgd_list, gan_cbtd_vao_df

if TYPE_CHECKING:
    from streamlit.delta_generator import DeltaGenerator

DS_PGD_ALL = [DON_VI_CHI_NHANH] + DS_PGD


def render(tab: DeltaGenerator = None, **kwargs) -> None:
    df       = kwargs.get("df")
    df_full  = kwargs.get("df_full", df)
    role_raw = str(kwargs.get("role", "user") or "user")
    role     = normalize_role(role_raw)
    username = kwargs.get("username", "unknown")
    state = SCMStateManager()

    import streamlit as _st
    ctx = tab if tab is not None else _st.container()

    with ctx:
        st.subheader("👔 Quản lý Cán bộ Tín dụng (CBTD)")
        st.caption("1 CBTD phụ trách 2–4 Điểm giao dịch (ĐGD) trong cùng PGD. "
                   "Thôn/ấp được suy ra tự động từ cấu hình ĐGD.")

        cbtd_data: dict = doc_cbtd()
        dgd_map: dict   = db.doc_dgd_map() or {}

        if not dgd_map:
            st.warning("⚠️ Chưa cấu hình Điểm giao dịch. "
                       "Vào tab **📍 Điểm GD** để cấu hình trước.")

        # ── Dữ liệu tính toán chung ──────────────────────────────────────────
        # Dict (pgd, dgd_name) → (ma_cb, ten_cb) — phát hiện trùng ĐGD
        dgd_da_phan: dict[tuple[str, str], tuple[str, str]] = {}
        for ma_cb, info in cbtd_data.items():
            pgd_cb = info.get("pgd", "")
            for dgd in info.get("ds_dgd", []):
                dgd_da_phan[(pgd_cb, dgd)] = (ma_cb, info.get("ho_ten", ""))

        # ── Helpers ──────────────────────────────────────────────────────────
        def _ds_dgd_cua_pgd(pgd: str) -> list[tuple[str, str]]:
            """[(xa, dgd_name)] — toàn bộ ĐGD trong PGD (từ DGD_DANH_SACH)."""
            dgd_list = lay_dgd_cho_pgd(pgd)
            return [(d["xa"], d["ten"]) for d in dgd_list]

        def _label_dgd(xa: str, dgd_name: str) -> str:
            return f"{xa} — {dgd_name}"

        def _ap_cua_dgd(pgd: str, dgd_name: str) -> list[str]:
            """List ấp của một ĐGD từ dgd_map (schema mới: dict với key 'thon')."""
            for xa, dgd_block in dgd_map.get(pgd, {}).items():
                if isinstance(dgd_block, dict) and dgd_name in dgd_block:
                    entry = dgd_block[dgd_name]
                    if isinstance(entry, dict):
                        thon_list = entry.get("thon", [])
                    elif isinstance(entry, list):
                        thon_list = entry
                    else:
                        thon_list = []
                    return [str(a).strip() for a in thon_list if str(a).strip()]
            return []

        def _so_ap_cbtd(info: dict) -> int:
            pgd = info.get("pgd", "")
            ds_dgd = info.get("ds_dgd", [])
            return len(lay_ap_tu_dgd_list(pgd, ds_dgd, dgd_map))

        def _kiem_tra_trung_dgd(pgd: str, ds_dgd: list[str], bo_qua_ma: str | None = None) -> dict[str, str]:
            """Trả về {dgd_name: 'ma_cb — ten_cb'} cho ĐGD đã bị chiếm."""
            trung = {}
            for dgd_name in ds_dgd:
                found = dgd_da_phan.get((pgd, dgd_name))
                if found and found[0] != bo_qua_ma:
                    trung[dgd_name] = f"{found[0]} — {found[1]}"
            return trung

        def _fmt_tien(x: float) -> str:
            try:
                x = float(x)
                if abs(x) > 0:
                    return f"{x/1_000_000:,.0f}".replace(",","X").replace(".",",").replace("X",".")
                return "—"
            except Exception:
                return "—"

        # ════════════════════════════════════════════════════════════════════
        # 3 SUB-TAB XEM
        # ════════════════════════════════════════════════════════════════════
        xem1, xem2, xem3 = st.tabs([
            "📋 Danh sách CBTD",
            "🗺️ Bản đồ ĐGD → CBTD",
            "🔎 Chi tiết CBTD",
        ])

        # ── SUB-TAB 1: Danh sách ─────────────────────────────────────────────
        with xem1:
            if not cbtd_data:
                st.info("Chưa có CBTD nào. Thêm mới bên dưới.")
            else:
                tong_dgd = sum(len(i.get("ds_dgd", [])) for i in cbtd_data.values())
                tong_ap  = sum(_so_ap_cbtd(i) for i in cbtd_data.values())
                c1, c2, c3 = st.columns(3)
                c1.metric("Số CBTD", len(cbtd_data))
                c2.metric("Tổng ĐGD đã phân", tong_dgd)
                c3.metric("Tổng ấp phụ trách", tong_ap)

                rows = []
                for ma, info in cbtd_data.items():
                    pgd_cb = info.get("pgd", "—")
                    ds_dgd = info.get("ds_dgd", [])
                    so_ap  = _so_ap_cbtd(info)
                    dgd_tom_tat = " | ".join(ds_dgd[:4]) + ("…" if len(ds_dgd) > 4 else "")
                    loai = "✅ Đầy đủ" if ds_dgd and pgd_cb != "—" else "⚠️ Cần cập nhật"
                    rows.append({
                        "Mã CBTD":    ma,
                        "Họ tên":     info.get("ho_ten", ""),
                        "PGD":        pgd_cb,
                        "Điện thoại": info.get("dien_thoai", "") or "—",
                        "Số ĐGD":    len(ds_dgd),
                        "Số ấp":     so_ap,
                        "ĐGD phụ trách": dgd_tom_tat or "—",
                        "Trạng thái": loai,
                        "Cập nhật":  info.get("ngay_cap", ""),
                    })
                hien_thi_dataframe_phan_trang(pd.DataFrame(rows), key="cbtd_ds")

                # ĐGD chưa có CBTD
                tong_dgd_cfg = sum(
                    len(dgd_block)
                    for xa_block in dgd_map.values()
                    for dgd_block in xa_block.values()
                    if isinstance(dgd_block, dict)
                )
                so_chua = tong_dgd_cfg - len(dgd_da_phan)
                if so_chua > 0:
                    with st.expander(f"⚠️ {so_chua} ĐGD chưa có CBTD phụ trách"):
                        for pgd_k, xa_block in dgd_map.items():
                            for xa_k, dgd_block in xa_block.items():
                                if not isinstance(dgd_block, dict):
                                    continue
                                chua = [d for d in dgd_block if (pgd_k, d) not in dgd_da_phan]
                                if chua:
                                    st.caption(f"**{pgd_k} / {xa_k}:** {', '.join(chua)}")

        # ── SUB-TAB 2: Bản đồ ĐGD → CBTD ────────────────────────────────────
        with xem2:
            st.caption("Toàn bộ ĐGD và CBTD phụ trách. Dễ kiểm tra trùng, thiếu.")
            if not dgd_map:
                st.warning("Chưa có cấu hình ĐGD.")
            else:
                pgd_opts = ["Tất cả"] + [p for p in dgd_map if dgd_map[p]]
                loc_pgd = st.selectbox("Lọc theo PGD", pgd_opts, key="bd_pgd")
                loc_tt  = st.selectbox("Tình trạng",
                    ["Tất cả", "✅ Đã phân", "⚠️ Chưa phân"], key="bd_tt")

                rows_bd = []
                for pgd_k, xa_block in dgd_map.items():
                    if loc_pgd != "Tất cả" and pgd_k != loc_pgd:
                        continue
                    for xa_k, dgd_block in xa_block.items():
                        if not isinstance(dgd_block, dict):
                            continue
                        for dgd_name, ap_list in dgd_block.items():
                            assigned = dgd_da_phan.get((pgd_k, dgd_name))
                            tt = "✅ Đã phân" if assigned else "⚠️ Chưa phân"
                            if loc_tt != "Tất cả" and tt != loc_tt:
                                continue
                            rows_bd.append({
                                "PGD":       pgd_k,
                                "Xã":        xa_k,
                                "ĐGD":       dgd_name,
                                "Mã CBTD":   assigned[0] if assigned else "—",
                                "Tên CBTD":  assigned[1] if assigned else "—",
                                "Số ấp":     len(ap_list or []),
                                "Tình trạng": tt,
                            })

                if rows_bd:
                    df_bd = pd.DataFrame(rows_bd)
                    m1, m2 = st.columns(2)
                    m1.metric("Tổng ĐGD", len(df_bd))
                    m2.metric("Chưa phân CBTD", len(df_bd[df_bd["Tình trạng"]=="⚠️ Chưa phân"]))
                    hien_thi_dataframe_phan_trang(df_bd, key="cbtd_bd_dgd", height=420)
                else:
                    st.info("Không có ĐGD nào phù hợp bộ lọc.")

        # ── SUB-TAB 3: Chi tiết từng CBTD ────────────────────────────────────
        with xem3:
            if not cbtd_data:
                st.info("Chưa có CBTD nào.")
            else:
                opts_xem = {
                    ma: f"{ma} — {info['ho_ten']} / {info.get('pgd','?')} "
                        f"({len(info.get('ds_dgd',[]))} ĐGD)"
                    for ma, info in cbtd_data.items()
                }
                chon = st.selectbox("Chọn CBTD", list(opts_xem.keys()),
                                    format_func=lambda k: opts_xem[k],
                                    key="cbtd_chon_xem")
                info_xem = cbtd_data[chon]
                pgd_xem  = info_xem.get("pgd", "")
                ds_dgd_xem = info_xem.get("ds_dgd", [])

                xv1, xv2, xv3 = st.columns(3)
                xv1.markdown(f"👤 **{info_xem['ho_ten']}**")
                xv2.markdown(f"🏢 {pgd_xem or '—'}")
                xv3.markdown(f"📞 {info_xem.get('dien_thoai','') or '—'}")

                if ds_dgd_xem and pgd_xem:
                    with st.expander(f"📍 {len(ds_dgd_xem)} ĐGD phụ trách", expanded=True):
                        for dgd_name in ds_dgd_xem:
                            ap_list = _ap_cua_dgd(pgd_xem, dgd_name)
                            st.caption(
                                f"**{dgd_name}** ({len(ap_list)} ấp)"
                                + (f": {', '.join(ap_list)}" if ap_list else "")
                            )
                else:
                    st.warning("⚠️ CBTD này chưa được gán ĐGD (dữ liệu cũ). "
                               "Dùng **Chỉnh sửa** để cập nhật.")

                # Dữ liệu hồ sơ từ HSTD
                if df is not None and not df.empty and ds_dgd_xem and pgd_xem:
                    df_cb_xem = gan_cbtd_vao_df(df, {chon: info_xem}, dgd_map)
                    df_cb_xem = df_cb_xem[df_cb_xem["CBTD"] == chon].copy()
                    if COT_HINH_THUC_VAY in df_cb_xem.columns:
                        df_cb_xem = df_cb_xem[df_cb_xem[COT_HINH_THUC_VAY] != 1]

                    tdn = df_cb_xem[COT_TONG_DU_NO].sum() if COT_TONG_DU_NO in df_cb_xem.columns else 0
                    dqh = df_cb_xem[COT_DU_NO_QH].sum()   if COT_DU_NO_QH   in df_cb_xem.columns else 0
                    tlqh = (dqh/tdn*100) if tdn > 0 else 0

                    mx1, mx2, mx3, mx4 = st.columns(4)
                    mx1.metric("Số KH",      fmt_so(df_cb_xem[COT_MA_KH].nunique()) if COT_MA_KH in df_cb_xem.columns else "—")
                    mx2.metric("Số món vay", fmt_so(df_cb_xem[COT_SO_KU].nunique()) if COT_SO_KU in df_cb_xem.columns else "—")
                    mx3.metric("Tổng dư nợ (tr.đ)", _fmt_tien(tdn))
                    mx4.metric("Tỷ lệ QH", f"{tlqh:.2f}%",
                               delta="⚠" if tlqh >= 2 else None, delta_color="inverse")

                    if COT_TEN_THON in df_cb_xem.columns and COT_TEN_XA in df_cb_xem.columns:
                        st.markdown("**Tổng hợp theo ấp**")
                        th_ap = df_cb_xem.groupby([COT_TEN_XA, COT_TEN_THON]).agg(
                            Số_KH       =(COT_MA_KH, "nunique"),
                            Tổng_dư_nợ =(COT_TONG_DU_NO, "sum"),
                            Dư_nợ_QH   =(COT_DU_NO_QH, "sum"),
                        ).reset_index().sort_values("Tổng_dư_nợ", ascending=False)
                        th_ap["Tổng dư nợ (tr.đ)"] = th_ap["Tổng_dư_nợ"].apply(_fmt_tien)
                        th_ap["Dư nợ QH (tr.đ)"]   = th_ap["Dư_nợ_QH"].apply(_fmt_tien)
                        th_ap["QH %"] = (th_ap["Dư_nợ_QH"]/th_ap["Tổng_dư_nợ"]*100).fillna(0).round(2)
                        hien_thi_dataframe_phan_trang(
                            th_ap[[COT_TEN_XA, COT_TEN_THON, "Số_KH", "Tổng dư nợ (tr.đ)", "Dư nợ QH (tr.đ)", "QH %"]],
                            key="cbtd_ct_ap",
                        )

                # ── Cross-link: Tổ TK&VV thuộc địa bàn CBTD ─────────────────
                st.markdown("**🏘️ Tổ TK&VV phụ trách**")
                try:
                    from services.cbtd_dia_ban_service import lay_to_theo_cbtd
                    from services.cdtotkvv_service import tong_hop_tu_pgd_data
                    df_cdto_xem = tong_hop_tu_pgd_data()
                    to_map = lay_to_theo_cbtd({chon: info_xem}, dgd_map, df_cdto_xem)
                    tos_cbtd = to_map.get(chon, [])
                    if not tos_cbtd:
                        st.caption("Chưa có dữ liệu Tổ TK&VV khớp với địa bàn CBTD này.")
                    else:
                        df_tos = pd.DataFrame(tos_cbtd)
                        col_hien = [c for c in ["dgd", "ten_xa", "ma_to", "ten_to_truong",
                                                "xep_loai", "tong_diem", "tinh_trang"]
                                    if c in df_tos.columns]
                        rename_tos = {
                            "dgd": "ĐGD", "ten_xa": "Xã", "ma_to": "Mã Tổ",
                            "ten_to_truong": "Tổ trưởng", "xep_loai": "Xếp loại",
                            "tong_diem": "Điểm", "tinh_trang": "Tình trạng",
                        }
                        hien_thi_dataframe_phan_trang(
                            df_tos[col_hien].rename(columns=rename_tos),
                            key="cbtd_ct_to_tkvv",
                        )
                except Exception:
                    st.caption("Chưa có dữ liệu Tổ TK&VV.")

        st.divider()

        # ════════════════════════════════════════════════════════════════════
        # CRUD (admin + manager CN)
        # ════════════════════════════════════════════════════════════════════
        if not la_phan_he_cn(role) or la_executive(role):
            st.caption("Chỉ Quản lý Chi nhánh mới được thêm/sửa/xóa CBTD.")
        else:
            che_do = st.radio("Thao tác",
                ["➕ Thêm mới", "✏️ Chỉnh sửa", "🗑️ Xóa"],
                horizontal=True, key="cbtd_mode")
            st.divider()

            # ── THÊM MỚI ─────────────────────────────────────────────────────
            if che_do == "➕ Thêm mới":
                st.markdown("**➕ Thêm CBTD mới**")
                c1, c2 = st.columns(2)

                with c1:
                    ma_new  = st.text_input("Mã CBTD *", placeholder="vd: CB01", key="cbtd_ma_new")
                    ten_new = st.text_input("Họ và tên *", key="cbtd_ten_new")
                    dt_new  = st.text_input("Số điện thoại", key="cbtd_dt_new")
                    gc_new  = st.text_input("Ghi chú", key="cbtd_gc_new")
                    pgd_new = st.selectbox("PGD trực thuộc *", DS_PGD_ALL, key="cbtd_pgd_new")

                with c2:
                    dgd_opts_new = _ds_dgd_cua_pgd(pgd_new)
                    if not dgd_opts_new:
                        st.warning(f"PGD **{pgd_new}** chưa cấu hình ĐGD.")
                        dgd_sel_new = []
                    else:
                        labels_new = [_label_dgd(xa, d) for xa, d in dgd_opts_new]
                        sel_labels = st.multiselect(
                            "ĐGD phụ trách *",
                            labels_new,
                            help="1 CBTD phụ trách 2–4 ĐGD trong cùng PGD",
                            key="cbtd_dgd_new")
                        dgd_sel_new = [d for xa, d in dgd_opts_new
                                       if _label_dgd(xa, d) in sel_labels]

                        if dgd_sel_new:
                            trung = _kiem_tra_trung_dgd(pgd_new, dgd_sel_new)
                            if trung:
                                for d, cb in trung.items():
                                    st.error(f"⛔ **{d}** đã thuộc CBTD **{cb}**")
                            else:
                                # Preview ấp
                                tong_ap_new = lay_ap_tu_dgd_list(pgd_new, dgd_sel_new, dgd_map)
                                st.success(f"✅ {len(dgd_sel_new)} ĐGD hợp lệ → "
                                           f"{len(tong_ap_new)} ấp/thôn phụ trách")
                                with st.expander("Xem danh sách ấp"):
                                    for xa_p, ap_p in sorted(tong_ap_new):
                                        st.caption(f"• {xa_p} / {ap_p}")
                        else:
                            st.caption("👆 Chọn ít nhất 1 ĐGD")

                if st.button("✅ Thêm CBTD", type="primary", key="btn_them_cbtd"):
                    err = []
                    if not ma_new.strip():   err.append("Thiếu Mã CBTD")
                    if not ten_new.strip():  err.append("Thiếu Họ tên")
                    if not dgd_sel_new:      err.append("Chọn ít nhất 1 ĐGD")
                    if ma_new.strip().upper() in cbtd_data:
                        err.append(f"Mã **{ma_new.strip().upper()}** đã tồn tại")
                    trung_luu = _kiem_tra_trung_dgd(pgd_new, dgd_sel_new)
                    if trung_luu:
                        for d, cb in trung_luu.items():
                            err.append(f"ĐGD **{d}** đã thuộc CBTD **{cb}**")
                    if err:
                        for e in err: st.error(f"❌ {e}")
                    else:
                        ma_key = ma_new.strip().upper()
                        cbtd_data[ma_key] = {
                            "ho_ten":     ten_new.strip(),
                            "pgd":        pgd_new,
                            "ds_dgd":     dgd_sel_new,
                            "dien_thoai": dt_new.strip(),
                            "ghi_chu":    gc_new.strip(),
                            "ngay_cap":   datetime.today().strftime("%d/%m/%Y %H:%M"),
                        }
                        luu_cbtd(cbtd_data)
                        db.ghi_audit(username, "luu_cbtd",
                                     f"Thêm {ma_key} — {ten_new.strip()} "
                                     f"({pgd_new}, {len(dgd_sel_new)} ĐGD)")
                        st.success(f"✅ Đã thêm **{ma_key}** — {ten_new.strip()}")
                        st.rerun()

            # ── CHỈNH SỬA ────────────────────────────────────────────────────
            elif che_do == "✏️ Chỉnh sửa":
                st.markdown("**✏️ Chỉnh sửa CBTD**")
                if not cbtd_data:
                    st.info("Chưa có CBTD nào.")
                else:
                    chon_sua = st.selectbox(
                        "Chọn CBTD",
                        list(cbtd_data.keys()),
                        format_func=lambda k: f"{k} — {cbtd_data[k]['ho_ten']} "
                                              f"/ {cbtd_data[k].get('pgd','?')} "
                                              f"({len(cbtd_data[k].get('ds_dgd',[]))} ĐGD)",
                        key="cbtd_chon_sua")
                    info_cu = cbtd_data[chon_sua]

                    c1, c2 = st.columns(2)
                    with c1:
                        ten_sua = st.text_input("Họ và tên *",
                            value=info_cu.get("ho_ten",""), key="cbtd_ten_sua")
                        dt_sua  = st.text_input("Số điện thoại",
                            value=info_cu.get("dien_thoai",""), key="cbtd_dt_sua")
                        gc_sua  = st.text_input("Ghi chú",
                            value=info_cu.get("ghi_chu",""), key="cbtd_gc_sua")
                        pgd_idx = DS_PGD_ALL.index(info_cu["pgd"]) if info_cu.get("pgd") in DS_PGD_ALL else 0
                        pgd_sua = st.selectbox("PGD trực thuộc *",
                            DS_PGD_ALL, index=pgd_idx, key="cbtd_pgd_sua")

                    with c2:
                        dgd_opts_sua = _ds_dgd_cua_pgd(pgd_sua)
                        if not dgd_opts_sua:
                            st.warning(f"PGD **{pgd_sua}** chưa cấu hình ĐGD.")
                            dgd_sel_sua = []
                        else:
                            labels_sua = [_label_dgd(xa, d) for xa, d in dgd_opts_sua]
                            ds_dgd_cu  = info_cu.get("ds_dgd", []) if pgd_sua == info_cu.get("pgd") else []
                            default_labels = [_label_dgd(xa, d) for xa, d in dgd_opts_sua
                                              if d in ds_dgd_cu]
                            sel_labels_sua = st.multiselect(
                                "ĐGD phụ trách *",
                                labels_sua,
                                default=default_labels,
                                key="cbtd_dgd_sua")
                            dgd_sel_sua = [d for xa, d in dgd_opts_sua
                                           if _label_dgd(xa, d) in sel_labels_sua]

                            if dgd_sel_sua:
                                trung_sua = _kiem_tra_trung_dgd(pgd_sua, dgd_sel_sua, bo_qua_ma=chon_sua)
                                if trung_sua:
                                    for d, cb in trung_sua.items():
                                        st.error(f"⛔ **{d}** đang thuộc CBTD **{cb}**")
                                else:
                                    tong_ap_sua = lay_ap_tu_dgd_list(pgd_sua, dgd_sel_sua, dgd_map)
                                    st.info(f"✅ {len(dgd_sel_sua)} ĐGD → {len(tong_ap_sua)} ấp/thôn")

                    if st.button("💾 Lưu thay đổi", type="primary", key="btn_luu_sua"):
                        if not ten_sua.strip():
                            st.error("❌ Họ tên không được để trống")
                        elif not dgd_sel_sua:
                            st.error("❌ Chọn ít nhất 1 ĐGD")
                        else:
                            trung_luu_sua = _kiem_tra_trung_dgd(pgd_sua, dgd_sel_sua, bo_qua_ma=chon_sua)
                            if trung_luu_sua:
                                for d, cb in trung_luu_sua.items():
                                    st.error(f"❌ ĐGD **{d}** đang thuộc CBTD **{cb}**")
                            else:
                                da_thay = (
                                    ten_sua.strip() != info_cu.get("ho_ten","").strip() or
                                    dt_sua.strip()  != info_cu.get("dien_thoai","").strip() or
                                    gc_sua.strip()  != info_cu.get("ghi_chu","").strip() or
                                    pgd_sua         != info_cu.get("pgd","") or
                                    sorted(dgd_sel_sua) != sorted(info_cu.get("ds_dgd",[]))
                                )
                                if not da_thay:
                                    st.warning("⚠️ Không có gì thay đổi")
                                else:
                                    cbtd_data[chon_sua] = {
                                        "ho_ten":     ten_sua.strip(),
                                        "pgd":        pgd_sua,
                                        "ds_dgd":     dgd_sel_sua,
                                        "dien_thoai": dt_sua.strip(),
                                        "ghi_chu":    gc_sua.strip(),
                                        "ngay_cap":   datetime.today().strftime("%d/%m/%Y %H:%M"),
                                    }
                                    luu_cbtd(cbtd_data)
                                    db.ghi_audit(username, "luu_cbtd",
                                                 f"Sửa {chon_sua} — {pgd_sua}, {len(dgd_sel_sua)} ĐGD")
                                    st.success(f"✅ Đã cập nhật **{chon_sua}**")
                                    st.rerun()

            # ── XÓA ─────────────────────────────────────────────────────────
            elif che_do == "🗑️ Xóa":
                st.markdown("**🗑️ Xóa CBTD**")
                if not cbtd_data:
                    st.info("Chưa có CBTD nào.")
                else:
                    chon_xoa = st.selectbox(
                        "Chọn CBTD",
                        list(cbtd_data.keys()),
                        format_func=lambda k: f"{k} — {cbtd_data[k]['ho_ten']} "
                                              f"/ {cbtd_data[k].get('pgd','?')}",
                        key="cbtd_chon_xoa")
                    info_xoa = cbtd_data[chon_xoa]
                    st.warning(
                        f"⚠️ Sắp xóa: **{chon_xoa}** — {info_xoa['ho_ten']}\n\n"
                        f"PGD: {info_xoa.get('pgd','?')} | "
                        f"ĐGD: {', '.join(info_xoa.get('ds_dgd',[]))}"
                    )
                    xn = st.checkbox("Xác nhận xóa", key="cbtd_xn_xoa")
                    if st.button("🗑️ Xóa", type="primary",
                                 disabled=not xn, key="btn_xoa_cbtd"):
                        del cbtd_data[chon_xoa]
                        luu_cbtd(cbtd_data)
                        db.ghi_audit(username, "luu_cbtd", f"Xóa {chon_xoa}")
                        st.success(f"✅ Đã xóa **{chon_xoa}**")
                        st.rerun()

        st.divider()

        # ════════════════════════════════════════════════════════════════════
        # BÁO CÁO DƯ NỢ THEO CBTD
        # ════════════════════════════════════════════════════════════════════
        cbtd_co_dgd = {ma: info for ma, info in cbtd_data.items()
                       if info.get("pgd") and info.get("ds_dgd")}
        if not cbtd_co_dgd:
            if cbtd_data:
                st.info("ℹ️ Chưa có CBTD nào được gán ĐGD. "
                        "Dùng **Chỉnh sửa** để cập nhật.")
            return

        st.markdown("**📊 Tổng hợp dư nợ theo CBTD**")

        if df is None or df.empty:
            st.warning("Chưa có dữ liệu HSTD.")
            return

        # Join toàn bộ df với cbtd
        df_joined = gan_cbtd_vao_df(df, cbtd_co_dgd, dgd_map)
        if COT_HINH_THUC_VAY in df_joined.columns:
            df_joined = df_joined[df_joined[COT_HINH_THUC_VAY] != 1]

        rows_bc = []
        for ma, info in cbtd_co_dgd.items():
            df_cb = df_joined[df_joined["CBTD"] == ma]
            if df_cb.empty:
                continue
            tdn = df_cb[COT_TONG_DU_NO].sum() if COT_TONG_DU_NO in df_cb.columns else 0
            dqh = df_cb[COT_DU_NO_QH].sum()   if COT_DU_NO_QH   in df_cb.columns else 0
            rows_bc.append({
                "Mã CBTD":       ma,
                "Họ tên":        info["ho_ten"],
                "PGD":           info.get("pgd",""),
                "SĐT":           info.get("dien_thoai",""),
                "Số KH":         fmt_so(df_cb[COT_MA_KH].nunique()) if COT_MA_KH in df_cb.columns else "—",
                "Số món vay":    fmt_so(df_cb[COT_SO_KU].nunique()) if COT_SO_KU in df_cb.columns else "—",
                "Tổng dư nợ":   _fmt_tien(tdn),
                "Dư nợ QH":     _fmt_tien(dqh),
                "Tỷ lệ QH %":   round(dqh/tdn*100, 2) if tdn else 0,
                "Số ĐGD":       len(info.get("ds_dgd",[])),
                "Số ấp":        _so_ap_cbtd(info),
            })

        if not rows_bc:
            st.info("Không có dữ liệu dư nợ cho CBTD nào (kiểm tra lại tên thôn trong ĐGD).")
            return

        hien_thi_dataframe_phan_trang(pd.DataFrame(rows_bc), key="cbtd_bc_tong_hop")

        if st.button("📥 Xuất báo cáo CBTD", key="btn_xuat_cbtd"):
            buf = BytesIO()
            with pd.ExcelWriter(buf, engine="openpyxl") as w:
                pd.DataFrame(rows_bc).to_excel(w, index=False, sheet_name="Tổng hợp CBTD")
                for ma, info in cbtd_co_dgd.items():
                    df_cb2 = df_joined[df_joined["CBTD"] == ma].copy()
                    if not df_cb2.empty:
                        df_cb2.drop(columns=["CBTD","Tên CBTD"], errors="ignore", inplace=True)
                        df_cb2.to_excel(w, index=False, sheet_name=f"CB_{ma}"[:31])
            state.downloads.set(
                "cbtd_excel",
                buf.getvalue(),
                f"BC_CBTD_{datetime.today().strftime('%d%m%Y')}.xlsx",
            )

        if state.downloads.has("cbtd_excel"):
            if st.download_button(
                "⬇ Tải Excel",
                data=state.downloads.get_bytes("cbtd_excel"),
                file_name=state.downloads.get_filename("cbtd_excel") or f"BC_CBTD_{datetime.today().strftime('%d%m%Y')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="dl_cbtd",
            ):
                state.downloads.clear("cbtd_excel")
