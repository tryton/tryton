# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.model.exceptions import (
    RequiredValidationError, SizeValidationError)
from trytond.modules.product.exceptions import TemplateValidationError


class GiftCardValidationError(TemplateValidationError):
    pass


class MoveGiftCardValidationError(
        RequiredValidationError, SizeValidationError):
    pass
