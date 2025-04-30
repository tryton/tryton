# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
import decimal
import locale
import logging
import math
import os
import tempfile
from decimal import Decimal
from itertools import chain
from pathlib import Path

import tryton.common as common
from tryton.common import (
    EvalEnvironment, RPCException, RPCExecute, concat, domain_inversion,
    eval_domain, extract_reference_models, filter_leaf, inverse_leaf,
    localize_domain, merge, prepare_reference_domain, simplify, unique_value)
from tryton.common.htmltextbuffer import guess_decode
from tryton.config import CONFIG
from tryton.pyson import PYSONDecoder

logger = logging.getLogger(__name__)


class Field(object):
    '''
    get: return the values to write to the server
    get_client: return the value for the client widget (form_gtk)
    set: save the value from the server
    set_client: save the value from the widget
    '''
    _default = None
    _single_value = True

    @staticmethod
    def get_field(ctype):
        return TYPES.get(ctype, CharField)

    def __init__(self, attrs):
        self.attrs = attrs
        self.name = attrs['name']
        self.views = set()

    def sig_changed(self, record):
        record.on_change([self.name])
        record.on_change_with([self.name])
        record.autocomplete_with(self.name)
        record.set_field_context()

    def domains_get(self, record, pre_validate=None):
        screen_domain = domain_inversion(
            [record.group.domain4inversion, pre_validate or []],
            self.name, EvalEnvironment(record))
        if isinstance(screen_domain, bool) and not screen_domain:
            screen_domain = [('id', '=', None)]
        elif isinstance(screen_domain, bool) and screen_domain:
            screen_domain = []
        attr_domain = record.expr_eval(self.attrs.get('domain', []))
        return screen_domain, attr_domain

    def domain_get(self, record):
        screen_domain, attr_domain = self.domains_get(record)
        return concat(localize_domain(screen_domain), attr_domain)

    def validation_domains(self, record, pre_validate=None):
        return concat(*self.domains_get(record, pre_validate))

    def get_context(self, record, record_context=None, local=False):
        if record_context is not None:
            context = record_context.copy()
        else:
            context = record.get_context(local=local)
        context.update(record.expr_eval(self.attrs.get('context', {})))
        return context

    def get_search_context(self, record):
        context = self.get_context(record)
        context.update(record.expr_eval(self.attrs.get('search_context', {})))
        return context

    def get_search_order(self, record):
        order = record.expr_eval(self.attrs.get('search_order', None))
        return order

    def _is_empty(self, record):
        return not self.get_eval(record)

    def check_required(self, record):
        state_attrs = self.get_state_attrs(record)
        if bool(int(state_attrs.get('required') or 0)):
            if (self._is_empty(record)
                    and not bool(int(state_attrs.get('readonly') or 0))):
                return False
        return True

    def validate(self, record, softvalidation=False, pre_validate=None):
        if self.attrs.get('readonly'):
            return True
        state_attrs = self.get_state_attrs(record)
        is_required = bool(int(state_attrs.get('required') or 0))
        is_invisible = bool(int(state_attrs.get('invisible') or 0))
        invalid = False
        state_attrs['domain_readonly'] = False
        domain = simplify(self.validation_domains(record, pre_validate))
        if not softvalidation:
            if not self.check_required(record):
                invalid = 'required'
        if isinstance(domain, bool):
            if not domain:
                invalid = 'domain'
        elif domain == [('id', '=', None)]:
            invalid = 'domain'
        else:
            screen_domain, _ = self.domains_get(record, pre_validate)
            unique, leftpart, value = unique_value(
                domain, single_value=self._single_value)
            unique_from_screen, _, _ = unique_value(
                screen_domain, single_value=self._single_value)
            if (self._is_empty(record)
                    and not is_required
                    and not is_invisible
                    and not unique_from_screen):
                pass
            elif unique:
                # If the inverted domain is so constraint that only one value
                # is possible we should use it. But we must also pay attention
                # to the fact that the original domain might be a 'OR' domain
                # and thus not preventing the modification of fields.
                if value is False:
                    # XXX to remove once server domains are fixed
                    value = None
                setdefault = True
                if record.group.domain:
                    original_domain = merge(record.group.domain)
                else:
                    original_domain = merge(domain)
                domain_readonly = original_domain[0] == 'AND'
                if '.' in leftpart:
                    recordpart, localpart = leftpart.split('.', 1)
                    constraintfields = set()
                    if domain_readonly:
                        for leaf in localize_domain(original_domain[1:]):
                            constraintfields.add(leaf[0])
                    if localpart != 'id' or recordpart not in constraintfields:
                        setdefault = False
                if setdefault and not pre_validate:
                    self.set_client(record, value)
                    state_attrs['domain_readonly'] = domain_readonly
            if not eval_domain(domain, EvalEnvironment(record)):
                invalid = domain
        state_attrs['invalid'] = invalid
        return not invalid

    def set(self, record, value):
        record.value[self.name] = value

    def get(self, record):
        return record.value.get(self.name, self._default)

    def get_eval(self, record):
        return self.get(record)

    def get_on_change_value(self, record):
        return self.get_eval(record)

    def set_client(self, record, value, force_change=False):
        previous_value = self.get(record)
        self.set(record, value)
        if previous_value != self.get(record):
            self.sig_changed(record)
            record.validate(softvalidation=True)
            record.set_modified(self.name)
        elif force_change:
            self.sig_changed(record)
            record.validate(softvalidation=True)
            record.set_modified()

    def get_client(self, record):
        return self.get(record)

    def set_default(self, record, value):
        self.set(record, value)
        record.modified_fields.setdefault(self.name)

    def set_on_change(self, record, value):
        record.modified_fields.setdefault(self.name)
        self.set(record, value)

    def state_set(self, record, states=('readonly', 'required', 'invisible')):
        state_changes = record.expr_eval(self.attrs.get('states', {}))
        for key in states:
            if key == 'readonly' and self.attrs.get(key, False):
                continue
            if key in state_changes:
                self.get_state_attrs(record)[key] = state_changes[key]
            elif key in self.attrs:
                self.get_state_attrs(record)[key] = self.attrs[key]
        if (record.group.readonly
                or self.get_state_attrs(record).get('domain_readonly')
                or record.parent_name == self.name):
            self.get_state_attrs(record)['readonly'] = True

    def get_state_attrs(self, record):
        if self.name not in record.state_attrs:
            record.state_attrs[self.name] = self.attrs.copy()
        if record.group.readonly or record.readonly:
            record.state_attrs[self.name]['readonly'] = True
        return record.state_attrs[self.name]

    def get_timestamp(self, record):
        return {}


