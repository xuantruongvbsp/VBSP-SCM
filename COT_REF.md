# COT_REF — Tra cứu nhanh tên cột

> Tách từ rules.md để tiết kiệm token. Agent chỉ đọc khi cần dùng tên cột.
> Mọi tên cột đều định nghĩa trong `config.py`. Dùng COT_*, không hardcode tiếng Việt.

---

## Core

```python
COT_TEN_PGD      = "Tên PGD"
COT_MA_KH        = "Mã KH"
COT_TEN_KH       = "Tên KH"
COT_SO_KU        = "Số khế ước"
COT_NGAY_VAY     = "Ngày vay"
COT_NGAY_DH      = "Ngày ĐH theo Gia hạn"
COT_NGAY_DH_HD   = "Ngày ĐH theo hợp đồng"
COT_THOI_HAN     = "Thời hạn vay"
COT_LAI_SUAT     = "Lãi suất"
COT_MUC_VAY      = "Mức vay"
COT_DU_NO_TH     = "Dư nợ trong hạn"
COT_DU_NO_QH     = "Dư nợ quá hạn"
COT_TONG_DU_NO   = "Tổng dư nợ"
COT_DU_NO_KHOANH = "Dư nợ khoanh"
COT_TEN_CT       = "Tên chương trình"
COT_TINH_TRANG   = "Tình trạng món vay"
COT_DIA_CHI      = "Địa chỉ"
COT_SDT          = "Số điện thoại"       # KHÔNG dùng COT_DIEN_THOAI
COT_NGAY_SL      = "Ngày số liệu"
COT_GOC_TRA      = "Gốc đã trả"
```

## Extended

```python
COT_CMND              = "Số CMND"
COT_TEN_TO            = "Tên tổ"          # KHÔNG dùng COT_TEN_TKVV
COT_TEN_XA            = "Tên xã"
COT_TEN_THON          = "Tên thôn"
COT_NGUON_VON         = "Nguồn vốn"       # 1=TW, 2=ĐP
COT_MA_CHUONG_TRINH   = "Mã chương trình"
COT_PL_NV             = "Phân loại NV"    # KHÔNG hardcode "PL NV"
COT_MA_NHA_DAU_TU     = "Mã nhà đầu tư"
COT_TEN_NHA_DAU_TU    = "Tên nhà đầu tư"
COT_TEN_TO_TRUONG     = "Tên tổ trưởng"
```

## Personal

```python
COT_NGAY_SINH        = "Ngày sinh"
COT_NGAY_CAP_CMND    = "Ngày cấp CMND"
COT_NOI_CAP_CMND     = "Nơi cấp CMND"
COT_NGAY_HH_KHOANH   = "Ngày hết hạn khoanh"
COT_TEN_HSSV         = "Họ tên HSSV"
COT_TEN_VC           = "Họ tên vợ/chồng"
COT_HINH_THUC_VAY    = "Hình thức vay"
```

## NQ11

```python
COT_DNO_NQ11          = "Dư nợ gốc NQ11"
COT_NQ11_NO_TH        = "Nợ trong hạn NQ11"
COT_NQ11_NO_QH        = "Nợ quá hạn NQ11"
COT_NQ11_MA_KH        = "Mã KH NQ11"
COT_NQ11_TEN_KH       = "Tên KH NQ11"
COT_NQ11_SO_TIEN      = "Số tiền NQ11"
COT_NQ11_DU_NO        = "Dư nợ NQ11"
COT_NQ11_SO_TIEN_GN   = "Số tiền giải ngân NQ11"
COT_NQ11_DEN_HAN_SC   = "Đến hạn sổ cuối NQ11"
COT_NQ11_NGAY_BC      = "Ngày báo cáo NQ11"
```

## GQVL

```python
COT_GQVL_MA_PGD       = "Mã PGD GQVL"
COT_GQVL_DU_NO_KHOANH = "Dư nợ khoanh GQVL"
```

## Risk / Activity

```python
COT_LAI_TON    = "Lãi tồn TH"
COT_LAI_TON_QH = "Lãi tồn QH"
COT_LAI_THANG  = "Lãi DT trong tháng"
COT_DVUT       = "Tên ĐVUT"
```
