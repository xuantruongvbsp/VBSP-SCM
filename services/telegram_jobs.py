"""Registry các job Telegram có thể chạy thủ công hoặc theo lịch."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Callable

from logger import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class TelegramJobResult:
    ok: bool
    info: str = ""
    sent: int = 0
    failed: int = 0
    error: str = ""
    snapshot: dict[str, Any] | None = None


# ── 3 job gốc (nhắc deadline / nhập liệu / đến hạn phân tầng) ─────────────


def _run_deadline_bc(baseline: dict | None = None) -> TelegramJobResult:
    from scripts.nhac_deadline import run_deadline_bc_with_snapshot

    sent, pending, failed, error, snapshot = run_deadline_bc_with_snapshot(baseline)
    if failed:
        return TelegramJobResult(
            False,
            f"Đã gửi {sent}/{pending} loại báo cáo",
            sent,
            failed,
            error or "Gửi nhắc deadline thất bại.",
            snapshot,
        )
    empty_info = "Không có báo cáo cần nhắc" if baseline is None else "Không có thay đổi cần gửi"
    info = f"Đã gửi {sent} loại báo cáo" if sent else empty_info
    return TelegramJobResult(True, info, sent, 0, "", snapshot)


def _run_nhap_lieu(baseline: dict | None = None) -> TelegramJobResult:
    from scripts.nhac_deadline import run_nhap_lieu

    sent, pending, error, snapshot = run_nhap_lieu(baseline)
    if error and pending == 0:
        return TelegramJobResult(False, failed=1, error=error, snapshot=snapshot)
    failed = max(pending - sent, 0)
    if failed:
        return TelegramJobResult(
            False,
            f"Đã gửi {sent}/{pending} nhắc nhập liệu",
            sent,
            failed,
            error or "Gửi nhắc nhập liệu thất bại.",
            snapshot,
        )
    empty_info = "Không có sheet nhập liệu cần nhắc" if baseline is None else "Không có thay đổi cần gửi"
    info = f"Đã gửi {sent} nhắc nhập liệu" if sent else empty_info
    return TelegramJobResult(True, info, sent, 0, "", snapshot)


def _run_den_han_phan_tang(baseline: dict | None = None) -> TelegramJobResult:
    from scripts.nhac_deadline import run_den_han_phan_tang_with_snapshot

    ok, sent, total, error, snapshot = run_den_han_phan_tang_with_snapshot(baseline)
    if not ok:
        return TelegramJobResult(False, f"{total} khoản cần nhắc", sent, 1, error, snapshot)
    if sent:
        label = "thay đổi" if baseline is not None else "khoản"
        info = f"Đã gửi {total} {label} T-1/T-3/T-7"
    else:
        info = "Không có khoản đến hạn cần nhắc" if baseline is None else "Không có thay đổi cần gửi"
    return TelegramJobResult(True, info, sent, 0, "", snapshot)


# ── Báo cáo định kỳ ───────────────────────────────────────────────────────


def _run_bao_cao_sang(baseline: dict | None = None) -> TelegramJobResult:
    import pandas as pd
    import db
    from config import CACHE_HSTD, DS_PGD, COT_TONG_DU_NO, COT_DU_NO_QH
    from services import telegram_service as tg

    if not Path(CACHE_HSTD).exists():
        return TelegramJobResult(False, error="Chưa có dữ liệu HSTD.")
    df = pd.read_parquet(CACHE_HSTD, columns=[COT_TONG_DU_NO, COT_DU_NO_QH])
    tong_dn = df[COT_TONG_DU_NO].sum()
    tong_qh = df[COT_DU_NO_QH].sum()
    ty_le = f"{tong_qh / tong_dn * 100:.2f}%".replace(".", ",") if tong_dn else "0%"
    meta = db.doc_kv("merge_meta_hstd") or {}
    so_pgd = meta.get("so_pgd", 0)
    ok = tg.gui_bao_cao_sang(
        date.today().strftime("%d/%m/%Y"),
        f"{tong_dn / 1e9:.1f}".replace(".", ",") + " tỷ",
        f"{tong_qh / 1e6:.0f} triệu",
        ty_le, so_pgd, len(DS_PGD),
    )
    if ok:
        return TelegramJobResult(True, f"{so_pgd}/{len(DS_PGD)} PGD", sent=1)
    return TelegramJobResult(False, error="Gửi báo cáo sáng thất bại.", failed=1)


def _run_khoang_den_han(baseline: dict | None = None) -> TelegramJobResult:
    import pandas as pd
    from config import CACHE_HSTD, COT_NGAY_DH, COT_TONG_DU_NO, COT_TEN_PGD, COT_TEN_KH, COT_SO_KU
    from services import telegram_service as tg

    if not Path(CACHE_HSTD).exists():
        return TelegramJobResult(False, error="Chưa có dữ liệu HSTD.")
    df = pd.read_parquet(CACHE_HSTD)
    today_ts = pd.Timestamp.today().normalize()
    last_day = today_ts.replace(day=1) + pd.offsets.MonthEnd(0)
    if COT_NGAY_DH not in df.columns:
        return TelegramJobResult(False, error=f"Thiếu cột {COT_NGAY_DH}.")
    mask = (
        df[COT_NGAY_DH].notna()
        & (df[COT_NGAY_DH] >= today_ts)
        & (df[COT_NGAY_DH] <= last_day)
    )
    df_dh = df[mask].sort_values(COT_NGAY_DH)
    ds = [
        {
            "ten_kh":  str(r.get(COT_TEN_KH, "")),
            "so_ku":   str(r.get(COT_SO_KU, "")),
            "ngay_dh": r[COT_NGAY_DH].strftime("%d/%m/%Y") if pd.notna(r[COT_NGAY_DH]) else "",
            "du_no":   f"{float(r.get(COT_TONG_DU_NO, 0) or 0) / 1e6:.0f} tr",
            "ten_pgd": str(r.get(COT_TEN_PGD, "")),
        }
        for _, r in df_dh.iterrows()
    ]
    ok = tg.gui_nhac_khoang_den_han(ds)
    if ok:
        return TelegramJobResult(True, f"{len(ds)} khoản", sent=len(ds))
    return TelegramJobResult(False, error="Gửi nhắc khoản đến hạn thất bại.", failed=1)


def _run_phan_ky_nxh(baseline: dict | None = None) -> TelegramJobResult:
    import pandas as pd
    from data.phan_ky_nxh import doc_phan_ky_nxh
    from services import telegram_service as tg

    df = doc_phan_ky_nxh()
    if df.empty:
        return TelegramJobResult(False, error="Chưa có dữ liệu phân kỳ NXH.")
    today_ts = pd.Timestamp.today().normalize()
    last_day = today_ts.replace(day=1) + pd.offsets.MonthEnd(0)
    COL_NGAY = "Ngày đến hạn kỳ con"
    mask = (
        df[COL_NGAY].notna()
        & (df[COL_NGAY] >= today_ts)
        & (df[COL_NGAY] <= last_day)
    )
    df_t = df[mask].sort_values(["Tên xã", COL_NGAY])
    if df_t.empty:
        return TelegramJobResult(True, "Không có khoản đến hạn tháng này", sent=0)
    sent_count = 0
    failed_count = 0
    first_err = ""
    for ten_pgd, grp in df_t.groupby("Tên PGD"):
        ds = [
            {
                "ten_kh":        str(r.get("Tên khách hàng", "")),
                "so_ku":         str(r.get("Số khế ước", "")),
                "ngay_dh":       r[COL_NGAY].strftime("%d/%m/%Y") if pd.notna(r[COL_NGAY]) else "",
                "du_no":         float(r.get("Dư nợ kỳ con đến hạn", 0) or 0),
                "lai_ton":       float(r.get("Lãi tồn", 0) or 0),
                "tong_tgk":      float(r.get("Tổng TG, TK", 0) or 0),
                "sdt":           str(r.get("Số điện thoại", "") or ""),
                "ten_xa":        str(r.get("Tên xã", "") or ""),
                "ten_to_truong": str(r.get("Tên tổ trưởng", "") or ""),
                "ghi_chu":       str(r.get("Ghi chú", "") or ""),
            }
            for _, r in grp.iterrows()
        ]
        ok_pgd = tg.gui_nhac_phan_ky_nxh(str(ten_pgd), ds, today_ts.strftime("%d/%m/%Y"))
        if ok_pgd:
            sent_count += 1
        else:
            failed_count += 1
            if not first_err:
                first_err = "Gửi phân kỳ NXH thất bại."
    if failed_count:
        info = f"Đã gửi {sent_count} PGD, lỗi {failed_count} PGD"
        return TelegramJobResult(False, info, sent_count, failed_count, first_err)
    return TelegramJobResult(True, f"Đã gửi {sent_count} PGD", sent=sent_count)


def _run_khtd_tien_do(baseline: dict | None = None) -> TelegramJobResult:
    import pandas as pd
    import db
    from config import CACHE_HSTD, COT_TEN_PGD, COT_TONG_DU_NO
    from services import telegram_service as tg

    khtd_cn = db.doc_kv("khtd_cn")
    if not khtd_cn:
        return TelegramJobResult(False, error="Chưa có dữ liệu KHTD (cần giao KHTD trước).")
    if not Path(CACHE_HSTD).exists():
        return TelegramJobResult(False, error="Chưa có dữ liệu HSTD (cần merge trước).")
    df_dn = pd.read_parquet(CACHE_HSTD, columns=[COT_TEN_PGD, COT_TONG_DU_NO])
    du_no_pgd = df_dn.groupby(COT_TEN_PGD)[COT_TONG_DU_NO].sum().to_dict()
    kh_pgd: dict[str, float] = {}
    for _ct, targets in khtd_cn.items():
        if not isinstance(targets, dict):
            continue
        for ten_pgd, val in targets.items():
            if isinstance(val, (int, float)):
                kh_pgd[ten_pgd] = kh_pgd.get(ten_pgd, 0) + float(val)
    if not kh_pgd:
        return TelegramJobResult(False, error="Dữ liệu KHTD không có thông tin PGD.")
    ds_pgd = []
    for ten_pgd, ke_hoach in sorted(kh_pgd.items()):
        thuc_hien = float(du_no_pgd.get(ten_pgd, 0))
        pct = (thuc_hien / ke_hoach * 100) if ke_hoach > 0 else 0.0
        ds_pgd.append({
            "ten_pgd":   ten_pgd,
            "ke_hoach":  ke_hoach,
            "thuc_hien": thuc_hien,
            "pct":       round(pct, 1),
        })
    ok = tg.gui_khtd_tien_do(ds_pgd)
    if ok:
        return TelegramJobResult(True, f"{len(ds_pgd)} PGD", sent=1)
    return TelegramJobResult(False, error="Gửi tiến độ KHTD thất bại.", failed=1)


def _run_qh_moi(baseline: dict | None = None) -> TelegramJobResult:
    from scripts.daily_report import _canh_bao_tong_hop_rui_ro

    sent = _canh_bao_tong_hop_rui_ro()
    if sent:
        return TelegramJobResult(True, f"Đã gửi tin gộp cảnh báo rủi ro ({sent} cảnh báo)", sent=sent)
    return TelegramJobResult(True, "Không có cảnh báo rủi ro tín dụng để gửi", sent=0)


def _run_giai_ngan_tuan(baseline: dict | None = None) -> TelegramJobResult:
    import pandas as pd
    from config import CACHE_HSTD, COT_NGAY_VAY, COT_TEN_PGD, COT_TONG_DU_NO, DON_VI_CHI_NHANH
    from services import telegram_service as tg

    if not Path(CACHE_HSTD).exists():
        return TelegramJobResult(False, error="Chưa có dữ liệu HSTD.")
    df = pd.read_parquet(CACHE_HSTD)
    if COT_NGAY_VAY not in df.columns:
        return TelegramJobResult(False, error=f"Thiếu cột {COT_NGAY_VAY}.")
    today_ts = pd.Timestamp.today().normalize()
    t7 = today_ts - pd.Timedelta(days=7)
    mask = df[COT_NGAY_VAY].notna() & (df[COT_NGAY_VAY] >= t7) & (df[COT_NGAY_VAY] <= today_ts)
    df_gn = df[mask & (df[COT_TEN_PGD] != DON_VI_CHI_NHANH)]
    if df_gn.empty:
        return TelegramJobResult(True, "Không có khoản vay mới trong 7 ngày qua", sent=0)
    tuan_str = f"{t7.strftime('%d/%m')}–{today_ts.strftime('%d/%m/%Y')}"
    grp = df_gn.groupby(COT_TEN_PGD)[COT_TONG_DU_NO].agg(["sum", "count"]).reset_index()
    ds_pgd = [
        {"ten_pgd": str(r[COT_TEN_PGD]), "so_khoan": int(r["count"]), "giai_ngan": float(r["sum"])}
        for _, r in grp.iterrows()
    ]
    ok = tg.gui_giai_ngan_tuan(ds_pgd, tuan_str)
    if ok:
        return TelegramJobResult(True, f"{len(df_gn)} khoản vay mới", sent=1)
    return TelegramJobResult(False, error="Gửi báo cáo giải ngân tuần thất bại.", failed=1)


def _run_nqh_tuan(baseline: dict | None = None) -> TelegramJobResult:
    import pandas as pd
    import db
    from config import CACHE_HSTD, COT_TEN_PGD, COT_TONG_DU_NO, COT_DU_NO_QH, DON_VI_CHI_NHANH
    from services import telegram_service as tg

    if not Path(CACHE_HSTD).exists():
        return TelegramJobResult(False, error="Chưa có dữ liệu HSTD.")
    df = pd.read_parquet(CACHE_HSTD, columns=[COT_TEN_PGD, COT_TONG_DU_NO, COT_DU_NO_QH])
    df = df[df[COT_TEN_PGD] != DON_VI_CHI_NHANH]
    grp = df.groupby(COT_TEN_PGD)[[COT_TONG_DU_NO, COT_DU_NO_QH]].sum().reset_index()
    meta = db.doc_kv("merge_meta_hstd") or {}
    ngay_sl = meta.get("ngay_sl", date.today().strftime("%d/%m/%Y"))
    ds_pgd = []
    for _, r in grp.iterrows():
        dn = float(r[COT_TONG_DU_NO] or 0)
        qh = float(r[COT_DU_NO_QH] or 0)
        tl = qh / dn * 100 if dn > 0 else 0.0
        ds_pgd.append({
            "ten_pgd":   str(r[COT_TEN_PGD]),
            "du_no":     dn,
            "nqh":       qh,
            "ty_le_nqh": round(tl, 2),
        })
    ok = tg.gui_bao_cao_nqh_tuan(ds_pgd, str(ngay_sl))
    if ok:
        return TelegramJobResult(True, f"{len(ds_pgd)} đơn vị", sent=1)
    return TelegramJobResult(False, error="Gửi báo cáo NQH tuần thất bại.", failed=1)


def _run_khtd_ct(baseline: dict | None = None) -> TelegramJobResult:
    import pandas as pd
    import db
    from config import CACHE_HSTD, COT_TONG_DU_NO, CHUONG_TRINH_KHTD
    from services import telegram_service as tg

    khtd_cn = db.doc_kv("khtd_cn")
    if not khtd_cn:
        return TelegramJobResult(False, error="Chưa có dữ liệu KHTD (cần giao KHTD trước).")
    if not Path(CACHE_HSTD).exists():
        return TelegramJobResult(False, error="Chưa có dữ liệu HSTD (cần merge trước).")
    from tabs.tab_khtd_xuat import _tinh_thuc_hien_theo_ct
    th_dict = _tinh_thuc_hien_theo_ct(pd.read_parquet(CACHE_HSTD))
    meta = db.doc_kv("merge_meta_hstd") or {}
    ngay_sl = str(meta.get("ngay_sl", date.today().strftime("%d/%m/%Y")))
    ds_ct = []
    for ma_key, ma_ct, ten_hien_thi, nguon_von, _tm in CHUONG_TRINH_KHTD:
        kh_ct  = float(khtd_cn.get(ma_key, {}).get("_cn", 0) or 0)
        th_val = float(th_dict.get(ma_key, 0.0))
        pct    = th_val / kh_ct * 100 if kh_ct > 0 else 0.0
        ds_ct.append({
            "ten_ct":    ten_hien_thi,
            "nguon_von": nguon_von,
            "ke_hoach":  kh_ct,
            "thuc_hien": th_val,
            "pct":       round(pct, 1),
        })
    ok = tg.gui_khtd_theo_chuong_trinh(ds_ct, ngay_sl)
    if ok:
        return TelegramJobResult(True, f"{len(ds_ct)} chương trình", sent=1)
    return TelegramJobResult(False, error="Gửi KHTD theo chương trình thất bại.", failed=1)


def _run_tong_ket_thang(baseline: dict | None = None) -> TelegramJobResult:
    import pandas as pd
    import db
    from config import (
        CACHE_HSTD, COT_TEN_PGD, COT_TONG_DU_NO, COT_DU_NO_QH,
        COT_NGAY_DH, DON_VI_CHI_NHANH,
    )
    from services import telegram_service as tg

    if not Path(CACHE_HSTD).exists():
        return TelegramJobResult(False, error="Chưa có dữ liệu HSTD.")
    df = pd.read_parquet(CACHE_HSTD)
    khtd_cn = db.doc_kv("khtd_cn") or {}
    du_no  = float(df[COT_TONG_DU_NO].sum()) if COT_TONG_DU_NO in df.columns else 0.0
    nqh    = float(df[COT_DU_NO_QH].sum())   if COT_DU_NO_QH   in df.columns else 0.0
    ke_hoach = 0.0
    for _ct, targets in khtd_cn.items():
        if isinstance(targets, dict):
            ke_hoach += float(targets.get("_cn", 0) or 0)
    so_dh, dn_dh = 0, 0.0
    if COT_NGAY_DH in df.columns:
        today_ts = pd.Timestamp.today().normalize()
        nm1 = today_ts.replace(day=1) + pd.offsets.MonthBegin(1)
        nm_end = nm1 + pd.offsets.MonthEnd(0)
        mask_dh = df[COT_NGAY_DH].notna() & (df[COT_NGAY_DH] >= nm1) & (df[COT_NGAY_DH] <= nm_end)
        so_dh  = int(mask_dh.sum())
        dn_dh  = float(df.loc[mask_dh, COT_TONG_DU_NO].sum()) if COT_TONG_DU_NO in df.columns else 0.0
    kh_pgd: dict[str, float] = {}
    for _ct, targets in khtd_cn.items():
        if isinstance(targets, dict):
            for pgd, val in targets.items():
                if pgd != "_cn" and isinstance(val, (int, float)):
                    kh_pgd[pgd] = kh_pgd.get(pgd, 0) + float(val)
    df_pgd = (
        df[df[COT_TEN_PGD] != DON_VI_CHI_NHANH]
        .groupby(COT_TEN_PGD)[COT_TONG_DU_NO].sum()
        .reset_index()
    ) if COT_TEN_PGD in df.columns else pd.DataFrame()
    ds_ranked = []
    for _, r in df_pgd.iterrows():
        pgd = str(r[COT_TEN_PGD])
        kh  = kh_pgd.get(pgd, 0)
        th  = float(r[COT_TONG_DU_NO] or 0)
        pct = th / kh * 100 if kh > 0 else 0.0
        ds_ranked.append({"ten_pgd": pgd, "pct_kh": round(pct, 1)})
    ds_ranked.sort(key=lambda x: x["pct_kh"], reverse=True)
    top5 = ds_ranked[:5]
    bot5 = list(reversed(ds_ranked[-5:])) if len(ds_ranked) >= 5 else ds_ranked
    thang = date.today().month
    nam   = date.today().year
    ok = tg.gui_tong_ket_thang(
        thang, nam, du_no, ke_hoach, nqh,
        so_dh, dn_dh, top5, bot5,
    )
    if ok:
        return TelegramJobResult(True, f"Tháng {thang:02d}/{nam}", sent=1)
    return TelegramJobResult(False, error="Gửi tổng kết tháng thất bại.", failed=1)


# ── Nhắc nghiệp vụ ────────────────────────────────────────────────────────


def _run_nop_moi_gsheet(baseline: dict | None = None) -> TelegramJobResult:
    import pandas as pd
    from services.report_submission_service import doc_du_lieu_gsheet
    from services import telegram_service as tg

    df_gs = doc_du_lieu_gsheet()
    if df_gs.empty:
        return TelegramJobResult(False, error="Không có dữ liệu GSheet (kiểm tra credentials.json).")
    cutoff = pd.Timestamp.now() - pd.Timedelta(hours=24)
    df_moi = df_gs[df_gs["thoi_gian"] > cutoff]
    if df_moi.empty:
        return TelegramJobResult(True, "Không có submission mới trong 24h qua", sent=0)
    ds = []
    for _, r in df_moi.iterrows():
        ts_str = ""
        try:
            if pd.notna(r.get("thoi_gian")):
                ts_str = pd.Timestamp(r["thoi_gian"]).strftime("%d/%m %H:%M")
        except Exception:
            pass
        ds.append({
            "ten_pgd":      str(r.get("ten_pgd", "") or ""),
            "loai_bao_cao": str(r.get("loai_bao_cao", "") or ""),
            "thoi_gian":    ts_str,
            "ho_ten":       str(r.get("ho_ten", "") or ""),
        })
    ok = tg.gui_thong_bao_nop_moi_gsheet(ds)
    if ok:
        return TelegramJobResult(True, f"{len(ds)} submission trong 24h qua", sent=1)
    return TelegramJobResult(False, error="Gửi thông báo nộp mới GSheet thất bại.", failed=1)


def _run_lich_cong_tac(baseline: dict | None = None) -> TelegramJobResult:
    import datetime as _dt
    import pandas as pd
    import db
    from services import telegram_service as tg

    ds_lich = db.doc_kv("khnv_lich_list")
    if not ds_lich or not isinstance(ds_lich, list):
        return TelegramJobResult(False, error="Chưa có lịch công tác (vào tab Phòng KH-NV → Lịch để thêm).")
    tomorrow = date.today() + _dt.timedelta(days=1)
    ngay_mai_str = tomorrow.strftime("%d/%m/%Y")
    tomorrow_ts  = pd.Timestamp(tomorrow)
    ds_sv = []
    for entry in ds_lich:
        if not isinstance(entry, dict):
            continue
        ngay_raw = entry.get("ngay") or entry.get("date") or ""
        try:
            ngay_entry = pd.to_datetime(ngay_raw, dayfirst=True).normalize()
        except Exception:
            continue
        if ngay_entry != tomorrow_ts:
            continue
        ds_sv.append({
            "gio":             str(entry.get("gio", "") or ""),
            "noi_dung":        str(entry.get("noi_dung", "") or ""),
            "nguoi_phu_trach": str(entry.get("nguoi_phu_trach", "") or ""),
            "dia_diem":        str(entry.get("dia_diem", "") or ""),
        })
    if not ds_sv:
        return TelegramJobResult(True, f"Không có lịch ngày mai ({ngay_mai_str})", sent=0)
    ds_sv.sort(key=lambda x: x["gio"] or "99:99")
    ok = tg.gui_nhac_lich_cong_tac(ds_sv, ngay_mai_str)
    if ok:
        return TelegramJobResult(True, f"{len(ds_sv)} sự kiện ngày {ngay_mai_str}", sent=1)
    return TelegramJobResult(False, error="Gửi nhắc lịch công tác thất bại.", failed=1)


# ── Cảnh báo rủi ro ───────────────────────────────────────────────────────


def _run_khoanh_tang(baseline: dict | None = None) -> TelegramJobResult:
    from scripts.daily_report import _canh_bao_tong_hop_rui_ro

    sent = _canh_bao_tong_hop_rui_ro()
    if sent:
        return TelegramJobResult(True, f"Đã gửi tin gộp cảnh báo rủi ro ({sent} cảnh báo)", sent=sent)
    return TelegramJobResult(True, "Không có cảnh báo rủi ro tín dụng để gửi", sent=0)


# ── Hệ thống ──────────────────────────────────────────────────────────────


def _run_health_check(baseline: dict | None = None) -> TelegramJobResult:
    from services import telegram_service as tg

    ok = tg.gui_ket_qua_health_check(
        0, 0, 0, date.today().strftime("%d/%m/%Y"), "Kiểm tra từ scheduler",
    )
    if ok:
        return TelegramJobResult(True, "Đã gửi health check", sent=1)
    return TelegramJobResult(False, error="Gửi health check thất bại.", failed=1)


# ── Registry ──────────────────────────────────────────────────────────────

_JOB_REGISTRY: dict[str, Callable[[dict | None], TelegramJobResult]] = {
    # Nhắc nghiệp vụ
    "deadline_bc":        _run_deadline_bc,
    "nhap_lieu":          _run_nhap_lieu,
    "den_han_phan_tang":  _run_den_han_phan_tang,
    "nop_moi_gsheet":     _run_nop_moi_gsheet,
    "lich_cong_tac":      _run_lich_cong_tac,
    # Báo cáo định kỳ
    "bao_cao_sang":       _run_bao_cao_sang,
    "khoang_den_han":     _run_khoang_den_han,
    "phan_ky_nxh":        _run_phan_ky_nxh,
    "khtd_tien_do":       _run_khtd_tien_do,
    "giai_ngan_tuan":     _run_giai_ngan_tuan,
    "nqh_tuan":           _run_nqh_tuan,
    "khtd_ct":            _run_khtd_ct,
    "tong_ket_thang":     _run_tong_ket_thang,
    # Cảnh báo rủi ro
    "qh_moi":             _run_qh_moi,
    "khoanh_tang":        _run_khoanh_tang,
    # Hệ thống
    "health_check":       _run_health_check,
}

_JOB_DEDUPE_GROUPS: dict[str, str] = {
    "qh_moi": "rui_ro_tin_dung",
    "khoanh_tang": "rui_ro_tin_dung",
}

# Nhãn hiển thị trong UI scheduler
JOB_LABELS: dict[str, str] = {
    "deadline_bc":        "⚠️ PGD chưa nộp báo cáo",
    "nhap_lieu":          "📝 PGD chưa hoàn thành nhập liệu",
    "den_han_phan_tang":  "⏰ Khoản vay đến hạn T-7/T-3/T-1",
    "nop_moi_gsheet":     "📋 PGD nộp BC mới (GSheet)",
    "lich_cong_tac":      "📅 Lịch công tác ngày mai",
    "bao_cao_sang":       "📊 Báo cáo tổng hợp sáng",
    "khoang_den_han":     "⏰ Nhắc khoản đến hạn",
    "phan_ky_nxh":        "🏠 Nhắc phân kỳ NXH",
    "khtd_tien_do":       "📈 Tiến độ KHTD",
    "giai_ngan_tuan":     "💸 Giải ngân tuần",
    "nqh_tuan":           "📊 Báo cáo NQH tuần",
    "khtd_ct":            "🎯 KHTD theo chương trình",
    "tong_ket_thang":     "📅 Tổng kết tháng",
    "qh_moi":             "🔴 Cảnh báo NQH tăng",
    "khoanh_tang":        "⚠️ Cảnh báo nợ khoanh tăng",
    "health_check":       "🔍 Kết quả Health Check",
}


def telegram_job_keys() -> tuple[str, ...]:
    return tuple(_JOB_REGISTRY)


def telegram_job_dedupe_key(notify_key: str) -> str:
    """Nhóm các notify_key gửi cùng một nội dung để scheduler không bắn trùng."""
    key = str(notify_key or "").strip()
    return _JOB_DEDUPE_GROUPS.get(key, key)


def run_telegram_job(notify_key: str, baseline: dict | None = None) -> TelegramJobResult:
    """Chạy job từ whitelist; không nhận module/function tùy ý từ rule."""
    runner = _JOB_REGISTRY.get(str(notify_key or "").strip())
    if runner is None:
        return TelegramJobResult(False, error=f"Job Telegram không được hỗ trợ: {notify_key}")
    try:
        return runner(baseline)
    except Exception as e:
        logger.error("run_telegram_job(%s): %s", notify_key, e, exc_info=True)
        return TelegramJobResult(False, error=str(e))