class CharField(Field):
    _default = ''

    def set(self, record, value):
        if self.attrs.get('strip') and value:
            if self.attrs['strip'] == 'leading':
                value = value.lstrip()
            elif self.attrs['strip'] == 'trailing':
                value = value.rstrip()
            else:
                value = value.strip()
        super().set(record, value)

    def get(self, record):
        return super(CharField, self).get(record) or self._default

    def set_client(self, record, value, force_change=False):
        if isinstance(value, bytes):
            try:
                value = guess_decode(value)
            except UnicodeDecodeError:
                logger.warning(
                    "The encoding can not be guessed for field '%(name)s'",
                    {'name': self.name})
                value = None
        super().set_client(record, value, force_change)


class SelectionField(Field):

    _default = None

    def set_client(self, record, value, force_change=False):
        record.value.pop(self.name + ':string', None)
        super().set_client(record, value, force_change=force_change)


class MultiSelectionField(SelectionField):

    _default = None
    _single_value = False

    def get(self, record):
        value = super().get(record)
        if not value:
            value = self._default
        else:
            value.sort()
        return value

    def get_eval(self, record):
        value = super().get_eval(record)
        if value is None:
            value = []
        return value

    def set_client(self, record, value, force_change=False):
        if value is None:
            value = []
        if isinstance(value, str):
            value = [value]
        if value:
            value = sorted(value)
        super().set_client(record, value, force_change=force_change)


class DateTimeField(Field):

    _default = None

    def set_client(self, record, value, force_change=False):
        if isinstance(value, datetime.time):
            current_value = self.get_client(record)
            if current_value:
                value = datetime.datetime.combine(
                    current_value.date(), value)
            else:
                value = None
        elif value and not isinstance(value, datetime.datetime):
            current_value = self.get_client(record)
            if current_value:
                time = current_value.time()
            else:
                time = datetime.time()
            value = datetime.datetime.combine(value, time)
        if value:
            value = common.untimezoned_date(value)
        super(DateTimeField, self).set_client(record, value,
            force_change=force_change)

    def get_client(self, record):
        value = super(DateTimeField, self).get_client(record)
        if value:
            return common.timezoned_date(value)

    def date_format(self, record):
        context = self.get_context(record)
        return common.date_format(context.get('date_format'))

    def time_format(self, record):
        return record.expr_eval(self.attrs['format'])


