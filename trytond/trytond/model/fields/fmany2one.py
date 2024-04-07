# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from sql import Column, Literal

from trytond.pool import Pool
from trytond.tools import grouped_slice

from .function import Function
from .many2one import Many2One


def fmany2one(
        name, sources, target, string="", ondelete='SET NULL', **kwargs):
    sources = sources.split(',')
    target_model, target_fields = target.split(',', 1)
    target_fields = target_fields.split(',')
    assert len(sources) == len(target_fields)

    class Mixin:
        __slots__ = ()

        @classmethod
        def __register__(cls, module):
            pool = Pool()
            Target = pool.get(target_model)
            table_h = cls.__table_handler__(module)
            super().__register__(module)
            table_h.add_fk(
                sources, Target._table, target_fields,
                on_delete=getattr(cls, name).ondelete)

    @classmethod
    def getter(cls, records, name):
        pool = Pool()
        Target = pool.get(target_model)
        values = set(filter(all,
                (tuple(getattr(r, s) for s in sources) for r in records)))
        values2id = {}
        for sub_values in grouped_slice(values):
            domain = ['OR']
            for values in sub_values:
                domain.append(
                    [(f, '=', v) for f, v in zip(target_fields, values)])
            targets = Target.search(domain)
            values2id.update(
                (tuple(getattr(t, f) for f in target_fields), t.id)
                for t in targets)
        return {r.id: values2id.get(
                tuple(getattr(r, s) for s in sources)) for r in records}

    @classmethod
    def setter(cls, records, name, value):
        pool = Pool()
        Target = pool.get(target_model)
        if value:
            value = getattr(Target(value), target_fields[0])
        else:
            value = None
        cls.write(records, {sources[0]: value})

    @classmethod
    def searcher(cls, clause, tables):
        pool = Pool()
        Target = pool.get(target_model)
        table, _ = tables[None]
        if name not in tables:
            target = Target.__table__()
            join = Literal(True)
            for source, target_field in zip(sources, target_fields):
                join &= Column(table, source) == Column(target, target_field)
            tables[name] = {
                None: (target, join),
                }
        nested = clause[0][len(name) + 1:]
        if not nested:
            if isinstance(clause[2], str):
                nested = 'rec_name'
            else:
                nested = 'id'
        domain = [(nested, *clause[1:])]
        tables, clause = Target.search_domain(
            domain, tables=tables[name])
        return clause

    setattr(Mixin, name, Function(
            Many2One(target_model, string, ondelete=ondelete, **kwargs),
            f'get_{name}', setter=f'set_{name}'))
    setattr(Mixin, f'get_{name}', getter)
    setattr(Mixin, f'set_{name}', setter)
    setattr(Mixin, f'domain_{name}', searcher)
    return Mixin
