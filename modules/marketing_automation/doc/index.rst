Marketing Automation Module
###########################

The marketing_automation module allows marketing actions to be automated. It is
based on scenarios and activities that are executed on selected records.

Scenario
********

A scenario provides the entry point for records into an automated marketing
campaign. Each record can only enter a scenario once. A scenario is defined by:

    * Name
    * Model: the type of record for the scenario (by default Party and Sale)
    * Domain: used to filter records
    * State:

        * Draft
        * Running
        * Stopped

A cron task runs periodically to find new records to apply the scenario to.

Activity
********

The activities form a scenario. They define which action should be triggered
and when it should happen. The activities are organized as a tree and defined
by:

    * Name
    * Parent
    * Children
    * On: event from the parent that triggers the activity:

        * E-Mail Opened
        * E-Mail Not Opened
        * E-Mail Clicked
        * E-Mail Not Clicked

    * Condition: that the record must match to execute the activity
    * Delay: before the action is executed
    * Action: list of available actions

Actions
-------

Send E-Mail
...........

The activity send an e-mail to the party defined on the record.
The E-mail is composed using an HTML `Genshi <https://genshi.edgewall.org/>`_
template with `record` in the evaluation context.
All `<a>` elements have their `href` replaced by a shortened version used to
trigger children activities. If the `href` value is `unsubscribe`, it is
replaced by the URL which allows the recipient to block their record for the
scenario.
A empty image is automatically added at the end of the `<body>` to track when
emails are opened.

Record
******

It stores a reference to the records included in each scenario. If the record
is blocked, no activity will be triggered for the record.

Record Activity
***************

It stores the state of a record for an activity of the scenario.

A cron task runs periodically to execute any waiting record activity that is
due.

Configuration
*************

The marketing_automation module uses parameters from the section:

- `[marketing]`:

    - `email_from`: The default `From` for the email.
    - `automation_base`: The base URL without a path for the unsubscribe URL
      and the empty image.
      The default value is created using the configuration `[web]` `hostname`.
