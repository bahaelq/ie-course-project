"""Demo examples for the UI. They are synthetic and contain no personal data."""

from __future__ import annotations

EXAMPLES: list[dict[str, str]] = [
    {
        "id": "software",
        "label": "Backend Software Developer",
        "short": "Python, SQL, Docker · Hybrid · Berlin",
        "text": (
            "Backend Software Developer (m/f/d) – Python & Cloud\n"
            "Location: Berlin (Hybrid: 2 days on-site, 3 days remote) · Full-time · Permanent\n\n"
            "We are building a data-driven platform for industrial applications and are looking for you to "
            "strengthen our backend team. You will work closely with product and data science.\n\n"
            "Your responsibilities:\n"
            "- Developing and operating microservices in Python (FastAPI)\n"
            "- Designing and optimizing databases (PostgreSQL, SQL)\n"
            "- Containerization with Docker and deployment on Kubernetes\n"
            "- Code reviews, testing, and continuous improvement of the architecture\n\n"
            "Your profile:\n"
            "- Completed degree in computer science or comparable qualification\n"
            "- 2+ years of professional experience in backend development\n"
            "- Very good knowledge of Python and SQL, experience with Docker\n"
            "- Structured, self-directed way of working and team spirit\n"
            "- Good German skills (C1) and good English skills (B2)\n\n"
            "We offer flexible working hours, remote work, training opportunities, and 30 days of vacation."
        ),
    },
    {
        "id": "pflege",
        "label": "Intensive Care Nurse",
        "short": "Intensive care · Shift work · Hamburg",
        "text": (
            "Registered Nurse, Intensive Care Unit (m/f/d)\n"
            "Klinikum Hamburg – Hamburg · Full-time · Shift work\n\n"
            "For our interdisciplinary intensive care unit, we are looking for a nursing professional to join "
            "our team as soon as possible. You will provide nursing care for intensive care patients, monitor "
            "vital signs, and document nursing services.\n\n"
            "Your responsibilities:\n"
            "- Monitoring and caring for intensive care patients\n"
            "- Assisting with medical procedures and emergency care\n"
            "- Documentation and interdisciplinary collaboration\n\n"
            "Your profile:\n"
            "- Completed training as a registered nurse or equivalent nursing qualification\n"
            "- Professional experience in intensive care desirable\n"
            "- Knowledge of intensive care monitoring and ventilation care\n"
            "- Empathy, reliability, and team spirit\n"
            "- German language skills at C1 level, written and spoken, required\n\n"
            "We offer a permanent employment contract, a subsidy for the Deutschlandticket, "
            "occupational health management, and structured onboarding."
        ),
    },
    {
        "id": "purchasing",
        "label": "Purchasing Clerk",
        "short": "Purchasing, SAP, MS Office · Part-time possible",
        "text": (
            "Purchasing Clerk (m/f/d) – Procurement Focus\n"
            "Mid-sized industrial company · Cologne · Full-time or part-time (30–35 hours/week) · Hybrid possible\n\n"
            "To strengthen our purchasing team, we are looking for an organized and communicative "
            "personality. You will be responsible for operational procurement and maintain contact with suppliers.\n\n"
            "Your responsibilities:\n"
            "- Operational procurement of raw materials and services\n"
            "- Negotiations with suppliers and maintenance of framework agreements\n"
            "- Master data maintenance and order processing in SAP\n"
            "- Preparation of reports in MS Excel\n\n"
            "Your profile:\n"
            "- Completed commercial training, e.g. as an industrial clerk or comparable qualification\n"
            "- 3 years of professional experience in purchasing or procurement\n"
            "- Confident use of SAP and MS Office, especially Excel\n"
            "- Negotiation skills, strong communication, and analytical thinking\n"
            "- Good German skills (C1) and English skills (B1) are an advantage\n\n"
            "We offer flexible working hours, remote work, 30 days of vacation, and training opportunities."
        ),
    },
]

# Fast lookup by ID.
EXAMPLE_BY_ID = {ex["id"]: ex for ex in EXAMPLES}
