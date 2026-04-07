# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from unittest import TestCase

from naiad import Record, set_delete, set_remove


class RecordTestCase(TestCase):

    def test_repr(self):
        "Test repr"
        string = repr(Record('res.user', id=42))

        self.assertEqual(string, "Record('res.user', id=42)")

    def test_contains(self):
        "Test contains"
        record = Record('res.user', login='foo')
        self.assertIn('login', record)

    def test_int(self):
        "Test int"
        record = Record('res.user', id=42)
        self.assertEqual(int(record), 42)

    def test_int_no_id(self):
        "Test int without id"
        record = Record('res.user')
        with self.assertRaises(TypeError):
            int(record)

    def test_str(self):
        "Test str"
        record = Record('res.user', id=42)
        self.assertEqual(str(record), '42')

    def test_str_no_id(self):
        "Test str without id"
        record = Record('res.user')
        self.assertEqual(str(record), '')

    def test_str_rec_name(self):
        "Test str with rec_name"
        record = Record('res.user', id=42, rec_name="Foo")
        self.assertEqual(str(record), "Foo")

    def test_equality(self):
        "Test equality"
        record1 = Record('res.user', id=42, login='foo')
        record2 = Record('res.user', id=42, name='bar')

        self.assertEqual(record1, record2)
        self.assertEqual(record1, 42)

    def test_inequality(self):
        "Test inequality"
        record1 = Record('res.user', id=42)
        record2 = Record('res.user', id=1)
        record3 = Record('res.group', id=42)

        self.assertNotEqual(record1, record2)
        self.assertNotEqual(record1, record3)

    def test_order(self):
        "Test order"
        record1 = Record('res.user', id=1)
        record2 = Record('res.user', id=2)

        self.assertLess(record1, record2)

    def test_hashable(self):
        "Test hashable"
        record = Record('res.user', id=42)

        self.assertIn(record, {record: None})

    def test_boolean(self):
        "Test boolean"
        self.assertTrue(Record('res.user'))

    def test_to_dict(self):
        "Test to dict"
        record = Record(
            'res.user', id=1,
            name="User",
            groups=[{'__name__': 'res.group', 'id': 2, 'name': "Group"}])

        self.assertDictEqual(record.to_dict(), {
                '__name__': 'res.user',
                'id': 1,
                'name': "User",
                'groups': [{
                        '__name__': 'res.group',
                        'id': 2,
                        'name': "Group",
                        }],
                })

    def test_to_dict_instance(self):
        "Test to dict with instance"
        record = Record('res.user', id=1)
        record.groups = [Record('res.group', id=2)]

        self.assertDictEqual(record.to_dict(), {
                '__name__': 'res.user',
                'id': 1,
                'groups': [{
                        '__name__': 'res.group',
                        'id': 2,
                        }],
                })

    def test_to_values(self):
        "Test to values"
        record = Record('res.user', id=1)
        record.name = "Name"

        self.assertDictEqual(record.to_values(), {
                'name': "Name",
                })

    def test_to_values_not_modified(self):
        "Test to values not modified"
        record = Record('res.user', id=1, name="Name")
        record.name = "Name"

        self.assertDictEqual(record.to_values(), {})

    def test_to_values_list_create(self):
        "Test to values with list to create"
        record = Record('res.user', id=1)
        record.groups = [Record('res.group', name="Group")]

        self.assertDictEqual(record.to_values(), {
                'groups': [('create', [{'name': "Group"}])],
                })

    def test_to_values_list_add(self):
        "Test to values with list to add"
        record = Record('res.user', id=1)
        record.groups = [Record('res.group', id=2)]

        self.assertDictEqual(record.to_values(), {
                'groups': [('add', [2])],
                })

    def test_to_values_list_add_write(self):
        "Test to values with list to add and write"
        record = Record('res.user', id=1)
        record2 = Record('res.group', id=2)
        record.groups = [record2]
        record2.name = "Group"

        self.assertDictEqual(record.to_values(), {
                'groups': [('add', [2]), ('write', [2], {'name': "Group"})],
                })

    def test_to_values_list_write(self):
        "Test to values with list to write"
        record = Record(
            'res.user', id=1, groups=[{'__name__': 'res.group', 'id': 2}])
        record.groups[0].name = "Group"

        self.assertDictEqual(record.to_values(), {
                'groups': [('write', [2], {'name': "Group"})],
                })

    def test_to_values_list_delete(self):
        "Test to values with list to delete"
        record = Record(
            'res.user', id=1, groups=[{'__name__': 'res.group', 'id': 2}])
        record.groups = ()

        with set_delete('res.user', 'groups'):
            self.assertDictEqual(record.to_values(), {
                    'groups': [('delete', [2])],
                    })

    def test_to_values_list_remove(self):
        "Test to values with list to remove"
        record = Record(
            'res.user', id=1, groups=[{'__name__': 'res.group', 'id': 2}])
        record.groups = ()

        with set_remove('res.user', 'groups'):
            self.assertDictEqual(record.to_values(), {
                    'groups': [('remove', [2])],
                    })
