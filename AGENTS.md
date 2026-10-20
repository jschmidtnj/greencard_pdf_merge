# Agent Guide & Repository Rules

This document provides guidelines and instructions for AI agents and developers operating in this repository. It covers environment setup, configuration management, interacting with `merge_pdfs.py`, and handling text/checkmark overlays.

---

## 1. Project Overview

## 1. Project Overview

> **Skill Available**: For step-by-step procedures, refer to the [greencard-pdf-merger](./.agents/skills/greencard-pdf-merger/SKILL.md) skill located in `.agents/skills/greencard-pdf-merger/SKILL.md`.


This repository automates the merging, indexing, bookmarking, and annotation of multi-document PDF application packets (such as USCIS green card applications).

- **`merge_pdfs.py`**: The primary executable CLI tool. Merges PDFs defined in a YAML configuration into one or more standalone packets with document-level bookmarks and optional text overlays.
- **`config.example.yaml`**: The starter template configuration file for new users.
- **`config.yaml`**: The active user configuration (created from `config.example.yaml`).
- **`requirements.txt`**: Python dependencies (`pypdf`, `pyyaml`, `pymupdf`).
- **`docs/`**: Directory where raw source PDFs are placed.

---

## 2. Python Environment Setup (From Scratch)

When starting on a new machine or with a fresh clone:

1. **Prerequisites**:
   - Python 3.10 or higher.
   - Recommended: Check Python version with `python3 --version`.

2. **Create and Activate Virtual Environment**:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. **Install Dependencies**:
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

4. **Verify Dependencies**:
   ```bash
   python3 -c "import pypdf, yaml, pymupdf; print('Environment ready!')"
   ```

> **Note on auto-switching**: `merge_pdfs.py` includes a self-healing bootstrap function (`_ensure_dependencies`). If executed with a system Python lacking the required libraries, it will automatically look for and re-execute itself using `.venv/bin/python`.

---

## 3. Configuration Management

New users start with `config.example.yaml`.

### Step 1: Initialize `config.yaml`
```bash
cp config.example.yaml config.yaml
```

### Step 2: Configure Document Packets
In `config.yaml`, customize:
- `source_dir`: Base folder containing the PDF files (defaults to `"docs"`).
- `packets`: Dictionary of packets to produce. Each packet includes:
  - `output`: Output PDF file name (e.g. `i_130_petition_packet.pdf`).
  - `description`: Human-readable label printed during merge runs.
  - `bookmarks`: `true` to generate outline bookmarks (recommended: `true`).
  - `import_sub_bookmarks`: `false` to prevent cluttering the outline with internal bookmarks from tax returns or bank statements.
  - `text_overlays`: List of custom text/checkmarks to stamp on merged pages (see Section 5).
  - `files`: Ordered list of file paths relative to `source_dir`.

---

## 4. Interacting with `merge_pdfs.py`

### CLI Commands & Flags

| Command | Description |
| :--- | :--- |
| `./merge_pdfs.py` | Merges all packets defined in `config.yaml`. |
| `./merge_pdfs.py --dry-run` | **Preview only**: Prints file order, page ranges, and overlay plans without creating files. |
| `./merge_pdfs.py --packet <key>` | Merges only the specified packet (e.g., `--packet i130_packet`). |
| `./merge_pdfs.py -c <path>` | Specifies a custom YAML configuration file instead of `config.yaml`. |
| `./merge_pdfs.py -d <path>` | Overrides the source documents directory. |
| `./merge_pdfs.py --no-bookmarks` | Disables outline bookmarks for the run. |
| `./merge_pdfs.py --no-auto-rotate` | Disables automatic rotation of horizontal/landscape pages. |
| `./merge_pdfs.py --no-fit-to-letter` | Disables automatic resizing to standard US Letter (8.5x11). |

### Recommended Workflow for Agents
1. Whenever modifying `config.yaml` or `merge_pdfs.py`, **always run a dry run first**:
   ```bash
   ./merge_pdfs.py --dry-run
   ```
2. Verify that all referenced files resolve and no warnings are emitted.
3. Execute the target packet or full build:
   ```bash
   ./merge_pdfs.py --packet <packet_key>
   ```

---

## 5. Working with Text & Checkmark Overlays

The merger script uses `pymupdf` to draw text overlays (such as checkboxes, initials, or notes) directly on top of the merged PDF pages.

### Coordinate System & Rules
- **Coordinate Origin**: Top-left corner of the page is `(0, 0)`.
- **Units**: Standard PDF points ($72 \text{ points} = 1 \text{ inch}$). A US Letter page is $612 \times 792$ points.
- **Page Indexing**: `page` in `text_overlays` is **1-based** referencing the page number in the final merged packet.
- **Baseline Alignment**: When providing `(x, y)`, `y` is the **text baseline** (the bottom edge of text glyphs like "X").

### Configuration Syntax
In `config.yaml` under the desired packet:
```yaml
text_overlays:
  # Using point coordinates:
  - page: 12                # Page number in merged packet (1-based)
    x: 61                   # Points from left edge
    y: 490                  # Points from top edge (baseline)
    text: "X"               # Text to render
    fontsize: 14            # Font size (default: 14)
    color: [0, 0, 0]        # RGB color tuple (default: black)
    overlay: true           # Render on top of page content

  # Alternatively, using bounding box rectangle [x0, y0, x1, y1]:
  - page: 286
    rect: [80, 500, 95, 515]
    text: "X"
    fontsize: 14
```

### Finding Coordinates on Scanned Pages
If fine-tuning coordinates for a checkbox or field:
```python
import pymupdf
doc = pymupdf.open("i_130_petition_packet.pdf")
page = doc[11]  # 0-indexed for Page 12
# Render a high-resolution preview of a region to inspect:
rect = pymupdf.Rect(40, 450, 150, 550)
pix = page.get_pixmap(dpi=150, clip=rect)
pix.save("scratch/checkbox_preview.png")
```

---

## 6. Safety & Best Practices for Agents

1. **Source Document Immutability**: Never overwrite, modify, or delete original files inside `docs/`.
2. **Bookmarks Integrity**: Maintain top-level bookmarks for easy navigation. Avoid setting `import_sub_bookmarks: true` unless explicitly requested, as large tax returns can inject hundreds of noisy sub-bookmarks.
3. **Missing File Handling**: The script reports missing files during `--dry-run` and aborts safely if required files are absent during a live merge.
