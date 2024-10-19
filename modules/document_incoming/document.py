# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import mimetypes
from collections import defaultdict
from io import BytesIO

from pypdf import PdfReader, PdfWriter

from trytond.config import config
from trytond.i18n import gettext
from trytond.model import (
    DeactivableMixin, ModelSingleton, ModelSQL, ModelView, Workflow, fields)
from trytond.pool import Pool
from trytond.pyson import Eval, If
from trytond.transaction import Transaction
from trytond.wizard import Button, StateTransition, StateView, Wizard

from .exceptions import DocumentIncomingSplitError

if config.getboolean('document_incoming', 'filestore', default=True):
    file_id = 'file_id'
    store_prefix = config.get(
        'document_incoming', 'store_prefix', default=None)
else:
    file_id = store_prefix = None


class IncomingConfiguration(ModelSingleton, ModelSQL, ModelView):
    "Incoming Document Configuration"
    __name__ = 'document.incoming.configuration'


class Incoming(DeactivableMixin, Workflow, ModelSQL, ModelView):
    "Incoming Document"
    __name__ = 'document.incoming'

    _states = {
        'readonly': Eval('state') != 'draft',
        }

    name = fields.Char("Name", required=True, states=_states)
    company = fields.Many2One('company.company', "Company", states=_states)
    data = fields.Binary(
        "Data", filename='name',
        file_id=file_id, store_prefix=store_prefix, required=True,
        states=_states)
    parsed_data = fields.Dict(None, "Parsed Data", readonly=True)
    file_id = fields.Char("File ID", readonly=True)
    mime_type = fields.Function(
        fields.Char("MIME Type"), 'on_change_with_mime_type')
    type = fields.Selection([
            (None, ""),
            ('document_incoming', "Unknown"),
            ], "Type",
        states={
            'required': Eval('state') == 'done',
            'readonly': _states['readonly'],
            })
    source = fields.Char("Source", states=_states)
    parent = fields.Many2One(
        'document.incoming', "Parent", readonly=True,
        domain=[
            ('active', '=', False),
            ],
        states={
            'invisible': ~Eval('parent'),
            })
    children = fields.One2Many(
        'document.incoming', 'parent', "Children", readonly=True,
        states={
            'invisible': ~Eval('children'),
            })
    result = fields.Reference(
        "Result", selection='get_results', readonly=True,
        states={
            'required': Eval('state') == 'done',
            'invisible': ~Eval('result'),
            })
    state = fields.Selection([
            ('draft', "Draft"),
            ('processing', "Processing"),
            ('done', "Done"),
            ('cancelled', "Cancelled"),
            ], "State", required=True, readonly=True)

    del _states

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._transitions |= {
            ('draft', 'processing'),
            ('draft', 'cancelled'),
            ('processing', 'processing'),
            ('processing', 'done'),
            ('processing', 'draft'),
            ('cancelled', 'draft'),
            }
        cls._buttons.update(
            cancel={
                'invisible': Eval('state') != 'draft',
                'depends': ['state'],
                },
            draft={
                'invisible': ~Eval('state').in_(['processing', 'cancelled']),
                'depends': ['state'],
                },
            split_wizard={
                'invisible': (
                    (Eval('state') != 'draft')
                    | ~Eval('mime_type').in_(cls._split_mime_types())),
                'depends': ['state', 'mime_type'],
                },
            process={
                'pre_validate': [
                    If(~Eval('type'),
                        ('type', '!=', None),
                        ()),
                    ],
                'invisible': Eval('state') != 'draft',
                'depends': ['state'],
                },
            proceed={
                'invisible': Eval('state') != 'processing',
                'depends': ['state'],
                },
            )

    @fields.depends('name')
    def on_change_with_mime_type(self, name=None):
        if self.name:
            type, _ = mimetypes.guess_type(self.name)
            return type

    @classmethod
    def get_results(cls):
        pool = Pool()
        IrModel = pool.get('ir.model')
        get_name = IrModel.get_name
        models = cls._get_results()
        return [(None, '')] + [(m, get_name(m)) for m in models]

    @classmethod
    def _get_results(cls):
        return {'document.incoming'}

    @classmethod
    def default_state(cls):
        return 'draft'

    @classmethod
    def view_attributes(cls):
        process_states = cls._buttons['process'].copy()
        process_states['invisible'] = Eval('state') != 'draft'
        return super().view_attributes() + [
            ('/form//button[@name="process"]', 'states', process_states),
            ]

    @classmethod
    @ModelView.button
    @Workflow.transition('cancelled')
    def cancel(cls, documents):
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition('draft')
    def draft(cls, documents):
        pass

    @classmethod
    @ModelView.button_action(
        'document_incoming.wizard_document_incoming_split')
    def split_wizard(cls, documents):
        pass

    @classmethod
    def _split_mime_types(cls):
        return ['application/pdf']

    @classmethod
    def from_inbound_email(cls, email_, rule):
        message = email_.as_dict()
        active = not message.get('attachments')
        data = message.get('text', message.get('html'))
        if isinstance(data, str):
            data = data.encode()
        name = message.get('subject') or 'No Subject'
        for forbidden_char in cls.name.forbidden_chars:
            name = name.replace(forbidden_char, ' ')
        document = cls(
            active=active,
            name=name,
            company=rule.document_incoming_company,
            data=data,
            type=rule.document_incoming_type if active else None,
            source='inbound_email',
            )
        children = []
        for attachment in message.get('attachments', []):
            child = cls(
                name=attachment['filename'] or 'data.bin',
                company=rule.document_incoming_company,
                data=attachment['data'],
                type=rule.document_incoming_type,
                source='inbound_email')
            children.append(child)
        document.children = children
        document.save()
        return document

    @classmethod
    @ModelView.button
    @Workflow.transition('processing')
    def process(cls, documents, with_children=False):
        transaction = Transaction()
        context = transaction.context
        with transaction.set_context(
                queue_batch=context.get('queue_batch', True)):
            cls.__queue__.proceed(documents, with_children=with_children)

    @classmethod
    @ModelView.button
    @Workflow.transition('done')
    def proceed(cls, documents, with_children=False):
        pool = Pool()
        Attachment = pool.get('ir.attachment')
        results = defaultdict(list)
        attachments = []
        for document in documents:
            if document.result or not document.active:
                continue
            document.result = getattr(document, f'_process_{document.type}')()
            results[document.result.__class__].append(document.result)
            attachment = Attachment(
                name=document.name,
                resource=document.result,
                type='data',
                data=document.data)
            attachments.append(attachment)
        for kls, records in results.items():
            kls.save(records)
        cls.save(documents)
        Attachment.save(attachments)

        if with_children:
            children = list(filter(
                    lambda d: d.type,
                    (c for d in documents for c in d.children)))
            if children:
                cls.process(children, with_children=True)

    def _process_document_incoming(self):
        self.active = False
        self.save()
        document, = self.__class__.copy([self], default={
                'type': None,
                'parent': self.id,
                })
        return document

    @classmethod
    def copy(cls, documents, default=None):
        default = default.copy() if default is not None else {}
        default.setdefault('result')
        default.setdefault('parsed_data')
        default.setdefault('children')
        return super().copy(documents, default=default)


