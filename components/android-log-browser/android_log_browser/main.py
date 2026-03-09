from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Annotated

import typer

from .html_viewer import build_sections_viewer_html
from .parsers import (
    dumpsys_summary_json,
    expand_inputs,
    index_dumpsys_blocks,
    iter_buffer_matches,
    list_dumpstate_sections,
    select_dumpsys_blocks,
)


app = typer.Typer(help="android-log-browser: Android bugreport/dumpstate parser CLI.")


def _compile_regex(pattern: str, ignore_case: bool) -> re.Pattern[str]:
    flags = re.IGNORECASE if ignore_case else 0
    try:
        return re.compile(pattern, flags=flags)
    except re.error as err:
        raise typer.BadParameter(f"Invalid regex: {err}") from err


def _parse_buffer_set(buffers: str) -> set[str]:
    if not buffers.strip():
        raise typer.BadParameter("At least one buffer is required.")

    normalized = set()
    for item in buffers.split(","):
        b = item.strip().lower()
        if b in {"main", "system", "logcat"}:
            normalized.add("logcat")
        elif b == "radio":
            normalized.add("radio")
        elif b in {"event", "events"}:
            normalized.add("events")
        else:
            raise typer.BadParameter(
                f"Unsupported buffer '{item}'. Use logcat, radio, or events."
            )
    return normalized


def _emit(message: str | dict, output_file: Path | None = None) -> None:
    text = message if isinstance(message, str) else str(message)
    typer.echo(text)
    if output_file is not None:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with output_file.open("a", encoding="utf-8") as handle:
            handle.write(text)
            handle.write("\n")


@app.command("buffers")
def filter_buffers(
    input_path: Annotated[Path, typer.Option("--input", "-i", help="Input zip/txt/log/dir")],
    regex: Annotated[str, typer.Option("--regex", "-r", help="Regex pattern to match")],
    buffers: Annotated[
        str,
        typer.Option("--buffers", "-b", help="Comma-separated: logcat,radio,events"),
    ] = "logcat,radio,events",
    ignore_case: Annotated[bool, typer.Option("--ignore-case", "-I")] = False,
    context: Annotated[
        int, typer.Option("--context", "-c", help="Lines before/after each match")
    ] = 0,
    as_json: Annotated[bool, typer.Option("--json", help="Output matches in JSON-like format")] = False,
    output: Annotated[Path | None, typer.Option("--output", "-o", help="Write output to file")] = None,
) -> None:
    if output is not None:
        output.write_text("", encoding="utf-8")

    selected = _parse_buffer_set(buffers)
    compiled = _compile_regex(regex, ignore_case=ignore_case)
    files, tempdir = expand_inputs(input_path)

    try:
        count = 0
        for match in iter_buffer_matches(
            files=files,
            selected_buffers=selected,
            pattern=compiled,
            context=max(context, 0),
        ):
            count += 1
            if as_json:
                _emit(
                    {
                        "buffer": match.buffer,
                        "source": str(match.line.source),
                        "line_no": match.line.line_no,
                        "text": match.line.text,
                    },
                    output_file=output,
                )
            else:
                _emit(
                    f"[{match.buffer}] {match.line.source}:{match.line.line_no}: {match.line.text}",
                    output_file=output,
                )

        _emit(f"\nTotal matched lines: {count}", output_file=output)
    finally:
        if tempdir is not None:
            tempdir.cleanup()