class DateField(Field):

    _default = None

    def set_client(self, record, value, force_change=False):
        if isinstance(value, datetime.datetime):
            assert value.time() == datetime.time()
            value = value.date()
        super(DateField, self).set_client(record, value,
            force_change=force_change)

    def date_format(self, record):
        context = self.get_context(record)
        return common.date_format(context.get('date_format'))


class TimeField(Field):

    _default = None

    def _is_empty(self, record):
        return self.get(record) is None

    def set_client(self, record, value, force_change=False):
        if isinstance(value, datetime.datetime):
            value = value.time()
        super(TimeField, self).set_client(record, value,
            force_change=force_change)

    def time_format(self, record):
        return record.expr_eval(self.attrs['format'])


class TimeDeltaField(Field):

    _default = None

    def _is_empty(self, record):
        return self.get(record) is None

    def converter(self, group):
        return group.context.get(self.attrs.get('converter'))

    def set_client(self, record, value, force_change=False):
        if isinstance(value, str):
            value = common.timedelta.parse(value, self.converter(record.group))
        super(TimeDeltaField, self).set_client(
            record, value, force_change=force_change)

    def get_client(self, record):
        value = super(TimeDeltaField, self).get_client(record)
        return common.timedelta.format(value, self.converter(record.group))


class FloatField(Field):
    _default = None

    def __init__(self, attrs):
        super().__init__(attrs)
        self._digits = {}
        self._symbol = {}

    def _is_empty(self, record):
        return self.get(record) is None

    def get(self, record):
        return record.value.get(self.name, self._default)

    def digits(self, record, factor=1):
        digits = record.expr_eval(self.attrs.get('digits'))
        if isinstance(digits, str):
            if digits not in record.group.fields:
                return
            digits_field = record.group.fields[digits]
            digits_name = digits_field.attrs.get('relation')
            digits_id = digits_field.get(record)
            if digits_name and digits_id is not None and digits_id >= 0:
                if digits_id in self._digits:
                    digits = self._digits[digits_id]
                else:
                    try:
                        digits = RPCExecute(
                            'model', digits_name, 'get_digits', digits_id)
                    except RPCException:
                        logger.warn(
                            "Fail to fetch digits for %s,%s",
                            digits_name, digits_id)
                        return
                    self._digits[digits_id] = digits
            else:
                return
        if not digits or any(d is None for d in digits):
            return
        shift = int(round(math.log(abs(factor), 10)))
        return (digits[0] + shift, digits[1] - shift)

    def get_symbol(self, record, symbol):
        if record and symbol in record.group.fields:
            value = self.get(record) or 0
            sign = 1
            if value < 0:
                sign = -1
            elif value == 0:
                sign = 0
            symbol_field = record.group.fields[symbol]
            symbol_name = symbol_field.attrs.get('relation')
            symbol_id = symbol_field.get(record)
            if symbol_name and symbol_id is not None and symbol_id >= 0:
                if symbol_id in self._symbol:
                    return self._symbol[symbol_id]
                try:
                    result = RPCExecute(
                        'model', symbol_name, 'get_symbol', symbol_id, sign,
                        context=record.get_context())
                    self._symbol[symbol_id] = result
                    return result
                except RPCException:
                    logger.warn(
                        "Fail to fetch symbol for %s,%s",
                        symbol_name, symbol_id)
        return '', 1

    def convert(self, value):
        if value is None:
            return None
        if isinstance(value, str):
            value = locale.delocalize(
                value, self.attrs.get('monetary', False))
        try:
            return self._convert(value)
        except ValueError:
            return self._default
    _convert = float

    def apply_factor(self, record, value, factor):
        if value is not None:
            value /= factor
            digits = self.digits(record)
            if digits:
                value = round(value, digits[1])
            value = self.convert(value)
        return value

    def set_client(self, record, value, force_change=False, factor=1):
        value = self.apply_factor(record, self.convert(value), factor)
        super(FloatField, self).set_client(record, value,
            force_change=force_change)

    def get_client(self, record, factor=1, grouping=True):
        value = record.value.get(self.name)
        if value is not None:
            digits = self.digits(record, factor=factor)
            d = value * factor
            if not isinstance(d, Decimal):
                d = Decimal(repr(d))
            if digits:
                p = int(digits[1])
            elif d == d.to_integral_value():
                p = 0
            else:
                p = -int(d.as_tuple().exponent)
            monetary = self.attrs.get('monetary', False)
            return locale.localize(
                '{0:.{1}f}'.format(d, p), grouping, monetary)
        else:
            return ''


