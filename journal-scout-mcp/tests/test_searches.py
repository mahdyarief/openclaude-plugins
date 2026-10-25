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
    search_id = await _cache(fake).record_search(
        "graph neural networks",
        author="Alice",
        sources=["arxiv"],
        filters={"year_from": 2020},
        result_count=7,
        results=[{"doi": "10.1/a", "title": "A"}],
    )

    assert len(fake.calls) == 1
    sql, args = fake.calls[0]
    assert sql.startswith("INSERT INTO searches")
    assert "fingerprint" in sql
    assert isinstance(args, list) and len(args) == 9

    # Every user-supplied value travels as a bound parameter, not as SQL text.
    for value in ("graph neural networks", "Alice", "2020"):
        assert value not in sql
    assert args[0] == search_id
    assert args[1] == "graph neural networks"
    assert args[2] == "Alice"
    assert '[["arxiv"]]' not in sql
    assert args[3] == '["arxiv"]'
    assert args[4] == '{"year_from": 2020}'
    assert args[5] == 7
    assert isinstance(args[6], float)
    assert args[7] == '[{"doi": "10.1/a", "title": "A"}]'
    # Without a fingerprint the row is a plain append.
    assert args[8] is None


async def test_record_search_without_results_stores_null_payload():
    fake = FakeTurso()
    await _cache(fake).record_search("q")
    assert fake.calls[0][1][7] is None


async def test_record_search_returns_none_on_error():
    fake = FakeTurso(error=RuntimeError("turso down"))
    assert await _cache(fake).record_search("q") is None


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
            "size_bytes",
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
                512,
            ],
            [
                "a",
                "older query",
                "Alice",
                '["crossref"]',
                '{"year_to": 2019}',
                2,
                100.0,
                128,
            ],
        ],
    )

    result = await _cache(fake).list_searches(limit=5)

    sql, args = fake.calls[0]
    assert "FROM searches ORDER BY created_at DESC LIMIT ?" in sql
    assert "LENGTH(results) AS size_bytes" in sql
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
        "size_bytes",
        "age_seconds",
    ]
    assert result[0]["sources"] == ["arxiv", "openalex"]
    assert result[0]["filters"] == {"year_from": 2021}
    assert result[0]["author"] is None
    assert result[0]["size_bytes"] == 512
    assert isinstance(result[0]["age_seconds"], float)
    assert result[1]["sources"] == ["crossref"]
    assert result[1]["filters"] == {"year_to": 2019}
    assert result[1]["author"] == "Alice"
    assert result[1]["size_bytes"] == 128


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
            "size_bytes",
        ],
        rows=[["a", "q", None, "not json", None, 0, 1.0, 0]],
    )

    result = await _cache(fake).list_searches()

    assert result[0]["sources"] == "not json"
    assert result[0]["filters"] is None


async def test_get_search_returns_archived_results():
    fake = FakeTurso(
        columns=[
            "id", "query", "author", "sources", "filters",
            "result_count", "created_at", "results",
        ],
        rows=[[
            "abc", "graphene", None, '["arxiv"]', None, 1, 100.0,
            '[{"doi": "10.1/a", "title": "A"}]',
        ]],
    )

    row = await _cache(fake).get_search("abc")

    sql, args = fake.calls[0]
    assert "FROM searches WHERE id = ?" in sql
    assert args == ["abc"]
    assert row["id"] == "abc"
    assert row["results"] == [{"doi": "10.1/a", "title": "A"}]
    assert row["sources"] == ["arxiv"]


async def test_get_search_returns_none_when_missing():
    fake = FakeTurso(columns=[], rows=[])
    assert await _cache(fake).get_search("nope") is None


async def test_setup_adds_fingerprint_column_for_dedup():
    fake = FakeTurso()
    await _cache(fake).setup()

    sql_text = "\n".join(sql for sql, _ in fake.calls)
    assert "ALTER TABLE searches ADD COLUMN fingerprint TEXT" in sql_text
    assert "idx_searches_fingerprint" in sql_text


async def test_record_search_updates_the_existing_row_for_a_known_fingerprint():
    fake = FakeTurso(rows=[["existing-id"]])

    search_id = await _cache(fake).record_search(
        "machine learning",
        sources=["garuda"],
        filters={"year_from": 2020},
        result_count=9,
        results=[{"title": "A"}],
        fingerprint="fp-1",
    )

    assert search_id == "existing-id"
    select_sql, select_args = fake.calls[0]
    assert "SELECT id FROM searches WHERE fingerprint = ?" in select_sql
    assert select_args == ["fp-1"]

    update_sql, update_args = fake.calls[1]
    assert update_sql.startswith("UPDATE searches SET")
    assert "WHERE id = ?" in update_sql
    assert update_args[-1] == "existing-id"
    assert not any(sql.startswith("INSERT INTO searches") for sql, _ in fake.calls)


async def test_record_search_inserts_when_the_fingerprint_is_new():
    fake = FakeTurso(rows=[])

    search_id = await _cache(fake).record_search(
        "machine learning",
        sources=["garuda"],
        result_count=9,
        fingerprint="fp-new",
    )

    assert search_id
    insert_sql, insert_args = fake.calls[-1]
    assert insert_sql.startswith("INSERT INTO searches")
    assert "fp-new" in insert_args


async def test_record_search_without_fingerprint_still_appends():
    """Explicit writes (split/import) must keep creating new rows."""
    fake = FakeTurso(rows=[["existing-id"]])

    await _cache(fake).record_search("q")

    assert len(fake.calls) == 1
    assert fake.calls[0][0].startswith("INSERT INTO searches")


async def test_get_search_returns_none_on_error():
    fake = FakeTurso(error=RuntimeError("turso down"))
    assert await _cache(fake).get_search("abc") is None


async def test_delete_search_removes_the_row_and_reports_found():
    fake = FakeTurso(rows=[["abc"]])

    deleted = await _cache(fake).delete_search("abc")

    assert deleted is True
    select_sql, select_args = fake.calls[0]
    assert "SELECT id FROM searches WHERE id = ?" in select_sql
    assert select_args == ["abc"]
    delete_sql, delete_args = fake.calls[1]
    assert delete_sql.startswith("DELETE FROM searches WHERE id = ?")
    assert delete_args == ["abc"]


async def test_delete_search_reports_missing_row_without_deleting():
    fake = FakeTurso(rows=[])

    deleted = await _cache(fake).delete_search("nope")

    assert deleted is False
    assert len(fake.calls) == 1
    assert not any(sql.startswith("DELETE") for sql, _ in fake.calls)


async def test_import_search_inserts_new_row():
    fake = FakeTurso()
    archive = {"format": "josc-search-archive", "version": 1}
    search_id = await _cache(fake).import_search(
        archive,
        query="graphene",
        sources=["arxiv"],
        results=[{"doi": "10.1/a"}],
        result_count=1,
    )

    assert search_id
    sql, args = fake.calls[0]
    assert sql.startswith("INSERT INTO searches")
    assert args[0] == search_id
    assert args[1] == "graphene"
    assert args[5] == 1
    assert args[7] == '[{"doi": "10.1/a"}]'
