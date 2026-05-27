from __future__ import annotations

import json
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk


EXCLUDED_PROJECT_NAMES = {"source", "segments"}


def resolve_repo_root() -> Path:
    candidates = [Path.cwd(), Path(__file__).resolve().parent]
    for candidate in candidates:
        if candidate.joinpath("data").is_dir():
            return candidate
    return candidates[0]


def discover_projects(repo_root: Path) -> list[str]:
    data_dir = repo_root.joinpath("data")
    if not data_dir.is_dir():
        return []
    return sorted(
        child.name
        for child in data_dir.iterdir()
        if child.is_dir() and child.name not in EXCLUDED_PROJECT_NAMES
    )


def parse_positive_int(value: str, field_name: str) -> int:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} is required.")
    try:
        parsed = int(normalized)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be a number.") from exc
    if parsed < 1:
        raise ValueError(f"{field_name} must be at least 1.")
    return parsed


def format_segment_id(chapter: int, segment: int) -> str:
    return f"c{chapter:03d}_s{segment:03d}"


def create_source_record(chapter_text: str, name: str, content: str) -> dict[str, object]:
    chapter = parse_positive_int(chapter_text, "Source chapter")
    return {
        "chapter": chapter,
        "name": name.strip(),
        "content": content.strip(),
    }


def create_segment_record(chapter_text: str, segment_text: str, name: str, content: str) -> dict[str, str]:
    chapter = parse_positive_int(chapter_text, "Segment chapter")
    segment = parse_positive_int(segment_text, "Segment number")
    return {
        "name": name.strip(),
        "chapter": str(chapter),
        "content": content.strip(),
        "segment": format_segment_id(chapter, segment),
    }


def volume_stem(volume: int) -> str:
    return f"volume_{volume:02d}"


def build_project_paths(repo_root: Path, project_name: str, volume: int) -> tuple[Path, Path]:
    project_root = repo_root.joinpath("data", project_name)
    base_name = volume_stem(volume)
    source_path = project_root.joinpath("source", f"{base_name}.json")
    segment_path = project_root.joinpath("segments", f"{base_name}.segments.json")
    return source_path, segment_path


def write_pretty_json(path: Path, payload: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=4) + "\n", encoding="utf-8")


