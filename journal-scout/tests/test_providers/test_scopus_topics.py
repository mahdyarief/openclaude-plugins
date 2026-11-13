import httpx

from josc.providers.scopus import ScopusProvider


async def test_scopus_maps_subject_area_and_authkeywords():
    entry = {
        "dc:identifier": "Scopus:2-s2.0-123",
        "prism:doi": "10.1/x",
        "dc:title": "A paper",
        "prism:coverDate": "2020-01-01",
        "citedby-count": "10",
        "subtypeDescription": "Article",
        "subject-area": [
            {"@abbrev": "COMP", "code": "1700", "$": "Computer Science"},
            {"@abbrev": "ENGI", "code": "2200", "$": "Engineering"},
        ],
        "authkeywords": [
            {"@xml:lang": "eng", "$": "deep learning"},
            {"@xml:lang": "eng", "$": "optimization"},
        ],
    }

    paper = ScopusProvider._to_paper(entry)
    assert "Computer Science" in paper.topics
    assert "Engineering" in paper.topics
    assert "1700" in paper.topic_ids
    assert "deep learning" in paper.keywords
    assert "optimization" in paper.keywords
