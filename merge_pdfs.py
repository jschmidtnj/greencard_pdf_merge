#!/usr/bin/env python3
"""
Merge PDF files in a specified order defined in a YAML configuration file.
Supports generating multiple packets and applying custom checkmark/text overlays via PyMuPDF.

Usage:
    python3 merge_pdfs.py
    python3 merge_pdfs.py --packet i130_packet
    python3 merge_pdfs.py --dry-run
"""

import sys
import os
import tempfile
from pathlib import Path

# --- Auto-switch to local virtualenv if dependencies are missing ---
def _ensure_dependencies():
    try:
        import yaml  # noqa: F401
        import pypdf  # noqa: F401
        import pymupdf  # noqa: F401
    except ImportError:
        script_dir = Path(__file__).resolve().parent
        venv_python = script_dir / ".venv" / "bin" / "python"
        if venv_python.exists() and sys.executable != str(venv_python):
            os.execv(str(venv_python), [str(venv_python)] + sys.argv)
        else:
            print("Error: Missing required packages 'pypdf', 'pyyaml', or 'pymupdf'.", file=sys.stderr)
            print("Please run: pip install -r requirements.txt", file=sys.stderr)
            sys.exit(1)

_ensure_dependencies()

import argparse
import yaml
import pymupdf
from pypdf import PdfReader, PdfWriter


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Merge PDF files in an order specified by a YAML configuration file."
    )
    parser.add_argument(
        "-c", "--config",
        type=Path,
        default=None,
        help="Path to YAML file defining the merge order (default: config.yaml)"
    )
    parser.add_argument(
        "-p", "--packet",
        type=str,
        default=None,
        help="Specific packet key to merge (default: merge all packets in config)"
    )
    parser.add_argument(
        "-d", "--source-dir",
        type=Path,
        default=None,
        help="Directory containing input PDFs (overrides 'source_dir' in YAML, defaults to 'docs' or '.')"
    )
    parser.add_argument(
        "-o", "--output",
        type=Path,
        default=None,
        help="Override output filename (applicable when merging a single packet)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate the merge without writing output files"
    )
    parser.add_argument(
        "--bookmarks",
        dest="bookmarks",
        action="store_true",
        default=None,
        help="Create bookmark/outline entries for each document in merged PDFs"
    )
    parser.add_argument(
        "--no-bookmarks",
        dest="bookmarks",
        action="store_false",
        help="Do not create bookmark/outline entries"
    )
    parser.add_argument(
        "--import-sub-bookmarks",
        action="store_true",
        default=False,
        help="Import internal sub-bookmarks from source PDFs (default: False)"
    )
    parser.add_argument(
        "--auto-rotate",
        dest="auto_rotate_portrait",
        action="store_true",
        default=None,
        help="Ensure all pages are vertical by rotating landscape pages 90 degrees (default: True)"
    )
    parser.add_argument(
        "--no-auto-rotate",
        dest="auto_rotate_portrait",
        action="store_false",
        help="Disable automatic rotation of landscape pages"
    )
    return parser.parse_args()


def normalize_file_entries(raw_files):
    file_entries = []
    for item in raw_files:
        if isinstance(item, str):
            file_entries.append({"file": item, "title": Path(item).stem})
        elif isinstance(item, dict):
            file_path = item.get("file") or item.get("path")
            if not file_path:
                raise ValueError(f"Dictionary item missing 'file' key: {item}")
            title = item.get("title", Path(file_path).stem)
            file_entries.append({"file": file_path, "title": title})
        else:
            raise ValueError(f"Unsupported file entry type in YAML: {item}")
    return file_entries


def normalize_text_overlays(raw_marks):
    if not raw_marks:
        return []
    normalized = []
    for m in raw_marks:
        if not isinstance(m, dict):
            continue
        page = m.get("page")
        if page is None:
            continue
        normalized.append({
            "page": int(page),
            "x": m.get("x"),
            "y": m.get("y"),
            "rect": m.get("rect"),
            "text": str(m.get("text", "X")),
            "fontsize": float(m.get("fontsize", 14)),
            "color": tuple(m.get("color", (0, 0, 0))),
            "overlay": bool(m.get("overlay", True)),
        })
    return normalized


