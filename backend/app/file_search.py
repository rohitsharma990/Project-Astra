import os
from pathlib import Path

from . import ui

SEARCH_ROOTS = [Path("Files"), Path(".")]


def find_files(query: str) -> None:
    query = query.lower().strip()
    if not query:
        ui.error("Please provide a filename or search term.")
        return

    results = []
    for root in SEARCH_ROOTS:
        path = root.resolve()
        if not path.exists():
            continue

        for folder, _, filenames in os.walk(path):
            for filename in filenames:
                if query in filename.lower():
                    results.append(Path(folder) / filename)

    if not results:
        ui.error(f"No files found matching '{query}'.")
        return

    ui.section("File Search Results")
    ui.info(f"Found {len(results)} matching files.")
    for result in results[:25]:
        print(f"• {result}")

    if len(results) > 25:
        ui.info(f"Showing first 25 of {len(results)} matches.")
