import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from dashboard.server import App
from dashboard.tools import command


class AgentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.app = App(self.temp.name)
        self.e = self.app.save_engagement(dict(name='Analysis fixture', scope='example.test', authorized=True))
        self.other = self.app.save_engagement(dict(name='Other fixture', scope='other.test', authorized=True))
        self.binary = Path(self.temp.name) / 'provider'
        self.binary.write_text('''#!/usr/bin/env python3
import json,sys,time
from pathlib import Path
prompt=sys.stdin.read()
assert 'UNTRUSTED SNAPSHOT JSON:' in prompt
assert 'Do not execute tools' in prompt
if 'sleep-fixture' in prompt: time.sleep(30)
if 'large-fixture' in prompt: print('x'*30000); sys.exit(0)
if 'fail-fixture' in prompt: print('Provider authentication failed'); sys.exit(2)
text='Analysis cites asset-fixture. No vulnerability demonstrated.'
if 'redact-fixture' in prompt: text += ' fixture-session-secret'
if '-o' in sys.argv: Path(sys.argv[sys.argv.index('-o')+1]).write_text(text)
else: print(text)
''')
        self.binary.chmod(0o700)
        self.mock = patch.object(self.app, 'tools', return_value=[dict(name=n, path=str(self.binary)) for n in ('claude', 'codex')])
        self.mock.start()

    def tearDown(self):
        self.app.shutdown()
        self.app.db.close()
        self.mock.stop()
        self.temp.cleanup()

    def asset(self, value='https://example.test/path?token=secret#fragment', engagement=None):
        e = engagement or self.e
        self.app.put('asset', dict(id='asset-fixture' if e == self.e else 'other-asset', engagement_id=e['id'], value=value, tool='httpx', job_ids=['job-fixture'], detail={'status_code': 301, 'title': 'Example', 'header': {'set_cookie': 'never-export'}, 'request': 'never-export'}))

    def start(self, provider='claude'):
        context = self.app.agents.prepare(self.e['id'])
        return self.app.agents.start(dict(engagement_id=self.e['id'], provider=provider, digest=context['digest']))

    def done(self, record):
        deadline = time.monotonic() + 7
        while time.monotonic() < deadline:
            result = self.app.get('analysis', record['id'])
            if result['status'] not in ('queued', 'running', 'cancelling'):
                return result
            time.sleep(.02)
        self.fail('Analysis did not terminate')

    def test_snapshot_is_engagement_specific_redacted_and_deterministic(self):
        self.asset()
        self.asset('https://other.test/private', self.other)
        secret = self.app.data / 'secrets/session.json'
        secret.parent.mkdir(exist_ok=True)
        secret.write_text(json.dumps({'Cookie': 'sid=private-cookie', 'Authorization': 'Bearer private-token'}))
        self.app.put('auth', dict(id='session', engagement_id=self.e['id']))
        self.app.put('job', dict(id='job-fixture', engagement_id=self.e['id'], tool='httpx', status='failed', error='private-cookie private-token', target='https://example.test/?secret=x', returncode=1))
        a = self.app.agents.prepare(self.e['id'])
        b = self.app.agents.prepare(self.e['id'])
        self.assertEqual(a, b)
        for value in ('private-cookie', 'private-token', 'never-export', '?token=', '#fragment', 'other.test', '?secret='):
            self.assertNotIn(value, a['text'])
        data = json.loads(a['text'])
        self.assertEqual(data['assets'][0]['observations']['status_code'], '301')
        self.assertEqual(data['totals']['job'], 1)
        self.assertIn('[REDACTED]', a['text'])
        path = self.app.workspace(self.e) / 'gathered-data.json'
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_changed_snapshot_and_invalid_provider_are_rejected(self):
        context = self.app.agents.prepare(self.e['id'])
        self.asset()
        with self.assertRaisesRegex(ValueError, 'changed'):
            self.app.agents.start(dict(engagement_id=self.e['id'], provider='claude', digest=context['digest']))
        with self.assertRaises(ValueError):
            self.start('anything; touch /tmp/no')
        self.assertEqual(self.app.all('analysis'), [])

    def test_both_cli_adapters_return_results_without_launching_jobs(self):
        self.asset()
        for provider in ('claude', 'codex'):
            result = self.done(self.start(provider))
            self.app.agents.thread.join(2)
            self.assertEqual(result['status'], 'completed', result)
            self.assertIn('asset-fixture', result['output'])
            self.assertEqual(self.app.all('job'), [])
            self.assertFalse((self.app.data / 'analyses' / result['id'] / 'answer.md').exists())

    def test_duplicate_cancellation_timeout_and_failure_are_visible(self):
        self.asset('sleep-fixture')
        record = self.start()
        with self.assertRaisesRegex(ValueError, 'already running'):
            self.start()
        self.app.agents.cancel(record['id'])
        self.assertEqual(self.done(record)['status'], 'cancelled')
        self.app.agents.thread.join(2)
        self.app.agents.timeout = .1
        record = self.start()
        self.assertEqual(self.done(record)['status'], 'timed_out')
        self.app.agents.thread.join(2)
        self.asset('fail-fixture')
        result = self.done(self.start())
        self.assertEqual(result['status'], 'failed')
        self.assertIn('authentication failed', result['output'])

    def test_output_is_bounded(self):
        self.asset('large-fixture')
        self.app.agents.output_limit = 8192
        result = self.done(self.start())
        self.assertEqual(result['status'], 'output_limit')
        self.assertLessEqual(len(result['output']), 8192 + 4096)

    def test_cli_security_options_and_claude_provider_environment(self):
        home = Path(self.temp.name) / 'home'
        (home / '.claude').mkdir(parents=True)
        (home / '.claude/settings.json').write_text(json.dumps(dict(env={'ANTHROPIC_BASE_URL': 'https://fixture.invalid', 'ANTHROPIC_AUTH_TOKEN': 'fake-provider-token', 'UNSAFE': 'ignored'}, hooks={'SessionStart': 'never-run'})))
        with patch('dashboard.agents.Path.home', return_value=home), patch.dict(os.environ, {}, clear=True):
            args, env = self.app.agents.cli('claude', home)
        self.assertEqual(env['ANTHROPIC_AUTH_TOKEN'], 'fake-provider-token')
        self.assertNotIn('UNSAFE', env)
        self.assertNotIn('fake-provider-token', args)
        self.assertIn('--bare', args)
        self.assertEqual(args[args.index('--tools')+1], '')
        args, _ = self.app.agents.cli('codex', home)
        self.assertIn('--ignore-user-config', args)
        self.assertIn('features.shell_tool=false', args)
        self.assertIn('read-only', args)

    def test_saved_session_secret_is_redacted_from_completed_answer(self):
        secret = self.app.data / 'secrets/session.json'
        secret.parent.mkdir(exist_ok=True)
        secret.write_text(json.dumps({'Cookie': 'sid=fixture-session-secret'}))
        self.app.put('auth', dict(id='session', engagement_id=self.e['id']))
        self.asset('redact-fixture')
        result = self.done(self.start())
        self.assertEqual(result['status'], 'completed')
        self.assertNotIn('fixture-session-secret', result['output'])
        self.assertIn('[REDACTED]', result['output'])

    def test_snapshot_caps_observations_and_reports_omissions(self):
        with self.app.lock:
            for i in range(503):
                self.app.put('asset', dict(id=str(i), engagement_id=self.e['id'], value='https://example.test/' + str(i), detail={'title':'x'*5000}, tool='httpx'))
        context = self.app.agents.prepare(self.e['id'])
        data = json.loads(context['text'])
        self.assertEqual(data['totals']['asset'], 503)
        self.assertLessEqual(data['included']['asset'], 500)
        self.assertEqual(data['included']['asset'], len(data['assets']))
        self.assertLessEqual(len(context['text']), 180000)

    def test_quoted_and_numeric_secrets_do_not_break_json(self):
        secret = self.app.data / 'secrets/session.json'
        secret.parent.mkdir(exist_ok=True)
        secret.write_text(json.dumps({'Cookie': 'sid=1', 'X-Token': 'quoted"token'}))
        self.app.put('auth', dict(id='session', engagement_id=self.e['id']))
        self.asset()
        data = json.loads(self.app.agents.prepare(self.e['id'])['text'])
        self.assertEqual(data['version'], 1)
        self.assertEqual(data['totals']['asset'], 1)
        self.assertNotIn('quoted"token', json.dumps(data))

    def test_tlsx_inventory_uses_compatible_probe_flags(self):
        args = command(self.e, dict(tool='tlsx', target='example.test'), [dict(name='tlsx', adapter=True, installed=True, path='/fixture/tlsx')])
        self.assertIn('-tv', args)
        self.assertIn('-j', args)
        self.assertNotIn('-san', args)
        self.assertNotIn('-cn', args)


if __name__ == '__main__':
    unittest.main()
