import pandas as pd

from utils import fmt, fmt_tien, pick_hstd_column


def test_pick_hstd_column_exact_match() -> None:
    df = pd.DataFrame(columns=["Số khế ước", "Tên xã"])
    assert pick_hstd_column(df, "Tên xã") == "Tên xã"


def test_pick_hstd_column_case_insensitive_match() -> None:
    df = pd.DataFrame(columns=["Tên Thôn"])
    assert pick_hstd_column(df, "tên thôn") == "Tên Thôn"


def test_pick_hstd_column_not_found() -> None:
    df = pd.DataFrame(columns=["A"])
    assert pick_hstd_column(df, "B") is None


def test_pick_hstd_column_prioritize_first_candidate() -> None:
    df = pd.DataFrame(columns=["Tên xã", "Tên thôn"])
    assert pick_hstd_column(df, "Tên thôn", "Tên xã") == "Tên thôn"


def test_fmt_positive() -> None:
    assert fmt(123_456) == "123.456"


def test_fmt_negative() -> None:
    assert fmt(-123_456) == "-123.456"


def test_fmt_zero() -> None:
    assert fmt(0) == "—"


def test_fmt_none() -> None:
    assert fmt(None) == "—"


def test_fmt_tien_trieu() -> None:
    assert fmt_tien(12_000_000) == "12,0 triệu đồng"


def test_fmt_tien_ty() -> None:
    assert fmt_tien(1_000_000_000) == "1 tỷ đồng"
