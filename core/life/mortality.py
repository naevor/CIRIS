"""6.1 Death — when ANY condition holds steadily for death_ticks substrate-ticks:
vitality == 0 (flesh ran out) | coherence < 0.12 (terminal decoherence) | age > cap."""
from __future__ import annotations


class Mortality:
    def __init__(self, cfg: dict):
        self.coh_death = float(cfg["life"]["coherence_death"])
        self.death_ticks = int(cfg["life"]["death_ticks"])
        self.age_cap = int(cfg["life"].get("age_cap", 0))
        self.reset()

    def reset(self):
        self.streak = 0
        self.cause = None

    def check(self, axes: dict, age_thoughts: int):
        cause = None
        if axes["vitality"] <= 0.001:
            cause = "vitality"
        elif axes["coherence"] < self.coh_death:
            cause = "decoherence"
        if cause:
            self.streak += 1
            self.cause = cause
        else:
            self.streak = 0
            self.cause = None
        if self.streak >= self.death_ticks:
            return self.cause
        if self.age_cap and age_thoughts >= self.age_cap:
            return "age"
        return None
