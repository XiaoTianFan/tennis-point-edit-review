"""Local-only tennis timeline: init, serve, context, update and render commands."""
import argparse
import copy
import json
import mimetypes
import hashlib
import shutil
import subprocess
import secrets
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse
from local_model import SCHEMA, Store, Conflict, context, read, write, validate
from local_media import prepare_media, frame_image, render_graphics, export_video, probe

WEB = Path(__file__).resolve().parent / 'local_web'

def initialize(plan, directory, base=None):
    directory = Path(directory).resolve()
    if directory.exists():
        raise ValueError('Create a new project directory')
    p = copy.deepcopy(plan)
    p.update(schema=SCHEMA, projectId=secrets.token_hex(12), revision=0, answers={}, needsRebuild=[], undo=[], redo=[], events=[])
    p.setdefault('overlays', [])
    base = Path(base or Path.cwd())
    for asset in p['assets']:
        if 'metadata' in asset:
            asset.update(read(base / asset.pop('metadata')))
        asset['path'] = str((base / asset['path']).resolve())
        info = probe(asset['path'])
        video = next(s for s in info['streams'] if s['codec_type'] == 'video')
        if asset.get('timing') != 'cfr-proxy' or video['r_frame_rate'] != video['avg_frame_rate']:
            raise ValueError('Prepare a CFR asset with the media command first')
        from fractions import Fraction
        if Fraction(video['avg_frame_rate']) != Fraction(str(p['fps'])):
            raise ValueError('Asset fps must match timeline fps')
        asset['frames'] = int(video['nb_frames'])
        asset['hasAudio'] = any(s['codec_type'] == 'audio' for s in info['streams'])
    validate(p, check_files=True)
    directory.mkdir(parents=True)
    render_graphics(p, directory)
    write(directory / 'project.json', p)
    return p

