# Q-Break — A Quantum Red-Team Engine for Breach Testing Encrypted Communications

**Qiskit Fall Fest 2026 · Track 5 (Open Innovation)**

Q-Break runs genuine Grover and Shor circuits on a classical simulator (Qiskit Aer) against
**miniature** symmetric (MiniAES) and public-key (MiniRSA) encryption, and reports the outcome
as a breach test: what an eavesdropper who intercepts the traffic could recover, with
evidence. Breaching production AES or RSA requires large, fault-tolerant quantum hardware that
does not exist yet; this project demonstrates the attack and verification workflow and **does
not claim a present-day speed advantage**.

Q-Break then **protects** the same message and proves the protection holds. One complete loop:

```
1. ATTACK     Grover breaks MiniAES / Shor breaks MiniRSA               ->  "Breached"
2. PROTECT    re-encrypt the message with AES-256, ML-KEM-768 and BB84 QKD (real crypto; BB84 simulated)
3. RE-ATTACK  the same quantum adversary attacks each protected version, blind
4. COMPARE    side-by-side table of the three defences + a recommendation
```

- Working notebook (all experiments + charts): [`backend/notebooks/track5_results.ipynb`](backend/notebooks/track5_results.ipynb)
- Live Evaluation page: `/evaluation` in the app (reads `/api/evaluation/*`)

---

## 1. Problem, motivation, users

"Harvest now, decrypt later": traffic recorded today can be decrypted once capable quantum
computers exist. Security teams need to **show**, not just assert, what a quantum adversary
does to their encrypted communications, so they can justify migration to post-quantum
cryptography.

**Users:** security engineers and red teams running breach-testing exercises, CISOs and
auditors who need an evidence-backed explanation, and educators teaching quantum risk.
The user plays "the organisation" (encrypts a message with a secret key); Q-Break plays the
**quantum adversary**, which only ever sees intercepted data and must earn the secret back.
After the breach, Q-Break answers the next question, "what do we migrate to?", by protecting
the message three ways and re-running the same adversary against each (§9).

## 2. Dataset / problem instances — self-generated

There is no external dataset. **All benchmark instances are self-generated and fully
reproducible** from the repository:

| Component | Instances | Source |
|---|---|---|
| Symmetric keys | **all** keys for 4/6-bit (16/64); 8 seeded keys per size for 8/10/12-bit (full key sets 256/1024/4096 are available by passing `keys_per_size`) | `qbreak.experiments.runner.grover_success_rate` |
| Messages | fixed set `"Hi judges!"`, `"Top secret plan"`, `"Quantum 2026"`, `"Hello, world"`, `"meet me at noon"` (+ known substrings `judges`, `secret`, `2026`, `world`, `noon`) | `runner.MESSAGES`, `runner.SUBSTRINGS` |
| RSA moduli (Backend B) | `N ∈ {15, 21, 33, 35, 55, 77}` (distinct odd primes ≤ 11) | RSA modules |
| Seeds | base seed `1234`, per-run seeds derived deterministically | `runner.BASE_SEED` |
| Noise | depolarising `p ∈ {0, 1e-5, 3e-5, 1e-4, 3e-4, 1e-3, 1e-2}`; fake IBM backend `FakeGuadalupeV2` | `runner.NOISE_LEVELS` |

Regenerate everything:

```bash
pip install -e "backend[dev,experiments]"
cd backend
python -m qbreak.experiments.runner          # or --quick for a smoke run
python -m qbreak.experiments.aggregate       # results/aggregated/*.json + *.csv
```

Records follow the shared results schema (§8 below) and are stored under `backend/results/<experiment>/`.

## 3. Why a quantum approach

Grover's algorithm searches an unstructured keyspace of size N with about (π/4)·√N oracle
calls instead of the ~N/2 classical tries — the quadratic speed-up that halves the effective
key length of symmetric ciphers. Shor's algorithm finds the period of aˣ mod N in polynomial
time, which breaks RSA outright. These are *the* two quantum threats to today's cryptography,
so a breach-testing tool must run them, not simulate their effect. Q-Break builds the real
circuits: the Grover oracle runs the MiniAES cipher reversibly in superposition over every
key; quantum counting (phase estimation of the Grover operator) estimates how many keys fit
before choosing the iteration count.

## 4. Classical baseline

Every symmetric attack also runs a **classical brute-force key search** on the *same*
intercepted data and the *same* condition (`qbreak/aes/classical.py`). It is blind (no key
input; tested). Each run returns a comparison record:

```json
{ "quantum":   { "oracle_calls": 18, "grover_iterations": 3, "qubits": 15, "depth": 9, ... },
  "classical": { "cipher_evaluations": 12, "expected_tries": 8.5, "exhaustive_evaluations": 16, ... },
  "wallclock_note": "Wall-clock time is not the fair comparison: ..." }
```

