"""Explicit session-metadata boundaries, without inferred project identity."""

from __future__ import annotations

import hashlib
import json


def normalize_projects(projects=None):
    if projects is None:
        return []
    if (not isinstance(projects, list) or len(projects) > 32
            or any(not isinstance(value, str) or not value.strip() or len(value) > 4096 for value in projects)):
        raise ValueError('Project scope needs at most 32 nonempty exact metadata values.')
    return sorted(set(projects))


def project_matches(row, projects):
    """Match an exact recorded cwd or project slug, never a guessed alias."""
    if not projects:
        return True
    return any(value == row.get('cwd') or value == row.get('project_slug') for value in projects)


def scope_summary(rows, projects):
    return dict(method='exact_session_metadata_v1', projects=projects, indexed_sources=len(rows),
                in_scope_sources=sum(project_matches(row, projects) for row in rows.values()),
                excluded_sources=sum(not project_matches(row, projects) for row in rows.values()),
                missing_project_metadata=sum(not row.get('cwd') and not row.get('project_slug') for row in rows.values()))


def review_scope_hash(rows, projects):
    """Bind review-visible identities and membership, excluding unrelated rows.

    Source bytes have their own hashes. Index formatting, titles and counters
    do not change the source-selection prompt's identity metadata.
    """
    selected = {sid: {key: row.get(key, '') for key in ('agent', 'cwd', 'project_slug')}
                for sid, row in rows.items() if project_matches(row, projects)}
    return hashlib.sha256(json.dumps(selected, sort_keys=True, ensure_ascii=False,
                                     separators=(',', ':')).encode()).hexdigest()


def assistant_review_is_stale(review, query, projects, rows, snapshots, index_sha256):
    metadata_changed = (review['scope_sha256'] != review_scope_hash(rows, projects)
                        if 'scope_sha256' in review else review['index_sha256'] != index_sha256)
    return (review['query'] != query or review['projects'] != projects
            or metadata_changed or review['source_snapshots'] != snapshots)
