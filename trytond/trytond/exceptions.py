#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.


class UserError(Exception):

    def __init__(self, message, description=''):
        super(UserError, self).__init__('UserError', (message, description))
        self.message = message
        self.description = description
        self.code = 1


class UserWarning(Exception):

    def __init__(self, name, message, description=''):
        super(UserWarning, self).__init__('UserWarning', (name, message,
                description))
        self.name = name
        self.message = message
        self.description = description
        self.code = 2


class NotLogged(Exception):

    def __init__(self):
        super(NotLogged, self).__init__('NotLogged')
        self.code = 3


class ConcurrencyException(Exception):

    def __init__(self, message):
        super(ConcurrencyException, self).__init__('ConcurrencyException',
            message)
        self.message = message
        self.code = 4
