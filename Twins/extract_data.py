"""
Build-order step 1: data extraction tool.

Walks data/raw_sources/, pulls text out of whatever's in there, and writes
one clean .txt file per source into data/clean/ — ready for ingest_cli.py
to chunk, embed, and extract facts/opinions from.

Supports .txt, .md, .pdf, .docx out of the box, plus a basic WhatsApp
chat-export parser (name a WhatsApp export file "*_whatsapp.txt" to use
it — adapt parse_whatsapp_export() for other chat export formats).

Run from the backend/ folder:
    python extract_data.py
"""

import os
import re

from document_extract_standalone import extract_text_from_path

RAW_DIR = "../data/raw_sources"
CLEAN_DIR = "../data/clean"


def parse_whatsapp_export(path: str, your_name: str) -> str:
    """Keeps only messages sent by `your_name`, strips timestamps/system
    lines. WhatsApp's exported line format looks like:
    12/3/24, 9:41 PM - Alex: message text here"""
    pattern = re.compile(r"^\d{1,2}/\d{1,2}/\d{2,4}, \d{1,2}:\d{2}.*? - (.*?): (.*)$")
    lines_out = []
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            m = pattern.match(line.strip())
            if m and m.group(1).strip().lower() == your_name.lower():
                lines_out.append(m.group(2))
    return "\n".join(lines_out)


def main():
    os.makedirs(CLEAN_DIR, exist_ok=True)
    if not os.path.isdir(RAW_DIR) or not os.listdir(RAW_DIR):
        print(f"Put your raw source files in {RAW_DIR}/ first, then re-run this.")
        return

    persona_name = os.getenv("PERSONA_NAME", "Me")
    wrote_any = False

    for fname in sorted(os.listdir(RAW_DIR)):
        path = os.path.join(RAW_DIR, fname)
        if not os.path.isfile(path):
            continue

        try:
            if fname.lower().endswith("_whatsapp.txt"):
                text = parse_whatsapp_export(path, your_name=persona_name)
            else:
                text = extract_text_from_path(path)
        except Exception as e:
            print(f"Skipping {fname}: {e}")
            continue

        text = text.strip()
        if not text:
            print(f"No text extracted from {fname}, skipping.")
            continue

        out_name = os.path.splitext(fname)[0].replace("_whatsapp", "") + ".txt"
        out_path = os.path.join(CLEAN_DIR, out_name)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"Wrote {out_path} ({len(text)} chars)")
        wrote_any = True

    if wrote_any:
        print(f"\nDone. Clean text is in {CLEAN_DIR}/ — next run ingest_cli.py.")
    else:
        print("Nothing was extracted — check the files in raw_sources/.")


if __name__ == "__main__":
    main()
