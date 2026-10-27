# -*- coding: utf-8 -*-
"""Provjera da li su mail adrese firme bile u poznatim curenjima podataka.

Have I Been Pwned traži ključ (oko 4 $ mjesečno). Bez ključa modul javi da
provjera nije izvršena umjesto da izmišlja rezultat.

Servis strogo ograničava broj upita prema pretplati — najjeftiniji ključ
dozvoljava deset upita u minuti, dakle jedan upit na šest sekundi. Ako se ide
brže, servis vraća 429 i upit se mora ponoviti, nikad preskočiti: preskočena
adresa u izvještaju izgleda kao čista, a to je najgora moguća greška.
"""
import re
import time

import requests

from .nalaz import nalaz, VISOK, SREDNJI, INFO, DOBRO

API = "https://haveibeenpwned.com/api/v3/breachedaccount/{}"

# Razmak između upita po pretplati (sekundi). Pwned 1 = 10 upita/min.
RAZMAK = {"pwned1": 6.5, "pwned2": 1.4, "pwned3": 0.8, "pwned4": 0.3}
PODRAZUMIJEVANI_RAZMAK = RAZMAK["pwned1"]

MAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")


def _jedna(adresa, zaglavlja, log, pokusaja=4):
    """Vrati ('pogodjena', [curenja]) | ('cista', None) | ('kljuc', poruka)
    | ('greska', poruka). Na 429 čeka onoliko koliko servis traži i ponovi."""
    cekanje = 0.0
    for pokusaj in range(1, pokusaja + 1):
        if cekanje:
            time.sleep(cekanje)
        try:
            r = requests.get(API.format(requests.utils.quote(adresa, safe="")),
                             headers=zaglavlja,
                             params={"truncateResponse": "false"}, timeout=20)
        except Exception as e:
            cekanje = 3.0 * pokusaj
            if pokusaj == pokusaja:
                return "greska", f"{type(e).__name__}: {e}"
            log(f"    veza pukla, ponavljam za {cekanje:g} s")
            continue

        if r.status_code == 200:
            return "pogodjena", [
                {"ime": b.get("Name"), "datum": (b.get("BreachDate") or "")[:4],
                 "podaci": ", ".join(b.get("DataClasses") or [])}
                for b in r.json()]
        if r.status_code == 404:
            return "cista", None
        if r.status_code in (401, 403):
            return "kljuc", f"servis je odbio ključ ({r.status_code})"
        if r.status_code == 429:
            # servis kaže tačno koliko treba čekati
            try:
                cekanje = float(r.headers.get("retry-after", 6)) + 0.5
            except ValueError:
                cekanje = 6.5
            log(f"    servis traži pauzu od {cekanje:g} s, ponavljam istu adresu")
            continue
        if r.status_code >= 500:
            cekanje = 4.0 * pokusaj
            log(f"    servis vraća {r.status_code}, ponavljam za {cekanje:g} s")
            continue
        return "greska", f"neočekivan odgovor {r.status_code}"

    return "greska", "ograničenje broja upita — nije uspjelo ni nakon ponavljanja"