def load_config(config_path: Path):
    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if data is None:
        raise ValueError(f"Configuration file '{config_path}' is empty.")

    global_bookmarks = data.get("bookmarks", True) if isinstance(data, dict) else True
    global_import_subs = data.get("import_sub_bookmarks", False) if isinstance(data, dict) else False
    global_auto_rotate = data.get("auto_rotate_portrait", data.get("auto_rotate", True)) if isinstance(data, dict) else True
    source_dir_name = data.get("source_dir", None) if isinstance(data, dict) else None

    packets = []

    if isinstance(data, dict) and "packets" in data:
        # Multi-packet format
        for pkt_key, pkt_val in data["packets"].items():
            if not isinstance(pkt_val, dict):
                raise ValueError(f"Packet '{pkt_key}' must be a dictionary configuration.")
            raw_files = pkt_val.get("files", [])
            output_name = pkt_val.get("output", f"{pkt_key}.pdf")
            description = pkt_val.get("description", pkt_key)
            bookmarks = pkt_val.get("bookmarks", global_bookmarks)
            import_subs = pkt_val.get("import_sub_bookmarks", global_import_subs)
            auto_rotate = pkt_val.get("auto_rotate_portrait", pkt_val.get("auto_rotate", global_auto_rotate))
            text_overlays = normalize_text_overlays(pkt_val.get("text_overlays") or pkt_val.get("checkmarks", []))
            packets.append({
                "key": pkt_key,
                "description": description,
                "output": output_name,
                "bookmarks": bookmarks,
                "import_sub_bookmarks": import_subs,
                "auto_rotate_portrait": auto_rotate,
                "files": normalize_file_entries(raw_files),
                "text_overlays": text_overlays,
            })
    elif isinstance(data, dict) and "files" in data:
        # Single-packet dictionary format
        raw_files = data.get("files", [])
        output_name = data.get("output", "merged.pdf")
        text_overlays = normalize_text_overlays(data.get("text_overlays") or data.get("checkmarks", []))
        packets.append({
            "key": "default",
            "description": "Merged Packet",
            "output": output_name,
            "bookmarks": global_bookmarks,
            "import_sub_bookmarks": global_import_subs,
            "auto_rotate_portrait": global_auto_rotate,
            "files": normalize_file_entries(raw_files),
            "text_overlays": text_overlays,
        })
    elif isinstance(data, list):
        # Single-packet list format
        packets.append({
            "key": "default",
            "description": "Merged Packet",
            "output": "merged.pdf",
            "bookmarks": True,
            "import_sub_bookmarks": False,
            "auto_rotate_portrait": True,
            "files": normalize_file_entries(data),
            "text_overlays": [],
        })
    else:
        raise ValueError("Invalid YAML format: Root must contain 'packets' or 'files'.")

    return {
        "source_dir": source_dir_name,
        "global_bookmarks": global_bookmarks,
        "global_import_subs": global_import_subs,
        "packets": packets,
    }


def format_size(bytes_num: int) -> str:
    for unit in ["B", "KB", "MB", "GB"]:
        if bytes_num < 1024.0:
            return f"{bytes_num:.1f} {unit}"
        bytes_num /= 1024.0
    return f"{bytes_num:.1f} TB"


def resolve_file_path(entry_path_str: str, base_dir: Path, source_dir: Path, file_lookup_cache: dict) -> Path | None:
    entry_path = Path(entry_path_str)

    # 1. Absolute path
    if entry_path.is_absolute() and entry_path.exists():
        return entry_path.resolve()

    # 2. Relative to source_dir
    candidate_source = (source_dir / entry_path).resolve()
    if candidate_source.exists():
        return candidate_source

    # 3. Relative to base_dir
    candidate_base = (base_dir / entry_path).resolve()
    if candidate_base.exists():
        return candidate_base

    # 4. Search recursively by filename in source_dir
    filename = entry_path.name
    matches = file_lookup_cache.get(filename)
    if matches:
        return matches[0]

    return None


def format_page_ranges(pages: list[int]) -> str:
    if not pages:
        return "none"
    ranges = []
    start = prev = pages[0]
    for p in pages[1:]:
        if p == prev + 1:
            prev = p
        else:
            ranges.append(f"{start}..{prev}" if start != prev else f"{start}")
            start = prev = p
    ranges.append(f"{start}..{prev}" if start != prev else f"{start}")
    if len(ranges) <= 8:
        return ", ".join(ranges)
    first_few = ", ".join(ranges[:6])
    return f"{first_few}, ... ({len(pages)} pages total)"


