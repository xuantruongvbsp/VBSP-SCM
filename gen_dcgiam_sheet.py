
"""
gen_dcgiam_sheet.py
_________________
Script doc lap day du lieu GQVL len Google Sheet de theo doi
KH vs TH phan tang 4 nhom: NHCSXH TW, NSNN TW, DP cap tinh, DP cap xa.

Cach dung:
    python gen_dcgiam_sheet.py --th
    python gen_dcgiam_sheet.py --kh --nam 2026
    python gen_dcgiam_sheet.py --all
"""

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

import db
import config
from db import doc_ndt_dp_ma_list

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
_LOG = logging.getLogger(__name__)

DCGIAM_SHEET_ID = "15Ev2rTv6khLFaMpAiMwqJCVC_33ocJ-6cp016RGNkYk"
CREDENTIALS_FILE = "credentials.json"
SHEET_TAB_GQVL = "GQVL"
SHEET_TAB_KH = "KH_GQVL"
SHEET_KH_TH_TONG_HOP = "KH_TH_TONG_HOP"
SHEET_KH_TH_THEO_PGD = "KH_TH_THEO_PGD"

GQVL_PARQUET = Path(config.CACHE_GQVL)


def _ket_noi_gsheet():
    import gspread
    from oauth2client.service_account import ServiceAccountCredentials

    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]
    if not Path(CREDENTIALS_FILE).exists():
        raise FileNotFoundError(
            f"Khong tim thay file credentials: {CREDENTIALS_FILE}"
        )
    creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, scope)
    return gspread.authorize(creds)


def _doc_gqvl_parquet() -> pd.DataFrame:
    if not GQVL_PARQUET.exists():
        raise FileNotFoundError(
            f"Khong tim thay file parquet: {GQVL_PARQUET}. "
            "Hay upload va merge GQVL truoc khi chay script nay."
        )
    df = pd.read_parquet(GQVL_PARQUET)
    _LOG.info("Doc %d dong tu %s", len(df), GQVL_PARQUET)
    return df


def _doc_hstd_parquet() -> pd.DataFrame:
    hstd_parquet = Path(config.CACHE_HSTD)
    if not hstd_parquet.exists():
        raise FileNotFoundError(
            f"Khong tim thay file parquet: {hstd_parquet}. "
            "Hay upload va merge HSTD truoc khi chay script nay."
        )
    df = pd.read_parquet(hstd_parquet)
    _LOG.info("Doc %d dong tu %s", len(df), hstd_parquet)
    return df


