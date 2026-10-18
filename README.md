# Green Card Packet Merger

Merges documents into two separate packets as recommended by USCIS:
1. **I-130 Petition for Alien Relative** (Sponsor / Petitioner)
2. **I-485 Adjustment of Status** (Applicant)

## Quick Start

1. Edit [config.yaml](./config.yaml) to arrange the files in your desired order for each packet.
2. Run the merge script:
   ```bash
   ./merge_pdfs.py
   # or
   python3 merge_pdfs.py
   ```

This generates:
- `i_130_petition_packet.pdf`
- `i_485_adjustment_of_status_packet.pdf`

## CLI Options

- **Dry Run (Preview order & page counts without writing files)**:
  ```bash
  python3 merge_pdfs.py --dry-run
  ```
- **Merge only one packet**:
  ```bash
  python3 merge_pdfs.py --packet i130_packet
  # or
  python3 merge_pdfs.py --packet i485_packet
  ```
- `-c, --config <file>`: Use a different YAML configuration file.
- `-d, --source-dir <dir>`: Override the source directory (defaults to `docs/`).
- `--no-bookmarks`: Disable outline/bookmark generation.
- `--auto-rotate`: Ensure all pages are vertical by rotating landscape pages 90 degrees (default: True).
- `--no-auto-rotate`: Disable automatic rotation of landscape pages.