def make_server(directory, port=0):
    store = Store(directory)
    store.get()
    token = secrets.token_urlsafe(32)
    job = {'state': 'idle'}
    job_lock = threading.Lock()
    frame_lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def reply(self, value, code=200):
            body = json.dumps(value, ensure_ascii=False).encode('utf-8')
            self.send_response(code)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.end_headers()
            self.wfile.write(body)

        def authorized(self):
            expected = f'127.0.0.1:{self.server.server_port}'
            if self.headers.get('Host') != expected:
                return False
            origin = self.headers.get('Origin')
            if origin and origin != 'http://' + expected:
                return False
            supplied = self.headers.get('X-Session-Token') or parse_qs(urlparse(self.path).query).get('token', [''])[0]
            return secrets.compare_digest(supplied, token)

        def send_file(self, path, mime=None, ranges=False):
            path = Path(path)
            size = path.stat().st_size
            start, end, status = 0, size-1, 200
            if ranges and self.headers.get('Range'):
                import re
                match = re.fullmatch(r'bytes=(\d*)-(\d*)', self.headers['Range'])
                if not match or not any(match.groups()):
                    self.reply({'error': 'Unsupported range'}, 416)
                    return
                if match[1]:
                    start, end = int(match[1]), min(size-1, int(match[2]) if match[2] else size-1)
                else:
                    start = max(0, size-int(match[2]))
                if start > end or start >= size:
                    self.send_response(416)
                    self.send_header('Content-Range', f'bytes */{size}')
                    self.end_headers()
                    return
                status = 206
            self.send_response(status)
            self.send_header('Content-Type', mime or mimetypes.guess_type(path)[0] or 'application/octet-stream')
            self.send_header('Content-Length', str(end-start+1))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' blob:; media-src 'self' blob:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
            if ranges:
                self.send_header('Accept-Ranges', 'bytes')
            if status == 206:
                self.send_header('Content-Range', f'bytes {start}-{end}/{size}')
            self.end_headers()
            if self.command != 'HEAD':
                with path.open('rb') as f:
                    f.seek(start)
                    remaining = end-start+1
                    while remaining:
                        chunk = f.read(min(65536, remaining))
                        if not chunk:
                            break
                        self.wfile.write(chunk)
                        remaining -= len(chunk)

        def do_HEAD(self):
            self.do_GET()

        def do_GET(self):
            try:
                route = unquote(urlparse(self.path).path)
                public = {'/': 'index.html', '/app.js': 'app.js', '/model.js': 'model.js', '/review.js': 'review.js', '/timeline.js': 'timeline.js', '/player.js': 'player.js', '/style.css': 'style.css'}
                if route in public:
                    if self.headers.get('Host') != f'127.0.0.1:{self.server.server_port}':
                        self.reply({'error': 'Invalid host'}, 403)
                        return
                    self.send_file(WEB / public[route], 'text/javascript; charset=utf-8' if route.endswith('.js') else None)
                    return
                if not self.authorized():
                    self.reply({'error': 'Open the launch URL containing this session token'}, 403)
                    return
                p = store.get()
                if route == '/api/project':
                    self.reply(p)
                elif route == '/api/context':
                    self.reply({**context(p), 'projectPath': str(store.path)})
                elif route == '/api/job':
                    self.reply(job.copy())
                elif route == '/api/export':
                    if job.get('state') != 'complete':
                        raise ValueError('No completed export')
                    self.send_file(job['path'], 'video/mp4', True)
                elif route == '/api/frame':
                    query = parse_qs(urlparse(self.path).query)
                    asset = next(a for a in p['assets'] if a['id'] == query['asset'][0])
                    frame = int(query['frame'][0])
                    stamp = str(Path(asset['path']).stat().st_mtime_ns)
                    cache = hashlib.sha256((asset['path'] + stamp + str(p['fps'])).encode()).hexdigest()[:16]
                    with frame_lock:
                        path = frame_image(asset, frame, p['fps'], store.directory / 'frames' / f'{asset["id"]}-{cache}-{frame}.jpg')
                    self.send_file(path, 'image/jpeg')
                elif route.startswith('/media/'):
                    asset = next(a for a in p['assets'] if a['id'] == route[7:])
                    self.send_file(asset['path'], 'video/mp4', True)
                elif route.startswith('/graphics/'):
                    overlay = next(o for o in p['overlays'] if o['id'] == route[10:])
                    self.send_file(overlay['image'], 'image/png')
                else:
                    self.reply({'error': 'Not found'}, 404)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass
            except (ValueError, KeyError, StopIteration, OSError) as e:
                self.reply({'error': str(e) or 'Missing project resource'}, 400)

        def do_POST(self):
            try:
                if not self.authorized():
                    self.reply({'error': 'Invalid session or origin'}, 403)
                    return
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= 2_000_000:
                    raise ValueError('Invalid request size')
                data = json.loads(self.rfile.read(size))
                route = urlparse(self.path).path
                if route == '/api/operation':
                    self.reply(store.apply(data['revision'], data['operation']))
                elif route == '/api/handoff':
                    with store.locked():
                        p = store.get()
                        if data['revision'] != p['revision']:
                            raise Conflict('Reload before exporting review')
                        value = {**context(p), 'projectPath': str(store.path)}
                        write(store.directory / 'agent-context.json', value)
                        write(store.directory / 'review.json', value['review'])
                    self.reply(value)
                elif route == '/api/render':
                    p = store.get()
                    if data['revision'] != p['revision']:
                        raise Conflict('Reload before exporting video')
                    if p.get('needsRebuild'):
                        raise ValueError('Send the changes to your agent to refresh graphics before exporting')
                    with job_lock:
                        if job.get('state') == 'running':
                            raise Conflict('Export already running')
                        job.clear()
                        job.update(state='running', revision=p['revision'], completedClips=0, totalClips=len(p['clips']))
                    def export():
                        try:
                            export_video(p, store.directory / 'exports' / f'r{p["revision"]}-{time.time_ns()}', lambda v: job.update(v))
                        except Exception as e:
                            job.update(state='failed', error=str(e))
                    threading.Thread(target=export, daemon=True).start()
                    self.reply(job.copy(), 202)
                else:
                    self.reply({'error': 'Not found'}, 404)
            except Conflict as e:
                self.reply({'error': str(e)}, 409)
            except (ValueError, KeyError, TypeError, StopIteration, OSError) as e:
                self.reply({'error': str(e) or 'Invalid operation'}, 400)

    server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    server.daemon_threads = True
    server.launch_url = f'http://127.0.0.1:{server.server_port}/#token={token}'
    return server

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('doctor', help='Check terminal dependencies without starting a browser')
    media = sub.add_parser('media', help='Create a browser-compatible CFR source proxy')
    media.add_argument('source'); media.add_argument('output'); media.add_argument('--fps', default='30')
    media.add_argument('--width', type=int, default=1280); media.add_argument('--start', type=float, default=0)
    media.add_argument('--duration', type=float)
    init = sub.add_parser('init'); init.add_argument('plan'); init.add_argument('directory')
    serve = sub.add_parser('serve'); serve.add_argument('directory'); serve.add_argument('--port', type=int, default=0); serve.add_argument('--open', action='store_true')
    inspect = sub.add_parser('context'); inspect.add_argument('directory'); inspect.add_argument('--output')
    update = sub.add_parser('update'); update.add_argument('directory'); update.add_argument('plan'); update.add_argument('--expected-revision', type=int, required=True)
    render = sub.add_parser('render'); render.add_argument('directory'); render.add_argument('output')
    args = parser.parse_args()
    if args.command == 'doctor':
        result = {'python': __import__('sys').version.split()[0],
                  'executables': {name: shutil.which(name) for name in ('ffmpeg', 'ffprobe', 'node')}}
        if result['executables']['node']:
            check = subprocess.run(['node', '-e', "for(const m of ['react','react-dom','esbuild','playwright']) console.log(m+': '+require.resolve(m))"],
                                   cwd=WEB.parent, capture_output=True, text=True, encoding='utf-8')
            result['graphicsDependencies'] = {'ready': check.returncode == 0, 'details': check.stdout or check.stderr}
        result['ready'] = all(result['executables'].values()) and result.get('graphicsDependencies', {}).get('ready', False)
        result['browser'] = 'Render a small project to verify Chromium or the selected installed browser channel'
    elif args.command == 'media':
        result = prepare_media(args.source, args.output, args.fps, args.width, args.start, args.duration)
    elif args.command == 'init':
        p = initialize(read(args.plan), args.directory, Path(args.plan).resolve().parent)
        result = {'project': str(Path(args.directory).resolve() / 'project.json'), 'revision': p['revision']}
    elif args.command == 'serve':
        server = make_server(args.directory, args.port)
        write(Path(args.directory) / 'session.json', {'url': server.launch_url})
        print(server.launch_url, flush=True)
        if args.open:
            webbrowser.open(server.launch_url)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()
        return
    elif args.command == 'context':
        result = {**context(Store(args.directory).get()), 'projectPath': str(Store(args.directory).path)}
        if args.output:
            write(args.output, result)
    elif args.command == 'update':
        store = Store(args.directory)
        old, updated = store.get(), read(args.plan)
        if old['revision'] != args.expected_revision:
            raise Conflict('Stale revision; read current context before updating')
        if updated['review']['source'] != old['review']['source'] or updated['review']['ledgerRevision'] != old['review']['ledgerRevision'] or [(r['reviewId'], r['pointId']) for r in updated['review']['rows']] != [(r['reviewId'], r['pointId']) for r in old['review']['rows']]:
            raise ValueError('Preserve the current review source, revision and point mapping')
        updated.update(projectId=old.get('projectId'), answers=old.get('answers', {}), needsRebuild=[], undo=[], redo=[])
        validate(updated, check_files=True)
        render_graphics(updated, store.directory)
        result = store.commit(updated, args.expected_revision, {'type': 'agent-reconciliation'})
    else:
        result = export_video(Store(args.directory).get(), args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
