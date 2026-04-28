# vaultpilot-mcp-smoke-test

Snapshot of a two-pass smoke test of [vaultpilot-mcp](https://github.com/szhygulin/vaultpilot-mcp) and the [vaultpilot-preflight](https://github.com/szhygulin/vaultpilot-security-skill) skill, run on **2026-04-28**.

This is a **frozen artifact set** — scripts, transcripts, and analysis from a specific run. The methodology lives in two companion skill repos:

- [`mcp-smoke-test-skill`](https://github.com/szhygulin/mcp-smoke-test-skill) — base honest-baseline methodology, MCP-agnostic
- [`crypto-security-smoke-test-skill`](https://github.com/szhygulin/crypto-security-smoke-test-skill) — adversarial red-team extension

Findings filed as issues #427–#463 on `szhygulin/vaultpilot-mcp` (tracker issues [#448](https://github.com/szhygulin/vaultpilot-mcp/issues/448) and [#456](https://github.com/szhygulin/vaultpilot-mcp/issues/456)).

## TL;DR — start with `SUMMARY.md`

The cross-pass executive overview is at [`SUMMARY.md`](SUMMARY.md). Read that first; everything below is supporting evidence.

## Layout

```
.
├── SUMMARY.md                         # cross-pass executive overview (start here)
│
├── smoketest/                         # Pass 1: honest baseline (mcp-smoke-test)
│   ├── scripts.json                   # 120-script catalog
│   ├── transcripts/NNN.txt            # 120 individual transcripts
│   ├── all_transcripts.txt            # concatenated corpus (568 KB)
│   ├── summary.txt                    # per-script structured extract
│   └── findings.md                    # full Pass-1 analysis (UX, feature gaps, security)
│
└── smoketest-adversarial/             # Pass 2: red-team (crypto-security-smoke-test)
    ├── scripts.json                   # 44-script initial adversarial catalog (with role tags)
    ├── enrichment.json                # 30 security-enriched scripts (121-150)
    ├── scripts-base.json              # copy of Pass-1 scripts.json for reference
    ├── transcripts/                   # 111 adversarial transcripts (44 initial + 67 b-prefixed expansion)
    ├── all_transcripts.txt            # initial 44-script concat
    ├── all_transcripts_full.txt       # full 111-script concat (1.8 MB)
    ├── summary.txt                    # initial structured extract
    ├── summary_full.txt               # full structured extract (103 KB)
    ├── findings_adversarial.md        # initial 44-script analysis
    └── findings_adversarial_full.md   # full 111-script analysis (latest)
```

## Coverage at a glance

| | Pass 1 (honest) | Pass 2 (adversarial) |
|---|---|---|
| Scripts | 120 | 111 |
| Caught / passed | 120 (no successful attacks because everything was honest) | 104 caught cleanly + 1 tricked-unless-second-LLM (a086) + 6 defense-by-gap or depends-on-user |
| Filed issues | 22 (#427–#447 + tracker #448) | 6 + 4 (#450–#455, #460–#463 + tracker #456) |
| Threat-model roles | 1 (all honest) | 5 (rogue agent, rogue MCP, combined, supply-chain tamper, control) |

## Reproducing

This corpus is a frozen snapshot. To re-run on a future vaultpilot-mcp release, use the methodology in the two skill repos linked above against a fresh workdir.

## Caveats

- All testing was in vaultpilot-mcp **demo mode** (no real funds, no Ledger paired, broadcast intercepted).
- Adversarial subagents simulated attacks via transcript narration — no actual exfiltration, no real broadcasts.
- ~30% of read-only scripts in Pass 1 hit Claude Code subagent permission denials. Documented as a meta-finding; not a vaultpilot bug.
- The corpus is signing-flow-heavy. Several CF-* surfaces (BIP-137 message signing, EIP-712 typed-data, EIP-7702 setCode) are under-sampled in the adversarial pass and remain documented by 1–3 scripts each.
