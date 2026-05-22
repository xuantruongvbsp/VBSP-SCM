# UI Guidelines — VBSP-SCM
> Cập nhật lần cuối: 05/2026
> Áp dụng cho toàn bộ giao diện Streamlit

---

## 1. Nguyên tắc chung

- CSS inject **một lần duy nhất** vào `app.py` — áp dụng toàn hệ thống
- Không hardcode màu sắc rải rác trong từng tab
- Bảng ≥ 8 cột → dùng **HTML thuần** + `st.markdown(unsafe_allow_html=True)`
- Form nhập nhiều cột → `st.columns` + CSS inject kẻ bảng
- Không dùng `streamlit-aggrid` hay các thư viện UI nặng

---

## 2. Bảng màu chuẩn

### Header bảng theo nhóm
| Nhóm | Header dòng 1 (bg) | Header dòng 2 (bg) | Chữ |
|---|---|---|---|
| Trung ương (TW) | `#1a3a5c` | `#2d5986` | `#fff` |
| Địa phương (ĐP) | `#1D9E75` | `#5DCAA5` | `#04342C` |
| Tổng cộng | `#854F0B` | `#EF9F27` | `#412402` |
| Neutral / Chỉ tiêu | `#37474f` (bg `#f0f4fa`) | — | `#37474f` |

### Màu dòng bảng
| Dòng | Màu nền | Màu chữ |
|---|---|---|
| Chẵn | `#FFFFFF` | `#212121` |
| Lẻ | `#F5F8FC` | `#212121` |
| Nhóm (A/I/II) | `#E6F1FB` | `#0C447C` |
| Tổng cộng | `#B5D4F4` | `#042C53` |
| Hover | `#f8fafc` | — |

### Màu trạng thái
| Trạng thái | Nền | Viền | Ý nghĩa |
|---|---|---|---|
| Tốt / Đạt | `#e8f5e9` | `#4caf50` | TL% ≥ 100% |
| Cảnh báo | `#fff8e1` | `#ff9800` | TL% 50–99% |
| Nguy hiểm | `#fff3cd` | `#ffc107` | TL% < 50% hoặc chưa nhập |
| Vượt | `#ffebee` | `#c62828` | Vượt kế hoạch |

### Màu nhóm chương trình (form nhập)
```python
nhom_mau_nen = ["#eef6ff", "#eefaf3", "#fff8ee"]
# Chữ nhóm: color:#004D40; border-left:4px solid #00897B
```

---

## 3. Typography

| Thành phần | font-size | font-weight |
|---|---|---|
| Subheader | `1.1rem` | `600` |
| Header bảng dòng 1 | `0.83rem` | `500` |
| Header bảng dòng 2 | `0.82rem` | `500` |
| Dữ liệu bảng | `0.88rem` | `400` |
| Tên chương trình | `0.88rem` | `400` |
| Nhãn nhóm | `0.9rem` | `600` |
| Caption / ghi chú | `0.78rem` | `400` |
| KPI metric label | `0.8rem` | `500` |
| KPI metric value | `1.6rem` | `700` |

Font stack: `'Inter', 'Segoe UI', system-ui, sans-serif`

---

## 4. Pattern HTML Table chuẩn

Tái sử dụng pattern từ `tab_tongquan.py` (dòng 770–811):

