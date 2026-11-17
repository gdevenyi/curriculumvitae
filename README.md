# curriculumvitae

Source files and the latest PDFs of my curriculum vitae.

- [`cv.pdf`](cv.pdf) — full CV
- [`cv-short.pdf`](cv-short.pdf) — short CV (about 4 pages)

Both PDFs are rebuilt by GitHub Actions on every push to `master` and
committed back to the repository.

## How it works

| Part | Source |
|---|---|
| Text and layout | `cv.tex` (`cv-short.tex` sets `\shortcv` and inputs `cv.tex`) |
| Publications | Paperpile folders, exported to this repository by Paperpile Bot |
| Software statistics | `scripts/github_stats.py` → `software_stats.tex` |
| Publication counts and citation metrics | `scripts/pub_stats.py` → `pub_stats.tex` |

### Paperpile export

Each folder under *My Publications* in Paperpile has a BibTeX export workflow
to GitHub (branch `master`):

| Paperpile folder | File | CV section |
|---|---|---|
| Papers | `papers.bib` | Peer-Reviewed Publications |
| Preprints | `preprints.bib` | Preprints |
| Datasets | `datasets.bib` | Datasets |
| Patents | `patents.bib` | Patents |
| Invited | `invited.bib` | Invited Presentations |
| Contributed | `contributed.bib` | Contributed Publications |

Do not edit these `.bib` files by hand: the next Paperpile export overwrites
them. Change the record in Paperpile instead.

### Statistics

- `scripts/github_stats.py` reads the GitHub and PyPI APIs (stars, forks,
  commit share, contributor rank, releases, downloads, merged pull requests).
- `scripts/pub_stats.py` counts the entries in the `.bib` files (first- and
  senior-author papers included) and reads citations, h-index and i10-index
  from OpenAlex. It also selects the papers for the short CV: all first- and
  senior-author papers plus the 10 most-cited papers.

Both scripts use only the Python standard library. If an API request fails,
they keep the previous values, so the build does not fail.

## Build locally

The build uses [Tectonic](https://tectonic-typesetting.github.io/) (XeTeX)
and **biber 2.17**. The Tectonic bundle contains biblatex 3.17, which needs
exactly this biber version.

```bash
python3 scripts/github_stats.py   # needs `gh auth login` or GITHUB_TOKEN
python3 scripts/pub_stats.py
tectonic -X compile -Z search-path=texmf/fontawesome6 cv.tex
tectonic -X compile -Z search-path=texmf/fontawesome6 cv-short.tex
```

The icons use `fontawesome6`, which is not in the Tectonic bundle. A copy of
the package (LPPL 1.3c) and its fonts (SIL OFL 1.1) from CTAN is in
`texmf/fontawesome6/`; the `-Z search-path` option makes Tectonic find it.

Put `biber` 2.17 on your `PATH` first (binaries:
<https://sourceforge.net/projects/biblatex-biber/files/biblatex-biber/2.17/binaries/>).

## Continuous integration

`.github/workflows/build.yml` runs on every push and pull request:

1. Update the software and publication statistics.
2. Build `cv.pdf` and `cv-short.pdf`.
3. Fail if a character is missing from the font.
4. Upload both PDFs and logs as the `cv` artifact.
5. On `master` only: commit the PDFs and the statistics files
   (`[skip ci]`).