The fair metric is **query count** (Grover oracle calls vs classical cipher evaluations). In
wall-clock the simulator is far slower than classical brute force at these sizes, and we say
so. The RSA side's classical baselines (trial division / classical order finding) are in
Backend B's modules.

## 5. Qiskit implementation overview

```
backend/qbreak/
  aes/cipher.py       MiniAES: 4-bit block, one round, 4/6/8/10/12-bit keys
  aes/conditions.py   the three attack conditions -> AttackSpec (groups of checks)
  aes/grover.py       reversible oracle (S-box lookup, scratch uncompute), diffuser, attack
  aes/counting.py     quantum counting: QPE on the Grover operator, max-likelihood M
  aes/classical.py    classical brute force + comparison record
  aes/resources.py    real-scale AES resource estimates (cited)
  common/simulator.py the single door to Aer (concurrency limit, noise models, fake backends)
  experiments/        shared results schema, runner, aggregator
  defence/            round 3: aes256.py, mlkem.py, bb84.py (protect), reattack.py (blind),
                      compare.py (table + recommendation), experiments.py, types.py
  api/                FastAPI: /api/aes/*, /api/rsa/*, /api/defence/*, /api/evaluation/*, /api/config
```

**Symmetric attack conditions** (`condition` on `POST /api/aes/attack`):

| Condition | Attacker knows | Oracle marks a key when |
|---|---|---|
| `known_beginning` | first k characters (default 3) | it encrypts the known first blocks to the ciphertext |
| `known_substring` | text somewhere in the message | it encrypts the known text to the ciphertext at **any** byte-aligned offset (OR over offsets, one `hit` qubit per offset) |
| `ciphertext_only` | nothing | every first-of-byte block decrypts to a high nibble of ASCII (bytes 0x20–0x7F) — expect several keys → **Ambiguous** verdict |

Sub-block alignment is out of scope: MiniAES encrypts whole 4-bit blocks and text is whole
bytes, so a known string never starts part-way through a block.

**Key sizes.** 4/6/8-bit is the original one-round cipher. 10/12-bit keep the 8-bit cipher
in the low byte; key bits 8–9 add an output rotation and bits 10–11 an input rotation
(controlled swaps in the circuit), so all 4096 12-bit keys are distinct permutations.
Circuit width is `key_bits + 8 + checks + 1` (4-bit: 15, 8-bit: 20, 12-bit: 24 qubits).
12-bit needs ~2 GB RAM and is gated by `SYMMETRIC_MAX_KEY_BITS` (the default deploy sets 8);
**16-bit is not simulated** (≈30 qubits ≈ 16 GB state vector, ~200 iterations) — the reason
is served as data by `/api/config`.

**Quantum counting** runs before Grover for keys up to `QBREAK_COUNTING_MAX_KEY_BITS`
(default 4; it costs 2ᵗ−1 controlled Grover operators). The estimate M̂ sets the iteration
count ⌊π/4·√(N/M̂)⌋; above the cap the attack falls back to trying M = 1, 2, 4, 8.

### Configuration

| Env var | Default | Meaning |
|---|---|---|
| `QBREAK_KEY_BITS` | `4` | requested key sizes, e.g. `4,6,8,10,12` locally |
| `SYMMETRIC_MAX_KEY_BITS` | `12` (`8` in Docker/Render) | memory cap on key size |
| `QBREAK_COUNTING_MAX_KEY_BITS` | `4` | largest key size with quantum counting |
| `QBREAK_AES_TIMEOUT_S` | `60` | per-request limit (raise for 12-bit) |
| `QBREAK_NOISE_MAX_KEY_BITS` | `4` | largest key size accepting `noise_p` |
| `QBREAK_RESULTS_DIR` | `backend/results` | experiment records |
| `QBREAK_BB84_MAX_RAW_QUBITS` | `4096` | cap on BB84 raw qubits per request |
| `QBREAK_DEFENCE_TIMEOUT_S` | `60` | per-request limit for `/api/defence/*` |

## 6. Quantitative metrics and visuals

See the notebook and the Evaluation page (`GET /api/evaluation/{scaling|noise|iteration-curve|success_rate|comparison|counting}`):
the Grover success-vs-iterations curve against the sin² envelope, qubits/depth vs key size,
success vs noise, success rates per condition, quantum oracle calls vs classical tries, and
quantum-counting accuracy. Real-scale context: `GET /api/aes/resources` (Grassl et al. 2016;
NIST PQC call 2016). Defence series: `bb84_qber_vs_eve`, `bb84_qber_vs_noise`, `bb84_key_rate`,
`defence_overhead` (§9).

