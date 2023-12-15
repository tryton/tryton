# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.model import DictSchemaMixin, ModelSQL, ModelView, fields
from trytond.pool import Pool
from trytond.pyson import Eval, If


class ModelViewChangedValues(ModelView):
    'ModelView Changed Values'
    __name__ = 'test.modelview.changed_values'
    name = fields.Char('Name')
    target = fields.Many2One('test.modelview.changed_values.target', 'Target')
    stored_target = fields.Many2One(
        'test.modelview.changed_values.stored_target', "Stored Target")
    ref_target = fields.Reference('Target Reference', [
            ('test.modelview.changed_values.target', 'Target'),
            ])
    targets = fields.One2Many('test.modelview.changed_values.target', 'parent',
        'Targets')
    m2m_targets = fields.Many2Many('test.modelview.changed_values.target',
        None, None, 'Targets')
    multiselection = fields.MultiSelection([
            ('a', 'A'), ('b', 'B'),
            ], "MultiSelection")
    dictionary = fields.Dict(
        'test.modelview.changed_values.dictionary', "Dictionary")
    m2m_function = fields.Function(fields.Many2Many(
            'test.modelview.changed_values.target', None, None, "Targets"),
        'on_change_with_m2m_function')

    def on_change_with_m2m_function(self, name=None):
        return


class ModelViewChangedValuesDictSchema(DictSchemaMixin, ModelSQL):
    'ModelView Changed Values Dict Schema'
    __name__ = 'test.modelview.changed_values.dictionary'


class ModelViewChangedValuesTarget(ModelView):
    'ModelView Changed Values Target'
    __name__ = 'test.modelview.changed_values.target'
    name = fields.Char('Name')
    parent = fields.Many2One('test.modelview.changed_values', 'Parent')


class ModelViewChangedValuesStoredTarget(ModelSQL):
    "ModelSQL Changed Values Target"
    __name__ = 'test.modelview.changed_values.stored_target'
    name = fields.Char("Name")


class ModelViewStoredChangedValues(ModelSQL, ModelView):
    "ModelView Stored Changed Values Stored"
    __name__ = 'test.modelview.stored.changed_values'
    targets = fields.One2Many(
        'test.modelview.stored.changed_values.target', 'parent', "Targets")


class ModelViewStoredChangedValuesTarget(ModelSQL, ModelView):
    "ModelSQL Stored Changed Values Target"
    __name__ = 'test.modelview.stored.changed_values.target'
    name = fields.Char("Name")
    parent = fields.Many2One('test.modelview.stored.changed_values', "Parent")


class ModelViewButton(ModelView):
    'ModelView Button'
    __name__ = 'test.modelview.button'
    value = fields.Integer("Value")

    @classmethod
    def __setup__(cls):
        super(ModelViewButton, cls).__setup__()
        cls._buttons = {
            'test': {},
            }

    @classmethod
    @ModelView.button
    def test(cls, records):
        cls.test_non_decorated(records)

    @classmethod
    def test_non_decorated(cls, records):
        pass


class ModelViewButtonDepends(ModelView):
    'ModelView Button Depends'
    __name__ = 'test.modelview.button_depends'
    value = fields.Integer("Value")

    @classmethod
    def __setup__(cls):
        super(ModelViewButtonDepends, cls).__setup__()
        cls._buttons = {
            'test': {
                'depends': ['value'],
                },
            }

    @classmethod
    @ModelView.button
    def test(cls, records):
        pass


class ModelViewButtonAction(ModelView):
    'ModelView Button Action'
    __name__ = 'test.modelview.button_action'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._buttons = {
            'test': {},
            }

    @classmethod
    @ModelView.button_action('tests.test_modelview_button_action')
    def test(cls, records):
        pass

    @classmethod
    @ModelView.button_action('tests.test_modelview_button_action')
    def test_update(cls, records):
        return {'url': 'http://www.tryton.org/'}


class ModelViewButtonChange(ModelView):
    "ModelView Button Change"
    __name__ = 'test.modelview.button_change'

    name = fields.Char("Name")
    extra = fields.Char("Extra")

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._buttons = {
            'test': {}
            }

    @ModelView.button_change('name', methods=['extra_method'])
    def test(self):
        self.extra_method()

    @fields.depends('extra')
    def extra_method(self):
        pass


class ModelViewLink(ModelView):
    "ModelView Link"
    __name__ = 'test.modelview.link'


