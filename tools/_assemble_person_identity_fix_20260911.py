from pathlib import Path
import json
import re
import subprocess

p = Path('lib/person-identity-validation.ts')
s = 'import policy from "./person-identity-policy.json";\n\n' + p.read_text()
s = re.sub(r'const NON_PERSON_TERMS = .*?;', 'const NON_PERSON_TERMS = new RegExp(policy.patterns.nonPersonTerms, "u");', s)
s = re.sub(r'const TITLE_BLEED = .*?;', 'const TITLE_BLEED = new RegExp(policy.patterns.titleBleed, "iu");', s)
s = '\n'.join('const SENTENCE_PUNCTUATION = new RegExp(policy.patterns.sentencePunctuation, "u");' if line.startswith('const SENTENCE_PUNCTUATION = ') else line for line in s.split('\n'))
s = s.replace('function clean(value: string | undefined) {', 'const PERSON_CHARACTERS = new RegExp(policy.patterns.personCharacters, "iu");\nconst LATIN_WORDS = new RegExp(policy.patterns.latinWords, "giu");\nconst WHITESPACE = new RegExp(policy.patterns.whitespace, "gu");\n\nfunction clean(value: string | undefined) {')
s = s.replace('normalize("NFKC").replace(/\\s+/gu, " ")', 'normalize(policy.normalizationForm).replace(WHITESPACE, " ")')
s = s.replace('name.length > 72 || englishName.length > 96', 'name.length > policy.maxNameUtf16Units || englishName.length > policy.maxEnglishNameUtf16Units')
s = s.replace('!/[a-z\\u3400-\\u9fff]/iu.test(name)', '!PERSON_CHARACTERS.test(name)')
s = s.replace("name.match(/[a-z][a-z.'’-]*/giu)", 'name.match(LATIN_WORDS)').replace('latinWords.length > 6', 'latinWords.length > policy.maxLatinWords')
p.write_text(s)

p = Path('lib/person-name-normalization.ts')
s = 'import identityPolicy from "./person-identity-policy.json";\n\n' + p.read_text()
s = s.replace('function clean(value: string): string {', 'const WHITESPACE = new RegExp(identityPolicy.patterns.whitespace, "g");\nconst CJK = new RegExp(identityPolicy.patterns.cjk);\nconst LATIN = new RegExp(identityPolicy.patterns.latin);\nconst HANDLE = new RegExp(identityPolicy.patterns.handle);\nconst BILINGUAL_LABEL = new RegExp(identityPolicy.patterns.bilingualLabel);\n\nfunction clean(value: string): string {')
s = s.replace('.replace(/\\s+/g, " ")', '.replace(WHITESPACE, " ")')
s = s.replace('/[\\u3400-\\u9fff]/.test(value)', 'CJK.test(value)').replace('/[A-Za-z\\u00c0-\\u024f]/.test(value)', 'LATIN.test(value)')
s = s.replace('value.match(/^(.*?)\\s+@([A-Za-z0-9_]{1,30})$/)', 'value.match(HANDLE)')
s = s.replace('label.match(/^(.+?)\\s*[（(]\\s*([^()（）]+?)\\s*[)）]?\\s*$/)', 'label.match(BILINGUAL_LABEL)')
p.write_text(s)

p = Path('tools/person_research_agent.py')
s = p.read_text().replace('import re\n', 'import re\nimport sys\n')
s = s.replace('ROOT = Path(__file__).resolve().parents[1]\n', 'ROOT = Path(__file__).resolve().parents[1]\nif str(ROOT) not in sys.path:\n    sys.path.insert(0, str(ROOT))\n\nfrom tools.person_identity_contract import validate_generated_person_identity\n\n')
s = s.replace('if not name or not slug:\n        return tasks', 'if not name or not slug or not validate_generated_person_identity(person)["valid"]:\n        return tasks')
p.write_text(s)
p = Path('tools/person_research_scheduler.py')
s = p.read_text().replace('from tools.person_research_agent import (', 'from tools.person_identity_contract import validate_generated_person_identity\nfrom tools.person_research_agent import (')
s = s.replace('        person = people.get(str(slug), {})\n        for task', '        person = people.get(str(slug))\n        # Reject stale agenda rows before ranking or allocating either workstream.\n        # A display label in an old agenda is not a current person identity.\n        if person is None or not validate_generated_person_identity(person)["valid"]:\n            continue\n        for task')
p.write_text(s)
p = Path('.github/workflows/scheduled-sync.yml')
s = p.read_text().replace('      - tools/person_research_agent.py\n', '      - tools/person_research_agent.py\n      - tools/person_identity_contract.py\n      - lib/person-identity-policy.json\n      - lib/person-identity-validation.ts\n      - lib/person-name-normalization.ts\n')
p.write_text(s)
p = Path('tools/full_refresh_input_guard.py')
s = p.read_text().replace('    "tools/full_refresh_input_guard.py",', '    "tools/full_refresh_input_guard.py",\n    "tools/person_research_agent.py",\n    "tools/person_research_scheduler.py",\n    "tools/person_identity_contract.py",\n    "lib/person-identity-policy.json",\n    "lib/person-identity-validation.ts",\n    "lib/person-name-normalization.ts",')
p.write_text(s)

