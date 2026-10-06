# Q-Break — Agent 2 build prompt: Shor / MiniRSA (Public-key breach test engine)

> **You are Agent 2 of 4.** Your human teammate will paste this whole file to you as your only brief. You will build **tiny-number RSA and the genuine Qiskit Shor period-finding attack that powers the public-key breach test**, on branch `feat/shor`.
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

# PART B — YOUR ROLE: AGENT 2 · SHOR / MiniRSA

**Branch:** `feat/shor`
**You own:** `backend/qbreak/rsa/__init__.py`, `backend/qbreak/rsa/minirsa.py`, `backend/qbreak/rsa/shor.py`, `backend/tests/test_rsa_minirsa.py`, `backend/tests/test_rsa_shor.py`, `backend/scripts/benchmark_shor.py`.
**You must not touch** anything else. You write no FastAPI, encoding, or frontend code. Agent 3 wraps your functions; Agent 4 displays your results.

You build the public-key half of the demo: tiny but real RSA (the victim side) and a **genuine** Shor period-finding attack (the attacker side). Your milestones match locked build-order items 2, 5, and 6.

## B1. Deliverables, in order

| # | Deliverable | Merge by |
|---|---|---|
| 1 | `minirsa.py` + `test_rsa_minirsa.py` green | H+2:00 (small PR, merge early) |
| 2 | `shor.py` for **N = 15**, textbook-swap construction, + tests green | **H+5:00 (Checkpoint A)** |
| 3 | Permutation-unitary construction, cross-checked against the textbook one at N = 15 | H+7:00 |
| 4 | **N = 21** passing + benchmark table | ~H+9:30 |
| 5 | **Dynamic set** {33, 35} passing + benchmark table (39 optional) | H+13:00 (Checkpoint C) |

## B2. `minirsa.py`: the victim side

```python
SUPPORTED_MODULI = {15: (3, 5), 21: (3, 7), 33: (3, 11), 35: (5, 7)}
```
This table is the **victim's** private knowledge. `shor.py` must never import this module.

- `generate_keypair(n)`:
  - φ = (p−1)(q−1).
  - e = the smallest odd e ≥ 3 with gcd(e, φ) = 1.
  - d = `pow(e, -1, φ)`.
  - `e_equals_d = (e == d)`.

  Expected values (already verified):

  | N | p·q | φ | e | d | e = d? |
  |---|---|---|---|---|---|
  | 15 | 3·5 | 8 | 3 | 3 | **yes** |
  | 21 | 3·7 | 12 | 5 | 5 | **yes** |
  | 33 | 3·11 | 20 | 3 | 7 | no |
  | 35 | 5·7 | 24 | 5 | 5 | **yes** |

- `encrypt_chunks`: each chunk m → `pow(m, e, n)`. Validate 0 ≤ m < n, else `ValueError`.
- `decrypt_chunks`: each c → `pow(c, d, n)`.
- `private_exponent(p, q, e) -> (d, φ)`: the attacker uses this **after** Shor has found p and q. Computing d from factors is ordinary public math, not a leak. Validate that `gcd(e, φ) == 1`.

**Exact test vector:** "Hi" → chunks `[2, 2, 0, 6, 4, 4]` (bit_length 16) → with N = 15, e = 3: ciphertext `[8, 8, 0, 6, 4, 4]` → decrypts back. Chunking is Agent 3's job; you just need the numbers.

### `test_rsa_minirsa.py`
- Round trip for every m < 8 and every N in the table.
- `e·d ≡ 1 (mod φ)`.
- The `e_equals_d` flags match the table above.
- Unsupported n → `ValueError`.

## B3. `shor.py`: the attacker side

The attacker knows only `n`. It does not know p, q, φ, or d, and must not import `minirsa`.

### Registers and sizes
- **Work register:** `n_work = ceil(log2(n))` qubits, initialised to |1⟩. That means `x(work[0])` only, since qubit 0 is the LSB (A3 convention).
- **Counting register:** `n_count = 2 · n_work` qubits by default. Each counting qubit gets an H.
- Classical register: `n_count` bits. Measure `count[i] → c[i]`.
- **Controlled-U^(2^j)** is controlled by `count[j]` and acts on `work`.
- Then **inverse QFT** on `count`, then measure.

| N | n_work | n_count | total qubits |
|---|---|---|---|
| 15 | 4 | 8 | 12 |
| 21 | 5 | 10 | 15 |
| 33, 35 | 6 | 12 | 18 |

### `inverse_qft(t)`: write it by hand, exactly like this
This matches "counting qubit j controls U^(2^j)", so the measured integer y ≈ s · 2^t / r.

