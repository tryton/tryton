# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
import time
import uuid
from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr, getaddresses
from urllib.parse import (
    urlsplit, parse_qsl, urlencode, urlunsplit, quote, urljoin)

try:
    import html2text
except ImportError:
    html2text = None

from sql import Literal
from sql.aggregate import Count
from sql.functions import Substring, Position
from genshi.template import MarkupTemplate
from genshi.core import START, END, QName, Attrs

from trytond.config import config
from trytond.i18n import gettext
from trytond.model import (fields, ModelSQL, ModelView, Workflow, Unique,
    EvalEnvironment, dualmethod)
from trytond.pool import Pool
from trytond.pyson import PYSONDecoder, Eval, If
from trytond.report import Report
from trytond.sendmail import sendmail_transactional, SMTPDataManager
from trytond.tools import grouped_slice, reduce_ids
from trytond.transaction import Transaction
from trytond.url import HOSTNAME
from trytond.wsgi import Base64Converter

from .exceptions import DomainError, ConditionError, TemplateError
from .mixin import MarketingAutomationMixin

if not config.get(
        'html', 'plugins-marketing.automation.activity-email_template'):
    config.set(
        'html', 'plugins-marketing.automation.activity-email_template',
        'fullpage')

USE_SSL = bool(config.get('ssl', 'certificate'))
URL_BASE = config.get('marketing', 'automation_base',
    default=urlunsplit(
        ('http' + ('s' if USE_SSL else ''), HOSTNAME, '', '', '')))
URL_OPEN = urljoin(URL_BASE, '/m/empty.gif')


def _formataddr(name, email):
    if name:
        name = str(Header(name, 'utf-8'))
    return formataddr((name, email))


