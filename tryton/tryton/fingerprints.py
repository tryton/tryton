# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import os
from threading import Lock

from tryton.config import get_config_dir

KNOWN_HOSTS_PATH = os.path.join(get_config_dir(), 'known_hosts')

_lock = Lock()


def _load():
    if not os.path.isfile(KNOWN_HOSTS_PATH):
        return {}
    fingerprints = {}
    with open(KNOWN_HOSTS_PATH) as known_hosts:
        for line in known_hosts:
            line = line.strip()
            try:
                host, sha1 = line.split(' ')
            except ValueError:
                host, sha1 = line, ''
            fingerprints[host] = sha1
    return fingerprints


def exists(host):
    return host in _load()


def get(host):
    return _load().get(host)


def set(host, fingerprint):
    fingerprints = _load()
    assert isinstance(host, str)
    if fingerprint:
        assert len(fingerprint) == 59  # len of formated sha1
    else:
        fingerprint = ''
    changed = fingerprint != fingerprints.get(host)
    fingerprints[host] = fingerprint
    if changed:
        _save(fingerprints)


def _save(fingerprints):
    with _lock:
        with open(KNOWN_HOSTS_PATH, 'w') as known_hosts:
            known_hosts.writelines(
                '%s %s' % (host, sha1) + os.linesep
                for host, sha1 in fingerprints.items())
