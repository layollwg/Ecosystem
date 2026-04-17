from __future__ import annotations

import random
from dataclasses import dataclass
from typing import ClassVar, Dict, Tuple


@dataclass
class Genome:
    """
    Genetic blueprint for an organism.

    Each field is an independently heritable trait that is passed to offspring
    with optional Gaussian mutation.  All values are clamped to ``_BOUNDS``.
    """

    # ── Instance fields (dataclass fields) ────────────────────────────────────
    size: float        # Body size (0.5–5.0): initial energy, max energy
    speed: float       # Move speed (0.5–3.0): movement, escape velocity
    vision: int        # Sight radius (1–10): grid cells the organism can sense
    metabolism: float  # Metabolic rate (0.5–2.0): base energy consumption

    # ── Class-level constant (NOT a dataclass field) ──────────────────────────
    _BOUNDS: ClassVar[Dict[str, Tuple[float, float]]] = {
        "size":       (0.5, 5.0),
        "speed":      (0.5, 3.0),
        "vision":     (1.0, 10.0),
        "metabolism": (0.5, 2.0),
    }

    # ── Evolutionary operators ─────────────────────────────────────────────────

    def mutate(self, mutation_rate: float = 0.05) -> Genome:
        """Return a new Genome with small Gaussian perturbations on each gene.

        The standard deviation scales with the current value so that all traits
        mutate proportionally (matching real biology where larger deviations
        occur in already-extreme phenotypes).

        Args:
            mutation_rate: Fraction of the current value used as std-dev.

        Returns:
            A new Genome with values clamped to ``_BOUNDS``.
        """
        def _apply(value: float, lo: float, hi: float) -> float:
            return max(lo, min(hi, random.gauss(value, abs(value) * mutation_rate)))

        b = Genome._BOUNDS
        return Genome(
            size=_apply(self.size, *b["size"]),
            speed=_apply(self.speed, *b["speed"]),
            vision=int(_apply(float(self.vision), *b["vision"])),
            metabolism=_apply(self.metabolism, *b["metabolism"]),
        )

    def crossover(self, other: Genome, mutation_rate: float = 0.05) -> Genome:
        """Produce an offspring genome via random per-gene inheritance + mutation.

        Each gene is independently chosen from either parent with equal
        probability, then the combined genome is mutated.

        Args:
            other: The second parent's genome.
            mutation_rate: Mutation rate applied after crossover.

        Returns:
            A new Genome resulting from crossover followed by mutation.
        """
        return Genome(
            size=random.choice([self.size, other.size]),
            speed=random.choice([self.speed, other.speed]),
            vision=random.choice([self.vision, other.vision]),
            metabolism=random.choice([self.metabolism, other.metabolism]),
        ).mutate(mutation_rate)

    # ── Visualisation helpers ─────────────────────────────────────────────────

    def get_phenotype_color(self) -> Tuple[int, int, int]:
        """Map gene values to an RGB colour so evolutionary change is visible.

        Channel mapping:
        - Red   → speed  (higher speed = more red)
        - Green → size   (larger body  = more green)
        - Blue  → vision (wider vision = more blue)

        Returns:
            ``(R, G, B)`` tuple, each channel in ``[0, 255]``.
        """
        b = Genome._BOUNDS

        def _norm(val: float, lo: float, hi: float) -> float:
            return (val - lo) / (hi - lo) if hi != lo else 0.0

        r = int(255 * _norm(self.speed,            *b["speed"]))
        g = int(255 * _norm(self.size,             *b["size"]))
        bv = int(255 * _norm(float(self.vision),   *b["vision"]))
        return (r, g, bv)

    def get_hex_color(self) -> str:
        """Return the phenotype colour as ``#rrggbb`` hex (for Tkinter)."""
        r, g, b = self.get_phenotype_color()
        return f"#{r:02x}{g:02x}{b:02x}"

    def __repr__(self) -> str:
        return (
            f"Genome(size={self.size:.2f}, speed={self.speed:.2f}, "
            f"vision={self.vision}, metabolism={self.metabolism:.2f})"
        )
