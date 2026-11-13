import httpx

from josc.providers.pubmed import PubMedProvider

ESEARCH_XML = """<?xml version="1.0" encoding="UTF-8"?>
<PubmedArticleSet>
  <PubmedArticle>
    <MedlineCitation>
      <PMID>123</PMID>
      <Article>
        <ArticleTitle>Long Short-Term Memory</ArticleTitle>
        <Abstract>
          <AbstractText>We propose LSTM.</AbstractText>
          <AbstractText>It works well.</AbstractText>
        </Abstract>
        <Journal>
          <JournalIssue>
            <PubDate>
              <Year>1997</Year>
            </PubDate>
          </JournalIssue>
          <Title>Neural Computation</Title>
        </Journal>
        <AuthorList>
          <Author>
            <LastName>Hochreiter</LastName>
            <ForeName>Sepp</ForeName>
          </Author>
          <Author>
            <LastName>Schmidhuber</LastName>
            <ForeName>Jurgen</ForeName>
          </Author>
        </AuthorList>
        <ELocationID EIdType="doi">10.1162/neco.1997.9.8.1735</ELocationID>
      </Article>
    </MedlineCitation>
  </PubmedArticle>
  <PubmedArticle>
    <MedlineCitation>
      <PMID>456</PMID>
      <Article>
        <ArticleTitle>Attention Is All You Need</ArticleTitle>
        <Journal>
          <JournalIssue>
            <PubDate>
              <MedlineDate>2017 Jan-Feb</MedlineDate>
            </PubDate>
          </JournalIssue>
          <Title>Advances in Neural Information Processing Systems</Title>
        </Journal>
        <AuthorList>
          <Author>
            <LastName>Vaswani</LastName>
            <ForeName>Ashish</ForeName>
          </Author>
        </AuthorList>
      </Article>
    </MedlineCitation>
    <PubmedData>
      <ArticleIdList>
        <ArticleId IdType="doi">10.5555/attention</ArticleId>
      </ArticleIdList>
    </PubmedData>
  </PubmedArticle>
</PubmedArticleSet>
"""


def _router(esearch_payload, efetch_xml=ESEARCH_XML, captured=None):
    def handler(request):
        url = str(request.url)
        if "esearch.fcgi" in url:
            if captured is not None:
                captured["term"] = request.url.params.get("term")
                captured["esearch_calls"] = captured.get("esearch_calls", 0) + 1
            return httpx.Response(200, json=esearch_payload)
        if "efetch.fcgi" in url:
            if captured is not None:
                captured["id"] = request.url.params.get("id")
                captured["efetch_calls"] = captured.get("efetch_calls", 0) + 1
            return httpx.Response(200, text=efetch_xml)
        return httpx.Response(404)

    return handler


async def test_search_maps_articles_to_papers(make_fetcher):
    captured = {}
    fetcher = make_fetcher(
        _router({"esearchresult": {"idlist": ["123", "456"]}}, captured=captured)
    )
    provider = PubMedProvider(fetcher)
    try:
        papers = await provider.search("long short-term memory", 5)
        assert len(papers) == 2
        first, second = papers
        assert first.doi == "10.1162/neco.1997.9.8.1735"
        assert first.year == 1997
        assert first.title == "Long Short-Term Memory"
        assert first.abstract == "We propose LSTM. It works well."
        assert first.authors == ["Hochreiter Sepp", "Schmidhuber Jurgen"]
        assert first.venue == "Neural Computation"
        assert first.sources == ["pubmed"]
        assert first.ids["pubmed"] == "123"
        assert second.doi == "10.5555/attention"
        assert second.year == 2017
        assert captured["id"] == "123,456"
    finally:
        await fetcher.close()


async def test_search_author_sends_author_term(make_fetcher):
    captured = {}
    fetcher = make_fetcher(
        _router({"esearchresult": {"idlist": []}}, captured=captured)
    )
    provider = PubMedProvider(fetcher)
    try:
        papers = await provider.search_author("Vaswani", 5)
        assert papers == []
        assert '"Vaswani"[Author]' in captured["term"]
    finally:
        await fetcher.close()


