from __future__ import annotations

import random
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, List, Optional, Tuple, Type, TypeVar

if TYPE_CHECKING:
    from ecosystem import Ecosystem

import config
from genetics import Genome

Position = Tuple[int, int]

# Display symbols (constant — not part of the configurable preset).
PLANT_SYMBOL = "P"
HERBIVORE_SYMBOL = "H"
CARNIVORE_SYMBOL = "C"

TAnimal = TypeVar("TAnimal", bound="Animal")
TOrganism = TypeVar("TOrganism", bound="Organism")


class Organism(ABC):
    """Base organism with position tracking."""

    def __init__(self, x: int, y: int, symbol: str, max_age: int) -> None:
        self.x = x
        self.y = y
        self.symbol = symbol
        self.alive = True
        self.age = 0
        self.max_age = max_age

    def age_one_tick(self, ecosystem: Ecosystem) -> None:
        self.age += 1
        if self.age >= self.max_age:
            ecosystem.queue_remove_organism(self)

    @abstractmethod
    def update(self, ecosystem: Ecosystem) -> None:
        """Perform the organism's action for the current tick."""


class Plant(Organism):
    """Stationary organism that can spread to adjacent empty cells."""

    def __init__(self, x: int, y: int) -> None:
        super().__init__(x, y, PLANT_SYMBOL, config.get("PLANT_MAX_AGE"))

    def update(self, ecosystem: Ecosystem) -> None:
        self.age_one_tick(ecosystem)
        if not self.alive:
            return

        if random.random() >= config.get_plant_reproduction_chance(ecosystem.tick_count):
            return

        empty_cells = ecosystem.get_adjacent_empty_cells(self.x, self.y)
        if not empty_cells:
            return

        new_x, new_y = random.choice(empty_cells)
        ecosystem.queue_add_organism(Plant(new_x, new_y))


class Animal(Organism, ABC):
    """Abstract organism that expends energy while acting.

    Energy and lifespan are driven by the organism's ``Genome``.  All animals
    carry a genome; default genomes are created automatically when none is
    supplied so that the class remains backwards-compatible with callers that
    do not use the genetics system.
    """

    def __init__(
        self,
        x: int,
        y: int,
        symbol: str,
        energy: float,
        max_age: int,
        genome: Optional[Genome] = None,
    ) -> None:
        super().__init__(x, y, symbol, max_age)
        self.genome: Genome = genome if genome is not None else Genome(1.0, 1.0, 1, 1.0)
        self.energy: float = energy

    # ── Energy model ──────────────────────────────────────────────────────────

    def calculate_energy_cost(self) -> float:
        """Per-tick energy expenditure derived from the organism's genome.

        Cost model (non-linear to prevent unconstrained extremes):
          base    = metabolism × size              (maintenance cost)
          speed   = 0.5 × speed²                  (quadratic — air resistance analogy)
          vision  = 0.2 × vision^1.5              (neural maintenance)
          total   = max(1.0, base + speed + vision)

        The floor of 1.0 prevents degenerate zero-cost organisms.

        Returns:
            Energy consumed this tick.
        """
        g = self.genome
        base_cost   = g.metabolism * g.size
        speed_cost  = 0.5 * (g.speed ** 2)
        vision_cost = 0.2 * (g.vision ** 1.5)
        return max(1.0, base_cost + speed_cost + vision_cost)

    def update(self, ecosystem: Ecosystem) -> None:  # type: ignore[override]
        self.energy -= self.calculate_energy_cost()
        if self.energy <= 0:
            ecosystem.queue_remove_organism(self)
            return

        self.age_one_tick(ecosystem)
        if not self.alive:
            return

    # ── Movement ──────────────────────────────────────────────────────────────

    def move(self, ecosystem: Ecosystem) -> bool:
        empty_cells = ecosystem.get_adjacent_empty_cells(self.x, self.y)
        if not empty_cells:
            return False

        new_x, new_y = random.choice(empty_cells)
        ecosystem.move_organism(self, new_x, new_y)
        return True

    # ── Shared perception helper ──────────────────────────────────────────────

    def _get_organisms_in_vision(
        self,
        ecosystem: Ecosystem,
        organism_type: Type[TOrganism],
    ) -> List[TOrganism]:
        """Return all organisms of *organism_type* within this animal's vision range.

        Vision range is taken from ``self.genome.vision`` (in grid cells).
        The centre cell (the animal itself) is excluded.

        Args:
            ecosystem: The active ecosystem.
            organism_type: Class to filter by.

        Returns:
            List of matching organisms in the visible neighbourhood.
        """
        results: List[TOrganism] = []
        vr = self.genome.vision
        for dx in range(-vr, vr + 1):
            for dy in range(-vr, vr + 1):
                if dx == 0 and dy == 0:
                    continue
                nx, ny = self.x + dx, self.y + dy
                if 0 <= nx < ecosystem.grid_size and 0 <= ny < ecosystem.grid_size:
                    occupant = ecosystem.get_organism_at(nx, ny)
                    if isinstance(occupant, organism_type):
                        results.append(occupant)
        return results


