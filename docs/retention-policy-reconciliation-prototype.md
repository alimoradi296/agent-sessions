# Retention-policy reconciliation: synthetic product test

**Status:** Offline synthetic workflow spike. No provider integrations or deletion actions were run. The runnable example is [retention_reconciliation_demo.py](../examples/retention_reconciliation_demo.py).

## Product question

Can one content-free workflow tell an organization whether a 30-day coding-agent data-retention rule is actually enforced across local transcripts, provider-synced sessions, cloud-agent records, and persistent memories—and show which operator action can close each gap?

The proposed user is an enterprise security or privacy operator responsible for AI coding tools. The outcome is a trustworthy list of policy exceptions and the action owner. This is a product hypothesis, not a selected feature: no recurring buyer workflow, deployment feasibility, or willingness to pay has been established.

## Synthetic policy

> Remove local and provider-held coding-agent session content no later than 30 days after inactivity. Do not retain another transcript copy in this service. For every store, report whether the policy is configured, deletion was requested, deletion was confirmed by the provider, user action is required, or the store cannot be verified. Never label an unknown store compliant.

This scenario uses no real transcript, account, device, or organization data. It is a desk-research comparison against published controls, not a live compliance test.

## Expected reconciliation from reviewed documentation

| Store | Published control | Expected policy state | What the operator would need to do |
|---|---|---|---|
| Claude Code local files | Enterprise managed `cleanupPeriodDays` controls local cleanup; local data is on employee devices | **Unknown until endpoint setting is observed** | Verify effective endpoint configuration and distinguish it from provider-side records. Do not infer a successful purge from the configured value alone. |
| Anthropic Compliance API local sessions | Six-year default or organization-configured conversation retention; API is read-only for deletion; HIPAA/ZDR cases have exceptions | **Policy mismatch or unverified until retention is checked** | Set and confirm the organization retention period where available; label deletion as unavailable through this API. |
| GitHub Copilot local and synced sessions | Local deletion and synced-copy deletion are separate controls; disabling sync does not delete existing synced copies | **Existing copies require separate review** | Disable future sync if policy requires it; use the documented deletion flow for prior cloud copies and keep admin/user ownership explicit. |
| Cursor Cloud Agent conversations | Indefinite by default; Enterprise policy offers 90 days, with custom windows in early access; Delete Agent API removes conversation transcript and artifacts | **The synthetic 90-day setting exceeds 30 days; custom windows may change this for eligible teams** | Verify the team's effective window and deletion result. Do not infer snapshot removal from transcript deletion. |
| Cursor environment snapshots | Separate maximum 30-day inactivity lifecycle; snapshots cannot be deleted on demand | **Lifecycle differs from the policy's inactivity definition** | Report the exact expiry condition and residual period; do not promise immediate deletion. |
| Microsoft Copilot saved memories | Purview retention policies do not apply; no admin retention control; users delete saved memories | **Not centrally enforceable through Purview** | Require user-side deletion or disable application of memory at admin level while clearly reporting that stored memories remain. This is adjacent Microsoft Copilot evidence, not proof about GitHub Copilot coding-agent memory. |
| Stacktrace Fleet | Its public policy controls component allow/block/approval; the published rule list does not state session-age deletion enforcement | **No documented retention control in reviewed material** | Compare any actual account capability before treating this as an unmet need. Public documentation is not proof of absence. |

