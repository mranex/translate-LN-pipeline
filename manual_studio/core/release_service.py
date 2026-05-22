from __future__ import annotations

import datetime as dt
import html as py_html
import json
import mimetypes
import re
import subprocess
import sys
import time
from collections import OrderedDict
from dataclasses import asdict, dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from .jsonio import read_json, read_jsonl, write_json
from .workspace import Workspace


@dataclass(frozen=True)
class ReleaseOptions:
    volume: int
    output_dir: Path
    translation_source: str = "fixed_if_available"
    novel_title: str = ""
    book_author: str = "Unknown"
    copy_css: bool = False
    css_files: list[Path] = field(default_factory=list)
    pack_epub: bool = False
    add_to_calibre: bool = False
    cover_path: Path | None = None


@dataclass(frozen=True)
class ReleaseDiagnostics:
    source_mode: str
    total_chapters: int
    total_segments: int
    translated_segments: int
    missing_segments: list[str]
    missing_count: int


@dataclass(frozen=True)
class ReleaseBuildResult:
    volume: int
    output_dir: Path
    volume_json_path: Path | None
    html_dir: Path | None
    toc_path: Path | None
    epub_path: Path | None
    manifest_path: Path | None
    diagnostics: ReleaseDiagnostics
    messages: list[str]


class _HtmlTitleExtractor(HTMLParser):
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


def _sanitize_filename(text: str, fallback: str = "book") -> str:
    safe = "".join(ch for ch in text if ch.isalnum() or ch in (" ", "-", "_", ".")).strip()
    safe = re.sub(r"\s+", " ", safe).strip(" .")
    return safe or fallback


def _natural_sort_key(path: Path) -> list[Any]:
    parts = re.split(r"(\d+)", path.name.lower())
    return [int(part) if part.isdigit() else part for part in parts]


def _extract_html_title(raw_html: str, fallback: str) -> str:
    parser = _HtmlTitleExtractor()
    try:
        parser.feed(raw_html)
        title = parser.title.strip()
        return title or fallback
    except Exception:
        return fallback


def _media_type_for_cover(path: Path) -> str:
    guessed, _ = mimetypes.guess_type(str(path))
    return guessed or "image/jpeg"


