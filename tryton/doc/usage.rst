
:tocdepth: 2

Client Usage
############
This document is the reference about the concepts of the graphical user
interface (also known as *Tryton client* ) of the Tryton application framework.


Name
****
tryton - Graphical user client of the Tryton application framework


Synopsis
********

::

  tryton [options] [url]

On startup the login dialog is displayed.

Options
*******

--version                            Show program version number and exit

-h, --help                           Show help message and exit

-c FILE, --config=FILE               Specify alternate `configuration file`_

-d, --dev                            Enable development mode, which deactivates
                                     client side caching

-v, --verbose                        Enable basic debugging

-l LOG_LEVEL, --log-level=LOG_LEVEL  Specify the log level: DEBUG, INFO,
                                     WARNING, ERROR, CRITICAL

-u LOGIN, --user=LOGIN               Specify the login user

-s SERVER, --server=SERVER           Specify the server hostname:port

URL
***

When an url is passed, the client will try to find already running client that
could handle it and send to this one to open the url. If it doesn't find one
then it will start the GUI and open the url itself.

The url schemes are:

    `tryton://<hostname>[:<port>]/<database>/model/<model name>[/<id>][;parameters]`

    `tryton://<hostname>[:<port>]/<database>/wizard/<wizard name>[;parameters]`

    `tryton://<hostname>[:<port>]/<database>/report/<report name>[;parameters]`


where `parameters` are the corresponding fields of actions encoded in
`JSON`_.

.. _JSON: http://en.wikipedia.org/wiki/Json
.. Note:: `model` is for `act_window`
.. Note:: `report` must have at least a data parameter with `ids`, `id` and
    `model name`


Overview
********

On startup the login dialog is displayed. It allows to select a existing
profile (or to manage them) or to enter the host and database information.

The following schematic illustration of the Tryton client shows the names of
all important visual parts.

Figure: Tryton client application::

  Client Window       ________________________________________________________________
                     |T| Search  | Favorites    Tryton                           _ o x|
                     |----------------------------------------------------------------|
                     | +           |          ______                                  |
  Tabs               | |-+         |  [Tab1] |[Tab2]| [Tab3]...                       |
                     | | |-        | +-------+      +--------------------------------+|
                     | +           | | Menu Tab2                                     ||
                     | |-+         | |-----------------------------------------------||
  Tool bar           | | |-        | | New Save Switch Reload | Prev Next | Attach v ||
                     | | |-        | |-----------------------------------------------||
                     | +           | |        _______________________                ||
  Search widget      | |-+         | | Filter |                    *| Bookmark <- -> ||
                     | | |-        | |-----------------------------------------------||
                     | | |-        | |                                               ||
                     | +           | |                                               ||
  View               | |-+         | |                                               ||
                     |   |-        | |                                               ||
                     |   |-        | |                                               ||
                     |             | |                                               ||
                     |             | |                                               ||
                     |             | |                                               ||
                     |             | |                                               ||
                     |_____________| |_______________________________________________||
                     |________________________________________________________________|


Tabbed Main Frame
^^^^^^^^^^^^^^^^^
This part of the client contains all the related contents and
functions provided by the :term:`Tryton server` :term:`modules`.
All aspects inside the *main frame* depend at least on the individual set
of activated modules.

The main frame provides a `tabbed document interface`__ to arrange different
views side by side. New :term:`tabs` are opened by special :term:`actions`,
like choosing a menu item or clicking some action buttons. All tabs include
titles which show the name of the provided view.

:term:`Tabs` can be arranged by Drag and Drop.

__ TDI_

.. _TDI: http://en.wikipedia.org/wiki/Tabbed_document_interface

.. Note:: Inside :term:`views` there can be tabs, too.


Menu
++++
The *menu* does not contain fixed menu items.
All of them are dynamically provided by the actual set of the activated
:term:`modules` depending on the access rules of the current user. If a menu
item is clicked, the appropriate action will open in a new tab.

A search field allows to quickly filter the menu items by name and to search in
models for which the global search is enabled.


