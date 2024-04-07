# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool, PoolMeta


class CreateChart(metaclass=PoolMeta):
    __name__ = 'account.create_chart'

    def default_properties(self, fields):
        pool = Pool()
        ModelData = pool.get('ir.model.data')
        defaults = super().default_properties(fields)
        for lang in ['fr']:
            for version in ['2001', '2016']:
                try:
                    template_id = ModelData.get_id(
                        'account_syscohada.root_%s_%s' % (version, lang))
                except KeyError:
                    continue
                if self.account.account_template.id == template_id:
                    defaults['account_receivable'] = self.get_account(
                        'account_syscohada.4111_%s_%s' % (version, lang))
                    defaults['account_payable'] = self.get_account(
                        'account_syscohada.4011_%s_%s' % (version, lang))
                    break
        return defaults