```python
# Màu constants
H1 = "#1a3a5c"      # header nhóm
H2 = "#2d5986"      # header cột
BORDER = "#c8d8e8"  # viền

# Header dòng 1 — nhóm cột
NHOM_COT = [
    ("", 1),                    # Chỉ tiêu
    ("KẾ HOẠCH", 2),
    ("THỰC HIỆN", 2),
    ("CÒN PHẢI TH", 2),
]
header1 = "".join(
    f'<th colspan="{span}" style="background:{H1};color:#fff;'
    f'text-align:center;padding:7px 8px;border:0.5px solid {BORDER};'
    f'font-size:0.83rem;font-weight:500">{nhom}</th>'
    for nhom, span in NHOM_COT
)

# Header dòng 2 — tên cột
header2 = "".join(
    f'<th style="background:{H2};color:#fff;text-align:center;'
    f'padding:6px 8px;border:0.5px solid {BORDER};font-size:0.82rem;'
    f'white-space:nowrap">{c}</th>'
    for c in cot_hien
)

# Render rows
rows_html = ""
for i, (_, row) in enumerate(df.iterrows()):
    is_nhom = row.get("_nhom") in ("A", "I", "II")
    is_tong = row.get("_nhom") == "tong_all"
    bg = "#E6F1FB" if is_nhom else ("#B5D4F4" if is_tong else ("#fff" if i % 2 == 0 else "#F5F8FC"))
    fw = "500" if (is_nhom or is_tong) else "400"
    cells = "".join(
        f'<td style="padding:6px 10px;border:0.5px solid {BORDER};'
        f'text-align:{"left" if j == 0 else "right"};'
        f'font-weight:{fw};font-size:0.88rem">{val}</td>'
        for j, val in enumerate(row_values)
    )
    rows_html += f'<tr style="background:{bg}">{cells}</tr>\n'

# Wrapper
html_table = f"""
<div style="overflow-x:auto;margin:8px 0">
<table style="border-collapse:collapse;width:100%;
  font-family:'Inter','Segoe UI',sans-serif">
  <thead>
    <tr>{header1}</tr>
    <tr>{header2}</tr>
  </thead>
  <tbody>{rows_html}</tbody>
</table>
<p style="font-size:0.78rem;color:#6B7280;margin:4px 0 0 0">
  * Đơn vị: triệu đồng
</p>
</div>
"""
st.markdown(html_table, unsafe_allow_html=True)
```

---

## 5. CSS Kẻ bảng cho st.columns

Inject **một lần** ngay trước vòng lặp render dòng:

```python
st.markdown("""
<style>
[data-testid="stHorizontalBlock"] {
    border-bottom: 1px solid #e2e8f0 !important;
    padding: 2px 0 !important;
}
[data-testid="stHorizontalBlock"]:hover {
    background-color: #f8fafc !important;
}
</style>
""", unsafe_allow_html=True)
```

---

## 6. Header Cell Helper (`_khtd_cn_hdr_cell`)

Dùng lại hàm đã có trong `tab_khtd.py`:

```python
def _khtd_cn_hdr_cell(text, bg, color=None, bold=True) -> str:
    sty = (
        f"background-color:{bg};padding:8px 6px;border-radius:4px;"
        f"font-weight:{'600' if bold else '400'};font-size:0.88rem;"
        f"text-align:center;line-height:1.4"
        + (f";color:{color}" if color else "")
    )
    return f"<div style='{sty}'>{text}</div>"
```

---

## 7. KPI Metric Card

```python
k1, k2, k3, k4 = st.columns(4)
k1.metric("Tổng kế hoạch", f"{_fvn(tong_kh / 1e9, 3)} tỷ đồng")
k2.metric("Tổng thực hiện", f"{_fvn(tong_th / 1e9, 3)} tỷ đồng")
k3.metric("Tỷ lệ đạt KH", f"{_fvn(pct, 1)}%" if pct else "—")
k4.metric("Số CT có KH", f"{so_ct}/{tong_ct} chương trình")
```

---

## 8. Banner trạng thái

```python
if so_ct == 0:
    mau, vien, icon = "#fff3cd", "#ffc107", "🔴"
    msg = f"Chưa có kế hoạch — 0/{tong_ct} chương trình"
elif so_ct < tong_ct:
    mau, vien, icon = "#fff8e1", "#ff9800", "🟡"
    msg = f"Đã nhập {so_ct}/{tong_ct} chương trình · Tổng KH: {_fvn(tong_ty, 3)} tỷ"
else:
    mau, vien, icon = "#e8f5e9", "#4caf50", "🟢"
    msg = f"Đã nhập đủ {tong_ct}/{tong_ct} chương trình · Tổng KH: {_fvn(tong_ty, 3)} tỷ"

st.markdown(
    f"<div style='padding:8px 14px;background:{mau};border-left:4px solid {vien};"
    f"border-radius:6px;font-size:0.9rem;font-weight:500;margin-bottom:8px'>"
    f"{icon} {msg}</div>",
    unsafe_allow_html=True,
)
```

---

## 9. Padding & Spacing chuẩn

| Thành phần | Padding |
|---|---|
| Ô header bảng dòng 1 | `7px 8px` |
| Ô header bảng dòng 2 | `6px 8px` |
| Ô dữ liệu bảng | `6px 10px` |
| Nhãn nhóm chương trình | `7px 12px` |
| Banner trạng thái | `8px 14px` |
| KPI metric | `16px 20px` |
