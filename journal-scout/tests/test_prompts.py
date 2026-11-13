from josc import prompts


def test_list_prompts_exposes_registered_templates():
    listed = prompts.list_prompts()
    names = {p.name for p in listed}
    assert {"literature_review", "author_overview", "citation_trace"} <= names
    for prompt in listed:
        assert prompt.name
        assert prompt.description


def test_list_prompts_marks_required_arguments():
    listed = {p.name: p for p in prompts.list_prompts()}
    review = listed["literature_review"]
    by_name = {a.name: a for a in (review.arguments or [])}
    assert by_name["topic"].required is True
    assert by_name["year_from"].required is False


def test_render_prompt_returns_single_user_message():
    result = prompts.render_prompt(
        "literature_review", {"topic": "graph neural networks", "year_from": 2020}
    )
    assert result.description
    assert len(result.messages) == 1
    message = result.messages[0]
    assert message.role == "user"
    text = message.content.text
    assert "graph neural networks" in text
    assert "2020" in text
    # The template must compose real tools rather than invent tool names.
    assert "search_all" in text


def test_render_author_overview_composes_author_tools():
    result = prompts.render_prompt("author_overview", {"author": "Ashish Vaswani"})
    text = result.messages[0].content.text
    assert "Ashish Vaswani" in text
    assert "search_author" in text


def test_render_prompt_accepts_missing_optional_arguments():
    result = prompts.render_prompt("citation_trace", {"identifier": "10.1162/neco.1997.9.8.1735"})
    text = result.messages[0].content.text
    assert "10.1162/neco.1997.9.8.1735" in text


def test_render_unknown_prompt_raises():
    try:
        prompts.render_prompt("nope", {})
    except ValueError as e:
        assert "Unknown prompt" in str(e)
    else:
        raise AssertionError("expected ValueError")
