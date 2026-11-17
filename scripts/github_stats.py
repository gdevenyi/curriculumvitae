#!/usr/bin/env python3
"""Write software_stats.tex with live GitHub and PyPI numbers for the CV.

The CV reads the values with \\swstat{<key>}{<field>}, for example
\\swstat{CoBrALab/qbatch}{stars}. Run with a GitHub token in GITHUB_TOKEN
(CI) or with a logged-in `gh` CLI (local). If any request fails, the script
keeps the old file and exits 0, so the CV still builds with the last values.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

USER = "gdevenyi"
OUTPUT = Path(__file__).resolve().parent.parent / "software_stats.tex"

# Repositories that the CV shows, with the stats each one needs.
REPOS = [
    "CoBrALab/optimized_antsMultivariateTemplateConstruction",
    "CoBrALab/qbatch",
    "CoBrALab/twolevel_ants_dbm",
    "CoBrALab/libBIDS.sh",
    "CoBrALab/minc-toolkit-extras",
    "CoBrALab/atlases",
    "CoBrALab/iterativeN3",
    "Gabriel-Devenyi-Consulting/NeuroAnsible",
    "DouglasNeuroInformatics/OpenDataCapture",
    "DouglasNeuroInformatics/DataBank",
    "DouglasNeuroInformatics/ansible-playbooks",
    "ANTsX/ANTs",
    "BIC-MNI/minc-toolkit-v2",
    "CoBrALab/RABIES",
    "CoBrALab/MAGeTbrain",
]
PYPI = ["qbatch"]
TEAM_ORG = "DouglasNeuroInformatics"
# Organizations that count as "own" when counting upstream contributions.
OWN_ORGS = [
    "CoBrALab",
    "DouglasNeuroInformatics",
    "Douglas-Cerebral-Imaging-Centre",
    "Gabriel-Devenyi-Consulting",
    "clinivance",
    "neuralabc",
    "pondrai",
]


def token() -> str:
    tok = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if tok:
        return tok
    return subprocess.run(
        ["gh", "auth", "token"], capture_output=True, text=True, check=True
    ).stdout.strip()


TOKEN = ""


def get(url: str, headers: dict | None = None) -> tuple[object, dict]:
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp), dict(resp.headers)


def gh(path: str, **params) -> tuple[object, dict]:
    url = f"https://api.github.com/{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    return get(
        url,
        {
            "Authorization": f"Bearer {TOKEN}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "cv-stats-script",
        },
    )


def gh_all(path: str, **params) -> list:
    """Fetch every page of a list endpoint."""
    items: list = []
    page = 1
    while True:
        data, _ = gh(path, per_page=100, page=page, **params)
        items.extend(data)
        if len(data) < 100:
            return items
        page += 1


def search_count(query: str) -> int:
    data, _ = gh("search/issues", q=query, per_page=1)
    return data["total_count"]


def search_repos(query: str) -> set[str]:
    """Distinct repositories of the issues/PRs matching a search (max 1000 hits)."""
    repos: set[str] = set()
    for page in range(1, 11):
        data, _ = gh("search/issues", q=query, per_page=100, page=page)
        for item in data["items"]:
            repos.add(item["repository_url"].split("/repos/", 1)[1])
        if len(data["items"]) < 100:
            break
    return repos


def graphql(query: str) -> dict:
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query}).encode(),
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "User-Agent": "cv-stats-script",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        out = json.load(resp)
    if "errors" in out:
        raise RuntimeError(out["errors"])
    return out["data"]


def fmt(n: int) -> str:
    return f"{n:,}".replace(",", "{,}")


def collect() -> dict[str, dict[str, str]]:
    stats: dict[str, dict[str, str]] = {}

    for repo in REPOS:
        info, _ = gh(f"repos/{repo}")
        contributors = gh_all(f"repos/{repo}/contributors")
        total = sum(c["contributions"] for c in contributors)
        ranked = sorted(contributors, key=lambda c: -c["contributions"])
        rank, mine = 0, 0
        for i, c in enumerate(ranked, 1):
            if c["login"].lower() == USER:
                rank, mine = i, c["contributions"]
        releases = gh_all(f"repos/{repo}/releases")
        stats[repo] = {
            "stars": fmt(info["stargazers_count"]),
            "forks": fmt(info["forks_count"]),
            "contributors": fmt(len(contributors)),
            "commits": fmt(mine),
            "totalcommits": fmt(total),
            "rank": str(rank) if rank else "--",
            "releases": fmt(len(releases)),
        }

    for pkg in PYPI:
        data, _ = get(f"https://pypistats.org/api/packages/{pkg}/recent")
        stats[f"pypi/{pkg}"] = {"month": fmt(data["data"]["last_month"])}

    org_repos = gh_all(f"orgs/{TEAM_ORG}/repos", type="public")
    stats[f"org/{TEAM_ORG}"] = {
        "repos": fmt(len(org_repos)),
        "stars": fmt(sum(r["stargazers_count"] for r in org_repos)),
    }

    merged = f"author:{USER} type:pr is:merged"
    external = merged + f" -user:{USER}" + "".join(f" -org:{o}" for o in OWN_ORGS)
    user = graphql(
        f'{{user(login:"{USER}"){{repositoriesContributedTo('
        "contributionTypes:[COMMIT,PULL_REQUEST,ISSUE,REPOSITORY]){totalCount}}}"
    )["user"]
    stats["user"] = {
        "mergedprs": fmt(search_count(merged)),
        "externalprs": fmt(search_count(external)),
        "externalprojects": fmt(len(search_repos(external))),
        "contributedrepos": fmt(user["repositoriesContributedTo"]["totalCount"]),
    }
    return stats


def write(stats: dict[str, dict[str, str]]) -> None:
    lines = [
        "% Generated by scripts/github_stats.py -- do not edit by hand.",
        "% Read with \\swstat{<key>}{<field>}.",
    ]
    for key in sorted(stats):
        for field, value in sorted(stats[key].items()):
            lines.append(
                f"\\expandafter\\def\\csname sw@{key}@{field}\\endcsname{{{value}}}"
            )
    OUTPUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    global TOKEN
    try:
        TOKEN = token()
        stats = collect()
    except (
        urllib.error.URLError,
        TimeoutError,
        KeyError,
        RuntimeError,
        ValueError,
        subprocess.CalledProcessError,
    ) as exc:  # keep the last good file
        print(f"warning: stats not updated ({exc})", file=sys.stderr)
        return 0
    write(stats)
    print(f"wrote {OUTPUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
