"""Demo-Beispiele für die UI – keine personenbezogenen Daten, synthetisch aber realistisch."""

from __future__ import annotations

EXAMPLES: list[dict[str, str]] = [
    {
        "id": "software",
        "label": "Softwareentwickler Backend",
        "short": "Python, SQL, Docker · Hybrid · Berlin",
        "text": (
            "Softwareentwickler Backend (m/w/d) – Python & Cloud\n"
            "Standort: Berlin (Hybrid: 2 Tage vor Ort, 3 Tage Remote) · Vollzeit · Unbefristet\n\n"
            "Wir entwickeln eine datengetriebene Plattform für industrielle Anwendungen und suchen dich zur "
            "Verstärkung unseres Backend-Teams. Du arbeitest eng mit Produkt und Data Science zusammen.\n\n"
            "Deine Aufgaben:\n"
            "- Entwicklung und Betrieb von Microservices in Python (FastAPI)\n"
            "- Design und Optimierung von Datenbanken (PostgreSQL, SQL)\n"
            "- Containerisierung mit Docker und Deployment auf Kubernetes\n"
            "- Code-Reviews, Tests und kontinuierliche Verbesserung der Architektur\n\n"
            "Dein Profil:\n"
            "- Abgeschlossenes Studium der Informatik oder vergleichbare Qualifikation\n"
            "- 2+ Jahre Berufserfahrung in der Backend-Entwicklung\n"
            "- Sehr gute Kenntnisse in Python und SQL, Erfahrung mit Docker\n"
            "- Strukturierte, eigenverantwortliche Arbeitsweise und Teamfähigkeit\n"
            "- Gute Deutschkenntnisse (C1) und gute Englischkenntnisse (B2)\n\n"
            "Wir bieten flexible Arbeitszeiten, mobiles Arbeiten, Weiterbildungen und 30 Tage Urlaub."
        ),
    },
    {
        "id": "pflege",
        "label": "Pflegefachkraft Intensiv",
        "short": "Intensivpflege · Schichtdienst · Hamburg",
        "text": (
            "Gesundheits- und Krankenpfleger Intensivstation (m/w/d)\n"
            "Klinikum Hamburg – Hamburg · Vollzeit · Schichtdienst\n\n"
            "Für unsere interdisziplinäre Intensivstation suchen wir zum nächstmöglichen Zeitpunkt eine "
            "Pflegefachkraft zur Verstärkung des Teams. Du übernimmst die pflegerische Versorgung von "
            "Intensivpatient:innen, überwachst Vitalparameter und dokumentierst Pflegeleistungen.\n\n"
            "Deine Aufgaben:\n"
            "- Überwachung und Versorgung von Intensivpatient:innen\n"
            "- Assistenz bei ärztlichen Maßnahmen und Notfallversorgung\n"
            "- Dokumentation und interdisziplinäre Zusammenarbeit\n\n"
            "Dein Profil:\n"
            "- Abgeschlossene Ausbildung als Gesundheits- und Krankenpfleger:in oder Pflegefachfrau/-mann\n"
            "- Berufserfahrung in der Intensivpflege wünschenswert\n"
            "- Kenntnisse in der Intensivüberwachung und Beatmungspflege\n"
            "- Einfühlungsvermögen, Zuverlässigkeit und Teamfähigkeit\n"
            "- Deutschkenntnisse C1 in Wort und Schrift erforderlich\n\n"
            "Wir bieten ein unbefristetes Arbeitsverhältnis, Zuschuss zum Deutschlandticket, "
            "betriebliches Gesundheitsmanagement und strukturierte Einarbeitung."
        ),
    },
    {
        "id": "kaufmännisch",
        "label": "Sachbearbeiter Einkauf",
        "short": "Einkauf, SAP, MS Office · Teilzeit möglich",
        "text": (
            "Sachbearbeiter Einkauf (m/w/d) – Schwerpunkt Beschaffung\n"
            "Mittelständisches Industrieunternehmen · Köln · Vollzeit oder Teilzeit (30–35 Stunden/Woche) · Hybrid möglich\n\n"
            "Zur Verstärkung unseres Einkaufsteams suchen wir eine organisierte und kommunikationsstarke "
            "Persönlichkeit. Du verantwortest die operative Beschaffung und pflegst den Kontakt zu Lieferanten.\n\n"
            "Deine Aufgaben:\n"
            "- Operative Beschaffung von Rohstoffen und Dienstleistungen\n"
            "- Verhandlungen mit Lieferanten und Pflege von Rahmenverträgen\n"
            "- Stammdatenpflege und Bestellabwicklung in SAP\n"
            "- Erstellung von Auswertungen in MS-Excel\n\n"
            "Dein Profil:\n"
            "- Abgeschlossene kaufmännische Ausbildung, z. B. Industriekaufmann/-frau oder vergleichbar\n"
            "- 3 Jahre Berufserfahrung im Einkauf oder in der Beschaffung\n"
            "- Sicherer Umgang mit SAP und MS Office, insbesondere Excel\n"
            "- Verhandlungsgeschick, Kommunikationsstärke und analytisches Denken\n"
            "- Gute Deutschkenntnisse (C1) und Englischkenntnisse (B1) von Vorteil\n\n"
            "Wir bieten flexible Arbeitszeiten, mobiles Arbeiten, 30 Tage Urlaub und Weiterbildungen."
        ),
    },
]

# Schneller Zugriff per ID
EXAMPLE_BY_ID = {ex["id"]: ex for ex in EXAMPLES}
