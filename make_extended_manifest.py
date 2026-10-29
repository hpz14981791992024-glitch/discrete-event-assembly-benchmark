"""Hash the tracked artifact and the supplementary experiment records."""

from pathlib import Path

from make_release_manifest import ROOT, digest, files_for_release


SUPPLEMENT = (
    "make_extended_manifest.py",
    "compare_backends.py",
    "test_compare_backends.py",
    "model_mismatch_experiment.py",
    "test_model_mismatch_experiment.py",
    "robot_sim/README.md",
    "robot_sim/requirements.txt",
    "robot_sim/experiment.py",
    "robot_sim/analyze.py",
    "robot_sim/test_experiment.py",
    "robot_sim/diagnose.py",
)


def main() -> None:
    files = set(files_for_release())
    for name in SUPPLEMENT:
        path = ROOT / name
        if path.is_file():
            files.add(path)
    for directory in ("results_cpp", "results_model_mismatch", "robot_sim/results"):
        base = ROOT / directory
        if base.is_dir():
            files.update(path for path in base.rglob("*")
                         if path.is_file() and "figures" not in path.relative_to(base).parts)
    lines = [f"{digest(path)}  {path.relative_to(ROOT).as_posix()}" for path in sorted(files)]
    output = ROOT / "SHA256SUMS"
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {len(lines)} SHA-256 entries to {output}")


if __name__ == "__main__":
    main()
