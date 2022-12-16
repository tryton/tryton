# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.exceptions import UserError, UserWarning
from trytond.model.exceptions import ValidationError


class ProcessError(UserError):
    pass


class OverpayWarning(UserWarning):
    pass


class PaymentValidationError(ValidationError):
    pass


class BlockedWarning(UserWarning):
    pass


class GroupWarning(UserWarning):
    pass
