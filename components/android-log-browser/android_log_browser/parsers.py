from __future__ import annotations

import json
import math
import re
import tempfile
import zipfile
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator


SECTION_HEADER_RE = re.compile(r"^\s*[-=]{6,}\s*(.*?)\s*[-=]{6,}\s*$")
DUMP_OF_SERVICE_RE = re.compile(
    r"^\s*DUMP OF SERVICE(?:\s+(?P<priority>CRITICAL|HIGH|NORMAL))?\s+(?P<service>[^:]+?)\s*:\s*$"
)
DURATION_HEADER_RE = re.compile(r"^\d+\.\d+s was the duration of '.*'$")
SERVICE_PRIORITIES = {"CRITICAL", "HIGH", "NORMAL"}


@dataclass(frozen=True)
class LogLine:
    source: Path
    line_no: int
    text: str


@dataclass(frozen=True)
class BufferMatch:
    buffer: str
    line: LogLine


@dataclass(frozen=True)
class DumpsysBlock:
    service: str
    source: Path
    start_line: int
    end_line: int
    lines: list[str]


@dataclass(frozen=True)
class DumpstateSection:
    title: str
    source: Path
    start_line: int
    end_line: int
    line_count: int


def _is_text_candidate(path: Path) -> bool:
    return path.suffix.lower() in {".txt", ".log"}


def _score_analysis_candidate(path: Path) -> float:
    """
    Score likely primary dumpstate/bugreport text files.
    Higher score means better candidate for main analysis.
    """
    name = path.name.lower()
    stem = path.stem.lower()
    score = 0.0

    if re.match(r"^dumpstate-\d{4}-\d{2}-\d{2}-\d{2}-\d{2}-\d{2}\.txt$", name):
        score += 1000.0
    elif stem.startswith("dumpstate") and path.suffix.lower() == ".txt":
        score += 900.0
    elif re.match(r"^bugreport-\d{4}-\d{2}-\d{2}-\d{2}-\d{2}-\d{2}\.txt$", name):
        score += 800.0
    elif "bugreport" in name and path.suffix.lower() == ".txt":
        score += 700.0
    elif "dumpstate" in name:
        score += 600.0

    # Prefer top-level files over deeply nested FS/* artifacts.
    depth = len(path.parts)
    score += max(0.0, 50.0 - min(depth, 50))

    # Larger text files are more likely to be the consolidated report.
    try:
        size = path.stat().st_size
        score += math.log10(max(size, 1))
    except OSError:
        pass

    return score


def _select_primary_analysis_file(files: list[Path]) -> Path:
    if not files:
        raise ValueError("No candidate files found for analysis.")
    return max(files, key=_score_analysis_candidate)


def expand_inputs(input_path: Path) -> tuple[list[Path], tempfile.TemporaryDirectory[str] | None]:
    """
    Resolve input to primary analysis text file(s).
    - For zip/directory, auto-select the most likely dumpstate/bugreport text.
    - For direct text/log file input, use that file.
    Returns ([selected_file], tempdir_handle). Caller should keep tempdir_handle alive.
    """
    if not input_path.exists():
        raise FileNotFoundError(f"Input path does not exist: {input_path}")

    tempdir: tempfile.TemporaryDirectory[str] | None = None

    if input_path.is_file() and input_path.suffix.lower() == ".zip":
        tempdir = tempfile.TemporaryDirectory(prefix="bugreport_")
        with zipfile.ZipFile(input_path) as zf:
            zf.extractall(tempdir.name)
        root = Path(tempdir.name)
        candidates = [p for p in root.rglob("*") if p.is_file() and _is_text_candidate(p)]
        if not candidates:
            raise ValueError("No .txt/.log files found in zip archive.")
        primary = _select_primary_analysis_file(candidates)
        return [primary], tempdir

    if input_path.is_file() and _is_text_candidate(input_path):
        return [input_path], tempdir

    if input_path.is_dir():
        candidates = [p for p in input_path.rglob("*") if p.is_file() and _is_text_candidate(p)]
        if not candidates:
            raise ValueError("No .txt/.log files found in directory.")
        primary = _select_primary_analysis_file(candidates)
        return [primary], tempdir

    raise ValueError("Unsupported input. Use .zip, .txt, .log, or a directory.")


