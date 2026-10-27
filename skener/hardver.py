# -*- coding: utf-8 -*-
"""Popis hardvera: starost uređaja, disk, memorija, sistem, baterija.

Na Windowsu ide kroz PowerShell i CIM. Na Linuxu kroz /sys i standardne alate,
pa radi i u laboratoriji.
"""
import datetime
import json
import os
import re
import subprocess
import sys

from .nalaz import nalaz, VISOK, SREDNJI, NIZAK, INFO, DOBRO
from . import mak as m_mak
from . import starost as m_starost

JE_WINDOWS = sys.platform.startswith("win")

# Windows 10 je izašao iz redovne podrške u oktobru 2025.
KRAJ_PODRSKE = {
    "10": ("Windows 10", "oktobra 2025"),
    "8": ("Windows 8", "januara 2016"),
    "8.1": ("Windows 8.1", "januara 2023"),
    "7": ("Windows 7", "januara 2020"),
}


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


# SMBIOSMemoryType iz Win32_PhysicalMemory
TIP_RAM = {20: "DDR", 21: "DDR2", 24: "DDR3", 26: "DDR4", 34: "DDR5",
           35: "DDR5", 0x1A: "DDR4", 27: "LPDDR", 28: "LPDDR2",
           29: "LPDDR3", 30: "LPDDR4", 31: "Logical NV-DIMM"}

# BusType iz Get-PhysicalDisk
SABIRNICA = {1: "SCSI", 2: "ATAPI", 3: "ATA", 4: "1394", 5: "SSA", 6: "Fibre",
             7: "USB", 8: "RAID", 9: "iSCSI", 10: "SAS", 11: "SATA",
             12: "SD", 13: "MMC", 17: "NVMe", 18: "SCM", 19: "UFS"}

# MediaType iz Get-PhysicalDisk
VRSTA_MEDIJA = {3: "HDD", 4: "SSD", 5: "SCM"}


def _vrsta_diska(media, bus, obrtaji):
    """NVMe je bitna razlika u odnosu na obični SSD — i po brzini i po cijeni."""
    vrsta = VRSTA_MEDIJA.get(media) or (str(media) if media else "")
    if str(vrsta).lower() in ("unspecified", "0", "none", ""):
        # stariji sistemi ne prijave vrstu — zaključi iz obrtaja i sabirnice
        if obrtaji in (0, None) and bus == 17:
            vrsta = "SSD"
        elif isinstance(obrtaji, int) and obrtaji > 0:
            vrsta = "HDD"
        else:
            vrsta = "nepoznato"
    if vrsta == "SSD" and bus == 17:
        return "SSD (NVMe)"
    if vrsta == "SSD" and bus == 11:
        return "SSD (SATA)"
    return vrsta


def _gb(b):
    try:
        return round(int(b) / 1073741824, 1)
    except Exception:
        return None


def _datum_iz_cim(v):
    """CIM datum stiže kao /Date(1690000000000)/ ili ISO tekst."""
    if not v:
        return None
    t = str(v)
    m = re.search(r"(\d{10,13})", t)
    if m:
        try:
            return datetime.datetime.fromtimestamp(int(m.group(1)[:13]) / 1000)
        except Exception:
            pass
    for f in ("%Y-%m-%dT%H:%M:%S", "%m/%d/%Y %H:%M:%S", "%Y%m%d"):
        try:
            return datetime.datetime.strptime(t[:19], f)
        except Exception:
            continue
    return None


