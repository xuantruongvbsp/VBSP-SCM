"""Mock toàn bộ module streamlit để các module gốc import được khi chạy pytest."""
import sys
from pathlib import Path
from unittest.mock import MagicMock

# Mock streamlit TRƯỚC khi import bất kỳ module nào của dự án
mock_st = MagicMock()
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
