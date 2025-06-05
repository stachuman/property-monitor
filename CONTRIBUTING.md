# 🤝 Przewodnik dla Współtwórców

Dziękujemy za zainteresowanie wkładem w rozwój Property Monitor! Ten dokument zawiera wytyczne dla osób chcących przyczynić się do rozwoju projektu.

## 📋 Sposób Współpracy

### Zgłaszanie Problemów

Przed zgłoszeniem nowego problemu:

1. **Sprawdź istniejące Issues** - możliwe, że problem został już zgłoszony
2. **Sprawdź dokumentację** - upewnij się, że nie jest to kwestia konfiguracji
3. **Uruchom diagnostykę** - użyj `python cli_tools.py status`

#### Szablon Zgłoszenia Błędu

```markdown
**Opis problemu**
Krótki opis tego, co się wydarzyło.

**Kroki do odtworzenia**
1. Przejdź do...
2. Kliknij na...
3. Przewiń do...
4. Zobacz błąd

**Oczekiwane zachowanie**
Opis tego, co powinno się wydarzyć.

**Rzeczywiste zachowanie**
Opis tego, co rzeczywiście się wydarzyło.

**Środowisko**
- OS: [np. Ubuntu 20.04]
- Python: [np. 3.9.7]
- Wersja Property Monitor: [np. 1.0.0]

**Dodatkowe informacje**
Wszelkie dodatkowe informacje, zrzuty ekranu, logi.
```

### Propozycje Nowych Funkcji

Dla nowych funkcji:

1. **Sprawdź roadmapę** - może funkcja jest już planowana
2. **Otwórz Discussion** - przedyskutuj pomysł przed implementacją
3. **Utwórz Issue** z etykietą `enhancement`

#### Szablon Propozycji Funkcji

```markdown
**Czy ta funkcja rozwiązuje problem?**
Jasny opis problemu. np. "Frustruje mnie, że..."

**Opisz rozwiązanie**
Jasny opis tego, czego oczekujesz.

**Opisz alternatywy**
Opis alternatywnych rozwiązań, które rozważałeś.

**Dodatkowy kontekst**
Dodaj wszelkie inne informacje o propozycji funkcji.
```

## 🔧 Rozwój

### Konfiguracja Środowiska Deweloperskiego

```bash
# Sklonuj repozytorium
git clone https://github.com/stachuman/property-monitor.git
cd property-monitor

# Utwórz branch dla swojej funkcji
git checkout -b feature/nowa-funkcja

# Utwórz środowisko wirtualne
python -m venv venv
source venv/bin/activate  # Linux/macOS
# lub
venv\Scripts\activate     # Windows

# Zainstaluj zależności deweloperskie
pip install -r requirements.txt
pip install -r requirements-dev.txt  # Jeśli istnieje

# Skonfiguruj pre-commit hooks
pre-commit install

# Uruchom testy
python -m pytest
```

### Standardy Kodowania

#### Styl Kodu

