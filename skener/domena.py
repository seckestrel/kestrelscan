# -*- coding: utf-8 -*-
"""Provjera mail domene: SPF, DKIM, DMARC, MX, DNSSEC.

Direktni DNS upiti — ne treba MXToolbox ni bilo kakav ključ.
"""
import re

import dns.resolver
import dns.exception

from .nalaz import nalaz, VISOK, SREDNJI, NIZAK, INFO, DOBRO

# Selektor je ime pod kojim provajder objavljuje DKIM ključ u DNS-u i svaki ga
# bira sam. Ne postoji način da se spisak selektora pročita iz DNS-a — mogu se
# samo pogađati poznati. Zato odsustvo ovdje nikad ne znači „nema DKIM-a".
SELEKTORI = [
    # najčešći kod nas
    "google", "selector1", "selector2", "default", "dkim", "mail", "mx",
    # Zoho, Titan, Hostinger, cPanel i registratori
    "zoho", "zmail", "titan1", "titan2",
    "hostingermail1", "hostingermail2", "hostingermail3",
    "cpanel", "x", "dkim1", "dkim2",
    # Proton, Fastmail, Yandex, Mail.ru
    "protonmail", "protonmail2", "protonmail3",
    "fm1", "fm2", "fm3", "mailru", "yandex",
    # servisi za slanje
    "k1", "k2", "k3", "s1", "s2", "s3", "sig1", "smtp", "mandrill",
    "sendgrid", "mailgun", "mg", "mailjet", "sparkpost", "scph0120",
    "everlytickey1", "everlytickey2", "pm", "pmta", "postmark",
    "brevo", "sendinblue", "amazonses", "ses",
    # ostali koji se sreću
    "key1", "key2", "m1", "mail1", "mailo", "dk", "ctct1", "ctct2",
]

# po MX zapisu se zna provajder, pa se prvo probaju njegovi selektori
PO_PROVAJDERU = {
    "google": ["google"],
    "outlook": ["selector1", "selector2"],
    "microsoft": ["selector1", "selector2"],
    "zoho": ["zoho", "zmail"],
    "titan": ["titan1", "titan2"],
    "hostinger": ["hostingermail1", "hostingermail2", "hostingermail3"],
    "yandex": ["mail", "yandex"],
    "protonmail": ["protonmail", "protonmail2", "protonmail3"],
    "proton": ["protonmail", "protonmail2", "protonmail3"],
    "fastmail": ["fm1", "fm2", "fm3"],
    "messagingengine": ["fm1", "fm2", "fm3"],
    "mailru": ["mailru"],
    "sendgrid": ["s1", "s2"],
    "mailgun": ["mg", "mailgun", "smtp"],
    "amazonaws": ["amazonses", "ses"],
    "mimecast": ["mimecast20200101", "mimecast"],
    "secureserver": ["default"],          # GoDaddy
    "one": ["default"],
}


def _selektori_za(mx, rucni=None):
    """Red kojim se selektori probaju: ručno unesen, pa oni koje koristi
    provajder iz MX zapisa, pa opšti spisak."""
    red = []
    for s in (rucni or "").replace(",", " ").split():
        s = s.strip().strip(".").removesuffix("._domainkey")
        if s and s not in red:
            red.append(s)

    spojeni_mx = " ".join(mx or []).lower()
    for kljuc, lista in PO_PROVAJDERU.items():
        if kljuc in spojeni_mx:
            for s in lista:
                if s not in red:
                    red.append(s)

    for s in SELEKTORI:
        if s not in red:
            red.append(s)
    return red


def _txt(ime, timeout=6):
    try:
        r = dns.resolver.Resolver()
        r.lifetime = timeout
        r.timeout = timeout
        odg = r.resolve(ime, "TXT")
        out = []
        for rr in odg:
            out.append(b"".join(rr.strings).decode("utf-8", "replace"))
        return out
    except Exception:
        return []


def _mx(ime, timeout=6):
    try:
        r = dns.resolver.Resolver()
        r.lifetime = timeout
        r.timeout = timeout
        return sorted((int(x.preference), str(x.exchange).rstrip("."))
                      for x in r.resolve(ime, "MX"))
    except Exception:
        return []


def _razrjesava(ime, tip="NS", timeout=5):
    try:
        r = dns.resolver.Resolver()
        r.lifetime = timeout
        r.timeout = timeout
        r.resolve(ime, tip)
        return True
    except dns.resolver.NXDOMAIN:
        return False
    except dns.resolver.NoAnswer:
        return True
    except Exception:
        return None  # DNS nedostupan


