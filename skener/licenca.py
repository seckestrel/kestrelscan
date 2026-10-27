# -*- coding: utf-8 -*-
"""Aktivacija i licenciranje Windowsa i Officea.

Neaktiviran Windows nije samo kozmetika. Sistem u obavještajnom režimu ne dobija
sve ispravke, pozadina se gasi, a kod inspekcije je to nelicencirani softver na
poslovnoj opremi — kazna ide firmi, ne onome ko je instalirao.

Česti slučaj kod malih firmi: kupi se računar sa OEM Windowsom, poslije se
reinstalira sa tuđim ključem ili KMS aktivatorom, pa „radi" dok ne prestane.
"""
import json
import subprocess
import sys

from .nalaz import nalaz, VISOK, SREDNJI, NIZAK, INFO, DOBRO

JE_WINDOWS = sys.platform.startswith("win")

# SoftwareLicensingProduct.LicenseStatus
STANJE = {
    0: ("Nije licenciran", VISOK),
    1: ("Licenciran", DOBRO),
    2: ("Početni rok (OOB grace)", SREDNJI),
    3: ("Produženi rok (OOT grace)", SREDNJI),
    4: ("Rok zbog neoriginalne kopije", VISOK),
    5: ("Obavještajni režim — nije aktiviran", VISOK),
    6: ("Produženi rok", SREDNJI),
}

KANAL = {"OEM": "OEM — vezan za ovu mašinu",
         "Retail": "Retail — prenosiv na drugu mašinu",
         "Volume:MAK": "Volume MAK — firmski ključ",
         "Volume:GVLK": "Volume KMS — traži KMS server u mreži"}


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


def _lista(x):
    if x is None:
        return []
    return x if isinstance(x, list) else [x]


