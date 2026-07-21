# Annotation Guidelines for JobExtract

Diese Richtlinien dienen als kleine, manuell überprüfbare Beispielbasis für deutsche Stellenanzeigen. Ziel ist eine konsistente Annotation der sieben erlaubten Entitätstypen.

## Allgemeine Regeln

- Annotieren Sie nur Textspannen, die im Eingabetext eindeutig vorkommen.
- Spans dürfen nicht leer sein.
- Spans müssen exakt mit dem Originaltext übereinstimmen.
- Mehrfache Vorkommen desselben Wortes oder Ausdrucks werden separat annotiert, sofern sie semantisch getrennt auftreten.
- Wenn mehrere sinnvolle Interpretationen möglich sind, bevorzugen Sie die explizitere und lokalere Span.
- Orte wie Berlin, Hamburg oder München werden nicht annotiert, sofern sie nicht Teil einer Arbeitssituation wie „Remote aus Berlin“ sind.
- Firmennamen, Abteilungen und generische Organisationseinheiten sind keine JOB_TITLE.

## JOB_TITLE

- Bedeutung: ausgeschriebene Position oder Berufsbezeichnung.
- Einschlussregeln:
  - Stellenbezeichnungen wie „Data Scientist“, „Pflegefachkraft“, „Softwareentwickler“, „Verkäufer“, „Sachbearbeiter".
  - Titel mit Spezifizierung wie „Senior Data Scientist" oder „Werkstudent (m/w/d) für Data Science".
- Ausschlussregeln:
  - Firmenname, Abteilung, Teamname oder Projektbezeichnung.
  - Allgemeine Unternehmensbeschreibungen wie „innovatives Unternehmen".
- Positive Beispiele:
  - „Data Scientist"
  - „Pflegefachkraft"
  - „Softwareentwickler"
- Negative bzw. schwierige Beispiele:
  - „Müller GmbH" -> kein JOB_TITLE
  - „IT-Abteilung" -> kein JOB_TITLE
- Mehrteilige Spans:
  - Wenn Titel und Zusatz zusammen eine eindeutige Position bilden, können beide gemeinsam markiert werden.
- Mehrfache Vorkommen:
  - Wenn dieselbe Funktion mehrfach im Text erwähnt wird, annotieren Sie jede relevante Erwähnung separat.

## HARD_SKILL

- Bedeutung: technische Fähigkeiten, Werkzeuge, Sprachen, Methoden, Verfahren.
- Einschlussregeln:
  - Programmiersprachen, Frameworks, Tools, Datenbanken, Methoden, technische Prozesse.
  - Beispiele: Python, SQL, SAP, Machine Learning, Docker, Tableau.
- Ausschlussregeln:
  - Allgemeine Berufserfahrung oder soft skills.
  - Nicht-technische Aufgaben wie „Kundenbetreuung".
- Positive Beispiele:
  - „Python"
  - „SQL"
  - „SAP"
  - „Machine Learning"
- Negative bzw. schwierige Beispiele:
  - „Datenanalyse" kann je nach Kontext technisch oder allgemein sein; bevorzugen Sie die technische Lesart, wenn ein konkretes Werkzeug oder Verfahren folgt.
- Mehrteilige Spans:
  - Gebräuchliche Mehrwort-Ausdrücke wie „Machine Learning" oder „Cloud Computing" sollten als ein Span annotiert werden.
- Mehrfache Vorkommen:
  - Wenn dasselbe Tool mehrfach erwähnt wird, annotieren Sie jede relevante Stelle separat.

## SOFT_SKILL

- Bedeutung: persönliche, soziale oder organisatorische Fähigkeiten.
- Einschlussregeln:
  - Teamfähigkeit, Kommunikationsstärke, selbstständige Arbeitsweise, Verantwortungsbereitschaft, Zuverlässigkeit.
- Ausschlussregeln:
  - Technische Kompetenzen oder fachliche Kenntnisse.
  - Generelle Eigenschaften ohne explizite Fähigkeit wie „interessiert an Innovation".
- Positive Beispiele:
  - „Teamfähigkeit"
  - „Kommunikationsstärke"
  - „selbstständige Arbeitsweise"
- Negative bzw. schwierige Beispiele:
  - „Verantwortung" ist nur dann ein SOFT_SKILL, wenn es als Eigenschaft im Stellenprofil erscheint.
- Mehrteilige Spans:
  - Mehrwort-Ausdrücke wie „starke Kommunikationsfähigkeit" können als ein Span annotiert werden.
