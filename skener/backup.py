# -*- coding: utf-8 -*-
"""Prepoznavanje backup softvera i kad je zadnji put nešto zaista odrađeno.

Ne zamjenjuje test vraćanja — ali hvata najčešći slučaj: backup koji stoji
mjesecima a niko ne zna.
"""
import datetime
import json
import re
import subprocess
import sys

from .nalaz import nalaz, VISOK, SREDNJI, NIZAK, INFO, DOBRO

JE_WINDOWS = sys.platform.startswith("win")

POZNATI = [
    "veeam", "acronis", "macrium", "paragon backup", "easeus todo",
    "aomei backupper", "iperius", "urbackup", "duplicati", "cobian",
    "nakivo", "altaro", "arcserve", "veritas", "backup exec",
    "synology active backup", "qnap netbak", "handy backup", "genie",
    "idrive", "backblaze", "carbonite", "datto", "shadowprotect",
    "windows server backup", "restic", "kopia",
]

# cloud sinhronizacija — korisna, ali nije backup
SINHRONIZACIJA = ["onedrive", "google drive", "dropbox", "mega", "pcloud",
                  "nextcloud", "box sync", "icloud"]


def _ps(skripta, timeout=90):
    if not JE_WINDOWS:
        return None
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy",
             "Bypass", "-Command", skripta],
            capture_output=True, text=True, timeout=timeout,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        izlaz = (r.stdout or "").strip()
        return json.loads(izlaz) if izlaz else None
    except Exception:
        return None


def _datum(v):
    if not v:
        return None
    m = re.search(r"(\d{10,13})", str(v))
    if m:
        try:
            return datetime.datetime.fromtimestamp(int(m.group(1)[:13]) / 1000)
        except Exception:
            return None
    try:
        return datetime.datetime.strptime(str(v)[:19], "%Y-%m-%dT%H:%M:%S")
    except Exception:
        return None


