"""Seeded synthetic per-cell NF-kappa-B proxy variability around the reference.

Counter-addressed draws depend on seed, cell ID, accepted step and channel.
They are generated only on a validated candidate transition. There is no
mutable global RNG; the checkpoint records seed, accepted counter, per-cell
parameters and the complete underlying physical/private state. Variability
does not modify an amount or a transfer ledger.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math

from .checkpoint import canonical_bytes
from .nfkb_episode import NfkbEpisode, NfkbRejected
from .state import number


FORMAT = "cellsim-seeded-nfkb-episode/1"
_VARIED_KEYS = (
    "nuclear_relaxation_min", "feedback_relaxation_min",
    "reporter_relaxation_min",
)


class SeededNfkbRejected(ValueError):
    """Rejected action leaves accepted world, private state, and counter intact."""


def _normal(seed: int, cell_id: str, accepted_step: int, channel: str) -> float:
    digest = hashlib.sha256(canonical_bytes([
        seed, cell_id, accepted_step, channel,
    ])).digest()
    u1 = (int.from_bytes(digest[:8], "big") + 0.5) / 2**64
    u2 = (int.from_bytes(digest[8:16], "big") + 0.5) / 2**64
    return math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * u2)


class _VariableCore(NfkbEpisode):
    def _response_parameters_for(self, cell_id: str) -> dict[str, float]:
        return self._cell_parameters[cell_id]


class SeededNfkbEpisode:
    """Transactional, seeded extension of the deterministic NfkbEpisode."""

    def __init__(self, *, seed: int, cell_count: int = 1,
                 horizon_steps: int = 82, step_min: float = 6.0,
                 parameters: dict | None = None,
                 initial_stimulus_reservoir_mol: float = 0.5,
                 initial_payload_reservoir_mol: float = 0.1,
                 parameter_spread_sigma: float = 0.15,
                 step_noise_sigma: float = 0.06):
        if type(seed) is not int or not 0 <= seed < 2**64:
            raise ValueError("seed must be an unsigned 64-bit integer")
        spread = number(parameter_spread_sigma, "parameter spread sigma", minimum=0)
        noise = number(step_noise_sigma, "step noise sigma", minimum=0)
        if spread > 1 or noise > 1:
            raise ValueError("seeded response sigmas must be at most one")
        self._seed = seed
        self._parameter_spread_sigma = spread
        self._step_noise_sigma = noise
        self._core = _VariableCore(
            cell_count=cell_count, horizon_steps=horizon_steps, step_min=step_min,
            parameters=parameters,
            initial_stimulus_reservoir_mol=initial_stimulus_reservoir_mol,
            initial_payload_reservoir_mol=initial_payload_reservoir_mol,
        )
        self._cell_parameters = {}
        for cid in self._core._cell_ids:
            params = copy.deepcopy(self._core._parameters)
            for key in _VARIED_KEYS:
                params[key] *= math.exp(spread * _normal(seed, cid, 0, key))
                number(params[key], f"{cid} {key}", positive=True)
            self._cell_parameters[cid] = params
        self._core._cell_parameters = self._cell_parameters
        self._profile_sha256 = hashlib.sha256(canonical_bytes({
            "seed": seed, "parameter_spread_sigma": spread,
            "step_noise_sigma": noise,
            "cell_parameters_by_id": self._cell_parameters,
        })).hexdigest()

    def reset(self) -> dict:
        self._core.reset()
        return self.observe()

    def observe(self) -> dict:
        result = self._core.observe()
        result["accepted_step"] = self._core._accepted[-1]
        result["variability_profile_sha256"] = self._profile_sha256
        for cell in result["cells"]:
            cell["response_variant_id"] = f"seeded-response:{cell['cell_id']}:{self._profile_sha256[:12]}"
        return result

    def _wrap_action(self, base_action: dict) -> dict:
        return {
            "kind": "seeded_nfkb_interval",
            "variability_profile_sha256": self._profile_sha256,
            "accepted_step": self._core._accepted[-1],
            "base_action": base_action,
        }

    def make_action(self, **kwargs) -> dict:
        return self._wrap_action(self._core.make_action(**kwargs))

    def make_scheduled_action(self, **kwargs) -> dict:
        return self._wrap_action(self._core.make_scheduled_action(**kwargs))

    def step(self, action: dict) -> dict:
        if (type(action) is not dict or set(action) != {
                "kind", "variability_profile_sha256", "accepted_step", "base_action"} or
                action["kind"] != "seeded_nfkb_interval" or
                action["variability_profile_sha256"] != self._profile_sha256):
            raise SeededNfkbRejected("seeded action identity mismatch")
        if action["accepted_step"] != self._core._accepted[-1]:
            raise SeededNfkbRejected("seeded action accepted-step counter mismatch")
        try:
            candidate = SeededNfkbEpisode.from_checkpoint(self.checkpoint())
            transition = NfkbEpisode.step(candidate._core, action["base_action"])
            world, states, stores, waste, code, accepted_step = candidate._core._accepted
            varied = copy.deepcopy(states)
            draws = {}
            for cid in candidate._core._cell_ids:
                feedback_log = candidate._step_noise_sigma * _normal(
                    candidate._seed, cid, accepted_step, "feedback")
                reporter_log = candidate._step_noise_sigma * _normal(
                    candidate._seed, cid, accepted_step, "reporter")
                varied[cid]["feedback"] *= math.exp(feedback_log)
                varied[cid]["reporter_index"] *= math.exp(reporter_log)
                for key in ("feedback", "reporter_index"):
                    number(varied[cid][key], f"varied {key}", minimum=0)
                draws[cid] = {"feedback_log_factor": feedback_log,
                              "reporter_log_factor": reporter_log}
            candidate._core._accepted = (world, varied, stores, waste, code, accepted_step)
            # Restore validation covers private clocks, all tracked amounts and
            # the finite external stores before the candidate is published.
            SeededNfkbEpisode.from_checkpoint(candidate.checkpoint())
        except (NfkbRejected, ValueError, TypeError, OverflowError) as exc:
            raise SeededNfkbRejected(str(exc)) from exc
        self._core = candidate._core
        info = copy.deepcopy(transition["info"])
        info["variability"] = {
            "seed": self._seed, "accepted_step": accepted_step,
            "counter_addressed_log_factors_by_cell": draws,
        }
        return {"observation": self.observe(), "terminated": transition["terminated"],
                "info": info}

    def checkpoint(self) -> dict:
        payload = json.loads(canonical_bytes({
            "format": FORMAT,
            "seed": self._seed,
            "parameter_spread_sigma": self._parameter_spread_sigma,
            "step_noise_sigma": self._step_noise_sigma,
            "cell_parameters_by_id": self._cell_parameters,
            "variability_profile_sha256": self._profile_sha256,
            "accepted_step": self._core._accepted[-1],
            "core_checkpoint": self._core.checkpoint(),
        }))
        return {"payload": payload,
                "sha256": hashlib.sha256(canonical_bytes(payload)).hexdigest()}

    @classmethod
    def from_checkpoint(cls, checkpoint: object) -> "SeededNfkbEpisode":
        if type(checkpoint) is not dict or set(checkpoint) != {"payload", "sha256"}:
            raise ValueError("invalid seeded NF-kB checkpoint wrapper")
        payload = checkpoint["payload"]
        if type(payload) is not dict or set(payload) != {
                "format", "seed", "parameter_spread_sigma", "step_noise_sigma",
                "cell_parameters_by_id", "variability_profile_sha256",
                "accepted_step", "core_checkpoint"}:
            raise ValueError("invalid seeded NF-kB checkpoint payload")
        if hashlib.sha256(canonical_bytes(payload)).hexdigest() != checkpoint["sha256"]:
            raise ValueError("seeded NF-kB checkpoint hash mismatch")
        if payload["format"] != FORMAT:
            raise ValueError("unsupported seeded NF-kB checkpoint format")
        core_checkpoint = payload["core_checkpoint"]
        validated_core = NfkbEpisode.from_checkpoint(core_checkpoint)
        restored = cls(
            seed=payload["seed"],
            parameters=validated_core._parameters,
            parameter_spread_sigma=payload["parameter_spread_sigma"],
            step_noise_sigma=payload["step_noise_sigma"],
            **validated_core._config,
        )
        if (payload["cell_parameters_by_id"] != restored._cell_parameters or
                payload["variability_profile_sha256"] != restored._profile_sha256 or
                payload["accepted_step"] != validated_core._accepted[-1]):
            raise ValueError("seeded NF-kB parameter identity or accepted counter mismatch")
        restored._core._accepted = validated_core._accepted
        return restored
