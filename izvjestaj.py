# -*- coding: utf-8 -*-
"""Generisanje PDF izvještaja po KestrelSec šablonu iz rezultata skeniranja."""
import datetime
import os

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor, white
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.platypus import (BaseDocTemplate, PageTemplate, Frame, Paragraph,
                                Spacer, PageBreak, NextPageTemplate, Table,
                                TableStyle, KeepTogether)
from reportlab.platypus.flowables import HRFlowable
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from skener.nalaz import VISOK, SREDNJI, NIZAK, INFO, DOBRO, ocjena, sortiraj

PW, PH = A4
LM = RM = 18 * mm
CW = PW - LM - RM

NAVY = HexColor("#0f2740")
NAVY2 = HexColor("#0d1c38")
CYAN = HexColor("#34c6fe")
CYAN_D = HexColor("#1a8fc4")
BODY = HexColor("#33414f")
MUTED = HexColor("#6a7889")
RULE = HexColor("#d3dde6")
BOX = HexColor("#f0f6fa")
BOXB = HexColor("#c3d8e6")

BOJA_TEZ = {
    VISOK: HexColor("#b3261e"),
    SREDNJI: HexColor("#b26a00"),
    NIZAK: HexColor("#1a8fc4"),
    INFO: HexColor("#6a7889"),
    DOBRO: HexColor("#1e7e4f"),
}
NAZIV_TEZ = {VISOK: "VISOK", SREDNJI: "SREDNJI", NIZAK: "NIZAK",
             INFO: "INFORMATIVNO", DOBRO: "U REDU"}

_fontovi_ucitani = False


def _fontovi(korijen):
    global _fontovi_ucitani
    if _fontovi_ucitani:
        return
    mapa = {
        "DV": "DejaVuSans.ttf",
        "DV-B": "DejaVuSans-Bold.ttf",
        "DV-I": "DejaVuSans-Oblique.ttf",
        "SR": "DejaVuSerif.ttf",
        "SR-B": "DejaVuSerif-Bold.ttf",
    }
    mjesta = [os.path.join(korijen, "fontovi"),
              "/usr/share/fonts/truetype/dejavu",
              "C:\\Windows\\Fonts"]
    for ime, fajl in mapa.items():
        for m in mjesta:
            p = os.path.join(m, fajl)
            if os.path.isfile(p):
                pdfmetrics.registerFont(TTFont(ime, p))
                break
    _fontovi_ucitani = True


def _stilovi():
    S = {
        "h1": ParagraphStyle("h1", fontName="SR-B", fontSize=19, textColor=NAVY, leading=23),
        "kick": ParagraphStyle("kick", fontName="DV-B", fontSize=8.2, textColor=CYAN_D,
                               leading=11, spaceAfter=3),
        "h2": ParagraphStyle("h2", fontName="DV-B", fontSize=12.5, textColor=NAVY,
                             leading=16, spaceBefore=14, spaceAfter=6),
        "h3": ParagraphStyle("h3", fontName="DV-B", fontSize=10.3, textColor=NAVY,
                             leading=14, spaceBefore=6, spaceAfter=2),
        "p": ParagraphStyle("p", fontName="DV", fontSize=9.3, textColor=BODY,
                            leading=14, spaceAfter=5),
        "small": ParagraphStyle("small", fontName="DV-I", fontSize=8.2, textColor=MUTED,
                                leading=11.5, spaceAfter=4),
        "mono": ParagraphStyle("mono", fontName="DV", fontSize=8, textColor=HexColor("#123b52"),
                               leading=11.5),
        "ctr": ParagraphStyle("ctr", fontName="DV", fontSize=9.3, textColor=BODY,
                              leading=14, alignment=TA_CENTER),
    }
    S["li"] = ParagraphStyle("li", parent=S["p"], leftIndent=12, bulletIndent=2,
                             spaceAfter=2.5, leading=13)
    return S


