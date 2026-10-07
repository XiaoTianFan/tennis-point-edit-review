"""Localize generated presentation text only; never translate evidence or IDs."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EN = json.loads((ROOT / 'references/output-en.json').read_text(encoding='utf8'))


def resolve_language(explicit=None, interaction=None, saved=None):
    """The agent supplies the dominant interaction language, not raw chat text.

    Explicit rendering requests win. Saved output language resumes existing work
    when no interaction language is supplied. Legacy callers retain Chinese.
    """
    value = explicit or interaction or saved or 'zh-CN'
    tag = value.lower().replace('_', '-')
    if tag == 'en' or tag.startswith('en-'):
        return 'en'
    if tag in ('zh', 'zh-cn', 'zh-hans', 'zh-hans-cn'):
        return 'zh-CN'
    raise ValueError('Unsupported output language: ' + value)


def text(value, language='zh-CN', **values):
    language = resolve_language(language)
    if language == 'en':
        if value not in EN and re.search('[\u3400-\u9fff]', value):
            raise ValueError('Missing English presentation text: ' + value)
        value = EN.get(value, value)
    return value.format(**values) if values else value


def localize(value, language='zh-CN'):
    """Use only on package defaults; explicit caller content stays untouched."""
    if isinstance(value, dict):
        return {k: localize(v, language) for k, v in value.items()}
    if isinstance(value, list):
        return [localize(v, language) for v in value]
    return text(value, language) if isinstance(value, str) else value


def default_props(component, language='zh-CN'):
    props = {p['key']: p['defaultValue'] for p in component['properties']}
    if 'rows' in props:
        props['rows'] = json.loads(props['rows'])
    props = localize(props, language)
    if 'rows' in props:
        props['rows'] = json.dumps(props['rows'], ensure_ascii=False)
    return props