def provjeri(log=lambda s: None):
    nalazi, sirovo = [], {}

    if not JE_WINDOWS:
        nalazi.append(nalaz(
            "Licence", "Provjera licenci nije izvršena", INFO,
            "Ova provjera radi samo na Windowsu.",
            preporuka="Pokrenuti alat na mašini klijenta."))
        return {"nalazi": nalazi, "sirovo": sirovo}

    log("Aktivacija Windowsa i Officea")
    proizvodi = _lista(_ps(
        "Get-CimInstance SoftwareLicensingProduct -Filter "
        "\"PartialProductKey IS NOT NULL\" | Select-Object Name,Description,"
        "LicenseStatus,LicenseStatusReason,GracePeriodRemaining,"
        "ProductKeyChannel,PartialProductKey,GenuineStatus | ConvertTo-Json -Compress"))

    if not proizvodi:
        nalazi.append(nalaz(
            "Licence", "Stanje aktivacije nije očitano", INFO,
            "Upit o licencama nije vratio rezultat. Servis za licenciranje je "
            "možda isključen ili nalog nema prava.",
            preporuka="Provjeriti ručno: u komandnoj liniji `slmgr /dli`.",
            dokaz=["Get-CimInstance SoftwareLicensingProduct — bez rezultata"]))
        return {"nalazi": nalazi, "sirovo": sirovo}

    sirovo["proizvodi"] = proizvodi
    redovi, windows_nalazi, office_nalazi = [], [], []

    for p in proizvodi:
        ime = p.get("Name") or ""
        opis = p.get("Description") or ""
        st = p.get("LicenseStatus")
        opis_st, tezina = STANJE.get(st, ("Nepoznato stanje", INFO))
        kanal = p.get("ProductKeyChannel") or ""
        dani = p.get("GracePeriodRemaining")
        preostalo = f"{int(dani) // 1440} dana" if dani else ""

        redovi.append([ime[:46], opis_st, KANAL.get(kanal, kanal or "—"),
                       preostalo or "—",
                       "…" + str(p.get("PartialProductKey") or "")])

        je_office = "office" in (ime + opis).lower()
        (office_nalazi if je_office else windows_nalazi).append(
            (ime, opis_st, tezina, kanal, preostalo))

    nalazi.append(nalaz(
        "Licence", f"Stanje licenci — {len(proizvodi)} proizvoda", INFO,
        "Očitano stanje aktivacije za sve proizvode sa unesenim ključem na ovoj "
        "mašini.",
        preporuka="Uporediti sa kupljenim licencama. Broj instalacija mora "
                  "odgovarati broju kupljenih licenci, ne broju računara.",
        tabela={"zaglavlje": ["Proizvod", "Stanje", "Vrsta ključa",
                              "Rok", "Ključ"],
                "redovi": redovi, "sirine": [34, 22, 22, 11, 11]}))

    # --- Windows ---
    losi_w = [x for x in windows_nalazi if x[2] in (VISOK, SREDNJI)]
    if losi_w:
        najgori = VISOK if any(x[2] == VISOK for x in losi_w) else SREDNJI
        nalazi.append(nalaz(
            "Licence", "Windows nije ispravno aktiviran", najgori,
            "; ".join(f"{i} — {s}" + (f", preostalo {r}" if r else "")
                      for i, s, _, _, r in losi_w),
            "Neaktiviran Windows ne dobija sve ispravke i vremenom prelazi u "
            "obavještajni režim. Za firmu je to i pravno pitanje: nelicencirani "
            "softver na poslovnoj opremi je prekršaj, a odgovornost je na firmi.",
            "Aktivirati sistem kupljenim ključem. Ako je mašina kupljena sa "
            "Windowsom, ključ je upisan u firmver i ne treba ga tražiti na "
            "naljepnici.",
            sati=0.5 * len(losi_w), trosak=30 * len(losi_w),
            dokaz=[f"{i}: {s} | kanal: {k or '—'}" for i, s, _, k, _ in losi_w]))
    elif windows_nalazi:
        nalazi.append(nalaz(
            "Licence", "Windows je uredno aktiviran", DOBRO,
            "; ".join(f"{i} — {s}" for i, s, _, _, _ in windows_nalazi)))

    # --- KMS bez servera je mina koja čeka ---
    kms = [x for x in windows_nalazi if x[3] == "Volume:GVLK"]
    if kms:
        nalazi.append(nalaz(
            "Licence", "Windows je aktiviran preko KMS-a", NIZAK,
            "; ".join(f"{i} — {s}" for i, s, _, _, _ in kms),
            "KMS aktivacija važi 180 dana i obnavlja se samo dok mašina vidi KMS "
            "server. Prenosni računar koji mjesecima ne dolazi u kancelariju "
            "jednog dana prestane biti aktiviran usred posla. Ako KMS server u "
            "firmi uopšte ne postoji, aktivacija je urađena tuđim serverom ili "
            "alatom — to nije licenca.",
            "Provjeriti postoji li KMS server u firmi i da li su licence stvarno "
            "kupljene. Ako nisu, nabaviti ispravne ključeve.",
            sati=1, trosak=60,
            dokaz=[f"{i}: Volume:GVLK (KMS)" for i, *_ in kms]))

    # --- Office ---
    losi_o = [x for x in office_nalazi if x[2] in (VISOK, SREDNJI)]
    if losi_o:
        nalazi.append(nalaz(
            "Licence", "Office nije ispravno aktiviran", SREDNJI,
            "; ".join(f"{i} — {s}" + (f", preostalo {r}" if r else "")
                      for i, s, _, _, r in losi_o),
            "Office u neaktiviranom stanju poslije roka radi samo za čitanje — "
            "dokumenti se otvaraju, ali se ne mogu snimiti. Kod knjigovodstva i "
            "administracije to je zastoj istog dana.",
            "Aktivirati kupljenom licencom ili preći na pretplatu, zavisno šta je "
            "firmi jeftinije za broj korisnika.",
            sati=0.5 * len(losi_o), trosak=30 * len(losi_o),
            dokaz=[f"{i}: {s}" for i, s, _, _, _ in losi_o]))
    elif office_nalazi:
        nalazi.append(nalaz(
            "Licence", "Office je uredno aktiviran", DOBRO,
            "; ".join(f"{i} — {s}" for i, s, _, _, _ in office_nalazi)))

    # --- ključ iz firmvera: dokaz da je mašina kupljena sa Windowsom ---
    sluzba = _ps("Get-CimInstance SoftwareLicensingService | Select-Object "
                 "OA3xOriginalProductKey,OA3xOriginalProductKeyDescription,"
                 "KeyManagementServiceMachine | ConvertTo-Json -Compress")
    if sluzba:
        sirovo["sluzba"] = {k: v for k, v in sluzba.items()
                            if k != "OA3xOriginalProductKey"}
        oem = (sluzba.get("OA3xOriginalProductKeyDescription") or "").strip()
        ima_oem = bool((sluzba.get("OA3xOriginalProductKey") or "").strip())
        kms_server = (sluzba.get("KeyManagementServiceMachine") or "").strip()
        detalji = []
        if ima_oem:
            detalji.append(f"U firmveru postoji originalni ključ: {oem or 'OEM'}")
        if kms_server:
            detalji.append(f"Podešen KMS server: {kms_server}")
        if detalji:
            nalazi.append(nalaz(
                "Licence", "Podaci o porijeklu licence", INFO,
                ". ".join(detalji) + ".",
                preporuka="Ako u firmveru postoji OEM ključ a sistem je aktiviran "
                          "drugim putem, mašina ima licencu koja se ne koristi — "
                          "vrijedi je vratiti umjesto kupovati novu.",
                dokaz=detalji))

    return {"nalazi": nalazi, "sirovo": sirovo}
