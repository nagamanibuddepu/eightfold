"""Deterministic weights and normalization aliases."""

SOURCE_RELIABILITY = {
    "resume": 1.00,
    "ats_json": 0.85,
    "recruiter_csv": 0.70,
    "recruiter_notes": 0.50,
    "github": 0.40,
}

SOURCE_PRIORITY = {
    "resume": 0,
    "ats_json": 1,
    "recruiter_csv": 2,
    "recruiter_notes": 3,
    "github": 4,
}

CONFLICT_PENALTY = 0.25
AGREEMENT_BONUS = 0.15

SKILL_ALIASES = {
    "py": "python",
    "python3": "python",
    "reactjs": "react",
    "react.js": "react",
    "js": "javascript",
    "node.js": "node",
    "postgresql": "postgres",
    "postgres sql": "postgres",
    "ml": "machine learning",
    "machine-learning": "machine learning",
    "data pipelines": "data pipeline",
}
