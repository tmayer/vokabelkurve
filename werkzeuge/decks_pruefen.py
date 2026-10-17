# Prüft alle Deck-Dateien in webspace/decks/ so, wie die App sie liest:
# erste Zeile = zwei Sprachnamen, danach Deutsch;Fremdsprache(;Thema;…), Trennzeichen ; (oder , bzw. Tab).
# Aufruf: python3 werkzeuge/decks_pruefen.py [ordner]   -> Exit-Code 1 bei Fehlern
import csv, re, sys
from pathlib import Path

ordner = Path(sys.argv[1] if len(sys.argv) > 1 else 'webspace/decks')
norm = lambda s: re.sub(r'\W+', ' ', s.lower()).strip()
fehler = 0

for f in sorted(ordner.glob('*.csv')):
    try:
        text = f.read_text(encoding='utf-8-sig')
    except UnicodeDecodeError:
        print(f'FEHLER {f.name}: keine UTF-8-Datei'); fehler += 1; continue
    erste = text.splitlines()[0] if text else ''
    trenner = max([';', ',', '\t'], key=erste.count)
    zeilen = [z for z in csv.reader(text.splitlines(), delimiter=trenner) if any(x.strip() for x in z)]
    if len(zeilen) < 6 or len(zeilen[0]) < 2:
        print(f'FEHLER {f.name}: braucht eine Kopfzeile mit zwei Sprachen und mindestens 5 Wortpaare'); fehler += 1; continue
    gesehen, doppelt, kaputt = set(), [], []
    for nr, z in enumerate(zeilen[1:], start=2):
        if len(z) < 2 or not z[0].strip() or not z[1].strip():
            kaputt.append(nr); continue
        k = (norm(z[0]), norm(z[1]))
        if k in gesehen: doppelt.append(nr)
        gesehen.add(k)
    if kaputt:
        print(f'FEHLER {f.name}: unvollständige Zeilen {kaputt[:10]}'); fehler += 1
    if doppelt:
        print(f'WARNUNG {f.name}: doppelte Wortpaare in Zeilen {doppelt[:10]}')
    print(f'ok {f.name}: {len(gesehen)} Wortpaare')

sys.exit(1 if fehler else 0)
