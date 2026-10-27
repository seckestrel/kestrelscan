# -*- coding: utf-8 -*-
"""Inventar računara i laptopa na mreži, sa procjenom za zamjenu.

Podaci se povlače sa udaljenih mašina kroz WMI preko DCOM-a — isti put kojim
radi svaka Windows administratorska konzola. Traži administratorski nalog na
tim mašinama (u domenu obično domenski administrator).
"""
import datetime
import json
import os
import re
import subprocess
import sys

from .nalaz import nalaz, VISOK, SREDNJI, NIZAK, INFO, DOBRO
from . import starost as m_starost
from .hardver import TIP_RAM, _vrsta_diska

JE_WINDOWS = sys.platform.startswith("win")

# Win32_ComputerSystem.PCSystemType
TIP = {1: "Stoni", 2: "Prenosivi", 3: "Radna stanica", 4: "Server",
       5: "Server", 6: "Mini PC", 7: "Server", 8: "Tablet"}

SKRIPTA = r"""
$ErrorActionPreference = 'SilentlyContinue'
$mete = METE_OVDJE
$opt  = New-CimSessionOption -Protocol Dcom
$cred = $null
if ($env:KS_KORISNIK) {
  $tajna = ConvertTo-SecureString $env:KS_LOZINKA -AsPlainText -Force
  $cred  = New-Object System.Management.Automation.PSCredential($env:KS_KORISNIK, $tajna)
}
$izlaz = @()
foreach ($m in $mete) {
  try {
    if ($cred) { $s = New-CimSession -ComputerName $m -SessionOption $opt -Credential $cred -OperationTimeoutSec 12 }
    else       { $s = New-CimSession -ComputerName $m -SessionOption $opt -OperationTimeoutSec 12 }
    if (-not $s) { $izlaz += [pscustomobject]@{ip=$m; greska='nema pristupa'}; continue }

    $cs   = Get-CimInstance Win32_ComputerSystem  -CimSession $s
    $bios = Get-CimInstance Win32_BIOS            -CimSession $s
    $cpu  = Get-CimInstance Win32_Processor       -CimSession $s | Select-Object -First 1
    $os   = Get-CimInstance Win32_OperatingSystem -CimSession $s
    $disk = Get-CimInstance Win32_DiskDrive       -CimSession $s | Select-Object -First 1
    $mem  = Get-CimInstance Win32_PhysicalMemory  -CimSession $s
    $memTip = ($mem | Select-Object -Expand SMBIOSMemoryType -Unique) -join "/"
    $memMhz = ($mem | Measure-Object -Property ConfiguredClockSpeed -Maximum).Maximum
    $pd   = Get-CimInstance MSFT_PhysicalDisk -Namespace root\Microsoft\Windows\Storage -CimSession $s | Select-Object -First 1

    $izlaz += [pscustomobject]@{
      ip          = $m
      ime         = $cs.Name
      proizvodjac = $cs.Manufacturer
      model       = $cs.Model
      tip         = $cs.PCSystemType
      ram         = [math]::Round($cs.TotalPhysicalMemory / 1GB, 1)
      cpu         = $cpu.Name
      jezgara     = $cpu.NumberOfCores
      serijski    = $bios.SerialNumber
      bios        = $bios.ReleaseDate
      sistem      = $os.Caption
      build       = $os.BuildNumber
      instaliran  = $os.InstallDate
      disk_model  = $disk.Model
      disk_gb     = [math]::Round($disk.Size / 1GB, 0)
      disk_media  = $pd.MediaType
      disk_bus    = $pd.BusType
      disk_rpm    = $pd.SpindleSpeed
      ram_tip     = $memTip
      ram_mhz     = $memMhz
      ram_modula  = ($mem | Measure-Object).Count
    }
    Remove-CimSession $s
  } catch {
    $izlaz += [pscustomobject]@{ip=$m; greska=$_.Exception.Message}
  }
}
if ($izlaz) { $izlaz | ConvertTo-Json -Compress -Depth 3 } else { '[]' }
"""


