"""Mock toàn bộ module streamlit để các module gốc import được khi chạy pytest."""
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd


def _noop_cache(*args, **kwargs):
    """No-op cache decorator — trả về function gốc, không cache gì cả."""
    if args and callable(args[0]):
        func = args[0]
        func.clear = lambda: None
        return func
    def _decorator(f):
        f.clear = lambda: None
        return f
    return _decorator
_noop_cache.clear = lambda: None  # cho st.cache_data.clear()


def _mock_selectbox(label, options=None, index=None, **kwargs):
    """Mock st.selectbox() — trả về item đầu tiên của options."""
    if options is not None:
        if isinstance(options, (list, tuple)) and len(options) > 0:
            return options[0]
        try:
            return options[0]
        except (TypeError, IndexError, KeyError):
            return 0
    return 0


def _mock_multiselect(label, options=None, default=None, **kwargs):
    """Mock st.multiselect() — trả về list rỗng."""
    return []


def _mock_date_input(label, value=None, **kwargs):
    """Mock st.date_input() — trả về hôm nay."""
    from datetime import date
    return date.today()


def _mock_columns(columns_arg, *args, **kwargs):
    """Mock st.columns() — trả về list Mock theo số lượng cột yêu cầu."""
    n = columns_arg if isinstance(columns_arg, int) else len(columns_arg)
    return [MagicMock() for _ in range(n)]


def _mock_tabs(labels, *args, **kwargs):
    """Mock st.tabs() — trả về list Mock theo số lượng tab."""
    return [MagicMock() for _ in range(len(labels))]


class _SessionState(dict):
    """Dict hỗ trợ cả attribute access (st.session_state.foo = ...)."""
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)
    def __setattr__(self, name, value):
        self[name] = value


# Mock streamlit TRƯỚC khi import bất kỳ module nào của dự án
mock_st = MagicMock()
mock_st.cache_data = _noop_cache
mock_st.cache_resource = _noop_cache
mock_st.columns = _mock_columns
mock_st.tabs = _mock_tabs
mock_st.selectbox = _mock_selectbox
mock_st.multiselect = _mock_multiselect
mock_st.date_input = _mock_date_input
mock_st.text_input = lambda label=None, **kw: ""
mock_st.number_input = lambda label=None, **kw: 0
mock_st.text_area = lambda label=None, **kw: ""
mock_st.slider = lambda label=None, **kw: 0
mock_st.radio = lambda label=None, options=None, **kw: (options[0] if options and len(options) > 0 else "")
mock_st.checkbox = lambda label=None, **kw: False
class _FakeFile:
    """File giả có size, seek, read, name — hỗ trợ for-loop (accept_multiple_files)."""
    def __init__(self):
        self.name = "mock.xlsx"
        self.size = 0
        self._data = b"mock"
        self._pos = 0
    def read(self, n=-1):
        if n == -1:
            return self._data
        return self._data[:n]
    def seek(self, offset, whence=0):
        if whence == 0:
            self._pos = offset
        elif whence == 1:
            self._pos += offset
        elif whence == 2:
            self._pos = len(self._data) + offset
        return self._pos
    def __iter__(self):
        return iter([self])

mock_st.file_uploader = lambda label=None, **kw: None
mock_st.data_editor = lambda data=None, **kw: pd.DataFrame() if data is None else (data.copy() if isinstance(data, pd.DataFrame) else data)
mock_st.dataframe = lambda data=None, **kw: None
mock_st.button = lambda label=None, **kw: False
mock_st.form_submit_button = lambda label=None, **kw: False
mock_st.download_button = lambda *a, **kw: None
mock_st.container = lambda **kw: MagicMock()
mock_st.empty = lambda **kw: MagicMock()
mock_st.expander = lambda label=None, **kw: MagicMock()
mock_st.sidebar = MagicMock()
mock_st.sidebar.selectbox = lambda label=None, options=None, **kw: (options[0] if options and len(options) > 0 else "")
mock_st.sidebar.radio = lambda label=None, options=None, **kw: (options[0] if options and len(options) > 0 else "")
mock_st.sidebar.checkbox = lambda label=None, **kw: False
sys.modules["streamlit"] = mock_st

# Mock streamlit.components.v1
sys.modules["streamlit.components.v1"] = MagicMock()
sys.modules["streamlit.components"] = MagicMock()

# Mock streamlit.delta_generator (dùng trong tab_so_sanh_ky.py)
sys.modules["streamlit.delta_generator"] = MagicMock()
sys.modules["streamlit.delta_generator"].DeltaGenerator = MagicMock()

# Thêm thư mục gốc vào sys.path để import được các module gốc
ROOT_DIR = Path(__file__).parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
