# 🏠 Monitor Licytacji Nieruchomości


![Alt text](property-monitor/Capture_01.PNG "Monitor aukcji")

System monitorowania aukcji komorniczych nieruchomości w Polsce z interaktywną mapą i zaawansowanymi funkcjami zarządzania.

## 📋 Opis Projektu

Monitor Licytacji Nieruchomości to zaawansowany system do automatycznego pozyskiwania, przetwarzania i wizualizacji danych o aukcjach komorniczych nieruchomości w Polsce. System pobiera dane z portalu elicytacje.komornik.pl, geokoduje lokalizacje nieruchomości i prezentuje je na interaktywnej mapie.

### ✨ Główne Funkcje

- **🗺️ Interaktywna Mapa**: Wyświetlanie wszystkich nieruchomości na mapie Polski z dokładnymi współrzędnymi
- **🔍 Zaawansowane Filtry**: Filtrowanie po mieście, cenie, kategorii, statusie i dacie
- **⭐ Lista Obserwowanych**: Możliwość dodawania nieruchomości do listy obserwowanych z notatkami
- **🔄 Automatyczne Aktualizacje**: Regularne pobieranie nowych danych z systemu komorniczego
- **📍 Geokodowanie**: Automatyczne określanie współrzędnych geograficznych na podstawie nazw miast
- **⚙️ Panel Administracyjny**: Pełne zarządzanie systemem, konfiguracją i monitorowaniem
- **📱 Responsywny Design**: Optymalizacja dla urządzeń mobilnych i desktopowych
- **🔧 Narzędzia CLI**: Zarządzanie systemem z linii poleceń

### 🎯 Zastosowania

- **Inwestorzy**: Monitorowanie atrakcyjnych nieruchomości na aukcjach
- **Deweloperzy**: Poszukiwanie działek pod inwestycje
- **Osoby Prywatne**: Znajdowanie nieruchomości w przystępnych cenach
- **Analitycy Rynku**: Badanie trendów cenowych na rynku nieruchomości

## 🚀 Szybki Start

### Wymagania Systemowe

- Python 3.8+
- SQLite3
- System operacyjny: Linux/macOS/Windows
- RAM: minimum 512MB, zalecane 1GB
- Miejsce na dysku: minimum 100MB

### Instalacja za pomocą Docker (Zalecane)

```bash
# Sklonuj repozytorium
git clone https://github.com/stachuman/property-monitor.git
cd property-monitor

# Uruchom za pomocą Docker Compose
docker-compose up -d

# Sprawdź status
docker-compose ps
```

Aplikacja będzie dostępna pod adresem:
- **Mapa publiczna**: http://localhost
- **Panel administracyjny**: http://localhost:8080

### Instalacja Manualna

```bash
# Sklonuj repozytorium
git clone https://github.com/stachuman/property-monitor.git
cd property-monitor

# Utwórz środowisko wirtualne
python -m venv venv
source venv/bin/activate  # Linux/macOS
# lub
venv\Scripts\activate     # Windows

# Zainstaluj zależności
pip install -r requirements.txt

# Skopiuj i skonfiguruj plik konfiguracyjny
cp config.json.example config.json
# Edytuj config.json według potrzeb

# Uruchom migracje bazy danych
python -c "from database import DatabaseManager; DatabaseManager().init_database()"

# Uruchom system
python main_service.py
```

## 📖 Instrukcja Użytkowania

### Pierwsze Uruchomienie

1. **Dostęp do aplikacji**: Otwórz przeglądarkę i przejdź do http://localhost
2. **Panel administracyjny**: Przejdź do http://localhost:8080 dla zaawansowanego zarządzania
3. **Pierwsza synchronizacja**: W panelu admin kliknij "Start Full Scrape" aby pobrać dane

### Korzystanie z Mapy

- **Nawigacja**: Używaj myszy do przybliżania, oddalania i przewijania mapy
- **Filtry**: Wykorzystaj panel boczny do filtrowania nieruchomości
- **Szczegóły**: Kliknij na marker aby zobaczyć szczegóły nieruchomości
- **Obserwowane**: Kliknij gwiazdkę aby dodać nieruchomość do obserwowanych

### Panel Administracyjny

- **Dashboard**: Przegląd stanu systemu i statystyk
- **Scraping Control**: Zarządzanie pobieraniem danych
- **Geocoding Control**: Konfiguracja geokodowania
- **Failed Geocoding**: Ręczne poprawianie błędnych lokalizacji
- **System Status**: Monitoring zdrowia systemu

### Narzędzia CLI

```bash
# Status systemu
python cli_tools.py status

# Manualne pobieranie danych
python cli_tools.py scrape

# Geokodowanie nieruchomości
python cli_tools.py geocode --batch-size 50

# Konfiguracja
python cli_tools.py config --show

# Eksport danych
python cli_tools.py export data_export.json
```

## ⚙️ Konfiguracja

### Główny Plik Konfiguracyjny

Plik `config.json` zawiera wszystkie ustawienia systemu:

```json
{
  "environment": "production",
  "database": {
    "path": "/var/lib/property_monitor/properties.db"
  },
  "web_server": {
    "host": "0.0.0.0",
    "port": 80,
    "admin_port": 8080
  },
  "scraping_api": {
    "requests_per_minute": 30,
    "delay_seconds": 2.0
  },
  "geocoding_api": {
    "batch_size": 50,
    "delay_seconds": 1.1
  }
}
```

