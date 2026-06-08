# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from genshi.template.astutil import ASTTransformer
from genshi.template.eval import (
    BUILTINS, Code, ExpressionASTTransformer, TemplateASTTransformer)


class _SafeASTTransformer(ASTTransformer):

    def visit_Attribute(self, node):
        if (node.attr.startswith('_')
                and node.attr not in {'__class__', '__name__'}):
            raise ValueError(f"invalid attribute {node.attr!r}")
        return super().visit_Attribute(node)

    def visit_Import(self, node):
        raise ValueError("invalid import")

    def visit_ImportFrom(self, node):
        raise ValueError("invalid import from")

    def visit_Name(self, node):
        if (node.id.startswith('_')
                and not node.id.startswith('__relatorio_')
                and node.id not in {'_'}):
            raise ValueError(f"invalid name {node.id!r}")
        return super().visit_Name(node)


class SafeExpressionASTTransformer(
        _SafeASTTransformer, ExpressionASTTransformer):
    pass


class SafeTemplateASTTransformer(_SafeASTTransformer, TemplateASTTransformer):
    pass


ALLOWED_BUILTINS = {
    'False',
    'True',
    'None',
    'abs',
    'all',
    'any',
    'ascii',
    'bin',
    'bool',
    'bytearray',
    'bytes',
    'chr',
    'complex',
    'dict',
    'dir',
    'divmod',
    'enumerate',
    'filter',
    'float',
    'format',
    'frozenset',
    'hasattr',
    'hash',
    'hex',
    'int',
    'iter',
    'len',
    'list',
    'map',
    'max',
    'min',
    'next',
    'oct',
    'ord',
    'pow',
    'range',
    'repr',
    'reversed',
    'round',
    'set'
    'slice',
    'sorted',
    'str',
    'sum',
    'tuple',
    'zip',
    }


def genshi_patch():

    code__init__ = Code.__init__

    def patched_code__init__(
            self, source, filename=None, lineno=-1, lookup='strict',
            xform=None):
        if self.mode == 'eval':
            xform = SafeExpressionASTTransformer
        else:
            xform = SafeTemplateASTTransformer
        code__init__(
            self, source, filename=filename, lineno=lineno, lookup=lookup,
            xform=xform)
    Code.__init__ = patched_code__init__

    for name in BUILTINS.keys() - ALLOWED_BUILTINS:
        BUILTINS.pop(name)
