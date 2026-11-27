"""Isolated invariants: import safety and the gate before starting downloads."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import media_backend as m


class FakeQB:
    def json(self, path):
        if path == 'app/preferences':
            return {'current_network_interface': 'tun0'}
        if path.startswith('torrents/info'):
            return [{'amount_left': 0, 'progress': 1, 'state': 'stoppedUP', 'save_path': '/downloads/complete'}]
        if path.startswith('torrents/files'):
            return [{'index': 0, 'progress': 1, 'name': 'example.mkv', 'size': 5}]
        raise AssertionError(path)


class MediaTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.downloads = self.root / 'downloads'
        self.video = self.root / 'VIDEO'
        (self.downloads / 'complete').mkdir(parents=True)
        (self.video / 'Movies').mkdir(parents=True)
        self.source = self.downloads / 'complete/example.mkv'
        self.source.write_bytes(b'media')
        self.a = {'hash': 'a' * 40, 'file_index': 0, 'section': 1, 'destination': 'Example (2026)/Example (2026).mkv'}
        self.stack = [
            {'Name': '/agent-gluetun', 'Id': 'vpn-id', 'Image': 'vpn-image', 'State': {'Health': {'Status': 'healthy'}}},
            {'Name': '/agent-qbittorrent', 'Image': 'qb-image', 'State': {'Running': True}, 'HostConfig': {'NetworkMode': 'container:vpn-id'}}]
        for name, value in [('ROOT', self.root), ('DOWNLOADS', self.downloads), ('VIDEO', self.video)]:
            p = patch.object(m, name, value); p.start(); self.addCleanup(p.stop)
        p = patch.object(m, 'section', return_value={'id': 1, 'paths': ['/data/VIDEO/Movies']})
        p.start(); self.addCleanup(p.stop)
        (self.root / 'compose.yml').write_text('fixture')

    def test_hardlink_idempotent_and_never_overwrites(self):
        out = m.import_file(FakeQB(), self.a)
        dest = Path(out['imported'])
        self.assertEqual(dest.stat().st_ino, self.source.stat().st_ino)
        self.assertIn('already_imported', m.import_file(FakeQB(), self.a))
        dest.unlink(); dest.write_text('existing')
        with self.assertRaises(ValueError): m.import_file(FakeQB(), self.a)
        self.assertEqual(dest.read_text(), 'existing')

    def test_rejects_traversal_symlink_nonmedia_and_incomplete(self):
        for value in ('../../escape.mkv', '/tmp/escape.mkv', 'X/../../escape.mkv'):
            with self.assertRaises(ValueError): m.import_file(FakeQB(), {**self.a, 'destination': value})
        (self.video / 'Movies/link').symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(ValueError): m.import_file(FakeQB(), {**self.a, 'destination': 'link/x.mkv'})
        self.source.write_text('shorter or longer')
        with self.assertRaises(ValueError): m.import_file(FakeQB(), self.a)
        self.source.write_bytes(b'media')
        with self.assertRaises(ValueError): m.import_file(FakeQB(), {**self.a, 'destination': 'x.exe'})
        q = FakeQB()
        original = q.json
        q.json = lambda p: [{**original(p)[0], 'progress': 0.5}] if p.startswith('torrents/info') else original(p)
        with self.assertRaises(ValueError): m.import_file(q, self.a)

    def test_existing_library_root_and_unsupported_operation(self):
        with patch.object(m, 'section', return_value={'id': 1, 'paths': ['/data/VIDEO/missing', '/data/VIDEO/Movies']}):
            result = m.import_file(FakeQB(), self.a)
            self.assertTrue(Path(result['imported']).is_relative_to(self.video / 'Movies'))
            self.assertFalse((self.video / 'missing').exists())
        with self.assertRaises(ValueError): m.main({'action': 'shell'})

    def test_gate_rejects_missing_acceptance_bad_namespace_or_interface(self):
        with patch.object(m, 'containers', return_value=self.stack):
            with self.assertRaises(RuntimeError): m.guard(FakeQB())
            (self.root / 'vpn-accepted.json').write_text(json.dumps({'fingerprint': m.fingerprint(self.stack)}))
            m.guard(FakeQB())
            self.stack[1]['HostConfig']['NetworkMode'] = 'host'
            with self.assertRaises(RuntimeError): m.guard(FakeQB())
            self.stack[1]['HostConfig']['NetworkMode'] = 'container:vpn-id'
            q = FakeQB(); q.json = lambda p: {'current_network_interface': ''}
            with self.assertRaises(RuntimeError): m.guard(q)
            self.stack[0]['State']['Health']['Status'] = 'unhealthy'
            with self.assertRaises(RuntimeError): m.guard(FakeQB())


if __name__ == '__main__':
    unittest.main()
