# Duplicate Rig Retirement Documentation

Status: operator-input

## Summary

Rig `0e00a01b-9bde-44f4-9650-78d458d87c18` is an **exact byte-for-byte duplicate** of rig `2da41b7d-cdb3-44ec-a26f-cd25e5225563` (claude-setup).

## Canonical Rig

| Field | Value |
|---|---|
| Rig ID | `2da41b7d-cdb3-44ec-a26f-cd25e5225563` |
| Name | claude-setup |
| Status | Canonical |

## Duplicate Rig

| Field | Value |
|---|---|
| Rig ID | `0e00a01b-9bde-44f4-9650-78d458d87c18` |
| Status | Exact duplicate — should be retired |

## Verification

An md5sum comparison was performed across all files in both rigs. **Zero content differences** were found: every file has an identical md5 hash in both repositories.

## Recommendation

This duplicate rig should be **retired** and all future work consolidated into the canonical claude-setup rig (`2da41b7d-cdb3-44ec-a26f-cd25e5225563`). Maintaining two identical rigs invites divergence and doubles maintenance overhead for no benefit.

No files or repository structure should be modified until a formal retirement decision is made.
