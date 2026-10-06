import { useId } from "react";

export default function ShotsSlider({
  value,
  max,
  onChange,
  disabled,
}: {
  value: number;
  max: number;
  onChange: (v: number) => void;
  disabled?: boolean;
}) {
  const id = useId();
  const min = 256;
  const hi = Math.max(min, max);
  return (
    <div className="field">
      <label htmlFor={id} className="field-label">
        Shots (circuit repetitions): <span className="mono">{value}</span>
      </label>
      <input
        id={id}
        type="range"
        min={min}
        max={hi}
        step={256}
        value={Math.min(value, hi)}
        onChange={(e) => onChange(Number(e.target.value))}
        disabled={disabled}
      />
      <div className="range-ends mono muted small">
        <span>{min}</span>
        <span>{hi}</span>
      </div>
    </div>
  );
}
