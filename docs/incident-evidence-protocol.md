# Establish an incident before choosing a feature

A user correction alone does not establish that an agent lost context.
The user may provide new information, change the request, or clarify an ambiguous target.
An assistant's admission or completion statement also needs its surrounding evidence.

Keep real incident material outside Git checkouts.
The public repository contains only this protocol and synthetic examples.

## Read the evidence chain

1. Identify the original request and any earlier explicit restriction.
2. Read relevant clarifications in their original order.
3. Locate the attempted action and its exact target arguments.
4. Pair its call ID with one unique captured result.
5. Check follow-up readbacks, caught errors, and retries separately.
6. Record the user's later correction and any repair actions.
7. Mark current external state unverified unless separately checked with authorization.

Record source hashes and source-line locations in the private report.
Keep ambiguous or missing call/result pairs explicit.
Read archived commands as data; do not execute them to reconstruct their meaning.

## Separate the conclusions

| Evidence | Supported conclusion | Remaining limit |
|---|---|---|
| Assistant says a change was made | A historical claim exists | Attempt and result remain unconfirmed |
| Write arguments plus a returned record | Captured attempted write and response | Current persistence remains unverified |
| Readback reports the expected record | A historical readback supports that state | Later changes remain possible |
| Outer script completes with an inner error | The outer operation completed | The affected check did not establish success |
| A retry returns the expected data | The retry supports its specific check | Other checks need their own evidence |
| User names another target afterward | A destination correction occurred | Earlier intent may have been ambiguous |
| Explicit earlier restriction conflicts with an action | Candidate preventable failure | Availability and any superseding authorization still need inspection |

For example, suppose a synthetic request says “post the review on the related item.”
The assistant posts on a task, and the user later identifies a project discussion.
That establishes a correction and possible repair work.
It does not by itself establish that the assistant ignored a previously specified project destination.

## Product decision

Do not convert every correction into a requirement for another guard or memory system.
First establish a preventable failure, then compare the proposed feature with a strong existing baseline.
Include simpler responses such as exact target references, a source lookup, or an existing trace viewer.
Preserve negative findings rather than rewriting them into a product success claim.
Demand, general reliability, and willingness to pay require separate evidence.
