import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import type { Bb84Options, DefenceMethod, ProtectResult } from "../../api/types";
import ErrorBox from "../ErrorBox";
import RunProgress from "../RunProgress";
import StageCard from "../StageCard";
import { Bb84Verdict, PhotonStream, PhotonTable, QberGauge, SiftingFunnel } from "./Bb84Visual";
import { fmtMs, fmtValue, humanize, PublicBundleView } from "./bits";
import DefenceHood from "./DefenceHood";
import { ALL_METHODS, methodName } from "./settings";
import type { DefenceState } from "./useDefence";

/** Debounce for the BB84 sliders: a drag commits once it settles, never on every tick. */
const SLIDER_DEBOUNCE_MS = 350;

function useDebouncedCommit<T>(value: T, commit: (v: T) => void, ms: number) {
  const first = useRef(true);
  useEffect(() => {
    if (first.current) {
      first.current = false;
      return;
    }
    const t = setTimeout(() => commit(value), ms);
    return () => clearTimeout(t);
  }, [JSON.stringify(value)]);
}

function Range({
  label,
  value,
  min,
  max,
  step,
  format,
  onChange,
  disabled,
  hint,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  format: (v: number) => string;
  onChange: (v: number) => void;
  disabled?: boolean;
  hint?: ReactNode;
}) {
  const id = useId();
  return (
    <div className="field">
      <label htmlFor={id} className="field-label">
        {label}: <span className="mono">{format(value)}</span>
      </label>
      <input
        id={id}
        type="range"
        className="range-def"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        disabled={disabled || min === max}
        aria-valuetext={format(value)}
      />
      <div className="range-ends mono muted small">
        <span>{format(min)}</span>
        <span>{format(max)}</span>
      </div>
      {hint && <div className="field-hint">{hint}</div>}
    </div>
  );
}

const pct = (v: number) => `${Math.round(v * 100)}%`;
const pct1 = (v: number) => `${(v * 100).toFixed(1)}%`;

interface Props {
  d: DefenceState;
  id: string;
  n: number;
  locked: boolean;
  lockedHint?: string;
  /** The organization's message. Carried from Act I, or typed here in the standalone flow. */
  message: string;
  onMessageChange?: (m: string) => void;
  carriedFrom?: string;
  demoRunning?: boolean;
}

