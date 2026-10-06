# Q-Break — Agent 3 build prompt: API, Verification, Integration & Deployment

> **You are Agent 3 of 4.** Your human teammate will paste this whole file to you as your only brief. You will build **the repo skeleton, FastAPI layer, verification, end-to-end tests, and deployment**, on branch `feat/api`.
>
> **How to use this file:** read Part A (shared by all four agents) in full, then Part B (your role). Part A is identical in all four files, so every agent shares the same contracts. When Part A and Part B seem to conflict, Part A's contracts (A5, A6) win; raise the conflict with your human.
>
> **Start now:** confirm the skeleton is on `main` (`git pull`). If it isn't there yet — you are the one who creates it, so start with B2. Then work through your B1 deliverables in order, committing small and opening PRs at each milestone.

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

# PART B — YOUR ROLE: AGENT 3 · API, VERIFICATION, INTEGRATION & DEPLOYMENT

**Branch:** you push the **skeleton directly to `main`** at H+0:30. After that, everything goes through `feat/api` (or short-lived `feat/api-*` branches) and PRs.
**You own:** every file in the repo that is not inside `backend/qbreak/aes/`, `backend/qbreak/rsa/`, `frontend/`, or the six A1/A2 test and script files. That includes: root files, `docs/`, CI, Docker, `pyproject.toml`, `qbreak/common/**`, `qbreak/config.py`, `qbreak/verification/**`, `qbreak/services/**`, `qbreak/api/**`, `tests/conftest.py`, `tests/test_encoding.py`, `tests/test_api.py`, `tests/test_e2e_*.py`.

You are the **integrator**. Your human is the one who reviews and merges every PR. You turn Agents 1 and 2's pure functions into a verified, deployed product that Agent 4 can call. Your milestone matches locked build-order item 3 ("complete end-to-end verification"), plus you own the deployment.

## B1. Deliverables, in order

| # | Deliverable | When |
|---|---|---|
| 1 | **Skeleton on `main`** (see B2), tagged `skeleton` | **H+0:30, hard deadline**. The other three agents are waiting for it |
| 2 | `schemas.py` (all of A6), all routes live with **mock services**, `test_api.py` | H+2:00 |
| 3 | Dockerfile + `render.yaml` + **first deploy** serving `/api/health` | H+2:30 |
| 4 | Real `aes_service` / `rsa_service`, verification, evidence | as soon as A1 and A2 merge (≈ H+5:00) |
| 5 | `test_e2e_aes.py` (all 16 keys) + `test_e2e_rsa.py`; full app deployed with the frontend | **H+9:00 (Checkpoint B)** |
| 6 | Enable 6/8-bit and N = 21/33/35 via config after benchmarks; abuse limits; README | H+13:00 |
| 7 | Release, demo rehearsal support, keep production warm | H+14:00–16:00 |

## B2. The skeleton commit (exact contents)

Create these files, and nothing in `aes/`, `rsa/`, or `frontend/`:

**`backend/pyproject.toml`**
```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "qbreak"
version = "0.1.0"
requires-python = ">=3.11,<3.13"
dependencies = [
  "qiskit>=2.0,<3",
  "qiskit-aer>=0.17",
  "numpy>=1.26",
  "fastapi>=0.115",
  "uvicorn[standard]>=0.30",
  "pydantic>=2.7",
]
[project.optional-dependencies]
dev = ["pytest>=8", "httpx>=0.27", "ruff>=0.6"]

[tool.setuptools.packages.find]
include = ["qbreak*"]

[tool.pytest.ini_options]
testpaths = ["tests"]
markers = ["slow: exhaustive or large-circuit tests (excluded in CI)"]
```

