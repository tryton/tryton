# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from email.utils import parseaddr


def _domainaddr(address):
    _, email = parseaddr(address)
    if '@' in email:
        return email.split('@', 1)[1]


def set_from_header(message, sender, from_):
    "Fill email headers to appear at best from the address"
    if parseaddr(sender)[1] != parseaddr(from_)[1]:
        if _domainaddr(sender) == _domainaddr(from_):
            message['From'] = from_
            message['Sender'] = sender
        else:
            message['From'] = sender
            message['On-Behalf-Of'] = from_
            message['Reply-To'] = from_
    else:
        message['From'] = from_