Sources: [Claude Compliance API](https://platform.claude.com/docs/en/manage-claude/compliance-sessions), [Claude enterprise local-mode guidance](https://support.claude.com/en/articles/17318731-use-claude-code-local-mode-and-claude-cowork-local-mode-on-a-hipaa-ready-enterprise-plan), [GitHub session data controls](https://docs.github.com/en/copilot/concepts/security-governance-and-network-settings/session-data), [Cursor Cloud Agent retention and deletion](https://prod.cursor.com/docs/cloud-agent/security-network), [Microsoft Copilot memory controls](https://learn.microsoft.com/en-us/microsoft-365/copilot/copilot-personalization-memory), and [Stacktrace Fleet](https://stacktrace.ai/fleet/).

## Desk comparison result

The published baseline splits the job across endpoint settings, per-user deletion flows, provider retention settings, and cloud APIs. In this synthetic case, a reconciler should flag at least three follow-up actions: confirm whether Anthropic's effective organization retention meets 30 days; locate and separately delete any previously synced GitHub sessions; and use Cursor's per-agent delete API when its minimum Enterprise retention window exceeds the policy. It should also report Cursor snapshots as a separate store with a different expiry condition. The provider documentation does not establish that the same organization can automate every action or obtain a deletion confirmation for every store.

Stacktrace Fleet is a useful same-category baseline for cross-agent inventory and policy, but its public policy examples concern agent components and actions, not a maximum age or deletion receipt. Purview covers supported Copilot and AI-app interactions, but its own documentation excludes Copilot saved memory from admin retention. The [AI Developer Toolkit publishes a ready-to-use manual AI service register](https://developertoolkit.ai/en/org/privacy-data-handling/) with one record per tool, plan, route, retention period, owner, and change trigger. That register can represent much of this spike's inventory manually. Thus the remaining hypothesis is automated state discovery and drift detection, not a new retention matrix. This source review has not measured completeness against a live tenant, time saved over that manual register and MDM scripts, or whether the follow-ups are valuable enough to buy.

The first offline spike produces six surface rows: two `policy_configured`, one `policy_mismatch_actionable` for Anthropic, one `user_action_required` for prior GitHub synced copies, one `policy_mismatch_actionable` for Cursor Cloud Agents, and one `unverifiable` derived-memory store. The overall status remains `not_certified`; it never calls the synthetic organization compliant. It correctly keeps Cursor snapshots separate from conversations.

This proves only that the status model can represent the authored scenario. It does not compare operator decisions with the manual baseline, observe real settings, measure time saved, establish that an action can be completed, or justify a production build. If a later same-case comparison shows the example merely repeats settings pages or emits unresolved warnings, stop.

## Proposed comparison

Compare a content-free reconciler with the documented operator baseline: provider admin settings, vendor delete flows, the organization's MDM/Purview, Stacktrace or GitLab AI governance, and the manual AI service register. Score only observable outcomes:

1. Did it identify every synthetic store and the responsible control owner?
2. Did it distinguish policy configured, deletion requested, provider-confirmed, user-action required, and unverifiable?
3. Did it avoid calling unknown or out-of-scope data compliant?
4. Did it identify an actionable retention violation the baseline missed?
5. Did it reduce operator time without collecting transcript content?

Use synthetic records with known expected states. A useful result requires zero false-compliant classifications and at least one material, actionable gap absent from the same-case baseline. Otherwise, stop: a more polished dashboard is not a product wedge.

## Hard limits

- Local filesystem inspection cannot establish provider-side deletion.
- A provider API's accepted deletion request is not a provider-confirmed physical purge.
- Retention and legal holds can require retaining data after an end-user delete request.
- Existing company MDM, scripts, and vendor controls may already solve the operator's job.
- Microsoft Copilot saved-memory behavior must not be generalized to GitHub Copilot coding-agent memory.
- No source reviewed here proves buyer demand or willingness to pay.

## Fit with this repository

The current archive readers cannot populate a reliable service/route register. The [Codex reader](../agent_sessions/parsers/codex.py) records `model_provider` and model identifiers when present. The [Claude reader](../agent_sessions/parsers/claude.py) records a model identifier but no authentication account or provider route. The [Cursor reader](../agent_sessions/parsers/cursor.py) documents that its transcript schema has no built-in model or provider field. The shared [session model](../agent_sessions/models.py) has no authenticated tenant, plan, effective retention, or route-confirmation field. A local transcript therefore cannot establish which organization account or backend received the prompt.

There are already stronger live-source options for some surfaces: VS Code's [OpenTelemetry integration](https://code.visualstudio.com/docs/agents/guides/monitoring-agents) emits provider, requested/resolved model, and conversation identifiers, while Cursor Enterprise documents [model access controls and an Admin API](https://prod.cursor.com/docs/enterprise/model-and-integration-management). Those sources do not cover every agent or prove end-to-end deletion, but they make an archive-only product a weak place to build route inventory. Correcting this would require new endpoint and provider integrations, not just extending the current report renderer.

## Go/no-go gate

Do not implement production connectors until the synthetic comparison shows a material decision improvement over native tools and governance platforms. Even a positive synthetic result only justifies a scoped feasibility spike; enterprise buyer validation and provider integration contracts remain separate gates.

## Current API feasibility update (October 28, 2026)

Anthropic now documents a read-only Compliance API endpoint that returns **effective** organization settings, including typed `data_retention_periods`. Its response can distinguish fixed durations from indefinite retention. A missing data-type key means no administrator-configured period is in force for that type; Anthropic service defaults may still apply. An `all` key covers every data type and is exclusive. The setting endpoint requires `read:compliance_org_data`, must be enabled for the parent organization, and targets linked organizations. See the [effective settings API reference](https://platform.claude.com/docs/en/api/http/compliance/organizations/settings/retrieve) and [organization settings guide](https://platform.claude.com/docs/en/manage-claude/compliance-org-data).

This is stronger than the earlier assumption that every setting needed manual inspection: at least one provider exposes machine-readable effective retention state. It still does not prove that a given local session was captured, that every account route is in scope, or that a retention period caused physical deletion. Treat the endpoint as a settings signal, not a deletion receipt. The API response also contains unrelated key metadata; any implementation should normalize only the required setting fields and never store raw responses by default.

Cursor's current documentation describes Enterprise retention settings and a delete API for Cloud Agent conversations, while its published Cloud Agents API reference documents agent operations but no organization retention-policy field. Therefore, code should classify Cursor retention as **operator-verified** until the vendor publishes a machine-readable setting contract. GitHub's documented Copilot usage-record endpoint is limited to certain Enterprise Managed Users/data-residency organizations; it is activity evidence, not a general retention-setting API. See [Cursor retention controls](https://prod.cursor.com/docs/cloud-agent/security-network), [Cursor Cloud Agents API](https://prod.cursor.com/docs/cloud-agent/api/endpoints), and [GitHub Copilot usage records](https://docs.github.com/en/enterprise-cloud%40latest/rest/copilot/copilot-usage-metrics).

[Coder Agents](https://coder.com/beta-docs/ai-coder/agents/platform-controls/chat-retention/) provides a direct API to read or update the retention period for its own archived conversations, with separate cleanup for debug data and referenced files. This is important same-surface competition: a retention controller would need to show value across independently administered providers, not merely automate a setting for one hosted coding-agent platform.

### Next synthetic comparison

Use invented API responses with three states: an explicit fixed retention period, a missing key with a documented provider default, and an unsupported or unavailable setting. Compare:

1. A manual AI-service register filled from the same official documentation.
2. A content-free reconciler that consumes only the documented read-only settings response where available and requires a human citation for other providers.

Score false-compliant results, unresolved stores, actionable exceptions, and operator steps. The reconciler advances only if it catches a material policy mismatch the manual register misses, while labeling unsupported or unknown states honestly. Otherwise close the lead. This remains a contract-level synthetic evaluation; no tenant credentials, provider calls, transcripts, or deployment claims are authorized or implied.

### Contract-level comparison result (October 28, 2026)

I applied that comparison to the documented API contracts using invented, same-day effective settings. This is a source-based scenario analysis, not a running product or a provider call.

| Provider surface | Manual register with current evidence | API-aware report | Incremental result |
|---|---|---|---|
| Anthropic linked Enterprise org | Records a 30-day setting after an admin checks the effective settings endpoint | Reads the same effective 30-day setting | Same policy finding; the API can refresh it without a manual console lookup |
| Coder Agents | Records the 30-day configured value from its admin/API surface | Reads the same retention-days value | Same policy finding; Coder already supplies the product-specific control |
| Cursor Cloud Agents | Records a 90-day or indefinite setting from admin evidence | Cannot read a retention-policy field from the published Cloud Agents API; asks an operator to verify | No automated advantage; same manual step remains |
| GitHub Copilot | Records sync and deletion controls from its supported admin workflow | Usage-record API is restricted to eligible enterprise setups and does not itself prove retention or deletion | No general automated retention finding |

With both methods given fresh evidence, the API-aware report finds **no policy mismatch the manual register misses**. If the manual register is stale, the Anthropic API can detect drift, but that advantage depends on how often settings change and how often people refresh the register; neither frequency nor avoided review time is measured. Cursor and GitHub remain manual or unknown. Existing vendor APIs already automate their own settings, so a cross-provider layer must prove value from ongoing drift detection across multiple services, not from normalizing one API response.

**Decision:** this comparison does not justify a product prototype or production connector. Keep the lead as a conditional research question only: do organizations with multiple coding-agent providers experience retention-setting drift often enough that periodic API checks save meaningful audit or rollout work? The public forum request supports one user's desired outcome; it does not answer frequency, cross-provider scope, or willingness to pay. Public documentation, this synthetic comparison, and listed prices are insufficient to select this as the paid product.