class Scenario(Workflow, ModelSQL, ModelView):
    "Marketing Scenario"
    __name__ = 'marketing.automation.scenario'

    name = fields.Char("Name")
    model = fields.Selection('get_models', "Model", required=True)
    domain = fields.Char(
        "Domain", required=True,
        help="A PYSON domain used to filter records valid for this scenario.")
    activities = fields.One2Many(
        'marketing.automation.activity', 'parent', "Activities")
    record_count = fields.Function(
        fields.Integer("Records"), 'get_record_count')
    record_count_blocked = fields.Function(
        fields.Integer("Records Blocked"), 'get_record_count')
    state = fields.Selection([
            ('draft', "Draft"),
            ('running', "Running"),
            ('stopped', "Stopped"),
            ], "State", required=True, readonly=True)

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._transitions |= set((
                ('draft', 'running'),
                ('running', 'stopped'),
                ('stopped', 'draft'),
                ))
        cls._buttons.update(
            draft={
                'invisible': Eval('state') != 'stopped',
                'depends': ['state'],
                },
            run={
                'invisible': Eval('state') != 'draft',
                'depends': ['state'],
                },
            stop={
                'invisible': Eval('state') != 'running',
                },
            )

    @classmethod
    def default_state(cls):
        return 'draft'

    @classmethod
    def default_domain(cls):
        return '[]'

    @classmethod
    def get_models(cls):
        pool = Pool()
        Model = pool.get('ir.model')

        models = [name for name, klass in pool.iterobject()
            if issubclass(klass, MarketingAutomationMixin)]
        models = Model.search([
                ('model', 'in', models),
                ])
        return [(m.model, m.name) for m in models]

    @classmethod
    def get_record_count(cls, scenarios, names):
        pool = Pool()
        Record = pool.get('marketing.automation.record')
        record = Record.__table__()
        cursor = Transaction().connection.cursor()

        drafts = []
        others = []
        for scenario in scenarios:
            if scenario.state == 'draft':
                drafts.append(scenario)
            else:
                others.append(scenario)

        count = {name: dict.fromkeys(map(int, scenarios), 0) for name in names}
        for sub in grouped_slice(others):
            cursor.execute(*record.select(
                    record.scenario,
                    Count(Literal('*')),
                    Count(Literal('*'), filter_=record.blocked),
                    where=reduce_ids(record.scenario, sub),
                    group_by=record.scenario))
            for id_, all_, blocked in cursor:
                if 'record_count' in count:
                    count['record_count'][id_] = all_
                if 'record_count_blocked' in count:
                    count['record_count_blocked'][id_] = blocked
        for scenario in drafts:
            Model = pool.get(scenario.model)
            domain = PYSONDecoder({}).decode(scenario.domain)
            count['record_count'][scenario.id] = Model.search(
                domain, count=True)
        return count

    @classmethod
    def validate(cls, scenarios):
        super().validate(scenarios)
        cls.check_domain(scenarios)

    @classmethod
    def check_domain(cls, scenarios):
        for scenario in scenarios:
            try:
                value = PYSONDecoder({}).decode(scenario.domain)
                fields.domain_validate(value)
            except Exception as exception:
                raise DomainError(
                    gettext('marketing_automation.msg_scenario_invalid_domain',
                        scenario=scenario.rec_name,
                        exception=exception)) from exception

    @classmethod
    @ModelView.button
    @Workflow.transition('draft')
    def draft(cls, scenarios):
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition('running')
    def run(cls, scenarios):
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition('stopped')
    def stop(cls, scenarios):
        pass

    @classmethod
    def trigger(cls, scenarios=None):
        pool = Pool()
        Record = pool.get('marketing.automation.record')
        RecordActivity = pool.get('marketing.automation.record.activity')

        if scenarios is None:
            scenarios = cls.search([
                    ('state', '=', 'running'),
                    ])

        for scenario in scenarios:
            Model = pool.get(scenario.model)
            sql_int = scenario.__class__.id.sql_type().base
            record = Record.__table__()
            cursor = Transaction().connection.cursor()
            domain = PYSONDecoder({}).decode(scenario.domain)
            cursor.execute(*(
                    Model.search(domain, query=True, order=[])
                    - record.select(
                        Substring(
                            record.record,
                            Position(',', record.record) + Literal(1)
                            ).cast(sql_int),
                        where=record.scenario == scenario.id)))

            records = []
            for id_, in cursor.fetchall():
                records.append(
                    Record(scenario=scenario, record=Model(id_)))

            if not records:
                continue
            Record.save(records)
            record_activities = []
            for record in records:
                for activity in scenario.activities:
                    if (activity.condition
                            and not record.eval(activity.condition)):
                        continue
                    record_activities.append(
                        RecordActivity.get(record, activity))
            RecordActivity.save(record_activities)