def _build_rows_kh_th(
    kh_cn: dict,
    th_hstd: dict,
    th_gqvl: dict,
    ten_don_vi: str,
) -> list[list]:
    rows: list[list] = []
    rows.append([ten_don_vi, "", "", "", ""])
    rows.append(["STT", "Chỉ tiêu", "KH năm (tỷ)", "TH (tỷ)", "TL%"])

    rows.append(["A", "KẾ HOẠCH TÍN DỤNG", "", "", ""])

    stt_tw = 1
    stt_dp = 1
    tong_kh = 0.0
    tong_th = 0.0

    rows.append(["I", "NGUỒN VỐN TRUNG ƯƠNG", "", "", ""])
    for mk, _, ten, nv, *_ in config.CHUONG_TRINH_KHTD:
        if nv != "TW":
            continue
        kh = float(kh_cn.get(mk, 0.0)) / 1e9
        if "GQVL" in str(ten) or str(mk).startswith("3_TW"):
            th_tw_gqvl = (
                float(th_gqvl.get("cap_tinh_tw_nhcsxh", 0.0))
                + float(th_gqvl.get("cap_tinh_tw_nsnn", 0.0))
            ) / 1e9
            tl = (th_tw_gqvl / kh) if kh > 0 else None
            rows.append([str(stt_tw), f"  {ten}", round(kh, 3), round(th_tw_gqvl, 3), tl])
            for sub_ten, sub_key in [
                ("    TW - NHCSXH huy động", "cap_tinh_tw_nhcsxh"),
                ("    TW - NSNN/Quỹ QG TW", "cap_tinh_tw_nsnn"),
            ]:
                th_sub = float(th_gqvl.get(sub_key, 0.0)) / 1e9
                rows.append(["*", sub_ten, "", round(th_sub, 3), ""])
            th = th_tw_gqvl
        else:
            th = float(th_hstd.get(mk, 0.0)) / 1e9
            tl = (th / kh) if kh > 0 else None
            rows.append([str(stt_tw), f"  {ten}", round(kh, 3), round(th, 3), tl])
        tong_kh += kh
        tong_th += th
        stt_tw += 1

    rows.append(["II", "NGUỒN VỐN ĐỊA PHƯƠNG", "", "", ""])
    for mk, _, ten, nv, *_ in config.CHUONG_TRINH_KHTD:
        if nv != "DP":
            continue
        kh = float(kh_cn.get(mk, 0.0)) / 1e9
        if "GQVL" in str(ten) or str(mk).startswith("3_DP"):
            th_dp_gqvl = (
                float(th_gqvl.get("cap_tinh", 0.0))
                + float(th_gqvl.get("cap_xa", 0.0))
            ) / 1e9
            tl = (th_dp_gqvl / kh) if kh > 0 else None
            rows.append([str(stt_dp), f"  {ten}", round(kh, 3), round(th_dp_gqvl, 3), tl])
            for sub_ten, sub_key in [
                ("    ĐP - Cấp tỉnh", "cap_tinh"),
                ("    ĐP - Cấp xã/khác", "cap_xa"),
            ]:
                th_sub = float(th_gqvl.get(sub_key, 0.0)) / 1e9
                rows.append(["*", sub_ten, "", round(th_sub, 3), ""])
            th = th_dp_gqvl
        else:
            th = float(th_hstd.get(mk, 0.0)) / 1e9
            tl = (th / kh) if kh > 0 else None
            rows.append([str(stt_dp), f"  {ten}", round(kh, 3), round(th, 3), tl])
        tong_kh += kh
        tong_th += th
        stt_dp += 1

    tl_tong = (tong_th / tong_kh) if tong_kh > 0 else None
    rows.append(["", "TỔNG CỘNG", round(tong_kh, 3), round(tong_th, 3), tl_tong])
    rows.append(["", "", "", "", ""])
    return rows


def _hex_to_rgb01(hex_color: str) -> dict:
    s = hex_color.strip().lstrip("#")
    r = int(s[0:2], 16) / 255.0
    g = int(s[2:4], 16) / 255.0
    b = int(s[4:6], 16) / 255.0
    return {"red": r, "green": g, "blue": b}


def _repeat_row_format(ws, row_idx_1based: int, fmt: dict) -> dict:
    sheet_id = ws._properties["sheetId"]
    return {
        "repeatCell": {
            "range": {
                "sheetId": sheet_id,
                "startRowIndex": row_idx_1based - 1,
                "endRowIndex": row_idx_1based,
                "startColumnIndex": 0,
                "endColumnIndex": 5,
            },
            "cell": {"userEnteredFormat": fmt},
            "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment,numberFormat)",
        }
    }


