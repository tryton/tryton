
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

After startup the `login dialog`__ is displayed.

__ Menu-Connection_


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

Environment
***********

`GTKOSXAPPLICATION`                  Activate with native Mac desktop

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
The following schematic illustration of the Tryton client shows the names of
all important visual parts.

Figure: Tryton client application::

  Client Window       ________________________________________________________________
                     |                      Tryton                               _ o x|
                     |----------------------------------------------------------------|
  Menu bar           | Connection User Options Favorites Help                         |
                     |________________________________________________________________|
                     |             |          ______                                  |
  Tabs               | Menu        |  [Tab1] |[Tab2]| [Tab3]...                       |
                     |-------------| +-------+      +--------------------------------+|
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


Menu Bar
^^^^^^^^
The menu bar is the main control unit. It provides most of the functionalities
of the client application. The menu bar is grouped into categories. It is
controlled with mouse or keyboard. The `menu bar items`_ are explained later.


Mouse and Keyboard Use
++++++++++++++++++++++
Most functions of the Tryton client can be accessed with mouse or keyboard.
`Key bindings`__ for all menu items are preset. Furthermore all key bindings
are manually configurable. To change the binding of a menu item the user needs
to put the cursor onto it and simply press the user defined key combination.
For this purpose it is needed to activate the configuration of the key bindings
with Options > Menubar > Change Accelerators. After the configuration it is
preferable to disable Change Accelerators, to avoid accidental changes of key
bindings while navigating the Menu bar with the keyboard.

To remove a key binding simply press the delete button while pointing the
cursor on the menu item to change.

.. Note:: Usually key bindings are composed with modifier keys.

__ Menu-Help-Keyboard_Shortcuts_

Additionally the menu bar items are accessible with the *Alt* or *Option* key.
The user needs to hold the *Alt* or *Option* key followed by the underlined
character of the menu bar item to choose. To dive into deeper menu levels,
he needs to release the *Alt* or *Option* key and to simply press the
underlined letter of the sub menu item. If there exist several menu items with
the same shortcut, repeated activation of the shortcut key will jump to the
next one.

The second mouse button (usually right mouse button) provides an additional
contextual menu for some views and fields. In this context menu the user finds
:term:`actions` to copy and paste contents or selections for several fields.


Tabbed Main Frame
^^^^^^^^^^^^^^^^^
This part of the client contains all the related contents and
functions provided by the :term:`Tryton server` :term:`modules`.
All aspects inside the *main frame* depend at least on the individual set
of installed modules.

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
All of them are dynamically provided by the actual set of the installed
:term:`modules` depending on the access rules of the current user. If a menu
item is clicked, the appropriate action will open in a new tab.

A search field allows to quickly filter the menu items by name and to search in
models for which the global search is enabled.


Menu Bar Items
**************
The following section describes the function of each menu bar entry in detail.
A rule of thumb: All items of the menu bar that are suffixed by three dots
(...) will open an intermediate :term:`dialog` for setting up the provided
menu action. Most dialogs provide a *Cancel* button, used to stop the
complete dialog process.


Connection
^^^^^^^^^^
The connection menu level provides functions about Tryton server login,
logout and closing the client application.

.. _Menu-Connection:

Connect...
  By choosing this menu entry the client will be connected to an available
  Tryton server. A :term:`dialog` opens to request credentials:

  * `Server`__
  * Database: Database to connect server side
  * User name: Tryton user name to login
  * Password: Tryton password to login
  * Actions:

    - Connect: Connects to the server with the given credentials.
    - Cancel

.. note:: Depending on server configuration for session timeout, the actual
   user may be logged out of the current session, and need to login again.
   Default timeout for inactivity logout is six minutes.

.. _Menu-Connection-Disconnect:

Disconnect...
  Disconnects the client from an active server connection. In case of unsaved
  changes in an open tab, the Tryton client will request for saving the
  changes.

__ Connection-Server-Connection_

.. _Connection-Server-Connection:

Server (connection) dialog:
  This :term:`dialog` is widely used to setup a Tryton server connection.
  This dialog shows the actual state of the client/server communication.
  It also shows when there is no connection to a Tryton server at all.
  The *Change* button opens a dialog for connection details:

  * Server: Network address or IP number of the Tryton server (protocols
    are not supported)
  * Port: Port where the Tryton server listens.

