"""
gen_dcgiam_sheet.py
─────────────────
Script độc lập đẩy dữ liệu GQVL lên Google Sheet để theo dõi
KH vs TH phân tầng TW/ĐP.

Cách dùng:
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
import gspread
from oauth2client.service_account import ServiceAccountCredentials

import db
import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
_LOG = logging.getLogger(__name__)

DCGIAM_SHEET_ID = "15Ev2rTv6khLFaMpAiMwqJCVC_33ocJ-6cp016RGNkYk"
CREDENTIALS_FILE = "credentials.json"
SHEET_TAB_GQVL = "GQVL"
SHEET_TAB_KH = "KH_GQVL"

GQVL_PARQUET = Path("cache") / "gqvl.parquet"


def _ket_noi_gsheet():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]
    if not Path(CREDENTIALS_FILE).exists():
        raise FileNotFoundError(
            f"Không tìm thấy file credentials: {CREDENTIALS_FILE}"
        )
    creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, scope)
    return gspread.authorize(creds)


def _doc_gqvl_parquet() -> pd.DataFrame:
    if not GQVL_PARQUET.exists():
        raise FileNotFoundError(
            f"Không tìm thấy file parquet: {GQVL_PARQUET}. "
            "Hãy upload và merge GQVL trước khi chạy script này."
        )
    df = pd.read_parquet(GQVL_PARQUET)
    _LOG.info("Đọc %d dòng từ %s", len(df), GQVL_PARQUET)
    return df


def _phan_loai_tw_dp(df: pd.DataFrame):
    cot_ct = config.COT_TEN_CT
    ds_tw = [ten for _mk, _ma_ct, ten, nv, _ten_match in config.CHUONG_TRINH_KHTD if nv == "TW"]
    ds_dp = [ten for _mk, _ma_ct, ten, nv, _ten_match in config.CHUONG_TRINH_KHTD if nv == "DP"]

    if cot_ct not in df.columns:
        _LOG.warning("Cột '%s' không có trong DataFrame. Các cột hiện có: %s", cot_ct, list(df.columns))
        df_tw = pd.DataFrame()
        df_dp = pd.DataFrame()
        return df_tw, df_dp

    df_tw = df[df[cot_ct].isin(ds_tw)]
    df_dp = df[df[cot_ct].isin(ds_dp)]
    so_khong_khop = len(df) - len(df_tw) - len(df_dp)
    _LOG.info("Phân loại: TW=%d dòng, ĐP=%d dòng, Không khớp=%d dòng", len(df_tw), len(df_dp), so_khong_khop)
    return df_tw, df_dp


def _tong_hop_theo_pgd(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["Tên PGD", "Tổng dư nợ", "Số hộ vay"])

    cot_pgd = config.COT_TEN_PGD
    cot_dn = config.COT_TONG_DU_NO
    cot_ma_kh = config.COT_MA_KH

    if cot_pgd not in df.columns:
        _LOG.warning("Cột '%s' không có, trả về DataFrame rỗng", cot_pgd)
        return pd.DataFrame(columns=["Tên PGD", "Tổng dư nợ", "Số hộ vay"])

    agg_dict = {"Tổng dư nợ": (cot_dn, "sum") if cot_dn in df.columns else ("__count__", "count")}
    if cot_ma_kh in df.columns:
        agg_dict["Số hộ vay"] = (cot_ma_kh, "nunique")
    else:
        agg_dict["Số hộ vay"] = (cot_pgd, "count")

    grouped = df.groupby(cot_pgd).agg(**agg_dict).reset_index()
    grouped = grouped.rename(columns={cot_pgd: "Tên PGD"})
    grouped["Tổng dư nợ"] = grouped["Tổng dư nợ"].fillna(0).astype(float)
    grouped["Số hộ vay"] = grouped["Số hộ vay"].fillna(0).astype(int)

    thutu = {ten: i for i, ten in enumerate(config.DS_PGD)}
    grouped["_order"] = grouped["Tên PGD"].map(thutu).fillna(999)
    grouped = grouped.sort_values("_order").drop(columns=["_order"])

    tong_dn = grouped["Tổng dư nợ"].sum()
    tong_ho = grouped["Số hộ vay"].sum()
    row_tc = pd.DataFrame([{"Tên PGD": "TỔNG CỘNG", "Tổng dư nợ": tong_dn, "Số hộ vay": tong_ho}])
    grouped = pd.concat([grouped, row_tc], ignore_index=True)
    return grouped


def push_th_gqvl_len_sheet() -> bool:
    try:
        client = _ket_noi_gsheet()
        df_full = _doc_gqvl_parquet()
        df_tw, df_dp = _phan_loai_tw_dp(df_full)

        bang_tw = _tong_hop_theo_pgd(df_tw)
        bang_dp = _tong_hop_theo_pgd(df_dp)

        spreadsheet = client.open_by_key(DCGIAM_SHEET_ID)
        try:
            ws = spreadsheet.worksheet(SHEET_TAB_GQVL)
        except gspread.exceptions.WorksheetNotFound:
            ws = spreadsheet.add_worksheet(title=SHEET_TAB_GQVL, rows=100, cols=10)

        ws.clear()

        header1 = ["", "NGUỒN VỐN TRUNG ƯƠNG (TW)", "", "", "NGUỒN VỐN ĐỊA PHƯƠNG (ĐP)", "", ""]
        header2 = ["Tên PGD", "Tổng dư nợ TW", "Số hộ TW", "", "Tổng dư nợ ĐP", "Số hộ ĐP", "Tổng cộng"]

        ds_pgd = config.DS_PGD + ["TỔNG CỘNG"]
        rows_data = [header1, header2]

        tw_map = {}
        for _, row in bang_tw.iterrows():
            tw_map[row["Tên PGD"]] = (row["Tổng dư nợ"], row["Số hộ vay"])

        dp_map = {}
        for _, row in bang_dp.iterrows():
            dp_map[row["Tên PGD"]] = (row["Tổng dư nợ"], row["Số hộ vay"])

        for ten_pgd in ds_pgd:
            dn_tw, ho_tw = tw_map.get(ten_pgd, (0, 0))
            dn_dp, ho_dp = dp_map.get(ten_pgd, (0, 0))
            dn_tw = int(dn_tw)
            dn_dp = int(dn_dp)
            tong_cong = int(dn_tw + dn_dp)
            rows_data.append([ten_pgd, dn_tw, ho_tw, "", dn_dp, ho_dp, tong_cong])

        ws.update(rows_data, value_input_option="USER_ENTERED")

        timestamp = datetime.now().strftime("Cập nhật lúc %H:%M %d/%m/%Y")
        ws.update_acell("A40", timestamp)

        _LOG.info("Push TH GQVL lên sheet thành công — %d PGD", len(config.DS_PGD))
        return True
    except Exception:
        _LOG.exception("Lỗi push TH GQVL lên sheet")
        return False


def push_kh_len_sheet(nam: int = None) -> bool:
    if nam is None:
        nam = datetime.now().year

    try:
        kh_data = db.doc_kv(f"kh_gqvl_cn_{nam}")
        if kh_data is None:
            _LOG.warning("Chưa có KH GQVL năm %d", nam)
            return False

        pgd_data = kh_data.get("pgd", {})
        if not pgd_data:
            _LOG.warning("KH GQVL năm %d rỗng (không có PGD nào)", nam)
            return False

        client = _ket_noi_gsheet()
        spreadsheet = client.open_by_key(DCGIAM_SHEET_ID)
        try:
            ws = spreadsheet.worksheet(SHEET_TAB_KH)
        except gspread.exceptions.WorksheetNotFound:
            ws = spreadsheet.add_worksheet(title=SHEET_TAB_KH, rows=100, cols=5)

        ws.clear()

        rows_data = [["Tên PGD", "KH TW (VND)", "KH ĐP (VND)", "KH Tổng cộng"]]
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

        rows_data.append(["TỔNG CỘNG", int(tong_tw), int(tong_dp), int(tong_tw + tong_dp)])

        ws.update(rows_data, value_input_option="USER_ENTERED")

        _LOG.info("Push KH GQVL năm %d lên sheet thành công — %d PGD", nam, len(pgd_data))
        return True
    except Exception:
        _LOG.exception("Lỗi push KH GQVL lên sheet")
        return False


def main():
    parser = argparse.ArgumentParser(description="Đẩy dữ liệu GQVL lên Google Sheet")
    parser.add_argument("--th", action="store_true", help="Push TH GQVL lên sheet")
    parser.add_argument("--kh", action="store_true", help="Push KH GQVL lên sheet")
    parser.add_argument("--nam", type=int, default=None, help="Năm kế hoạch (mặc định: năm hiện tại)")
    parser.add_argument("--all", action="store_true", help="Push cả TH lẫn KH")
    args = parser.parse_args()

    if args.all or args.th:
        ok = push_th_gqvl_len_sheet()
        print(f"TH: {'✅ OK' if ok else '❌ FAIL'}")

    if args.all or args.kh:
        ok = push_kh_len_sheet(args.nam)
        print(f"KH: {'✅ OK' if ok else '❌ FAIL'}")

    if not any([args.all, args.th, args.kh]):
        parser.print_help()


if __name__ == "__main__":
    main()
