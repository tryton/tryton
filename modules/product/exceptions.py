# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.model.exceptions import AccessError, ValidationError


class TemplateValidationError(ValidationError):
    pass


class ProductValidationError(TemplateValidationError):
    pass


class UOMValidationError(ValidationError):
    pass


class UOMAccessError(AccessError):
    pass


class InvalidIdentifierCode(ValidationError):
    pass
