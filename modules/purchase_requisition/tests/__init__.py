try:
    from trytond.modules.purchase_requisition.tests.test_purchase_requisition \
        import suite
except ImportError:
    from .test_purchase_requisition import suite

__all__ = ['suite']
