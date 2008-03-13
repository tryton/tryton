"Journal"

from trytond.osv import fields, OSV


class Type(OSV):
    'Journal Type'
    _name = 'account.journal.type'
    _order = 'code'
    _description = __doc__
    name = fields.Char('Name', size=None, required=True, translate=True)
    code = fields.Char('Code', size=None, required=True)

    def __init__(self):
        super(Type, self).__init__()
        self._sql_constraints += [
            ('code_uniq', 'UNIQUE(code)', 'Code must be unique!'),
        ]

Type()


class View(OSV):
    'Journal View'
    _name = 'account.journal.view'
    _description = __doc__
    _order = 'name, id'
    name = fields.Char('Name', size=None, required=True)
    columns = fields.One2Many('account.journal.view.column', 'view', 'Columns')

View()


class Column(OSV):
    'Journal View Column'
    _name = 'account.journal.view.column'
    _description = __doc__
    _order = 'sequence, id'
    name = fields.Char('Name', size=None, required=True)
    field = fields.Many2One('ir.model.field', 'Field', required=True,
            domain="[('model.model', '=', 'account.move.line')]")
    view = fields.Many2One('account.journal.view', 'View', select=1)
    sequence = fields.Integer('Sequence', select=2)
    required = fields.Boolean('Required')
    readonly = fields.Boolean('Readonly')

    def default_sequence(self, cursor, user, context=None):
        cursor.execute('SELECT MAX(sequence) ' \
                'FROM ' + self._table)
        res = cursor.fetchone()
        if res:
            return res[0]
        return 0

Column()


class Journal(OSV):
    'Journal'
    _name = 'account.journal'
    _description = __doc__
    _order = 'name, id'

    name = fields.Char('Name', size=None, required=True, translate=True)
    code = fields.Char('Code', size=None)
    active = fields.Boolean('Active', select=2)
    type = fields.Selection('get_types', 'Type', required=True)
    view = fields.Many2One('account.journal.view', 'View')
    centralisation = fields.Boolean('Centralised counterpart')
    update_posted = fields.Boolean('Allow cancelling moves')
    sequence = fields.Many2One('ir.sequence', 'Sequence', required=True,
            domain="[('code', '=', 'account.journal')]")
    credit_account = fields.Many2One('account.account', 'Default credit account')
    debit_account = fields.Many2One('account.account', 'Default debit account')

    def default_active(self, cursor, user, context=None):
        return True

    def default_centralisation(self, cursor, user, context=None):
        return False

    def get_types(self, cursor, user, context=None):
        type_obj = self.pool.get('account.journal.type')
        type_ids = type_obj.search(cursor, user, [], context=context)
        types = type_obj.browse(cursor, user, type_ids, context=context)
        return [(x.code, x.name) for x in types]

    def name_search(self, cursor, user, name='', args=None, operator='ilike',
            context=None, limit=None):
        if name:
            ids = self.search(cursor, user,
                    [('code', 'like', name + '%')] + args,
                    limit=limit, context=context)
            if not ids:
                ids = self.search(cursor, user,
                        [(self._rec_name, operator, name)] + args,
                        limit=limit, context=context)
        else:
            ids = self.search(cursor, user, args, limit=limit, context=context)
        res = self.name_get(cursor, user, ids, context=context)
        return res

Journal()