Also include:
- `qbreak/__init__.py`, `qbreak/common/__init__.py`, and `qbreak/common/simulator.py`, **exactly** as in A5.1.
- `qbreak/common/encoding.py`, fully implemented (B3) with `tests/test_encoding.py`.
- `qbreak/config.py` (A5.8).
- `qbreak/api/__init__.py` and `qbreak/api/main.py` with `/api/health`.
- `tests/conftest.py`.
- `.gitignore`: `.venv/`, `__pycache__/`, `*.egg-info/`, `node_modules/`, `frontend/dist/`, `.pytest_cache/`, `.env`.
- A short `README.md`.
- `docs/agents/` containing all four agent prompt files.
- `.github/workflows/ci.yml`.

Verify locally that `pip install -e "backend[dev]"` and `pytest` both work, then push and tell your human to announce "skeleton is on main".

**CI (`.github/workflows/ci.yml`):** on push and PR to main.
- **Job 1:** Python 3.11, `pip install -e "backend[dev]"`, `cd backend && pytest -m "not slow"`.
- **Job 2:** Node 20, but only if `frontend/package.json` exists (`if: hashFiles('frontend/package.json') != ''`). Runs `cd frontend && npm ci && npm run build`.

## B3. `encoding.py` (A5.2): exact behaviour
- `text_to_nibbles("Hi") == [4, 8, 6, 9]`, and `nibbles_to_text` reverses it. An odd number of nibbles, or invalid UTF-8, raises `ValueError` with a friendly message.
- `text_to_chunks("Hi") == ([2, 2, 0, 6, 4, 4], 16)`. `chunks_to_text([2, 2, 0, 6, 4, 4], 16) == "Hi"`.
  - Bits are taken MSB first per byte. The last chunk is right-padded with zeros, and `bit_length` drops that padding on decode.
- `key_str_to_int("1001", 4) == 9`. Wrong length or non-binary characters raise `ValueError`.
- Tests: round trips with ASCII, emoji (multi-byte UTF-8), the empty string (rejected at the API layer, but the encoding functions may accept it), and every 4-bit key string.

## B4. Pydantic schemas and routes
- Implement **every** request and response model in A6 exactly. Field names are a contract with Agent 4, so do not rename anything.
- Validation:
  - AES text: 1–`MAX_AES_TEXT_CHARS` characters. `key_bits` must be in `ENABLED_KEY_BITS`.
  - The key matches `^[01]+$` with length `key_bits`.
  - The known plaintext is 1 to len(text) characters, and its encoding must be a prefix of the ciphertext length.
  - `n` must be in `ENABLED_MODULI`. `shots` is 1–`MAX_SHOTS`.
  - RSA ciphertext values must be < n.
  - Violations → 422 with a readable `detail`.
- The AES `/attack` request model has **no key field**, and the RSA `/attack` model has no p, q, d, or phi fields. Set `model_config = ConfigDict(extra="forbid")` on attack requests, so a client sending a key gets a 422. Add a test for that.
- Run CPU-bound simulations off the event loop: `await run_in_threadpool(service_fn, ...)`. The semaphore in `simulator.py` limits concurrency.
- `GET /api/config` reads from `config.py`.

## B5. Mock mode (so Agent 4 is never blocked)
Until Agents 1 and 2 merge, the services import their modules inside `try/except ImportError`. If an import fails, return a **mock response** with exactly the A6 shape, realistic values, and `warnings: ["MOCK DATA — quantum module not merged yet"]`.

For the AES encrypt mock, you may use the exact test vector from A6. Remove mock mode at Checkpoint B.

## B6. Services (the orchestration layer)

**`aes_service.attack(req)`:**
1. `known = text_to_nibbles(req.known_plaintext)`.
2. Call `run_grover_attack(known, req.ciphertext_nibbles, key_bits, shots, seed)`.
3. For each recovered key, decrypt the full ciphertext and add it to `candidate_decryptions`. The text is `None` if decoding fails.
4. Set `unique = len(recovered_keys) == 1`, `key = recovered key if unique else None`, and the decrypted text from that key.
5. Build `optimal_iterations_formula`, e.g. `"⌊π/4 · √(16/1)⌋ = 3"`.
6. Build the verification steps (B7), the evidence (B8), and the warnings:
   - multiple keys → `"Several keys fit the known plaintext; supply a longer known prefix to disambiguate."`
   - only one distinct pair available → a weak-crib warning.

