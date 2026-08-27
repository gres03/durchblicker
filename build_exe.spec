# PyInstaller-Spec fuer eine eigenstaendige durchblicker-automation.exe.
# Bauen mit: pyinstaller build_exe.spec
#
# Playwrights Treiber (playwright/driver/, enthaelt eine gebuendelte
# Node-Laufzeit fuer die Browsersteuerung -- NICHT der Chromium-Browser
# selbst, der wird beim ersten Start separat heruntergeladen, siehe
# app._stelle_chromium_sicher) muss als Datenordner mitgegeben werden,
# PyInstallers automatische Analyse findet ihn nicht von selbst.

import playwright
from pathlib import Path

playwright_dir = Path(playwright.__file__).resolve().parent

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('templates', 'templates'),
        ('fall.schema.json', '.'),
        ('synonyme.json', '.'),
        (str(playwright_dir / 'driver'), 'playwright/driver'),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='durchblicker-automation',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
