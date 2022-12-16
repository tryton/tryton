#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from __future__ import with_statement
from string import Template
import datetime
import time
from trytond.model import ModelView, ModelSQL, fields
from trytond.tools import datetime_strftime
from trytond.pyson import In, Eval, Not
from trytond.transaction import Transaction


class SequenceType(ModelSQL, ModelView):
    "Sequence type"
    _name = 'ir.sequence.type'
    _description = __doc__
    name = fields.Char('Sequence Name', required=True, translate=True)
    code = fields.Char('Sequence Code', required=True)

SequenceType()


class Sequence(ModelSQL, ModelView):
    "Sequence"
    _name = 'ir.sequence'
    _description = __doc__
    name = fields.Char('Sequence Name', required=True, translate=True)
    code = fields.Selection('code_get', 'Sequence Code', required=True,
            states={
                'readonly': In('code', Eval('context', {})),
            })
    active = fields.Boolean('Active')
    prefix = fields.Char('Prefix')
    suffix = fields.Char('Suffix')
    type = fields.Selection([
        ('incremental', 'Incremental'),
        ('decimal timestamp', 'Decimal Timestamp'),
        ('hexadecimal timestamp', 'Hexadecimal Timestamp'),
        ], 'Type')
    number_next = fields.Integer('Next Number',
            states={
                'invisible': Not(In(Eval('type'), ['incremental'])),
            }, depends=['type'])
    number_increment = fields.Integer('Increment Number',
            states={
                'invisible': Not(In(Eval('type'), ['incremental'])),
            }, depends=['type'])
    padding = fields.Integer('Number padding',
            states={
                'invisible': Not(In(Eval('type'), ['incremental'])),
            }, depends=['type'])
    timestamp_rounding = fields.Integer('Timestamp Rounding', required=True,
            states={
                'invisible': Not(In(Eval('type'),
                    ['decimal timestamp', 'hexadecimal timestamp'])),
            }, depends=['type'])
    timestamp_offset = fields.Float('Timestamp Offset',
            states={
                'invisible': Not(In(Eval('type'),
                    ['decimal timestamp', 'hexadecimal timestamp'])),
            }, depends=['type'])
    last_timestamp = fields.Integer('Last Timestamp',
            states={
                'invisible': Not(In(Eval('type'),
                    ['decimal timestamp', 'hexadecimal timestamp'])),
            }, depends=['type'])

    def __init__(self):
        super(Sequence, self).__init__()
        self._constraints += [
            ('check_prefix_suffix', 'invalid_prefix_suffix'),
            ('check_last_timestamp', 'future_last_timestamp'),
        ]
        self._error_messages.update({
            'missing': 'Missing sequence!',
            'invalid_prefix_suffix': 'Invalid prefix/suffix!',
            'future_last_timestamp': 'Last Timestamp could not be in future!',
            })

    def default_active(self):
        return True

    def default_type(self):
        return 'incremental'

    def default_number_increment(self):
        return 1

    def default_number_next(self):
        return 1

    def default_padding(self):
        return 0

    def default_timestamp_rounding(self):
        return 1.0

    def default_timestamp_offset(self):
        return 946681200.0 # Offset for 2000-01-01

    def default_last_timestamp(self):
        return 0.0

    def default_code(self):
        return Transaction().context.get('code', False)

    def code_get(self):
        sequence_type_obj = self.pool.get('ir.sequence.type')
        sequence_type_ids = sequence_type_obj.search([])
        sequence_types = sequence_type_obj.browse(sequence_type_ids)
        return [(x.code, x.name) for x in sequence_types]

    def check_prefix_suffix(self, ids):
        "Check prefix and suffix"

        for sequence in self.browse(ids):
            try:
                self._process(sequence.prefix)
                self._process(sequence.suffix)
            except Exception:
                return False
        return True

    def check_last_timestamp(self, ids):
        "Check last_timestamp"

        for sequence in self.browse(ids):
            next_timestamp = self._timestamp(sequence)
            if sequence.last_timestamp > next_timestamp:
                return False
        return True

    def _process(self, string, date=None):
        date_obj = self.pool.get('ir.date')
        if not date:
            date = date_obj.today()
        year = datetime_strftime(date, '%Y')
        month = datetime_strftime(date, '%m')
        day = datetime_strftime(date, '%d')
        return Template(string or '').substitute(
                year=year,
                month=month,
                day=day,
                )

    def _timestamp(self, sequence):
        return int((time.time() - sequence.timestamp_offset)
                / sequence.timestamp_rounding)

    def _get_sequence(self, sequence):
        if sequence.type == 'incremental':
            #Pre-fetch number_next
            number_next = sequence.number_next or 0

            with Transaction().set_user(0):
                self.write(sequence.id, {
                        'number_next': number_next + sequence.number_increment,
                        })
            return '%%0%sd' % sequence.padding % number_next
        elif sequence.type in ('decimal timestamp', 'hexadecimal timestamp'):
            timestamp = sequence.last_timestamp
            while timestamp == sequence.last_timestamp:
                timestamp = self._timestamp(sequence)
            with Transaction().set_user(0):
                self.write(sequence.id, {
                    'last_timestamp': timestamp,
                    })
            if sequence.type == 'decimal timestamp':
                return '%d' % timestamp
            else:
                return hex(timestamp)[2:].upper()
        return ''


    def get_id(self, domain):
        '''
        Return sequence value for the domain

        :param domain: a domain or a sequence id
        :return: the sequence value
        '''
        if isinstance(domain, (int, long)):
            domain = [('id', '=', domain)]

        # bypass rules on sequences
        with Transaction().set_context(user=False):
            with Transaction().set_user(0):
                sequence_ids = self.search(domain, limit=1)
            date = Transaction().context.get('date')
            if sequence_ids:
                with Transaction().set_user(0):
                    sequence = self.browse(sequence_ids[0])
                return '%s%s%s' % (
                        self._process(sequence.prefix, date=date),
                        self._get_sequence(sequence),
                        self._process(sequence.suffix, date=date),
                        )
        self.raise_user_error('missing')

    def get(self, code):
        return self.get_id([('code', '=', code)])

Sequence()


class SequenceStrict(Sequence):
    "Sequence Strict"
    _name = 'ir.sequence.strict'
    _description = __doc__

    def get_id(self, clause):
        Transaction().cursor.lock(self._table)
        return super(SequenceStrict, self).get_id(clause)

SequenceStrict()
