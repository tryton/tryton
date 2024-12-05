=====================================
Sale Promotion Coupon Unique Scenario
=====================================

Imports::

    >>> import datetime as dt

    >>> from proteus import Model
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.tests.tools import activate_modules, assertEqual

    >>> today = dt.date.today()
    >>> tomorrow = today + dt.timedelta(days=1)

Activate modules::

    >>> config = activate_modules('sale_promotion_coupon')

    >>> Promotion = Model.get('sale.promotion')

Create a company::

    >>> _ = create_company()

Create a promotion with coupon::

    >>> promotion1 = Promotion(name="Promotion 1")
    >>> promotion1.formula = 'unit_price'
    >>> coupon = promotion1.coupons.new()
    >>> number = coupon.numbers.new(number="TEST", start_date=None)
    >>> promotion1.save()

Try to create a second promotion with same coupon number::

    >>> promotion2 = Promotion(name="Promotion 2")
    >>> promotion2.formula = 'unit_price'
    >>> coupon = promotion2.coupons.new()
    >>> number = coupon.numbers.new(number="TEST")
    >>> promotion2.save()
    Traceback (most recent call last):
        ...
    SQLConstraintError: ...

End the first promotion and start the second after::

    >>> promotion1.end_date = today
    >>> promotion1.save()
    >>> coupon1 = promotion1.coupons[0].numbers[0]
    >>> coupon1.start_date
    >>> assertEqual(coupon1.end_date, today)

    >>> coupon2 = promotion2.coupons[0].numbers[0]
    >>> coupon2.start_date = tomorrow
    >>> promotion2.save()
