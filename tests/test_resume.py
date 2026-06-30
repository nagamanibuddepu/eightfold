"""Tests for the resume parser adapter."""

from candidate_transformer.adapters.resume_adapter import parse_resume


def test_parse_resume_pdf() -> None:
    """pdfplumber extracts contact, skills, and education from the real resume PDF."""

    output = parse_resume("sample_data/resume.pdf")
    fields = output[0].fields

    assert output[0].method == "resume_pdf_parse"
    assert not output[0].issues
    assert fields["full_name"] == "Nagamani Buddepu"
    assert "mbuddepu0827@gmail.com" in fields["emails"]
    assert "9398172938" in fields["phones"][0]
    assert "python" in {skill.lower() for skill in fields["skills"]}
    assert fields["education"]
    assert fields["education"][0]["end_year"] == 2027


def test_parse_resume_rejects_non_pdf() -> None:
    output = parse_resume("sample_data/recruiter_notes.txt")
    assert output[0].issues
    assert "unsupported resume format" in output[0].issues[0].message


def test_parse_resume_handles_pdf_errors(monkeypatch) -> None:
    def raise_runtime_error(*_args, **_kwargs):
        raise RuntimeError("pdf extraction failed")

    monkeypatch.setattr("candidate_transformer.adapters.resume_adapter.pdfplumber.open", raise_runtime_error)
    output = parse_resume("sample_data/resume.pdf")

    assert output[0].source_type == "resume"
    assert output[0].issues
    assert "could not read resume" in output[0].issues[0].message
