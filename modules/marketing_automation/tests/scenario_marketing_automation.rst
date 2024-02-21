Marketing Automation Scenario
=============================

Imports::

    >>> import datetime
    >>> import re
    >>> from unittest.mock import patch

    >>> from proteus import Model
    >>> from trytond.modules.marketing_automation import marketing_automation
    >>> from trytond.pyson import Eval, PYSONEncoder
    >>> from trytond.tests.tools import (
    ...     activate_modules, assertEqual, assertIn, assertTrue)
    >>> from trytond.tools import file_open

Patch send_message_transactional::

    >>> smtp_calls = patch.object(
    ...     marketing_automation, 'send_message_transactional').start()
    >>> manager = patch.object(
    ...     marketing_automation, 'SMTPDataManager').start()

Activate modules::

    >>> config = activate_modules('marketing_automation')

    >>> Email = Model.get('ir.email')
    >>> ReportingScenario = Model.get('marketing.automation.reporting.scenario')
    >>> ReportingActivity = Model.get('marketing.automation.reporting.activity')

Create a party::

    >>> Party = Model.get('party.party')
    >>> party = Party()
    >>> party.name = "Michael Scott"
    >>> contact = party.contact_mechanisms.new()
    >>> contact.type = 'email'
    >>> contact.value = 'michael@example.com'
    >>> party.save()

Create the running scenario::

    >>> Scenario = Model.get('marketing.automation.scenario')
    >>> Activity = Model.get('marketing.automation.activity')
    >>> scenario = Scenario()
    >>> scenario.name = "Party Scenario"
    >>> scenario.model = 'party.party'
    >>> scenario.domain = '[["contact_mechanisms", "!=", null]]'
    >>> scenario.save()

    >>> root_activity = Activity()
    >>> root_activity.name = "First E-Mail"
    >>> root_activity.parent = scenario
    >>> root_activity.action = 'send_email'
    >>> root_activity.email_title = "Hello"
    >>> root_activity.condition = PYSONEncoder().encode(
    ...     Eval('self', {}).get('active'))
    >>> with file_open('marketing_automation/tests/email.html', mode='r') as fp:
    ...     root_activity.email_template = fp.read()
    >>> root_activity.save()

    >>> email_opened = Activity()
    >>> email_opened.name = "E-Mail Opened"
    >>> email_opened.parent = root_activity
    >>> email_opened.on = 'email_opened'
    >>> email_opened.save()

    >>> email_clicked = Activity()
    >>> email_clicked.name = "E-Mail Clicked"
    >>> email_clicked.parent = root_activity
    >>> email_clicked.on = 'email_clicked'
    >>> email_clicked.save()

    >>> email_not_clicked = Activity()
    >>> email_not_clicked.name = "E-Mail no clicked"
    >>> email_not_clicked.parent = root_activity
    >>> email_not_clicked.on = 'email_clicked_not'
    >>> email_not_clicked.delay = datetime.timedelta(days=2)
    >>> email_not_clicked.save()

    >>> email_reminder = Activity()
    >>> email_reminder.name = "E-Mail Reminder"
    >>> email_reminder.parent = root_activity
    >>> email_reminder.action = 'send_email'
    >>> email_reminder.email_title = "Reminder"
    >>> email_reminder.delay = datetime.timedelta()
    >>> with file_open('marketing_automation/tests/reminder.html', mode='r') as fp:
    ...     email_reminder.email_template = fp.read()
    >>> email_reminder.save()

    >>> scenario.record_count
    1

    >>> scenario.click('run')

Trigger scenario::

    >>> Cron = Model.get('ir.cron')
    >>> cron_trigger, = Cron.find([
    ...     ('method', '=', 'marketing.automation.scenario|trigger'),
    ...     ])
    >>> cron_process, = Cron.find([
    ...     ('method', '=', 'marketing.automation.record.activity|process'),
    ...     ])
    >>> cron_trigger.click('run_once')
    >>> cron_process.click('run_once')

    >>> Record = Model.get('marketing.automation.record')
    >>> record, = Record.find([])
    >>> assertEqual(record.record, party)
    >>> scenario.record_count
    1
    >>> scenario.record_count_blocked
    0
    >>> scenario.block_rate
    0.0
    >>> bool(scenario.block_rate_trend)
    True

    >>> reporting, = ReportingScenario.find([])
    >>> reporting.record_count
    1
    >>> reporting.record_count_blocked
    0
    >>> reporting.block_rate
    0.0

