# -*- coding: utf-8 -*-
"""Popis štampača — način povezivanja, drajver, port, i šta je od toga rizik.

Mrežni štampač je pun računar sa web sučeljem, diskom i često fabričkom
lozinkom. Na njemu se zadržavaju skenirani dokumenti, a kroz njegovo sučelje se
često mogu pročitati i podaci o mreži.
"""
import json
import re
import subprocess
import sys

from .nalaz import nalaz, VISOK, SREDNJI, NIZAK, INFO, DOBRO

JE_WINDOWS = sys.platform.startswith("win")

VIRTUELNI = ["microsoft print to pdf", "microsoft xps", "onenote", "fax",
             "adobe pdf", "pdf creator", "pdfcreator", "cutepdf", "foxit",
             "bullzip", "anydesk printer", "able2extract", "send to onenote",
             "print to pdf", "nitro pdf", "clipboard"]


def _ps(skripta, timeout=60):
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


def _vrsta_veze(port, naziv):
    p = str(port or "").upper()
    n = str(naziv or "").lower()
    if any(v in n for v in VIRTUELNI) or any(v in p.lower() for v in VIRTUELNI):
        return "VIRTUELNI / PDF / FAX", False
    if p.startswith("USB") or p.startswith("DOT4") or p.startswith("LPT"):
        return "LOKALNI — USB", False
    if p.startswith("WSD"):
        return "MREŽNI — WSD", True
    if re.match(r"^\d{1,3}(\.\d{1,3}){3}", p) or p.startswith("IP_"):
        return "MREŽNI — direktni TCP/IP", True
    if p.startswith("\\\\"):
        return "DIJELJENI — preko servera", True
    if p.startswith("NUL") or p.startswith("PORTPROMPT"):
        return "VIRTUELNI / PDF / FAX", False
    return "NEPOZNATO", None


def _ip_iz_porta(port):
    m = re.search(r"(\d{1,3}(?:\.\d{1,3}){3})", str(port or ""))
    return m.group(1) if m else ""


