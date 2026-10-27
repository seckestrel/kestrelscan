# -*- coding: utf-8 -*-
"""MAC adrese uređaja na mreži i prepoznavanje proizvođača.

IP adresa se mijenja, MAC ostaje. Zato je MAC ono što se upisuje u popis opreme,
po njemu se uređaj prepoznaje na sljedećem pregledu, i po njemu se vidi da li je
na mreži nešto što niko u firmi ne prepoznaje.

Prva tri bajta MAC adrese su oznaka proizvođača (OUI). Puni registar ima preko
30.000 stavki i ne isplati se nositi na USB-u, pa je ovdje spisak proizvođača
koji se stvarno sreću u malim firmama.
"""
import re
import subprocess
import sys

JE_WINDOWS = sys.platform.startswith("win")

# prva tri bajta -> proizvođač, i šta taj uređaj obično jeste
OUI = {
    # računari i matične ploče
    "00:1A:A0": ("Dell", "računar"), "00:14:22": ("Dell", "računar"),
    "18:03:73": ("Dell", "računar"), "D4:BE:D9": ("Dell", "računar"),
    "F8:BC:12": ("Dell", "računar"), "B0:83:FE": ("Dell", "računar"),
    "00:21:5A": ("HP", "računar"), "3C:D9:2B": ("HP", "računar"),
    "94:57:A5": ("HP", "računar"), "A0:D3:C1": ("HP", "računar"),
    "80:C1:6E": ("HP", "računar"), "98:E7:F4": ("HP", "računar"),
    "00:21:CC": ("Lenovo", "računar"), "68:F7:28": ("Lenovo", "računar"),
    "54:E1:AD": ("Lenovo", "računar"), "E8:6A:64": ("Lenovo", "računar"),
    "00:23:24": ("Asus", "računar"), "2C:56:DC": ("Asus", "računar"),
    "1C:1B:0D": ("Gigabyte", "računar"), "94:DE:80": ("Gigabyte", "računar"),
    "00:1B:FC": ("Asus", "računar"), "D8:5E:D3": ("Asus", "računar"),
    "00:E0:4C": ("Realtek", "mrežna kartica"),
    "00:1B:21": ("Intel", "mrežna kartica"), "00:15:17": ("Intel", "mrežna kartica"),
    "A4:BB:6D": ("Intel", "mrežna kartica"), "8C:16:45": ("Intel", "mrežna kartica"),
    "48:2A:E3": ("Intel", "mrežna kartica"), "E4:B9:7A": ("Intel", "mrežna kartica"),

    # mrežna oprema
    "00:0C:29": ("VMware", "virtuelna mašina"), "00:50:56": ("VMware", "virtuelna mašina"),
    "00:1C:42": ("Parallels", "virtuelna mašina"),
    "08:00:27": ("VirtualBox", "virtuelna mašina"),
    "00:15:5D": ("Microsoft Hyper-V", "virtuelna mašina"),
    "52:54:00": ("QEMU/KVM", "virtuelna mašina"),
    "00:1D:7E": ("Cisco", "mrežna oprema"), "00:1E:14": ("Cisco", "mrežna oprema"),
    "00:26:99": ("Cisco", "mrežna oprema"), "F4:0F:1B": ("Cisco", "mrežna oprema"),
    "4C:5D:3C": ("MikroTik", "mrežna oprema"), "64:D1:54": ("MikroTik", "mrežna oprema"),
    "48:8F:5A": ("MikroTik", "mrežna oprema"), "DC:2C:6E": ("MikroTik", "mrežna oprema"),
    "2C:C8:1B": ("MikroTik", "mrežna oprema"), "74:4D:28": ("MikroTik", "mrežna oprema"),
    "00:15:6D": ("Ubiquiti", "pristupna tačka"), "24:A4:3C": ("Ubiquiti", "pristupna tačka"),
    "78:8A:20": ("Ubiquiti", "pristupna tačka"), "68:D7:9A": ("Ubiquiti", "pristupna tačka"),
    "F0:9F:C2": ("Ubiquiti", "pristupna tačka"), "74:AC:B9": ("Ubiquiti", "pristupna tačka"),
    "50:C7:BF": ("TP-Link", "mrežna oprema"), "A4:2B:B0": ("TP-Link", "mrežna oprema"),
    "C0:25:E9": ("TP-Link", "mrežna oprema"), "98:DA:C4": ("TP-Link", "mrežna oprema"),
    "AC:84:C6": ("TP-Link", "mrežna oprema"), "60:A4:B7": ("TP-Link", "mrežna oprema"),
    "00:1E:58": ("D-Link", "mrežna oprema"), "C8:BE:19": ("D-Link", "mrežna oprema"),
    "00:24:01": ("D-Link", "mrežna oprema"),
    "00:1F:33": ("Netgear", "mrežna oprema"), "A0:40:A0": ("Netgear", "mrežna oprema"),
    "20:4E:7F": ("Netgear", "mrežna oprema"),
    "00:19:CB": ("Zyxel", "mrežna oprema"), "5C:F4:AB": ("Zyxel", "mrežna oprema"),
    "00:04:ED": ("AVM FRITZ!Box", "ruter"), "38:10:D5": ("AVM FRITZ!Box", "ruter"),
    "E0:28:6D": ("AVM FRITZ!Box", "ruter"),
    "00:E0:FC": ("Huawei", "mrežna oprema"), "70:72:3C": ("Huawei", "mrežna oprema"),
    "00:17:C2": ("Huawei", "mrežna oprema"), "F4:9F:F3": ("Huawei", "mrežna oprema"),

    # štampači
    "00:00:48": ("Epson", "štampač"), "00:26:AB": ("Epson", "štampač"),
    "A4:5D:36": ("Epson", "štampač"), "64:EB:8C": ("Epson", "štampač"),
    "00:00:85": ("Canon", "štampač"), "00:1E:8F": ("Canon", "štampač"),
    "2C:9E:FC": ("Canon", "štampač"), "88:87:17": ("Canon", "štampač"),
    "00:80:77": ("Brother", "štampač"), "00:1B:A9": ("Brother", "štampač"),
    "30:05:5C": ("Brother", "štampač"), "00:1B:78": ("HP", "štampač"),
    "00:17:A4": ("HP", "štampač"), "00:25:B3": ("HP", "štampač"),
    "9C:B6:54": ("HP", "štampač"), "00:00:AA": ("Xerox", "štampač"),
    "00:00:F0": ("Samsung", "štampač"), "00:15:99": ("Samsung", "uređaj"),
    "00:23:7D": ("Zebra", "štampač naljepnica"), "00:07:4D": ("Zebra", "štampač naljepnica"),
    "00:1B:B3": ("Kyocera", "štampač"), "00:17:C8": ("Kyocera", "štampač"),
    "00:20:6B": ("Konica Minolta", "štampač"), "00:1E:A0": ("Lexmark", "štampač"),
    "00:21:B7": ("Lexmark", "štampač"), "00:04:00": ("Lexmark", "štampač"),

    # kamere i nadzor
    "BC:AD:28": ("Hikvision", "kamera / NVR"), "C0:56:E3": ("Hikvision", "kamera / NVR"),
    "4C:BD:8F": ("Hikvision", "kamera / NVR"), "58:03:FB": ("Hikvision", "kamera / NVR"),
    "28:57:BE": ("Hikvision", "kamera / NVR"), "A4:14:37": ("Hikvision", "kamera / NVR"),
    "3C:EF:8C": ("Dahua", "kamera / NVR"), "90:02:A9": ("Dahua", "kamera / NVR"),
    "E0:50:8B": ("Dahua", "kamera / NVR"), "4C:11:BF": ("Dahua", "kamera / NVR"),
    "00:80:F0": ("Panasonic", "kamera"), "00:0F:7C": ("Axis", "kamera"),
    "AC:CC:8E": ("Axis", "kamera"), "B8:A4:4F": ("Axis", "kamera"),

    # telefoni, tableti, ostalo
    "00:03:47": ("Intel", "uređaj"),
    "3C:5A:B4": ("Google", "telefon / tablet"), "F4:F5:D8": ("Google", "telefon / tablet"),
    "00:17:88": ("Philips Hue", "pametni uređaj"),
    "B8:27:EB": ("Raspberry Pi", "mali računar"), "DC:A6:32": ("Raspberry Pi", "mali računar"),
    "E4:5F:01": ("Raspberry Pi", "mali računar"),
    "00:1D:60": ("Asus", "uređaj"),
    "00:04:F2": ("Polycom", "IP telefon"), "00:0B:82": ("Grandstream", "IP telefon"),
    "C0:74:AD": ("Grandstream", "IP telefon"), "00:15:65": ("Yealink", "IP telefon"),
    "80:5E:C0": ("Yealink", "IP telefon"), "24:9A:D8": ("Yealink", "IP telefon"),
    "00:0E:08": ("Cisco/Linksys", "IP telefon"),
    "00:50:C2": ("Synology", "NAS"), "00:11:32": ("Synology", "NAS"),
    "24:5E:BE": ("QNAP", "NAS"), "00:08:9B": ("QNAP", "NAS"),
    "00:1F:16": ("Western Digital", "NAS"),
    "00:C0:B7": ("APC", "UPS"), "00:20:85": ("APC", "UPS"),
    "28:29:86": ("Eaton", "UPS"),

    # Apple
    "00:1B:63": ("Apple", "Apple uređaj"), "3C:07:54": ("Apple", "Apple uređaj"),
    "A4:5E:60": ("Apple", "Apple uređaj"), "F0:18:98": ("Apple", "Apple uređaj"),
    "AC:BC:32": ("Apple", "Apple uređaj"), "88:66:A5": ("Apple", "Apple uređaj"),
}