def _esc(t):
    return (str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def _sazetak(podaci, nalazi, oc):
    firma = podaci.get("firma") or "Firma"
    datum = podaci.get("datum")
    stvarni = [n for n in nalazi if n["tezina"] in (VISOK, SREDNJI, NIZAK)]
    visoki = [n for n in nalazi if n["tezina"] == VISOK]
    dobri = [n for n in nalazi if n["tezina"] == DOBRO]

    d = []
    d.append(f"Pregled je obavljen {datum} u prostorijama firme "
             f"{firma.rstrip('.')}. Obuhvatio je provjere navedene u odjeljku o obimu.")
    if dobri:
        imena = [n["naslov"] for n in dobri[:2]]
        d.append("Firma dobro stoji u ovome: " + "; ".join(imena) + ".")
    if stvarni:
        rec = (f"Utvrđeno je {len(stvarni)} nalaza koja zahtijevaju pažnju, "
               f"od čega {len(visoki)} visokog prioriteta.")
        if visoki:
            rec += " Najozbiljniji je — " + visoki[0]["naslov"] + "."
        d.append(rec)
        bez_troska = [n for n in stvarni if not n.get("trosak")]
        if bez_troska:
            d.append(f"Preporučujemo da se u naredne dvije sedmice riješe stavke "
                     f"označene kao visok prioritet. Njih {len(bez_troska)} ne "
                     f"zahtijeva nikakvo ulaganje, nego samo promjenu postavki.")
    else:
        d.append("Tokom pregleda nisu utvrđeni nalazi koji zahtijevaju hitnu pažnju.")
    if oc.get("mjerljivo"):
        d.append(f"Ukupna ocjena stanja: {oc['bodovi']} od {oc['maks']} bodova — "
                 f"{oc['nivo']}, {oc['opis'].lower()}.")
    else:
        d.append("Ocjena stanja nije izdata jer nijedna provjera nije dala "
                 "mjerljiv rezultat. Vidjeti napomene u nalazima.")
    return d


def napravi(podaci, nalazi, putanja, korijen="."):
    """podaci: firma, datum, obim, kontakt… | nalazi: lista iz skener modula"""
    _fontovi(korijen)
    S = _stilovi()
    nalazi = sortiraj(nalazi)
    oc = ocjena(nalazi)

    firma = podaci.get("firma") or "Firma"
    datum = podaci.get("datum") or datetime.date.today().strftime("%d.%m.%Y.")
    izvrsio = podaci.get("izvrsio") or "Dragomir Babić, KestrelSec"
    kontakt = podaci.get("kontakt") or "066/531-666 · dragomir@kestrelsec.io · kestrelsec.io"
    podaci.setdefault("datum", datum)

    def naslovna(c, doc):
        c.saveState()
        c.setFillColor(NAVY2)
        c.rect(0, 0, PW, PH, fill=1, stroke=0)
        c.setStrokeColor(CYAN)
        c.setLineWidth(1.2)
        c.line(20 * mm, PH - 16 * mm, PW - 20 * mm, PH - 16 * mm)
        c.line(20 * mm, 16 * mm, PW - 20 * mm, 16 * mm)
        c.setFillColor(CYAN)
        c.setFont("DV-B", 23)
        c.drawCentredString(PW / 2, PH - 72 * mm, "KestrelSec")
        c.setFillColor(HexColor("#9fb3c8"))
        c.setFont("DV", 9)
        c.drawCentredString(PW / 2, PH - 84 * mm, "S I G U R N O S N I   P R E G L E D")
        c.setFillColor(white)
        c.setFont("DV-B", 26)
        c.drawCentredString(PW / 2, PH - 108 * mm, "IZVJEŠTAJ")
        c.setStrokeColor(HexColor("#2b4a6e"))
        c.setLineWidth(0.8)
        c.line(55 * mm, PH - 118 * mm, PW - 55 * mm, PH - 118 * mm)
        c.setFillColor(HexColor("#c7d3e0"))
        c.setFont("DV-B", 13)
        c.drawCentredString(PW / 2, PH - 132 * mm, firma[:60])
        c.setFont("DV", 10)
        c.setFillColor(HexColor("#8ea3ba"))
        c.drawCentredString(PW / 2, PH - 143 * mm, datum)
        c.setFont("DV-B", 11)
        c.setFillColor(CYAN)
        c.drawCentredString(PW / 2, 56 * mm, izvrsio)
        c.setFont("DV", 9)
        c.setFillColor(HexColor("#8ea3ba"))
        c.drawCentredString(PW / 2, 47 * mm, kontakt)
        c.setFont("DV-I", 7.6)
        c.setFillColor(HexColor("#5f748a"))
        c.drawCentredString(PW / 2, 30 * mm, "POVJERLJIVO — namijenjeno isključivo naručiocu")
        c.restoreState()

    def unutra(c, doc):
        c.saveState()
        c.setFont("DV-B", 7.6)
        c.setFillColor(CYAN_D)
        c.drawString(LM, PH - 13 * mm, "KESTRELSEC")
        c.setFont("DV", 7.4)
        c.setFillColor(MUTED)
        c.drawRightString(PW - RM, PH - 13 * mm, f"Sigurnosni pregled — {firma[:42]}")
        c.setStrokeColor(RULE)
        c.setLineWidth(0.5)
        c.line(LM, PH - 15.5 * mm, PW - RM, PH - 15.5 * mm)
        c.setFont("DV", 7.4)
        c.setFillColor(MUTED)
        c.drawCentredString(PW / 2, 12 * mm, str(doc.page - 1))
        c.setFont("DV", 6.5)
        c.setFillColor(HexColor("#9aa6b2"))
        c.drawCentredString(PW / 2, 8 * mm, f"{izvrsio} · {kontakt}")
        c.restoreState()

    doc = BaseDocTemplate(putanja, pagesize=A4, leftMargin=LM, rightMargin=RM,
                          topMargin=20 * mm, bottomMargin=18 * mm,
                          title=f"Sigurnosni pregled — {firma}", author=izvrsio)
    doc.addPageTemplates([
        PageTemplate(id="N", frames=[Frame(0, 0, PW, PH, leftPadding=0, rightPadding=0,
                                           topPadding=0, bottomPadding=0)], onPage=naslovna),
        PageTemplate(id="U", frames=[Frame(LM, 16 * mm, CW, PH - 36 * mm)], onPage=unutra),
    ])

    st = [NextPageTemplate("U"), PageBreak()]

    # --- podaci o pregledu ---
    red = [["Firma", firma]]
    if (podaci.get("lokacija_puna") or "").strip():
        red.append(["Lokacija", podaci["lokacija_puna"]])
    red += [["Datum pregleda", datum], ["Izvršio", izvrsio]]
    if (podaci.get("kontakt_osoba") or "").strip():
        red.append(["Kontakt osoba", podaci["kontakt_osoba"]])
    if (podaci.get("masina") or "").strip():
        red.append(["Mašina sa koje je pregled rađen", podaci["masina"]])
    red.append(["Obim", podaci.get("obim") or "—"])
    if (podaci.get("napomena") or "").strip():
        red.append(["Napomena", podaci["napomena"]])
    t = Table([[Paragraph(f"<b>{_esc(a)}</b>", S["p"]), Paragraph(_esc(b), S["p"])]
               for a, b in red], colWidths=[36 * mm, CW - 36 * mm])
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, -2), 0.4, RULE),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
    ]))
    st += [Paragraph("IZVJEŠTAJ O SIGURNOSNOM PREGLEDU", S["kick"]),
           Paragraph(firma, S["h1"]),
           HRFlowable(width="100%", thickness=2, color=CYAN, spaceBefore=4, spaceAfter=12),
           t]

    # --- 1. sažetak ---
    st.append(Paragraph("1. Sažetak za rukovodstvo", S["h2"]))
    for p in _sazetak(podaci, nalazi, oc):
        st.append(Paragraph(_esc(p), S["p"]))

    # --- poređenje sa prošlim pregledom ---
    por = podaci.get("poredjenje")
    if por:
        st.append(Paragraph("Šta se promijenilo od prošlog pregleda", S["h2"]))
        prosla = por.get("ocjena_prethodna") or {}
        sada_b = oc.get("bodovi")
        prije_b = prosla.get("bodovi")
        if isinstance(sada_b, int) and isinstance(prije_b, int):
            razlika = sada_b - prije_b
            smjer = ("bolje za " + str(razlika)) if razlika > 0 else (
                ("lošije za " + str(abs(razlika))) if razlika < 0 else "bez promjene")
            st.append(Paragraph(
                f'<b>Ocjena: {prije_b} → {sada_b} od {oc["maks"]} bodova '
                f'({smjer}).</b> Prethodni pregled: '
                f'{_esc((por.get("datum_prethodnog") or "ranije").rstrip("."))}.', S["p"]))
        b = por["broj"]
        st.append(Paragraph(
            f'Riješeno {b["rijeseno"]}, novih {b["novo"]}, i dalje otvoreno '
            f'{b["ostalo"]}.', S["p"]))

        for naslov, grupa, boja in (
                ("Riješeno od prošlog puta", por["rijeseno"], BOJA_TEZ[DOBRO]),
                ("Novo", por["novo"], BOJA_TEZ[VISOK]),
                ("I dalje otvoreno", por["ostalo"], BOJA_TEZ[SREDNJI])):
            if not grupa:
                continue
            st.append(Paragraph(naslov, ParagraphStyle(
                "pg", parent=S["h3"], textColor=boja)))
            for n in grupa[:14]:
                st.append(Paragraph(
                    f'{_esc(n["naslov"])} <font size="8" color="#6a7889">'
                    f'({_esc(n["oblast"])})</font>', S["li"], bulletText="•"))
            if len(grupa) > 14:
                st.append(Paragraph(f"… i još {len(grupa) - 14}", S["small"]))

    # --- 2. ocjena ---
    st.append(Paragraph("2. Ocjena stanja", S["h2"]))
    skala = [["Bodova", "Nivo", "Značenje"],
             ["0–10", "Nivo 0–1", "Osnovna zaštita nedostaje"],
             ["11–20", "Nivo 1", "Osnove postoje, sa rupama"],
             ["21–27", "Nivo 2", "Kontrolisano stanje"],
             ["28–32", "Nivo 3", "Upravljano stanje"]]
    red_ist = next((i for i, r in enumerate(skala) if r[1] == oc["nivo"]), -1)
    ts = Table([[Paragraph(f"<b>{_esc(c)}</b>" if i == 0 else _esc(c), S["p"])
                 for c in r] for i, r in enumerate(skala)],
               colWidths=[26 * mm, 30 * mm, CW - 56 * mm])
    ts.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY2),
        ("TEXTCOLOR", (0, 0), (-1, 0), white),
        ("BACKGROUND", (0, red_ist), (-1, red_ist),
         HexColor("#dcedf8") if red_ist >= 0 else white),
        ("GRID", (0, 0), (-1, -1), 0.4, RULE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ]))
    if oc.get("mjerljivo"):
        zaglavlje_oc = (f"<b>Rezultat: {oc['bodovi']} od {oc['maks']} bodova — "
                        f"{oc['nivo']}</b>")
    else:
        zaglavlje_oc = ("<b>Ocjena nije izdata.</b> Nijedna provjera nije dala "
                        "mjerljiv rezultat — vidjeti napomene u nalazima.")
    st += [Paragraph(zaglavlje_oc, S["p"]), Spacer(1, 4), ts]

    # po oblastima
    oblasti = {}
    for n in nalazi:
        oblasti.setdefault(n["oblast"], []).append(n["tezina"])
    izgubljeno = {o["oblast"]: o for o in (oc.get("oblasti") or [])}

    red = [["Oblast", "Stanje", "Nalaza", "Bodova"]]
    for o, tez in oblasti.items():
        if VISOK in tez:
            stanje = "kritično"
        elif SREDNJI in tez:
            stanje = "treba popraviti"
        elif NIZAK in tez:
            stanje = "zadovoljava"
        else:
            stanje = "dobro"
        b = izgubljeno.get(o)
        if b:
            bod = f'−{b["izgubljeno"]} od {b["tavan"]}'
            if b["preko_tavana"]:
                bod += " (najveći mogući)"
        else:
            bod = "ne ulazi"
        red.append([o, stanje,
                    str(len([t for t in tez if t in (VISOK, SREDNJI, NIZAK)])), bod])
    to = Table([[Paragraph(f"<b>{_esc(c)}</b>" if i == 0 else _esc(c), S["p"])
                 for c in r] for i, r in enumerate(red)],
               colWidths=[CW - 90 * mm, 38 * mm, 18 * mm, 34 * mm])
    to.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY2),
        ("TEXTCOLOR", (0, 0), (-1, 0), white),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [white, BOX]),
        ("GRID", (0, 0), (-1, -1), 0.4, RULE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ]))
    st += [Paragraph("Ocjena po oblastima", S["h3"]), to]
    if oc.get("mjerljivo") and oc.get("moguce"):
        st.append(Paragraph(
            f'Ocjena se računa iz {len(oc["oblasti"])} pregledanih oblasti. Svaka '
            f'oblast može izgubiti najviše {oc["oblasti"][0]["tavan"]} bodova, bez '
            f'obzira na broj propusta u njoj — više propusta iste vrste je jedan '
            f'problem, ne više njih. Oznaka „najveći mogući" znači da je ta oblast '
            f'izgubila sve što je mogla i da je tu posao najveći. Ukupno izgubljeno: '
            f'{oc["oduzeto"]} od {oc["moguce"]} mogućih, što na skali od '
            f'{oc["maks"]} daje {oc["bodovi"]}. Oblast koja nije provjerena ne ulazi '
            f'u računicu.', S["small"]))

    # --- 3. šta stoji dobro ---
    dobri = [n for n in nalazi if n["tezina"] == DOBRO]
    st.append(Paragraph("3. Šta stoji dobro", S["h2"]))
    if dobri:
        for n in dobri:
            st.append(Paragraph(f"<b>{_esc(n['naslov'])}.</b> {_esc(n['utvrdjeno'])}",
                                S["li"], bulletText="•"))
    else:
        st.append(Paragraph("Tokom pregleda nije utvrđena nijedna stavka koja bi se "
                            "mogla navesti kao dobro postavljena.", S["p"]))

    # --- 4. nalazi ---
    stvarni = [n for n in nalazi if n["tezina"] in (VISOK, SREDNJI, NIZAK)]
    st.append(Paragraph("4. Nalazi", S["h2"]))
    if not stvarni:
        st.append(Paragraph("Nema nalaza koji zahtijevaju pažnju.", S["p"]))
    for i, n in enumerate(stvarni, 1):
        blok = []
        zag = Table([[Paragraph(f"<b>{i}</b>", ParagraphStyle(
                        "x", fontName="DV-B", fontSize=11, textColor=white, leading=14)),
                      Paragraph(f"<b>{_esc(n['naslov'])}</b>", ParagraphStyle(
                        "y", fontName="DV-B", fontSize=10.5, textColor=NAVY, leading=14)),
                      Paragraph(NAZIV_TEZ[n["tezina"]], ParagraphStyle(
                        "z", fontName="DV-B", fontSize=7.6, textColor=white,
                        leading=11, alignment=TA_CENTER))]],
                    colWidths=[9 * mm, CW - 9 * mm - 24 * mm, 24 * mm])
        zag.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (0, 0), NAVY2),
            ("BACKGROUND", (1, 0), (1, 0), BOX),
            ("BACKGROUND", (2, 0), (2, 0), BOJA_TEZ[n["tezina"]]),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (0, 0), (0, 0), "CENTER"),
            ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (1, 0), (1, 0), 7),
            ("BOX", (0, 0), (-1, -1), 0.4, BOXB),
        ]))
        blok += [Spacer(1, 7), zag, Spacer(1, 4)]
        blok.append(Paragraph(f"<b>Oblast:</b> {_esc(n['oblast'])}", S["small"]))
        blok.append(Paragraph(f"<b>Šta je utvrđeno:</b> {_esc(n['utvrdjeno'])}", S["p"]))
        if n.get("rizik"):
            blok.append(Paragraph(f"<b>Zašto je to rizik:</b> {_esc(n['rizik'])}", S["p"]))
        if n.get("preporuka"):
            blok.append(Paragraph(f"<b>Preporuka:</b> {_esc(n['preporuka'])}", S["p"]))
        if n.get("sati") or n.get("trosak"):
            s = []
            if n.get("sati"):
                s.append(f"{n['sati']} h rada")
            if n.get("trosak"):
                s.append(f"oko {n['trosak']} KM")
            if n.get("izvorno") and ("sati" in n["izvorno"] or "trosak" in n["izvorno"]):
                s.append("procjenu ispravio tehničar na terenu")
            blok.append(Paragraph("<b>Procjena:</b> " + " · ".join(s), S["p"]))
        if (n.get("komentar") or "").strip():
            blok.append(Paragraph(
                f"<b>Napomena tehničara:</b> {_esc(n['komentar'])}", S["p"]))
        if n.get("izvorno"):
            ime_polja = {"sati": "sati rada", "trosak": "trošak u KM",
                         "tezina": "težina nalaza"}
            dj = []
            for k, staro in n["izvorno"].items():
                novo = n.get(k)
                dj.append(f"{ime_polja.get(k, k)}: "
                          f"{'nije bilo procjene' if staro in (None, '') else staro}"
                          f" → {'nema' if novo in (None, '') else novo}")
            blok.append(Paragraph(
                "<b>Ispravljeno nakon skeniranja:</b> " + _esc("; ".join(dj))
                + ". Prvobitna vrijednost je automatska procjena alata; ispravku je "
                  "unio tehničar na osnovu stanja na mjestu.", S["small"]))
        if n.get("rucni"):
            blok.append(Paragraph(
                "<b>Izvor podatka:</b> ručni unos tehničara na osnovu fizičkog "
                "pregleda — uređaj alat nije mogao očitati.", S["small"]))
        if n.get("tabela"):
            tb = n["tabela"]
            zg = ParagraphStyle("tz", fontName="DV-B", fontSize=7.4, textColor=white,
                                leading=9.5)
            cel = ParagraphStyle("tc", fontName="DV", fontSize=7.4, textColor=BODY,
                                 leading=9.8)
            # boja se mora staviti u sam paragraf — boja ćelije ne utiče na tekst
            boje_ocjene = [
                ("za zamjenu", BOJA_TEZ[VISOK]),
                ("planirati", BOJA_TEZ[SREDNJI]),
                ("nadogradnja", BOJA_TEZ[SREDNJI]),
                ("u redu", BOJA_TEZ[DOBRO]),
            ]

            def _celija(tekst, zadnja):
                t = str(tekst)
                if zadnja:
                    for kljuc, boja in boje_ocjene:
                        if kljuc in t.lower():
                            return Paragraph(_esc(t), ParagraphStyle(
                                "to", parent=cel, fontName="DV-B", textColor=boja))
                return Paragraph(_esc(t), cel)

            nk = len(tb["zaglavlje"])
            podaci_t = [[Paragraph(_esc(c), zg) for c in tb["zaglavlje"]]]
            for red in tb["redovi"]:
                podaci_t.append([_celija(c, j == nk - 1) for j, c in enumerate(red)])

            tezine = tb.get("sirine") or [1] * nk
            uk = float(sum(tezine))
            sirine = [CW * t / uk for t in tezine]

            tt = Table(podaci_t, colWidths=sirine, repeatRows=1)
            tt.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), NAVY2),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [white, BOX]),
                ("GRID", (0, 0), (-1, -1), 0.3, RULE),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ]))
            blok += [Spacer(1, 4), tt, Spacer(1, 3)]

        if n.get("dokaz"):
            redovi = [Paragraph(_esc(d), S["mono"]) for d in n["dokaz"][:14]]
            if len(n["dokaz"]) > 14:
                redovi.append(Paragraph(f"… i još {len(n['dokaz']) - 14} redova", S["small"]))
            td = Table([[redovi]], colWidths=[CW])
            td.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), HexColor("#eceff3")),
                ("BOX", (0, 0), (-1, -1), 0.4, HexColor("#c8cfd8")),
                ("LEFTPADDING", (0, 0), (-1, -1), 9), ("RIGHTPADDING", (0, 0), (-1, -1), 9),
                ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]))
            blok += [Spacer(1, 3), td]
        st.append(KeepTogether(blok) if len(blok) < 9 else blok[0])
        if len(blok) >= 9:
            st += blok[1:]

    # --- 5. plan ---
    st.append(Paragraph("5. Plan po prioritetu", S["h2"]))
    faze = [("Odmah (ove sedmice)", [n for n in stvarni if n["tezina"] == VISOK]),
            ("Uskoro (do mjesec dana)", [n for n in stvarni if n["tezina"] == SREDNJI]),
            ("Kad stigne (u tri mjeseca)", [n for n in stvarni if n["tezina"] == NIZAK])]
    for naslov, grupa in faze:
        st.append(Paragraph(naslov, S["h3"]))
        if not grupa:
            st.append(Paragraph("—", S["p"]))
        for n in grupa:
            st.append(Paragraph(_esc(n["naslov"]), S["li"], bulletText="•"))

    # --- 6. procjena ---
    sa_procjenom = [n for n in stvarni if n.get("sati") or n.get("trosak")]
    if sa_procjenom:
        st.append(Paragraph("6. Procjena rada i troška", S["h2"]))
        red = [["Stavka", "Rad", "Trošak"]]
        uk_s = uk_t = 0
        for n in sa_procjenom:
            s = n.get("sati") or 0
            tr = n.get("trosak") or 0
            uk_s += s
            uk_t += tr
            red.append([n["naslov"], f"{s} h" if s else "—",
                        f"{tr} KM" if tr else "—"])
        red.append(["UKUPNO", f"{uk_s:g} h", f"{uk_t:g} KM"])
        tp = Table([[Paragraph(f"<b>{_esc(c)}</b>" if (i == 0 or i == len(red) - 1)
                               else _esc(c), S["p"]) for c in r]
                    for i, r in enumerate(red)],
                   colWidths=[CW - 50 * mm, 25 * mm, 25 * mm])
        tp.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), NAVY2),
            ("TEXTCOLOR", (0, 0), (-1, 0), white),
            ("ROWBACKGROUNDS", (0, 1), (-1, -2), [white, BOX]),
            ("BACKGROUND", (0, -1), (-1, -1), HexColor("#dcedf8")),
            ("GRID", (0, 0), (-1, -1), 0.4, RULE),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ]))
        st.append(tp)
        st.append(Spacer(1, 6))
        st.append(Paragraph(
            "Alternativa jednokratnom sređivanju je mjesečni paket, u kojem se "
            "ovo odradi kroz prva dva mjeseca i nakon toga održava.", S["p"]))

    # --- 7. napomena ---
    st.append(Paragraph("7. Napomena o obimu", S["h2"]))
    nap = Table([[Paragraph(
        "Ovaj pregled predstavlja presjek stanja u datom trenutku. Nije obavljeno "
        "testiranje probijanjem niti detaljna analiza svih uređaja. Nalazi se odnose "
        "na ono što je bilo dostupno i vidljivo tokom pregleda, i ne predstavljaju "
        "garanciju odsustva drugih ranjivosti.", S["p"])]], colWidths=[CW])
    nap.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), HexColor("#fbfcfd")),
        ("LINEBEFORE", (0, 0), (0, -1), 3, CYAN_D),
        ("BOX", (0, 0), (-1, -1), 0.5, BOXB),
        ("LEFTPADDING", (0, 0), (-1, -1), 11), ("RIGHTPADDING", (0, 0), (-1, -1), 11),
        ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    st.append(nap)

    st += [Spacer(1, 12),
           Paragraph("Izvještaj je vaš bez obzira na dalju saradnju. Slobodno me "
                     "pozovite oko bilo koje stavke, čak i ako je rješavate sami.", S["p"]),
           Spacer(1, 6),
           Paragraph(f"<b>{_esc(izvrsio)}</b>", S["p"]),
           Paragraph(_esc(kontakt), S["small"])]

    doc.build(st)
    return putanja


