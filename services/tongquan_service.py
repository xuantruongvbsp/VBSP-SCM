"""Service: các hàm thuần túy cho tab Tổng quan (không có st.* calls)."""
from __future__ import annotations

from io import BytesIO

import pandas as pd


def xuat_excel_tqpgd(df: pd.DataFrame, ten_file: str) -> bytes:
    """Xuất df_show TQPGD ra Excel với định dạng đẹp."""
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter

    _ = ten_file
    df_xuat = df.copy()
    cols_pct = [c for c in df_xuat.columns if "%" in str(c)]
    for c in cols_pct:
        df_xuat[c] = pd.to_numeric(df_xuat[c], errors="coerce") / 100.0

    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df_xuat.to_excel(writer, sheet_name="Tổng quan PGD", index=False)
        ws = writer.sheets["Tổng quan PGD"]

        header_fill = PatternFill("solid", fgColor="003D7A")
        header_font = Font(bold=True, color="FFFFFF", size=10)
        center = Alignment(horizontal="center", vertical="center", wrap_text=True)
        left = Alignment(horizontal="left", vertical="center")
        right = Alignment(horizontal="right", vertical="center")
        thin = Side(style="thin", color="CCCCCC")
        border = Border(left=thin, right=thin, top=thin, bottom=thin)

        for cell in ws[1]:
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = center
            cell.border = border

        COT_SO = [
            "Số KH",
            "Dư nợ (triệu đồng)",
            "QH (triệu đồng)",
            "TL QH %",
            "Khoanh (triệu đồng)",
            "TL Khoanh %",
            "Nợ xấu (triệu đồng)",
            "TL NPL %",
            "Lãi tồn (triệu đồng)",
            "Nợ ĐH năm (triệu đồng)",
            "DS Cho vay (triệu đồng)",
            "DS Thu nợ (triệu đồng)",
            "Tổng Tổ",
            "Tốt",
            "Khá",
            "TB",
            "Yếu",
        ]
        col_names = [cell.value for cell in ws[1]]

        for row in ws.iter_rows(min_row=2, max_row=ws.max_row):
            for cell in row:
                col_name = col_names[cell.column - 1]
                cell.border = border
                if col_name == df_xuat.columns[0]:
                    cell.alignment = left
                    cell.font = Font(bold=True, size=10)
                elif col_name in COT_SO:
                    cell.alignment = right
                    cell.font = Font(size=10)
                    if "%" in str(col_name):
                        cell.number_format = "0.00%"
                    elif col_name == "Số KH" or col_name in ["Tổng Tổ", "Tốt", "Khá", "TB", "Yếu"]:
                        cell.number_format = "#,##0"
                    else:
                        cell.number_format = "#,##0.000"
                else:
                    cell.alignment = center
                    cell.font = Font(size=10)

        alt_fill = PatternFill("solid", fgColor="EEF4FB")
        for i, row in enumerate(ws.iter_rows(min_row=2, max_row=ws.max_row), start=1):
            if i % 2 == 0:
                for cell in row:
                    if not cell.fill or cell.fill.fgColor.rgb == "00000000":
                        cell.fill = alt_fill

        for col_idx, col_cells in enumerate(ws.columns, start=1):
            max_len = max((len(str(c.value)) if c.value is not None else 0) for c in col_cells)
            ws.column_dimensions[get_column_letter(col_idx)].width = min(max_len + 4, 30)

        ws.freeze_panes = "B2"

    return buf.getvalue()
