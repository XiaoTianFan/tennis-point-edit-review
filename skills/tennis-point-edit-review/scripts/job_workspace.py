"""Create durable job workspaces and resolve explicitly relocated JSON references."""
import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import re
import stat
import subprocess

MARKER = 'job-workspace.json'
RELOCATION = 'relocation-map.json'


def safe_path(path, checked=None):
    """Reject reparse traversal before resolving an absolute filesystem path."""
    path = Path(os.path.abspath(path))
    checked = set() if checked is None else checked
    for parent in [*reversed(path.parents), path]:
        if parent in checked:
            continue
        try:
            info = parent.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
            raise ValueError('Workspace path crosses a link/reparse point: ' + str(parent))
        checked.add(parent)
    return path


def outputs_root(explicit=None, package=None):
    selected = explicit or os.environ.get('TENNIS_OUTPUTS_ROOT')
    if selected:
        if not Path(selected).is_absolute():
            raise ValueError('Outputs root must be absolute')
        return safe_path(selected)
    package = Path(package or Path(__file__).resolve().parents[1])
    try:
        result = subprocess.run(['git', '-C', str(package), 'rev-parse', '--path-format=absolute',
                                 '--git-common-dir'], capture_output=True, text=True, encoding='utf-8')
    except OSError:
        result = None
    if result is not None and result.returncode == 0:
        common = Path(result.stdout.strip())
        repo = common.parent
        # Linked worktrees point at the saved checkout's common .git directory.
        if common.name == '.git' and (repo / 'skills' / 'tennis-point-edit-review' / 'SKILL.md').is_file():
            return safe_path(repo / 'outputs')
    raise ValueError('Cannot locate the saved skill repository; set TENNIS_OUTPUTS_ROOT or --outputs-root. Do not default to cwd or an extracted skill directory.')


def create_workspace(source=None, work_dir=None, root=None, job_id=None, package=None):
    if work_dir is not None:
        directory = safe_path(work_dir)
        if directory.exists():
            raise ValueError('Workspace already exists; resume it in place')
    else:
        base = outputs_root(root, package)
        name = job_id or datetime.now().strftime('%Y%m%d-') + (Path(source).stem if source else 'match')
        if job_id and (job_id in ('.', '..') or not re.fullmatch(r'[\w-]{1,100}', job_id)):
            raise ValueError('job-id must be a single portable name (letters, digits, underscore, hyphen)')
        name = re.sub(r'[^\w-]', '-', name).strip('-')[:100] or 'match'
        if name.upper() in {'CON','PRN','AUX','NUL',*[f'COM{i}' for i in range(1,10)],*[f'LPT{i}' for i in range(1,10)]}:
            raise ValueError('Reserved job-id')
        directory = safe_path(base / name)
    directory.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation: never silently merge two jobs or reuse a completed job.
    if work_dir is None and job_id is None:
        original = directory
        for suffix in range(1, 10000):
            try:
                directory.mkdir()
                break
            except FileExistsError:
                directory = safe_path(original.with_name(original.name + '-' + str(suffix + 1)))
        else:
            raise ValueError('Too many workspace name collisions')
    else:
        directory.mkdir()
    paths = {name: str(directory / name) for name in
             ('media', 'analysis', 'statistics', 'evidence', 'cache', 'runtime', 'exports', 'audit', 'edit')}
    for name, path in paths.items():
        if name != 'edit':  # init requires a new project directory.
            Path(path).mkdir()
    record = dict(schema='tennis-job-workspace/v1', directory=str(directory), paths=paths,
                  source=str(Path(source).resolve()) if source else None,
                  createdAt=datetime.now().astimezone().isoformat())
    (directory / MARKER).write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return record


def relocation_map(location):
    location = Path(location).resolve()
    start = location if location.is_dir() else location.parent
    for parent in (start, *start.parents):
        path = parent / RELOCATION
        if path.is_file():
            safe_path(path)
            value = json.loads(path.read_text(encoding='utf-8-sig'))
            if value.get('schema') != 'tennis-job-relocation/v1' or not isinstance(value.get('mappings'), list):
                raise ValueError('Unsupported relocation map: ' + str(path))
            seen = set()
            for entry in value['mappings']:
                old, new = entry['old'], entry['new']
                if not Path(old).is_absolute() or not Path(new).is_absolute():
                    raise ValueError('Relocation roots must be absolute')
                key = os.path.normcase(os.path.normpath(old))
                if key in seen:
                    raise ValueError('Duplicate relocation root')
                seen.add(key)
                if not safe_path(new).is_relative_to(parent):
                    raise ValueError('Relocation destination must stay inside this job')
            return value['mappings']
    return []


def resolve_reference(value, mappings, checked=None):
    if not isinstance(value, str) or not Path(value).is_absolute():
        return value
    normalized = os.path.normcase(os.path.normpath(value))
    for entry in sorted(mappings, key=lambda e: len(e['old']), reverse=True):
        old = os.path.normcase(os.path.normpath(entry['old']))
        if normalized == old or normalized.startswith(old + os.sep):
            suffix = os.path.relpath(os.path.normpath(value), os.path.normpath(entry['old']))
            target = safe_path(Path(entry['new']) / suffix, checked)
            if not target.is_relative_to(safe_path(entry['new'], checked)):
                raise ValueError('Relocated reference escapes its destination')
            return str(target)
    return value


def resolve_document(value, mappings, cache=None, checked=None):
    cache = {} if cache is None else cache
    checked = set() if checked is None else checked
    if isinstance(value, dict):
        return {key: resolve_document(item, mappings, cache, checked) for key, item in value.items()}
    if isinstance(value, list):
        return [resolve_document(item, mappings, cache, checked) for item in value]
    if isinstance(value, str):
        if value not in cache:
            cache[value] = resolve_reference(value, mappings, checked)
        return cache[value]
    return value


def read_document(path, workspace=None):
    mappings = relocation_map(workspace or path)
    path = resolve_reference(str(path), mappings)
    value = json.loads(Path(path).read_text(encoding='utf-8-sig'))
    return resolve_document(value, mappings) if mappings else value


def add_create_arguments(parser):
    parser.add_argument('--source')
    parser.add_argument('--work-dir', help='Exact user-selected new working directory')
    parser.add_argument('--outputs-root', help='Absolute root; defaults to the saved skill checkout outputs')
    parser.add_argument('--job-id', help='Unique portable job folder name')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    add_create_arguments(commands.add_parser('create'))
    for command in ('resolve', 'read'):
        sub = commands.add_parser(command)
        sub.add_argument('path'); sub.add_argument('--workspace', required=True)
    args = parser.parse_args()
    if args.command == 'create':
        result = create_workspace(args.source, args.work_dir, args.outputs_root, args.job_id)
    elif args.command == 'resolve':
        result = resolve_reference(args.path, relocation_map(args.workspace))
    else:
        result = read_document(args.path, args.workspace)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
