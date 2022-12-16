#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from string import Template
import datetime
import time
from trytond.model import ModelView, ModelSQL, fields
from trytond.tools import datetime_strftime
from trytond.pyson import Eval
from trytond.transaction import Transaction
from trytond.pool import Pool
from trytond.config import CONFIG
from trytond.backend import TableHandler

sql_sequence = CONFIG.options['db_type'] == 'postgresql'


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
    _strict = False
    name = fields.Char('Sequence Name', required=True, translate=True)
    code = fields.Selection('code_get', 'Sequence Code', required=True,
        states={
            'readonly': Eval('context', {}).contains('code'),
            })
    active = fields.Boolean('Active')
    prefix = fields.Char('Prefix')
    suffix = fields.Char('Suffix')
    type = fields.Selection([
        ('incremental', 'Incremental'),
        ('decimal timestamp', 'Decimal Timestamp'),
        ('hexadecimal timestamp', 'Hexadecimal Timestamp'),
        ], 'Type')
    number_next_internal = fields.Integer('Next Number',
        states={
            'invisible': ~Eval('type').in_(['incremental']),
            }, depends=['type'])
    number_next = fields.Function(number_next_internal, 'get_number_next',
        'set_number_next')
    number_increment = fields.Integer('Increment Number',
        states={
            'invisible': ~Eval('type').in_(['incremental']),
            }, depends=['type'])
    padding = fields.Integer('Number padding',
        states={
            'invisible': ~Eval('type').in_(['incremental']),
            }, depends=['type'])
    timestamp_rounding = fields.Float('Timestamp Rounding', required=True,
        states={
            'invisible': ~Eval('type').in_(
                ['decimal timestamp', 'hexadecimal timestamp']),
            }, depends=['type'])
    timestamp_offset = fields.Float('Timestamp Offset',
        states={
            'invisible': ~Eval('type').in_(
                ['decimal timestamp', 'hexadecimal timestamp']),
            }, depends=['type'])
    last_timestamp = fields.Integer('Last Timestamp',
        states={
            'invisible': ~Eval('type').in_(
                ['decimal timestamp', 'hexadecimal timestamp']),
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

    def init(self, module_name):
        cursor = Transaction().cursor
        table = TableHandler(cursor, self, module_name)

        # Migration from 2.0 rename number_next into number_next_internal
        table.column_rename('number_next', 'number_next_internal')

        super(Sequence, self).init(module_name)

        # Migration from 2.0 create sql_sequence
        if sql_sequence and not self._strict:
            sequence_ids = self.search([])
            for sequence in self.browse(sequence_ids):
                if sequence.type != 'incremental':
                    continue
                if not TableHandler.sequence_exist(cursor,
                        self._sql_sequence_name(sequence)):
                    self.create_sql_sequence(sequence,
                        sequence.number_next_internal)

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

    def get_number_next(self, ids, name):
        cursor = Transaction().cursor
        result = {}
        for sequence in self.browse(ids):
            sql_name = self._sql_sequence_name(sequence)
            if sql_sequence and not self._strict:
                cursor.execute('SELECT '
                    'CASE WHEN NOT is_called THEN last_value '
                        'ELSE last_value + increment_by '
                    'END FROM "%s"' % sql_name)
                value, = cursor.fetchone()
            else:
                value = sequence.number_next_internal
            result[sequence.id] = value
        return result

    def set_number_next(self, ids, name, value):
        cursor = Transaction().cursor
        super(Sequence, self).write(ids, {
                'number_next_internal': value,
                })

    def create(self, values):
        sequence_id = super(Sequence, self).create(values)
        if sql_sequence and not self._strict:
            sequence = self.browse(sequence_id)
            self.update_sql_sequence(sequence, values.get('number_next',
                    self.default_number_next()))
        return sequence_id

    def write(self, ids, values):
        result = super(Sequence, self).write(ids, values)
        if sql_sequence and not self._strict:
            ids = [ids] if isinstance(ids, (int, long)) else ids
            sequences = self.browse(ids)
            for sequence in sequences:
                self.update_sql_sequence(sequence, values.get('number_next'))
        return result

    def delete(self, ids):
        if sql_sequence and not self._strict:
            ids = [ids] if isinstance(ids, (int, long)) else ids
            sequences = self.browse(ids)
            for sequence in sequences:
                self.delete_sql_sequence(sequence)
        return super(Sequence, self).delete(ids)

    def code_get(self):
        pool = Pool()
        sequence_type_obj = pool.get('ir.sequence.type')
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

    def _sql_sequence_name(self, sequence):
        'Return SQL sequence name'
        return '%s_%s' % (self._table, sequence.id)

    def create_sql_sequence(self, sequence, number_next=None):
        'Create the SQL sequence'
        cursor = Transaction().cursor
        if sequence.type != 'incremental':
            return
        if number_next is None:
            number_next = sequence.number_next
        cursor.execute('CREATE SEQUENCE "' + self._sql_sequence_name(sequence)
            + '" INCREMENT BY %s START WITH %s', (sequence.number_increment,
                number_next))

    def update_sql_sequence(self, sequence, number_next=None):
        'Update the SQL sequence'
        cursor = Transaction().cursor
        exist = TableHandler.sequence_exist(cursor,
            self._sql_sequence_name(sequence))
        if sequence.type != 'incremental':
            if exist:
                self.delete_sql_sequence(sequence)
            return
        if not exist:
            self.create_sql_sequence(sequence, number_next)
            return
        if number_next is None:
            number_next = sequence.number_next
        cursor.execute('ALTER SEQUENCE "' + self._sql_sequence_name(sequence)
            + '" INCREMENT BY %s RESTART WITH %s', (sequence.number_increment,
                number_next))

    def delete_sql_sequence(self, sequence):
        'Delete the SQL sequence'
        cursor = Transaction().cursor
        if sequence.type != 'incremental':
            return
        cursor.execute('DROP SEQUENCE "%s"'
            % self._sql_sequence_name(sequence))

    def _process(self, string, date=None):
        pool = Pool()
        date_obj = pool.get('ir.date')
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
            if sql_sequence and not self._strict:
                cursor = Transaction().cursor
                cursor.execute('SELECT nextval(\'"%s"\')'
                    % self._sql_sequence_name(sequence))
                number_next, = cursor.fetchone()
            else:
                #Pre-fetch number_next
                number_next = sequence.number_next_internal

                with Transaction().set_user(0):
                    self.write(sequence.id, {
                            'number_next_internal': (number_next
                                + sequence.number_increment),
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
    _strict = True

    def get_id(self, clause):
        Transaction().cursor.lock(self._table)
        return super(SequenceStrict, self).get_id(clause)

SequenceStrict()
