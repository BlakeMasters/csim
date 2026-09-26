"""Sequential Lie-split synchronization windows, with per-process subcycling.

Not an asynchronous multirate solver and not second-order Strang splitting.
Processes must be pure with respect to their own state and external side effects.
All shared state is committed only after the entire synchronization window succeeds.
"""
from __future__ import annotations
from dataclasses import dataclass
from fractions import Fraction
from typing import Callable
from .state import Update, World, identifier, time_fraction


@dataclass(frozen=True)
class Process:
    name: str
    max_step_s: Fraction
    writes: frozenset[str]
    propose: Callable[[World, float], Update]

    def validate(self) -> None:
        identifier(self.name,"process name")
        if time_fraction(self.max_step_s) <= 0:
            raise ValueError("process max_step must be positive")
        if set(self.writes)-{"cells","fields","ledger","events"}:
            raise ValueError("unknown write category")
        if not callable(self.propose):
            raise TypeError("propose must be callable")


class WindowStepper:
    def __init__(self, processes: list[Process], max_window_s: Fraction):
        self.processes = tuple(processes)  # input order is the explicit splitting order
        self.max_window_s = time_fraction(max_window_s)
        if self.max_window_s <= 0:
            raise ValueError("window must be positive")
        names = [p.name for p in self.processes]
        if len(set(names)) != len(names):
            raise ValueError("duplicate process name")
        for p in self.processes:
            p.validate()

    def advance(self, world: World, until_s: Fraction) -> None:
        world.validate()
        end = time_fraction(until_s)
        if end < world.time_s:
            raise ValueError("cannot integrate backwards")
        while world.time_s < end:
            start = world.time_s
            stop = min(start+self.max_window_s,end)
            working = world.clone()
            for process in self.processes:
                elapsed = Fraction(0)
                while elapsed < stop-start:
                    h = min(time_fraction(process.max_step_s),stop-start-elapsed)
                    snapshot = working.clone()
                    snapshot.time_s = start+elapsed
                    initial = snapshot.clone()
                    update = process.propose(snapshot,float(h))
                    if snapshot != initial:
                        raise PermissionError("process mutated its read snapshot; return an Update")
                    if not isinstance(update,Update):
                        raise TypeError("process must return Update")
                    update.commit(working,process.writes)
                    elapsed += h
            working.time_s = stop
            working.step += 1
            world.overwrite(working)