class NumericField(FloatField):

    def convert(self, value):
        try:
            return super().convert(value)
        except decimal.InvalidOperation:
            return self._default
    _convert = Decimal

    def set_client(self, record, value, force_change=False, factor=1):
        return super(NumericField, self).set_client(record, value,
            force_change=force_change, factor=Decimal(str(factor)))

    def get_client(self, record, factor=1, grouping=True):
        return super(NumericField, self).get_client(record,
            factor=Decimal(str(factor)), grouping=grouping)


class IntegerField(FloatField):

    _convert = int

    def set_client(self, record, value, force_change=False, factor=1):
        return super(IntegerField, self).set_client(record, value,
            force_change=force_change, factor=int(factor))

    def get_client(self, record, factor=1, grouping=True):
        return super(IntegerField, self).get_client(
            record, factor=int(factor), grouping=grouping)


class BooleanField(Field):

    _default = False

    def set_client(self, record, value, force_change=False):
        value = bool(value)
        super(BooleanField, self).set_client(record, value,
            force_change=force_change)

    def get(self, record):
        return bool(record.value.get(self.name))

    def get_client(self, record):
        return bool(record.value.get(self.name))


class M2OField(Field):
    '''
    internal = (id, name)
    '''

    _default = None

    def _is_empty(self, record):
        return self.get(record) is None

    def get_client(self, record):
        rec_name = record.value.get(self.name + '.', {}).get('rec_name')
        if rec_name is None:
            self.set(record, self.get(record))
            rec_name = record.value.get(self.name + '.', {}).get('rec_name')
        return rec_name or ''

    def set_client(self, record, value, force_change=False):
        if isinstance(value, (tuple, list)):
            value, rec_name = value
        else:
            if value == self.get(record):
                rec_name = record.value.get(
                    self.name + '.', {}).get('rec_name', '')
            else:
                rec_name = ''
        if value and value < 0 and self.name != record.parent_name:
            value, rec_name = None, ''
        record.value.setdefault(self.name + '.', {})['rec_name'] = rec_name
        super(M2OField, self).set_client(record, value,
            force_change=force_change)

    def set(self, record, value):
        rec_name = record.value.get(self.name + '.', {}).get('rec_name') or ''
        if not rec_name and value is not None and value >= 0:
            try:
                result, = RPCExecute('model', self.attrs['relation'], 'read',
                    [value], ['rec_name'])
            except RPCException:
                return
            rec_name = result['rec_name'] or ''
        record.value.setdefault(self.name + '.', {})['rec_name'] = rec_name
        record.value[self.name] = value

    def get_context(self, record, record_context=None, local=False):
        context = super(M2OField, self).get_context(
            record, record_context=record_context, local=local)
        if self.attrs.get('datetime_field'):
            context['_datetime'] = record.get_eval(
                )[self.attrs.get('datetime_field')]
        return context

    def validation_domains(self, record, pre_validate=None):
        screen_domain, attr_domain = self.domains_get(record, pre_validate)
        return screen_domain

    def domain_get(self, record):
        screen_domain, attr_domain = self.domains_get(record)
        return concat(localize_domain(inverse_leaf(screen_domain), self.name),
            attr_domain)

    def get_on_change_value(self, record):
        if record.parent_name == self.name and record.parent:
            return record.parent.get_on_change_value(
                skip={record.group.child_name})
        return super(M2OField, self).get_on_change_value(record)


class O2OField(M2OField):
    pass


