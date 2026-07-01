#!/usr/bin/env python3
"""
telegram_polling.py — Bot 2 chiều: nhận lệnh từ Telegram, trả kết quả.

Thiết kế: chạy 1 lần rồi thoát — Task Scheduler gọi mỗi phút.
Mỗi lần chạy lấy các update mới kể từ lần trước (dùng offset lưu trong kv_store).

Lệnh hỗ trợ:
  /help   — Danh sách lệnh
  /sl     — Số liệu tổng hợp (dư nợ, NQH)
  /nqh    — Báo cáo NQH từng đơn vị
  /khtd   — Tiến độ KHTD từng PGD
  /dh     — Khoản đến hạn tháng này
  /pgd <tên>  — Tóm tắt 1 PGD cụ thể
"""
from __future__ import annotations

import sys
import os
from datetime import date
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import pandas as pd
import requests

import db
from config import (
    CACHE_HSTD,
    COT_TEN_PGD, COT_TONG_DU_NO, COT_DU_NO_QH, COT_DU_NO_KHOANH,
    COT_NGAY_DH, COT_TEN_KH, COT_SO_KU, COT_NGAY_VAY,
    DON_VI_CHI_NHANH,
)
from logger import get_logger

logger = get_logger(__name__)

_API_TIMEOUT = 10
_KV_OFFSET   = "telegram_poll_last_offset"

_HELP_TEXT = (
    "🤖 <b>VBSP-SCM Bot — Danh sách lệnh</b>\n\n"
    "/sl   — Số liệu tổng hợp (dư nợ, NQH)\n"
    "/nqh  — NQH từng đơn vị\n"
    "/khtd — Tiến độ KHTD từng PGD\n"
    "/dh   — Khoản đến hạn tháng này\n"
    "/gn   — Giải ngân 7 ngày qua\n"
    "/pgd &lt;tên&gt; — Tóm tắt 1 PGD (vd: /pgd bh)\n"
    "/help — Hiển thị danh sách này"
)


def _get_bot_config() -> tuple[str, str]:
    cfg = db.doc_kv("telegram_config") or {}
    token   = cfg.get("token", os.environ.get("TELEGRAM_BOT_TOKEN", ""))
    chat_id = cfg.get("chat_id", "")
    return token, chat_id


def _send(token: str, chat_id: str | int, text: str) -> bool:
    from services.telegram_service import gui_tin_chi_tiet_voi_config

    ok, err = gui_tin_chi_tiet_voi_config(
        token,
        str(chat_id),
        text,
        parse_mode="HTML",
        log_func=None,
    )
    if not ok:
        logger.error("_send chat_id=%s: %s", chat_id, err)
    return ok


def _get_updates(token: str, offset: int) -> list[dict]:
    try:
        r = requests.get(
            f"https://api.telegram.org/bot{token}/getUpdates",
            params={"offset": offset, "timeout": 5, "limit": 50},
            timeout=15,
        )
        if r.ok:
            return r.json().get("result", [])
    except Exception as e:
        logger.warning("getUpdates: %s", e)
    return []


# ── Command handlers ──────────────────────────────────────────────────────────

def _cmd_sl() -> str:
    if not Path(CACHE_HSTD).exists():
        return "⚠️ Chưa có dữ liệu HSTD."
    df = pd.read_parquet(CACHE_HSTD, columns=[COT_TONG_DU_NO, COT_DU_NO_QH])
    dn = float(df[COT_TONG_DU_NO].sum())
    qh = float(df[COT_DU_NO_QH].sum())
    tl = qh / dn * 100 if dn else 0.0
    meta = db.doc_kv("merge_meta_hstd") or {}
    ngay = meta.get("ngay_sl", date.today().strftime("%d/%m/%Y"))
    dn_s  = f"{dn / 1e9:,.1f}".replace(",", ".") + " tỷ"
    qh_s  = f"{qh / 1e6:,.0f}".replace(",", ".") + " triệu"
    tl_s  = f"{tl:.2f}%".replace(".", ",")
    return (
        f"📊 <b>Số liệu tổng hợp</b>  📅 {ngay}\n"
        f"💰 Dư nợ: <b>{dn_s}</b>\n"
        f"🔴 NQH: <b>{qh_s}</b> ({tl_s})"
    )


