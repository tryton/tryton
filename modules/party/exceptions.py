# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.exceptions import UserError, UserWarning
from trytond.model.exceptions import ValidationError


class InvalidIdentifierCode(ValidationError):
    pass


class InvalidPhoneNumber(ValidationError):
    pass


class InvalidEMail(ValidationError):
    pass


class VIESUnavailable(UserError):
    pass


class SimilarityWarning(UserWarning):
    pass


class EraseError(ValidationError):
    pass


class InvalidFormat(ValidationError):
    pass
