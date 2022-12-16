# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
"""
Inter-Process Communication
"""
import tempfile
import os
import threading
import select
import time
from tryton.config import get_config_dir

__all__ = ['Server', 'Client']


class IPCServer(object):

    thread = None
    running = None
    instance = None

    def __init__(self, hostname, port, database):
        from tryton.common import slugify
        if Server.instance:
            Server.instance.stop()
        self.hostname = slugify(hostname).lower()
        self.port = port
        self.database = slugify(database)
        self.config = os.path.join(get_config_dir(), '%s@%s@%s' %
                (self.hostname, self.port, self.database))
        self.tmpdir = tempfile.mkdtemp(prefix='.tryton')
        Server.instance = self

    def setup(self):
        raise NotImplemented

    def run(self):
        self.setup()
        self.running = True
        self.thread = threading.Thread(target=self._read)
        self.thread.start()

    def clean(self):
        raise NotImplemented

    def stop(self):
        self.running = False
        self.thread.join()
        self.thread = None
        self.clean()
        Server.instance = None

    def _read(self):
        raise NotImplemented


class FileServer(IPCServer):

    def setup(self):
        config = open(self.config, 'w')
        print >> config, self.tmpdir

    def clean(self):
        try:
            os.remove(self.config)
            os.rmdir(self.tmpdir)
        except OSError:
            pass

    def _read(self):
        to_remove = set()
        while self.running:
            for filename in os.listdir(self.tmpdir):
                path = os.path.join(self.tmpdir, filename)
                if not os.path.isfile(path):
                    continue
                if path in to_remove:
                    continue
                try:
                    data = open(path, 'r').readline()
                except IOError:
                    pass
                if data and data[-1] != '\n':
                    continue
                to_remove.add(path)
                if data:
                    from tryton.gui.main import Main
                    Main.get_main().open_url(data[:-1])
            if not os.path.exists(self.config):
                self.setup()
            for path in to_remove.copy():
                try:
                    os.remove(path)
                except OSError:
                    continue
                to_remove.remove(path)
            time.sleep(1)


class FIFOServer(IPCServer):

    def setup(self):
        self.filename = os.path.join(self.tmpdir, 'Socket')
        os.mkfifo(self.filename, 0600)
        if os.path.lexists(self.config):
            os.remove(self.config)
        os.symlink(self.filename, self.config)

    def clean(self):
        try:
            os.remove(self.config)
            os.rmdir(self.tmpdir)
        except OSError:
            pass

    def _read(self):
        fifo = os.fdopen(os.open(self.filename, os.O_RDONLY | os.O_NONBLOCK))
        data = ''
        while self.running:
            try:
                rlist, _, _ = select.select([fifo], [], [], 1)
            except select.error:
                continue
            if rlist:
                try:
                    data += fifo.readline()
                except IOError:
                    pass
                if data and data[-1] != '\n':
                    continue
                if data:
                    from tryton.gui.main import Main
                    Main.get_main().open_url(data.strip())
                data = ''
            if not os.path.lexists(self.config):
                os.symlink(self.filename, self.config)


class IPCClient(object):

    def __init__(self, hostname, port, database):
        self.hostname = hostname
        self.port = port
        self.database = database
        self.filename = os.path.join(get_config_dir(),
                '%s@%s@%s' % (hostname, port, database))

    def write(self, message):
        raise NotImplemented


class FileClient(IPCClient):

    def __init__(self, hostname, port, database):
        super(FileClient, self).__init__(hostname, port, database)

    def write(self, message):
        if not os.path.exists(self.filename):
            return False
        tmpdir = open(self.filename, 'r').readline().strip()
        _, tmpfile = tempfile.mkstemp(dir=tmpdir, text=True)
        with open(tmpfile, 'w') as tmpfile:
            print >> tmpfile, message
        return True


class FIFOClient(IPCClient):

    def __init__(self, hostname, port, database):
        super(FIFOClient, self).__init__(hostname, port, database)

    def write(self, message):
        if not os.path.lexists(self.filename):
            return False
        fifo = open(self.filename, 'w')
        print >> fifo, message
        return True

if hasattr(os, 'mkfifo'):
    Server = FIFOServer
    Client = FIFOClient
else:
    Server = FileServer
    Client = FileClient
