# -*- coding: utf-8 -*-
"""Napravi opis za .exe — ono što Windows pokaže u Svojstvima fajla.

Pokreće se sam iz NAPRAVI_EXE.bat. Verziju čita iz app.py, da ne bude dva
mjesta za održavanje.
"""
import re
import os

KORIJEN = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(KORIJEN, "app.py"), encoding="utf-8") as f:
    VERZIJA = re.search(r'VERZIJA\s*=\s*"([^"]+)"', f.read()).group(1)

d = [int(x) for x in VERZIJA.split(".")]
while len(d) < 4:
    d.append(0)
cetvorka = ", ".join(str(x) for x in d[:4])

OPIS = f"""VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({cetvorka}), prodvers=({cetvorka}),
    mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0,
    date=(0, 0)),
  kids=[
    StringFileInfo([
      StringTable(
        '040904B0',
        [StringStruct('CompanyName', 'KestrelSec — Dragomir Babic'),
         StringStruct('FileDescription', 'KestrelScan — sigurnosni pregled za male firme'),
         StringStruct('FileVersion', '{VERZIJA}'),
         StringStruct('InternalName', 'KestrelScan'),
         StringStruct('LegalCopyright', 'KestrelSec, kestrelsec.io'),
         StringStruct('OriginalFilename', 'KestrelScan.exe'),
         StringStruct('ProductName', 'KestrelScan'),
         StringStruct('ProductVersion', '{VERZIJA}')])
    ]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"""

with open(os.path.join(KORIJEN, "opis_exe.txt"), "w", encoding="utf-8") as f:
    f.write(OPIS)
print(f"opis_exe.txt napravljen za verziju {VERZIJA}")
