#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.osv import fields, OSV

class Cron(OSV):
    "Cron"
    _name = "ir.cron"
    companies = fields.Many2Many(
        'company.company', 'cron_company_rel', 'cron', 'company', 'Companies',
        help='Companies registered for this cron')

    def _callback(self, cursor, user, job_id, model, func, args):
        cursor.execute("SELECT company,cron from cron_company_rel "
                       "WHERE cron = %s", (job_id,))
        for company, cron in cursor.fetchall():
            cursor.execute("UPDATE res_user SET company = %s "
                           "WHERE id = %s", (company,user))
            super(Cron, self)._callback(cursor, user, job_id, model, func, args)
Cron()
