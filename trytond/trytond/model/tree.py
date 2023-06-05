# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from itertools import chain

from trytond.i18n import gettext
from trytond.tools import escape_wildcard

from .modelstorage import ValidationError


class RecursionError(ValidationError):
    pass


def tree(parent='parent', name='name', separator=None):
    from . import fields

    class TreeMixin(object):
        __slots__ = ()

        if separator:
            @classmethod
            def __setup__(cls):
                super(TreeMixin, cls).__setup__()
                field = getattr(cls, name)
                clause = (
                    name, 'not like', '%' + escape_wildcard(separator) + '%')
                # If TreeMixin is after the class where name is defined in
                # __mro__, it modifies the base field copied so it must ensure
                # to add only once the domain
                if clause not in field.domain:
                    domain = [clause]
                    if field.domain:
                        domain.append(field.domain)
                    field.domain = domain

            def get_rec_name(self, _):
                record, names = self, []
                while record:
                    names.append(getattr(record, name))
                    record = getattr(record, parent)
                return separator.join(reversed(names))

            @fields.depends(parent, '_parent_%s.rec_name' % parent, name)
            def on_change_with_rec_name(self):
                names = []
                if self.parent and self.parent.rec_name:
                    names.append(self.parent.rec_name)
                names.append(getattr(self, name) or '')
                return separator.join(names)

            @classmethod
            def search_rec_name(cls, _, clause):
                domain = []
                if isinstance(clause[2], str):
                    field = name
                    values = list(reversed(clause[2].split(separator)))
                    for value in values:
                        domain.append((field, clause[1], value.strip()))
                        field = parent + '.' + field
                    if ((
                                clause[1].endswith('like')
                                and not clause[2].replace(
                                    '%%', '__').startswith('%'))
                            or not clause[1].endswith('like')):
                        if clause[1].startswith('not') or clause[1] == '!=':
                            operator = '!='
                            domain.insert(0, 'OR')
                        else:
                            operator = '='
                        top_parent = '.'.join((parent,) * len(values))
                        domain.append((top_parent, operator, None))
                    if (clause[1].endswith('like')
                            and clause[2].replace('%%', '__').endswith('%')):
                        ids = list(map(int, cls.search(domain, order=[])))
                        domain = [(parent, 'child_of', ids)]
                elif clause[2] is None:
                    domain.append((name, clause[1], clause[2]))
                else:
                    if clause[1].startswith('not'):
                        operator = '!='
                        domain.append('AND')
                    else:
                        operator = '='
                        domain.append('OR')
                    for value in clause[2]:
                        domain.append(cls.search_rec_name(
                                name, (clause[0], operator, value)))
                return domain

        @classmethod
        def validate_fields(cls, records, field_names):
            super().validate_fields(records, field_names)
            cls.check_recursion(records, field_names)

        @classmethod
        def check_recursion(cls, records, field_names=None):
            '''
            Function that checks if there is no recursion in the tree
            composed with parent as parent field name.
            '''
            if hasattr(super(TreeMixin, cls), 'check_recursion'):
                super(TreeMixin, cls).check_recursion(records, field_names)

            if field_names and parent not in field_names:
                return

            parent_type = cls._fields[parent]._type

            if parent_type not in ('many2one', 'many2many', 'one2one'):
                raise ValueError(
                    'Unsupported field type "%s" for field "%s" on "%s"'
                    % (parent_type, parent, cls.__name__))

            visited = set()

            for record in records:
                walked = set()
                walker = getattr(record, parent)
                while walker:
                    if parent_type == 'many2many':
                        for walk in walker:
                            walked.add(walk.id)
                            if walk.id == record.id:
                                parent_name = ', '.join(getattr(r, name)
                                    for r in getattr(record, parent))
                                raise RecursionError(
                                    gettext('ir.msg_recursion_error',
                                        rec_name=getattr(record, name),
                                        parent_rec_name=parent_name))
                        walker = list(chain(*(
                                    getattr(walk, parent)
                                    for walk in walker
                                    if walk.id not in visited)))
                    else:
                        walked.add(walker.id)
                        if walker.id == record.id:
                            parent_name = getattr(
                                getattr(record, parent), name)
                            raise RecursionError(
                                gettext('ir.msg_recursion_error',
                                    rec_name=getattr(record, name),
                                    parent_rec_name=parent_name))
                        walker = (getattr(walker, parent) not in visited
                            and getattr(walker, parent))
                visited.update(walked)

    return TreeMixin


def sum_tree(records, values, parent='parent'):
    "Sum up values following records tree"
    result = values.copy()
    parents = {
        int(r): int(getattr(r, parent)) for r in records if getattr(r, parent)}
    records = set(map(int, records))
    leafs = records - set(parents.values())
    while leafs:
        for leaf in leafs:
            records.remove(leaf)
            parent = parents.get(leaf)
            if parent:
                try:
                    result[parent] += result[leaf]
                except KeyError:
                    result[parent] = result[leaf]
        next_leafs = set(records)
        for record in records:
            parent = parents.get(record)
            if not parent:
                continue
            if parent in next_leafs and parent in records:
                next_leafs.remove(parent)
        leafs = next_leafs
    return result
