/** Hex nibbles in monospace, grouped by byte (two nibbles per byte). */
export default function CiphertextView({ nibbles, label = "Ciphertext" }: { nibbles: number[]; label?: string }) {
  const bytes: number[][] = [];
  for (let i = 0; i < nibbles.length; i += 2) bytes.push(nibbles.slice(i, i + 2));
  return (
    <div className="ciphertext">
      <div className="ct-label">
        {label} <span className="muted">({nibbles.length} nibbles · {bytes.length} bytes, hex)</span>
      </div>
      <div className="ct-bytes mono" aria-label={`${label} in hex: ${nibbles.map((n) => n.toString(16)).join("")}`}>
        {bytes.map((b, i) => (
          <span className="ct-byte" key={i}>
            {b.map((n) => n.toString(16)).join("")}
          </span>
        ))}
      </div>
    </div>
  );
}
