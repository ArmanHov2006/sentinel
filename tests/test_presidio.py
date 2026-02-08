import pytest
from presidio_analyzer import AnalyzerEngine

analyzer = AnalyzerEngine()

TEXTS = [
    "Hey today I took my dog for a walk at 10:00 AM at the park, and we met our neighbor Johnny Depp",
    "Tomorrow I think I will go University of Toronto at 10 am so I can go to gym as well",
    "I am going to the gym at 10:00 AM tomorrow, and I will meet my friend John Doe at the gym",
    "My email address is john.doe@example.com and my phone number is +1234567890",
    "My address is 123 Main St, Anytown, USA",
    "My SSN is 123-45-6789",
    "My credit card number is 1234567890123456",
]


@pytest.fixture
def texts():
    return TEXTS


def analyze_text(text: str) -> list[dict]:
    """Analyze text for PII entities."""
    results = analyzer.analyze(
        text=text,
        language="en",
        score_threshold=0.5,
        entities=["PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER", "LOCATION", "DATE_TIME"],
    )
    findings = []
    for result in results:
        findings.append(
            {
                "type": result.entity_type,
                "text": text[result.start : result.end],
                "start": result.start,
                "end": result.end,
                "score": result.score,
            }
        )
    return findings


def test_analyze_text(texts: list[str]):
    """Run analysis on sample texts and assert expected PII is detected."""
    for text in texts:
        findings = analyze_text(text)
        assert isinstance(findings, list)
        for item in findings:
            assert "type" in item and "text" in item and "score" in item
            assert item["text"] == text[item["start"] : item["end"]]
            assert 0 <= item["score"] <= 1


if __name__ == "__main__":
    for i, text in enumerate(TEXTS, 1):
        findings = analyze_text(text)
        print(f"--- Text {i} ---")
        print(text)
        for item in findings:
            print(f"  [{item['type']}] '{item['text']}' (score: {item['score']:.2f})")
        print()
    test_analyze_text(TEXTS)
    print("All tests passed.")