Application Menu
****************
The following section describes the action of the application menu.
A rule of thumb: All items of the menu bar that are suffixed by three dots
(...) will open an intermediate :term:`dialog` for setting up the provided
menu action. Most dialog provide a *Cancel* button, used to stop the
complete dialog process.

.. _Menu-Preferences:

Preferences:
  A preference dialog opens, where the actual user can show and edit his
  personal settings. All user preferences are stored server side.
  I.e. logging in with the same credentials from different computers
  always restores the same preferences.

Options
^^^^^^^
The Options menu sets up several visual and context depending preferences.


.. _Menu-Options-Toolbar:

Toolbar:

  * Default:
    Shows labels and icons as defaulted in the GTK configuration.

  * Text and Icons:
    Shows labels and icons in the tool bar.

  * Icons:
    Shows icons only in the tool bar.

  * Text:
    Shows labels only in the tool bar.

.. _Menu-Options-Form:

Form:

  * Save Column Width:
    Check box to enable saving of manually adjusted widths of columns in lists
    and trees.

  * Save Tree Expanded State:
    Check box to enable saving of expanded and selected nodes in trees/lists.

  * Spell Checking:
    Check box to enable spell checking in fields.

.. _Menu-Options-PDA-Mode:

PDA Mode:
  When activated, the client display in a condensed mode.

.. _Menu-Options-Search-Limit:

Search Limit:
  Open a dialog to set up the maximum number of records displayed on a list.

.. _Menu-Options-Check_Version:

Check Version:
  Check box to enable the check of new bug-fix version.

Help
^^^^

.. _Menu-Help-Keyboard_Shortcuts:

Keyboard Shortcuts...:
  Shows the information dialog of the predefined keyboard shortcut map.

  * Edition Widgets: Shows shortcuts working on text entries, relation entries
    and date/time entries.

.. _Menu-Help-About:

About...:
  License, Contributors, Authors of Tryton

Tool Bar
********
The tool bar contains the functionalities linked to the current tab.
Some operations are working with one record or with a selection of
:term:`records`. In :term:`form view` the actual record is selected for
operations. In :term:`tree view` all selected records are used for operations.

.. _Toolbar-New:

New:
  Creates a new record.

.. _Toolbar-Save:

Save:
  Saves the actual record.

.. _Toolbar-Switch_View:

Switch View:
  Switches the actual view aspect to:

  * :term:`Form view`
  * :term:`Tree view`
  * :term:`Graph view`

  Not all views provide all aspects.

.. _Toolbar-Reload_Undo:

Reload/Undo:
  Reloads the content of the actual tab. Undoes changes, if save request for
  the current record is denied.

.. _Toolbar-Duplicate:

Duplicate:
  Duplicates the content of the actual record in a newly created record.

.. _Toolbar-Delete:

Delete:
  Deletes the selected or actual record.

.. _Toolbar-Previous:

Previous:
  Goes to the last record in a list (sequence).

.. _Toolbar-Next:

Next:
  Goes to the next record in a list (sequence).

.. _Toolbar-Search:

Search:
    Goes to the search widget.

.. _Toolbar-View_Logs:

View Logs...:
  Shows generic information of the current record.

.. _Toolbar-Show revisions:

Show revisions...:
  Reload the current view/record at a specific revision.

.. _Toolbar-Close:

Close Tab:
  Closes the current tab. A Request :term:`Dialog` opens in case of unsaved
  changes.

.. _Toolbar-Attachment:

Attachment:
  The attachment item handles the document management system of
  Tryton which is able to attach files to any arbitrary :term:`model`.
  On click it opens the attachments :term:`dialog`. The default dialog
  shows a list view of the attached files and links.

.. _Toolbar-Actions:

Actions...:
  Shows all actions for the actual view, model and record.

.. _Toolbar-Relate:

Relate...:
  Shows all relate view for the actual view, model and record.

.. _Toolbar-Report:

Report...:
  Shows all reports for the actual view, model and record.

.. _Toolbar-Email:

E-Mail...:
  Open an editor to send an email related to the actual record.

.. _Toolbar-Print:

Print...:
  Shows all print actions for the actual view, model and record.

.. _Toolbar-Copy-URL:

