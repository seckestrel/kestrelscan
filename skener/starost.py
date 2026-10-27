# -*- coding: utf-8 -*-
"""Procjena starosti uređaja.

Datum BIOS-a NIJE datum proizvodnje — mijenja se pri svakom ažuriranju firmvera,
pa svježe ažuriran sedmogodišnji laptop izgleda kao nov. Zato se starost računa
iz generacije procesora, a potvrđuje satima rada diska.
"""
import datetime
import re

# --- Intel ---
INTEL_GEN = {2: 2011, 3: 2012, 4: 2013, 5: 2014, 6: 2015, 7: 2016, 8: 2017,
             9: 2018, 10: 2019, 11: 2020, 12: 2021, 13: 2022, 14: 2023}
INTEL_ULTRA = {1: 2023, 2: 2024, 3: 2025}
XEON_V = {1: 2012, 2: 2013, 3: 2014, 4: 2016}
XEON_SKALABILNI = {1: 2017, 2: 2019, 3: 2021, 4: 2023, 5: 2023, 6: 2024}

# --- AMD ---
# prva cifra oznake Ryzen procesora → godina izlaska serije
AMD_RYZEN = {1: 2017, 2: 2018, 3: 2019, 4: 2020, 5: 2021, 6: 2022, 7: 2023,
             8: 2024, 9: 2025}
AMD_RYZEN_AI = {3: 2024}          # Ryzen AI 9 365, Ryzen AI 7 350…
AMD_THREADRIPPER = {1: 2017, 2: 2018, 3: 2019, 5: 2022, 7: 2023, 9: 2025}
AMD_EPYC = {1: 2017, 2: 2019, 3: 2021, 4: 2022, 5: 2024}

# uređaj sa novim procesorom stigne u prodaju i kod kupca kroz otprilike godinu
POMAK_DO_ISPORUKE = 1.0
SATI_U_GODINI = 8760          # ako je mašina radila neprekidno
SATI_KANCELARIJSKI = 2000     # 8 sati dnevno, oko 250 radnih dana


def godina_procesora(cpu):
    """Vrati (godina_izlaska, objašnjenje) ili (None, None)."""
    if not cpu:
        return None, None
    t = " ".join(str(cpu).split())

    # --- AMD Ryzen AI (nova serija) ---
    m = re.search(r"Ryzen\s+AI\s+(?:MAX\s+)?\d\s+(\d)(\d{2})", t, re.I)
    if m:
        g = AMD_RYZEN_AI.get(int(m.group(1)))
        if g:
            return g, f"AMD Ryzen AI serija {m.group(1)}00 — izašla {g}."

    # --- AMD Threadripper ---
    m = re.search(r"Threadripper\s+(?:PRO\s+)?(\d)(\d{3})", t, re.I)
    if m:
        g = AMD_THREADRIPPER.get(int(m.group(1)))
        if g:
            return g, f"AMD Threadripper serija {m.group(1)}000 — izašla {g}."

    # --- AMD EPYC ---
    m = re.search(r"EPYC\s+(\d{4})", t, re.I)
    if m:
        oznaka = m.group(1)
        g = AMD_EPYC.get(int(oznaka[-1]))
        if g:
            return g, f"AMD EPYC {oznaka} — generacija {oznaka[-1]}, izašla {g}."

    # --- AMD Ryzen (stono i prenosivo, uključujući PRO) ---
    m = re.search(r"Ryzen\s+\d(?:\s+PRO)?\s+(\d)(\d{3})", t, re.I)
    if m:
        g = AMD_RYZEN.get(int(m.group(1)))
        if g:
            return g, f"AMD Ryzen serija {m.group(1)}000 — izašla {g}."

    # --- stariji AMD, prije Ryzena ---
    if re.search(r"\bAMD\b.*\b(A\d{1,2}-\d{4}|Athlon|FX-\d{4}|Phenom|Sempron|E1-|E2-)",
                 t, re.I):
        return 2014, "Stariji AMD procesor iz doba prije Ryzena — najkasnije 2015."

    # --- Intel Core Ultra ---
    m = re.search(r"Core\s*\(?TM\)?\s*Ultra\s*\d\s+(\d)(\d{2})", t, re.I)
    if m:
        g = INTEL_ULTRA.get(int(m.group(1)))
        if g:
            return g, f"Intel Core Ultra, serija {m.group(1)} — izašla {g}."

    # --- Intel Core i3/i5/i7/i9 ---
    m = re.search(r"\bi[3579][\s-]*(\d{4,5})", t, re.I)
    if m:
        oznaka = m.group(1)
        # Od 10. generacije oznaka počinje jedinicom: i7-1165G7 (11. gen, četiri
        # cifre) i i7-10510U (10. gen, pet cifara). Ranije generacije imaju
        # generaciju u prvoj cifri: i5-8250U.
        gen = int(oznaka[:2]) if oznaka[0] == "1" else int(oznaka[0])
        g = INTEL_GEN.get(gen)
        if g:
            return g, f"Intel Core {gen}. generacije — izašla {g}."

    # --- Intel Xeon skalabilni (Silver/Gold/Platinum/Bronze) ---
    m = re.search(r"Xeon.*?(?:Silver|Gold|Platinum|Bronze)\s+\d(\d)\d{2}", t, re.I)
    if m:
        g = XEON_SKALABILNI.get(int(m.group(1)))
        if g:
            return g, f"Intel Xeon skalabilni, {m.group(1)}. generacija — izašla {g}."

    # --- Intel Xeon E5/E3 v-oznake ---
    m = re.search(r"Xeon.*?\bv(\d)\b", t, re.I)
    if m:
        g = XEON_V.get(int(m.group(1)))
        if g:
            return g, f"Intel Xeon v{m.group(1)} — izašao {g}."

    # --- vrlo stari Intel ---
    if re.search(r"Core\s*(?:\(TM\))?\s*2\s*(?:Duo|Quad|Solo|Extreme)"
                 r"|Pentium\s+[DT4]|\bCeleron\s+[MN]?\d{3}\b", t, re.I):
        return 2009, "Procesor iz generacije prije Core i serije — 2010. ili stariji."

    return None, None


