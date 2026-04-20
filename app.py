import json
import random
import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox

APP_DIR = Path(__file__).resolve().parent
DB_PATH = APP_DIR / "seating_app.db"


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
"""


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
        return self.conn.execute(
            "SELECT id, name, rows_count, cols_count FROM classrooms ORDER BY name"
        ).fetchall()

    def create_classroom(self, name: str, rows_count: int, cols_count: int):
        now = datetime.now().isoformat(timespec="seconds")
        with self.conn:
            cur = self.conn.execute(
                "INSERT INTO classrooms(name, rows_count, cols_count, created_at) VALUES (?, ?, ?, ?)",
                (name, rows_count, cols_count, now),
            )
            classroom_id = cur.lastrowid
            labels = []
            for r in range(rows_count):
                for c in range(cols_count):
                    label = f"{chr(65 + r)}{c + 1}"
                    labels.append((classroom_id, r, c, label))
            self.conn.executemany(
                "INSERT INTO seats(classroom_id, row_index, col_index, label) VALUES (?, ?, ?, ?)", labels
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

    def list_recent_arrangements(self, classroom_id: int, limit: int = 10):
        return self.conn.execute(
            "SELECT id, created_at, mode, overall_rating FROM arrangements WHERE classroom_id = ? ORDER BY id DESC LIMIT ?",
            (classroom_id, limit),
        ).fetchall()

    def get_arrangement_assignments(self, arrangement_id: int):
        rows = self.conn.execute(
            "SELECT seat_id, student_id FROM arrangement_assignments WHERE arrangement_id = ?",
            (arrangement_id,),
        ).fetchall()
        return {r["seat_id"]: r["student_id"] for r in rows}

    def save_feedback(self, arrangement_id: int, overall_rating: int, student_ratings: dict[int, int]):
        with self.conn:
            self.conn.execute(
                "UPDATE arrangements SET overall_rating = ? WHERE id = ?",
                (overall_rating, arrangement_id),
            )
            self.conn.execute("DELETE FROM student_feedback WHERE arrangement_id = ?", (arrangement_id,))
            self.conn.executemany(
                "INSERT INTO student_feedback(arrangement_id, student_id, rating) VALUES (?, ?, ?)",
                [(arrangement_id, sid, rating) for sid, rating in student_ratings.items()],
            )

    def _upsert_avg(self, table: str, key_fields: tuple, values: dict):
        if table == "pair_scores":
            existing = self.conn.execute(
                "SELECT id, avg_score, observations FROM pair_scores WHERE classroom_id=? AND student_a_id=? AND student_b_id=? AND proximity=?",
                key_fields,
            ).fetchone()
            if existing:
                old_avg = float(existing["avg_score"])
                obs = int(existing["observations"])
                new_avg = (old_avg * obs + values["score"]) / (obs + 1)
                self.conn.execute(
                    "UPDATE pair_scores SET avg_score=?, observations=? WHERE id=?",
                    (new_avg, obs + 1, existing["id"]),
                )
            else:
                self.conn.execute(
                    "INSERT INTO pair_scores(classroom_id, student_a_id, student_b_id, proximity, avg_score, observations) VALUES (?, ?, ?, ?, ?, 1)",
                    (*key_fields, values["score"]),
                )
        elif table == "seat_scores":
            existing = self.conn.execute(
                "SELECT id, avg_score, observations FROM seat_scores WHERE classroom_id=? AND student_id=? AND seat_id=?",
                key_fields,
            ).fetchone()
            if existing:
                old_avg = float(existing["avg_score"])
                obs = int(existing["observations"])
                new_avg = (old_avg * obs + values["score"]) / (obs + 1)
                self.conn.execute(
                    "UPDATE seat_scores SET avg_score=?, observations=? WHERE id=?",
                    (new_avg, obs + 1, existing["id"]),
                )
            else:
                self.conn.execute(
                    "INSERT INTO seat_scores(classroom_id, student_id, seat_id, avg_score, observations) VALUES (?, ?, ?, ?, 1)",
                    (*key_fields, values["score"]),
                )
        else:
            raise ValueError("Unsupported table")

    def update_scores_from_feedback(
        self,
        classroom_id: int,
        seats: list[Seat],
        assignments: dict[int, int | None],
        overall_rating: int,
        student_ratings: dict[int, int],
    ):
        occupied = {sid: stu for sid, stu in assignments.items() if stu is not None}
        neighbors = self._build_neighbors(seats)

        with self.conn:
            if overall_rating != 0:
                weak = overall_rating * 0.25
                for seat_id, student_id in occupied.items():
                    self._upsert_avg("seat_scores", (classroom_id, student_id, seat_id), {"score": weak})
                    for proximity, other_id in self._iter_neighbors(occupied, neighbors, seat_id):
                        a, b = sorted((student_id, other_id))
                        self._upsert_avg(
                            "pair_scores",
                            (classroom_id, a, b, proximity),
                            {"score": weak},
                        )

            for student_id, rating in student_ratings.items():
                if rating == 0:
                    continue
                seat_id = next((s for s, stu in occupied.items() if stu == student_id), None)
                if seat_id is None:
                    continue
                self._upsert_avg("seat_scores", (classroom_id, student_id, seat_id), {"score": rating * 0.8})
                for proximity, other_id in self._iter_neighbors(occupied, neighbors, seat_id):
                    a, b = sorted((student_id, other_id))
                    factor = 1.0 if proximity == "side" else 0.5
                    self._upsert_avg(
                        "pair_scores",
                        (classroom_id, a, b, proximity),
                        {"score": rating * factor},
                    )

    def _iter_neighbors(self, occupied: dict[int, int], neighbors: dict[int, list[tuple[str, int]]], seat_id: int):
        seen = set()
        for proximity, other_seat_id in neighbors.get(seat_id, []):
            other_id = occupied.get(other_seat_id)
            if other_id is None:
                continue
            key = (proximity, other_id)
            if key in seen:
                continue
            seen.add(key)
            yield proximity, other_id

    def _build_neighbors(self, seats: list[Seat]):
        index = {(seat.row_index, seat.col_index): seat.id for seat in seats if seat.is_active}
        neighbors = defaultdict(list)
        for seat in seats:
            if not seat.is_active:
                continue
            for delta, proximity in [((0, -1), "side"), ((0, 1), "side"), ((-1, 0), "front_back"), ((1, 0), "front_back")]:
                key = (seat.row_index + delta[0], seat.col_index + delta[1])
                if key in index:
                    neighbors[seat.id].append((proximity, index[key]))
        return neighbors

    def load_pair_scores(self, classroom_id: int):
        rows = self.conn.execute(
            "SELECT student_a_id, student_b_id, proximity, avg_score, observations FROM pair_scores WHERE classroom_id = ?",
            (classroom_id,),
        ).fetchall()
        result = {}
        for r in rows:
            result[(r["student_a_id"], r["student_b_id"], r["proximity"])] = (float(r["avg_score"]), int(r["observations"]))
        return result

    def load_seat_scores(self, classroom_id: int):
        rows = self.conn.execute(
            "SELECT student_id, seat_id, avg_score, observations FROM seat_scores WHERE classroom_id = ?",
            (classroom_id,),
        ).fetchall()
        result = {}
        for r in rows:
            result[(r["student_id"], r["seat_id"])] = (float(r["avg_score"]), int(r["observations"]))
        return result


class SeatingEngine:
    def __init__(self, seats: list[Seat], students: list[Student], pair_scores, seat_scores, locked: dict[int, int]):
        self.seats = [s for s in seats if s.is_active]
        self.seat_map = {seat.id: seat for seat in self.seats}
        self.students = students
        self.pair_scores = pair_scores
        self.seat_scores = seat_scores
        self.locked = {seat_id: student_id for seat_id, student_id in locked.items() if seat_id in self.seat_map}
        self.neighbors = self._build_neighbors(self.seats)

    def _build_neighbors(self, seats: list[Seat]):
        index = {(seat.row_index, seat.col_index): seat.id for seat in seats}
        neighbors = defaultdict(list)
        for seat in seats:
            for delta, proximity in [((0, -1), "side"), ((0, 1), "side"), ((-1, 0), "front_back"), ((1, 0), "front_back")]:
                key = (seat.row_index + delta[0], seat.col_index + delta[1])
                if key in index:
                    neighbors[seat.id].append((proximity, index[key]))
        return neighbors

    def random_arrangement(self):
        assignments = {seat.id: None for seat in self.seats}
        locked_student_ids = set(self.locked.values())
        unlocked_students = [stu.id for stu in self.students if stu.id not in locked_student_ids]
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
            seat_score = self.seat_scores.get((student_id, seat_id))
            if seat_score:
                avg, obs = seat_score
                contribution = avg * (1 + min(obs, 5) * 0.1)
                seat_total += contribution
                seat_terms.append(
                    {
                        "type": "seat",
                        "seat_id": seat_id,
                        "student_id": student_id,
                        "contribution": contribution,
                        "avg": avg,
                        "observations": obs,
                    }
                )

        visited_pairs = set()
        for seat_id, student_id in assignments.items():
            if student_id is None or seat_id not in self.seat_map:
                continue
            for proximity, other_seat_id in self.neighbors.get(seat_id, []):
                other_student_id = assignments.get(other_seat_id)
                if other_student_id is None:
                    continue
                a, b = sorted((student_id, other_student_id))
                pair_key = (a, b, proximity)
                if pair_key in visited_pairs:
                    continue
                visited_pairs.add(pair_key)
                pair_score = self.pair_scores.get(pair_key)
                if pair_score:
                    avg, obs = pair_score
                    contribution = avg * (1 + min(obs, 5) * 0.15)
                    pair_total += contribution
                    pair_terms.append(
                        {
                            "type": "pair",
                            "student_a_id": a,
                            "student_b_id": b,
                            "seat_a_id": seat_id,
                            "seat_b_id": other_seat_id,
                            "proximity": proximity,
                            "contribution": contribution,
                            "avg": avg,
                            "observations": obs,
                        }
                    )

        total = seat_total + pair_total
        seat_terms.sort(key=lambda x: x["contribution"], reverse=True)
        pair_terms.sort(key=lambda x: x["contribution"], reverse=True)
        return {
            "total": total,
            "seat_total": seat_total,
            "pair_total": pair_total,
            "seat_terms": seat_terms,
            "pair_terms": pair_terms,
        }

    def score_arrangement(self, assignments: dict[int, int | None]):
        return self.analyze_arrangement(assignments)["total"]

    def best_of_random_search(self, iterations: int = 2000):
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

        for idx, stu in enumerate(students):
            ttk.Label(inner, text=student_names_by_id[stu.id]).grid(row=idx, column=0, sticky="w", padx=6, pady=2)
            var = tk.StringVar(value="")
            self.student_rating_vars[stu.id] = var
            cb = ttk.Combobox(inner, values=["", "-2", "-1", "0", "+1", "+2"], textvariable=var, width=6, state="readonly")
            cb.grid(row=idx, column=1, sticky="w", padx=6, pady=2)

        button_frame = ttk.Frame(self)
        button_frame.grid(row=3, column=0, columnspan=3, sticky="e", padx=10, pady=10)
        ttk.Button(button_frame, text="Uložit", command=self.on_save).pack(side="right", padx=4)
        ttk.Button(button_frame, text="Zrušit", command=self.on_cancel).pack(side="right", padx=4)

        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

    def on_save(self):
        student_ratings = {}
        for student_id, var in self.student_rating_vars.items():
            value = var.get().strip()
            if not value:
                continue
            student_ratings[student_id] = int(value.replace("+", ""))
        self.result = {
            "overall": int(self.overall_var.get()),
            "student_ratings": student_ratings,
        }
        self.destroy()

    def on_cancel(self):
        self.result = None
        self.destroy()


class SeatingApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Zasedací pořádek – lokální MVP")
        self.geometry("1380x820")

        self.db = Database(DB_PATH)
        self.current_classroom_id = None
        self.current_assignments: dict[int, int | None] = {}
        self.current_mode = "manual"
        self.selected_student_id = None
        self.locked_assignments: dict[int, int] = {}
        self.layout_edit_mode = False

        self.classrooms_by_label = {}
        self.students_cache: list[Student] = []
        self.seats_cache: list[Seat] = []
        self.student_names_by_id = {}
        self.seat_buttons = {}
        self.last_analysis = None

        self.create_widgets()
        self.refresh_classrooms()

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

        self.layout_button_var = tk.StringVar(value="Upravit učebnu")
        ttk.Button(actions, textvariable=self.layout_button_var, command=self.toggle_layout_edit_mode).pack(side="left", padx=(18, 6), pady=8)
        ttk.Button(actions, text="Zapnout všechna místa", command=self.activate_all_seats).pack(side="left", padx=6, pady=8)

        help_text = (
            "Normální režim: vyber žáka vlevo → klikni na místo v plánku.\n"
            "Dvojklik na místo = zamknout/odemknout obsazení. V režimu učebny kliknutím vypínáš/zapínáš místa."
        )
        ttk.Label(actions, text=help_text).pack(side="left", padx=16)

        self.grid_frame = ttk.LabelFrame(center, text="Plánek třídy")
        self.grid_frame.pack(fill="both", expand=True)

        status_box = ttk.LabelFrame(right, text="Aktuální stav")
        status_box.pack(fill="x", pady=(0, 10))
        self.mode_var = tk.StringVar(value="Režim: manual")
        self.score_var = tk.StringVar(value="Skóre návrhu: 0.00")
        self.selected_var = tk.StringVar(value="Vybraný žák: —")
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
        self.explanation_tree.column("item", width=230)
        self.explanation_tree.column("score", width=70, anchor="e")
        self.explanation_tree.pack(fill="both", expand=True, padx=8, pady=(0, 8))

    def refresh_classrooms(self):
        classrooms = self.db.list_classrooms()
        labels = [f"{r['name']} ({r['rows_count']}×{r['cols_count']})" for r in classrooms]
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

        button_frame = ttk.Frame(dialog)
        button_frame.grid(row=3, column=0, columnspan=2, sticky="e", padx=10, pady=10)
        ttk.Button(button_frame, text="Vytvořit", command=create_and_close).pack(side="right", padx=4)
        ttk.Button(button_frame, text="Zrušit", command=dialog.destroy).pack(side="right", padx=4)

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
        self.active_seats_var.set(f"Aktivní místa: {sum(1 for seat in self.seats_cache if seat.is_active)}")

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
        seat = next(seat for seat in self.seats_cache if seat.id == seat_id)
        if not seat.is_active:
            return f"{seat.label}\nNEAKTIVNÍ"
        student_id = self.current_assignments.get(seat_id)
        student_name = self.student_names_by_id.get(student_id, "—") if student_id else "—"
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
            self.selected_var.set("Vybraný žák: —")
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
        current_seat_of_student = next((sid for sid, stu in self.current_assignments.items() if stu == self.selected_student_id), None)
        current_student_on_target = self.current_assignments.get(seat_id)
        self.current_assignments[seat_id] = self.selected_student_id
        if current_seat_of_student is not None and current_seat_of_student != seat_id:
            self.current_assignments[current_seat_of_student] = current_student_on_target
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
        if self.layout_edit_mode:
            self.layout_button_var.set("Ukončit úpravu učebny")
            self.layout_mode_var.set("Režim učebny: zapnutý")
        else:
            self.layout_button_var.set("Upravit učebnu")
            self.layout_mode_var.set("Režim učebny: vypnutý")
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
        self.seats_cache = [Seat(s.id, s.row_index, s.col_index, s.label, True) for s in self.seats_cache]
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
        arrangement, _ = engine.best_of_random_search(iterations=2500)
        self.current_assignments = arrangement
        self.current_mode = "smart"
        self.mode_var.set("Režim: smart")
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
            for sid, locked_student in list(self.locked_assignments.items()):
                if locked_student == student_id:
                    self.locked_assignments.pop(sid, None)
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

    def refresh_explanation(self, analysis=None):
        for item in self.explanation_tree.get_children():
            self.explanation_tree.delete(item)

        analysis = analysis if analysis is not None else self.last_analysis
        if analysis is None:
            self.explanation_summary_var.set("Zatím není co vysvětlovat.")
            return

        seat_total = analysis["seat_total"]
        pair_total = analysis["pair_total"]
        seat_count = len(analysis["seat_terms"])
        pair_count = len(analysis["pair_terms"])
        self.explanation_summary_var.set(
            f"Součet pozic: {seat_total:+.2f} | součet sousedství: {pair_total:+.2f} | "
            f"známé vazby v návrhu: {seat_count + pair_count}"
        )

        combined = []
        for term in analysis["seat_terms"]:
            seat_label = next((s.label for s in self.seats_cache if s.id == term["seat_id"]), str(term["seat_id"]))
            student_name = self.student_names_by_id.get(term["student_id"], str(term["student_id"]))
            combined.append((abs(term["contribution"]), "Pozice", f"{student_name} na {seat_label}", term["contribution"]))
        for term in analysis["pair_terms"]:
            proximity = "vedle sebe" if term["proximity"] == "side" else "před/za"
            a_name = self.student_names_by_id.get(term["student_a_id"], str(term["student_a_id"]))
            b_name = self.student_names_by_id.get(term["student_b_id"], str(term["student_b_id"]))
            combined.append((abs(term["contribution"]), "Dvojice", f"{a_name} × {b_name} ({proximity})", term["contribution"]))

        if not combined:
            self.explanation_summary_var.set(
                "Tento návrh zatím nemá žádné známé plusové ani minusové vazby. Random a smart proto mohou vycházet podobně."
            )
            return

        combined.sort(key=lambda item: item[0], reverse=True)
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
            rating = "—" if row["overall_rating"] is None else row["overall_rating"]
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

    def on_close(self):
        self.db.close()
        self.destroy()


def main():
    app = SeatingApp()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()


if __name__ == "__main__":
    main()