def provjeri(domena, log=lambda s: None, dkim_selektor=None):
    domena = domena.strip().lower().lstrip("@")
    nalazi = []
    sirovo = {"domena": domena}

    # Bez ovoga bi zatvoren DNS izgledao kao "domena nema nijedan zapis"
    # i izvještaj bi bio pun lažnih nalaza.
    log("Provjeravam da li DNS uopšte odgovara")
    if not _razrjesava("cloudflare.com") or not _razrjesava("google.com"):
        nalazi.append(nalaz(
            "Mail i domena", "Provjera domene nije izvršena", INFO,
            "DNS upiti sa ove mreže ne prolaze — ni poznata imena se ne razrješavaju.",
            preporuka="Pokrenuti provjeru domene sa druge veze (mobilni internet "
                      "ili vlastita kancelarija). Mreža klijenta vjerovatno "
                      "propušta samo upite ka svom DNS serveru."))
        sirovo["dns_nedostupan"] = True
        return {"nalazi": nalazi, "sirovo": sirovo}

    postoji = _razrjesava(domena)
    if postoji is False:
        nalazi.append(nalaz(
            "Mail i domena", "Domena ne postoji", SREDNJI,
            f"Upit za {domena} vraća NXDOMAIN — domena nije registrovana ili je ime pogrešno.",
            preporuka="Provjeriti tačan naziv domene sa klijentom."))
        sirovo["nxdomain"] = True
        return {"nalazi": nalazi, "sirovo": sirovo}

    # --- MX ---
    log(f"MX zapisi za {domena}")
    mx = _mx(domena)
    sirovo["mx"] = mx
    if not mx:
        nalazi.append(nalaz(
            "Mail i domena", "Domena nema MX zapis", SREDNJI,
            f"Upit za MX zapise domene {domena} nije vratio nijedan rezultat.",
            "Firma ne prima poštu na ovoj domeni, ili je DNS pogrešno podešen.",
            "Provjeriti kod registrara da li je domena aktivna i kod koga je pošta.",
            sati=0.5, dokaz=[f"dig +short MX {domena}  ->  (prazno)"]))
    else:
        nalazi.append(nalaz(
            "Mail i domena", "MX zapisi postoje", DOBRO,
            "Pošta je usmjerena na: " + ", ".join(h for _, h in mx[:3]),
            dokaz=[f"dig +short MX {domena}"] + [f"{p} {h}" for p, h in mx]))

    # --- SPF ---
    log("SPF zapis")
    txt = _txt(domena)
    sirovo["txt"] = txt
    spf = next((t for t in txt if t.lower().startswith("v=spf1")), None)
    sirovo["spf"] = spf
    if not spf:
        nalazi.append(nalaz(
            "Mail i domena", "Ne postoji SPF zapis", VISOK,
            "Domena nema SPF zapis.",
            "Bilo ko sa interneta može poslati poruku koja izgleda kao da dolazi "
            "sa vaše adrese. To je osnova prevare sa fakturom.",
            "Postaviti SPF zapis sa spiskom ovlaštenih pošiljalaca, prvo sa ~all, "
            "pa nakon provjere pooštriti na -all.",
            sati=1, trosak=60,
            dokaz=[f"dig +short TXT {domena}  ->  nema v=spf1"]))
    else:
        zavrsetak = "nepoznat"
        for ozn, opis in (("-all", "strogo"), ("~all", "blago"),
                          ("?all", "bez stava"), ("+all", "propušta sve")):
            if ozn in spf:
                zavrsetak = f"{ozn} ({opis})"
                break
        if "-all" in spf:
            nalazi.append(nalaz(
                "Mail i domena", "SPF zapis ispravno postavljen", DOBRO,
                f"SPF završava sa -all. Zapis: {spf}",
                dokaz=[f"dig +short TXT {domena}", spf]))
        elif "+all" in spf:
            nalazi.append(nalaz(
                "Mail i domena", "SPF propušta sve pošiljaoce", VISOK,
                f"SPF završava sa +all. Zapis: {spf}",
                "Zapis je postavljen tako da prihvata poruku sa bilo koje adrese. "
                "Gore je nego da ga nema, jer stvara lažan osjećaj zaštite.",
                "Zamijeniti +all sa -all nakon popisa legitimnih pošiljalaca.",
                sati=1, trosak=60, dokaz=[spf]))
        else:
            nalazi.append(nalaz(
                "Mail i domena", "SPF nije dovoljno strog", SREDNJI,
                f"SPF završava sa {zavrsetak}. Zapis: {spf}",
                "Poruka poslata sa neovlaštenog servera neće biti odbijena, nego "
                "samo označena kao sumnjiva — a mnogi serveri to ignorišu.",
                "Nakon popisa svih legitimnih pošiljalaca izmijeniti završetak u -all.",
                sati=1, trosak=60, dokaz=[spf]))

        br_lookup = len(re.findall(r"\b(include|a|mx|ptr|exists|redirect):?", spf))
        if br_lookup > 10:
            nalazi.append(nalaz(
                "Mail i domena", "SPF prelazi dozvoljenih 10 DNS upita", SREDNJI,
                f"Zapis sadrži oko {br_lookup} mehanizama koji traže DNS upit.",
                "Preko deset upita SPF provjera pada sa greškom i prestaje da štiti.",
                "Objediniti include zapise ili preći na SPF flattening.",
                sati=1, dokaz=[spf]))

    # --- DKIM ---
    log("DKIM selektori")
    red = _selektori_za(mx, dkim_selektor)
    nadjeni = []
    for sel in red:
        t = _txt(f"{sel}._domainkey.{domena}", timeout=3)
        if any("v=dkim1" in x.lower() or "p=" in x for x in t):
            nadjeni.append(sel)
    sirovo["dkim"] = nadjeni
    sirovo["dkim_provjereno"] = len(red)
    if nadjeni:
        nalazi.append(nalaz(
            "Mail i domena", "DKIM je uključen", DOBRO,
            "Pronađeni selektori: " + ", ".join(nadjeni),
            dokaz=[f"dig +short TXT {s}._domainkey.{domena}" for s in nadjeni]))
    else:
        # Selektor bira provajder i ne postoji način da se izlista iz DNS-a.
        # Zato „nije nađen na poznatim selektorima" nije isto što i „nema DKIM".
        nalazi.append(nalaz(
            "Mail i domena", "DKIM nije potvrđen", INFO,
            f"Provjereno je {len(red)} poznatih selektora i nijedan ne vraća "
            f"ključ za domenu {domena}. To ne znači nužno da DKIM ne radi — "
            f"selektor bira provajder i ne može se izlistati iz DNS-a.",
            "Ako poruke stvarno nisu potpisane, primalac ne može provjeriti da "
            "nisu mijenjane u prolazu, a DMARC politika se oslanja samo na SPF.",
            "Provjeriti u bilo kojoj poslanoj poruci: otvoriti izvorni oblik "
            "poruke (u Gmailu Prikaži original, u Outlooku Prikaži izvor) i naći "
            "red DKIM-Signature. U njemu piše s=selektor. Taj selektor unijeti u "
            "polje DKIM selektor i ponoviti provjeru. Ako reda DKIM-Signature "
            "nema, DKIM se uključuje u administraciji mail servisa.",
            dokaz=[f"provjereno selektora: {len(red)}",
                   "prvih deset: " + ", ".join(red[:10])]))

    # --- DMARC ---
    log("DMARC zapis")
    dm = _txt(f"_dmarc.{domena}")
    dmarc = next((t for t in dm if t.lower().startswith("v=dmarc1")), None)
    sirovo["dmarc"] = dmarc
    if not dmarc:
        nalazi.append(nalaz(
            "Mail i domena", "Ne postoji DMARC zapis", VISOK,
            "Domena nema DMARC politiku.",
            "Bez DMARC-a su SPF i DKIM samo preporuka — ne postoji pravilo šta "
            "server primaoca treba uraditi kad provjera padne, niti ijedan "
            "izvještaj o tome ko šalje u ime domene.",
            "Uvesti postepeno: prvo p=none uz prikupljanje izvještaja 30 dana, "
            "pa p=quarantine, pa p=reject.",
            sati=1.5, trosak=90,
            dokaz=[f"dig +short TXT _dmarc.{domena}  ->  (prazno)"]))
    else:
        pol = re.search(r"p\s*=\s*(\w+)", dmarc)
        pol = pol.group(1).lower() if pol else "?"
        ima_rua = "rua=" in dmarc.lower()
        if pol == "reject":
            nalazi.append(nalaz(
                "Mail i domena", "DMARC je na najstrožoj politici", DOBRO,
                f"Politika p=reject. Zapis: {dmarc}", dokaz=[dmarc]))
        elif pol == "quarantine":
            nalazi.append(nalaz(
                "Mail i domena", "DMARC je na prelaznoj politici", NIZAK,
                f"Politika p=quarantine. Zapis: {dmarc}",
                "Sumnjive poruke idu u neželjenu poštu umjesto da budu odbijene.",
                "Nakon mjesec dana praćenja izvještaja preći na p=reject.",
                sati=0.5, dokaz=[dmarc]))
        else:
            nalazi.append(nalaz(
                "Mail i domena", "DMARC je samo u režimu posmatranja", SREDNJI,
                f"Politika p={pol}. Zapis: {dmarc}",
                "Zapis postoji ali ništa ne odbija. Korisno za prikupljanje "
                "izvještaja, ali ne štiti domenu od zloupotrebe.",
                "Nakon analize izvještaja pooštriti na p=quarantine pa p=reject.",
                sati=1, trosak=60, dokaz=[dmarc]))
        if not ima_rua:
            nalazi.append(nalaz(
                "Mail i domena", "DMARC ne prikuplja izvještaje", NIZAK,
                "U zapisu nema rua= adrese za agregatne izvještaje.",
                "Nema vidljivosti u to ko šalje poruke u ime domene.",
                "Dodati rua=mailto:dmarc@domena u DMARC zapis.",
                sati=0.25, dokaz=[dmarc]))

    return {"nalazi": nalazi, "sirovo": sirovo}