# ---------------------------------------------------------------- Windows
def _windows(log):
    h = {}
    log("Model i serijski broj")
    cs = _ps("Get-CimInstance Win32_ComputerSystem | Select-Object Manufacturer,"
             "Model,TotalPhysicalMemory,Name | ConvertTo-Json -Compress")
    bios = _ps("Get-CimInstance Win32_BIOS | Select-Object SerialNumber,ReleaseDate,"
               "SMBIOSBIOSVersion | ConvertTo-Json -Compress")
    cpu = _ps("Get-CimInstance Win32_Processor | Select-Object Name,NumberOfCores,"
              "MaxClockSpeed | ConvertTo-Json -Compress")
    oss = _ps("Get-CimInstance Win32_OperatingSystem | Select-Object Caption,Version,"
              "BuildNumber,InstallDate | ConvertTo-Json -Compress")
    if cs:
        h["proizvodjac"] = cs.get("Manufacturer")
        h["model"] = cs.get("Model")
        h["ime"] = cs.get("Name")
        h["ram_gb"] = _gb(cs.get("TotalPhysicalMemory"))
    if bios:
        h["serijski"] = bios.get("SerialNumber")
        d = _datum_iz_cim(bios.get("ReleaseDate"))
        if d:
            h["bios_datum"] = d.strftime("%d.%m.%Y.")
            h["bios_datum_raw"] = d
    if cpu:
        cpu = cpu[0] if isinstance(cpu, list) else cpu
        h["cpu"] = (cpu.get("Name") or "").strip()
        h["jezgara"] = cpu.get("NumberOfCores")
    if oss:
        h["sistem"] = oss.get("Caption")
        h["verzija"] = oss.get("Version")
        h["build"] = oss.get("BuildNumber")
        inst = _datum_iz_cim(oss.get("InstallDate"))
        if inst:
            h["os_instaliran"] = inst

    log("Moduli memorije")
    mem = _ps("Get-CimInstance Win32_PhysicalMemory | Select-Object Capacity,"
              "Speed,ConfiguredClockSpeed,SMBIOSMemoryType,Manufacturer,"
              "PartNumber,DeviceLocator | ConvertTo-Json -Compress")
    if mem:
        mem = mem if isinstance(mem, list) else [mem]
        h["memorija_moduli"] = [{
            "gb": _gb(m.get("Capacity")),
            "tip": TIP_RAM.get(m.get("SMBIOSMemoryType"), ""),
            "mhz": m.get("ConfiguredClockSpeed") or m.get("Speed"),
            "proizvodjac": (m.get("Manufacturer") or "").strip(),
            "oznaka": (m.get("PartNumber") or "").strip(),
            "slot": m.get("DeviceLocator") or "",
        } for m in mem]
        tipovi = sorted({x["tip"] for x in h["memorija_moduli"] if x["tip"]})
        h["ram_tip"] = "/".join(tipovi)
        brzine = [x["mhz"] for x in h["memorija_moduli"] if x["mhz"]]
        if brzine:
            h["ram_mhz"] = max(brzine)
        h["ram_modula"] = len(h["memorija_moduli"])

    arr = _ps("Get-CimInstance Win32_PhysicalMemoryArray | Select-Object "
              "MemoryDevices,MaxCapacityEx | ConvertTo-Json -Compress")
    if arr:
        arr = arr[0] if isinstance(arr, list) else arr
        h["ram_slotova"] = arr.get("MemoryDevices")

    log("Diskovi")
    pd = _ps("Get-PhysicalDisk | Select-Object FriendlyName,MediaType,Size,"
             "HealthStatus,BusType,SpindleSpeed | ConvertTo-Json -Compress")
    if pd:
        pd = pd if isinstance(pd, list) else [pd]
        h["diskovi"] = [{"ime": d.get("FriendlyName"),
                         "vrsta": _vrsta_diska(d.get("MediaType"),
                                               d.get("BusType"),
                                               d.get("SpindleSpeed")),
                         "sabirnica": SABIRNICA.get(d.get("BusType"), ""),
                         "gb": _gb(d.get("Size")), "zdravlje": d.get("HealthStatus")}
                        for d in pd]
    sr = _ps("Get-PhysicalDisk | Get-StorageReliabilityCounter | Select-Object "
             "DeviceId,PowerOnHours,Wear,Temperature | ConvertTo-Json -Compress")
    if sr:
        h["pouzdanost"] = sr if isinstance(sr, list) else [sr]

    ld = _ps("Get-CimInstance Win32_LogicalDisk -Filter 'DriveType=3' | "
             "Select-Object DeviceID,Size,FreeSpace | ConvertTo-Json -Compress")
    if ld:
        ld = ld if isinstance(ld, list) else [ld]
        h["particije"] = [{"slovo": d.get("DeviceID"), "gb": _gb(d.get("Size")),
                           "slobodno_gb": _gb(d.get("FreeSpace"))} for d in ld]

    bat = _ps("Get-CimInstance -ClassName BatteryStaticData -Namespace root/WMI | "
              "Select-Object DesignedCapacity,FullChargedCapacity | ConvertTo-Json -Compress")
    if bat:
        bat = bat[0] if isinstance(bat, list) else bat
        try:
            d_, f_ = int(bat.get("DesignedCapacity")), int(bat.get("FullChargedCapacity"))
            if d_:
                h["baterija_posto"] = round(f_ / d_ * 100)
        except Exception:
            pass
    return h


