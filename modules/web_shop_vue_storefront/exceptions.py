# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from werkzeug import exceptions


class LoginException(exceptions.Unauthorized):
    pass


class NotFound(exceptions.NotFound):
    pass


class BadRequest(exceptions.BadRequest):
    pass
