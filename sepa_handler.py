#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from lxml import etree

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
        payment = self.get_payment(element)
        if self.is_returned(element):
            self.set_return_information(payment, element)
            payment.save()
            self.Payment.fail([payment])
        else:
            self.Payment.succeed([payment])

    def get_payment_kind(self, element):
        tag = etree.QName(element)
        return self._kinds[
            element.find('./{%s}CdtDbtInd' % tag.namespace).text]
    _kinds = {
        'CRDT': 'payable',
        'DBIT': 'receivable',
        }

    def get_payment(self, element):
        tag = etree.QName(element)
        details = element.find('./{%s}NtryDtls' % tag.namespace)
        if details is None:
            # Version 1 doesn't have NtryDtls but directly TxDtls
            details = element.find('./{%s}TxDtls' % tag.namespace)
        if details is None:
            return
        instr_id = details.find('.//{%s}InstrId' % tag.namespace)
        if instr_id is not None:
            payment, = self.Payment.search([
                    ('sepa_instruction_id', '=', instr_id.text),
                    ('kind', '=', self.get_payment_kind(element)),
                    ])
            return payment
        end_to_end_id = details.find('.//{%s}EndToEndId' % tag.namespace)
        if end_to_end_id is not None:
            payment, = self.Payment.search([
                    ('sepa_end_to_end_id', '=', end_to_end_id.text),
                    ('kind', '=', self.get_payment_kind(element)),
                    ])
            return payment

    def is_returned(self, element):
        tag = etree.QName(element)
        details = element.find('./{%s}NtryDtls' % tag.namespace)
        if details is None:
            return
        return_reason = details.find('.//{%s}RtrInf' % tag.namespace)
        if return_reason is None:
            return False
        return True

    def set_return_information(self, payment, element):
        tag = etree.QName(element)

        reason_code = element.find(
            './{%(ns)s}NtryDtls//{%(ns)s}RtrInf/{%(ns)s}Rsn/{%(ns)s}Cd'
            % {'ns': tag.namespace})
        if reason_code is not None:
            payment.sepa_return_reason_code = reason_code.text

        reason_information = element.find(
            './{%(ns)s}NtryDtls//{%(ns)s}RtrInf/{%(ns)s}AddtlInf'
            % {'ns': tag.namespace})
        if reason_information is not None:
            payment.sepa_return_reason_information = reason_information.text
