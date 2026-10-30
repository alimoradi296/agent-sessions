"""Print a content-free retention-policy reconciliation from synthetic states.

This is an offline product spike. It reads no agent history, contacts no
provider, and performs no deletion. The store states below are invented to
exercise the reporting model; they are not account observations.
"""

from __future__ import annotations

import json


POLICY = {"max_inactive_days": 30}

STORES = [
    {
        "surface": "claude_code_local",
        "scope": "local_session_files",
        "effective_retention_days": 30,
        "observed_state": "present",
        "inactive_days": 12,
        "deletion_state": "none",
        "owner": "endpoint_admin",
        "action": "Check the effective managed cleanup setting on enrolled devices.",
        "evidence_needed": "Read-only endpoint policy snapshot; not a deletion receipt.",
        "basis": "Synthetic managed setting at the 30-day limit.",
    },
    {
        "surface": "anthropic_compliance_api_local",
        "scope": "provider_retained_session_content",
        "effective_retention_days": 2190,
        "observed_state": "present",
        "inactive_days": 44,
        "deletion_state": "none",
        "owner": "organization_admin",
        "action": "Review the organization retention setting; the Compliance API cannot delete this record.",
        "evidence_needed": "Effective retention configuration and provider-side lifecycle evidence.",
        "basis": "Synthetic six-year default scenario; no API call was made.",
    },
    {
        "surface": "github_copilot_synced_sessions",
        "scope": "provider_synced_session_copies",
        "effective_retention_days": None,
        "observed_state": "present",
        "inactive_days": 52,
        "deletion_state": "none",
        "owner": "user_or_account_owner",
        "action": "Locate and delete the existing synced copies using the supported account flow.",
        "evidence_needed": "Per-session deletion result; sync-disabled alone is insufficient.",
        "basis": "Synthetic old cloud copies remain after sync is disabled.",
    },
    {
        "surface": "cursor_cloud_agent_conversation",
        "scope": "provider_cloud_conversation",
        "effective_retention_days": 90,
        "observed_state": "present",
        "inactive_days": 44,
        "deletion_state": "none",
        "owner": "organization_admin_or_api_operator",
        "action": "Use the documented per-agent deletion path if the policy requires removal now.",
        "evidence_needed": "Provider response for the specific agent; transcript and snapshot states stay separate.",
        "basis": "Synthetic 90-day Enterprise retention policy against a 30-day rule.",
    },
    {
        "surface": "cursor_environment_snapshot",
        "scope": "provider_cloud_snapshot",
        "effective_retention_days": 30,
        "observed_state": "present",
        "inactive_days": 21,
        "deletion_state": "none",
        "owner": "provider_lifecycle",
        "action": "Track the separate inactivity expiry; do not infer deletion from conversation removal.",
        "evidence_needed": "Snapshot lifecycle state or provider confirmation after expiry.",
        "basis": "Synthetic snapshot inside its documented inactivity window.",
    },
    {
        "surface": "unidentified_derived_memory_store",
        "scope": "derived_memory",
        "effective_retention_days": None,
        "observed_state": "unknown",
        "inactive_days": None,
        "deletion_state": "unknown",
        "owner": "unknown",
        "action": "Identify the store and its owner before making a compliance claim.",
        "evidence_needed": "Inventory evidence and the store's retention/deletion contract.",
        "basis": "Synthetic unknown store included to exercise fail-closed reporting.",
    },
]


def reconcile(policy: dict, stores: list[dict]) -> dict:
    """Classify policy evidence without treating configuration as erasure."""
    limit = policy["max_inactive_days"]
    rows = []

    for store in stores:
        configured = store["effective_retention_days"]
        observed = store["observed_state"]
        deletion = store["deletion_state"]
        inactive = store["inactive_days"]
        findings = []

        if configured is not None and configured > limit:
            findings.append("configured_retention_exceeds_policy")
        if observed == "present" and inactive is not None and inactive > limit:
            findings.append("record_observed_past_policy_limit")

        if deletion == "provider_confirmed":
            status = "provider_confirmed"
        elif deletion == "requested":
            status = "deletion_requested"
        elif observed == "unknown" or configured is None and store["owner"] == "unknown":
            status = "unverifiable"
        elif store["owner"] == "user_or_account_owner" and observed == "present":
            status = "user_action_required"
        elif configured is not None and configured > limit:
            status = "policy_mismatch_actionable" if store["owner"] != "unknown" else "unverifiable"
        elif configured is not None and configured <= limit:
            status = "policy_configured"
        else:
            status = "unverifiable"

        rows.append(
            {
                "surface": store["surface"],
                "scope": store["scope"],
                "status": status,
                "findings": findings,
                "owner": store["owner"],
                "next_action": store["action"],
                "evidence_needed": store["evidence_needed"],
                "basis": store["basis"],
            }
        )

    return {
        "synthetic_only": True,
        "policy": policy,
        "overall_assessment": "not_certified",
        "reason": "Configuration, user action, or a provider response does not prove physical erasure across all stores.",
        "attention_count": sum(row["status"] != "policy_configured" for row in rows),
        "stores": rows,
    }


if __name__ == "__main__":
    print(json.dumps(reconcile(POLICY, STORES), indent=2))
