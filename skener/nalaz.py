# -*- coding: utf-8 -*-
"""Zajednički oblik nalaza koji svi moduli vraćaju."""

VISOK = "visok"
SREDNJI = "srednji"
NIZAK = "nizak"
INFO = "info"
DOBRO = "dobro"

TEZINA_RED = {VISOK: 0, SREDNJI: 1, NIZAK: 2, INFO: 3, DOBRO: 4}

# koliko bodova nosi propust po težini (oduzima se od maksimuma)
BODOVI = {VISOK: 3, SREDNJI: 2, NIZAK: 1, INFO: 0, DOBRO: 0}

# najviše bodova koje jedna oblast može izgubiti, bez obzira na broj
# propusta u njoj — deset propusta u istoj oblasti je jedan problem
TAVAN_PO_OBLASTI = 5


def nalaz(oblast, naslov, tezina, utvrdjeno, rizik="", preporuka="",
          sati=None, trosak=None, dokaz=None, tabela=None):
    """Jedan nalaz u izvještaju.

    tabela: {"zaglavlje": [...], "redovi": [[...], ...]} — prikazuje se kao
    prava tabela u izvještaju, umjesto kao niz redova dokaza.
    """
    return {
        "oblast": oblast,
        "naslov": naslov,
        "tezina": tezina,
        "utvrdjeno": utvrdjeno,
        "rizik": rizik,
        "preporuka": preporuka,
        "sati": sati,
        "trosak": trosak,
        "dokaz": dokaz or [],
        "tabela": tabela,
    }


def ocjena(nalazi, _zastarjelo=None):
    """Bodovi 0-32 i nivo, po KestrelSec skali.

    `nalazi` je CIJELI spisak nalaza, ne samo propusti.

    Bodovi se ne oduzimaju neograničeno. Svaka oblast može izgubiti najviše
    TAVAN_PO_OBLASTI bodova — deset propusta u istoj oblasti je i dalje jedan
    problem, ne deset. Bez toga se skala zasiti: firma sa 25 propusta i firma
    sa 50 propusta obje dobiju nulu, pa se na sljedećem pregledu ne vidi da je
    nešto sređeno.

    Računa se udio izgubljenog od onoga što se u pregledanim oblastima uopšte
    moglo izgubiti, pa se taj udio prenese na skalu 0-32. Oblast koja nije
    provjerena ne ulazi ni u brojilac ni u imenilac.
    """
    maks = 32
    mjerljivi = [n for n in nalazi
                 if n.get("tezina") in (VISOK, SREDNJI, NIZAK, DOBRO)]
    if not mjerljivi:
        return {"bodovi": None, "maks": maks, "nivo": "Nije ocijenjeno",
                "opis": "Nijedna provjera nije dala mjerljiv nalaz",
                "mjerljivo": False, "oblasti": [], "oduzeto": 0, "moguce": 0}

    po_oblasti = {}
    for n in mjerljivi:
        po_oblasti.setdefault(n.get("oblast") or "Ostalo", []).append(n)

    oblasti, oduzeto = [], 0
    for ime in sorted(po_oblasti):
        sirovo = sum(BODOVI.get(n["tezina"], 0) for n in po_oblasti[ime])
        izgubljeno = min(TAVAN_PO_OBLASTI, sirovo)
        oduzeto += izgubljeno
        oblasti.append({
            "oblast": ime,
            "izgubljeno": izgubljeno,
            "tavan": TAVAN_PO_OBLASTI,
            "preko_tavana": max(0, sirovo - TAVAN_PO_OBLASTI),
            "propusta": len([n for n in po_oblasti[ime]
                             if n["tezina"] in (VISOK, SREDNJI, NIZAK)]),
        })

    moguce = TAVAN_PO_OBLASTI * len(oblasti)
    bodovi = int(round(maks * (1 - oduzeto / moguce))) if moguce else maks
    bodovi = max(0, min(maks, bodovi))

    if bodovi <= 10:
        nivo, opis = "Nivo 0\u20131", "Osnovna za\u0161tita nedostaje"
    elif bodovi <= 20:
        nivo, opis = "Nivo 1", "Osnove postoje, sa rupama"
    elif bodovi <= 27:
        nivo, opis = "Nivo 2", "Kontrolisano stanje"
    else:
        nivo, opis = "Nivo 3", "Upravljano stanje"
    return {"bodovi": bodovi, "maks": maks, "nivo": nivo, "opis": opis,
            "mjerljivo": True, "oblasti": oblasti,
            "oduzeto": oduzeto, "moguce": moguce}


def sortiraj(nalazi):
    return sorted(nalazi, key=lambda n: TEZINA_RED.get(n["tezina"], 9))
