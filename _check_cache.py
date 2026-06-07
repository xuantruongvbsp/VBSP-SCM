import os
from pathlib import Path
from datetime import datetime

cache = Path('d:/VBSP-SCM/cache')
for f in sorted(cache.glob('hstd*')):
    size_mb = f.stat().st_size / 1024 / 1024
    mtime = datetime.fromtimestamp(f.stat().st_mtime)
    print(f'{f.name}: {size_mb:.1f} MB - {mtime.strftime("%d/%m %H:%M:%S")}')
