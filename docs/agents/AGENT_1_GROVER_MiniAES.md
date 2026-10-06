# Q-Break — Agent 1 build prompt: Grover / MiniAES (Symmetric breach test engine)

> **You are Agent 1 of 4.** Your human teammate will paste this whole file to you as your only brief. You will build **the MiniAES toy cipher and the genuine Qiskit Grover attack that powers the symmetric breach test**, on branch `feat/grover`.
>
> **How to use this file:** read Part A (shared by all four agents) in full, then Part B (your role). Part A is identical in all four files, so every agent shares the same contracts. When Part A and Part B seem to conflict, Part A's contracts (A5, A6) win; raise the conflict with your human.
>
> **Start now:** confirm the skeleton is on `main` (`git pull`). If it isn't there yet, plan and set up your environment while you wait. Then work through your B1 deliverables in order, committing small and opening PRs at each milestone.

---

# PART A — SHARED CONTEXT (identical in all four agent files)

You are one of **four AI coding agents**, each driven by one human teammate, building **Q-Break**, a quantum breach-testing tool prototype, in a **16-hour hackathon**. The four agents work **in parallel on separate git branches** of one repository and merge into `main`. This file is the **only context you have**. Everything you need to know about the project, the codebase, the contracts between agents, and your own job is written here. If something is not specified here, choose the simplest option that respects the contracts below, and write down what you chose in your PR description.

The four agents are:

| Agent | Name | Branch | Owns |
|---|---|---|---|
| **Agent 1** | Grover / MiniAES | `feat/grover` | `backend/qbreak/aes/**`, `backend/tests/test_aes_*.py`, `backend/scripts/benchmark_grover.py` |
| **Agent 2** | Shor / MiniRSA | `feat/shor` | `backend/qbreak/rsa/**`, `backend/tests/test_rsa_*.py`, `backend/scripts/benchmark_shor.py` |
| **Agent 3** | API, verification, integration, deployment | `feat/api` (plus the initial skeleton commit directly on `main`) | Everything in the repo that is not owned by another agent |
| **Agent 4** | Frontend | `feat/ui` | `frontend/**` |

**Golden rule: never create, edit, or delete a file you do not own.** If you need a change in someone else's file, write the request in your PR description or tell your human, and they will pass it to the owner. This rule is what keeps the final merge conflict-free.

---

## A1. The project idea and positioning

### Positioning (read this first; it shapes every user-facing word)

**Q-Break is a quantum breach-testing tool.** The vision: once suitable quantum hardware exists, companies, governments, and any organization that sends encrypted messages can run Q-Break to answer one question: **"Could a quantum attacker breach our encrypted messages?"**

What we are building in this hackathon is the **working prototype at miniature scale**:
- The organization submits an encrypted message (the "test subject").
- Q-Break runs **real quantum attack circuits** against it: Grover for symmetric keys, Shor for public-key RSA.
- Q-Break returns a **Breach Report** with a clear verdict, the evidence, and what the result means for real-world key sizes.
- **"Pop the Hood"** explains everything that happened, in depth: the circuit, the measurements, the maths, and the verification.

The product framing is a **testing tool**, not a "lab toy". The language throughout the app is that of a security assessment: test, target, breach, verdict, evidence, report, recommendation. The science stays exact; only the framing changes.

The two test modules cover **two different quantum threats**:

| Test module | Real-world family it models | What is hidden | Qiskit algorithm | Breach result |
|---|---|---|---|---|
| **Symmetric breach test** (MiniAES, an AES-inspired toy cipher) | Shared-key ciphers such as AES | A secret key (4 bits, later 6 and 8 bits) | **Grover's search** | Key recovered, message decrypted |
| **Public-key breach test** (MiniRSA: real RSA arithmetic, tiny numbers) | RSA (and, by the same algorithm, other factoring/discrete-log systems) | The prime factors of the public modulus N | **Shor's period finding** | N factored, private key rebuilt, message decrypted |

### The user experience, end to end (identical shape for both tests)

1. **Configure the test (the sender side, "Your organization"):**
   - **Symmetric test:** the user types the message their organization would send (e.g. `Hi judges!`) and a secret key (e.g. `1001`), then clicks "Encrypt". The app shows the ciphertext.
   - **Public-key test:** the user picks a modulus (N = 15 first; later 21 and others), and the app generates the organization's RSA key pair. The user types a message, which is encrypted with the public key (n, e).
2. **Interception (what crosses the wall):** Q-Break plays the **quantum adversary**. It receives only what a real eavesdropper would have:
   - **Symmetric test:** the ciphertext, the public cipher rules, and a short **known plaintext prefix** (a "crib", e.g. a standard greeting or header; default: the first 3 characters, which the user can edit). It **never receives the key**.
   - **Public-key test:** only n, e, and the ciphertext. It never sees p, q, φ, or d.
3. **Run the breach test:**
   - **Symmetric:** a Grover circuit searches all 2^k keys. Its oracle runs the cipher *reversibly inside the quantum circuit*, marks keys that turn the known prefix into the observed ciphertext, and diffusion amplifies them.
   - **Public-key:** a period-finding circuit finds the order r of a random base a modulo N. Continued fractions and GCDs then turn r into the factors, and the private key is rebuilt.
4. **Breach Report:** a verdict ("BREACHED: key recovered" or "Not breached this run"), the recovered secret, the decrypted message (highlighting the part the adversary did not know), and the cost of the attack (qubits, iterations or circuit size, time). It also includes a **"What this means at real scale"** section and a **recommendation**, for example:
   - a key found by Grover means symmetric keys need doubling, because Grover halves the effective key length;
   - a factored modulus means RSA itself must be replaced with post-quantum algorithms.
5. **Pop the Hood:** the full explanation and evidence. It shows the circuit, the measurement histogram, the qubit count, depth, gate counts, the iteration or phase → period → factor maths, and every verification step, each with a plain-English explanation.

### What the project claims (and what it must NOT claim)

The claim is deliberately precise, and the app states it plainly:

> **Q-Break is a prototype of a quantum breach-testing tool. Today it runs genuine Grover and Shor circuits, on a classical simulator, against miniature versions of symmetric and RSA encryption. Breaching real AES or production RSA keys requires large, fault-tolerant quantum hardware that does not exist yet. Q-Break demonstrates exactly how such a test would work, and does not claim a speed advantage today.**

