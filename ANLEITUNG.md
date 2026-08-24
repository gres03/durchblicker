# Anleitung: KFZ-Rechner automatisch ausfüllen

Diese Anleitung erklärt, wie du das Tool im Alltag benutzt — ohne
Programmierkenntnisse. Alles ist kostenlos.

## Was du einmalig brauchst

- Einen Windows-, Mac- oder Linux-PC
- Einmalig eingerichtet (das macht jemand einmal für dich, danach bleibt es
  so): Python + das Programm selbst, siehe README.md "Setup"
- Einen kostenlosen Account bei [claude.ai](https://claude.ai) (für die
  Texterkennung aus dem Dokument — dazu gleich mehr)
- Deine Zugangsdaten für durchblicker.at (die hast du schon)

Das war's. Kein Abo, keine laufenden Kosten.

## Der Ablauf für einen Kundenfall — Schritt für Schritt

### Schritt 1: Dokument in Daten verwandeln (bei claude.ai, kostenlos)

Du hast z.B. einen Zulassungsschein als Foto oder ein Kundenformular als
PDF. Damit das Programm etwas damit anfangen kann, muss daraus zuerst eine
strukturierte Liste werden.

1. Öffne [claude.ai](https://claude.ai) im Browser, logge dich ein
   (kostenloser Account reicht).
2. Lade das Foto/PDF des Dokuments hoch (Büroklammer-Symbol im Chat).
3. Kopiere den Text aus der Datei `extraktion_anfrage.txt` (liegt im
   Programm-Ordner) in den Chat, direkt unter dem hochgeladenen Dokument,
   und schick die Nachricht ab.
4. Claude gibt dir eine Antwort mit einem Textblock, der mit `{` beginnt
   und mit `}` endet. Das ist die "Datenliste". Kopiere genau diesen
   Textblock.
5. Öffne im Programm-Ordner eine neue Textdatei, füge den Text ein, und
   speichere sie z.B. als `kunde_mueller.json`.

**Wichtig:** Claude macht gelegentlich Fehler beim Lesen (z.B. bei
schlechten Fotos). Das ist kein Problem — im nächsten Schritt wird genau
das automatisch geprüft und du bekommst die Möglichkeit, es zu korrigieren.
Deshalb: nicht blind vertrauen, aber auch keine Sorge, es fällt auf.

### Schritt 2: Daten übersetzen

Terminal/PowerShell im Programm-Ordner öffnen, dann:

```
python mapping.py kunde_mueller.json -o kunde_mueller_fall.json
```

Das übersetzt Dinge wie "bar bezahlt" automatisch in die Wörter, die das
Formular auf durchblicker.at erwartet.

### Schritt 3: Prüfen und bestätigen

```
python confirm.py kunde_mueller_fall.json
```

Es erscheint eine Tabelle mit allen erkannten Daten. Alles, was **rot**
markiert ist, musst du dir ansehen: entweder war die Angabe im Dokument
nicht eindeutig, oder Claude hat sie nicht gefunden. Für jede rote Zeile
fragt dich das Programm: Enter drücken zum Bestätigen, oder den richtigen
Wert eintippen. Erst wenn alles **grün** ist, geht es weiter.

### Schritt 4: Automatisch ausfüllen

```
python fill.py kunde_mueller_fall.json
```

Jetzt öffnet sich ein Browserfenster von selbst, und das Programm trägt
alle Daten Schritt für Schritt in den durchblicker.at-Rechner ein. Am Ende
siehst du wieder eine Tabelle: Soll-Wert vs. tatsächlich eingetragener
Wert. Steht überall "OK", ist alles korrekt eingetragen.

### Schritt 5: Selbst prüfen und abschließen

**Das Programm klickt absichtlich nirgends auf "Berechnen" oder "Zum
Ergebnis"** — das machst du von Hand, nachdem du dir den ausgefüllten
Rechner im offenen Browserfenster nochmal in Ruhe angeschaut hast. Der
Browser bleibt extra offen, genau dafür.

## Was, wenn etwas nicht geklappt hat?

Falls das Programm mitten im Ausfüllen abbricht, sagt es dir das klar und
speichert einen Screenshot im Ordner `logs/` — den kannst du mir (oder
jemand anderem, der sich mit dem Programm auskennt) einfach zeigen.

## Wichtige Einschränkung: Nationalcode muss lesbar sein

Der Rechner findet das Fahrzeug am zuverlässigsten über den **Nationalen
Code** (Feld A7 im Zulassungsschein, eine kurze Ziffernfolge). Nur dieser
Weg ist bisher automatisiert.

Ist der Nationalcode auf dem Dokument nicht lesbar (z.B. schlechtes Foto)
und Claude erkennt stattdessen nur Marke/Modell, bricht `fill.py` bewusst
und sauber ab — mit der Meldung, dass dieser Weg noch nicht unterstützt
wird. Das ist **kein Fehler**, sondern Absicht: das Programm rät lieber
nicht, als etwas Falsches einzutragen.

In diesem Fall: entweder ein besseres Foto vom Zulassungsschein machen
(Feld A7 muss scharf lesbar sein) oder diesen einen Fall von Hand auf
durchblicker.at eintragen.

## Kurzfassung zum Aufkleben

1. Dokument + `extraktion_anfrage.txt` bei claude.ai hochladen → Antwort
   als `.json`-Datei speichern
2. `python mapping.py <datei>.json -o <datei>_fall.json`
3. `python confirm.py <datei>_fall.json` — rote Zeilen klären
4. `python fill.py <datei>_fall.json` — Ergebnis im Browser selbst prüfen
5. Selbst auf "Berechnen" klicken, wenn alles passt
