from collections.abc import Iterable, Mapping
from itertools import islice

_MAX_ARGUMENTS = 5
_MAX_ITEMS = 5
_ELLIPSE = '...'
_MAX_STR_LENGTH = 20 - len(_ELLIPSE)


class Ellipse:

    __slots__ = ('text',)

    def __init__(self, text=_ELLIPSE):
        self.text = text

    def __str__(self):
        return self.text

    __repr__ = __str__


class EllipseDict:

    __slots__ = ('items',)

    def __init__(self, items):
        self.items = items

    def __str__(self):
        strings = []
        ellipse = False
        for key, value in self.items:
            if isinstance(key, Ellipse):
                ellipse = True
                break
            strings.append(f'{key!r}: {value!r}')
        if ellipse:
            strings.append(_ELLIPSE)

        s = ', '.join(strings)
        return '{' + s + '}'

    __repr__ = __str__


class format_args:

    __slots__ = ('args', 'kwargs', 'verbose', 'max_args', 'max_items')

    def __init__(self, args, kwargs, verbose=False,
            max_args=_MAX_ARGUMENTS, max_items=_MAX_ITEMS):
        self.args = args
        self.kwargs = kwargs
        self.verbose = verbose
        self.max_args = max_args
        self.max_items = max_items

    def __str__(self):
        _nb_args = self.max_args
        _nb_items = self.max_items

        def _shorten_sequence(value):
            nonlocal _nb_items

            for v in islice(value, None, self.max_items + 1):
                if not self.verbose and not _nb_items:
                    yield Ellipse()
                    break
                yield v
                _nb_items -= 1

        def _log_repr(value):
            if self.verbose:
                return value
            elif isinstance(value, bytes):
                return Ellipse(f'<{len(value)} bytes>')
            elif isinstance(value, str):
                if len(value) <= _MAX_STR_LENGTH:
                    return value
                return (value[:_MAX_STR_LENGTH]
                    + (_ELLIPSE if len(value) > _MAX_STR_LENGTH else ''))
            elif isinstance(value, Mapping):
                def shorten(value):
                    for items in _shorten_sequence(value.items()):
                        if isinstance(items, Ellipse):
                            yield Ellipse(), Ellipse()
                            break
                        key, value = items
                        yield _log_repr(key), _log_repr(value)

                return EllipseDict(shorten(value))
            elif isinstance(value, Iterable):
                return type(value)(_log_repr(v)
                    for v in _shorten_sequence(value))
            else:
                return value

        s = '('

        logged_args = []
        for args in self.args:
            if not _nb_args and not self.verbose:
                logged_args.append(Ellipse())
                break
            _nb_items = self.max_items
            logged_args.append(_log_repr(args))
            _nb_args -= 1
        s += ', '.join(repr(a) for a in logged_args)

        if self.kwargs and (not logged_args
                or not isinstance(logged_args[-1], Ellipse)):
            s += ', ' if self.args and self.kwargs else ''
            logged_kwargs = []
            for key, value in self.kwargs.items():
                if not _nb_args and not self.verbose:
                    logged_kwargs.append(repr(Ellipse()))
                    break
                _nb_items = self.max_items
                logged_kwargs.append(
                    f'{_log_repr(key)}={_log_repr(value)!r}')
                _nb_args -= 1
            s += ', '.join(logged_kwargs)

        s += ')'
        return s