```python
import numpy as np
from qiskit import QuantumCircuit

def inverse_qft(t: int) -> QuantumCircuit:
    qc = QuantumCircuit(t, name="IQFT")
    for q in range(t // 2):
        qc.swap(q, t - q - 1)
    for j in range(t):
        for m in range(j):
            qc.cp(-np.pi / float(2 ** (j - m)), m, j)
        qc.h(j)
    return qc
```
Do **not** use `qiskit.circuit.library.QFT`; it is deprecated in 2.x.

### Two constructions of controlled modular multiplication

**(a) `"textbook-swaps"`: N = 15 only.** This is the classic hand-built circuit where multiplication by a mod 15 is a bit rotation, plus a NOT on all bits for some bases.

```python
def amod15(a: int, power: int) -> QuantumCircuit:
    if a not in (2, 4, 7, 8, 11, 13):
        raise ValueError("a must be 2,4,7,8,11,13")
    U = QuantumCircuit(4)
    for _ in range(power % 4):        # every valid a has order dividing 4 mod 15
        if a in (2, 13):
            U.swap(2, 3); U.swap(1, 2); U.swap(0, 1)
        if a in (7, 8):
            U.swap(0, 1); U.swap(1, 2); U.swap(2, 3)
        if a in (4, 11):
            U.swap(1, 3); U.swap(0, 2)
        if a in (7, 11, 13):
            for q in range(4):
                U.x(q)
    gate = U.to_gate(label=f"{a}^{power} mod 15")
    return gate.control(1)            # append with [count[j]] + list(work)
```

Two things to check in your tests:
- `power % 4` is valid because every allowed a has order dividing 4 (a⁴ ≡ 1 mod 15). Remember that `U^0` is the identity, which is correct.
- Sanity-check the bit order once by hand: for a = 7 on |0001⟩, the circuit must give |0111⟩ = 7.

**(b) `"permutation-unitary"`: any supported N.** This works for N = 15 too, and is used as a cross-check.
- For counting qubit j, compute `b = pow(a, 2**j, n)` classically. This is ordinary repeated squaring, which the circuit builder is allowed to do.
- Build a **permutation matrix** on n_work + 1 qubits, with the control as the *highest* qubit:

```python
from qiskit.circuit.library import UnitaryGate
import numpy as np

def controlled_mult_gate(b: int, n: int, n_work: int, label: str) -> UnitaryGate:
    dim = 2 ** (n_work + 1)
    M = np.zeros((dim, dim))
    for idx in range(dim):
        ctrl, x = idx >> n_work, idx & ((1 << n_work) - 1)
        out = (ctrl << n_work) | ((b * x) % n) if (ctrl and x < n) else idx
        M[out, idx] = 1
    return UnitaryGate(M, label=label)
# append with: qc.append(gate, list(work) + [count[j]])   # control last = highest index
```
- `(b·x) mod n` is a bijection on x < n because gcd(b, n) = 1, and x ≥ n is left unchanged, so M is a permutation (unitary). Add an assertion in a test.
- Building the full controlled matrix yourself avoids slow `UnitaryGate(...).control()` synthesis. Aer simulates `unitary` instructions natively.
- **Honesty note** (Agent 3 shows it, but put it in your docstring too): this block embeds the multiplication-by-b permutation, which is computed classically at build time. That is standard for small demos. A full-scale Shor would need reversible modular-arithmetic circuits instead.

`build_period_finding_circuit(a, n, n_count=None, construction="auto")`:
- `"auto"` means `"textbook-swaps"` if n == 15, otherwise `"permutation-unitary"`.
- Set `qc.name` and keep the boxed gates labelled (`"U^(2^j)"`, `"IQFT"`) so the logical drawing is readable.

### Classical post-processing

`choose_bases(n, seed)`:
- Bases a with 2 ≤ a ≤ n − 2 and `gcd(a, n) == 1`, shuffled with `random.Random(seed)`.
- **Skip any a with gcd(a, n) > 1.** That would factor n classically by luck and spoil the demo. Instead, record it in a `ShorAttempt` with reason `"skipped: gcd(a, N) > 1 would factor classically (not a quantum result)"`. Only do this if the caller passed such an a explicitly.
- For N = 15, put **7** first when no seed is given. It is the classic example with order 4.

`candidate_periods(counts, n_count, n, a)` — for each measured bitstring, from most to least frequent:
1. y = `int(bitstring, 2)`; phase = y / 2^t.
2. If y = 0, reject: `"phase 0 carries no period information"`.
3. `frac = Fraction(y, 2**t).limit_denominator(n)`; candidate r = `frac.denominator`.
4. Test r, 2r, 3r (in that order) for `pow(a, r', n) == 1`. The first one that works is the candidate. Small multiples recover the true period when the measured s/r was in lowest terms with a common factor.
5. If none works, reject: `"a^r mod N ≠ 1"`.
6. Accept only if the period is even and `pow(a, r//2, n) != n − 1`. Otherwise reject with a specific reason (`"r is odd"` or `"a^(r/2) ≡ −1 mod N"`).
7. The reason string for an accepted candidate shows the arithmetic, e.g. `"7^4 mod 15 = 1; r even; 7^2 mod 15 = 4 ≠ 14"`.

