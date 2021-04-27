# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import json
import logging
import os
import socket
import threading
import time
from collections import namedtuple
from contextlib import contextmanager

status = dict()
logger = logging.getLogger(__name__)
address = 'trytond-stat.socket'

Process = namedtuple('Process', ['start_time', 'request'])

_PID = None
_PATH = None
_LOCK = threading.Lock()


@contextmanager
def processing(request):
    start(_PATH)  # check if running thread
    process = Process(time.perf_counter(), request)
    status[id(process)] = process
    try:
        yield
    finally:
        status.pop(id(process), None)


def log():
    from trytond.cache import Cache
    msg = []
    now = time.perf_counter()
    for process in sorted(status.copy().values(), key=lambda p: p.start_time):
        msg.append({
                'since': now - process.start_time,
                'request': str(process.request),
                })
    return {
        'id': os.getpid(),
        'status': msg,
        'caches': list(Cache.stats()),
        }


def dump(path):
    sock = socket.socket(socket.AF_UNIX)
    try:
        try:
            sock.connect(os.path.join(path, address))
        except socket.error:
            return False
        try:
            sock.sendall(json.dumps(log()).encode('utf-8'))
        except socket.error:
            pass
    finally:
        sock.close()
    return True


def dumper(path):
    while True:
        if dump(path):
            time.sleep(5)
        else:
            time.sleep(60)


def start(path):
    global _PID, _PATH
    if _PID != os.getpid() and path:  # Quick test without lock
        with _LOCK:
            if _PID != os.getpid():
                threading.Thread(
                    target=dumper, args=(path,), daemon=True).start()
                _PID = os.getpid()
                _PATH = path


def listen(path, callback=None):
    sock = socket.socket(socket.AF_UNIX)
    socket_file = os.path.join(path, address)
    try:
        sock.bind(socket_file)
        sock.listen(1)
        sock.settimeout(5)
        while True:
            try:
                connection, client_address = sock.accept()
            except socket.timeout:
                if callback:
                    callback()
                continue
            try:
                data = b''
                while True:
                    chunk = connection.recv(1024)
                    if not chunk:
                        break
                    else:
                        data += chunk
                try:
                    data = json.loads(data)
                except ValueError:
                    continue
                if callback:
                    callback(data)
            finally:
                connection.close()
    finally:
        sock.close()
        os.unlink(socket_file)
