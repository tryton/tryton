# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import trytond.config as config
from trytond.model import fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Bool, Eval
from trytond.report import get_email
from trytond.sendmail import SMTPDataManager, send_message_transactional
from trytond.tools.email_ import format_address, has_rcpt, set_from_header
from trytond.transaction import Transaction
from trytond.wizard import StateTransition


class Configuration(metaclass=PoolMeta):
    __name__ = 'account.configuration'

    dunning_email_fallback = fields.Many2One(
        'res.user', "Fall-back User",
        domain=[
            ('email', '!=', None),
            ],
        help="User notified when no email is found to send the dunning.")


class DunningLevel(metaclass=PoolMeta):
    __name__ = 'account.dunning.level'
    send_email = fields.Boolean("Send Email")
    email_template = fields.Many2One(
        'ir.action.report', "Email Template",
        domain=[
            ('template_extension', 'in', ['plain', 'html', 'xhtml']),
            ('model', '=', 'account.dunning'),
            ],
        states={
            'required': Bool(Eval('send_email')),
            'invisible': ~Eval('send_email'),
            })
    email_from = fields.Char(
        "From", translate=True,
        states={
            'invisible': ~Eval('send_email'),
            },
        help="Leave empty for the value defined in the configuration file.")
    email_contact_mechanism = fields.Selection(
        'get_contact_mechanisms', "Contact Mechanism",
        states={
            'invisible': ~Eval('send_email'),
            },
        help="Define which email to use from the party's contact mechanisms.")

    @classmethod
    def default_email_template(cls):
        pool = Pool()
        Data = pool.get('ir.model.data')
        try:
            return Data.get_id('account_dunning_email', 'report_email')
        except KeyError:
            return

    @classmethod
    def get_contact_mechanisms(cls):
        pool = Pool()
        ContactMechanism = pool.get('party.contact_mechanism')
        return ContactMechanism.usages()

    @classmethod
    def view_attributes(cls):
        return super().view_attributes() + [
            ('//separator[@id="email"]', 'states', {
                    'invisible': ~Eval('send_email'),
                    }),
            ]


class ProcessDunning(metaclass=PoolMeta):
    __name__ = 'account.dunning.process'
    send_email = StateTransition()

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._actions.append('send_email')

    def transition_send_email(self):
        pool = Pool()
        Email = pool.get('ir.email')
        datamanager = SMTPDataManager()
        if not pool.test:
            Transaction().join(datamanager)
        emails = []
        for dunning in self.records:
            if dunning.level.send_email:
                email = dunning.send_email(datamanager=datamanager)
                if email:
                    emails.append(email)
        if emails:
            Email.save(emails)
        return self.next_state('send_email')


class Dunning(metaclass=PoolMeta):
    __name__ = 'account.dunning'

    def send_email(self, datamanager=None):
        pool = Pool()
        Configuration = pool.get('ir.configuration')
        AccountConfig = pool.get('account.configuration')
        Lang = pool.get('ir.lang')
        Email = pool.get('ir.email')

        account_config = AccountConfig(1)

        from_ = config.get('email', 'from')
        to = []
        contact = self.party.contact_mechanism_get(
            'email', usage=self.level.email_contact_mechanism)
        if contact and contact.email:
            name = contact.name or self.party.rec_name
            to.append(format_address(contact.email, name))
        elif account_config.dunning_email_fallback:
            user = account_config.get_multivalue(
                'dunning_email_fallback', company=self.company.id)
            to.append(format_address(user.email, self.party.rec_name))
        cc = []
        bcc = []
        languages = set()
        if self.party.lang:
            languages.add(self.party.lang)
        else:
            lang, = Lang.search([
                    ('code', '=', Configuration.get_language()),
                    ], limit=1)
            languages.add(lang)

        msg = self._email(from_, to, cc, bcc, languages)
        if has_rcpt(msg):
            send_message_transactional(msg, datamanager=datamanager)
            return Email.from_message(
                msg, resource=self, dunning_level=self.level)

    def _email(self, sender, to, cc, bcc, languages):
        # TODO order languages to get default as last one for title
        msg, title = get_email(self.level.email_template, self, languages)
        language = list(languages)[-1]
        from_ = sender
        with Transaction().set_context(language=language.code):
            dunning = self.__class__(self.id)
            if dunning.level.email_from:
                from_ = dunning.level.email_from
        set_from_header(msg, sender, from_)
        if to:
            msg['To'] = to
        if cc:
            msg['Cc'] = cc
        if bcc:
            msg['Bcc'] = bcc
        msg['Subject'] = title
        msg['Auto-Submitted'] = 'auto-generated'
        return msg
