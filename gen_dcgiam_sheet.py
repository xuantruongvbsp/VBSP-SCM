
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
import gspread
from oauth2client.service_account import ServiceAccountCredentials

import db
import config
from db import doc_ndt_dp_ma_list

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
_LOG = logging.getLogger(__name__)

DCGIAM_SHEET_ID = "15Ev2rTv6khLFaMpAiMwqJCVC_33ocJ-6cp016RGNkYk"
CREDENTIALS_FILE = "credentials.json"
SHEET_TAB_GQVL = "GQVL"
SHEET_TAB_KH = "KH_GQVL"

GQVL_PARQUET = Path(config.CACHE_GQVL)


def _ket_noi_gsheet():
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
        client = _ket_noi_gsheet()
        df_full = _doc_gqvl_parquet()
        nhom_dict = _phan_loai_4_nhom(df_full)

        bang_nhcsxh = _tong_hop_theo_pgd(nhom_dict["cap_tinh_tw_nhcsxh"])
        bang_nsnn = _tong_hop_theo_pgd(nhom_dict["cap_tinh_tw_nsnn"])
        bang_cap_tinh = _tong_hop_theo_pgd(nhom_dict["cap_tinh"])
        bang_cap_xa = _tong_hop_theo_pgd(nhom_dict["cap_xa"])

        spreadsheet = client.open_by_key(DCGIAM_SHEET_ID)
        try:
            ws = spreadsheet.worksheet(SHEET_TAB_GQVL)
        except gspread.exceptions.WorksheetNotFound:
            ws = spreadsheet.add_worksheet(title=SHEET_TAB_GQVL, rows=100, cols=10)

        ws.clear()

        header1 = [
            "",
            "TW \u2014 NHCSXH huy dong", "", "TW \u2014 NSNN (Quy QG TW)", "",
            "DP \u2014 Cap tinh", "", "DP \u2014 Cap xa/khac", "", "",
        ]
        header2 = [
            "Ten PGD",
            "Du no", "So ho",
            "Du no", "So ho",
            "Du no", "So ho",
            "Du no", "So ho",
            "Tong cong",
        ]

        ds_pgd = config.DS_PGD + ["TONG CONG"]
        rows_data = [header1, header2]

        def _build_map(bang):
            m = {}
            for _, row in bang.iterrows():
                m[row["Ten PGD"]] = (row["Tong du no"], row["So ho vay"])
            return m

        map_nhcsxh = _build_map(bang_nhcsxh)
        map_nsnn = _build_map(bang_nsnn)
        map_tinh = _build_map(bang_cap_tinh)
        map_xa = _build_map(bang_cap_xa)

        for ten_pgd in ds_pgd:
            dn_nhcsxh, ho_nhcsxh = map_nhcsxh.get(ten_pgd, (0, 0))
            dn_nsnn, ho_nsnn = map_nsnn.get(ten_pgd, (0, 0))
            dn_tinh, ho_tinh = map_tinh.get(ten_pgd, (0, 0))
            dn_xa, ho_xa = map_xa.get(ten_pgd, (0, 0))
            dn_nhcsxh = int(dn_nhcsxh)
            dn_nsnn = int(dn_nsnn)
            dn_tinh = int(dn_tinh)
            dn_xa = int(dn_xa)
            tong_cong = dn_nhcsxh + dn_nsnn + dn_tinh + dn_xa
            rows_data.append([
                ten_pgd,
                dn_nhcsxh, int(ho_nhcsxh),
                dn_nsnn, int(ho_nsnn),
                dn_tinh, int(ho_tinh),
                dn_xa, int(ho_xa),
                tong_cong,
            ])

        ws.update(rows_data, value_input_option="USER_ENTERED")

        timestamp = datetime.now().strftime("Cap nhat luc %H:%M %d/%m/%Y")
        ws.update_acell("A40", timestamp)

        _LOG.info("Push TH GQVL len sheet thanh cong %d PGD", len(config.DS_PGD))
        return True
    except Exception:
        _LOG.exception("Loi push TH GQVL len sheet")
        return False


def push_kh_len_sheet(nam: int = None) -> bool:
    if nam is None:
        nam = datetime.now().year

    try:
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
