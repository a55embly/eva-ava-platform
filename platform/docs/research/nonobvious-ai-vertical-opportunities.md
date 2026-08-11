# Nieoczywiste wertykalne produkty AI dla polskich MŚP

**Data:** 27 lipca 2026  
**Zakres:** produkty B2B niezależne od chatbotów i ogólnej „automatyzacji biura”

## Executive summary

Najciekawsze okazje nie wyglądają jak „AI dla branży X”. Wyglądają jak **bramka odpowiedzialności w jednym kosztownym momencie**: zanim wynik badania zostanie przeoczony, laboratorium rozpocznie pracę na złych danych, instalator zniknie wraz z dokumentacją, element budynku zostanie zakryty albo odbiorca odpadu zakwestionuje masę i potrąci „zanieczyszczenia”.

AI jest tu mechanizmem odczytującym zdjęcie, PDF, numer seryjny lub dokument. Produkt sprzedaje wynik: mniej remake'ów, sporów, niezakończonych spraw i utraconych gwarancji.

| Priorytet | Produkt | Ból | Nasycenie konkurencji* | MVP | Dostęp PL | Potencjał reklamy |
|---|---|---:|---:|---:|---:|---:|
| 1 | Vet Result Closed Loop | 5 | 3 | 4 | 4 | 4 |
| 2 | Dental Responsibility Gate | 5 | 4 | 4 | 4 | 5 |
| 3 | PV Rescue Passport | 4 | 4 | 4 | 4 | 5 |
| 4 | CoverProof | 5 | 4 | 5 | 5 | 5 |
| 5 | Waste Handoff Proof | 5 | 4 | 4 | 4 | 5 |

\* Dla nasycenia 5 oznacza tłok. Pozostałe oceny: 5 = najlepiej.

Raport oddziela obserwacje ze źródeł od inferencji produktowej. Nie twierdzi, że „nikt tego nie oferuje”; wskazuje dokładny fragment procesu, którego nie eksponują sprawdzone produkty.

---

## 1. Weterynaria — Vet Result Closed Loop

### Problem i sygnały praktyków

Laboratorium dostarcza wynik, ale klinika nadal musi dopilnować sekwencji: **wynik finalny → obejrzany przez właściwego lekarza → właściciel poinformowany → następny krok wykonany**. Przy kilku lekarzach, dniach wolnych, wynikach wstępnych i aneksach odpowiedzialność jest niejasna.