Required honesty points. These must appear in the app (the About page plus short notes in each report), and nothing in the code may contradict them:
- **The "once scaled" story is a vision, not a current capability.** Never word anything as "we tested your real AES/RSA". Use "this miniature test shows how..." and "at real key sizes this attack would need...".
- "MiniAES" is an **AES-inspired toy cipher**. It is not a reduced version of the real AES standard. It uses a 4-bit block, a single round, and ECB-style independent blocks, all of which are insecure on purpose.
- MiniRSA uses genuine RSA arithmetic with numbers far too small to be secure. At N = 15, 21, and 35, the public and private exponents are numerically equal (e = d). These tests demonstrate Shor's **factor-recovery workflow**, not secure RSA examples.
- The modular-multiplication blocks in the Shor circuit are built from the permutation that multiplication by a performs, and that permutation is computed classically when the circuit is built. This is the standard approach in small textbook demonstrations, and the app says so openly. For N = 15, a hand-built swap-gate version (the Qiskit textbook construction) is also shown.
- Text encoding for RSA uses 3-bit chunks, so every plaintext value is ≤ 7 < N. This is textbook RSA with no padding, so equal chunks encrypt to equal ciphertexts. That is insecure, and the app says so.
- The real-world guidance in reports must stay accurate and general:
  - Shor breaks RSA and elliptic-curve cryptography at any key size, given enough fault-tolerant qubits.
  - Grover roughly halves the effective security of a symmetric key, so AES-128 drops to about 64-bit security and AES-256 to about 128-bit, which is still considered strong.
  - "Harvest now, decrypt later" means data intercepted today can be decrypted once the hardware exists.
  - The recommended path is moving to NIST post-quantum standards (ML-KEM, FIPS 203; ML-DSA, FIPS 204) and to 256-bit symmetric keys.

  Do not invent precise qubit counts or dates.

### Terminology map (UI words vs code words)
The backend contract field names in A5 and A6 stay **unchanged**. Only the user-facing words change:

| In code / API | In the UI |
|---|---|
| victim, `victim_secret` | "Your organization", "Organization's private key (hidden from adversary)" |
| attacker, `/attack` | "Quantum adversary (simulated)", "Run breach test" |
| Grover lab / Shor lab | "Symmetric breach test" / "Public-key breach test" |
| crib / known plaintext | "Known plaintext (e.g. a standard greeting or header)" |
| attack response | "Breach Report" |

### Non-negotiable integrity rules
1. **No hardcoded answers.** The attack code must never receive or look up the secret key or the factors. Agent 3's tests will verify this for **every** possible 4-bit key and for every supported N.
2. **Verification is part of the product.** Every result is classically re-checked, and the result of each check is shown to the user.
3. **Longer text does not mean a bigger circuit.** Grover works only on a few known blocks, and classical decryption handles the full message. The Shor circuit depends only on N.
4. Everything runs locally on **Qiskit Aer**, with no IBM hardware queue. The app is also **deployed** on the public internet for judging.

---

## A2. Tech stack (pinned)

- **Python 3.11**
- **Qiskit 2.x** (`qiskit>=2.0,<3`) and the latest **qiskit-aer** compatible with it (`qiskit-aer>=0.17`)
- **numpy**
- **FastAPI**, **uvicorn**, **pydantic v2**
- **pytest** and **httpx** (for API tests)
- **React 18 + Vite + TypeScript**, `react-router-dom`, `recharts` (histogram)
- **Docker** (single image: FastAPI serves the built frontend), deployed to **Render** as a Docker web service (Railway or Fly.io work as fallbacks)
- GitHub Actions CI

### Qiskit 2.x usage rules (everyone follows these)
- Imports: `from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister, transpile` and `from qiskit_aer import AerSimulator`.
- **Never** use `execute`, `qiskit.Aer`, `BasicAer`, `IBMQ`, or `qiskit.providers.aer`. All of these are gone in Qiskit 2.x.
- **Do not** use `qiskit.circuit.library.QFT` (deprecated). Write the inverse QFT by hand; Agent 2 has the exact code.
- `UnitaryGate` comes from `qiskit.circuit.library`.
- Multi-controlled X is `qc.mcx(control_qubits, target_qubit)`. Multi-controlled Z is H, then MCX, then H on the target.
- **All simulations go through the shared helper** `qbreak.common.simulator.run_circuit` (defined in A5). Do not create your own `AerSimulator` instances elsewhere.
- Every circuit you simulate has **exactly one classical register**, so Aer count keys are plain bitstrings with no spaces.
- Build big repeated blocks as named sub-circuits converted with `.to_gate(label="...")`. Examples: `"Oracle"`, `"Diffuser"`, `"U^(2^3)"`, `"IQFT"`. This keeps the overview drawing readable.

---

## A3. Global conventions (everyone must follow these exactly)

**Bit order and bitstrings**
- A key or bitstring shown to humans is written **MSB first**. The key `"1001"` is the integer 9.
- Inside circuits, **qubit i of a register holds bit i (value 2^i)**, so qubit 0 is the LSB. Measure qubit i into classical bit i. Aer then prints count keys MSB first, so a count key `"1001"` also means the integer 9. This makes counts and human keys line up with no reversing.

**Nibbles (MiniAES)**
- A nibble is an `int` from 0 to 15.
- Text is converted to UTF-8 bytes, and each byte becomes two nibbles: `[byte >> 4, byte & 0xF]` (high nibble first).
- Ciphertext is a `list[int]` of nibbles. It is shown in the UI as a hex string, one hex digit per nibble.

**3-bit chunks (MiniRSA)**
- Text is converted to UTF-8 bytes, then to one bitstream (MSB first within each byte), then split into 3-bit chunks.
- The last chunk is padded with zeros on the right. `bit_length = 8 * len(bytes)` is sent along with the ciphertext so decoding can drop the padding.
- Each chunk is an `int` from 0 to 7.

**Keys**
- `key_bits` ∈ {4, 6, 8}. Keys travel as MSB-first binary strings of exactly `key_bits` characters.

**Determinism**
- Every function that simulates takes `shots: int = 1024` and `seed: int | None = None`. Tests always pass a seed.

**Code style**
- Type hints everywhere and docstrings on public functions.
- Format only your own files: `ruff format` for Python, Prettier defaults for TypeScript.
- Never reformat other people's files.

---

## A4. Repository tree (final state) and file ownership

