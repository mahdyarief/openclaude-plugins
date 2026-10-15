"""Reusable MCP prompt templates.

Prompts are declared as data (name -> spec) so adding one never touches the
server wiring; ``server.py`` only lists and renders whatever is registered
here. Each template composes the existing tools instead of duplicating
retrieval logic, which keeps the instructions consistent with what the
server can actually do.
"""
from typing import Any, Callable, Dict, List, Optional

import mcp.types as types

RenderFn = Callable[[Dict[str, Any]], str]


def _year_span(arguments: Dict[str, Any]) -> str:
    """Human-readable year bounds for a prompt, or ``""`` when unbounded."""
    lo, hi = arguments.get("year_from"), arguments.get("year_to")
    if lo and hi:
        return f" between {lo} and {hi}"
    if lo:
        return f" from {lo} onward"
    if hi:
        return f" up to {hi}"
    return ""


def _literature_review(arguments: Dict[str, Any]) -> str:
    topic = arguments.get("topic", "")
    return (
        f"Run a literature review on “{topic}”{_year_span(arguments)}.\n\n"
        "1. Call `search_all` with the topic and the year bounds to gather papers across sources.\n"
        "2. Cluster the merged results by theme; note venues and citation counts.\n"
        "3. Call `get_paper` on the central papers to pull full metadata and open-access links.\n"
        "4. Write up the state of the art: key groups, dominant venues, open questions — cite DOIs.\n"
    )


def _author_overview(arguments: Dict[str, Any]) -> str:
    author = arguments.get("author", "")
    return (
        f"Profile the research output of {author}{_year_span(arguments)}.\n\n"
        "1. Call `search_author` to collect their papers across every author-capable source.\n"
        "2. Call `scival_author_lookup` to resolve the Scopus author id, then "
        "`scival_author_metrics` for citation and h-index totals.\n"
        f"3. Summarise {author}'s main topics, most cited work, and publication venues.\n"
    )


def _citation_trace(arguments: Dict[str, Any]) -> str:
    identifier = arguments.get("identifier", "")
    return (
        f"Trace the citation impact of “{identifier}”.\n\n"
        "1. Call `get_paper` to resolve the record and confirm its DOI.\n"
        "2. Call `get_citations` to collect the citing papers across sources.\n"
        "3. Group the citing work by year and venue, and highlight the most influential follow-ups.\n"
    )


# name -> (title, description, arguments, renderer). Arguments are plain
# dicts so a new template never has to import MCP types directly.
_PROMPTS: Dict[str, tuple] = {
    "literature_review": (
        "Literature review",
        "Plan a multi-source literature review for a topic.",
        [
            {"name": "topic", "description": "Research topic or question.", "required": True},
            {"name": "year_from", "description": "Earliest publication year."},
            {"name": "year_to", "description": "Latest publication year."},
        ],
        _literature_review,
    ),
    "author_overview": (
        "Author overview",
        "Profile one author's papers, venues, and citation metrics.",
        [
            {"name": "author", "description": "Author name.", "required": True},
            {"name": "year_from", "description": "Earliest publication year."},
            {"name": "year_to", "description": "Latest publication year."},
        ],
        _author_overview,
    ),
    "citation_trace": (
        "Citation trace",
        "Trace who cites a paper and how it has been built upon.",
        [
            {"name": "identifier", "description": "DOI, arXiv, Scopus, or OpenAlex id.", "required": True},
        ],
        _citation_trace,
    ),
}


def list_prompts() -> List[types.Prompt]:
    return [
        types.Prompt(
            name=name,
            title=title,
            description=description,
            arguments=[
                types.PromptArgument(
                    name=arg["name"],
                    description=arg.get("description"),
                    required=bool(arg.get("required", False)),
                )
                for arg in arguments
            ],
        )
        for name, (title, description, arguments, _render) in _PROMPTS.items()
    ]


def render_prompt(name: str, arguments: Optional[Dict[str, Any]]) -> types.GetPromptResult:
    """Render ``name`` into a single user message, or raise if unknown."""
    entry = _PROMPTS.get(name)
    if entry is None:
        raise ValueError(f"Unknown prompt: {name}")
    _title, description, _arguments, render = entry
    text = render(arguments or {})
    return types.GetPromptResult(
        description=description,
        messages=[
            types.PromptMessage(role="user", content=types.TextContent(type="text", text=text))
        ],
    )
