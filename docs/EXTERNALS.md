# Introducing external components

The goal is extensible experiments, not arbitrary mutation of the world. The interface described here is a **proposed production contract**. Current kernels demonstrate material transfer and scoped updates; plugin registration, isolation and full observation/action APIs are not implemented.

## Typed effects

| External | Required declaration | Coupling output | Essential verification |
|---|---|---|---|
| Chemical reservoir | Species/form, concentration or amount, volume, schedule | Amount-per-time or amount integrated over a stated interval | Finite reservoir depletion; sign and unit consistency |
| Imposed mechanical object | Geometry, material law, motion/control, contact/adhesion rules | Force, displacement or constrained boundary | Contact orientation, work/energy interpretation, penetration |
| Matrix/material region | Structure, permeability, mechanics, remodeling law if any | Interface stress, flux or property update | No double counting with native ECM or fluid terms |
| Introduced cells | Identified population, initial states, geometry, amount inventory | Atomic population insertion with provenance | Unique IDs, boundary displacement and material ledger |
| Intracellular model | State variables, compartments, species mapping, input/output laws | Reaction or exchange rates, event proposals | Conservation assumptions, stiff integration, known unsupported inputs |
| Learned model/controller | Training/evaluation provenance, input availability, output meanings | Bounded proposal only | Held-out error, abstention, no privileged observation leakage |

A source concentration alone does not specify a finite delivered dose. If a boundary concentration is held fixed, record that it represents an external reservoir and account for resulting flux. A “drug” identifier alone does not determine binding, uptake or fate decisions.

## Proposed port record

```text
port_id, owner_id, interface_version
quantity_type: amount | amount_rate | concentration | force | traction | displacement | event
unit, species_or_material_id, compartment_or_mesh_id
orientation, sample_location, valid_time_interval
ownership, allowed_receiver, interpolation_rule
balance_account, failure_policy, provenance_ref
```

Do not sum a concentration and a molar amount, or a traction and a nodal force, merely because both are numerical arrays. Make conversions at the interface and test them.

## Scheduling and intervention semantics

External interventions act at declared synchronization boundaries initially. Define whether actions take effect before or after observation, how simultaneous interventions are ordered and how they appear in checkpoints. A zero-duration query should not integrate an extra time interval.

Physical stochastic draws belong to replayable state. An implicit coupling retry must replay the same tentative draws unless the numerical method explicitly defines a different stochastic coupling. Side-effecting actions such as writing a final artifact or consuming an external input stream must not occur in a rejected iteration.

## Observation versus privileged state

For agent training, distinguish complete simulator state from measurements available to the policy. Do not let a policy use an unobservable internal phenotype label while describing the task as image- or assay-based. Log actions and interventions separately from the response model. The existence of a controllable simulator does not validate a learned treatment policy.

## Failure modes

Reject missing physical laws, invalid units, stale mappings, nonfinite outputs, duplicate identities, unsupported geometry, unavailable backend state and material overdraw. A source outside its validated response range may be simulated exploratorily only under an explicit unqualified status. Do not silently invent a pharmacodynamic law or promote solver resolution to compensate for absent biology.

Plugins are trusted code in the reference package. A production security boundary would require separate processes and explicit authorization, resource budgets and controlled file/network access; the broad write-set checks are not that boundary.