### Zmienne Środowiskowe

```bash
# Podstawowe ustawienia
FLASK_HOST=0.0.0.0
FLASK_PORT=80
ADMIN_PORT=8080
DATABASE_PATH=/var/lib/property_monitor/properties.db

# Opcjonalne ustawienia serwera
SERVER_NAME=property-monitor.example.com
SERVER_PROTOCOL=https
```

## 🔧 Architektura Systemu

### Komponenty

1. **Web Service** (`web_service.py`): Publiczny interfejs mapowy
2. **Admin Service** (`admin_service.py`): Panel administracyjny
3. **Scraping Service** (`property_scraper_service.py`): Pobieranie danych
4. **Geocoding Service** (`geocoding_service.py`): Geokodowanie lokalizacji
5. **Database Manager** (`database.py`): Zarządzanie bazą danych
6. **CLI Tools** (`cli_tools.py`): Narzędzia linii poleceń

### Schemat Bazy Danych

- **properties**: Główna tabela nieruchomości
- **geocoding_cache**: Cache wyników geokodowania
- **scraping_config**: Konfiguracja kategorii pobierania
- **system_health**: Logi zdrowia systemu
- **watched_properties**: Lista obserwowanych nieruchomości

### Harmonogram Zadań

- **06:00**: Codzienny scraping nowych nieruchomości
- **Co godzinę**: Geokodowanie nowych lokalizacji
- **02:00**: Czyszczenie starych danych
- **Co 5 minut**: Sprawdzanie zdrowia systemu

## 🛠️ Rozwój i Wkład

### Uruchomienie Środowiska Deweloperskiego

```bash
# Tryb deweloperski
export FLASK_DEBUG=true
python main_service.py

# Uruchomienie testów
python -m pytest tests/

# Sprawdzenie jakości kodu
flake8 .
black .
```

### Struktura Projektu

```
property-monitor/
├── config.json              # Konfiguracja główna
├── main_service.py          # Główny orchestrator
├── web_service.py           # Serwis publiczny
├── admin_service.py         # Panel admin
├── property_scraper_service.py  # Scraping
├── geocoding_service.py     # Geokodowanie
├── database.py              # Manager bazy danych
├── cli_tools.py             # Narzędzia CLI
├── models.py                # Modele danych
├── templates/               # Szablony HTML
├── admin_templates/         # Szablony admin
├── geocoding_data/          # Dane geokodowania
├── requirements.txt         # Zależności Python
├── docker-compose.yml       # Konfiguracja Docker
├── Dockerfile              # Obraz Docker
└── README.md               # Ta dokumentacja
```

### Dodawanie Nowych Funkcji

1. Fork repozytorium
2. Utwórz branch dla nowej funkcji
3. Zaimplementuj zmiany z testami
4. Wyślij Pull Request z opisem zmian

## 📊 Monitoring i Logi

### Monitorowanie Systemu

System posiada wbudowane narzędzia monitoringu:

```bash
# Status systemu
python monitor.py --check-only

# Raport zdrowia
python monitor.py --format html --output health_report.html

# Alerty
python monitor.py --alerts-only
```

### Lokalizacja Logów

- **Aplikacja**: `/var/log/property_monitor/property_monitor.log`
- **Błędy**: Automatycznie rejestrowane w bazie danych
- **System**: `/var/log/property_monitor/monitor.log`

## 🔒 Bezpieczeństwo

### Najlepsze Praktyki

- Regularne aktualizacje systemu i zależności
- Konfiguracja firewalla dla portów 80 i 8080
- Backup bazy danych co 24 godziny
- Monitoring nietypowej aktywności

### Backup i Przywracanie

```bash
# Backup bazy danych
cp /var/lib/property_monitor/properties.db backup_$(date +%Y%m%d).db

# Eksport wszystkich danych
python cli_tools.py export full_backup_$(date +%Y%m%d).json

# Przywracanie z backup
cp backup_20240101.db /var/lib/property_monitor/properties.db
sudo systemctl restart property-monitor
```

## 📄 Licencja

Ten projekt jest udostępniony na licencji MIT. Zobacz plik [LICENSE](LICENSE) dla szczegółów.

## 🤝 Wsparcie

### Zgłaszanie Problemów

Jeśli napotkasz problemy:

1. Sprawdź [Issues](https://github.co/stachuman/property-monitor/issues)
2. Sprawdź logi systemu
3. Uruchom diagnostykę: `python cli_tools.py status`
4. Utwórz nowy Issue z opisem problemu

### Społeczność

- **Issues**: Zgłaszanie błędów i propozycji
- **Discussions**: Pytania i dyskusje ogólne
- **Wiki**: Dodatkowa dokumentacja i tutoriale

## 🎯 Roadmapa

### Planowane Funkcje

- [ ] Powiadomienia email o nowych nieruchomościach
- [ ] Zaawansowana analityka i raporty
- [ ] Aplikacja mobilna
- [ ] System alertów cenowych

### Wersje

- **v1.0**: Podstawowa funkcjonalność (obecna)

---