Copy URL:
   Copy the URL of the form into the clipboard.

.. _Toolbar-Export_Data:

Export Data...:
  Export of current/selected records into :term:`CSV`-file or open it in Excel.

  * Predefined exports

    - Choose preferences of already saved exports.

  * All Fields: Fields available from the model.
  * Fields to export: Defines the specific fields to export.
  * Options:

    - Save: Save export as a CSV file.
    - Open: Open export in spread sheet application.

  * Add field names: Add a header row with field names to the export data.
  * Actions:

    - Add: Adds selected fields to *Fields to export*.
    - Remove: Removes selected fields from *Fields to export*.
    - Clear: Removes all fields from *Fields to export*.
    - Save Export: Saves field mapping to a *Predefined export* with a name.
    - Delete Export: Deletes a selected *Predefined export*.
    - OK: Exports the data (action depending on *Options*).
    - Cancel

.. _Toolbar-Import_Data:

Import Data...:
  Import records from :term:`CSV`-file.

  * All Fields: Fields available in the model (required fields are marked up).
  * Fields to Import: Exact sequence of all columns in the CSV file.
  * File to Import: File :term:`dialog` for choosing a CSV file to import.
  * CSV Parameters: Setup specific parameters for chosen CSV file.

    - Field Separator: Character which separates CSV fields.
    - Text Delimiter: Character which encloses text in CSV.
    - Encoding: :term:`Character encoding` of CSV file.
    - Lines to Skip: Count of lines to skip a headline or another offset.

  * Actions:

    - Add: Adds fields to *Fields to Import*.
    - Remove: Deletes fields from *Fields to Import*.
    - Clear: Removes all fields from *Fields to Import*.
    - Auto-Detect: Tries to auto detect fields in the CSV *File to Import*.
    - OK: Proceeds the data import.
    - Cancel

Widgets
*******

There are a several widgets used on Tryton in client side. The follow sections
will explains some of them.


Date/DateTime/Time Widgets
^^^^^^^^^^^^^^^^^^^^^^^^^^

These widgets have several key shortcuts to quickly modify the value. Each key
increases if lower case or decreases if upper case:

    - `y`: by one year
    - `m`: by one month
    - `w`: by one week
    - `d`: by one day
    - `h`: by one hour
    - `i`: by one minute
    - `s`: by one second

The `=` key sets the widget value to the current date and time.

TimeDelta Widgets
^^^^^^^^^^^^^^^^^

This widget represent a duration using different symbol of time separated by
space:

   - `Y`: for years (default: 365 days)
   - `M`: for months (default: 30 days)
   - `w`: for weeks (default: 7 days)
   - `d`: for days (default: 24 hours)
   - `h`: for hours (default: 60 minutes)
   - `m`: for minutes (default: 60 seconds)
   - `s`: for seconds (default: 1 seconds)

The hours, minutes and seconds are also represented as `H:M:s`.

For example: ``2w 3d 4:30`` which represents: two weeks, three days and four
and an half hours.

The value of each symbol may be changed by the context of the widget. For
example, a day could be configured as 8 hours.

Search Widget
^^^^^^^^^^^^^

The search widget adds the ability to easily search for records on the current
tab.  This widget is visible only on :term:`tree view`.

The Syntax
++++++++++

A query is composed of search clauses.
A clause is composed of a field name (with `:` at the end), an operator and a value.
The field name is optional and defaults to the record name.
The operator is also optional and defaults to `like` or `equal` depending on
the type of the field.  The default operator is `=` except for fields of type
`char`, `text` and `many2one` which is `ilike`.

Field Names
+++++++++++

All field names shown in the :term:`tree view` can be searched. Field names
must be followed by a `:`

    For example: ``Name:``

If the field name contains spaces, it is possible to
escape it using double quotes.

    For example: ``"Receivable Today":``

Operators
+++++++++

The following operators can be used:

    * `=`: equal to
    * `<`: less then
    * `<=`: less then or equal to
    * `>`: greater then
    * `>=`: greater then or equal to
    * `!=`: not equal
    * `!`: not equal or not like (depending of the type of field)

    For example: ``Name: != Dwight``

