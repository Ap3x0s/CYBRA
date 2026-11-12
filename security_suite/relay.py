"""Local authenticated relay: exact upstream URL, request budgets and response checks."""
import copy
import json
import secrets
import ssl
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from .common import append

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

class Relay:
    def __init__(self, config, model, out):
        self.config, self.model, self.out = config, model, Path(out)
        self.key = secrets.token_urlsafe(32)
        self.counts = {'target': 0, 'judge': 0}
        self.errors = []
        self.lock = threading.Lock()
        ctx = (
            ssl._create_unverified_context()
            if config.get("insecure_skip_tls_verify")
            else ssl.create_default_context(cafile=config.get("ca_file"))
        )
        self.opener = urllib.request.build_opener(NoRedirect(), urllib.request.HTTPSHandler(context=ctx))
        self.local_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect(), urllib.request.HTTPSHandler(context=ctx))
        relay = self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass
            def do_POST(self):
                route = self.path.strip('/').split('/')[0]
                if route not in ('target', 'judge') or self.path != f'/{route}/v1/chat/completions':
                    return self.respond(404, {'error': {'message': 'Unknown endpoint'}})
                if self.headers.get('Authorization') != 'Bearer ' + relay.key:
                    return self.respond(401, {'error': {'message': 'Unauthorized'}})
                try:
                    length = int(self.headers.get('Content-Length', '0'))
                    if not 0 < length <= 8 * 1024 * 1024:
                        raise ValueError('Request size limit')
                    payload = json.loads(self.rfile.read(length))
                    status, response = relay.forward(route, payload)
                except Exception as e:
                    status, response = 400, {'error': {'message': str(e)}}
                self.respond(status, response)
            def respond(self, status, obj):
                data = json.dumps(obj, ensure_ascii=False).encode()
                self.send_response(status)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(data)))
                self.end_headers()
                try:
                    self.wfile.write(data)
                except (BrokenPipeError, ConnectionResetError):
                    pass
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.server.daemon_threads = True
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
    def __enter__(self):
        self.thread.start()
        return self
    def __exit__(self, *args):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
    def base(self, route):
        return f'http://127.0.0.1:{self.server.server_port}/{route}/v1'
    def redact(self, value):
        s = str(value)
        for name in ('key', 'judge_key'):
            if self.config.get(name):
                s = s.replace(self.config[name], '[REDACTED]')
        return s
    def forward(self, route, payload):
        start = time.monotonic()
        with self.lock:
            budget = self.config['max_requests']
            if self.counts[route] >= budget:
                reason = route + ' request budget exhausted'
                if reason not in self.errors:
                    self.errors.append(reason)
                return 402, {'error': {'message': reason, 'type': 'budget_exhausted'}}
            self.counts[route] += 1
            request_id = f'{route}-{self.counts[route]}'
        payload = copy.deepcopy(payload)
        payload['model'] = self.model if route == 'target' else self.config['judge_model']
        payload['stream'] = False
        payload.pop('stream_options', None)
        payload.pop('max_tokens', None)
        payload.pop('max_completion_tokens', None)
        payload[self.config['token_parameter']] = self.config['max_tokens'] if route == 'target' else self.config['judge_max_tokens']
        if self.config['temperature'] is None:
            payload.pop('temperature', None)
        else:
            payload['temperature'] = self.config['temperature'] if route == 'target' else 0
        for field in self.config.get('drop_params', []):
            payload.pop(field, None)
        if self.config.get('developer_as_system'):
            for msg in payload.get('messages', []):
                if msg.get('role') == 'developer':
                    msg['role'] = 'system'
        payload.update(self.config.get('extra_body' if route == 'target' else 'judge_extra_body', {}))
        endpoint = self.config['endpoint' if route == 'target' else 'judge_endpoint']
        api_key = self.config['key' if route == 'target' else 'judge_key']
        # Тот же User-Agent, что и в пробе эндпоинта: без него Cloudflare
        # может отдать 403/1010 ещё до проверки ключа, и прогон упадёт на
        # каждом кейсе с виду необъяснимой ошибкой.
        headers = {
            'Content-Type': 'application/json',
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                '(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
            ),
        }
        if api_key:
            headers['Authorization'] = 'Bearer ' + api_key
        headers.update(self.config.get('headers', {}) if route == 'target' else self.config.get('judge_headers', {}))
        status, response, error = 200, None, None
        try:
            req = urllib.request.Request(endpoint, data=json.dumps(payload).encode(), headers=headers)
            opener = self.local_opener if urllib.parse.urlparse(endpoint).hostname in ('127.0.0.1', 'localhost', '::1') else self.opener
            with opener.open(req, timeout=self.config['timeout']) as r:
                response = json.load(r)
            choices = response.get('choices', [])
            if not choices:
                raise ValueError('EMPTY_CHOICES: response is not a chat completion')
            for choice in choices:
                reason = choice.get('finish_reason')
                if reason == 'length':
                    raise ValueError('TRUNCATED: finish_reason=length')
                msg = choice.get('message', {})
                content = msg.get('content')
                if not ((isinstance(content, str) and content.strip()) or msg.get('tool_calls') or msg.get('refusal')):
                    raise ValueError('EMPTY_OUTPUT: reasoning alone is not a final answer')
        except urllib.error.HTTPError as e:
            status, error = e.code, f'Upstream HTTP {e.code}: ' + e.read(2000).decode(errors='replace')
        except Exception as e:
            status, error = 502, f'{type(e).__name__}: {e}'
        event = {'request_id': request_id, 'route': route, 'request': payload, 'response': response,
                 'http_status': status, 'error': self.redact(error) if error else None,
                 'seconds': round(time.monotonic() - start, 3)}
        with self.lock:
            append(self.out / 'http.jsonl', event)
            if error:
                self.errors.append(event['error'])
        if error:
            return status, {'error': {'message': self.redact(error), 'type': 'suite_transport_error'}}
        return status, response
