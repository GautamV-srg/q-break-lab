// Writes the defence mock fixtures (src/api/mocks/defence_*.json) from the synthetic
// stand-in in src/api/mocks/defenceSynth.ts. Run: npm run gen:defence-mocks
//
// Replace these with recordings of the live /api/defence/* endpoints once the defence
// backend has merged (see src/api/mocks/README.md).

import { writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { MOCK_MESSAGE } from "../src/api/mocks/demo";
import aesResources from "../src/api/mocks/aes_resources.json";
import config from "../src/api/mocks/config.json";
import * as synth from "../src/api/mocks/defenceSynth";
import { buildReattackRequest } from "../src/api/payloads";
import type { ProtectRequest } from "../src/api/types";

const dir = resolve(__dirname, "../src/api/mocks");
const write = (name: string, data: unknown) => {
  writeFileSync(resolve(dir, name), JSON.stringify(data, null, 1) + "\n");
  console.log("wrote", name);
};

const maxText = (config as { max_aes_text_chars: number }).max_aes_text_chars;
const info = synth.info(maxText);
const base: ProtectRequest = { plaintext: MOCK_MESSAGE, methods: ["aes256", "mlkem", "bb84"], bb84: { ...synth.BB84_DEFAULTS } };

const accepted = await synth.protect(base);
const aborted = await synth.protect({ ...base, bb84: { ...base.bb84, eve: true } });
const aes256 = (aesResources as { estimates: { key_bits: number }[] }).estimates.find((e) => e.key_bits === 256);
const { request } = buildReattackRequest(accepted, {
  bb84_attack: { eve_intercept_fraction: 1, channel_noise: 0, seed: null },
  original_attack: { cipher: "miniaes", verdict: "breached" },
});

write("defence_info.json", info);
write("defence_config.json", {
  methods: ["aes256", "mlkem", "bb84"],
  max_text_chars: maxText,
  bb84_defaults: info.bb84.defaults,
  bb84_limits: info.bb84.limits,
});
write("defence_protect.json", { request: base, accepted, aborted });
write("defence_reattack.json", { request, response: synth.reattack(request, aes256) });
write("evaluation_defence.json", synth.evaluationSeries());
