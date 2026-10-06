# Mock fixtures

Mock-data mode (`npm run dev:mock`, or any page with `?mock=1`) answers every API call from the
files in this folder, so the whole UI can be demoed with no backend. `engine.ts` is the only
reader; it is loaded on demand, so a live deployment never downloads these files.

## Where the data comes from

Every fixture is a **recording of the real Q-Break engine**, taken on 2026-10-06 from the
Track 5 backend branches (`feat/track5-symmetric` for the symmetric and evaluation endpoints,
`feat/track5-publickey` for the public-key and risk endpoints) running locally on Qiskit Aer.
Nothing here was written by hand.

| File | Recorded from |
|---|---|
| `config.json` | `GET /api/config` of both branches, merged the way one deploy serves it. The mock instance plays a memory-constrained deploy (`SYMMETRIC_MAX_KEY_BITS=8`) so the disabled-size UI is exercised; the reason text is the engine's own wording. |
| `aes_encrypt.json`, `aes_attack.json` | `POST /api/aes/encrypt` and `/attack` for the message and keys in `demo.ts`: all three attack modes at 4, 6 and 8 bits, plus the two-character message `"Hi"` in ciphertext-only mode (a genuinely ambiguous result). |
| `aes_noise.json` | The 4-bit known-beginning attack re-run with `noise_p` from 0 to the engine's maximum (128 shots). |
| `rsa_keygen.json`, `rsa_encrypt.json`, `rsa_attack.json` | `POST /api/rsa/*` for every enabled modulus and every construction offered for it. |
| `rsa_noise.json` | The N = 15 attack re-run with `noise_p` from 0 to the engine's maximum, per construction. |
| `evaluation.json` | `GET /api/evaluation` after running both branches' experiment runners with their `--quick` settings. |
| `mosca_info.json`, `aes_resources.json`, `rsa_resource_estimate.json` | `GET /api/risk/mosca`, `/api/aes/resources`, `/api/rsa/resource-estimate?modulus_bits=2048`. |

Circuit drawings and OpenQASM are truncated (and say so) to keep the files small. Noise recordings
keep only the fields that change with the noise level.

`public/deck-data.js` is the same recording, trimmed to what the presentation deck plots.

## Inputs that were not recorded

For the recorded message and keys, mock mode replays an engine response verbatim. For any other
key or message, `engine.ts` relabels the nearest recording (it remembers the key and message from
the mock "encrypt" call, standing in for the real engine's ability to recover them) and adds a
`MOCK DATA` warning to the response, which the Breach Report shows under "Notes from the test
engine".

## Re-recording

Start both backends, run their experiment runners, call the endpoints above, and overwrite these
files with the JSON responses. Keep `demo.ts` in step with the message and keys you record.