def _apply_format_kh_th(ws, rows: list[list]) -> None:
    navy = _hex_to_rgb01("#003D7A")
    group_bg = _hex_to_rgb01("#D9E1F2")
    total_bg = _hex_to_rgb01("#F2F2F2")
    sub_bg = _hex_to_rgb01("#EBF3E8")

    reqs: list[dict] = []
    for i, r in enumerate(rows, start=1):
        stt = str(r[0]) if len(r) > 0 else ""
        chi_tieu = str(r[1]) if len(r) > 1 else ""
        if stt and chi_tieu == "" and (len(r) >= 5 and all(str(x) == "" for x in r[1:])):
            reqs.append(
                _repeat_row_format(
                    ws,
                    i,
                    {
                        "backgroundColor": navy,
                        "textFormat": {"bold": True, "foregroundColor": _hex_to_rgb01("#FFFFFF")},
                        "horizontalAlignment": "LEFT",
                    },
                )
            )
        elif stt == "STT":
            reqs.append(
                _repeat_row_format(
                    ws,
                    i,
                    {
                        "backgroundColor": navy,
                        "textFormat": {"bold": True, "foregroundColor": _hex_to_rgb01("#FFFFFF")},
                        "horizontalAlignment": "CENTER",
                    },
                )
            )
        elif stt in ("A", "I", "II"):
            reqs.append(
                _repeat_row_format(
                    ws,
                    i,
                    {"backgroundColor": group_bg, "textFormat": {"bold": True}, "horizontalAlignment": "LEFT"},
                )
            )
        elif chi_tieu == "TỔNG CỘNG":
            reqs.append(
                _repeat_row_format(
                    ws,
                    i,
                    {"backgroundColor": total_bg, "textFormat": {"bold": True}, "horizontalAlignment": "LEFT"},
                )
            )
        elif stt == "*":
            reqs.append(
                _repeat_row_format(
                    ws,
                    i,
                    {"backgroundColor": sub_bg, "horizontalAlignment": "LEFT"},
                )
            )

    sheet_id = ws._properties["sheetId"]
    n_rows = len(rows)
    if n_rows >= 3:
        reqs.append(
            {
                "repeatCell": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": 2,
                        "endRowIndex": n_rows,
                        "startColumnIndex": 2,
                        "endColumnIndex": 4,
                    },
                    "cell": {"userEnteredFormat": {"numberFormat": {"type": "NUMBER", "pattern": "0.000"}}},
                    "fields": "userEnteredFormat.numberFormat",
                }
            }
        )
        reqs.append(
            {
                "repeatCell": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": 2,
                        "endRowIndex": n_rows,
                        "startColumnIndex": 4,
                        "endColumnIndex": 5,
                    },
                    "cell": {"userEnteredFormat": {"numberFormat": {"type": "PERCENT", "pattern": "0.0%"}}},
                    "fields": "userEnteredFormat.numberFormat",
                }
            }
        )

        tl_range = {
            "sheetId": sheet_id,
            "startRowIndex": 2,
            "endRowIndex": n_rows,
            "startColumnIndex": 4,
            "endColumnIndex": 5,
        }
        reqs.append(
            {
                "addConditionalFormatRule": {
                    "rule": {
                        "ranges": [tl_range],
                        "booleanRule": {
                            "condition": {"type": "NUMBER_LESS", "values": [{"userEnteredValue": "0.8"}]},
                            "format": {"textFormat": {"foregroundColor": _hex_to_rgb01("#C62828")}},
                        },
                    },
                    "index": 0,
                }
            }
        )
        reqs.append(
            {
                "addConditionalFormatRule": {
                    "rule": {
                        "ranges": [tl_range],
                        "booleanRule": {
                            "condition": {"type": "NUMBER_GREATER_THAN_EQ", "values": [{"userEnteredValue": "1"}]},
                            "format": {"textFormat": {"foregroundColor": _hex_to_rgb01("#2E7D32")}},
                        },
                    },
                    "index": 0,
                }
            }
        )

    if reqs:
        ws.spreadsheet.batch_update({"requests": reqs})


