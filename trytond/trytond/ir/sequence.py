# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from string import Template
import time

from sql import Literal, For

from ..model import ModelView, ModelSQL, DeactivableMixin, fields, Check
from ..tools import datetime_strftime
from ..pyson import Eval, And
from ..transaction import Transaction
from ..pool import Pool
from .. import backend

__all__ = [
    'SequenceType', 'Sequence', 'SequenceStrict',
    ]

sql_sequence = backend.get('Database').has_sequence()


class SequenceType(ModelSQL, ModelView):
    "Sequence type"
    __name__ = 'ir.sequence.type'

    name = fields.Char('Sequence Name', required=True, translate=True)
    code = fields.Char('Sequence Code', required=True)


class Sequence(DeactivableMixin, ModelSQL, ModelView):
    "Sequence"
    __name__ = 'ir.sequence'

    _strict = False
    name = fields.Char('Sequence Name', required=True, translate=True)
    code = fields.Selection('code_get', 'Sequence Code', required=True,
        states={
            'readonly': Eval('context', {}).contains('code'),
            })
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
            'required': And(Eval('type').in_(['incremental']),
                not sql_sequence),
            }, depends=['type'])
    number_next = fields.Function(number_next_internal, 'get_number_next',
        'set_number_next')
    number_increment = fields.Integer('Increment Number',
        states={
            'invisible': ~Eval('type').in_(['incremental']),
            'required': Eval('type').in_(['incremental']),
            }, depends=['type'])
    padding = fields.Integer('Number padding',
        states={
            'invisible': ~Eval('type').in_(['incremental']),
            'required': Eval('type').in_(['incremental']),
            }, depends=['type'])
    timestamp_rounding = fields.Float('Timestamp Rounding', required=True,
        states={
            'invisible': ~Eval('type').in_(
                ['decimal timestamp', 'hexadecimal timestamp']),
            }, depends=['type'])
    timestamp_offset = fields.Float('Timestamp Offset', required=True,
        states={
            'invisible': ~Eval('type').in_(
                ['decimal timestamp', 'hexadecimal timestamp']),
            }, depends=['type'])
    last_timestamp = fields.Integer('Last Timestamp',
        states={
            'invisible': ~Eval('type').in_(
                ['decimal timestamp', 'hexadecimal timestamp']),
            'required': Eval('type').in_(
                ['decimal timestamp', 'hexadecimal timestamp']),
            }, depends=['type'])

    @classmethod
    def __setup__(cls):
        super(Sequence, cls).__setup__()
        table = cls.__table__()
        cls._sql_constraints += [
            ('check_timestamp_rounding',
                Check(table, table.timestamp_rounding > 0),
                'Timestamp rounding should be greater than 0'),
            ]
        cls._error_messages.update({
                'missing': 'Missing sequence.',
                'invalid_prefix': ('Invalid prefix "%(prefix)s" on sequence '
                    '"%(sequence)s".'),
                'invalid_suffix': ('Invalid suffix "%(suffix)s" on sequence '
                    '"%(sequence)s".'),
                'future_last_timestamp': ('Last Timestamp cannot be in the '
                    'future on sequence "%s".'),
                })

    @staticmethod
    def default_type():
        return 'incremental'

    @staticmethod
    def default_number_increment():
        return 1

    @staticmethod
    def default_number_next():
        return 1

    @staticmethod
    def default_padding():
        return 0

    @staticmethod
    def default_timestamp_rounding():
        return 1.0

    @staticmethod
    def default_timestamp_offset():
        return 946681200.0  # Offset for 2000-01-01

    @staticmethod
    def default_last_timestamp():
        return 0

    @staticmethod
    def default_code():
        return Transaction().context.get('code')

    def get_number_next(self, name):
        if self.type != 'incremental':
            return

        transaction = Transaction()
        if sql_sequence and not self._strict:
            return transaction.database.sequence_next_number(
                transaction.connection, self._sql_sequence_name)
        else:
            return self.number_next_internal

    @classmethod
    def set_number_next(cls, sequences, name, value):
        super(Sequence, cls).write(sequences, {
                'number_next_internal': value,
                })

    @classmethod
    def view_attributes(cls):
        return [
            ('//group[@id="incremental"]', 'states', {
                    'invisible': ~Eval('type').in_(['incremental']),
                    }),
            ('//group[@id="timestamp"]', 'states', {
                    'invisible': ~Eval('type').in_(
                        ['decimal timestamp', 'hexadecimal timestamp']),
                    }),
            ]

    @classmethod
    def create(cls, vlist):
        sequences = super(Sequence, cls).create(vlist)
        for sequence, values in zip(sequences, vlist):
            if sql_sequence and not cls._strict:
                sequence.update_sql_sequence(values.get('number_next',
                        cls.default_number_next()))
        return sequences

    @classmethod
    def write(cls, sequences, values, *args):
        super(Sequence, cls).write(sequences, values, *args)
        if sql_sequence and not cls._strict:
            actions = iter((sequences, values) + args)
            for sequences, values in zip(actions, actions):
                for sequence in sequences:
                    sequence.update_sql_sequence(values.get('number_next'))

    @classmethod
    def delete(cls, sequences):
        if sql_sequence and not cls._strict:
            for sequence in sequences:
                sequence.delete_sql_sequence()
        return super(Sequence, cls).delete(sequences)

    @classmethod
    def code_get(cls):
        pool = Pool()
        SequenceType = pool.get('ir.sequence.type')
        sequence_types = SequenceType.search([])
        return [(x.code, x.name) for x in sequence_types]

    @classmethod
    def validate(cls, sequences):
        super(Sequence, cls).validate(sequences)
        cls.check_prefix_suffix(sequences)
        cls.check_last_timestamp(sequences)

    @classmethod
    def check_prefix_suffix(cls, sequences):
        "Check prefix and suffix"

        for sequence in sequences:
            for fix, error_message in ((sequence.prefix, 'invalid_prefix'),
                    (sequence.suffix, 'invalid_suffix')):
                try:
                    cls._process(fix)
                except (TypeError, ValueError):
                    cls.raise_user_error(error_message, {
                            'prefix': fix,
                            'sequence': sequence.rec_name,
                            })

    @classmethod
    def check_last_timestamp(cls, sequences):
        "Check last_timestamp"

        for sequence in sequences:
            next_timestamp = cls._timestamp(sequence)
            if (sequence.last_timestamp is not None
                    and sequence.last_timestamp > next_timestamp):
                cls.raise_user_error('future_last_timestamp', (
                        sequence.rec_name,))

    @property
    def _sql_sequence_name(self):
        'Return SQL sequence name'
        return '%s_%s' % (self._table, self.id)

    def create_sql_sequence(self, number_next=None):
        'Create the SQL sequence'
        transaction = Transaction()

        if self.type != 'incremental':
            return
        if number_next is None:
            number_next = self.number_next
        if sql_sequence:
            transaction.database.sequence_create(transaction.connection,
                self._sql_sequence_name, self.number_increment, number_next)

    def update_sql_sequence(self, number_next=None):
        'Update the SQL sequence'
        transaction = Transaction()

        exist = transaction.database.sequence_exist(
            transaction.connection, self._sql_sequence_name)
        if self.type != 'incremental':
            if exist:
                self.delete_sql_sequence()
            return
        if not exist:
            self.create_sql_sequence(number_next)
            return
        if number_next is None:
            number_next = self.number_next
        transaction.database.sequence_update(transaction.connection,
            self._sql_sequence_name, self.number_increment, number_next)

    def delete_sql_sequence(self):
        'Delete the SQL sequence'
        transaction = Transaction()
        if self.type != 'incremental':
            return
        transaction.database.sequence_delete(
            transaction.connection, self._sql_sequence_name)

    @classmethod
    def _process(cls, string, date=None):
        return Template(string or '').substitute(
            **cls._get_substitutions(date))

    @classmethod
    def _get_substitutions(cls, date):
        '''
        Returns a dictionary with the keys and values of the substitutions
        available to format the sequence
        '''
        pool = Pool()
        Date = pool.get('ir.date')
        if not date:
            date = Date.today()
        return {
            'year': datetime_strftime(date, '%Y'),
            'month': datetime_strftime(date, '%m'),
            'day': datetime_strftime(date, '%d'),
            }

    @staticmethod
    def _timestamp(sequence):
        return int((time.time() - sequence.timestamp_offset)
                / sequence.timestamp_rounding)

    @classmethod
    def _get_sequence(cls, sequence):
        if sequence.type == 'incremental':
            if sql_sequence and not cls._strict:
                cursor = Transaction().connection.cursor()
                cursor.execute('SELECT nextval(\'"%s"\')'
                    % sequence._sql_sequence_name)
                number_next, = cursor.fetchone()
            else:
                # Pre-fetch number_next
                number_next = sequence.number_next_internal

                cls.write([sequence], {
                        'number_next_internal': (number_next
                            + sequence.number_increment),
                        })
            return '%%0%sd' % sequence.padding % number_next
        elif sequence.type in ('decimal timestamp', 'hexadecimal timestamp'):
            timestamp = sequence.last_timestamp
            while timestamp == sequence.last_timestamp:
                timestamp = cls._timestamp(sequence)
            cls.write([sequence], {
                'last_timestamp': timestamp,
                })
            if sequence.type == 'decimal timestamp':
                return '%d' % timestamp
            else:
                return hex(timestamp)[2:].upper()
        return ''

    @classmethod
    def get_id(cls, domain, _lock=False):
        '''
        Return sequence value for the domain
        '''
        if isinstance(domain, cls):
            domain = domain.id
        if isinstance(domain, int):
            domain = [('id', '=', domain)]

        # bypass rules on sequences
        with Transaction().set_context(user=False, _check_access=False):
            with Transaction().set_user(0):
                try:
                    sequence, = cls.search(domain, limit=1)
                except TypeError:
                    cls.raise_user_error('missing')
                if _lock:
                    transaction = Transaction()
                    database = transaction.database
                    connection = transaction.connection
                    if not database.has_select_for():
                        database.lock(connection, cls._table)
                    else:
                        table = cls.__table__()
                        query = table.select(Literal(1),
                            where=table.id == sequence.id,
                            for_=For('UPDATE', nowait=True))
                        cursor = connection.cursor()
                        cursor.execute(*query)
                date = Transaction().context.get('date')
                return '%s%s%s' % (
                    cls._process(sequence.prefix, date=date),
                    cls._get_sequence(sequence),
                    cls._process(sequence.suffix, date=date),
                    )

    @classmethod
    def get(cls, code):
        return cls.get_id([('code', '=', code)])


class SequenceStrict(Sequence):
    "Sequence Strict"
    __name__ = 'ir.sequence.strict'
    _table = None  # Needed to reset Sequence._table
    _strict = True

    @classmethod
    def get_id(cls, clause):
        return super(SequenceStrict, cls).get_id(clause, _lock=True)