class RecordEditorPanel(tk.LabelFrame):
    def __init__(
        self,
        parent: tk.Misc,
        *,
        title: str,
        colors: dict[str, str],
        include_segment: bool,
    ) -> None:
        super().__init__(
            parent,
            text=title,
            padx=12,
            pady=12,
            font=("Segoe UI", 11, "bold"),
            bg=colors["panel"],
            fg=colors["text"],
        )
        self.colors = colors
        self.include_segment = include_segment
        self.records: dict[str, dict[str, object]] = {}
        self.history: list[str] = []
        self._build_ui()
        self._apply_theme(self)
        self._sync_segment_state()

    def _build_ui(self) -> None:
        self.columnconfigure(1, weight=1)
        self.rowconfigure(3, weight=1)

        self.chapter_var = tk.StringVar(value="1")
        self.chapter_var.trace_add("write", self._on_chapter_changed)
        self.segment_var = tk.StringVar(value="1")
        self.name_var = tk.StringVar(value="")
        self._last_chapter_seen = self.chapter_var.get().strip()

        self._make_label("Chapter").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        chapter_row = tk.Frame(self, bg=self.colors["panel"])
        chapter_row.grid(row=0, column=1, padx=5, pady=5, sticky="w")
        self.chapter_entry = tk.Entry(chapter_row, textvariable=self.chapter_var, width=12)
        self.chapter_entry.pack(side=tk.LEFT)
        self.chapter_inc_button = self._make_button(chapter_row, "+", self.increment_chapter, width=3, bg=self.colors["blue"])
        self.chapter_inc_button.pack(side=tk.LEFT, padx=(6, 0))

        self.segment_label = self._make_label("Segment")
        self.segment_label.grid(row=1, column=0, padx=5, pady=5, sticky="e")
        segment_row = tk.Frame(self, bg=self.colors["panel"])
        segment_row.grid(row=1, column=1, padx=5, pady=5, sticky="w")
        self.segment_entry = tk.Entry(segment_row, textvariable=self.segment_var, width=12)
        self.segment_entry.pack(side=tk.LEFT)
        self.segment_inc_button = self._make_button(segment_row, "+", self.increment_segment, width=3, bg=self.colors["purple"])
        self.segment_inc_button.pack(side=tk.LEFT, padx=(6, 0))

        self._make_label("Name").grid(row=2, column=0, padx=5, pady=5, sticky="e")
        self.name_entry = tk.Entry(self, textvariable=self.name_var)
        self.name_entry.grid(row=2, column=1, padx=5, pady=5, sticky="we")

        self._make_label("Content").grid(row=3, column=0, padx=5, pady=5, sticky="ne")
        self.content_text = tk.Text(self, wrap=tk.WORD, width=44)
        self.content_text.grid(row=3, column=1, padx=5, pady=5, sticky="nsew")

        button_row = tk.Frame(self, bg=self.colors["panel"])
        button_row.grid(row=4, column=0, columnspan=2, pady=(10, 0))
        self.back_button = self._make_button(button_row, "Back", self.go_back, width=10, bg=self.colors["gray_btn"])
        self.back_button.pack(side=tk.LEFT, padx=4)
        self.next_button = self._make_button(button_row, "Next", self.go_next, width=10, bg=self.colors["accent"])
        self.next_button.pack(side=tk.LEFT, padx=4)
        self.count_button = self._make_button(button_row, "Count", self.count_chars, width=10, bg=self.colors["purple"])
        self.count_button.pack(side=tk.LEFT, padx=4)
        self.clear_button = self._make_button(button_row, "Clear Panel", self.clear_panel, width=12, bg=self.colors["red"])
        self.clear_button.pack(side=tk.LEFT, padx=4)

    def _make_label(self, text: str) -> tk.Label:
        return tk.Label(self, text=text, bg=self.colors["panel"], fg=self.colors["text"])

    def _make_button(self, parent: tk.Misc, text: str, command, *, width: int, bg: str) -> tk.Button:
        return tk.Button(
            parent,
            text=text,
            command=command,
            width=width,
            bg=bg,
            fg="white",
            activebackground=self.colors["border"],
            activeforeground="white",
            relief=tk.FLAT,
            padx=6,
            pady=4,
            cursor="hand2",
        )

    def _apply_theme(self, widget: tk.Misc) -> None:
        for child in widget.winfo_children():
            class_name = child.winfo_class()
            if class_name in {"Frame", "Labelframe"}:
                child.configure(bg=self.colors["panel"])
            elif class_name == "LabelFrame":
                child.configure(bg=self.colors["panel"], fg=self.colors["text"])
            elif class_name == "Label":
                child.configure(bg=self.colors["panel"], fg=self.colors["text"])
            elif class_name == "Entry":
                child.configure(
                    bg=self.colors["entry"],
                    fg=self.colors["text"],
                    insertbackground=self.colors["text"],
                    relief=tk.FLAT,
                )
            elif class_name == "Text":
                child.configure(
                    bg=self.colors["entry"],
                    fg=self.colors["text"],
                    insertbackground=self.colors["text"],
                    relief=tk.FLAT,
                    padx=8,
                    pady=8,
                )
            self._apply_theme(child)

    def _sync_segment_state(self) -> None:
        state = tk.NORMAL if self.include_segment else tk.DISABLED
        self.segment_entry.configure(state=state)
        self.segment_inc_button.configure(state=state)
        self.segment_label.configure(fg=self.colors["text"] if self.include_segment else self.colors["muted"])
        if not self.include_segment:
            self.segment_var.set("1")

    def _current_key(self) -> str:
        chapter = self.chapter_var.get().strip() or "1"
        if not self.include_segment:
            return chapter
        segment = self.segment_var.get().strip() or "1"
        return format_segment_id(parse_positive_int(chapter, "Segment chapter"), parse_positive_int(segment, "Segment number"))

    def _current_record_is_blank(self) -> bool:
        return not self.name_var.get().strip() and not self.content_text.get("1.0", tk.END).strip()

    def _build_record(self) -> dict[str, object]:
        chapter = self.chapter_var.get().strip()
        name = self.name_var.get()
        content = self.content_text.get("1.0", tk.END)
        if self.include_segment:
            return create_segment_record(chapter, self.segment_var.get().strip(), name, content)
        return create_source_record(chapter, name, content)

    def save_current_record(self, *, show_error: bool = True) -> bool:
        if self._current_record_is_blank():
            return True
        try:
            key = self._current_key()
            record = self._build_record()
        except ValueError as exc:
            if show_error:
                messagebox.showwarning("Invalid Input", str(exc))
            return False
        self.records[key] = record
        return True

    def load_record(self, key: str) -> bool:
        record = self.records.get(key)
        if record is None:
            return False
        self.chapter_var.set(str(record.get("chapter", "1")))
        if self.include_segment:
            segment_id = str(record.get("segment", "c001_s001"))
            try:
                self.segment_var.set(str(int(segment_id.split("_s", 1)[1])))
            except (IndexError, ValueError):
                self.segment_var.set("1")
        else:
            self.segment_var.set("1")
        self.name_var.set(str(record.get("name", "")))
        self.content_text.delete("1.0", tk.END)
        self.content_text.insert(tk.END, str(record.get("content", "")))
        return True

    def clear_inputs(self, *, preserve_position: bool = False) -> None:
        if not preserve_position:
            self.chapter_var.set("1")
            self.segment_var.set("1")
        elif self.include_segment:
            self.segment_var.set(self.segment_var.get().strip() or "1")
        self.name_var.set("")
        self.content_text.delete("1.0", tk.END)

    def clear_panel(self) -> None:
        if not messagebox.askyesno("Confirm Clear", "Clear all records in this panel?"):
            return
        self.records.clear()
        self.history.clear()
        self.clear_inputs()
        self.content_text.focus_set()

    def go_next(self) -> None:
        current_key = None
        if not self._current_record_is_blank():
            if not self.save_current_record():
                return
            current_key = self._current_key()
        if current_key:
            self.history.append(current_key)
        if self.include_segment:
            self.increment_segment()
        else:
            self.increment_chapter(reset_segment=False)
        self.name_var.set("")
        self.content_text.delete("1.0", tk.END)
        self.content_text.focus_set()

    def go_back(self) -> None:
        if not self.save_current_record():
            return
        if not self.history:
            messagebox.showinfo("Back", "No previous record in this panel.")
            return
        previous_key = self.history.pop()
        self.load_record(previous_key)
        self.content_text.focus_set()

    def increment_chapter(self, *, reset_segment: bool = True) -> None:
        try:
            chapter = parse_positive_int(self.chapter_var.get().strip(), "Chapter")
        except ValueError as exc:
            messagebox.showwarning("Invalid Input", str(exc))
            return
        self.chapter_var.set(str(chapter + 1))
        if self.include_segment and reset_segment:
            self.segment_var.set("1")

    def increment_segment(self) -> None:
        try:
            segment = parse_positive_int(self.segment_var.get().strip(), "Segment number")
        except ValueError as exc:
            messagebox.showwarning("Invalid Input", str(exc))
            return
        self.segment_var.set(str(segment + 1))

    def count_chars(self) -> None:
        text = self.content_text.get("1.0", tk.END).rstrip("\n")
        messagebox.showinfo("Character Count", f"Characters: {len(text)}")

    def ordered_records(self) -> list[dict[str, object]]:
        def sort_key(item: dict[str, object]) -> tuple[int, int]:
            chapter_value = int(str(item.get("chapter", "1")))
            if not self.include_segment:
                return chapter_value, 0
            segment_id = str(item.get("segment", "c001_s001"))
            try:
                segment_value = int(segment_id.split("_s", 1)[1])
            except (IndexError, ValueError):
                segment_value = 0
            return chapter_value, segment_value

        return sorted(self.records.values(), key=sort_key)

    def _on_chapter_changed(self, *_args) -> None:
        current = self.chapter_var.get().strip()
        if self.include_segment and current and current != self._last_chapter_seen:
            self.segment_var.set("1")
        self._last_chapter_seen = current


class InputSourceSegmentApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.repo_root = resolve_repo_root()
        self.root.title("Input Source & Segment")
        self.root.geometry("1360x760")
        self.root.minsize(1180, 620)

        self.colors = {
            "bg": "#111827",
            "panel": "#1f2937",
            "text": "#e5e7eb",
            "muted": "#9ca3af",
            "entry": "#374151",
            "border": "#4b5563",
            "accent": "#22c55e",
            "blue": "#3b82f6",
            "orange": "#f97316",
            "red": "#ef4444",
            "purple": "#a855f7",
            "gray_btn": "#6b7280",
        }
        self.root.configure(bg=self.colors["bg"])
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)

        self.project_var = tk.StringVar(value="")
        self.volume_var = tk.StringVar(value="1")
        self.status_var = tk.StringVar(value=f"Repo root: {self.repo_root}")

        self._build_top_bar()
        self._build_panels()
        self.refresh_projects()

    def _build_top_bar(self) -> None:
        top = tk.Frame(self.root, bg=self.colors["bg"])
        top.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 0))
        top.columnconfigure(3, weight=1)

        tk.Label(top, text="Project", bg=self.colors["bg"], fg=self.colors["text"]).grid(row=0, column=0, padx=(0, 6), pady=6, sticky="w")
        self.project_combo = ttk.Combobox(top, textvariable=self.project_var, state="readonly", width=22)
        self.project_combo.grid(row=0, column=1, padx=(0, 8), pady=6, sticky="w")

        self.refresh_button = tk.Button(
            top,
            text="Refresh Projects",
            command=self.refresh_projects,
            bg=self.colors["orange"],
            fg="white",
            activebackground=self.colors["border"],
            activeforeground="white",
            relief=tk.FLAT,
            padx=10,
            pady=4,
            cursor="hand2",
        )
        self.refresh_button.grid(row=0, column=2, padx=(0, 16), pady=6, sticky="w")

        tk.Label(top, text="Volume", bg=self.colors["bg"], fg=self.colors["text"]).grid(row=0, column=3, padx=(0, 6), pady=6, sticky="e")
        self.volume_entry = tk.Entry(top, textvariable=self.volume_var, width=8, bg=self.colors["entry"], fg=self.colors["text"], insertbackground=self.colors["text"], relief=tk.FLAT)
        self.volume_entry.grid(row=0, column=4, padx=(0, 16), pady=6, sticky="w")

        self.save_button = tk.Button(
            top,
            text="Save To Project",
            command=self.save_to_project,
            bg=self.colors["accent"],
            fg="white",
            activebackground=self.colors["border"],
            activeforeground="white",
            relief=tk.FLAT,
            padx=12,
            pady=6,
            cursor="hand2",
        )
        self.save_button.grid(row=0, column=5, pady=6, sticky="e")

        status_label = tk.Label(top, textvariable=self.status_var, bg=self.colors["bg"], fg=self.colors["muted"], anchor="w")
        status_label.grid(row=1, column=0, columnspan=6, sticky="ew", pady=(4, 0))

    def _build_panels(self) -> None:
        panel_row = tk.Frame(self.root, bg=self.colors["bg"])
        panel_row.grid(row=1, column=0, sticky="nsew", padx=12, pady=12)
        panel_row.columnconfigure(0, weight=1, uniform="panel")
        panel_row.columnconfigure(1, weight=1, uniform="panel")
        panel_row.rowconfigure(0, weight=1)

        self.source_panel = RecordEditorPanel(
            panel_row,
            title="Input Source",
            colors=self.colors,
            include_segment=False,
        )
        self.source_panel.grid(row=0, column=0, padx=(0, 8), sticky="nsew")

        self.segment_panel = RecordEditorPanel(
            panel_row,
            title="Input Segment",
            colors=self.colors,
            include_segment=True,
        )
        self.segment_panel.grid(row=0, column=1, padx=(8, 0), sticky="nsew")

    def refresh_projects(self) -> None:
        projects = discover_projects(self.repo_root)
        current = self.project_var.get().strip()
        self.project_combo["values"] = projects
        if current in projects:
            self.project_var.set(current)
        elif projects:
            self.project_var.set(projects[0])
        else:
            self.project_var.set("")
        self.status_var.set(f"Repo root: {self.repo_root}")

    def get_selected_project(self) -> str:
        project_name = self.project_var.get().strip()
        if not project_name:
            raise ValueError("Please choose a project before saving.")
        project_root = self.repo_root.joinpath("data", project_name)
        if not project_root.is_dir():
            raise ValueError(f"Project does not exist: {project_name}")
        return project_name

    def get_volume_number(self) -> int:
        return parse_positive_int(self.volume_var.get().strip(), "Volume")

    def save_to_project(self) -> None:
        if not self.source_panel.save_current_record():
            return
        if not self.segment_panel.save_current_record():
            return

        if not self.source_panel.records:
            messagebox.showwarning("Missing Data", "Please enter at least one source record before saving.")
            return
        if not self.segment_panel.records:
            messagebox.showwarning("Missing Data", "Please enter at least one segment record before saving.")
            return

        try:
            project_name = self.get_selected_project()
            volume = self.get_volume_number()
        except ValueError as exc:
            messagebox.showwarning("Invalid Input", str(exc))
            return

        source_path, segment_path = build_project_paths(self.repo_root, project_name, volume)
        existing_paths = [path for path in (source_path, segment_path) if path.exists()]
        if existing_paths:
            existing_text = "\n".join(str(path) for path in existing_paths)
            if not messagebox.askyesno(
                "Overwrite Files",
                f"These files already exist:\n\n{existing_text}\n\nOverwrite them?",
            ):
                return

        try:
            write_pretty_json(source_path, self.source_panel.ordered_records())
            write_pretty_json(segment_path, self.segment_panel.ordered_records())
        except OSError as exc:
            messagebox.showerror("Save Failed", f"Could not write project files:\n{exc}")
            return

        self.status_var.set(
            f"Saved {volume_stem(volume)} to project '{project_name}' at {source_path.parent} and {segment_path.parent}."
        )
        messagebox.showinfo(
            "Saved",
            f"Saved files:\n{source_path.name}\n{segment_path.name}",
        )


def main() -> None:
    root = tk.Tk()
    app = InputSourceSegmentApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
