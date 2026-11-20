# AGENTS.md — Egzamin_8K_JP

## Cel projektu

Budujemy edukacyjną bibliotekę egzaminu ósmoklasisty z **autorskimi, statycznymi stronami HTML**, na których uczeń może przeczytać opracowanie całego arkusza, zadanie po zadaniu: materiał źródłowy (gdy można go legalnie zacytować), polecenie, wszystkie warianty odpowiedzi, poprawna odpowiedź, wyjaśnienie, typowe błędy, zadania otwarte i zasady punktacji. **PDF jest źródłem do sprawdzenia, a nie podstawowym interfejsem do nauki.** Nie wolno ograniczyć się do iframe PDF, listy kluczy ani automatycznego zrzutu PDF → Markdown.

Dla angielskiego szczególnie istotny jest **odsłuch dowolnego angielskiego akapitu** w samej przeglądarce (Web Speech API). Przeglądarka wypowiada tekst w języku angielskim po świadomym kliknięciu użytkownika. Synteza mowy **nie jest oryginalnym nagraniem egzaminacyjnym CKE**.

## Repozytorium i istniejące komponenty

- `docs/pdf/<przedmiot>/<rok>/*.pdf` — pobrane arkusze, odpowiedzi i transkrypcje; PDF-y pozostają oryginalnym źródłem.
- `docs/pdf/manifest.json` — pochodzenie pobranych plików.
- `docs/pdfs.md` — indeks arkuszy; generowany przez `docs/build_pdf_index.py`.
- `docs/opracowania/polski-2026.md` — pełna strona HTML z polskiego 2026; traktować ją jako wzorzec układu, **nie jako automatycznie zatwierdzony merytorycznie**.
- `docs/opracowania/angielski-2026.md` — angielski 2026: opracowanie pokazowe, wyraźnie oznaczone etapem weryfikacji.
- `docs/stylesheets/e8-longread.css` — styl długiej, przewijanej strony.
- `docs/stylesheets/e8-type-scale.css` — wspólna, umiarkowana skala fontów.
- `docs/stylesheets/e8-english.css` — dodatkowe elementy ćwiczeń językowych.
- `docs/javascripts/e8-tts.js` — odsłuch angielskich tekstów za pomocą lokalnych głosów przeglądarki.
- `docs/javascripts/e8-catalog.js` — kafelki arkuszy i przyciski do **istniejących** opracowań.
- `mkdocs.yml` — kolejność stylów, skryptów i nawigacja.
- `gh-pages` — publikowany statyczny HTML. `main` zawiera źródła. W tym repo mogą działać także akcje przebudowujące `gh-pages`; pilnować synchronizacji.

## Proces tworzenia nowego opracowania — obowiązkowa kolejność

