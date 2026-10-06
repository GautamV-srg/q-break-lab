# Q-Break status

## Merged baseline

- Agent 3 skeleton is committed locally on `main` and tagged `skeleton`.
- Shared encoding, simulator configuration, health endpoint, tests, and CI are present.
- Push is pending repository access for the GitHub credential available on the development machine.

## Agent 3 API branch

- All API schemas and routes are implemented with strict attacker-input separation.
- Mock services keep frontend development unblocked until the Grover and Shor modules merge.
- Real-module orchestration, evidence generation, and verification checks are wired to the locked interfaces.
- Docker and Render configuration enable key size 4 and modulus 15.

## Production

- No deployment URL yet. The GitHub branch must be pushed before Render can build it.

## Known issues

- Python and Docker are unavailable in the current local environment, so executable validation is delegated to GitHub Actions after push.
- Grover, MiniAES, Shor, MiniRSA, and the React frontend are owned by the other agents and are not yet merged.

## Track 5 — symmetric (Backend A, branch `feat/track5-symmetric`)

Components extended (mapped from the brief's roles):

| Role | File / symbol |
|---|---|
| Shared simulator helper | `backend/qbreak/common/simulator.py::run_circuit` (+ `noise_p`, `backend`, `depolarizing_noise_model`) |
| MiniAES | `backend/qbreak/aes/cipher.py` (10/12-bit keys via `rotation_amounts`) |
| Attack conditions | `backend/qbreak/aes/conditions.py` (`AttackSpec`, `circuit_spec`, `full_spec`) — new |
| Grover attack | `backend/qbreak/aes/grover.py::run_grover_attack(..., condition=, counting=, noise_p=)` |
| Quantum counting | `backend/qbreak/aes/counting.py` — new |
| Classical baseline | `backend/qbreak/aes/classical.py` (`classical_key_search`, `comparison_record`) — new |
| AES resource estimator | `backend/qbreak/aes/resources.py` — new |
| Config / flags | `backend/qbreak/config.py` (symmetric section) |
| Experiments schema / runner / aggregator | `backend/qbreak/experiments/{schema,runner,aggregate}.py` — new |
| API | `routes_aes.py` (+ `GET /api/aes/resources`), `routes_evaluation.py` — new, `schemas.py`, `main.py` (`/api/config`) |
| Tests | `backend/tests/test_track5_symmetric.py` |
| Notebook | `backend/notebooks/track5_results.ipynb` |

### Contract notes for Backend B

- Write Shor experiment records with `from qbreak.experiments.schema import make_record, append_record`
  (`cipher="minirsa"`, `size={"modulus": N}`). Do not edit `runner.py`. Put per-base values under
  `extra.a`, average runs under `extra.runs_to_success` — the aggregator's `success_rate` series reads them.
  A record with both `quantum.oracle_calls` and `classical.evaluations` shows up in the `comparison` series.
- `config.py` now has delimited symmetric and RSA sections; RSA settings live at the bottom.
- `ConfigResponse` allows extra fields, so RSA additions to `/api/config` validate without touching symmetric fields.

### Contract notes for the frontend

- `POST /api/aes/attack` request: `condition` (`known_beginning` default | `known_substring` | `ciphertext_only`),
  `known_plaintext` optional (required for the two known-text conditions, forbidden for ciphertext-only),
  `noise_p` optional (≤ `aes_max_noise_p`, keys ≤ `aes_noise_max_key_bits`, shots ≤ `aes_max_noisy_shots`).
- Response adds: `condition`, `verdict` (`breached|ambiguous|not_breached`), `verdict_text`,
  `estimated_matching_keys`, `counting` (derivation lines, outcomes, counting qubits — or `ran: false` with
  `skipped_reason`), `comparison` (quantum vs classical record with `wallclock_note`), `known_text_offsets`,
  `plausibility_alphabet`, `noise_p`. `pairs_used` may be empty for substring/ciphertext-only.
- `/api/config` adds `aes_key_options` (`bits, enabled, simulated, reason` for 4/6/8/10/12/16),
  `aes_max_key_bits`, `aes_key_bits_16_note`, `aes_conditions`, `aes_counting_max_key_bits`, noise limits;
  `max_aes_text_chars` is now 1000.
- Evaluation: `GET /api/evaluation/{scaling|noise|iteration-curve|success_rate|comparison|counting}` →
  `{series, empty, rows, description}`; `GET /api/evaluation` returns all; `GET /api/evaluation/schema`.
- Real-scale context: `GET /api/aes/resources`.

## Round 3 — Defence backend (branch `feat/defence-backend`, from `integration/track5`)

Protect → blind re-attack → compare is implemented and tested end to end.

| Role | File / symbol |
|---|---|
| Defence module | `backend/qbreak/defence/` — `types.py` (shared types, AES-GCM helpers, citations, honesty notes), `aes256.py`, `mlkem.py`, `bb84.py`, `reattack.py` (blind), `compare.py`, `experiments.py` |
| Shared simulator helper | `common/simulator.py::run_circuit(..., method=, noise_model=)`: BB84 runs on the stabilizer method, 64-photon batches; native Clifford circuits skip transpilation |
| Shor input stage | `rsa/shor.py::shor_input_stage` (ML-KEM applicability check) |
| API | `api/routes_defence.py` (`POST /api/defence/protect`, `POST /api/defence/reattack`, `GET /api/defence/info`), models at the end of `api/schemas.py`, `services/defence_service.py`; `/api/config` adds `defence_methods`, `defence_max_text_chars`, `defence_bb84` |
| Config | `config.py` defence section (`BB84_*`, `DEFENCE_*`; env `QBREAK_BB84_MAX_RAW_QUBITS`, `QBREAK_DEFENCE_TIMEOUT_S`) |
| Experiments | `bb84_qber_vs_eve`, `bb84_qber_vs_noise`, `bb84_key_rate`, `defence_overhead` registered in `experiments/runner.py`; schema ciphers add `aes256`, `mlkem`, `bb84`; four new aggregator series served by `/api/evaluation/{name}`; results generated under `backend/results/` |
| Tests | `backend/tests/test_defence.py` (27 fast, 2 slow) |
| Smoke | `backend/scripts/smoke_full_loop.py` (`--base-url` or `--in-process`) — PASS for the MiniAES and MiniRSA loops |
| Notebook / README | notebook §7–10 (Defence); README §9 Defence and "Run it locally (Windows PowerShell)" |

### Contract notes for the frontend (Defence B)

- Implements `AGENT_DEFENCE_A_BACKEND.md` §7. Additive changes: every bundle carries an optional
  `public_metrics: {sizes, timings_ms}` (non-secret; used by the comparison's overhead row; send the
  bundle back unchanged). The BB84 bundle's public record is under `channel`
  (`raw_qubits, alice_bases, bob_bases, sample_positions, sample_alice_bits, sample_bob_bits, qber,
  qber_threshold, disclosed_parity_bits, confirmation_tag_bits, accepted`).
- ML-KEM protect results also carry `honesty_note`. BB84 `qkd` also has `reconciliation` and
  `privacy_amplification` objects.
- Re-attack: `bundles.bb84` may be `null` (aborted exchange). BB84 is re-attacked whenever the `bb84` field is
  present, even when it is null. `bb84_attack` also accepts an optional `raw_qubits`. The response adds `before`
  (`{cipher, verdict, text}`) when `original_attack` is sent. Verdict values:
  `infeasible | not_applicable | detected | undetected_low_intercept`. Citations are `[{id, text}]`.
- `channel_noise` is the per-photon bit-flip probability (QBER ≈ p), capped at 0.25.

### Known issues

- Docker was not available on the development machine, so the image was not built locally. The new
  dependencies (`cryptography`, `kyber-py==1.2.0`) install from wheels/pure Python on `python:3.11-slim`.
- On noisy channels the default 1024 raw qubits often aborts with "not enough secure bits", because the leak
  budget is conservative; use 2048+ raw qubits (see `bb84_key_rate`).
