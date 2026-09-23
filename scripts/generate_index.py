#!/usr/bin/env python3
"""
Script to scan the FAQ directory and generate faq_index.json.
Can be executed locally or in a CI/CD pipeline (e.g. GitHub Actions).
"""

import os
import re
import json
import hashlib
from datetime import datetime, timezone

FAQ_DIR = os.environ.get("FAQ_DIR", "FAQ")
OUTPUT_FILE = os.environ.get("OUTPUT_INDEX_FILE", "faq_index.json")

# Directories to exclude from category scanning
EXCLUDED_DIRS = {"images", ".git", "__pycache__"}


def extract_title_and_preview(file_path: str):
    """
    Extracts the title (first # Heading or file name) and a short text preview.
    """
    title = None
    preview = ""
    lines = []

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return os.path.splitext(os.path.basename(file_path))[0], ""

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        # Extract title from the first H1
        if title is None and stripped.startswith("# "):
            title = stripped.lstrip("# ").strip()
            continue
        # If we have title, pick the first descriptive line for preview
        if title and not preview:
            # Strip markdown links and formatting for preview
            clean = re.sub(r"!\[.*?\]\(.*?\)", "", stripped)  # remove images
            clean = re.sub(r"\[(.*?)\]\(.*?\)", r"\1", clean)  # links to text
            clean = re.sub(r"[*_`#>-]", "", clean).strip()
            if clean:
                preview = clean[:160] + ("..." if len(clean) > 160 else "")

    if not title:
        # Fallback to filename without extension
        title = os.path.splitext(os.path.basename(file_path))[0]

    return title, preview


def generate_short_id(val: str) -> str:
    """Generates an 8-character hex hash from a relative path."""
    return hashlib.md5(val.encode("utf-8")).hexdigest()[:8]


def build_index():
    if not os.path.isdir(FAQ_DIR):
        print(f"Directory '{FAQ_DIR}' not found. Creating empty index.")
        return {
            "version": 1,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "categories": [],
            "root_files": [],
        }

    categories = []
    root_files = []

    # 1. Process root markdown files
    for entry in sorted(os.listdir(FAQ_DIR)):
        full_path = os.path.join(FAQ_DIR, entry)
        if os.path.isfile(full_path) and entry.lower().endswith(".md"):
            rel_path = os.path.join(FAQ_DIR, entry).replace("\\", "/")
            title, preview = extract_title_and_preview(full_path)
            file_id = generate_short_id(rel_path)
            root_files.append({
                "id": file_id,
                "title": title,
                "filename": entry,
                "path": rel_path,
                "preview": preview,
            })

    # 2. Process subdirectories (Categories)
    for entry in sorted(os.listdir(FAQ_DIR)):
        cat_path = os.path.join(FAQ_DIR, entry)
        if os.path.isdir(cat_path) and entry.lower() not in EXCLUDED_DIRS:
            cat_id = generate_short_id(f"cat_{entry}")
            cat_files = []

            for f_entry in sorted(os.listdir(cat_path)):
                f_full = os.path.join(cat_path, f_entry)
                if os.path.isfile(f_full) and f_entry.lower().endswith(".md"):
                    rel_path = os.path.join(cat_path, f_entry).replace("\\", "/")
                    title, preview = extract_title_and_preview(f_full)
                    file_id = generate_short_id(rel_path)
                    cat_files.append({
                        "id": file_id,
                        "title": title,
                        "filename": f_entry,
                        "path": rel_path,
                        "preview": preview,
                    })

            categories.append({
                "id": cat_id,
                "name": entry,
                "path": os.path.join(FAQ_DIR, entry).replace("\\", "/"),
                "files": cat_files,
            })

    data = {
        "version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "categories": categories,
        "root_files": root_files,
    }

    return data


def main():
    print(f"Generating FAQ index from '{FAQ_DIR}'...")
    index_data = build_index()

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(index_data, f, indent=2, ensure_ascii=False)

    total_cats = len(index_data["categories"])
    total_cat_files = sum(len(c["files"]) for c in index_data["categories"])
    total_root = len(index_data["root_files"])
    print(f"Successfully generated {OUTPUT_FILE} with {total_cats} categories, {total_cat_files + total_root} total FAQs.")


if __name__ == "__main__":
    main()