.. note:: The `ilike` operator is never explicit and `%` is appended to the
    value to make it behaves like `starts with`

Values
++++++

The format of the value depends on the type of the field.
A list of values can be set using `;` as separator.

    For example: ``Name: Michael; Pam``

    It will find all records having the `Name` starting with `Michael` or
    `Pam`.

A range of number values can be set using `..`.

    For example: ``Amount: 100..500``

    It will find all records with `Amount` between `100` and `500` included.

There are two wildcards:

    * `%`: matches any string of zero or more characters.
    * `_`: matches any single character.

It is possible to escape special characters in values by using double quotes.

    For example: ``Name: "Michael:Scott"``

    Here it will search with the value `Michael:Scott`.

Clause composition
++++++++++++++++++

The clauses can be composed using the two boolean operators `and` and `or`.
By default, there is an implicit `and` between each clause if no operator is
specified.

    For example: ``Name: Michael Amount: 100``

    is the same as ``Name: Michael and Amount: 100``

The `and` operator has a highest precedence than `or` but you can change it by
using parenthesis.

    For example: ``(Name: Michael or Name: Pam) and Amount: 100``

    is different than ``Name: Michael or Name: Pam and Amount: 100``

    which is evaluated as ``Name: Michael or (Name: Pam and Amount: 100)``

RichText Editor
^^^^^^^^^^^^^^^

This feature create a rich text editor with various features that allow for
text formatting. The features are:

  * Bold: On/off style of bold text
  * Italic: On/off style of italic text
  * Underline: On/off style of underline text
  * Choose font family: Choice from a combo box the desired font family
  * Choose font size: Choice from a combo box the desired size font
  * Text justify: Choice between four options for alignment of the line (left,
    right, center, fill)
  * Background color: Choose the background color of text from a color palette
  * Foreground color: Choose the foreground color of text from a color palette

Besides these features, it can change and edit text markup. The text markup
feature has a similar HTML tags and is used to describe the format specified by
the user and is a way of storing this format for future opening of a correct
formatted text. The tags are explain follows:

  * Bold: Tag `b` is used, i.e. <b>text</b>
  * Italic: Tag `i` is used, i.e. <i>text</i>
  * Underline: Tag `u` is used, i.e. <u>text</u>
  * Font family: It is a attribute `font-family` for `span` tag, i.e.
    <span font-family="Arial">text</span>
  * Font size: It is a attribute `size` for `span` tag, i.e. <span size="12">
    text</span>
  * Text Justify: For justification text is used paragraph tag `p`. The
    paragraph tag is used to create new lines and the alignment is applied
    across the board. Example: <p align='center'>some text</p>
  * Background color: It is a attribute `background` for `span` tag, i.e.
    <span background='#7f7f7f'>text</span>
  * Foreground color: It is a attribute `foreground` for `span` tag, i.e.
    <span foreground='#00f'>text</span>

CSS
***

The client can be styled using the file `theme.css`.

Here are the list of custom selectors:

    * `.readonly`: readonly widget or label

    * `.required`: widget or label of required field

    * `.invalid`: widget for which the field value is not valid

    * `headerbar.profile-<name>`: the name of the connection profile is set on the
      main window

For more information about style option see `GTK+ CSS`_

.. _GTK+ CSS: https://developer.gnome.org/gtk3/stable/chap-css-overview.html

Appendix
********


Configuration File
^^^^^^^^^^^^^^^^^^

::

   ~/.config/tryton/x.y/tryton.conf      # General configuration
   ~/.config/tryton/x.y/accel.map        # Accelerators configuration
   ~/.config/tryton/x.y/known_hosts      # Fingerprints
   ~/.config/tryton/x.y/ca_certs         # Certification Authority (http://docs.python.org/library/ssl.html#ssl-certificates)
   ~/.config/tryton/x.y/profiles.cfg     # Profile configuration
   ~/.config/tryton/x.y/plugins          # Local user plugins directory
   ~/.config.tryton/x.y/theme.css        # Custom CSS theme

.. note::
    `~` means the home directory of the user.
    But on Windows system it is the `APPDATA` directory.