rows = []
def add(label, name, english, valid, reason=''):
    rows.append({'case': label, 'candidate': {'name': name, 'englishName': english, 'aliases': [], 'handles': []}, 'expected': {'valid': True} if valid else {'valid': False, 'reason': reason}})
reason = 'title-or-organization-bleed'
for name in ['Class Presiden Thomas Sonderman', 'Massachusetts Governo Chris Ballance', 'CEO Chris Ballance', 'ＣＥＯ Chris Ballance', '张CEO李', 'John Classé Smith', 'Presiden_test User']:
    add(name, name, '', False, reason)
for name in ['Chris Ballance', 'Thomas Sonderman', 'Classical Smith', 'Clément Delangue', '王小川', '张三', 'ſ', 'K']:
    add(name, name, '', True)
add('model not person', '混合专家模型', 'Mixture of Experts', False, 'non-person-entity-term')
add('bilingual malformed', '黄仁勋(Jensen Huang', '', True)
add('bilingual reverse', 'Clément Delangue（克莱门特·德朗格）', '', True)
add('handle', '埃隆·马斯克 @elonmusk', '', True)
add('handle is not a title', 'Chris Ballance @company', '', True)
add('role parentheses not stripped', 'Chris Ballance (CEO)', '', False, reason)
add('english bleed retained', '黄仁勋', 'CEO Jensen Huang', False, reason)
add('fallback English only', '', 'Chris Ballance', True)
add('empty', '', '', False, 'missing-name')
add('digits', '123456', '', False, 'name-has-no-person-characters')
add('dotted I', 'İ', '', False, 'name-has-no-person-characters')
add('dotless I', 'ı', '', False, 'name-has-no-person-characters')
add('punctuation', '王小川：观点', '', False, 'sentence-like-name')
add('dash separator', 'Chris - Ballance', '', False, 'sentence-like-name')
add('seven words', 'One Two Three Four Five Six Seven', '', False, 'too-many-name-tokens')
add('length boundary', '张'*72, '', True)
add('length too long', '张'*73, '', False, 'name-too-long')
add('UTF16 counted', '张'+'😀'*36, '', False, 'name-too-long')
add('English boundary', '张三', 'A'*96, True)
add('English too long', '张三', 'A'*97, False, 'name-too-long')
add('FEFF whitespace', '\ufeffChris\ufeffBallance\ufeff', '', True)
add('NEL is not JS whitespace', 'Chris\x85Ballance', '', True)
p = Path('tests/fixtures/person-identity-contract.json')
p.parent.mkdir(exist_ok=True)
p.write_text('[\n' + ',\n'.join('  '+json.dumps(row, ensure_ascii=False) for row in rows) + '\n]\n')

expected = {
 '.github/workflows/scheduled-sync.yml': 'cb0b4838614c4dd1ec9752827f8463155bfd4f81',
 'lib/person-identity-policy.json': '74d06e6fca8764736322a92300d3129acbc11747',
 'lib/person-identity-validation.ts': 'd9b19468daff9b7f90caa3b96f44fdd9a56ec14b',
 'lib/person-name-normalization.ts': '06ce4f17134ba6b45d18c99cf62717809401b81a',
 'tests/fixtures/person-identity-contract.json': 'e095569acf6b97a9f93d6e74c15103832b431b8c',
 'tests/person-identity-parity.test.ts': 'aee72d9e9384c1f2685aff641f00aa9c4d753f44',
 'tests/test_person_identity_contract.py': '52638437f1ab0be620b696f8515f1e8aa347f3ea',
 'tools/full_refresh_input_guard.py': '548c37291e24e1c40c5cfbf069f38026f2a2cc22',
 'tools/person_identity_contract.py': 'bda8f4611dd1ddc645f56a91367e71085a7fd666',
 'tools/person_research_agent.py': 'a6d569e1d4a2662fc0bf809ef5647506179b5e73',
 'tools/person_research_scheduler.py': '1cce3cd88a219426ed323a1ff351c38547b14f31',
}
for path, sha in expected.items():
    actual = subprocess.check_output(['git', 'hash-object', path], text=True).strip()
    if actual != sha:
        raise RuntimeError(f'Locally validated content mismatch: {path}: {actual} != {sha}')
print('All 11 files exactly match locally validated blob hashes.')
