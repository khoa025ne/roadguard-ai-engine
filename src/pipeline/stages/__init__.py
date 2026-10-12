"""
src/pipeline/stages/__init__.py — Các giai đoạn tuyến tính của Architecture A
=============================================================================
Stage 01: Segment   -> 01_segment.py
Stage 02: Detect    -> 02_detect.py
Stage 03: Filter    -> 03_filter.py
Stage 04: Dedup     -> 04_dedup.py
Stage 05: Measure   -> 05_measure.py
Stage 06: Inspect   -> 06_inspect.py
Stage 07: Report    -> 07_report.py
"""

import importlib

STAGE_NAMES = [
    "01_segment",
    "02_detect",
    "03_filter",
    "04_dedup",
    "05_measure",
    "06_inspect",
    "07_report",
]

STAGES = []
for name in STAGE_NAMES:
    mod = importlib.import_module(f".{name}", package=__name__)
    STAGES.append((name, mod.run))

__all__ = ["STAGES", "STAGE_NAMES"]
