import config


def test_ds_pgd_has_21_items_excluding_hoi_so() -> None:
    assert len(config.DS_PGD) == 21
    assert "Hội sở Chi nhánh tỉnh" not in config.DS_PGD


def test_don_vi_chi_nhanh_not_empty() -> None:
    assert isinstance(config.DON_VI_CHI_NHANH, str)
    assert config.DON_VI_CHI_NHANH.strip() != ""


def test_pgd_xa_map_has_keys_for_all_pgd_in_ds_pgd() -> None:
    missing = set(config.DS_PGD) - set(config.PGD_XA_MAP.keys())
    assert missing == set()


def test_each_pgd_in_pgd_xa_map_has_at_least_one_xa() -> None:
    for pgd, ds_xa in config.PGD_XA_MAP.items():
        assert isinstance(ds_xa, list)
        assert len(ds_xa) >= 1


def test_total_number_of_xa_is_95() -> None:
    assert len(config.DS_XA) == 95
