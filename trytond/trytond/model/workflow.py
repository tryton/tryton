# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from collections import OrderedDict
from functools import wraps


class Workflow(object):
    """
    Mix-in class to handle transition check.
    """
    _transition_state = 'state'

    @classmethod
    def __setup__(cls):
        super(Workflow, cls).__setup__()
        cls._transitions = set()

    @staticmethod
    def transition(state):
        def check_transition(func):
            @wraps(func)
            def wrapper(cls, records, *args, **kwargs):
                filtered = []
                to_update = OrderedDict()

                assert len(records) == len(set(records)), "Duplicate records"

                for record in records:
                    current_state = getattr(record, cls._transition_state)
                    transition = (current_state, state)
                    if transition in cls._transitions:
                        filtered.append(record)
                        if current_state != state:
                            to_update[record] = current_state

                result = func(cls, filtered, *args, **kwargs)
                if to_update:
                    for record in list(to_update.keys()):
                        current_state = getattr(record, cls._transition_state)
                        if current_state != to_update[record]:
                            del to_update[record]
                    cls.write(list(to_update), {
                            cls._transition_state: state,
                            })
                return result
            return wrapper
        return check_transition

    @classmethod
    def copy(cls, records, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault(
            cls._transition_state, cls._defaults[cls._transition_state]())
        return super().copy(records, default=default)
