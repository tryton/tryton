# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.transaction import Transaction
from trytond.pool import Pool
from trytond.exceptions import UserError, UserWarning


class WarningErrorMixin(object):

    @classmethod
    def _get_error_messages(cls):
        return list(cls._error_messages.values())

    @classmethod
    def raise_user_error(cls, error, error_args=None,
            error_description='', error_description_args=None,
            raise_exception=True):
        '''
        Raise an exception that will be displayed as an error message
        in the client.

        :param error: the key of the dictionary _error_messages used
            for error message
        :param error_args: the arguments that will be used
            for "%"-based substitution
        :param error_description: the key of the dictionary
            _error_messages used for error description
        :param error_description_args: the arguments that will be used
            for "%"-based substitution
        :param raise_exception: if set to False return the error string
            (or tuple if error_description is not empty) instead of raising an
            exception.
        '''
        Translation = Pool().get('ir.translation')

        error = cls._error_messages.get(error, error)

        language = Transaction().language
        res = Translation.get_source(cls.__name__, 'error', language, error)
        if not res:
            res = Translation.get_source(error, 'error', language)
        if res:
            error = res

        if error_args is not None:
            try:
                error = error % error_args
            except (TypeError, KeyError):
                pass

        if error_description:
            error_description = cls._error_messages.get(error_description,
                    error_description)

            res = Translation.get_source(cls.__name__, 'error', language,
                error_description)
            if not res:
                res = Translation.get_source(error_description, 'error',
                    language)
            if res:
                error_description = res

            if error_description_args:
                try:
                    error_description = (error_description
                        % error_description_args)
                except (TypeError, KeyError):
                    pass
            if raise_exception:
                raise UserError(error, error_description)
            else:
                return (error, error_description)
        if raise_exception:
            raise UserError(error)
        else:
            return error

    @classmethod
    def raise_user_warning(cls, warning_name, warning,
            warning_args=None, warning_description='',
            warning_description_args=None):
        '''
        Raise an exception that will be displayed as a warning message
        in the client, if the user has not yet bypassed it.

        :param warning_name: the unique warning name
        :param warning: the key of the dictionary _error_messages used
            for warning message
        :param warning_args: the arguments that will be used for
            "%"-based substitution
        :param warning_description: the key of the dictionary
            _error_messages used for warning description
        :param warning_description_args: the arguments that will be used
            for "%"-based substitution
        '''
        Warning_ = Pool().get('res.user.warning')
        if Warning_.check(warning_name):
            if warning_description:
                warning, warning_description = cls.raise_user_error(warning,
                        error_args=warning_args,
                        error_description=warning_description,
                        error_description_args=warning_description_args,
                        raise_exception=False)
                raise UserWarning(warning_name, warning, warning_description)
            else:
                warning = cls.raise_user_error(warning,
                        error_args=warning_args, raise_exception=False)
                raise UserWarning(warning_name, warning)