def provjeri(mrezni_uredjaji=None, log=lambda s: None):
    nalazi, sirovo = [], {}

    if not JE_WINDOWS:
        nalazi.append(nalaz(
            "Štampači", "Popis štampača nije izvršen", INFO,
            "Ova provjera radi samo na Windowsu.",
            preporuka="Pokrenuti alat na mašini klijenta."))
        return {"nalazi": nalazi, "sirovo": sirovo}

    log("Instalirani redovi štampe")
    red = _ps("Get-Printer | Select-Object Name,DriverName,PortName,Shared,"
              "Published,Location,Comment,PrinterStatus | ConvertTo-Json -Compress")
    portovi = _ps("Get-PrinterPort | Select-Object Name,PrinterHostAddress,"
                  "PortNumber,SNMPEnabled,SNMPCommunity | ConvertTo-Json -Compress")

    if not red:
        nalazi.append(nalaz(
            "Štampači", "Nema instaliranih štampača", INFO,
            "Na ovoj mašini nije instaliran nijedan red štampe."))
        return {"nalazi": nalazi, "sirovo": sirovo}

    red = red if isinstance(red, list) else [red]
    portovi = (portovi if isinstance(portovi, list) else [portovi]) if portovi else []
    po_imenu = {str(p.get("Name")): p for p in portovi if p.get("Name")}

    spisak = []
    for s in red:
        naziv = s.get("Name") or ""
        port = s.get("PortName") or ""
        pinfo = po_imenu.get(port, {})
        vrsta, mrezni = _vrsta_veze(port, naziv)
        ip = pinfo.get("PrinterHostAddress") or _ip_iz_porta(port)
        spisak.append({
            "naziv": naziv,
            "veza": vrsta,
            "mrezni": mrezni,
            "port": port,
            "ip": ip or "",
            "drajver": s.get("DriverName") or "",
            "dijeljen": bool(s.get("Shared")),
            "lokacija": s.get("Location") or "",
            "snmp": pinfo.get("SNMPEnabled"),
            "snmp_zajednica": pinfo.get("SNMPCommunity") or "",
        })

    spisak.sort(key=lambda x: (x["veza"], x["naziv"]))
    sirovo["stampaci"] = spisak

    stvarni = [s for s in spisak if s["veza"] != "VIRTUELNI / PDF / FAX"]
    mrezni = [s for s in spisak if s["mrezni"]]
    virtuelni = [s for s in spisak if s["veza"] == "VIRTUELNI / PDF / FAX"]

    log(f"Pronađeno {len(stvarni)} stvarnih štampača ({len(mrezni)} mrežnih), "
        f"{len(virtuelni)} virtuelnih")

    # --- glavni popis ---
    zaglavlje = ["Naziv", "Povezivanje", "Mrežni", "IP / port", "Drajver"]
    redovi = [[s["naziv"][:38], s["veza"],
               "DA" if s["mrezni"] else ("NE" if s["mrezni"] is False else "?"),
               (s["ip"] or s["port"])[:26], s["drajver"][:30]]
              for s in spisak]
    nalazi.append(nalaz(
        "Štampači", f"Popisano {len(stvarni)} štampača", INFO,
        f'{len(stvarni)} stvarnih štampača, od toga {len(mrezni)} na mreži. '
        f'Uz njih {len(virtuelni)} virtuelnih (PDF, fax) koji se ne računaju '
        f'kao oprema.',
        preporuka="Uporediti spisak sa onim što je stvarno u prostorijama. "
                  "Štampač koji niko ne prepoznaje treba identifikovati.",
        tabela={"zaglavlje": zaglavlje, "redovi": redovi,
                "sirine": [26, 20, 9, 22, 23]},
        dokaz=[f'{s["naziv"]} — {s["veza"]} — {s["ip"] or s["port"]} — '
               f'{s["drajver"]}' for s in spisak]))

    # --- mrežni štampači su uređaji, ne periferija ---
    if mrezni:
        sa_ip = [s for s in mrezni if s["ip"]]
        nalazi.append(nalaz(
            "Štampači", f"{len(mrezni)} štampača je na mreži", SREDNJI,
            "Mrežni štampači: "
            + ", ".join(f'{s["naziv"]}{" (" + s["ip"] + ")" if s["ip"] else ""}'
                        for s in mrezni[:10]),
            "Mrežni štampač je mali računar sa web sučeljem, diskom i firmverom. "
            "Na njemu ostaju skenirani dokumenti, a kroz njegovo sučelje se često "
            "vide i postavke mreže. Fabrička lozinka na štampaču se gotovo nikad "
            "ne mijenja.",
            "Za svaki mrežni štampač promijeniti administratorsku lozinku, "
            "isključiti nepotrebne servise (FTP, Telnet), ažurirati firmver i "
            "uključiti brisanje memorije nakon štampe gdje uređaj to podržava.",
            sati=0.5 * len(mrezni), trosak=30 * len(mrezni),
            dokaz=[f'{s["naziv"]} — {s["ip"] or s["port"]} — {s["veza"]}'
                   for s in mrezni]))

        # --- ukrštanje sa popisom mreže ---
        if mrezni_uredjaji and sa_ip:
            po_ip = {u["ip"]: u for u in mrezni_uredjaji}
            izlozeni = []
            for s in sa_ip:
                u = po_ip.get(s["ip"])
                if not u:
                    continue
                otv = [p["port"] for p in u.get("portovi", [])]
                rizicni = [p for p in otv if p in (21, 23, 80, 161, 443, 8080, 9100)]
                if rizicni:
                    izlozeni.append((s["naziv"], s["ip"], rizicni))
            sirovo["izlozeni_portovi"] = [
                {"naziv": n, "ip": i, "portovi": p} for n, i, p in izlozeni]
            if izlozeni:
                opis = {21: "FTP", 23: "Telnet", 80: "web sučelje",
                        161: "SNMP", 443: "web sučelje (HTTPS)",
                        8080: "web sučelje", 9100: "direktna štampa"}
                nalazi.append(nalaz(
                    "Štampači", "Štampači imaju otvorene servise na mreži", SREDNJI,
                    "; ".join(f'{n} ({i}): '
                              + ", ".join(f"{opis.get(p, p)} [{p}]" for p in ps)
                              for n, i, ps in izlozeni[:8]),
                    "Preko otvorenog web sučelja sa fabričkom lozinkom može se "
                    "pročitati adresar, postavke mreže i zadnji skenirani "
                    "dokumenti. Telnet i FTP uz to šalju lozinku u čitljivom obliku.",
                    "Isključiti Telnet i FTP, promijeniti lozinku web sučelja, i "
                    "izdvojiti štampače u zaseban mrežni segment ako je moguće.",
                    sati=1.5, trosak=90,
                    dokaz=[f'{n} ({i}): portovi {", ".join(str(p) for p in ps)}'
                           for n, i, ps in izlozeni]))

    # --- SNMP sa fabričkom zajednicom ---
    snmp = [s for s in spisak if s.get("snmp")
            and str(s.get("snmp_zajednica", "")).lower() in ("public", "private")]
    if snmp:
        nalazi.append(nalaz(
            "Štampači", "SNMP sa fabričkom zajednicom", NIZAK,
            ", ".join(f'{s["naziv"]} (zajednica „{s["snmp_zajednica"]}")'
                      for s in snmp),
            "Sa fabričkom zajednicom svako na mreži može očitati podatke o "
            "uređaju, a kod nekih modela i promijeniti postavke.",
            "Promijeniti SNMP zajednicu ili isključiti SNMP ako se ne koristi.",
            sati=0.5, trosak=30))

    # --- dijeljeni štampači ---
    dijeljeni = [s for s in spisak if s["dijeljen"]
                 and s["veza"] != "VIRTUELNI / PDF / FAX"]
    if dijeljeni:
        nalazi.append(nalaz(
            "Štampači", f"{len(dijeljeni)} štampača je dijeljeno sa ove mašine",
            NIZAK,
            ", ".join(s["naziv"] for s in dijeljeni),
            "Dijeljenje štampača drži ovu mašinu uključenom kao posrednika i "
            "otvara dodatne SMB puteve prema njoj.",
            "Mrežne štampače bolje je instalirati direktno na svakoj mašini "
            "preko IP adrese nego dijeliti preko jednog računara.",
            sati=0.5 * len(dijeljeni)))

    if virtuelni:
        nalazi.append(nalaz(
            "Štampači", f"{len(virtuelni)} virtuelnih štampača", INFO,
            "Ne računaju se kao oprema: "
            + ", ".join(s["naziv"] for s in virtuelni[:12]),
            dokaz=[s["naziv"] for s in virtuelni]))

    return {"nalazi": nalazi, "sirovo": sirovo}
