# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.


class TrytonException(Exception):
    pass


class UserError(TrytonException):

    def __init__(self, message, description='', domain=None):
        super().__init__('UserError', (message, description, domain))
        self.message = message
        self.description = description
        self.domain = domain
        self.code = 1

    def __str__(self):
        return '%s - %s' % (self.message, self.description)


class UserWarning(TrytonException):
    "Exception that will be displayed as a warning message in the client."

    def __init__(self, name, message, description=''):
        super(UserWarning, self).__init__('UserWarning', (name, message,
                description))
        self.name = name
        self.message = message
        self.description = description
        self.code = 2

    def __str__(self):
        return '%s - %s' % (self.message, self.description)


class LoginException(TrytonException):
    """Request the named parameter for the login process.
    The type can be 'password' or 'char'.
    """

    def __init__(self, name, message, type='password'):
        super(LoginException, self).__init__(
            'LoginException', (name, message, type))
        self.name = name
        self.message = message
        self.type = type
        self.code = 3


class ConcurrencyException(TrytonException):

    def __init__(self, message):
        super(ConcurrencyException, self).__init__('ConcurrencyException',
            message)
        self.message = message
        self.code = 4

    def __str__(self):
        return self.message


class RateLimitException(TrytonException):
    """User has sent too many requests in a given amount of time."""


class MissingDependenciesException(TrytonException):

    def __init__(self, missings):
        self.missings = missings

    def __str__(self):
        return 'Missing dependencies: %s' % ' '.join(self.missings)