def normalizuj(mac):
    """Sve zapise svodi na AA:BB:CC:DD:EE:FF."""
    if not mac:
        return ""
    z = re.sub(r"[^0-9A-Fa-f]", "", str(mac)).upper()
    if len(z) != 12:
        return ""
    return ":".join(z[i:i + 2] for i in range(0, 12, 2))


def proizvodjac(mac):
    """(proizvođač, vrsta uređaja) ili ('', '') ako prefiks nije poznat."""
    m = normalizuj(mac)
    if not m:
        return "", ""
    return OUI.get(m[:8], ("", ""))


def je_nasumican(mac):
    """Privatna (nasumična) adresa — telefoni je koriste dok se ne spoje na
    poznatu mrežu. Takav uređaj se po MAC-u ne može pratiti."""
    m = normalizuj(mac)
    if not m:
        return False
    return bool(int(m[:2], 16) & 0b10)


def tabela():
    """ARP tabela ove mašine: {ip: MAC}. Popunjava se sama tokom skeniranja
    mreže, jer svaki pokušaj povezivanja prođe kroz ARP."""
    out = {}
    try:
        if JE_WINDOWS:
            r = subprocess.run(["arp", "-a"], capture_output=True, text=True,
                               timeout=20,
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        else:
            r = subprocess.run(["arp", "-an"], capture_output=True, text=True,
                               timeout=20)
        tekst = r.stdout or ""
    except Exception:
        tekst = ""

    if not tekst:
        try:  # Linux bez arp naredbe
            with open("/proc/net/arp", encoding="utf-8") as f:
                for red in f.readlines()[1:]:
                    d = red.split()
                    if len(d) < 4:
                        continue
                    m = normalizuj(d[3])
                    # nepotpun ARP unos ima nule — to nije adresa uređaja
                    if m and m not in ("FF:FF:FF:FF:FF:FF", "00:00:00:00:00:00"):
                        out[d[0]] = m
        except Exception:
            pass
        return out

    for red in tekst.splitlines():
        ip = re.search(r"\b(\d{1,3}(?:\.\d{1,3}){3})\b", red)
        mk = re.search(r"\b([0-9A-Fa-f]{2}(?:[:-][0-9A-Fa-f]{2}){5})\b", red)
        if ip and mk:
            m = normalizuj(mk.group(1))
            if m and m not in ("FF:FF:FF:FF:FF:FF", "00:00:00:00:00:00"):
                out[ip.group(1)] = m
    return out


def opis(mac):
    """Kratak opis za tabelu u izvještaju."""
    p, vrsta = proizvodjac(mac)
    if p:
        return f"{p} ({vrsta})" if vrsta else p
    if je_nasumican(mac):
        return "nasumična adresa (telefon?)"
    return "nepoznat proizvođač"