def _guess_buffer_from_filename(path: Path) -> str | None:
    name = path.name.lower()
    if "radio" in name:
        return "radio"
    if "event" in name:
        return "events"
    if "main" in name or "logcat" in name or "system" in name:
        return "logcat"
    return None


def _extract_header_text(line: str) -> str | None:
    match = SECTION_HEADER_RE.match(line)
    return match.group(1).strip() if match else None


def _extract_dump_of_service(line: str) -> tuple[str | None, str] | None:
    """
    Parse lines like:
      DUMP OF SERVICE CRITICAL power:
      DUMP OF SERVICE activity:
    Returns (priority, service_name).
    """
    match = DUMP_OF_SERVICE_RE.match(line)
    if not match:
        return None
    priority = match.group("priority")
    service = match.group("service").strip()
    if priority is None and service.upper() in SERVICE_PRIORITIES:
        # Guard against malformed lines where only priority was present.
        return None
    return priority, service


def _normalize_section_title(header_text: str) -> str:
    return " ".join(header_text.split())


def _is_meaningful_section_title(title: str, include_noisy: bool = False) -> bool:
    if not title:
        return False
    if not re.search(r"[A-Za-z0-9]", title):
        return False
    if include_noisy:
        return True
    if DURATION_HEADER_RE.match(title):
        return False
    # Table-like border headers and repetitive dash-art are usually noise.
    if title.startswith("+") and "-" in title:
        return False
    if set(title) <= set("-= _"):
        return False
    return True


def _guess_buffer_from_header(header_text: str) -> str | None:
    h = header_text.lower()
    if "radio" in h and "log" in h:
        return "radio"
    if "events" in h and "log" in h:
        return "events"
    if "logcat" in h and ("main" in h or "system" in h):
        return "logcat"
    if "main log" in h or "system log" in h:
        return "logcat"
    return None


def iter_buffer_matches(
    files: list[Path],
    selected_buffers: set[str],
    pattern: re.Pattern[str],
    context: int = 0,
) -> Iterator[BufferMatch]:
    for source in files:
        current_buffer = _guess_buffer_from_filename(source)
        previous = deque(maxlen=max(context, 0))
        pending_after = 0

        with source.open("r", encoding="utf-8", errors="replace") as handle:
            for idx, raw in enumerate(handle, start=1):
                line = raw.rstrip("\n")

                header_text = _extract_header_text(line)
                if header_text:
                    guessed = _guess_buffer_from_header(header_text)
                    if guessed:
                        current_buffer = guessed

                if current_buffer not in selected_buffers:
                    previous.append((idx, line))
                    continue

                matched = bool(pattern.search(line))
                if matched and context > 0:
                    for prev_no, prev_line in previous:
                        yield BufferMatch(
                            buffer=current_buffer,
                            line=LogLine(source=source, line_no=prev_no, text=prev_line),
                        )

                if matched or pending_after > 0:
                    yield BufferMatch(
                        buffer=current_buffer,
                        line=LogLine(source=source, line_no=idx, text=line),
                    )

                if matched:
                    pending_after = context
                elif pending_after > 0:
                    pending_after -= 1

                previous.append((idx, line))


def _extract_dumpsys_service_from_header(header_text: str) -> str | None:
    h = header_text.strip()
    lowered = h.lower()
    if "dumpsys" not in lowered:
        return None

    # Common bugreport style: "DUMPSYS SERVICE activity"
    if "service" in lowered:
        parts = h.split()
        try:
            service_index = next(i for i, p in enumerate(parts) if p.lower() == "service")
            if service_index + 1 < len(parts):
                candidate = parts[service_index + 1].strip(":")
                if candidate.upper() in SERVICE_PRIORITIES and service_index + 2 < len(parts):
                    return parts[service_index + 2].strip(":")
                return candidate
        except StopIteration:
            return None

    # Fallback: token after "dumpsys"
    parts = h.split()
    for i, token in enumerate(parts):
        if token.lower() == "dumpsys" and i + 1 < len(parts):
            candidate = parts[i + 1].strip(":")
            if candidate.upper() in SERVICE_PRIORITIES:
                return None
            return candidate
    return None


