"""Session state helpers — pending merge queue và cache trạng thái upload."""
import streamlit as st

PENDING_MERGE_KEY = "upload_khnv_pending_merge"


def them_vao_hang_cho(loai: str) -> None:
    queue: set[str] = st.session_state.setdefault(PENDING_MERGE_KEY, set())
    queue.add(loai)


def lay_hang_cho() -> set[str]:
    return st.session_state.get(PENDING_MERGE_KEY, set())


def xoa_hang_cho() -> None:
    st.session_state.pop(PENDING_MERGE_KEY, None)


def xoa_cache_trang_thai() -> None:
    st.session_state.pop("trang_thai_upload_pgd", None)
    for k in [k for k in st.session_state if k.startswith("_blcache_")]:
        st.session_state.pop(k, None)


def lam_moi_du_lieu_app() -> None:
    """
    Buộc app.py nạp lại parquet sau merge/upload.
    Chỉ cache_data.clear() không đủ — _load_hstd dùng @st.cache_resource
  và app.py giữ _ctx khi _ctx_cache_key khớp _data_version.
    """
    try:
        st.cache_data.clear()
    except Exception:
        pass
    try:
        st.cache_resource.clear()
    except Exception:
        pass
    for _k in (
        "_ctx",
        "_ctx_cache_key",
        "_pgd_map_cache_ts",
        "_pgd_xa_map_cached",
        "_ds_pgd_all_cached",
        "_pgd_op_mtime_ss",
        "df_full",
    ):
        st.session_state.pop(_k, None)