def procijeni(h):
    """h = sirovi podaci iz hardver.py ili inventara.

    Vraća: godine (procjena), osnov, pouzdanost, redovi (za dokaz u izvještaju).
    """
    danas = datetime.datetime.now()
    sada = danas.year + (danas.month - 1) / 12
    redovi, kandidati = [], []

    # --- procesor: najpouzdaniji pokazatelj ---
    cpu_god, cpu_opis = godina_procesora(h.get("cpu"))
    if cpu_god:
        godina_uredjaja = cpu_god + POMAK_DO_ISPORUKE
        g = max(0.0, round(sada - godina_uredjaja, 1))
        kandidati.append(("procesor", g))
        redovi.append(f"Procesor: {h.get('cpu')}")
        redovi.append(f"   {cpu_opis} Uređaj sa njim obično stiže kod kupca kroz "
                      f"godinu — procjena {g:g} godina.")

    # --- sati rada diska: daje najmanju moguću starost ---
    sati_maks = 0
    for r in h.get("pouzdanost") or []:
        s = r.get("PowerOnHours")
        if isinstance(s, int) and s > 0:
            sati_maks = max(sati_maks, s)
    if sati_maks:
        # i da je mašina radila neprekidno, toliko sati traži bar ovoliko godina
        najmanje = round(sati_maks / SATI_U_GODINI, 1)
        kancelarijski = round(sati_maks / SATI_KANCELARIJSKI, 1)
        kandidati.append(("sati rada", najmanje))
        redovi.append(f"Disk: {sati_maks} sati rada — najmanje {najmanje:g} godina "
                      f"i da je mašina radila danonoćno, odnosno oko "
                      f"{kancelarijski:g} godina uobičajene kancelarijske upotrebe.")

    # --- datum BIOS-a: samo kao gruba donja granica ---
    bios = h.get("bios_datum_raw")
    if isinstance(bios, datetime.datetime):
        g = round((danas - bios).days / 365.25, 1)
        redovi.append(f"Firmver (BIOS): {bios.strftime('%d.%m.%Y.')} — {g:g} godina. "
                      f"Mijenja se pri svakom ažuriranju, pa nije mjera starosti "
                      f"uređaja.")
        if not kandidati:
            kandidati.append(("firmver", g))

    # --- instalacija sistema: slaba potvrda ---
    inst = h.get("os_instaliran")
    if isinstance(inst, datetime.datetime):
        g = round((danas - inst).days / 365.25, 1)
        redovi.append(f"Sistem instaliran: {inst.strftime('%d.%m.%Y.')} — {g:g} "
                      f"godina. Reinstalacija poništava ovaj podatak.")

    if not kandidati:
        return {"godine": None, "osnov": "nije utvrđeno", "pouzdanost": None,
                "redovi": redovi, "cpu_godina": None}

    # uređaj ne može biti mlađi od svog procesora ni od sati koje je disk odradio
    osnov, godine = max(kandidati, key=lambda k: k[1])
    return {"godine": godine, "osnov": osnov,
            "pouzdanost": "dobra" if cpu_god else "gruba",
            "redovi": redovi, "cpu_godina": cpu_god}


def presuda(godine, sistem=""):
    """Kratka ocjena za tabelu inventara."""
    van_podrske = bool(re.search(r"Windows\s+(7|8|8\.1|10)\b", str(sistem or ""), re.I))
    if godine is None:
        return ("Nepoznato", "")
    if godine >= 7:
        return ("Za zamjenu", "star preko 7 godina")
    if van_podrske:
        return ("Nadogradnja sistema", "sistem van podrške")
    if godine >= 5:
        return ("Planirati zamjenu", "ulazi u godine")
    return ("U redu", "")
