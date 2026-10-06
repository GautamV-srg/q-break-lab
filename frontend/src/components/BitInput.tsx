import { useId } from "react";

interface Props {
  value: string;
  bits: number;
  onChange: (v: string) => void;
  label: string;
  disabled?: boolean;
}

export function randomBits(bits: number): string {
  // Not cryptographic: just picks a demo key for the organization.
  let s = "";
  for (let i = 0; i < bits; i++) s += Math.random() < 0.5 ? "0" : "1";
  return s;
}

/** Clickable bit toggles + a typed field, exactly `bits` characters of 0/1. MSB first. */
export default function BitInput({ value, bits, onChange, label, disabled }: Props) {
  const id = useId();
  const padded = value.padEnd(bits, "0").slice(0, bits);
  const valid = value.length === bits && /^[01]+$/.test(value);

  function toggle(i: number) {
    const arr = padded.split("");
    arr[i] = arr[i] === "1" ? "0" : "1";
    onChange(arr.join(""));
  }

  return (
    <div className="bitinput">
      <label htmlFor={id} className="field-label">
        {label}
      </label>
      <div className="bitinput-row">
        <div className="bit-toggles" role="group" aria-label={`${label}: toggle bits, most significant first`}>
          {padded.split("").map((b, i) => (
            <button
              type="button"
              key={i}
              className={`bit ${b === "1" ? "bit-on" : ""}`}
              aria-pressed={b === "1"}
              aria-label={`Bit ${bits - 1 - i} (value ${2 ** (bits - 1 - i)}): ${b}`}
              onClick={() => toggle(i)}
              disabled={disabled}
            >
              {b}
            </button>
          ))}
        </div>
        <input
          id={id}
          className={`mono input bit-typed ${valid ? "" : "input-invalid"}`}
          value={value}
          maxLength={bits}
          inputMode="numeric"
          pattern="[01]*"
          spellCheck={false}
          autoComplete="off"
          aria-invalid={!valid}
          onChange={(e) => onChange(e.target.value.replace(/[^01]/g, "").slice(0, bits))}
          disabled={disabled}
        />
        <button type="button" className="btn btn-ghost btn-small" onClick={() => onChange(randomBits(bits))} disabled={disabled}>
          🎲 Random key
        </button>
      </div>
      {!valid && (
        <p className="field-hint field-error">
          The key must be exactly {bits} bits of 0 and 1.
        </p>
      )}
    </div>
  );
}
