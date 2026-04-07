# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from naiad import Record
from trytond.pool import Pool

from .common import NaiadTestCase


class DeleteTestCase(NaiadTestCase):

    @classmethod
    def setUpDatabase(cls):
        pool = Pool()
        Group = pool.get('res.group')
        super().setUpDatabase()
        group = Group(name="Group to delete")
        group.save()
        cls.group_id = group.id

    def test_delete(self):
        record = Record('res.group', id=self.group_id)
        self.client().delete(record)
