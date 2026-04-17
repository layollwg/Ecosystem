from __future__ import annotations

import random
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, List, Optional, Tuple, Type, TypeVar

if TYPE_CHECKING:
    from ecosystem import Ecosystem


Position = Tuple[int, int]

# Simulation constants
PLANT_SYMBOL = "P"
PLANT_REPRODUCTION_CHANCE = 0.10
PLANT_MAX_AGE = 30

HERBIVORE_SYMBOL = "H"
HERBIVORE_INITIAL_ENERGY = 15
HERBIVORE_CHILD_ENERGY = 10
HERBIVORE_ENERGY_GAIN = 10
HERBIVORE_REPRODUCTION_THRESHOLD = 20
HERBIVORE_REPRODUCTION_CHANCE = 0.15
HERBIVORE_REPRODUCTION_COST = 8
HERBIVORE_MAX_AGE = 50

CARNIVORE_SYMBOL = "C"
CARNIVORE_INITIAL_ENERGY = 25
CARNIVORE_CHILD_ENERGY = 20
CARNIVORE_ENERGY_GAIN = 15
CARNIVORE_REPRODUCTION_THRESHOLD = 40
CARNIVORE_REPRODUCTION_CHANCE = 0.10
CARNIVORE_REPRODUCTION_COST = 20
CARNIVORE_MAX_AGE = 60

TAnimal = TypeVar("TAnimal", bound="Animal")


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
        super().__init__(x, y, PLANT_SYMBOL, PLANT_MAX_AGE)

    def update(self, ecosystem: Ecosystem) -> None:
        self.age_one_tick(ecosystem)
        if not self.alive:
            return

        if random.random() >= PLANT_REPRODUCTION_CHANCE:
            return

        empty_cells = ecosystem.get_adjacent_empty_cells(self.x, self.y)
        if not empty_cells:
            return

        new_x, new_y = random.choice(empty_cells)
        ecosystem.queue_add_organism(Plant(new_x, new_y))


class Animal(Organism, ABC):
    """Abstract organism that expends energy while acting."""

    def __init__(
        self,
        x: int,
        y: int,
        symbol: str,
        energy: int,
        max_age: int,
    ) -> None:
        super().__init__(x, y, symbol, max_age)
        self.energy = energy

    def update(self, ecosystem: Ecosystem) -> None:  # type: ignore[override]
        self.energy -= 1
        if self.energy <= 0:
            ecosystem.queue_remove_organism(self)
            return

        self.age_one_tick(ecosystem)
        if not self.alive:
            return

    def move(self, ecosystem: Ecosystem) -> bool:
        empty_cells = ecosystem.get_adjacent_empty_cells(self.x, self.y)
        if not empty_cells:
            return False

        new_x, new_y = random.choice(empty_cells)
        ecosystem.move_organism(self, new_x, new_y)
        return True


class Herbivore(Animal):
    """Animal that eats plants for energy."""

    def __init__(self, x: int, y: int, energy: int = HERBIVORE_INITIAL_ENERGY) -> None:
        super().__init__(x, y, HERBIVORE_SYMBOL, energy, HERBIVORE_MAX_AGE)

    def update(self, ecosystem: Ecosystem) -> None:
        super().update(ecosystem)
        if not self.alive:
            return

        plant = self._eat(ecosystem)
        if plant:
            ecosystem.queue_remove_organism(plant)
            self.energy += HERBIVORE_ENERGY_GAIN
            ecosystem.move_organism(self, plant.x, plant.y)
        else:
            reproduced = self._try_reproduce(ecosystem)
            if not reproduced:
                self.move(ecosystem)

    def _eat(self, ecosystem: Ecosystem) -> Optional[Plant]:
        plants = ecosystem.get_adjacent_organisms(self.x, self.y, Plant)
        if not plants:
            return None
        return random.choice(plants)

    def _try_reproduce(self, ecosystem: Ecosystem) -> bool:
        if self.energy <= HERBIVORE_REPRODUCTION_THRESHOLD:
            return False
        if random.random() >= HERBIVORE_REPRODUCTION_CHANCE:
            return False

        empty_cells = ecosystem.get_adjacent_empty_cells(self.x, self.y)
        if not empty_cells:
            return False

        child_x, child_y = random.choice(empty_cells)
        self.energy -= HERBIVORE_REPRODUCTION_COST
        child = Herbivore(child_x, child_y, HERBIVORE_CHILD_ENERGY)
        ecosystem.queue_add_organism(child)
        return True


class Carnivore(Animal):
    """Animal that hunts herbivores for energy."""

    def __init__(self, x: int, y: int, energy: int = CARNIVORE_INITIAL_ENERGY) -> None:
        super().__init__(x, y, CARNIVORE_SYMBOL, energy, CARNIVORE_MAX_AGE)

    def update(self, ecosystem: Ecosystem) -> None:
        super().update(ecosystem)
        if not self.alive:
            return

        herbivore = self._hunt(ecosystem)
        if herbivore:
            ecosystem.queue_remove_organism(herbivore)
            self.energy += CARNIVORE_ENERGY_GAIN
            ecosystem.move_organism(self, herbivore.x, herbivore.y)
        else:
            reproduced = self._try_reproduce(ecosystem)
            if not reproduced:
                self.move(ecosystem)

    def _hunt(self, ecosystem: Ecosystem) -> Optional[Herbivore]:
        herbivores = ecosystem.get_adjacent_organisms(self.x, self.y, Herbivore)
        if not herbivores:
            return None
        return random.choice(herbivores)

    def _try_reproduce(self, ecosystem: Ecosystem) -> bool:
        if self.energy <= CARNIVORE_REPRODUCTION_THRESHOLD:
            return False
        if random.random() >= CARNIVORE_REPRODUCTION_CHANCE:
            return False

        empty_cells = ecosystem.get_adjacent_empty_cells(self.x, self.y)
        if not empty_cells:
            return False

        child_x, child_y = random.choice(empty_cells)
        self.energy -= CARNIVORE_REPRODUCTION_COST
        child = Carnivore(child_x, child_y, CARNIVORE_CHILD_ENERGY)
        ecosystem.queue_add_organism(child)
        return True