# ---------------------------------------------------------------- sažetak
def sazetak(podaci, nalazi, putanja, korijen="."):
    """Jedna strana za vlasnika: ocjena, tri najvažnije stavke, šta nudiš."""
    _fontovi(korijen)
    S = _stilovi()
    nalazi = sortiraj(nalazi)
    propusti = [n for n in nalazi if n["tezina"] in (VISOK, SREDNJI, NIZAK)]
    dobri = [n for n in nalazi if n["tezina"] == DOBRO]
    oc = ocjena(nalazi)

    firma = podaci.get("firma") or "Firma"
    datum = podaci.get("datum") or datetime.date.today().strftime("%d.%m.%Y.")
    izvrsio = podaci.get("izvrsio") or "Dragomir Babić, KestrelSec"
    kontakt = podaci.get("kontakt") or ("066/531-666 · dragomir@kestrelsec.io "
                                        "· kestrelsec.io")

    uk_sati = sum(n.get("sati") or 0 for n in propusti)
    uk_trosak = sum(n.get("trosak") or 0 for n in propusti)
    visoki = [n for n in propusti if n["tezina"] == VISOK]

    def okvir(c, doc):
        c.saveState()
        c.setFillColor(NAVY2)
        c.rect(0, PH - 30 * mm, PW, 30 * mm, fill=1, stroke=0)
        c.setFillColor(CYAN)
        c.setFont("DV-B", 15)
        c.drawString(18 * mm, PH - 15 * mm, "KestrelSec")
        c.setFillColor(HexColor("#9fb3c8"))
        c.setFont("DV", 8.4)
        c.drawString(18 * mm, PH - 21 * mm, "Sigurnosni pregled — sažetak")
        c.setFont("DV", 8.4)
        c.drawRightString(PW - 18 * mm, PH - 15 * mm, firma[:46])
        lok = (podaci.get("lokacija_puna") or "").strip()
        if lok:
            # dug naziv se skraćuje po dijelovima, ne nasred riječi
            dijelovi = [x.strip() for x in lok.split("|") if x.strip()]
            while len(" | ".join(dijelovi)) > 42 and len(dijelovi) > 1:
                dijelovi.pop()
            lok = " | ".join(dijelovi)
            if len(lok) > 42:
                lok = lok[:41].rstrip() + "…"
        c.drawRightString(PW - 18 * mm, PH - 21 * mm,
                          f"{lok} · {datum}" if lok else datum)
        c.setFillColor(NAVY2)
        c.rect(0, 0, PW, 16 * mm, fill=1, stroke=0)
        c.setFillColor(HexColor("#c7d3e0"))
        c.setFont("DV-B", 8.6)
        c.drawCentredString(PW / 2, 9.5 * mm, izvrsio)
        c.setFont("DV", 7.8)
        c.setFillColor(HexColor("#8ea3ba"))
        c.drawCentredString(PW / 2, 5 * mm, kontakt)
        c.restoreState()

    doc = BaseDocTemplate(putanja, pagesize=A4, leftMargin=18 * mm,
                          rightMargin=18 * mm, topMargin=36 * mm,
                          bottomMargin=20 * mm,
                          title=f"Sažetak pregleda — {firma}", author=izvrsio)
    doc.addPageTemplates([PageTemplate(
        id="S", frames=[Frame(18 * mm, 18 * mm, CW, PH - 56 * mm)], onPage=okvir)])

    st = []

    # --- ocjena ---
    if oc.get("mjerljivo"):
        lijevo = Paragraph(
            f'<font size="34"><b>{oc["bodovi"]}</b></font>'
            f'<font size="13" color="#6a7889">/{oc["maks"]}</font>',
            ParagraphStyle("b", fontName="DV-B", fontSize=34, textColor=CYAN_D,
                           leading=38, alignment=TA_CENTER))
        desno = [Paragraph(f'<b>{_esc(oc["nivo"])}</b>', S["h2"]),
                 Paragraph(_esc(oc["opis"]), S["p"])]
    else:
        lijevo = Paragraph("—", ParagraphStyle("b", fontName="DV-B", fontSize=30,
                                               textColor=MUTED, alignment=TA_CENTER))
        desno = [Paragraph("<b>Ocjena nije izdata</b>", S["h2"]),
                 Paragraph(_esc(oc["opis"]), S["p"])]

    t = Table([[lijevo, desno]], colWidths=[34 * mm, CW - 34 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), BOX),
        ("BOX", (0, 0), (-1, -1), 0.5, BOXB),
        ("LINEAFTER", (0, 0), (0, 0), 0.5, BOXB),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("LEFTPADDING", (1, 0), (1, 0), 14),
    ]))
    st += [t, Spacer(1, 7)]

    st.append(Paragraph(
        f'Utvrđeno je <b>{len(propusti)}</b> stavki koje traže pažnju, '
        f'od toga <b>{len(visoki)}</b> hitnih.', S["p"]))

    # --- tri najvažnije ---
    st.append(Paragraph("Najvažnije tri stavke", S["h2"]))
    if propusti:
        for i, n in enumerate(propusti[:3], 1):
            ime = Paragraph(f'<b>{_esc(n["naslov"])}</b>', S["p"])
            zasto = Paragraph(_esc(n.get("rizik") or n.get("utvrdjeno") or ""),
                              S["small"])
            broj = Paragraph(f'<b>{i}</b>', ParagraphStyle(
                "n", fontName="DV-B", fontSize=12, textColor=white,
                alignment=TA_CENTER, leading=15))
            red = Table([[broj, [ime, zasto]]], colWidths=[9 * mm, CW - 9 * mm])
            red.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (0, 0), BOJA_TEZ[n["tezina"]]),
                ("BACKGROUND", (1, 0), (1, 0), white),
                ("BOX", (0, 0), (-1, -1), 0.4, RULE),
                ("VALIGN", (0, 0), (0, 0), "MIDDLE"),
                ("VALIGN", (1, 0), (1, 0), "TOP"),
                ("LEFTPADDING", (1, 0), (1, 0), 9),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]))
            st += [red, Spacer(1, 4)]
    else:
        st.append(Paragraph("Nije utvrđena nijedna stavka koja traži pažnju.",
                            S["p"]))

    # --- šta stoji dobro ---
    if dobri:
        st.append(Paragraph("Šta već stoji dobro", S["h2"]))
        st.append(Paragraph(
            "; ".join(_esc(n["naslov"]) for n in dobri[:4]) + ".", S["p"]))

    # --- šta nudim ---
    st.append(Paragraph("Šta predlažem", S["h2"]))
    if uk_sati or uk_trosak:
        st.append(Paragraph(
            f'Sređivanje svega utvrđenog procjenjujem na <b>{uk_sati:g} sati</b> '
            f'rada, odnosno oko <b>{uk_trosak:g} KM</b> jednokratno.', S["p"]))
    st.append(Paragraph(
        "Alternativa je mjesečno održavanje: isto se odradi kroz prva dva "
        "mjeseca, a poslije se održava — bez jednokratnog troška i bez "
        "zapošljavanja IT osobe.", S["p"]))

    paketi = [["Paket", "Uređaja", "Mjesečno"],
              ["Osnovni", "do 10", "150 KM"],
              ["Srednji", "do 20", "300 KM"],
              ["Premium", "do 30", "500 KM"],
              ["Enterprise", "30 do 45", "1000 KM"]]
    tp = Table([[Paragraph(f'<b>{_esc(c)}</b>' if i == 0 else _esc(c), S["p"])
                 for c in r] for i, r in enumerate(paketi)],
               colWidths=[CW - 70 * mm, 35 * mm, 35 * mm])
    tp.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY2),
        ("TEXTCOLOR", (0, 0), (-1, 0), white),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [white, BOX]),
        ("GRID", (0, 0), (-1, -1), 0.4, RULE),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
    ]))
    st += [Spacer(1, 3), tp, Spacer(1, 9)]

    st.append(Paragraph(
        "Potpuni izvještaj sa svim nalazima, dokazima i planom po fazama "
        "predat je uz ovaj sažetak. Izvještaj je vaš bez obzira na dalju "
        "saradnju.", S["small"]))

    doc.build(st)
    return putanja
