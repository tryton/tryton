# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
import logging
import time
import uuid
from collections import defaultdict
from email.message import EmailMessage
from functools import partial
from urllib.parse import (
    parse_qsl, quote, urlencode, urljoin, urlsplit, urlunsplit)

from dateutil.relativedelta import relativedelta

try:
    import html2text
except ImportError:
    html2text = None

from genshi.core import END, START, Attrs, QName
from genshi.template import MarkupTemplate
from genshi.template import TemplateError as GenshiTemplateError
from genshi.template import TextTemplate
from sql import Literal
from sql.aggregate import Count

from trytond.config import config
from trytond.i18n import gettext
from trytond.model import (
    EvalEnvironment, Index, ModelSQL, ModelView, Unique, Workflow, dualmethod,
    fields)
from trytond.pool import Pool
from trytond.pyson import Eval, If, PYSONDecoder, TimeDelta
from trytond.report import Report
from trytond.sendmail import SMTPDataManager, send_message_transactional
from trytond.tools import grouped_slice, pairwise_longest, reduce_ids
from trytond.tools.chart import sparkline
from trytond.tools.email_ import format_address, has_rcpt, set_from_header
from trytond.transaction import Transaction
from trytond.url import http_host
from trytond.wsgi import Base64Converter

from .exceptions import ConditionError, DomainError, TemplateError
from .mixin import MarketingAutomationMixin

USE_SSL = bool(config.get('ssl', 'certificate'))
URL_BASE = config.get('marketing', 'automation_base', default=http_host())
URL_OPEN = urljoin(URL_BASE, '/m/empty.gif')
logger = logging.getLogger(__name__)


def trend_mixin(model_name, field_name):
    class TrendMixin:
        __slots__ = ()

        def get_trend(self, name):
            name = name[:-len('_trend')]
            return sparkline([
                    getattr(ts, name, 0) or 0 for ts in self.trends])

        @property
        def trends(self):
            pool = Pool()
            Model = pool.get(model_name)
            Date = pool.get('ir.date')

            delta = self._trend_period_delta()
            date = Date.today()
            date -= 10 * delta

            records = Model.search([
                    ('date', '>=', date),
                    (field_name, '=', self.id),
                    ],
                order=[('date', 'ASC')])
            for record, next_record in pairwise_longest(records):
                yield record
                if delta and next_record:
                    date = record.date + delta
                    while date < next_record.date:
                        yield None
                        date += delta

        @classmethod
        def _trend_period_delta(cls):
            context = Transaction().context
            return {
                'year': relativedelta(years=1),
                'month': relativedelta(months=1),
                'day': relativedelta(days=1),
                }.get(context.get('period', 'month'))
    return TrendMixin


class Scenario(
        trend_mixin('marketing.automation.reporting.scenario', 'scenario'),
        Workflow, ModelSQL, ModelView):
    "Marketing Scenario"
    __name__ = 'marketing.automation.scenario'

    name = fields.Char("Name", translate=True)
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
    block_rate = fields.Function(
        fields.Float("Block Rate"),
        'get_rate')
    block_rate_trend = fields.Function(
        fields.Char("Block Rate Trend"),
        'get_trend')
    unsubscribable = fields.Boolean(
        "Unsubscribable",
        help="If checked parties are also unsubscribed from the scenario.")
    state = fields.Selection([
            ('draft', "Draft"),
            ('running', "Running"),
            ('stopped', "Stopped"),
            ], "State", required=True, readonly=True, sort=False)

    @classmethod
    def __setup__(cls):
        super().__setup__()
        t = cls.__table__()
        cls._sql_indexes.add(
            Index(
                t,
                (t.state, Index.Equality(cardinality='low')),
                where=t.state.in_(['draft', 'running'])))
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
    def default_unsubscribable(cls):
        return False

    @classmethod
    def get_models(cls):
        pool = Pool()
        Model = pool.get('ir.model')
        get_name = Model.get_name
        models = (name for name, klass in pool.iterobject()
            if issubclass(klass, MarketingAutomationMixin))
        return [(m, get_name(m)) for m in models]

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

        count = {name: defaultdict(int) for name in names}
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
            try:
                count['record_count'][scenario.id] = Model.search(
                    domain, count=True)
            except Exception:
                pass
        return count

    @classmethod
    def get_rate(cls, scenarios, names):
        rates = {name: defaultdict(float) for name in names}
        for scenario in scenarios:
            if 'block_rate' in names and scenario.record_count:
                rates['block_rate'][scenario.id] = round(
                    scenario.record_count_blocked / scenario.record_count, 2)
        return rates

    @classmethod
    def validate_fields(cls, scenarios, field_names):
        super().validate_fields(scenarios, field_names)
        cls.check_domain(scenarios)

    @classmethod
    def check_domain(cls, scenarios, field_names=None):
        pool = Pool()
        if field_names and not (field_names & {'model', 'domain'}):
            return
        for scenario in scenarios:
            Model = pool.get(scenario.model)
            try:
                value = PYSONDecoder({}).decode(scenario.domain)
                fields.domain_validate(value)
                Model.search(value, limit=0)
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
            record = Record.__table__()
            cursor = Transaction().connection.cursor()
            domain = PYSONDecoder({}).decode(scenario.domain)
            domain = [
                domain,
                ('marketing_party.marketing_scenario_unsubscribed',
                    'not where', [('id', '=', scenario.id)]),
                ]
            try:
                query = Model.search(domain, query=True, order=[])
            except Exception:
                logger.error(
                    "Error when triggering scenario %d", scenario.id,
                    exc_info=True)
                continue
            cursor.execute(*(
                    query - record.select(
                        Record.record.sql_id(record.record, Model),
                        where=record.scenario == scenario.id)))

            records = []
            for id_, in cursor:
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


