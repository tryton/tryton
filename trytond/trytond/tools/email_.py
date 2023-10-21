# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from email.utils import parseaddr

from trytond.pool import Pool

__all__ = [
    'set_from_header', 'validate_email', 'normalize_email',
    'convert_ascii_email', 'EmailNotValidError']


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


try:
    from dns.exception import DNSException
    from email_validator import EmailNotValidError, caching_resolver
    from email_validator import validate_email as _validate_email

    try:
        resolver = caching_resolver()
    except DNSException:
        if Pool.test:
            resolver = None
        else:
            raise

    def validate_email(email):
        emailinfo = _validate_email(
            email, check_deliverability=True,
            dns_resolver=resolver,
            test_environment=Pool.test)
        return emailinfo.normalized

    def normalize_email(email):
        try:
            emailinfo = _validate_email(
                email, check_deliverability=False,
                test_environment=Pool.test)
            return emailinfo.normalized
        except EmailNotValidError:
            return email

    def convert_ascii_email(email):
        try:
            emailinfo = _validate_email(
                email, check_deliverability=False,
                test_environment=Pool.test)
            return emailinfo.ascii_email
        except EmailNotValidError:
            return email

except ImportError:

    def validate_email(email):
        return email

    def normalize_email(email):
        return email

    def convert_ascii_email(email):
        return email

    class EmailNotValidError(Exception):
        pass
