# -*- coding: utf-8 -*-
"""Politika lozinki i zaključavanja naloga — lokalna i domenska."""
import json
import re
import subprocess
import sys

from .nalaz import nalaz, VISOK, SREDNJI, NIZAK, INFO, DOBRO

JE_WINDOWS = sys.platform.startswith("win")


def _net_accounts(domen=False, timeout=25):
    if not JE_WINDOWS:
        return ""
    try:
        cmd = ["net", "accounts"] + (["/domain"] if domen else [])
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                           errors="replace",
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return r.stdout or ""
    except Exception:
        return ""


def _broj(tekst, *kljucevi):
    for k in kljucevi:
        m = re.search(rf"{k}[^:]*:\s*(\S+)", tekst, re.I)
        if m:
            v = m.group(1)
            if v.lower() in ("never", "unlimited", "nikad", "neograničeno"):
                return -1
            try:
                return int(v)
            except ValueError:
                return None
    return None


def provjeri(log=lambda s: None):
    nalazi, sirovo = [], {}

    if not JE_WINDOWS:
        nalazi.append(nalaz(
            "Lozinke i pristupi", "Provjera politike lozinki nije izvršena", INFO,
            "Ova provjera radi samo na Windowsu.",
            preporuka="Pokrenuti alat na mašini klijenta."))
        return {"nalazi": nalazi, "sirovo": sirovo}

    log("Politika lozinki")
    u_domenu = False
    cs = None
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "(Get-CimInstance Win32_ComputerSystem).PartOfDomain"],
            capture_output=True, text=True, timeout=25,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        u_domenu = "true" in (r.stdout or "").strip().lower()
    except Exception:
        pass

    tekst = _net_accounts(domen=u_domenu) or _net_accounts(domen=False)
    sirovo["izvor"] = "domen" if u_domenu else "lokalno"
    sirovo["ispis"] = tekst
    if not tekst.strip():
        nalazi.append(nalaz(
            "Lozinke i pristupi", "Politika lozinki nije očitana", INFO,
            "Komanda net accounts nije vratila podatke."))
        return {"nalazi": nalazi, "sirovo": sirovo}

    duzina = _broj(tekst, "Minimum password length", "Minimalna dužina lozinke")
    maks_dana = _broj(tekst, "Maximum password age", "Maksimalna starost lozinke")
    istorija = _broj(tekst, "Length of password history", "Dužina istorije lozinki")
    prag = _broj(tekst, "Lockout threshold", "Prag zaključavanja")
    trajanje = _broj(tekst, "Lockout duration", "Trajanje zaključavanja")
    sirovo.update({"min_duzina": duzina, "maks_starost": maks_dana,
                   "istorija": istorija, "prag_zakljucavanja": prag})

    gdje = "domena" if u_domenu else "ove mašine"
    red = [f"Minimalna dužina: {duzina if duzina is not None else '?'}",
           f"Maksimalna starost: {'nikad' if maks_dana == -1 else maks_dana}",
           f"Istorija: {istorija}",
           f"Prag zaključavanja: {'nema' if prag in (0, None) else prag}",
           f"Trajanje zaključavanja: {trajanje}"]

    if duzina is not None and duzina < 12:
        tez = VISOK if duzina < 8 else SREDNJI
        nalazi.append(nalaz(
            "Lozinke i pristupi", "Dozvoljene su prekratke lozinke", tez,
            f"Politika {gdje} traži najmanje {duzina} znakova.",
            "Lozinka od osam znakova se danas probija za nekoliko sati. Dužina je "
            "jedino što stvarno otežava pogađanje — više nego mješavina znakova.",
            "Podići minimum na 12 znakova, a za administratorske naloge na 16. "
            "Umjesto komplikovanih lozinki uvesti duge fraze od tri-četiri riječi.",
            sati=1, trosak=60, dokaz=red))
    elif duzina is not None:
        nalazi.append(nalaz(
            "Lozinke i pristupi", "Minimalna dužina lozinke je zadovoljavajuća",
            DOBRO, f"Traži se najmanje {duzina} znakova.", dokaz=red))

    if prag in (0, None):
        nalazi.append(nalaz(
            "Lozinke i pristupi", "Nalog se ne zaključava nakon pogrešnih pokušaja",
            VISOK,
            f"Politika {gdje} nema prag zaključavanja.",
            "Automatizovan napad može pokušavati lozinke bez ograničenja — "
            "hiljadama puta na sat, dok ne pogodi. Zaključavanje je jedina stvar "
            "koja ga zaustavlja.",
            "Postaviti zaključavanje nakon 10 neuspjelih pokušaja, u trajanju od "
            "15 minuta. Više od toga smeta korisnicima, manje ne zaustavlja napad.",
            sati=0.5, trosak=30, dokaz=red))
    else:
        nalazi.append(nalaz(
            "Lozinke i pristupi", "Zaključavanje naloga je uključeno", DOBRO,
            f"Nalog se zaključava nakon {prag} pokušaja.", dokaz=red))

    if maks_dana == -1:
        nalazi.append(nalaz(
            "Lozinke i pristupi", "Lozinke ne ističu nikad", NIZAK,
            f"Politika {gdje} nema rok isteka lozinke.",
            "Lozinka koja je procurila prije tri godine i dalje radi. Uz to, "
            "prečesto mijenjanje tjera ljude na Lozinka1, Lozinka2 — pa ni to "
            "nije rješenje.",
            "Umjesto roka isteka uvesti dvofaktorsku zaštitu i obaveznu promjenu "
            "samo kad postoji sumnja da je lozinka procurila.",
            sati=0.5, dokaz=red))

    return {"nalazi": nalazi, "sirovo": sirovo}