```
q-break-lab/
├── README.md                              (A3)  how to run, deploy, project claim
├── Dockerfile                             (A3)  multi-stage: build frontend, then python image
├── .dockerignore                          (A3)
├── .gitignore                             (A3)
├── render.yaml                            (A3)  Render blueprint (Docker web service)
├── .github/workflows/ci.yml               (A3)  backend tests (not slow) + frontend build
├── docs/agents/                           (A3)  these four prompt files, committed in the skeleton
│
├── backend/
│   ├── pyproject.toml                     (A3)  ALL Python deps live here (already complete in skeleton)
│   ├── qbreak/
│   │   ├── __init__.py                    (A3)  empty
│   │   ├── config.py                      (A3)  feature flags / env vars
│   │   ├── common/
│   │   │   ├── __init__.py                (A3)
│   │   │   ├── simulator.py               (A3)  run_circuit(): the ONLY Aer entry point
│   │   │   ├── encoding.py                (A3)  text <-> nibbles / 3-bit chunks, key strings
│   │   │   └── evidence.py                (A3)  QuantumCircuit/counts -> JSON evidence
│   │   ├── aes/                           (A1)  ← Agent 1 owns this whole folder
│   │   │   ├── __init__.py                (A1)
│   │   │   ├── cipher.py                  (A1)  MiniAES classical cipher
│   │   │   └── grover.py                  (A1)  oracle, diffuser, Grover attack
│   │   ├── rsa/                           (A2)  ← Agent 2 owns this whole folder
│   │   │   ├── __init__.py                (A2)
│   │   │   ├── minirsa.py                 (A2)  keygen / encrypt / decrypt (victim side)
│   │   │   └── shor.py                    (A2)  period-finding circuit + post-processing
│   │   ├── verification/
│   │   │   ├── __init__.py                (A3)
│   │   │   ├── aes_checks.py              (A3)
│   │   │   └── rsa_checks.py              (A3)
│   │   ├── services/
│   │   │   ├── __init__.py                (A3)
│   │   │   ├── aes_service.py             (A3)  orchestrates encoding + A1 code + verification
│   │   │   └── rsa_service.py             (A3)  orchestrates encoding + A2 code + verification
│   │   └── api/
│   │       ├── __init__.py                (A3)
│   │       ├── main.py                    (A3)  FastAPI app, static frontend serving
│   │       ├── schemas.py                 (A3)  pydantic models = the API contract in A6
│   │       ├── routes_aes.py              (A3)
│   │       └── routes_rsa.py              (A3)
│   ├── scripts/
│   │   ├── benchmark_grover.py            (A1)
│   │   └── benchmark_shor.py              (A2)
│   └── tests/
│       ├── conftest.py                    (A3)  markers, shared fixtures
│       ├── test_aes_cipher.py             (A1)
│       ├── test_aes_grover.py             (A1)
│       ├── test_rsa_minirsa.py            (A2)
│       ├── test_rsa_shor.py               (A2)
│       ├── test_encoding.py               (A3)
│       ├── test_api.py                    (A3)
│       ├── test_e2e_aes.py                (A3)  every key x several messages, end to end
│       └── test_e2e_rsa.py                (A3)
│
└── frontend/                              (A4)  ← Agent 4 owns this whole folder
    ├── package.json, vite.config.ts, tsconfig.json, index.html
    └── src/
        ├── main.tsx, App.tsx, styles/
        ├── api/        client.ts, types.ts (mirror of A6), mocks/*.json
        ├── pages/      Home.tsx, SymmetricTest.tsx, PublicKeyTest.tsx, Readiness.tsx, About.tsx
        └── components/ (Stepper, BitInput, CiphertextView, InterceptionWall, BreachReport,
                         Histogram, CircuitViewer, VerificationChecklist, MathPanel,
                         PopTheHood, PrototypeNotice, ...)
```

**Python package root:** `backend/` is the project root for Python.
- Install with `pip install -e "backend[dev]"`.
- Run tests from `backend/` with `pytest`.
- Imports always look like `from qbreak.aes.cipher import encrypt_nibble`.

**Dependencies:** the skeleton's `pyproject.toml` already contains every dependency anyone needs. If you truly need a new package, ask Agent 3; do not edit `pyproject.toml` yourself. Agent 4 manages `frontend/package.json` freely.

**pytest markers:** `slow` is for exhaustive or 6–8-bit / N ≥ 21 tests. CI runs `pytest -m "not slow"`. Run everything locally before the final merge.

---

## A5. Python module contracts (the code-level interfaces between agents)

These signatures are **binding**. Owners implement them exactly; consumers rely on them exactly. You may add extra private helpers, but you may not rename or reshape these.

### A5.1 `qbreak/common/simulator.py` (Agent 3; ships in the skeleton, exact code)

```python
from __future__ import annotations
import os, threading, time
from dataclasses import dataclass
from qiskit import QuantumCircuit, transpile
from qiskit_aer import AerSimulator

_SIM = AerSimulator()
_GATE = threading.Semaphore(int(os.getenv("QBREAK_MAX_CONCURRENT_SIMS", "1")))

@dataclass
class SimRun:
    counts: dict[str, int]          # MSB-first bitstrings of the single classical register
    transpiled: QuantumCircuit      # the circuit actually executed by Aer
    sim_time_ms: float
    shots: int

def run_circuit(qc: QuantumCircuit, shots: int = 1024, seed: int | None = None) -> SimRun:
    """Transpile for Aer and run. qc must have exactly one classical register."""
    if len(qc.cregs) != 1:
        raise ValueError("run_circuit expects exactly one classical register")
    with _GATE:
        t0 = time.perf_counter()
        tqc = transpile(qc, _SIM, optimization_level=0)
        result = _SIM.run(tqc, shots=shots, seed_simulator=seed).result()
        elapsed = (time.perf_counter() - t0) * 1000
    return SimRun(counts=dict(result.get_counts()), transpiled=tqc,
                  sim_time_ms=elapsed, shots=shots)
```

### A5.2 `qbreak/common/encoding.py` (Agent 3)

```python
def text_to_nibbles(text: str) -> list[int]
def nibbles_to_text(nibbles: list[int]) -> str            # raises ValueError if invalid UTF-8
def text_to_chunks(text: str, bits: int = 3) -> tuple[list[int], int]   # (chunks, bit_length)
def chunks_to_text(chunks: list[int], bit_length: int, bits: int = 3) -> str
def key_str_to_int(key: str, key_bits: int) -> int        # validates length + chars
def int_to_key_str(key: int, key_bits: int) -> str
```

### A5.3 `qbreak/aes/cipher.py` (Agent 1)