Check email sent::

    >>> ShortenedURL = Model.get('web.shortened_url')
    >>> open_url, = ShortenedURL.find([
    ...         ('redirect_url', 'like', '%/m/empty.gif'),
    ...         ])
    >>> click_url, = ShortenedURL.find([
    ...         ('redirect_url', '=', 'http://example.com/action'),
    ...         ])

    >>> RecordActivity = Model.get('marketing.automation.record.activity')
    >>> record_activity, = RecordActivity.find([
    ...         ('record', '=', record.id),
    ...         ('activity', '=', root_activity.id),
    ...         ])
    >>> record_activity.state
    'done'
    >>> root_activity.reload()
    >>> root_activity.record_count
    1

    >>> smtp_calls.call_count
    1
    >>> msg, = smtp_calls.call_args[0]
    >>> smtp_calls.reset_mock()
    >>> msg = msg.get_body().get_content()
    >>> assertEqual(re.search(r'Hello, (.*)!', msg).group(1), party.name)
    >>> open_url.shortened_url in msg
    True
    >>> assertEqual(open_url.record, record_activity)
    >>> open_url.method
    'marketing.automation.record.activity|on_email_opened'
    >>> click_url.shortened_url in msg
    True
    >>> assertEqual(click_url.record, record_activity)
    >>> click_url.method
    'marketing.automation.record.activity|on_email_clicked'
    >>> assertIn(record.uuid, msg)

    >>> email, = Email.find([])
    >>> email.recipients
    'Michael Scott <michael@example.com>'
    >>> email.subject
    'Hello'
    >>> email.resource == party
    True
    >>> assertEqual(email.marketing_automation_activity, root_activity)
    >>> assertTrue(email.marketing_automation_record)

Trigger open email and reminder after delay::

    >>> record_activity.click('on_email_opened')

    >>> open_activity, = RecordActivity.find([
    ...         ('record', '=', record.id),
    ...         ('activity', '=', email_opened.id),
    ...         ])
    >>> bool(open_activity.at)
    True
    >>> open_activity.state
    'waiting'

    >>> cron_process.click('run_once')

    >>> open_activity.reload()
    >>> open_activity.state
    'done'
    >>> root_activity.reload()
    >>> root_activity.email_opened
    1
    >>> root_activity.email_opened
    1
    >>> root_activity.email_clicked
    0
    >>> root_activity.email_open_rate
    1.0
    >>> bool(root_activity.email_open_rate_trend)
    True
    >>> root_activity.email_click_rate
    0.0
    >>> bool(root_activity.email_click_rate_trend)
    True
    >>> root_activity.email_click_through_rate
    0.0
    >>> bool(root_activity.email_click_through_rate_trend)
    True

    >>> reporting, = ReportingActivity.find([
    ...         ('activity', '=', root_activity.id),
    ...         ])
    >>> reporting.activity_action
    'send_email'
    >>> reporting.record_count
    1
    >>> reporting.email_opened
    1
    >>> reporting.email_clicked
    0
    >>> reporting.email_open_rate
    1.0
    >>> reporting.email_click_rate
    0.0
    >>> reporting.email_click_through_rate
    0.0

    >>> email_reminder, = RecordActivity.find([
    ...         ('record', '=', record.id),
    ...         ('activity', '=', email_reminder.id),
    ...         ])
    >>> email_reminder.state
    'done'

    >>> smtp_calls.call_count
    1
    >>> smtp_calls.reset_mock()

Trigger click email::

    >>> record_activity.click('on_email_clicked')
    >>> cron_process.click('run_once')

    >>> clicked_activity, = RecordActivity.find([
    ...         ('record', '=', record.id),
    ...         ('activity', '=', email_clicked.id),
    ...         ])
    >>> clicked_activity.state
    'done'
    >>> root_activity.reload()
    >>> root_activity.record_count
    1
    >>> root_activity.email_opened
    1
    >>> root_activity.email_clicked
    1
    >>> root_activity.email_open_rate
    1.0
    >>> root_activity.email_click_rate
    1.0
    >>> root_activity.email_click_through_rate
    1.0

    >>> reporting.reload()
    >>> reporting.record_count
    1
    >>> reporting.email_opened
    1
    >>> reporting.email_clicked
    1
    >>> reporting.email_open_rate
    1.0
    >>> reporting.email_click_rate
    1.0
    >>> reporting.email_click_through_rate
    1.0

    >>> not_clicked_activity, = RecordActivity.find([
    ...         ('record', '=', record.id),
    ...         ('activity', '=', email_not_clicked.id),
    ...         ])
    >>> not_clicked_activity.state
    'cancelled'