def post_process_merged_pdf(pdf_path: Path, overlays: list = None, auto_rotate_portrait: bool = True):
    """
    Post-processes the merged PDF:
    1. Applies custom text overlays (checkmarks, annotations).
    2. Auto-rotates any horizontal (landscape) pages 90 degrees clockwise so all pages
       are vertical (portrait) for clean, reliable printing.
    """
    if not overlays and not auto_rotate_portrait:
        return

    doc = pymupdf.open(str(pdf_path))
    modified = False
    total_pages = len(doc)

    # 1. Apply any text overlays
    if overlays:
        applied_count = 0
        for cm in overlays:
            page_num = cm["page"]
            if page_num < 1 or page_num > total_pages:
                print(f"   ⚠️  Warning: Page {page_num} out of bounds (1..{total_pages}). Skipping overlay.", file=sys.stderr)
                continue

            page = doc[page_num - 1]
            text = cm["text"]
            fontsize = cm["fontsize"]
            color = cm["color"]
            overlay = cm["overlay"]

            if cm.get("rect"):
                r = cm["rect"]
                rect = pymupdf.Rect(r[0], r[1], r[2], r[3])
                point = (rect.x0, rect.y1)
            elif cm.get("x") is not None and cm.get("y") is not None:
                point = (float(cm["x"]), float(cm["y"]))
            else:
                print(f"   ⚠️  Warning: Overlay on page {page_num} missing coordinates. Skipping.", file=sys.stderr)
                continue

            page.insert_text(
                point=point,
                text=text,
                fontsize=fontsize,
                color=color,
                overlay=overlay,
            )
            applied_count += 1
            print(f"   ✍️  Added overlay '{text}' on Page {page_num} at ({point[0]}, {point[1]})")

        if applied_count > 0:
            modified = True

    # 2. Auto-rotate horizontal/landscape pages so all pages are vertical (portrait)
    if auto_rotate_portrait:
        rotated_pages = []
        for i, page in enumerate(doc):
            if page.rect.width > page.rect.height:
                page.set_rotation((page.rotation + 90) % 360)
                rotated_pages.append(i + 1)
        if rotated_pages:
            modified = True
            print(f"   🔄 Rotated {len(rotated_pages)} horizontal page(s) to vertical (portrait): pages {format_page_ranges(rotated_pages)}")

    if modified:
        temp_fd, temp_path = tempfile.mkstemp(suffix=".pdf")
        os.close(temp_fd)
        doc.save(temp_path)
        doc.close()
        os.replace(temp_path, str(pdf_path))
    else:
        doc.close()