class Activity(
        trend_mixin('marketing.automation.reporting.activity', 'activity'),
        ModelSQL, ModelView):
    "Marketing Activity"
    __name__ = 'marketing.automation.activity'

    name = fields.Char("Name", translate=True, required=True)
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
            ('email_opened', "Email Opened"),
            ('email_clicked', "Email Clicked"),
            ], "Event")  # domain set by _parent_action_events
    negative = fields.Boolean("Negative",
        states={
            'invisible': ~Eval('event'),
            },
        help="Check to execute the activity "
        "if the event has not happened by the end of the delay.")
    on = fields.Function(fields.Selection([
                (None, ""),
                ('email_opened', "Email Opened"),
                ('email_opened_not', "Email Not Opened"),
                ('email_clicked', "Email Clicked"),
                ('email_clicked_not', "Email Not Clicked"),
                ], "On"),  # domain set by _parent_action_events
        'get_on', setter='set_on')
    condition = fields.Char("Condition",
        help="The PYSON statement that the record must match "
        "in order to execute the activity.\n"
        'The record is represented by "self".')

    delay = fields.TimeDelta(
        "Delay",
        domain=['OR',
            ('delay', '=', None),
            ('delay', '>=', TimeDelta()),
            ],
        states={
            'required': Eval('negative', False),
            },
        help="After how much time the action should be executed.")

    action = fields.Selection([
            (None, ''),
            ('send_email', "Send email"),
            ], "Action")

    # Send email
    email_from = fields.Char("From", translate=True,
        states={
            'invisible': Eval('action') != 'send_email',
            },
        help="Leave empty to use the value defined in the configuration file.")
    email_title = fields.Char(
        "Email Title",
        translate=True,
        states={
            'invisible': Eval('action') != 'send_email',
            'required': Eval('action') == 'send_email',
            },
        help="The subject of the email.\n"
        "The Genshi syntax can be used "
        "with 'record' in the evaluation context.")
    email_template = fields.Text(
        "Email Template",
        translate=True,
        states={
            'invisible': Eval('action') != 'send_email',
            'required': Eval('action') == 'send_email',
            },
        help="The HTML content of the email.\n"
        "The Genshi syntax can be used "
        "with 'record' in the evaluation context.")

    record_count = fields.Function(
        fields.Integer("Records"), 'get_record_count')
    email_opened = fields.Function(
        fields.Integer(
            "Emails Opened",
            states={
                'invisible': Eval('action') != 'send_email',
                }), 'get_record_count')
    email_clicked = fields.Function(
        fields.Integer(
            "Emails Clicked",
            states={
                'invisible': Eval('action') != 'send_email',
                }),
        'get_record_count')

    email_open_rate = fields.Function(
        fields.Float(
            "Email Open Rate",
            states={
                'invisible': Eval('action') != 'send_email',
                }),
        'get_rate')
    email_open_rate_trend = fields.Function(
        fields.Char(
            "Email Open Rate Trend",
            states={
                'invisible': Eval('action') != 'send_email',
                }),
        'get_trend')
    email_click_rate = fields.Function(
        fields.Float(
            "Email Click Rate",
            states={
                'invisible': Eval('action') != 'send_email',
                }),
        'get_rate')
    email_click_rate_trend = fields.Function(
        fields.Char(
            "Email Click Rate Trend",
            states={
                'invisible': Eval('action') != 'send_email',
                }),
        'get_trend')
    email_click_through_rate = fields.Function(
        fields.Float(
            "Email Click-Through Rate",
            states={
                'invisible': Eval('action') != 'send_email',
                }),
        'get_rate')
    email_click_through_rate_trend = fields.Function(
        fields.Char(
            "Email Click-Through Rate Trend",
            states={
                'invisible': Eval('action') != 'send_email',
                }),
        'get_trend')

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
            field.depends.add('parent_action')

    @classmethod
    def view_attributes(cls):
        return super().view_attributes() + [
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

        count = {name: defaultdict(int) for name in names}
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
    def get_rate(cls, activities, names):
        rates = {name: defaultdict(float) for name in names}
        for activity in activities:
            if 'email_open_rate' in names and activity.record_count:
                rates['email_open_rate'][activity.id] = round(
                    activity.email_opened / activity.record_count, 2)
            if 'email_click_rate' in names and activity.record_count:
                rates['email_click_rate'][activity.id] = round(
                    activity.email_clicked / activity.record_count, 2)
            if 'email_click_through_rate' in names and activity.email_opened:
                rates['email_click_through_rate'][activity.id] = round(
                    activity.email_clicked / activity.email_opened, 2)
        return rates

    @classmethod
    def validate_fields(cls, activities, fields_names):
        super().validate_fields(activities, fields_names)
        for activity in activities:
            activity.check_condition(fields_names)
            activity.check_email_title(fields_names)
            activity.check_email_template(fields_names)

    def check_condition(self, fields_names=None):
        if fields_names and 'condition' not in fields_names:
            return
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

    def check_email_template(self, fields_names=None):
        if fields_names and 'email_template' not in fields_names:
            return
        if not self.email_template:
            return
        try:
            MarkupTemplate(self.email_template)
        except GenshiTemplateError as exception:
            raise TemplateError(
                gettext('marketing_automation'
                    '.msg_activity_invalid_email_template',
                    activity=self.rec_name,
                    exception=exception)) from exception

    def check_email_title(self, fields_names=None):
        if fields_names and 'email_title' not in fields_names:
            return
        if not self.email_title:
            return
        try:
            TextTemplate(self.email_title)
        except GenshiTemplateError as exception:
            raise TemplateError(
                gettext('marketing_automation'
                    '.msg_activity_invalid_email_title',
                    activity=self.rec_name,
                    exception=exception)) from exception

    def execute(self, activity, **kwargs):
        pool = Pool()
        RecordActivity = pool.get('marketing.automation.record.activity')
        record = activity.record

        # As it is a reference, the record may have been deleted
        if not record:
            return

        # XXX: use domain
        if self.condition and not record.eval(self.condition):
            return

        if self.action:
            getattr(self, 'execute_' + self.action)(activity, **kwargs)
        RecordActivity.save([
                RecordActivity.get(record, child)
                for child in self.children])

    def _email_recipient(self, record):
        party = record.marketing_party
        contact = party.contact_mechanism_get('email')
        if contact and contact.email:
            return format_address(
                contact.email, contact.name or party.rec_name)

    def execute_send_email(
            self, record_activity, smtpd_datamanager=None, **kwargs):
        pool = Pool()
        WebShortener = pool.get('web.shortened_url')
        Email = pool.get('ir.email')
        record = record_activity.record

        with Transaction().set_context(language=record.language):
            record = record.__class__(record.id)
            translated = self.__class__(self.id)

        to = self._email_recipient(record.record)

        def unsubscribe(redirect):
            parts = urlsplit(urljoin(
                    URL_BASE, quote('/m/%(database)s/unsubscribe' % {
                            'database': Base64Converter(None).to_url(
                                Transaction().database.name),
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
                    if tag == 'a' and attrs.get('href'):
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

        context = self.email_context(record)
        context['short'] = partial(short, event='on_email_clicked')
        try:
            title = (TextTemplate(translated.email_title)
                .generate(**context)
                .render())
        except GenshiTemplateError as exception:
            raise TemplateError(
                gettext('marketing_automation'
                    '.msg_activity_invalid_email_title',
                    activity=self.rec_name,
                    exception=exception)) from exception
        try:
            template = MarkupTemplate(translated.email_template)
            content = (template
                .generate(**context)
                .filter(convert_href)
                .render())
        except GenshiTemplateError as exception:
            raise TemplateError(gettext('marketing_automation'
                    '.msg_activity_invalid_email_template',
                    activity=self.rec_name,
                    exception=exception)) from exception

        msg = self._email(translated.email_from, to, title, content)

        if has_rcpt(msg):
            send_message_transactional(msg, datamanager=smtpd_datamanager)
            email = Email.from_message(
                msg, resource=record.record,
                marketing_automation_activity=self,
                marketing_automation_record=record)
            email.save()

    def email_context(self, record):
        return {
            'record': record.record,
            'format_date': Report.format_date,
            'format_datetime': Report.format_datetime,
            'format_timedelta': Report.format_timedelta,
            'format_currency': Report.format_currency,
            'format_number': Report.format_number,
            'datetime': datetime,
            }

    def _email(self, sender, to, subject, content):
        msg = EmailMessage()
        from_ = (config.get('marketing', 'email_from')
            or config.get('email', 'from'))
        set_from_header(msg, from_, sender or from_)
        msg['To'] = to
        msg['Subject'] = subject
        if html2text:
            converter = html2text.HTML2Text()
            content_text = converter.handle(content)
            msg.add_alternative(content_text, subtype='plain')
        if msg.is_multipart():
            msg.add_alternative(content, subtype='html')
        else:
            msg.set_content(content, subtype='html')
        return msg


class Record(ModelSQL, ModelView):
    "Marketing Record"
    __name__ = 'marketing.automation.record'

    scenario = fields.Many2One(
        'marketing.automation.scenario', "Scenario",
        required=True, ondelete='CASCADE')
    record = fields.Reference(
        "Record", selection='get_models', required=True)
    blocked = fields.Boolean(
        "Blocked",
        states={
            'readonly': ~Eval('blocked', False),
            })
    uuid = fields.Char("UUID", readonly=True, strip=False)

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
        cls._buttons.update({
                'block': {
                    'invisible': Eval('blocked', False),
                    },
                })

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
        Scenario = pool.get('marketing.automation.scenario')

        if not self.scenario:
            return Scenario.get_models()

        model = self.scenario.model
        return [(model, Model.get_name(model))]

    def eval(self, expression):
        env = {}
        env['current_date'] = datetime.datetime.today()
        env['time'] = time
        env['context'] = Transaction().context
        env['self'] = EvalEnvironment(self.record, self.record.__class__)
        return PYSONDecoder(env).decode(expression)

    @property
    def language(self):
        lang = self.record.marketing_party.lang
        if lang:
            return lang.code

    @dualmethod
    @ModelView.button
    def block(cls, records):
        pool = Pool()
        Party = pool.get('party.party')

        cls.write(records, {'blocked': True})

        parties = defaultdict(set)
        for record in records:
            if record.scenario.unsubscribable:
                parties[record.record.marketing_party].add(record.scenario.id)
        if parties:
            Party.write(*sum((
                        ([p], {'marketing_scenario_unsubscribed': [
                                    ('add', s)]})
                        for p, s in parties.items()), ()))

    def get_rec_name(self, name):
        if self.record:
            return self.record.rec_name
        else:
            return '(%s)' % self.id

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
            'required': Eval('state') == 'done',
            })
    email_opened = fields.Boolean(
        "Email Opened",
        states={
            'invisible': Eval('activity_action') != 'send_email',
            })
    email_clicked = fields.Boolean(
        "Email Clicked",
        states={
            'invisible': Eval('activity_action') != 'send_email',
            })
    state = fields.Selection([
            ('waiting', "Waiting"),
            ('done', "Done"),
            ('cancelled', "Cancelled"),
            ], "State", required=True, readonly=True, sort=False)

    @classmethod
    def __setup__(cls):
        super().__setup__()
        t = cls.__table__()
        cls._sql_constraints = [
            ('activity_record_unique', Unique(t, t.activity, t.record),
                'marketing_automation.msg_activity_record_unique'),
            ]
        cls._sql_indexes.add(
            Index(
                t,
                (t.state, Index.Equality(cardinality='low')),
                where=t.state.in_(['waiting'])))
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
        transaction = Transaction()
        context = transaction.context
        now = datetime.datetime.now()
        activities = cls.search([
                ('state', '=', 'waiting'),
                ('at', '<=', now),
                ('record.blocked', '!=', True),
                ])
        with transaction.set_context(
                queue_batch=context.get('queue_batch', True)):
            cls.__queue__.do(activities)

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
                ('record', '=', self.record),
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