```python
SBOX: tuple[int, ...]       # 16 entries (spec in Agent 1 section, also below)
INV_SBOX: tuple[int, ...]
RCON: int = 0x3

def round_keys(key: int, key_bits: int) -> tuple[int, int]          # (K0, K1)
def encrypt_nibble(p: int, key: int, key_bits: int) -> int
def decrypt_nibble(c: int, key: int, key_bits: int) -> int
def encrypt_nibbles(ps: list[int], key: int, key_bits: int) -> list[int]
def decrypt_nibbles(cs: list[int], key: int, key_bits: int) -> list[int]
def trace_encrypt_nibble(p: int, key: int, key_bits: int) -> list[dict]
    # [{"step": "AddRoundKey K0", "value": int, "detail": str}, ...] for the UI explainer
def matching_keys(pairs: list[tuple[int, int]], key_bits: int) -> list[int]
    # CLASSICAL brute force. ONLY for tests and verification displays. NEVER used by the attack.
```

**MiniAES cipher definition** (everyone should know it; Agent 1 implements it):
- Block: 4 bits. One round.
- `K0 = key & 0xF`
- `H = (key >> (key_bits - 4)) & 0xF`, `K1 = rotl4(H, 1) ^ RCON`
- Encryption: `x = p ^ K0` → `s = SBOX[x]` → `y = rotl4(s, 1)` → `c = y ^ K1`
- Steps, in AES vocabulary: AddRoundKey → SubNibble → RotateBits (a stand-in for ShiftRows/MixColumns) → AddRoundKey.
- `rotl4(v, 1) = ((v << 1) | (v >> 3)) & 0xF`
- `SBOX = (0xE,0x4,0xD,0x1,0x2,0xF,0xB,0x8,0x3,0xA,0x6,0xC,0x5,0x9,0x0,0x7)` (the S-box from the educational Mini-AES by R. Phan, 2002)

### A5.4 `qbreak/aes/grover.py` (Agent 1)

```python
@dataclass
class GroverAttempt:
    iterations: int
    counts: dict[str, int]
    verified_keys: list[int]

@dataclass
class GroverResult:
    key_bits: int
    pairs_used: list[tuple[int, int]]          # (plain_nibble, cipher_nibble) pairs IN the circuit
    iterations: int                            # iterations of the attempt that succeeded (or last tried)
    counts: dict[str, int]                     # counts of that attempt, MSB-first key bitstrings
    candidate_keys: list[int]                  # measured candidates considered (before verification)
    recovered_keys: list[int]                  # candidates that verify against ALL known pairs
    circuit: QuantumCircuit                    # logical circuit (boxed Oracle/Diffuser gates)
    transpiled: QuantumCircuit
    sim_time_ms: float
    attempts: list[GroverAttempt]
    explain_circuits: list[tuple[str, QuantumCircuit]]  # [("One Grover iteration", ...), ("Oracle", ...), ("Diffuser", ...)]
    register_roles: dict[str, str]             # {"key": "...", "work": "...", "sbox": "...", "flag": "..."}

def select_known_pairs(known_plain: list[int], cipher: list[int], key_bits: int,
                       max_pairs: int | None = None) -> list[tuple[int, int]]
def build_oracle(pairs: list[tuple[int, int]], key_bits: int) -> QuantumCircuit
def build_diffuser(key_bits: int) -> QuantumCircuit
def optimal_iterations(key_bits: int, num_solutions: int = 1) -> int
def build_grover_circuit(pairs: list[tuple[int, int]], key_bits: int, iterations: int) -> QuantumCircuit
def run_grover_attack(known_plain: list[int], cipher: list[int], key_bits: int,
                      shots: int = 1024, seed: int | None = None) -> GroverResult
```

Note that the signature of `run_grover_attack` has **no key parameter**. That is the point.

### A5.5 `qbreak/rsa/minirsa.py` (Agent 2; the victim side)

```python
@dataclass
class RSAKeyPair:
    n: int; e: int; d: int; p: int; q: int; phi: int
    e_equals_d: bool

SUPPORTED_MODULI: dict[int, tuple[int, int]]   # victim-side table, e.g. {15: (3, 5), 21: (3, 7), ...}

def generate_keypair(n: int) -> RSAKeyPair          # ValueError if n not in SUPPORTED_MODULI
def encrypt_chunks(chunks: list[int], n: int, e: int) -> list[int]
def decrypt_chunks(cipher: list[int], n: int, d: int) -> list[int]
def private_exponent(p: int, q: int, e: int) -> tuple[int, int]   # (d, phi) from factors (attacker uses this after Shor)
```

### A5.6 `qbreak/rsa/shor.py` (Agent 2; the attacker side; must NOT import `minirsa`)

```python
@dataclass
class ShorAttempt:
    a: int
    measured: str            # bitstring of counting register
    y: int
    phase: float             # y / 2^t
    fraction: str            # e.g. "1/4"
    r_candidate: int | None
    ok: bool
    reason: str              # human-readable: why accepted / rejected

@dataclass
class ShorResult:
    n: int
    a: int                   # base that succeeded (or last tried)
    period: int | None
    factors: tuple[int, int] | None
    counts: dict[str, int]   # counts for the circuit of the successful/last base
    n_count: int             # counting qubits t
    n_work: int              # work qubits
    attempts: list[ShorAttempt]
    circuit: QuantumCircuit
    transpiled: QuantumCircuit
    sim_time_ms: float
    construction: str        # "textbook-swaps" or "permutation-unitary"
    explain_circuits: list[tuple[str, QuantumCircuit]]   # e.g. [("Controlled U^(2^0)", ...), ("Inverse QFT", ...)]
    register_roles: dict[str, str]

SHOR_SUPPORTED_N: tuple[int, ...]     # moduli whose circuits are implemented + tested

def choose_bases(n: int, seed: int | None = None) -> list[int]
def inverse_qft(t: int) -> QuantumCircuit
def build_period_finding_circuit(a: int, n: int, n_count: int | None = None,
                                 construction: str = "auto") -> QuantumCircuit
def candidate_periods(counts: dict[str, int], n_count: int, n: int, a: int) -> list[ShorAttempt]
def factors_from_period(a: int, r: int, n: int) -> tuple[int, int] | None
def run_shor_attack(n: int, a: int | None = None, shots: int = 1024,
                    seed: int | None = None, max_bases: int = 4) -> ShorResult
```

### A5.7 `qbreak/common/evidence.py` (Agent 3)

This module converts `GroverResult` and `ShorResult` objects into the JSON `CircuitInfo` and `Measurement` objects from A6. It needs nothing extra from Agents 1 and 2 beyond the dataclass fields above.

