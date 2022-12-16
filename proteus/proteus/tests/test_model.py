# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from proteus import Model
from .common import ProteusTestCase


class TestModel(ProteusTestCase):

    def test_class_cache(self):
        User1 = Model.get('res.user')
        User2 = Model.get('res.user')
        self.assertEqual(id(User1), id(User2))

        Model.reset()
        User3 = Model.get('res.user')
        self.assertNotEqual(id(User1), id(User3))

    def test_class_method(self):
        User = Model.get('res.user')
        self.assertTrue(len(User.search([('login', '=', 'admin')], {})))

    def test_int(self):
        User = Model.get('res.user')
        admin = User.find([('login', '=', 'admin')])[0]
        self.assertEqual(int(admin), admin.id)

    def test_id_zero(self):
        User = Model.get('res.user')
        root = User(0)
        self.assertEqual(root.login, 'root')

    def test_find(self):
        User = Model.get('res.user')
        admin = User.find([('login', '=', 'admin')])[0]
        self.assertEqual(admin.login, 'admin')

    def test_many2one(self):
        User = Model.get('res.user')
        admin = User.find([('login', '=', 'admin')])[0]
        self.assertTrue(isinstance(admin.create_uid, User))
        try:
            admin.create_uid = 'test'
            self.fail()
        except AssertionError:
            pass
        admin.create_uid = admin
        admin.create_uid = None

        User(write_uid=None)

    def test_one2many(self):
        Group = Model.get('res.group')
        administration = Group.find([('name', '=', 'Administration')])[0]
        self.assertTrue(isinstance(administration.model_access, list))
        self.assertTrue(isinstance(administration.model_access[0],
            Model.get('ir.model.access')))
        try:
            administration.model_access = []
            self.fail()
        except AttributeError:
            pass

    def test_many2many(self):
        User = Model.get('res.user')
        admin = User.find([('login', '=', 'admin')])[0]
        self.assertTrue(isinstance(admin.groups, list))
        self.assertTrue(isinstance(admin.groups[0],
            Model.get('res.group')))
        try:
            admin.groups = []
            self.fail()
        except AttributeError:
            pass

    # TODO test date

    def test_reference(self):
        Attachment = Model.get('ir.attachment')
        User = Model.get('res.user')
        admin = User.find([('login', '=', 'admin')])[0]
        attachment = Attachment()
        attachment.name = 'Test'
        attachment.resource = admin
        attachment.save()
        self.assertEqual(attachment.resource, admin)

    def test_id_counter(self):
        User = Model.get('res.user')
        test1 = User()
        self.assertTrue(test1.id < 0)
        test2 = User()
        self.assertTrue(test2.id < 0)
        self.assertNotEqual(test1.id, test2.id)

    def test_init(self):
        User = Model.get('res.user')
        self.assertEqual(User(1).id, 1)
        self.assertEqual(User(name='Foo').name, 'Foo')

        Lang = Model.get('ir.lang')
        en, = Lang.find([('code', '=', 'en')])
        self.assertEqual(User(language=en).language, en)
        self.assertEqual(User(language=en.id).language, en)

        Group = Model.get('res.group')
        groups = Group.find()
        self.assertEqual(len(User(groups=groups).groups), len(groups))
        self.assertEqual(len(User(groups=[x.id for x in groups]).groups),
                len(groups))

    def test_assign_unknown_field(self):
        "Test it is not allowed to assign unknown field"
        User = Model.get('res.user')
        user = User()

        with self.assertRaises(AttributeError):
            user.unknown_field = 'foo'

    def test_save(self):
        User = Model.get('res.user')
        test = User()
        test.name = 'Test'
        test.login = 'test'
        test.save()
        self.assertTrue(test.id > 0)

        test = User(test.id)
        self.assertEqual(test.name, 'Test')
        self.assertEqual(test.login, 'test')
        self.assertTrue(test.active)

        test.signature = 'Test signature'
        self.assertEqual(test.signature, 'Test signature')
        test.save()
        self.assertEqual(test.signature, 'Test signature')
        test = User(test.id)
        self.assertEqual(test.signature, 'Test signature')

        Group = Model.get('res.group')
        test2 = User(name='Test 2', login='test2',
                groups=[Group(name='Test 2')])
        test2.save()
        self.assertTrue(test2.id > 0)
        self.assertEqual(test2.name, 'Test 2')
        self.assertEqual(test2.login, 'test2')

        test.signature = 'classmethod save'
        test2.name = 'Test 2 classmethod'
        test3 = User(name='Test 3', login='test3')
        User.save([test, test2, test3])
        self.assertEqual(test.signature, 'classmethod save')
        self.assertEqual(test2.name, 'Test 2 classmethod')
        self.assertTrue(test3.id > 0)
        self.assertEqual(test3.name, 'Test 3')

    def test_save_many2one(self):
        User = Model.get('res.user')
        test = User()
        test.name = 'Test save many2one'
        test.login = 'test_save_many2one'
        test.save()

        Lang = Model.get('ir.lang')
        en, = Lang.find([('code', '=', 'en')])
        test.language = en
        test.save()
        self.assertEqual(test.language, en)

        test.language = None
        test.save()
        self.assertFalse(test.language)

    def test_save_one2many(self):
        Group = Model.get('res.group')
        group = Group()
        group.name = 'Test save one2many'
        group.save()

        ModelAccess = Model.get('ir.model.access')
        Model_ = Model.get('ir.model')
        model_access = ModelAccess()
        model_access.model = Model_.find([('model', '=', 'res.group')])[0]
        model_access.perm_read = True
        model_access.perm_write = True
        model_access.perm_create = True
        model_access.perm_delete = True

        group.model_access.append(model_access)
        group.save()
        self.assertEqual(len(group.model_access), 1)

        model_access_id = group.model_access[0].id

        group.name = 'Test save one2many bis'
        group.model_access[0].description = 'Test save one2many'
        group.save()
        self.assertEqual(group.model_access[0].description,
                'Test save one2many')

        group.model_access.pop()
        group.save()
        self.assertEqual(group.model_access, [])
        self.assertEqual(len(ModelAccess.find([('id', '=', model_access_id)])),
                1)

        group.model_access.append(ModelAccess(model_access_id))
        group.save()
        self.assertEqual(len(group.model_access), 1)

        group.model_access.remove(group.model_access[0])
        group.save()
        self.assertEqual(group.model_access, [])
        self.assertEqual(len(ModelAccess.find([('id', '=', model_access_id)])),
                0)

    def test_save_many2many(self):
        User = Model.get('res.user')
        test = User()
        test.name = 'Test save many2many'
        test.login = 'test_save_many2many'
        test.save()

        Group = Model.get('res.group')
        group = Group()
        group.name = 'Test save many2many'
        group.save()

        test.groups.append(group)
        test.save()
        self.assertEqual(len(test.groups), 1)

        group_id = test.groups[0].id

        test.name = 'Test save many2many bis'
        test.groups[0].name = 'Test save many2many bis'
        test.save()
        self.assertEqual(test.groups[0].name,
                'Test save many2many bis')

        test.groups.pop()
        test.save()
        self.assertEqual(test.groups, [])
        self.assertEqual(len(Group.find([('id', '=', group_id)])), 1)

        test.groups.append(Group(group_id))
        test.save()
        self.assertEqual(len(test.groups), 1)

        test.groups.remove(test.groups[0])
        test.save()
        self.assertEqual(test.groups, [])
        self.assertEqual(len(Group.find([('id', '=', group_id)])), 0)

    def test_eq(self):
        User = Model.get('res.user')
        test = User()
        test.name = 'Test eq'
        test.login = 'test_eq'
        test.save()
        admin1 = User.find([('login', '=', 'admin')])[0]
        admin2 = User.find([('login', '=', 'admin')])[0]

        self.assertEqual(admin1, admin2)
        self.assertFalse(admin1 != admin2)
        self.assertNotEqual(admin1, test)
        self.assertFalse(admin1 == test)
        self.assertNotEqual(admin1, None)
        self.assertNotEqual(admin1, False)
        self.assertNotEqual(admin1, 1)

    def test_default_set(self):
        User = Model.get('res.user')
        Group = Model.get('res.group')
        group_ids = [x.id for x in Group.find()]
        test = User()
        test._default_set({
            'name': 'Test',
            'groups': group_ids,
            })
        self.assertEqual(test.name, 'Test')
        self.assertEqual([x.id for x in test.groups], group_ids)

        test = User()
        test._default_set({
            'name': 'Test',
            'groups': [
                {
                    'name': 'Group 1',
                },
                {
                    'name': 'Group 2',
                },
                ],
            })
        self.assertEqual(test.name, 'Test')
        self.assertEqual([x.name for x in test.groups], ['Group 1', 'Group 2'])

    def test_delete(self):
        Group = Model.get('res.group')
        test = Group()
        test.name = 'Test delete'
        test.save()
        test.delete()

    def test_duplicate(self):
        User = Model.get('res.user')
        test = User()
        test.name = 'Test duplicate'
        test.login = 'test duplicate'
        test.save()
        copy, = User.duplicate([test], {'name': 'Test copy'})
        self.assertEqual(copy.name, 'Test copy')
        self.assertEqual(copy.login, 'test duplicate (copy)')
        self.assertNotEqual(copy.id, test.id)

    def test_on_change(self):
        Trigger = Model.get('ir.trigger')

        trigger = Trigger()

        trigger.on_time = True
        self.assertEqual(trigger.on_create, False)

        trigger.on_create = True
        self.assertEqual(trigger.on_time, False)

    def test_on_change_with(self):
        Attachment = Model.get('ir.attachment')

        attachment = Attachment()

        attachment.description = 'Test'
        self.assertEqual(attachment.summary, 'Test')

    def test_on_change_set(self):
        User = Model.get('res.user')
        Group = Model.get('res.group')

        test = User()
        test._on_change_set('name', 'Test')
        self.assertEqual(test.name, 'Test')
        group_ids = [x.id for x in Group.find()]
        test._on_change_set('groups', group_ids)
        self.assertEqual([x.id for x in test.groups], group_ids)

        test._on_change_set('groups', {'remove': [group_ids[0]]})
        self.assertEqual([x.id for x in test.groups], group_ids[1:])

        test._on_change_set('groups', {'add': [(-1, {
                            'name': 'Bar',
                            })]})
        self.assertTrue([x for x in test.groups if x.name == 'Bar'])

        test.groups.extend(Group.find())
        group = test.groups[0]
        test._on_change_set('groups', {'update': [{
            'id': group.id,
            'name': 'Foo',
            }]})
        self.assertTrue([x for x in test.groups if x.name == 'Foo'])

    def test_model_list_find(self):
        User = Model.get('res.user')
        Group = Model.get('res.group')

        test = User()
        groups = test.groups.find(order=[('id', 'ASC')])
        all_groups = Group.find([], order=[('id', 'ASC')])

        self.assertListEqual(groups, all_groups)