def iter_pages(expression, size):
    ranges = set()
    for pages in expression.split(','):
        pages = pages.split('-')
        if not len(pages):
            continue
        if not pages[0]:
            pages[0] = 1
        if not pages[-1]:
            pages[-1] = size
        pages = list(map(int, filter(None, pages)))
        ranges.add((
                min(max(min(pages) - 1, 0), size),
                min(max(max(pages), 0), size)))
    ranges = sorted(ranges)

    def iter_():
        last = 0
        for start, end in ranges:
            if last != start:
                yield range(last, start)
            yield range(start, end)
            last = end
        if last != size:
            yield range(last, size)
    return iter_()


class IncomingSplit(Wizard):
    "Split Incoming Document"
    __name__ = 'document.incoming.split'

    start = StateView(
        'document.incoming.split.start',
        'document_incoming.document_incoming_split_start_view_form', [
            Button("Cancel", 'end', 'tryton-cancel'),
            Button("Split", 'split', 'tryton-ok', default=True),
            ])
    split = StateTransition()

    def default_start(self, fields):
        if self.record.mime_type == 'application/pdf':
            reader = PdfReader(BytesIO(self.record.data))
            if len(reader.pages) == 1:
                pages = '1'
            else:
                pages = '1-%d' % len(reader.pages)
        else:
            pages = ''
        return {
            'data': self.record.data,
            'pages': pages,
            }

    def transition_split(self):
        pool = Pool()
        Document = pool.get('document.incoming')
        if self.record.active and self.record.mime_type == 'application/pdf':
            self.record.active = False
            self.record.save()
            reader = PdfReader(BytesIO(self.record.data))
            try:
                iter_ = iter_pages(self.start.pages, len(reader.pages))
            except ValueError as exception:
                raise DocumentIncomingSplitError(gettext(
                        'document_incoming.msg_document_split_invalid_pages',
                        expression=self.start.pages,
                        exception=exception)) from exception
            for pages in iter_:
                writer = PdfWriter()
                for i in pages:
                    page = reader.pages[i]
                    writer.add_page(page)
                data = BytesIO()
                writer.write(data)
                Document.copy([self.record], default={
                        'active': True,
                        'data': data.getvalue(),
                        'parent': self.record.id,
                        })
        return 'end'

    def end(self):
        return 'reload'


class IncomingSplitStart(ModelView):
    "Split Incoming Document"
    __name__ = 'document.incoming.split.start'

    data = fields.Binary("Data", readonly=True)
    pages = fields.Char(
        "Pages", required=True,
        help="List pages to split.\n"
        "Ex: 1-3,4,5-6")
