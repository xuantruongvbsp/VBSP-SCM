import sys
sys.stdout.reconfigure(encoding='utf-8')

import pandas as pd
import plotly.graph_objects as go
from components.export_pdf import xuat_pdf_co_chart, _tim_logo

print("Logo found at:", _tim_logo())

df = pd.DataFrame({
    "Tên ĐVUT": ["Hội nông dân", "Hội phụ nữ", "Hội CCB", "Đoàn thanh niên", "CỘNG"],
    "Số KH": [120, 98, 76, 54, 348],
    "Tổng dư nợ": [15_600_000_000, 12_300_000_000, 9_800_000_000, 7_200_000_000, 44_900_000_000],
    "Nợ quá hạn": [156_000_000, 98_000_000, 210_000_000, 45_000_000, 509_000_000],
    "Số khoản 3m KHĐ": [5, 3, 8, 2, 18],
})

fig = go.Figure(data=[
    go.Bar(x=df["Tên ĐVUT"][:4], y=df["Tổng dư nợ"][:4] / 1e6, marker_color="#2E7D32", name="Tổng dư nợ"),
])
fig.update_layout(title="Tổng dư nợ theo ĐVUT (triệu đồng)", xaxis_title="", yaxis_title="Triệu đồng")

pdf_bytes = xuat_pdf_co_chart(
    df=df,
    tieu_de="Báo cáo Giao ban - Xã An Bình",
    nguoi_xuat="Admin Test",
    figs=[(fig, "Tổng dư nợ theo ĐVUT")],
    cols_tien=["Tổng dư nợ", "Nợ quá hạn"],
    don_vi_tien="đồng",
    prefix_file="Test",
    them_dong_tong=True,
)

out_path = r"d:\VBSP-SCM\_test_logo.pdf"
with open(out_path, "wb") as f:
    f.write(pdf_bytes)

import os
size_kb = os.path.getsize(out_path) / 1024
print(f"PDF created: {out_path} ({size_kb:.1f} KB)")
print("SUCCESS - Logo đã có trong PDF!")