# ---------------------------------------------------------------- Linux
def _citaj(p):
    try:
        with open(p, encoding="utf-8", errors="replace") as f:
            return f.read().strip()
    except Exception:
        return None


def _linux(log):
    h = {}
    log("Model i BIOS")
    dmi = "/sys/class/dmi/id/"
    h["proizvodjac"] = _citaj(dmi + "sys_vendor")
    h["model"] = _citaj(dmi + "product_name")
    h["serijski"] = _citaj(dmi + "product_serial")
    bd = _citaj(dmi + "bios_date")
    if bd:
        for f in ("%m/%d/%Y", "%d/%m/%Y", "%Y-%m-%d"):
            try:
                d = datetime.datetime.strptime(bd, f)
                h["bios_datum"] = d.strftime("%d.%m.%Y.")
                h["bios_datum_raw"] = d
                break
            except Exception:
                continue

    try:
        r = subprocess.run(["dmidecode", "-t", "memory"], capture_output=True,
                           text=True, timeout=10)
        if r.returncode == 0:
            tipovi = set(re.findall(r"^\s*Type:\s*(DDR\d|LPDDR\d)", r.stdout, re.M))
            if tipovi:
                h["ram_tip"] = "/".join(sorted(tipovi))
            brzine = [int(x) for x in re.findall(r"Configured Memory Speed:\s*(\d+)",
                                                 r.stdout)]
            if brzine:
                h["ram_mhz"] = max(brzine)
    except Exception:
        pass

    mi = _citaj("/proc/meminfo") or ""
    m = re.search(r"MemTotal:\s+(\d+) kB", mi)
    if m:
        h["ram_gb"] = round(int(m.group(1)) / 1048576, 1)

    ci = _citaj("/proc/cpuinfo") or ""
    m = re.search(r"model name\s*:\s*(.+)", ci)
    if m:
        h["cpu"] = m.group(1).strip()
    h["jezgara"] = ci.count("processor\t:") or None

    try:
        osr = dict(l.split("=", 1) for l in (_citaj("/etc/os-release") or "").splitlines() if "=" in l)
        h["sistem"] = osr.get("PRETTY_NAME", "").strip('"')
    except Exception:
        pass
    h["verzija"] = os.uname().release if hasattr(os, "uname") else None

    log("Diskovi")
    diskovi = []
    try:
        for d in sorted(os.listdir("/sys/block")):
            if d.startswith(("loop", "ram", "dm-", "sr")):
                continue
            put = f"/sys/block/{d}/"
            sektori = _citaj(put + "size")
            rot = _citaj(put + "queue/rotational")
            model = _citaj(put + "device/model") or d
            vrsta = "HDD" if rot == "1" else "SSD"
            if vrsta == "SSD" and d.startswith("nvme"):
                vrsta = "SSD (NVMe)"
            diskovi.append({
                "ime": model.strip(),
                "vrsta": vrsta,
                "sabirnica": "NVMe" if d.startswith("nvme") else "",
                "gb": round(int(sektori) * 512 / 1073741824, 1) if sektori else None,
                "zdravlje": None,
            })
    except Exception:
        pass
    if diskovi:
        h["diskovi"] = diskovi

    try:
        import shutil
        u = shutil.disk_usage("/")
        h["particije"] = [{"slovo": "/", "gb": round(u.total / 1073741824, 1),
                           "slobodno_gb": round(u.free / 1073741824, 1)}]
    except Exception:
        pass
    return h


# ---------------------------------------------------------------- nalazi

