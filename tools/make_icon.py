"""Write assets/icon.ico from the icon drawn in tecknet_control/icons.py."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tecknet_control.icons import app_icon, save_ico  # noqa: E402

assets = ROOT / "assets"
assets.mkdir(exist_ok=True)
save_ico(assets / "icon.ico")
app_icon(256).save(assets / "icon.png")
print("Written", assets / "icon.ico")