1. **Identyfikuj arkusz.** Zanotuj przedmiot, rok, sesję, dokładny kod CKE, **wersję X/Y**, liczbę zadań, źródłowy PDF, PDF zasad oceniania, ewentualną transkrypcję i nagrania. Wersje X i Y nie mają automatycznie tego samego układu odpowiedzi.
2. **Czytaj wizualnie.** Obejrzyj wszystkie strony PDF, nie tylko wydobyty tekst. Sprawdź boldy, kursywę, podkreślenia, zasięg pierwiastków, diagramy, zdjęcia, tabele, oznaczenia odpowiedzi i opisy nagrań. Notuj numer strony przy każdym zadaniu. Odczyt tekstowy jest pomocniczy.
3. **Opracuj ręcznie HTML.** Przygotuj spójny układ: nagłówek egzaminu, spis zadań, materiał źródłowy, ponumerowane zadania, możliwe odpowiedzi, od razu widoczny klucz, wyjaśnienie krok po kroku, pułapki i ewentualne modelowe wypowiedzi. **Jedna przewijana strona**, bez osobnego przełączania zadań i bez PDF jako treści głównej. Zachowuj znaczące <strong>pogrubienia</strong>, <em>kursywę</em> i <u>podkreślenia</u> w semantycznym HTML.
4. **Prawo do reprodukcji.** Nie kopiuj automatycznie długich tekstów lub cudzych zdjęć na stronę, jeżeli nie ma odpowiednich praw/licencji. Dla chronionych fragmentów stosuj krótkie uzasadnione cytaty lub wyraźnie oznaczone autorskie adaptacje; pełen oryginał pozostaje w odnośniku do PDF. Nie nazywaj adaptacji „tekstem oryginalnym”. Materiały własne należy odróżniać od tekstu CKE.
5. **Dopasuj do klucza CKE.** Każdemu podzadaniu przyporządkuj oficjalną odpowiedź **tej konkretnej wersji** i prawidłową punktację. Sprawdź wszystkie podpunkty, odpowiedzi alternatywne i warunki akceptacji. Wypracowania oceniać rubryką; przykład autorski nie jest automatycznie pracą na maksimum punktów. Nie wymyślaj brakujących odpowiedzi.
6. **Dydaktyka.** Odpowiedź wyjaśnia *dlaczego*, nie tylko *co*. Dodaj argument za wyborem i przeciw mylącym dystraktorom, podaj odpowiednie reguły gramatyczne, przykłady i informację o typowych błędach. Materiały do słuchania powinny odróżniać tekst autorski od faktycznej transkrypcji nagrania CKE.
7. **Angielski — TTS.** Angielskie teksty i przykłady przeznaczone do odsłuchu umieszczaj w elementach `lang="en"` lub `lang="en-GB"` z klasą `e8-speakable`. Przy każdym tekście zapewnij przycisk `data-e8-speak` i opcjonalnie `data-e8-stop`. Skrypt używa `speechSynthesis` po kliknięciu. **Nie wybieraj pierwszego głosu en-GB bez porównania**: pobierz dostępne głosy asynchronicznie (`voiceschanged`), preferuj nazwane Natural/Neural/Enhanced, umożliwiaj użytkownikowi ręczny wybór, przycisk krótkiej próbki głosu i przechowywanie wyłącznie lokalnej preferencji. Wymagane: Stop, normalne tempo 1×, dostępność przez klawiaturę, brak autoplay, brak kluczy i zewnętrznego API. Jeżeli system nie oferuje jakościowego głosu, poinformuj o ograniczeniu. Web Speech API **nie gwarantuje głosu neuralnego**, a jakość zależy od urządzenia. Wariant przyszłościowy: dedykowana usługa TTS z legalną konfiguracją kluczy po stronie serwera, nie w publicznym JavaScript.
8. **QA merytoryczne + UI.** Porównaj **każde** zadanie z arkuszem i kluczem, w tym odmienne warianty X/Y. Przejdź stronę na desktopie i mobilnie, skontroluj rozmiary fontów, przecinki, tłumaczenia, wszystkie linki, brak przewijania w poziomie, obsługę klawiatury, focus, alt ilustracji i odczyt TTS; sprawdź Play/Stop po wielu kliknięciach. W przeglądarce bez TTS pokaż sensowny komunikat.
9. **Publikuj dopiero po kontroli.** Edytuj plik w `main`, przebuduj MkDocs (`mkdocs build` lub workflow), sprawdź wynik na `gh-pages`, a dopiero wtedy dodaj przycisk `Czytaj opracowanie` w katalogu. Nie pokazuj aktywnego przycisku do strony, której nie ma. Jeżeli aktualizacja `gh-pages` wykonana ręcznie, pamiętaj o ponownej synchronizacji przy następnej przebudowie.
10. **Etykietuj status.** `pilot / w trakcie kontroli / zweryfikowane / kompletne` są odrębnymi stanami. Nie opisuj przykładowego fragmentu jako „pełnego opracowania 14 zadań”; postęp i ograniczenia muszą być widoczne uczniowi.

## Wspólne zasady wizualne

- Nie powiększaj dramatycznie różnicy między nagłówkami i tekstem. Wspólna skala: **16px tekst**, 13–14px opis, 17–19px mniejsze nagłówki, 21–22px sekcje, 26–32px główne tytuły.
- Przewijana, jasna strona z wyraźną hierarchią i dużą ilością przestrzeni, ale bez 60px nagłówków i 9px etykiet.
- Przycisk opracowania w katalogu ma jasny pomarańczowy kolor i łagodną poświatę, nie pulsuje i nie rozprasza.
- W angielskim TTS ma być łatwy do znalezienia, z czytelnym opisem „Odsłuchaj po angielsku”. Głosy i wymowa zależą od urządzenia.

