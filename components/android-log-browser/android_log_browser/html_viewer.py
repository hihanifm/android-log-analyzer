from __future__ import annotations

import json

from .parsers import DumpstateSection


def build_sections_viewer_html(
    sections: list[DumpstateSection],
    dumpstate_hint_path: str,
    preview_line_limit: int = 400,
) -> str:
    section_payload = [
        {
            "title": section.title,
            "source": str(section.source),
            "start_line": section.start_line,
            "end_line": section.end_line,
            "line_count": section.line_count,
        }
        for section in sections
    ]
    sections_json = json.dumps(section_payload, ensure_ascii=False)
    hint_json = json.dumps(dumpstate_hint_path, ensure_ascii=False)

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>android-log-browser sections viewer</title>
  <style>
    :root {{
      --bg: #0b1020;
      --panel: #121a2d;
      --text: #e7ecf7;
      --muted: #9fb0d0;
      --accent: #4da3ff;
      --border: #26324d;
    }}
    body {{
      margin: 0;
      font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial;
      background: var(--bg);
      color: var(--text);
      overflow: hidden;
    }}
    .app {{
      display: grid;
      grid-template-columns: 380px 1fr;
      height: 100vh;
      overflow: hidden;
    }}
    .left {{
      border-right: 1px solid var(--border);
      background: var(--panel);
      display: flex;
      flex-direction: column;
      min-width: 320px;
      min-height: 0;
    }}
    .toolbar {{
      padding: 12px;
      border-bottom: 1px solid var(--border);
      display: grid;
      gap: 8px;
    }}
    input[type="text"] {{
      width: 100%;
      box-sizing: border-box;
      background: #0f1528;
      color: var(--text);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 10px;
      font-size: 14px;
    }}
    button {{
      background: #183157;
      color: #dbe7ff;
      border: 1px solid #2a4a79;
      border-radius: 8px;
      padding: 8px 10px;
      cursor: pointer;
    }}
    button:hover {{ filter: brightness(1.1); }}
    .list {{
      flex: 1;
      min-height: 0;
      overflow: auto;
      overscroll-behavior: contain;
      padding: 8px;
    }}
    .item {{
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 10px;
      margin-bottom: 8px;
      cursor: pointer;
      background: #0f1629;
    }}
    .item:hover {{ border-color: var(--accent); }}
    .item.active {{ border-color: var(--accent); box-shadow: 0 0 0 1px #2d5ea2 inset; }}
    .title {{
      font-size: 13px;
      font-weight: 600;
      line-height: 1.3;
    }}
    .meta {{
      margin-top: 6px;
      color: var(--muted);
      font-size: 12px;
    }}
    .right {{
      display: flex;
      flex-direction: column;
      min-width: 0;
      min-height: 0;
    }}
    .status {{
      border-bottom: 1px solid var(--border);
      padding: 10px 12px;
      color: var(--muted);
      font-size: 13px;
      display: flex;
      justify-content: space-between;
      gap: 16px;
      align-items: center;
      flex-wrap: wrap;
    }}
    .content {{
      flex: 1;
      min-height: 0;
      padding: 12px;
      overflow: auto;
      overscroll-behavior: contain;
      white-space: pre-wrap;
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 12px;
      line-height: 1.4;
      margin: 0;
    }}
    .contentHeader {{
      padding: 10px 12px;
      border-bottom: 1px solid var(--border);
      display: flex;
      align-items: center;
      gap: 8px;
      flex-wrap: wrap;
      background: #0f1628;
    }}
    .hint {{ color: var(--muted); font-size: 12px; }}
  </style>
</head>
<body>
  <div class="app">
    <aside class="left">
      <div class="toolbar">
        <button id="pickFileBtn">Open dumpstate file</button>
        <input id="fileInput" type="file" accept=".txt,.log" style="display:none" />
        <input id="searchInput" type="text" placeholder="Search sections..." />
        <div class="hint" id="listInfo"></div>
      </div>
      <div id="sectionList" class="list"></div>
    </aside>

    <main class="right">
      <div class="status">
        <div id="fileStatus">No file selected. Hint path: <code id="hintPath"></code></div>
        <div id="loadStatus">Idle</div>
      </div>
      <div class="contentHeader">
        <button id="loadPreviewBtn" disabled>Load preview</button>
        <button id="loadFullBtn" disabled>Load full section</button>
        <button id="copyBtn" disabled>Copy visible content</button>
        <div class="hint" id="selectionInfo">No section selected</div>
      </div>
      <pre id="contentPane" class="content">Select a section from the left panel.</pre>
    </main>
  </div>

  <script>
  const sections = {sections_json};
  const dumpstateHintPath = {hint_json};
  const previewLineLimit = {preview_line_limit};

  const sectionListEl = document.getElementById("sectionList");
  const searchInputEl = document.getElementById("searchInput");
  const listInfoEl = document.getElementById("listInfo");
  const fileStatusEl = document.getElementById("fileStatus");
  const loadStatusEl = document.getElementById("loadStatus");
  const hintPathEl = document.getElementById("hintPath");
  const contentPaneEl = document.getElementById("contentPane");
  const selectionInfoEl = document.getElementById("selectionInfo");
  const pickFileBtnEl = document.getElementById("pickFileBtn");
  const fileInputEl = document.getElementById("fileInput");
  const loadPreviewBtnEl = document.getElementById("loadPreviewBtn");
  const loadFullBtnEl = document.getElementById("loadFullBtn");
  const copyBtnEl = document.getElementById("copyBtn");

  hintPathEl.textContent = dumpstateHintPath || "(none)";

  let selectedFile = null;
  let selectedSection = null;
  let filteredSections = [...sections];
  let lineOffsets = null;
  let lineIndexReady = false;
  let sectionCache = new Map();

  function setLoadStatus(text) {{
    loadStatusEl.textContent = text;
  }}

  function updateListInfo() {{
    listInfoEl.textContent = `${{filteredSections.length}} sections shown / ${{sections.length}} total`;
  }}

  function normalize(text) {{
    return (text || "").toLowerCase();
  }}

  function renderSectionList() {{
    sectionListEl.innerHTML = "";
    for (const section of filteredSections) {{
      const item = document.createElement("div");
      item.className = "item" + (selectedSection === section ? " active" : "");
      item.innerHTML = `
        <div class="title">${{escapeHtml(section.title)}}</div>
        <div class="meta">${{section.start_line}}-${{section.end_line}} | ${{section.line_count}} lines</div>
      `;
      item.addEventListener("click", () => selectSection(section));
      sectionListEl.appendChild(item);
    }}
    updateListInfo();
  }}

  function escapeHtml(value) {{
    return value
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;");
  }}

  function selectSection(section) {{
    selectedSection = section;
    selectionInfoEl.textContent = `${{section.title}} (${{section.start_line}}-${{section.end_line}}, ${{section.line_count}} lines)`;
    loadPreviewBtnEl.disabled = false;
    loadFullBtnEl.disabled = false;
    renderSectionList();
    void loadSectionPreview();
  }}

  async function pickFileViaPicker() {{
    if (window.showOpenFilePicker) {{
      const [handle] = await window.showOpenFilePicker({{
        types: [{{ description: "Dumpstate text", accept: {{ "text/plain": [".txt", ".log"] }} }}],
        multiple: false
      }});
      return await handle.getFile();
    }}
    return null;
  }}

  async function ensureLineIndex() {{
    if (!selectedFile) {{
      throw new Error("Select a file first.");
    }}
    if (lineIndexReady && lineOffsets) {{
      return;
    }}

    setLoadStatus("Indexing lines...");
    lineOffsets = [0];
    let bytePos = 0;
    const reader = selectedFile.stream().getReader();

    let prevEndedWithCR = false;
    while (true) {{
      const {{ done, value }} = await reader.read();
      if (done) {{
        break;
      }}

      if (prevEndedWithCR && value.length > 0) {{
        if (value[0] === 10) {{
          // Previous chunk ended with CR and this chunk starts with LF (CRLF pair).
          lineOffsets.push(bytePos + 1);
        }}
        prevEndedWithCR = false;
      }}

      for (let i = 0; i < value.length; i += 1) {{
        const current = value[i];
        const next = i + 1 < value.length ? value[i + 1] : null;

        if (current === 13) {{
          // CR or CRLF newline.
          if (next === 10) {{
            lineOffsets.push(bytePos + i + 2);
            i += 1; // consume LF as part of CRLF
          }} else if (next === null) {{
            prevEndedWithCR = true;
          }} else {{
            lineOffsets.push(bytePos + i + 1);
          }}
        }} else if (current === 10) {{
          // Bare LF newline.
          lineOffsets.push(bytePos + i + 1);
        }}
      }}
      bytePos += value.length;
    }}

    if (prevEndedWithCR) {{
      // File ended with lone CR newline.
      lineOffsets.push(bytePos);
    }}

    lineOffsets.push(selectedFile.size);
    lineIndexReady = true;
    setLoadStatus(`Indexed ${{lineOffsets.length - 1}} lines`);
  }}

  function lineToByteStart(lineNumber) {{
    if (!lineOffsets) {{
      return 0;
    }}
    const idx = Math.max(0, Math.min(lineNumber - 1, lineOffsets.length - 1));
    return lineOffsets[idx];
  }}

  function lineToByteEnd(nextLineNumber) {{
    if (!lineOffsets) {{
      return selectedFile.size;
    }}
    const idx = Math.max(0, Math.min(nextLineNumber - 1, lineOffsets.length - 1));
    return lineOffsets[idx];
  }}

  async function readLineRange(startLine, endLine) {{
    await ensureLineIndex();
    const startByte = lineToByteStart(startLine);
    const endByte = lineToByteEnd(endLine + 1);
    const blob = selectedFile.slice(startByte, endByte);
    return await blob.text();
  }}

  async function loadSectionContent(mode) {{
    if (!selectedFile) {{
      contentPaneEl.textContent = "Select dumpstate file first (Open dumpstate file).";
      return;
    }}
    if (!selectedSection) {{
      contentPaneEl.textContent = "Select a section first.";
      return;
    }}

    const isPreview = mode === "preview";
    const previewEnd = Math.min(
      selectedSection.end_line,
      selectedSection.start_line + previewLineLimit - 1
    );
    const startLine = selectedSection.start_line;
    const endLine = isPreview ? previewEnd : selectedSection.end_line;
    const cacheKey = `${{selectedSection.start_line}}:${{selectedSection.end_line}}:${{mode}}`;

    if (sectionCache.has(cacheKey)) {{
      contentPaneEl.textContent = sectionCache.get(cacheKey);
      setLoadStatus(`Loaded from cache (${{mode}})`);
      return;
    }}

    setLoadStatus(`Loading lines ${{startLine}}-${{endLine}}...`);
    const text = await readLineRange(startLine, endLine);
    sectionCache.set(cacheKey, text);

    if (isPreview && selectedSection.end_line > endLine) {{
      contentPaneEl.textContent =
        text + "\\n\\n[Preview truncated. Click 'Load full section' to read the remaining lines.]";
    }} else {{
      contentPaneEl.textContent = text;
    }}
    setLoadStatus(`Loaded ${{mode}} lines ${{startLine}}-${{endLine}}`);
    copyBtnEl.disabled = false;
  }}

  async function loadSectionPreview() {{
    await loadSectionContent("preview");
  }}

  async function loadSectionFull() {{
    await loadSectionContent("full");
  }}

  pickFileBtnEl.addEventListener("click", async () => {{
    try {{
      let file = await pickFileViaPicker();
      if (!file) {{
        fileInputEl.click();
        return;
      }}
      onFileSelected(file);
    }} catch (error) {{
      fileInputEl.click();
    }}
  }});

  fileInputEl.addEventListener("change", () => {{
    const file = fileInputEl.files && fileInputEl.files[0];
    if (file) {{
      onFileSelected(file);
    }}
  }});

  function onFileSelected(file) {{
    selectedFile = file;
    lineOffsets = null;
    lineIndexReady = false;
    sectionCache = new Map();
    fileStatusEl.textContent = `Selected file: ${{file.name}} (${{Math.round(file.size / 1024 / 1024)}} MB)`;
    setLoadStatus("File selected. Pick a section.");
  }}

  searchInputEl.addEventListener("input", () => {{
    const query = normalize(searchInputEl.value.trim());
    if (!query) {{
      filteredSections = [...sections];
    }} else {{
      filteredSections = sections.filter((section) => normalize(section.title).includes(query));
    }}
    renderSectionList();
  }});

  loadPreviewBtnEl.addEventListener("click", () => {{
    void loadSectionPreview();
  }});

  loadFullBtnEl.addEventListener("click", () => {{
    void loadSectionFull();
  }});

  copyBtnEl.addEventListener("click", async () => {{
    try {{
      await navigator.clipboard.writeText(contentPaneEl.textContent || "");
      setLoadStatus("Copied visible content.");
    }} catch (error) {{
      setLoadStatus("Clipboard copy failed.");
    }}
  }});

  renderSectionList();
  </script>
</body>
</html>
"""
