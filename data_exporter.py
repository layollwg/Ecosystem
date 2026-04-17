from __future__ import annotations

import csv
import datetime
import json
from typing import Any, Dict, List


def export_to_csv(history: Dict[str, List[int]], filename: str) -> None:
    """Write tick-by-tick population counts to a CSV file.

    Columns: Tick, Plants, Herbivores, Carnivores
    """
    plants = history.get("plants", [])
    herbivores = history.get("herbivores", [])
    carnivores = history.get("carnivores", [])
    with open(filename, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["Tick", "Plants", "Herbivores", "Carnivores"])
        length = min(len(plants), len(herbivores), len(carnivores))
        for i in range(length):
            writer.writerow([i + 1, plants[i], herbivores[i], carnivores[i]])


def export_to_json(
    history: Dict[str, List[int]],
    metadata: Dict[str, Any],
    filename: str,
) -> None:
    """Write history and simulation metadata to a JSON file."""
    plants = history.get("plants", [])
    herbivores = history.get("herbivores", [])
    carnivores = history.get("carnivores", [])
    length = min(len(plants), len(herbivores), len(carnivores))
    data: Dict[str, Any] = {
        "metadata": {
            **metadata,
            "export_time": datetime.datetime.now().isoformat(),
            "total_ticks": length,
        },
        "history": [
            {
                "tick": i + 1,
                "plants": plants[i],
                "herbivores": herbivores[i],
                "carnivores": carnivores[i],
            }
            for i in range(length)
        ],
    }
    with open(filename, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
