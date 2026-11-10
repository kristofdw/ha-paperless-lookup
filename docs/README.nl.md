# Paperless Lookup voor Home Assistant

*[English](../README.md)*

Een aangepaste integratie, te installeren via de [Marktplaats](https://www.home-assistant.io/integrations/marketplace/)
(vroeger HACS), die gekozen [Paperless-ngx](https://docs.paperless-ngx.com/)-documenten doorzoekbaar
maakt in [Home Assistant](https://www.home-assistant.io/):

- **Handleidingen bij toestellen:** bekijk de handleiding van een toestel in Home Assistant, op een
  dashboardkaart of in het zijbalkpaneel.
- **Onderweg opzoeken:** zoek kastickets, facturen en garantiebewijzen op je gsm (Home Assistant
  Companion-app), gefilterd op categorie, winkel en datum, ook in de tekst van de documenten (OCR).
- **Opt-in:** alleen documenten met een toegangstag (standaard `HA`) zijn zichtbaar in Home Assistant.
- **Toegang per categorie per Home Assistant-gebruiker:** bijvoorbeeld handleidingen voor iedereen,
  kastickets alleen voor sommige gebruikers.
- **Alleen lezen en privé:** Home Assistant praat met Paperless over je lokale netwerk. Browsers en gsm's
  krijgen nooit een Paperless-token, en Home Assistant bewaart niets behalve koppelingen en instellingen.

Deze vertaling volgt de [Engelse README](../README.md); bij een verschil geldt de Engelse versie.
Menunamen van Paperless staan in het Engels, zoals in de Engelse interface van Paperless-ngx 3.

## Inhoud

1. [Vereisten](#vereisten)
2. [Paperless-ngx voorbereiden](#1-paperless-ngx-voorbereiden)
3. [De integratie installeren](#2-de-integratie-installeren)
4. [De integratie toevoegen](#3-de-integratie-toevoegen)
5. [Kiezen wie wat ziet (opties)](#4-kiezen-wie-wat-ziet-opties)
6. [Gebruiken](#5-gebruiken)
7. [Handleidingen aan toestellen koppelen](#6-handleidingen-aan-toestellen-koppelen)
8. [Hoe gegevens worden bijgewerkt](#hoe-gegevens-worden-bijgewerkt)
9. [Beveiliging](#beveiliging)
10. [Bekende beperkingen](#bekende-beperkingen)
11. [Problemen oplossen](#problemen-oplossen)
12. [Bijwerken en verwijderen](#bijwerken-en-verwijderen)

## Vereisten

| Wat | Versie |
|---|---|
| Home Assistant | 2026.11.0 of nieuwer (met de Marktplaats) |
| Paperless-ngx | 3.0.0 of nieuwer (REST API versie 10) |

Home Assistant moet Paperless via het netwerk kunnen bereiken (bijvoorbeeld `http://paperless.local:8000`).
Je gsm hoeft alleen Home Assistant te bereiken.

## 1. Paperless-ngx voorbereiden

Doe dit in de webinterface van Paperless als beheerder.

### 1.1 De toegangstag

Maak een tag **`HA`** aan (*Attributes → Tags → Create*). Alleen documenten met deze tag kunnen ooit in
Home Assistant verschijnen; al de rest blijft onzichtbaar, ook voor beheerders van Home Assistant. Je mag
een andere naam gebruiken en die later in de opties kiezen.

Zet de tag op de documenten die je in Home Assistant wilt zien. Een document kan meerdere tags hebben, dus
dit stoort je andere tags niet.

> **Tip: automatisch taggen.** Maak een workflow (*Workflows → Create*) met de triggers *Document added*
> en *Document updated*, een filter op de documenttypes die je in Home Assistant wilt, en een
> toewijzingsactie die de tag `HA` toevoegt. Elk kasticket of elke handleiding krijgt de tag dan vanzelf.

### 1.2 Categorieën (documenttypes)

Een **categorie** in Home Assistant is een **documenttype** in Paperless: bijvoorbeeld *Handleiding*,
*Kasticket*, *Factuur*, *Garantie*. Toegang geef je per categorie, dus geef elk document dat je vrijgeeft
een documenttype (*Attributes → Document Types*). Documenten zonder documenttype worden nooit getoond.

### 1.3 Aangepast veld voor toestelmodellen (voor handleidingen)

Om handleidingen automatisch aan toestellen te koppelen, maak je een aangepast veld **`HA model`** van het
type **Text** (*Attributes → Custom Fields*). Vul het bij elke handleiding in met het model van het
toestel, of met meerdere modellen gescheiden door `;`, bijvoorbeeld `E1524/E1810` of
`RTCGQ11LM; MCCGQ11LM`. Zie [Handleidingen aan toestellen koppelen](#6-handleidingen-aan-toestellen-koppelen)
voor welk model je gebruikt.

### 1.4 Een aparte Paperless-gebruiker voor Home Assistant

Maak een gebruiker aan, bijvoorbeeld `ha-lookup` (*Users & Groups → Add User*):

- *Active* aan, *Admin* en *Superuser* **uit**.
- Rechten: alleen **View** op de rijen *Document*, *Tag*, *Correspondent*, *DocumentType*,
  *CustomField* en *UISettings*. Nergens *Add*, *Change* of *Delete*: de integratie schrijft nooit naar
  Paperless. Met *UISettings* kan de integratie zien bij welke gebruiker de token hoort.

**Objectrechten (belangrijk).** In Paperless is een document, tag, documenttype of correspondent met een
**eigenaar** alleen zichtbaar voor andere gebruikers als het met hen gedeeld is. Objecten zonder eigenaar
zijn zichtbaar voor elke gebruiker met het View-recht. Zorg dat de gebruiker `ha-lookup` dit kan zien:

- de tag `HA`,
- de documenttypes die je als categorie wilt,
- de correspondenten (winkels) van die documenten,
- de documenten zelf.

Open het object (*Edit*), ga naar *Permissions* en voeg de gebruiker toe onder *View*. Voor veel objecten
tegelijk gebruik je *Select* en daarna *Permissions* in de lijsten onder *Attributes*, of selecteer je
documenten in de documentenlijst en zet je hun rechten in één keer. Een snelle controle: log in Paperless
in als `ha-lookup` en bekijk de documenten met de tag `HA`. Wat je daar ziet, is het maximum dat Home
Assistant ooit kan tonen.

### 1.5 API-token

Log in Paperless in als `ha-lookup`, open *My Profile* (gebruikersmenu rechtsboven) en maak een **API Auth
Token** aan. Kopieer hem; je vult hem in Home Assistant in bij stap 3. Behandel hem als een wachtwoord.

## 2. De integratie installeren

### Via de Marktplaats (aangeraden)

Home Assistant 2026.11 verving HACS door de ingebouwde Marktplaats. Deze integratie staat nog niet in de
catalogus van de Marktplaats, dus voeg je ze toe via haar GitHub-link:

1. Ga naar *Instellingen →* **Marktplaats**.
2. Kies rechtsboven **Voeg toe via een GitHub-link**. Vul bij **GitHub link**
   `https://github.com/kristofdw/ha-paperless-lookup` (of `kristofdw/ha-paperless-lookup`) in en voeg toe.
   Heb je GitHub nog niet gekoppeld, dan vraagt de Marktplaats dat eerst. Vraagt hij het type, kies dan
   **Integratie**.
3. Open **Paperless Lookup for Home Assistant** en installeer. De Marktplaats waarschuwt dat de integratie
   gemaakt en ondersteund wordt door haar auteur, niet door het Home Assistant-project. De Marktplaats
   installeert de laatste release; wat er veranderde, staat in de [changelog](../CHANGELOG.md) (Engels).
4. **Herstart Home Assistant** als de Marktplaats daarom vraagt (een reparatie biedt de herstart aan), of
   via *Instellingen → Systeem → ⏻ → Herstart Home Assistant*.

Al geïnstalleerd met HACS? Dan hoef je niets te doen: Home Assistant 2026.11 zet je repositories en
updates over naar de Marktplaats.

### Handmatig

Kopieer de map `custom_components/paperless_lookup` van deze repository naar de map `custom_components`
van je Home Assistant-configuratie (maak die aan als ze nog niet bestaat), zodat je
`<config>/custom_components/paperless_lookup/manifest.json` krijgt. Herstart Home Assistant.

## 3. De integratie toevoegen

[![Open je Home Assistant en begin met het instellen van Paperless Lookup.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=paperless_lookup)

Of: *Instellingen → Apparaten en diensten → Integratie toevoegen →* **Paperless Lookup**.

| Veld | Wat je invult |
|---|---|
| URL | Het adres van Paperless zoals Home Assistant het bereikt, bijvoorbeeld `http://192.168.1.10:8000` of `https://paperless.example.org`. Draait Paperless onder een subpad, vul dat mee in (`https://example.org/paperless`). Gebruik het uiteindelijke adres: doorverwijzingen worden niet gevolgd. |
| API-token | De token van `ha-lookup` uit stap 1.5. |
| SSL-certificaat controleren | Laat aan. Zet alleen uit voor een zelfondertekend certificaat op je eigen netwerk. |

De integratie controleert dan de verbinding, de Paperless-versie en de rechten van de gebruiker. Er kunnen
twee waarschuwingen volgen; na elk ervan kun je verder:

- **Onversleutelde verbinding**: het adres begint met `http://`. Prima op een vertrouwd thuisnetwerk;
  gebruik `https://` als Paperless achter een reverse proxy staat.
- **Paperless-gebruiker mag meer dan lezen**: de token hoort bij een superuser of bij een gebruiker met
  rechten om toe te voegen, te wijzigen of te verwijderen. Een gebruiker met alleen View-rechten (stap 1.4)
  is veiliger.

De integratie krijgt de naam van de Paperless-gebruiker (bijvoorbeeld `ha-lookup`). Er kan maar één
Paperless-verbinding zijn.

**Wat je meteen krijgt (standaard):**

- toegangstag: de tag met de naam `HA` (als die bestaat),
- elk documenttype is een categorie, maar **zonder gebruikers**: alleen beheerders van Home Assistant zien
  documenten tot je in de opties toegang geeft,
- toestelcategorie: het documenttype *Handleiding* (of *Manual*), modelveld: het tekstveld `HA model`,
- een zijbalkitem **Paperless Lookup** en de dashboardkaart `custom:paperless-lookup-card`,
- de lijst met documenten wordt elke 60 minuten ververst.

## 4. Kiezen wie wat ziet (opties)

*Instellingen → Apparaten en diensten → Paperless Lookup →* **Configureren**. De opties zijn een menu; elke
keuze in de lijsten komt rechtstreeks uit Paperless. Na elke stap keer je terug naar het menu. Wijzigingen
worden pas bewaard met **Opslaan en sluiten**; sluit je het venster met ✕, dan gaan ze verloren.

- **Toegangstag en zichtbaarheid**
  - *Toegangstag*: de tag die documenten vrijgeeft (zonder tag is niets zichtbaar).
  - *Beheerders zien alle categorieën*: standaard aan. Zet het uit om ook beheerders per categorie toegang
    te geven.
  - *Gebruikers die Paperless Lookup in de zijbalk zien*: kies wie het menu-item krijgt. Kies je niemand,
    dan krijgt iedereen het. Dit gaat alleen over het menu-item: welke documenten iemand mag zien (ook op
    dashboardkaarten), stel je in bij *Gebruikers per categorie*. Een gebruiker met het menu-item maar
    zonder categorie ziet een leeg paneel.
- **Categorieën**: kies welke documenttypes categorieën zijn in Home Assistant. Documenten van andere types
  zijn niet zichtbaar. Daarna gaat het venster verder met *Gebruikers per categorie*.
- **Gebruikers per categorie**: kies per categorie de Home Assistant-gebruikers die ze mogen zien.
  Voorbeeld: *Handleiding* voor iedereen, *Kasticket* en *Factuur* alleen voor twee gebruikers, niets voor
  de gebruiker van een wandtablet. Beheerders zien elke categorie zolang *Beheerders zien alle
  categorieën* aan staat, dus die hoef je niet te kiezen.
- **Toestellen**
  - *Toestelcategorieën*: de categorieën die op model aan toestellen gekoppeld worden (meestal
    *Handleiding*; een categorie *Garantie* werkt ook).
  - *Modelveld*: het aangepaste tekstveld met de modellen (`HA model`).
  - *Zigbee2MQTT-link als reserve*: voor een Zigbee2MQTT-toestel zonder handleiding een link naar zijn
    pagina op zigbee2mqtt.io.
- **Bijhouden wie documenten opent**: kies per gebruiker de categorieën waarvan geopende en gedownloade
  documenten in de activiteit (het logboek) van Home Assistant komen (zie
  [Bijhouden wie wat opent](#bijhouden-wie-wat-opent)). Standaard uit.

Alleen beheerders van Home Assistant kunnen deze opties openen. De integratie herlaadt na *Opslaan en
sluiten*.

### Bijhouden wie wat opent

Paperless weet niet welke Home Assistant-gebruiker een document opende: elke aanvraag komt van de ene
Paperless-gebruiker van de integratie, en het auditlog van Paperless houdt alleen wijzigingen bij. De
integratie kan het openen daarom in het logboek van Home Assistant (*Activiteit*) zetten, bijvoorbeeld om
*Factuur* te volgen voor sommige gebruikers en *Handleiding* te negeren:

1. *Configureren →* **Bijhouden wie documenten opent**.
2. Vink per gebruiker de categorieën aan die je wilt volgen. Elke gebruiker krijgt alleen de categorieën
   die hij mag zien; gebruikers die geen enkele categorie mogen zien, staan in plaats daarvan onder het
   formulier (er is niets dat ze kunnen openen).

Elke preview of download van een gevolgde categorie geeft dan een regel zoals *"Alex opende
Paperless-document 5 (Kasticket)"*: de gebruiker, het tijdstip, het documentnummer en de categorie, nooit
de titel (het logboek staat in de database van Home Assistant). Miniaturen worden niet gelogd, en hetzelfde
bestand binnen een minuut opnieuw openen telt één keer. Een bestand dat de browser nog in zijn cache heeft
(tot 5 minuten), komt niet opnieuw bij Home Assistant en wordt dus ook niet opnieuw gelogd. De tekst staat
in de taal van Home Assistant (*Instellingen → Systeem → Algemeen*), niet in de taal van elke gebruiker.

Om alleen deze regels te zien, open je *Instellingen → Apparaten en diensten → Paperless Lookup →* het
apparaat **Paperless Lookup** (zijn activiteitenkaart), of filter je de activiteit op dat apparaat. Het
documentnummer is de id in Paperless (`/documents/<nummer>/details`).

## 5. Gebruiken

### Het zijbalkpaneel

**Paperless Lookup** in de zijbalk (of `/paperless-lookup`) is gemaakt voor de gsm:

- zoeken in titels en inhoud,
- filterchips per categorie en een periode,
- een winkelfilter met alleen winkels die documenten hebben in de gekozen categorieën; bij veel winkels
  wordt het een zoekveld,
- resultaten met miniatuur, datum, winkel, categorie en de gevonden woorden,
- tik op een resultaat voor een preview met **Openen** en **Downloaden**,
- voor beheerders: een tabblad **Toestellen zonder handleiding** (zie sectie 6).

Gebruikers zonder toegang tot een categorie zien de melding dat ze geen toegang hebben. Wil je het
menu-item voor sommige gebruikers weghalen, gebruik dan *Gebruikers die Paperless Lookup in de zijbalk
zien* in de opties; dat werkt via de zijbalkinstellingen van elke gebruiker, dus een gebruiker kan het
terugzetten onder *Profiel*. De documenten blijven hoe dan ook beschermd in de backend: wie het paneel via
het adres opent, ziet alleen de categorieën waartoe hij toegang heeft.

> Op Android kan de Companion-app geen PDF's in de pagina tonen. De preview toont dan de eerste pagina;
> gebruik **Openen** of **Downloaden** voor het volledige document.

### De dashboardkaart

Voeg een kaart toe via *Dashboard bewerken → Kaart toevoegen →* **Paperless Lookup**; in de visuele editor
kies je een toestel, een entiteit (dan wordt haar toestel gebruikt) of een ruimte. In YAML:

```yaml
# De handleidingen (en andere gekoppelde documenten) van een toestel
type: custom:paperless-lookup-card
device_id: 0123456789abcdef0123456789abcdef
title: Handleiding
```

```yaml
# Het toestel van een entiteit
type: custom:paperless-lookup-card
entity: sensor.washing_machine_power
```

```yaml
# Alle toestellen met documenten in een ruimte, zonder miniaturen
type: custom:paperless-lookup-card
area: kitchen
show_thumbnails: false
```

Het toestel-ID, de entiteit en de ruimte (een ruimte-ID) hierboven zijn voorbeelden: vervang ze door je
eigen waarden, of laat de visuele editor ze invullen. De kaart toont alleen documenten van categorieën die
de kijkende gebruiker mag zien. Beheerders kunnen een koppeling verwijderen met ✕.

## 6. Handleidingen aan toestellen koppelen

Een document van een toestelcategorie wordt gekoppeld aan elk toestel waarvan het model overeenkomt met
een van de modellen in zijn veld `HA model`. Hoofdletters, spaties en de tekens `-`, `_`, `/`, `(` en `)`
tellen niet mee. De modellen van een toestel worden vergeleken, met en zonder de fabrikant ervoor:

- de **model-ID** van het toestel (Zigbee2MQTT: het Zigbee-model, bijvoorbeeld `E1524/E1810`),
- het **model** (bijvoorbeeld `TRADFRI remote control`),
- een deel tussen haakjes van het model (oudere Zigbee2MQTT-versies: `TRADFRI remote control (E1524/E1810)`).

Je vindt ze op de toestelpagina in Home Assistant (*Instellingen → Apparaten en diensten → Apparaten →* het
toestel: de regel onder de naam toont het model en de fabrikant; de model-ID staat bij de
toestelinformatie). Modellen van minder dan drie tekens worden genegeerd, om toevallige koppelingen te
vermijden.

Het paneeltabblad **Toestellen zonder handleiding** (beheerders) toont ingeschakelde toestellen met een
model maar zonder document van een toestelcategorie. Per toestel kun je:

- **Document koppelen**: een document zoeken en met de hand koppelen (elke categorie, bijvoorbeeld een
  factuur),
- **Negeren**: het toestel uit deze lijst halen (voor toestellen die nooit een handleiding krijgen),
- de **Zigbee2MQTT-pagina** openen als de reserve aan staat.

Een automatische koppeling verwijderen (✕ op de kaart) wordt onthouden: het document blijft dan los van
dat toestel.

## Hoe gegevens worden bijgewerkt

- **Zoeken** vraagt het altijd rechtstreeks aan Paperless, en een nieuw document dat een zoekopdracht
  vindt, komt meteen in de lijst.
- **Bestanden** worden bij Paperless opgehaald wanneer iemand ze opent; Home Assistant bewaart geen kopie.
- **De lijst met vrijgegeven documenten** (filterlijsten, toestelkoppelingen, *Toestellen zonder
  handleiding*) wordt elke 60 minuten uit Paperless gelezen. Wil je dat sneller, herlaad dan de integratie
  (*⋮ → Herladen*).

## Beveiliging

- **Opt-in in Paperless**: alleen documenten met de toegangstag in een ingeschakelde categorie zijn
  bereikbaar. Al de rest antwoordt "niet gevonden", ook voor beheerders, zodat zelfs het bestaan van een
  document niet uitlekt.
- **Toegang wordt in de backend gecontroleerd** bij elke aanvraag: elk websocketcommando en elke
  bestandsaanvraag gaat door één centrale controle van de Home Assistant-gebruiker en de categorie.
  Zoekopdrachten naar Paperless zijn altijd beperkt tot de toegangstag en de toegestane categorieën, en de
  resultaten worden in Home Assistant nog eens gecontroleerd. Een kaart verbergen wordt niet als
  bescherming gebruikt.
- **Bestanden** (preview, miniatuur, download) worden via Home Assistant doorgestuurd met ondertekende
  links die na 60 seconden verlopen. Vóór het doorsturen wordt het document live in Paperless
  gecontroleerd (tag en categorie), zodat het weghalen van de tag meteen werkt. Alleen PDF, gangbare
  afbeeldingstypes en platte tekst worden doorgegeven, met een groottelimiet. Een bestand dat een browser al
  laadde, kan tot 5 minuten in zijn cache blijven.
- **De API-token** wordt bewaard in de configuratie van de integratie, zoals bij andere integraties. Hij is
  niet versleuteld op schijf, maar zit wel in de versleutelde back-ups van Home Assistant. Hij wordt nooit
  gelogd, nooit naar de browser gestuurd en weggelaten uit de diagnostische gegevens. Die bevatten ook geen
  URL's, gebruikersnamen of documenttitels.
- **Alleen lezen**: de integratie wijzigt nooit iets in Paperless. Het auditlog van Paperless houdt
  wijzigingen bij, geen leesacties; om te volgen welke Home Assistant-gebruiker wat opent, gebruik je de
  optie [Bijhouden wie documenten opent](#bijhouden-wie-wat-opent).

Een beveiligingsprobleem melden: zie [SECURITY.md](../SECURITY.md).

## Bekende beperkingen

- **Eén Paperless-verbinding**, via één Paperless-gebruiker.
- **Alleen lezen**: documenten, tags en notities kun je niet wijzigen vanuit Home Assistant.
- **Geen entiteiten of acties**: de integratie biedt een paneel en een kaart, dus er is niets om in
  automatiseringen te gebruiken.
- **Geen toegangsrechten per zijbalkitem in Home Assistant**: *Gebruikers die Paperless Lookup in de
  zijbalk zien* verbergt alleen het menu-item. Toegang tot documenten stel je per categorie in.
- **Beheerders zien elke categorie** zolang *Beheerders zien alle categorieën* aan staat; gebruik dus geen
  beheerdersaccount op een gedeeld toestel zoals een wandtablet.
- **Bestandstypes**: alleen PDF, gangbare afbeeldingstypes en platte tekst kunnen geopend worden. Een
  Office-document kan alleen geopend worden als Paperless er een PDF-versie van heeft.
- **Bestandsgrootte**: maximaal 100 MiB per document en 5 MiB per miniatuur.
- **Zoeken** vindt hele woorden. De geavanceerde zoeksyntax van Paperless wordt niet ondersteund.
- **Onderliggende toestellen** (child devices) worden niet aan handleidingen gekoppeld. Modellen van minder
  dan drie tekens worden genegeerd.
- **Android**: de Companion-app kan geen PDF's in de pagina tonen (zie [het paneel](#het-zijbalkpaneel)).

## Problemen oplossen

**Fouten bij het toevoegen van de integratie**

| Melding | Oorzaak en oplossing |
|---|---|
| Kan geen verbinding maken met Paperless | Home Assistant bereikt de URL niet, of Paperless antwoordde met een doorverwijzing of een serverfout. Controleer het adres vanaf de Home Assistant-host (niet vanaf je pc) en gebruik de uiteindelijke URL. |
| Geen Paperless-ngx-API gevonden op dit adres | De URL wijst niet naar Paperless. Controleer de poort en een subpad. |
| De API-token werd geweigerd | Verkeerde of opnieuw aangemaakte token. Maak een nieuwe aan (stap 1.5). |
| De Paperless-gebruiker mist deze rechten: … | Geef de gebruiker de genoemde View-rechten (stap 1.4). `view_uisettings` ontbreekt het vaakst. |
| Deze Paperless-versie wordt niet ondersteund | Werk Paperless-ngx bij naar 3.0.0 of nieuwer. |

**Ik zie geen documenten (of niet alle)**

1. Hebben de documenten de toegangstag, en is die tag gekozen in *Opties → Toegangstag en zichtbaarheid*?
2. Is hun documenttype een categorie (*Opties → Categorieën*), en heeft je gebruiker er toegang toe onder
   *Opties → Gebruikers per categorie* (of ben je beheerder en staat *Beheerders zien alle categorieën*
   aan)? Gekozen zijn voor het zijbalkitem is niet genoeg.
3. Kan de Paperless-gebruiker ze zien? Log in Paperless in als die gebruiker (stap 1.4, objectrechten).
   Een tag of documenttype die hij niet ziet, staat ook niet in de lijsten van de opties.
4. Nieuwe of gewijzigde documenten verschijnen meteen bij het zoeken. Voor toestelkoppelingen en de
   filterlijsten wacht je op de volgende verversing (hoogstens 60 minuten) of herlaad je de integratie
   (*⋮ → Herladen*).

**Meldingen onder *Instellingen → Systeem → Reparaties***

| Melding | Oorzaak en oplossing |
|---|---|
| Paperless-ngx-versie niet ondersteund | Werk Paperless-ngx bij naar 3.0.0 of nieuwer en herlaad daarna de integratie. |
| Paperless-gebruiker mist rechten | Geef de gebruiker de genoemde View-rechten (stap 1.4) en herlaad daarna de integratie. |
| Paperless-toegangstag niet beschikbaar | Er is geen tag gekozen, of de Paperless-gebruiker kan hem niet zien, dus er zijn geen documenten zichtbaar. Maak de tag aan of deel hem (stappen 1.1 en 1.4), of kies een andere in de opties. |

**Een handleiding verschijnt niet bij een toestel**: vergelijk de waarde van `HA model` met het model en
de model-ID op de toestelpagina (sectie 6), en controleer dat het documenttype een toestelcategorie is. Je
kunt altijd met de hand koppelen via *Toestellen zonder handleiding*.

**De kaart meldt "Custom element doesn't exist"**: ververs de browserpagina (leeg zo nodig de cache van de
Companion-app) na het installeren of bijwerken.

**Token gewijzigd of gebruiker verwijderd**: Home Assistant vraagt om opnieuw te verifiëren; vul een token
in van **dezelfde** Paperless-gebruiker. Om het adres of de certificaatcontrole te wijzigen, gebruik je
*⋮ → Opnieuw configureren*. Overschakelen naar een andere Paperless-gebruiker kan alleen door de integratie
te verwijderen en opnieuw toe te voegen (de opties gaan uit van wat die gebruiker in Paperless ziet).

**Diagnostische gegevens**: *Instellingen → Apparaten en diensten → Paperless Lookup → ⋮ → Diagnostische
gegevens downloaden* geeft versies, rechten en aantallen, zonder token, URL, namen of titels. Voeg ze toe
aan een issue.

## Bijwerken en verwijderen

- **Bijwerken**: updates verschijnen onder *Instellingen → Updates*, net als andere updates van Home
  Assistant. Installeer, herstart Home Assistant (een reparatie biedt de herstart aan) en ververs daarna de
  browser.
- **Verwijderen**: *Instellingen → Apparaten en diensten → Paperless Lookup → ⋮ → Verwijderen*. De bewaarde
  koppelingen met handleidingen worden mee verwijderd. Verwijder daarna de repository onder
  *Instellingen → Marktplaats* (of verwijder de map) en herstart. Verwijder in Paperless de gebruiker
  `ha-lookup` of zijn token als je die niet meer nodig hebt.

## Licentie

[Apache-2.0](../LICENSE). Bijdragen: zie [CONTRIBUTING.md](../CONTRIBUTING.md) (Engels).
