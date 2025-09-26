# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
import shutil
import unittest
from decimal import Decimal
from unittest.mock import ANY, Mock, patch

try:
    import zoneinfo
except ImportError:
    zoneinfo = None
try:
    import pydot
except ImportError:
    pydot = None

from dateutil.relativedelta import relativedelta

from trytond.ir.exceptions import SequenceAffixError
from trytond.ir.lang import _replace
from trytond.pool import Pool
from trytond.pyson import Eval, If, PYSONEncoder
from trytond.tools import timezone
from trytond.transaction import Transaction

from .test_tryton import (
    ModuleTestCase, TestCase, activate_module, drop_db, with_transaction)


class IrTestCase(ModuleTestCase):
    'Test ir module'
    module = 'ir'

    @with_transaction()
    def test_model_search_name(self):
        "Test searching on name of model"
        pool = Pool()
        Model = pool.get('ir.model')

        record, = Model.search([
                ('string', '=', "Language"),
                ('module', '=', 'ir'),
                ])
        self.assertEqual(record.string, "Language")

    @with_transaction()
    def test_model_search_order(self):
        "Test searching and ordering on name of model"
        pool = Pool()
        Model = pool.get('ir.model')

        records = Model.search([
                ('string', 'in', ["Language", "Module"]),
                ('module', '=', 'ir'),
                ],
            order=[('string', 'ASC')])
        self.assertEqual([r.string for r in records], ["Language", "Module"])

    @with_transaction()
    def test_model_field_search_description(self):
        "Test searching on description of model field"
        pool = Pool()
        ModelField = pool.get('ir.model.field')

        field, = ModelField.search([
                ('string', '=', "Name"),
                ('model', '=', 'ir.lang'),
                ('module', '=', 'ir'),
                ])
        self.assertEqual(field.string, "Name")

    @with_transaction()
    def test_model_field_search_order_description(self):
        "Test searching and ordering on description of model field"
        pool = Pool()
        ModelField = pool.get('ir.model.field')

        fields = ModelField.search([
                ('string', 'in', ["Name", "Code"]),
                ('model', '=', 'ir.lang'),
                ('module', '=', 'ir'),
                ])
        self.assertEqual([f.string for f in fields], ["Code", "Name"])

    @with_transaction()
    def test_model_field_lazy(self):
        "Test searching on lazy string of model field"
        pool = Pool()
        ModelField = pool.get('ir.model.field')

        field, = ModelField.search([
                ('string', '=', "ID"),
                ('model', '=', 'ir.lang'),
                ('module', '=', 'ir'),
                ])
        self.assertEqual(field.string, "ID")

    @with_transaction()
    def test_sequence_substitutions(self):
        'Test Sequence Substitutions'
        pool = Pool()
        Sequence = pool.get('ir.sequence')
        SequenceType = pool.get('ir.sequence.type')
        Date = pool.get('ir.date')
        try:
            Group = pool.get('res.group')
            groups = Group.search([])
        except KeyError:
            groups = []

        sequence_type = SequenceType(name='Test', groups=groups)
        sequence_type.save()
        sequence = Sequence(name='Test Sequence', sequence_type=sequence_type)
        sequence.save()
        self.assertEqual(sequence.get(), '1')
        today = Date.today()
        sequence.prefix = '${year}'
        sequence.save()
        self.assertEqual(sequence.get(), '%s2' % str(today.year))
        next_year = today + relativedelta(years=1)
        with Transaction().set_context(date=next_year):
            self.assertEqual(sequence.get(), '%s3' % str(next_year.year))

    @with_transaction()
    def test_sequence_format(self):
        'Test Sequence Format'
        pool = Pool()
        Sequence = pool.get('ir.sequence')
        SequenceType = pool.get('ir.sequence.type')
        try:
            Group = pool.get('res.group')
            groups = Group.search([])
        except KeyError:
            groups = []

        sequence_type = SequenceType(name='Test', groups=groups)
        sequence_type.save()
        sequence = Sequence(name='Test Sequence', sequence_type=sequence_type)
        sequence.save()
        sequence.prefix = '${date_y}-'
        sequence.save()

        today = datetime.date(2023, 1, 1)

        with Transaction().set_context(date=today):
            self.assertEqual(sequence.get(), '23-1')

    @with_transaction()
    def test_sequence_wrong_format(self):
        'Test Sequence Wrong Format'
        pool = Pool()
        Sequence = pool.get('ir.sequence')
        SequenceType = pool.get('ir.sequence.type')
        try:
            Group = pool.get('res.group')
            groups = Group.search([])
        except KeyError:
            groups = []

        sequence_type = SequenceType(name='Test', groups=groups)
        sequence_type.save()
        sequence = Sequence(name='Test Sequence', sequence_type=sequence_type)
        sequence.save()

        with self.assertRaises(SequenceAffixError):
            sequence.prefix = '${date_K}'
            sequence.save()

    @with_transaction()
    def test_sequence_get(self):
        "Test get sequences"
        pool = Pool()
        Sequence = pool.get('ir.sequence')
        SequenceType = pool.get('ir.sequence.type')
        try:
            Group = pool.get('res.group')
            groups = Group.search([])
        except KeyError:
            groups = []

        sequence_type = SequenceType(name='Test', groups=groups)
        sequence_type.save()
        sequence = Sequence(name='Test Sequence', sequence_type=sequence_type)
        sequence.save()

        self.assertEqual(sequence.get(), '1')

    @with_transaction()
    def test_sequence_get_many(self):
        "Test get many sequences"
        pool = Pool()
        Sequence = pool.get('ir.sequence')
        SequenceType = pool.get('ir.sequence.type')
        try:
            Group = pool.get('res.group')
            groups = Group.search([])
        except KeyError:
            groups = []

        sequence_type = SequenceType(name='Test', groups=groups)
        sequence_type.save()
        sequence = Sequence(name='Test Sequence', sequence_type=sequence_type)
        sequence.save()

        self.assertEqual(
            list(sequence.get_many(10)), list(map(str, range(1, 11))))

    @with_transaction()
    def test_ui_view_tree_width_set(self):
        "Test set view tree width"
        pool = Pool()
        ViewTreeWidth = pool.get('ir.ui.view_tree_width')

        model = 'ir.ui.view_tree_width'
        ViewTreeWidth.set_width(model, {
                'user': 100,
                'screen_width': 50,
                }, 1000)

        records = ViewTreeWidth.search([
                ('model', '=', model),
                ])
        self.assertEqual(len(records), 2)
        self.assertEqual({r.screen_width for r in records}, {992})
        self.assertEqual(
            {r.field: r.width for r in records}, {
                'user': 100,
                'screen_width': 50,
                })

    @with_transaction()
    def test_ui_view_tree_width_set_duplicate(self):
        "Test set view tree width with existing duplicate"
        pool = Pool()
        ViewTreeWidth = pool.get('ir.ui.view_tree_width')

        model = 'ir.ui.view_tree_width'
        ViewTreeWidth.create([{
                    'user': Transaction().user,
                    'model': model,
                    'field': 'user',
                    'screen_width': 992,
                    'width': 200,
                    }, {
                    'user': Transaction().user,
                    'model': model,
                    'field': 'user',
                    'screen_width': 992,
                    'width': 300,
                    }])
        ViewTreeWidth.set_width(model, {
                'user': 100,
                'screen_width': 50,
                }, 1000)

        records = ViewTreeWidth.search([
                ('model', '=', model),
                ])
        self.assertEqual(len(records), 2)
        self.assertEqual({r.screen_width for r in records}, {992})
        self.assertEqual(
            {r.field: r.width for r in records}, {
                'user': 100,
                'screen_width': 50,
                })

    @with_transaction()
    def test_ui_view_tree_width_reset(self):
        "Test reset view tree width"
        pool = Pool()
        ViewTreeWidth = pool.get('ir.ui.view_tree_width')

        model = 'ir.ui.view_tree_width'
        ViewTreeWidth.create([{
                    'user': Transaction().user,
                    'model': model,
                    'field': 'user',
                    'screen_width': 992,
                    'width': 200,
                    }, {
                    'user': Transaction().user,
                    'model': model,
                    'field': 'user',
                    'screen_width': None,
                    'width': 200,
                    }, {
                    'user': Transaction().user,
                    'model': model,
                    'field': 'user',
                    'screen_width': 1400,
                    'width': 200,
                    }])

        ViewTreeWidth.reset_width(model, 1000)

        record, = ViewTreeWidth.search([
                ('model', '=', model),
                ])
        self.assertEqual(record.screen_width, 1400)

    @with_transaction()
    def test_ui_view_tree_width_get(self):
        "Test get view tree width"
        pool = Pool()
        ViewTreeWidth = pool.get('ir.ui.view_tree_width')

        model = 'ir.ui.view_tree_width'
        ViewTreeWidth.set_width(model, {
                'user': 100,
                'screen_width': 50,
                }, 1000)

        widths = ViewTreeWidth.get_width(model, 1000)

        self.assertEqual(
            widths, {
                'user': 100,
                'screen_width': 50,
                })

    @with_transaction()
    def test_ui_view_tree_width_get_fallback(self):
        "Test get view tree width"
        pool = Pool()
        ViewTreeWidth = pool.get('ir.ui.view_tree_width')

        model = 'ir.ui.view_tree_width'
        ViewTreeWidth.set_width(model, {
                'user': 100,
                'screen_width': 50,
                }, 500)

        widths = ViewTreeWidth.get_width(model, 1000)

        self.assertEqual(
            widths, {
                'user': 100,
                'screen_width': 50,
                })

    @with_transaction()
    def test_global_search(self):
        'Test Global Search'
        pool = Pool()
        Model = pool.get('ir.model')
        Model.global_search('User', 10)

    @with_transaction()
    def test_lang_get_subtags(self):
        "Test Lang.get with subtags"
        pool = Pool()
        Lang = pool.get('ir.lang')

        self.assertEqual(Lang.get('fr_CA').code, 'fr')
        self.assertEqual(Lang.get('fr-BE').code, 'fr')

    @with_transaction()
    def test_lang_get_unknown(self):
        "Test Lang.get with unknown language"
        pool = Pool()
        Lang = pool.get('ir.lang')

        self.assertEqual(Lang.get('foo').code, 'en')

    @with_transaction()
    def test_lang_currency(self):
        "Test Lang.currency"
        pool = Pool()
        Lang = pool.get('ir.lang')
        lang = Lang.get('en')
        currency = Mock()
        currency.digits = 2
        currency.symbol = '$'
        test_data = [
            (Decimal('10.50'), True, False, None, '$10.50'),
            (Decimal('10.50'), True, False, 4, '$10.5000'),
            ]
        for value, symbol, grouping, digits, result in test_data:
            self.assertEqual(
                lang.currency(value, currency, symbol, grouping, digits),
                result)

    @with_transaction()
    def test_lang_currency_without_symbol(self):
        "Test Lang.currency without symbol"
        pool = Pool()
        Lang = pool.get('ir.lang')
        lang = Lang.get('en')
        currency = Mock()
        currency.digits = 2
        currency.symbol = None
        currency.code = 'USD'
        test_data = [
            (Decimal('10.50'), True, False, None, 'USD 10.50'),
            (Decimal('10.50'), True, False, 4, 'USD 10.5000'),
            ]
        for value, symbol, grouping, digits, result in test_data:
            self.assertEqual(
                lang.currency(value, currency, symbol, grouping, digits),
                result)

    @with_transaction()
    def test_lang_format(self):
        "Test Lang.format"
        pool = Pool()
        Lang = pool.get('ir.lang')
        lang = Lang.get('en')
        test_data = [
            ('%i', 42, False, False, [], "42"),
            ]
        for percent, value, grouping, monetary, add, result in test_data:
            self.assertEqual(
                lang.format(percent, value, grouping, monetary, *add), result)

    def test_lang_replace(self):
        "Test string _replace"
        for src, result in [
                ('%x', 'foo'),
                ('%%x', '%%x'),
                ('%x %x', 'foo foo'),
                ('%x %y %x %%x', 'foo %y foo %%x'),
                ]:
            with self.subTest(src=src):
                self.assertEqual(_replace(src, '%x', 'foo'), result)

    @with_transaction()
    def test_lang_strftime(self):
        "Test Lang.strftime"
        pool = Pool()
        Lang = pool.get('ir.lang')
        lang = Lang.get('en')
        test_data = [
            (datetime.date(2016, 8, 3), '%d %B %Y', "03 August 2016"),
            (datetime.time(8, 20), '%I:%M %p', "08:20 AM"),
            (datetime.datetime(2018, 11, 1, 14, 30), '%a %d %b %Y %I:%M %p',
                "Thu 01 Nov 2018 02:30 PM"),
            (datetime.date(2018, 11, 1), '%x', "11/01/2018"),
            (datetime.datetime(2018, 11, 1, 14, 30, 12),
                '%x %X', "11/01/2018 14:30:12"),
            (datetime.datetime(2018, 11, 1, 14, 30, 12),
                '%H:%M:%S', "14:30:12"),
            (datetime.datetime(2018, 11, 1, 14, 30, 12), None,
                "11/01/2018 14:30:12"),
            (datetime.date(2016, 8, 3), '%d %%m %Y', "03 %m 2016"),
            (datetime.date(2018, 11, 1), '%d %%x', "01 %x"),
            (datetime.date(2018, 11, 1), '%d %%a', "01 %a"),
            (datetime.datetime(2018, 11, 1, 14, 30, 12), '%d %%p', "01 %p"),
            ]
        for date, format_, result in test_data:
            with self.subTest(date=date, format=format_):
                self.assertEqual(lang.strftime(date, format_), result)

    @with_transaction()
    def test_lang_format_number(self):
        "Test Lang.format_number"
        pool = Pool()
        Lang = pool.get('ir.lang')
        lang = Lang.get('en')
        test_data = [
            (Decimal('10.50'), False, None, '10.50'),
            (Decimal('10.50'), False, 4, '10.5000'),
            (Decimal('1000.50'), True, 4, '1,000.5000'),
            ]
        for value, grouping, digits, result in test_data:
            self.assertEqual(
                lang.format_number(value, digits, grouping), result)

    @with_transaction()
    def test_lang_format_number_symbol(self):
        "Test Lang.format_number_symbol"
        pool = Pool()
        Lang = pool.get('ir.lang')
        lang = Lang.get('en')
        unit = Mock()
        unit.symbol = 'Kg'
        unit.get_symbol = Mock()
        unit.get_symbol.return_value = 'Kg', 1
        test_data = [
            (Decimal('10.50'), False, None, '10.50 Kg'),
            (Decimal('1000.50'), True, 4, '1,000.5000 Kg'),
            ]
        for value, grouping, digits, result in test_data:
            self.assertEqual(
                lang.format_number_symbol(value, unit, digits, grouping),
                result)

    @with_transaction()
    def test_lang_plural(self):
        "Test Lang plural"
        pool = Pool()
        Lang = pool.get('ir.lang')

        languages = Lang.search([])
        for i in range(100):
            for language in languages:
                language.get_plural(i)

    @with_transaction()
    def test_model_data_get_id(self):
        "Test ModelData.get_id"
        pool = Pool()
        ModelData = pool.get('ir.model.data')
        User = pool.get('res.user')

        admin_id = ModelData.get_id('res', 'user_admin')
        admin, = User.search([('login', '=', 'admin')])

        self.assertEqual(admin_id, admin.id)

    @with_transaction()
    def test_model_data_get_id_dot(self):
        "Test ModelData.get_id with dot"
        pool = Pool()
        ModelData = pool.get('ir.model.data')
        User = pool.get('res.user')

        admin_id = ModelData.get_id('res.user_admin')
        admin, = User.search([('login', '=', 'admin')])

        self.assertEqual(admin_id, admin.id)

    @with_transaction()
    def test_email_send(self):
        "Test sending email"
        pool = Pool()
        Email = pool.get('ir.email')
        Report = pool.get('ir.action.report')
        Attachment = pool.get('ir.attachment')

        report = Report(
            name="Test Email",
            model='res.user',
            report_name='tests.email_send',
            report_content=b'report',
            template_extension='txt',
            )
        report.save()

        def set_message_id(msg, *args, **kwargs):
            msg['Message-ID'] = 'test'

        with patch(
                'trytond.ir.email_.send_message_transactional'
                ) as send_message:
            send_message.side_effect = set_message_id
            email = Email.send(
                to='"John Doe" <john@example.com>, Jane <jane@example.com>',
                cc='User <user@example.com>',
                bcc='me@example.com',
                subject="Email subject",
                body='<p>Hello</p>',
                files=[('file.txt', b'data')],
                record=('res.user', 1),
                reports=[report.id])

            attachments = Attachment.search([
                    ('resource', '=', str(email)),
                    ])

        addresses = [
            'john@example.com',
            'jane@example.com',
            'user@example.com',
            'me@example.com']
        send_message.assert_called_once_with(ANY, strict=True)
        self.assertEqual(
            email.recipients,
            'John Doe <john@example.com>, Jane <jane@example.com>')
        self.assertEqual(email.recipients_secondary, 'User <user@example.com>')
        self.assertEqual(email.recipients_hidden, 'me@example.com')
        self.assertEqual(
            [a.address for a in email.addresses],
            addresses)
        self.assertEqual(email.message_id, 'test')
        self.assertEqual(email.subject, "Email subject")
        self.assertEqual(email.body, '<p>Hello</p>')
        self.assertEqual(len(attachments), 2)
        self.assertEqual(
            {a.name for a in attachments},
            {'file.txt', 'Test-Email-Administrator.txt'})
        self.assertEqual(
            {a.data for a in attachments}, {b'data', b'report'})

    @with_transaction()
    def test_email_template_get(self):
        "Test email template get"
        pool = Pool()
        Template = pool.get('ir.email.template')
        IrModel = pool.get('ir.model')
        IrModelField = pool.get('ir.model.field')
        User = pool.get('res.user')

        admin = User(1)
        admin.email = 'admin@example.com'
        admin.save()
        model, = IrModel.search([('name', '=', 'res.user')])
        field, = IrModelField.search([
                ('model', '=', 'res.user'),
                ('name', '=', 'id'),
                ])

        template = Template(
            model=model,
            name="Test",
            recipients=field,
            subject="Subject: ${record.login}",
            body="<p>Hello, ${record.name}</p>")
        template.save()

        values = template.get(admin)

        self.assertEqual(
            values, {
                'to': ['Administrator <admin@example.com>'],
                'subject': "Subject: admin",
                'body': '<p>Hello, Administrator</p>',
                })

    @with_transaction()
    def test_email_template_get_default(self):
        "Test email template get default"
        pool = Pool()
        Template = pool.get('ir.email.template')
        IrModel = pool.get('ir.model')
        IrModelField = pool.get('ir.model.field')
        User = pool.get('res.user')

        admin = User(1)
        admin.email = 'admin@example.com'
        admin.save()
        model, = IrModel.search([('name', '=', 'res.user')])
        field, = IrModelField.search([
                ('model', '=', 'res.user'),
                ('name', '=', 'id'),
                ])

        values = Template.get_default(User.__name__, admin.id)

        self.assertEqual(
            values, {
                'to': ['Administrator <admin@example.com>'],
                'subject': "User: Administrator",
                })

    @with_transaction()
    def test_email_template_get_pyson(self):
        "Test email template get with pyson"
        pool = Pool()
        Template = pool.get('ir.email.template')
        IrModel = pool.get('ir.model')
        IrModelField = pool.get('ir.model.field')
        User = pool.get('res.user')

        admin = User(1)
        admin.email = 'admin@example.com'
        admin.save()
        model, = IrModel.search([('name', '=', 'res.user')])
        field, = IrModelField.search([
                ('model', '=', 'res.user'),
                ('name', '=', 'id'),
                ])

        template = Template(
            model=model,
            name="Test",
            recipients_pyson=PYSONEncoder().encode(
                [Eval('self.email')]),
            recipients_secondary_pyson=PYSONEncoder().encode(
                If(Eval('self.email'),
                    ['fallback@example.com'],
                    [])),
            )
        template.save()

        values = template.get(admin)

        self.assertEqual(
            values, {
                'to': ['admin@example.com'],
                'cc': ['fallback@example.com'],
                })

    @unittest.skipUnless(
        pydot and shutil.which('dot'), "pydot is needed to generate graph")
    @with_transaction()
    def test_model_graph(self):
        "Test model graph"
        pool = Pool()
        Model = pool.get('ir.model')
        ModelGraph = pool.get('ir.model.graph', type='report')

        models = Model.search([])

        oext, content, print_, filename = (
            ModelGraph.execute([m.id for m in models], {
                    'level': 1,
                    'filter': '',
                    }))
        self.assertEqual(oext, 'png')
        self.assertTrue(content)
        self.assertFalse(print_)
        self.assertEqual(filename, "Graph")

    @unittest.skipUnless(
        pydot and shutil.which('dot'), "pydot is needed to generate graph")
    @with_transaction()
    def test_workflow_graph(self):
        "Test workflow graph"
        pool = Pool()
        Model = pool.get('ir.model')
        ModelWorkflowGraph = pool.get('ir.model.workflow_graph', type='report')

        model, = Model.search([('name', '=', 'ir.error')])

        oext, content, print_, filename = (
                ModelWorkflowGraph.execute([model.id], {}))
        self.assertEqual(oext, 'png')
        self.assertTrue(content)
        self.assertFalse(print_)
        self.assertEqual(filename, "Workflow Graph")


