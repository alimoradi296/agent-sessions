# Source-origin hints

A User role does not establish who wrote every paragraph in that message.
Coding-agent exports can place attached skills, harness notices, copied replies, and direct requests in the same role.
Counting every instruction-like sentence as a fresh user correction produces misleading analysis.

Suggestions and assistant review packets now annotate recognized wrapper shapes without removing their text.
The method is `wrapper_shape_v1`.

| Hint | Recognized shape |
|---|---|
| `embedded_reference` | `skill` or `manually_attached_skills` wrapper |
| `harness_reference` | `available_subagent_types` wrapper |
| `wrapped_query` | `user_query` wrapper |
| `wrapped_reply` | `send_user_message_question_reply` wrapper |
| `mixed_wrapper_boundary` | Paragraph overlaps a wrapper and other text |
| `unattributed` | No recognized complete wrapper |

Plain text and incomplete wrappers remain unattributed.
None of these labels authenticates a person or grants current permission.
A copied or forged wrapper can receive the same hint.
Nested, unknown, and malformed formats are not fully parsed.

The annotation uses existing paragraph line locations.
It does not change quotes, paragraph hashes, source hashes, or selection requirements.
Known hints appear beside displayed paragraphs in review prompts.
Unattributed paragraphs retain the usual presentation, with a shared warning about authorship limits.
Suggestions expose the hint separately from their evidence anchor.

Embedded skills can contain relevant restrictions.
Those restrictions remain available for selection and exact-source validation.
Do not discard them merely because they appear inside a wrapper.
Conversely, repeated template text does not establish repeated user mistakes, lost memory, or a context-recovery request.

This change addresses a triage attribution problem, rather than establishing a new competitive capability.
Aggregate keyword counts remain candidate signals and require source review.
Historical reports of mistakes also need their surrounding request, tool arguments, and result before drawing stronger conclusions.
Private source material and incident reviews stay outside the repository.
