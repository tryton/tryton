# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from sql import Table

from trytond.pool import PoolMeta
from trytond.transaction import Transaction


__all__ = ['TaxTemplate', 'TaxRuleTemplate']
__metaclass__ = PoolMeta


class TaxTemplate:
    __name__ = 'account.tax.template'

    @classmethod
    def __register__(cls, module_name):
        cursor = Transaction().cursor
        model_data = Table('ir_model_data')

        # Migration from 3.0: new tax rates
        if module_name == 'account_fr':
            for old_id, new_id in (
                    ('tva_vente_19_6', 'tva_vente_taux_normal'),
                    ('tva_vente_7', 'tva_vente_taux_intermediaire'),
                    ('tva_vente_intracommunautaire_19_6',
                        'tva_vente_intracommunautaire_taux_normal'),
                    ('tva_vente_intracommunautaire_7',
                        'tva_vente_intracommunautaire_taux_intermediaire'),
                    ('tva_achat_19_6', 'tva_achat_taux_normal'),
                    ('tva_achat_7', 'tva_achat_taux_intermediaire'),
                    ('tva_achat_intracommunautaire_19_6',
                        'tva_achat_intracommunautaire_taux_normal'),
                    ):
                cursor.execute(*model_data.select(model_data.id,
                        where=(model_data.fs_id == new_id)
                        & (model_data.module == module_name)))
                if cursor.fetchone():
                    continue
                cursor.execute(*model_data.update(
                        columns=[model_data.fs_id],
                        values=[new_id],
                        where=(model_data.fs_id == old_id)
                        & (model_data.module == module_name)))

        super(TaxTemplate, cls).__register__(module_name)


class TaxRuleTemplate:
    __name__ = 'account.tax.rule.template'

    @classmethod
    def __register__(cls, module_name):
        cursor = Transaction().cursor
        model_data = Table('ir_model_data')

        if module_name == 'account_fr':
            for old_id, new_id in (
                    ('tax_rule_ventes_intracommunautaires_19_6',
                        'tax_rule_ventes_intracommunautaires_taux_normal'),
                    ('tax_rule_ventes_intracommunautaires_7',
                        'tax_rule_ventes_intracommunautaires_taux_intermediaire'),
                    ):
                cursor.execute(*model_data.update(
                        columns=[model_data.fs_id],
                        values=[new_id],
                        where=(model_data.fs_id == old_id)
                        & (model_data.module == module_name)))

        super(TaxRuleTemplate, cls).__register__(module_name)
