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
