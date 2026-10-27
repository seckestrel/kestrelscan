# -*- coding: utf-8 -*-
"""Instalirani softver, alati za daljinski pristup, lozinke u pregledaču, makroi."""
import json
import os
import subprocess
import sys

from .nalaz import nalaz, VISOK, SREDNJI, NIZAK, INFO, DOBRO

JE_WINDOWS = sys.platform.startswith("win")

# alati za daljinski pristup — legitimni, ali svaki je i vrata u sistem
DALJINSKI = ["teamviewer", "anydesk", "ammyy", "supremo", "radmin", "vnc",
             "logmein", "gotoassist", "splashtop", "chrome remote desktop",
             "dameware", "screenconnect", "connectwise", "rustdesk", "atera"]

# softver koji se po pravilu zatiče zastario i nosi poznate propuste
RIZICNO = {
    "java": "Java se rijetko ažurira, a propusti se objavljuju redovno",
    "adobe flash": "Flash je ugašen 2020. i više ne dobija zakrpe",
    "adobe shockwave": "Shockwave je ugašen i ne dobija zakrpe",
    "quicktime": "QuickTime za Windows je napušten 2016.",
    "winrar": "Starije verzije WinRAR-a imaju poznate propuste u obradi arhiva",
    "python 2": "Python 2 nema podršku od 2020.",
    "internet explorer": "Internet Explorer više ne dobija zakrpe",
    "utorrent": "Dijeljenje fajlova na poslovnoj mašini nosi i pravni i tehnički rizik",
}

PREGLEDACI = {
    "Chrome": r"Google\Chrome\User Data\Default\Login Data",
    "Edge": r"Microsoft\Edge\User Data\Default\Login Data",
    "Brave": r"BraveSoftware\Brave-Browser\User Data\Default\Login Data",
}


def _ps(skripta, timeout=90):
    if not JE_WINDOWS:
        return None
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
             "-Command", skripta],
            capture_output=True, text=True, timeout=timeout,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        izlaz = (r.stdout or "").strip()
        return json.loads(izlaz) if izlaz else None
    except Exception:
        return None


def _broj_lozinki(putanja):
    """Broj sačuvanih prijava u pregledaču — bez čitanja samih lozinki."""
    try:
        import shutil
        import sqlite3
        import tempfile
        tmp = os.path.join(tempfile.gettempdir(), "ks_logins.db")
        shutil.copy2(putanja, tmp)
        v = sqlite3.connect(tmp)
        n = v.execute("SELECT COUNT(*) FROM logins").fetchone()[0]
        v.close()
        os.remove(tmp)
        return n
    except Exception:
        return None