def index_dumpsys_blocks(files: list[Path]) -> dict[str, list[DumpsysBlock]]:
    blocks_by_service: dict[str, list[DumpsysBlock]] = defaultdict(list)

    for source in files:
        current_service: str | None = None
        current_start = 0
        current_lines: list[str] = []
        current_last_line = 0

        def flush_current() -> None:
            nonlocal current_service, current_start, current_lines, current_last_line
            if current_service is None:
                return
            blocks_by_service[current_service].append(
                DumpsysBlock(
                    service=current_service,
                    source=source,
                    start_line=current_start,
                    end_line=current_last_line,
                    lines=current_lines[:],
                )
            )
            current_service = None
            current_start = 0
            current_lines = []
            current_last_line = 0

        with source.open("r", encoding="utf-8", errors="replace") as handle:
            for idx, raw in enumerate(handle, start=1):
                line = raw.rstrip("\n")
                start_new: str | None = None

                direct = _extract_dump_of_service(line)
                if direct:
                    _, service = direct
                    start_new = service
                else:
                    header_text = _extract_header_text(line)
                    if header_text:
                        start_new = _extract_dumpsys_service_from_header(header_text)

                if start_new is not None:
                    flush_current()
                    current_service = start_new
                    current_start = idx
                    current_lines = [line]
                    current_last_line = idx
                    continue

                if current_service is not None:
                    current_lines.append(line)
                    current_last_line = idx

        flush_current()

    return blocks_by_service


def select_dumpsys_blocks(
    blocks_by_service: dict[str, list[DumpsysBlock]],
    service_pattern: re.Pattern[str] | None = None,
    service_names: set[str] | None = None,
) -> list[DumpsysBlock]:
    selected: list[DumpsysBlock] = []
    for service, blocks in blocks_by_service.items():
        if service_names and service in service_names:
            selected.extend(blocks)
            continue
        if service_pattern and service_pattern.search(service):
            selected.extend(blocks)
    return selected


def dumpsys_summary_json(blocks: Iterable[DumpsysBlock]) -> str:
    payload = []
    for block in blocks:
        payload.append(
            {
                "service": block.service,
                "source": str(block.source),
                "start_line": block.start_line,
                "end_line": block.end_line,
                "line_count": len(block.lines),
            }
        )
    return json.dumps(payload, indent=2)


def list_dumpstate_sections(
    files: list[Path],
    unique: bool = True,
    include_noisy: bool = False,
) -> list[DumpstateSection]:
    sections: list[DumpstateSection] = []
    seen_titles: set[str] = set()
    for source in files:
        section_starts: list[tuple[int, str]] = []
        total_lines = 0

        with source.open("r", encoding="utf-8", errors="replace") as handle:
            for idx, raw in enumerate(handle, start=1):
                total_lines = idx
                line = raw.rstrip("\n")
                header_text = _extract_header_text(line)

                if header_text:
                    normalized = _normalize_section_title(header_text)
                else:
                    direct = _extract_dump_of_service(line)
                    if not direct:
                        continue
                    priority, service = direct
                    normalized = (
                        f"DUMP OF SERVICE {priority} {service}"
                        if priority
                        else f"DUMP OF SERVICE {service}"
                    )

                if not _is_meaningful_section_title(normalized, include_noisy=include_noisy):
                    continue

                section_starts.append((idx, normalized))

        for i, (start_line, title) in enumerate(section_starts):
            next_start = section_starts[i + 1][0] if i + 1 < len(section_starts) else total_lines + 1
            end_line = max(start_line, next_start - 1)
            line_count = max(0, end_line - start_line + 1)

            if unique and title in seen_titles:
                continue
            seen_titles.add(title)
            sections.append(
                DumpstateSection(
                    title=title,
                    source=source,
                    start_line=start_line,
                    end_line=end_line,
                    line_count=line_count,
                )
            )
    return sections