class Herbivore(Animal):
    """Animal that eats plants for energy.

    Energy, lifespan, search radius and reproduction threshold are all derived
    from the organism's Genome, enabling natural selection to favour well-adapted
    genotypes over many generations.
    """

    # ── Genome-scale energy constants (multiplied by genome.size) ─────────────
    _MAX_ENERGY_FACTOR: float      = 100.0   # max energy = factor × size
    _SATIATION_FRACTION: float     = 0.9     # eat up to 90 % of max energy
    _REPRODUCE_FRACTION: float     = 0.8     # reproduce at 80 % of max energy

    def __init__(
        self,
        x: int,
        y: int,
        energy: Optional[float] = None,
        genome: Optional[Genome] = None,
    ) -> None:
        resolved_genome = genome if genome is not None else Genome(
            size=1.0, speed=1.0, vision=1, metabolism=1.0
        )
        if energy is None:
            energy = self._MAX_ENERGY_FACTOR * 0.5 * resolved_genome.size

        # Lifespan: large, slow-metabolising organisms live longer.
        max_age = max(20, int(100 * resolved_genome.size / resolved_genome.metabolism))

        super().__init__(x, y, HERBIVORE_SYMBOL, energy, max_age, resolved_genome)

    def update(self, ecosystem: Ecosystem) -> None:
        super().update(ecosystem)
        if not self.alive:
            return

        # Flee from immediately adjacent carnivores first.
        if self._flee(ecosystem):
            return

        plant = self._eat(ecosystem)
        if plant:
            ecosystem.queue_remove_organism(plant)
            # Energy gain is reduced for faster organisms (trade-off: speed vs. feeding).
            energy_gain = (
                config.get("HERBIVORE_ENERGY_GAIN")
                / max(0.5, self.genome.speed)
            )
            self.energy += energy_gain
            ecosystem.move_organism(self, plant.x, plant.y)
        else:
            if not self._try_reproduce(ecosystem):
                self.move(ecosystem)

    def _flee(self, ecosystem: Ecosystem) -> bool:
        """Move away from adjacent carnivores.  Returns True if the herbivore fled."""
        carnivores = ecosystem.get_adjacent_organisms(self.x, self.y, Carnivore)
        if not carnivores:
            return False

        empty_cells = ecosystem.get_adjacent_empty_cells(self.x, self.y)
        if not empty_cells:
            return False

        avg_cx = sum(c.x for c in carnivores) / len(carnivores)
        avg_cy = sum(c.y for c in carnivores) / len(carnivores)
        best = max(
            empty_cells,
            key=lambda cell: (cell[0] - avg_cx) ** 2 + (cell[1] - avg_cy) ** 2,
        )
        ecosystem.move_organism(self, best[0], best[1])
        return True

    def _eat(self, ecosystem: Ecosystem) -> Optional[Plant]:
        # Satiation: skip eating when energy is already near the genome-scaled cap.
        satiation = self._MAX_ENERGY_FACTOR * self._SATIATION_FRACTION * self.genome.size
        if self.energy >= satiation:
            return None
        # Search within vision radius.
        plants = self._get_organisms_in_vision(ecosystem, Plant)
        return random.choice(plants) if plants else None

    def _try_reproduce(self, ecosystem: Ecosystem) -> bool:
        # Reproduction threshold is genome-scaled (body-mass-dependent investment).
        reproduce_threshold = (
            self._MAX_ENERGY_FACTOR * self._REPRODUCE_FRACTION * self.genome.size
        )
        if self.energy <= reproduce_threshold:
            return False

        # Density-dependent suppression.
        nearby = ecosystem.get_adjacent_organisms(self.x, self.y, Herbivore)
        if len(nearby) >= config.get("HERBIVORE_CROWDING_THRESHOLD"):
            return False
        if random.random() >= config.get("HERBIVORE_REPRODUCTION_CHANCE"):
            return False

        empty_cells = ecosystem.get_adjacent_empty_cells(self.x, self.y)
        if not empty_cells:
            return False

        child_x, child_y = random.choice(empty_cells)

        # Parent donates 40 % of current energy to offspring.
        child_energy = self.energy * 0.4
        self.energy -= child_energy

        # Genome is inherited with mutation — the core of natural selection.
        child_genome = self.genome.mutate(mutation_rate=0.05)
        child = Herbivore(child_x, child_y, energy=child_energy, genome=child_genome)
        ecosystem.queue_add_organism(child)
        return True


