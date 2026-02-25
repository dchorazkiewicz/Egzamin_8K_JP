#!/bin/bash
set -euo pipefail

export PYENV_ROOT="${PYENV_ROOT:-$HOME/.pyenv}"
export PATH="$PYENV_ROOT/shims:$PYENV_ROOT/bin:$PATH"

if ! command -v pyenv >/dev/null 2>&1; then
    echo "Błąd: pyenv nie jest dostępny w PATH (sprawdź instalację w $PYENV_ROOT)." >&2
    exit 1
fi

# Ustalenie wersji na podstawie pliku .python-version
VERSION=$(cat .python-version)

echo "Konfiguracja wersji Pythona $VERSION..."

# Sprawdzenie czy pyenv posiada tę wersję
if ! pyenv versions --bare | grep -Fxq "$VERSION"; then
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
if ! python -c 'import socket; socket.getaddrinfo("pypi.org", 443)' >/dev/null 2>&1; then
    echo "Błąd: brak dostępu do DNS/internetu (nie mogę pobrać paczek z PyPI)." >&2
    echo "Uruchom ponownie w środowisku z dostępem do sieci lub z ustawionym mirror: PIP_INDEX_URL." >&2
    exit 2
fi

pip install --upgrade pip
pip install -r requirements.txt

# Inicjalizacja MkDocs jeśli nie istnieje
if [ ! -f "mkdocs.yml" ]; then
    echo "Inicjalizacja nowej struktury MkDocs..."
    mkdocs new .
fi

echo "Środowisko zostało pomyślnie zresetowane."
