from josc.fulltext import build_index, search_index, tokenize


def test_tokenize_lowercases_and_drops_short_tokens():
    assert tokenize("Deep Learning: A Survey!") == ["deep", "learning", "survey"]


def test_tokenize_handles_punctuation_and_numbers():
    assert tokenize("BERT-2 vs GPT3, 2023") == ["bert", "gpt3", "2023"]


def test_tokenize_returns_empty_list_for_blank_input():
    assert tokenize("   ") == []


def test_build_index_maps_tokens_to_paper_positions():
    papers = [
        {"title": "Deep Learning"},
        {"title": "Deep Reinforcement Learning"},
    ]
    index = build_index(papers)
    assert index["deep"] == [0, 1]
    assert index["reinforcement"] == [1]


def test_search_index_requires_every_token():
    papers = [
        {"title": "Deep Learning", "abstract": "neural networks"},
        {"title": "Deep Learning", "abstract": "bayesian inference"},
    ]
    index = build_index(papers)
    hits = search_index(index, papers, "deep bayesian")
    assert len(hits) == 1
    assert hits[0]["abstract"] == "bayesian inference"


def test_search_index_returns_empty_for_unknown_token():
    papers = [{"title": "Deep Learning"}]
    assert search_index(build_index(papers), papers, "quantum") == []


def test_search_index_ranks_more_matches_higher():
    papers = [
        {"title": "Learning", "abstract": "learning learning"},
        {"title": "Learning", "abstract": "learning once"},
    ]
    index = build_index(papers)
    hits = search_index(index, papers, "learning")
    assert hits[0]["abstract"] == "learning learning"
