# Egzamin Ósmoklasisty — materiały, arkusze i opracowania

Repozytorium zawiera zestawy PDF egzaminu ósmoklasisty (język polski, matematyka, język angielski) oraz **autorskie, przewijane strony HTML**, na których można uczyć się z zadań i odpowiedzi.

**Strona:** https://dchorazkiewicz.github.io/Egzamin_8K_JP/

## Nad czym pracujemy?

PDF-y są dokumentami źródłowymi, a **strona HTML jest właściwym środowiskiem do nauki**: teksty i polecenia tam, gdzie można je zamieścić, warianty odpowiedzi, poprawne rozwiązania z klucza CKE, wyjaśnienia krok po kroku oraz pułapki. Nie chodzi o automatyczny eksport PDF → Markdown.

- **Polski 2026:** [opracowanie do przewijania](https://dchorazkiewicz.github.io/Egzamin_8K_JP/opracowania/polski-2026/).
- **Angielski 2026:** [pilotażowe opracowanie 14 zadań](https://dchorazkiewicz.github.io/Egzamin_8K_JP/opracowania/angielski-2026/) — odpowiedzi wersji X, komentarze oraz autorskie teksty ćwiczeniowe z przyciskami odsłuchu w przeglądarce.
- **Matematyka:** następne opracowania w takim samym formacie; dla wzorów konieczna jest wizualna kontrola zapisów i diagramów.

## Jak tworzymy opracowania?

1. Sprawdzamy arkusz, **wersję X/Y**, zasady oceniania i transkrypcję/nagranie (jeśli dotyczy).
2. Oglądamy PDF wizualnie, aby nie zgubić pogrubień, kursywy, podkreśleń, geometrii ani ilustracji.
3. Ręcznie opracowujemy zadania do semantycznego HTML. Dla materiałów wymagających odrębnych praw autorskich używamy krótkich cytatów albo jawnie oznaczonych adaptacji i linkujemy oryginał.
4. Każdą odpowiedź porównujemy z kluczem odpowiedniej wersji CKE, uwzględniając zasady oceniania zadań otwartych.
5. Dodajemy wyjaśnienia, różnice między dystraktorami, przykłady, typowe błędy.
6. Dla angielskiego dodajemy odsłuch przez **SpeechSynthesis**, używając głosu angielskiego z urządzenia ucznia. Dodano **wybór głosu i próbkę przed odsłuchem**, bo domyślne głosy mogą być robotyczne. Jakość głosu zależy od przeglądarki/systemu; sam Web Speech API nie gwarantuje głosu neuralnego. To **nie jest oryginalna ścieżka audio CKE**.
7. Weryfikujemy układ i linki na urządzeniach mobilnych i desktopie, aktualizujemy `main` oraz publikowaną gałąź `gh-pages`.

Szczegółowa procedura i reguły dla kolejnych agentów znajdują się w **[AGENTS.md](AGENTS.md)**. Ten dokument jest źródłem zasad redakcyjnych i kontroli jakości.

## Architektura

- `docs/pdf/` – pobrane arkusze, odpowiedzi, transkrypcje.
- `docs/opracowania/` – opracowania HTML w źródłach MkDocs.
- `docs/stylesheets/` – główne style, wspólna skala typografii oraz style dla angielskiego.
- `docs/javascripts/e8-tts.js` – przyciski odsłuchu w przeglądarce.
- `docs/javascripts/e8-catalog.js` – katalog arkuszy, filtry i przyciski do istniejących opracowań.
- `docs/sync_exams.py` – synchronizacja dostępnych PDF-ów.
- `docs/build_pdf_index.py` – przebudowa listy arkuszy.
- `mkdocs.yml` – konfiguracja MkDocs Material i nawigacja.

## Uruchomienie lokalne

```bash
python -m pip install -r requirements.txt
mkdocs serve
```

Publikacja `gh-pages`:

```bash
mkdocs gh-deploy --force
```

**Status:** angielski 2026 ma kompletną mapę 14 zadań z odpowiedziami X i pilotażowe, autorskie teksty do odsłuchu. Nie należy mylić ich z dosłownym odtworzeniem całego oryginalnego arkusza i nagrań CKE. Pełne weryfikowanie każdej adaptacji pozostaje osobnym etapem.