class ReleaseService:
    def __init__(self, workspace: Workspace):
        self.workspace = workspace

    def source_paths(self, volume: int) -> dict[str, Path]:
        return {
            "segments": self.workspace.segments_file(volume),
            "draft": self.workspace.draft_translations(volume),
            "fixed": self.workspace.fixed_translations(volume),
        }

    def choose_translation_map(self, volume: int, mode: str) -> tuple[str, dict[str, str]]:
        paths = self.source_paths(volume)
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
                if isinstance(text, str) and text:
                    draft_map[str(item_id)] = text

        for row in fixed_rows:
            if row.get("status") != "success":
                continue
            item_id = row.get("item_id")
            result = row.get("result", {})
            if item_id and isinstance(result, dict):
                text = result.get("fixed_translation") or result.get("translation") or ""
                if isinstance(text, str) and text:
                    fixed_map[str(item_id)] = text

        if mode == "draft_only":
            return "draft", draft_map
        if mode == "fixed_only":
            return "fixed", fixed_map
        if mode != "fixed_if_available":
            raise ValueError(f"Unsupported translation source mode: {mode}")

        if fixed_map:
            merged = dict(draft_map)
            merged.update(fixed_map)
            return "fixed_if_available", merged
        return "draft", draft_map

    def build_volume_json(self, volume: int, translation_source: str) -> tuple[list[dict[str, Any]], ReleaseDiagnostics]:
        paths = self.source_paths(volume)
        if not paths["segments"].exists():
            raise FileNotFoundError(f"Khong tim thay segments file: {paths['segments']}")

        segments_data = read_json(paths["segments"])
        if isinstance(segments_data, dict) and "segments" in segments_data:
            segments = segments_data["segments"]
        elif isinstance(segments_data, list):
            segments = segments_data
        else:
            raise ValueError("Segments file khong dung schema.")

        if not isinstance(segments, list):
            raise ValueError("Segments file khong dung schema.")

        source_mode, translations = self.choose_translation_map(volume, translation_source)

        chapters: OrderedDict[int, dict[str, Any]] = OrderedDict()
        missing_segments: list[str] = []

        for seg in segments:
            if not isinstance(seg, dict):
                continue
            chapter = int(seg.get("chapter", 0))
            name = str(seg.get("name", f"Chapter {chapter}"))
            segment_id = str(seg.get("segment", f"c{chapter:03d}"))
            translated = translations.get(segment_id, "").strip()

            if chapter not in chapters:
                chapters[chapter] = {"chapter": chapter, "name": name, "_parts": []}

            if translated:
                chapters[chapter]["_parts"].append(translated)
            else:
                missing_segments.append(segment_id)

        out: list[dict[str, Any]] = []
        for chapter, data in chapters.items():
            content = "\n\n".join(part for part in data["_parts"] if part).strip()
            out.append({"chapter": chapter, "name": data["name"], "content": content})

        diagnostics = ReleaseDiagnostics(
            source_mode=source_mode,
            total_chapters=len(out),
            total_segments=len(segments),
            translated_segments=len(translations),
            missing_segments=missing_segments[:200],
            missing_count=len(missing_segments),
        )
        return out, diagnostics

    def write_volume_json(self, volume: int, chapters: list[dict[str, Any]], output_dir: Path) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / f"volume_{volume:02d}.json"
        write_json(path, chapters)
        return path

    def create_chapter_html(self, title: str, content: str) -> str:
        paragraphs = [p.strip() for p in content.split("\n") if p.strip()]
        p_tags = "".join([f'\n<p class="calibre3">{py_html.escape(p)}</p>' for p in paragraphs])
        safe_title = py_html.escape(title)

        return f"""<?xml version="1.0" encoding="utf-8"?>
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
</html>"""

    def write_html_release(
        self,
        volume: int,
        chapters: list[dict[str, Any]],
        output_dir: Path,
        novel_title: str,
    ) -> tuple[Path, Path]:
        html_dir = output_dir / f"volume_{volume:02d}_html"
        html_dir.mkdir(parents=True, exist_ok=True)
        toc_items: list[tuple[str, str]] = []

        for index, chapter in enumerate(chapters, start=1):
            chapter_number = int(chapter.get("chapter", index))
            chapter_name = str(chapter.get("name", f"Chapter {chapter_number}"))
            chapter_content = str(chapter.get("content", ""))
            filename = f"chapter_{chapter_number:04d}.html"
            html = self.create_chapter_html(chapter_name, chapter_content)
            (html_dir / filename).write_text(html, encoding="utf-8")
            toc_items.append((filename, chapter_name))

        toc_path = self._create_toc_html(
            html_dir,
            novel_title.strip() or f"Volume {volume:02d}",
            toc_items,
        )
        return html_dir, toc_path

    def copy_css_files(self, html_dir: Path, css_files: list[Path]) -> list[Path]:
        copied: list[Path] = []
        html_dir.mkdir(parents=True, exist_ok=True)
        for src in css_files:
            source = Path(src)
            if not source.exists():
                continue
            dst = html_dir / source.name
            dst.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
            copied.append(dst)
        return copied

    def pack_epub_from_html(
        self,
        html_dir: Path,
        output_dir: Path,
        title: str,
        author: str,
        volume: int,
        css_files: list[Path],
        cover_path: Path | None,
    ) -> tuple[Path, dict[str, Any]]:
        try:
            from ebooklib import epub
        except ImportError as exc:
            raise ImportError("Thieu dependency 'ebooklib'. Cai bang: pip install ebooklib") from exc

        html_files = self._html_files_for_epub(html_dir)
        if not html_files:
            raise FileNotFoundError(f"Khong tim thay HTML trong: {html_dir}")

        epub_css = self._css_files_for_epub(html_dir, css_files)
        safe_title = title.strip() or f"Volume {volume:02d}"
        safe_author = author.strip() or "Unknown"
        epub_filename = f"{_sanitize_filename(safe_title)} - v{volume:02d}.epub"
        epub_path = output_dir / epub_filename

        book = epub.EpubBook()
        book.set_identifier(f"ln_release_v{volume:02d}_{int(time.time())}")
        book.set_title(safe_title)
        book.set_language("vi")
        book.add_author(safe_author)

        for epub_name, css_path in epub_css:
            css_item = epub.EpubItem(
                uid=f"css_{_sanitize_filename(epub_name, 'style').replace('.', '_')}",
                file_name=epub_name,
                media_type="text/css",
                content=css_path.read_text(encoding="utf-8"),
            )
            book.add_item(css_item)

        html_items = []
        toc_items = []
        for index, html_path in enumerate(html_files, start=1):
            raw_html = html_path.read_text(encoding="utf-8")
            fallback_title = safe_title if html_path.name == "0.html" else f"Chapter {index}"
            chapter_title = _extract_html_title(raw_html, fallback_title)
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

        cover_added = False
        if cover_path is not None:
            resolved_cover = Path(cover_path)
            if resolved_cover.exists():
                cover_name = f"cover{resolved_cover.suffix.lower() or '.jpg'}"
                book.set_cover(cover_name, resolved_cover.read_bytes())
                cover_added = True

        book.toc = [epub.Link(item.file_name, getattr(item, "title", item.file_name), item.id) for item in toc_items]
        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())
        book.spine = ["nav"] + html_items

        epub.write_epub(str(epub_path), book, {})
        return epub_path, {
            "epub_output": str(epub_path),
            "html_count": len(html_items),
            "toc_count": len(toc_items),
            "css_count": len(epub_css),
            "cover_added": cover_added,
            "cover_media_type": _media_type_for_cover(Path(cover_path)) if cover_added and cover_path is not None else None,
        }

    def add_to_calibre(self, epub_path: Path) -> dict[str, Any]:
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
            return {
                "attempted": True,
                "success": False,
                "error": "calibredb not found",
                "stdout": "",
                "stderr": "",
                "returncode": None,
            }

        success = result.returncode == 0
        payload: dict[str, Any] = {
            "attempted": True,
            "success": success,
            "stdout": (result.stdout or "").strip(),
            "stderr": (result.stderr or "").strip(),
            "returncode": result.returncode,
        }
        if not success:
            payload["error"] = ((result.stderr or result.stdout or "Unknown Calibre error").strip())
        return payload

    def build_release(self, options: ReleaseOptions) -> ReleaseBuildResult:
        output_dir = Path(options.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        messages: list[str] = []

        chapters, diagnostics = self.build_volume_json(options.volume, options.translation_source)
        messages.append(
            f"Built volume JSON from {diagnostics.source_mode} with {diagnostics.total_chapters} chapters."
        )
        if diagnostics.missing_count:
            sample = ", ".join(diagnostics.missing_segments[:15])
            messages.append(f"Missing segments: {diagnostics.missing_count}" + (f" ({sample})" if sample else ""))

        volume_json_path = self.write_volume_json(options.volume, chapters, output_dir)
        messages.append(f"Wrote volume JSON: {volume_json_path}")

        title = options.novel_title.strip() or f"Volume {options.volume:02d}"
        html_dir, toc_path = self.write_html_release(options.volume, chapters, output_dir, title)
        messages.append(f"Wrote HTML release: {html_dir}")
        messages.append(f"Wrote TOC HTML: {toc_path}")

        copied_css: list[Path] = []
        if options.copy_css:
            copied_css = self.copy_css_files(html_dir, [Path(path) for path in options.css_files])
            for copied in copied_css:
                messages.append(f"Copied CSS: {copied.name}")
            requested = [Path(path) for path in options.css_files]
            copied_names = {path.name for path in copied_css}
            for css_path in requested:
                if css_path.name not in copied_names:
                    messages.append(f"Skipped missing CSS: {css_path}")

        epub_path: Path | None = None
        epub_info: dict[str, Any] | None = None
        calibre_info: dict[str, Any] | None = None
        if options.pack_epub:
            epub_path, epub_info = self.pack_epub_from_html(
                html_dir=html_dir,
                output_dir=output_dir,
                title=title,
                author=options.book_author,
                volume=options.volume,
                css_files=[Path(path) for path in options.css_files] if options.css_files else copied_css,
                cover_path=options.cover_path,
            )
            messages.append(f"Packed EPUB: {epub_path}")
            if options.add_to_calibre and epub_path.exists():
                calibre_info = self.add_to_calibre(epub_path)
                if calibre_info.get("success"):
                    messages.append("Added EPUB to Calibre.")
                else:
                    messages.append(
                        "Calibre add failed: "
                        + str(calibre_info.get("error") or calibre_info.get("stderr") or calibre_info.get("returncode"))
                    )

        manifest_message = f"Wrote release manifest: {output_dir / f'volume_{options.volume:02d}.release_manifest.json'}"
        manifest = {
            "timestamp": dt.datetime.now().isoformat(),
            "volume": options.volume,
            "output_paths": {
                "volume_json_path": str(volume_json_path) if volume_json_path is not None else None,
                "html_dir": str(html_dir) if html_dir is not None else None,
                "toc_path": str(toc_path) if toc_path is not None else None,
                "epub_path": str(epub_path) if epub_path is not None else None,
            },
            "options": self._json_safe(asdict(options)),
            "diagnostics": self._json_safe(asdict(diagnostics)),
            "messages": messages + [manifest_message],
            "epub": self._json_safe(epub_info),
            "calibre": self._json_safe(calibre_info),
        }
        manifest_path = output_dir / f"volume_{options.volume:02d}.release_manifest.json"
        write_json(manifest_path, manifest)
        messages.append(manifest_message)

        return ReleaseBuildResult(
            volume=options.volume,
            output_dir=output_dir,
            volume_json_path=volume_json_path,
            html_dir=html_dir,
            toc_path=toc_path,
            epub_path=epub_path,
            manifest_path=manifest_path,
            diagnostics=diagnostics,
            messages=messages,
        )

    def _create_toc_html(self, html_dir: Path, novel_title: str, toc_items: list[tuple[str, str]]) -> Path:
        body_lines = [
            f'\n<p class="calibre3"><a href="{filename}">{py_html.escape(title)}</a></p>'
            for filename, title in toc_items
        ]
        full_html = f"""<?xml version="1.0" encoding="utf-8"?>
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
</html>"""
        toc_path = html_dir / "0.html"
        toc_path.write_text(full_html, encoding="utf-8")
        return toc_path

    def _css_files_for_epub(self, html_dir: Path, css_files: list[Path]) -> list[tuple[str, Path]]:
        resolved: list[tuple[str, Path]] = []
        seen_names: set[str] = set()

        for source in css_files:
            src = Path(source)
            target_name = src.name
            html_css = html_dir / target_name
            candidate = html_css if html_css.exists() else src
            if candidate.exists() and target_name not in seen_names:
                resolved.append((target_name, candidate))
                seen_names.add(target_name)

        for src in sorted(html_dir.glob("*.css"), key=_natural_sort_key):
            if src.name not in seen_names:
                resolved.append((src.name, src))
                seen_names.add(src.name)

        return resolved

    def _html_files_for_epub(self, html_dir: Path) -> list[Path]:
        files = [path for path in html_dir.iterdir() if path.is_file() and path.suffix.lower() in {".html", ".htm", ".xhtml"}]
        return sorted(files, key=_natural_sort_key)

    def _json_safe(self, value: Any) -> Any:
        if isinstance(value, Path):
            return str(value)
        if isinstance(value, dict):
            return {str(key): self._json_safe(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self._json_safe(item) for item in value]
        return value