def _cmd_nqh() -> str:
    if not Path(CACHE_HSTD).exists():
        return "⚠️ Chưa có dữ liệu HSTD."
    df = pd.read_parquet(CACHE_HSTD, columns=[COT_TEN_PGD, COT_TONG_DU_NO, COT_DU_NO_QH])
    df = df[df[COT_TEN_PGD] != DON_VI_CHI_NHANH]
    grp = df.groupby(COT_TEN_PGD)[[COT_TONG_DU_NO, COT_DU_NO_QH]].sum().reset_index()
    grp["ty_le"] = grp.apply(
        lambda r: r[COT_DU_NO_QH] / r[COT_TONG_DU_NO] * 100 if r[COT_TONG_DU_NO] else 0.0, axis=1
    )
    grp = grp.sort_values("ty_le", ascending=False)

    def _icon(tl: float) -> str:
        return "🔴" if tl >= 3 else "🟠" if tl >= 1 else "🟢"

    lines = ["📊 <b>NQH từng đơn vị</b>", ""]
    for _, r in grp.iterrows():
        tl = float(r["ty_le"])
        qh = float(r[COT_DU_NO_QH])
        if qh == 0:
            continue
        pgd  = str(r[COT_TEN_PGD])
        qh_s = f"{qh / 1e6:,.0f}".replace(",", ".") + " tr"
        tl_s = f"{tl:.2f}%".replace(".", ",")
        lines.append(f"  {_icon(tl)} {pgd}: {qh_s} ({tl_s})")
    return "\n".join(lines) if len(lines) > 2 else "✅ Không có NQH."


def _cmd_khtd() -> str:
    khtd_cn = db.doc_kv("khtd_cn")
    if not khtd_cn:
        return "⚠️ Chưa có KHTD (cần giao KHTD trước)."
    if not Path(CACHE_HSTD).exists():
        return "⚠️ Chưa có dữ liệu HSTD."
    df = pd.read_parquet(CACHE_HSTD, columns=[COT_TEN_PGD, COT_TONG_DU_NO])
    du_no_pgd = df.groupby(COT_TEN_PGD)[COT_TONG_DU_NO].sum().to_dict()
    # Tổng KH theo PGD
    kh_pgd: dict[str, float] = {}
    for _ct, targets in khtd_cn.items():
        if not isinstance(targets, dict):
            continue
        for pgd, val in targets.items():
            if pgd != "_cn" and isinstance(val, (int, float)):
                kh_pgd[pgd] = kh_pgd.get(pgd, 0) + float(val)
    if not kh_pgd:
        return "⚠️ Dữ liệu KHTD chưa có thông tin PGD."

    def _icon(pct: float) -> str:
        return "✅" if pct >= 100 else "🟡" if pct >= 80 else "🔴"

    lines = ["🎯 <b>Tiến độ KHTD từng PGD</b>", ""]
    tong_kh = sum(kh_pgd.values())
    tong_th = sum(float(du_no_pgd.get(p, 0)) for p in kh_pgd)
    for pgd, kh in sorted(kh_pgd.items(), key=lambda x: -float(du_no_pgd.get(x[0], 0)) / x[1] if x[1] else 0):
        th  = float(du_no_pgd.get(pgd, 0))
        pct = th / kh * 100 if kh else 0.0
        pct_s = f"{pct:.1f}%".replace(".", ",")
        lines.append(f"  {_icon(pct)} {pgd}: {pct_s}")
    if tong_kh > 0:
        pct_cn = tong_th / tong_kh * 100
        pct_cn_s = f"{pct_cn:.1f}%".replace(".", ",")
        lines.append("")
        lines.append(f"🏆 <b>Tổng CN: {pct_cn_s}</b>")
    return "\n".join(lines)