def _datum(v):
    if not v:
        return None
    t = str(v)
    m = re.search(r"(\d{10,13})", t)
    if m:
        try:
            return datetime.datetime.fromtimestamp(int(m.group(1)[:13]) / 1000)
        except Exception:
            pass
    for f in ("%Y-%m-%dT%H:%M:%S", "%m/%d/%Y %H:%M:%S"):
        try:
            return datetime.datetime.strptime(t[:19], f)
        except Exception:
            continue
    return None


def provjeri(mrezni_uredjaji, korisnik=None, lozinka=None, log=lambda s: None):
    nalazi, sirovo = [], {}

    if not JE_WINDOWS:
        nalazi.append(nalaz(
            "Uređaji", "Inventar mreže nije napravljen", INFO,
            "Prikupljanje podataka sa udaljenih mašina radi samo sa Windowsa.",
            preporuka="Pokrenuti alat sa USB-a na mašini u domenu klijenta."))
        return {"nalazi": nalazi, "sirovo": sirovo}

    # mašine koje liče na Windows računare
    mete = []
    for u in (mrezni_uredjaji or []):
        portovi = {p["port"] for p in u.get("portovi", [])}
        if portovi & {445, 135, 3389, 5985}:
            mete.append(u["ip"])
    mete = mete[:60]

    if not mete:
        nalazi.append(nalaz(
            "Uređaji", "Nema Windows mašina za inventar", INFO,
            "Na mreži nije pronađen nijedan uređaj sa otvorenim Windows servisima.",
            preporuka="Provjeriti je li mrežni opseg tačan i je li popis mreže "
                      "uopšte pokrenut."))
        return {"nalazi": nalazi, "sirovo": sirovo}

    log(f"Prikupljam podatke sa {len(mete)} mašina (traje nekoliko minuta)")
    lista = "@(" + ",".join(f"'{ip}'" for ip in mete) + ")"
    okolina = dict(os.environ)
    if korisnik:
        okolina["KS_KORISNIK"] = korisnik
        okolina["KS_LOZINKA"] = lozinka or ""

    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy",
             "Bypass", "-Command", SKRIPTA.replace("METE_OVDJE", lista)],
            capture_output=True, text=True, timeout=60 + 18 * len(mete),
            env=okolina,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        podaci = json.loads((r.stdout or "").strip() or "[]")
    except Exception as e:
        nalazi.append(nalaz("Uređaji", "Inventar nije prikupljen", INFO, str(e)))
        return {"nalazi": nalazi, "sirovo": sirovo}

    podaci = podaci if isinstance(podaci, list) else [podaci]
    uspjeli = [d for d in podaci if not d.get("greska") and d.get("cpu")]
    neuspjeli = [d for d in podaci if d.get("greska") or not d.get("cpu")]

    log(f"Podaci prikupljeni sa {len(uspjeli)} od {len(mete)} mašina")

    if not uspjeli:
        nalazi.append(nalaz(
            "Uređaji", "Inventar mreže nije prikupljen", INFO,
            f"Nijedna od {len(mete)} mašina nije dozvolila čitanje podataka.",
            preporuka="Za inventar je potreban administratorski nalog na tim "
                      "mašinama. U domenu je to domenski administrator — unesi "
                      "ga u polja za prijavu. Ako mašine nisu u domenu, inventar "
                      "se radi ručno.",
            dokaz=[f'{d["ip"]}: {str(d.get("greska"))[:90]}' for d in neuspjeli[:12]]))
        sirovo["neuspjeli"] = neuspjeli
        return {"nalazi": nalazi, "sirovo": sirovo}

    # --- obradi svaku mašinu ---
    masine = []
    for d in uspjeli:
        h = {"cpu": d.get("cpu"),
             "bios_datum_raw": _datum(d.get("bios")),
             "os_instaliran": _datum(d.get("instaliran"))}
        p = m_starost.procijeni(h)
        ocjena, razlog = m_starost.presuda(p.get("godine"), d.get("sistem"))
        tipovi = []
        for t in str(d.get("ram_tip") or "").split("/"):
            try:
                naziv = TIP_RAM.get(int(t))
                if naziv:
                    tipovi.append(naziv)
            except ValueError:
                continue
        masine.append({
            "ip": d.get("ip"),
            "ram_tip": "/".join(sorted(set(tipovi))),
            "ram_mhz": d.get("ram_mhz"),
            "ram_modula": d.get("ram_modula"),
            "disk_vrsta": _vrsta_diska(d.get("disk_media"), d.get("disk_bus"),
                                       d.get("disk_rpm")),
            "ime": d.get("ime") or "",
            "tip": TIP.get(d.get("tip"), "Nepoznato"),
            "model": " ".join(x for x in [d.get("proizvodjac"), d.get("model")] if x).strip(),
            "cpu": (d.get("cpu") or "").strip(),
            "ram": d.get("ram"),
            "disk": f'{d.get("disk_model") or ""} {d.get("disk_gb") or ""}'.strip(),
            "sistem": d.get("sistem") or "",
            "serijski": d.get("serijski") or "",
            "godine": p.get("godine"),
            "osnov": p.get("osnov"),
            "ocjena": ocjena,
            "razlog": razlog,
        })

    masine.sort(key=lambda m: (-(m["godine"] or 0), m["ime"]))
    sirovo["masine"] = masine
    sirovo["neuspjeli"] = neuspjeli

    # --- glavni nalaz: tabela inventara ---
    zaglavlje = ["Uređaj", "Tip", "Model", "Procesor", "RAM", "Disk", "Sistem",
                 "Starost", "Ocjena"]
    redovi = []
    for m in masine:
        redovi.append([
            m["ime"] or m["ip"],
            m["tip"],
            m["model"][:34] or "—",
            re.sub(r"\(R\)|\(TM\)|CPU|Processor|@.*", "", m["cpu"]).strip()[:30] or "—",
            (f'{m["ram"]:g} GB' + (f' {m["ram_tip"]}' if m.get("ram_tip") else ""))
            if m["ram"] else "—",
            m.get("disk_vrsta") or "—",
            re.sub(r"Microsoft ", "", m["sistem"])[:26] or "—",
            f'{m["godine"]:g} g.' if m["godine"] is not None else "—",
            m["ocjena"],
        ])

    za_zamjenu = [m for m in masine if m["ocjena"] == "Za zamjenu"]
    planirati = [m for m in masine if m["ocjena"] == "Planirati zamjenu"]
    nadogradnja = [m for m in masine if m["ocjena"] == "Nadogradnja sistema"]

    tez = VISOK if za_zamjenu else (SREDNJI if (planirati or nadogradnja) else DOBRO)
    sazetak = (f'Popisano {len(masine)} uređaja: {len(za_zamjenu)} za zamjenu, '
               f'{len(planirati)} za planiranje, {len(nadogradnja)} traži '
               f'nadogradnju sistema.')

    nalazi.append(nalaz(
        "Uređaji", "Inventar uređaja sa procjenom za zamjenu",
        tez if za_zamjenu or planirati or nadogradnja else INFO,
        sazetak,
        "Oprema koja izađe iz podrške prestaje da dobija ažuriranja firmvera, a "
        "dijelovi se teže nabavljaju. Kvar tada znači zastoj dok se ne nađe "
        "zamjena — a zamjena pod pritiskom uvijek košta više."
        if (za_zamjenu or planirati) else "",
        "Uređaje označene za zamjenu uvrstiti u plan nabavke. Starost je "
        "procijenjena po generaciji procesora, pa je tačna unutar oko godinu dana."
        if (za_zamjenu or planirati) else "",
        tabela={"zaglavlje": zaglavlje, "redovi": redovi,
                "sirine": [12, 8, 15, 14, 10, 9, 13, 7, 12]},
        dokaz=[f'{m["ime"] or m["ip"]} — serijski {m["serijski"]}' for m in masine]))

    # --- posebno: mašine starije od sedam godina ---
    if za_zamjenu:
        nalazi.append(nalaz(
            "Uređaji", f"{len(za_zamjenu)} uređaja starijih od sedam godina", VISOK,
            "Za zamjenu: " + ", ".join(
                f'{m["ime"] or m["ip"]} ({m["godine"]:g} g.)' for m in za_zamjenu),
            "Na uređajima ove starosti otkaz diska ili napajanja je pitanje "
            "vremena, a ne slučajnosti. Svaki od njih je jedan dan zastoja koji "
            "čeka da se desi.",
            "Napraviti plan zamjene po prioritetu — prvo mašine na kojima radi "
            "neko ko ne može stati, pa ostale.",
            sati=2, dokaz=[f'{m["ime"] or m["ip"]}: {m["model"]}, {m["cpu"]}, '
                           f'procjena {m["godine"]:g} godina' for m in za_zamjenu]))

    # --- sistemi van podrške ---
    if nadogradnja:
        nalazi.append(nalaz(
            "Uređaji", f"{len(nadogradnja)} uređaja ima sistem van podrške", VISOK,
            "Pogođeni: " + ", ".join(
                f'{m["ime"] or m["ip"]} ({re.sub("Microsoft ", "", m["sistem"])})'
                for m in nadogradnja),
            "Sistem van podrške ne dobija sigurnosne zakrpe. Svaka nova ranjivost "
            "ostaje otvorena trajno, a te mašine su na istoj mreži kao i sve ostalo.",
            "Nadograditi na podržanu verziju gdje hardver to dozvoljava, a gdje ne "
            "— zamijeniti uređaj. Do tada ih izdvojiti u zaseban mrežni segment.",
            sati=3 * len(nadogradnja), trosak=180 * len(nadogradnja),
            dokaz=[f'{m["ime"] or m["ip"]}: {m["sistem"]}' for m in nadogradnja]))

    # --- mehanički diskovi na mreži ---
    hdd = [m for m in masine if str(m.get("disk_vrsta") or "").startswith("HDD")]
    if hdd:
        nalazi.append(nalaz(
            "Uređaji", f"{len(hdd)} uređaja još radi sa mehaničkim diskom", NIZAK,
            ", ".join(f'{m["ime"] or m["ip"]}' for m in hdd),
            "Mehanički disk otkazuje češće od SSD-a i usporava svakodnevni rad. "
            "Na starijoj mašini to je najčešći uzrok sporog rada.",
            "Zamjena SSD-om je najjeftinija nadogradnja koja postoji — produži "
            "mašini vijek za godinu-dvije i smanji rizik od gubitka podataka.",
            sati=1.5 * len(hdd), trosak=90 * len(hdd),
            dokaz=[f'{m["ime"] or m["ip"]}: {m.get("disk")} ({m.get("disk_vrsta")})'
                   for m in hdd]))

    # --- slaba memorija ---
    slabi = [m for m in masine if m["ram"] and m["ram"] < 8]
    if slabi:
        nalazi.append(nalaz(
            "Uređaji", f"{len(slabi)} uređaja ima manje od 8 GB memorije", NIZAK,
            ", ".join(f'{m["ime"] or m["ip"]} ({m["ram"]:g} GB)' for m in slabi),
            "Ispod 8 GB sistem stalno koristi disk umjesto memorije — rad je spor, "
            "a disk se brže troši.",
            "Nadogradnja memorije je najjeftiniji način da se stara mašina "
            "produži za godinu-dvije.",
            sati=0.5 * len(slabi), trosak=60 * len(slabi)))

    # --- mašine kojima nismo prišli ---
    if neuspjeli:
        nalazi.append(nalaz(
            "Uređaji", f"{len(neuspjeli)} uređaja nije dalo podatke", INFO,
            "Nije bilo pristupa: " + ", ".join(d["ip"] for d in neuspjeli[:15]),
            preporuka="Obično su to uređaji koji nisu Windows računari (štampači, "
                      "kamere, NAS) ili mašine van domena. Vrijedi ih identifikovati "
                      "ručno jer se ne pojavljuju u inventaru.",
            dokaz=[f'{d["ip"]}: {str(d.get("greska"))[:90]}' for d in neuspjeli[:15]]))

    return {"nalazi": nalazi, "sirovo": sirovo}
