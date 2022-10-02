# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from dateutil.parser import parse
from lxml import etree

from trytond.transaction import Transaction

__all__ = ['SEPAHandler', 'CAMT054']


class SEPAHandler(object):

    def __init__(self, source):
        for event, element in etree.iterparse(source):
            self.handle(event, element)

    def handle(self, event, element):
        raise NotImplementedError


class CAMT054(SEPAHandler):
    msg_id = None

    def __init__(self, source, Payment):
        self.Payment = Payment
        super(CAMT054, self).__init__(source)

    def handle(self, event, element):
        tag = etree.QName(element)
        if tag.localname == 'GrpHdr':
            self.msg_id = element.find('./{%s}MsgId' % tag.namespace).text
            element.clear()
        elif tag.localname == 'Ntry':
            self.handle_entry(element)
            element.clear()

    def handle_entry(self, element):
        tag = etree.QName(element)
        failed, succeeded = [], []
        date_value = self.date_value(element)

        for transaction in element.findall('.//{%s}TxDtls' % tag.namespace):
            payments = self.get_payments(transaction)
            if self.is_returned(transaction):
                for payment in payments:
                    self.set_return_information(payment, transaction)
                failed.extend(payments)
            else:
                succeeded.extend(payments)

        if failed:
            self.Payment.save(failed)
            self.Payment.fail(failed)
        if succeeded:
            with Transaction().set_context(date_value=date_value):
                self.Payment.succeed(succeeded)

    def get_payment_kind(self, element):
        camt_ns = etree.QName(element).namespace
        for path in [
                './camt:CdtDbtInd',
                './ancestor::camt:NtryDtls/camt:Btch/camt:CdtDbtInd',
                './ancestor::camt:Ntry/camt:CdtDbtInd',
                ]:
            cdtdbtind = element.xpath(path, namespaces={'camt': camt_ns})
            if cdtdbtind:
                return self._kinds[cdtdbtind[0].text]
    _kinds = {
        'CRDT': 'payable',
        'DBIT': 'receivable',
        }

    def get_payments(self, transaction):
        tag = etree.QName(transaction)
        instr_id = transaction.find(
            './/{%s}InstrId' % tag.namespace)
        end_to_end_id = transaction.find(
            './/{%s}EndToEndId' % tag.namespace)
        payment_kind = self.get_payment_kind(transaction)
        if instr_id is not None:
            return self.Payment.search([
                    ('sepa_instruction_id', '=', instr_id.text),
                    ('kind', '=', payment_kind),
                    ])
        elif end_to_end_id is not None:
            return self.Payment.search([
                    ('sepa_end_to_end_id', '=', end_to_end_id.text),
                    ('kind', '=', payment_kind),
                    ])
        return []

    def date_value(self, element):
        tag = etree.QName(element)
        date = element.find('./{%(ns)s}ValDt/{%(ns)s}Dt'
            % {'ns': tag.namespace})
        if date is not None:
            return parse(date.text).date()
        else:
            datetime = element.find('./{%(ns)s}ValDt/{%(ns)s}DtTm'
                % {'ns': tag.namespace})
            if datetime:
                return parse(datetime.text).date()

    def is_returned(self, element):
        tag = etree.QName(element)
        return_reason = element.find('.//{%s}RtrInf' % tag.namespace)
        return return_reason is not None

    def set_return_information(self, payment, element):
        tag = etree.QName(element)

        reason_code = element.find(
            './/{%(ns)s}RtrInf/{%(ns)s}Rsn/{%(ns)s}Cd' % {'ns': tag.namespace})
        if reason_code is not None:
            payment.sepa_return_reason_code = reason_code.text

        reason_information = element.find(
            './/{%(ns)s}RtrInf/{%(ns)s}AddtlInf' % {'ns': tag.namespace})
        if reason_information is not None:
            payment.sepa_return_reason_information = reason_information.text