async def test_get_with_pmid_uses_efetch_directly(make_fetcher):
    captured = {}
    fetcher = make_fetcher(
        _router({"esearchresult": {"idlist": []}}, captured=captured)
    )
    provider = PubMedProvider(fetcher)
    try:
        paper = await provider.get("123")
        assert paper is not None
        assert paper.ids["pubmed"] == "123"
        assert captured.get("esearch_calls", 0) == 0
        assert captured["id"] == "123"
    finally:
        await fetcher.close()


async def test_empty_idlist_returns_empty(make_fetcher):
    fetcher = make_fetcher(_router({"esearchresult": {"idlist": []}}))
    provider = PubMedProvider(fetcher)
    try:
        assert await provider.search("nothing matches", 5) == []
    finally:
        await fetcher.close()


PLACEHOLDER_TITLE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<PubmedArticleSet>
  <PubmedArticle>
    <MedlineCitation>
      <PMID>999</PMID>
      <Article>
        <ArticleTitle>[Not Available].</ArticleTitle>
        <VernacularTitle>Utilisation des données probantes</VernacularTitle>
        <Journal>
          <JournalIssue>
            <PubDate>
              <Year>2024</Year>
            </PubDate>
          </JournalIssue>
          <Title>Revue Example</Title>
        </Journal>
      </Article>
    </MedlineCitation>
  </PubmedArticle>
</PubmedArticleSet>
"""


MESH_AND_KEYWORD_XML = """<?xml version="1.0" encoding="UTF-8"?>
<PubmedArticleSet>
  <PubmedArticle>
    <MedlineCitation>
      <PMID>777</PMID>
      <Article>
        <ArticleTitle>Data quality in practice</ArticleTitle>
        <Journal>
          <JournalIssue>
            <PubDate><Year>2022</Year></PubDate>
          </JournalIssue>
          <Title>Journal of Data</Title>
        </Journal>
        <PublicationTypeList>
          <PublicationType>Review</PublicationType>
          <PublicationType>Journal Article</PublicationType>
        </PublicationTypeList>
      </Article>
      <MeshHeadingList>
        <MeshHeading>
          <DescriptorName>Data Accuracy</DescriptorName>
        </MeshHeading>
        <MeshHeading>
          <DescriptorName>Information Storage and Retrieval</DescriptorName>
        </MeshHeading>
      </MeshHeadingList>
      <KeywordList>
        <Keyword>governance</Keyword>
        <Keyword>provenance</Keyword>
      </KeywordList>
    </MedlineCitation>
  </PubmedArticle>
</PubmedArticleSet>
"""


async def test_search_parses_mesh_keywords_and_publication_types(make_fetcher):
    # PubMed ships MeSH headings, author keywords and publication types in the
    # same XML response; they were being thrown away.
    fetcher = make_fetcher(
        _router({"esearchresult": {"idlist": ["777"]}}, efetch_xml=MESH_AND_KEYWORD_XML)
    )
    provider = PubMedProvider(fetcher)
    try:
        paper = (await provider.search("data quality", 5))[0]
        assert paper.keywords == ["governance", "provenance"]
        assert paper.topics == ["Data Accuracy", "Information Storage and Retrieval"]
        assert "Review" in paper.publication_types
    finally:
        await fetcher.close()


async def test_search_falls_back_to_vernacular_title(make_fetcher):
    fetcher = make_fetcher(
        _router({"esearchresult": {"idlist": ["999"]}}, efetch_xml=PLACEHOLDER_TITLE_XML)
    )
    provider = PubMedProvider(fetcher)
    try:
        papers = await provider.search("data quality", 5)
        assert papers[0].title == "Utilisation des données probantes"
    finally:
        await fetcher.close()
