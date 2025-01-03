# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import time
from string import Template

from trytond import backend
from trytond.exceptions import UserError
from trytond.i18n import gettext
from trytond.model import Check, DeactivableMixin, ModelSQL, ModelView, fields
from trytond.model.exceptions import AccessError, ValidationError
from trytond.pool import Pool
from trytond.pyson import And, Eval
from trytond.transaction import Transaction, without_check_access

sql_sequence = backend.Database.has_sequence()


class AffixError(ValidationError):
    pass


class MissingError(UserError):
    pass


class LastTimestampError(ValidationError):
    pass


class SQLSequenceError(ValidationError):
    pass


class SequenceType(ModelSQL, ModelView):
    __name__ = 'ir.sequence.type'

    name = fields.Char('Sequence Name', required=True, translate=True)
    groups = fields.Many2Many(
        'ir.sequence.type-res.group', 'sequence_type', 'group', "Groups",
        help="Groups allowed to edit the sequences of this type.")


class SequenceTypeGroup(ModelSQL):
    __name__ = 'ir.sequence.type-res.group'
    sequence_type = fields.Many2One(
        'ir.sequence.type', "Sequence Type", ondelete='CASCADE', required=True)
    group = fields.Many2One(
        'res.group', "Group", ondelete='CASCADE', required=True)


