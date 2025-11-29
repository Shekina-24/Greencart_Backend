from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Iterable, Optional

from app.config import settings


def _save_json(items: Iterable[dict], destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8") as f:
        json.dump(list(items), f, ensure_ascii=False, indent=2)


def import_producers(csv_path: Path, output: Optional[Path] = None) -> Path:
    """
    Import a CSV of local producers and export a normalized JSON.

    Expected columns (best effort): name, region, city, latitude, longitude, labels, url.
    """
    if output is None:
        output = Path(settings.reports_storage_dir) / "public_producers.json"

    with csv_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        records: list[dict] = []
        for row in reader:
            records.append(
                {
                    "name": row.get("name") or row.get("nom") or "",
                    "region": row.get("region") or row.get("reg") or "",
                    "city": row.get("city") or row.get("ville") or "",
                    "latitude": _to_float(row.get("latitude") or row.get("lat")),
                    "longitude": _to_float(row.get("longitude") or row.get("lon") or row.get("lng")),
                    "labels": _split(row.get("labels") or row.get("label") or ""),
                    "url": row.get("url") or row.get("website") or row.get("site") or "",
                }
            )

    _save_json(records, output)
    return output


def import_consumption(csv_path: Path, output: Optional[Path] = None) -> Path:
    """
    Import consumption habits (large matrix style) and export JSON rows.
    Keeps POPULATION, NOMEN and all other columns as-is (numeric if possible).
    """
    if output is None:
        output = Path(settings.reports_storage_dir) / "consumption_stats.json"

    with csv_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        records: list[dict] = []
        for row in reader:
            normalized: dict[str, Any] = {}
            for key, value in row.items():
                if key is None:
                    continue
                if key.lower() in {"population", "nomen"}:
                    normalized[key.lower()] = value
                else:
                    numeric = _to_float(value)
                    normalized[key] = numeric if numeric is not None else value
            records.append(normalized)

    _save_json(records, output)
    return output


def import_waste(csv_path: Path, output: Optional[Path] = None) -> Path:
    """
    Import waste/anti-gaspillage actors and export a normalized JSON.

    Expected columns: name, region, city, category, url/contact.
    """
    if output is None:
        output = Path(settings.reports_storage_dir) / "waste_stats.json"

    with csv_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        records: list[dict] = []
        for row in reader:
            records.append(
                {
                    "name": row.get("name") or row.get("nom") or "",
                    "region": row.get("region") or "",
                    "city": row.get("city") or row.get("ville") or "",
                    "category": row.get("category") or row.get("categorie") or "",
                    "url": row.get("url") or row.get("website") or "",
                    "contact": row.get("contact") or row.get("email") or "",
                }
            )

    _save_json(records, output)
    return output


def _to_float(value: Optional[str]) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _split(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description="Import public datasets into normalized JSON caches.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_prod = subparsers.add_parser("producers", help="Import producteurs locaux CSV -> JSON")
    p_prod.add_argument("csv", type=Path, help="Path to CSV file of producers")
    p_prod.add_argument("--output", type=Path, help="Destination JSON path (default: generated_reports/public_producers.json)")

    p_cons = subparsers.add_parser("consumption", help="Import habitudes de consommation CSV -> JSON")
    p_cons.add_argument("csv", type=Path, help="Path to CSV file")
    p_cons.add_argument("--output", type=Path, help="Destination JSON path (default: generated_reports/consumption_stats.json)")

    p_waste = subparsers.add_parser("waste", help="Import gaspillage/acteurs CSV -> JSON")
    p_waste.add_argument("csv", type=Path, help="Path to CSV file")
    p_waste.add_argument("--output", type=Path, help="Destination JSON path (default: generated_reports/waste_stats.json)")

    args = parser.parse_args()

    if args.command == "producers":
        out = import_producers(args.csv, args.output)
    elif args.command == "consumption":
        out = import_consumption(args.csv, args.output)
    elif args.command == "waste":
        out = import_waste(args.csv, args.output)
    else:
        parser.error("Unknown command")
        return

    print(f"Imported {args.command} data -> {out}")


if __name__ == "__main__":
    main()
