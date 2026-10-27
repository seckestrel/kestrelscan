# -*- coding: utf-8 -*-
"""Uređaji koje alat ne može sam očitati, i ispravke koje unosi tehničar.

Dvije stvari koje nijedan skener ne može:

1. Mašina koja je ugašena, pokvarena ili van domena ipak postoji i mora ući u
   popis. Inače izvještaj tvrdi da firma ima deset računara, a ima dvanaest.

2. Procjena rada i troška koju alat izračuna je prosjek, ne nalaz. Ažuriranje
   dva programa alat procijeni na dva sata, a tehničaru koji zna mašinu to je
   deset minuta. Zato tehničar mora moći ispraviti procjenu i napisati zašto —
   a stara vrijednost ostaje u zapisima.
"""
from .nalaz import nalaz, VISOK, SREDNJI, NIZAK, INFO, DOBRO

VRSTE = ["Stoni računar", "Prenosivi računar", "Server", "Štampač", "Skener",
         "Svič", "Ruter", "Pristupna tačka", "NAS", "Kamera", "UPS",
         "Telefon / IP telefon", "Terminal / kasa", "Drugo"]

STANJA = {
    "ispravan": ("Ispravan — bez potrebe za intervencijom", DOBRO),
    "radi_uz_primjedbu": ("Radi, uz primjedbu", NIZAK),
    "za_servis": ("Potreban servis", SREDNJI),
    "za_zamjenu": ("Potrebna zamjena", SREDNJI),
    "ne_radi": ("Ne radi", VISOK),
    "nije_pristupacan": ("Nije bio dostupan za pregled", INFO),
}


def u_nalaz(u):
    """u: {vrsta, naziv, proizvodjac, model, serijski, ip, lokacija, stanje,
           starost, napomena, sati, trosak}"""
    stanje_kljuc = (u.get("stanje") or "nije_pristupacan").strip()
    opis_stanja, tezina = STANJA.get(stanje_kljuc,
                                     ("Stanje nije određeno", INFO))

    naziv = (u.get("naziv") or "").strip() or "Uređaj bez naziva"
    vrsta = (u.get("vrsta") or "Drugo").strip()

    identitet = []
    for k, oznaka in (("proizvodjac", ""), ("model", ""), ("serijski", "serijski br."),
                      ("ip", "IP"), ("lokacija", "lokacija")):
        v = (u.get(k) or "").strip()
        if v:
            identitet.append(f"{oznaka} {v}".strip())

    god = u.get("starost")
    try:
        god = float(god) if god not in (None, "") else None
    except (TypeError, ValueError):
        god = None

    utvrdjeno = f"{vrsta}: {naziv}"
    if identitet:
        utvrdjeno += " — " + ", ".join(identitet)
    utvrdjeno += f". Stanje: {opis_stanja.lower()}."
    if god is not None:
        utvrdjeno += f" Procijenjena starost: {god:g} godina."
    utvrdjeno += " Uneseno ručno, na osnovu fizičkog pregleda."

    rizik = ""
    preporuka = ""
    if stanje_kljuc == "ne_radi":
        rizik = ("Uređaj je u popisu opreme, a ne radi. Ako je u pitanju nešto "
                 "što nekome treba za rad, to je zastoj koji traje.")
        preporuka = "Utvrditi da li se isplati popravka ili zamjena."
    elif stanje_kljuc == "za_zamjenu":
        rizik = ("Uređaj radi, ali je pri kraju vijeka. Kvar je pitanje vremena, "
                 "a zamjena pod pritiskom uvijek košta više.")
        preporuka = "Uvrstiti u plan nabavke."
    elif stanje_kljuc == "za_servis":
        preporuka = "Zakazati servis prije nego stanje pređe u kvar."
    elif stanje_kljuc == "nije_pristupacan":
        rizik = ("Uređaj nije pregledan, pa se o njegovom stanju ne zna ništa. "
                 "Nepregledano nije isto što i ispravno.")
        preporuka = "Pregledati pri sljedećoj posjeti."

    sati = u.get("sati")
    trosak = u.get("trosak")
    try:
        sati = float(sati) if sati not in (None, "") else None
    except (TypeError, ValueError):
        sati = None
    try:
        trosak = float(trosak) if trosak not in (None, "") else None
    except (TypeError, ValueError):
        trosak = None

    napomena = (u.get("napomena") or "").strip()

    n = nalaz("Uređaji", f"{vrsta}: {naziv}", tezina, utvrdjeno, rizik, preporuka,
              sati, trosak,
              dokaz=[f"Ručni unos tehničara — {opis_stanja}"]
                    + ([f"Napomena: {napomena}"] if napomena else []))
    n["rucni"] = True
    n["uredjaj"] = {k: u.get(k) for k in
                    ("vrsta", "naziv", "proizvodjac", "model", "serijski", "ip",
                     "lokacija", "stanje", "starost")}
    if napomena:
        n["komentar"] = napomena
    return n


def primijeni_ispravku(n, izmjene):
    """Promijeni procjenu i dodaj komentar. Vrati šta je promijenjeno,
    sa starom i novom vrijednošću — to ide u zapise."""
    promjene = {}

    for polje, pretvori in (("sati", float), ("trosak", float)):
        if polje not in izmjene:
            continue
        nova = izmjene[polje]
        if nova in ("", None):
            nova = None
        else:
            try:
                nova = pretvori(nova)
            except (TypeError, ValueError):
                continue
        staro = n.get(polje)
        if staro != nova:
            n.setdefault("izvorno", {}).setdefault(polje, staro)
            promjene[polje] = {"prije": staro, "poslije": nova}
            n[polje] = nova

    if "tezina" in izmjene:
        nova = (izmjene["tezina"] or "").strip()
        if nova in (VISOK, SREDNJI, NIZAK, INFO, DOBRO) and nova != n.get("tezina"):
            n.setdefault("izvorno", {}).setdefault("tezina", n.get("tezina"))
            promjene["tezina"] = {"prije": n.get("tezina"), "poslije": nova}
            n["tezina"] = nova

    if "komentar" in izmjene:
        tekst = (izmjene["komentar"] or "").strip()
        if tekst != (n.get("komentar") or ""):
            promjene["komentar"] = {"prije": n.get("komentar") or "",
                                    "poslije": tekst}
            n["komentar"] = tekst

    if promjene:
        n["izmijenjeno"] = True
    return promjene