class Sequence(DeactivableMixin, ModelSQL, ModelView):
    __name__ = 'ir.sequence'

    _strict = False
    name = fields.Char('Sequence Name', required=True, translate=True)
    sequence_type = fields.Many2One(
        'ir.sequence.type', "Sequence Type",
        required=True, ondelete='RESTRICT',
        states={
            'readonly': Eval('id', -1) >= 0,
            },
        depends=['id'])
    prefix = fields.Char('Prefix', strip='leading',
        help="The current date can be used formatted using strftime format "
             "suffixed with underscores: i.e: ${date_Y}")
    suffix = fields.Char('Suffix', strip='trailing',
        help="The current date can be used formatted using strftime format "
             "suffixed with underscores: i.e: ${date_Y}")
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
    timestamp_rounding = fields.Float(
        "Timestamp Rounding", required=True,
        domain=[
            ('timestamp_rounding', '>', 0),
            ],
        states={
            'invisible': ~Eval('type').in_(
                ['decimal timestamp', 'hexadecimal timestamp']),
            },
        depends=['type'])
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
    preview = fields.Function(fields.Char("Preview"), 'on_change_with_preview')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        table = cls.__table__()
        cls._sql_constraints += [
            ('check_timestamp_rounding',
                Check(table, table.timestamp_rounding > 0),
                'Timestamp rounding should be greater than 0'),
            ]

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

    def get_number_next(self, name):
        if self.type != 'incremental':
            return

        transaction = Transaction()
        if sql_sequence and not self._strict:
            if transaction.database.sequence_exist(
                    transaction.connection, self._sql_sequence_name):
                return transaction.database.sequence_next_number(
                    transaction.connection, self._sql_sequence_name)
        else:
            return self.number_next_internal

    @classmethod
    def set_number_next(cls, sequences, name, value):
        super().write(sequences, {
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
        sequences = super().create(vlist)
        for sequence, values in zip(sequences, vlist):
            if sql_sequence and not cls._strict:
                sequence.update_sql_sequence(values.get('number_next',
                        cls.default_number_next()))
        return sequences

    @classmethod
    def write(cls, *args):
        transaction = Transaction()
        if transaction.user != 0 and transaction.check_access:
            for values in args[1::2]:
                if 'sequence_type' in values:
                    raise AccessError(gettext(
                            'ir.msg_sequence_change_sequence_type'))
        super().write(*args)
        if sql_sequence and not cls._strict:
            actions = iter(args)
            for sequences, values in zip(actions, actions):
                for sequence in sequences:
                    sequence.update_sql_sequence(values.get('number_next'))

    @classmethod
    def delete(cls, sequences):
        if sql_sequence and not cls._strict:
            for sequence in sequences:
                sequence.delete_sql_sequence()
        return super().delete(sequences)

    @classmethod
    def validate(cls, sequences):
        super().validate(sequences)
        cls.check_last_timestamp(sequences)

    @classmethod
    def validate_fields(cls, sequences, field_names):
        super().validate_fields(sequences, field_names)
        cls.check_affixes(sequences, field_names)

    @classmethod
    def check_affixes(cls, sequences, field_names=None):
        "Check prefix and suffix"
        if field_names and not (field_names & {'prefix', 'suffix'}):
            return
        for sequence in sequences:
            for affix, error_message in [
                    (sequence.prefix, 'msg_sequence_invalid_prefix'),
                    (sequence.suffix, 'msg_sequence_invalid_suffix')]:
                try:
                    cls._process(affix)
                except (TypeError, ValueError) as exc:
                    raise AffixError(gettext('ir.%s' % error_message,
                            affix=affix,
                            sequence=sequence.rec_name)) from exc

    @classmethod
    def check_last_timestamp(cls, sequences):
        "Check last_timestamp"

        for sequence in sequences:
            next_timestamp = cls._timestamp(sequence)
            if (sequence.last_timestamp is not None
                    and sequence.last_timestamp > next_timestamp):
                raise LastTimestampError(
                    gettext('ir.msg_sequence_last_timestamp_future'))

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
        try:
            transaction.database.sequence_create(
                transaction.connection, self._sql_sequence_name,
                self.number_increment, number_next)
        except Exception as exception:
            raise SQLSequenceError(
                gettext('ir.msg_sequence_invalid_number_increment_next',
                    number_increment=self.number_increment,
                    number_next=number_next,
                    exception=exception)) from exception

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
        try:
            transaction.database.sequence_update(
                transaction.connection, self._sql_sequence_name,
                self.number_increment, number_next)
        except Exception as exception:
            raise SQLSequenceError(
                gettext('ir.msg_sequence_invalid_number_increment_next',
                    number_increment=self.number_increment,
                    number_next=number_next,
                    exception=exception)) from exception

    def delete_sql_sequence(self):
        'Delete the SQL sequence'
        transaction = Transaction()
        if self.type != 'incremental':
            return
        transaction.database.sequence_delete(
            transaction.connection, self._sql_sequence_name)

    @classmethod
    def _process(cls, string, date=None):
        if not string:
            return ''

        substitutions = cls._get_substitutions(date)
        return Template(string or '').safe_substitute(substitutions)

    @classmethod
    def _get_substitutions(cls, date=None):
        '''
        Returns a dictionary with the keys and values of the substitutions
        available to format the sequence
        '''
        pool = Pool()
        Date = pool.get('ir.date')
        context = Transaction().context
        if not date:
            date = context.get('date') or Date.today()

        class CustomFormatter(dict):

            def __getitem__(self, name):
                try:
                    value = super().__getitem__(name)
                except KeyError:
                    value = cls._convert_substitution_key(self, name)
                return value

        return CustomFormatter({
            'date': date,
            })

    @classmethod
    def _convert_substitution_key(cls, substitutions, key):
        """
        Converts a substitution key into a different (i.e: formated) value
        Returns the updated value
        """
        # Compatibilty with previous keywords
        key = {
            'year': 'date_Y',
            'month': 'date_m',
            'day': 'date_d',
            }.get(key, key)
        if key.startswith('date_'):
            format_ = key[len('date'):].replace('_', '%')
            value = substitutions['date'].strftime(format_)
            if value == format_:
                raise ValueError(
                    f"Unknown substitution format {format_}")
            return value

    @fields.depends('timestamp_offset', 'timestamp_rounding')
    def _timestamp(self):
        return int(
            (time.time() - self.timestamp_offset) / self.timestamp_rounding)

    def _get_many(self, n=1):
        if self.type == 'incremental':
            if sql_sequence and not self._strict:
                transaction = Transaction()
                numbers = transaction.database.sequence_nextvals(
                    transaction.connection, self._sql_sequence_name, n)
                # clean cache
                transaction.counter += 1
                self._local_cache.pop(self.id, None)
            else:
                # pre-fetch number_next
                start = self.number_next_internal
                end = start + n * self.number_increment
                numbers = list(range(start, end, self.number_increment))
                self.number_next_internal = end
                self.save()
            for number in numbers:
                yield f'{number:0>{self.padding}d}'
        elif self.type in {'decimal timestamp', 'hexadecimal timestamp'}:
            timestamps = []
            last_timestamp = timestamp = self.last_timestamp
            for _ in range(n):
                while timestamp == last_timestamp:
                    timestamp = self._timestamp()
                timestamps.append(timestamp)
                last_timestamp = timestamp
            self.last_timestamp = last_timestamp
            self.save()
            if self.type == 'decimal timestamp':
                for timestamp in timestamps:
                    yield f'{timestamp:d}'
            else:
                for timestamp in timestamps:
                    yield hex(timestamp)[2:].upper()

    @fields.depends('type', 'padding', 'number_next', methods=['_timestamp'])
    def _get_preview_sequence(self):
        if self.type == 'incremental':
            number_next = self.number_next or 0
            padding = self.padding or 0
            return f'{number_next:0>{padding}d}'
        elif self.type in {'decimal timestamp', 'hexadecimal timestamp'}:
            timestamp = self._timestamp()
            if self.type == 'decimal timestamp':
                return f'{timestamp:d}'
            else:
                return hex(timestamp)[2:].upper()
        return ''

    def get(self):
        "Returns the next sequence value"
        return next(self.get_many(n=1))

    @without_check_access
    def get_many(self, n=1, _lock=False):
        "Yield the n next sequence values"
        assert n > 0, n
        if _lock:
            self.lock()
        for value in self._get_many(n=n):
            prefix = self._process(self.prefix)
            suffix = self._process(self.suffix)
            yield f'{prefix}{value}{suffix}'

    @fields.depends('prefix', 'suffix', methods=['_get_preview_sequence'])
    def on_change_with_preview(self, name=None):
        return '%s%s%s' % (
            self._process(self.prefix),
            self._get_preview_sequence(),
            self._process(self.suffix),
            )


class SequenceStrict(Sequence):
    __name__ = 'ir.sequence.strict'
    _table = None  # Needed to reset Sequence._table
    _strict = True

    def get_many(self, n=1, _lock=True):
        yield from super().get_many(n=n, _lock=True)
