#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.osv import fields, OSV

class Cron(OSV):
    "Cron"
    _name = "ir.cron"
    companies = fields.Many2Many(
        'company.company', 'cron_company_rel', 'cron', 'company', 'Companies',
        help='Companies registered for this cron')

    def _callback(self, cursor, cron):
        cursor.execute("SELECT company from cron_company_rel "
                       "WHERE cron = %s", (cron['id'],))
        for company in cursor.fetchall():
            cursor.execute("UPDATE res_user SET company = %s, main_company = %s "
                           "WHERE id = %s", (company, company, cron['user']))
            super(Cron, self)._callback(cursor, cron)
        cursor.execute("UPDATE res_user SET company = NULL, main_company = NULL "
                       "WHERE id = %s", (cron['user'],))

    def default_companies(self, cursor, user, context=None):
        company_obj = self.pool.get('company.company')
        return company_obj.search(cursor, user, [], context=context)

Cron()
