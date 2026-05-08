# SealAudit Final Claim Lock v2

This additive claim lock supersedes v1 for continuation planning. It does not overwrite v1.

- Gate pass: `True`
- Best-paper ready: `True`
- Allowed current claim: DeepSeek-only marker-hidden v5 selective audit/triage with support-evidence binding
- Formal v5 scoped claim allowed: `True`
- Security certificate allowed: `False`

Locked effect surface:
- Marker-hidden rows: `960`
- Unique cases: `320`
- Decisive rows: `320`
- Confirmed benign/risk: `80` / `240`
- Unsafe-pass rows: `0`
- Visible-marker claim rows: `0`

Forbidden claims:
- security certificate
- harmlessness guarantee
- automatic latent-trojan classifier
- visible-marker rows as main evidence
- expert-signed gold labels or named/institutional expert certification
- claim that hard ambiguity is resolved when retained as review load

Remaining blockers:
- None.