### A5.8 `qbreak/config.py` (Agent 3)

```python
ENABLED_KEY_BITS: list[int]  # env QBREAK_KEY_BITS, default "4"        e.g. "4,6,8"
ENABLED_MODULI: list[int]    # env QBREAK_MODULI,   default "15"       e.g. "15,21"
MAX_SHOTS = 4096
MAX_AES_TEXT_CHARS = 200
MAX_RSA_TEXT_CHARS = 80
```

A larger size (6- or 8-bit keys, N = 21, and so on) is turned on **only** after its owner's benchmark proves it runs in under about 20 seconds on the deployed machine.

---

## A6. HTTP API contract (Agent 3 implements, Agent 4 consumes)

- Base path: `/api`. All JSON.
- Errors use HTTP 400 or 422 with `{"detail": "<human readable message>"}`.
- In development the frontend proxies `/api` to `http://localhost:8000`. In production the API and frontend share one origin.

### Shared objects

```jsonc
// CircuitInfo
{
  "num_qubits": 14,
  "num_clbits": 4,
  "depth": 9,                       // logical circuit depth (boxed gates count as 1)
  "transpiled_depth": 1840,         // depth of what Aer actually ran
  "gate_counts": {"mcx": 410, "cx": 96, "x": 300, "h": 40},   // transpiled
  "registers": [{"name": "key", "size": 4, "role": "Candidate key, in superposition"}],
  "drawings": [{"title": "Full attack circuit", "text": "<qiskit text drawing>"},
               {"title": "Oracle", "text": "..."}],
  "qasm": "OPENQASM 3.0; ..."       // or null if export failed; truncated at 200 kB
}

// Measurement
{
  "shots": 1024,
  "counts": {"1001": 961, "0011": 7},
  "top": [{"bitstring": "1001", "value": 9, "count": 961, "probability": 0.938,
           "meaning": "key 1001"}]   // at most 16 entries, sorted by count desc
}

// VerificationStep
{"name": "Re-encrypt known block 1", "passed": true, "detail": "P=0x4 → C=0x3 with key 1001 ✓"}
```

### Endpoints

**`GET /api/health`** → `{"status": "ok"}`

**`GET /api/config`**
```json
{"aes_key_bits": [4], "rsa_moduli": [15], "max_shots": 4096,
 "max_aes_text_chars": 200, "max_rsa_text_chars": 80, "default_known_prefix_chars": 3}
```

**`POST /api/aes/encrypt`** (victim side)
```jsonc
// request
{"plaintext": "Hi judges!", "key": "1001", "key_bits": 4}
// response
{
  "key_bits": 4,
  "plaintext_nibbles": [4, 8, 6, 9, 2, 0, 6, 10, 7, 5, 6, 4, 6, 7, 6, 5, 7, 3, 2, 1],
  "ciphertext_nibbles": [3, 8, 14, 13, 9, 5, 14, 2, 0, 10, 14, 3, 14, 0, 14, 10, 0, 12, 9, 6],
  "ciphertext_hex": "38ed95e20ae3e0ea0c96",
  "byte_length": 10,
  "trace": [{"step": "Input P", "value": 4, "detail": "0100"},
            {"step": "AddRoundKey K0", "value": 13, "detail": "0100 ⊕ 1001 = 1101"}, ...]  // first block
}
```

**`POST /api/aes/attack`** (attacker side; **no key field exists**)
```jsonc
// request
{"key_bits": 4, "known_plaintext": "Hi ", "ciphertext_nibbles": [3, 8, 14, 13, ...],
 "shots": 1024, "seed": null}
// response
{
  "key_bits": 4,
  "search_space": 16,
  "pairs_used": [{"plain": 4, "cipher": 3}, {"plain": 8, "cipher": 8}],
  "iterations": 3,
  "optimal_iterations_formula": "⌊π/4 · √(16/1)⌋ = 3",
  "recovered_keys": ["1001"],
  "unique": true,
  "key": "1001",                       // null if not unique or none found
  "decrypted_text": "Hi judges!",      // null if key is null
  "decrypted_nibbles": [4, 8, ...],
  "candidate_decryptions": [{"key": "1001", "text": "Hi judges!"}],  // one per recovered key; text null if invalid UTF-8
                                       // (when several keys fit the crib, the UI shows each so the user sees which reads correctly)
  "attempts": [{"iterations": 3, "verified_keys": ["1001"]}],
  "sim_time_ms": 412.5,
  "circuit": { /* CircuitInfo */ },
  "measurement": { /* Measurement */ },
  "verification": [ /* VerificationStep[] */ ],
  "warnings": ["Known prefix produced only 2 distinct blocks; ..."]
}
```

**`POST /api/rsa/keygen`** (victim side)
```jsonc
// request
{"n": 15}
// response
{"n": 15, "e": 3,
 "victim_secret": {"p": 3, "q": 5, "phi": 8, "d": 3},   // shown only behind a "reveal" toggle; never sent to /attack
 "e_equals_d": true,
 "warnings": ["At N=15 the public and private exponents are equal (e = d = 3). ..."]}
```

**`POST /api/rsa/encrypt`**
```jsonc
// request
{"plaintext": "Hi", "n": 15, "e": 3}
// response
{"plaintext_chunks": [2, 2, 0, 6, 4, 4], "bit_length": 16, "chunk_bits": 3,
 "ciphertext": [8, 8, 0, 6, 4, 4]}
// "Hi" = 0x48 0x69 = 01001000 01101001 → 010|010|000|110|100|1(00) → [2,2,0,6,4,4]; x^3 mod 15
```

**`POST /api/rsa/attack`** (attacker side; **no p, q, d, or phi fields exist**)
```jsonc
// request
{"n": 15, "e": 3, "ciphertext": [8, 8, 0, 6, 4, 4], "bit_length": 16,
 "a": null, "shots": 1024, "seed": null}
// response
{
  "n": 15, "a": 7, "period": 4,
  "factors": [3, 5],
  "phi": 8, "d": 3,
  "decrypted_text": "Hi",
  "n_count": 8, "n_work": 4,
  "construction": "textbook-swaps",
  "attempts": [{"a": 7, "measured": "01000000", "y": 64, "phase": 0.25, "fraction": "1/4",
                "r_candidate": 4, "ok": true, "reason": "7^4 mod 15 = 1; r even; 7^2 mod 15 = 4 ≠ 14"}],
  "sim_time_ms": 230.1,
  "circuit": { /* CircuitInfo */ },
  "measurement": { /* Measurement */ },
  "verification": [ /* VerificationStep[] */ ],
  "warnings": ["e = d at this modulus; demonstration of factor recovery only."]
}
```

