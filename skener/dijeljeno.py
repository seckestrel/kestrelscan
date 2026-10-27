# -*- coding: utf-8 -*-
"""Dijeljeni folderi — lokalni i na mreži.

Dijeljeni folder otvoren za Everyone je najčešći način da ransomware
sa jedne mašine pokupi podatke cijele firme.
"""
import json
import re
import subprocess
import sys

from .nalaz import nalaz, VISOK, SREDNJI, NIZAK, INFO, DOBRO

JE_WINDOWS = sys.platform.startswith("win")

SISTEMSKI = {"ADMIN$", "IPC$", "print$", "NETLOGON", "SYSVOL"}


def _ps(skripta, timeout=60):
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


def _mrezni_dijeljeni(ip, timeout=12):
    """Pokuša izlistati dijeljene foldere na udaljenoj mašini bez lozinke."""
    if not JE_WINDOWS:
        return []
    try:
        r = subprocess.run(["net", "view", f"\\\\{ip}"], capture_output=True,
                           text=True, timeout=timeout, errors="replace",
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if r.returncode != 0:
            return []
        imena = []
        for linija in (r.stdout or "").splitlines():
            m = re.match(r"^(\S+)\s+Disk", linija)
            if m and m.group(1) not in SISTEMSKI:
                imena.append(m.group(1))
        return imena
    except Exception:
        return []


def provjeri(mrezni_uredjaji=None, log=lambda s: None):
    nalazi, sirovo = [], {}

    if not JE_WINDOWS:
        nalazi.append(nalaz(
            "Podaci", "Provjera dijeljenih foldera nije izvršena", INFO,
            "Ova provjera radi samo na Windowsu.",
            preporuka="Pokrenuti alat na mašini klijenta."))
        return {"nalazi": nalazi, "sirovo": sirovo}

    log("Dijeljeni folderi na ovoj mašini")
    shares = _ps("Get-SmbShare | Select-Object Name,Path,Description | "
                 "ConvertTo-Json -Compress")
    if shares:
        shares = shares if isinstance(shares, list) else [shares]
        korisnicki = [s for s in shares if s.get("Name") not in SISTEMSKI
                      and not str(s.get("Name", "")).endswith("$")]
        sirovo["lokalni"] = korisnicki

        otvoreni = []
        for s in korisnicki:
            prava = _ps(f"Get-SmbShareAccess -Name '{s['Name']}' | "
                        "Select-Object AccountName,AccessRight,AccessControlType | "
                        "ConvertTo-Json -Compress", timeout=25)
            if not prava:
                continue
            prava = prava if isinstance(prava, list) else [prava]
            s["prava"] = prava
            for p in prava:
                nalog = str(p.get("AccountName") or "")
                if nalog.lower() in ("everyone", "svi", "builtin\\users",
                                     "nt authority\\authenticated users"):
                    if str(p.get("AccessControlType")).lower() in ("0", "allow"):
                        otvoreni.append((s["Name"], s.get("Path"), nalog,
                                         p.get("AccessRight")))

        if otvoreni:
            nalazi.append(nalaz(
                "Podaci", "Dijeljeni folderi su otvoreni za sve", VISOK,
                "Folderi dostupni svima na mreži: "
                + ", ".join(sorted({o[0] for o in otvoreni})),
                "Svako ko dođe na mrežu — uključujući gosta na WiFi-ju i zaraženi "
                "uređaj — može čitati i mijenjati te fajlove. Ovako se ransomware "
                "širi sa jedne mašine na podatke cijele firme.",
                "Ukinuti pristup grupi Everyone i dodijeliti prava imenovanim "
                "korisnicima ili grupama, odvojeno za čitanje i izmjenu.",
                sati=2, trosak=120,
                dokaz=[f"{i} ({p}) — {n}: {pr}" for i, p, n, pr in otvoreni]))
        elif korisnicki:
            nalazi.append(nalaz(
                "Podaci", "Dijeljeni folderi imaju kontrolisan pristup", DOBRO,
                f"Provjereno {len(korisnicki)} dijeljenih foldera, nijedan nije "
                "otvoren za sve.",
                dokaz=[f'{s["Name"]} → {s.get("Path")}' for s in korisnicki]))
        else:
            nalazi.append(nalaz("Podaci", "Nema korisničkih dijeljenih foldera", DOBRO,
                                "Na ovoj mašini nema dijeljenih foldera osim sistemskih."))

    # --- dijeljeni folderi na drugim uređajima iz popisa mreže ---
    if mrezni_uredjaji:
        smb = [u["ip"] for u in mrezni_uredjaji
               if any(p["port"] == 445 for p in u.get("portovi", []))][:12]
        if smb:
            log(f"Provjeravam dijeljene foldere na {len(smb)} uređaja")
            nadjeno = {}
            for ip in smb:
                imena = _mrezni_dijeljeni(ip)
                if imena:
                    nadjeno[ip] = imena
            sirovo["mrezni"] = nadjeno
            if nadjeno:
                redovi = [f"{ip}: {', '.join(v)}" for ip, v in nadjeno.items()]
                nalazi.append(nalaz(
                    "Podaci", "Dijeljeni folderi vidljivi bez prijave", VISOK,
                    f"Na {len(nadjeno)} uređaja je spisak dijeljenih foldera "
                    "dostupan bez ikakve prijave.",
                    "Napadač na mreži tako odmah zna gdje su podaci, bez ijedne "
                    "ukradene lozinke. To je prvi korak u svakom upadu.",
                    "Isključiti anonimno izlistavanje i provjeriti prava pristupa "
                    "na svakom od navedenih uređaja.",
                    sati=2, trosak=120, dokaz=redovi))

    return {"nalazi": nalazi, "sirovo": sirovo}
