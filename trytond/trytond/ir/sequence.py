#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import time
from trytond.osv import fields, OSV
from string import Template


class SequenceType(OSV):
    "Sequence type"
    _name = 'ir.sequence.type'
    _description = __doc__
    name = fields.Char('Sequence Name', required=True, translate=True)
    code = fields.Char('Sequence Code', required=True)

SequenceType()


class Sequence(OSV):
    "Sequence"
    _name = 'ir.sequence'
    _description = __doc__
    name = fields.Char('Sequence Name', required=True, translate=True)
    code = fields.Selection('code_get', 'Sequence Code', required=True,
            states={
                'readonly': "context.get('code')",
            })
    active = fields.Boolean('Active')
    prefix = fields.Char('Prefix')
    suffix = fields.Char('Suffix')
    number_next = fields.Integer('Next Number')
    number_increment = fields.Integer('Increment Number')
    padding = fields.Integer('Number padding')

    def __init__(self):
        super(Sequence, self).__init__()
        self._constraints += [
            ('check_prefix_suffix', 'invalid_prefix_suffix'),
        ]
        self._error_messages.update({
            'missing': 'Missing sequence!',
            'invalid_prefix_suffix': 'Invalid prefix/suffix!',
            })

    def default_active(self, cursor, user, context=None):
        return 1

    def default_number_increment(self, cursor, user, context=None):
        return 1

    def default_number_next(self, cursor, user, context=None):
        return 1

    def default_padding(self, cursor, user, context=None):
        return 0

    def default_code(self, cursor, user, context=None):
        if context is None:
            context = {}
        return context.get('code', False)

    def code_get(self, cursor, user, context=None):
        sequence_type_obj = self.pool.get('ir.sequence.type')
        sequence_type_ids = sequence_type_obj.search(cursor, user, [],
                context=context)
        sequence_types = sequence_type_obj.browse(cursor, user,
                sequence_type_ids, context=context)
        return [(x.code, x.name) for x in sequence_types]

    def check_prefix_suffix(self, cursor, user, ids):
        "Check prefix and suffix"

        for sequence in self.browse(cursor, user, ids):
            try:
                self._process(cursor, user, sequence.prefix)
                self._process(cursor, user, sequence.suffix)
            except:
                return False
        return True

    def _process(self, cursor, user, string, date=None, context=None):
        date_obj = self.pool.get('ir.date')
        if not date:
            date = date_obj.today(cursor, user, context=context)
        year = date.strftime('%Y')
        month = date.strftime('%m')
        day = date.strftime('%d')
        return Template(string or '').substitute(
                year=year,
                month=month,
                day=day,
                )

    def get_id(self, cursor, user, sequence_id, test='id=%s', context=None):
        if context is None:
            context = {}
        cursor.execute('SELECT id, number_next, number_increment, prefix, ' \
                    'suffix, padding ' \
                'FROM "' + self._table + '" ' \
                'WHERE ' + test + ' AND active = True', (sequence_id,))
        res = cursor.dictfetchone()
        date = context.get('date')
        if res:
            cursor.execute('UPDATE "' + self._table + '" ' \
                    'SET number_next = number_next + number_increment, ' \
                        'write_uid = %s, ' \
                        'write_date = NOW() ' \
                    'WHERE id = %s AND active = True', (user, res['id'],))
            if res['number_next']:
                return self._process(cursor, user, res['prefix'], date=date,
                        context=context) + \
                        '%%0%sd' % res['padding'] % res['number_next'] + \
                        self._process(cursor, user, res['suffix'], date=date,
                                context=context)
            else:
                return self._process(cursor, user, res['prefix'], date=date,
                        context=context) + \
                        self._process(cursor, user, res['suffix'], date=date,
                                context=context)
        self.raise_user_error(cursor, 'missing', context=context)

    def get(self, cursor, user, code, context=None):
        return self.get_id(cursor, user, code, test='code=%s', context=context)

Sequence()


class SequenceStrict(Sequence):
    "Sequence Strict"
    _name = 'ir.sequence.strict'
    _description = __doc__

    def get_id(self, cursor, user, sequence_id, test='id=%s', context=None):
        cursor.execute('LOCK TABLE "' + self._table + '"')
        return super(SequenceStrict, self).get_id(cursor, user, sequence_id,
                test=test, context=context)

SequenceStrict()