- Mehrfache Vorkommen:
  - Wiederholte Erwähnungen derselben Fähigkeit werden separat markiert, wenn sie semantisch getrennt sind.

## EXPERIENCE

- Bedeutung: verlangte bisherige Berufs- oder Praxiserfahrung.
- Einschlussregeln:
  - Phrasen wie „mindestens zwei Jahre Berufserfahrung", „erfolgreiche Erfahrung im Vertrieb", „mehrjährige Erfahrung in Pflegeprozessen".
- Ausschlussregeln:
  - Wochenstunden, Beschäftigungsumfang, Werkstudentenstatus oder Arbeitszeitangaben.
  - „20 Stunden pro Woche" gehört nicht hierher.
- Positive Beispiele:
  - „mindestens zwei Jahre Berufserfahrung"
  - „mehrjährige Erfahrung im Vertrieb"
- Negative bzw. schwierige Beispiele:
  - „20 Stunden pro Woche" -> kein EXPERIENCE
  - „Werkstudent" -> kein EXPERIENCE
- Mehrteilige Spans:
  - Wenn Quantität und Bereich zusammen die Erfahrung beschreiben, kann der gesamte Ausdruck markiert werden.
- Mehrfache Vorkommen:
  - Mehrere Erfahrungsangaben werden separat annotiert.

## EDUCATION

- Bedeutung: Abschluss, Ausbildung oder Studienfach.
- Einschlussregeln:
  - „Bachelor in Informatik", „abgeschlossene Ausbildung im Gesundheitswesen", „Facharzt für Innere Medizin".
- Ausschlussregeln:
  - Allgemeine Fähigkeiten oder fachliche Erfahrung.
  - Nicht abgeschlossene oder unklare Bildungsangaben ohne Abschluss oder Studienfach.
- Positive Beispiele:
  - „Bachelor in Informatik"
  - „abgeschlossene Ausbildung"
- Negative bzw. schwierige Beispiele:
  - „Studium" ohne Fach oder Abschluss ist eher unklar; annotieren Sie nur, wenn das Fach oder der Abschluss explizit genannt ist.
- Mehrteilige Spans:
  - Abschluss plus Fach können gemeinsam markiert werden.
- Mehrfache Vorkommen:
  - Wenn mehrere Bildungsnachweise genannt werden, annotieren Sie jeden separat.

## LANGUAGE

- Bedeutung: Sprachkenntnisse inklusive Niveau.
- Einschlussregeln:
  - „Deutsch C1", „verhandlungssicheres Englisch", „Englisch B2", „Französisch fließend".
- Ausschlussregeln:
  - Allgemeine Hinweise auf „mehrsprachig" ohne Niveau oder konkrete Sprache.
  - Länder oder Orte.
- Positive Beispiele:
  - „Deutsch C1"
  - „Englisch B2"
- Negative bzw. schwierige Beispiele:
  - „mehrsprachig" -> kein LANGUAGE, wenn kein Niveau oder keine Sprache angegeben ist.
- Mehrteilige Spans:
  - Sprache und Niveau bleiben in einem Span zusammen, wenn sie direkt zusammen auftreten.
- Mehrfache Vorkommen:
  - Mehrere Sprachangaben werden separat annotiert.

## WORK_MODE

- Bedeutung: Arbeitsorganisation oder Modalität der Tätigkeit.
- Einschlussregeln:
  - Remote, Hybrid, Präsenz, Vollzeit, Teilzeit, Werkstudent, 20 Stunden pro Woche, 40 Wochenstunden.
- Ausschlussregeln:
  - Erfahrung, Bildungsangaben, Firmennamen oder Orte.
  - „Berlin" ist kein WORK_MODE.
- Positive Beispiele:
  - „Remote"
  - „Hybrid"
  - „Teilzeit"
  - „20 Stunden pro Woche"
  - „Werkstudent"
- Negative bzw. schwierige Beispiele:
  - „20 Jahre Erfahrung" -> kein WORK_MODE
  - „Berlin" -> kein WORK_MODE
- Mehrteilige Spans:
  - Mehrteilige Arbeitszeitangaben wie „20 Stunden pro Woche" werden als ein Span annotiert.
- Mehrfache Vorkommen:
  - Mehrere Arbeitsmodalitäten wie „Remote, Hybrid" können getrennt annotiert werden, sofern sie als separate Ausdrücke auftreten.
