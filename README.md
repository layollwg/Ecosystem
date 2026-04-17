# Student Information
- Name: Yuqi Ren
- Student ID: 50012405

# How to Run
1. Ensure Python 3.10+ is installed.
2. Optional: create and activate a virtual environment.
3. From the project directory, run `python main.py`.
4. Follow the on-screen prompts to configure the simulation.

# Design Decision Discussion
I chose to represent the ecosystem using a single list of organism objects and helper lookup methods rather than storing organisms directly in a 2D array. Each organism tracks its own coordinates and interacts with the world through the `Ecosystem` helper functions. This design keeps the core state (the list of organisms) easy to shuffle for each tick, satisfying the specification that action order is randomized. Alternatives such as storing organisms directly in a grid dictionary or nested list would have required keeping the list in sync for random iteration, adding bookkeeping overhead.

# Simulation Extension Proposal
- **Feature:** Introduce aging and lifespan for all organisms.
- **Rationale:** Adding age-based mechanics would make survival dynamics more realistic by preventing immortal entities and encouraging continuous reproduction to sustain populations.
- **Implementation Plan:** Add an `age` attribute to the base `Organism` class and a `max_age` constant per species. Increment age every tick within each organism's update method. When an organism exceeds its `max_age`, queue it for removal. This change would primarily touch `organisms.py`, leaving the `Ecosystem` orchestration untouched.