def _cmd_dh() -> str:
    if not Path(CACHE_HSTD).exists():
        return "⚠️ Chưa có dữ liệu HSTD."
    try:
        df = pd.read_parquet(CACHE_HSTD)
        if COT_NGAY_DH not in df.columns:
            return "⚠️ Thiếu cột ngày đến hạn trong dữ liệu."
        today_ts = pd.Timestamp.today().normalize()
        last_day = today_ts.replace(day=1) + pd.offsets.MonthEnd(0)
        mask = df[COT_NGAY_DH].notna() & (df[COT_NGAY_DH] >= today_ts) & (df[COT_NGAY_DH] <= last_day)
        df_dh = df[mask]
        so_khoan = len(df_dh)
        tong_dn  = float(df_dh[COT_TONG_DU_NO].sum()) if COT_TONG_DU_NO in df_dh.columns else 0.0
        if so_khoan == 0:
            return "✅ Không có khoản đến hạn tháng này."
        # Theo PGD
        if COT_TEN_PGD in df_dh.columns:
            grp = df_dh.groupby(COT_TEN_PGD).agg(
                so_khoan=(COT_TEN_KH, "count") if COT_TEN_KH in df_dh.columns else (COT_TONG_DU_NO, "count"),
                du_no=(COT_TONG_DU_NO, "sum"),
            ).reset_index()
        else:
            grp = pd.DataFrame()
        tong_s = f"{tong_dn / 1e6:,.0f}".replace(",", ".") + " triệu"
        lines = [
            f"⏰ <b>Khoản đến hạn tháng này</b>",
            f"📊 {so_khoan} khoản — {tong_s}",
            "",
        ]
        for _, r in grp.iterrows():
            pgd = str(r[COT_TEN_PGD])
            n   = int(r["so_khoan"])
            dn  = float(r["du_no"])
            dn_s = f"{dn / 1e6:,.0f}".replace(",", ".") + " tr"
            lines.append(f"  • {pgd}: {n} khoản ({dn_s})")
        return "\n".join(lines)
    except Exception as e:
        return f"❌ Lỗi: {e}"


def _cmd_gn() -> str:
    if not Path(CACHE_HSTD).exists():
        return "⚠️ Chưa có dữ liệu HSTD."
    try:
        df = pd.read_parquet(CACHE_HSTD)
        if COT_NGAY_VAY not in df.columns:
            return "⚠️ Thiếu cột ngày vay trong dữ liệu."
        today_ts = pd.Timestamp.today().normalize()
        t7 = today_ts - pd.Timedelta(days=7)
        mask = df[COT_NGAY_VAY].notna() & (df[COT_NGAY_VAY] >= t7) & (df[COT_NGAY_VAY] <= today_ts)
        df_gn = df[mask]
        if df_gn.empty:
            return "ℹ️ Không có khoản vay mới trong 7 ngày qua."
        tong_dn = float(df_gn[COT_TONG_DU_NO].sum()) if COT_TONG_DU_NO in df_gn.columns else 0.0
        lines = [
            f"💸 <b>Giải ngân 7 ngày qua</b>  ({len(df_gn)} khoản)",
            f"💰 Tổng: <b>{tong_dn / 1e9:,.2f}".replace(",", ".") + " tỷ</b>",
            "",
        ]
        if COT_TEN_PGD in df_gn.columns:
            grp = df_gn.groupby(COT_TEN_PGD)[COT_TONG_DU_NO].agg(["sum", "count"]).reset_index()
            for _, r in grp.sort_values("sum", ascending=False).iterrows():
                pgd = str(r[COT_TEN_PGD])
                gn_s = f"{float(r['sum']) / 1e6:,.0f}".replace(",", ".") + " tr"
                lines.append(f"  • {pgd}: {gn_s} ({int(r['count'])} khoản)")
        return "\n".join(lines)
    except Exception as e:
        return f"❌ Lỗi: {e}"


