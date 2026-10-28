# KestrelScan

Alat za sigurnosni pregled malih firmi. Objedinjuje provjere koje se inače rade
kroz šest različitih alata, i na kraju sam napravi PDF izvještaj po KestrelSec
šablonu — sa nalazima, bodovima, planom po fazama i procjenom troška.

Otvara se u pregledaču, radi sa USB-a, ne traži instalaciju.

---

## Pokretanje

**Windows** — dvoklik na `POKRENI.bat`

Prvi put traje oko minut (priprema okruženje). Poslije se otvara za par sekundi.
Treba Python sa python.org, uz obavezno čekirano **"Add Python to PATH"** pri instalaciji.

**Linux / macOS** — `./POKRENI.sh`

Pregledač se otvara sam na `http://127.0.0.1:8777`. Dok je prozor konzole otvoren,
alat radi. Zatvoriš prozor — alat se gasi.

### Verzija bez Pythona

**Na mašini klijenta Pythona po pravilu nema**, i nema ga šta ni instalirati.
Zato se jednom, na svom računaru, napravi `.exe` koji nosi Python u sebi.

Jednom, na svom računaru:

1. Instaliraj Python sa [python.org/downloads](https://www.python.org/downloads/)
   — na prvom ekranu **obavezno čekiraj „Add python.exe to PATH"**.
2. Dvoklik na `NAPRAVI_EXE.bat`. Traje dvije do tri minute i treba mu internet.
3. Gotov `dist\KestrelScan.exe` kopiraj na USB.

Na USB ide:

```
USB:\
  KestrelScan.exe
  postavke.json         <- ključevi i potpis
  tools\PingCastle.exe   <- ako ga koristiš
```

Folder `rezultati\` se pravi sam, pored exe fajla.

Exe nosi KestrelSec ikonu, a u **Svojstvima fajla** stoji ime firme, opis i
verzija — Windows to pokaže i u upozorenju pri prvom pokretanju.

**Upozorenje „Windows protected your PC" je očekivano.** Javlja se za svaki
program koji nije potpisan sertifikatom, bez obzira šta radi: *More info →
Run anyway*. Da upozorenja nema, treba sertifikat za potpisivanje koda
(oko 200–400 € godišnje) — vrijedi razmisliti kad alat počne da ide kod više
klijenata, jer pred klijentom to izgleda ozbiljnije.

`POKRENI.bat` i `NAPRAVI_EXE.bat` sami traže Python: prvo preko pokretača `py`,
pa `python`, pa po uobičajenim putanjama instalacije. Prazna ljuska iz Microsoft
Store-a se prepoznaje i preskače. Ako ga stvarno nema, ispišu šta da se uradi.

---

## Šta provjerava

**Spolja** — ne traži pristup mreži klijenta, može se uraditi prije dolaska:

| Provjera | Šta radi | Treba |
|---|---|---|
| **Mail domena** | SPF, DKIM, DMARC, MX — direktni DNS upiti | — |
| **Sertifikat i TLS** | Istek, verzije protokola, sigurnosna zaglavlja, preusmjeravanje | — |
| **CMS i izloženi fajlovi** | Prepoznavanje sistema i verzije, provjera `.env`, `.git`, arhiva i drugih javnih putanja | — |
| **Izloženost sa interneta** | Skenira javnu adresu klijenta — **pokreće se sa svoje veze**, ne iz njegove mreže | — |
| **Pasivni uvid (Shodan)** | Šta o adresi klijenta već zna javna evidencija interneta: otvoreni servisi, prepoznat proizvod i verzija, CVE oznake, datum zadnjeg viđenja. **Ne dira se klijentova mreža**, pa se može i prije prvog sastanka | Shodan ključ (neobavezno) |
| **Procurjeli nalozi** | Have I Been Pwned — provjerava svaku unesenu adresu | ključ (~4 $/mj) |

**Na mreži klijenta** — pokreće se sa lokacije:

| Provjera | Šta radi | Treba |
|---|---|---|
| **Mreža i otvoreni servisi** | Popis uređaja sa IP i **MAC adresom**, prepoznat proizvođač po MAC-u (štampač, kamera, pristupna tačka…), portovi, nesigurni protokoli | — |
| **Dijeljeni folderi** | Folderi otvoreni za sve, spiskovi vidljivi bez prijave | Windows |
| **Bežična mreža** | Šifrovanje, sačuvani profili, otvorene mreže | Windows |
| **Inventar uređaja** | Model, procesor, memorija, disk i sistem sa svake mašine, sortirano po starosti, sa procjenom za zamjenu | Windows + administratorski nalog |
| **Popis štampača** | Način povezivanja (USB, WSD, direktni TCP/IP, dijeljeni), mrežni štampači sa otvorenim servisima, SNMP sa fabričkom zajednicom | Windows |

**Na mašini klijenta** — sa USB-a, na računaru u domenu:

| Provjera | Šta radi | Treba |
|---|---|---|
| **Postavke sistema** | BitLocker, SMB, administratori, firewall, antivirus, zakrpe, evidencija prijava | Windows |
| **Politika lozinki** | Minimalna dužina, istek, zaključavanje naloga | Windows |
| **Licence i aktivacija** | Je li Windows i Office aktiviran, kakvim ključem (OEM, Retail, MAK, KMS), koliko roka ostaje, i postoji li u firmveru neiskorišten OEM ključ | Windows |
| **Softver i daljinski pristup** | Instalirani programi, TeamViewer i slični alati, lozinke u pregledaču, Office makroi | Windows |
| **Backup softver i zadaci** | Instalirani backup programi, zakazani zadaci, kad je zadnji put nešto odrađeno i je li palo | Windows |
| **Spremnost za Windows 11** | TPM, Secure Boot, procesor, memorija, disk — može li se nadograditi ili se mijenja | Windows |
| **Popis hardvera** | MAC adrese mrežnih kartica, starost uređaja, SSD ili NVMe ili HDD, zdravlje i sati rada diska, tip i takt memorije (DDR3/DDR4/DDR5) i slobodni slotovi, sistem, baterija | — |
| **Active Directory** | PingCastle ocjena domena | PingCastle.exe u `tools\` |

### Inventar uređaja i procjena za zamjenu

Alat se poveže na svaku Windows mašinu pronađenu u popisu mreže i povuče model,
procesor, memoriju, disk i verziju sistema. Iz toga pravi tabelu sortiranu od
najstarijeg uređaja, sa ocjenom: **Za zamjenu**, **Planirati zamjenu**,
**Nadogradnja sistema** ili **U redu**.

Za to je potreban administratorski nalog na tim mašinama — u domenu je to obično
domenski administrator. Unosi se u polja iznad područja provjere. **Lozinka se
nigdje ne snima** — koristi se samo dok skeniranje traje i ne upisuje se u
`nalazi.json`.

Ako naloga nema, inventar se neće napraviti, ali ostale provjere rade normalno.

#### Kako se računa starost

**Datum BIOS-a nije datum proizvodnje.** Mijenja se pri svakom ažuriranju
firmvera, pa svježe ažuriran sedmogodišnji laptop izgleda kao nov. Zato alat
starost računa iz **generacije procesora** — tu su Intel Core i Core Ultra,
Xeon, AMD Ryzen, Ryzen AI, Threadripper i EPYC — i dodaje otprilike godinu
koliko prođe od izlaska procesora do isporuke uređaja.

Sati rada diska služe kao potvrda i daju najmanju moguću starost. Datum BIOS-a
i datum instalacije sistema ulaze u izvještaj kao dokaz, ali ne kao mjera.

Procjena je tačna unutar otprilike godinu dana, što je dovoljno za odluku o
zamjeni.

### Poređenje sa prošlim pregledom

Kad za istu firmu postoji raniji pregled, alat ga sam pronađe i u izvještaj doda
sekciju **„Šta se promijenilo od prošlog pregleda"**: kretanje ocjene, šta je
riješeno, šta je novo i šta i dalje stoji.

To je ono što mjesečni izvještaj pretvara iz slike stanja u dokaz da si radio.

### VPN i tuđe mreže — granica koju ne prelaziš

Firma često ima VPN prema nečijem centralnom sistemu: zdravstvenom
informacionom sistemu, laboratoriji, matičnoj ustanovi, dobavljaču programa.
Sa mašine klijenta se preko tunela dolazi do **mreže koja nije njegova**.

Saglasnost koju ti je dao klijent pokriva **samo njegovu mrežu**. Skeniranje
preko tunela je skeniranje tuđeg sistema, bez saglasnosti vlasnika — i na
drugoj strani to vidi njihov nadzor.

Alat zato radi dvije provjere prije skeniranja:

- prepozna **VPN i tunel adaptere** na mašini (FortiClient, AnyConnect,
  OpenVPN, WireGuard, GlobalProtect, Pulse, ZeroTier, Tailscale, PPP…) i upiše
  nalaz da tunel postoji;
- uporedi **traženi opseg sa mrežama na koje je mašina priključena**. Ako opseg
  nije ni jedna od njih, javi *„Traženi opseg nije mreža ove mašine"* — znak da
  se do njega dolazi preko rutera ili tunela.

Oba nalaza su informativna, alat te ne zaustavlja. Odluka je tvoja, ali ako je
druga strana tuđa — ne skeniraj.

**Šta umjesto toga ide u izvještaj:** postojanje VPN-a, čemu služi, ko sve može
da se spoji, ima li dvofaktorsku prijavu, i da li dobavljač ima stalan pristup.
To su nalazi koji se dobijaju razgovorom, a vrijede više od skeniranja tuđe
mreže.

### Kad popis mreže nije potpun

Skeniranje vidi samo ono što u tom trenutku odgovara. Uređaj ostaje nevidljiv
ako je ugašen ili uspavan, ako ima firewall koji odbija sve i ne odgovara na
ping, ako je na drugom opsegu, ili ako ga bežična izolacija odvaja od žičane
mreže.

Zato alat uz popis gleda i **ARP tabelu** mašine — spisak svih sa kojima je ta
mašina nedavno komunicirala. Adresa koja je u ARP tabeli a nije odgovorila na
skeniranje dobija zaseban nalaz *„Još N uređaja postoji ali nije odgovorilo"*,
sa MAC adresom i prepoznatim proizvođačem.

Kad se to javi:

1. Traži od klijenta pristup ruteru i pogledaj **spisak dodijeljenih adresa
   (DHCP lease)** — to je jedini potpun spisak onoga što je na mreži.
2. Ako su uređaji na drugom opsegu, upiši više opsega odvojenih zarezom:
   `192.168.1.0/24, 192.168.2.0/24`.
3. Pokreni mrežni pregled sa druge mašine ili sa bežične mreže, pa spoji
   preglede zbirnim izvještajem — različite mašine vide različite dijelove.
4. Ono što ostane nevidljivo unesi ručno, u formi *Uređaj koji alat nije
   očitao*.

### Pokreni kao administrator

Na Windowsu desni klik na alat i **Pokreni kao administrator**. Bez toga
BitLocker, evidencija prijava i dio SMB postavki vrate prazno ili grešku — a
pregled izgleda uredno, što je gore nego da je pukao. Alat sam provjeri prava
i ispiše žutu traku ako nisu dovoljna.

### Šta vidi jedna mašina, a šta cijela firma

Pitanje koje se prvo postavi na terenu: ako pokrenem alat na jednom računaru,
hoće li on pregledati i ostale? Odgovor zavisi od provjere, i dijeli se na tri
grupe.

**1. Cijela firma iz jednog pokretanja** — ove ne zavise od toga na kojoj si
mašini:

| Provjera | Šta pokrije |
|---|---|
| Mail domena, Sertifikat i TLS, CMS | domen i sajt firme |
| Procurjeli nalozi | sve adrese koje upišeš |
| Pasivni uvid, Izloženost sa interneta | javna adresa firme |
| Mreža i otvoreni servisi | **sve uređaje na mreži** — IP, MAC, proizvođač, otvoreni portovi |
| Active Directory | cijeli domen |

**2. Samo mašina na kojoj je alat pokrenut** — ovo se najčešće promaši:

BitLocker, firewall, antivirus, zakrpe, administratorski nalozi, instalirani
softver, lozinke u pregledaču, backup, popis hardvera, spremnost za Windows 11,
licence i aktivacija, bežične mreže.

Ako na toj jednoj mašini BitLocker radi, **to ne znači da radi i na ostalima**.
Izvještaj iz jednog pokretanja opisuje jednu mašinu, ne firmu.

**3. Inventar uređaja — jedina koja zaviri u druge mašine.** Otvara CIM sesiju
preko DCOM-a prema svakoj mašini sa mreže i čita model, serijski broj,
procesor, memoriju, disk i verziju sistema. Treba joj administratorski nalog
koji se upisuje u polja na vrhu.

Ali čita **samo popis opreme** — ne i postavke sigurnosti. BitLocker, firewall
i softver se preko nje ne vide.

**Iz toga slijedi:**

- Za **ponudu i prvi pregled** dovoljno je jedno pokretanje sa jedne mašine, uz
  uključen Inventar uređaja. Dobiješ popis mreže, popis opreme sa svih mašina,
  sve spoljne provjere i jednu mašinu detaljno — dovoljno da se vlasniku pokaže
  stanje.
- Za **pregled koji se naplaćuje po uređaju** moraš proći mašine, pa spojiti
  preglede kroz zbirni izvještaj. Postupak je opisan ispod.

### Postupak za firmu sa više računara

Primjer: petnaest računara kod jednog klijenta.

**1. Prije dolaska, od kuće — jednom za cijelu firmu.**
Čekiraj samo grupu **Spolja** (domena, sertifikat, CMS, procurjeli nalozi,
izloženost). Naziv firme upiši tačno onako kako ćeš ga upisivati i poslije —
po njemu se pregledi kasnije spajaju i porede.

**2. Na lokaciji, jednom sa bilo koje mašine u domenu.**
Čekiraj **Mreža**, **Inventar uređaja**, **Dijeljeni folderi**. Inventar sam
povuče model, procesor, memoriju i sistem sa svih petnaest mašina — za to ne
moraš obilaziti nijednu.

**3. Obilazak mašina — ovdje ide USB.**
Lokalne provjere vide samo mašinu na kojoj su pokrenute. Na svakoj mašini
čekiraj **Postavke sistema, Politika lozinki, Softver i daljinski pristup,
Popis hardvera, Spremnost za Windows 11, Backup** i pokreni. Traje dvije do tri
minute po mašini.

U polje **Naziv firme** svaki put upiši isto. Alat sam zapisuje ime mašine, pa
se pregledi kasnije razlikuju po njemu.

Ne moraš obići svih petnaest. Uzorak od pet-šest mašina koje pokrivaju različite
uloge (knjigovodstvo, recepcija, direktor, server, jedan laptop koji ide kući)
daje realnu sliku, a inventar iz koraka 2 ionako pokriva sve.

**4. Spajanje.**
U odjeljku **Zbirni izvještaj** čekiraj sve preglede te firme i klikni
*Napravi zbirni izvještaj*. Dobijaš jedan PDF u kojem nalaz sa više mašina stoji
jednom, sa spiskom pogođenih i procjenom troška uvećanom za taj broj.

Vremenski: korak 1 je petnaest minuta, korak 2 je deset, korak 3 je oko
petnaest minuta za šest mašina, spajanje je trenutno.

### Zbirni izvještaj sa više mašina

Lokalne provjere — BitLocker, makroi, lozinke u pregledaču — vide samo mašinu na
kojoj je USB. Zato alat pokreneš na svakoj mašini, a onda u odjeljku **Zbirni
izvještaj** izabereš te preglede i spojiš ih u jedan.

Nalaz koji se javlja na više mašina prikazan je jednom, sa spiskom pogođenih i
procjenom troška uvećanom za taj broj: *„Pogođeno 7 od 9 mašina"*.

### Pregled sa druge mašine

Zbirni izvještaj se pravi od pregleda koji stoje u istom folderu `rezultati\` pored
alata. Zato je najjednostavnije pokretati alat **sa istog USB stika** na svakoj
mašini — rezultati svih mašina padnu na stick i zbirni radi bez ikakvog prenosa.

Ako je alat kopiran na svaki računar posebno, svaki ima svoj `rezultati\` i u
spisku vidiš samo jedan pregled, pa se dugme za zbirni ne otključava (traži najmanje
dva). Tada pregled uvezi, u panelu **Zbirni izvještaj → Pregled sa druge mašine**:

- **Iz fajla** — izabereš `nalazi.json` sa druge mašine, ili zip cijelog foldera
  pregleda. U zipu može biti i više pregleda odjednom.
- **Sa putanje** — upišeš putanju i alat sam pokupi sve preglede sa nje:
  `E:\rezultati`, `\\server\pregledi`, `D:\prenos\Saldo_RAC-02_2026-10-13_2104`.
  Radi i na folder jednog pregleda, i na cijeli `rezultati\` folder sa više njih.

Isti pregled se ne može uvesti dvaput — prepoznaje se po firmi, mašini, datumu i
broju nalaza, pa se jedna mašina ne pojavi dvaput u zbirnom izvještaju.

### Dva dokumenta na kraju

Svaki pregled pravi dva PDF-a:

- **Sigurnosni pregled** — puni izvještaj sa nalazima, dokazima i planom po fazama. Za onoga ko popravlja.
- **Sažetak** — jedna strana: ocjena, tri najvažnije stavke, cijena i paketi. Za vlasnika, da ostaviš na stolu.

### Ispravka procjene i stručni komentar

**Procjena koju alat izračuna je prosjek, ne nalaz.** Ažuriranje WinZipa i WinRAR-a
alat procijeni na dva sata i 120 KM, a tebi je to dva minuta uz ostali posao. Zato
ispod svakog nalaza, nakon skeniranja, stoji okvir **„Ispravi procjenu i dodaj
stručni komentar"**:

- **Sati** i **Trošak (KM)** — upiši stvarnu vrijednost
- **Težina** — spusti ili podigni nalaz ako je procjena alata promašila
- **Stručni komentar** — ide u izvještaj kao *„Napomena tehničara"*, ispod nalaza

Kad snimiš ispravku, javi se žuti pojas **„Izvještaj nije u skladu sa nalazima"**.
Pritisneš **Napravi izvještaj ponovo** i oba PDF-a se naprave od ispravljenih
podataka. Ukupan trošak u poglavlju 6 se preračuna sam.

Stara vrijednost se ne briše. U izvještaju piše *„Ispravljeno nakon skeniranja:
sati rada: 2 → 0.25"*, a u zapisima ostaje ko je i kada ispravio. To je bitno ako
klijent kasnije pita zašto cijena nije ona sa prvog izvještaja.

### Uređaj koji alat nije očitao

Mašina koja je ugašena, pokvarena, van domena ili je štampač bez drajvera ipak
postoji i mora ući u popis — inače izvještaj tvrdi da firma ima deset računara, a
ima dvanaest.

Ispod nalaza je forma za ručni unos: vrsta, naziv, proizvođač, model, serijski broj,
IP, lokacija, procijenjena starost, stanje i napomena. Stanje određuje težinu nalaza
(*ne radi* → visok, *potrebna zamjena* i *potreban servis* → srednji, *nije bio
dostupan* → info). U izvještaju takav nalaz nosi oznaku **„ručni unos tehničara"**,
pa se zna šta je mjereno a šta vidjeno.

### Lokacija pregleda

Polja **Regija / Lokacija / Podlokacija** idu u zaglavlje izvještaja kao jedan red
(*Banja Luka | Centralna kancelarija | II sprat, računovodstvo*) i u svaki zapis.
Za firmu sa poslovnicama to je razlika između „pregled firme" i „pregled koje
poslovnice, kada".

**Napomena o pregledu** ide ispod podataka o klijentu — tu se piše ono što važi za
cijeli pregled, a ne za jedan nalaz (*„rađeno van radnog vremena, dvije mašine
ugašene"*).

### Koliko šta traje

Na kraju pregleda, u dnevniku i u zapisima, stoji utrošeno vrijeme po provjeri:

```
── Utrošeno vrijeme: 14 min 20 s ──
     12 min 05 s  Inventar uređaja (84%)
      1 min 30 s  Dijeljeni folderi (10%)
           25 s   Mreža i otvoreni servisi (3%)
```

Orijentir za mrežu `/24` (254 adrese): **20 do 25 sekundi**. Toliko traje jer se
svaka adresa kuca na 17 portova sa 0,6 s čekanja, u 128 niti odjednom.

Ako pregled traje mnogo duže, vrijeme skoro uvijek odlazi na:

| Provjera | Zašto |
|---|---|
| **Inventar uređaja** | CIM sesija preko DCOM-a prema svakoj mašini; nedostupna mašina čeka istek 30–60 s |
| **Dijeljeni folderi** | SMB popis po svakoj mašini na mreži |
| **Procurjeli nalozi** | 6,5 s pauze između adresa — to traži sam HIBP |
| **Active Directory** | PingCastle na pravom domenu ide minutama |
| **Softver** | `Get-WinEvent` puzi na mašini sa velikim sigurnosnim dnevnikom |

### Zapisi

Svaki pregled vodi `zapisi.jsonl` u svom folderu — jedan red po događaju, dopisuje
se, ne mijenja: pokretanje, svaka izvršena provjera, svaka greška, svaka ispravka
sa starom i novom vrijednošću, svaki ručno unesen uređaj, svaki napravljen PDF.
U sučelju se vide pod **Zapisi o pregledu**.

Zašto to treba: kad klijent za tri mjeseca pita „jeste li uopšte gledali backup",
odgovor je red sa datumom, a ne sjećanje.

### Razgovor sa klijentom

Ispod provjera je lista od 18 pitanja koja nijedan alat ne može odgovoriti — radi li
backup, postoji li pravilo za promjenu bankovnog računa, je li iko prošao obuku.
Popunjavaš je dok skeniranje radi, u razgovoru.

Svako **„ne"** postaje nalaz u izvještaju, sa već napisanim obrazloženjem rizika,
preporukom i procjenom troška. **„Ne zna se"** se tretira kao srednji rizik —
kad se za nešto ne zna, obično znači da se time niko ne bavi.

U polje za bilješku upišeš šta si stvarno zatekao i to ide u izvještaj umjesto
standardnog teksta. Primjer: *„Testirano na licu mjesta — dokumenti se vraćaju,
baza knjigovodstva nije u backupu."*

### Mrežni opseg

Polje prima CIDR zapis i sam alat ponudi mrežu mašine na kojoj si:

| Upisano | Znači |
|---|---|
| `192.168.1.0/24` | cijela mreža — najčešći slučaj |
| `192.168.1.57/24` | isto to; ne moraš računati gdje mreža počinje |
| `192.168.1.57` | samo ta jedna adresa |
| `192.168.1.0/25` | donja polovina, 126 adresa |
| `192.168.1.0/255.255.255.0` | ista stvar, maska ispisana |

**Više mreža se odvaja zarezom**, za firme sa odvojenim VLAN-ovima:

```
192.168.1.0/24, 192.168.10.0/24, 10.0.0.0/24
```

Odvajaju se i tačka-zarezom ili razmakom. Iste mreže se ne skeniraju dvaput, a
dio koji nije prepoznat (npr. `192.168.1.10-50`) se preskoči uz napomenu u
izvještaju — ostatak se skenira normalno.

Ukupno se skenira najviše 512 adresa po pregledu. Preko toga alat upiše napomenu
u izvještaj i predloži da se mreže pregledaju odvojeno pa spoje zbirnim
izvještajem.

Mrežni dio je pisan u čistom Pythonu — **ne traži Nmap ni Npcap drajver**, pa radi
sa USB-a na zaključanoj mašini. Isto je što radi `nmap -sT`.

---

## Ažuriranje

Alat pri pokretanju pročita jedan mali JSON sa interneta i uporedi broj verzije
sa svojim. Ako je objavljena novija, pojavi se traka ispod zaglavlja sa spiskom
promjena i dugmetom **Ugradi sad** — preuzme zip, raspakuje ga preko sebe i javi
da se alat ponovo pokrene.

**Postavke i rezultati se ne diraju.** Pri ugradnji se preskaču `postavke.json`,
`rezultati\` i `tools\`, a zatečeno stanje se prije toga iskopira u
`_prethodna\` — ako nešto pođe po zlu, vrati se ručno iz tog foldera.

### Objava nove verzije preko GitHub izdanja

U **Postavke → Ažuriranje** dovoljno je upisati `korisnik/repozitorij` — alat
sam sastavi adresu. Koristi se `releases/latest/download/`, koja uvijek
pokazuje na zadnje izdanje, pa se u alatu ništa ne mijenja kad objaviš novu
verziju.

Objava ide kroz `objavi.py`, koji je u paketu. Na vrhu tog fajla stoji red
`REPO = "..."` — tu upiši svoj GitHub.

```
python objavi.py 1.6.0 "Dodata provjera licenci" "Popravljen DKIM"
```

Skripta podigne broj verzije u `app.py`, spakuje `KestrelScan.zip` bez
rezultata i postavki, napiše `verzija.json` i `opis.md`, i sve ostavi u folderu
`izdanje\`. Zatim:

```
gh release create v1.6.0 izdanje/KestrelScan.zip izdanje/verzija.json ^
   --title "KestrelScan 1.6.0" --notes-file izdanje/opis.md
```

Ili na github.com: **Releases → Draft a new release**, dodaj oba fajla kao
priloge i objavi. **Oba fajla moraju biti priložena uz izdanje** — alat prvo
čita `verzija.json`, pa iz njega saznaje gdje je zip.

Verzija se poredi po brojevima, pa je 1.10 novije od 1.9.

### Ključevi ne idu u paket

`postavke.json` nije u paketu, u `.gitignore` je, i ne dira se pri ažuriranju.
Tu stoje Shodan i HIBP ključ. U kodu ih namjerno nema, jer paket na GitHubu
može preuzeti svako.

U `.gitignore` su i `rezultati\` — podaci klijenata nikad ne odlaze na GitHub.

---

## Prije prvog korištenja

Otvori **Postavke** i upiši potpis i kontakt koji idu u podnožje izvještaja.
Tu se unose i ključevi: HIBP za provjeru procurjelih naloga i Shodan za pasivni
uvid.

### DKIM selektor

DKIM ključ stoji u DNS-u pod imenom koje bira provajder — `google._domainkey`,
`selector1._domainkey`, `zoho._domainkey`… **Taj spisak se ne može pročitati iz
DNS-a**, mogu se samo pogađati poznata imena. Alat ih proba 58, i prvo ona koja
odgovaraju provajderu iz MX zapisa.

Ako ni jedno ne pogodi, nalaz je **„DKIM nije potvrđen" (info)**, ne „nema
DKIM-a" — jer odsustvo na poznatim selektorima nije dokaz da potpisa nema.

Selektor se nađe za deset sekundi: otvori bilo koju poslanu poruku, prikaži
njen izvorni oblik (Gmail: *Prikaži original*, Outlook: *Prikaži izvor*) i nađi
red `DKIM-Signature:`. U njemu piše `s=nešto` — to „nešto" je selektor. Upiši ga
u polje **DKIM selektor** i provjera ga nađe iz prve.

### Pasivni uvid i Shodan ključ

Provjera radi i **bez ključa** — tada koristi besplatni `internetdb.shodan.io`,
koji daje otvorene portove i CVE oznake. Sa ključem se dobija i prepoznat
proizvod i verzija po portu, ime organizacije i datum zadnjeg viđenja.

Upit po IP adresi (`/shodan/host/{ip}`) **ne troši query kredite**, pa se sa
običnim članstvom može provjeravati koliko treba.

**Podatak je star od nekoliko dana do nekoliko sedmica**, a male firme često
imaju dinamičku adresu, pa ono što je viđeno prošle sedmice može pripadati
drugom pretplatniku. Zato svaki nalaz odavde nosi datum i rečenicu da je iz
javne evidencije, a ne iz mjerenja. Prije nego se po njemu postupa, potvrdi ga
provjerom **Izloženost sa interneta**, koja aktivno provjerava adresu.

---

## Rezultati

Svaki pregled pravi svoj folder, nazvan po firmi, datumu, vremenu i mašini sa koje
je rađen — da se u spisku na prvi pogled zna čiji je i odakle. Zbirni ima predmetak
`ZBIRNI_`:

```
rezultati\Saldo_doo_2026-10-13_21-55_RAC-02\
  Sigurnosni_pregled_Naziv_firme.pdf    <- ovo šalješ klijentu
  Sazetak_Naziv_firme.pdf               <- jedna strana, za vlasnika
  nalazi.json                           <- svi podaci, za dalju obradu
  zapisi.jsonl                          <- šta je rađeno, kad i ko — ne mijenja se
  ad_hc_domen.html                      <- PingCastle izvještaj, ako je pokrenut
```

`nalazi.json` sadrži i sirove ispise, pa se izvještaj može ponovo napraviti ili
dopuniti bez novog skeniranja.

---

### Kako se računa ocjena

Ocjena ide od 0 do 32 i to je KestrelSec skala, nije standard.

Svaki propust nosi bodove po težini — visok 3, srednji 2, nizak 1. Ali **nijedna
oblast ne može izgubiti više od 5 bodova**, bez obzira koliko propusta ima u njoj.
Deset otvorenih portova je i dalje jedan problem, ne deset.

Ocjena je udio izgubljenog u odnosu na ono što se u pregledanim oblastima uopšte
moglo izgubiti, prenesen na skalu 0–32:

```
ocjena = 32 × (1 − izgubljeno / (5 × broj pregledanih oblasti))
```

**Oblast koja nije provjerena ne ulazi u računicu** — ni u brojilac ni u imenilac.
Pregled bez Active Directoryja se ne kažnjava što ga nije gledao.

Bez te granice skala se zasiti: firma sa 25 propusta i firma sa 50 propusta obje
dobiju nulu, pa na sljedećem pregledu ne vidiš da je išta sređeno. Sa granicom
zapuštena firma dobije oko 10, a kad sredi najgore skoči na 23 — i to je ono što
prodaje sljedeći korak.

U izvještaju, u tabeli *Ocjena po oblastima*, piše koliko je koja oblast izgubila.
Oznaka **„najveći mogući"** znači da je ta oblast izgubila sve što je mogla — tu je
najviše posla i tu se najviše dobije kad se sredi.

---

## Tri stvari koje treba znati

**Saglasnost nije formalnost.** Alat te natjera da je potvrdiš prije pokretanja.
Skeniranje tuđe mreže bez pismenog odobrenja je pravni problem bez obzira na namjeru.
Tekst saglasnosti je u dokumentu *KestrelSec — Šablon izvještaja*.

**Antivirus će ga prijaviti.** Program koji skenira portove i čita Windows evidenciju
izgleda tačno kao ono što antivirusi traže. Kod klijenta ga dodaj u izuzetke, ili ga
potpiši sertifikatom za kod (oko 200–400 KM godišnje) ako ćeš ga često nositi.

**Popis hardvera u virtuelnoj mašini ne znači ništa.** Virtuelni disk se skoro
uvijek prijavi kao mehanički, a datum BIOS-a nije datum opreme. Alat to prepozna
i tako i napiše.

**Provjera procurjelih naloga ide sporo, i tako mora.** Servis ograničava broj
upita prema pretplati — najjeftiniji ključ dozvoljava deset upita u minuti,
dakle jedan na šest sekundi. Deset adresa traje oko minut. U Postavkama se bira
pauza koja odgovara tvojoj pretplati; ako je prekratka, servis odbija upite.
Adresa koja nije uspjela provjeru se **ne** prikazuje kao čista nego posebno
navodi, jer neprovjereno nije isto što i čisto.

**Ako jedna provjera padne, pregled se nastavlja.** Svaka provjera radi odvojeno,
pa greška u jednoj ne obara ostale — u izvještaju se pojavi kao napomena, a PDF
se svejedno pravi. Greške se ispisuju i iznad rezultata.

**Ocjena nije presuda.** Bodovi su orijentir za razgovor sa klijentom, ne revizorski
nalaz. Ako nijedna provjera ne da mjerljiv rezultat, alat neće izdati ocjenu — nego
će to i napisati.

---

## Nessus

Nessus se ne može spakovati na USB — to je server koji traži instalaciju i prva
inicijalizacija mu traje dvadesetak minuta. Ostaje kao zaseban korak kad ti treba
dublje skeniranje ranjivosti.

---

## Struktura

```
app.py              web server i pokretanje poslova
izvjestaj.py        PDF izvještaj (reportlab)
skener/
  nalaz.py          zajednički oblik nalaza, bodovanje
  domena.py         SPF / DKIM / DMARC / MX
  sajt.py           sertifikat, TLS, HTTP zaglavlja
  mreza.py          popis uređaja i portova
  windows.py        PowerShell provjere
  pingcastle.py     pokretanje i čitanje PingCastle izvještaja
  nalozi.py         Have I Been Pwned
  cms.py            prepoznavanje CMS-a i izloženi fajlovi
  wifi.py           bežične mreže i sačuvani profili
  dijeljeno.py      dijeljeni folderi, lokalni i mrežni
  softver.py        instalirani programi, daljinski pristup, makroi
  politika.py       politika lozinki i zaključavanja
  hardver.py        popis hardvera ove mašine
  inventar.py       inventar svih mašina na mreži sa procjenom za zamjenu
  starost.py        procjena starosti iz generacije procesora
  win11.py          spremnost za Windows 11
  backup.py         backup softver i zakazani zadaci
  poredjenje.py     poređenje sa prošlim pregledom
  spajanje.py       zbirni izvještaj sa više mašina
  rucno.py          pitanja za razgovor i nalazi iz njih
  rucni_unos.py     ručno uneseni uređaji i ispravke procjene
  stampaci.py       popis štampača i njihovi servisi na mreži
  zapisi.py         zapisi o pregledu (zapisi.jsonl)
sabloni/index.html  stranica
statika/            CSS, JS i logo
fontovi/            DejaVu — da č, ć, ž, š, đ rade i bez instaliranih fontova
tools/              ovdje ide PingCastle.exe
rezultati/          izlaz
```

---

**Dragomir Babić — KestrelSec**
066/531-666 · dragomir@kestrelsec.io · kestrelsec.io
