# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.exceptions import UserError, UserWarning


class ImportStatementError(UserError):
    pass


class StatementValidateError(UserError):
    pass


class StatementValidateWarning(UserWarning):
    pass


class StatementPostError(UserError):
    pass
