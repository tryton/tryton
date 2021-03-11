# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from dateutil.rrule import MO, TU, WE, TH, FR, SA, SU
from dateutil.rrule import YEARLY, MONTHLY, WEEKLY, DAILY
from dateutil.rrule import rrule, rruleset

from trytond.model import ModelSQL, ModelView, fields
from trytond.transaction import Transaction

__all__ = ['RecurrenceRuleSet', 'RecurrenceRule']
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
    wkst = fields.Selection([
            (None, ''),
            ('0', 'Monday'),
            ('1', 'Tuesday'),
            ('2', 'Wednesday'),
            ('3', 'Thursday'),
            ('4', 'Friday'),
            ('5', 'Saturday'),
            ('6', 'Sunday'),
            ], "Week Start Day", sort=False)

    exclusive = fields.Boolean("Exclusive")

    @classmethod
    def __setup__(cls):
        super(RecurrenceRule, cls).__setup__()
        cls._error_messages.update({
                'invalid_byweekday': (
                    '"By Week Day" (%(byweekday)s) is not valid.'),
                'invalid_bymonthday': (
                    '"By Month Day" (%(bymonthday)s) is not valid.'),
                'invalid_byyearday': (
                    '"By Year Day" (%(byyearday)s) is not valid.'),
                'invalid_byweekno': (
                    '"By Week Number" (%(byweekno)s) is not valid.'),
                'invalid_bymonth': (
                    '"By Month" (%(bymonth)s) is not valid.'),
                'invalid_bysetpos': (
                    '"By Position" (%(bysetpos)s) is not valid.'),
                })

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
            'wkst': int(self.wkst) if self.wkst else None,
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
        except ValueError:
            self.raise_user_error('invalid_%s' % name, {
                    name: getattr(self, name),
                    })