## 7. Noise, depth and problem-size analysis

`run_circuit` supports a depolarising model (error p on CX, p/10 on single-qubit gates; the
circuit is transpiled to `u`+`cx` so every gate is noisy) and fake IBM backends transpiled to
the real chip layout (`FakeGuadalupeV2`, 16 qubits). The experiments measure attack success vs
noise, depth vs key size, and the iteration curve. The takeaway, supported by the data: the
4-bit attack's transpiled circuit already has thousands of two-qubit gates, so at today's error
rates the signal collapses towards the uniform baseline — **even this miniature breach fails on
noisy hardware; real breach testing needs fault tolerance.**

## 8. Shared experiments results schema

Defined in `backend/qbreak/experiments/schema.py` (`RESULT_SCHEMA`, `make_record`,
`append_record`, `load_records`); served at `GET /api/evaluation/schema`. Backend B writes Shor
records through `make_record`/`append_record` without editing the runner.

```json
{
  "schema_version": 1,
  "experiment": "grover_iteration_curve | grover_noise_sweep | grover_fake_backend | grover_scaling | grover_success_rate | grover_counting_accuracy | shor_noise_sweep | shor_base_success | ...",
  "cipher": "miniaes | minirsa | aes256 | mlkem | bb84",
  "size": { "key_bits": 8 },
  "condition": "known_beginning | known_substring | ciphertext_only | null",
  "seed": 1234,
  "success": true,
  "p_success": 0.83,
  "quantum": { "oracle_calls": 12, "iterations": 3, "qubits": 18, "depth": 540, "gate_counts": {} },
  "classical": { "evaluations": 128 },
  "noise": { "model": "ideal | depolarizing | fake_backend", "p": 0.01, "backend": null },
  "extra": {},
  "timestamp": "ISO-8601"
}
```

## 9. Defence — protect, re-attack, compare

After the breach, `POST /api/defence/protect` re-encrypts the organisation's message
(≤ 1000 characters) with exactly three defences. Each returns a **public bundle** (what an
eavesdropper sees) plus a server-side round-trip check; keys and shared secrets never leave
the server.