def provjeri(programi=None, log=lambda s: None):
    """programi: lista iz skener.softver (da se ne čita registar dvaput)."""
    nalazi, sirovo = [], {}

    if not JE_WINDOWS:
        nalazi.append(nalaz(
            "Backup", "Provjera backup softvera nije izvršena", INFO,
            "Ova provjera radi samo na Windowsu.",
            preporuka="Pokrenuti alat na mašini klijenta."))
        return {"nalazi": nalazi, "sirovo": sirovo}

    # --- instalirani programi ---
    log("Tražim backup softver")
    if programi is None:
        programi = _ps(r"""
$k = @('HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*',
       'HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*')
Get-ItemProperty $k -ErrorAction SilentlyContinue |
  Where-Object {$_.DisplayName} |
  Select-Object DisplayName,DisplayVersion |
  Sort-Object DisplayName -Unique | ConvertTo-Json -Compress
""") or []
    imena = [str(p.get("DisplayName") or "") for p in programi]

    nadjeni = sorted({n for n in imena
                      if any(p in n.lower() for p in POZNATI)})
    sinhro = sorted({n for n in imena
                     if any(p in n.lower() for p in SINHRONIZACIJA)})
    sirovo["backup_softver"] = nadjeni
    sirovo["sinhronizacija"] = sinhro

    # --- ugrađeni Windows backup ---
    log("Evidencija ugrađenog backupa")
    wb = _ps("""
$e = Get-WinEvent -LogName 'Microsoft-Windows-Backup' -MaxEvents 20 -ErrorAction SilentlyContinue
if ($e) {
  $e | Select-Object -First 5 TimeCreated,Id,LevelDisplayName | ConvertTo-Json -Compress
} else { '[]' }
""")
    if wb:
        wb = wb if isinstance(wb, list) else [wb]
        sirovo["windows_backup"] = wb

    # --- zakazani zadaci koji liče na backup ---
    log("Zakazani zadaci")
    zadaci = _ps(r"""
$z = Get-ScheduledTask -ErrorAction SilentlyContinue |
  Where-Object { $_.TaskName -match 'backup|arhiv|kopij|veeam|acronis|macrium' }
$r = @()
foreach ($t in $z) {
  $i = $t | Get-ScheduledTaskInfo -ErrorAction SilentlyContinue
  $r += [pscustomobject]@{
    naziv = $t.TaskName
    stanje = [string]$t.State
    zadnji = $i.LastRunTime
    ishod = $i.LastTaskResult
  }
}
if ($r) { $r | ConvertTo-Json -Compress } else { '[]' }
""")
    if zadaci:
        zadaci = zadaci if isinstance(zadaci, list) else [zadaci]
        sirovo["zadaci"] = zadaci
    else:
        zadaci = []

    # --- nalazi ---
    if not nadjeni and not zadaci and not sirovo.get("windows_backup"):
        poruka = "Na mašini nije pronađen nijedan backup program ni zakazan zadatak."
        if sinhro:
            poruka += (" Pronađena je samo cloud sinhronizacija: "
                       + ", ".join(sinhro) + ".")
        nalazi.append(nalaz(
            "Backup", "Nema tragova backup rješenja", VISOK, poruka,
            "Sinhronizacija nije backup — ona odražava stanje. Ako se fajl "
            "obriše ili šifruje, ta izmjena se prenese na sve kopije. Bez pravog "
            "backupa kvar ili ransomware znače trajan gubitak."
            if sinhro else
            "Bez backupa kvar diska, ransomware ili krađa znače trajan gubitak "
            "podataka. Ne postoji način da se vrate.",
            "Uvesti backup po pravilu 3-2-1-1-0 i obavezno testirati vraćanje.",
            sati=4, trosak=240,
            dokaz=sinhro or ["nijedan poznati backup program nije instaliran"]))
        return {"nalazi": nalazi, "sirovo": sirovo}

    if nadjeni:
        nalazi.append(nalaz(
            "Backup", "Backup softver je instaliran", INFO,
            "Pronađeno: " + ", ".join(nadjeni),
            preporuka="Instaliran program ne znači da backup radi. Obavezno "
                      "provjeriti kad je zadnji put uspješno završio i testirati "
                      "vraćanje jednog fajla.",
            dokaz=nadjeni))

    # --- stanje zakazanih zadataka ---
    danas = datetime.datetime.now()
    stari, pali, dobri = [], [], []
    for z in zadaci:
        d = _datum(z.get("zadnji"))
        ishod = z.get("ishod")
        opis = f'{z.get("naziv")} — stanje {z.get("stanje")}'
        if d:
            dana = (danas - d).days
            opis += f', zadnji put {d.strftime("%d.%m.%Y.")} ({dana} dana)'
            if dana > 14:
                stari.append(opis)
            elif ishod not in (0, None):
                pali.append(opis + f", ishod {ishod}")
            else:
                dobri.append(opis)
        else:
            stari.append(opis + ", nikad pokrenut")

    if pali:
        nalazi.append(nalaz(
            "Backup", "Backup zadatak završava greškom", VISOK,
            "; ".join(pali),
            "Zadatak se pokreće ali ne završava uspješno. Backup formalno "
            "postoji, a kopije nema — to je najgora moguća kombinacija jer "
            "stvara lažan osjećaj sigurnosti.",
            "Utvrditi razlog greške, popraviti i uključiti obavještenje na mail "
            "pri svakom neuspjehu.",
            sati=2, trosak=120, dokaz=pali))

    if stari:
        nalazi.append(nalaz(
            "Backup", "Backup zadatak dugo nije odrađen", VISOK,
            "; ".join(stari),
            "Backup je stao, a niko nije primijetio. Ako se danas nešto desi, "
            "vraća se stanje od prije više od dvije sedmice — ili ništa.",
            "Utvrditi kad je i zašto stao, pokrenuti ručno, pa uključiti "
            "obavještenje o neuspjehu.",
            sati=2, trosak=120, dokaz=stari))

    if dobri and not (pali or stari):
        nalazi.append(nalaz(
            "Backup", "Backup zadatak se redovno izvršava", DOBRO,
            "; ".join(dobri),
            preporuka="Redovno izvršavanje ne znači da se podaci mogu vratiti. "
                      "Test vraćanja je i dalje obavezan.",
            dokaz=dobri))

    if sinhro and nadjeni:
        nalazi.append(nalaz(
            "Backup", "Uz backup postoji i cloud sinhronizacija", INFO,
            "Pronađeno: " + ", ".join(sinhro),
            preporuka="Sinhronizacija je korisna za dostupnost, ali se ne računa "
                      "kao kopija — izmjena i brisanje se prenose na sve uređaje."))

    return {"nalazi": nalazi, "sirovo": sirovo}