def _cmd_pgd(arg: str) -> str:
    """Tóm tắt 1 PGD — arg là tên hoặc slug (ví dụ: 'bh', 'biên hòa')."""
    if not arg:
        return "⚠️ Cú pháp: /pgd &lt;tên&gt;  (vd: /pgd bh hoặc /pgd biên hòa)"
    if not Path(CACHE_HSTD).exists():
        return "⚠️ Chưa có dữ liệu HSTD."
    try:
        from data.pgd import pgd_slug
        from config import DS_PGD
        # Tìm PGD khớp (slug hoặc tên chứa arg)
        arg_lower = arg.lower().strip()
        # Tìm PGD theo slug hoặc tên
        matched = None
        arg_slug = pgd_slug(arg)
        for pgd in DS_PGD:
            if pgd_slug(pgd) == arg_slug or arg_lower in pgd.lower():
                matched = pgd
                break
        if not matched:
            return f"❌ Không tìm thấy PGD: <b>{arg}</b>\nGợi ý: /pgd bh, /pgd lt, /pgd xk"
        df = pd.read_parquet(CACHE_HSTD)
        df_pgd = df[df[COT_TEN_PGD] == matched]
        if df_pgd.empty:
            return f"⚠️ Không có dữ liệu cho <b>{matched}</b>."
        dn  = float(df_pgd[COT_TONG_DU_NO].sum()) if COT_TONG_DU_NO in df_pgd.columns else 0.0
        qh  = float(df_pgd[COT_DU_NO_QH].sum())   if COT_DU_NO_QH   in df_pgd.columns else 0.0
        kh  = float(df_pgd[COT_DU_NO_KHOANH].sum()) if COT_DU_NO_KHOANH in df_pgd.columns else 0.0
        tl_qh = qh / dn * 100 if dn else 0.0
        # Khoản đến hạn tháng này
        so_dh = 0
        if COT_NGAY_DH in df_pgd.columns:
            today_ts = pd.Timestamp.today().normalize()
            last_day = today_ts.replace(day=1) + pd.offsets.MonthEnd(0)
            mask_dh = df_pgd[COT_NGAY_DH].notna() & (df_pgd[COT_NGAY_DH] >= today_ts) & (df_pgd[COT_NGAY_DH] <= last_day)
            so_dh = int(mask_dh.sum())
        # KHTD
        khtd_cn = db.doc_kv("khtd_cn") or {}
        kh_pgd = 0.0
        for _ct, targets in khtd_cn.items():
            if isinstance(targets, dict) and matched in targets:
                kh_pgd += float(targets[matched] or 0)
        pct_kh = dn / kh_pgd * 100 if kh_pgd else None
        dn_s   = f"{dn / 1e9:,.2f}".replace(",", ".") + " tỷ"
        qh_s   = f"{qh / 1e6:,.0f}".replace(",", ".") + " tr"
        kh_s   = f"{kh / 1e6:,.0f}".replace(",", ".") + " tr"
        tl_s   = f"{tl_qh:.2f}%".replace(".", ",")
        lines = [f"📍 <b>{matched}</b>", ""]
        lines.append(f"💰 Dư nợ: <b>{dn_s}</b>")
        if pct_kh is not None:
            kh_pgd_s = f"{kh_pgd / 1e9:,.2f}".replace(",", ".") + " tỷ"
            pct_s    = f"{pct_kh:.1f}%".replace(".", ",")
            lines.append(f"🎯 KH: {kh_pgd_s}  → Đạt <b>{pct_s}</b>")
        lines.append(f"🔴 NQH: {qh_s} ({tl_s})")
        if kh > 0:
            lines.append(f"⚠️ Nợ khoanh: {kh_s}")
        if so_dh > 0:
            lines.append(f"⏰ Đến hạn tháng này: {so_dh} khoản")
        return "\n".join(lines)
    except Exception as e:
        return f"❌ Lỗi: {e}"


# ── Main polling loop ─────────────────────────────────────────────────────────

def poll_once() -> None:
    """Lấy các update mới, xử lý lệnh, cập nhật offset."""
    token, _ = _get_bot_config()
    if not token:
        logger.warning("telegram_polling: chưa cấu hình token, bỏ qua.")
        return

    offset = int(db.doc_kv(_KV_OFFSET) or 0)
    updates = _get_updates(token, offset)
    if not updates:
        return

    for upd in updates:
        upd_id = upd.get("update_id", 0)
        offset = max(offset, upd_id + 1)

        msg = upd.get("message") or upd.get("edited_message")
        if not msg:
            continue
        text_raw = str(msg.get("text", "")).strip()
        if not text_raw.startswith("/"):
            continue

        chat_id = msg["chat"]["id"]
        parts   = text_raw.split(None, 1)
        cmd     = parts[0].split("@")[0].lower()  # loại bỏ @botname
        arg     = parts[1].strip() if len(parts) > 1 else ""

        try:
            if cmd in ("/help", "/start"):
                reply = _HELP_TEXT
            elif cmd == "/sl":
                reply = _cmd_sl()
            elif cmd == "/nqh":
                reply = _cmd_nqh()
            elif cmd == "/khtd":
                reply = _cmd_khtd()
            elif cmd == "/dh":
                reply = _cmd_dh()
            elif cmd == "/gn":
                reply = _cmd_gn()
            elif cmd == "/pgd":
                reply = _cmd_pgd(arg)
            else:
                reply = f"❓ Lệnh <code>{cmd}</code> không hỗ trợ.\nGõ /help để xem danh sách."
            _send(token, chat_id, reply)
        except Exception as e:
            logger.error("poll_once xử lý lệnh %s: %s", cmd, e, exc_info=True)
            _send(token, chat_id, f"❌ Lỗi xử lý lệnh <code>{cmd}</code>: {e}")

    db.ghi_kv(_KV_OFFSET, offset, "system")
    logger.info("telegram_polling: xử lý %d update(s), offset mới = %d", len(updates), offset)


if __name__ == "__main__":
    poll_once()