**`aes_service.encrypt(req)`:** encoding + `encrypt_nibbles` + `trace_encrypt_nibble` on the first nibble.

**`rsa_service.keygen`:** `generate_keypair`. Add a warning when `e_equals_d`: `"At N={n} the public and private exponents are equal (e = d = {e}). This is a demonstration of Shor's factor-recovery workflow, not a secure RSA example."`

**`rsa_service.encrypt`:** `text_to_chunks` + `encrypt_chunks`.

**`rsa_service.attack(req)`:**
1. Call `run_shor_attack(n, a, shots, seed)`.
2. If factors were found: `d, phi = private_exponent(p, q, e)` → `decrypt_chunks` → `chunks_to_text`.
3. If not: return 200 with factors `null` and the attempts showing why, so the UI can offer a retry with a different seed.
4. Always add a construction warning for `"permutation-unitary"`: `"Modular multiplication blocks are built from a classically computed permutation (standard for small demos)."`

**Victim/attacker separation is structural:**
- `services/*attack*` code paths must not import `minirsa.SUPPORTED_MODULI`, `generate_keypair`, or `matching_keys`.
- Write a test that monkeypatches those to raise, then calls the attack endpoints.

## B7. Verification (`verification/aes_checks.py`, `rsa_checks.py`)
Each check is a pure function that returns `VerificationStep(name, passed, detail)`. The details must show **real numbers**.

**AES:**
1. "Attacker input contains no key". This is a structural fact; the detail lists which fields the attacker received.
2. For each in-circuit pair: "Re-encrypt known block i" → `P=0x4 → C=0x3 with key 1001 ✓`.
3. "Recovered key fits all N known-prefix blocks".
4. "Key uniqueness": the number of keys that survived.
5. "Quantum signal": the probability on the recovered key vs the uniform baseline 1/2^k. E.g. `96.1% vs 6.25% uniform`; passes if more than 4× the baseline.
6. "Decrypted text is valid UTF-8 and starts with the known prefix".

**RSA:**
1. "Measured phase y/2^t → fraction s/r" (from the accepted attempt).
2. "a^r ≡ 1 (mod N)".
3. "r is even and a^(r/2) ≢ −1 (mod N)".
4. "p · q = N, both nontrivial".
5. "e · d ≡ 1 (mod φ)".
6. "Re-encrypting the decrypted chunks reproduces the ciphertext".
7. "Decrypted text is valid UTF-8".

## B8. Evidence (`common/evidence.py`)
- `circuit_info(logical, transpiled, register_roles, explain_circuits) -> dict`:
  - `num_qubits` / `num_clbits` / `depth` from the logical circuit; `transpiled_depth` and `gate_counts` (`dict(transpiled.count_ops())`) from the transpiled one.
  - `registers` from `logical.qregs` + `register_roles`.
  - `drawings`: the logical circuit first (`str(qc.draw(output="text", fold=-1))`), then each explain circuit, decomposed **once** (`qc.decompose()`) with `fold=120`. Truncate each drawing at 60 000 characters with a note.
  - `qasm`: `qiskit.qasm3.dumps(transpiled)` in `try/except` → `None` on failure (unitary gates may not export). Truncate at 200 kB.
- `measurement(counts, shots, interpret)`: build `top` as in A6. `interpret` maps a bitstring to `meaning`:
  - AES: `"key 1001"`, plus `" ✓ recovered"` when applicable.
  - RSA: `"y=64 → phase 0.25 → 1/4"`.

