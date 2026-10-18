---
name: greencard-pdf-merger
description: >-
  Sets up the Python virtual environment, initializes configuration from the example template,
  and manages the merging of PDF packets using merge_pdfs.py with bookmarks and text overlays.
  Use this skill whenever setting up the environment from scratch, adding documents to packets,
  adjusting text overlays (checkmarks, annotations), or validating and executing PDF merge workflows.
---

# Green Card PDF Merger Skill

This skill guides you through bootstrapping the Python environment from scratch, configuring packet manifests using `config.example.yaml`, positioning text overlays, and generating polished multi-document application packets with `merge_pdfs.py`.

---

## 1. Environment Setup (From Scratch)

When running on a clean machine or fresh repository checkout, set up a dedicated Python virtual environment.

### Steps
1. Verify Python 3.10+ is available:
   ```bash
   python3 --version
   ```

2. Create and activate a local virtual environment:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. Install required packages from `requirements.txt`:
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```
   *Required packages:*
   - `pypdf >= 5.0.0` (Fast PDF page merging & outline bookmark generation)
   - `pyyaml >= 6.0` (Configuration parsing)
   - `pymupdf >= 1.24.0` (High-performance rasterization, vector rendering, and text overlays)

4. Test environment readiness:
   ```bash
   python3 -c "import pypdf, yaml, pymupdf; print('Dependencies installed successfully!')"
   ```

> [!NOTE]
> `merge_pdfs.py` is configured with auto-bootstrap logic: if run outside an activated virtualenv, it automatically detects `.venv/bin/python` in the repository root and re-executes itself.

---

## 2. Configuration Setup

The repository ships with `config.example.yaml` as the canonical starter template.

### Initializing Active Configuration
If `config.yaml` does not exist:
```bash
cp config.example.yaml config.yaml
```

### Configuration Structure
Open `config.yaml` to define your packets:

```yaml
source_dir: "docs"            # Directory where input PDFs reside
bookmarks: true               # Generate clickable outline bookmarks
import_sub_bookmarks: false   # Suppress noisy internal bookmarks from sub-documents
auto_rotate_portrait: true   # Auto-rotate horizontal/landscape pages to vertical for printing

packets:
  i130_packet:
    output: "i_130_petition_packet.pdf"
    description: "I-130 Petition for Alien Relative"
    text_overlays: []
    files:
      - cover_letter_i_130.pdf
      - forms/i_130.pdf
      - sponsor/passport.pdf
```

---

## 3. Configuring Text & Checkmark Overlays

Use `text_overlays` to stamp checkmarks ("X" or "✔"), initials, or text onto specific pages of the merged packet without needing to manually edit underlying PDFs.

### Placement Rules
- Coordinates use the standard PDF point system ($72 \text{ points} = 1 \text{ inch}$).
- Origin `(0, 0)` is the **top-left corner** of the page.
- Standard US Letter dimensions: $612 \times 792$ points.
- The `page` property is **1-based** referencing the final page number in the merged packet.
- For `(x, y)`, `y` represents the **text baseline** (the bottom of the characters).

### Overlay Options
```yaml
text_overlays:
  # Method 1: Point coordinates (recommended for checkmarks)
  - page: 12
    x: 61
    y: 490
    text: "X"
    fontsize: 14
    color: [0, 0, 0]      # RGB: [0, 0, 0] is black
    overlay: true         # Draws on top of page content

  # Method 2: Bounding box rectangle [x0, y0, x1, y1]
  - page: 286
    rect: [80, 500, 95, 515]
    text: "X"
    fontsize: 14
```

### Interactive Coordinate Tuning
To check the visual placement of an overlay on page $N$:
```bash
.venv/bin/python -c '
import pymupdf
doc = pymupdf.open("i_130_petition_packet.pdf")
page = doc[11]  # 0-indexed for Page 12
rect = pymupdf.Rect(40, 460, 100, 520)
pix = page.get_pixmap(dpi=150, clip=rect)
pix.save("scratch/overlay_check.png")
'
```

---

## 4. Execution Workflow

### Step 1: Preview with Dry Run
Always run a dry run first to verify page numbering, file existence, and overlay mappings:
```bash
./merge_pdfs.py --dry-run
```
Examine the printed table:
- Check that all source files exist and report valid page counts.
- Note the cumulative page range for each document.
- Confirm overlay page numbers target the expected document.

### Step 2: Merge Single Packet
To save time during iteration, build only the packet you are editing:
```bash
./merge_pdfs.py --packet i130_packet
```

### Step 3: Merge All Packets
Generate the full set of final deliverable packets:
```bash
./merge_pdfs.py
```

---

## 5. Troubleshooting & Verification

| Issue | Cause | Solution |
| :--- | :--- | :--- |
| `Missing required packages` | Dependencies not installed in `.venv` | Run `source .venv/bin/activate && pip install -r requirements.txt`. |
| `File not found in docs/` | Typo in path or file not placed in `docs/` | Check file path in `config.yaml` relative to `source_dir`. |
| Overlay not visible | Coordinates off the page or behind opaque layer | Verify coordinates ($x < 612, y < 792$) and ensure `overlay: true`. |
| Bookmark outline too long/noisy | Sub-documents injected internal bookmarks | Ensure `import_sub_bookmarks: false` in `config.yaml`. |
| Page number out of bounds | Configured overlay page exceeds total merged pages | Run `--dry-run` to see actual page count and adjust `page`. |