class O2MField(Field):
    '''
    internal = Group of the related objects
    '''

    _default = None
    _single_value = False

    def __init__(self, attrs):
        super(O2MField, self).__init__(attrs)

    def _set_default_value(self, record, fields=None):
        if record.value.get(self.name) is not None:
            return
        from .group import Group
        parent_name = self.attrs.get('relation_field', '')
        fields = fields or {}
        group = Group(self.attrs['relation'], fields,
                parent=record,
                parent_name=parent_name,
                child_name=self.name,
                parent_datetime_field=self.attrs.get('datetime_field'))
        if not fields and record.model_name == self.attrs['relation']:
            group.fields = record.group.fields
        record.value[self.name] = group

    def get_client(self, record):
        self._set_default_value(record)
        return record.value.get(self.name)

    def get(self, record):
        if record.value.get(self.name) is None:
            return []
        record_removed = record.value[self.name].record_removed
        record_deleted = record.value[self.name].record_deleted
        result = []
        parent_name = self.attrs.get('relation_field', '')
        to_add = []
        to_create = []
        to_write = []
        for record2 in record.value[self.name]:
            if record2 in record_removed or record2 in record_deleted:
                continue
            if record2.id >= 0:
                if record2.modified:
                    values = record2.get()
                    values.pop(parent_name, None)
                    if values:
                        to_write.extend(([record2.id], values))
                    to_add.append(record2.id)
            else:
                values = record2.get()
                values.pop(parent_name, None)
                to_create.append(values)
        if to_add:
            result.append(('add', to_add))
        if to_create:
            result.append(('create', to_create))
        if to_write:
            result.append(('write',) + tuple(to_write))
        if record_removed:
            result.append(('remove', [x.id for x in record_removed]))
        if record_deleted:
            result.append(('delete', [x.id for x in record_deleted]))
        return result

    def get_timestamp(self, record):
        if record.value.get(self.name) is None:
            return {}
        result = {}
        record_modified = (r for r in record.value[self.name] if r.modified)
        for record2 in chain(record_modified,
                record.value[self.name].record_removed,
                record.value[self.name].record_deleted):
            result.update(record2.get_timestamp())
        return result

    def get_eval(self, record):
        if record.value.get(self.name) is None:
            return []
        record_removed = record.value[self.name].record_removed
        record_deleted = record.value[self.name].record_deleted
        return [x.id for x in record.value[self.name]
            if x not in record_removed and x not in record_deleted]

    def get_on_change_value(self, record):
        result = []
        if record.value.get(self.name) is None:
            return []
        for record2 in record.value[self.name]:
            if not (record2.deleted or record2.removed):
                result.append(
                    record2.get_on_change_value(
                        skip={self.attrs.get('relation_field', '')}))
        return result

    def _set_value(self, record, value, default=False, modified=False):
        self._set_default_value(record)
        group = record.value[self.name]
        if value is None:
            value = []
        if not value or isinstance(value[0], int):
            mode = 'list ids'
        else:
            mode = 'list values'

        if mode == 'list values':
            context = self.get_context(record)
            field_names = set(f for v in value for f in v
                if f not in group.fields and '.' not in f)
            if field_names:
                try:
                    fields = RPCExecute('model', self.attrs['relation'],
                        'fields_get', list(field_names), context=context)
                except RPCException:
                    return
                group.load_fields(fields)

        if mode == 'list ids':
            records_to_remove = [r for r in group if r.id not in value]
            for record_to_remove in records_to_remove:
                group.remove(record_to_remove, remove=True, modified=False)
            group.load(value, modified=modified or default)
        else:
            for vals in value:
                if 'id' in vals:
                    new_record = group.get(vals['id'])
                    if not new_record:
                        new_record = group.new(
                            default=False, obj_id=vals['id'])
                else:
                    new_record = group.new(default=False)
                if default:
                    # Don't validate as parent will validate
                    new_record.set_default(
                        vals, modified=False, validate=False)
                    group.add(new_record, modified=False)
                else:
                    new_record.set(vals, modified=False)
                    group.append(new_record)
            # Trigger modified only once
            group.record_modified()

    def set(self, record, value, _default=False):
        group = record.value.get(self.name)
        fields = {}
        if group is not None:
            fields = group.fields.copy()
            # Unconnect to prevent infinite loop
            group.parent = None
            group.destroy()
        elif record.model_name == self.attrs['relation']:
            fields = record.group.fields
        if fields:
            fields = dict((fname, field.attrs)
                for fname, field in fields.items())

        record.value[self.name] = None
        self._set_default_value(record, fields=fields)
        group = record.value[self.name]

        # Prevent to trigger group-cleared
        group.parent = None
        self._set_value(record, value, default=_default)
        group.parent = record

    def set_client(self, record, value, force_change=False):
        # domain inversion could try to set None as value
        if value is None:
            value = []
        # domain inversion could try to set id as value
        if isinstance(value, int):
            value = [value]

        previous_ids = self.get_eval(record)
        # The order of the ids is not significant
        modified = set(previous_ids) != set(value)
        self._set_value(record, value, modified=modified)
        if modified:
            self.sig_changed(record)
            record.validate(softvalidation=True)
            record.set_modified(self.name)
        elif force_change:
            self.sig_changed(record)
            record.validate(softvalidation=True)
            record.set_modified()

    def set_default(self, record, value):
        self.set(record, value, _default=True)
        record.modified_fields.setdefault(self.name)

    def set_on_change(self, record, value):
        record.modified_fields.setdefault(self.name)
        self._set_default_value(record)
        if isinstance(value, (list, tuple)):
            self._set_value(record, value, modified=True)
            return

        if value and (value.get('add') or value.get('update')):
            context = self.get_context(record)
            fields = record.value[self.name].fields
            values = chain(value.get('update', []),
                (d for _, d in value.get('add', [])))
            field_names = set(f for v in values
                for f in v if f not in fields and f != 'id' and '.' not in f)
            if field_names:
                try:
                    new_fields = RPCExecute('model', self.attrs['relation'],
                        'fields_get', list(field_names), context=context)
                except RPCException:
                    return
            else:
                new_fields = {}

        group = record.value[self.name]
        if value and value.get('delete'):
            for record_id in value['delete']:
                record2 = group.get(record_id)
                if record2 is not None:
                    group.remove(
                        record2, remove=False, modified=False,
                        force_remove=False)
        if value and value.get('remove'):
            for record_id in value['remove']:
                record2 = group.get(record_id)
                if record2 is not None:
                    group.remove(
                        record2, remove=True, modified=False,
                        force_remove=False)

        if value and (value.get('add') or value.get('update', [])):
            vals_to_set = {}
            # First set already added fields to prevent triggering a
            # second on_change call
            for vals in value.get('update', []):
                if 'id' not in vals:
                    continue
                record2 = group.get(vals['id'])
                if record2 is not None:
                    vals_to_set = {
                        k: v for k, v in vals.items() if k not in new_fields}
                    record2.set_on_change(vals_to_set)

            record.value[self.name].add_fields(new_fields)
            for index, vals in value.get('add', []):
                new_record = None
                id_ = vals.pop('id', None)
                if id_ is not None:
                    new_record = group.get(id_)
                if not new_record:
                    new_record = group.new(obj_id=id_, default=False)
                group.add(new_record, index, modified=False)
                new_record.set_on_change(vals)

            for vals in value.get('update', []):
                if 'id' not in vals:
                    continue
                record2 = group.get(vals['id'])
                if record2 is not None:
                    to_set = {
                        k: v for k, v in vals.items
                        if k not in vals_to_set}
                    record2.set_on_change(to_set)

    def validation_domains(self, record, pre_validate=None):
        screen_domain, attr_domain = self.domains_get(record, pre_validate)
        return screen_domain

    def validate(self, record, softvalidation=False, pre_validate=None):
        invalid = False
        ldomain = localize_domain(domain_inversion(
                record.group.clean4inversion(pre_validate or []), self.name,
                EvalEnvironment(record)), self.name)
        if isinstance(ldomain, bool):
            if ldomain:
                ldomain = []
            else:
                ldomain = [('id', '=', None)]
        for record2 in record.value.get(self.name, []):
            if not record2.loaded and record2.id >= 0 and not pre_validate:
                continue
            if not record2.validate(softvalidation=softvalidation,
                    pre_validate=ldomain):
                invalid = 'children'
        test = super(O2MField, self).validate(record, softvalidation,
            pre_validate)
        if test and invalid:
            self.get_state_attrs(record)['invalid'] = invalid
            return False
        return test

    def state_set(self, record, states=('readonly', 'required', 'invisible')):
        self._set_default_value(record)
        super(O2MField, self).state_set(record, states=states)

    def get_removed_ids(self, record):
        return [x.id for x in record.value[self.name].record_removed]

    def domain_get(self, record):
        screen_domain, attr_domain = self.domains_get(record)
        # Forget screen_domain because it only means at least one record
        # and not all records
        return attr_domain


