#!/usr/bin/env python3
"""
Lehký GUI smoke test.

- Na Linuxu bez DISPLAY se korektně přeskočí (exit 0).
- V prostředí s GUI ověří základní průchod:
  vytvoření třídy, přidání žáků, random/smart běh, uzavření aplikace.
"""

from __future__ import annotations

import os
import sys
import tempfile
import argparse
from pathlib import Path


def _has_display() -> bool:
    if sys.platform.startswith("win"):
        return True
    if sys.platform == "darwin":
        return True
    return bool(os.environ.get("DISPLAY"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--require-display",
        action="store_true",
        help="Pokud není dostupný DISPLAY, vrátí chybu místo skip.",
    )
    args = parser.parse_args(argv)

    if not _has_display():
        if args.require_display:
            print("GUI smoke failed: DISPLAY is required but not available.")
            return 1
        print("GUI smoke skipped: no DISPLAY.")
        return 0

    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    import app as app_module

    with tempfile.TemporaryDirectory() as tmp:
        app_module.DB_PATH = Path(tmp) / "gui_smoke.db"
        app = app_module.SeatingApp()
        app.withdraw()

        classroom_id = app.db.create_classroom("SMOKE", 3, 4)
        for name in ["Anna", "Boris", "Cyril", "Dana", "Eva", "Filip", "Gita", "Hana"]:
            app.db.add_student(classroom_id, name)

        app.refresh_classrooms()
        labels = list(app.classrooms_by_label.keys())
        if not labels:
            print("GUI smoke failed: no classrooms loaded.")
            app.on_close()
            return 1

        app.classroom_combo.set(labels[0])
        app.on_select_classroom()
        app.randomize()
        app.smart_generate()

        # Kontrola, že máme nějaké přiřazení
        assigned = sum(1 for v in app.current_assignments.values() if v is not None)
        app.on_close()
        if assigned <= 0:
            print("GUI smoke failed: no assigned students.")
            return 1

    print("GUI smoke OK.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
