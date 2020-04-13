# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest

from trytond.pool import Pool
from trytond.tests.test_tryton import activate_module, with_transaction


class ResourceTestCase(unittest.TestCase):
    "Test Resource"

    @classmethod
    def setUpClass(cls):
        activate_module('tests')

    @with_transaction()
    def test_resources_copied(self):
        "Test resources are copied"
        pool = Pool()
        Resource = pool.get('test.resource')
        Other = pool.get('test.resource.other')
        Note = pool.get('ir.note')

        record = Resource()
        record.save()
        note = Note(resource=record, copy_to_resources=[Other.__name__])
        note.save()
        other = Other()
        other.save()
        copies = record.copy_resources_to(other)

        other_notes = Note.search([('resource', '=', str(other))])
        self.assertTrue(other_notes)
        self.assertEqual(len(other_notes), 1)
        self.assertEqual(other_notes, copies)

    @with_transaction()
    def test_resources_not_copied(self):
        "Test resources are not copied"
        pool = Pool()
        Resource = pool.get('test.resource')
        Other = pool.get('test.resource.other')
        Note = pool.get('ir.note')

        record = Resource()
        record.save()
        note = Note(resource=record)
        note.save()
        other = Other()
        other.save()
        copies = record.copy_resources_to(other)

        other_notes = Note.search([('resource', '=', str(other))])
        self.assertFalse(other_notes)
        self.assertFalse(copies)


def suite():
    return unittest.TestLoader().loadTestsFromTestCase(ResourceTestCase)