| Defence | What runs | Why it is (or isn't) quantum-safe |
|---|---|---|
| **AES-256** | Real AES-256-GCM (`cryptography`), fresh 256-bit key, 96-bit nonce | Grover only square-roots a key search: 256-bit keys keep ~128-bit security. Does not solve key exchange. |
| **ML-KEM-768** | Real ML-KEM-768 (FIPS 203) via `kyber-py`: keygen → encaps → HKDF-SHA256 → AES-256-GCM → decaps → decrypt | Rests on Module-LWE; **no known efficient quantum attack** (not "proven unbreakable"). Solves key exchange over ordinary networks. |
| **BB84 QKD** | Simulated in Qiskit Aer (stabilizer method, 64-photon batches through the shared simulator): random bits/bases, optional channel noise and intercept-resend Eve, sifting, QBER sample, abort above 11%, simplified reconciliation, SHA-256 privacy amplification → 256-bit key → AES-256-GCM | Physics: measuring a photon disturbs it, so an eavesdropper raises the error rate (≈ fraction/4) and is detected. Needs photon hardware; ~100 km without trusted relays. |

`POST /api/defence/reattack` is the **blind** attacker side: it accepts only public bundles
(any key, secret or plaintext field is rejected with 422) and returns an honest verdict per method:

| Method | Attack | What actually runs | Verdict |
|---|---|---|---|
| AES-256 | Grover key search | Feasibility check only (no circuit): 6,681 logical qubits, ≈ 2^127.7 iterations (Grassl et al. 2016), against our simulator's 24-qubit ceiling and the measured MiniAES scaling curve | `infeasible` |
| ML-KEM-768 | Shor | The bundle goes to the Shor pipeline's input stage (`shor_input_stage`), which finds no RSA modulus and no discrete-log group | `not_applicable` |
| BB84 | Intercept-resend | A fresh BB84 exchange with Eve is **executed** in Qiskit | `detected` (QBER > threshold, key discarded) or `undetected_low_intercept` (Eve's ≈ fraction/2 knowledge is removed by privacy amplification) |

The response adds a comparison table (measured sizes/timings + cited properties) and a
rule-based recommendation (`{text, rule}`): ML-KEM for key exchange plus AES-256 for data
(which is what ML-KEM + AES-256-GCM already is), BB84 for high-security fixed links with photon
hardware. `GET /api/defence/info` serves the static rows, citations, BB84 defaults/limits and
honesty notes; `/api/config` carries `defence_methods`, `defence_max_text_chars`, `defence_bb84`.

**Experiments** (`python -m qbreak.experiments.runner --only bb84_qber_vs_eve bb84_qber_vs_noise bb84_key_rate defence_overhead`):
measured QBER tracks the theory, from 0% with no Eve to 25.3% at full intercept (theory 25%),
and QBER ≈ p for channel noise p. The 1024-qubit default yields a 256-bit key on a clean
channel. Noisy channels need 2048+ raw qubits, because the leak budget (disclosed parities,
confirmation tag, Eve's estimated knowledge) is conservative.

**Honesty notes.**
- No Grover circuit is run on AES-256 and no Shor circuit on ML-KEM; those verdicts are a cited estimate and an applicability check, and say so.
- `kyber-py` is an educational, pure-Python, **not constant-time** implementation of FIPS 203; production systems should use a vetted library (liboqs, BoringSSL, the OS crypto provider).
- BB84 is a simulation; reconciliation is a simplified block-parity / binary-search scheme (four shuffled passes, no Cascade back-tracking); privacy amplification is a single SHA-256 hash; the classical channel is assumed authenticated.

**Citations.** NIST FIPS 203 (ML-KEM, 2024); C. H. Bennett & G. Brassard, "Quantum cryptography:
Public key distribution and coin tossing", 1984; P. W. Shor & J. Preskill, PRL 85, 441 (2000)
(11% threshold); M. Grassl, B. Langenberg, M. Roetteler, R. Steinwandt, "Applying Grover's
algorithm to AES: quantum resource estimates", PQCrypto 2016; NIST FIPS 197 / SP 800-38D (AES-GCM);
RFC 5869 (HKDF); P. W. Shor, SIAM J. Comput. 26(5), 1997.

## 10. Limitations — can a quantum advantage be claimed?

**No.** Be clear about what this is:

- **Toy ciphers.** MiniAES has a 4-bit block and one round; MiniRSA uses moduli ≤ 77. They borrow
  the structure of AES/RSA so the attack is real, but they are not reduced versions of the standards.
- **Classical simulation.** Every circuit runs on Aer, so wall-clock time is far *worse* than
  classical brute force. The comparison we report is the number of queries, where Grover's
  √N scaling is visible but, at 2⁴–2¹² keys, also includes quantum counting overhead.
- **Scale.** Memory doubles per qubit; 16-bit keys (~30 qubits) are already out of reach.
  Real AES-128 needs ~2,953 logical qubits and ~2⁸⁶ T gates (Grassl et al. 2016) — and many
  more physical qubits after error correction.
- **Noise.** With realistic noise the miniature attack already degrades towards random guessing.
- **Ciphertext-only** relies on a plaintext-plausibility test (ASCII text) and is honest about
  ambiguity rather than guessing.

What *is* demonstrated: the complete, verifiable breach-testing workflow with genuine Grover,
quantum counting and Shor circuits, blind attackers, classical baselines, and evidence.

## Run it locally (Windows PowerShell, VS Code)

Requires **Python 3.11** (3.12 also works) and **Node.js 20**. From the repository root:

```powershell
# 1. Backend: virtual environment + dependencies (qiskit, qiskit-aer, fastapi, cryptography, kyber-py)
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1          # if blocked: Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
python -m pip install --upgrade pip
pip install -e "backend[dev]"

# 2. Run the API (terminal 1)
cd backend
$env:QBREAK_KEY_BITS = "4,6,8"         # optional: enable more MiniAES key sizes
uvicorn qbreak.api.main:app --reload --port 8000
```

```powershell
# 3. Frontend dev server (terminal 2); /api is proxied to port 8000
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173** (API health: http://localhost:8000/api/health, API docs:
http://localhost:8000/docs). To serve the built UI from FastAPI instead: `npm run build` in
`frontend`, then `$env:STATIC_DIR = "..\frontend\dist"` before starting uvicorn and open
http://localhost:8000.

**Tests and smoke test** (venv active, from `backend`):

```powershell
pytest -m "not slow"                       # fast suite (what CI runs)
pytest -m slow                             # 10/12-bit recovery, noise sweeps, BB84 sweeps
python scripts\smoke_full_loop.py          # full loop against the running server (PASS/FAIL per stage)
python scripts\smoke_full_loop.py --in-process   # same, without a server
```

**Experiments** (regenerate the Evaluation page data):

```powershell
python -m qbreak.experiments.runner --quick   # or without --quick for the full suite
python -m qbreak.experiments.aggregate
```

**Docker** (same image Render builds; frontend is built and served by FastAPI):

```powershell
docker build -t q-break .
docker run --rm -p 8000:8000 q-break
# open http://localhost:8000
```