class IrCronTestCase(TestCase):
    "Test ir.cron features"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        drop_db()
        activate_module(['ir'])

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        drop_db()

    def setUp(self):
        server_tz = timezone.SERVER
        timezone.SERVER = timezone.ZoneInfo('America/Toronto')
        self.addCleanup(setattr, timezone, 'SERVER', server_tz)

    def _get_cron(self):
        pool = Pool()
        Cron = pool.get('ir.cron')

        cron = Cron()
        for attribute in [
                'interval_number', 'interval_type', 'minute', 'hour',
                'weekday', 'day']:
            setattr(cron, attribute, None)
        return cron

    @with_transaction()
    def test_scheduling_non_utc(self):
        "Test scheduling with a non UTC timezone"
        cron = self._get_cron()
        cron.interval_number = 1
        cron.interval_type = 'days'
        cron.hour = 1
        cron.minute = 0

        # Quebec is UTC-5
        self.assertEqual(
            cron.compute_next_call(datetime.datetime(2021, 12, 31, 5, 0)),
            datetime.datetime(2022, 1, 1, 6, 0))

    @unittest.skipIf(not zoneinfo, "dateutil does not compute correctly")
    @with_transaction()
    def test_scheduling_on_dst_change(self):
        "Test scheduling while the DST change occurs"
        cron = self._get_cron()
        cron.interval_number = 1
        cron.interval_type = 'days'
        cron.hour = 2
        cron.minute = 30

        # 2022-03-13 is the day of DST switch
        # Quebec is UTC-4
        self.assertEqual(
            cron.compute_next_call(datetime.datetime(2022, 3, 12, 6, 30)),
            datetime.datetime(2022, 3, 13, 7, 30))

    @with_transaction()
    def test_scheduling_on_standard_time(self):
        "Test scheduling while the calendar returns to the standard time"
        cron = self._get_cron()
        cron.interval_number = 1
        cron.interval_type = 'hours'
        cron.minute = 30

        # 2022-11-06 is the day of DST switch
        # Quebec is UTC-5
        self.assertEqual(
            cron.compute_next_call(datetime.datetime(2022, 11, 6, 7, 30)),
            datetime.datetime(2022, 11, 6, 8, 30))

    @with_transaction()
    def test_get_timezone(self):
        "Test get_timezone"
        cron = self._get_cron()

        self.assertIsInstance(cron.get_timezone('timezone'), str)


del ModuleTestCase