@app.command("dumpsys")
def filter_dumpsys(
    input_path: Annotated[Path, typer.Option("--input", "-i", help="Input zip/txt/log/dir")],
    services: Annotated[
        str | None,
        typer.Option(
            "--services",
            "-s",
            help="Comma-separated exact service names, e.g. batterystats,alarm",
        ),
    ] = None,
    service_regex: Annotated[
        str | None, typer.Option("--service-regex", help="Regex for service names")
    ] = None,
    list_services: Annotated[bool, typer.Option("--list-services")] = False,
    as_json: Annotated[bool, typer.Option("--json", help="Output summary as JSON")] = False,
    output: Annotated[Path | None, typer.Option("--output", "-o", help="Write output to file")] = None,
) -> None:
    if output is not None:
        output.write_text("", encoding="utf-8")

    files, tempdir = expand_inputs(input_path)

    try:
        blocks_by_service = index_dumpsys_blocks(files)
        all_services = sorted(blocks_by_service.keys())

        if list_services:
            for name in all_services:
                _emit(name, output_file=output)
            _emit(f"\nTotal services indexed: {len(all_services)}", output_file=output)
            return

        selected_names: set[str] | None = None
        selected_pattern: re.Pattern[str] | None = None

        if services:
            selected_names = {s.strip() for s in services.split(",") if s.strip()}
        if service_regex:
            selected_pattern = _compile_regex(service_regex, ignore_case=True)

        if not selected_names and not selected_pattern:
            raise typer.BadParameter(
                "Provide --services or --service-regex, or use --list-services."
            )

        blocks = select_dumpsys_blocks(
            blocks_by_service=blocks_by_service,
            service_pattern=selected_pattern,
            service_names=selected_names,
        )

        if as_json:
            _emit(dumpsys_summary_json(blocks), output_file=output)
            return

        if not blocks:
            _emit("No dumpsys service blocks matched.", output_file=output)
            raise typer.Exit(code=1)

        for block in blocks:
            _emit(
                f"\n===== service={block.service} source={block.source} "
                f"lines={block.start_line}-{block.end_line} =====",
                output_file=output,
            )
            for line in block.lines:
                _emit(line, output_file=output)

        _emit(f"\nTotal matched service blocks: {len(blocks)}", output_file=output)
    finally:
        if tempdir is not None:
            tempdir.cleanup()


@app.command("sections")
def list_sections(
    input_path: Annotated[Path, typer.Option("--input", "-i", help="Input zip/txt/log/dir")],
    unique: Annotated[bool, typer.Option("--unique/--all", help="List unique section titles only")] = True,
    include_noisy: Annotated[
        bool,
        typer.Option("--include-noisy", help="Include duration/formatting-noise headers"),
    ] = False,
    as_json: Annotated[bool, typer.Option("--json", help="Output section list as JSON")] = False,
    output: Annotated[Path | None, typer.Option("--output", "-o", help="Write output to file")] = None,
) -> None:
    if output is not None:
        output.write_text("", encoding="utf-8")

    files, tempdir = expand_inputs(input_path)
    try:
        sections = list_dumpstate_sections(files, unique=unique, include_noisy=include_noisy)
        if as_json:
            payload = [
                {
                    "title": section.title,
                    "source": str(section.source),
                    "start_line": section.start_line,
                    "end_line": section.end_line,
                    "line_count": section.line_count,
                }
                for section in sections
            ]
            _emit(json.dumps(payload, indent=2), output_file=output)
            return

        for section in sections:
            _emit(
                f"{section.source}:{section.start_line}-{section.end_line} "
                f"({section.line_count} lines): {section.title}",
                output_file=output,
            )
        _emit(
            f"\nTotal sections detected: {len(sections)} "
            f"(unique={str(unique).lower()}, include_noisy={str(include_noisy).lower()})",
            output_file=output,
        )
    finally:
        if tempdir is not None:
            tempdir.cleanup()


@app.command("sections-html")
def sections_html(
    input_path: Annotated[Path, typer.Option("--input", "-i", help="Input zip/txt/log/dir")],
    output: Annotated[Path, typer.Option("--output", "-o", help="Output HTML file path")],
    unique: Annotated[bool, typer.Option("--unique/--all", help="List unique section titles only")] = True,
    include_noisy: Annotated[
        bool,
        typer.Option("--include-noisy", help="Include duration/formatting-noise headers"),
    ] = False,
    index_json: Annotated[
        Path | None,
        typer.Option("--index-json", help="Optional path to write section index JSON"),
    ] = None,
) -> None:
    files, tempdir = expand_inputs(input_path)
    try:
        source_hint = str(files[0]) if files else str(input_path)
        sections = list_dumpstate_sections(files, unique=unique, include_noisy=include_noisy)

        output.parent.mkdir(parents=True, exist_ok=True)
        html_content = build_sections_viewer_html(
            sections=sections,
            dumpstate_hint_path=source_hint,
        )
        output.write_text(html_content, encoding="utf-8")

        if index_json is not None:
            index_json.parent.mkdir(parents=True, exist_ok=True)
            payload = [
                {
                    "title": section.title,
                    "source": str(section.source),
                    "start_line": section.start_line,
                    "end_line": section.end_line,
                    "line_count": section.line_count,
                }
                for section in sections
            ]
            index_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")

        typer.echo(f"Wrote sections HTML viewer: {output}")
        typer.echo(f"Sections indexed: {len(sections)}")
        typer.echo(
            "Open the HTML in a browser, then click 'Open dumpstate file' to select the source file."
        )
    finally:
        if tempdir is not None:
            tempdir.cleanup()


if __name__ == "__main__":
    app()
