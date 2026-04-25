from __future__ import annotations

import html as py_html
import json
import mimetypes
import re
import subprocess
import sys
import threading
import time
from collections import OrderedDict
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from ebooklib import epub

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText




APP_TITLE = "LN Release Builder"

DARK = {
    "bg": "#2b2b2b",
    "fg": "#d3d3d3",
    "btn": "#3c3f41",
    "entry": "#3c3f41",
    "logbg": "#1e1e1e",
    "logfg": "#569cd6",
    "accent": "#4a90e2",
}


class HtmlTitleExtractor(HTMLParser):
    """Small stdlib-only title/h1 extractor for generated chapter HTML."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.in_title = False
        self.in_heading = False
        self.title_parts: list[str] = []
        self.heading_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag == "title":
            self.in_title = True
        elif tag == "h1" and not self.heading_parts:
            self.in_heading = True

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "title":
            self.in_title = False
        elif tag == "h1":
            self.in_heading = False

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.title_parts.append(data)
        elif self.in_heading:
            self.heading_parts.append(data)

    @property
    def title(self) -> str:
        title = " ".join(part.strip() for part in self.title_parts if part.strip()).strip()
        if title:
            return title
        return " ".join(part.strip() for part in self.heading_parts if part.strip()).strip()


def compact(value: Any, max_len: int = 120) -> str:
    if value is None:
        s = ""
    elif isinstance(value, (dict, list)):
        s = json.dumps(value, ensure_ascii=False)
    else:
        s = str(value)
    s = s.replace("\n", " ").strip()
    return s if len(s) <= max_len else s[: max_len - 1] + "…"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sanitize_filename(text: str, fallback: str = "book") -> str:
    safe = "".join(ch for ch in text if ch.isalnum() or ch in (" ", "-", "_", ".")).strip()
    safe = re.sub(r"\s+", " ", safe).strip(" .")
    return safe or fallback


def natural_sort_key(path: Path) -> list[Any]:
    parts = re.split(r"(\d+)", path.name.lower())
    return [int(part) if part.isdigit() else part for part in parts]


def extract_html_title(raw_html: str, fallback: str) -> str:
    parser = HtmlTitleExtractor()
    try:
        parser.feed(raw_html)
        title = parser.title.strip()
        return title or fallback
    except Exception:
        return fallback


def media_type_for_cover(path: Path) -> str:
    guessed, _ = mimetypes.guess_type(str(path))
    return guessed or "image/jpeg"


class ReleaseBuilderApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("980x760")
        self.root.minsize(820, 640)

        self.root.configure(bg=DARK["bg"])

        self.style = ttk.Style()
        try:
            self.style.theme_use("clam")
        except tk.TclError:
            pass
        self.style.configure(".", background=DARK["bg"], foreground=DARK["fg"], fieldbackground=DARK["entry"])
        self.style.configure("TButton", background=DARK["btn"], foreground=DARK["fg"], borderwidth=1, padding=(8, 5))
        self.style.map("TButton", background=[("active", "#4b4e50")])
        self.style.configure("Accent.TButton", background=DARK["accent"], foreground="#101217")
        self.style.configure("TEntry", fieldbackground=DARK["entry"], foreground=DARK["fg"], insertcolor=DARK["fg"])
        self.style.configure("TCombobox", fieldbackground=DARK["entry"], foreground=DARK["fg"], background=DARK["btn"])
        self.style.map("TCombobox", fieldbackground=[("readonly", DARK["entry"])], foreground=[("readonly", DARK["fg"])])
        self.style.configure("TCheckbutton", background=DARK["bg"], foreground=DARK["fg"])
        self.style.configure("Section.TLabel", background=DARK["bg"], foreground="#f2f2f2", font=("Segoe UI", 10, "bold"))
        self.style.configure("TProgressbar", troughcolor=DARK["btn"], background=DARK["accent"])

        self.project_root = tk.StringVar(value="C:/New folder/Translate/ln_translate_pipeline_final_test")
        self.output_dir = tk.StringVar(value="C:/New folder/Translate/ln_translate_pipeline_final_test/output")
        self.volume_var = tk.StringVar(value="1")
        self.translation_source = tk.StringVar(value="fixed_if_available")

        self.novel_title_var = tk.StringVar(value="Madan no Ou to Vanadis Volume ")
        self.book_author_var = tk.StringVar(value="Unknown")

        self.copy_css_var = tk.BooleanVar(value=True)
        self.css1_var = tk.StringVar(value="C:/New folder/Translate/0001.css")
        self.css2_var = tk.StringVar(value="C:/New folder/Translate/0002.css")

        self.pack_epub_var = tk.BooleanVar(value=True)
        self.add_calibre_var = tk.BooleanVar(value=True)
        self.cover_path_var = tk.StringVar()

        self._build_ui()
        self.log("Sẵn sàng. Chọn project root, output folder, CSS/cover nếu có, rồi bấm Build Full Release.")

    def _build_ui(self) -> None:
        main = ttk.Frame(self.root, padding=14)
        main.pack(fill="both", expand=True)

        ttk.Label(main, text="1) Nhận bản gốc từ pipeline", style="Section.TLabel").pack(anchor="w", pady=(0, 8))

        row1 = ttk.Frame(main)
        row1.pack(fill="x", pady=(0, 10))
        ttk.Label(row1, text="Project Root:").pack(side="left")
        ttk.Entry(row1, textvariable=self.project_root).pack(side="left", fill="x", expand=True, padx=10)
        ttk.Button(row1, text="Chọn...", command=self.choose_project_root).pack(side="left")

        row2 = ttk.Frame(main)
        row2.pack(fill="x", pady=(0, 10))
        ttk.Label(row2, text="Output Folder:").pack(side="left")
        ttk.Entry(row2, textvariable=self.output_dir).pack(side="left", fill="x", expand=True, padx=10)
        ttk.Button(row2, text="Chọn...", command=self.choose_output_dir).pack(side="left")

        row3 = ttk.Frame(main)
        row3.pack(fill="x", pady=(0, 14))
        ttk.Label(row3, text="Volume:").pack(side="left")
        ttk.Entry(row3, textvariable=self.volume_var, width=8).pack(side="left", padx=(6, 18))
        ttk.Label(row3, text="Translation Source:").pack(side="left")
        cb = ttk.Combobox(
            row3,
            textvariable=self.translation_source,
            state="readonly",
            width=22,
            values=["fixed_if_available", "fixed_only", "draft_only"],
        )
        cb.pack(side="left", padx=(6, 18))
        ttk.Label(row3, text="Book Title:").pack(side="left")
        ttk.Entry(row3, textvariable=self.novel_title_var).pack(side="left", fill="x", expand=True, padx=(6, 0))

        ttk.Label(main, text="2) Tạo HTML đẹp + CSS", style="Section.TLabel").pack(anchor="w", pady=(0, 8))

        row4 = ttk.Frame(main)
        row4.pack(fill="x", pady=(0, 10))
        ttk.Checkbutton(row4, text="Copy CSS files vào HTML folder (0001.css / 0002.css)", variable=self.copy_css_var).pack(side="left")

        row5 = ttk.Frame(main)
        row5.pack(fill="x", pady=(0, 10))
        ttk.Label(row5, text="0001.css:").pack(side="left")
        ttk.Entry(row5, textvariable=self.css1_var).pack(side="left", fill="x", expand=True, padx=8)
        ttk.Button(row5, text="Chọn...", command=lambda: self.choose_css(self.css1_var)).pack(side="left")

        row6 = ttk.Frame(main)
        row6.pack(fill="x", pady=(0, 14))
        ttk.Label(row6, text="0002.css:").pack(side="left")
        ttk.Entry(row6, textvariable=self.css2_var).pack(side="left", fill="x", expand=True, padx=8)
        ttk.Button(row6, text="Chọn...", command=lambda: self.choose_css(self.css2_var)).pack(side="left")

        ttk.Label(main, text="3) Đóng EPUB -> Calibre", style="Section.TLabel").pack(anchor="w", pady=(0, 8))

        row7 = ttk.Frame(main)
        row7.pack(fill="x", pady=(0, 10))
        ttk.Label(row7, text="Author:").pack(side="left")
        ttk.Entry(row7, textvariable=self.book_author_var, width=24).pack(side="left", padx=(6, 18))
        ttk.Checkbutton(row7, text="Pack EPUB", variable=self.pack_epub_var).pack(side="left", padx=(0, 18))
        ttk.Checkbutton(row7, text="Add to Calibre", variable=self.add_calibre_var).pack(side="left")

        row8 = ttk.Frame(main)
        row8.pack(fill="x", pady=(0, 15))
        ttk.Label(row8, text="Cover:").pack(side="left")
        ttk.Entry(row8, textvariable=self.cover_path_var).pack(side="left", fill="x", expand=True, padx=8)
        ttk.Button(row8, text="Chọn...", command=self.choose_cover).pack(side="left")

        row9 = ttk.Frame(main)
        row9.pack(fill="x", pady=(0, 10))
        self.btn_preview = ttk.Button(row9, text="Preview Inputs", command=self.preview_inputs)
        self.btn_preview.pack(side="left", padx=(0, 10))
        self.btn_build = ttk.Button(row9, text="Build Full Release", style="Accent.TButton", command=self.start_build)
        self.btn_build.pack(side="left", padx=(0, 10))
        self.progress = ttk.Progressbar(row9, orient="horizontal", mode="determinate")
        self.progress.pack(side="left", fill="x", expand=True)

        ttk.Label(main, text="Nhật ký:").pack(anchor="w", pady=(6, 0))
        self.log_box = ScrolledText(
            main,
            height=18,
            state="disabled",
            bg=DARK["logbg"],
            fg=DARK["logfg"],
            insertbackground="white",
            borderwidth=0,
        )
        self.log_box.pack(fill="both", expand=True, pady=(5, 0))

    def choose_project_root(self) -> None:
        folder = filedialog.askdirectory(title="Chọn project root của pipeline")
        if folder:
            self.project_root.set(folder)
            self.log(f"Đã chọn project root: {folder}")

    def choose_output_dir(self) -> None:
        folder = filedialog.askdirectory(title="Chọn thư mục output")
        if folder:
            self.output_dir.set(folder)
            self.log(f"Đã chọn output: {folder}")

    def choose_css(self, var: tk.StringVar) -> None:
        filepath = filedialog.askopenfilename(
            title="Chọn CSS file",
            filetypes=[("CSS Files", "*.css"), ("All Files", "*.*")]
        )
        if filepath:
            var.set(filepath)

    def choose_cover(self) -> None:
        filepath = filedialog.askopenfilename(
            title="Chọn ảnh bìa",
            filetypes=[("Images", "*.jpg *.jpeg *.png"), ("All Files", "*.*")],
        )
        if filepath:
            self.cover_path_var.set(filepath)

    def log(self, msg: str) -> None:
        def append() -> None:
            self.log_box.configure(state="normal")
            self.log_box.insert("end", msg + "\n")
            self.log_box.see("end")
            self.log_box.configure(state="disabled")

        if threading.current_thread() is threading.main_thread():
            append()
        else:
            self.root.after(0, append)

    def set_progress(self, value: int | None = None, maximum: int | None = None) -> None:
        def apply() -> None:
            if maximum is not None:
                self.progress["maximum"] = maximum
            if value is not None:
                self.progress["value"] = value

        if threading.current_thread() is threading.main_thread():
            apply()
        else:
            self.root.after(0, apply)

    def volume_num(self) -> int:
        try:
            return int(self.volume_var.get().strip())
        except ValueError:
            raise ValueError("Volume phải là số nguyên.")

    def get_project_root(self) -> Path:
        p = Path(self.project_root.get().strip())
        if not p.exists():
            raise FileNotFoundError(f"Project root không tồn tại: {p}")
        return p

    def get_output_dir(self) -> Path:
        text = self.output_dir.get().strip()
        if not text:
            raise FileNotFoundError("Chưa chọn output folder.")
        p = Path(text)
        p.mkdir(parents=True, exist_ok=True)
        return p

    def source_paths(self) -> dict[str, Path]:
        root = self.get_project_root()
        v = self.volume_num()
        return {
            "segments": root / "data" / "segments" / f"volume_{v:02d}.segments.json",
            "draft": root / "data" / "working" / "translations" / "draft" / f"volume_{v:02d}.translated.jsonl",
            "fixed": root / "data" / "working" / "translations" / "fixed" / f"volume_{v:02d}.fixed.jsonl",
        }

    def choose_translation_map(self, paths: dict[str, Path]) -> tuple[str, dict[str, str]]:
        mode = self.translation_source.get().strip()
        draft_rows = read_jsonl(paths["draft"])
        fixed_rows = read_jsonl(paths["fixed"])

        draft_map: dict[str, str] = {}
        fixed_map: dict[str, str] = {}

        for row in draft_rows:
            if row.get("status") != "success":
                continue
            item_id = row.get("item_id")
            result = row.get("result", {})
            if item_id and isinstance(result, dict):
                text = result.get("translation", "")
                if text:
                    draft_map[str(item_id)] = text

        for row in fixed_rows:
            if row.get("status") != "success":
                continue
            item_id = row.get("item_id")
            result = row.get("result", {})
            if item_id and isinstance(result, dict):
                text = result.get("fixed_translation") or result.get("translation") or ""
                if text:
                    fixed_map[str(item_id)] = text

        if mode == "draft_only":
            return ("draft", draft_map)
        if mode == "fixed_only":
            return ("fixed", fixed_map)

        if fixed_map:
            merged = dict(draft_map)
            merged.update(fixed_map)
            return ("fixed_if_available", merged)
        return ("draft", draft_map)

    def build_volume_json(self) -> tuple[list[dict], dict[str, Any]]:
        paths = self.source_paths()
        if not paths["segments"].exists():
            raise FileNotFoundError(f"Không tìm thấy segments file: {paths['segments']}")

        segments_data = read_json(paths["segments"])
        if isinstance(segments_data, dict) and "segments" in segments_data:
            segments = segments_data["segments"]
        elif isinstance(segments_data, list):
            segments = segments_data
        else:
            raise ValueError("Segments file không đúng schema.")

        source_mode, translations = self.choose_translation_map(paths)

        chapters: "OrderedDict[int, dict]" = OrderedDict()
        missing_segments: list[str] = []

        for seg in segments:
            chapter = int(seg.get("chapter", 0))
            name = str(seg.get("name", f"Chapter {chapter}"))
            segment_id = str(seg.get("segment", f"c{chapter:03d}"))
            translated = translations.get(segment_id, "").strip()

            if chapter not in chapters:
                chapters[chapter] = {
                    "chapter": chapter,
                    "name": name,
                    "_parts": []
                }

            if translated:
                chapters[chapter]["_parts"].append(translated)
            else:
                missing_segments.append(segment_id)

        out: list[dict] = []
        for chapter, data in chapters.items():
            content = "\n\n".join(part for part in data["_parts"] if part).strip()
            out.append({
                "chapter": chapter,
                "name": data["name"],
                "content": content
            })

        diagnostics = {
            "source_mode": source_mode,
            "total_chapters": len(out),
            "total_segments": len(segments),
            "translated_segments": len(translations),
            "missing_segments": missing_segments[:200],
            "missing_count": len(missing_segments),
        }
        return out, diagnostics

    def create_chapter_html(self, title: str, content: str) -> str:
        paragraphs = [p.strip() for p in content.split("\n") if p.strip()]
        p_tags = "".join([f'\n<p class="calibre3">{py_html.escape(p)}</p>' for p in paragraphs])
        safe_title = py_html.escape(title)

        return f'''<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
<meta charset="UTF-8"/>
<title>{safe_title}</title>
<link href="0001.css" rel="stylesheet" type="text/css"/>
<link href="0002.css" rel="stylesheet" type="text/css"/>
</head>
<body class="calibre">
<h1 class="header">{safe_title}</h1><br/><br/>{p_tags}
</body>
</html>'''

    def create_toc_html(self, dst_path: Path, novel_title: str, toc_items: list[tuple[str, str]]) -> None:
        body_lines = [f'\n<p class="calibre3"><a href="{fname}">{py_html.escape(title)}</a></p>' for fname, title in toc_items]
        full_html = f'''<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
<meta charset="UTF-8"/>
<title>{py_html.escape(novel_title)}</title>
<link href="0001.css" rel="stylesheet" type="text/css"/>
<link href="0002.css" rel="stylesheet" type="text/css"/>
</head>
<body class="calibre">
<h1 class="header">{py_html.escape(novel_title)}</h1>{"".join(body_lines)}
</body>
</html>'''
        (dst_path / "0.html").write_text(full_html, encoding="utf-8")

    def maybe_copy_css(self, out_dir: Path) -> list[Path]:
        copied: list[Path] = []
        if not self.copy_css_var.get():
            return copied

        css_specs = [("0001.css", self.css1_var.get().strip()), ("0002.css", self.css2_var.get().strip())]
        for target_name, src_text in css_specs:
            if not src_text:
                continue
            src = Path(src_text)
            if not src.exists():
                self.log(f"Bỏ qua CSS không tồn tại: {src}")
                continue
            dst = out_dir / target_name
            dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
            copied.append(dst)
            self.log(f"Đã copy {target_name}")
        return copied

    def css_files_for_epub(self, html_dir: Path) -> list[tuple[str, Path]]:
        css_files: list[tuple[str, Path]] = []
        seen_names: set[str] = set()

        for target_name, src_text in [("0001.css", self.css1_var.get().strip()), ("0002.css", self.css2_var.get().strip())]:
            html_css = html_dir / target_name
            src = html_css if html_css.exists() else Path(src_text) if src_text else None
            if src and src.exists() and target_name not in seen_names:
                css_files.append((target_name, src))
                seen_names.add(target_name)

        for src in sorted(html_dir.glob("*.css"), key=natural_sort_key):
            if src.name not in seen_names:
                css_files.append((src.name, src))
                seen_names.add(src.name)

        return css_files

    def html_files_for_epub(self, html_dir: Path) -> list[Path]:
        files = [p for p in html_dir.iterdir() if p.is_file() and p.suffix.lower() in {".html", ".htm", ".xhtml"}]
        return sorted(files, key=natural_sort_key)

    def pack_epub_from_html(self, html_dir: Path, output_dir: Path, title: str, author: str, volume: int) -> tuple[Path, dict[str, Any]]:
        if epub is None:
            raise ImportError("Thiếu dependency 'ebooklib'. Cài bằng: pip install ebooklib")

        html_files = self.html_files_for_epub(html_dir)
        if not html_files:
            raise FileNotFoundError(f"Không tìm thấy HTML trong: {html_dir}")

        css_files = self.css_files_for_epub(html_dir)
        if not css_files:
            self.log("Cảnh báo: Không có CSS nào được nhúng vào EPUB.")

        safe_title = title.strip() or f"Volume {volume:02d}"
        safe_author = author.strip() or "Unknown"
        epub_filename = f"{sanitize_filename(safe_title)} - v{volume:02d}.epub"
        epub_path = output_dir / epub_filename

        book = epub.EpubBook()
        book.set_identifier(f"ln_release_v{volume:02d}_{int(time.time())}")
        book.set_title(safe_title)
        book.set_language("vi")
        book.add_author(safe_author)

        for epub_name, css_path in css_files:
            css_item = epub.EpubItem(
                uid=f"css_{sanitize_filename(epub_name, 'style').replace('.', '_')}",
                file_name=epub_name,
                media_type="text/css",
                content=css_path.read_text(encoding="utf-8"),
            )
            book.add_item(css_item)
            self.log(f"Đã nhúng CSS vào EPUB: {epub_name}")

        html_items = []
        toc_items = []
        for index, html_path in enumerate(html_files, start=1):
            raw_html = html_path.read_text(encoding="utf-8")
            fallback_title = safe_title if html_path.name == "0.html" else f"Chapter {index}"
            chapter_title = extract_html_title(raw_html, fallback_title)
            item = epub.EpubItem(
                uid=f"html_{index:04d}",
                file_name=html_path.name,
                media_type="application/xhtml+xml",
                content=raw_html,
            )
            item.title = chapter_title
            book.add_item(item)
            html_items.append(item)
            if html_path.name != "0.html":
                toc_items.append(item)

        cover_text = self.cover_path_var.get().strip()
        cover_added = False
        if cover_text:
            cover_path = Path(cover_text)
            if cover_path.exists():
                cover_ext = cover_path.suffix.lower() or ".jpg"
                cover_name = f"cover{cover_ext}"
                book.set_cover(cover_name, cover_path.read_bytes())
                cover_added = True
                self.log(f"Đã thêm cover: {cover_path.name} ({media_type_for_cover(cover_path)})")
            else:
                self.log(f"Bỏ qua cover không tồn tại: {cover_path}")

        book.toc = [epub.Link(item.file_name, getattr(item, "title", item.file_name), item.id) for item in toc_items]
        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())
        book.spine = ["nav"] + html_items

        epub.write_epub(str(epub_path), book, {})
        self.log(f"Đã tạo EPUB: {epub_path}")

        return epub_path, {
            "epub_output": str(epub_path),
            "html_count": len(html_items),
            "toc_count": len(toc_items),
            "css_count": len(css_files),
            "cover_added": cover_added,
        }

    def add_to_calibre(self, epub_path: Path) -> dict[str, Any]:
        self.log("Đang gọi Calibre: calibredb add ...")
        startupinfo = None
        if sys.platform == "win32":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        try:
            result = subprocess.run(
                ["calibredb", "add", str(epub_path)],
                capture_output=True,
                text=True,
                startupinfo=startupinfo,
                check=False,
            )
        except FileNotFoundError:
            self.log("Không tìm thấy 'calibredb'. Hãy thêm Calibre vào PATH hoặc tắt Add to Calibre.")
            return {"attempted": True, "success": False, "error": "calibredb not found"}

        if result.returncode == 0:
            self.log("THÀNH CÔNG: Đã thêm EPUB vào thư viện Calibre.")
            return {"attempted": True, "success": True, "stdout": result.stdout.strip()}

        error_text = (result.stderr or result.stdout or "Unknown Calibre error").strip()
        self.log(f"Calibre báo lỗi:\n{error_text}")
        return {"attempted": True, "success": False, "error": error_text}

    def preview_inputs(self) -> None:
        try:
            volume_json, diagnostics = self.build_volume_json()
            self.log("--- PREVIEW ---")
            self.log(f"Volume: {self.volume_num():02d}")
            self.log(f"Mode: {diagnostics['source_mode']}")
            self.log(f"Chapters: {diagnostics['total_chapters']}")
            self.log(f"Segments total: {diagnostics['total_segments']}")
            self.log(f"Segments translated map: {diagnostics['translated_segments']}")
            self.log(f"Missing segments: {diagnostics['missing_count']}")
            if diagnostics["missing_segments"]:
                self.log("Missing sample: " + ", ".join(diagnostics["missing_segments"][:15]))
            if volume_json:
                self.log("First chapter preview: " + compact(volume_json[0], 240))
        except Exception as e:
            messagebox.showerror(APP_TITLE, str(e))

    def start_build(self) -> None:
        if not self.project_root.get().strip() or not self.output_dir.get().strip():
            messagebox.showwarning(APP_TITLE, "Vui lòng chọn project root và output folder.")
            return
        self.btn_build.config(state="disabled")
        self.set_progress(value=0)
        self.log("\n--- BẮT ĐẦU FULL RELEASE ---")
        threading.Thread(target=self._build_release, daemon=True).start()

    def _build_release(self) -> None:
        try:
            out_dir = self.get_output_dir()
            volume_json, diagnostics = self.build_volume_json()
            volume = self.volume_num()
            book_title = self.novel_title_var.get().strip() or f"Volume {volume:02d}"

            extra_steps = 4 if self.pack_epub_var.get() else 2
            self.set_progress(maximum=max(1, len(volume_json) + extra_steps), value=0)

            json_out = out_dir / f"volume_{volume:02d}.json"
            write_json(json_out, volume_json)
            self.log(f"Đã tạo JSON: {json_out}")
            self.set_progress(value=1)

            html_dir = out_dir / f"volume_{volume:02d}_html"
            html_dir.mkdir(parents=True, exist_ok=True)
            toc_items: list[tuple[str, str]] = []

            for idx, chapter in enumerate(volume_json, start=1):
                chap_no = int(chapter.get("chapter", idx))
                chap_name = str(chapter.get("name", f"Chapter {chap_no}"))
                chap_content = str(chapter.get("content", ""))

                filename = f"chapter_{chap_no:04d}.html"
                html = self.create_chapter_html(chap_name, chap_content)
                (html_dir / filename).write_text(html, encoding="utf-8")
                toc_items.append((filename, chap_name))

                if idx % 5 == 0 or idx == len(volume_json):
                    self.set_progress(value=idx + 1)
                    self.log(f"Đã tạo HTML: {filename} - {chap_name}")

            self.create_toc_html(html_dir, book_title, toc_items)
            self.log("Đã tạo 0.html")
            self.maybe_copy_css(html_dir)

            epub_info: dict[str, Any] | None = None
            calibre_info: dict[str, Any] | None = None

            if self.pack_epub_var.get():
                self.log("Bắt đầu đóng gói EPUB...")
                epub_path, epub_info = self.pack_epub_from_html(
                    html_dir=html_dir,
                    output_dir=out_dir,
                    title=book_title,
                    author=self.book_author_var.get(),
                    volume=volume,
                )
                self.set_progress(value=len(volume_json) + 3)

                if self.add_calibre_var.get():
                    calibre_info = self.add_to_calibre(epub_path)
                else:
                    calibre_info = {"attempted": False, "success": None}

            manifest = {
                "volume": volume,
                "json_output": str(json_out),
                "html_dir": str(html_dir),
                "epub": epub_info,
                "calibre": calibre_info,
                "diagnostics": diagnostics,
            }
            manifest_out = out_dir / f"volume_{volume:02d}.release_manifest.json"
            write_json(manifest_out, manifest)
            self.log(f"Đã tạo manifest: {manifest_out}")

            self.set_progress(value=len(volume_json) + extra_steps)
            self.log("--- HOÀN TẤT FULL RELEASE ---")

            msg_lines = [
                f"Đã build xong volume {volume:02d}.",
                "",
                f"- JSON: {json_out.name}",
                f"- HTML folder: {html_dir.name}",
                f"- Missing segments: {diagnostics['missing_count']}",
            ]
            if epub_info:
                msg_lines.append(f"- EPUB: {Path(epub_info['epub_output']).name}")
            if calibre_info and calibre_info.get("attempted"):
                msg_lines.append(f"- Calibre: {'OK' if calibre_info.get('success') else 'FAILED'}")

            self.root.after(0, lambda: messagebox.showinfo(APP_TITLE, "\n".join(msg_lines)))
        except Exception as e:
            self.log(f"❌ LỖI: {e}")
            self.root.after(0, lambda: messagebox.showerror(APP_TITLE, f"Lỗi:\n{e}"))
        finally:
            self.root.after(0, lambda: self.btn_build.config(state="normal"))


def main() -> None:
    root = tk.Tk()
    ReleaseBuilderApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