def provjeri(adrese, kljuc=None, log=lambda s: None, razmak=None):
    nalazi = []
    sirovo = {"provjereno": [], "pogodjeni": {}, "neprovjereno": {}}

    # ukloni duplikate, zadrži redoslijed
    ocisceno, vidjeno = [], set()
    for a in adrese:
        a = (a or "").strip().strip(",;").lower()
        if a and a not in vidjeno:
            vidjeno.add(a)
            ocisceno.append(a)

    neispravne = [a for a in ocisceno if not MAIL.match(a)]
    adrese = [a for a in ocisceno if MAIL.match(a)]

    if neispravne:
        log(f"Preskačem {len(neispravne)} unosa koji nisu mail adrese: "
            + ", ".join(neispravne[:5]))

    if not adrese:
        if neispravne:
            nalazi.append(nalaz(
                "Lozinke i pristupi", "Nijedna adresa nije provjerena", INFO,
                "Unešeni tekst ne sadrži ispravnu mail adresu: "
                + ", ".join(neispravne[:8]),
                preporuka="Adrese se unose odvojene zarezom, npr. "
                          "info@firma.ba, racunovodstvo@firma.ba"))
        return {"nalazi": nalazi, "sirovo": sirovo}

    if not kljuc:
        nalazi.append(nalaz(
            "Lozinke i pristupi", "Provjera procurjelih naloga nije izvršena", INFO,
            f"Nije unesen HIBP ključ, pa {len(adrese)} adresa nije provjereno.",
            preporuka="Ključ se uzima na haveibeenpwned.com/API/Key (oko 4 $ mjesečno) "
                      "i unosi se u postavkama alata. Do tada se adrese mogu "
                      "provjeriti ručno na haveibeenpwned.com.",
            dokaz=adrese))
        return {"nalazi": nalazi, "sirovo": sirovo}

    razmak = razmak if razmak is not None else PODRAZUMIJEVANI_RAZMAK
    zaglavlja = {"hibp-api-key": kljuc, "user-agent": "KestrelScan/1.0"}
    pogodjeni, neprovjereno = {}, {}

    log(f"Provjeravam {len(adrese)} adresa, sa pauzom od {razmak:g} s između upita "
        f"(servis to traži)")

    for i, a in enumerate(adrese, 1):
        log(f"  [{i}/{len(adrese)}] {a}")
        ishod, podatak = _jedna(a, zaglavlja, log)

        if ishod == "kljuc":
            nalazi.append(nalaz(
                "Lozinke i pristupi", "HIBP ključ nije prihvaćen", INFO,
                f"Provjera je prekinuta — {podatak}.",
                preporuka="Provjeriti ključ u postavkama alata. Do tada se adrese "
                          "mogu provjeriti ručno na haveibeenpwned.com.",
                dokaz=adrese))
            sirovo["neprovjereno"] = {x: "ključ odbijen" for x in adrese}
            return {"nalazi": nalazi, "sirovo": sirovo}

        if ishod == "pogodjena":
            pogodjeni[a] = podatak
            sirovo["provjereno"].append(a)
            log(f"    pronađeno u {len(podatak)} curenja")
        elif ishod == "cista":
            sirovo["provjereno"].append(a)
            log("    čisto")
        else:
            neprovjereno[a] = podatak
            log(f"    NIJE PROVJERENO: {podatak}")

        if i < len(adrese):
            time.sleep(razmak)

    sirovo["pogodjeni"] = pogodjeni
    sirovo["neprovjereno"] = neprovjereno

    if pogodjeni:
        redovi = []
        for a, lista in pogodjeni.items():
            for b in lista:
                redovi.append(f'{a} — {b["ime"]} ({b["datum"]}): {b["podaci"]}')
        nalazi.append(nalaz(
            "Lozinke i pristupi", "Poslovne adrese su bile u curenjima podataka", VISOK,
            f'{len(pogodjeni)} od {len(sirovo["provjereno"])} provjerenih adresa '
            f'pojavilo se u poznatim curenjima: ' + ", ".join(pogodjeni),
            "Lozinke korištene na tim servisima treba smatrati javno dostupnim. "
            "Ako se ista lozinka koristi i na poslovnom mailu, nalog je otvoren.",
            "Promijeniti lozinke na svim servisima gdje su te adrese korištene, "
            "uvesti menadžer lozinki i uključiti dvofaktorsku zaštitu.",
            sati=2, trosak=120, dokaz=redovi))

    ciste = [a for a in sirovo["provjereno"] if a not in pogodjeni]
    if ciste:
        nalazi.append(nalaz(
            "Lozinke i pristupi",
            f"{len(ciste)} adresa nije u poznatim curenjima", DOBRO,
            "Provjereno i čisto: " + ", ".join(ciste),
            dokaz=ciste))

    # Adresa koja nije provjerena ne smije proći kao čista.
    if neprovjereno:
        nalazi.append(nalaz(
            "Lozinke i pristupi", "Neke adrese nisu provjerene", INFO,
            f"{len(neprovjereno)} od {len(adrese)} adresa nije provjereno: "
            + ", ".join(neprovjereno),
            "Neprovjerena adresa nije isto što i čista — za nju se ne zna ništa.",
            "Ponoviti provjeru za te adrese, ili ih provjeriti ručno na "
            "haveibeenpwned.com.",
            dokaz=[f"{a}: {r}" for a, r in neprovjereno.items()]))

    return {"nalazi": nalazi, "sirovo": sirovo}