def main():
    args = parse_arguments()
    base_dir = Path(__file__).resolve().parent

    # Determine config file: CLI > config.yaml > order.yaml
    if args.config:
        config_path = args.config.resolve()
    elif (base_dir / "config.yaml").exists():
        config_path = base_dir / "config.yaml"
    elif (base_dir / "order.yaml").exists():
        config_path = base_dir / "order.yaml"
    else:
        config_path = base_dir / "config.yaml"

    print(f"\n📂 Loading configuration from: {config_path.name}")
    try:
        config = load_config(config_path)
    except Exception as e:
        print(f"❌ Configuration error: {e}", file=sys.stderr)
        sys.exit(1)

    # Determine source directory (CLI > YAML > 'docs' folder if present > base_dir)
    if args.source_dir:
        source_dir = (base_dir / args.source_dir).resolve()
    elif config["source_dir"]:
        source_dir = (base_dir / config["source_dir"]).resolve()
    elif (base_dir / "docs").is_dir():
        source_dir = (base_dir / "docs").resolve()
    else:
        source_dir = base_dir

    # Build cache of all PDFs in source_dir recursively
    file_lookup_cache = {}
    all_found_pdfs = set()

    for p in source_dir.rglob("*.pdf"):
        if p.is_file():
            resolved = p.resolve()
            all_found_pdfs.add(resolved)
            file_lookup_cache.setdefault(p.name, []).append(resolved)

    if source_dir != base_dir:
        for p in base_dir.glob("*.pdf"):
            if p.is_file():
                resolved = p.resolve()
                all_found_pdfs.add(resolved)
                file_lookup_cache.setdefault(p.name, []).append(resolved)

    # Filter packets if user specified --packet
    selected_packets = config["packets"]
    if args.packet:
        selected_packets = [p for p in selected_packets if p["key"] == args.packet]
        if not selected_packets:
            available = [p["key"] for p in config["packets"]]
            print(f"❌ Error: Packet '{args.packet}' not found. Available packets: {', '.join(available)}", file=sys.stderr)
            sys.exit(1)

    # Collect all output paths to exclude from unlisted scan
    configured_output_paths = set()
    for pkt in config["packets"]:
        configured_output_paths.add((base_dir / pkt["output"]).resolve())
    if args.output:
        configured_output_paths.add((base_dir / args.output).resolve())
    configured_output_paths.add((base_dir / "merged_packet.pdf").resolve())

    # Collect all resolved files across all packets for unlisted report
    all_packet_files_set = set()

    # Process each packet
    for pkt_idx, pkt in enumerate(selected_packets, start=1):
        if args.output and len(selected_packets) == 1:
            output_path = (base_dir / args.output).resolve()
        else:
            output_path = (base_dir / pkt["output"]).resolve()

        add_bookmarks = pkt["bookmarks"] if args.bookmarks is None else args.bookmarks
        import_sub_bookmarks = pkt["import_sub_bookmarks"] or args.import_sub_bookmarks
        auto_rotate = pkt["auto_rotate_portrait"] if args.auto_rotate_portrait is None else args.auto_rotate_portrait

        files_to_merge = []
        missing_files = []

        for entry in pkt["files"]:
            resolved_path = resolve_file_path(entry["file"], base_dir, source_dir, file_lookup_cache)
            if resolved_path is None:
                missing_files.append((entry["file"], source_dir / entry["file"]))
            else:
                all_packet_files_set.add(resolved_path)
                try:
                    rel_display = resolved_path.relative_to(source_dir)
                except ValueError:
                    rel_display = resolved_path.name

                files_to_merge.append({
                    "path": resolved_path,
                    "display_name": str(rel_display),
                    "title": entry["title"],
                })

        if missing_files:
            print(f"\n❌ Error in packet '{pkt['key']}': Missing files:", file=sys.stderr)
            for rel_name, looked_at in missing_files:
                print(f"   • {rel_name} (looked in: {looked_at.parent})", file=sys.stderr)
            sys.exit(1)

        # Print Packet Header
        print(f"\n{'=' * 84}")
        print(f"📦 PACKET {pkt_idx}/{len(selected_packets)}: {pkt['description']}")
        print(f"🎯 Output: {output_path.name}")
        print(f"{'=' * 84}")
        print(f"{'#':<3} {'Document Name':<48} {'Pages':<8} {'Range'}")
        print("-" * 84)

        writer = PdfWriter()
        total_pages = 0
        pkt_landscape_pages = 0
        current_page = 1

        for idx, item in enumerate(files_to_merge, start=1):
            try:
                reader = PdfReader(str(item["path"]))
                page_count = len(reader.pages)
                for p in reader.pages:
                    rot = p.rotation or 0
                    w = float(p.mediabox.width)
                    h = float(p.mediabox.height)
                    if rot in (90, 270):
                        w, h = h, w
                    if w > h:
                        pkt_landscape_pages += 1
            except Exception as e:
                print(f"\n❌ Failed to read PDF '{item['display_name']}': {e}", file=sys.stderr)
                sys.exit(1)

            start_page = current_page
            end_page = current_page + page_count - 1
            page_range_str = f"{start_page}..{end_page}" if page_count > 1 else f"{start_page}"

            disp = item["display_name"]
            if len(disp) > 48:
                disp = disp[:45] + "..."
            print(f"{idx:<3} {disp:<48} {page_count:<8} {page_range_str}")

            if not args.dry_run:
                bookmark_title = item["title"] if add_bookmarks else None
                writer.append(
                    str(item["path"]),
                    outline_item=bookmark_title,
                    import_outline=import_sub_bookmarks
                )

            total_pages += page_count
            current_page = end_page + 1

        print("-" * 84)
        print(f"Documents: {len(files_to_merge)} | Total pages: {total_pages}")
        print(f"Bookmarks: {'Enabled (clean document-level only)' if add_bookmarks else 'Disabled'}")
        if auto_rotate:
            print(f"Orientation: All vertical (auto-rotating {pkt_landscape_pages} horizontal pages to portrait)")
        else:
            print(f"Orientation: Preserving original ({pkt_landscape_pages} horizontal pages)")

        if pkt.get("text_overlays"):
            print(f"Text overlays configured: {len(pkt['text_overlays'])}")
            for cm in pkt["text_overlays"]:
                pos = f"rect={cm['rect']}" if cm.get("rect") else f"({cm.get('x')}, {cm.get('y')})"
                print(f"   • Page {cm['page']}: '{cm['text']}' at {pos}")

        if not args.dry_run:
            print(f"💾 Writing packet to: {output_path.name}...")
            try:
                with open(output_path, "wb") as out_f:
                    writer.write(out_f)
            except Exception as e:
                print(f"\n❌ Error writing output file: {e}", file=sys.stderr)
                sys.exit(1)

            # Apply overlays and auto-rotate horizontal pages to vertical for clean printing
            post_process_merged_pdf(
                output_path,
                overlays=pkt.get("text_overlays"),
                auto_rotate_portrait=auto_rotate
            )

            file_size = output_path.stat().st_size
            print(f"✅ Success! Created '{output_path.name}' ({format_size(file_size)}, {total_pages} pages)")
            print(f"📍 Full path: {output_path}")

    # Check for unlisted PDFs in source_dir (outside of all packets)
    unlisted_pdfs = all_found_pdfs - all_packet_files_set - configured_output_paths
    if unlisted_pdfs:
        print(f"\n⚠️  Notice: {len(unlisted_pdfs)} PDF(s) in '{source_dir.name}/' are not included in any packet:")
        for p in sorted(unlisted_pdfs):
            try:
                rel = p.relative_to(source_dir)
            except ValueError:
                rel = p.name
            print(f"   - {rel}")

    if args.dry_run:
        print("\n🔍 Dry-run complete. No output files were created.\n")
    else:
        print("\n🎉 All packets merged successfully!\n")


if __name__ == "__main__":
    main()