class Activity(ModelSQL, ModelView):
    "Marketing Activity"
    __name__ = 'marketing.automation.activity'

    name = fields.Char("Name", required=True)
    parent = fields.Reference(
        "Parent", [
            ('marketing.automation.scenario', "Scenario"),
            ('marketing.automation.activity', "Activity"),
            ],
        required=True)
    children = fields.One2Many(
        'marketing.automation.activity', 'parent', "Children")
    parent_action = fields.Function(
        fields.Selection('get_parent_actions', "Parent Action"),
        'on_change_with_parent_action')

    event = fields.Selection([
            (None, ""),
            ('email_opened', "E-Mail Opened"),
            ('email_clicked', "E-Mail Clicked"),
            ], "Event")  # domain set by _parent_action_events
    negative = fields.Boolean("Negative",
        states={
            'invisible': ~Eval('event'),
            },
        depends=['event'],
        help="Check to execute the activity "
        "if the event has not happened by the end of the delay.")
    on = fields.Function(fields.Selection([
                (None, ""),
                ('email_opened', "E-Mail Opened"),
                ('email_opened_not', "E-Mail Not Opened"),
                ('email_clicked', "E-Mail Clicked"),
                ('email_clicked_not', "E-Mail Not Clicked"),
                ], "On"),  # domain set by _parent_action_events
        'get_on', setter='set_on')
    condition = fields.Char("Condition",
        help="The PYSON statement that the record must match "
        "in order to execute the activity.\n"
        'The record is represented by "self"')

    delay = fields.TimeDelta(
        "Delay",
        states={
            'required': Eval('negative', False),
            },
        depends=['negative'],
        help="After how much time the action should be executed.")

    action = fields.Selection([
            (None, ''),
            ('send_email', "Send E-Mail"),
            ], "Action")

    # Send E-mail
    email_from = fields.Char("From",
        states={
            'invisible': Eval('action') != 'send_email',
            },
        depends=['action'],
        help="Leave empty to use the value defined in the configuration file.")
    email_title = fields.Char(
        "E-Mail Title",
        translate=True,
        states={
            'invisible': Eval('action') != 'send_email',
            'required': Eval('action') == 'send_email',
            },
        depends=['action'])
    email_template = fields.Text(
        "E-Mail Template",
        translate=True,
        states={
            'invisible': Eval('action') != 'send_email',
            'required': Eval('action') == 'send_email',
            },
        depends=['action'],
        help="The HTML content of the E-mail.\n"
        "The Genshi syntax can be used "
        "with 'record' in the evaluation context.")

    record_count = fields.Function(
        fields.Integer("Records"), 'get_record_count')
    email_opened = fields.Function(
        fields.Integer(
            "E-Mails Opened",
            states={
                'invisible': Eval('action') != 'send_email',
                },
            depends=['action']), 'get_record_count')
    email_clicked = fields.Function(
        fields.Integer(
            "E-Mails Clicked",
            states={
                'invisible': Eval('action') != 'send_email',
                },
            depends=['action']), 'get_record_count')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        for name in ['event', 'on']:
            field = getattr(cls, name)
            domain = [(name, '=', None)]
            for parent_action, events in cls._parent_action_events().items():
                if name == 'on':
                    events += [e + '_not' for e in events]
                domain = If(Eval('parent_action') == parent_action,
                    [(name, 'in', events + [None])],
                    domain)
            field.domain = [domain]
            field.depends = ['parent_action']

    @classmethod
    def view_attributes(cls):
        return [
            ('//group[@id="email"]', 'states', {
                    'invisible': Eval('action') != 'send_email',
                    }),
            ]

    @classmethod
    def get_parent_actions(cls):
        return cls.fields_get(['action'])['action']['selection']

    @fields.depends('parent')
    def on_change_with_parent_action(self, name=None):
        if isinstance(self.parent, self.__class__):
            return self.parent.action
        return None

    @classmethod
    def _parent_action_events(cls):
        "Return dictionary to pair parent action and valid events"
        return {
            'send_email': ['email_opened', 'email_clicked'],
            }

    def get_on(self, name):
        value = self.event
        if self.negative and value:
            value += '_not'
        return value

    @fields.depends('on', 'event', 'negative')
    def on_change_on(self):
        if not self.on:
            self.negative = False
            self.event = None
        else:
            self.negative = self.on.endswith('_not')
            self.event = self.on[:-len('_not')] if self.negative else self.on

    @classmethod
    def set_on(cls, activities, name, value):
        if not value:
            negative = False
            event = None
        else:
            negative = value.endswith('_not')
            event = value[:-len('_not')] if negative else value
        cls.write(activities, {
                'event': event,
                'negative': negative,
                })

    @classmethod
    def get_record_count(cls, activities, names):
        pool = Pool()
        RecordActivity = pool.get('marketing.automation.record.activity')
        record_activity = RecordActivity.__table__()
        cursor = Transaction().connection.cursor()

        count = {name: dict.fromkeys(map(int, activities), 0)
            for name in names}
        for sub in grouped_slice(activities):
            cursor.execute(*record_activity.select(
                    record_activity.activity,
                    Count(Literal('*'),
                        filter_=record_activity.state == 'done'),
                    Count(Literal('*'), filter_=record_activity.email_opened),
                    Count(Literal('*'), filter_=record_activity.email_clicked),
                    where=reduce_ids(record_activity.activity, sub),
                    group_by=record_activity.activity))
            for id_, all_, email_opened, email_clicked in cursor:
                if 'record_count' in count:
                    count['record_count'][id_] = all_
                if 'email_opened' in count:
                    count['email_opened'][id_] = email_opened
                if 'email_clicked' in count:
                    count['email_clicked'][id_] = email_clicked
        return count

    @classmethod
    def validate(cls, activities):
        super().validate(activities)
        for activity in activities:
            activity.check_condition()
            activity.check_email_template()

    def check_condition(self):
        if not self.condition:
            return
        try:
            PYSONDecoder(noeval=True).decode(self.condition)
        except Exception as exception:
            raise ConditionError(
                gettext('marketing_automation.msg_activity_invalid_condition',
                    condition=self.condition,
                    activity=self.rec_name,
                    exception=exception)) from exception

    def check_email_template(self):
        if not self.email_template:
            return
        try:
            MarkupTemplate(self.email_template)
        except Exception as exception:
            raise TemplateError(
                gettext('marketing_automation'
                    '.msg_activity_invalid_email_template',
                    activity=self.rec_name,
                    exception=exception)) from exception

    def execute(self, activity, **kwargs):
        pool = Pool()
        RecordActivity = pool.get('marketing.automation.record.activity')
        record = activity.record

        # XXX: use domain
        if self.condition and not record.eval(self.condition):
            return

        if self.action:
            getattr(self, 'execute_' + self.action)(activity, **kwargs)
        RecordActivity.save([
                RecordActivity.get(record, child)
                for child in self.children])

    def _email_recipient(self, record):
        pool = Pool()
        try:
            Party = pool.get('party.party')
        except KeyError:
            Party = None
        try:
            Sale = pool.get('sale.sale')
        except KeyError:
            Sale = None

        def get_party_email(party):
            contact = party.contact_mechanism_get('email')
            if contact and contact.email:
                return _formataddr(
                    contact.name or party.rec_name,
                    contact.email)
            return None

        if Party and isinstance(record, Party):
            return get_party_email(record)
        elif Sale and isinstance(record, Sale):
            return get_party_email(record.party)

    def execute_send_email(
            self, record_activity, smtpd_datamanager=None, **kwargs):
        pool = Pool()
        WebShortener = pool.get('web.shortened_url')
        record = record_activity.record

        with Transaction().set_context(language=record.language):
            record = record.__class__(record.id)
            translated = self.__class__(self.id)

        to = self._email_recipient(record.record)
        if not to:
            return

        def unsubscribe(redirect):
            parts = urlsplit(urljoin(
                    URL_BASE, quote('/m/%(database)s/unsubscribe' % {
                            'database': Base64Converter(None).to_url(
                                Transaction().database.name).decode('utf-8'),
                            })))
            query = parse_qsl(parts.query)
            query.append(('r', record.uuid))
            if redirect:
                query.append(('next', redirect))
            parts = list(parts)
            parts[3] = urlencode(query)
            return urlunsplit(parts)

        def short(url, event):
            url = WebShortener(
                record=record_activity,
                method='marketing.automation.record.activity|%s' % event,
                redirect_url=url)
            url.save()
            return url.shortened_url

        def convert_href(stream):
            for kind, data, pos in stream:
                if kind is START:
                    tag, attrs = data
                    if tag == 'a':
                        href = attrs.get('href')
                        attrs -= 'href'
                        if href.startswith('unsubscribe'):
                            href = unsubscribe(href[len('unsubscribe|'):])
                        else:
                            href = short(href, 'on_email_clicked')
                        attrs |= [(QName('href'), href)]
                        data = tag, attrs
                elif kind is END and data == 'body':
                    yield START, (QName('img'), Attrs([
                                (QName('src'), short(
                                        URL_OPEN, 'on_email_opened')),
                                (QName('height'), '1'),
                                (QName('width'), '1'),
                                ])), pos
                    yield END, QName('img'), pos
                yield kind, data, pos

        template = MarkupTemplate(translated.email_template)
        content = (template
            .generate(record=record.record)
            .filter(convert_href)
            .render())

        msg = MIMEMultipart('alternative')
        msg['From'] = self.email_from or config.get('email', 'from')
        msg['To'] = to
        msg['Subject'] = Header(translated.email_title, 'utf-8')
        if html2text:
            converter = html2text.HTML2Text()
            part = MIMEText(
                converter.handle(content), 'plain', _charset='utf-8')
            msg.attach(part)
        part = MIMEText(content, 'html', _charset='utf-8')
        msg.attach(part)

        to_addrs = [a for _, a in getaddresses([to])]
        if to_addrs:
            sendmail_transactional(
                self.email_from, to_addrs, msg, datamanager=smtpd_datamanager)