- **Python**: Używamy [PEP 8](https://pep8.org/) z kilkoma modyfikacjami
- **Maksymalna długość linii**: 100 znaków
- **Formatowanie**: Używamy `black` do automatycznego formatowania
- **Import**: Sortujemy za pomocą `isort`
- **Linting**: Używamy `flake8` do sprawdzania jakości kodu

```bash
# Formatowanie kodu
black .
isort .

# Sprawdzenie jakości
flake8 .
mypy .
```

#### Konwencje Nazewnictwa

- **Pliki**: `snake_case.py`
- **Klasy**: `PascalCase`
- **Funkcje/Metody**: `snake_case`
- **Stałe**: `UPPER_CASE`
- **Zmienne**: `snake_case`

#### Dokumentacja

- **Docstrings**: Używamy formatu Google
- **Komentarze**: W języku polskim dla logiki biznesowej, angielskim dla kodu technicznego
- **Type Hints**: Wymagane dla wszystkich nowych funkcji

```python
def process_property_data(property_data: Dict[str, Any]) -> Property:
    """Przetwarza surowe dane nieruchomości na obiekt Property.
    
    Args:
        property_data: Słownik z surowymi danymi z API
        
    Returns:
        Obiekt Property z przetworzonymi danymi
        
    Raises:
        ValueError: Gdy dane są nieprawidłowe
    """
    # Implementacja...
```

### Struktura Commitów

Używamy [Conventional Commits](https://www.conventionalcommits.org/):

```
<typ>[opcjonalny zasięg]: <opis>

[opcjonalne ciało]

[opcjonalne stopki]
```

#### Typy Commitów

- `feat`: Nowa funkcja
- `fix`: Naprawa błędu
- `docs`: Zmiany w dokumentacji
- `style`: Formatowanie, brak zmian w logice
- `refactor`: Refaktoryzacja kodu
- `test`: Dodanie lub modyfikacja testów
- `chore`: Aktualizacja narzędzi, konfiguracji

#### Przykłady

```bash
feat(geocoding): dodaj obsługę fuzzy search dla nazw miast

fix(scraping): napraw błąd timeout dla długich requestów

docs(readme): aktualizuj instrukcje instalacji

style: zastosuj formatowanie black

refactor(database): uprość logikę cache'owania

test(api): dodaj testy dla endpoint'ów watched

chore(deps): aktualizuj Flask do 2.3.3
```

### Proces Pull Request

1. **Fork repozytorium** na swoje konto
2. **Utwórz branch** z opisową nazwą
3. **Implementuj zmiany** zgodnie ze standardami
4. **Dodaj testy** dla nowej funkcjonalności
5. **Aktualizuj dokumentację** jeśli to konieczne
6. **Uruchom wszystkie testy** i upewnij się, że przechodzą
7. **Wyślij Pull Request** z opisem zmian

#### Szablon Pull Request

```markdown
## Opis

Krótki opis zmian wprowadzonych w tym PR.

## Typ zmiany

- [ ] Naprawa błędu (non-breaking change)
- [ ] Nowa funkcja (non-breaking change)
- [ ] Breaking change (zmiana która może zepsuć istniejącą funkcjonalność)
- [ ] Aktualizacja dokumentacji

## Jak zostało przetestowane?

Opisz testy które przeprowadziłeś.

## Checklist:

- [ ] Mój kod jest zgodny ze stylem tego projektu
- [ ] Przeprowadziłem self-review swojego kodu
- [ ] Skomentowałem kod w trudnych do zrozumienia obszarach
- [ ] Zaktualizowałem dokumentację
- [ ] Moje zmiany nie generują nowych ostrzeżeń
- [ ] Dodałem testy które dowodzą, że moja naprawa działa lub funkcja działa
- [ ] Nowe i istniejące testy jednostkowe przechodzą lokalnie
```

### Testowanie

#### Typy Testów

1. **Testy jednostkowe**: Testowanie pojedynczych funkcji/metod
2. **Testy integracyjne**: Testowanie współpracy komponentów
3. **Testy funkcjonalne**: Testowanie kompletnych scenariuszy
4. **Testy wydajnościowe**: Testowanie pod obciążeniem

#### Uruchamianie Testów

```bash
# Wszystkie testy
python -m pytest

# Testy z pokryciem kodu
python -m pytest --cov=. --cov-report=html

# Testy konkretnego modułu
python -m pytest tests/test_database.py

# Testy z verbose output
python -m pytest -v

# Testy wydajnościowe
python -m pytest tests/performance/
```

#### Pisanie Testów

```python
import pytest
from unittest.mock import Mock, patch
from database import DatabaseManager

class TestDatabaseManager:
    """Testy dla DatabaseManager."""
    
    def setup_method(self):
        """Przygotowanie przed każdym testem."""
        self.db = DatabaseManager(":memory:")
    
    def test_save_properties_success(self):
        """Test pomyślnego zapisania nieruchomości."""
        # Given
        properties = [{"id": 1, "title": "Test Property"}]
        
        # When
        new_count, updated_count = self.db.save_properties(properties)
        
        # Then
        assert new_count == 1
        assert updated_count == 0
    
    @patch('database.requests.get')
    def test_api_call_failure(self, mock_get):
        """Test obsługi błędu API."""
        # Given
        mock_get.side_effect = ConnectionError("API niedostępne")
        
        # When/Then
        with pytest.raises(ConnectionError):
            self.db.fetch_external_data()
```

## 🚀 Wydania

### Versioning

Używamy [Semantic Versioning](https://semver.org/):

- **MAJOR**: Zmiany breaking (API compatibility)
- **MINOR**: Nowe funkcje (backwards compatible)
- **PATCH**: Naprawy błędów (backwards compatible)

### Proces Wydania

1. **Aktualizacja CHANGELOG.md**
2. **Aktualizacja wersji** w `setup.py` / `pyproject.toml`
3. **Utworzenie tagu** w Git
4. **Utworzenie GitHub Release**
5. **Publikacja w PyPI** (jeśli dotyczy)

## 📚 Dodatkowe Zasoby

### Przydatne Linki

- [Python Style Guide](https://pep8.org/)
- [Flask Documentation](https://flask.palletsprojects.com/)
- [SQLite Documentation](https://sqlite.org/docs.html)
- [Leaflet Documentation](https://leafletjs.com/reference.html)

### Narzędzia Deweloperskie

- **IDE**: Zalecamy VS Code z Python extension
- **Linting**: flake8, mypy
- **Formatting**: black, isort
- **Testing**: pytest
- **Documentation**: Sphinx (dla przyszłej dokumentacji API)

### Społeczność

- **GitHub Discussions**: Pytania i dyskusje
- **Issues**: Zgłaszanie błędów i propozycji
- **Pull Requests**: Współpraca nad kodem

## ❓ Pytania?

Jeśli masz pytania dotyczące współpracy:

1. Sprawdź [FAQ w Wiki](https://github.co/stachuman/property-monitor/wiki)
2. Przeszukaj [GitHub Discussions](https://github.com/stachuman/property-monitor/discussions)
3. Utwórz nowe Discussion jeśli nie znajdziesz odpowiedzi

---

Dziękujemy za wkład w rozwój Property Monitor! 🏠💙