## B9. Tests you own
- `test_api.py`: every endpoint's happy path, validation errors, `extra="forbid"` on attack requests, and `/api/config`.
- `test_e2e_aes.py`:
  - **all 16 four-bit keys** × messages `["Hi judges!", "Quantum ☕", "aaaa"]` → encrypt endpoint → attack endpoint (crib = first 3 characters, fixed seed) → the true key is in `recovered_keys`, and if unique, the decrypted text equals the input.
  - The `slow` mark covers a sample of 6- and 8-bit keys.
  - Note: `"aaaa"` gives only 2 distinct nibbles, a deliberately weak crib. Assert the behaviour is correct, whether that is a unique key or a clearly reported ambiguity.
- `test_e2e_rsa.py`: for each enabled N, keygen → encrypt "Hi judges!" → attack with no factors given → the decrypted text equals the input. N ≥ 21 is marked `slow`.
- **Blindness tests** (B6).

## B10. Serving and deployment
- `api/main.py`:
  - CORS for `http://localhost:5173` in dev.
  - Include the routers under `/api`.
  - If `STATIC_DIR` (default `/app/static`) exists, mount the static assets and add a **SPA fallback**: any non-`/api` GET returns `index.html`.
- **`Dockerfile`** (multi-stage):
  - Stage 1: `node:20-slim`, then `WORKDIR /fe`, copy `frontend/`, then `npm ci && npm run build`.
  - Stage 2: `python:3.11-slim`, then `pip install --no-cache-dir ./backend`, then copy `/fe/dist` → `/app/static`.
  - Env: `QBREAK_KEY_BITS=4`, `QBREAK_MODULI=15`, `QBREAK_MAX_CONCURRENT_SIMS=1`.
  - `CMD uvicorn qbreak.api.main:app --host 0.0.0.0 --port ${PORT:-8000}`.
- **`render.yaml`**: one Docker web service, health check `/api/health`, and the env vars above.
  - Use at least the **Starter** instance (512 MB+). The free tier sleeps and cold-starts slowly, which is bad for judging.
  - Before the frontend exists (H+2:30), stage 1 must still succeed. Use `COPY frontend/ ./` (a `frontend/.gitkeep` from the skeleton keeps the folder present; ask Agent 4 to leave it) and `RUN if [ -f package.json ]; then npm ci && npm run build; else mkdir -p dist && echo '<h1>Q-Break API is up</h1>' > dist/index.html; fi`.
- Railway and Fly.io are fallbacks. The same Dockerfile works for both.
- After Checkpoint B, every merge to main auto-deploys. Smoke-test the production URL after each deploy: health, 4-bit attack, N = 15 attack.
- Enabling sizes: flip `QBREAK_KEY_BITS` / `QBREAK_MODULI` in Render env vars **only** after the A1/A2 benchmark tables show < 20 s and ≤ 400 MB, **and** you have re-measured on the deployed instance.
- Abuse guards: `MAX_SHOTS`, text limits, the simulation semaphore, and a 60 s per-request timeout. Return 503 `"Simulator busy, try again"` if the semaphore wait exceeds 30 s. (Add an optional timeout to the semaphore acquire in `simulator.py`; you own that file.)

## B11. Integration duties
- Review every PR for **file ownership**, CI status, and contract adherence. Reject PRs that edit files outside their owner's list.
- When A1 or A2 merges, wire the real modules the same hour and tell Agent 4's human that `/attack` now returns real data.
- Keep a short `docs/STATUS.md` (yours): what's merged, what's enabled in production, and known issues.
- At H+14:00, freeze. Then tag `v1.0` and write the README:
  - the project claim (A1), how to run locally (`pip install -e "backend[dev]"`, `uvicorn …`, `npm run dev`),
  - how to run tests, the deploy URL, and the honesty notes.
- Ten minutes before judging, hit the production URL so it is warm.

## B12. Definition of done
- The production URL runs both breach tests end to end.
- `pytest -m "not slow"` is green in CI; the full `pytest` is green locally at freeze.
- All 16 four-bit keys pass end to end through the API; all enabled N pass end to end.
- Every attack response carries real verification steps and evidence.
- No code path lets the attacker see the key or the factors.
