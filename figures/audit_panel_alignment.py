"""Minimal, project-local alignment audit for publication figures.

The audit records final Matplotlib axes geometry in physical points after the
renderer has laid out text and legends. It blocks exports when panels leave the
figure, overlap, or when side-by-side comparable axes do not share vertical
edges within the requested tolerance. It is intentionally a layout QA helper,
not evidence about the scientific content of a figure.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Mapping, Sequence


class PanelAlignmentError(RuntimeError):
    """Raised when a required panel-layout check fails."""


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
        temporary.replace(path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def _spread(values: Sequence[float]) -> float:
    return max(values) - min(values) if values else 0.0


def _bbox_pt(ax: Any, renderer: Any, points_per_pixel: float) -> dict[str, float]:
    bbox = ax.get_window_extent(renderer=renderer)
    return {
        "left": float(bbox.x0 * points_per_pixel),
        "bottom": float(bbox.y0 * points_per_pixel),
        "right": float(bbox.x1 * points_per_pixel),
        "top": float(bbox.y1 * points_per_pixel),
    }


def _label_anchor_pt(
    ax: Any,
    panel_id: str,
    renderer: Any,
    points_per_pixel: float,
) -> dict[str, float] | None:
    for text in ax.texts:
        if text.get_text().strip() == panel_id:
            bbox = text.get_window_extent(renderer=renderer)
            return {
                "x": float(bbox.x0 * points_per_pixel),
                "y": float(bbox.y1 * points_per_pixel),
            }
    return None


def _overlap(first: Mapping[str, float], second: Mapping[str, float]) -> bool:
    return not (
        first["right"] <= second["left"]
        or second["right"] <= first["left"]
        or first["top"] <= second["bottom"]
        or second["top"] <= first["bottom"]
    )


def _overlay_svg(
    path: Path,
    figure_width_pt: float,
    figure_height_pt: float,
    panels: Sequence[Mapping[str, Any]],
) -> None:
    rectangles: list[str] = []
    for panel in panels:
        bbox = panel["bbox_pt"]
        x = bbox["left"]
        y = figure_height_pt - bbox["top"]
        width = bbox["right"] - bbox["left"]
        height = bbox["top"] - bbox["bottom"]
        label = panel["id"]
        rectangles.append(
            f'<rect x="{x:.3f}" y="{y:.3f}" width="{width:.3f}" '
            f'height="{height:.3f}" fill="none" stroke="#dc2626" stroke-width="0.8"/>'
        )
        rectangles.append(
            f'<text x="{x + 2:.3f}" y="{y + 9:.3f}" font-size="7" '
            f'font-family="Arial, Helvetica, sans-serif" fill="#dc2626">{label}</text>'
        )
    svg = "\n".join(
        [
            '<?xml version="1.0" encoding="UTF-8"?>',
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{figure_width_pt:.3f}pt" '
            f'height="{figure_height_pt:.3f}pt" viewBox="0 0 {figure_width_pt:.3f} {figure_height_pt:.3f}">',
            *rectangles,
            "</svg>",
        ]
    )
    _atomic_write(path, svg + "\n")


def require_matplotlib_panel_alignment(
    fig: Any,
    *,
    axes: Sequence[Any],
    panel_ids: Sequence[str],
    json_out: Path | str,
    overlay_svg: Path | str,
    tolerance_pt: float = 1.5,
    gutter_tolerance_pt: float = 1.5,
    require_panel_labels: bool = False,
    strict: bool = True,
) -> dict[str, Any]:
    """Audit final axes geometry and raise if the declared layout is invalid.

    The figure scripts in this project use either one axis or two side-by-side
    comparable axes. For a two-panel row, top, bottom, and height are checked
    against ``tolerance_pt``. ``gutter_tolerance_pt`` is recorded for provenance
    because there is no repeated multi-gutter layout in the current figures.
    """

    if len(axes) != len(panel_ids) or not axes:
        raise ValueError("axes and panel_ids must be non-empty and have equal length")
    if len(panel_ids) != len(set(panel_ids)):
        raise ValueError("panel_ids must be unique")
    if tolerance_pt < 0 or gutter_tolerance_pt < 0:
        raise ValueError("alignment tolerances must be non-negative")

    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    points_per_pixel = 72.0 / fig.dpi
    figure_width_pt = float(fig.get_figwidth() * 72.0)
    figure_height_pt = float(fig.get_figheight() * 72.0)
    panels = [
        {
            "id": panel_id,
            "bbox_pt": _bbox_pt(ax, renderer, points_per_pixel),
            "panel_label_anchor_pt": _label_anchor_pt(
                ax, panel_id, renderer, points_per_pixel
            ),
        }
        for ax, panel_id in zip(axes, panel_ids)
    ]

    findings: list[dict[str, Any]] = []
    for panel in panels:
        bbox = panel["bbox_pt"]
        if (
            bbox["left"] < -0.01
            or bbox["bottom"] < -0.01
            or bbox["right"] > figure_width_pt + 0.01
            or bbox["top"] > figure_height_pt + 0.01
        ):
            findings.append(
                {
                    "severity": "FAIL",
                    "kind": "axes-outside-figure",
                    "panels": [panel["id"]],
                    "message": "Rendered axes extend beyond the figure boundary.",
                }
            )
        if require_panel_labels and panel["panel_label_anchor_pt"] is None:
            findings.append(
                {
                    "severity": "FAIL" if strict else "WARN",
                    "kind": "panel-label-not-found",
                    "panels": [panel["id"]],
                    "message": "A required panel label was not found among the axes text artists.",
                }
            )

    for index, first in enumerate(panels):
        for second in panels[index + 1 :]:
            if _overlap(first["bbox_pt"], second["bbox_pt"]):
                findings.append(
                    {
                        "severity": "FAIL",
                        "kind": "axes-overlap",
                        "panels": [first["id"], second["id"]],
                        "message": "Rendered plot areas overlap.",
                    }
                )

    if len(panels) >= 2:
        centers = [
            (panel["bbox_pt"]["bottom"] + panel["bbox_pt"]["top"]) / 2.0
            for panel in panels
        ]
        if _spread(centers) <= tolerance_pt:
            metrics = {
                "top": [panel["bbox_pt"]["top"] for panel in panels],
                "bottom": [panel["bbox_pt"]["bottom"] for panel in panels],
                "height": [
                    panel["bbox_pt"]["top"] - panel["bbox_pt"]["bottom"]
                    for panel in panels
                ],
            }
            if max(_spread(values) for values in metrics.values()) > tolerance_pt:
                findings.append(
                    {
                        "severity": "FAIL",
                        "kind": "side-by-side-axes-misalignment",
                        "panels": list(panel_ids),
                        "message": "Comparable side-by-side axes do not share vertical edges within tolerance.",
                        "metrics_pt": {
                            name: {
                                "spread": round(_spread(values), 6),
                                "values": [round(value, 6) for value in values],
                            }
                            for name, values in metrics.items()
                        },
                    }
                )

    failures = [finding for finding in findings if finding["severity"] == "FAIL"]
    warnings = [finding for finding in findings if finding["severity"] == "WARN"]
    verdict = "PASS" if not failures and not (strict and warnings) else "FIX BEFORE DELIVERY"
    report: dict[str, Any] = {
        "schema_version": 1,
        "backend": "matplotlib",
        "verdict": verdict,
        "applicable": len(panels) > 1,
        "figure": {
            "width_pt": round(figure_width_pt, 6),
            "height_pt": round(figure_height_pt, 6),
        },
        "tolerances": {
            "alignment_pt": tolerance_pt,
            "gutter_pt": gutter_tolerance_pt,
        },
        "panels": panels,
        "summary": {"fail": len(failures), "warn": len(warnings)},
        "findings": findings,
    }
    _atomic_write(Path(json_out), json.dumps(report, indent=2, sort_keys=True) + "\n")
    _overlay_svg(Path(overlay_svg), figure_width_pt, figure_height_pt, panels)
    if verdict != "PASS":
        raise PanelAlignmentError(
            f"Panel alignment audit failed; see {json_out} for measured geometry."
        )
    return report