Keep one `ShorAttempt` per distinct bitstring examined (cap at 16 per base).

`factors_from_period(a, r, n)`:
- p = gcd(a^(r/2) − 1, n), q = gcd(a^(r/2) + 1, n).
- Return the **sorted** pair if 1 < p < n and p·q == n (if q is trivial, use n // p). Otherwise return None.

`run_shor_attack(n, a=None, shots=1024, seed=None, max_bases=4)`:
- Raise `ValueError` if n is not in `SHOR_SUPPORTED_N`.
- For each base (the given a, or `choose_bases`) up to `max_bases`:
  1. Build the circuit, run it with `qbreak.common.simulator.run_circuit`, and get the candidates.
  2. Take the first accepted r that gives factors, and return a `ShorResult`.
- If every base fails, return a `ShorResult` with `period=None` and `factors=None` and all attempts listed. Do not raise.
- `explain_circuits` = `[("Controlled U^(2^0)", <decomposed small circuit>), ("Inverse QFT", inverse_qft(n_count))]`.
- `register_roles`:
  - `"count": "Exponent register: superposition of x = 0..2^t−1; after IQFT its measurement encodes s/r"`
  - `"work": "Holds a^x mod N, starts at |1⟩"`

**Expected behaviour (verified classically):**
- **N = 15:** a = 7 has r = 4. The ideal peaks are y ∈ {0, 64, 128, 192} with t = 8. y = 64 → 1/4 → r = 4 → gcd(48, 15) = 3 and gcd(50, 15) = 5.
- **N = 21:** a = 2 has r = 6 → gcd(2³ − 1, 21) = 7 and gcd(9, 21) = 3. The peaks are not exact powers of two, so continued fractions do the work.
- **N = 33:** a = 5 has r = 10.
- **N = 35:** a = 2 has r = 12.
- With ideal outcomes, continued fractions recover the right r from most nonzero peaks, so a 1024-shot run should succeed on the first base nearly always.

`SHOR_SUPPORTED_N`: start with `(15,)`. Add 21, then 33 and 35, **only** when their tests pass and the benchmark is acceptable.

### `test_rsa_shor.py` (N ≥ 21 → `@pytest.mark.slow`)
- `inverse_qft(t)` equals the inverse of a hand-built QFT. Compare `Operator`s for t = 3.
- `amod15(a, 1)` maps |1⟩ → |a⟩ for every allowed a. Use `Statevector` on 4 qubits.
- Permutation matrix: unitary, maps |ctrl = 1, x⟩ → |1, b·x mod n⟩ for x < n, and is the identity when ctrl = 0.
- **Cross-check:** at N = 15, a = 7, the measurement distributions of both constructions agree (same top 4 peaks).
- `run_shor_attack(15, seed=…)` returns factors (3, 5) and period 4 for a = 7. It also succeeds for every valid a ∈ {2, 7, 8, 13} (order 4). For a ∈ {4, 11} (order 2), it should succeed or fail with a clear reason.
- **Blindness:**
  - `shor.py` source contains no `import` of `minirsa` (read the file text and assert).
  - The signature has no p, q, d, or phi parameter.
- **Slow tests:** N = 21, 33, 35 each factor correctly with a fixed seed.

## B4. `benchmark_shor.py`
- CLI: `python scripts/benchmark_shor.py --n 15 21 33 35 --trials 5`.
- For each N, print: qubits, logical depth, transpiled depth, gate counts, mean / max simulation ms, success rate, and peak RSS.
- Paste the table in each PR. Agent 3 enables an N in production only if it runs in under about 20 s with ≤ 400 MB RSS.

## B5. Pitfalls
- **Bit order:** counting qubit j must control U^(2^j), and you measure count[i] → c[i]. If peaks land at bit-reversed positions, your IQFT swaps or measurement mapping are wrong.
- `power % 4` is valid only for N = 15. The general construction uses `pow(a, 2**j, n)`.
- Do not rely on `limit_denominator` alone. Always check `pow(a, r, n) == 1`.
- The work register must start at |1⟩, not |0⟩. Starting at |0⟩ gives a fixed point and no period.
- Do not create your own `AerSimulator`; call `run_circuit`.

## B6. Definition of done
- N = 15 end to end with both constructions, deterministic under a seed.
- N = 21 and the dynamic set added to `SHOR_SUPPORTED_N` only with passing tests and posted benchmarks.
- Every `ShorAttempt` carries a human-readable reason. The UI shows these verbatim as "why the attack accepted / rejected this measurement".
- Docstrings explain counting vs work registers, phase → fraction → period → factors, and the construction honesty note, in plain English. Agent 4 reuses your wording.