class M2MField(O2MField):

    def get_on_change_value(self, record):
        return self.get_eval(record)


class ReferenceField(Field):

    _default = None

    def _is_empty(self, record):
        result = super(ReferenceField, self)._is_empty(record)
        if not result and (record.value[self.name] is None
                or record.value[self.name][1] < 0):
            result = True
        return result

    def get_client(self, record):
        if record.value.get(self.name):
            model, _ = record.value[self.name]
            name = record.value.get(self.name + '.', {}).get('rec_name') or ''
            return model, name
        else:
            return None

    def get(self, record):
        if (record.value.get(self.name)
                and record.value[self.name][0]
                and record.value[self.name][1] is not None
                and record.value[self.name][1] >= -1):
            return ','.join(map(str, record.value[self.name]))
        return None

    def set_client(self, record, value, force_change=False):
        if value:
            if isinstance(value, str):
                value = value.split(',')
            ref_model, ref_id = value
            if isinstance(ref_id, (tuple, list)):
                ref_id, rec_name = ref_id
            else:
                if ref_id:
                    try:
                        ref_id = int(ref_id)
                    except ValueError:
                        pass
                if '%s,%s' % (ref_model, ref_id) == self.get(record):
                    rec_name = record.value.get(
                        self.name + '.', {}).get('rec_name') or ''
                else:
                    rec_name = ''
            record.value.setdefault(self.name + '.', {})['rec_name'] = rec_name
            value = (ref_model, ref_id)
        super(ReferenceField, self).set_client(record, value,
            force_change=force_change)

    def set(self, record, value):
        if not value:
            record.value[self.name] = self._default
            return
        if isinstance(value, str):
            ref_model, ref_id = value.split(',')
            if not ref_id:
                ref_id = None
            else:
                try:
                    ref_id = int(ref_id)
                except ValueError:
                    pass
        else:
            ref_model, ref_id = value
        rec_name = record.value.get(self.name + '.', {}).get('rec_name') or ''
        if ref_model and ref_id is not None and ref_id >= 0:
            if not rec_name and ref_id >= 0:
                try:
                    result, = RPCExecute('model', ref_model, 'read', [ref_id],
                        ['rec_name'])
                except RPCException:
                    return
                rec_name = result['rec_name']
        elif ref_model:
            rec_name = ''
        else:
            rec_name = str(ref_id) if ref_id is not None else ''
        record.value[self.name] = ref_model, ref_id
        record.value.setdefault(self.name + '.', {})['rec_name'] = rec_name

    def get_context(self, record, record_context=None, local=False):
        context = super(ReferenceField, self).get_context(
            record, record_context, local=local)
        if self.attrs.get('datetime_field'):
            context['_datetime'] = record.get_eval(
                )[self.attrs.get('datetime_field')]
        return context

    def get_on_change_value(self, record):
        if record.parent_name == self.name and record.parent:
            return record.parent.model_name, record.parent.get_on_change_value(
                skip={record.group.child_name})
        return super(ReferenceField, self).get_on_change_value(record)

    def validation_domains(self, record, pre_validate=None):
        screen_domain, attr_domain = self.domains_get(record, pre_validate)
        return screen_domain

    def domains_get(self, record, pre_validate=None):
        if record.value.get(self.name):
            model = record.value[self.name][0]
        else:
            model = None
        screen_domain, attr_domain = super().domains_get(
            record, pre_validate=pre_validate)
        attr_domain = attr_domain.get(model, [])
        return screen_domain, attr_domain

    def domain_get(self, record):
        if record.value.get(self.name):
            model = record.value[self.name][0]
        else:
            model = None
        screen_domain, attr_domain = self.domains_get(record)
        screen_domain = filter_leaf(screen_domain, self.name, model)
        screen_domain = prepare_reference_domain(screen_domain, self.name)
        return concat(localize_domain(
                screen_domain, self.name, strip_target=True), attr_domain)

    def get_search_order(self, record):
        order = super().get_search_order(record)
        if order is not None:
            if record.value.get(self.name):
                model = record.value[self.name][0]
            else:
                model = None
            order = order.get(model)
        return order

    def get_models(self, record):
        screen_domain, attr_domain = self.domains_get(record)
        screen_domain = prepare_reference_domain(screen_domain, self.name)
        return extract_reference_models(
            concat(screen_domain, attr_domain), self.name)


