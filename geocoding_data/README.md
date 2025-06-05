# Geocoding Data Files

This directory contains external data files used by the simplified geocoding system.

## Files:

### city_corrections.json
Maps common misspellings to correct city names.
Example: "warszewa" → "warszawa"

### diacritic_mapping.json  
Maps Polish diacritics to Latin characters.
Example: "ą" → "a", "ł" → "l"

### common_prefixes.json
List of administrative prefixes to remove from city names.
Example: "gmina", "miasto", "powiat"

## Usage:

5AThese files are automatically loaded by the GeocodingDataManager class.
You can edit them to add new corrections or mappings.

## Adding New Corrections:

1. Edit city_corrections.json to add new misspelling mappings
2. Add new diacritics to diacritic_mapping.json if needed  
3. Add new prefixes to common_prefixes.json if encountered
4. Restart the geocoding service to load changes

## File Format:

All files use UTF-8 encoding and standard JSON format.
Ensure proper JSON syntax when editing.
