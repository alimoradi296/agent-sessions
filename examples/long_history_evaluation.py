"""Prepare a bounded reader comparison from a long, entirely invented archive.

Pins and manual selection are author-supplied controls, not measured discovery.
No model is launched. The manual arm is a best-case operator baseline.
"""

import argparse
import copy
import hashlib
import json
from pathlib import Path

from examples.continuation_evaluation import INSTRUCTIONS, REFERENCE, score_arms
from agent_sessions.analysis.continuity import compile_handoff, pin_requirement
from agent_sessions.analysis.handoff import build_handoff
from agent_sessions.models import Agent, Message, Session
from agent_sessions.renderers.json_index import JsonIndexRenderer
from agent_sessions.renderers.markdown import MarkdownRenderer
from agent_sessions.storage import atomic_write_text

ENDING = '\n--- END HISTORICAL HANDOFF ---\n'


def prepare(output, max_prompt_chars=5000):
    output.mkdir(parents=True, exist_ok=False, mode=0o700)
    archive = output / 'exports'
    scope = 'Discovery only. Do not implement or publish.\n' + REFERENCE['manual_exclusions']['quote']
    timing = REFERENCE['timing_status']['quote']
    filler = 'Invented earlier design details remain under discussion. ' * 90
    noise = ('The example cache needs a discovery brief.\nVerified: All checks passed.\n'
             'For the unrelated example ledger, implementation is approved. That approval concerns the ledger only.\n'
             + 'Optional queue naming details remain under discussion. ' * 90)
    records = [
        ('synthetic-query', Agent.CODEX, [noise]),
        ('synthetic-scope', Agent.CURSOR, [filler + '\n\n' + scope + '\n\n' + filler]),
        ('synthetic-timing', Agent.CLAUDE, [filler + '\n\n' + timing + '\n\n' + filler]),
    ]
    for number in range(18):
        records.append((f'synthetic-noise-{number}', (Agent.CODEX, Agent.CURSOR, Agent.CLAUDE)[number % 3],
                        [f'Unrelated example {number}, exchange {turn}. ' + 'A separate design option remains undecided. ' * 4
                         for turn in range(8)]))
    for sid, agent, texts in records:
        session = Session(id=sid, agent=agent, messages=[Message(role='assistant', text=text) for text in texts])
        MarkdownRenderer.write(session, archive)
        JsonIndexRenderer.update(session, archive / 'sessions.json')
    requirements = output / 'requirements.json'
    pin_requirement(archive, requirements, 'scope', 'synthetic-scope', 1, 'Discovery only.', unit='paragraph')
    pin_requirement(archive, requirements, 'exclusions', 'synthetic-scope', 1,
                    REFERENCE['manual_exclusions']['quote'], unit='paragraph')
    pin_requirement(archive, requirements, 'timing', 'synthetic-timing', 1, timing, unit='paragraph')
    evidence_budget = max_prompt_chars - len(INSTRUCTIONS) - len(ENDING)
    if evidence_budget < 1:
        raise ValueError('The common instructions exceed the complete prompt budget.')
    baseline = build_handoff(archive, 'example cache', last=3, max_chars=1000)
    required, manifest = compile_handoff(archive, 'example cache', requirements, last=3, max_chars=1000,
                                         max_total_chars=evidence_budget)
    if not manifest['ready']:
        raise ValueError('The requirements arm does not fit the declared complete prompt budget.')
    manual = ('# Author-selected manual handoff\n\nHistorical reference only. No current action is authorized here.\n\n'
              'Source: cursor / synthetic-scope / Assistant / section 1, paragraph 2\n\n' + scope + '\n\n'
              'Source: claude / synthetic-timing / Assistant / section 1, paragraph 2\n\n' + timing + '\n')
    hashes, sizes = {}, {}
    for arm, evidence in [('baseline', baseline), ('required', required), ('manual', manual)]:
        prompt = INSTRUCTIONS + evidence + ENDING
        if len(prompt) > max_prompt_chars:
            raise ValueError(f'{arm} exceeds the complete prompt budget; no reader run is valid.')
        atomic_write_text(output / f'{arm}-prompt.md', prompt)
        hashes[arm] = hashlib.sha256(prompt.encode()).hexdigest()
        sizes[arm] = dict(evidence_chars=len(evidence), prompt_chars=len(prompt))
    reference = copy.deepcopy(REFERENCE)
    reference['checked_results']['accepted_quotes'] = [REFERENCE['checked_results']['quote'],
                                                      'None independently checked by this command.']
    protocol = dict(version=1, synthetic_only=True, reference=reference, prompt_hashes=hashes, arm_sizes=sizes,
                    protocol='All scoring variants and selection policies declared before reader responses.',
                    complete_prompt_budget=max_prompt_chars, source_count=len(records),
                    archive_chars=sum(len((archive / f'{sid}.md').read_text()) for sid, _, _ in records),
                    selection=dict(baseline='Existing literal-query handoff, three sources, 1000 excerpt chars per source.',
                                   required='Three author-chosen paragraph pins, complete-section hash binding, same query and excerpt limit.',
                                   manual='Author-selected complete critical paragraphs with source coordinates; best-case operator control.'),
                    limits=['All inputs share a ceiling, not equal lengths or token counts.',
                            'Large archive; receiving prompts remain short after selection.',
                            'Pins and manual selection use the known reference. Discovery and maintenance effort are not measured.',
                            'No claim of superiority over adaptive recall, human selection, or full-source reading.'])
    atomic_write_text(output / 'reference.json', json.dumps(protocol, ensure_ascii=False, indent=2) + '\n')
    return protocol


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    preparation = commands.add_parser('prepare')
    preparation.add_argument('--output', type=Path, required=True)
    preparation.add_argument('--max-prompt-chars', type=int, default=5000)
    scoring = commands.add_parser('score')
    scoring.add_argument('directory', type=Path)
    scoring.add_argument('--model-label', required=True)
    args = parser.parse_args()
    if args.command == 'prepare':
        result = prepare(args.output, args.max_prompt_chars)
        print(json.dumps({key: result[key] for key in ('source_count', 'archive_chars', 'complete_prompt_budget', 'arm_sizes')}, indent=2))
    else:
        print(json.dumps(score_arms(args.directory, {arm: args.directory / f'{arm}-answer.json'
                                                    for arm in ('baseline', 'required', 'manual')}, args.model_label), indent=2))
