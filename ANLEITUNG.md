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

## Der Ablauf für einen Kundenfall — nur 2 Schritte

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
   speichere sie z.B. als `kunde_mueller.json`. Im Detail:
   1. Windows-Taste drücken, "Editor" eintippen, Enter — **nicht Word**
      benutzen, das würde versteckte Formatierung mitspeichern.
   2. Text mit `Strg+V` einfügen.
   3. Oben "Datei" → "Speichern unter…".
   4. Zum Programm-Ordner navigieren
      (`C:\Users\PC\OneDrive\Dokumente\ai tool mama\durchblicker-automation`).
   5. Beim Dateinamen genau `"kunde_mueller.json"` eingeben — **mit
      Anführungszeichen**, sonst hängt der Editor automatisch `.txt`
      hinten an und die Datei heißt am Ende `kunde_mueller.json.txt`,
      was nicht funktioniert.
   6. Speichern klicken.

**Wichtig:** Claude macht gelegentlich Fehler beim Lesen (z.B. bei
schlechten Fotos). Das ist kein Problem — im nächsten Schritt wird genau
das automatisch geprüft und du bekommst die Möglichkeit, es zu korrigieren.
Deshalb: nicht blind vertrauen, aber auch keine Sorge, es fällt auf.

### Schritt 2: Datei draufziehen, fertig

**Windows:** Zieh `kunde_mueller.json` einfach mit der Maus auf die Datei
`Fall_starten.bat` im Programm-Ordner (oder Rechtsklick auf die JSON-Datei
→ "Öffnen mit" → `Fall_starten.bat`). Ein schwarzes Fenster öffnet sich von
selbst und macht den Rest.

**Mac/Linux:** Terminal im Programm-Ordner öffnen und:
```
./fall_starten.sh kunde_mueller.json
```

Ab hier läuft alles automatisch durch:
- Die Daten werden ins richtige Format übersetzt.
- Ist alles eindeutig, geht es **ohne jede Eingabe** direkt weiter.
- Ist irgendetwas unklar oder unplausibel (z.B. weil das Foto an einer
  Stelle unscharf war), zeigt eine Tabelle genau diese Zeile **rot** an
  und fragt kurz nach: Enter drücken zum Bestätigen, oder den richtigen
  Wert eintippen. Nur bei echten Unklarheiten — nie bei klaren Fällen.
- Ein Browserfenster öffnet sich von selbst und trägt alle Daten Schritt
  für Schritt in den durchblicker.at-Rechner ein.
- Am Ende siehst du eine Tabelle: Soll-Wert vs. tatsächlich eingetragener
  Wert. Steht überall "OK", ist alles korrekt eingetragen.

### Zum Schluss: Selbst prüfen und abschließen

**Das Programm klickt absichtlich nirgends auf "Berechnen" oder "Zum
Ergebnis"** — das machst du von Hand, nachdem du dir den ausgefüllten
Rechner im offenen Browserfenster nochmal in Ruhe angeschaut hast. Der
Browser bleibt extra offen, genau dafür. Danach im schwarzen Fenster Enter
drücken, um es zu schließen.

## Was, wenn etwas nicht geklappt hat?

Falls das Programm mitten im Ausfüllen abbricht, sagt es dir das klar und
speichert einen Screenshot im Ordner `logs/` — den kannst du mir (oder
jemand anderem, der sich mit dem Programm auskennt) einfach zeigen.

## Wichtige Einschränkung: Nationalcode muss lesbar sein

Der Rechner findet das Fahrzeug am zuverlässigsten über den **Nationalen
Code** (Feld A7 im Zulassungsschein, eine kurze Ziffernfolge). Nur dieser
Weg ist bisher automatisiert.

Ist der Nationalcode auf dem Dokument nicht lesbar (z.B. schlechtes Foto)
und Claude erkennt stattdessen nur Marke/Modell, bricht das Programm
bewusst und sauber ab — mit der Meldung, dass dieser Weg noch nicht
unterstützt wird. Das ist **kein Fehler**, sondern Absicht: das Programm
rät lieber nicht, als etwas Falsches einzutragen.

In diesem Fall: entweder ein besseres Foto vom Zulassungsschein machen
(Feld A7 muss scharf lesbar sein) oder diesen einen Fall von Hand auf
durchblicker.at eintragen.

## Kurzfassung zum Aufkleben

1. Dokument + `extraktion_anfrage.txt` bei claude.ai hochladen → Antwort
   als `.json`-Datei speichern
2. Datei auf `Fall_starten.bat` ziehen (Mac/Linux: `./fall_starten.sh datei.json`)
3. Nur bei roten Zeilen kurz nachschauen/korrigieren
4. Ergebnis im Browser selbst prüfen, dann selbst auf "Berechnen" klicken

## Für Fortgeschrittene: die einzelnen Schritte von Hand

Falls du lieber jeden Schritt einzeln sehen willst (z.B. zum Testen),
geht das weiterhin:

```
python mapping.py kunde_mueller.json -o kunde_mueller_fall.json
python confirm.py kunde_mueller_fall.json
python fill.py kunde_mueller_fall.json
```

`start.py` (was `Fall_starten.bat`/`fall_starten.sh` im Hintergrund
aufruft) macht genau das automatisch nacheinander.