(The AES encrypt and RSA encrypt examples above are exact and can be used as test vectors. Other numbers, such as counts, depths, and timings, are illustrative.)

---

## A7. Git workflow

1. **H+0:00 to H+0:30:** Agent 3 pushes the **skeleton commit directly to `main`** and tags it `skeleton`. The skeleton contains: `pyproject.toml`, `qbreak/__init__.py`, `qbreak/common/` (with `simulator.py` complete and `encoding.py` complete), `config.py`, `tests/conftest.py`, `.gitignore`, `docs/agents/*.md`, and a minimal `api/main.py` with `/api/health`.
   - The skeleton does **not** create anything inside `qbreak/aes/`, `qbreak/rsa/`, or `frontend/`. Those folders belong to their owners. The one exception is an empty `frontend/.gitkeep`, which keeps the Docker build working before the frontend exists.
2. While waiting for the skeleton, Agents 1, 2, and 4 read this file, plan, and set up local environments (Python venv / Node). After the skeleton lands:
   `git checkout main && git pull && git checkout -b feat/<yours>`
3. Commit small and often. Push your branch at least every hour.
4. **Rebase onto main** whenever main changes: `git fetch origin && git rebase origin/main`.
5. Merge through **pull requests into `main`**. Agent 3's human reviews and merges. A PR merges only if:
   - `pytest -m "not slow"` passes, and `npm run build` passes if the frontend is affected.
   - It touches **only** files the author owns.
   - Its description lists what works, what's next, and any request for another agent.
6. Merge at every milestone, not at the end. **Feature freeze at H+14:00.** After that, only bug fixes.
7. Never force-push `main`. Never commit `.venv`, `node_modules`, `dist`, or `__pycache__`.

---

## A8. 16-hour timeline and checkpoints (H = hackathon start)

| Time | Agent 1 (Grover) | Agent 2 (Shor) | Agent 3 (API/verify/deploy) | Agent 4 (Frontend) |
|---|---|---|---|---|
| H+0:00–0:30 | read, plan, venv | read, plan, venv | **skeleton → main** | read, plan, scaffold Vite locally |
| H+0:30–2:00 | classical cipher + tests | classical MiniRSA + tests | schemas, encoding, routes with fake services, **first deploy (health only)** | layout, routing, mock API, Home, symmetric-test configure stage |
| H+2:00–5:00 | 4-bit oracle, diffuser, attack | N=15 circuit, post-processing, attack | services, verification, evidence | intercept + breach-test stages, Breach Report, histogram, circuit viewer |
| **H+5:00** | **Checkpoint A:** 4-bit Grover merged | **Checkpoint A:** N=15 Shor merged | wire real modules | public-key test on mocks |
| H+5:00–9:00 | test every key; bug fixes; start 6-bit | N=21 build + benchmark | e2e tests, deploy full app | switch to real API, Pop the Hood (all 6 sections) |
| **H+9:00** | **Checkpoint B: both modules end to end in the DEPLOYED app (the guaranteed demo)** | | | |
| H+9:00–13:00 | 6-bit → 8-bit + benchmarks | N=21 enable → dynamic set (33, 35, …) | enable sizes via config, perf caps, exhaustive slow tests | polish, explainers, honesty page, mobile |
| **H+13:00** | **Checkpoint C:** stretch merged | **Checkpoint C** | final integration | final polish |
| H+14:00 | **FEATURE FREEZE** | | | |
| H+14:00–16:00 | bug fixes only, demo rehearsal, final deploy, wake the server before judging | | | |

If you fall behind, **protect Checkpoint B**: a fully working N=15 and 4-bit demo beats a half-working 8-bit one.

---

# PART B — YOUR ROLE: AGENT 1 · GROVER / MiniAES

**Branch:** `feat/grover`
**You own:** `backend/qbreak/aes/__init__.py`, `backend/qbreak/aes/cipher.py`, `backend/qbreak/aes/grover.py`, `backend/tests/test_aes_cipher.py`, `backend/tests/test_aes_grover.py`, `backend/scripts/benchmark_grover.py`.
**You must not touch** anything else. In particular you do not write FastAPI code, encoding code, or frontend code. Agent 3 wraps your functions in the API; Agent 4 displays your results.

Your job is the heart of the symmetric half of the demo. You build the toy cipher, then build a **genuine** Grover attack whose oracle executes that cipher reversibly on a superposition of all keys. Your milestones match locked build-order items 1 and 4.

## B1. Deliverables, in order

