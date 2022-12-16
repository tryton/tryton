# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

# Code come from python-Levenshtein

__all__ = ['StringMatcher', 'StringPartitioned', 'LazyString']

from warnings import warn
try:
    from Levenshtein import opcodes, editops, matching_blocks, ratio, distance

    class StringMatcher:
        """A SequenceMatcher-like class built on the top of Levenshtein"""

        def _reset_cache(self):
            self._ratio = self._distance = None
            self._opcodes = self._editops = self._matching_blocks = None

        def __init__(self, isjunk=None, seq1='', seq2=''):
            if isjunk:
                warn("isjunk not NOT implemented, it will be ignored")
            self._str1, self._str2 = seq1, seq2
            self._reset_cache()

        def set_seqs(self, seq1, seq2):
            self._str1, self._str2 = seq1, seq2
            self._reset_cache()

        def set_seq1(self, seq1):
            self._str1 = seq1
            self._reset_cache()

        def set_seq2(self, seq2):
            self._str2 = seq2
            self._reset_cache()

        def get_opcodes(self):
            if not self._opcodes:
                if self._editops:
                    self._opcodes = opcodes(
                        self._editops, self._str1, self._str2)
                else:
                    self._opcodes = opcodes(self._str1, self._str2)
            return self._opcodes

        def get_editops(self):
            if not self._editops:
                if self._opcodes:
                    self._editops = editops(
                        self._opcodes, self._str1, self._str2)
                else:
                    self._editops = editops(self._str1, self._str2)
            return self._editops

        def get_matching_blocks(self):
            if not self._matching_blocks:
                self._matching_blocks = matching_blocks(self.get_opcodes(),
                                                        self._str1, self._str2)
            return self._matching_blocks

        def ratio(self):
            if not self._ratio:
                self._ratio = ratio(self._str1, self._str2)
            return self._ratio

        def quick_ratio(self):
            # This is usually quick enough :o)
            if not self._ratio:
                self._ratio = ratio(self._str1, self._str2)
            return self._ratio

        def real_quick_ratio(self):
            len1, len2 = len(self._str1), len(self._str2)
            return 2.0 * min(len1, len2) / (len1 + len2)

        def distance(self):
            if not self._distance:
                self._distance = distance(self._str1, self._str2)
            return self._distance
except ImportError:
    from difflib import SequenceMatcher as StringMatcher


class StringPartitioned(str):
    "A string subclass that stores parts that composes itself."
    __slots__ = ('_parts',)

    def __init__(self, base):
        super().__init__()
        if isinstance(base, StringPartitioned):
            self._parts = base._parts
        else:
            self._parts = (base,)

    def __iter__(self):
        return iter(self._parts)

    def __add__(self, other):
        new = self.__class__(str(self) + other)
        new._parts = self._parts + (other,)
        return new

    def __radd__(self, other):
        new = self.__class__(other + str(self))
        new._parts = (other,) + self._parts
        return new


class LazyString():
    def __init__(self, func, *args, **kwargs):
        self._func = func
        self._args = args
        self._kwargs = kwargs

    def __str__(self):
        return self._func(*self._args, **self._kwargs)

    def __add__(self, other):
        return str(self) + other

    def __radd__(self, other):
        return other + str(self)
