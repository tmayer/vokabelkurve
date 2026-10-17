# Vokabelkurve auf IONOS

## Hochladen (einmalig)

1. In IONOS unter *Hosting → PHP-Version* PHP **8.1 oder neuer** einstellen.
2. Den **Inhalt** des Ordners `webspace/` per SFTP (z. B. FileZilla, Cyberduck) oder mit dem IONOS-Dateimanager in das Zielverzeichnis der Domain laden. Dazu gehören die versteckten Dateien `.htaccess` und `data/.htaccess`, die in FileZilla oder Cyberduck erst nach Einblenden versteckter Dateien sichtbar sind.
3. Die Seite aufrufen, unter **Daten & Einstellungen → Lernstand auf dem Server** den Schlüssel aus `GERAETESCHLUESSEL.txt` eingeben. Das einmal pro Gerät (Handy, Rechner).

`GERAETESCHLUESSEL.txt` **nicht** hochladen. Auf dem Server liegt nur ein Hash des Schlüssels.

## Neues Deck

CSV-Datei in den Ordner `decks/` laden, Seite neu laden. Erste Zeile die Sprachnamen, dann ein Wortpaar pro Zeile, optional eine dritte Spalte mit dem Thema. Als UTF-8 speichern.

```
Deutsch;Spanisch;Thema
der Hund;el perro;Tiere
```

Datei ändern ist in Ordnung (der Lernstand unveränderter Paare bleibt). Datei umbenennen erzeugt ein neues Deck.

## Was wo liegt

| Pfad | Inhalt | Wer darf |
|---|---|---|
| `index.html` | die App | alle |
| `decks/*.csv` | Vokabeln | alle lesen, ändern nur per SFTP |
| `api/decks.php` | Liste der Decks | alle |
| `api/progress.php` | Lernstand lesen/schreiben | nur mit Geräteschlüssel |
| `api/config.php` | Hash des Schlüssels | nicht abrufbar |
| `data/` | Lernstand als JSON | nicht abrufbar, nur über `progress.php` |

## Schlüssel wechseln

Neuen Zufallstext wählen, seinen SHA-256-Hash in `api/config.php` bei `VK_TOKEN_HASH` eintragen, hochladen und die Geräte neu verbinden. Im Terminal:

```bash
python3 -c "import secrets,hashlib;t=secrets.token_urlsafe(32);print(t);print(hashlib.sha256(t.encode()).hexdigest())"
```

Erste Zeile ist der neue Schlüssel, zweite Zeile der Hash.

## Sicherung

Der Lernstand liegt in `data/progress-*.json` und `data/settings.json`. Diese Dateien gelegentlich per SFTP herunterladen. Alternativ in der App „Sicherung kopieren“.
