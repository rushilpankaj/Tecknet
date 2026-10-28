# PyInstaller build: one folder (dist\TecknetControl), which starts faster and
# uses less memory than a single-file exe, and is what the installer packs.
import re
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files
from PyInstaller.utils.win32.versioninfo import (
    FixedFileInfo, StringFileInfo, StringStruct, StringTable, VarFileInfo, VarStruct, VSVersionInfo,
)

root = Path(SPECPATH)
version = re.search(r'__version__ = "([^"]+)"', (root / "tecknet_control" / "__init__.py").read_text()).group(1)
numbers = tuple(int(part) for part in version.split(".")) + (0,)

version_info = VSVersionInfo(
    ffi=FixedFileInfo(filevers=numbers, prodvers=numbers),
    kids=[
        StringFileInfo([StringTable("040904B0", [
            StringStruct("ProductName", "Tecknet Control"),
            StringStruct("FileDescription", "Tecknet Control"),
            StringStruct("FileVersion", version),
            StringStruct("ProductVersion", version),
            StringStruct("OriginalFilename", "TecknetControl.exe"),
            StringStruct("LegalCopyright", "MIT License"),
        ])]),
        VarFileInfo([VarStruct("Translation", [1033, 1200])]),
    ],
)

a = Analysis(
    ["TecknetControl.pyw"],
    pathex=[str(root)],
    datas=collect_data_files("customtkinter") + [("assets/icon.ico", "assets")],
    hiddenimports=["winrt.windows.devices.bluetooth", "pystray._win32"],
    excludes=["numpy", "unittest", "pydoc", "test"],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="TecknetControl",
    icon="assets/icon.ico",
    version=version_info,
    console=False,
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="TecknetControl", upx=False)
