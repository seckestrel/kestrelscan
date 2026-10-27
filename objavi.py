# -*- coding: utf-8 -*-
"""Napravi novo izdanje: podigni broj verzije, spakuj zip, napiši verzija.json.

Pokretanje:  python objavi.py 1.6.0 "Dodata provjera licenci" "Popravljen DKIM"

Poslije toga, ako imaš GitHub CLI:
    gh release create v1.6.0 izdanje/KestrelScan.zip izdanje/verzija.json ^
       --title "KestrelScan 1.6.0" --notes-file izdanje/opis.md

Ili na github.com: Releases -> Draft a new release -> dodaj oba fajla.
Adresa .../releases/latest/download/ uvijek pokazuje na zadnje izdanje, pa se
u alatu ništa ne mijenja.
"""
import datetime
import json
import os
import re
import shutil
import sys
import zipfile

# ----- ovdje upiši svoj GitHub, oblika korisnik/repozitorij -----
REPO = "seckestrel/kestrelscan"
# ----------------------------------------------------------------

KORIJEN = os.path.dirname(os.path.abspath(__file__))
IZLAZ = os.path.join(KORIJEN, "izdanje")
PRESKOCI = {"rezultati", "izdanje", "_prethodna", "_uvoz", "__pycache__",
            ".git", ".gitignore", "postavke.json", "build", "dist"}


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    verzija = sys.argv[1].strip().lstrip("v")
    promjene = [a.strip() for a in sys.argv[2:] if a.strip()]
    if not re.fullmatch(r"\d+(\.\d+){1,3}", verzija):
        print(f"Verzija mora biti oblika 1.6.0, dobijeno: {verzija}")
        return 1

    # --- upiši novu verziju u app.py ---
    put = os.path.join(KORIJEN, "app.py")
    with open(put, encoding="utf-8") as f:
        kod = f.read()
    stara = re.search(r'^VERZIJA\s*=\s*"([^"]+)"', kod, re.M)
    if not stara:
        print("U app.py nema reda VERZIJA = \"...\"")
        return 1
    kod = re.sub(r'^VERZIJA\s*=\s*"[^"]+"', f'VERZIJA = "{verzija}"', kod, count=1, flags=re.M)
    with open(put, "w", encoding="utf-8") as f:
        f.write(kod)
    print(f"app.py: {stara.group(1)} -> {verzija}")

    # --- spakuj ---
    shutil.rmtree(IZLAZ, ignore_errors=True)
    os.makedirs(IZLAZ)
    zp = os.path.join(IZLAZ, "KestrelScan.zip")
    broj = 0
    with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as z:
        for korijen, folderi, fajlovi in os.walk(KORIJEN):
            folderi[:] = [d for d in folderi if d not in PRESKOCI]
            for f in fajlovi:
                if f in PRESKOCI or f.endswith((".pyc", ".zip")):
                    continue
                p = os.path.join(korijen, f)
                rel = os.path.relpath(p, KORIJEN)
                z.write(p, os.path.join("kestrelscan", rel))
                broj += 1
    print(f"KestrelScan.zip: {broj} fajlova, {os.path.getsize(zp) // 1024} KB")

    # --- verzija.json ---
    podaci = {
        "verzija": verzija,
        "datum": datetime.date.today().strftime("%d.%m.%Y."),
        "promjene": promjene or ["Sitne izmjene i popravke"],
        "zip": f"https://github.com/{REPO}/releases/latest/download/KestrelScan.zip",
    }
    with open(os.path.join(IZLAZ, "verzija.json"), "w", encoding="utf-8") as f:
        json.dump(podaci, f, ensure_ascii=False, indent=2)
    with open(os.path.join(IZLAZ, "opis.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(f"- {p}" for p in podaci["promjene"]) + "\n")

    print(f"\nSve je u folderu: {IZLAZ}")
    print(f"\n  gh release create v{verzija} izdanje/KestrelScan.zip "
          f"izdanje/verzija.json --title \"KestrelScan {verzija}\" "
          f"--notes-file izdanje/opis.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
