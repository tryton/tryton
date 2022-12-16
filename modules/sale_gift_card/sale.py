# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from email.header import Header

from sql import Null
from sql.operators import Equal

from trytond.config import config
from trytond.model import ModelSQL, ModelView, Workflow, Exclude, fields
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, Bool, Id
from trytond.report import Report, get_email
from trytond.sendmail import sendmail_transactional
from trytond.transaction import Transaction

from trytond.modules.company.model import CompanyValueMixin


class Configuration(metaclass=PoolMeta):
    __name__ = 'sale.configuration'

    gift_card_sequence = fields.MultiValue(fields.Many2One(
            'ir.sequence', "Gift Card Sequence",
            domain=[
                ('company', 'in', [
                        Eval('context', {}).get('company', -1), None]),
                ('sequence_type', '=', Id(
                        'sale_gift_card', 'sequence_type_gift_card')),
                ]))

    @classmethod
    def multivalue_model(cls, field):
        pool = Pool()
        if field == 'gift_card_sequence':
            return pool.get('sale.configuration.gift_card.sequence')
        return super().multivalue_model(field)


class ConfigurationGiftCardSequence(ModelSQL, CompanyValueMixin):
    "Gift Card Configuration Sequence"
    __name__ = 'sale.configuration.gift_card.sequence'
    gift_card_sequence = fields.Many2One(
        'ir.sequence', "Gift Card Sequence",
        domain=[
            ('company', 'in', [Eval('company', -1), None]),
            ('sequence_type', '=', Id(
                    'sale_gift_card', 'sequence_type_gift_card')),
            ],
        depends=['company'])


class GiftCard(ModelSQL, ModelView):
    "Gift Card"
    __name__ = 'sale.gift_card'
    _rec_name = 'number'

    _states = {
        'readonly': Bool(Eval('origin')) | Bool(Eval('spent_on')),
        }
    _depends = ['origin']

    number = fields.Char(
        "Number", required=True, states=_states, depends=_depends)
    company = fields.Many2One(
        'company.company', "Company", required=True,
        states=_states, depends=_depends)
    product = fields.Many2One(
        'product.product', "Product", required=True,
        domain=[
            ('gift_card', '=', True),
            ],
        context={
            'company': Eval('company', -1),
            },
        states=_states, depends=_depends + ['company'])
    value = fields.Numeric(
        "Value", digits=(16, Eval('currency_digits', 2)), required=True,
        states=_states, depends=_depends + ['currency_digits'])
    currency = fields.Many2One(
        'currency.currency', "Currency", required=True,
        states=_states, depends=_depends)

    origin = fields.Reference(
        "Origin", selection='get_origin', select=True, readonly=True)
    spent_on = fields.Reference(
        "Spent On", selection='get_spent_on', select=True, readonly=True)

    currency_digits = fields.Function(
        fields.Integer("Currency Digits"), 'on_change_with_currency_digits')

    del _states
    del _depends

    @classmethod
    def __setup__(cls):
        super().__setup__()
        t = cls.__table__()
        cls._sql_constraints = [
            ('number_exclude',
                Exclude(t, (t.number, Equal), (t.company, Equal),
                    where=(t.spent_on == Null)),
                'sale_gift_card.msg_gift_card_number_unique'),
            ]
        cls._order.insert(0, ('number', 'ASC'))

    @classmethod
    def default_company(cls):
        return Transaction().context.get('company')

    @fields.depends('currency')
    def on_change_with_currency_digits(self, name=None):
        if self.currency:
            return self.currency.digits

    @classmethod
    def _get_origin(cls):
        return ['sale.line', 'stock.move']

    @classmethod
    def get_origin(cls):
        pool = Pool()
        Model = pool.get('ir.model')
        return [(None, '')] + [
            (m, Model.get_name(m)) for m in cls._get_origin()]

    @fields.depends('origin', 'value', 'currency')
    def on_change_origin(self):
        pool = Pool()
        SaleLine = pool.get('sale.line')
        StockMove = pool.get('stock.move')
        UoM = pool.get('product.uom')
        if isinstance(self.origin, SaleLine):
            line = self.origin
            self.company = line.sale.company
            self.product = line.product
            if line.unit and line.unit_price and line.product:
                self.value = UoM.compute_price(
                    line.unit, line.unit_price, line.product.default_uom)
                self.currency = line.sale.currency
        elif isinstance(self.origin, StockMove):
            move = self.origin
            self.company = move.company
            self.product = move.product
            if move.uom and move.unit_price:
                self.value = UoM.compute_price(
                    move.uom, move.unit_price, move.product.default_uom)
                self.currency = move.currency
        if self.value and self.currency:
            self.value = self.currency.round(self.value)

    @classmethod
    def _get_spent_on(cls):
        return ['sale.sale']

    @classmethod
    def get_spent_on(cls):
        pool = Pool()
        Model = pool.get('ir.model')
        return [(None, '')] + [
            (m, Model.get_name(m)) for m in cls._get_spent_on()]

    def get_rec_name(self, name):
        if not self.number:
            name = '(%d)' % self.id
        else:
            name = self.number
        return name

    @property
    def _email(self):
        pool = Pool()
        SaleLine = pool.get('sale.line')
        if isinstance(self.origin, SaleLine):
            return self.origin.gift_card_email or self.origin.sale.party.email

    @property
    def _languages(self):
        pool = Pool()
        SaleLine = pool.get('sale.line')
        languages = []
        if isinstance(self.origin, SaleLine):
            lang = self.origin.sale.party.lang
            if lang:
                languages.append(lang)
        return languages

    @classmethod
    def send(cls, gift_cards, from_=None):
        pool = Pool()
        Lang = pool.get('ir.lang')
        if from_ is None:
            from_ = config.get('email', 'from')
        for gift_card in gift_cards:
            email = gift_card._email
            languages = gift_card._languages
            if not languages:
                languages.append(Lang.get())
            msg, title = get_email(
                'sale.gift_card.email', gift_card, languages)
            msg['From'] = from_
            msg['To'] = email
            msg['Subject'] = Header(title, 'utf-8')
            sendmail_transactional(from_, [email], msg)


