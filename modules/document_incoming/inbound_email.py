# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.model import fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval


class Rule(metaclass=PoolMeta):
    __name__ = 'inbound.email.rule'

    document_incoming_type = fields.Selection(
        'get_document_incoming_types', "Type",
        states={
            'required': (
                Eval('action') == 'document.incoming|from_inbound_email'),
            'invisible': (
                Eval('action') != 'document.incoming|from_inbound_email'),
            },
        depends=['action'])
    document_incoming_process = fields.Boolean(
        "Process",
        states={
            'invisible': (
                Eval('action') != 'document.incoming|from_inbound_email'),
            },
        depends=['action'])
    document_incoming_company = fields.Many2One(
        'company.company', "Company",
        states={
            'invisible': (
                Eval('action') != 'document.incoming|from_inbound_email'),
            },
        depends=['action'])

    @classmethod
    def __setup__(cls):
        super().__setup__()

        cls.action.selection.append(
            ('document.incoming|from_inbound_email', "Incoming Document"))

    @classmethod
    def get_document_incoming_types(cls):
        pool = Pool()
        DocumentIncoming = pool.get('document.incoming')
        return DocumentIncoming.fields_get(['type'])['type']['selection']

    def run(self, email_):
        pool = Pool()
        DocumentIncoming = pool.get('document.incoming')
        super().run(email_)
        if (self.action == 'document.incoming|from_inbound_email'
                and self.document_incoming_process):
            document = email_.result
            DocumentIncoming.process([document], with_children=True)
