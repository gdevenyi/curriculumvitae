#!/usr/bin/env python3
"""Write pub_stats.tex with publication counts and citation metrics for the CV.

Counts come from the Paperpile-synced bib files. Citation metrics come from
OpenAlex (works linked to the ORCID below). The script also picks the
"selected publications" for the short CV: all first- and senior-author
papers plus the most-cited papers.

The CV reads the values with \\pubstat{<field>} and the list of selected
citation keys with \\selectedkeys. If OpenAlex fails, the counts are still
written and the citation fields keep their previous values.
"""

from __future__ import annotations

import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "pub_stats.tex"
ORCID = "0000-0002-7766-1187"
SURNAME = "Devenyi"
TOP_CITED = 10

BIBS = {
    "papers": "papers.bib",
    "preprints": "preprints.bib",
    "contributed": "contributed.bib",
    "invited": "invited.bib",
    "datasets": "datasets.bib",
    "patents": "patents.bib",
}


def entries(path: Path) -> list[str]:
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    return [e for e in re.split(r"\n(?=@)", text) if e.lstrip().startswith("@")]


def field(entry: str, name: str) -> str:
    m = re.search(
        rf"^\s*{name}\s*=\s*\{{(.*?)\}},?\s*$",
        entry,
        re.DOTALL | re.MULTILINE | re.IGNORECASE,
    )
    return re.sub(r"\s+", " ", m.group(1)).strip() if m else ""


def authors(entry: str) -> list[str]:
    raw = field(entry, "author")
    return [a.strip() for a in re.split(r"\s+and\s+", raw) if a.strip()]


def citekey(entry: str) -> str:
    return entry.split("{", 1)[1].split(",", 1)[0].strip()


def role(entry: str) -> str:
    """'first', 'senior' or '' for this entry."""
    names = authors(entry)
    if not names:
        return ""
    if names[0].startswith(SURNAME):
        return "first"
    # Senior only if last, and not listed as a consortium member
    # (a collective such as "{on behalf of ...}" before the name).
    if names[-1].startswith(SURNAME) and not any(n.startswith("{") for n in names):
        return "senior"
    return ""


def openalex(url: str, tries: int = 3) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "cv-stats-script"})
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.load(resp)
        except urllib.error.HTTPError:
            if attempt == tries - 1:
                raise
            time.sleep(5 * (attempt + 1))
    raise RuntimeError("unreachable")


def openalex_works() -> list[dict]:
    """The 200 most-cited works linked to the ORCID.

    One page sorted by citations is enough for an exact h-index and
    i10-index (both are far below 200), and needs no API key; OpenAlex
    asks for a key only for cursor paging.
    """
    q = urllib.parse.urlencode(
        {
            "filter": f"author.orcid:{ORCID}",
            "sort": "cited_by_count:desc",
            "per-page": 200,
            "select": "doi,cited_by_count",
        }
    )
    return openalex(f"https://api.openalex.org/works?{q}")["results"]


def openalex_citations() -> int:
    """Total citations over all OpenAlex author records linked to the ORCID."""
    q = urllib.parse.urlencode({"filter": f"orcid:{ORCID}", "select": "cited_by_count"})
    data = openalex(f"https://api.openalex.org/authors?{q}")
    return sum(a["cited_by_count"] for a in data["results"])


def old_values() -> dict[str, str]:
    if not OUTPUT.exists():
        return {}
    pat = r"\\expandafter\\def\\csname pub@(\w+)\\endcsname\{(.*)\}"
    return dict(re.findall(pat, OUTPUT.read_text(encoding="utf-8")))


def fmt(n: int) -> str:
    return f"{n:,}".replace(",", "{,}")


def main() -> int:
    stats = old_values()
    papers = entries(ROOT / BIBS["papers"])
    for key, name in BIBS.items():
        stats[key] = fmt(len(entries(ROOT / name)))
    roles = [role(e) for e in papers]
    stats["first"] = str(roles.count("first"))
    stats["senior"] = str(roles.count("senior"))

    selected = [citekey(e) for e, r in zip(papers, roles) if r]
    try:
        works = openalex_works()
        cites = sorted((w["cited_by_count"] for w in works), reverse=True)
        stats["citations"] = fmt(openalex_citations())
        stats["hindex"] = str(sum(1 for i, c in enumerate(cites, 1) if c >= i))
        stats["itenindex"] = str(sum(1 for c in cites if c >= 10))
        stats["citedate"] = date.today().strftime("%Y-%m")
        by_doi = {
            (w["doi"] or "").lower().removeprefix("https://doi.org/"): w[
                "cited_by_count"
            ]
            for w in works
        }
        ranked = sorted(
            papers,
            key=lambda e: -by_doi.get(field(e, "doi").lower(), 0),
        )
        for e in ranked:
            if (
                len([k for k in selected if k])
                >= len([r for r in roles if r]) + TOP_CITED
            ):
                break
            if citekey(e) not in selected:
                selected.append(citekey(e))
    except (
        urllib.error.URLError,
        TimeoutError,
        KeyError,
        ValueError,
        RuntimeError,
    ) as exc:
        print(f"warning: OpenAlex not updated ({exc})", file=sys.stderr)

    lines = [
        "% Generated by scripts/pub_stats.py -- do not edit by hand.",
        "% Read with \\pubstat{<field>}; \\selectedkeys lists the short-CV papers.",
    ]
    for key in sorted(stats):
        lines.append(f"\\expandafter\\def\\csname pub@{key}\\endcsname{{{stats[key]}}}")
    lines.append(f"\\def\\selectedkeys{{{','.join(selected)}}}")
    OUTPUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {OUTPUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
