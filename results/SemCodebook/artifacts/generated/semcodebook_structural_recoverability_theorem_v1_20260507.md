# SemCodebook Structural Recoverability Theorem v1

This artifact formalizes the claim that SemCodebook supports structured provenance recovery inside admitted white-box cells, not universal natural-generation watermarking.

Let a generated program be \(x\), and let the structural carrier set be
\[
C(x)=C_{AST}(x)\cup C_{CFG}(x)\cup C_{SSA}(x).
\]
For task identifier \(t\), secret key \(K\), and carrier index \(i\), slots are scheduled by
\[
s_i=\mathrm{HMAC}_K(t\Vert i)\bmod |C(x)|.
\]
Let \(\gamma(x)\) be carrier coverage, \(\rho(x,a)\) be the retained carrier fraction after attack \(a\), and \(d_{ECC}\) be the maximum correctable erasure distance. A sufficient condition for recovery is
\[
\gamma(x)\rho(x,a) \ge 1-d_{ECC}.
\]
The detector must abstain when the commitment check fails, when the retained carriers fall below the ECC boundary, or when the parser/compiler witness is unavailable. Therefore, false positive control is enforced by keyed schedule agreement and commitment consistency rather than by lowering thresholds.

Current evidence:

- 72,000 admitted white-box records.
- 23,342/24,000 positive recoveries.
- 0/48,000 negative-control hits.
- 43,200 generation-changing ablation rows.

This theorem is a claim-boundary artifact. It does not promote first-sample/no-retry generation, validator repair, or cells outside the admitted model/source matrix.