export default function ProtectStage({ d, id, n, locked, lockedHint, message, onMessageChange, carriedFrom, demoRunning }: Props) {
  const s = d.settings;
  const editable = !!onMessageChange;
  const [draft, setDraft] = useState<Bb84Options | null>(d.bb84);
  useEffect(() => {
    if (d.bb84 && JSON.stringify(d.bb84) !== JSON.stringify(draft)) setDraft(d.bb84);
  }, [d.bb84]);
  useDebouncedCommit(draft, (v) => v && d.setBb84(v), SLIDER_DEBOUNCE_MS);

  // Auto-run: re-protect once the committed BB84 settings change, only when the user opted in.
  const lastRun = useRef<string>("");
  useEffect(() => {
    const key = JSON.stringify(d.bb84);
    if (!d.autoRun || !d.protect || d.busy || key === lastRun.current) return;
    lastRun.current = key;
    void d.runProtect(message);
  }, [d.bb84, d.autoRun]);

  const maxChars = s?.maxTextChars ?? 0;
  const messageValid = message.length > 0 && message.length <= maxChars;
  const busy = d.busy || !!demoRunning;
  const canRun = !!s && !!d.bb84 && d.methods.length > 0 && messageValid && !busy;
  const bb84On = d.methods.includes("bb84");
  const stale = !!d.protect && d.protectedText !== message;

  function toggle(m: DefenceMethod) {
    d.setMethods(d.methods.includes(m) ? d.methods.filter((x) => x !== m) : ALL_METHODS.filter((x) => x === m || d.methods.includes(x)));
  }
  function patch(p: Partial<Bb84Options>) {
    setDraft((v) => (v ? { ...v, ...p } : v));
  }
  function run() {
    lastRun.current = JSON.stringify(draft);
    void d.runProtect(message, { bb84: draft ?? undefined });
  }

  const results = d.protect ? ALL_METHODS.map((m) => d.protect!.results[m]).filter((r): r is ProtectResult => !!r) : [];

  return (
    <StageCard id={id} n={n} title="Protect the message" side="def" sideLabel="Blue team · your organization" locked={locked} lockedHint={lockedHint}>
      <ErrorBox message={d.infoError && !s ? `Defence engine details unavailable: ${d.infoError}` : null} onRetry={d.reloadInfo} />
      {!s && !d.infoError && <p className="muted">Loading the defence engine's methods and limits…</p>}

      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (canRun) run();
        }}
      >
        <div className="field">
          <label htmlFor={`${id}-msg`} className="field-label">
            {editable ? "Message to protect" : "Message to protect (same plaintext, organization side only)"}
          </label>
          {editable ? (
            <>
              <textarea
                id={`${id}-msg`}
                className="input"
                rows={3}
                value={message}
                maxLength={maxChars || undefined}
                onChange={(e) => onMessageChange!(e.target.value)}
                disabled={busy}
                aria-invalid={!messageValid}
                aria-describedby={`${id}-msg-hint`}
              />
              <div id={`${id}-msg-hint`} className={`field-hint ${s && !messageValid ? "field-error" : ""}`}>
                {s ? `${message.length}/${maxChars} characters${message.length === 0 ? " · enter a message" : ""}` : "Waiting for the defence engine's limits…"}
              </div>
            </>
          ) : (
            <>
              <output id={`${id}-msg`} className="carried-msg mono">
                {message}
              </output>
              {carriedFrom && <div className="field-hint">{carriedFrom}</div>}
              {s && !messageValid && <div className="field-hint field-error">This message is longer than the defence engine's {maxChars}-character limit.</div>}
            </>
          )}
        </div>

        <fieldset className="field method-picker" disabled={busy}>
          <legend className="field-label">Defences to apply</legend>
          <div className="option-cards">
            {ALL_METHODS.map((m) => {
              const info = d.info?.methods?.find((x) => x.id === m);
              const offered = !s || s.methods.includes(m);
              const on = d.methods.includes(m);
              return (
                <label key={m} className={`option-card method-card ${on ? "option-card-on" : ""} ${offered ? "" : "option-card-off"}`}>
                  <span className="option-main">
                    <input type="checkbox" checked={on} disabled={!offered} onChange={() => toggle(m)} /> {methodName(d.info, m)}
                  </span>
                  <span className="option-sub">{info?.description ?? (d.infoLoading ? "Loading description…" : "")}</span>
                  {info?.kind && <span className="method-kind small">{info.kind}</span>}
                  {!offered && <span className="small">Not enabled on this engine.</span>}
                </label>
              );
            })}
          </div>
          {d.methods.length === 0 && <div className="field-hint field-error">Pick at least one defence.</div>}
        </fieldset>

        {bb84On && draft && s && (
          <fieldset className="bb84-panel" disabled={busy}>
            <legend>BB84 channel settings</legend>
            <div className="field">
              <label className="switch">
                <input type="checkbox" checked={draft.eve} onChange={(e) => patch({ eve: e.target.checked })} />
                <span className="switch-ui" aria-hidden="true" />
                <span>
                  <strong>Eavesdropper (Eve) on the channel</strong>{" "}
                  <span className="mono small">{draft.eve ? "ON" : "OFF"}</span>
                </span>
              </label>
              <div className="field-hint">Eve intercepts photons, measures each in a random basis and re-sends what she saw.</div>
            </div>
            <Range
              label="Intercept fraction"
              value={draft.eve_intercept_fraction}
              min={s.limits.eve_intercept_fraction_min}
              max={s.limits.eve_intercept_fraction_max}
              step={0.05}
              format={pct}
              onChange={(v) => patch({ eve_intercept_fraction: v })}
              disabled={!draft.eve}
              hint={`Theory: QBER ≈ fraction / 4, so ${pct(draft.eve_intercept_fraction)} → about ${pct1(draft.eve_intercept_fraction / 4)}.`}
            />
            <Range
              label="Channel noise (bit-flip rate)"
              value={draft.channel_noise}
              min={s.limits.channel_noise_min}
              max={s.limits.channel_noise_max}
              step={0.005}
              format={pct1}
              onChange={(v) => patch({ channel_noise: v })}
            />
            <details className="disclosure">
              <summary>Advanced</summary>
              <Range
                label="Raw qubits"
                value={draft.raw_qubits}
                min={s.limits.raw_qubits_min}
                max={s.limits.raw_qubits_max}
                step={Math.max(1, Math.min(256, s.limits.raw_qubits_min))}
                format={(v) => v.toLocaleString()}
                onChange={(v) => patch({ raw_qubits: v })}
                hint={`About a quarter of the raw qubits survive sifting and sampling; the abort threshold is ${pct1(draft.qber_threshold)}.`}
              />
            </details>
            <label className="check-line small">
              <input type="checkbox" checked={d.autoRun} onChange={(e) => d.setAutoRun(e.target.checked)} /> Re-run automatically when these
              settings change
            </label>
          </fieldset>
        )}

        <button type="submit" className="btn btn-defend" disabled={!canRun}>
          {d.protecting ? "Protecting…" : d.protect ? "↻ Protect again" : "🛡 Protect message"}
        </button>
        {stale && <p className="small muted">The message changed since the last run. Protect again to update the results.</p>}
      </form>

      {d.protecting && (
        <RunProgress
          stages={[
            ...(d.methods.includes("aes256") ? ["AES-256-GCM: fresh key, encrypt, decrypt"] : []),
            ...(d.methods.includes("mlkem") ? ["ML-KEM-768: keygen, encapsulate, encrypt, decapsulate"] : []),
            ...(bb84On ? [`BB84: sending ${draft?.raw_qubits ?? ""} photons${draft?.eve ? " past Eve" : ""}`, "Sifting and estimating the QBER"] : []),
            "Checking every round trip",
          ]}
        />
      )}
      <ErrorBox message={d.protectError} onRetry={busy ? undefined : run} />

      {results.length > 0 && (
        <div className={`protect-results ${d.protecting ? "is-stale" : ""}`} aria-live="polite">
          {results.map((r) => (
            <MethodResult key={r.method} r={r} name={methodName(d.info, r.method)} message={d.protectedText} />
          ))}
        </div>
      )}
    </StageCard>
  );
}

