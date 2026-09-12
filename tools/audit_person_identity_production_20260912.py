#!/usr/bin/env python3
"""Read-only acceptance of #490 from a pinned production commit and live CDN."""
from __future__ import annotations
import collections
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import types
import urllib.request
from html.parser import HTMLParser
from urllib.parse import urlsplit

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT))
OUT = Path(os.environ['AUDIT_OUTPUT'])
OUT.mkdir(parents=True, exist_ok=True)
EXPECTED = 'b4542b7d863715109176283c2058f87cf8149d07'
FIX = 'b9547622bf1e8fe8dd9006333591878eedeaae67'
BEFORE = 'fbe5111df6adcc13bb3fe19de288a06b58d8343c'
BASE = 'https://vciq.github.io'
BAD = {'class-presiden-thomas-sonderman', 'massachusetts-governo-chris-ballance', 'person-16c7c9ad4b'}
EXPECTED_BLOBS = {
    'people.json': '48ab6cc0e2268a971336e55199445a5da554ee68',
    'person_research_agenda.json': 'e21ea3c52a8caa90de0a1546df50811746bb22a9',
    'person_research_queue.json': '8cff2234f4a3af8f1f5db6ebd97dbbb77e7c3624',
    'person_research_outcomes.json': '056b3650d2de24a1c999ca4bee640f51ccc797f7',
    'research_agent_daily.json': '27e66b741689a8bc724ab06ed8358a6ad5145189',
    'research_agent_snapshot.json': '2cfc8cbf61641b0496c64dd44c2d148b18bd1a99',
    'articles.json': '3019d2c226ddec327f56410c4fae7ae1c895f7d8',
}
EXPECTED_HTML = '23f6eff5d4b1d9a3678b010aaa78e36666b4b6b7ef56fff71bfcd574070f2fdf'
report = {'issue': 490, 'startedAt': dt.datetime.now(dt.timezone.utc).isoformat(), 'sourceSha': EXPECTED, 'pagesRun': 34663792734, 'pagesArtifact': 10287594916, 'checks': [], 'observations': {}}

def check(name, passed, details=None):
    row = {'name': name, 'passed': bool(passed)}
    if details is not None: row['details'] = details
    report['checks'].append(row)
    if not passed: print('FAIL', name, json.dumps(details, ensure_ascii=False))

def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT).decode('utf-8')

def blob(raw):
    return hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()

def get(path):
    request = urllib.request.Request(BASE + path, headers={'User-Agent': 'VCIQ-read-only-release-acceptance', 'Cache-Control': 'no-cache'})
    with urllib.request.urlopen(request, timeout=40) as response:
        raw = response.read()
        check('http200.' + path, response.status == 200)
        return raw

class Links(HTMLParser):
    def __init__(self):
        super().__init__(); self.hrefs = []; self.ids = set()
    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        if 'id' in d: self.ids.add(d['id'])
        if tag == 'a' and d.get('href'): self.hrefs.append(d['href'])

def old_module(path, name):
    module = types.ModuleType(name)
    module.__file__ = str(ROOT / path)
    sys.modules[name] = module
    exec(compile(git('show', BEFORE + ':' + path), module.__file__, 'exec'), module.__dict__)
    return module

