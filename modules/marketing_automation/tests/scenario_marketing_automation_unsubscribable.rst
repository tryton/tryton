Marketing Automation Unsubscribable Scenario
============================================

Imports::

    >>> from unittest.mock import patch

    >>> from proteus import Model
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.modules.marketing_automation import marketing_automation
    >>> from trytond.pyson import Eval, PYSONEncoder
    >>> from trytond.tests.tools import activate_modules, assertEqual
    >>> from trytond.tools import file_open

Patch send_message_transactional::

    >>> smtp_calls = patch.object(
    ...     marketing_automation, 'send_message_transactional').start()
    >>> manager = patch.object(
    ...     marketing_automation, 'SMTPDataManager').start()

Activate modules::

    >>> config = activate_modules(['marketing_automation', 'sale'])

    >>> Activity = Model.get('marketing.automation.activity')
    >>> Cron = Model.get('ir.cron')
    >>> Party = Model.get('party.party')
    >>> Record = Model.get('marketing.automation.record')
    >>> Sale = Model.get('sale.sale')
    >>> Scenario = Model.get('marketing.automation.scenario')

    >>> cron_trigger, = Cron.find([
    ...     ('method', '=', 'marketing.automation.scenario|trigger'),
    ...     ])
    >>> cron_process, = Cron.find([
    ...     ('method', '=', 'marketing.automation.record.activity|process'),
    ...     ])

Create a party::

    >>> party = Party()
    >>> party.name = "Michael Scott"
    >>> contact = party.contact_mechanisms.new()
    >>> contact.type = 'email'
    >>> contact.value = 'michael@example.com'
    >>> party.save()

Create company::

    >>> _ = create_company()

Create a sale::

    >>> sale = Sale(party=party)
    >>> sale.save()

Create the running scenario::

    >>> scenario = Scenario()
    >>> scenario.name = "Sale Scenario"
    >>> scenario.model = 'sale.sale'
    >>> scenario.domain = '[["state", "=", "draft"]]'
    >>> scenario.unsubscribable = True
    >>> scenario.save()

    >>> activity = scenario.activities.new()
    >>> activity.name = "First E-Mail"
    >>> activity.action = 'send_email'
    >>> activity.email_title = "Pending Sale"
    >>> activity.condition = PYSONEncoder().encode(
    ...     Eval('self', {}).get('active'))
    >>> with file_open('marketing_automation/tests/email.html', mode='r') as fp:
    ...     activity.email_template = fp.read()

    >>> scenario.click('run')

Trigger scenario::

    >>> cron_trigger.click('run_once')
    >>> cron_process.click('run_once')

    >>> record, = Record.find([])
    >>> assertEqual(record.record, sale)

    >>> scenario.reload()
    >>> scenario.record_count
    1
    >>> scenario.record_count_blocked
    0
    >>> scenario.block_rate
    0.0

Block and unsubscribe::

    >>> record.click('block')
    >>> bool(record.blocked)
    True
    >>> party.reload()
    >>> assertEqual(party.marketing_scenario_unsubscribed, [scenario])

    >>> scenario.reload()
    >>> scenario.record_count
    1
    >>> scenario.record_count_blocked
    1
    >>> scenario.block_rate
    1.0

Create a new sale::

    >>> sale = Sale(party=party)
    >>> sale.save()

Trigger scenario::

    >>> cron_trigger.click('run_once')
    >>> cron_process.click('run_once')

    >>> Record.find([('blocked', '=', False)])
    []
