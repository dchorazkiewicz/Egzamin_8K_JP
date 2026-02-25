

# Instrukcja konfiguracji środowiska dla Agenta (wersja pyenv)

Twoim zadaniem jest zainicjalizowanie środowiska programistycznego dla projektu **Egzamin_8K_JP**. Musisz skonfigurować konkretną wersję Pythona, utworzyć środowisko wirtualne i przygotować bazową strukturę MkDocs.

### 1. Plik .python-version

Utwórz w głównym katalogu plik o nazwie `.python-version` z następującą zawartością:

```text
3.12.12

```

### 2. Plik requirements.txt

Przygotuj plik z zależnościami, które umożliwią generowanie dokumentacji z nowoczesnym wyglądem i obsługą dodatkowych rozszerzeń:

```text
mkdocs>=1.5.0
mkdocs-material>=9.0.0
mkdocs-minify-plugin>=0.7.0
mkdocs-git-revision-date-localized-plugin>=1.2.0
pymdown-extensions>=10.0

```

### 3. Skrypt instalacyjny setup.sh

Skrypt ma za zadanie zresetować środowisko i postawić je na nowo, korzystając z `pyenv` do wskazania interpretera oraz `venv` do izolacji bibliotek.

```bash
#!/bin/bash

# Ustalenie wersji na podstawie pliku .python-version
VERSION=$(cat .python-version)

echo "Konfiguracja wersji Pythona $VERSION..."

# Sprawdzenie czy pyenv posiada tę wersję
if ! pyenv versions | grep -q "$VERSION"; then
    echo "Instalacja brakującej wersji Pythona..."
    pyenv install "$VERSION"
fi

pyenv local "$VERSION"

# Resetowanie venv
echo "Usuwanie starego venv i tworzenie nowego..."
rm -rf venv
python -m venv venv

# Aktywacja i instalacja
source venv/bin/activate
echo "Aktualizacja pip i instalacja pakietów..."
pip install --upgrade pip
pip install -r requirements.txt

# Inicjalizacja MkDocs jeśli nie istnieje
if [ ! -f "mkdocs.yml" ]; then
    echo "Inicjalizacja nowej struktury MkDocs..."
    mkdocs new .
fi

echo "Środowisko zostało pomyślnie zresetowane."

```

### 4. Konfiguracja mkdocs.yml

Upewnij się, że plik `mkdocs.yml` zawiera motyw **Material** oraz polską lokalizację:

```yaml
site_name: Egzamin Ósmoklasisty - Język Polski
site_description: Repozytorium materiałów i opracowań egzaminacyjnych.

theme:
  name: material
  language: pl
  palette:
    - scheme: default
      primary: red
      accent: red
      toggle:
        icon: material/brightness-7
        name: Tryb ciemny
    - scheme: slate
      primary: red
      accent: red
      toggle:
        icon: material/brightness-4
        name: Tryb jasny
  features:
    - navigation.tabs
    - navigation.top
    - search.suggest
    - search.highlight

markdown_extensions:
  - admonition
  - pymdownx.superfences
  - pymdownx.details
  - pymdownx.magiclink
  - footnotes

plugins:
  - search
  - git-revision-date-localized:
      type: date

```

### Zadania do wykonania przez Agenta:

1. Zapisz pliki `.python-version`, `requirements.txt` oraz `mkdocs.yml`.
2. Zapisz skrypt `setup.sh` i nadaj mu uprawnienia: `chmod +x setup.sh`.
3. Uruchom `./setup.sh`.
4. Po zakończeniu instalacji, uruchom serwer testowy poleceniem `mkdocs serve`, aby upewnić się, że strona renderuje się poprawnie.
