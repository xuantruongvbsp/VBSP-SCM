#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse
import sys
from pathlib import Path
from datetime import datetime

import pandas as pd

from config import (
    DCGIAM_SHEET_ID,
    DCGIAM_CRED_FILE,
    GQVL_PHAN_TANG,
    COT_NGUON_VON,
    COT_MA_NHA_DAU_TU,
    COT_PL_NV,
    COT_MA_CHUONG_TRINH,
    COT_TEN_PGD,
    COT_MA_KH,
    COT_TEN_KH,
    COT_SO_KU,
    COT_NGAY_VAY,
    COT_NGAY_DH,
    COT_TEN_CT,
    COT_TEN_TO,
    COT_TEN_XA,
    COT_MUC_VAY,
    COT_DU_NO_TH,
    COT_DU_NO_QH,
    COT_TONG_DU_NO,
    COT_TEN_THON,
    COT_NGAY_SL,
    FILE_PATH,
    FILE_PATH_GQVL,
    FILE_PATH_SK_GQVL,
)

try:
    import gspread
    from oauth2client.service_account import ServiceAccountCredentials
    GSPREAD_READY = True
except ImportError:
    GSPREAD_READY = False


NDT_CAP_TINH = [
    "NDT000000129", "NDT000000138", "NDT000000141",
    "NDT000000131", "NDT000000142", "NDT000000134",
]


def _phan_loai_4_nhom(row: pd.Series) -> str:
    nv = str(row.get(COT_NGUON_VON, "")).strip().upper()
    pl = str(row.get(COT_PL_NV, "")).strip()
    ma_ndt = str(row.get(COT_MA_NHA_DAU_TU, "")).strip()

    if nv == "TW":
        if pl == "2":
            return "3_TW_NHCSXH"
        return "3_TW_NSNN"
    else:
        if ma_ndt in NDT_CAP_TINH:
            return "3_DP_TINH"
        return "3_DP_XA"


def push_th_gqvl_to_sheet():
    if not GSPREAD_READY:
        print("Thieu thu vien gspread. Chay: pip install gspread oauth2client")
        return

    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name(DCGIAM_CRED_FILE, scope)
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(DCGIAM_SHEET_ID)

    df = pd.read_excel(FILE_PATH_GQVL, sheet_name=0, dtype=str)
    if FILE_PATH_SK_GQVL:
        df_sk = pd.read_excel(FILE_PATH_SK_GQVL, sheet_name=0, dtype=str)
        df = pd.concat([df, df_sk], ignore_index=True)

    df["phan_tang"] = df.apply(_phan_loai_4_nhom, axis=1)
    df[COT_NGAY_SL] = datetime.now().strftime("%d/%m/%Y")

    cols_gui = [
        COT_TEN_PGD, COT_TEN_XA, COT_TEN_THON, COT_TEN_TO,
        COT_MA_KH, COT_TEN_KH, COT_SO_KU, COT_NGAY_VAY,
        COT_NGAY_DH, COT_TEN_CT, COT_MUC_VAY, COT_DU_NO_TH,
        COT_DU_NO_QH, COT_TONG_DU_NO, "phan_tang", COT_NGAY_SL,
    ]

    for nhom, _, _, _ in GQVL_PHAN_TANG:
        sub = df[df["phan_tang"] == nhom]
        sub = sub[cols_gui].fillna("")
        data = [list(sub.columns)] + sub.values.tolist()

        try:
            ws = sh.worksheet(nhom)
            ws.clear()
        except gspread.WorksheetNotFound:
            ws = sh.add_worksheet(title=nhom, rows=len(data), cols=len(cols_gui))

        ws.update(range_name="A1", values=data)
        print(f"OK: {nhom} ({len(sub)} dong)")


def push_kh_gqvl_to_sheet(nam: int):
    if not GSPREAD_READY:
        print("Thieu thu vien gspread. Chay: pip install gspread oauth2client")
        return

    from db import kv_get
    import json

    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name(DCGIAM_CRED_FILE, scope)
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(DCGIAM_SHEET_ID)

    kh_data_str = kv_get(f"kh_gqvl_{nam}")
    if not kh_data_str:
        print(f"Khong tim thay KH GQVL nam {nam}")
        return

    kh_data = json.loads(kh_data_str)
    df = pd.DataFrame(kh_data)

    for nhom, _, _, _ in GQVL_PHAN_TANG:
        sub = df[df["phan_tang"] == nhom] if "phan_tang" in df.columns else df
        if sub.empty:
            continue
        sub = sub.fillna("")
        col_names = list(sub.columns)
        data = [col_names] + sub.values.tolist()

        try:
            ws = sh.worksheet(f"KH_{nam}_{nhom}")
            ws.clear()
        except gspread.WorksheetNotFound:
            ws = sh.add_worksheet(title=f"KH_{nam}_{nhom}", rows=len(data), cols=len(col_names))

        if not data:
            continue
        ws.update(range_name="A1", values=data)
        print(f"OK: KH_{nam}_{nhom} ({len(sub)} dong)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Push GQVL du lieu giam / dieu chinh toi Google Sheet")
    parser.add_argument("--th", action="store_true", help="Push TH (thuc hien) GQVL")
    parser.add_argument("--kh", action="store_true", help="Push KH (ke hoach) GQVL")
    parser.add_argument("--nam", type=int, default=datetime.now().year, help="Nam KH")

    args = parser.parse_args()

    if args.th:
        push_th_gqvl_to_sheet()
    elif args.kh:
        push_kh_gqvl_to_sheet(args.nam)
    else:
        print("Vui long chon --th hoac --kh")
        sys.exit(1)
