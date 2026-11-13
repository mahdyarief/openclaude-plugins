from josc.providers.semanticscholar import SemanticScholarProvider


def test_s2_maps_fields_of_study():
    item = {
        "paperId": "abc",
        "title": "A paper",
        "year": 2021,
        "externalIds": {"DOI": "10.1/x"},
        "fieldsOfStudy": ["Computer Science", "Mathematics"],
        "s2FieldsOfStudy": [
            {"category": "Computer Science", "source": "external"},
            {"category": "Mathematics", "source": "s2-fos-model"},
        ],
    }

    paper = SemanticScholarProvider._to_paper(item)
    assert "Computer Science" in paper.topics
    assert "Mathematics" in paper.topics
    assert "s2:Computer Science" in paper.topic_ids
    assert "s2:Mathematics" in paper.topic_ids
