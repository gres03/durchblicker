# Anleitung: KFZ-Rechner automatisch ausfüllen

Diese Anleitung erklärt, wie du das Tool im Alltag benutzt — ohne
Programmierkenntnisse.

## Was du einmalig brauchst

- Einen Windows-, Mac- oder Linux-PC
- Einmalig eingerichtet (das macht jemand einmal für dich, danach bleibt es
  so): Python + das Programm selbst, siehe README.md "Setup"
- Einen kostenlosen Gemini-API-Schlüssel für die automatische
  Dokumentenerkennung (kein Zahlungsmittel nötig, wird beim Setup einmalig
  eingerichtet — siehe README.md)
- Deine Zugangsdaten für durchblicker.at (die hast du schon)

Kein Abo, keine laufenden Kosten.

## Der Ablauf für einen Kundenfall

### Web-Oberfläche starten

**Windows:** Doppelklick auf `Webapp_starten.bat` im Programm-Ordner.
**Mac/Linux:** Terminal im Programm-Ordner öffnen und `./webapp_starten.sh`.

Ein schwarzes Fenster öffnet sich kurz, dann öffnet sich automatisch dein
Browser mit der Programm-Oberfläche. Das schwarze Fenster einfach offen
lassen, solange du arbeitest.

### Schritt 1: Dokument hochladen

Foto oder PDF vom Zulassungsschein/Kundenformular auf die Fläche ziehen
(oder anklicken zum Auswählen) und auf "Automatisch auslesen" klicken.
Die Daten werden automatisch ausgelesen — das dauert ein paar Sekunden.

### Schritt 2: Nur bei Unklarheiten kurz prüfen

Du siehst eine Tabelle mit allen erkannten Daten. Ist alles eindeutig,
steht überall "OK" — dann direkt auf "Bestätigen & ausfüllen" klicken.

Ist etwas **rot** markiert (z.B. weil ein Feld auf dem Foto unscharf war),
siehst du direkt daneben ein Eingabefeld: entweder den richtigen Wert
eintragen, oder leer lassen, um den vorgeschlagenen Wert zu übernehmen.
Danach "Korrekturen speichern" — nur bei echten Unklarheiten wird
nachgefragt, nie bei klaren Fällen.

### Schritt 3: Automatisch ausfüllen

Ein Browserfenster öffnet sich von selbst und trägt alle Daten Schritt für
Schritt in den durchblicker.at-Rechner ein. Die Web-Seite zeigt danach eine
Tabelle: Soll-Wert vs. tatsächlich eingetragener Wert. Steht überall "OK",
ist alles korrekt eingetragen.

### Zum Schluss: Selbst prüfen und abschließen

**Das Programm klickt absichtlich nirgends auf "Berechnen" oder "Zum
Ergebnis"** — das machst du von Hand, nachdem du dir den ausgefüllten
Rechner im offenen Browserfenster nochmal in Ruhe angeschaut hast.

Für den nächsten Kundenfall auf der Ergebnis-Seite einfach auf "Nächsten
Fall bearbeiten" klicken.

## Was, wenn etwas nicht geklappt hat?

Falls das Programm mitten im Ausfüllen abbricht, sagt es dir das klar und
speichert einen Screenshot im Ordner `logs/` — den kannst du mir (oder
jemand anderem, der sich mit dem Programm auskennt) einfach zeigen.

## Wichtige Einschränkung: Nationalcode muss lesbar sein

Der Rechner findet das Fahrzeug am zuverlässigsten über den **Nationalen
Code** (Feld A7 im Zulassungsschein, eine kurze Ziffernfolge). Nur dieser
Weg ist bisher automatisiert.

Ist der Nationalcode auf dem Dokument nicht lesbar (z.B. schlechtes Foto)
und die Erkennung findet stattdessen nur Marke/Modell, bricht das Programm
bewusst und sauber ab — mit der Meldung, dass dieser Weg noch nicht
unterstützt wird. Das ist **kein Fehler**, sondern Absicht: das Programm
rät lieber nicht, als etwas Falsches einzutragen.

In diesem Fall: entweder ein besseres Foto vom Zulassungsschein machen
(Feld A7 muss scharf lesbar sein) oder diesen einen Fall von Hand auf
durchblicker.at eintragen.

## Alternative ohne Gemini-Schlüssel: manuell über claude.ai

Falls (noch) kein Gemini-Schlüssel eingerichtet ist, oder bei einem
besonders sensiblen Dokument, das du lieber selbst kontrollierst, bevor es
irgendwohin geschickt wird, geht es auch ganz ohne Web-Oberfläche:

1. Dokument + Text aus `extraktion_anfrage.txt` bei [claude.ai](https://claude.ai)
   (kostenloser Account) hochladen, Antwort als `.json`-Datei speichern
   (Editor, nicht Word — siehe Hinweis unten).
2. Datei auf `Fall_starten.bat` ziehen (Mac/Linux: `./fall_starten.sh datei.json`).
3. Nur bei roten Zeilen im schwarzen Fenster kurz nachschauen/korrigieren.
4. Ergebnis im Browser selbst prüfen, dann selbst auf "Berechnen" klicken.

**Beim Speichern in Notepad:** "Datei" → "Speichern unter…" → zum
Programm-Ordner navigieren → Dateiname mit Anführungszeichen eingeben,
z.B. `"kunde_mueller.json"` (sonst hängt Notepad automatisch `.txt` an).

## Für Fortgeschrittene: die einzelnen Schritte von Hand

```
python mapping.py kunde_mueller.json -o kunde_mueller_fall.json
python confirm.py kunde_mueller_fall.json
python fill.py kunde_mueller_fall.json
```

`start.py` (was `Fall_starten.bat`/`fall_starten.sh` aufruft) und `app.py`
(die Web-Oberfläche) machen im Hintergrund genau das automatisch.