class _FileCache(object):
    def __init__(self, data=None):
        _, filename = tempfile.mkstemp(prefix='tryton_')
        self.path = Path(filename)
        self.suffixes = {}
        if data:
            with open(self.path, 'wb') as fp:
                fp.write(data)

    @property
    def data(self):
        with open(self.path, 'rb') as fp:
            return fp.read()

    def __del__(self):
        try:
            os.remove(self.path)
        except IOError:
            pass
        for path in self.suffixes.values():
            try:
                os.remove(path)
            except IOError:
                pass

    def with_suffix(self, suffix):
        if suffix in self.suffixes:
            return self.suffixes[suffix]
        _, filename = tempfile.mkstemp(prefix='tryton_', suffix=suffix)
        self.suffixes[suffix] = path = Path(filename)
        with open(path, 'wb') as fp:
            fp.write(self.data)
        return path


class BinaryField(Field):

    _default = None

    def _set_file_cache(self, record, data):
        if isinstance(data, str):
            data = data.encode('utf-8')
        file_cache = _FileCache(data)
        self.set(record, file_cache)
        return file_cache

    def get(self, record):
        result = record.value.get(self.name, self._default)
        if isinstance(result, _FileCache):
            try:
                result = result.data
            except IOError:
                result = self.get_data(record)
        return result

    def get_client(self, record):
        return self.get(record)

    def set_client(self, record, value, force_change=False):
        self._set_file_cache(record, value or b'')
        self.sig_changed(record)
        record.validate(softvalidation=True)
        record.set_modified(self.name)

    def get_size(self, record):
        result = record.value.get(self.name) or 0
        if isinstance(result, _FileCache):
            result = os.stat(result.path).st_size
        elif isinstance(result, (str, bytes)):
            result = len(result)
        return result

    def get_data(self, record):
        if not isinstance(record.value.get(self.name),
                (str, bytes, _FileCache)):
            if record.id < 0:
                return b''
            context = record.get_context()
            try:
                values, = RPCExecute('model', record.model_name, 'read',
                    [record.id], [self.name], context=context)
            except RPCException:
                return b''
            self._set_file_cache(record, values[self.name] or b'')
        return self.get(record)

    def get_filename(self, record, suffix=None):
        data = self.get_data(record)
        file_cache = record.value.get(self.name)
        if not isinstance(file_cache, _FileCache):
            file_cache = self._set_file_cache(record, data)
        if suffix:
            filename = file_cache.with_suffix(suffix)
        else:
            filename = file_cache.path
        return filename


