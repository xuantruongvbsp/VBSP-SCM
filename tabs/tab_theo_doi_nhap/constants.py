"""Hằng số dùng cho module Theo dõi Nhập liệu."""

KV_LIST_KEY = "gsheet_theo_doi_nhap_list"
KV_LEGACY_KEY = "gsheet_theo_doi_nhap_config"
KV_SNAPSHOT_PREFIX = "tdn_snapshot_"
KV_DCTT_CONFIG_KEY = "tdn_dctt_config"

DEFAULT_CT = [
    {"ten": "HSSV", "col": 4},
    {"ten": "Nước sạch", "col": 8},
    {"ten": "Việc làm", "col": 13},
]

EMOJI_PCT = {"full": "🟢", "partial": "🟡", "empty": "🔴"}

LOAI_OPTIONS = {
    "phan_cap_stt": "📊 Phân cấp STT — STT chữ La Mã = PGD, STT số = xã/phường con",
    "phang": "📋 Phẳng — mỗi hàng = 1 đơn vị, không có hàng con",
    "cot_pgd": "🗂 Cột PGD riêng — có cột ghi tên PGD cho mỗi hàng",
}

LOAI_LABEL = {
    "phan_cap_stt": "phân cấp STT",
    "phang": "phẳng",
    "cot_pgd": "cột PGD",
}

CACHE_TTL = 300

MOCKUP_HTML = """
<div style="font-size:12px; border:1px solid var(--border-color,#ccc); border-radius:8px; overflow:auto; padding:12px;">
  <div style="margin-bottom:8px; font-weight:600;">📌 Cấu trúc Google Sheet được hỗ trợ</div>
  <table style="border-collapse:collapse; width:100%; font-size:11px;">
    <tr style="background:var(--secondary-background-color,#f0f2f6);">
      <td style="border:1px solid #ccc;padding:4px 8px;font-weight:600;">Hàng</td>
      <td style="border:1px solid #ccc;padding:4px 8px;font-weight:600;">Cột 1 (STT)</td>
      <td style="border:1px solid #ccc;padding:4px 8px;font-weight:600;">Cột 2 (Tên đơn vị)</td>
      <td style="border:1px solid #ccc;padding:4px 8px;font-weight:600;">Cột 3</td>
      <td style="border:1px solid #ccc;padding:4px 8px;font-weight:600; color:#e67e22;">Cột 4 ← theo dõi</td>
      <td style="border:1px solid #ccc;padding:4px 8px;font-weight:600;">Cột 5</td>
    </tr>
    <tr>
      <td style="border:1px solid #ccc;padding:4px 8px; color:#888;">1–7</td>
      <td colspan="5" style="border:1px solid #ccc;padding:4px 8px; color:#888; font-style:italic;">Tiêu đề, chú thích... (bỏ qua)</td>
    </tr>
    <tr style="background:#fff3cd;">
      <td style="border:1px solid #ccc;padding:4px 8px; font-weight:600;">8 ← Header row</td>
      <td style="border:1px solid #ccc;padding:4px 8px;">STT</td>
      <td style="border:1px solid #ccc;padding:4px 8px;">Tên PGD / xã</td>
      <td style="border:1px solid #ccc;padding:4px 8px;">KH đã giao</td>
      <td style="border:1px solid #ccc;padding:4px 8px; color:#e67e22; font-weight:600;">Điều chỉnh tăng trưởng</td>
      <td style="border:1px solid #ccc;padding:4px 8px;">Nợ đến hạn</td>
    </tr>
    <tr style="background:#d4edda;">
      <td style="border:1px solid #ccc;padding:4px 8px;">9</td>
      <td style="border:1px solid #ccc;padding:4px 8px; font-weight:600; color:#86efac;">I ← chữ = PGD</td>
      <td style="border:1px solid #ccc;padding:4px 8px; font-weight:600; color:#86efac;">Hội sở chi nhánh tỉnh</td>
      <td style="border:1px solid #ccc;padding:4px 8px;">92.539</td>
      <td style="border:1px solid #ccc;padding:4px 8px; color:#e67e22;">0</td>
      <td style="border:1px solid #ccc;padding:4px 8px;"></td>
    </tr>
    <tr>
      <td style="border:1px solid #ccc;padding:4px 8px;">10</td>
      <td style="border:1px solid #ccc;padding:4px 8px; color:#80CBC4;">1 ← số = xã</td>
      <td style="border:1px solid #ccc;padding:4px 8px; color:#80CBC4;">Phường Phước Tân</td>
      <td style="border:1px solid #ccc;padding:4px 8px;">4.336</td>
      <td style="border:1px solid #ccc;padding:4px 8px; color:#e67e22;"></td>
      <td style="border:1px solid #ccc;padding:4px 8px;"></td>
    </tr>
    <tr>
      <td style="border:1px solid #ccc;padding:4px 8px;">11</td>
      <td style="border:1px solid #ccc;padding:4px 8px; color:#80CBC4;">2</td>
      <td style="border:1px solid #ccc;padding:4px 8px; color:#80CBC4;">Phường Biên Hòa</td>
      <td style="border:1px solid #ccc;padding:4px 8px;">14.662</td>
      <td style="border:1px solid #ccc;padding:4px 8px; color:#e67e22;"></td>
      <td style="border:1px solid #ccc;padding:4px 8px;"></td>
    </tr>
    <tr style="background:#d4edda;">
      <td style="border:1px solid #ccc;padding:4px 8px;">...</td>
      <td style="border:1px solid #ccc;padding:4px 8px; font-weight:600; color:#86efac;">II ← chữ = PGD tiếp</td>
      <td style="border:1px solid #ccc;padding:4px 8px; font-weight:600; color:#86efac;">PGD Long Thành</td>
      <td style="border:1px solid #ccc;padding:4px 8px;">...</td>
      <td style="border:1px solid #ccc;padding:4px 8px;">...</td>
      <td style="border:1px solid #ccc;padding:4px 8px;">...</td>
    </tr>
  </table>
  <div style="margin-top:10px; display:flex; gap:16px; flex-wrap:wrap; font-size:11px;">
    <span>🟡 <b>Header row</b> = hàng chứa tên cột (STT, Tên PGD...)</span>
    <span>🟢 <b>Hàng PGD</b> = Cột STT là chữ La Mã (I, II, III...)</span>
    <span>🔵 <b>Hàng xã/phường</b> = Cột STT là số (1, 2, 3...)</span>
    <span>🟠 <b>Cột theo dõi</b> = Cột cần kiểm tra đã điền chưa</span>
  </div>
  <div style="margin-top:8px; font-size:11px; color:#888;">
    💡 Mở sheet → đếm số cột từ trái sang phải để biết số cột (A=1, B=2, C=3...)
  </div>
</div>
"""
