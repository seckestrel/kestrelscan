# -*- coding: utf-8 -*-
"""Nalazi koje nijedan alat ne može vidjeti — popunjavaju se u razgovoru.

Svako pitanje ima unaprijed napisan nalaz za odgovor "Ne". Tako se u izvještaju
backup koji ne radi pojavi istim rječnikom kao i nalaz iz skeniranja.
"""
from .nalaz import nalaz, VISOK, SREDNJI, NIZAK, INFO, DOBRO

# id, oblast, pitanje, težina ako je odgovor NE, naslov, rizik, preporuka, sati, trošak
PITANJA = [
    ("backup_postoji", "Backup", "Postoji li backup poslovnih podataka?", VISOK,
     "Backup ne postoji",
     "Kvar diska, ransomware ili krađa znače trajan gubitak svega. Ne postoji "
     "način da se podaci vrate.",
     "Uvesti backup po pravilu 3-2-1-1-0: tri kopije, dva medija, jedna van "
     "lokacije, jedna nedostupna za izmjenu, nula grešaka pri provjeri.",
     4, 240),

    ("backup_baza", "Backup", "Obuhvata li backup bazu poslovnog programa?", VISOK,
     "Backup ne obuhvata bazu poslovnog programa",
     "Dokumenti se mogu vratiti, ali knjigovodstvena ili prodajna baza ne. "
     "Rekonstrukcija bi značila ručni unos iz papira, ako ga ima.",
     "Proširiti backup na bazu, i to kroz izvoz iz samog programa — kopiranje "
     "otvorene baze daje neupotrebljiv fajl.",
     3, 180),

    ("backup_test", "Backup", "Je li ikad testirano vraćanje podataka iz backupa?", VISOK,
     "Vraćanje iz backupa nikad nije testirano",
     "Backup koji se ne testira nije backup nego nada. Greške se otkriju tek "
     "onog dana kad podaci zatrebaju, a tad je kasno.",
     "Odmah izvršiti probno vraćanje tri fajla, pa uvesti kvartalni test sa "
     "zapisnikom ko je i kad testirao.",
     2, 120),

    ("backup_odvojen", "Backup", "Postoji li kopija van lokacije ili nedostupna za izmjenu?",
     VISOK, "Sve kopije su na istom mjestu i stalno dostupne",
     "Ransomware šifruje i eksterni disk koji je stalno priključen. Požar ili "
     "krađa odnose i original i kopiju.",
     "Uvesti rotaciju dva diska sa odnošenjem van prostorija, ili cloud "
     "repozitorij sa zaključanom retencijom.",
     2, 120),

    ("backup_obavijest", "Backup", "Stiže li obavijest kad backup ne uspije?", SREDNJI,
     "Nema obavijesti o neuspjelom backupu",
     "Backup tiho prestane da radi i niko ne primijeti mjesecima.",
     "Uključiti slanje obavijesti na mail pri grešci.", 0.5, 30),

    ("placanje_potvrda", "Postupci",
     "Potvrđuje li se promjena bankovnog računa pozivom na poznat broj?", VISOK,
     "Nema postupka za potvrdu promjene bankovnog računa",
     "Ovo je napad koji u našem okruženju odnese najviše novca malim firmama. "
     "Napadač pošalje stvarnu fakturu sa svojim brojem računa i uplata prođe.",
     "Uvesti pravilo: svaka promjena računa potvrđuje se telefonskim pozivom na "
     "broj iz vlastitog imenika, nikad na broj iz te poruke.",
     1, 0),

    ("placanje_dvoje", "Postupci",
     "Odobravaju li iznosi preko dogovorene granice dvije osobe?", SREDNJI,
     "Veće uplate odobrava jedna osoba",
     "Jedna greška ili jedan kompromitovan nalog dovoljni su da novac ode.",
     "Dogovoriti iznos iznad kojeg su potrebna dva odobrenja i zapisati to.",
     1, 0),

    ("registar_dobavljaca", "Dobavljači", "Postoji li registar računa dobavljača?",
     NIZAK, "Nema registra računa dobavljača",
     "Bez spiska nema sa čim uporediti kad stigne faktura sa izmijenjenim računom.",
     "Napraviti tabelu sa nazivom, kontaktom i brojem računa svakog dobavljača.",
     1, 60),

    ("dobavljaci_pristup", "Dobavljači",
     "Zna li se tačno ko sve spolja ima pristup sistemima?", SREDNJI,
     "Ne postoji evidencija vanjskih pristupa",
     "Serviseri, knjigovođe i agencije često zadrže pristup godinama nakon "
     "završetka saradnje. Upad kroz dobavljača se ne primijeti.",
     "Popisati sve vanjske pristupe, ukinuti nepotrebne, za ostale uvesti "
     "pojedinačne naloge sa dvofaktorskom zaštitom.",
     2, 120),

    ("obuka", "Zaposleni", "Jesu li zaposleni prolazili obuku o prevarama?", SREDNJI,
     "Zaposleni nisu prošli obuku",
     "Najveći broj uspješnih napada ne probija zaštitu nego ubijedi čovjeka. "
     "Bez obuke zaposleni ne prepoznaju ni osnovne znakove.",
     "Održati obuku od 30 minuta sa stvarnim primjerima, i ponavljati je "
     "jednom godišnje i za svakog novog zaposlenog.",
     2, 150),

    ("prijava_greske", "Zaposleni",
     "Zna li zaposleni kome prijavljuje sumnjivu poruku, bez straha od posljedica?",
     SREDNJI, "Nema jasnog pravila za prijavu sumnjive poruke",
     "Ako prijava nosi posljedice, greška se krije — a tih nekoliko sati ćutanja "
     "je razlika između incidenta i katastrofe.",
     "Odrediti osobu kojoj se prijavljuje i naglasiti naglas da prijava greške "
     "nema posljedice.",
     0.5, 0),

    ("offboarding", "Zaposleni",
     "Postoji li lista koraka kad zaposleni napusti firmu?", SREDNJI,
     "Nema postupka za odlazak zaposlenog",
     "Nalozi bivših zaposlenih ostaju aktivni godinama. Niko ih ne prati, a "
     "lozinka se ne mijenja.",
     "Napraviti listu: gašenje naloga, oduzimanje opreme, promjena dijeljenih "
     "lozinki, uklanjanje sa mejling lista — sve istog dana.",
     1, 60),

    ("menadzer_lozinki", "Lozinke i pristupi", "Koristi li se menadžer lozinki?",
     SREDNJI, "Lozinke se čuvaju izvan upravljanog sistema",
     "Lozinke u svesci, u Excelu ili u pregledaču dostupne su svakome ko dođe "
     "do te mašine ili fajla.",
     "Uvesti menadžer lozinki, prebaciti naloge, pa tek onda mijenjati lozinke "
     "na jače. Obrisati stare spiskove nakon prebacivanja.",
     2, 120),

    ("plan_incident", "Postupci", "Postoji li napisan plan za slučaj incidenta?",
     NIZAK, "Nema plana za incident",
     "U prvih pola sata se odlučuje koliko će štete biti. Bez plana se gubi "
     "vrijeme na dogovaranje ko koga zove.",
     "Napisati plan na jednu stranu: ko se zove, šta se isključuje, šta se ne "
     "dira, i odštampati ga — jer u incidentu računar možda ne radi.",
     2, 120),

    ("ruter_lozinka", "Mreža", "Je li promijenjena fabrička lozinka na ruteru?",
     SREDNJI, "Na ruteru je fabrička lozinka",
     "Fabričke lozinke su javno objavljene za svaki model. Ko dođe do mreže, "
     "preuzima ruter i može preusmjeriti sav saobraćaj.",
     "Promijeniti lozinku, ažurirati firmver, isključiti UPnP i WPS.",
     1, 60),

    ("mreza_gosti", "Mreža", "Postoji li odvojena WiFi mreža za goste?", SREDNJI,
     "Gosti su na istoj mreži kao poslovni uređaji",
     "Telefon svakog posjetioca nalazi se na istoj mreži kao server sa podacima. "
     "Zaražen uređaj ima direktan put do njega.",
     "Uključiti gostujuću mrežu sa izolacijom i zasebnom lozinkom. Poslovnu "
     "lozinku ne dijeliti nikome izvan firme.",
     1, 60),

    ("stara_oprema", "Fizička sigurnost",
     "Briše li se podatak sa opreme prije bacanja ili prodaje?", NIZAK,
     "Stara oprema se otpisuje bez brisanja podataka",
     "Podaci se vraćaju sa diska i nakon formatiranja. Prodan ili bačen računar "
     "iznosi dokumentaciju iz firme.",
     "Uvesti brisanje u više prolaza ili fizičko uništavanje diska, uz zapisnik.",
     1, 60),

    ("prostorije", "Fizička sigurnost",
     "Je li serverska oprema u prostoriji koja se zaključava?", NIZAK,
     "Oprema nije fizički zaštićena",
     "Ko dođe do servera, dođe i do podataka — bez ijedne lozinke.",
     "Premjestiti opremu u prostoriju koja se zaključava ili u zaključan ormar.",
     1, 60),
]