.. note:: If there is no connection to a Tryton server, many items in menu bar
   and tool bar are deactivated.


User
^^^^
This menu bar item controls the preferences of the actual user.

.. _Menu-User-Preferences:

Preferences...
  A preference dialog opens, where the actual user can show and edit his
  personal settings. All user preferences are stored server side.
  I.e. logging in with the same credentials from different computers
  always restores the same preferences.

  * Name: Real name of the Tryton user.
  * Password: Password of the Tryton user.
  * Email: Email address of the Tryton user.
  * Signature: Signature block for the Tryton user.
  * Menu Action: Defines the action which is called as the
    `Menu`_.
  * Language: Language of the client interface.
  * Timezone: The local timezone where the user/client resides.
  * Groups: Displays the users membership to access groups.
  * Applications: A list of applications along with their access
    key and the authorization state.

.. _Menu-User-Menu-Reload:

Menu Reload:
  Reload the menu.

.. _Menu-User-Menu-Toggle:

Menu Toggle:
  Toggle the menu visibility


Options
^^^^^^^
The Options menu sets up several visual and context depending preferences.


Toolbar
+++++++

.. _Menu-Options-Toolbar-Default:

Default:
  Shows labels and icons as defaulted in the GTK configuration.

.. _Menu-Options-Toolbar-Text_and_Icons:

Text and Icons:
  Shows labels and icons in the tool bar.

.. _Menu-Options-Toolbar-Icons:

Icons:
  Shows icons only in the tool bar.

.. _Menu-Options-Toolbar-Text:

Text:
  Shows labels only in the tool bar.

Menubar
+++++++

.. _Menu-Options-Menubar-Accelerators:

Change Accelerators:
  If checked, keyboard shortcuts can be defined. S. a. `mouse and keyboard use`_

Mode
++++

.. _Menu-Options-Mode-Normal:

Normal:
  Shows the client in full feature mode.

.. _Menu-Options-Mode_PDA:

PDA:
  Shows the client in a condensed mode.

Form
++++

.. _Menu-Options-Form-Toolbar:

Toolbar:
  Checkbox to disable/enable the tool bar.

.. _Menu-Options-Form-Save_Columns_Width:

Save Width/Height:
  Check box to enable saving of manually adjusted widths of columns in lists
  and trees. Additionally saving of manually adjusted widths and heights of
  dialog and popup windows.

.. _Menu-Options-Form-Save_Tree_State:

Save Tree Expanded State:
  Check box to enable saving of expanded and selected nodes in trees/lists.

.. _Menu-Options-Form-Fast_Tabbing:

Fast Tabbing:
  Check box to enable fast tabbing navigation by skipping readonly entries.

.. _Menu-Options-Form-Spell_Checking:

Spell Checking:
  Check box to enable spell checking in fields.

.. _Menu-Options-Email:

Email...:
  Open a dialog to set up an email reader.

  * Command Line: The command line calling the email reader.
  * Placeholders:

    - ``${to}``: the destination email address
    - ``${cc}``: the carbon copy email address
    - ``${subject}``: the subject of the email
    - ``${body}``: the body of the email
    - ``${attachment}``: the attachment of the email

  * Examples:

    - Thunderbird 2 on Linux:
      ``thunderbird -compose "to='${to}',cc='${cc}',subject='${subject}',body='${body}',attachment='file://${attachment}'"``

    - Thunderbird 2 on Windows XP SP3:
      ``"C:\\Program Files\\Mozilla Thunderbird\\thunderbird.exe" -compose to="${to}",cc="${cc}",subject="${subject}",body="${body}",attachment="${attachment}"``

.. note:: The path of *Program Files* may vary dependent on the localization of your Windows version.

.. _Menu-Options-Check_Version:

Check Version:
  Check box to enable the check of new bug-fix version.

.. _Menu-Options-Save_Options:

Save Options:
  Saves all the options.


Favorites
^^^^^^^^^
A collection of user defined menu favorites.


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
  Shows all email reports for the actual view, model and record.

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

.. warn::
    Under Windows, the datetime before 1970 are shown in UTC instead of the
    local timezone.
..

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

    * `window.profile-<name>`: the name of the connection profile is set on the
      main window

For more information about style option see `GTK+ CSS`_

.. GTK+ CSS:: https://developer.gnome.org/gtk3/stable/chap-css-overview.html

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