class DictField(Field):

    _default = {}
    _single_value = False

    def __init__(self, attrs):
        super(DictField, self).__init__(attrs)
        self.keys = {}

    def get(self, record):
        return (super().get(record) or self._default).copy()

    def get_client(self, record):
        return super().get_client(record)

    def validation_domains(self, record, pre_validate=None):
        screen_domain, attr_domain = self.domains_get(record, pre_validate)
        return screen_domain

    def domain_get(self, record):
        screen_domain, attr_domain = self.domains_get(record)
        return concat(localize_domain(screen_domain), attr_domain)

    def date_format(self, record):
        context = self.get_context(record)
        return common.date_format(context.get('date_format'))

    def time_format(self, record):
        return '%X'

    def add_keys(self, keys, record):
        schema_model = self.attrs['schema_model']
        context = self.get_context(record)
        domain = self.domain_get(record)
        batchlen = min(10, CONFIG['client.limit'])
        for i in range(0, len(keys), batchlen):
            sub_keys = keys[i:i + batchlen]
            try:
                values = RPCExecute('model', schema_model, 'search_get_keys',
                    [('name', 'in', sub_keys), domain], CONFIG['client.limit'],
                    context=context)
            except RPCException:
                values = []
            if not values:
                continue
            self.keys.update({k['name']: k for k in values})

    def add_new_keys(self, key_ids, record):
        schema_model = self.attrs['schema_model']
        context = self.get_context(record)
        try:
            new_fields = RPCExecute('model', schema_model,
                'get_keys', key_ids, context=context)
        except RPCException:
            new_fields = []

        new_keys = []
        for new_field in new_fields:
            name = new_field['name']
            new_keys.append(name)
            self.keys[name] = new_field

        return new_keys

    def validate(self, record, softvalidation=False, pre_validate=None):
        valid = super(DictField, self).validate(
            record, softvalidation, pre_validate)

        if self.attrs.get('readonly'):
            return valid

        decoder = PYSONDecoder()
        field_value = self.get_eval(record)
        domain = []
        for key in field_value:
            if key not in self.keys:
                continue
            key_domain = self.keys[key].get('domain')
            if key_domain:
                domain.append(decoder.decode(key_domain))

        valid_value = eval_domain(domain, field_value)
        if not valid_value:
            self.get_state_attrs(record)['invalid'] = 'domain'

        return valid and valid_value


TYPES = {
    'char': CharField,
    'integer': IntegerField,
    'float': FloatField,
    'numeric': NumericField,
    'many2one': M2OField,
    'many2many': M2MField,
    'one2many': O2MField,
    'reference': ReferenceField,
    'selection': SelectionField,
    'multiselection': MultiSelectionField,
    'boolean': BooleanField,
    'datetime': DateTimeField,
    'date': DateField,
    'time': TimeField,
    'timestamp': DateTimeField,
    'timedelta': TimeDeltaField,
    'one2one': O2OField,
    'binary': BinaryField,
    'dict': DictField,
}
