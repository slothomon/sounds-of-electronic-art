# Pages CMS für sofea einrichten

Pages CMS ist hier nur die Bearbeitungsoberfläche. Die Daten bleiben in
`content/episodes.json`, Bilder im GitHub-Repository und die Veröffentlichung
läuft weiterhin über die vorhandenen GitHub Actions.

## Konten und Rechte

Keinen gemeinsamen oder zusätzlichen GitHub-Benutzer anlegen. Jede der zwei
oder drei beteiligten Personen verwendet ihr eigenes GitHub-Konto. Das hält
Änderungen nachvollziehbar und vermeidet gemeinsam genutzte Passwörter und
2FA-Zugänge.

1. Repository auf GitHub öffnen.
2. **Settings → Collaborators** öffnen.
3. Die weiteren Personen einzeln einladen.
4. Alle sollten Zwei-Faktor-Authentifizierung oder einen Passkey verwenden.

## Einmalige Vorbereitung vorhandener Listen

Pages CMS bearbeitet `music_presentations` und `tracklist` als wiederholbare
Objekte. Ältere Einträge dürfen im Build weiterhin einfache Strings enthalten,
für das CMS sollten sie aber einmalig vereinheitlicht werden.

Zuerst nur prüfen:

```cmd
py scripts\normalize_episode_lists.py
```

Wenn Konvertierungen angekündigt werden, vorher committen oder ein Backup
anlegen und dann schreiben:

```cmd
py scripts\normalize_episode_lists.py --write
py -m json.tool content\episodes.json > nul
py scripts\validate_site.py --source
py scripts\build.py
py scripts\validate_site.py --public
```

Ein String wie

```json
"Headache – Nineteen Sixty Five"
```

wird dabei zu:

```json
{
  "artist": "Headache",
  "title": "Nineteen Sixty Five"
}
```

Links und weitere Felder können danach im CMS ergänzt werden.

## Pages CMS verbinden

1. `https://app.pagescms.org` öffnen.
2. Mit dem eigenen GitHub-Konto anmelden.
3. Die Pages-CMS-GitHub-App installieren.
4. Bei der Repository-Auswahl am besten **Only select repositories** wählen
   und nur `slothomon/sounds-of-electronic-art` freigeben.
5. Das Repository und den Branch `main` öffnen.
6. Pages CMS liest die im Repository enthaltene `.pages.yml` automatisch.
7. In der Seitenleiste **Sendungen & Termine** öffnen.

Jede Person wiederholt nur Anmeldung und GitHub-Autorisierung mit ihrem eigenen
Konto. Eine gemeinsame CMS-Anmeldung ist nicht nötig.

## Was im Editor gepflegt werden kann

Der Editor deckt derzeit beides in einer Liste ab:

- künftige Radiosendungen und Veranstaltungen (`status: upcoming`);
- lokale Ergänzungen zu archivierten SoundCloud-Sendungen (`status: past`).

Unter anderem stehen Formulare bereit für:

- Beginn und Ende;
- Typ und Status;
- Titel, Kurz- und Detailtexte auf Deutsch und Englisch;
- Ort und strukturierte Veranstaltungsadresse;
- SoundCloud-URL;
- Artwork und eigenes Social-Media-Bild;
- Musikvorstellungen inklusive Discogs-/Bandcamp-Link;
- Tracklist und Zeitmarken;
- Line-up und weitere Links;
- `updated_at` für wesentliche Inhaltsänderungen.

### Archivsendung richtig zuordnen

Bei einer bestehenden Sendung muss `audio_url` exakt der öffentlichen
SoundCloud-Track-URL entsprechen. Dieses Feld verbindet den lokalen Eintrag
mit `content/archive-cache.json`.

### Bilder hochladen

Das Bildfeld speichert hochgeladene Dateien unter:

```text
assets/images/uploads/
```

Das Feld `image` überschreibt das automatisch von SoundCloud geladene Artwork.
Das Feld `social_image` ist nur nötig, wenn die automatisch erzeugte Social
Card ersetzt werden soll.

### Speichern und Veröffentlichung

Beim Speichern schreibt Pages CMS einen normalen Commit in das Repository.
Der bestehende Pages-Workflow validiert die JSON-Daten, baut die Seite und
veröffentlicht sie. Falls der Build rot wird, ist die Website weiterhin auf dem
zuletzt erfolgreichen Stand; die Fehlermeldung steht unter GitHub **Actions**.

## Empfohlener Redaktionsablauf

1. Eintrag in Pages CMS öffnen oder neu hinzufügen.
2. Änderungen speichern.
3. Auf GitHub den neuen Actions-Lauf kontrollieren.
4. Bei Tracklists oder Musikvorstellungen `updated_at` auf das aktuelle Datum
   setzen, weil sich der sichtbare Seiteninhalt wesentlich geändert hat.
5. Die veröffentlichte Detailseite kurz kontrollieren.

Für zwei bis drei Personen und einen Acht-Wochen-Rhythmus ist die bestehende
Top-Level-Liste praktikabel. Erst bei häufigen parallelen Änderungen wäre eine
spätere Aufteilung in eine JSON-Datei pro Sendung sinnvoll.
