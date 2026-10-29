"""Write SHA-256 checksums for the curated, final release contents.

The manifest deliberately omits local environments, historical and smoke-test
outputs, LaTeX intermediates, and noncanonical figure renderings. Regenerate it
after any release file, author metadata, DOI, or license change.
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parent
CORE_FILES = (
    "README.md",
    "README.zh-CN.md",
    "RELEASE_CHECKLIST.md",
    ".gitignore",
    "requirements.txt",
    "simulator.py",
    "cpp_checker.py",
    "cpp/action_checker.cpp",
    "run_experiments.py",
    "analyze_results.py",
    "audit_results.py",
    "generate_qualitative_trace.py",
    "make_release_manifest.py",
    "test_simulator.py",
    "test_cpp_checker.py",
    "figures/audit_panel_alignment.py",
    "figures/make_figure1_composite.py",
    "figures/make_publication_figures.py",
)
OPTIONAL_RELEASE_FILES = ("LICENSE", "LICENSE-DATA", "CITATION.cff", ".zenodo.json")
PUBLICATION_FIGURE_STEMS = (
    "fig1_architecture",
    "fig2_qualitative_recovery",
    "fig3_sensitivity",
    "fig4_failure_distribution",
)
FIGURE_QA_SUFFIXES = (
    ".alignment.json",
    ".collision-audit.json",
    ".text-audit.json",
)


def existing_files(paths: Iterable[str]) -> list[Path]:
    files: list[Path] = []
    for relative in paths:
        target = ROOT / relative
        if not target.exists():
            continue
        if target.is_file():
            files.append(target)
    return sorted(files)


def publication_figure_files() -> list[Path]:
    directory = ROOT / "figures" / "publication"
    files: list[Path] = []
    for stem in PUBLICATION_FIGURE_STEMS:
        for suffix in (".pdf", ".svg", *FIGURE_QA_SUFFIXES):
            path = directory / f"{stem}{suffix}"
            if path.is_file():
                files.append(path)
    return sorted(files)


def files_for_release() -> list[Path]:
    files = existing_files((*CORE_FILES, *OPTIONAL_RELEASE_FILES))
    results = ROOT / "results"
    if results.is_dir():
        files.extend(
            path
            for path in results.rglob("*")
            if path.is_file()
            # The PNGs are convenience renderings duplicated by the canonical
            # publication figures; they are deliberately not archival inputs.
            and path.relative_to(results).parts[:2] != ("analysis", "figures")
        )
    files.extend(publication_figure_files())
    return sorted(set(files))


def digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(block)
    return hasher.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "SHA256SUMS")
    args = parser.parse_args()
    output = args.output.resolve()
    lines = [
        f"{digest(path)}  {path.relative_to(ROOT).as_posix()}"
        for path in files_for_release()
        if path.resolve() != output
    ]
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {len(lines)} SHA-256 entries to {output}")


if __name__ == "__main__":
    main()
