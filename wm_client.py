"""Shared command transport for window-manager scripts.

Yabai uses its local socket. Other commands, or an unavailable socket before
sending, use the CLI. An interrupted request is never replayed.
"""
import os
import socket
import struct
import subprocess


def run(*args, check=True, timeout=None):
    args = [str(a) for a in args]
    result = yabai_message(args[2:]) if args[:2] == ['yabai', '-m'] else None
    if result is None:
        try:
            result = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired as error:
            raise RuntimeError('Command timed out: ' + ' '.join(args)) from error
    if check and result.returncode:
        raise RuntimeError(result.stderr.strip() or 'Command failed: ' + ' '.join(map(str, args)))
    return result


def yabai_message(args):
    # Same local protocol as yabai 7's CLI, without launching a process for
    # every query/change. See upstream src/yabai.c:client_send_message.
    payload = b'\0'.join(arg.encode() for arg in args) + b'\0\0'
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        connection.settimeout(2)
        try:
            connection.connect('/tmp/yabai_' + os.environ.get('USER', '') + '.socket')
        except OSError:
            return None  # CLI fallback is safe only before a request is sent.
        try:
            connection.sendall(struct.pack('=i', len(payload)) + payload)
            connection.shutdown(socket.SHUT_WR)
            chunks = []
            while True:
                chunk = connection.recv(65536)
                if not chunk:
                    break
                chunks.append(chunk)
        except OSError as error:
            # Never replay a possibly executed move through the CLI.
            raise RuntimeError('yabai connection interrupted: ' + str(error)) from error
    response = b''.join(chunks).decode()
    failed = response.startswith('\x07')
    return subprocess.CompletedProcess(args, int(failed), '' if failed else response,
                                       response[1:] if failed else '')

