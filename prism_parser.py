"""
Parser for GraphPad Prism .prism files (zip-based format, Prism 10+).

Extracts XY data tables from .prism archives and returns labeled pandas
DataFrames with hierarchical column headers (dataset title + replicate index).
"""

import json
import re
import zipfile
from dataclasses import dataclass
from io import StringIO
from pathlib import Path

import pandas as pd


@dataclass
class PrismSheet:
    """Container for a parsed Prism data sheet."""

    title: str
    df: pd.DataFrame
    xlabel: str = "X"
    ylabel: str = "Y"
    graph_title: str = ""


def _extract_graph_labels(zf: zipfile.ZipFile) -> dict[str, dict[str, str]]:
    """Extract axis labels from graph binary files.

    Returns a dict keyed by the graph sheet title (from sheet.json) with
    keys 'graph_title', 'xlabel', 'ylabel'.
    """
    doc = json.loads(zf.read("document.json"))
    graph_ids = doc["sheets"].get("graphs", [])
    labels: dict[str, dict[str, str]] = {}

    for gid in graph_ids:
        # Read the graph sheet title from its JSON metadata
        try:
            gsheet = json.loads(zf.read(f"graphs/{gid}/sheet.json"))
        except KeyError:
            continue
        sheet_title = gsheet.get("title", "").strip()

        bin_path = f"graphs/{gid}/data.bin"
        try:
            raw = zf.read(bin_path)
        except KeyError:
            continue

        # Labels in the binary are stored as ASCII strings terminated by '-'.
        # Filter to meaningful '-'-terminated strings (len > 1 after strip).
        raw_labels = re.findall(rb'[\x20-\x7e]{3,}-', raw)
        cleaned = []
        for m in raw_labels:
            s = m.decode().rstrip("-")
            # Skip noise strings (short hex-like fragments, padding)
            if len(s) > 1 and not all(c in "+Px @`" for c in s):
                cleaned.append(s)

        # The consistent pattern is:
        #   ... graph_title ... xlabel ... ylabel ... Y1Title ...
        # Find Y1Title and walk backwards.
        graph_title = xlabel = ylabel = ""
        for i, s in enumerate(cleaned):
            if s == "Y1Title":
                if i >= 1:
                    ylabel = cleaned[i - 1]
                if i >= 2:
                    xlabel = cleaned[i - 2]
                if i >= 3:
                    graph_title = cleaned[i - 3]
                break

        if sheet_title:
            labels[sheet_title] = {
                "graph_title": graph_title or sheet_title,
                "xlabel": xlabel or "X",
                "ylabel": ylabel or "Y",
            }

    return labels


def _match_graph_labels(
    sheet_title: str, graph_labels: dict[str, dict[str, str]]
) -> dict[str, str]:
    """Find the best matching graph labels for a data sheet title."""
    sheet_key = sheet_title.strip()
    # Direct match on graph sheet title (keyed from sheet.json)
    if sheet_key in graph_labels:
        return graph_labels[sheet_key]
    # Fuzzy: graph title may have trailing space or vice versa
    for gtitle, info in graph_labels.items():
        if gtitle.startswith(sheet_key) or sheet_key.startswith(gtitle):
            return info
    return {}


def parse_prism(prism_path: str | Path) -> dict[str, PrismSheet]:
    """Parse a .prism file and return a dict of {sheet_title: PrismSheet}.

    Each PrismSheet contains:
      - df: DataFrame with "X" column and MultiIndex Y columns
      - xlabel / ylabel: axis labels extracted from the graph binary
      - graph_title: full graph title (e.g. "CAMYEN-Giantin + GLP-1R")

    Parameters
    ----------
    prism_path : str or Path
        Path to the .prism archive.

    Returns
    -------
    dict[str, PrismSheet]
        Mapping from sheet title to its parsed data and metadata.
    """
    prism_path = Path(prism_path)
    results: dict[str, PrismSheet] = {}

    with zipfile.ZipFile(prism_path, "r") as zf:
        # Load document-level metadata
        doc = json.loads(zf.read("document.json"))

        # Extract axis labels from graph binaries
        graph_labels = _extract_graph_labels(zf)

        for sheet_id in doc["sheets"]["data"]:
            sheet_json = json.loads(
                zf.read(f"data/sheets/{sheet_id}/sheet.json")
            )
            sheet_title = sheet_json["title"]
            table = sheet_json["table"]
            table_uid = table["uid"]
            replicates_count = table["replicatesCount"]
            dataset_ids = table["dataSets"]

            # Read the raw CSV (no header row)
            csv_bytes = zf.read(f"data/tables/{table_uid}/data.csv")
            raw_df = pd.read_csv(StringIO(csv_bytes.decode("utf-8")), header=None)

            # First column is always X
            x_col = raw_df.iloc[:, 0]

            # Build labeled Y columns from dataset metadata, skipping
            # empty datasets (lastRow == -1, no title).
            col_tuples: list[tuple[str, int]] = []
            keep_cols: list[int] = []
            csv_col = 1  # current position in the raw CSV (0 = X)
            for ds_id in dataset_ids:
                ds_json = json.loads(zf.read(f"data/sets/{ds_id}.json"))
                ds_title = ds_json.get("title")
                is_empty = ds_title is None
                for rep in range(replicates_count):
                    if not is_empty:
                        col_tuples.append((ds_title, rep + 1))
                        keep_cols.append(csv_col)
                    csv_col += 1

            y_data = raw_df.iloc[:, keep_cols]
            y_data.columns = pd.MultiIndex.from_tuples(
                col_tuples, names=["dataset", "replicate"]
            )

            # Set X as the DataFrame index, keeping the MultiIndex on Y cols
            y_data.index = x_col.values
            y_data.index.name = "X"
            df = y_data.reset_index()

            # Match axis labels from graph metadata
            matched = _match_graph_labels(sheet_title, graph_labels)
            results[sheet_title] = PrismSheet(
                title=sheet_title,
                df=df,
                xlabel=matched.get("xlabel", "X"),
                ylabel=matched.get("ylabel", "Y"),
                graph_title=matched.get("graph_title", sheet_title),
            )

    return results


if __name__ == "__main__":
    import sys

    path = sys.argv[1] if len(sys.argv) > 1 else "Prism_Data.prism"
    sheets = parse_prism(path)
    for title, sheet in sheets.items():
        print(f"\n=== {title} ({sheet.df.shape[0]} rows x {sheet.df.shape[1]} cols) ===")
        print(f"  Graph title: {sheet.graph_title}")
        print(f"  X label: {sheet.xlabel}")
        print(f"  Y label: {sheet.ylabel}")
        print(sheet.df.head())
