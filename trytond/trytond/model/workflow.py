#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from functools import wraps


class Workflow(object):
    """
    Mix-in class to handle transition check.
    """
    _transition_state = 'state'

    def __init__(self):
        super(Workflow, self).__init__()
        self._transitions = set()

    @staticmethod
    def transition(state):
        def check_transition(func):
            @wraps(func)
            def wrapper(self, ids, *args, **kwargs):
                records = self.browse(ids)
                filtered = []
                to_update = []

                for record in records:
                    current_state = getattr(record, self._transition_state)
                    transition = (current_state, state)
                    if transition in self._transitions:
                        filtered.append(record.id)
                        if current_state != state:
                            to_update.append(record.id)

                result = func(self, filtered, *args, **kwargs)
                if to_update:
                    self.write(to_update, {
                            self._transition_state: state,
                            })
                return result
            return wrapper
        return check_transition
