import type { RsaEncryptResponse } from "../api/types";

/**
 * char → bits → 3-bit chunks → ciphertext ints. The bits shown are reassembled from the
 * response's plaintext_chunks (the backend's encoding), not re-encoded in the browser.
 */
export default function ChunkTable({ message, enc, n, e }: { message: string; enc: RsaEncryptResponse; n: number; e: number }) {
  const cb = enc.chunk_bits;
  const stream = enc.plaintext_chunks.map((c) => c.toString(2).padStart(cb, "0")).join("");
  const dataBits = stream.slice(0, enc.bit_length);

  // Group the bitstream by character (UTF-8 byte count per char) when it lines up.
  const encoder = new TextEncoder();
  const chars = Array.from(message);
  const charBytes = chars.map((ch) => encoder.encode(ch).length);
  const aligned = charBytes.reduce((a, b) => a + b, 0) * 8 === enc.bit_length;
  const groups: { label: string; bits: string }[] = [];
  if (aligned) {
    let pos = 0;
    chars.forEach((ch, i) => {
      const len = charBytes[i] * 8;
      groups.push({ label: ch === " " ? "␠" : ch, bits: dataBits.slice(pos, pos + len) });
      pos += len;
    });
  } else {
    for (let i = 0; i < dataBits.length; i += 8) groups.push({ label: `byte ${i / 8}`, bits: dataBits.slice(i, i + 8) });
  }

  return (
    <div className="chunk-table">
      <div className="ct-label">1 · Characters → bits (UTF-8, MSB first)</div>
      <div className="char-bits">
        {groups.map((g, i) => (
          <div className="char-bit" key={i}>
            <span className="char-glyph">{g.label}</span>
            <span className="mono small">{g.bits.replace(/(.{8})(?=.)/g, "$1 ")}</span>
          </div>
        ))}
      </div>

      <div className="ct-label">
        2 · Split into {cb}-bit chunks (m ≤ {2 ** cb - 1} &lt; N) → 3 · encrypt c = m<sup>e</sup> mod N with (n = {n}, e = {e})
      </div>
      <div className="table-scroll">
        <table className="data-table chunks">
          <tbody>
            <tr>
              <th scope="row">bits</th>
              {enc.plaintext_chunks.map((c, i) => {
                const start = i * cb;
                const real = Math.max(0, Math.min(cb, enc.bit_length - start));
                const s = c.toString(2).padStart(cb, "0");
                return (
                  <td key={i} className="mono">
                    {s.slice(0, real)}
                    {real < cb && <span className="pad-bits" title="zero padding">{s.slice(real)}</span>}
                  </td>
                );
              })}
            </tr>
            <tr>
              <th scope="row">m</th>
              {enc.plaintext_chunks.map((c, i) => (
                <td key={i} className="mono">
                  {c}
                </td>
              ))}
            </tr>
            <tr className="row-cipher">
              <th scope="row">c</th>
              {enc.ciphertext.map((c, i) => (
                <td key={i} className="mono">
                  {c}
                </td>
              ))}
            </tr>
          </tbody>
        </table>
      </div>
      <p className="small muted">
        {enc.ciphertext.length} chunks · bit_length = {enc.bit_length}
        {enc.plaintext_chunks.length * cb > enc.bit_length && " · faded bits are zero padding"} · textbook RSA without
        padding: equal chunks give equal ciphertexts (insecure on purpose).
      </p>
    </div>
  );
}
