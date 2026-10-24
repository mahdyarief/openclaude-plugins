"""Search-history persistence on :class:`TursoCache`, exercised against a fake."""

from josc.store import TursoCache


class FakeTurso:
    """Records every ``(sql, args)`` pair; never touches the network."""

    def __init__(self, rows=None, columns=None, error=None):
        self.calls = []
        self.rows = rows or []
        self.columns = columns or []
        self.error = error

    async def execute(self, sql, args=None):
        self.calls.append((sql, args))
        if self.error is not None:
            raise self.error
        return self.columns, self.rows


def _cache(fake):
    return TursoCache(fake, ttl=60)


async def test_setup_creates_searches_table():
    fake = FakeTurso()
    await _cache(fake).setup()

    sql_text = "\n".join(sql for sql, _ in fake.calls)
    assert "CREATE TABLE IF NOT EXISTS searches" in sql_text
    assert "CREATE INDEX IF NOT EXISTS idx_searches_created" in sql_text
    # The pre-existing cache DDL must still be issued.
    assert "CREATE TABLE IF NOT EXISTS query_cache" in sql_text


async def test_record_search_uses_bound_parameters():
    fake = FakeTurso()
    await _cache(fake).record_search(
        "graph neural networks",
        author="Alice",
        sources=["arxiv"],
        filters={"year_from": 2020},
        result_count=7,
    )

    assert len(fake.calls) == 1
    sql, args = fake.calls[0]
    assert sql.startswith("INSERT INTO searches")
    assert isinstance(args, list) and len(args) == 7

    # Every user-supplied value travels as a bound parameter, not as SQL text.
    for value in ("graph neural networks", "Alice", "2020"):
        assert value not in sql
    assert args[1] == "graph neural networks"
    assert args[2] == "Alice"
    assert '[["arxiv"]]' not in sql
    assert args[3] == '["arxiv"]'
    assert args[4] == '{"year_from": 2020}'
    assert args[5] == 7
    assert isinstance(args[6], float)


async def test_record_search_swallows_errors():
    fake = FakeTurso(error=RuntimeError("turso down"))
    # Must not raise.
    await _cache(fake).record_search("anything", author="Alice")


async def test_list_searches_decodes_json_columns():
    fake = FakeTurso(
        columns=[
            "id",
            "query",
            "author",
            "sources",
            "filters",
            "result_count",
            "created_at",
        ],
        rows=[
            [
                "b",
                "newer query",
                None,
                '["arxiv", "openalex"]',
                '{"year_from": 2021}',
                4,
                200.0,
            ],
            [
                "a",
                "older query",
                "Alice",
                '["crossref"]',
                '{"year_to": 2019}',
                2,
                100.0,
            ],
        ],
    )

    result = await _cache(fake).list_searches(limit=5)

    sql, args = fake.calls[0]
    assert "FROM searches ORDER BY created_at DESC LIMIT ?" in sql
    assert args == [5]

    assert [row["query"] for row in result] == ["newer query", "older query"]
    assert list(result[0].keys()) == [
        "id",
        "query",
        "author",
        "sources",
        "filters",
        "result_count",
        "created_at",
    ]
    assert result[0]["sources"] == ["arxiv", "openalex"]
    assert result[0]["filters"] == {"year_from": 2021}
    assert result[0]["author"] is None
    assert result[1]["sources"] == ["crossref"]
    assert result[1]["filters"] == {"year_to": 2019}
    assert result[1]["author"] == "Alice"


async def test_list_searches_returns_empty_on_error():
    fake = FakeTurso(error=RuntimeError("turso down"))
    assert await _cache(fake).list_searches() == []


async def test_list_searches_tolerates_bad_json():
    fake = FakeTurso(
        columns=[
            "id",
            "query",
            "author",
            "sources",
            "filters",
            "result_count",
            "created_at",
        ],
        rows=[["a", "q", None, "not json", None, 0, 1.0]],
    )

    result = await _cache(fake).list_searches()

    assert result[0]["sources"] == "not json"
    assert result[0]["filters"] is None
