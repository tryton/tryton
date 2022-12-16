# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import os
import shutil
import tempfile
import unittest
from unittest.mock import patch

from trytond.config import config
from trytond.filestore import filestore


class FileStoreTestCase(unittest.TestCase):
    "Test FileStore"

    def setUp(self):
        path = config.get('database', 'path')
        dtemp = tempfile.mkdtemp()
        config.set('database', 'path', dtemp)
        self.addCleanup(config.set, 'database', 'path', path)
        self.addCleanup(shutil.rmtree, dtemp)

    def data(self):
        return os.urandom(10)

    def test_set(self):
        "Test set"
        result = filestore.set(self.data(), prefix='test')
        self.assertTrue(result)
        self.assertIsInstance(result, str)

    def test_setmany(self):
        "Test setmany"
        result = filestore.setmany([self.data(), self.data()], prefix='test')
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 2)
        self.assertIsInstance(result[0], str)

    def test_get(self):
        "Test get"
        data = self.data()
        id = filestore.set(data, prefix='test')
        self.assertEqual(filestore.get(id, prefix='test'), data)

    def test_getmany(self):
        "Test getmany"
        data = [self.data(), self.data()]
        ids = filestore.setmany(data, prefix='test')
        self.assertListEqual(filestore.getmany(ids, prefix='test'), data)

    def test_size(self):
        "Test size"
        data = self.data()
        id = filestore.set(data, prefix='test')
        self.assertEqual(filestore.size(id, prefix='test'), len(data))

    def test_sizemany(self):
        "Test sizemany"
        data = [self.data(), self.data()]
        lens = [len(d) for d in data]
        ids = filestore.setmany(data, prefix='test')
        self.assertListEqual(filestore.sizemany(ids, prefix='test'), lens)

    def test_prefix(self):
        "Test prefix"
        data = self.data()
        id = filestore.set(data, prefix='foo')
        with self.assertRaises(IOError):
            filestore.get(id, prefix='bar')

    def test_bad_prefix(self):
        "Test bad prefix"
        with self.assertRaises(ValueError):
            filestore.set(self.data(), prefix='../')

    def test_duplicate(self):
        "Test duplicate"
        data = self.data()
        id = filestore.set(data, prefix='test')
        self.assertEqual(filestore.set(data, prefix='test'), id)

    def test_collision(self):
        "Test collision"
        data1 = self.data()
        data2 = self.data()

        id1 = filestore.set(data1, prefix='test')

        with patch.object(filestore, '_id') as _id:
            _id.return_value = id1

            id2 = filestore.set(data2, prefix='test')

        self.assertNotEqual(id1, id2)
        self.assertEqual(filestore.get(id1, prefix='test'), data1)
        self.assertEqual(filestore.get(id2, prefix='test'), data2)
