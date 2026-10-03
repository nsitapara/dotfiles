import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import wm_client as wm


class ClientTests(unittest.TestCase):
    def test_cli_fallback_preserves_timeout(self):
        import subprocess
        with patch.object(wm, 'yabai_message', return_value=None), \
                patch.object(wm.subprocess, 'run', side_effect=subprocess.TimeoutExpired('yabai', 2)) as cli:
            with self.assertRaisesRegex(RuntimeError, 'timed out'):
                wm.run('yabai', '-m', 'query', '--windows', timeout=2)
        self.assertEqual(cli.call_args.kwargs['timeout'], 2)

    def test_partial_send_is_not_replayed(self):
        from unittest.mock import MagicMock
        connection = MagicMock()
        connection.__enter__.return_value = connection
        connection.sendall.side_effect = BrokenPipeError('partial write')
        with patch.object(wm.socket, 'socket', return_value=connection), \
                patch.object(wm.subprocess, 'run') as cli:
            with self.assertRaisesRegex(RuntimeError, 'interrupted'):
                wm.run('yabai', '-m', 'window', 1, '--swap', 2)
        cli.assert_not_called()

    def test_socket_protocol_and_native_errors(self):
        import struct
        from unittest.mock import MagicMock
        for reply,code in [(b'{"ok":true}',0),(b'\x07invalid window\n',1)]:
            connection=MagicMock()
            connection.recv.side_effect=[reply[:3],reply[3:],b'']
            connection.__enter__.return_value=connection
            with patch.object(wm.socket,'socket',return_value=connection),patch.object(wm.subprocess,'run') as cli:
                result=wm.run('yabai','-m','query','--windows',check=False)
            self.assertEqual(result.returncode,code)
            payload=b'query\0--windows\0\0'
            connection.sendall.assert_called_once_with(struct.pack('=i',len(payload))+payload)
            cli.assert_not_called()
            if code:self.assertEqual(result.stderr,'invalid window\n')


    def test_socket_does_not_replay_a_move_after_connection_breaks(self):
        from unittest.mock import MagicMock
        connection=MagicMock();connection.__enter__.return_value=connection
        connection.recv.side_effect=TimeoutError('timeout')
        with patch.object(wm.socket,'socket',return_value=connection),patch.object(wm.subprocess,'run') as cli:
            with self.assertRaisesRegex(RuntimeError,'interrupted'):
                wm.run('yabai','-m','window',1,'--swap',2)
        cli.assert_not_called()


    def test_socket_connection_failure_falls_back_before_sending(self):
        from unittest.mock import MagicMock
        connection=MagicMock();connection.__enter__.return_value=connection
        connection.connect.side_effect=FileNotFoundError('socket missing')
        response=SimpleNamespace(returncode=0,stdout='[]',stderr='')
        with patch.object(wm.socket,'socket',return_value=connection),patch.object(wm.subprocess,'run',return_value=response) as cli:
            self.assertEqual(json.loads(wm.run('yabai','-m','query','--windows').stdout),[])
        connection.sendall.assert_not_called()
        cli.assert_called_once_with(['yabai','-m','query','--windows'],capture_output=True,text=True,timeout=None)
