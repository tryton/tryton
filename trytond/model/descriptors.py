# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import functools


class dualmethod(object):
    """Descriptor implementing combination of class and instance method

    When called on an instance, the class is passed as the first argument and a
    list with the instance as the second.
    When called on a class, the class itsefl is passed as the first argument.

    >>> class Example(object):
    ...     @dualmethod
    ...     def method(cls, instances):
    ...         print(len(instances))
    ...
    >>> Example.method([Example()])
    1
    >>> Example().method()
    1
    """
    def __init__(self, func):
        self.func = func

    def __get__(self, instance, owner):

        @functools.wraps(self.func)
        def newfunc(*args, **kwargs):
            if instance:
                return self.func(owner, [instance], *args, **kwargs)
            else:
                return self.func(owner, *args, **kwargs)
        return newfunc
