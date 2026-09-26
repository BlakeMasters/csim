# Live local demo

This is the three-view laptop demo. The work board reads `.agents/BOARD.md` on
localhost; the playground runs synthetic cell episodes and links a preserved
NF-κB campaign review. The observed p65 reporter view and frozen empirical
fit are separate from the illustrative payload and coupled-cell models.

## Start from the repository root

In PowerShell, first check the exact preserved local inputs and ports:

```powershell
& .venv/Scripts/python.exe tools/start_live_demo.py --check-only
```

Then run the foreground supervisor and keep that terminal open:

```powershell
& .venv/Scripts/python.exe tools/start_live_demo.py
```

Open the URLs printed by the launcher:

- Board: <http://127.0.0.1:8765/>
- Playground: <http://127.0.0.1:8766/>
- Campaign review: <http://127.0.0.1:8766/campaign>

The launcher requires Ocura OSS and checks its current ledger, the verified
`data/scmat_sequentialstim.mat` SHA-256, the preserved observed overlay,
frozen reporter candidate, 13-component integrated run, corrected 30-pair
campaign result and OSS sidecar, plus the matched coupled/uncoupled arena pair
at `runs/coupled_nfkb_arena_20260926_04/` and its OSS sidecar. It checks that
the compact report receipt
matches that exact campaign and selects
`runs/nfkb_campaign_review_20260926_04/index.html` for the read-only
`/campaign` route. It passes the verified corrected coupled result to the
playground through `--coupled-arena-result`, so a reused playground must report
that panel available. These local `runs/` and `data/` inputs are not bundled in
the tracked package; restore them before launching on another checkout. The
exact paths and hashes are saved in the new `runs/live_demo_*/launch.json`.

Ocura Engine is optional. If its installed executable is available, pass
`--engine-cli <absolute-path-to-ocura.exe>` to enable the optional Engine +
OSS replay button. The ordinary **Record through Ocura OSS** button works
without Engine.

## Two-minute click path

1. In the playground, use **3 cells** under **Reset synthetic NF-κB**, then
   **Run 82-step NF-κB pair preset** to compare two separate completed runs.
   That comparison does not advance the live pixel scene. Press **Step** once
   to advance the current live episode, then click a pixel cell to inspect its
   reporter, feedback, inventory and shared-field state.
2. Scroll to **Measured NF-κB reporter and frozen proxy fit**. Select a
   condition, inspect the observed source rows and descriptive band, and open
   **Run frozen empirical reporter predictor**. This predictor is a separate
   early baseline; some held-out responses are missed.
3. Open **the read-only NF-κB campaign review**. Its two protocol rows summarize
   30 matched synthetic baseline/intervention pairs; the full table retains
   every peak, peak time, AUC and amount residual. The attached OSS IDs record
   execution, not drug efficacy.
4. Return to the playground for the **Coupled NF-κB arena** panel. Compare the
   matched three-cell mediator run with its uncoupled control: the schedule
   and seed are identical, while mediator field/cell trajectories, reporter
   AUC and amount residuals are visible. Both arms are synthetic.
5. Continue to **Proposer and learner iterations**, the typed
   symbolic view and **Ocura OSS ledger and optional Engine**. The curriculum
   has frozen evaluation weights; it is not an RL or biology claim.
6. For a live ledger action, choose **Cell uptake**, reset the scenario, step
   through its four-interval horizon, then choose **Record through Ocura OSS**.
   The page displays the atom, chokepoint and receipt path. **Optional Engine
   + OSS** appears only when `--engine-cli` was supplied. Current-session
   recording applies to the complete uptake episode; the separate preserved
   OSS campaign records the NF-κB reference matrix.

## Reattach, alternate ports, and stop

If a matching board or playground already owns a requested port, the launcher
reuses it and leaves its current session state intact. It verifies the
playground is serving the exact compact campaign report. An occupied port
with an unrelated or stale service makes startup fail safely; the launcher
never kills that process. Choose free ports, for example:

```powershell
& .venv/Scripts/python.exe tools/start_live_demo.py --check-only --board-port 8875 --playground-port 8876
& .venv/Scripts/python.exe tools/start_live_demo.py --board-port 8875 --playground-port 8876
```

Use the printed URLs on alternate ports. The launcher passes the selected
board URL to the playground, so its in-page Agent board shortcut follows the
chosen port.

Press **Ctrl+C in the launcher terminal** to stop only the two services it
started. Reused services are left running. To reattach after losing that
terminal, run the command again; it identifies the running matching services
and does not take ownership of them. Stop a reused service in the terminal
that originally launched it. The launcher binds only `127.0.0.1`, runs on
the local CPU, and makes no cloud request.

## Evidence and scope

The alternate-port smoke at `runs/live_demo_smoke_20260926_04/launch.json`
started both services on `:8875`/`:8876`, checked the board, playground
state and byte-exact campaign SHA-256
`79bc441a8daae16be97b5cd0c9155f0abeedc735a9be1f8600b790daee9d05f6`,
then stopped both owned children while leaving the normal ports untouched.
The corrected campaign is 30 matched pairs/60 synthetic runs, 4,920
accepted steps, zero recorded failures and a maximum paired amount residual
of `1.39e-17 mol`. It is not biological validation or a drug-response
predictor. See [the integrated route](INTEGRATED_DEMO.md) and
[campaign contract](NFKB_CAMPAIGN.md) for the source split and limitations.