def _phan_loai_4_nhom(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """
    Phân tầng 4 nhóm GQVL theo quy tắc từ file thực tế.

    Quy tắc:
      - TW: dùng "Phân loại NV" (1=NSNN, 2=NHCSXH), KHÔNG dùng Mã NĐT
      - ĐP: dùng "Mã nhà đầu tư" với substring match từ ndt_dp_list

    Cột sau khi rename từ GQVL_COT_MAP:
      - "Nguồn vốn": "TW" hoặc "ĐP"
      - "Phân loại NV": 1.0 hoặc 2.0
      - "Mã nhà đầu tư": chuỗi như "INV0802140002662" hoặc NaN
    """
    cot_nv = "Nguồn vốn"           # sau rename từ GQVL_COT_MAP
    cot_pl_nv = "Phân loại NV"    # sau rename từ "PL NV"
    cot_ma_ndt = "Mã nhà đầu tư"  # giữ nguyên tên

    result: dict[str, pd.DataFrame] = {
        "cap_tinh_tw_nhcsxh": pd.DataFrame(),
        "cap_tinh_tw_nsnn": pd.DataFrame(),
        "cap_tinh": pd.DataFrame(),
        "cap_xa": pd.DataFrame(),
    }

    if df.empty:
        _LOG.info("DataFrame rong, tra ve 4 nhom rong")
        return result

    if cot_nv not in df.columns:
        _LOG.warning("Cot '%s' khong co trong GQVL. Cac cot: %s", cot_nv, list(df.columns))
        return result

    # Load ndt_dp_list từ db (dùng cho ĐP phân tầng)
    ndt_dp_list: list[str] = doc_ndt_dp_ma_list()
    _LOG.info("Danh sach ma NDT cap tinh: %s", ndt_dp_list)

    # ── Phân biệt TW vs ĐP ───────────────────────────────────────────────────
    nv_str = df[cot_nv].astype(str).str.strip()
    mask_tw = nv_str == "TW"
    mask_dp = nv_str == "ĐP"
    so_khong_xac_dinh = int((~mask_tw & ~mask_dp).sum())
    if so_khong_xac_dinh:
        _LOG.warning("Co %d dong khong xac dinh duoc Nguon von (khong phai TW/ĐP)", so_khong_xac_dinh)

    # ── Xử lý TW: phân biệt bằng Phân loại NV ─────────────────────────────────
    df_tw = df[mask_tw].copy()
    _LOG.info("Tong so dong TW: %d", len(df_tw))
    if not df_tw.empty:
        if cot_pl_nv in df_tw.columns:
            # Ép kiểu PL NV: int(float(val)) vì file lưu dạng float 1.0/2.0
            pl_vals = pd.to_numeric(df_tw[cot_pl_nv], errors="coerce")
            mask_nhcsxh = pl_vals == 2.0  # PL = 2 → NHCSXH huy động
            mask_nsnn = pl_vals == 1.0   # PL = 1 → NSNN
        else:
            _LOG.warning("Cot '%s' khong co trong TW, het xep vao NSNN", cot_pl_nv)
            mask_nhcsxh = pd.Series(False, index=df_tw.index)
            mask_nsnn = pd.Series(True, index=df_tw.index)

        result["cap_tinh_tw_nhcsxh"] = df_tw[mask_nhcsxh]
        result["cap_tinh_tw_nsnn"] = df_tw[mask_nsnn]
        _LOG.info("  TW NHCSXH (PL=2): %d dong", mask_nhcsxh.sum())
        _LOG.info("  TW NSNN (PL=1): %d dong", mask_nsnn.sum())

    # ── Xử lý ĐP: phân biệt bằng Mã nhà đầu tư (substring match) ──────────────
    df_dp = df[mask_dp].copy()
    _LOG.info("Tong so dong DP: %d", len(df_dp))
    if not df_dp.empty:
        if cot_ma_ndt in df_dp.columns:
            ma_ndt_str = df_dp[cot_ma_ndt].astype(str).str.strip()
            # Exact match: chỉ khớp khi Mã NĐT chính xác có trong danh sách
            mask_cap_tinh = ma_ndt_str.isin(ndt_dp_list)
        else:
            _LOG.warning("Cot '%s' khong co trong DP, het xep vao cap xa", cot_ma_ndt)
            mask_cap_tinh = pd.Series(False, index=df_dp.index)

        result["cap_tinh"] = df_dp[mask_cap_tinh]
        result["cap_xa"] = df_dp[~mask_cap_tinh]
        _LOG.info("  DP Cấp tỉnh (match NĐT): %d dong", mask_cap_tinh.sum())
        _LOG.info("  DP Cấp xã/khác: %d dong", (~mask_cap_tinh).sum())

    for slug, df_nhom in result.items():
        _LOG.info("Phan tang '%s': %d dong", slug, len(df_nhom))

    return result


def _tong_hop_theo_pgd(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["Ten PGD", "Tong du no", "So ho vay"])

    cot_pgd = config.COT_TEN_PGD
    cot_dn = config.COT_TONG_DU_NO
    cot_ma_kh = config.COT_MA_KH

    if cot_pgd not in df.columns:
        _LOG.warning("Cot '%s' khong co, tra ve DataFrame rong", cot_pgd)
        return pd.DataFrame(columns=["Ten PGD", "Tong du no", "So ho vay"])

    agg_dict = {"Tong du no": (cot_dn, "sum") if cot_dn in df.columns else ("__count__", "count")}
    if cot_ma_kh in df.columns:
        agg_dict["So ho vay"] = (cot_ma_kh, "nunique")
    else:
        agg_dict["So ho vay"] = (cot_pgd, "count")

    grouped = df.groupby(cot_pgd).agg(**agg_dict).reset_index()
    grouped = grouped.rename(columns={cot_pgd: "Ten PGD"})
    grouped["Tong du no"] = grouped["Tong du no"].fillna(0).astype(float)
    grouped["So ho vay"] = grouped["So ho vay"].fillna(0).astype(int)

    thutu = {ten: i for i, ten in enumerate(config.DS_PGD)}
    grouped["_order"] = grouped["Ten PGD"].map(thutu).fillna(999)
    grouped = grouped.sort_values("_order").drop(columns=["_order"])

    tong_dn = grouped["Tong du no"].sum()
    tong_ho = grouped["So ho vay"].sum()
    row_tc = pd.DataFrame([{"Ten PGD": "TONG CONG", "Tong du no": tong_dn, "So ho vay": tong_ho}])
    grouped = pd.concat([grouped, row_tc], ignore_index=True)
    return grouped


def push_th_gqvl_len_sheet() -> bool:
    try:
        import gspread

        client = _ket_noi_gsheet()
        df_hstd = _doc_hstd_parquet()
        df_gqvl = _doc_gqvl_parquet()

        from tabs.tab_khtd import _tinh_thuc_hien_theo_ct, KV_KEY_XA
        from tabs.tab_khtd_nhap import _tinh_th_gqvl_phan_tang

        kh_cn = db.doc_kv("khtd_cn")
        if not isinstance(kh_cn, dict):
            kh_cn = {}

        th_hstd_cn = _tinh_thuc_hien_theo_ct(df_hstd) if df_hstd is not None else {}
        th_gqvl_cn = _tinh_th_gqvl_phan_tang(df_gqvl) if df_gqvl is not None else {}

        rows_cn = _build_rows_kh_th(kh_cn, th_hstd_cn, th_gqvl_cn, "TOÀN CHI NHÁNH")
        rows_cn.append(["", f"Cập nhật lúc {datetime.now().strftime('%H:%M %d/%m/%Y')}", "", "", ""])

        spreadsheet = client.open_by_key(DCGIAM_SHEET_ID)

        try:
            ws_cn = spreadsheet.worksheet(SHEET_KH_TH_TONG_HOP)
        except gspread.exceptions.WorksheetNotFound:
            ws_cn = spreadsheet.add_worksheet(title=SHEET_KH_TH_TONG_HOP, rows=500, cols=8)
        ws_cn.clear()
        ws_cn.resize(rows=len(rows_cn), cols=5)
        ws_cn.update(rows_cn, value_input_option="USER_ENTERED")
        _apply_format_kh_th(ws_cn, rows_cn)

        try:
            ws_pgd = spreadsheet.worksheet(SHEET_KH_TH_THEO_PGD)
        except gspread.exceptions.WorksheetNotFound:
            ws_pgd = spreadsheet.add_worksheet(title=SHEET_KH_TH_THEO_PGD, rows=2000, cols=8)
        ws_pgd.clear()

        kh_xa = db.doc_kv(KV_KEY_XA)
        if not isinstance(kh_xa, dict):
            kh_xa = {}

        all_rows: list[list] = []
        for ten_pgd in config.DS_PGD:
            xa_list = config.PGD_XA_MAP.get(ten_pgd, [])
            kh_pgd: dict[str, float] = {}
            for xa in xa_list:
                for mk, v in kh_xa.items():
                    if not isinstance(mk, str) or "|" not in mk:
                        continue
                    xa_key, ma_key = mk.split("|", 1)
                    if str(xa_key).strip() != str(xa).strip():
                        continue
                    try:
                        kh_pgd[ma_key] = float(kh_pgd.get(ma_key, 0.0)) + float(v or 0.0)
                    except Exception:
                        continue

            if df_hstd is not None and config.COT_TEN_PGD in df_hstd.columns:
                df_hstd_pgd = df_hstd[df_hstd[config.COT_TEN_PGD].astype(str).str.strip() == str(ten_pgd).strip()]
            else:
                df_hstd_pgd = pd.DataFrame()
            th_hstd_pgd = _tinh_thuc_hien_theo_ct(df_hstd_pgd) if not df_hstd_pgd.empty else {}

            if df_gqvl is not None and config.COT_TEN_PGD in df_gqvl.columns:
                df_gqvl_pgd = df_gqvl[df_gqvl[config.COT_TEN_PGD].astype(str).str.strip() == str(ten_pgd).strip()]
            else:
                df_gqvl_pgd = pd.DataFrame()
            th_gqvl_pgd = _tinh_th_gqvl_phan_tang(df_gqvl_pgd) if not df_gqvl_pgd.empty else {}

            all_rows.extend(_build_rows_kh_th(kh_pgd, th_hstd_pgd, th_gqvl_pgd, ten_pgd))

        all_rows.append(["", f"Cập nhật lúc {datetime.now().strftime('%H:%M %d/%m/%Y')}", "", "", ""])

        ws_pgd.resize(rows=len(all_rows), cols=5)
        ws_pgd.update(all_rows, value_input_option="USER_ENTERED")
        _apply_format_kh_th(ws_pgd, all_rows)

        try:
            db.ghi_audit(
                "gen_dcgiam_sheet",
                "push_gsheet_kh_th",
                f"Push KH vs TH (CN + {len(config.DS_PGD)} PGD) lên GSheet",
            )
        except Exception:
            pass

        _LOG.info("Push KH vs TH len sheet thanh cong %d PGD", len(config.DS_PGD))
        return True
    except Exception:
        _LOG.exception("Loi push TH GQVL len sheet")
        return False


def push_kh_len_sheet(nam: int = None) -> bool:
    if nam is None:
        nam = datetime.now().year

    try:
        import gspread

        kh_data = db.doc_kv(f"kh_gqvl_cn_{nam}")
        if kh_data is None:
            _LOG.warning("Chua co KH GQVL nam %d", nam)
            return False

        pgd_data = kh_data.get("pgd", {})
        if not pgd_data:
            _LOG.warning("KH GQVL nam %d rong (khong co PGD nao)", nam)
            return False

        client = _ket_noi_gsheet()
        spreadsheet = client.open_by_key(DCGIAM_SHEET_ID)
        try:
            ws = spreadsheet.worksheet(SHEET_TAB_KH)
        except gspread.exceptions.WorksheetNotFound:
            ws = spreadsheet.add_worksheet(title=SHEET_TAB_KH, rows=100, cols=5)

        ws.clear()

        rows_data = [["Ten PGD", "KH TW (VND)", "KH DP (VND)", "KH Tong cong"]]
        tong_tw = 0
        tong_dp = 0

        for ten_pgd in config.DS_PGD:
            info = pgd_data.get(ten_pgd, {})
            kh_tw = int(info.get("kh_tw", 0))
            kh_dp = int(info.get("kh_dp", 0))
            tong = kh_tw + kh_dp
            rows_data.append([ten_pgd, kh_tw, kh_dp, int(tong)])
            tong_tw += kh_tw
            tong_dp += kh_dp

        rows_data.append(["TONG CONG", int(tong_tw), int(tong_dp), int(tong_tw + tong_dp)])

        ws.update(rows_data, value_input_option="USER_ENTERED")

        _LOG.info("Push KH GQVL nam %d len sheet thanh cong %d PGD", nam, len(pgd_data))
        return True
    except Exception:
        _LOG.exception("Loi push KH GQVL len sheet")
        return False


def main():
    parser = argparse.ArgumentParser(description="Day du lieu GQVL len Google Sheet")
    parser.add_argument("--th", action="store_true", help="Push TH GQVL len sheet")
    parser.add_argument("--kh", action="store_true", help="Push KH GQVL len sheet")
    parser.add_argument("--nam", type=int, default=None, help="Nam ke hoach (mac dinh: nam hien tai)")
    parser.add_argument("--all", action="store_true", help="Push ca TH lan KH")
    args = parser.parse_args()

    if args.all or args.th:
        ok = push_th_gqvl_len_sheet()
        print(f"TH: {'OK' if ok else 'FAIL'}")

    if args.all or args.kh:
        ok = push_kh_len_sheet(args.nam)
        print(f"KH: {'OK' if ok else 'FAIL'}")

    if not any([args.all, args.th, args.kh]):
        parser.print_help()


if __name__ == "__main__":
    main()