def _mrezne():
    """Mrežne kartice ove mašine i njihove MAC adrese — to je ono što ostaje
    isto kad se IP promijeni, pa po tome uređaj ide u popis opreme."""
    out = []
    if JE_WINDOWS:
        podaci = _ps("Get-CimInstance Win32_NetworkAdapterConfiguration -Filter "
                     "\"MACAddress IS NOT NULL\" | Select-Object Description,"
                     "MACAddress,IPAddress | ConvertTo-Json -Compress")
        for a in (podaci if isinstance(podaci, list) else [podaci] if podaci else []):
            mac = m_mak.normalizuj(a.get("MACAddress"))
            if not mac:
                continue
            ip = a.get("IPAddress") or []
            ip = [x for x in (ip if isinstance(ip, list) else [ip]) if ":" not in str(x)]
            out.append({"naziv": (a.get("Description") or "")[:60], "mac": mac,
                        "ip": ip[0] if ip else ""})
    else:
        import glob as _g
        for put in sorted(_g.glob("/sys/class/net/*/address")):
            ime = put.split("/")[-2]
            if ime == "lo":
                continue
            try:
                with open(put, encoding="utf-8") as f:
                    mac = m_mak.normalizuj(f.read())
            except Exception:
                continue
            if mac and mac != "00:00:00:00:00:00":
                out.append({"naziv": ime, "mac": mac, "ip": ""})
    return out