class Record(ModelSQL, ModelView):
    "Marketing Record"
    __name__ = 'marketing.automation.record'

    scenario = fields.Many2One(
        'marketing.automation.scenario', "Scenario",
        required=True, ondelete='CASCADE')
    record = fields.Reference(
        "Record", selection='get_models', required=True)
    blocked = fields.Boolean("Blocked")
    uuid = fields.Char("UUID", readonly=True)

    @classmethod
    def __setup__(cls):
        super().__setup__()

        t = cls.__table__()
        cls._sql_constraints = [
            ('scenario_record_unique', Unique(t, t.scenario, t.record),
                'marketing_automation.msg_record_scenario_unique'),
            ('uuid_unique', Unique(t, t.uuid),
                'marketing_automation.msg_record_uuid_unique'),
            ]

    @classmethod
    def default_uuid(cls):
        return uuid.uuid4().hex

    @classmethod
    def default_blocked(cls):
        return False

    @fields.depends('scenario')
    def get_models(self):
        pool = Pool()
        Model = pool.get('ir.model')

        if not self.scenario:
            return [('', '')]

        model, = Model.search([
                ('model', '=', self.scenario.model),
                ])
        return [(model.model, model.name)]

    def eval(self, expression):
        env = {}
        env['current_date'] = datetime.datetime.today()
        env['time'] = time
        env['context'] = Transaction().context
        env['self'] = EvalEnvironment(self.record, self.record.__class__)
        return PYSONDecoder(env).decode(expression)

    @property
    def language(self):
        pool = Pool()
        try:
            Party = pool.get('party.party')
        except KeyError:
            Party = None
        try:
            Sale = pool.get('sale.sale')
        except KeyError:
            Sale = None

        if Party and isinstance(self.record, Party):
            if self.record.lang:
                return self.record.lang.code
        elif Sale and isinstance(self.record, Sale):
            if self.record.party.lang:
                return self.record.party.lang.code

    @dualmethod
    def block(cls, records):
        cls.write(records, {'blocked': True})

    def get_rec_name(self, name):
        return self.record.rec_name

    @classmethod
    def create(cls, vlist):
        vlist = [v.copy() for v in vlist]
        for values in vlist:
            # Ensure to get a different uuid for each record
            # default methods are called only once
            values.setdefault('uuid', cls.default_uuid())
        return super().create(vlist)