class GiftCardEmail(Report):
    __name__ = 'sale.gift_card.email'


class Sale(metaclass=PoolMeta):
    __name__ = 'sale.sale'

    gift_cards = fields.One2Many(
        'sale.gift_card', 'spent_on', "Gift Cards",
        domain=[
            ('company', '=', Eval('company', -1)),
            ('currency', '=', Eval('currency', -1)),
            ],
        add_remove=[
            ('spent_on', '=', None),
            ],
        states={
            'readonly': Eval('state') != 'draft',
            },
        depends=['state', 'company', 'currency'])

    @classmethod
    @ModelView.button
    @Workflow.transition('quotation')
    def quote(cls, sales):
        for sale in sales:
            sale.add_return_gift_cards()
        cls.save(sales)
        super().quote(sales)

    def add_return_gift_cards(self):
        lines = list(self.lines)
        for line in self.lines:
            if line.is_gift_card and line.quantity < 0:
                lines.remove(line)
        for gift_card in self.gift_cards:
            lines.append(self.get_return_gift_card_line(gift_card))
        self.lines = lines

    def get_return_gift_card_line(self, gift_card):
        pool = Pool()
        Line = pool.get('sale.line')
        sequence = None
        if self.lines:
            last_line = self.lines[-1]
            if last_line.sequence is not None:
                sequence = last_line.sequence + 1
        return Line(
            sale=self,
            sequence=sequence,
            type='line',
            product=gift_card.product,
            quantity=-1,
            unit=gift_card.product.default_uom,
            unit_price=gift_card.value,
            )

    @classmethod
    @ModelView.button
    def process(cls, sales):
        pool = Pool()
        GiftCard = pool.get('sale.gift_card')
        cls.lock(sales)
        gift_cards = []
        for sale in sales:
            for line in sale.lines:
                cards = line.get_gift_cards()
                if cards:
                    gift_cards.extend(cards)
        GiftCard.save(gift_cards)
        GiftCard.send(gift_cards)
        super().process(sales)


class Line(metaclass=PoolMeta):
    __name__ = 'sale.line'

    gift_cards = fields.One2Many(
        'sale.gift_card', 'origin', "Gift Cards", readonly=True,
        states={
            'invisible': ~Eval('gift_cards', []),
            })
    is_gift_card = fields.Function(
        fields.Boolean("Is Gift Card"), 'on_change_with_is_gift_card')
    is_gift_card_service = fields.Function(
        fields.Boolean("Is Gift Card Service"),
        'on_change_with_is_gift_card_service')
    gift_card_email = fields.Char(
        "Gift Card Email",
        states={
            'invisible': ~Eval('is_gift_card_service', False),
            },
        depends=['is_gift_card_service'],
        help="Leave empty for the customer email.")

    @fields.depends('product')
    def on_change_with_is_gift_card(self, name=None):
        return self.product and self.product.gift_card

    @fields.depends('product', methods=['on_change_with_is_gift_card'])
    def on_change_with_is_gift_card_service(self, name=None):
        return (self.on_change_with_is_gift_card()
            and self.product.type == 'service')

    @classmethod
    def view_attributes(cls):
        return super().view_attributes() + [
            ('//page[@id="gift_cards"]', 'states', {
                    'invisible': ~Eval('is_gift_card_service', False),
                    }, ['is_gift_card_service']),
            ]

    def get_gift_cards(self):
        if (not self.is_gift_card_service
                or self.quantity < 0
                or self.gift_cards):
            return
        pool = Pool()
        GiftCard = pool.get('sale.gift_card')
        UoM = pool.get('product.uom')
        Config = pool.get('sale.configuration')
        config = Config(1)
        cards = []
        quantity = UoM.compute_qty(
            self.unit, self.quantity, self.product.default_uom)
        quantity -= len(self.gift_cards)
        quantity = max(quantity, 0)
        unit_price = UoM.compute_price(
            self.unit, self.unit_price, self.product.default_uom)
        unit_price = self.sale.currency.round(unit_price)
        for _ in range(int(quantity)):
            card = GiftCard()
            card.company = self.sale.company
            sequence = config.get_multivalue(
                'gift_card_sequence', company=card.company.id)
            if sequence:
                card.number = sequence.get()
            card.product = self.product
            card.value = unit_price
            card.currency = self.sale.currency
            card.origin = self
            cards.append(card)
        return cards