class Carnivore(Animal):
    """Animal that hunts herbivores for energy.

    Hunting range, success rate, and reproductive capacity all depend on the
    organism's Genome, creating selective pressure for speed, vision, and size.
    """

    # ── Genome-scale energy constants ─────────────────────────────────────────
    _MAX_ENERGY_FACTOR: float      = 150.0   # max energy = factor × size
    _SATIATION_FRACTION: float     = 0.9     # hunt up to 90 % of max energy
    _REPRODUCE_FRACTION: float     = 0.8     # reproduce at 80 % of max energy

    def __init__(
        self,
        x: int,
        y: int,
        energy: Optional[float] = None,
        genome: Optional[Genome] = None,
    ) -> None:
        resolved_genome = genome if genome is not None else Genome(
            size=1.2, speed=1.3, vision=2, metabolism=1.1
        )
        if energy is None:
            energy = self._MAX_ENERGY_FACTOR * 0.5 * resolved_genome.size

        max_age = max(20, int(100 * resolved_genome.size / resolved_genome.metabolism))

        super().__init__(x, y, CARNIVORE_SYMBOL, energy, max_age, resolved_genome)

    def update(self, ecosystem: Ecosystem) -> None:
        super().update(ecosystem)
        if not self.alive:
            return

        herbivore = self._hunt(ecosystem)
        if herbivore:
            ecosystem.queue_remove_organism(herbivore)
            # Energy gain scales with prey size — larger prey is more rewarding.
            energy_gain = config.get("CARNIVORE_ENERGY_GAIN") * (
                1.0 + herbivore.genome.size
            )
            self.energy += energy_gain
            ecosystem.move_organism(self, herbivore.x, herbivore.y)
        else:
            if not self._try_reproduce(ecosystem):
                self.move(ecosystem)

    def _hunt(self, ecosystem: Ecosystem) -> Optional[Herbivore]:
        # Satiation: skip hunting when energy is already near the genome-scaled cap.
        satiation = self._MAX_ENERGY_FACTOR * self._SATIATION_FRACTION * self.genome.size
        if self.energy >= satiation:
            return None

        herbivores = self._get_organisms_in_vision(ecosystem, Herbivore)
        if not herbivores:
            return None

        # Hunt success rate is speed-dependent (faster predators catch prey more reliably).
        success_rate = min(0.9, 0.5 + (self.genome.speed / 3.0) * 0.4)
        if random.random() < success_rate:
            return random.choice(herbivores)
        return None

    def _try_reproduce(self, ecosystem: Ecosystem) -> bool:
        reproduce_threshold = (
            self._MAX_ENERGY_FACTOR * self._REPRODUCE_FRACTION * self.genome.size
        )
        if self.energy <= reproduce_threshold:
            return False

        # Density-dependent suppression.
        nearby = ecosystem.get_adjacent_organisms(self.x, self.y, Carnivore)
        if len(nearby) >= config.get("CARNIVORE_CROWDING_THRESHOLD"):
            return False
        if random.random() >= config.get("CARNIVORE_REPRODUCTION_CHANCE"):
            return False

        empty_cells = ecosystem.get_adjacent_empty_cells(self.x, self.y)
        if not empty_cells:
            return False

        child_x, child_y = random.choice(empty_cells)

        child_energy = self.energy * 0.4
        self.energy -= child_energy

        child_genome = self.genome.mutate(mutation_rate=0.05)
        child = Carnivore(child_x, child_y, energy=child_energy, genome=child_genome)
        ecosystem.queue_add_organism(child)
        return True
