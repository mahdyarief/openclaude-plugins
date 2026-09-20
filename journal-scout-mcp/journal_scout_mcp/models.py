from dataclasses import dataclass, field


@dataclass
class Paper:
    doi: str | None = None
    title: str = ""
    abstract: str | None = None
    year: int | None = None
    authors: list[str] = field(default_factory=list)
    venue: str | None = None
    citation_count: int | None = None
    url: str | None = None
    pdf_url: str | None = None
    is_open_access: bool | None = None
    type: str | None = None
    sources: list[str] = field(default_factory=list)
    ids: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "doi": self.doi,
            "title": self.title,
            "abstract": self.abstract,
            "year": self.year,
            "authors": self.authors,
            "venue": self.venue,
            "citation_count": self.citation_count,
            "url": self.url,
            "pdf_url": self.pdf_url,
            "is_open_access": self.is_open_access,
            "type": self.type,
            "sources": self.sources,
            "ids": self.ids,
        }


class ProviderError(Exception):
    def __init__(self, provider: str, message: str):
        self.provider = provider
        self.message = message
        super().__init__(f"[{provider}] {message}")