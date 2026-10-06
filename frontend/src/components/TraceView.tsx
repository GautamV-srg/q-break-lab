import type { TraceStep } from "../api/types";

/** Collapsible "How one block was encrypted", built from the encrypt response's trace. */
export default function TraceView({ trace }: { trace: TraceStep[] }) {
  if (!trace.length) return null;
  return (
    <details className="disclosure">
      <summary>How one block was encrypted</summary>
      <p className="muted small">
        MiniAES encrypts each 4-bit block (nibble) independently, one round: AddRoundKey → SubNibble → RotateBits →
        AddRoundKey. The first block of your message:
      </p>
      <ol className="trace">
        {trace.map((t, i) => (
          <li key={i}>
            <span className="trace-step">{t.step}</span>
            <span className="mono trace-detail">{t.detail}</span>
            <span className="mono trace-value">
              = {t.value.toString(2).padStart(4, "0")} (0x{t.value.toString(16)})
            </span>
          </li>
        ))}
      </ol>
    </details>
  );
}