PO_ID = {p[0]: p for p in PITANJA}


def po_oblastima():
    """Za prikaz u UI."""
    out = {}
    for pid, oblast, pitanje, *_ in PITANJA:
        out.setdefault(oblast, []).append({"id": pid, "pitanje": pitanje})
    return out


def u_nalaze(odgovori, biljeske=None):
    """odgovori: {id: 'da'|'ne'|'nz'|'np'} · biljeske: {id: tekst}"""
    biljeske = biljeske or {}
    nalazi = []
    for pid, odg in (odgovori or {}).items():
        p = PO_ID.get(pid)
        if not p:
            continue
        _, oblast, pitanje, tez, naslov, rizik, preporuka, sati, trosak = p
        b = (biljeske.get(pid) or "").strip()

        if odg == "ne":
            nalazi.append(nalaz(
                oblast, naslov, tez,
                (b or f'U razgovoru je potvrđeno — na pitanje "{pitanje}" '
                      f'odgovor je ne.'),
                rizik, preporuka, sati, trosak,
                dokaz=[f"Utvrđeno u razgovoru sa klijentom: {pitanje} → NE"]))
        elif odg == "da":
            nalazi.append(nalaz(
                oblast, pitanje.rstrip("?"), DOBRO,
                b or "Potvrđeno u razgovoru sa klijentom.",
                dokaz=[f"{pitanje} → DA"]))
        elif odg == "nz":
            nalazi.append(nalaz(
                oblast, f"Nije poznato: {pitanje.rstrip('?').lower()}", SREDNJI,
                b or "U firmi niko nije znao odgovor na ovo pitanje.",
                "Kad se za nešto ne zna odgovor, obično znači da se time niko ne "
                "bavi. Tretira se kao da ne postoji dok se ne dokaže suprotno.",
                "Utvrditi stvarno stanje i tek onda planirati korake.",
                1, 60, dokaz=[f"{pitanje} → ne zna se"]))
        # 'np' (ne primjenjuje se) se preskače
    return nalazi