## Kryterium ukończenia nowej strony

Sprawdzone źródła → strona HTML z **rzeczywiście opracowanymi** zadaniami → kontrola odpowiedzi i liter → poprawnie działający odsłuch przy angielskich treściach → poprawne linki w katalogu → przetestowana publikacja. Jeżeli któryś etap jest niewykonany, opisz go jako brak i **nie deklaruj kompletności**.

## Przykładowe źródła angielskiego 2026

- Arkusz (13 maja 2026): `docs/pdf/jezyk-angielski/2026/jezyk-angielski-2026-egzamin-osmoklasisty.pdf`.
- Zasady oceniania: `docs/pdf/jezyk-angielski/2026/jezyk-angielski-2026-egzamin-osmoklasisty-odpowiedzi.pdf`.
- Transkrypcja nagrań: `docs/pdf/jezyk-angielski/2026/jezyk-angielski-2026-egzamin-osmoklasisty-transkrypcja.pdf`.
- Arkusz standardowy CKE oznaczony `OJAP-100-2605`, zadania 1–14. Odpowiedzi zamknięte dla wersji X należy weryfikować w kolumnie X; nie kopiuj do niej kolumny Y.

## Plan rozszerzenia

- **Polski:** rozbudowa opracowań HTML o kolejne sesje i lata, kontrola kryteriów oceniania wypowiedzi pisemnych i wiernego formatowania tekstu.
- **Matematyka 2026:** kompletne opracowanie 20 zadań w `docs/opracowania/matematyka-2026.md`, 74 kolorowo oznaczone etapy i wskazówki punktowania zadań 15–20. Matematyka w kolejnych latach powinna wykorzystywać ten układ: dane, sposób, kolejne równania, kontrola, ewentualne alternatywne rozwiązania; bez wyświetlania podglądu PDF jako podstawowego interfejsu.
- **Angielski:** opracowania z czytaniem, słuchaniem, funkcjami językowymi i pisaniem. Oddzielaj nagranie CKE od autorskiego TTS; oferuj odsłuch poszczególnych akapitów, zatrzymanie i wolniejsze tempo. Wskazuj poziom weryfikacji każdego zestawu.

## Matematyka — rygor zapisu i sposobu rozwiązania

- Opracowania matematyczne **muszą** stosować prawdziwy LaTeX renderowany przez MathJax; nie stosować tekstu ASCII do dzielenia, pierwiastków, indeksów, wykładników, potęg i ułamków.
- Każde zadanie ma strukturę: dane w LaTeX → metoda → kolejne równania lub przekształcenia → wynik → kontrola; dla zadań otwartych także punktowanie. Nie wolno zastępować pełnych rachunków samą literą odpowiedzi ani skokiem od równania do wyniku.
- Wyrównywać rachunki przez `\\begin{aligned}...\\end{aligned}`; używać `\\frac{a}{b}`, `\\sqrt{...}`, `\\mathrm{cm}^2`, `\\boxed{...}`. Pilnować, że kreska pierwiastka obejmuje dokładnie właściwe wyrażenie.
- Wzory są renderowane przez `docs/javascripts/e8-mathjax.js`, a styluje je `docs/stylesheets/e8-math.css`. Skrypt próbuje jsDelivr, a w razie braku dostępności korzysta z unpkg. Nie usuwać informacji o błędach ładowania.
- Matematyka 2026: `docs/opracowania/matematyka-2026.md` zawiera 74 bloki matematyczne LaTeX w 20 zadaniach, 20 bloków danych i 20 zapisanych matematycznie odpowiedzi. Każdą nową sesję sprawdzać wizualnie z arkuszem danej wersji X/Y.
- **QA:** sprawdzić wyrenderowane wzory w przeglądarce desktop i mobile, a nie tylko obecność ukośników w pliku źródłowym. Równania mają być widoczne także przy zawijaniu wąskiego ekranu. Kontrola syntaktyczna LaTeX nie zastępuje kontroli matematycznej.