def provjeri(log=lambda s: None):
    nalazi = []
    log("Popis hardvera")
    h = _windows(log) if JE_WINDOWS else _linux(log)

    if not h:
        return {"nalazi": [nalaz("Uređaji", "Popis hardvera nije izvršen", INFO,
                                 "Podaci o uređaju nisu dostupni.")], "sirovo": {}}

    opis = []
    if h.get("proizvodjac") or h.get("model"):
        opis.append(f'{h.get("proizvodjac", "")} {h.get("model", "")}'.strip())
    if h.get("cpu"):
        opis.append(h["cpu"])
    if h.get("ram_gb"):
        opis.append(f'{h["ram_gb"]} GB RAM'
                    + (f' {h["ram_tip"]}' if h.get("ram_tip") else "")
                    + (f' {h["ram_mhz"]} MHz' if h.get("ram_mhz") else ""))
    if h.get("sistem"):
        opis.append(h["sistem"])

    # --- mrežne kartice i njihove MAC adrese ---
    h["mrezne"] = _mrezne()

    redovi = []
    for k, naziv in (("proizvodjac", "Proizvođač"), ("model", "Model"),
                     ("serijski", "Serijski broj"), ("ime", "Naziv u mreži"),
                     ("cpu", "Procesor"), ("jezgara", "Jezgara"),
                     ("ram_gb", "Memorija (GB)"), ("ram_tip", "Tip memorije"),
                     ("ram_mhz", "Brzina memorije (MHz)"),
                     ("ram_modula", "Modula memorije"),
                     ("ram_slotova", "Slotova ukupno"), ("sistem", "Sistem"),
                     ("build", "Build"), ("bios_datum", "Datum firmvera (BIOS)")):
        if h.get(k) not in (None, ""):
            redovi.append(f"{naziv}: {h[k]}")
    for m in h.get("mrezne", []):
        redovi.append(f'Mrežna kartica: {m["naziv"]} — MAC {m["mac"]}'
                      + (f' — {m["ip"]}' if m.get("ip") else ""))
    for d in h.get("diskovi", []):
        if (d.get("gb") or 0) < 20:
            continue
        redovi.append(f'Disk: {d["ime"]} — {d["vrsta"]}, {d["gb"]} GB'
                      + (f', {d["sabirnica"]}' if d.get("sabirnica") else "")
                      + (f', stanje {d["zdravlje"]}' if d.get("zdravlje") else ""))
    for p in h.get("particije", []):
        redovi.append(f'Particija {p["slovo"]}: {p["slobodno_gb"]} GB slobodno '
                      f'od {p["gb"]} GB')
    for m in h.get("memorija_moduli", []):
        redovi.append(f'Modul: {m["slot"]} — {m["gb"]} GB {m["tip"]} '
                      f'{m["mhz"] or "?"} MHz {m["proizvodjac"]} {m["oznaka"]}'.strip())
    for r in h.get("pouzdanost", []):
        if r.get("PowerOnHours"):
            redovi.append(f'Sati rada diska: {r["PowerOnHours"]}'
                          + (f', istrošenost {r["Wear"]}%' if r.get("Wear") else ""))

    nalazi.append(nalaz(
        "Uređaji", "Popis hardvera", INFO, " · ".join(opis) or "Osnovni podaci o uređaju.",
        dokaz=redovi))

    # --- starost uređaja ---
    # Datum BIOS-a se mijenja pri ažuriranju firmvera, pa nije mjera starosti.
    # Procjena se gradi na generaciji procesora i satima rada diska.
    proc = m_starost.procijeni(h)
    h["procjena_starosti"] = {k: v for k, v in proc.items() if k != "redovi"}
    god = proc.get("godine")

    if god is not None:
        osnov_tekst = {
            "procesor": "prema generaciji procesora",
            "sati rada": "prema satima rada diska",
            "firmver": "prema datumu firmvera — gruba donja granica",
        }.get(proc["osnov"], proc["osnov"])

        if god >= 7:
            nalazi.append(nalaz(
                "Uređaji", f"Uređaj je star oko {god:g} godina", SREDNJI,
                f'{h.get("model") or "Uređaj"} — procjena {osnov_tekst}.',
                "Poslije sedam godina proizvođač obično više ne izdaje ažuriranja "
                "firmvera, a dijelovi se teško nabavljaju. Kvar znači zastoj dok se "
                "ne nađe zamjena.",
                "Uvrstiti u plan zamjene. Dok je u upotrebi, obavezno šifrovati disk "
                "i imati backup, jer je vjerovatnoća kvara veća.",
                sati=1, dokaz=proc["redovi"]))
        elif god >= 5:
            nalazi.append(nalaz(
                "Uređaji", f"Uređaj je star oko {god:g} godina", NIZAK,
                f'{h.get("model") or "Uređaj"} ulazi u godine kad se planira zamjena '
                f'— procjena {osnov_tekst}.',
                "Još radi, ali vrijedi ga imati u planu nabavke da zamjena ne bude hitna.",
                "Predvidjeti zamjenu u narednih 12 do 24 mjeseca.",
                dokaz=proc["redovi"]))
        else:
            nalazi.append(nalaz(
                "Uređaji", f"Uređaj je star oko {god:g} godina", DOBRO,
                f"Uređaj je u radnom vijeku — procjena {osnov_tekst}.",
                dokaz=proc["redovi"]))
    else:
        nalazi.append(nalaz(
            "Uređaji", "Starost uređaja nije utvrđena", INFO,
            "Ni procesor ni podaci o disku ne daju dovoljno za procjenu.",
            preporuka="Starost se može provjeriti po serijskom broju na sajtu "
                      "proizvođača.",
            dokaz=proc["redovi"]))

    # --- sistem van podrške ---
    sistem = (h.get("sistem") or "")
    for kljuc, (ime, kad) in KRAJ_PODRSKE.items():
        if re.search(rf"Windows\s+{re.escape(kljuc)}\b", sistem):
            nalazi.append(nalaz(
                "Uređaji", f"{ime} je van redovne podrške", VISOK,
                f"Na uređaju je {sistem}.",
                f"{ime} više ne dobija redovne sigurnosne zakrpe (podrška je "
                f"prestala {kad}). Svaka nova ranjivost ostaje otvorena zauvijek. "
                "Produženo održavanje se plaća posebno i nije trajno rješenje.",
                "Nadograditi na podržanu verziju ili zamijeniti uređaj. Dok traje "
                "prelaz, mašinu izdvojiti u zaseban mrežni segment.",
                sati=3, trosak=180, dokaz=[f"{sistem} (build {h.get('build')})"]))
            break

    # --- diskovi ---
    # Sitni virtuelni uređaji nisu diskovi firme i samo zatrpavaju izvještaj.
    pravi = [d for d in h.get("diskovi", []) if (d.get("gb") or 0) >= 20]

    for d in pravi:
        if d.get("zdravlje") and str(d["zdravlje"]).lower() not in ("healthy", "ok"):
            nalazi.append(nalaz(
                "Uređaji", "Disk prijavljuje problem", VISOK,
                f'{d["ime"]} ({d["gb"]} GB) — stanje: {d["zdravlje"]}.',
                "Disk koji prijavljuje grešku može otkazati u svakom trenutku. "
                "Ako na njemu ima podataka koji nisu u backupu, gube se.",
                "Odmah napraviti punu kopiju podataka, pa zamijeniti disk.",
                sati=2, trosak=120, dokaz=[json.dumps(d, ensure_ascii=False)]))

    # U virtuelnoj mašini podatak o vrsti diska ne znači ništa — virtuelni disk
    # se skoro uvijek prijavi kao mehanički bez obzira na to šta je ispod.
    tekst = f'{h.get("proizvodjac") or ""} {h.get("model") or ""}'.lower()
    virtuelna = (not h.get("model")) or any(
        z in tekst for z in ("qemu", "vmware", "virtualbox", "kvm", "xen",
                             "hyper-v", "virtual machine", "bochs", "parallels"))

    hdd = [d for d in pravi if d.get("vrsta") == "HDD"]
    if hdd and not virtuelna:
        nalazi.append(nalaz(
            "Uređaji", "Sistem radi sa mehaničkim diskom", NIZAK,
            "Mehanički diskovi: " + ", ".join(f'{d["ime"]} ({d["gb"]} GB)' for d in hdd),
            "Mehanički disk ima pokretne dijelove i otkazuje češće od SSD-a. "
            "Uz to usporava i sam rad, pa zaposleni gube vrijeme svakodnevno.",
            "Zamjena SSD-om je najjeftinija nadogradnja koja postoji — i brža "
            "mašina i manji rizik od gubitka podataka.",
            sati=1.5 * len(hdd), trosak=90 * len(hdd),
            dokaz=[f'{d["ime"]} — HDD, {d["gb"]} GB' for d in hdd]))
    elif virtuelna:
        nalazi.append(nalaz(
            "Uređaji", "Uređaj je virtuelna mašina", INFO,
            "Prepoznata je virtuelna mašina, pa podaci o starosti i vrsti diska "
            "ne odražavaju stvarni hardver.",
            preporuka="Za stvarno stanje opreme pokrenuti popis na fizičkom hostu."))

    for r in h.get("pouzdanost", []):
        sati = r.get("PowerOnHours")
        if isinstance(sati, int) and sati > 35000:
            nalazi.append(nalaz(
                "Uređaji", "Disk ima mnogo sati rada", SREDNJI,
                f"Disk je u pogonu {sati} sati (oko {sati // 8760} godina neprekidno).",
                "Preko 35.000 sati vjerovatnoća otkaza znatno raste.",
                "Planirati zamjenu i provjeriti da backup stvarno radi.",
                sati=2, trosak=120))
        if isinstance(r.get("Wear"), int) and r["Wear"] > 80:
            nalazi.append(nalaz(
                "Uređaji", "SSD je pri kraju vijeka", VISOK,
                f'Istrošenost ćelija: {r["Wear"]}%.',
                "SSD pri kraju vijeka prelazi u režim samo za čitanje ili otkaže bez najave.",
                "Zamijeniti disk prije nego otkaže.", sati=2, trosak=120))

    # --- prostor ---
    for p in h.get("particije", []):
        if p.get("gb") and p.get("slobodno_gb") is not None:
            posto = p["slobodno_gb"] / p["gb"] * 100
            if posto < 10:
                nalazi.append(nalaz(
                    "Uređaji", f'Particija {p["slovo"]} je skoro puna', SREDNJI,
                    f'Slobodno {p["slobodno_gb"]} GB od {p["gb"]} GB ({posto:.0f}%).',
                    "Kad nestane prostora, ažuriranja prestaju da se instaliraju, a "
                    "backup tiho pada. Oboje se primijeti tek kad zatreba.",
                    "Osloboditi prostor ili povećati disk.", sati=1, trosak=60))

    # --- memorija ---
    ram = h.get("ram_gb")
    if ram and ram < 8:
        nalazi.append(nalaz(
            "Uređaji", "Malo radne memorije", NIZAK,
            f"Uređaj ima {ram} GB RAM-a.",
            "Ispod 8 GB sistem stalno koristi disk umjesto memorije — rad je spor, "
            "a disk se brže troši.",
            "Nadogradnja memorije je jeftina i odmah se osjeti.",
            sati=1, trosak=60))

    # --- baterija ---
    b = h.get("baterija_posto")
    if b is not None and b < 60:
        nalazi.append(nalaz(
            "Uređaji", "Baterija je istrošena", NIZAK,
            f"Kapacitet baterije je {b}% od fabričkog.",
            "Prenosivi računar se gasi pri nestanku struje, pa se gubi nesnimljen rad.",
            "Zamijeniti bateriju.", sati=1, trosak=60))

    return {"nalazi": nalazi, "sirovo": h}