| # | Deliverable | Merge by |
|---|---|---|
| 1 | `cipher.py` complete + `test_aes_cipher.py` green | H+2:00 (PR #1, small, merge early so Agent 3 can wire the encrypt endpoint) |
| 2 | `grover.py` for **4-bit keys** + `test_aes_grover.py` green, every one of the 16 keys recovered | **H+5:00 (Checkpoint A)** |
| 3 | Bug fixes from integration, robust multi-solution handling | H+9:00 |
| 4 | `benchmark_grover.py`; **6-bit** passing + timing table in PR | ~H+11:00 |
| 5 | **8-bit** passing + timing table in PR | H+13:00 (Checkpoint C) |

Your code must be **generic in `key_bits` from the start**. 6 and 8 bits should only need testing and benchmarking, not a rewrite.

## B2. `cipher.py`: exact specification

Implement exactly the cipher in A5.3. Everything is integer bit-twiddling.

```python
SBOX = (0xE, 0x4, 0xD, 0x1, 0x2, 0xF, 0xB, 0x8, 0x3, 0xA, 0x6, 0xC, 0x5, 0x9, 0x0, 0x7)
INV_SBOX = tuple(SBOX.index(i) for i in range(16))
RCON = 0x3

def _rotl4(v): return ((v << 1) | (v >> 3)) & 0xF
def _rotr4(v): return ((v >> 1) | (v << 3)) & 0xF

def round_keys(key, key_bits):
    # validate key_bits in (4, 6, 8) and 0 <= key < 2**key_bits, else ValueError
    k0 = key & 0xF
    h = (key >> (key_bits - 4)) & 0xF
    k1 = _rotl4(h) ^ RCON
    return k0, k1

# encrypt:  x = p ^ K0 ; s = SBOX[x] ; y = rotl4(s) ; c = y ^ K1
# decrypt:  y = c ^ K1 ; s = rotr4(y) ; x = INV_SBOX[s] ; p = x ^ K0
```

Notes:
- For 4-bit keys, H = K0 = the whole key. For 6-bit keys, K0 is bits 0–3 and H is bits 2–5, so they overlap. For 8-bit keys, K0 is the low nibble and H is the high nibble. Every key bit affects the cipher.
- `trace_encrypt_nibble` returns 5 steps for the UI explainer. Each `detail` is a short human string using MSB-first binary:
  - `Input P` (e.g. `"0100"`)
  - `AddRoundKey K0` (`"0100 ⊕ 1001 = 1101"`)
  - `SubNibble` (`"S[1101] = 1001"`)
  - `RotateBits` (`"rotl(1001) = 0011"`)
  - `AddRoundKey K1` (`"... ⊕ K1 = ..."`)
- `matching_keys(pairs, key_bits)` is a classical brute force. It exists only so **tests** can compute ground truth. `grover.py` must never call it. Agent 3's tests will monkeypatch it to raise an error during the attack, to prove this.

**Facts already verified for this exact cipher** (use them to sanity-check your tests):
- For every key size, every key produces a **different** permutation of the 16 nibbles. No two keys are equivalent, so a long enough crib always gives a unique key.
- The average number of keys matching *d* distinct known (p, c) pairs:

  | key bits | d=1 pair | d=2 | d=3 |
  |---|---|---|---|
  | 4 | 1.25 (worst 2) | 1.02 (worst 2) | 1.00 (worst 1) |
  | 6 | 4.5 (worst 6) | 1.63 (worst 4) | 1.14 (worst 4) |
  | 8 | 16 (worst 16) | 3.4 (worst 8) | 1.44 (worst 4) |

  So Grover must handle **more than one solution** (M > 1). The final answer also needs a classical filter against **all** crib pairs.

### `test_aes_cipher.py` must cover
- `decrypt(encrypt(p)) == p` for all 16 p × all keys × key_bits ∈ {4, 6, 8}.
- `encrypt_nibble(·, key)` is a bijection for every key.
- All 2^k keys give distinct permutations (the fact above).
- One hand-computed vector you work out on paper. For example, key `1001`, p = `0x4`: x = 0100 ⊕ 1001 = 1101 → S[1101] = 1001 → rotl = 0011 → K1 = rotl(1001) ⊕ 0011 = 0011 ⊕ 0011 = 0000 → c = 0011 = 0x3. Assert `encrypt_nibble(0x4, 0b1001, 4) == 0x3`.
- `trace_encrypt_nibble` ends with the same value as `encrypt_nibble`.
- Invalid key or key_bits raises `ValueError`.

## B3. The Grover attack: design (follow this)

### Inputs
`run_grover_attack(known_plain, cipher, key_bits, shots, seed)` receives:
- the known-plaintext prefix as nibbles,
- the full ciphertext nibbles,
- the key size.

Nothing else. **There is no key argument.**

### Step 1: `select_known_pairs`
- Zip `known_plain` with the first `len(known_plain)` ciphertext nibbles.
- Deduplicate on the plaintext nibble. The cipher is ECB, so a repeated plaintext nibble always gives the same ciphertext nibble, and repeats add no information.
- Keep the first `max_pairs` distinct pairs. The default `max_pairs` is `{4: 2, 6: 3, 8: 3}[key_bits]`.
- If the known prefix is shorter than the ciphertext, also check that consistent repeats agree (same p → same c). If they conflict, raise `ValueError("Known plaintext is inconsistent with ciphertext")`.
- If no pairs are available, raise `ValueError`.

### Step 2: registers (order matters for drawing readability)

| Register | Size | Role |
|---|---|---|
| `key` | key_bits | Candidate key, in uniform superposition |
| `work` | 4 | Holds x = p ⊕ K0 for the pair currently being checked |
| `sbox` | 4 | Holds s = SBOX[x] (out-of-place S-box output) |
| `match` | number of pairs | Bit i = 1 iff pair i matches |
| `flag` | 1 | Phase-kickback qubit prepared in \|−⟩ |
| classical `c` | key_bits | Measurement of the key register only |

**Reuse `work` and `sbox` for every pair.** Compute pair i, write its result into `match[i]`, then **uncompute** `work` and `sbox` back to |0⟩ before the next pair. This keeps the qubit count at `key_bits + 8 + pairs + 1`:

| key bits | pairs in circuit | qubits | Grover iterations (M = 1) |
|---|---|---|---|
| 4 | 2 | 15 | 3 |
| 6 | 3 | 18 | 6 |
| 8 | 3 | 20 | 12 |

These are all comfortable for an Aer statevector (20 qubits is about 16 MB).

### Step 3: the per-pair "compute" block for pair (p, c)

Use the convention: qubit i of a register = bit i (LSB = qubit 0).

1. **Load p and add K0:** for each bit i of p equal to 1, apply `x(work[i])`. Then `cx(key[i], work[i])` for i = 0..3. Now `work = p ⊕ K0`.
2. **SubNibble as a reversible lookup table**, written out of place into `sbox`. For each input value v = 0..15, and for each output bit j where `SBOX[v]` has a 1:
   - flip (X) the `work` qubits where v has a 0,
   - apply `mcx(work[0..3], sbox[j])`,
   - un-flip the same qubits.

   (Optimisation: group all the targets for one v inside a single X-sandwich.) This is a textbook QROM-style lookup and is easy to explain on stage: "for each of the 16 possible inputs, write its S-box output".
3. **RotateBits costs no gates.** It is just a relabelling. Output bit i of y is `sbox[(i − 1) mod 4]`.
4. **AddRoundKey K1 and compare with c:**
   - H_j is key bit `key_bits − 4 + j`, and K1 bit i = H_{(i−1) mod 4} ⊕ RCON_i.
   - Working through the algebra, the pair matches iff for every j ∈ {0, 1, 2, 3}:
     `s_j ⊕ H_j = t_j`, where `t_j = RCON_{(j+1) mod 4} ⊕ c_{(j+1) mod 4}` (a classical constant).

   So:
   - (a) `cx(key[key_bits − 4 + j], sbox[j])` for each j,
   - (b) `x(sbox[j])` wherever t_j = 0,
   - (c) `mcx(sbox[0..3], match[i])`.

   This formula has been **verified exhaustively** against the classical cipher: it is true exactly when `encrypt_nibble(p, k) == c`, for every p, k, c and every key size. Write your own unit test that checks this too.
5. **Uncompute:** apply steps (4b), (4a), (2), (1) in reverse (each gate here is its own inverse; reverse the order). Do **not** uncompute `match[i]`. The cleanest approach is to build steps 1–4b as a sub-circuit `compute_i`, then do `compute_i`, `mcx → match[i]`, `compute_i.inverse()`.

### Step 4: the oracle (`build_oracle`)
- For each pair: compute → write match[i] → uncompute.
- Then `mcx(match[all], flag)`. With the flag in |−⟩, this flips the phase of every key that matches **all** in-circuit pairs.
- Then repeat the per-pair blocks to **uncompute `match`** (same sequence as before, in reverse order).
- Return it as a `QuantumCircuit` over the registers (key, work, sbox, match, flag). Label it `"Oracle"` when converted with `.to_gate()`.

### Step 5: the diffuser (`build_diffuser`)
Standard Grover diffuser on the key register only: H, X on all → multi-controlled Z (H on last, mcx, H on last) → X, H on all. Label it `"Diffuser"`.

### Step 6: `build_grover_circuit(pairs, key_bits, iterations)`
- H on all key qubits.
- Prepare flag in |−⟩ (`x(flag)`, `h(flag)`).
- Repeat `iterations` times: append Oracle gate, then Diffuser gate.
- Measure `key[i] → c[i]`.

There must be exactly one classical register (A2 rule), so the count keys come out as MSB-first key strings.

### Step 7: `optimal_iterations(key_bits, M) = max(1, floor(π/4 · sqrt(2**key_bits / M)))`
Values: 16/1 → 3, 64/1 → 6, 256/1 → 12.

### Step 8: unknown number of solutions (`run_grover_attack`)
The attacker does not know how many keys match the in-circuit pairs (M), so try the schedule M_guess ∈ [1, 2, 4, 8], skipping guesses that give the same iteration count as an earlier one. For each guess:
1. Build and run the circuit with `iterations = optimal_iterations(key_bits, M_guess)`. Use `qbreak.common.simulator.run_circuit(qc, shots, seed)`.
2. **Candidate keys** = measured bitstrings whose count ≥ max(2, 0.02 · shots), sorted by count.
3. **Verify** each candidate classically with `encrypt_nibble` against the **in-circuit pairs** → `verified_keys`. This is legitimate: checking a guessed key is what a real attacker does.
4. Record a `GroverAttempt`.
5. Stop at the first attempt whose verified keys together hold ≥ 40% of the shots. If no attempt reaches that, use the attempt with the most verified probability mass.

Then compute `recovered_keys`: the verified keys from the chosen attempt that **also** encrypt every pair in the full known prefix correctly (the extra pairs that were not in the circuit). Sort them by count. Fill every `GroverResult` field. In particular:
- `circuit` is the logical circuit with boxed `"Oracle"` and `"Diffuser"` gates.
- `transpiled` comes from `SimRun`.
- `explain_circuits` = `[("One Grover iteration", ...), ("Oracle (decomposed)", oracle_circuit), ("Diffuser", diffuser_circuit)]`.
- `register_roles` = plain-English one-liners per register, which the UI shows.

**The probability check you should see:** for 4-bit keys with M = 1 and 3 iterations, the correct key should get about 96% of the shots (sin²(7·θ) with sin θ = 1/4). If you see roughly uniform counts, your oracle is not uncomputing cleanly, or your bit order is wrong.

## B4. `test_aes_grover.py` (mark 6- and 8-bit cases `@pytest.mark.slow`)
- **The oracle is correct as a phase oracle, without measurement.**
  - Build the oracle alone for a few random pair sets.
  - For every basis key k, prepare |k⟩ with ancillas at |0⟩ and the flag in |−⟩, apply the oracle, and use `qiskit.quantum_info.Statevector` (fine for ≤ 15 qubits; for 4-bit only) to check that the ancillas return to |0⟩ and the phase is −1 exactly for `matching_keys(...)`.
  - A cheaper alternative: build the oracle **without** the flag mcx, put the key in a basis state, measure `match`, and compare with `matching_keys`.
- **Every 4-bit key is recovered:** for each of the 16 keys and 3 different messages, encrypt with the cipher, call `run_grover_attack` with a fixed seed and a 3-character crib, and assert the true key ∈ `recovered_keys`. If `len(recovered_keys) > 1`, assert they all fit every crib pair.
- **The attack is blind to the key:**
  - `inspect.signature(run_grover_attack)` has no parameter containing `"key"` except `key_bits`.
  - Monkeypatch `qbreak.aes.cipher.matching_keys` to raise during the attack; the attack must still succeed.
- **Iteration counts** are correct for 4, 6, and 8 bits.
- **Qubit counts** match the table above.
- **Slow tests:** 8 random keys each at 6 and 8 bits recovered.

## B5. `benchmark_grover.py`
- CLI: `python scripts/benchmark_grover.py --bits 4 6 8 --trials 5`.
- For each size, print a table: qubits, logical depth, transpiled depth, mcx count, mean / max simulation ms, success rate, and peak RSS memory (`resource.getrusage`).
- Paste this table in your PRs. Agent 3 enables 6- or 8-bit keys in production only if they run in under about 20 s with ≤ 400 MB RSS.
- If 8-bit is too slow, try these in order:
  1. `AerSimulator(method="statevector")` (no change needed in your code). Tell Agent 3 if it helps, because `run_circuit` is theirs.
  2. Fewer shots (512).
  3. 2 pairs instead of 3. More solutions are fine; your M schedule and the classical filter handle them.

## B6. Pitfalls
- **Bit order** is the number-one bug. Qubit i = bit i. Count key strings are MSB first. Test with a non-symmetric key like `0001`.
- Forgetting to uncompute `work`, `sbox`, or `match` leaves garbage entangled with the key register and silently destroys interference.
- `mcx` with a list of controls: `qc.mcx([q0, q1, q2, q3], target)`.
- Do not create an `AerSimulator` yourself; call `run_circuit`.
- Do not use `qiskit.circuit.library.GroverOperator` or `ZGate().control()`. Hand-building the oracle and diffuser is the point, and judges will ask about them.

## B7. Definition of done
- All 16 four-bit keys recovered in tests with fixed seeds.
- 6- and 8-bit slow tests pass, and benchmark tables are posted.
- No call from `grover.py` to `matching_keys` or anything else that knows the key.
- Docstrings explain each register and each oracle step in plain English. Agent 4 will copy your wording into the UI explainers, so write it for a curious non-expert.
