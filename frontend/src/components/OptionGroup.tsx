import { useId, type ReactNode } from "react";

export interface Option<T extends string | number> {
  value: T;
  label: ReactNode;
  /** Plain-text name used in the reasons list and for assistive tech. */
  name: string;
  sub?: ReactNode;
  badge?: string;
  /** Present when the engine does not offer this option; shown, never hidden. */
  disabledReason?: string | null;
}

interface Props<T extends string | number> {
  label: string;
  options: Option<T>[];
  value: T | null;
  onChange: (v: T) => void;
  /** Temporarily inert (a request is running). */
  busy?: boolean;
  /** "seg" = compact segmented control, "cards" = one card per option with a description. */
  variant?: "seg" | "cards";
  hint?: ReactNode;
}

/**
 * Radio group whose unavailable options stay visible: they are `aria-disabled`, keep
 * keyboard focus so their reason can be read, and the reason text is listed underneath.
 * Enabled/disabled state and reasons always come from /api/config.
 */
export default function OptionGroup<T extends string | number>({
  label,
  options,
  value,
  onChange,
  busy,
  variant = "seg",
  hint,
}: Props<T>) {
  const id = useId();
  const unavailable = options.filter((o) => o.disabledReason);

  return (
    <div className="field">
      <span className="field-label" id={`${id}-label`}>
        {label}
      </span>
      <div className={variant === "cards" ? "option-cards" : "segmented"} role="radiogroup" aria-labelledby={`${id}-label`}>
        {options.map((o) => {
          const off = !!o.disabledReason;
          const on = o.value === value;
          const cls = variant === "cards" ? "option-card" : "seg";
          return (
            <button
              type="button"
              role="radio"
              key={String(o.value)}
              aria-checked={on}
              aria-disabled={off || busy || undefined}
              aria-describedby={off ? `${id}-why-${o.value}` : undefined}
              title={o.disabledReason ?? undefined}
              className={`${cls} ${on ? `${cls}-on` : ""} ${off ? `${cls}-off` : ""}`}
              onClick={() => {
                if (!off && !busy && !on) onChange(o.value);
              }}
            >
              <span className="option-main">
                {off && (
                  <span className="option-lock" aria-hidden="true">
                    ⦸{" "}
                  </span>
                )}
                {o.label}
                {o.badge && <span className="option-badge">{o.badge}</span>}
              </span>
              {o.sub && <span className="option-sub">{o.sub}</span>}
              {off && <span className="sr-only"> (unavailable)</span>}
            </button>
          );
        })}
      </div>
      {hint && <div className="field-hint">{hint}</div>}
      {unavailable.length > 0 && (
        <ul className="option-reasons">
          {unavailable.map((o) => (
            <li key={String(o.value)} id={`${id}-why-${o.value}`}>
              <strong>{o.name} is unavailable.</strong> {o.disabledReason}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
