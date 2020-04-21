# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from textwrap import TextWrapper

from sql import Null
from sql.conditionals import Case

from trytond.i18n import lazy_gettext
from ..model import ModelView, ModelSQL, ModelStorage, fields
from ..pool import Pool
from ..transaction import Transaction
from ..tools import grouped_slice, reduce_ids
from ..pyson import Eval
from .resource import ResourceMixin, resource_copy

__all__ = ['NoteCopyMixin']


class Note(ResourceMixin, ModelSQL, ModelView):
    "Note"
    __name__ = 'ir.note'
    message = fields.Text('Message', states={
            'readonly': Eval('id', 0) > 0,
            })
    message_wrapped = fields.Function(fields.Text('Message'),
        'on_change_with_message_wrapped')
    unread = fields.Function(fields.Boolean('Unread'), 'get_unread',
        searcher='search_unread', setter='set_unread')

    @staticmethod
    def default_unread():
        return False

    @classmethod
    def get_wrapper(cls):
        return TextWrapper(width=79)

    @fields.depends('message')
    def on_change_with_message_wrapped(self, name=None):
        wrapper = self.get_wrapper()
        message = self.message or ''
        return '\n'.join(map(wrapper.fill, message.splitlines()))

    @classmethod
    def get_unread(cls, ids, name):
        pool = Pool()
        Read = pool.get('ir.note.read')
        cursor = Transaction().connection.cursor()
        user_id = Transaction().user
        table = cls.__table__()
        read = Read.__table__()

        unread = {}
        for sub_ids in grouped_slice(ids):
            where = reduce_ids(table.id, sub_ids)
            query = table.join(read, 'LEFT',
                condition=(table.id == read.note)
                & (read.user == user_id)
                ).select(table.id,
                    Case((read.user != Null, False), else_=True),
                    where=where)
            cursor.execute(*query)
            unread.update(cursor.fetchall())
        return unread

    @classmethod
    def search_unread(cls, name, clause):
        pool = Pool()
        Read = pool.get('ir.note.read')
        user_id = Transaction().user
        table = cls.__table__()
        read = Read.__table__()

        _, operator, value = clause
        assert operator in ['=', '!=']
        Operator = fields.SQL_OPERATORS[operator]

        where = Operator(Case((read.user != Null, False), else_=True), value)
        query = table.join(read, 'LEFT',
            condition=(table.id == read.note)
            & (read.user == user_id)
            ).select(table.id, where=where)
        return [('id', 'in', query)]

    @classmethod
    def set_unread(cls, notes, name, value):
        pool = Pool()
        Read = pool.get('ir.note.read')
        user_id = Transaction().user
        if not value:
            Read.create([{'note': n.id, 'user': user_id} for n in notes])
        else:
            reads = []
            for sub_notes in grouped_slice(notes):
                reads += Read.search([
                        ('note', 'in', [n.id for n in sub_notes]),
                        ('user', '=', user_id),
                        ])
            Read.delete(reads)

    @classmethod
    def write(cls, notes, values, *args):
        # Avoid changing write meta data if only unread is set
        if args or set(values.keys()) != {'unread'}:
            super(Note, cls).write(notes, values, *args)
        else:
            # Check access write and clean cache
            # Use __func__ to directly access ModelStorage's write method and
            # pass it the right class
            ModelStorage.write.__func__(cls, notes, values)
            cls.set_unread(notes, 'unread', values['unread'])


class NoteRead(ModelSQL):
    "Note Read"
    __name__ = 'ir.note.read'
    note = fields.Many2One('ir.note', 'Note', required=True,
        ondelete='CASCADE')
    user = fields.Many2One('res.user', 'User', required=True,
        ondelete='CASCADE')


class NoteCopyMixin(
        resource_copy('ir.note', 'notes', lazy_gettext('ir.msg_notes'))):
    pass
