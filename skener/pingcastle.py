# -*- coding: utf-8 -*-
"""Pokretanje PingCastle alata i čitanje ocjene iz njegovog XML izvještaja.

PingCastle.exe se stavi u folder tools/ pored alata. Besplatan je i ne traži
instalaciju, pa radi sa USB-a.
"""
import glob
import os
import subprocess
import sys
import xml.etree.ElementTree as ET

from .nalaz import nalaz, VISOK, SREDNJI, NIZAK, INFO, DOBRO

KATEGORIJE = {
    "StaleObjects": "Zapušteni objekti (stari nalozi, zastarjeli sistemi)",
    "PrivilegedAccounts": "Privilegovani nalozi",
    "Trusts": "Odnosi povjerenja sa drugim domenima",
    "Anomalies": "Nepravilnosti u postavkama",
}


def putanja_exe(korijen):
    for ime in ("PingCastle.exe", "pingcastle.exe"):
        p = os.path.join(korijen, "tools", ime)
        if os.path.isfile(p):
            return p
    return None


def provjeri(korijen, domen, izlaz_dir, log=lambda s: None):
    nalazi, sirovo = [], {}
    exe = putanja_exe(korijen)

    if not sys.platform.startswith("win"):
        nalazi.append(nalaz(
            "Active Directory", "PingCastle nije pokrenut", INFO,
            "PingCastle radi samo na Windowsu.",
            preporuka="Pokrenuti alat sa USB-a na mašini u domenu."))
        return {"nalazi": nalazi, "sirovo": sirovo}

    if not exe:
        nalazi.append(nalaz(
            "Active Directory", "PingCastle nije pronađen", INFO,
            "U folderu tools/ nema PingCastle.exe.",
            preporuka="Preuzmi besplatnu verziju sa pingcastle.com i kopiraj "
                      "PingCastle.exe u folder tools/ pored alata."))
        return {"nalazi": nalazi, "sirovo": sirovo}

    log(f"Pokrećem PingCastle za domen {domen} (traje 5–15 minuta)")
    try:
        subprocess.run([exe, "--healthcheck", "--server", domen, "--no-enum-limit"],
                       cwd=izlaz_dir, capture_output=True, text=True, timeout=1800,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except subprocess.TimeoutExpired:
        nalazi.append(nalaz("Active Directory", "PingCastle je prekinut zbog vremena",
                            INFO, "Analiza je trajala duže od 30 minuta."))
        return {"nalazi": nalazi, "sirovo": sirovo}
    except Exception as e:
        nalazi.append(nalaz("Active Directory", "PingCastle nije uspio", INFO, str(e)))
        return {"nalazi": nalazi, "sirovo": sirovo}

    xmls = sorted(glob.glob(os.path.join(izlaz_dir, "ad_hc_*.xml")),
                  key=os.path.getmtime, reverse=True)
    htmls = sorted(glob.glob(os.path.join(izlaz_dir, "ad_hc_*.html")),
                   key=os.path.getmtime, reverse=True)
    sirovo["html"] = os.path.basename(htmls[0]) if htmls else None

    if not xmls:
        nalazi.append(nalaz("Active Directory", "PingCastle nije napravio izvještaj",
                            INFO, "Nema ad_hc_*.xml u izlaznom folderu."))
        return {"nalazi": nalazi, "sirovo": sirovo}

    try:
        korijen_xml = ET.parse(xmls[0]).getroot()

        def broj(tag):
            el = korijen_xml.find(tag)
            try:
                return int(el.text)
            except Exception:
                return None

        ukupno = broj("GlobalScore")
        djelovi = {k: broj(k + "Score") for k in KATEGORIJE}
        sirovo["ocjena"] = ukupno
        sirovo["po_kategorijama"] = djelovi

        pravila = []
        for r in korijen_xml.iter("HealthcheckRiskRule"):
            pravila.append({
                "id": (r.findtext("RiskId") or "").strip(),
                "bodovi": r.findtext("Points"),
                "kategorija": (r.findtext("Category") or "").strip(),
                "opis": (r.findtext("Rationale") or "").strip(),
            })
        pravila.sort(key=lambda p: -int(p["bodovi"] or 0))
        sirovo["pravila"] = pravila[:40]

        if ukupno is None:
            tez = INFO
        elif ukupno >= 70:
            tez = VISOK
        elif ukupno >= 40:
            tez = SREDNJI
        elif ukupno >= 20:
            tez = NIZAK
        else:
            tez = DOBRO

        opis_dj = ", ".join(f"{KATEGORIJE[k].split('(')[0].strip()}: {v}"
                            for k, v in djelovi.items() if v is not None)
        nalazi.append(nalaz(
            "Active Directory", f"Ocjena rizika domena: {ukupno}/100", tez,
            f"PingCastle je ocijenio domen {domen} sa {ukupno} bodova rizika "
            f"(niže je bolje; ispod 30 se smatra dobrim). Po kategorijama — {opis_dj}.",
            "Visoka ocjena obično znači da je domen postavljen i ostavljen — "
            "nalozi se gomilaju, prava se ne revidiraju, stare postavke ostaju.",
            "Krenuti od pravila sa najviše bodova u priloženom PingCastle izvještaju.",
            sati=4, trosak=240,
            dokaz=[f'{p["bodovi"]} bod(a) — {p["id"]}: {p["opis"][:110]}'
                   for p in pravila[:10]]))

        for p in pravila[:5]:
            if int(p["bodovi"] or 0) >= 10:
                nalazi.append(nalaz(
                    "Active Directory", p["id"] or "Pravilo bez naziva", SREDNJI,
                    p["opis"][:400] or "Vidjeti PingCastle izvještaj.",
                    preporuka="Detalji i tačan postupak ispravke su u priloženom "
                              "PingCastle HTML izvještaju.",
                    sati=1, dokaz=[f'{p["bodovi"]} bodova, kategorija {p["kategorija"]}']))
    except Exception as e:
        nalazi.append(nalaz("Active Directory", "Izvještaj se nije mogao pročitati",
                            INFO, str(e)))

    return {"nalazi": nalazi, "sirovo": sirovo}
