# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import email.parser
import email.policy
import itertools
import re
from email.utils import getaddresses

import trytond.config as config
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction

REPLY_LINE = '\N{EM DASH}' * 80
DESTINATION_RE = re.compile(r"^[^@]*\+([0-9a-f]{32})@", re.IGNORECASE)


def _get_channel_identifier(email):
    base = config.get(
        'inbound_email', 'chat_reply_to',
        default=config.get('email', 'from'))
    _, our_domain = base.split('@', 1)

    for key in ('To', 'Cc'):
        if key not in email:
            continue
        addresses = [a for _, a in getaddresses(email.get_all(key))]
        for address in addresses:
            _, domain = address.split('@', 1)
            if domain != our_domain:
                continue
            if (m := DESTINATION_RE.match(address)):
                channel_id, = m.groups()
                return channel_id
    return None


class Channel(metaclass=PoolMeta):
    __name__ = 'ir.chat.channel'

    @classmethod
    def _email_channel(cls, email):
        channels = []
        if (channel_id := _get_channel_identifier(email)):
            channels = cls.search([('identifier', '=', channel_id)])
        return None if len(channels) != 1 else channels[0]

    @classmethod
    def _email_content(cls, body):
        return '\n'.join(itertools.takewhile(
                lambda l: REPLY_LINE not in l,
                body.splitlines()))

    @classmethod
    def post_inbound_email(cls, inbound_email):
        parser = email.parser.BytesParser(policy=email.policy.default)
        message = parser.parsebytes(inbound_email.data)
        return cls.post_from_email(message)

    @classmethod
    def _email_reply_to(cls, message):
        base = config.get(
            'inbound_email', 'chat_reply_to',
            default=config.get('email', 'from'))
        local_part, domain_part = base.split('@', 1)
        if '+' in local_part:
            local_part, _ = local_part.split('+', 1)
        local_part += f'+{message.channel.identifier}'
        return '@'.join((local_part, domain_part))

    @classmethod
    def _email_body(cls, message):
        pool = Pool()
        Message = pool.get('ir.message')
        ModelData = pool.get('ir.model.data')

        with Transaction().set_context(language=message.channel.language):
            above_msg = Message(ModelData.get_id('ir', 'msg_reply_above'))
            return f'{REPLY_LINE}\n{above_msg.text}\n\n{message.content}'