def audit():
    from tools.person_identity_contract import validate_generated_person_identity
    from tools.person_research_agent import build_agenda
    from tools.person_research_scheduler import build_daily_queue
    check('checkout.pinned', git('rev-parse', 'HEAD').strip() == EXPECTED)
    check('checkout.contains_fix', subprocess.run(['git', 'merge-base', '--is-ancestor', FIX, EXPECTED]).returncode == 0)
    provenance = json.loads(get('/build-provenance.json'))
    check('live.provenance.source', provenance.get('sourceSha') == EXPECTED, provenance.get('sourceSha'))
    report['provenance'] = provenance
    data = {}
    report['blobs'] = {}
    for name, expected in EXPECTED_BLOBS.items():
        source = (ROOT / 'public/data' / name).read_bytes()
        check('source.blob.' + name, blob(source) == expected, blob(source))
        live = get('/data/' + name)
        check('live.matches_source.' + name, live == source, {'sourceBlob': blob(source), 'liveBlob': blob(live)})
        data[name] = json.loads(source)
        report['blobs'][name] = blob(live)
    people = data['people.json']; agenda = data['person_research_agenda.json']; queue = data['person_research_queue.json']; memory = data['person_research_outcomes.json']; articles = data['articles.json']
    by_slug = {r['slug']: r for r in people['people']}
    rejected = {slug: validate_generated_person_identity(row) for slug, row in by_slug.items() if not validate_generated_person_identity(row)['valid']}
    report['rejectedIdentities'] = [{'slug': slug, 'name': by_slug[slug]['name'], **decision} for slug, decision in rejected.items()]
    check('agenda.no_missing_or_invalid', all(slug in by_slug and slug not in rejected for slug in agenda['people']))
    check('queue.no_missing_or_invalid', all(row['personSlug'] in by_slug and row['personSlug'] not in rejected for row in queue['queue']))
    check('agenda.known_bad_absent', not BAD.intersection(agenda['people']))
    check('queue.known_bad_absent', not any(r['personSlug'] in BAD for r in queue['queue']))
    check('queue.known_bad_query_budget_zero', sum(r['queryBudget'] for r in queue['queue'] if r['personSlug'] in BAD) == 0)
    check('raw_identity_records.not_deleted', BAD.issubset(by_slug))
    for name in ['Chris Ballance', 'Thomas Sonderman']:
        check('valid_fixture.' + name, validate_generated_person_identity({'name': name, 'englishName': '', 'aliases': [], 'handles': []})['valid'])
    check('agenda.generation_matches_people', agenda['generatedAt'] == people['generatedAt'])
    check('queue.generation_matches_agenda', queue['generatedAt'] == agenda['generatedAt'])
    check('agenda.generated_after_fix', dt.datetime.fromisoformat(agenda['generatedAt']) > dt.datetime.fromisoformat('2026-09-11T15:50:15+00:00'))
    rebuilt = build_agenda(people, articles)
    check('agenda.exact_deterministic_rebuild', rebuilt == agenda)
    rebuilt_queue = build_daily_queue(agenda, people, memory)
    check('queue.exact_deterministic_rebuild', rebuilt_queue == queue)
    old_planner = old_module('tools/person_research_agent.py', 'audit_old_planner')
    old_agenda = old_planner.build_agenda(people, articles)
    expected_retained = {s: r for s, r in old_agenda['people'].items() if s not in rejected}
    check('valid_people.task_records_unchanged', expected_retained == agenda['people'])
    old_scheduler = old_module('tools/person_research_scheduler.py', 'audit_old_scheduler')
    old_filtered_queue = old_scheduler.build_daily_queue(agenda, people, memory)
    check('valid_people.scoring_lanes_queries_unchanged', old_filtered_queue == queue)
    stale_guard = build_daily_queue(old_agenda, people, memory)
    check('stale_agenda.cannot_reintroduce_invalid', stale_guard == queue)
    js = "import {researchPeople} from './lib/people-data.ts'; console.log(JSON.stringify(researchPeople.map(p=>p.slug)));"
    canonical = set(json.loads(subprocess.check_output(['node', '--import', 'tsx', '--input-type=module', '-e', js], cwd=ROOT)))
    check('agenda.canonical_public_membership', set(agenda['people']).issubset(canonical))
    check('queue.canonical_public_membership', all(r['personSlug'] in canonical for r in queue['queue']))
    check('canonical.known_bad_absent', not BAD.intersection(canonical))
    counts = collections.Counter(r['personSlug'] for r in queue['queue'])
    check('queue.count_summary', len(counts) == queue['selectedPeopleCount'] and len(queue['queue']) == queue['selectedTaskCount'])
    check('agenda.count_summary', len(agenda['people']) == agenda['personCount'] and sum(len(r['tasks']) for r in agenda['people'].values()) == agenda['taskCount'])
    check('queue.query_summary', sum(r['queryBudget'] for r in queue['queue']) == queue['allocatedQuerySlots'])
    check('queue.limits', len(counts) <= queue['limits']['people'] and len(queue['queue']) <= queue['limits']['tasks'] and max(counts.values(), default=0) <= queue['limits']['tasksPerPerson'] and queue['allocatedQuerySlots'] <= queue['limits']['activeQuerySlots'])
    check('queue.maintenance_limits', queue['selectedMaintenanceTaskCount'] <= queue['limits']['maintenanceTasks'] and queue['allocatedMaintenanceQuerySlots'] <= queue['limits']['maintenanceQuerySlots'])
    old_unfiltered = old_scheduler.build_daily_queue(old_agenda, people, memory)
    report['sameInputComparison'] = {
        'before': {'agendaPeople': old_agenda['personCount'], 'agendaTasks': old_agenda['taskCount'], 'selectedTasks': old_unfiltered['selectedTaskCount'], 'querySlots': old_unfiltered['allocatedQuerySlots']},
        'after': {'agendaPeople': agenda['personCount'], 'agendaTasks': agenda['taskCount'], 'selectedTasks': queue['selectedTaskCount'], 'querySlots': queue['allocatedQuerySlots']},
        'removedTaskCount': old_agenda['taskCount'] - agenda['taskCount'],
    }
    report['production'] = {'generatedAt': agenda['generatedAt'], 'rawPeople': len(by_slug), 'agendaPeople': agenda['personCount'], 'agendaTasks': agenda['taskCount'], 'selectedPeople': queue['selectedPeopleCount'], 'selectedTasks': queue['selectedTaskCount'], 'researchTasks': queue['selectedResearchTaskCount'], 'maintenanceTasks': queue['selectedMaintenanceTaskCount'], 'querySlots': queue['allocatedQuerySlots'], 'limits': queue['limits'], 'outcomeAttempts': memory['attemptCount']}
    report['dataCommits'] = {name: git('log', '-1', '--format=%H|%aI|%an|%s', '--', 'public/data/' + name).strip() for name in ['people.json', 'person_research_agenda.json', 'person_research_queue.json']}
    lineage = json.loads(get('/data/data_lineage.json'))
    report['producers'] = {}
    for name in ['people.json', 'person_research_agenda.json', 'person_research_queue.json']:
        row = lineage['artifacts']['public/data/' + name]
        producer = row.get('producer', {})
        report['producers'][name] = producer
        check('producer.normal_full_refresh.' + name, producer.get('jobId') == 'public-intelligence-full-refresh' and producer.get('status') == 'success' and producer.get('qualityGate') == 'passed')
        check('producer.content_hash.' + name, row.get('contentSha256') == hashlib.sha256((ROOT / 'public/data' / name).read_bytes()).hexdigest())
    html_bytes = get('/research-agent/')
    check('live.html_matches_deployed_artifact', hashlib.sha256(html_bytes).hexdigest() == EXPECTED_HTML, hashlib.sha256(html_bytes).hexdigest())
    html = html_bytes.decode(); parser = Links(); parser.feed(html)
    check('html.known_bad_routes_absent', all(not any('/people/' + bad + '/' in href for bad in BAD) for href in parser.hrefs))
    check('html.history_anchor', 'history' in parser.ids)
    targets = sorted({urlsplit(h).path for h in parser.hrefs if h.startswith('/people/')})
    report['personLinks'] = targets
    for path in targets:
        raw = get(path)
        check('person_route.not_soft_404.' + path, b'<main' in raw and b'This page could not be found' not in raw)
    for person in queue['queue']:
        check('selected_person.has_source_agenda.' + person['taskId'], any(t['id'] == person['taskId'] for t in agenda['people'][person['personSlug']]['tasks']))
    daily = data['research_agent_daily.json']; snapshot = data['research_agent_snapshot.json']
    report['researchScope'] = daily.get('researchScope')
    for dataset in ['technology', 'track', 'person', 'ventureCompany']:
        entry = daily['researchScope'][dataset]
        check('research_scope.' + dataset, entry['status'] == 'active' and entry['count'] == len(snapshot['datasets'][dataset]))
    thesis = daily['thesisMemory']; observations = thesis['observations']; ids = {r['id'] for r in observations}
    check('thesis_memory.integrity', len(ids) == len(observations) == thesis['observationCount'] and set(thesis['currentObservationIds']).issubset(ids) and all(r.get('evidence') for r in observations))
    report['thesisObservationCount'] = len(observations)
    health = json.loads(get('/data/pipeline_health.json'))
    report['pipelineHealth'] = {'overallStatus': health['overallStatus'], 'summary': health['summary'], 'nonhealthy': [{'jobId': j['jobId'], 'status': j['status']} for j in health['jobs'] if j['status'] != 'healthy']}
    end = json.loads(get('/build-provenance.json'))
    check('live.provenance_stable_through_audit', end.get('sourceSha') == EXPECTED, end.get('sourceSha'))
    check('source.no_writes', subprocess.run(['git', 'diff', '--exit-code', '--', 'config', 'public/data'], stdout=subprocess.DEVNULL).returncode == 0)

try:
    audit()
except Exception as exc:
    check('audit.unhandled_error', False, {'type': type(exc).__name__, 'message': str(exc)[:500]})
    raise
finally:
    report['completedAt'] = dt.datetime.now(dt.timezone.utc).isoformat()
    report['passed'] = sum(c['passed'] for c in report['checks'])
    report['total'] = len(report['checks'])
    report['success'] = report['passed'] == report['total']
    (OUT / '490-production-audit.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: report[k] for k in ['success', 'passed', 'total', 'completedAt']}, ensure_ascii=False))
if not report['success']:
    raise SystemExit(1)
