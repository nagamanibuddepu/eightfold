# Assumptions and Scope

- Sample ATS, CSV, notes, and GitHub cache data are fictitious. `sample_data/resume.pdf` is the submitter's real resume PDF.
- The default phone region is `US` unless the CLI caller passes `--default-region`.
- A source can be malformed, empty, or missing. The run continues when another source can still establish identity.
- Identity resolution never merges on name alone because that risks wrong-but-confident output.
- GitHub data is treated as inferred evidence. It can add skills, links, and bio/headline evidence, but it does not establish identity and does not override claimed ATS/recruiter fields.
- The GitHub adapter accepts a profile URL and calls the public REST API for user and repository data. A cache file is only a fallback for rate limits, network failures, or deterministic demos.
- LinkedIn live fetching is out of scope because public scraping/API access is not reliable for a take-home assignment.
- Resume parsing uses `pdfplumber` to extract text from `sample_data/resume.pdf`, then applies conservative regex/heuristic field extraction. Complex PDF layouts may yield partial fields; structured ATS JSON still supplies experience when resume lines are hard to parse.
- Confidence weights are explainable heuristics, not empirically trained probabilities.
- The repository optimizes for correctness, readability, and interview explainability over framework abstraction.
