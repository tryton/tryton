# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from dateutil.rrule import MO, TU, WE, TH, FR, SA, SU
from dateutil.rrule import YEARLY, MONTHLY, WEEKLY, DAILY
from dateutil.rrule import rrule, rruleset

from trytond.i18n import gettext
from trytond.model import ModelSQL, ModelView, fields
from trytond.pool import Pool
from trytond.transaction import Transaction

from .exceptions import RecurrenceRuleValidationError

WEEKDAYS = {
    'MO': MO,
    'TU': TU,
    'WE': WE,
    'TH': TH,
    'FR': FR,
    'SA': SA,
    'SU': SU,
    }
FREQUENCIES = {
    'yearly': YEARLY,
    'monthly': MONTHLY,
    'weekly': WEEKLY,
    'daily': DAILY,
    }


class RecurrenceRuleSet(ModelSQL, ModelView):
    "Subscription Recurrence Rule Set"
    __name__ = 'sale.subscription.recurrence.rule.set'

    name = fields.Char(
        "Name", required=True, translate=True,
        help="The main identifier of the rule set.")
    rules = fields.One2Many(
        'sale.subscription.recurrence.rule', 'set_', "Rules")

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._order.insert(0, ('name', 'ASC'))

    @classmethod
    def default_rules(cls):
        if Transaction().user == 0:
            return []
        return [{}]

    def rruleset(self, dtstart):
        set_ = rruleset(**self._rruleset())
        for rule in self.rules:
            if not rule.exclusive:
                set_.rrule(rule.rrule(dtstart))
            else:
                set_.exrule(rule.rrule(dtstart))
        return set_

    def _rruleset(self):
        return {}


class RecurrenceRule(ModelSQL, ModelView):
    "Subscription Recurrence Rule"
    __name__ = 'sale.subscription.recurrence.rule'

    set_ = fields.Many2One(
        'sale.subscription.recurrence.rule.set', "Set",
        required=True, select=True,
        help="Add the rule below the set.")
    freq = fields.Selection([
            ('yearly', 'Yearly'),
            ('monthly', 'Monthly'),
            ('weekly', 'Weekly'),
            ('daily', 'Daily'),
            ], "Frequency", sort=False, required=True)
    interval = fields.Integer("Interval", required=True)
    byweekday = fields.Char(
        "By Week Day",
        help="A comma separated list of integers or weekday (MO, TU etc).")
    bymonthday = fields.Char(
        "By Month Day",
        help="A comma separated list of integers.")
    byyearday = fields.Char(
        "By Year Day",
        help="A comma separated list of integers.")
    byweekno = fields.Char(
        "By Week Number",
        help="A comma separated list of integers (ISO8601).")
    bymonth = fields.Char(
        "By Month",
        help="A comma separated list of integers.")
    bysetpos = fields.Char(
        "By Position",
        help="A comma separated list of integers.")
    week_start_day = fields.Many2One('ir.calendar.day', "Week Start Day")

    exclusive = fields.Boolean("Exclusive")

    @classmethod
    def __register__(cls, module_name):
        pool = Pool()
        Day = pool.get('ir.calendar.day')
        day = Day.__table__()
        transaction = Transaction()
        table = cls.__table__()

        super().__register__(module_name)
        table_h = cls.__table_handler__(module_name)

        # Migration from 5.0: replace wkst by week_start_day
        if table_h.column_exist('wkst'):
            cursor = transaction.connection.cursor()
            update = transaction.connection.cursor()
            cursor.execute(*day.select(day.id, day.index))
            for day_id, index in cursor:
                update.execute(*table.update(
                        [table.week_start_day], [day_id],
                        where=table.wkst == str(index)))
            table_h.drop_column('wkst')

    @classmethod
    def default_interval(cls):
        return 1

    @classmethod
    def default_exclusive(cls):
        return False

    def rrule(self, dtstart):
        return rrule(**self._rrule(dtstart))

    def _rrule(self, dtstart):
        return {
            'dtstart': dtstart,
            'freq': FREQUENCIES[self.freq],
            'interval': self.interval,
            'byweekday': self._byweekday,
            'bymonthday': self._bymonthday,
            'byyearday': self._byyearday,
            'byweekno': self._byweekno,
            'bymonth': self._bymonth,
            'bysetpos': self._bysetpos,
            'wkst': self.week_start_day.index if self.week_start_day else None,
            }

    @property
    def _byweekday(self):
        if not self.byweekday:
            return None
        byweekday = []
        for weekday in self.byweekday.split(','):
            try:
                weekday = int(weekday)
            except ValueError:
                pass
            else:
                if 0 <= weekday <= len(WEEKDAYS):
                    byweekday.append(weekday)
                    continue
                else:
                    raise ValueError('Invalid weekday')
            try:
                cls = WEEKDAYS[weekday[:2]]
            except KeyError:
                raise ValueError('Invalid weekday')
            if not weekday[2:]:
                byweekday.append(cls)
            else:
                byweekday.append(cls(int(weekday[3:-1])))
        return byweekday

    @property
    def _bymonthday(self):
        if not self.bymonthday:
            return None
        return [int(md) for md in self.bymonthday.split(',')]

    @property
    def _byyearday(self):
        if not self.byyearday:
            return None
        return [int(yd) for yd in self.byyearday.split(',')]

    @property
    def _byweekno(self):
        if not self.byweekno:
            return None
        return [int(wn) for wn in self.byweekno.split(',')]

    @property
    def _bymonth(self):
        if not self.bymonth:
            return None
        return [int(m) for m in self.bymonth.split(',')]

    @property
    def _bysetpos(self):
        if not self.bysetpos:
            return None
        positions = []
        for setpos in self.bysetpos.split(','):
            setpos = int(setpos)
            if -366 <= setpos <= 366:
                positions.append(setpos)
            else:
                raise ValueError('Invalid setpos')
        return positions

    def pre_validate(self):
        for name in ['byweekday', 'bymonthday', 'byyearday', 'byweekno',
                'bymonth', 'bysetpos']:
            self.check_by(name)

    def check_by(self, name):
        try:
            getattr(self, '_%s' % name)
        except ValueError as exception:
            raise RecurrenceRuleValidationError(
                gettext('sale_subscription.msg_recurrence_rule_invalid_by',
                    value=getattr(self, name),
                    recurrence_rule=self.rec_name,
                    exception=exception,
                    **self.__names__(name))) from exception
