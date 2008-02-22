"Company"

import copy
from trytond.osv import fields, OSV


class Company(OSV):
    'Company'

    _name = 'company.company'
    _description = __doc__
    _columns = {
        'name': fields.Char('Name', size=128, required=True),
        'partner':fields.Many2One('partner.partner', 'Partner', required=True),
        'parent': fields.Many2One('company.company', 'Parent'),
        'childs': fields.One2Many('company.company', 'parent', 'Childs'),
    }
    _constraints = [
        ('check_recursion',
            'Error! You can not create recursive companies.', ['parent']),
    ]

    def write(self, cursor, user, ids, vals, context=None):
        res = super(Company, self).write(cursor, user, ids, vals,
                context=context)
        # Restart the cache on the domain_get method
        self.pool.get('ir.rule').domain_get()
        return res

Company()


class User(OSV):
    _name = 'res.user'

    def __init__(self, pool):
        super(User, self).__init__(pool)
        if pool:
            self._columns = copy.copy(self._columns)
            self._columns['main_company'] = fields.Many2One('company.company',
                    'Main Company')
            self._columns['company'] = fields.Many2One('company.company',
                    'Current Company',
                    domain="[('parent', 'child_of', [main_company])]")
            self._context_fields = self._context_fields + ['company']
            self._constraints = self._constraints + [
                    ('check_company',
                        'Error! You can not set a company that is not ' \
                                'a child of your main company.', ['company']),
                    ]

    def check_company(self, cursor, user_id, ids):
        company_obj = self.pool.get('company.company')
        for user in self.browse(cursor, user_id, ids):
            if user.main_company:
                companies = company_obj.search(cursor, user_id, [
                    ('parent', 'child_of', [user.main_company.id]),
                    ])
                if user.company.id and (user.company.id not in companies):
                    return False
            elif user.company:
                return False
        return True

    def get_preferences(self, cursor, user, context_only=False, context=None):
        res = super(User, self).get_preferences(cursor, user,
                context_only=context_only, context=context)
        if not context_only:
            user = self.browse(cursor, 0, user, context=context)
            res['main_company'] = user.main_company.id
        return res

    def get_preferences_fields_view(self, cursor, user, context=None):
        res = super(User, self).get_preferences_fields_view(cursor, user,
                context=context)
        fields = self.fields_get(cursor, user, fields_names=['main_company'],
                context=context)
        res['fields'].update(fields)
        return res

User()


class Property(OSV):
    _name = 'ir.property'

    def __init__(self, pool):
        super(Property, self).__init__(pool)
        if pool:
            self._columns = copy.copy(self._columns)
            self._columns['company'] = fields.Many2One('company.company',
                    'Company')

    def set(self, cursor, user, name, model, res_id, val, context=None):
        res = super(Property, self).set(cursor, user, name, model, res_id, val,
                context=context)
        if res:
            user_obj = self.pool.get('res.user')
            company = user_obj.browse(cursor, user, user, context=context)
            self.write(cursor, user, {
                'company': company.id,
                }, context=context)
        return res

Property()