def provjeri(log=lambda s: None):
    nalazi, sirovo = [], {}

    if not JE_WINDOWS:
        nalazi.append(nalaz(
            "Uređaji", "Provjera instaliranog softvera nije izvršena", INFO,
            "Ova provjera radi samo na Windowsu.",
            preporuka="Pokrenuti alat na mašini klijenta."))
        return {"nalazi": nalazi, "sirovo": sirovo}

    log("Instalirani programi")
    programi = _ps(r"""
$k = @('HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*',
       'HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*',
       'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*')
Get-ItemProperty $k -ErrorAction SilentlyContinue |
  Where-Object {$_.DisplayName} |
  Select-Object DisplayName,DisplayVersion,Publisher,InstallDate |
  Sort-Object DisplayName -Unique | ConvertTo-Json -Compress
""")
    if programi:
        programi = programi if isinstance(programi, list) else [programi]
        sirovo["programi"] = programi
        imena = [(p.get("DisplayName") or "", p.get("DisplayVersion") or "")
                 for p in programi]

        nalazi.append(nalaz(
            "Uređaji", f"Instalirano {len(imena)} programa", INFO,
            "Popis instaliranog softvera na mašini.",
            dokaz=[f"{n}  {v}".strip() for n, v in imena[:60]]))

        # --- daljinski pristup ---
        nadjeni = sorted({n for n, _ in imena
                          if any(d in n.lower() for d in DALJINSKI)})
        if nadjeni:
            nalazi.append(nalaz(
                "Lozinke i pristupi", "Instalirani alati za daljinski pristup", SREDNJI,
                "Pronađeno: " + ", ".join(nadjeni),
                "Svaki od ovih alata je otvoren put u mašinu spolja. Često ih "
                "ostave serviseri i niko ih poslije ne ukloni. Napadači ih "
                "svjesno koriste jer ne izgledaju sumnjivo.",
                "Utvrditi ko i zašto koristi svaki od njih. Nepotrebne ukloniti. "
                "Za potrebne postaviti lozinku i dvofaktorsku zaštitu i uključiti "
                "obavještenje pri svakoj udaljenoj prijavi.",
                sati=1.5, trosak=90, dokaz=nadjeni))

        # --- rizičan softver ---
        rizicni = []
        for n, v in imena:
            for kljuc, zasto in RIZICNO.items():
                if kljuc in n.lower():
                    rizicni.append((f"{n} {v}".strip(), zasto))
                    break
        if rizicni:
            nalazi.append(nalaz(
                "Uređaji", "Instaliran softver sa poznatim propustima", SREDNJI,
                "Pronađeno: " + ", ".join(sorted({r[0] for r in rizicni})),
                "; ".join(sorted({r[1] for r in rizicni})) + ".",
                "Ukloniti sa mašina gdje nije neophodan. Gdje jeste, ažurirati na "
                "podržanu verziju i provjeriti sa dobavljačem aplikacije.",
                sati=2, trosak=120, dokaz=[r[0] for r in rizicni]))

    # --- lozinke u pregledaču ---
    log("Lozinke sačuvane u pregledaču")
    lokal = os.environ.get("LOCALAPPDATA", "")
    ukupno, detalji = 0, []
    for ime, rel in PREGLEDACI.items():
        p = os.path.join(lokal, rel)
        if os.path.isfile(p):
            n = _broj_lozinki(p)
            if n:
                ukupno += n
                detalji.append(f"{ime}: {n} sačuvanih prijava")
    sirovo["lozinke_pregledac"] = detalji
    if ukupno:
        nalazi.append(nalaz(
            "Lozinke i pristupi", "Lozinke se čuvaju u pregledaču", SREDNJI,
            f"Ukupno {ukupno} sačuvanih prijava. " + "; ".join(detalji),
            "Lozinke iz pregledača se izvlače jednostavnim alatom čim neko dođe "
            "do otključane mašine ili pokrene zlonamjerni program pod tim "
            "korisnikom. To je prvi cilj svakog zaraznog programa.",
            "Prebaciti lozinke u menadžer lozinki i isključiti čuvanje u pregledaču.",
            sati=2, trosak=120, dokaz=detalji))

    # --- Office makroi ---
    log("Postavke makroa u Officeu")
    makroi = _ps(r"""
$r = @()
Get-ChildItem 'HKCU:\Software\Microsoft\Office' -ErrorAction SilentlyContinue |
 ForEach-Object {
   $v = $_.PSChildName
   foreach ($app in 'Word','Excel','PowerPoint') {
     $p = "HKCU:\Software\Microsoft\Office\$v\$app\Security"
     if (Test-Path $p) {
       $w = (Get-ItemProperty $p -ErrorAction SilentlyContinue).VBAWarnings
       if ($w -ne $null) { $r += [pscustomobject]@{App="$app $v"; VBAWarnings=$w} }
     }
   }
 }
if ($r) { $r | ConvertTo-Json -Compress } else { '[]' }
""")
    if makroi:
        makroi = makroi if isinstance(makroi, list) else [makroi]
        sirovo["makroi"] = makroi
        # 1 = svi makroi dozvoljeni bez upozorenja
        opasni = [m for m in makroi if str(m.get("VBAWarnings")) == "1"]
        if opasni:
            nalazi.append(nalaz(
                "Uređaji", "Office pokreće makroe bez upozorenja", VISOK,
                "Pogođeno: " + ", ".join(str(m.get("App")) for m in opasni),
                "Dokument sa makroom iz maila se izvršava bez ijednog pitanja. "
                "To je i dalje jedan od najčešćih načina na koji ransomware uđe "
                "u malu firmu.",
                "Postaviti blokiranje makroa iz interneta kroz GPO ili postavke "
                "Office centra za pouzdanost.",
                sati=1, trosak=60,
                dokaz=[f'{m.get("App")}: VBAWarnings={m.get("VBAWarnings")}'
                       for m in makroi]))

    return {"nalazi": nalazi, "sirovo": sirovo}
