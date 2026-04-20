import json
import importlib.util
import random
import shutil
import sqlite3
import hashlib
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog

REPORTLAB_AVAILABLE = importlib.util.find_spec("reportlab") is not None
if REPORTLAB_AVAILABLE:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

APP_DIR = Path(__file__).resolve().parent
DB_PATH = APP_DIR / "seating_app.db"
PIN_HASH_SETTING_KEY = "app_pin_hash"

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS classrooms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    rows_count INTEGER NOT NULL,
    cols_count INTEGER NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS seats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    classroom_id INTEGER NOT NULL,
    row_index INTEGER NOT NULL,
    col_index INTEGER NOT NULL,
    label TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    UNIQUE(classroom_id, row_index, col_index),
    FOREIGN KEY(classroom_id) REFERENCES classrooms(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS students (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    classroom_id INTEGER NOT NULL,
    display_name TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    UNIQUE(classroom_id, display_name),
    FOREIGN KEY(classroom_id) REFERENCES classrooms(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS arrangements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    classroom_id INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    mode TEXT NOT NULL,
    overall_rating INTEGER,
    notes_json TEXT,
    FOREIGN KEY(classroom_id) REFERENCES classrooms(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS arrangement_assignments (
    arrangement_id INTEGER NOT NULL,
    seat_id INTEGER NOT NULL,
    student_id INTEGER,
    PRIMARY KEY(arrangement_id, seat_id),
    FOREIGN KEY(arrangement_id) REFERENCES arrangements(id) ON DELETE CASCADE,
    FOREIGN KEY(seat_id) REFERENCES seats(id) ON DELETE CASCADE,
    FOREIGN KEY(student_id) REFERENCES students(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS student_feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    arrangement_id INTEGER NOT NULL,
    student_id INTEGER NOT NULL,
    rating INTEGER NOT NULL,
    FOREIGN KEY(arrangement_id) REFERENCES arrangements(id) ON DELETE CASCADE,
    FOREIGN KEY(student_id) REFERENCES students(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS pair_scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    classroom_id INTEGER NOT NULL,
    student_a_id INTEGER NOT NULL,
    student_b_id INTEGER NOT NULL,
    proximity TEXT NOT NULL,
    avg_score REAL NOT NULL DEFAULT 0,
    observations INTEGER NOT NULL DEFAULT 0,
    UNIQUE(classroom_id, student_a_id, student_b_id, proximity),
    FOREIGN KEY(classroom_id) REFERENCES classrooms(id) ON DELETE CASCADE,
    FOREIGN KEY(student_a_id) REFERENCES students(id) ON DELETE CASCADE,
    FOREIGN KEY(student_b_id) REFERENCES students(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS seat_scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    classroom_id INTEGER NOT NULL,
    student_id INTEGER NOT NULL,
    seat_id INTEGER NOT NULL,
    avg_score REAL NOT NULL DEFAULT 0,
    observations INTEGER NOT NULL DEFAULT 0,
    UNIQUE(classroom_id, student_id, seat_id),
    FOREIGN KEY(classroom_id) REFERENCES classrooms(id) ON DELETE CASCADE,
    FOREIGN KEY(student_id) REFERENCES students(id) ON DELETE CASCADE,
    FOREIGN KEY(seat_id) REFERENCES seats(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS locked_seats (
    classroom_id INTEGER NOT NULL,
    seat_id INTEGER NOT NULL,
    student_id INTEGER NOT NULL,
    PRIMARY KEY(classroom_id, seat_id),
    FOREIGN KEY(classroom_id) REFERENCES classrooms(id) ON DELETE CASCADE,
    FOREIGN KEY(seat_id) REFERENCES seats(id) ON DELETE CASCADE,
    FOREIGN KEY(student_id) REFERENCES students(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

FONT_NAME = "Helvetica"
if REPORTLAB_AVAILABLE:
    for _font_path in [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans.ttf",
    ]:
        if Path(_font_path).exists():
            try:
                pdfmetrics.registerFont(TTFont("DejaVuSans", _font_path))
                FONT_NAME = "DejaVuSans"
                break
            except Exception:
                pass


@dataclass(frozen=True)
class Seat:
    id: int
    row_index: int
    col_index: int
    label: str
    is_active: bool


@dataclass(frozen=True)
class Student:
    id: int
    display_name: str
    is_active: bool


def hash_pin(pin: str) -> str:
    return hashlib.sha256(pin.encode("utf-8")).hexdigest()


def export_arrangement_pdf(
    output_path: str | Path,
    classroom_name: str,
    mode: str,
    score: float,
    seats: list[Seat],
    assignments: dict[int, int | None],
    student_names_by_id: dict[int, str],
    analysis: dict | None = None,
):
    if not REPORTLAB_AVAILABLE:
        raise RuntimeError("PDF export vyžaduje knihovnu reportlab. Nainstaluj ji příkazem: pip install reportlab")
    output_path = str(output_path)
    doc = SimpleDocTemplate(
        output_path,
        pagesize=landscape(A4),
        leftMargin=12 * mm,
        rightMargin=12 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "TitleCZ", parent=styles["Title"], fontName=FONT_NAME, fontSize=18, leading=22, spaceAfter=8
    )
    body_style = ParagraphStyle(
        "BodyCZ", parent=styles["BodyText"], fontName=FONT_NAME, fontSize=9, leading=11, spaceAfter=3
    )
    small_style = ParagraphStyle(
        "SmallCZ", parent=styles["BodyText"], fontName=FONT_NAME, fontSize=8, leading=10, spaceAfter=2
    )

    story = []
    seat_map = {seat.id: seat for seat in seats}
    max_row = max((seat.row_index for seat in seats), default=0)
    max_col = max((seat.col_index for seat in seats), default=0)

    story.append(Paragraph("Zasedací pořádek", title_style))
    story.append(
        Paragraph(
            f"Třída: <b>{classroom_name}</b> - režim: <b>{mode}</b> - skóre návrhu: <b>{score:.2f}</b> - export: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            body_style,
        )
    )
    story.append(Spacer(1, 4 * mm))

    grid = []
    for r in range(max_row + 1):
        row = []
        for c in range(max_col + 1):
            seat = next((s for s in seats if s.row_index == r and s.col_index == c), None)
            if seat is None:
                row.append(Paragraph("", small_style))
            elif not seat.is_active:
                row.append(Paragraph(f"<b>{seat.label}</b><br/>neaktivní", small_style))
            else:
                student_id = assignments.get(seat.id)
                student_name = student_names_by_id.get(student_id, "-") if student_id else "-"
                row.append(Paragraph(f"<b>{seat.label}</b><br/>{student_name}", body_style))
        grid.append(row)

    col_count = max(max_col + 1, 1)
    total_table_width = 260 * mm
    col_width = total_table_width / col_count
    table = Table(grid, colWidths=[col_width] * col_count)
    style_cmds = [
        ("FONTNAME", (0, 0), (-1, -1), FONT_NAME),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("LEADING", (0, 0), (-1, -1), 11),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#9ca3af")),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]
    for seat in seats:
        if not seat.is_active:
            style_cmds.extend(
                [
                    ("BACKGROUND", (seat.col_index, seat.row_index), (seat.col_index, seat.row_index), colors.HexColor("#4b5563")),
                    ("TEXTCOLOR", (seat.col_index, seat.row_index), (seat.col_index, seat.row_index), colors.white),
                ]
            )
        elif assignments.get(seat.id):
            style_cmds.append(
                ("BACKGROUND", (seat.col_index, seat.row_index), (seat.col_index, seat.row_index), colors.HexColor("#eff6ff"))
            )
    table.setStyle(TableStyle(style_cmds))
    story.append(table)

    if analysis:
        story.append(Spacer(1, 5 * mm))
        story.append(Paragraph("Shrnutí skóre", body_style))
        story.append(
            Paragraph(
                f"Pozice: <b>{analysis.get('seat_total', 0):+.2f}</b> - sousedství: <b>{analysis.get('pair_total', 0):+.2f}</b>",
                body_style,
            )
        )
        lines = []
        for term in analysis.get("seat_terms", [])[:6]:
            seat = seat_map.get(term["seat_id"])
            seat_label = seat.label if seat else str(term["seat_id"])
            student_name = student_names_by_id.get(term["student_id"], str(term["student_id"]))
            lines.append((abs(term["contribution"]), f"Pozice: {student_name} na {seat_label} ({term['contribution']:+.2f})"))
        for term in analysis.get("pair_terms", [])[:6]:
            proximity = "vedle sebe" if term["proximity"] == "side" else "před/za"
            a_name = student_names_by_id.get(term["student_a_id"], str(term["student_a_id"]))
            b_name = student_names_by_id.get(term["student_b_id"], str(term["student_b_id"]))
            lines.append((abs(term["contribution"]), f"Dvojice: {a_name} × {b_name}, {proximity} ({term['contribution']:+.2f})"))
        lines.sort(key=lambda x: x[0], reverse=True)
        for _, line in lines[:10]:
            story.append(Paragraph(f"- {line}", small_style))

    doc.build(story)


class Database:
    def __init__(self, path: Path):
        self.path = path
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def close(self):
        self.conn.close()

    def list_classrooms(self):
        return self.conn.execute("SELECT id, name, rows_count, cols_count FROM classrooms ORDER BY name").fetchall()

    def get_setting(self, key: str):
        row = self.conn.execute("SELECT value FROM app_settings WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else None

    def set_setting(self, key: str, value: str):
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO app_settings(key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (key, value),
            )

    def delete_arrangements_older_than(self, cutoff_iso: str):
        with self.conn:
            row = self.conn.execute(
                "SELECT COUNT(*) AS cnt FROM arrangements WHERE created_at < ?",
                (cutoff_iso,),
            ).fetchone()
            deleted = int(row["cnt"]) if row else 0
            self.conn.execute("DELETE FROM arrangements WHERE created_at < ?", (cutoff_iso,))
        return deleted

    def create_classroom(self, name: str, rows_count: int, cols_count: int):
        now = datetime.now().isoformat(timespec="seconds")
        with self.conn:
            cur = self.conn.execute(
                "INSERT INTO classrooms(name, rows_count, cols_count, created_at) VALUES (?, ?, ?, ?)",
                (name, rows_count, cols_count, now),
            )
            classroom_id = cur.lastrowid
            values = []
            for r in range(rows_count):
                for c in range(cols_count):
                    values.append((classroom_id, r, c, f"{chr(65 + r)}{c + 1}"))
            self.conn.executemany(
                "INSERT INTO seats(classroom_id, row_index, col_index, label) VALUES (?, ?, ?, ?)",
                values,
            )
        return classroom_id

    def get_classroom(self, classroom_id: int):
        return self.conn.execute(
            "SELECT id, name, rows_count, cols_count FROM classrooms WHERE id = ?", (classroom_id,)
        ).fetchone()

    def list_seats(self, classroom_id: int):
        rows = self.conn.execute(
            "SELECT id, row_index, col_index, label, is_active FROM seats WHERE classroom_id = ? ORDER BY row_index, col_index",
            (classroom_id,),
        ).fetchall()
        return [Seat(r["id"], r["row_index"], r["col_index"], r["label"], bool(r["is_active"])) for r in rows]

    def set_seat_active(self, seat_id: int, is_active: bool):
        with self.conn:
            self.conn.execute("UPDATE seats SET is_active = ? WHERE id = ?", (1 if is_active else 0, seat_id))
            if not is_active:
                self.conn.execute("DELETE FROM locked_seats WHERE seat_id = ?", (seat_id,))

    def activate_all_seats(self, classroom_id: int):
        with self.conn:
            self.conn.execute("UPDATE seats SET is_active = 1 WHERE classroom_id = ?", (classroom_id,))

    def list_students(self, classroom_id: int):
        rows = self.conn.execute(
            "SELECT id, display_name, is_active FROM students WHERE classroom_id = ? AND is_active = 1 ORDER BY display_name",
            (classroom_id,),
        ).fetchall()
        return [Student(r["id"], r["display_name"], bool(r["is_active"])) for r in rows]

    def get_student_name_map(self, classroom_id: int):
        rows = self.conn.execute(
            "SELECT id, display_name FROM students WHERE classroom_id = ? ORDER BY display_name", (classroom_id,)
        ).fetchall()
        return {r["id"]: r["display_name"] for r in rows}

    def add_student(self, classroom_id: int, display_name: str):
        with self.conn:
            self.conn.execute(
                "INSERT INTO students(classroom_id, display_name) VALUES (?, ?)",
                (classroom_id, display_name.strip()),
            )

    def deactivate_student(self, student_id: int):
        with self.conn:
            self.conn.execute("UPDATE students SET is_active = 0 WHERE id = ?", (student_id,))
            self.conn.execute("DELETE FROM locked_seats WHERE student_id = ?", (student_id,))

    def save_locks(self, classroom_id: int, seat_to_student: dict[int, int]):
        with self.conn:
            self.conn.execute("DELETE FROM locked_seats WHERE classroom_id = ?", (classroom_id,))
            for seat_id, student_id in seat_to_student.items():
                self.conn.execute(
                    "INSERT INTO locked_seats(classroom_id, seat_id, student_id) VALUES (?, ?, ?)",
                    (classroom_id, seat_id, student_id),
                )

    def get_locks(self, classroom_id: int):
        rows = self.conn.execute(
            "SELECT seat_id, student_id FROM locked_seats WHERE classroom_id = ?", (classroom_id,)
        ).fetchall()
        return {r["seat_id"]: r["student_id"] for r in rows}

    def save_arrangement(self, classroom_id: int, mode: str, assignments: dict[int, int | None], overall_rating=None, notes=None):
        notes_json = json.dumps(notes or {}, ensure_ascii=False)
        now = datetime.now().isoformat(timespec="seconds")
        with self.conn:
            cur = self.conn.execute(
                "INSERT INTO arrangements(classroom_id, created_at, mode, overall_rating, notes_json) VALUES (?, ?, ?, ?, ?)",
                (classroom_id, now, mode, overall_rating, notes_json),
            )
            arrangement_id = cur.lastrowid
            self.conn.executemany(
                "INSERT INTO arrangement_assignments(arrangement_id, seat_id, student_id) VALUES (?, ?, ?)",
                [(arrangement_id, seat_id, student_id) for seat_id, student_id in assignments.items()],
            )
        return arrangement_id

    def list_recent_arrangements(self, classroom_id: int, limit: int = 20):
        return self.conn.execute(
            "SELECT id, created_at, mode, overall_rating FROM arrangements WHERE classroom_id = ? ORDER BY id DESC LIMIT ?",
            (classroom_id, limit),
        ).fetchall()

    def get_arrangement_assignments(self, arrangement_id: int):
        rows = self.conn.execute(
            "SELECT seat_id, student_id FROM arrangement_assignments WHERE arrangement_id = ?", (arrangement_id,)
        ).fetchall()
        return {r["seat_id"]: r["student_id"] for r in rows}

    def save_feedback(self, arrangement_id: int, overall_rating: int, student_ratings: dict[int, int]):
        with self.conn:
            self.conn.execute("UPDATE arrangements SET overall_rating = ? WHERE id = ?", (overall_rating, arrangement_id))
            self.conn.execute("DELETE FROM student_feedback WHERE arrangement_id = ?", (arrangement_id,))
            self.conn.executemany(
                "INSERT INTO student_feedback(arrangement_id, student_id, rating) VALUES (?, ?, ?)",
                [(arrangement_id, student_id, rating) for student_id, rating in student_ratings.items()],
            )

    def _upsert_avg(self, table: str, key_fields: tuple, score: float):
        if table == "pair_scores":
            row = self.conn.execute(
                "SELECT id, avg_score, observations FROM pair_scores WHERE classroom_id=? AND student_a_id=? AND student_b_id=? AND proximity=?",
                key_fields,
            ).fetchone()
            if row:
                obs = int(row["observations"])
                new_avg = (float(row["avg_score"]) * obs + score) / (obs + 1)
                self.conn.execute(
                    "UPDATE pair_scores SET avg_score = ?, observations = ? WHERE id = ?",
                    (new_avg, obs + 1, row["id"]),
                )
            else:
                self.conn.execute(
                    "INSERT INTO pair_scores(classroom_id, student_a_id, student_b_id, proximity, avg_score, observations) VALUES (?, ?, ?, ?, ?, 1)",
                    (*key_fields, score),
                )
        elif table == "seat_scores":
            row = self.conn.execute(
                "SELECT id, avg_score, observations FROM seat_scores WHERE classroom_id=? AND student_id=? AND seat_id=?",
                key_fields,
            ).fetchone()
            if row:
                obs = int(row["observations"])
                new_avg = (float(row["avg_score"]) * obs + score) / (obs + 1)
                self.conn.execute(
                    "UPDATE seat_scores SET avg_score = ?, observations = ? WHERE id = ?",
                    (new_avg, obs + 1, row["id"]),
                )
            else:
                self.conn.execute(
                    "INSERT INTO seat_scores(classroom_id, student_id, seat_id, avg_score, observations) VALUES (?, ?, ?, ?, 1)",
                    (*key_fields, score),
                )

    @staticmethod
    def _build_neighbors(seats: list[Seat]):
        seat_index = {(seat.row_index, seat.col_index): seat.id for seat in seats if seat.is_active}
        neighbors = defaultdict(list)
        for seat in seats:
            if not seat.is_active:
                continue
            for delta, proximity in [((0, -1), "side"), ((0, 1), "side"), ((-1, 0), "front_back"), ((1, 0), "front_back")]:
                target = (seat.row_index + delta[0], seat.col_index + delta[1])
                if target in seat_index:
                    neighbors[seat.id].append((proximity, seat_index[target]))
        return neighbors

    @staticmethod
    def _iter_neighbors(occupied: dict[int, int], neighbors: dict[int, list[tuple[str, int]]], seat_id: int):
        seen = set()
        for proximity, other_seat_id in neighbors.get(seat_id, []):
            other_student_id = occupied.get(other_seat_id)
            if other_student_id is None:
                continue
            key = (proximity, other_student_id)
            if key in seen:
                continue
            seen.add(key)
            yield proximity, other_student_id

    def update_scores_from_feedback(
        self,
        classroom_id: int,
        seats: list[Seat],
        assignments: dict[int, int | None],
        overall_rating: int,
        student_ratings: dict[int, int],
    ):
        occupied = {seat_id: student_id for seat_id, student_id in assignments.items() if student_id is not None}
        neighbors = self._build_neighbors(seats)
        with self.conn:
            if overall_rating != 0:
                weak_score = overall_rating * 0.25
                for seat_id, student_id in occupied.items():
                    self._upsert_avg("seat_scores", (classroom_id, student_id, seat_id), weak_score)
                    for proximity, other_student_id in self._iter_neighbors(occupied, neighbors, seat_id):
                        a, b = sorted((student_id, other_student_id))
                        self._upsert_avg("pair_scores", (classroom_id, a, b, proximity), weak_score)

            for student_id, rating in student_ratings.items():
                if rating == 0:
                    continue
                seat_id = next((sid for sid, stu_id in occupied.items() if stu_id == student_id), None)
                if seat_id is None:
                    continue
                self._upsert_avg("seat_scores", (classroom_id, student_id, seat_id), rating * 0.8)
                for proximity, other_student_id in self._iter_neighbors(occupied, neighbors, seat_id):
                    factor = 1.0 if proximity == "side" else 0.5
                    a, b = sorted((student_id, other_student_id))
                    self._upsert_avg("pair_scores", (classroom_id, a, b, proximity), rating * factor)

    def load_pair_scores(self, classroom_id: int):
        rows = self.conn.execute(
            "SELECT student_a_id, student_b_id, proximity, avg_score, observations FROM pair_scores WHERE classroom_id = ?",
            (classroom_id,),
        ).fetchall()
        return {
            (r["student_a_id"], r["student_b_id"], r["proximity"]): (float(r["avg_score"]), int(r["observations"]))
            for r in rows
        }

    def load_seat_scores(self, classroom_id: int):
        rows = self.conn.execute(
            "SELECT student_id, seat_id, avg_score, observations FROM seat_scores WHERE classroom_id = ?",
            (classroom_id,),
        ).fetchall()
        return {
            (r["student_id"], r["seat_id"]): (float(r["avg_score"]), int(r["observations"]))
            for r in rows
        }

    def get_student_pair_insights(self, classroom_id: int, student_id: int, limit: int = 30):
        rows = self.conn.execute(
            """
            SELECT
                CASE
                    WHEN student_a_id = ? THEN student_b_id
                    ELSE student_a_id
                END AS other_student_id,
                proximity,
                avg_score,
                observations
            FROM pair_scores
            WHERE classroom_id = ?
              AND (student_a_id = ? OR student_b_id = ?)
            ORDER BY avg_score DESC, observations DESC
            LIMIT ?
            """,
            (student_id, classroom_id, student_id, student_id, limit),
        ).fetchall()
        return [
            {
                "other_student_id": r["other_student_id"],
                "proximity": r["proximity"],
                "avg_score": float(r["avg_score"]),
                "observations": int(r["observations"]),
            }
            for r in rows
        ]

    def get_student_seat_insights(self, classroom_id: int, student_id: int, limit: int = 30):
        rows = self.conn.execute(
            """
            SELECT
                seat_scores.seat_id,
                seats.label AS seat_label,
                seat_scores.avg_score,
                seat_scores.observations
            FROM seat_scores
            JOIN seats ON seats.id = seat_scores.seat_id
            WHERE seat_scores.classroom_id = ?
              AND seat_scores.student_id = ?
            ORDER BY seat_scores.avg_score DESC, seat_scores.observations DESC
            LIMIT ?
            """,
            (classroom_id, student_id, limit),
        ).fetchall()
        return [
            {
                "seat_id": r["seat_id"],
                "seat_label": r["seat_label"],
                "avg_score": float(r["avg_score"]),
                "observations": int(r["observations"]),
            }
            for r in rows
        ]


class SeatingEngine:
    def __init__(self, seats: list[Seat], students: list[Student], pair_scores: dict, seat_scores: dict, locked: dict[int, int]):
        self.seats = [seat for seat in seats if seat.is_active]
        self.seat_map = {seat.id: seat for seat in self.seats}
        self.students = students
        self.pair_scores = pair_scores
        self.seat_scores = seat_scores
        self.locked = {seat_id: student_id for seat_id, student_id in locked.items() if seat_id in self.seat_map}
        self.neighbors = self._build_neighbors(self.seats)

    @staticmethod
    def _build_neighbors(seats: list[Seat]):
        seat_index = {(seat.row_index, seat.col_index): seat.id for seat in seats}
        neighbors = defaultdict(list)
        for seat in seats:
            for delta, proximity in [((0, -1), "side"), ((0, 1), "side"), ((-1, 0), "front_back"), ((1, 0), "front_back")]:
                target = (seat.row_index + delta[0], seat.col_index + delta[1])
                if target in seat_index:
                    neighbors[seat.id].append((proximity, seat_index[target]))
        return neighbors

    def random_arrangement(self):
        assignments = {seat.id: None for seat in self.seats}
        locked_student_ids = set(self.locked.values())
        unlocked_students = [student.id for student in self.students if student.id not in locked_student_ids]
        unlocked_seats = [seat.id for seat in self.seats if seat.id not in self.locked]

        for seat_id, student_id in self.locked.items():
            assignments[seat_id] = student_id
        random.shuffle(unlocked_students)
        for seat_id, student_id in zip(unlocked_seats, unlocked_students):
            assignments[seat_id] = student_id
        return assignments

    def analyze_arrangement(self, assignments: dict[int, int | None]):
        seat_terms = []
        pair_terms = []
        seat_total = 0.0
        pair_total = 0.0

        for seat_id, student_id in assignments.items():
            if student_id is None or seat_id not in self.seat_map:
                continue
            data = self.seat_scores.get((student_id, seat_id))
            if data:
                avg, obs = data
                contribution = avg * (1 + min(obs, 5) * 0.1)
                seat_total += contribution
                seat_terms.append({
                    "type": "seat",
                    "seat_id": seat_id,
                    "student_id": student_id,
                    "contribution": contribution,
                    "avg": avg,
                    "observations": obs,
                })

        visited = set()
        for seat_id, student_id in assignments.items():
            if student_id is None or seat_id not in self.seat_map:
                continue
            for proximity, other_seat_id in self.neighbors.get(seat_id, []):
                other_student_id = assignments.get(other_seat_id)
                if other_student_id is None:
                    continue
                a, b = sorted((student_id, other_student_id))
                key = (a, b, proximity)
                if key in visited:
                    continue
                visited.add(key)
                data = self.pair_scores.get(key)
                if data:
                    avg, obs = data
                    contribution = avg * (1 + min(obs, 5) * 0.15)
                    pair_total += contribution
                    pair_terms.append({
                        "type": "pair",
                        "student_a_id": a,
                        "student_b_id": b,
                        "seat_a_id": seat_id,
                        "seat_b_id": other_seat_id,
                        "proximity": proximity,
                        "contribution": contribution,
                        "avg": avg,
                        "observations": obs,
                    })

        seat_terms.sort(key=lambda x: x["contribution"], reverse=True)
        pair_terms.sort(key=lambda x: x["contribution"], reverse=True)
        return {
            "total": seat_total + pair_total,
            "seat_total": seat_total,
            "pair_total": pair_total,
            "seat_terms": seat_terms,
            "pair_terms": pair_terms,
        }

    def score_arrangement(self, assignments: dict[int, int | None]):
        return self.analyze_arrangement(assignments)["total"]

    @staticmethod
    def recommend_iterations(student_count: int, active_seat_count: int) -> int:
        # Heuristika: víc žáků/aktivních míst => víc náhodných pokusů.
        # Udržujeme bezpečné meze kvůli plynulosti GUI.
        base = max(student_count, active_seat_count, 1)
        iterations = 400 + base * 120
        return max(600, min(iterations, 5000))

    def best_of_random_search(self, iterations: int = 2500):
        best = None
        best_score = float("-inf")
        for _ in range(iterations):
            candidate = self.random_arrangement()
            score = self.score_arrangement(candidate)
            if score > best_score:
                best = candidate
                best_score = score
        if best is None:
            best = self.random_arrangement()
            best_score = self.score_arrangement(best)
        return best, best_score


class RatingDialog(tk.Toplevel):
    def __init__(self, parent, students: list[Student], student_names_by_id: dict[int, str]):
        super().__init__(parent)
        self.title("Hodnocení po hodině")
        self.result = None
        self.student_rating_vars = {}
        self.transient(parent)
        self.grab_set()

        ttk.Label(self, text="Celkové hodnocení rozesazení (-2 až +2):").grid(row=0, column=0, sticky="w", padx=10, pady=(10, 4))
        self.overall_var = tk.IntVar(value=0)
        ttk.Spinbox(self, from_=-2, to=2, textvariable=self.overall_var, width=5).grid(row=0, column=1, sticky="w", padx=10, pady=(10, 4))

        ttk.Label(self, text="Ohodnoť jen vybrané žáky. Prázdné = bez hodnocení.").grid(row=1, column=0, columnspan=2, sticky="w", padx=10, pady=(0, 8))

        canvas = tk.Canvas(self, height=300, width=420)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        inner = ttk.Frame(canvas)
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.grid(row=2, column=0, columnspan=2, sticky="nsew", padx=(10, 0), pady=5)
        scrollbar.grid(row=2, column=2, sticky="ns", pady=5, padx=(0, 10))

        for idx, student in enumerate(students):
            ttk.Label(inner, text=student_names_by_id[student.id]).grid(row=idx, column=0, sticky="w", padx=6, pady=2)
            var = tk.StringVar(value="")
            self.student_rating_vars[student.id] = var
            cb = ttk.Combobox(inner, values=["", "-2", "-1", "0", "+1", "+2"], textvariable=var, width=6, state="readonly")
            cb.grid(row=idx, column=1, sticky="w", padx=6, pady=2)

        buttons = ttk.Frame(self)
        buttons.grid(row=3, column=0, columnspan=3, sticky="e", padx=10, pady=10)
        ttk.Button(buttons, text="Uložit", command=self.on_save).pack(side="right", padx=4)
        ttk.Button(buttons, text="Zrušit", command=self.on_cancel).pack(side="right", padx=4)

        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

    def on_save(self):
        student_ratings = {}
        for student_id, var in self.student_rating_vars.items():
            value = var.get().strip()
            if not value:
                continue
            student_ratings[student_id] = int(value.replace("+", ""))
        self.result = {"overall": int(self.overall_var.get()), "student_ratings": student_ratings}
        self.destroy()

    def on_cancel(self):
        self.result = None
        self.destroy()


class SeatingApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Zasedací pořádek - lokální aplikace")
        self.geometry("1450x840")

        self.db = Database(DB_PATH)
        self.current_classroom_id = None
        self.current_assignments: dict[int, int | None] = {}
        self.current_mode = "manual"
        self.selected_student_id = None
        self.locked_assignments: dict[int, int] = {}
        self.layout_edit_mode = False
        self.last_analysis = None

        self.classrooms_by_label = {}
        self.students_cache: list[Student] = []
        self.seats_cache: list[Seat] = []
        self.student_names_by_id: dict[int, str] = {}
        self.seat_buttons = {}

        self.create_widgets()
        self.refresh_classrooms()
        self.after(10, self.ensure_unlocked_on_start)

    def create_widgets(self):
        root = ttk.Frame(self, padding=10)
        root.pack(fill="both", expand=True)

        left = ttk.Frame(root)
        left.pack(side="left", fill="y")
        center = ttk.Frame(root)
        center.pack(side="left", fill="both", expand=True, padx=12)
        right = ttk.Frame(root)
        right.pack(side="left", fill="both")

        classroom_box = ttk.LabelFrame(left, text="Třída")
        classroom_box.pack(fill="x", pady=(0, 10))
        self.classroom_combo = ttk.Combobox(classroom_box, state="readonly", width=28)
        self.classroom_combo.pack(fill="x", padx=8, pady=8)
        self.classroom_combo.bind("<<ComboboxSelected>>", lambda e: self.on_select_classroom())
        ttk.Button(classroom_box, text="Načíst třídu", command=self.on_select_classroom).pack(fill="x", padx=8, pady=(0, 6))
        ttk.Button(classroom_box, text="Nová třída", command=self.create_classroom_dialog).pack(fill="x", padx=8, pady=(0, 8))

        students_box = ttk.LabelFrame(left, text="Žáci")
        students_box.pack(fill="both", expand=True)
        self.students_list = tk.Listbox(students_box, width=28, height=24)
        self.students_list.pack(fill="both", expand=True, padx=8, pady=8)
        self.students_list.bind("<<ListboxSelect>>", self.on_select_student)

        entry_frame = ttk.Frame(students_box)
        entry_frame.pack(fill="x", padx=8, pady=(0, 8))
        self.new_student_var = tk.StringVar()
        ttk.Entry(entry_frame, textvariable=self.new_student_var).pack(side="left", fill="x", expand=True)
        ttk.Button(entry_frame, text="Přidat", command=self.add_student).pack(side="left", padx=(6, 0))
        ttk.Button(students_box, text="Odebrat vybraného", command=self.remove_selected_student).pack(fill="x", padx=8, pady=(0, 8))

        actions = ttk.LabelFrame(center, text="Akce")
        actions.pack(fill="x", pady=(0, 10))
        ttk.Button(actions, text="Náhodně rozmístit", command=self.randomize).pack(side="left", padx=6, pady=8)
        ttk.Button(actions, text="Najít výhodné rozmístění", command=self.smart_generate).pack(side="left", padx=6, pady=8)
        ttk.Button(actions, text="Vyčistit", command=self.clear_assignments).pack(side="left", padx=6, pady=8)
        ttk.Button(actions, text="Uložit zámky", command=self.save_locks).pack(side="left", padx=6, pady=8)
        ttk.Button(actions, text="Ohodnotit tuto hodinu", command=self.rate_current_arrangement).pack(side="left", padx=6, pady=8)
        ttk.Button(actions, text="Přehled žáka", command=self.show_selected_student_insights).pack(side="left", padx=6, pady=8)

        self.layout_button_var = tk.StringVar(value="Upravit učebnu")
        ttk.Button(actions, textvariable=self.layout_button_var, command=self.toggle_layout_edit_mode).pack(side="left", padx=(18, 6), pady=8)
        ttk.Button(actions, text="Zapnout všechna místa", command=self.activate_all_seats).pack(side="left", padx=6, pady=8)
        export_pdf_btn = ttk.Button(actions, text="Export PDF", command=self.export_current_pdf)
        export_pdf_btn.pack(side="left", padx=(18, 6), pady=8)
        if not REPORTLAB_AVAILABLE:
            export_pdf_btn.state(["disabled"])
        ttk.Button(actions, text="Záloha DB", command=self.backup_database).pack(side="left", padx=6, pady=8)
        ttk.Button(actions, text="Obnovit DB", command=self.restore_database).pack(side="left", padx=6, pady=8)
        ttk.Button(actions, text="Nastavení", command=self.open_settings_dialog).pack(side="left", padx=(18, 6), pady=8)

        help_text = (
            "Normální režim: vyber žáka vlevo a klikni na místo.\n"
            "Dvojklik na místo = zamknout/odemknout. V režimu učebny klikáním vypínáš a zapínáš místa."
        )
        ttk.Label(actions, text=help_text).pack(side="left", padx=16)

        self.grid_frame = ttk.LabelFrame(center, text="Plánek třídy")
        self.grid_frame.pack(fill="both", expand=True)

        status_box = ttk.LabelFrame(right, text="Aktuální stav")
        status_box.pack(fill="x", pady=(0, 10))
        self.mode_var = tk.StringVar(value="Režim: manual")
        self.score_var = tk.StringVar(value="Skóre návrhu: 0.00")
        self.selected_var = tk.StringVar(value="Vybraný žák: -")
        self.layout_mode_var = tk.StringVar(value="Režim učebny: vypnutý")
        self.active_seats_var = tk.StringVar(value="Aktivní místa: 0")
        ttk.Label(status_box, textvariable=self.mode_var).pack(anchor="w", padx=8, pady=(8, 3))
        ttk.Label(status_box, textvariable=self.score_var).pack(anchor="w", padx=8, pady=3)
        ttk.Label(status_box, textvariable=self.selected_var).pack(anchor="w", padx=8, pady=3)
        ttk.Label(status_box, textvariable=self.layout_mode_var).pack(anchor="w", padx=8, pady=3)
        ttk.Label(status_box, textvariable=self.active_seats_var).pack(anchor="w", padx=8, pady=(3, 8))

        history_box = ttk.LabelFrame(right, text="Poslední rozesazení")
        history_box.pack(fill="both", expand=True)
        self.history_tree = ttk.Treeview(history_box, columns=("created", "mode", "rating"), show="headings", height=10)
        self.history_tree.heading("created", text="Čas")
        self.history_tree.heading("mode", text="Režim")
        self.history_tree.heading("rating", text="Celek")
        self.history_tree.column("created", width=140)
        self.history_tree.column("mode", width=90)
        self.history_tree.column("rating", width=60, anchor="center")
        self.history_tree.pack(fill="both", expand=True, padx=8, pady=8)
        ttk.Button(history_box, text="Načíst vybrané rozesazení", command=self.load_selected_history).pack(fill="x", padx=8, pady=(0, 8))

        explain_box = ttk.LabelFrame(right, text="Proč tento návrh")
        explain_box.pack(fill="both", expand=True, pady=(10, 0))
        self.explanation_summary_var = tk.StringVar(value="Zatím není co vysvětlovat.")
        ttk.Label(explain_box, textvariable=self.explanation_summary_var, wraplength=360, justify="left").pack(anchor="w", padx=8, pady=(8, 6))
        self.explanation_tree = ttk.Treeview(explain_box, columns=("type", "item", "score"), show="headings", height=12)
        self.explanation_tree.heading("type", text="Typ")
        self.explanation_tree.heading("item", text="Položka")
        self.explanation_tree.heading("score", text="Body")
        self.explanation_tree.column("type", width=80)
        self.explanation_tree.column("item", width=240)
        self.explanation_tree.column("score", width=70, anchor="e")
        self.explanation_tree.pack(fill="both", expand=True, padx=8, pady=(0, 8))

    def refresh_classrooms(self):
        classrooms = self.db.list_classrooms()
        labels = [f"{row['name']} ({row['rows_count']}×{row['cols_count']})" for row in classrooms]
        self.classrooms_by_label = {label: row["id"] for label, row in zip(labels, classrooms)}
        self.classroom_combo["values"] = labels
        if labels and not self.classroom_combo.get():
            self.classroom_combo.current(0)
            self.on_select_classroom()

    def create_classroom_dialog(self):
        dialog = tk.Toplevel(self)
        dialog.title("Nová třída")
        dialog.transient(self)
        dialog.grab_set()

        name_var = tk.StringVar()
        rows_var = tk.IntVar(value=4)
        cols_var = tk.IntVar(value=4)

        ttk.Label(dialog, text="Název třídy:").grid(row=0, column=0, sticky="w", padx=10, pady=8)
        ttk.Entry(dialog, textvariable=name_var, width=24).grid(row=0, column=1, padx=10, pady=8)
        ttk.Label(dialog, text="Počet řad:").grid(row=1, column=0, sticky="w", padx=10, pady=8)
        ttk.Spinbox(dialog, from_=1, to=10, textvariable=rows_var, width=8).grid(row=1, column=1, sticky="w", padx=10, pady=8)
        ttk.Label(dialog, text="Počet sloupců:").grid(row=2, column=0, sticky="w", padx=10, pady=8)
        ttk.Spinbox(dialog, from_=1, to=10, textvariable=cols_var, width=8).grid(row=2, column=1, sticky="w", padx=10, pady=8)

        def create_and_close():
            name = name_var.get().strip()
            if not name:
                messagebox.showwarning("Chybí název", "Zadej název třídy.")
                return
            try:
                classroom_id = self.db.create_classroom(name, int(rows_var.get()), int(cols_var.get()))
            except sqlite3.IntegrityError:
                messagebox.showerror("Chyba", "Třída s tímto názvem už existuje.")
                return
            dialog.destroy()
            self.refresh_classrooms()
            for label, cid in self.classrooms_by_label.items():
                if cid == classroom_id:
                    self.classroom_combo.set(label)
                    break
            self.on_select_classroom()

        buttons = ttk.Frame(dialog)
        buttons.grid(row=3, column=0, columnspan=2, sticky="e", padx=10, pady=10)
        ttk.Button(buttons, text="Vytvořit", command=create_and_close).pack(side="right", padx=4)
        ttk.Button(buttons, text="Zrušit", command=dialog.destroy).pack(side="right", padx=4)

    def normalize_assignments(self):
        active_seat_ids = {seat.id for seat in self.seats_cache if seat.is_active}
        normalized = {seat_id: self.current_assignments.get(seat_id) for seat_id in active_seat_ids}
        for seat_id in active_seat_ids:
            normalized.setdefault(seat_id, None)
        self.current_assignments = normalized
        self.locked_assignments = {
            seat_id: student_id
            for seat_id, student_id in self.locked_assignments.items()
            if seat_id in active_seat_ids and self.current_assignments.get(seat_id) == student_id
        }

    def on_select_classroom(self):
        label = self.classroom_combo.get()
        classroom_id = self.classrooms_by_label.get(label)
        if not classroom_id:
            return
        self.current_classroom_id = classroom_id
        self.students_cache = self.db.list_students(classroom_id)
        self.seats_cache = self.db.list_seats(classroom_id)
        self.student_names_by_id = self.db.get_student_name_map(classroom_id)
        self.locked_assignments = self.db.get_locks(classroom_id)
        self.current_assignments = {seat.id: None for seat in self.seats_cache if seat.is_active}
        self.layout_edit_mode = False
        self.layout_button_var.set("Upravit učebnu")
        self.layout_mode_var.set("Režim učebny: vypnutý")
        self.refresh_students_list()
        self.render_grid()
        self.refresh_history()
        self.recompute_score()
        self.mode_var.set("Režim: manual")

    def refresh_students_list(self):
        self.students_list.delete(0, tk.END)
        for student in self.students_cache:
            self.students_list.insert(tk.END, student.display_name)

    def render_grid(self):
        for widget in self.grid_frame.winfo_children():
            widget.destroy()
        self.seat_buttons = {}
        if not self.seats_cache:
            return
        max_row = max(seat.row_index for seat in self.seats_cache)
        max_col = max(seat.col_index for seat in self.seats_cache)
        for r in range(max_row + 1):
            self.grid_frame.rowconfigure(r, weight=1)
        for c in range(max_col + 1):
            self.grid_frame.columnconfigure(c, weight=1)

        for seat in self.seats_cache:
            btn = tk.Button(
                self.grid_frame,
                text=self.format_seat_text(seat.id),
                width=16,
                height=4,
                wraplength=110,
                command=lambda seat_id=seat.id: self.on_click_seat(seat_id),
            )
            btn.bind("<Double-Button-1>", lambda event, seat_id=seat.id: self.toggle_lock(seat_id))
            btn.grid(row=seat.row_index, column=seat.col_index, padx=6, pady=6, sticky="nsew")
            self.seat_buttons[seat.id] = btn
        self.update_grid_visuals()

    def format_seat_text(self, seat_id: int):
        seat = next((s for s in self.seats_cache if s.id == seat_id), None)
        if seat is None:
            return ""
        if not seat.is_active:
            return f"{seat.label}\nNEAKTIVNÍ"
        student_id = self.current_assignments.get(seat_id)
        student_name = self.student_names_by_id.get(student_id, "-") if student_id else "-"
        lock_marker = "🔒" if self.locked_assignments.get(seat_id) == student_id and student_id is not None else ""
        return f"{seat.label} {lock_marker}\n{student_name}"

    def update_grid_visuals(self):
        active_count = 0
        for seat in self.seats_cache:
            btn = self.seat_buttons.get(seat.id)
            if not btn:
                continue
            btn.configure(text=self.format_seat_text(seat.id))
            if not seat.is_active:
                btn.configure(bg="#404040", fg="#ffffff", activebackground="#404040", state="normal")
                continue
            active_count += 1
            btn.configure(fg="#000000", activebackground="#d6e9ff")
            student_id = self.current_assignments.get(seat.id)
            if self.layout_edit_mode:
                btn.configure(bg="#d6e9ff")
            elif self.locked_assignments.get(seat.id) == student_id and student_id is not None:
                btn.configure(bg="#fff1bf")
            else:
                btn.configure(bg="#f4f4f4")
        self.active_seats_var.set(f"Aktivní místa: {active_count}")

    def on_select_student(self, event=None):
        indices = self.students_list.curselection()
        if not indices:
            self.selected_student_id = None
            self.selected_var.set("Vybraný žák: -")
            return
        student = self.students_cache[indices[0]]
        self.selected_student_id = student.id
        self.selected_var.set(f"Vybraný žák: {student.display_name}")

    def on_click_seat(self, seat_id: int):
        if not self.current_classroom_id:
            return
        seat = next((s for s in self.seats_cache if s.id == seat_id), None)
        if seat is None:
            return
        if self.layout_edit_mode:
            self.toggle_seat_active(seat_id)
            return
        if not seat.is_active:
            return
        if self.selected_student_id is None:
            self.unassign_seat(seat_id)
            return
        current_seat = next((sid for sid, stu in self.current_assignments.items() if stu == self.selected_student_id), None)
        displaced_student = self.current_assignments.get(seat_id)
        self.current_assignments[seat_id] = self.selected_student_id
        if current_seat is not None and current_seat != seat_id:
            self.current_assignments[current_seat] = displaced_student
        self.current_mode = "manual"
        self.mode_var.set("Režim: manual")
        self.update_grid_visuals()
        self.recompute_score()

    def unassign_seat(self, seat_id: int):
        if seat_id in self.current_assignments:
            self.current_assignments[seat_id] = None
        self.current_mode = "manual"
        self.mode_var.set("Režim: manual")
        self.update_grid_visuals()
        self.recompute_score()

    def toggle_layout_edit_mode(self):
        if not self.current_classroom_id:
            return
        self.layout_edit_mode = not self.layout_edit_mode
        self.layout_button_var.set("Ukončit úpravu učebny" if self.layout_edit_mode else "Upravit učebnu")
        self.layout_mode_var.set("Režim učebny: zapnutý" if self.layout_edit_mode else "Režim učebny: vypnutý")
        self.update_grid_visuals()

    def toggle_seat_active(self, seat_id: int):
        seat = next((s for s in self.seats_cache if s.id == seat_id), None)
        if seat is None:
            return
        new_active = not seat.is_active
        self.db.set_seat_active(seat_id, new_active)
        self.seats_cache = [
            Seat(s.id, s.row_index, s.col_index, s.label, new_active if s.id == seat_id else s.is_active)
            for s in self.seats_cache
        ]
        if not new_active:
            self.current_assignments.pop(seat_id, None)
            self.locked_assignments.pop(seat_id, None)
        else:
            self.current_assignments.setdefault(seat_id, None)
        self.normalize_assignments()
        self.update_grid_visuals()
        self.recompute_score()

    def activate_all_seats(self):
        if not self.current_classroom_id:
            return
        self.db.activate_all_seats(self.current_classroom_id)
        self.seats_cache = [Seat(seat.id, seat.row_index, seat.col_index, seat.label, True) for seat in self.seats_cache]
        for seat in self.seats_cache:
            self.current_assignments.setdefault(seat.id, None)
        self.normalize_assignments()
        self.update_grid_visuals()
        self.recompute_score()

    def add_student(self):
        if not self.current_classroom_id:
            messagebox.showwarning("Bez třídy", "Nejprve vytvoř nebo načti třídu.")
            return
        name = self.new_student_var.get().strip()
        if not name:
            return
        try:
            self.db.add_student(self.current_classroom_id, name)
        except sqlite3.IntegrityError:
            messagebox.showerror("Chyba", "Žák s tímto jménem už v této třídě existuje.")
            return
        self.new_student_var.set("")
        self.students_cache = self.db.list_students(self.current_classroom_id)
        self.student_names_by_id = self.db.get_student_name_map(self.current_classroom_id)
        self.refresh_students_list()
        self.recompute_score()

    def remove_selected_student(self):
        indices = self.students_list.curselection()
        if not indices or not self.current_classroom_id:
            return
        student = self.students_cache[indices[0]]
        if not messagebox.askyesno("Odebrat", f"Odebrat žáka {student.display_name} z aktivního seznamu?"):
            return
        self.db.deactivate_student(student.id)
        for seat_id, occupant in list(self.current_assignments.items()):
            if occupant == student.id:
                self.current_assignments[seat_id] = None
        self.locked_assignments = {seat_id: sid for seat_id, sid in self.locked_assignments.items() if sid != student.id}
        self.students_cache = self.db.list_students(self.current_classroom_id)
        self.student_names_by_id = self.db.get_student_name_map(self.current_classroom_id)
        self.refresh_students_list()
        self.update_grid_visuals()
        self.recompute_score()

    def build_engine(self):
        return SeatingEngine(
            self.seats_cache,
            self.students_cache,
            self.db.load_pair_scores(self.current_classroom_id),
            self.db.load_seat_scores(self.current_classroom_id),
            self.locked_assignments,
        )

    def randomize(self):
        if not self.current_classroom_id:
            return
        engine = self.build_engine()
        self.current_assignments = engine.random_arrangement()
        self.current_mode = "random"
        self.mode_var.set("Režim: random")
        self.update_grid_visuals()
        self.recompute_score()

    def smart_generate(self):
        if not self.current_classroom_id:
            return
        engine = self.build_engine()
        active_seat_count = sum(1 for seat in self.seats_cache if seat.is_active)
        iterations = engine.recommend_iterations(len(self.students_cache), active_seat_count)
        arrangement, _ = engine.best_of_random_search(iterations=iterations)
        self.current_assignments = arrangement
        self.current_mode = "smart"
        self.mode_var.set(f"Režim: smart ({iterations} pokusů)")
        self.update_grid_visuals()
        self.recompute_score()

    def clear_assignments(self):
        self.current_assignments = {seat.id: None for seat in self.seats_cache if seat.is_active}
        self.current_mode = "manual"
        self.mode_var.set("Režim: manual")
        self.update_grid_visuals()
        self.recompute_score()

    def toggle_lock(self, seat_id: int):
        if self.layout_edit_mode:
            return
        seat = next((s for s in self.seats_cache if s.id == seat_id), None)
        if seat is None or not seat.is_active:
            return
        student_id = self.current_assignments.get(seat_id)
        if student_id is None:
            return
        if self.locked_assignments.get(seat_id) == student_id:
            self.locked_assignments.pop(seat_id, None)
        else:
            for s_id, locked_student in list(self.locked_assignments.items()):
                if locked_student == student_id:
                    self.locked_assignments.pop(s_id, None)
            self.locked_assignments[seat_id] = student_id
        self.update_grid_visuals()
        self.recompute_score()

    def save_locks(self):
        if not self.current_classroom_id:
            return
        active_locks = {
            seat_id: student_id
            for seat_id, student_id in self.locked_assignments.items()
            if self.current_assignments.get(seat_id) == student_id
        }
        self.locked_assignments = active_locks
        self.db.save_locks(self.current_classroom_id, active_locks)
        self.update_grid_visuals()
        messagebox.showinfo("Uloženo", "Zámky byly uloženy pro další generování.")

    def show_selected_student_insights(self):
        if not self.current_classroom_id:
            messagebox.showwarning("Bez třídy", "Nejprve načti třídu.")
            return
        if self.selected_student_id is None:
            messagebox.showwarning("Bez výběru", "Vyber žáka v levém seznamu.")
            return

        student_name = self.student_names_by_id.get(self.selected_student_id, str(self.selected_student_id))
        pair_rows = self.db.get_student_pair_insights(self.current_classroom_id, self.selected_student_id, limit=30)
        seat_rows = self.db.get_student_seat_insights(self.current_classroom_id, self.selected_student_id, limit=20)

        dialog = tk.Toplevel(self)
        dialog.title(f"Přehled vazeb: {student_name}")
        dialog.transient(self)
        dialog.grab_set()
        dialog.geometry("880x620")

        header = ttk.Label(
            dialog,
            text=f"Přehled žáka: {student_name} | párové vazby: {len(pair_rows)} | poziční vazby: {len(seat_rows)}",
        )
        header.pack(anchor="w", padx=10, pady=(10, 6))

        pair_box = ttk.LabelFrame(dialog, text="Sousedi a spolužáci")
        pair_box.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        pair_tree = ttk.Treeview(pair_box, columns=("student", "prox", "score", "obs"), show="headings", height=10)
        pair_tree.heading("student", text="Spolužák")
        pair_tree.heading("prox", text="Typ")
        pair_tree.heading("score", text="Průměr")
        pair_tree.heading("obs", text="Pozorování")
        pair_tree.column("student", width=280)
        pair_tree.column("prox", width=120, anchor="center")
        pair_tree.column("score", width=110, anchor="e")
        pair_tree.column("obs", width=110, anchor="e")
        pair_tree.pack(fill="both", expand=True, padx=8, pady=8)

        for row in pair_rows:
            prox = "vedle sebe" if row["proximity"] == "side" else "před/za"
            other_name = self.student_names_by_id.get(row["other_student_id"], str(row["other_student_id"]))
            pair_tree.insert("", "end", values=(other_name, prox, f"{row['avg_score']:+.2f}", row["observations"]))

        seat_box = ttk.LabelFrame(dialog, text="Oblíbené / problematické pozice")
        seat_box.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        seat_tree = ttk.Treeview(seat_box, columns=("seat", "score", "obs"), show="headings", height=8)
        seat_tree.heading("seat", text="Místo")
        seat_tree.heading("score", text="Průměr")
        seat_tree.heading("obs", text="Pozorování")
        seat_tree.column("seat", width=240)
        seat_tree.column("score", width=110, anchor="e")
        seat_tree.column("obs", width=110, anchor="e")
        seat_tree.pack(fill="both", expand=True, padx=8, pady=8)

        for row in seat_rows:
            seat_tree.insert("", "end", values=(row["seat_label"], f"{row['avg_score']:+.2f}", row["observations"]))

        if not pair_rows and not seat_rows:
            ttk.Label(
                dialog,
                text="Zatím nejsou k dispozici žádná historická data pro tohoto žáka.",
            ).pack(anchor="w", padx=10, pady=(0, 10))

    def ensure_unlocked_on_start(self):
        pin_hash = self.db.get_setting(PIN_HASH_SETTING_KEY)
        if not pin_hash:
            return
        if not self.prompt_unlock_dialog("Aplikace je uzamčena. Zadej PIN pro pokračování.", allow_cancel=False):
            self.after(0, self.on_close)

    def configure_pin(self):
        dialog = tk.Toplevel(self)
        dialog.title("Nastavení PIN")
        dialog.transient(self)
        dialog.grab_set()

        existing_hash = self.db.get_setting(PIN_HASH_SETTING_KEY)
        current_var = tk.StringVar()
        new_var = tk.StringVar()
        confirm_var = tk.StringVar()

        row = 0
        ttk.Label(dialog, text="Nastavení lokálního PINu aplikace").grid(row=row, column=0, columnspan=2, sticky="w", padx=10, pady=(10, 8))
        row += 1

        if existing_hash:
            ttk.Label(dialog, text="Aktuální PIN:").grid(row=row, column=0, sticky="w", padx=10, pady=5)
            ttk.Entry(dialog, textvariable=current_var, show="*", width=22).grid(row=row, column=1, sticky="w", padx=10, pady=5)
            row += 1

        ttk.Label(dialog, text="Nový PIN (min. 4 číslice):").grid(row=row, column=0, sticky="w", padx=10, pady=5)
        ttk.Entry(dialog, textvariable=new_var, show="*", width=22).grid(row=row, column=1, sticky="w", padx=10, pady=5)
        row += 1
        ttk.Label(dialog, text="Potvrzení PINu:").grid(row=row, column=0, sticky="w", padx=10, pady=5)
        ttk.Entry(dialog, textvariable=confirm_var, show="*", width=22).grid(row=row, column=1, sticky="w", padx=10, pady=5)
        row += 1

        buttons = ttk.Frame(dialog)
        buttons.grid(row=row, column=0, columnspan=2, sticky="e", padx=10, pady=(10, 10))

        def on_save():
            if existing_hash and hash_pin(current_var.get().strip()) != existing_hash:
                messagebox.showerror("Chybný PIN", "Aktuální PIN nesouhlasí.")
                return
            new_pin = new_var.get().strip()
            confirm_pin = confirm_var.get().strip()
            if len(new_pin) < 4 or not new_pin.isdigit():
                messagebox.showerror("Neplatný PIN", "PIN musí mít alespoň 4 číslice.")
                return
            if new_pin != confirm_pin:
                messagebox.showerror("Neshoda", "Nový PIN a potvrzení se neshodují.")
                return
            self.db.set_setting(PIN_HASH_SETTING_KEY, hash_pin(new_pin))
            messagebox.showinfo("Uloženo", "PIN byl nastaven.")
            dialog.destroy()

        def on_remove():
            if not existing_hash:
                return
            if hash_pin(current_var.get().strip()) != existing_hash:
                messagebox.showerror("Chybný PIN", "Aktuální PIN nesouhlasí.")
                return
            if not messagebox.askyesno("Odebrat PIN", "Opravdu chceš odstranit PIN ochranu aplikace?"):
                return
            self.db.set_setting(PIN_HASH_SETTING_KEY, "")
            messagebox.showinfo("Hotovo", "PIN byl odstraněn.")
            dialog.destroy()

        ttk.Button(buttons, text="Uložit PIN", command=on_save).pack(side="right", padx=4)
        if existing_hash:
            ttk.Button(buttons, text="Odebrat PIN", command=on_remove).pack(side="right", padx=4)
        ttk.Button(buttons, text="Zavřít", command=dialog.destroy).pack(side="right", padx=4)

    def open_settings_dialog(self):
        dialog = tk.Toplevel(self)
        dialog.title("Nastavení")
        dialog.transient(self)
        dialog.grab_set()

        ttk.Label(dialog, text="Nastavení aplikace", font=("TkDefaultFont", 10, "bold")).pack(anchor="w", padx=10, pady=(10, 8))
        ttk.Label(
            dialog,
            text="PIN ochrana je lokální a volitelná. Pokud ji nechceš používat, nech ji vypnutou.",
            wraplength=420,
            justify="left",
        ).pack(anchor="w", padx=10, pady=(0, 10))

        controls = ttk.Frame(dialog)
        controls.pack(fill="x", padx=10, pady=(0, 10))
        ttk.Button(controls, text="Nastavit / změnit PIN", command=self.configure_pin).pack(side="left", padx=(0, 8))
        ttk.Button(controls, text="Zamknout aplikaci", command=self.lock_app).pack(side="left", padx=(0, 8))
        ttk.Button(controls, text="Archivace starých dat", command=self.purge_old_data).pack(side="left", padx=(0, 8))
        ttk.Button(controls, text="Zavřít", command=dialog.destroy).pack(side="right")

    def purge_old_data(self):
        months = simpledialog.askinteger(
            "Archivace dat",
            "Smazat historii rozesazení starší než kolik měsíců?\n(Doporučeno: 12)",
            minvalue=1,
            maxvalue=120,
            initialvalue=12,
            parent=self,
        )
        if months is None:
            return
        cutoff = datetime.now() - timedelta(days=30 * months)
        cutoff_iso = cutoff.isoformat(timespec="seconds")
        deleted = self.db.delete_arrangements_older_than(cutoff_iso)
        self.refresh_history()
        messagebox.showinfo(
            "Archivace hotová",
            f"Smazané záznamy historie: {deleted}\nHranice: {cutoff.strftime('%Y-%m-%d')}",
        )

    def prompt_unlock_dialog(self, message: str, allow_cancel: bool = True) -> bool:
        pin_hash = self.db.get_setting(PIN_HASH_SETTING_KEY)
        if not pin_hash:
            return True

        dialog = tk.Toplevel(self)
        dialog.title("Odemknout aplikaci")
        dialog.transient(self)
        dialog.grab_set()

        ttk.Label(dialog, text=message, wraplength=360, justify="left").grid(row=0, column=0, columnspan=2, sticky="w", padx=10, pady=(10, 8))
        pin_var = tk.StringVar()
        ttk.Label(dialog, text="PIN:").grid(row=1, column=0, sticky="w", padx=10, pady=6)
        ttk.Entry(dialog, textvariable=pin_var, show="*", width=22).grid(row=1, column=1, sticky="w", padx=10, pady=6)

        result = {"ok": False}

        def on_unlock():
            if hash_pin(pin_var.get().strip()) == pin_hash:
                result["ok"] = True
                dialog.destroy()
            else:
                messagebox.showerror("Chybný PIN", "PIN není správný.")

        def on_cancel():
            result["ok"] = False
            dialog.destroy()

        buttons = ttk.Frame(dialog)
        buttons.grid(row=2, column=0, columnspan=2, sticky="e", padx=10, pady=(4, 10))
        ttk.Button(buttons, text="Odemknout", command=on_unlock).pack(side="right", padx=4)
        if allow_cancel:
            ttk.Button(buttons, text="Zrušit", command=on_cancel).pack(side="right", padx=4)

        if not allow_cancel:
            dialog.protocol("WM_DELETE_WINDOW", lambda: None)
        else:
            dialog.protocol("WM_DELETE_WINDOW", on_cancel)

        self.wait_window(dialog)
        return result["ok"]

    def lock_app(self):
        pin_hash = self.db.get_setting(PIN_HASH_SETTING_KEY)
        if not pin_hash:
            messagebox.showinfo("Bez PINu", "Nejprve nastav PIN přes tlačítko 'Nastavit PIN'.")
            return
        self.prompt_unlock_dialog("Aplikace je uzamčena. Pro odemknutí zadej PIN.", allow_cancel=False)

    def refresh_explanation(self, analysis=None):
        for item in self.explanation_tree.get_children():
            self.explanation_tree.delete(item)
        analysis = analysis if analysis is not None else self.last_analysis
        if analysis is None:
            self.explanation_summary_var.set("Zatím není co vysvětlovat.")
            return
        self.explanation_summary_var.set(
            f"Součet pozic: {analysis['seat_total']:+.2f} | součet sousedství: {analysis['pair_total']:+.2f} | známé vazby v návrhu: {len(analysis['seat_terms']) + len(analysis['pair_terms'])}"
        )
        combined = []
        seat_map = {seat.id: seat for seat in self.seats_cache}
        for term in analysis["seat_terms"]:
            seat = seat_map.get(term["seat_id"])
            seat_label = seat.label if seat else str(term["seat_id"])
            student_name = self.student_names_by_id.get(term["student_id"], str(term["student_id"]))
            combined.append((abs(term["contribution"]), "Pozice", f"{student_name} na {seat_label}", term["contribution"]))
        for term in analysis["pair_terms"]:
            prox = "vedle sebe" if term["proximity"] == "side" else "před/za"
            a_name = self.student_names_by_id.get(term["student_a_id"], str(term["student_a_id"]))
            b_name = self.student_names_by_id.get(term["student_b_id"], str(term["student_b_id"]))
            combined.append((abs(term["contribution"]), "Dvojice", f"{a_name} × {b_name} ({prox})", term["contribution"]))
        if not combined:
            self.explanation_summary_var.set(
                "Tento návrh zatím nemá žádné známé plusové ani minusové vazby. Random a smart proto mohou vycházet podobně."
            )
            return
        combined.sort(key=lambda x: x[0], reverse=True)
        for _, typ, item_text, contribution in combined[:12]:
            self.explanation_tree.insert("", "end", values=(typ, item_text, f"{contribution:+.2f}"))

    def recompute_score(self):
        if not self.current_classroom_id:
            self.score_var.set("Skóre návrhu: 0.00")
            self.last_analysis = None
            self.refresh_explanation()
            return
        engine = self.build_engine()
        analysis = engine.analyze_arrangement(self.current_assignments)
        self.last_analysis = analysis
        self.score_var.set(f"Skóre návrhu: {analysis['total']:.2f}")
        self.refresh_explanation(analysis)

    def rate_current_arrangement(self):
        if not self.current_classroom_id:
            return
        if not any(self.current_assignments.values()):
            messagebox.showwarning("Bez rozesazení", "Nejprve rozmísti žáky.")
            return
        dialog = RatingDialog(self, self.students_cache, self.student_names_by_id)
        self.wait_window(dialog)
        if dialog.result is None:
            return
        arrangement_id = self.db.save_arrangement(
            self.current_classroom_id,
            self.current_mode,
            self.current_assignments,
            notes={"rated_immediately": True},
        )
        overall = dialog.result["overall"]
        student_ratings = dialog.result["student_ratings"]
        self.db.save_feedback(arrangement_id, overall, student_ratings)
        self.db.update_scores_from_feedback(
            self.current_classroom_id,
            self.seats_cache,
            self.current_assignments,
            overall,
            student_ratings,
        )
        self.refresh_history()
        self.recompute_score()
        messagebox.showinfo("Uloženo", "Hodnocení bylo uloženo a model se průběžně aktualizoval.")

    def refresh_history(self):
        for item in self.history_tree.get_children():
            self.history_tree.delete(item)
        if not self.current_classroom_id:
            return
        for row in self.db.list_recent_arrangements(self.current_classroom_id, limit=20):
            rating = "-" if row["overall_rating"] is None else row["overall_rating"]
            self.history_tree.insert("", "end", iid=str(row["id"]), values=(row["created_at"].replace("T", " "), row["mode"], rating))

    def load_selected_history(self):
        selected = self.history_tree.selection()
        if not selected:
            return
        arrangement_id = int(selected[0])
        self.current_assignments = self.db.get_arrangement_assignments(arrangement_id)
        self.normalize_assignments()
        self.current_mode = "history"
        self.mode_var.set("Režim: history")
        self.update_grid_visuals()
        self.recompute_score()

    def export_current_pdf(self):
        if not self.current_classroom_id:
            return
        if not self.seats_cache:
            messagebox.showwarning("Bez třídy", "Nejprve načti třídu.")
            return
        classroom = self.db.get_classroom(self.current_classroom_id)
        safe_name = classroom["name"].replace(" ", "_") if classroom else "trida"
        default_name = f"zasedaci_poradek_{safe_name}_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
        path = filedialog.asksaveasfilename(
            title="Exportovat do PDF",
            defaultextension=".pdf",
            initialfile=default_name,
            filetypes=[("PDF", "*.pdf")],
        )
        if not path:
            return
        try:
            export_arrangement_pdf(
                path,
                classroom["name"] if classroom else "Třída",
                self.current_mode,
                self.last_analysis["total"] if self.last_analysis else 0.0,
                self.seats_cache,
                self.current_assignments,
                self.student_names_by_id,
                self.last_analysis,
            )
        except Exception as e:
            messagebox.showerror("Chyba exportu", f"PDF se nepodařilo vytvořit.\n\n{e}")
            return
        messagebox.showinfo("Export hotov", f"PDF bylo uloženo:\n{path}")

    def backup_database(self):
        default_name = f"seating_app_backup_{datetime.now().strftime('%Y%m%d_%H%M')}.db"
        path = filedialog.asksaveasfilename(
            title="Uložit zálohu databáze",
            defaultextension=".db",
            initialfile=default_name,
            filetypes=[("Databáze SQLite", "*.db"), ("Všechny soubory", "*.*")],
        )
        if not path:
            return
        try:
            self.db.conn.commit()
            shutil.copy2(DB_PATH, path)
        except Exception as e:
            messagebox.showerror("Chyba zálohy", f"Zálohu se nepodařilo uložit.\n\n{e}")
            return
        messagebox.showinfo("Záloha hotová", f"Databáze byla zazálohována do:\n{path}")

    def restore_database(self):
        path = filedialog.askopenfilename(
            title="Obnovit databázi ze zálohy",
            filetypes=[("Databáze SQLite", "*.db"), ("Všechny soubory", "*.*")],
        )
        if not path:
            return
        if not messagebox.askyesno(
            "Obnovit databázi",
            "Opravdu chceš přepsat aktuální lokální databázi vybranou zálohou? Tato akce nelze vrátit zpět.",
        ):
            return
        try:
            self.db.close()
            shutil.copy2(path, DB_PATH)
            self.db = Database(DB_PATH)
            self.current_classroom_id = None
            self.current_assignments = {}
            self.locked_assignments = {}
            self.students_cache = []
            self.seats_cache = []
            self.student_names_by_id = {}
            self.last_analysis = None
            self.classroom_combo.set("")
            self.refresh_classrooms()
            self.render_grid()
            self.refresh_history()
            self.recompute_score()
        except Exception as e:
            try:
                self.db = Database(DB_PATH)
            except Exception:
                pass
            messagebox.showerror("Chyba obnovy", f"Databázi se nepodařilo obnovit.\n\n{e}")
            return
        messagebox.showinfo("Obnova hotová", "Databáze byla obnovena ze zálohy.")

    def on_close(self):
        self.db.close()
        self.destroy()


def main():
    app = SeatingApp()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()


if __name__ == "__main__":
    main()
