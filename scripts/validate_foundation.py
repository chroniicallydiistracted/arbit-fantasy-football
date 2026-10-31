#!/usr/bin/env python3
"""Offline checks for Arbit's planning artifacts; not a product/runtime test suite."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from urllib.parse import unquote, urlsplit
from uuid import UUID

KEYWORDS = {
    '$schema', '$id', 'title', 'description', 'type', 'const', 'enum', 'required',
    'properties', 'additionalProperties', 'items', 'minItems', 'uniqueItems',
    'minimum', 'maximum', 'minLength', 'pattern', 'format',
}


def load_json(path: Path):
    def invalid_constant(value: str):
        raise ValueError(f'non-finite JSON constant {value}')

    return json.loads(path.read_text(encoding='utf-8'), parse_constant=invalid_constant)


def matches_type(value, kind: str) -> bool:
    return {
        'object': lambda: isinstance(value, dict),
        'array': lambda: isinstance(value, list),
        'string': lambda: isinstance(value, str),
        'integer': lambda: isinstance(value, int) and not isinstance(value, bool),
        'number': lambda: isinstance(value, (int, float)) and not isinstance(value, bool)
        and (isinstance(value, int) or math.isfinite(value)),
        'boolean': lambda: isinstance(value, bool),
        'null': lambda: value is None,
    }.get(kind, lambda: False)()


def schema_errors(schema: dict, value, location: str = '$') -> list[str]:
    """Validate only the declared keyword subset; unknown keywords fail closed."""
    errors = []
    unknown = set(schema) - KEYWORDS
    if unknown:
        errors.append(f'{location}: unsupported schema keywords {sorted(unknown)}')
    kinds = schema.get('type', [])
    kinds = [kinds] if isinstance(kinds, str) else kinds
    if kinds and not any(matches_type(value, kind) for kind in kinds):
        return errors + [f'{location}: expected type {kinds}']
    if 'const' in schema and value != schema['const']:
        errors.append(f'{location}: value does not match declared constant')
    if 'enum' in schema and value not in schema['enum']:
        errors.append(f'{location}: value outside declared enum')
    if isinstance(value, dict):
        properties = schema.get('properties', {})
        for name in schema.get('required', []):
            if name not in value:
                errors.append(f'{location}: missing required field {name}')
        if schema.get('additionalProperties') is False:
            for name in value.keys() - properties.keys():
                errors.append(f'{location}: unexpected field {name}')
        for name, child in properties.items():
            if name in value:
                errors.extend(schema_errors(child, value[name], f'{location}.{name}'))
    if isinstance(value, list):
        if len(value) < schema.get('minItems', 0):
            errors.append(f'{location}: too few items')
        if schema.get('uniqueItems') and len({json.dumps(x, sort_keys=True) for x in value}) != len(value):
            errors.append(f'{location}: duplicate items')
        for index, item in enumerate(value):
            if 'items' in schema:
                errors.extend(schema_errors(schema['items'], item, f'{location}[{index}]'))
    if isinstance(value, str):
        if len(value) < schema.get('minLength', 0):
            errors.append(f'{location}: string too short')
        if 'pattern' in schema and not re.search(schema['pattern'], value):
            errors.append(f'{location}: string does not match declared pattern')
        try:
            if schema.get('format') == 'uuid':
                if str(UUID(value)) != value.lower():
                    raise ValueError('noncanonical UUID')
            elif schema.get('format') == 'date-time':
                parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
                if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
                    raise ValueError('UTC timestamp required')
            elif schema.get('format') is not None:
                raise ValueError('unsupported format')
        except ValueError:
            errors.append(f'{location}: invalid {schema.get("format")} format')
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if 'minimum' in schema and value < schema['minimum']:
            errors.append(f'{location}: number below minimum')
        if 'maximum' in schema and value > schema['maximum']:
            errors.append(f'{location}: number above maximum')
    return errors


def luminance(color: str) -> float:
    if not re.fullmatch(r'#[0-9A-Fa-f]{6}', color):
        raise ValueError('expected six-digit hex color')
    values = [int(color[index:index + 2], 16) / 255 for index in (1, 3, 5)]
    linear = [value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4 for value in values]
    return sum(channel * weight for channel, weight in zip(linear, (0.2126, 0.7152, 0.0722)))


def contrast(first: str, second: str) -> float:
    high, low = sorted((luminance(first), luminance(second)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def project_artifacts(root: Path, pattern: str) -> list[Path]:
    """Project artifacts exclude local captures, private state and vendor checkouts."""
    local_roots = {'.references', '.superpowers', 'data', 'artifacts', 'local-storage', 'secrets'}
    return sorted(
        path for path in root.rglob(pattern)
        if path.relative_to(root).parts[0] not in local_roots
        and not any(part in {'.git', 'node_modules', '.venv'} for part in path.relative_to(root).parts)
    )


def validate(root: Path) -> tuple[list[str], dict[str, int]]:
    errors = []
    counts = {}
    manifest = load_json(root / 'foundation-manifest.json')
    for filename in manifest['requiredFiles']:
        if not (root / filename).is_file():
            errors.append(f'Missing required artifact: {filename}')
    if errors:
        return errors, counts

    json_files = project_artifacts(root, '*.json')
    for path in json_files:
        load_json(path)
    counts['JSON artifacts'] = len(json_files)

    source = load_json(root / 'docs/product/source-manifest.json')
    actual_hash = hashlib.sha256((root / source['sourceFile']).read_bytes()).hexdigest()
    if actual_hash != source['sha256']:
        errors.append('Original owner brief checksum does not match source manifest')

    docs = project_artifacts(root, '*.md')
    link_pattern = re.compile(r'(?<!!)\[[^\]]+\]\((<[^>]+>|[^)\s]+)\)')
    for path in docs:
        for match in link_pattern.finditer(path.read_text(encoding='utf-8')):
            target = match.group(1).strip('<>')
            parsed = urlsplit(target)
            if parsed.scheme or not parsed.path:
                continue
            linked = (path.parent / unquote(parsed.path)).resolve()
            if not linked.is_relative_to(root):
                errors.append(f'{path.relative_to(root)}: local link leaves repository: {target}')
            elif not linked.exists():
                errors.append(f'{path.relative_to(root)}: broken local link: {target}')
    counts['Markdown documents'] = len(docs)

    registry = load_json(root / 'docs/product/requirements.json')['requirements']
    requirement_ids = set()
    covered_sections = set()
    covered_groups = set()
    roadmap = (root / 'docs/project/roadmap.md').read_text(encoding='utf-8')
    table = (root / 'docs/product/requirements.md').read_text(encoding='utf-8')
    for requirement in registry:
        rid = requirement['id']
        if not re.fullmatch(r'[A-Z]+-\d{3}', rid) or rid in requirement_ids:
            errors.append(f'Invalid or duplicate requirement ID: {rid}')
        requirement_ids.add(rid)
        covered_groups.add(rid.split('-')[0])
        covered_sections.update(section.split('.')[0] for section in requirement['sourceSections'])
        if not (root / requirement['spec']).is_file():
            errors.append(f'{rid}: missing owning specification')
        if not requirement['acceptance'].strip() or not requirement['sourceSections']:
            errors.append(f'{rid}: missing acceptance/source traceability')
        if f"## {requirement['milestone']} " not in roadmap:
            errors.append(f'{rid}: missing roadmap milestone')
        expected_row = f"| {rid} | {requirement['title']} | {', '.join(requirement['sourceSections'])} | {requirement['milestone']} | {requirement['acceptance']} |"
        if expected_row not in table:
            errors.append(f'{rid}: Markdown traceability table differs from JSON registry')
        if requirement['status'] not in {'specified', 'in_progress', 'implemented', 'verified', 'blocked'}:
            errors.append(f'{rid}: invalid requirement status')
    if covered_sections != {str(index) for index in range(1, 13)}:
        errors.append('Requirement registry does not cover all original sections 1–12')
    required_groups = {'CTX', 'FO', 'DR', 'LN', 'WA', 'TR', 'SC', 'LV', 'MD', 'AR', 'DATA', 'UX', 'ENG', 'GOV', 'PLAN', 'SUCCESS'}
    if required_groups - covered_groups:
        errors.append(f'Missing requirement groups: {sorted(required_groups - covered_groups)}')
    counts['traceable requirements'] = len(registry)

    league = load_json(root / 'config/league.json')
    errors.extend(schema_errors(load_json(root / 'packages/contracts/schemas/league-config.schema.json'), league, 'league config'))
    recommendation = load_json(root / 'tests/fixtures/recommendation.example.json')
    rec_errors = schema_errors(load_json(root / 'packages/contracts/schemas/recommendation.schema.json'), recommendation, 'recommendation example')
    errors.extend(rec_errors)
    if not rec_errors:
        if recommendation['synthetic'] is not True:
            errors.append('Contract example must be explicitly synthetic')
        if recommendation['context']['leagueId'] != league['leagueId'] or recommendation['context']['season'] != league['season']:
            errors.append('Contract example and configured league/season differ')
        if recommendation['confidence']['kind'] != 'validated' and recommendation['confidence']['probability'] is not None:
            errors.append('Unvalidated recommendation must not contain numeric confidence probability')
        if Decimal(recommendation['projection']['lower']) > Decimal(recommendation['projection']['upper']):
            errors.append('Recommendation interval bounds reversed')
        lineage = recommendation['lineage']
        generated = datetime.fromisoformat(lineage['generatedAt'].replace('Z', '+00:00'))
        for key in ('featureCutoff', 'sourceObservedAt'):
            if datetime.fromisoformat(lineage[key].replace('Z', '+00:00')) > generated:
                errors.append(f'Recommendation {key} is after generation time')

    tokens = load_json(root / 'packages/design-tokens/tokens.json')
    pair_count = 0
    if set(tokens['color']) != {'light', 'dark'} or not tokens['contrastChecks']:
        errors.append('Both themes and declared contrast checks are required')
    for theme, colors in tokens['color'].items():
        for color in colors.values():
            luminance(color)
        for check in tokens['contrastChecks']:
            fg, bg = check['foreground'], check['background']
            ratio = contrast(colors[fg], colors[bg])
            pair_count += 1
            if ratio < check['minRatio']:
                errors.append(f'{theme} {fg}/{bg}: contrast {ratio:.2f} below {check["minRatio"]}')
    counts['token contrast pairs'] = pair_count

    for line in (root / '.env.example').read_text(encoding='utf-8').splitlines():
        if line and not line.startswith('#') and '=' in line:
            name, value = line.split('=', 1)
            if name != 'ARBIT_ENV' and value:
                errors.append(f'Environment example must not contain a real setting value: {name}')
    return errors, counts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    root = parser.parse_args().root.resolve()
    if sys.version_info < (3, 12):
        print('FAIL: Python 3.12 or later is required', file=sys.stderr)
        return 1
    try:
        errors, counts = validate(root)
    except (ValueError, KeyError, TypeError, OSError) as error:
        print(f'FAIL: malformed or missing foundation artifact ({type(error).__name__}): {error}', file=sys.stderr)
        return 1
    if errors:
        for error in errors:
            print(f'FAIL: {error}', file=sys.stderr)
        return 1
    print('PASS: foundation validation')
    for name, count in counts.items():
        print(f'  {count} {name}')
    print('  Owner brief checksum, local links, league configuration and contract example verified.')
    print('  Scope: planning artifacts only; no application/provider/model readiness claimed.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