class RecordActivity(Workflow, ModelSQL, ModelView):
    "Marketing Record Activity"
    __name__ = 'marketing.automation.record.activity'

    record = fields.Many2One(
        'marketing.automation.record', "Record",
        required=True, ondelete='CASCADE')
    activity = fields.Many2One(
        'marketing.automation.activity', "Activity",
        required=True, ondelete='CASCADE')
    activity_action = fields.Function(
        fields.Selection('get_activity_actions', "Activity Action"),
        'on_change_with_activity_action')
    at = fields.DateTime(
        "At",
        states={
            'readonly': Eval('state') != 'waiting',
            },
        depends=['state'])
    email_opened = fields.Boolean(
        "E-Mail Opened",
        states={
            'invisible': Eval('activity_action') != 'send_email',
            },
        depends=['activity_action'])
    email_clicked = fields.Boolean(
        "E-Mail Clicked",
        states={
            'invisible': Eval('activity_action') != 'send_email',
            },
        depends=['activity_action'])
    state = fields.Selection([
            ('waiting', "Waiting"),
            ('done', "Done"),
            ('cancelled', "Cancelled"),
            ], "State", required=True, readonly=True)

    @classmethod
    def __setup__(cls):
        super().__setup__()
        t = cls.__table__()
        cls._sql_constraints = [
            ('activity_record_unique', Unique(t, t.activity, t.record),
                'marketing_automation.msg_activity_record_unique'),
            ]
        cls._transitions |= set((
                ('waiting', 'done'),
                ('waiting', 'cancelled'),
                ))
        cls._buttons.update(
            on_email_opened={
                'invisible': ((Eval('state') != 'waiting')
                    | (Eval('activity_action') != 'send_email')
                    | Eval('email_opened', False)),
                'depends': ['state', 'activity_action', 'email_opened'],
                },
            on_email_clicked={
                'invisible': ((Eval('state') != 'waiting')
                    | (Eval('activity_action') != 'send_email')
                    | Eval('email_clicked', False)),
                'depends': ['state', 'activity_action', 'email_clicked'],
                },
            )

    @classmethod
    def default_email_opened(cls):
        return False

    @classmethod
    def default_email_clicked(cls):
        return False

    @classmethod
    def default_state(cls):
        return 'waiting'

    @classmethod
    def get_activity_actions(cls):
        pool = Pool()
        Activity = pool.get('marketing.automation.activity')
        return Activity.fields_get(['action'])['action']['selection']

    @fields.depends('activity')
    def on_change_with_activity_action(self, name=None):
        if self.activity:
            return self.activity.action

    @classmethod
    def get(cls, record, activity):
        record_activity = cls(activity=activity, record=record)
        if activity.negative or not activity.event:
            record_activity.set_delay()
        return record_activity

    def set_delay(self):
        now = datetime.datetime.now()
        self.at = now
        if self.activity.delay is not None:
            self.at += self.activity.delay

    @classmethod
    def process(cls):
        now = datetime.datetime.now()
        activities = cls.search([
                ('state', '=', 'waiting'),
                ('at', '<=', now),
                ('record.blocked', '!=', True),
                ])
        cls.do(activities)

    @classmethod
    @ModelView.button
    def on_email_opened(cls, record_activities):
        for record_activity in record_activities:
            record_activity._on_event('email_opened')
        cls.save(record_activities)

    @classmethod
    @ModelView.button
    def on_email_clicked(cls, record_activities):
        for record_activity in record_activities:
            record_activity._on_event('email_clicked')
        cls.save(record_activities)

    def _on_event(self, event):
        cls = self.__class__
        record_activities = cls.search([
                ('record', '=', str(self.record)),
                ('activity', 'in', [
                        c.id for c in self.activity.children
                        if c.event == event and not c.negative]),
                ('state', '=', 'waiting'),
                ])
        cls._cancel_opposite(record_activities)
        for record_activity in record_activities:
            record_activity.set_delay()
        cls.save(record_activities)
        setattr(self, event, True)

    @classmethod
    def _cancel_opposite(cls, record_activities):
        to_cancel = set()
        for record_activity in record_activities:
            records = cls.search([
                    ('record', '=', record_activity.record),
                    ('state', '=', 'waiting'),
                    ('activity.parent',
                        '=', str(record_activity.activity.parent)),
                    ('activity.event', '=', record_activity.activity.event),
                    ('activity.negative',
                        '=', not record_activity.activity.negative),
                    ])
            to_cancel.update(records)
        cls.cancel(to_cancel)

    @classmethod
    @Workflow.transition('done')
    def do(cls, record_activities, **kwargs):
        cls._cancel_opposite(record_activities)

        now = datetime.datetime.now()
        smtpd_datamanager = Transaction().join(SMTPDataManager())
        for record_activity in record_activities:
            record_activity.activity.execute(
                record_activity, smtpd_datamanager=smtpd_datamanager, **kwargs)
            record_activity.at = now
            record_activity.state = 'done'
        cls.save(record_activities)

    @classmethod
    @Workflow.transition('cancelled')
    def cancel(cls, record_activities):
        now = datetime.datetime.now()
        cls.write(record_activities, {
                'at': now,
                'state': 'cancelled',
                })


class Unsubscribe(Report):
    "Marketing Automation Unsubscribe"
    __name__ = 'marketing.automation.unsubscribe'
