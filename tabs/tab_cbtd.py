"""Tab CBTD — Quản lý Cán bộ Tín dụng."""
from __future__ import annotations

from io import BytesIO
from datetime import datetime, date
from typing import TYPE_CHECKING, Any

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from config import *
from auth import la_phan_he_cn
from utils import xuat_excel, ten_file_xuat, hien_thi_dataframe_phan_trang
from data import doc_cbtd, luu_cbtd

if TYPE_CHECKING:
    from streamlit.delta_generator import DeltaGenerator


def render(tab: DeltaGenerator, **kwargs: dict) -> None:
    """
    Render tab Quản lý Cán bộ Tín dụng (CBTD).
    
    Args:
        tab: Streamlit DeltaGenerator cho tab này
        **kwargs: Chứa df, df_full, role, pgd_user, username, df_nq11
    """
    df = kwargs.get("df")
    df_full = kwargs.get("df_full", df)
    role = kwargs.get("role")
    pgd_user = kwargs.get("pgd_user")
    username = kwargs.get("username")
    df_nq11 = kwargs.get("df_nq11")

    if tab is not None:
        _ctx = tab
    else:
        _ctx = st.container()
    with _ctx:
        st.subheader("👔 Quản lý Cán bộ Tín dụng (CBTD)")
        st.caption("Phân CBTD theo ấp/thôn. Mã CBTD là khóa chính. 1 CBTD có thể phụ trách nhiều ấp.")

        cbtd_data = doc_cbtd()

        # ── Lấy danh sách ấp từ HSTD — giữ tất cả 86 ấp ──
        if "Mã thôn" in df.columns and "Tên thôn" in df.columns and "Tên xã" in df.columns:
            dm_ap = (df[["Mã thôn","Tên thôn","Tên xã"]]
                     .drop_duplicates()
                     .dropna(subset=["Mã thôn","Tên thôn","Tên xã"])
                     .sort_values(["Tên xã","Mã thôn"])
                     .reset_index(drop=True))
            dm_ap["Mã thôn"] = dm_ap["Mã thôn"].astype(int).astype(str)
            # Nhãn hiển thị: "Xã — Tên ấp"
            dm_ap["Nhãn"] = dm_ap["Tên xã"] + " — " + dm_ap["Tên thôn"]
            # Dict: mã thôn → nhãn
            ma_to_nhan = dict(zip(dm_ap["Mã thôn"], dm_ap["Nhãn"]))
            # Nhóm theo xã để hiển thị dễ chọn
            ds_ap_options = dm_ap["Nhãn"].tolist()
            ds_xa_list    = sorted(dm_ap["Tên xã"].unique().tolist())
        else:
            dm_ap = pd.DataFrame(columns=["Mã thôn","Tên thôn","Tên xã","Nhãn"])
            ds_ap_options = []
            ds_xa_list    = []
            ma_to_nhan    = {}

        # Helper: mã thôn → nhãn và ngược lại
        nhan_to_ma = {v:k for k,v in ma_to_nhan.items()}

        def nhan_list(ma_list):
            """Chuyển list mã thôn → list nhãn"""
            return [ma_to_nhan.get(str(m), str(m)) for m in ma_list]

        def ma_list(nhan_l):
            """Chuyển list nhãn → list mã thôn"""
            return [nhan_to_ma.get(n, n) for n in nhan_l]

        # ══════════════════════════════════════════
        # PHẦN XEM & TRA CỨU — 3 sub-tab
        # ══════════════════════════════════════════
        xem_tab1, xem_tab2, xem_tab3 = st.tabs([
            "📋 Danh sách CBTD", "🗺️ Bản đồ ấp → CBTD", "🔎 Xem chi tiết CBTD"
        ])

        # Tính toán chung dùng cho cả 3 tab
        ap_da_phan = set(
            str(m) for info in cbtd_data.values() for m in info.get("ds_thon",[])
        )
        # Dict ngược: mã thôn → mã CBTD phụ trách
        ap_to_cbtd = {}
        for ma_cb, info_cb in cbtd_data.items():
            for m in info_cb.get("ds_thon",[]):
                ap_to_cbtd[str(m)] = (ma_cb, info_cb.get("ho_ten",""))

        # ── SUB-TAB 1: Danh sách CBTD ──
        with xem_tab1:
            if not cbtd_data:
                st.info("Chưa có CBTD nào. Nhập mới bên dưới.")
            else:
                # Metrics tóm tắt
                c1,c2,c3 = st.columns(3)
                c1.metric("Số CBTD", len(cbtd_data))
                c2.metric("Ấp đã phân công", len(ap_da_phan))
                c3.metric("Ấp chưa phân công",
                          len(dm_ap) - len(ap_da_phan),
                          delta="⚠️ Còn sót" if len(dm_ap) - len(ap_da_phan) > 0 else None,
                          delta_color="inverse")

                # Bảng danh sách
                rows_list = []
                for ma, info in cbtd_data.items():
                    ap_nhan = nhan_list(info.get("ds_thon",[]))
                    # Nhóm ấp theo xã cho gọn
                    theo_xa = {}
                    for n in ap_nhan:
                        xa = n.split(" — ")[0] if " — " in n else "?"
                        theo_xa.setdefault(xa, []).append(n.split(" — ")[-1])
                    ap_tom_tat = " | ".join(
                        f"{xa}({len(aps)}): {', '.join(aps[:3])}{'…' if len(aps)>3 else ''}"
                        for xa, aps in theo_xa.items()
                    )
                    rows_list.append({
                        "Mã CBTD":       ma,
                        "Họ tên":        info.get("ho_ten",""),
                        "Điện thoại":    info.get("dien_thoai","") or "—",
                        "Số ấp":         len(info.get("ds_thon",[])),
                        "Ấp phụ trách":  ap_tom_tat,
                        "Ghi chú":       info.get("ghi_chu","") or "—",
                        "Cập nhật":      info.get("ngay_cap",""),
                    })
                hien_thi_dataframe_phan_trang(
                    pd.DataFrame(rows_list),
                    key="cbtd_ds_ap_phan_cong",
                )

                # Cảnh báo ấp chưa phân công
                chua_phan_ds = dm_ap[~dm_ap["Mã thôn"].isin(ap_da_phan)]
                if not chua_phan_ds.empty:
                    with st.expander(f"⚠️ {len(chua_phan_ds)} ấp chưa có CBTD phụ trách"):
                        theo_xa_cp = {}
                        for _, row_cp in chua_phan_ds.iterrows():
                            theo_xa_cp.setdefault(row_cp["Tên xã"], []).append(row_cp["Tên thôn"])
                        for xa_cp, aps_cp in sorted(theo_xa_cp.items()):
                            st.caption(f"**{xa_cp}** ({len(aps_cp)}): {', '.join(aps_cp)}")

        # ── SUB-TAB 2: Bản đồ ấp → CBTD ──
        with xem_tab2:
            st.caption("Toàn bộ ấp/thôn và CBTD phụ trách. Dễ kiểm tra trùng, thiếu.")

            if dm_ap.empty:
                st.warning("Không có dữ liệu ấp/thôn trong file HSTD.")
            else:
                # Bộ lọc
                bf1, bf2 = st.columns([2,1])
                with bf1:
                    loc_xa_bd = st.selectbox("Lọc theo xã",
                        ["Tất cả"] + ds_xa_list, key="bd_xa")
                with bf2:
                    loc_trang_thai = st.selectbox("Tình trạng phân công",
                        ["Tất cả","✅ Đã phân công","⚠️ Chưa phân công"], key="bd_tt")

                # Build bảng đầy đủ
                rows_bd = []
                for _, row_ap in dm_ap.iterrows():
                    ma_thon = str(row_ap["Mã thôn"])
                    co_cbtd = ma_thon in ap_da_phan
                    if ma_thon in ap_to_cbtd:
                        ma_cb_ap, ten_cb_ap = ap_to_cbtd[ma_thon]
                    else:
                        ma_cb_ap, ten_cb_ap = "—", "—"
                    rows_bd.append({
                        "Xã":              row_ap["Tên xã"],
                        "Ấp/Thôn":         row_ap["Tên thôn"],
                        "Mã thôn":         ma_thon,
                        "Mã CBTD":         ma_cb_ap,
                        "Tên CBTD":        ten_cb_ap,
                        "Tình trạng":      "✅ Đã phân" if co_cbtd else "⚠️ Chưa phân",
                    })

                df_bd = pd.DataFrame(rows_bd)

                # Áp lọc
                if loc_xa_bd != "Tất cả":
                    df_bd = df_bd[df_bd["Xã"] == loc_xa_bd]
                if loc_trang_thai == "✅ Đã phân công":
                    df_bd = df_bd[df_bd["Tình trạng"] == "✅ Đã phân"]
                elif loc_trang_thai == "⚠️ Chưa phân công":
                    df_bd = df_bd[df_bd["Tình trạng"] == "⚠️ Chưa phân"]

                # Metrics sau lọc
                m1, m2 = st.columns(2)
                m1.metric("Tổng ấp hiển thị", len(df_bd))
                m2.metric("Chưa phân công", len(df_bd[df_bd["Tình trạng"]=="⚠️ Chưa phân"]))

                hien_thi_dataframe_phan_trang(
                    df_bd.reset_index(drop=True),
                    key="cbtd_bien_dong",
                    height=420,
                )

                # Kiểm tra trùng ấp (ấp bị khai báo ở 2 CBTD)
                kiem_tra_trung_all = {}
                for ma_cb_t, info_cb_t in cbtd_data.items():
                    for m_t in info_cb_t.get("ds_thon",[]):
                        m_t = str(m_t)
                        if m_t not in kiem_tra_trung_all:
                            kiem_tra_trung_all[m_t] = []
                        kiem_tra_trung_all[m_t].append(ma_cb_t)
                trung_ap_list = {m: cbs for m, cbs in kiem_tra_trung_all.items() if len(cbs) > 1}
                if trung_ap_list:
                    st.error(f"⛔ Phát hiện **{len(trung_ap_list)} ấp bị trùng** — cần sửa ngay!")
                    trung_rows = []
                    for m_t, cbs_t in trung_ap_list.items():
                        nhan_t = ma_to_nhan.get(m_t, m_t)
                        trung_rows.append({
                            "Ấp/Thôn": nhan_t,
                            "Mã thôn": m_t,
                            "CBTD đang giữ": " & ".join(
                                f"{cb} ({cbtd_data[cb]['ho_ten']})" for cb in cbs_t if cb in cbtd_data
                            ),
                        })
                    hien_thi_dataframe_phan_trang(
                        pd.DataFrame(trung_rows),
                        key="cbtd_ap_trung",
                    )
                else:
                    st.success("✅ Không có ấp nào bị trùng CBTD")

        # ── SUB-TAB 3: Xem chi tiết từng CBTD ──
        with xem_tab3:
            if not cbtd_data:
                st.info("Chưa có CBTD nào.")
            else:
                chon_xem = st.selectbox("Chọn CBTD để xem chi tiết",
                    list(cbtd_data.keys()),
                    format_func=lambda k: f"{k} — {cbtd_data[k]['ho_ten']} ({len(cbtd_data[k].get('ds_thon',[]))} ấp)",
                    key="cbtd_chon_xem")
                info_xem = cbtd_data[chon_xem]
                ds_ma_xem = [str(m) for m in info_xem.get("ds_thon",[])]
                ap_nhan_xem = nhan_list(ds_ma_xem)

                xv1, xv2, xv3 = st.columns(3)
                xv1.markdown(f"👤 **{info_xem['ho_ten']}**")
                xv2.markdown(f"📞 {info_xem.get('dien_thoai','—') or '—'}")
                xv3.markdown(f"🗒️ {info_xem.get('ghi_chu','') or '—'}")

                # Danh sách ấp phân theo xã
                ap_theo_xa_xem = {}
                for n in ap_nhan_xem:
                    xa = n.split(" — ")[0] if " — " in n else "?"
                    ap_theo_xa_xem.setdefault(xa, []).append(n.split(" — ")[-1])
                with st.expander(f"📍 {len(ap_nhan_xem)} ấp phụ trách", expanded=True):
                    for xa_x, aps_x in sorted(ap_theo_xa_xem.items()):
                        st.caption(f"**{xa_x}** ({len(aps_x)}): {', '.join(aps_x)}")

                # Dữ liệu hồ sơ
                if "Mã thôn" in df.columns and ds_ma_xem:
                    mask_xem = df["Mã thôn"].astype(str).isin(ds_ma_xem)
                    df_xem = df[mask_xem].copy()
                    if "Hình thức vay" in df_xem.columns:
                        df_xem = df_xem[df_xem["Hình thức vay"] != 1]
                    tdn_xem = df_xem[COT_TONG_DU_NO].sum() if COT_TONG_DU_NO in df_xem.columns else 0
                    dqh_xem = df_xem[COT_DU_NO_QH].sum()   if COT_DU_NO_QH   in df_xem.columns else 0
                    tlqh_xem = (dqh_xem/tdn_xem*100) if tdn_xem > 0 else 0

                    mx1,mx2,mx3,mx4 = st.columns(4)
                    mx1.metric("Số KH",      f"{df_xem[COT_MA_KH].nunique():,}".replace(",","."))
                    mx2.metric("Số món vay", f"{df_xem[COT_SO_KU].nunique():,}".replace(",","."))
                    mx3.metric("Tổng dư nợ",
                        f"{tdn_xem/1e9:.3f} tỷ".replace(".",",") if tdn_xem >= 1e9
                        else f"{tdn_xem/1e6:.1f} triệu".replace(".",","))
                    mx4.metric("Tỷ lệ QH", f"{tlqh_xem:.2f}%",
                        delta="⚠" if tlqh_xem >= 2 else None, delta_color="inverse")

                    # Bảng tổng hợp theo ấp
                    if "Tên thôn" in df_xem.columns:
                        st.markdown("**Tổng hợp theo ấp**")
                        th_ap = df_xem.groupby(["Mã thôn","Tên thôn"]).agg(
                            Số_KH      =(COT_MA_KH, "nunique"),
                            Số_món_vay =(COT_SO_KU, "nunique"),
                            Tổng_dư_nợ =(COT_TONG_DU_NO, "sum"),
                            Dư_nợ_QH   =(COT_DU_NO_QH, "sum"),
                        ).reset_index().sort_values("Tổng_dư_nợ", ascending=False)
                        th_ap["Mã thôn"] = th_ap["Mã thôn"].astype(str)
                        th_ap["Tổng dư nợ"] = th_ap["Tổng_dư_nợ"].apply(
                            lambda x: f"{x/1e9:.3f} tỷ".replace(".",",") if x >= 1e9
                            else f"{x/1e6:.1f} tr".replace(".",","))
                        th_ap["Dư nợ QH"] = th_ap["Dư_nợ_QH"].apply(
                            lambda x: f"{x/1e6:.1f} triệu".replace(".",",") if x > 0 else "—")
                        th_ap["QH%"] = (th_ap["Dư_nợ_QH"]/th_ap["Tổng_dư_nợ"]*100).fillna(0).round(2)
                        hien_thi_dataframe_phan_trang(
                            th_ap[["Mã thôn","Tên thôn","Số_KH","Số_món_vay","Tổng dư nợ","Dư nợ QH","QH%"]],
                            key="cbtd_chi_tiet_ap",
                        )

        st.divider()

        # ── Helper: tìm ấp trùng với CBTD khác ──
        def kiem_tra_trung_ap(ap_nhan_chon: list[str], bo_qua_ma: str | None = None) -> dict[str, str]:
            """
            Trả về dict {nhãn_ấp: mã_CBTD} cho các ấp đã bị chiếm.
            
            Args:
                ap_nhan_chon: Danh sách nhãn ấp cần kiểm tra
                bo_qua_ma: Mã CBTD bỏ qua (khi chỉnh sửa)
            
            Returns:
                Dict ấp trùng → thông tin CBTD đang giữ
            """
            trung = {}
            for ma, info in cbtd_data.items():
                if ma == bo_qua_ma: continue
                for m in info.get("ds_thon",[]):
                    nhan = ma_to_nhan.get(str(m), str(m))
                    if nhan in ap_nhan_chon:
                        trung[nhan] = f"{ma} — {info['ho_ten']}"
            return trung

        # ── Thao tác (admin + manager) ──
        if not la_phan_he_cn(role) or role == "executive":
            st.caption("Chỉ Quản lý trở lên mới được quản lý CBTD.")
        else:
            che_do = st.radio("Thao tác",
                ["➕ Thêm mới","✏️ Chỉnh sửa","🗑️ Xóa"],
                horizontal=True, key="cbtd_mode")
            st.divider()

            # ══ THÊM MỚI ══
            if che_do == "➕ Thêm mới":
                st.markdown("**➕ Thêm CBTD mới**")
                c1, c2 = st.columns(2)
                with c1:
                    ma_new  = st.text_input("Mã CBTD *",
                        placeholder="vd: CB01",
                        help="Mã duy nhất — không được trùng",
                        key="cbtd_ma_new")
                    ten_new = st.text_input("Họ và tên *",
                        placeholder="vd: Nguyễn Văn A",
                        key="cbtd_ten_new")
                    dt_new  = st.text_input("Số điện thoại",
                        key="cbtd_dt_new")
                    gc_new  = st.text_input("Ghi chú",
                        key="cbtd_gc_new")
                with c2:
                    # Lọc theo xã trước để dễ chọn ấp
                    loc_xa_new = st.selectbox("Lọc theo xã",
                        ["Tất cả"] + ds_xa_list,
                        key="cbtd_loc_xa_new")
                    opts_new = ds_ap_options if loc_xa_new == "Tất cả" else \
                               dm_ap[dm_ap["Tên xã"]==loc_xa_new]["Nhãn"].tolist()

                    ap_new = st.multiselect(
                        "Ấp/thôn phụ trách *",
                        opts_new,
                        help="Có thể chọn nhiều ấp, kể cả khác xã",
                        key="cbtd_ap_new")

                    if ap_new:
                        # Kiểm tra trùng real-time
                        trung_new = kiem_tra_trung_ap(ap_new)
                        if trung_new:
                            for ap_t, cb_t in trung_new.items():
                                st.error(f"⛔ **{ap_t}** đã thuộc CBTD **{cb_t}**")
                        else:
                            st.success(f"✅ **{len(ap_new)}** ấp hợp lệ, chưa có CBTD nào phụ trách")
                    else:
                        st.caption("👆 Chọn ít nhất 1 ấp")

                if st.button("✅ Thêm CBTD", type="primary",
                             use_container_width=True, key="btn_them_cbtd"):
                    err = []
                    if not ma_new.strip():  err.append("Thiếu Mã CBTD")
                    if not ten_new.strip(): err.append("Thiếu Họ tên")
                    if not ap_new:          err.append("Chọn ít nhất 1 ấp")
                    if ma_new.strip().upper() in cbtd_data:
                        err.append(f"Mã **{ma_new.strip().upper()}** đã tồn tại")
                    # Kiểm tra trùng ấp khi bấm lưu
                    trung_new_luu = kiem_tra_trung_ap(ap_new)
                    if trung_new_luu:
                        for ap_t, cb_t in trung_new_luu.items():
                            err.append(f"Ấp **{ap_t}** đã thuộc CBTD **{cb_t}** — bỏ bớt hoặc chuyển ấp đó sang CBTD này bằng cách sửa CBTD kia trước")
                    if err:
                        for e in err: st.error(f"❌ {e}")
                    else:
                        cbtd_data[ma_new.strip().upper()] = {
                            "ho_ten":     ten_new.strip(),
                            "dien_thoai": dt_new.strip(),
                            "ds_thon":    ma_list(ap_new),   # lưu mã thôn
                            "ghi_chu":    gc_new.strip(),
                            "ngay_cap":   datetime.today().strftime("%d/%m/%Y %H:%M"),
                        }
                        luu_cbtd(cbtd_data)
                        st.success(f"✅ Đã thêm **{ma_new.strip().upper()}** — {ten_new.strip()} ({len(ap_new)} ấp)")
                        st.rerun()

            # ══ CHỈNH SỬA ══
            elif che_do == "✏️ Chỉnh sửa":
                st.markdown("**✏️ Chỉnh sửa CBTD**")
                if not cbtd_data:
                    st.info("Chưa có CBTD nào.")
                else:
                    chon_sua = st.selectbox("Chọn CBTD",
                        list(cbtd_data.keys()),
                        format_func=lambda k: f"{k} — {cbtd_data[k]['ho_ten']} ({len(cbtd_data[k].get('ds_thon',[]))} ấp)",
                        key="cbtd_chon_sua")
                    info_cu = cbtd_data[chon_sua]
                    ap_cu_nhan  = nhan_list(info_cu.get("ds_thon",[]))
                    ap_cu_valid = [n for n in ap_cu_nhan if n in ds_ap_options]

                    c1, c2 = st.columns(2)
                    with c1:
                        ten_sua = st.text_input("Họ và tên *",
                            value=info_cu.get("ho_ten",""), key="cbtd_ten_sua")
                        dt_sua  = st.text_input("Số điện thoại",
                            value=info_cu.get("dien_thoai",""), key="cbtd_dt_sua")
                        gc_sua  = st.text_input("Ghi chú",
                            value=info_cu.get("ghi_chu",""), key="cbtd_gc_sua")
                        if ap_cu_valid:
                            ap_theo_xa_cu = {}
                            for n in ap_cu_valid:
                                xa = n.split(" — ")[0] if " — " in n else "Khac"
                                ap_theo_xa_cu.setdefault(xa,[]).append(n.split(" — ")[-1])
                            st.caption("**Ấp hiện tại:**")
                            for xa, aps in ap_theo_xa_cu.items():
                                st.caption(f"- **{xa}** ({len(aps)}): {chr(44).join(aps)}")

                    with c2:
                        st.markdown("**Chỉnh sửa ấp phụ trách**")
                        st.caption("💡 Lọc theo xã để dễ chọn. Ấp xã khác vẫn được giữ lại.")
                        loc_xa_sua = st.selectbox("Lọc theo xã",
                            ["Tất cả"] + ds_xa_list, key="cbtd_loc_xa_sua")
                        opts_sua = ds_ap_options if loc_xa_sua == "Tất cả" else \
                                   dm_ap[dm_ap["Tên xã"]==loc_xa_sua]["Nhãn"].tolist()
                        default_sua = [a for a in ap_cu_valid if a in opts_sua]
                        ap_xa_dang_loc = st.multiselect(
                            f"Ấp {'tất cả xã' if loc_xa_sua=='Tất cả' else loc_xa_sua}",
                            opts_sua, default=default_sua, key="cbtd_ap_sua")
                        ap_xa_khac  = [a for a in ap_cu_valid if a not in opts_sua]
                        ap_tong_hop = sorted(set(ap_xa_khac + ap_xa_dang_loc))
                        if ap_tong_hop:
                            ap_theo_xa_moi = {}
                            for n in ap_tong_hop:
                                xa = n.split(" — ")[0] if " — " in n else "Khac"
                                ap_theo_xa_moi.setdefault(xa,[]).append(n.split(" — ")[-1])
                            tong_txt = " | ".join(
                                f"{xa}({len(aps)}): {chr(44).join(aps)}"
                                for xa, aps in ap_theo_xa_moi.items())
                            st.info(f"Tổng sẽ lưu ({len(ap_tong_hop)} ấp): {tong_txt}")
                            # Kiểm tra trùng real-time khi chỉnh sửa (bỏ qua chính CBTD đang sửa)
                            trung_sua = kiem_tra_trung_ap(ap_tong_hop, bo_qua_ma=chon_sua)
                            if trung_sua:
                                for ap_t, cb_t in trung_sua.items():
                                    st.error(f"⛔ **{ap_t}** đang thuộc CBTD **{cb_t}**")

                    if st.button("💾 Lưu thay đổi", type="primary",
                                 use_container_width=True, key="btn_luu_sua"):
                        if not ten_sua.strip():
                            st.error("❌ Họ tên không được để trống")
                        elif not ap_tong_hop:
                            st.error("❌ Chọn ít nhất 1 ấp")
                        else:
                            # Chặn lưu nếu có ấp trùng
                            trung_sua_luu = kiem_tra_trung_ap(ap_tong_hop, bo_qua_ma=chon_sua)
                            thay_doi = False
                            if trung_sua_luu:
                                for ap_t, cb_t in trung_sua_luu.items():
                                    st.error(f"❌ Ấp **{ap_t}** đang thuộc CBTD **{cb_t}** — cần bỏ ấp này hoặc sửa CBTD kia trước")
                            else:
                                ma_moi = sorted(ma_list(ap_tong_hop))
                                ma_cu  = sorted([str(m) for m in info_cu.get("ds_thon",[])])
                                thay_doi = (
                                    ten_sua.strip()  != info_cu.get("ho_ten","").strip()     or
                                    dt_sua.strip()   != info_cu.get("dien_thoai","").strip() or
                                    gc_sua.strip()   != info_cu.get("ghi_chu","").strip()    or
                                    ma_moi           != ma_cu
                                )
                                if not thay_doi:
                                    st.warning("⚠️ Không có dữ liệu gì thay đổi")
                            if not trung_sua_luu and thay_doi:
                                cbtd_data[chon_sua] = {
                                    "ho_ten":     ten_sua.strip(),
                                    "dien_thoai": dt_sua.strip(),
                                    "ds_thon":    ma_list(ap_tong_hop),
                                    "ghi_chu":    gc_sua.strip(),
                                    "ngay_cap":   datetime.today().strftime("%d/%m/%Y %H:%M"),
                                }
                                luu_cbtd(cbtd_data)
                                st.success(f"✅ Đã cập nhật **{chon_sua}** — {len(ap_tong_hop)} ấp")
                                st.rerun()

            # ══ XÓA ══
            elif che_do == "🗑️ Xóa":
                st.markdown("**🗑️ Xóa CBTD**")
                if not cbtd_data:
                    st.info("Chưa có CBTD nào.")
                else:
                    chon_xoa = st.selectbox("Chọn CBTD",
                        list(cbtd_data.keys()),
                        format_func=lambda k: f"{k} — {cbtd_data[k]['ho_ten']} ({len(cbtd_data[k].get('ds_thon',[]))} ấp)",
                        key="cbtd_chon_xoa")
                    info_xoa = cbtd_data[chon_xoa]
                    ap_xoa_nhan = nhan_list(info_xoa.get("ds_thon",[]))
                    st.warning(f"⚠️ Sắp xóa: **{chon_xoa}** — {info_xoa['ho_ten']}\n\n"
                               f"Ấp phụ trách: {', '.join(ap_xoa_nhan)}")
                    xn = st.checkbox("Xác nhận xóa", key="cbtd_xn_xoa")
                    if st.button("🗑️ Xóa", type="primary",
                                 disabled=not xn, key="btn_xoa_cbtd"):
                        del cbtd_data[chon_xoa]
                        luu_cbtd(cbtd_data)
                        st.success(f"✅ Đã xóa **{chon_xoa}**")
                        st.rerun()

        st.divider()

        # ── Báo cáo theo CBTD ──
        if cbtd_data:
            st.markdown("**📊 Tổng hợp dư nợ theo CBTD**")

            def fmt_cbtd(x: float) -> str:
                """Format số tiền cho báo cáo CBTD (tỷ/triệu)."""
                try:
                    x = float(x)
                    if x >= 1e9:
                        s = f"{x/1e9:,.3f}".replace(",","X").replace(".",",").replace("X",".")
                        return f"{s.rstrip('0').rstrip(',') if ',' in s else s} tỷ"
                    if x >= 1e6:
                        return f"{x/1e6:,.1f} tr".replace(",","X").replace(".",",").replace("X",".")
                    return f"{x:,.0f}".replace(",",".")
                except Exception:
                    return "—"

            rows_bc = []
            for ma, info in cbtd_data.items():
                ds_ma_thon = [str(m) for m in info.get("ds_thon",[])]
                if not ds_ma_thon: continue
                # Join theo Mã thôn, loại món vay trực tiếp (Hình thức vay=1)
                mask = df["Mã thôn"].astype(str).isin(ds_ma_thon) \
                       if "Mã thôn" in df.columns else pd.Series([False]*len(df))
                df_cb = df[mask]
                # Loại món vay trực tiếp khỏi báo cáo CBTD
                if "Hình thức vay" in df_cb.columns:
                    df_cb = df_cb[df_cb["Hình thức vay"] != 1]
                if df_cb.empty: continue

                tdn = df_cb[COT_TONG_DU_NO].sum() if COT_TONG_DU_NO in df_cb.columns else 0
                dqh = df_cb[COT_DU_NO_QH].sum()   if COT_DU_NO_QH   in df_cb.columns else 0
                rows_bc.append({
                    "Mã CBTD":    ma,
                    "Họ tên":     info["ho_ten"],
                    "SĐT":        info.get("dien_thoai",""),
                    "Số KH":      f"{df_cb[COT_MA_KH].nunique():,}".replace(",","."),
                    "Số món vay": f"{df_cb[COT_SO_KU].nunique():,}".replace(",","."),
                    "Tổng dư nợ": fmt_cbtd(tdn),
                    "Dư nợ QH":   fmt_cbtd(dqh),
                    "Tỷ lệ QH %": round(dqh/tdn*100, 2) if tdn else 0,
                    "Số ấp":      len(ds_ma_thon),
                })

            if rows_bc:
                hien_thi_dataframe_phan_trang(
                    pd.DataFrame(rows_bc),
                    key="cbtd_tong_hop_bc",
                )

                if st.button("📥 Xuất báo cáo CBTD", key="btn_xuat_cbtd"):
                    buf = BytesIO()
                    with pd.ExcelWriter(buf, engine="openpyxl") as w:
                        pd.DataFrame(rows_bc).to_excel(w, index=False, sheet_name="Tổng hợp CBTD")
                        for ma, info in cbtd_data.items():
                            ds_ma = [str(m) for m in info.get("ds_thon",[])]
                            mask2 = df["Mã thôn"].astype(str).isin(ds_ma) \
                                    if "Mã thôn" in df.columns else pd.Series([False]*len(df))
                            df_cb2 = df[mask2]
                            if "Hình thức vay" in df_cb2.columns:
                                df_cb2 = df_cb2[df_cb2["Hình thức vay"] != 1]
                            if not df_cb2.empty:
                                df_cb2.to_excel(w, index=False, sheet_name=f"CB_{ma}"[:31])
                    st.session_state["_bytes_cbtd"] = buf.getvalue()
                    st.session_state["_file_cbtd"] = f"BC_CBTD_{datetime.today().strftime('%d%m%Y')}.xlsx"

                if st.session_state.get("_bytes_cbtd"):
                    st.download_button("⬇ Tải Excel",
                        data=st.session_state["_bytes_cbtd"],
                        file_name=st.session_state["_file_cbtd"],
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key="dl_cbtd")