class ModelViewLinkTarget(ModelSQL):
    "ModelView Link Target"
    __name__ = 'test.modelview.link.target'


class ModelViewRPC(ModelView):
    'ModelView RPC'
    __name__ = 'test.modelview.rpc'

    selection = fields.Selection([('a', 'A')], 'Selection')
    computed_selection = fields.Selection(
        'get_selection', 'Computed Selection')
    function_selection = fields.Function(
        fields.Selection('get_function_selection', 'Function Selection'),
        'function_selection_getter')

    reference = fields.Reference('Reference', selection=[('a', 'A')])
    computed_reference = fields.Reference(
        'Computed reference', selection='get_reference')
    function_reference = fields.Function(
        fields.Reference('Function Reference',
            selection='get_function_reference'),
        'function_reference_getter')

    integer = fields.Integer('Integer')
    float = fields.Float('Float')
    char = fields.Char('Char')

    @fields.depends('selection')
    def on_change_with_integer(self):
        pass

    @fields.depends('reference')
    def on_change_float(self):
        pass

    @fields.depends('integer')
    def autocomplete_char(self):
        pass

    @classmethod
    def get_selection(cls):
        pass

    @classmethod
    def get_function_selection(cls):
        pass

    @classmethod
    def get_reference(cls):
        pass

    @classmethod
    def get_function_reference(cls):
        pass


class ModelViewEmptyPage(ModelView):
    'ModelView Empty Page'
    __name__ = 'test.modelview.empty_page'


class ModelViewCircularDepends(ModelView):
    'ModelView Circular Depends'
    __name__ = 'test.modelview.circular_depends'

    foo = fields.Char("Char", depends=['bar'])
    bar = fields.Char("Char", depends=['foobar'])
    foobar = fields.Char("Char", depends=['foo'])


class ModeViewDependsDepends(ModelView):
    "ModelView depends of depends"
    __name__ = 'test.modelview.depends_depends'

    foo = fields.Char("Foo", depends=['bar'])
    bar = fields.Char("Bar", depends=['baz'])
    baz = fields.Char("Baz")


class ModelViewViewAttributes(ModelView):
    'ModelView View Attributes'
    __name__ = 'test.modelview.view_attributes'

    foo = fields.Char("Char")

    @classmethod
    def view_attributes(cls):
        return super().view_attributes() + [
            ('//field[@name="foo"]',
                'visual', If(Eval('foo') == 'foo', 'danger', '')),
            ]


class ModelViewViewAttributesDepends(ModelView):
    'ModelView View Attributes Depends'
    __name__ = 'test.modelview.view_attributes_depends'

    foo = fields.Char("Char")
    bar = fields.Char("Char")

    @classmethod
    def view_attributes(cls):
        return super().view_attributes() + [
            ('//field[@name="foo"]',
                'visual', If(Eval('bar') == 'foo', 'danger', ''), ['bar']),
            ]


class ModelViewStatesDepends(ModelView):
    "ModelView States Depends"
    __name__ = 'test.modelview.states_depends'

    foo = fields.Char("Foo",
        states={
            'invisible': Eval('bar', True),
            'readonly': Eval('baz', True),
            },
        depends=['quux'])
    bar = fields.Boolean("Bar")
    baz = fields.Boolean("Baz")
    quux = fields.Char("Quux")


class ModelViewAutocomplete(ModelView):
    "ModelView Autocomplete"
    __name__ = 'test.modelview.autocomplete'

    name = fields.Char("Name")


class ModelViewAutocompleteStorage(ModelSQL, ModelViewAutocomplete):
    "ModelView Autocomplete Storage"
    __name__ = 'test.modelview.autocomplete.storage'


def register(module):
    Pool.register(
        ModelViewChangedValues,
        ModelViewChangedValuesDictSchema,
        ModelViewChangedValuesTarget,
        ModelViewChangedValuesStoredTarget,
        ModelViewStoredChangedValues,
        ModelViewStoredChangedValuesTarget,
        ModelViewButton,
        ModelViewButtonDepends,
        ModelViewButtonAction,
        ModelViewButtonChange,
        ModelViewLink,
        ModelViewLinkTarget,
        ModelViewRPC,
        ModelViewEmptyPage,
        ModelViewCircularDepends,
        ModeViewDependsDepends,
        ModelViewViewAttributes,
        ModelViewViewAttributesDepends,
        ModelViewStatesDepends,
        ModelViewAutocomplete,
        ModelViewAutocompleteStorage,
        module=module, type_='model')