function SizeTable({ title, data, format }: { title: string; data: Record<string, unknown>; format: (k: string, v: unknown) => string }) {
  const entries = Object.entries(data);
  if (entries.length === 0) return null;
  return (
    <div className="kv-block">
      <div className="kv-title">{title}</div>
      <dl className="kv">
        {entries.map(([k, v]) => (
          <div key={k}>
            <dt>{humanize(k)}</dt>
            <dd className="mono">{format(k, v)}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

function MethodResult({ r, name, message }: { r: ProtectResult; name: string; message: string }) {
  const aborted = r.status !== "protected";
  return (
    <article className="method-result" aria-labelledby={`mr-${r.method}`}>
      <h3 id={`mr-${r.method}`} className="method-result-title">
        {name}
        {r.parameter_set && r.parameter_set !== name && <span className="method-param mono">{r.parameter_set}</span>}
        {aborted ? (
          <span className="vbadge vbadge-warn">
            <span aria-hidden="true">✗</span> {r.status === "aborted" ? "Aborted: key discarded" : r.status}
          </span>
        ) : (
          <span className="vbadge vbadge-safe">
            <span aria-hidden="true">🛡</span> Protected
          </span>
        )}
      </h3>

      <div className="duo duo-def">
        <div className="duo-col duo-org">
          <div className="def-col def-col-org">
            <span className="side-tag side-tag-org">Your organization</span>
            <p className="mono carried-msg small-msg">{message}</p>
            <p>
              {aborted ? (
                <span className="vbadge vbadge-neutral">
                  <span aria-hidden="true">–</span> No round trip: nothing was encrypted
                </span>
              ) : r.roundtrip_ok ? (
                <span className="vbadge vbadge-safe">
                  <span aria-hidden="true">✓</span> Round trip: decrypts to the original
                </span>
              ) : (
                <span className="vbadge vbadge-breach">
                  <span aria-hidden="true">✗</span> Round trip failed
                </span>
              )}
            </p>
            <SizeTable title="Sizes" data={r.sizes} format={(k, v) => (typeof v === "number" && k.endsWith("_bytes") ? `${v.toLocaleString()} B` : fmtValue(v))} />
            <SizeTable title="Timings" data={r.timings_ms} format={(_, v) => fmtMs(typeof v === "number" ? v : null)} />
            {r.steps.length > 0 && (
              <details className="disclosure">
                <summary>What happened, step by step</summary>
                <ol className="def-steps small">
                  {r.steps.map((s, i) => (
                    <li key={i}>{s}</li>
                  ))}
                </ol>
              </details>
            )}
          </div>
        </div>
        <div className="duo-wall" aria-hidden="true" />
        <div className="duo-col duo-adv">
          <div className="def-col def-col-adv">
            <span className="side-tag side-tag-adv">Quantum adversary sees (public only)</span>
            {r.bundle ? (
              <PublicBundleView bundle={r.bundle} />
            ) : (
              <p className="no-ct">
                <strong>
                  <span aria-hidden="true">∅ </span>No ciphertext exists.
                </strong>{" "}
                {r.qkd?.reason ?? "The key was discarded, so the message was never encrypted."}
              </p>
            )}
          </div>
        </div>
      </div>

      {r.method === "bb84" && r.qkd && (
        <section className="bb84-visual" aria-label="BB84 key exchange">
          <PhotonStream photons={r.qkd.photon_preview} eve={r.qkd.photon_preview.some((p) => p.eve_basis !== null)} />
          <div className="bb84-grid">
            <div>
              <h4>Photon preview</h4>
              <PhotonTable photons={r.qkd.photon_preview} eve={r.qkd.photon_preview.some((p) => p.eve_basis !== null)} />
            </div>
            <div>
              <h4>Sifting funnel</h4>
              <SiftingFunnel qkd={r.qkd} />
              <QberGauge qber={r.qkd.qber} threshold={r.qkd.qber_threshold} />
            </div>
          </div>
          <Bb84Verdict qkd={r.qkd} />
          <DefenceHood evidence={r.evidence} qkd={r.qkd} />
        </section>
      )}
    </article>
  );
}
