# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import hashlib
import os
from functools import cache

import trytond.config as config
from trytond.tools import resolve

__all__ = ['filestore']


@cache
def _normpath(path):
    return os.path.normpath(path)


class FileStore(object):

    def get(self, id, prefix=''):
        filename = self._filename(id, prefix)
        with open(filename, 'rb') as fp:
            return fp.read()

    def getmany(self, ids, prefix=''):
        return [self.get(id, prefix) for id in ids]

    def size(self, id, prefix=''):
        filename = self._filename(id, prefix)
        statinfo = os.stat(filename)
        return statinfo.st_size

    def sizemany(self, ids, prefix=''):
        return [self.size(id, prefix) for id in ids]

    def set(self, data, prefix=''):
        id = self._id(data)
        filename = self._filename(id, prefix)
        dirname = os.path.dirname(filename)
        os.makedirs(dirname, mode=0o770, exist_ok=True)

        collision = 0
        while True:
            basename = os.path.basename(filename)
            if os.path.exists(filename):
                if data != self.get(basename, prefix):
                    collision += 1
                    filename = self._filename(
                        '%s-%s' % (id, collision), prefix)
                    continue
            else:
                with open(filename, 'wb')as fp:
                    fp.write(data)
            return basename

    def setmany(self, data, prefix=''):
        return [self.set(d, prefix) for d in data]

    @property
    def path(self):
        return _normpath(config.get('database', 'path'))

    def _filename(self, id, prefix):
        path = self.path
        filename = os.path.join(path, prefix, id[0:2], id[2:4], id)
        filename = os.path.normpath(filename)
        if not filename.startswith(path):
            raise ValueError('Bad prefix')
        return filename

    def _id(self, data):
        return hashlib.md5(data).hexdigest()


if config.get('database', 'class'):
    FileStore = resolve(config.get('database', 'class'))  # noqa: F811
filestore = FileStore()