- Weterynarz opisuje telefony i SMS-y o wynikach w dni wolne, brak jasnego zastępstwa i recepcję zablokowaną oczekującymi klientami ([VeterinaryProfession](https://www.reddit.com/r/veterinaryprofession/comments/1i21008)).
- Inny wątek pyta wprost, czy za kontakt odpowiada lekarz zlecający, czy lekarz będący akurat na zmianie ([VeterinaryProfession](https://www.reddit.com/r/veterinaryprofession/comments/1ulwh5e/question_about_client_communication/)).
- W ezyVet wynik wstępny z badania wieloczęściowego potrafił przedwcześnie zakończyć request i fałszywie powiadomić lekarza o kompletności ([VetTech](https://www.reddit.com/r/VetTech/comments/zqeg0z)).

### Co już istnieje i gdzie jest luka

IDEXX VetConnect PLUS pokazuje wyniki pending/recent i powiadomienia, a IDEXX Neo tworzy zadania callback i potrafi ponownie otworzyć zadanie po aktualizacji wyniku ([VetConnect PLUS](https://www.idexx.com/en/veterinary/software-services/vetconnect-plus/), [IDEXX Neo](https://idexxneosupport.zendesk.com/hc/en-us/articles/217334487-Manage-follow-up-actions-with-the-task-list)). Polski Klinika XP importuje wyniki z laboratoriów i urządzeń ([Klinika XP](https://www.klinikaxp.pl/help_online/pl/Buforwynikowbadan.html)).

**Inferowana luka:** vendor-neutral warstwa nad kilkoma laboratoriami, PDF-ami i PIMS-em. Nie przechowuje tylko wyniku, lecz prowadzi audytowalny ledger odpowiedzialności aż do potwierdzonego kontaktu i następnego kroku. Szczególnie wartościowe są wyniki wstępne, finalne, addendum i sprawy osierocone po zmianie dyżuru.

### Produkt i AI

System odbiera pliki ze wspólnej skrzynki, rozpoznaje pacjenta, typ badania i status preliminary/final/addendum, a następnie kieruje sprawę według grafiku i protokołu kliniki. AI proponuje klasyfikację oraz pilność, lecz lekarz zatwierdza medyczną interpretację i treść krytycznego kontaktu. Dashboard pokazuje tylko wyjątki: brak właściciela, przekroczone SLA, wynik uzupełniony po zamknięciu albo kontakt bez potwierdzonego next step.

**MVP 14–21 dni:** wspólna skrzynka, parser 2–3 formatów PDF, ręczne reguły badań/statusów, kolejka wyników, przypisanie według grafiku, outcome kontaktu i eksport audytowy. Bez integracji zwrotnej do PIMS i bez autonomicznej porady medycznej.

**Płatnik i dostęp PL:** właściciel/manager kliniki z co najmniej trzema lekarzami lub sieć klinik. Dotarcie przez okręgowe izby lekarsko-weterynaryjne, laboratoria, resellerów PIMS i konferencje weterynaryjne.

**Ryzyka:** dane wrażliwe, odpowiedzialność medyczna, błędne rozpoznanie statusu, alert fatigue i zamknięcie luki przez dostawcę PIMS. Produkt musi być workflowem odpowiedzialności, nie systemem diagnozy.

**Reklama:** wynik wpada w piątek po dyżurze lekarza → sprawa nie znika w inboxie → system kieruje ją do zastępcy, wykrywa późniejsze addendum i zamyka dopiero po potwierdzonym kontakcie.

---

## 2. Protetyka — Dental Responsibility Gate

### Problem i sygnały praktyków

Laboratorium otrzymuje skan, zdjęcia odcienia i receptę różnymi kanałami. Dane bywają formalnie obecne, lecz za słabe do dobrego wyniku. Technik telefonuje do gabinetu albo podejmuje ryzyko; po remaku obie strony spierają się, kto powinien był zatrzymać pracę.

- Dyskusja o kolejnych, coraz gorszych skanach pokazuje spór o koszt remake'u. Praktycy wskazują, że jawne „kontynuuj mimo ostrzeżenia” powinno przenosić odpowiedzialność ([Dentistry](https://www.reddit.com/r/Dentistry/comments/1l821o7)).
- Pracownik laboratorium opisał pacjenta generującego przez wielokrotne remaki tysiące dolarów kosztu z powodu kształtu i odcienia ([LegalAdvice](https://www.reddit.com/r/legaladvice/comments/cnaxsk)).
- Laboratoria publikują bardzo konkretne wymagania dla fotografii odcienia, ustawienia wzornika i kompletu materiałów ([Barksdale Dental Lab](https://barksdaledentallab.com/case-list-guidelines/)).

### Co już istnieje i gdzie jest luka

TrazaLab ma cyfrową receptę, pliki, komunikację i walidację, a Arch automatycznie odczytuje odcień, numer zęba i materiał oraz prowadzi checklisty QC ([TrazaLab](https://trazalab.com/product.html), [Arch](https://www.archforlabs.com/)). Sam portal zleceń lub LMS nie jest luką.

**Inferowana luka:** preflight dowodowy przed akceptacją przypadku. System wskazuje dokładnie, które dane są słabe, pokazuje konsekwencję i zbiera wersjonowaną decyzję: „uzupełniam”, „odrzucam” albo „kontynuuję na własne ryzyko”. Może działać przed obecnym LMS-em.

### Produkt i AI

Vision ocenia techniczną jakość zdjęcia odcienia: obecność wzornika, przepalenia, perspektywę i komplet ujęć. Reguły kontrolują spójność numeru zęba, materiału, recepty i nazw plików. Technik zatwierdza kartę ryzyka, a lekarz jawnie akceptuje wyjątek.

**MVP 14–21 dni:** tylko pojedyncze korony; formularz, reguły kompletności, kontrola jakości fotografii, trzy rodzaje ostrzeżeń, akceptacja obu stron i PDF osi decyzji. Bez diagnozy klinicznej.

**Płatnik i dostęp PL:** laboratorium protetyczne płaci za mniej remake'ów i telefonów. [Katalog CEDE](https://www.cede.pl/en/exhibition/exhibitors-catalogue/) daje bezpośrednią listę dostawców, laboratoriów i partnerów.

**Ryzyka:** dane medyczne, odpowiedzialność zawodowa i możliwość użycia systemu do zrzucania winy. Produkt dokumentuje decyzję; nie rozstrzyga automatycznie odpowiedzialności.

**Reklama:** zdjęcie „wygląda dobrze” → system pokazuje brak wzornika i przepalone światło → gabinet poprawia jedno ujęcie → znika wizja pacjenta wracającego po trzeci remake.

---

## 3. Fotowoltaika — PV Rescue Passport

### Problem i sygnały praktyków

Po montażu dokumentacja, seriale i konta producentów pozostają u instalatora albo są rozproszone między fakturą, aplikacją falownika i pocztą. Gdy instalator znika lub dom zmienia właściciela, serwis zaczyna się od odtwarzania instalacji.

- Polski właściciel dostał instalację praktycznie bez kopii dokumentacji; faktura słabo identyfikowała elementy, co utrudniało wykazanie gwarancji ([Forum Fronius](https://www.forum-fronius.pl/forum/topic/dokumentacja-dla-klienta-po-zamontowaniu-instalacji/)).
- W FoxESS serial przypisany do starego konta blokował utworzenie instalacji i wymagał wsparcia ([Forum FoxESS](https://forum-foxess.pro/community/foxess-monitoring-falownikow/brak-poprawnie-zweryfikowanego-numeru-seryjnego-no-valid-verified-sn-blad-podczas-tworzenia-instalacji/)).
- Właściciele opisują brak numerów seryjnych i dokumentów potrzebnych do gwarancji ([Solar](https://www.reddit.com/r/solar/comments/chgfgs/lg_proof_of_warranty_help/)).

### Co już istnieje i gdzie jest luka

OpenSolar przechowuje datę montażu, seriale i dokumenty, a ConnectFSM prowadzi instalatora przez zdjęcia, testy i commissioning ([OpenSolar](https://support.opensolar.com/hc/en-us/articles/4406902813465-Include-Installation-Details-for-a-Project), [ConnectFSM](https://connectfsm.co.uk/solar-panel-installer-software/)).

**Inferowana luka:** te produkty są installer-centric. Brakuje prostej, wielomarkowej teczki **należącej do właściciela aktywa**, którą można zbudować również po fakcie i przekazać dowolnej firmie serwisowej. Nie chodzi o monitoring uzysku.

### Produkt i AI

Użytkownik wykonuje prowadzony film oraz zdjęcia falownika, rozdzielnicy i dostępnych oznaczeń. Vision/OCR odczytuje modele i seriale, wykrywa duplikaty oraz rozbieżności z fakturą. Wynikiem jest mapa urządzeń, lista braków, vendor-neutral eksport i szkic pakietu RMA dla człowieka-serwisanta.

**MVP 21–30 dni:** jedna marka falownika, trzy marki modułów, checklista zdjęć, OCR kodów, porównanie z fakturą PDF i dossier. Bez integracji z OSD i bez automatycznego zgłoszenia gwarancji.

**Płatnik i dostęp PL:** instalator chcący wyróżnić ofertę, niezależny serwis, inspektor przy odbiorze domu lub ubezpieczyciel. Publiczny katalog [ENEX](https://www.targikielce.pl/en/enex-2026/list-of-exhibitors?industries=5424%2C8958%2C15035) daje listę firm do rozmów.

**Ryzyka:** bezpieczeństwo przy zdjęciach, błędy OCR, brak API producentów i pomylenie kompletności dokumentów z oceną elektryczną. Produkt nie obiecuje ważności gwarancji.

**Reklama:** „Firma instalacyjna już nie istnieje” → właściciel skanuje urządzenia → powstaje mapa seriali i braków → nowy serwis dostaje gotową sprawę.

---

## 4. Budownictwo — CoverProof

### Problem i sygnały praktyków

Przewody, rury, mocowania i hydroizolacja znikają po tynku, wylewce lub płytkach. Zdjęcia istnieją w telefonach i WhatsAppie, ale po dwóch latach trudno wykazać, co znajdowało się pod konkretnym miejscem i czy etap był kompletny.

- Polski wątek pokazuje prozaiczny skutek braku dokumentacji: puszki elektryczne zatynkowane przed ich odnalezieniem; rada praktyków brzmi, by fotografować instalacje przed tynkami i wylewkami ([BudujemyDom](https://forum.budujemydom.pl/topic/6504-zapomnieli-o-gniazdkach/)).
- Wykonawcy opisują zdjęcia przed/po i fotografie ukrytych usterek jako dowód w sporach ([Construction](https://www.reddit.com/r/Construction/comments/1c68r94), [Construction](https://www.reddit.com/r/Construction/comments/1d73rog)).

### Co już istnieje i gdzie jest luka

OpenSpace mapuje zdjęcia 360° do planów i pozwala „zajrzeć” do wcześniejszego stanu, PlanRadar zbiera zdjęcia, głos, plany i raporty, a polski Build/Log prowadzi zadania i archiwum zdjęć ([OpenSpace](https://www.openspace.ai/resources/use-cases/documentation/), [PlanRadar](https://www.planradar.com/product/evidence-collection/), [Build/Log](https://buildlog.app/)).

**Inferowana luka:** nie kolejny dziennik budowy. Mała ekipa potrzebuje obowiązkowego checkpointu dla konkretnego etapu: właściwe kąty, identyfikacja pomieszczenia/ściany, komplet ujęć i podpis **zanim element zostanie zakryty**. System ma sprzedawać gotowy pakiet gwarancyjny bez BIM-u i kamer 360°.

### Produkt i AI

Telefon prowadzi wykonawcę po wymaganych ujęciach. Vision sprawdza ostrość, duplikaty, obecność markera lokalizacji i coverage, a OCR odczytuje oznaczenia materiałów. Człowiek z uprawnieniami zatwierdza jakość techniczną; AI tylko pilnuje kompletności dowodu.

**MVP 14–21 dni:** jedna branża, np. elektryka lub hydroizolacja; pięć szablonów odbioru, QR pokoju/ściany, guided capture, kontrola blur/coverage, podpisany PDF/ZIP. Bez BIM-u i bez oceny zgodności z normą.

**Płatnik i dostęp PL:** instalator, mały generalny wykonawca, inspektor lub producent systemu materiałowego. Dostęp przez hurtownie, grupy wykonawcze i [katalog BUDMA](https://budma.pl/en/visitors/important-information/list-of-exhibitors-at-the-budma-2026-fair/).

**Ryzyka:** fotografia nie dowodzi pełnej zgodności; możliwe ponowne użycie zdjęcia; PlanRadar może dodać podobną checklistę. Przewagą musi być szablon konkretnej technologii i wyjątkowo prosty proces.

**Reklama:** ściana zamyka się jak kurtyna → dwa lata później pojawia się awaria → system cofa czas i pokazuje dokładny przebieg instalacji, materiał, ujęcia i podpis.

---

## 5. Odpady i złom — Waste Handoff Proof

### Problem i sygnały praktyków

Przy przekazaniu odpadu różnią się masa szacowana na KPO, waga odbiorcy, faktura i potrącenie za zanieczyszczenia. Mały skup, broker lub wytwórca nie ma dobrego dowodu stanu ładunku w dokładnym momencie przejęcia.

- Polski praktyk opisuje 15 ton złomu, przyjęcie 14 ton i kolejne potrącenie 0,5 t „zanieczyszczeń”, pytając o rozjazd między KPO i fakturą ([Odpady-Help](https://www.odpady-help.pl/forum/threads/858/posts?page=89)).
- Inny wątek wskazuje, że rozbieżność między masą szacowaną a ważeniem jest częsta; workaround to wydruk, dopisek i zachowany e-mail ([Odpady-Help](https://odpady-help.pl/forum/threads/ewidencja-w-bdo-kontra-rzeczywistosc/posts?page=8)).
- BDO wyjaśnia, że w KEO wpisuje się rzeczywistą masę mimo błędu na zrealizowanej KPO, a błędną KPO należy zwrócić do korekty ([BDO: rzeczywista masa](https://bdo.mos.gov.pl/baza-wiedzy/55-w-jaki-sposob-nalezy-dokonac-prawidlowej-ewidencji-odpadow-gdy-na-kpo-o-statusie-zrealizowane-przejecie-widnieje-bledna-masa-odpadow/), [BDO: korekta](https://bdo.mos.gov.pl/baza-wiedzy/54-kiedy-istnieje-mozliwosc-zmiany-masy-odpadow-na-kpo/)).

### Co już istnieje i gdzie jest luka

BDO ma API, eBDO wykrywa duplikaty i błędy masy/kodu, Waste24 integruje KPO/KEO, a Odpadomat łączy wagę z BDO ([API BDO](https://bdo.mos.gov.pl/news/modul-integracyjny-api-bdo/), [eBDO](https://ebdo.pl/), [Waste24](https://waste24.net/integracja-z-baza-danych-odpadowych/), [Odpadomat](https://odpadomat.pl/oprogramowanie-dla-skupu-zlomu)). AMCS Vision AI dostarcza dowód wizualny z kamer pojazdu, ale wymaga szerszego wdrożenia sprzętowego ([AMCS](https://www.amcsgroup.com/solutions/amcs-vision-ai/)).

**Inferowana luka:** odpowiednik „evidence at handoff” bez hardware'u dla MŚP. Nie zastępuje BDO i nie próbuje wyliczać masy ze zdjęcia. Łączy prowadzony film przed/po rozładunku, kwit wagowy, KPO, fakturę i listę rozjazdów w jedną sprawę.

### Produkt i AI

Vision oznacza potencjalne zanieczyszczenia do potwierdzenia przez człowieka, OCR czyta kwit wagowy i fakturę, a system porównuje dokumenty i tworzy chronologię. Nie klasyfikuje prawnie odpadu i nie estymuje wiarygodnie masy z obrazu.

**MVP 21 dni:** jeden strumień, np. złom metali; guided capture, ręcznie zatwierdzane etykiety vision, OCR wagi, import CSV/API BDO, dashboard rozjazdów i podpisany PDF sprawy.

**Płatnik i dostęp PL:** skup, recykler, broker lub duży wytwórca. Dotarcie przez konsultantów BDO, dostawców wag, fora odpadowe oraz [POLECO](https://poleco.pl/en/exhibitors/offer/why-is-it-worthwhile/).

**Ryzyka:** obraz nie udowadnia masy ani procentu zanieczyszczeń; druga strona może nie uznać materiału; brudne środowisko i konkurencja ERP/BDO. Najpierw trzeba potwierdzić wartość faktycznych polskich sporów.

**Reklama:** 15 ton wyrusza → na kwicie pojawia się 14 ton i potrącenie → system zestawia film przekazania, KPO, wagę i fakturę → zamiast tygodnia maili powstaje jeden pakiet sporu.

---

## Mocne alternatywy tuż poza TOP 5

### Supplier Allergen Change Gate

Restauracja może mieć poprawną macierz alergenów, która staje się nieaktualna po zmianie SKU lub dostawcy. Praktyczny polski przykład to pieczywo od nowego dostawcy zawierające sezam; ta wiedza nie może pozostać tylko w głowie szefa kuchni ([Restauracja od Kuchni](https://restauracjaodkuchni.pl/artykuly/jak-zarzadzac-alergenami-w-kuchni-procedury)). Nutritics, FoodDocs i Menutech zarządzają recepturami i alergenami, ale luka może leżeć w samym **zdarzeniu zmiany dostawy**: faktura/nowy SKU → zdjęcie etykiety → różnica składu → lista dotkniętych dań → akceptacja przed użyciem ([Nutritics](https://en-gb.nutritics.com/en/support-center/allergen-management/), [FoodDocs](https://www.fooddocs.com/food-safety-solutions), [Menutech](https://menutech.com/en)).

### FirstPack Gate

Esko Comply i ArtworkIQ sprawdzają projekt etykiety przed drukiem, lecz mały producent może nadal założyć starą rolkę na linię ([Esko](https://www.esko.com/en/products/comply), [ArtworkIQ](https://artworkiq.co.uk/)). Tani tablet porównujący **pierwszą fizyczną paczkę po zmianie SKU/rolki** z aktualną recepturą i masterem ma jasny efekt reklamowy oraz 21-dniowy MVP. Ryzykiem jest odpowiedzialność food-safety, dlatego QA musi pozostawać decydentem.

---

## Kategorie odrzucone po sprawdzeniu konkurencji

### Automatyczna dyspozycja po przekroczeniu temperatury

Problem jest realny i regulowany, lecz Controlant oraz Sensitech już oceniają ekspozycję względem profilu stabilności i proponują release/reject ([Controlant](https://www.controlant.com/product-stability-automation), [Sensitech](https://www.sensitech.com/en/solutions/lynx-factor/)). Trudny pierwszy rynek bez własnych danych i integracji.

### AI do diagnozy auta po dźwięku

DriveVerse, CarEKG i inne aplikacje już łączą audio, opis i dane pojazdu ([DriveVerse](https://thedriveverse.com/), [CarEKG](https://www.carekg.app/)). Efektowne demo, lecz słaby moat bez unikalnego zbioru danych warsztatowych.

### Automatyczna dokumentacja osuszania szkód

Reclaim obsługuje zdjęcia, voice-to-text, mapowanie wilgoci i raporty ubezpieczeniowe, a DryTrack Pro tworzy logi, wykresy i pakiety dla likwidatora ([Reclaim](https://www.heyreclaim.com/), [DryTrack Pro](https://drytrackpro.com/)). Kategoria jest znacznie bardziej kompletna, niż sugeruje problem.

### Inspekcja ubrań w pralni

KansoFlow i Launderly już rozpoznają stan, plamy i uszkodzenia, tworząc dowód przed/po ([KansoFlow](https://www.kansoflow.com/), [Launderly](https://launderly.app/)). Brak wyraźnej przewagi lokalnej.

### Liczenie bielizny hotelowej ze zdjęcia

Problem ręcznego liczenia istnieje, ale RFID jest dojrzałe, a vision przegrywa przy okluzji, mokrych i mieszanych stosach. Polski dostawca deklaruje tagowanie każdej sztuki i koszt taga około 1,8–2 zł ([RFID Polska](https://www.rfidpolska.pl/kontrola-prania-rfid/)). To raczej integracja lub usługa wdrożeniowa niż atrakcyjny nowy produkt AI.

### Ogólny protokół przyjęcia auta ze zdjęciami

Warsztatnik i MotoWarsztat mają już zdjęcia, podpisy, PDF-y, kosztorysy oraz protokoły przyjęcia/wydania ([Warsztatnik](https://warsztatnik.pl/), [MotoWarsztat](https://motowarsztat.pl/)); UVeye automatyzuje skan sprzętowo w segmencie dealerskim ([UVeye](https://uveye.com/dealerships/)). Ewentualna nisza to wyłącznie kontrola kompletności tych samych ujęć before/after i dowód zgody na rozszerzenie naprawy.

## Rekomendowany następny krok

Do pierwszych rozmów wybrałbym **Vet Result Closed Loop** oraz **PV Rescue Passport**: pierwszy ma najsilniejszą lukę procesową, drugi najłatwiej pokazać w reklamie i sprzedać najpierw jako usługę odtworzenia dokumentacji.

Nie pytać firm, czy „pomysł im się podoba”. Poprosić o ostatnie 20–30 prawdziwych przypadków i sprawdzić:

1. co istniało przed błędem;
2. kto mógł zatrzymać proces;
3. ile czasu i pieniędzy kosztowało domknięcie;
4. dlaczego obecne narzędzie tego nie zrobiło;
5. czy firma zapłaci za ręczny mikro-pilot bez pełnej aplikacji.

Najlepsza hipoteza to ta, przy której firma pokaże dokumenty, wskaże właściciela budżetu i zgodzi się zmierzyć wynik.
