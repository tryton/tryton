
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

After startup, there raises the `login dialog`__ and optionally a
`tips dialog`__.

__ Menu-File-Connect_
__ Menu-Help-Tips_


Options
*******

--version                            Show program version number and exit

-h, --help                           Show help message and exit

-c FILE, --config=FILE               Specify alternate `configuration file`_

-v, --verbose                        Enable basic debugging

-d LOG_LOGGER, --log=LOG_LOGGER      Specify channels to log (ex: rpc.request, rpc.result, ...)

-l LOG_LEVEL, --log-level=LOG_LEVEL  Specify the log level: INFO, DEBUG,
                                     WARNING, ERROR, CRITICAL

-u LOGIN, --user=LOGIN               Specify the login user

-p PORT, --port=PORT                 Specify the server port

-s SERVER, --server=SERVER           Specify the server hostname

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
  Menu bar           | File User Options Plugins Shortcuts Help                       |
                     |________________________________________________________________|
                     |             |          ______                                  |
  Tabs               | Menu        |  [Tab1] |[Tab2]| [Tab3]...                       |
                     |-------------| +-------+      +--------------------------------+|
                     | +           | | Tab2                                          ||
                     | |-+         | |-----------------------------------------------||
  Tool bar           | | |-        | | New Save|Delete|Find Previous Next Switch   v ||
                     | | |-        | |-----------------------------------------------||
                     | +           | |                                               ||
                     | |-+         | |                                               ||
                     | | |-        | |                                               ||
                     | | |-        | |                                               ||
                     | +           | |                                               ||
  View               | |-+         | |                                               ||
                     |   |-        | |                                               ||
                     |   |-        | |                                               ||
                     |             | |                                               ||
                     |             | |                                               ||
                     |             | |                                               ||
                     |             | |                                               ||
                     |             | |                                               ||
                     |_____________| |_______________________________________________||
                     |________________________________________________________________|
  Status bar         |username company           Waiting requests...         login@...|
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


Home
++++
A tab opens during the startup of the Tryton client: the home.  It is
usually an item of the `Menu`_ opening when the user calls his
`Home`__ action defined in the `preferences`__.

__ Menu-User-Home_

__ Menu-User-Preferences_


Status bar
++++++++++
The status bar provides general informations of the state of the
Tryton client. It is divided in three parts.

* On its left side the real name and company name of the users actual company
  is shown.
* In the center of the status bar the number of waiting requests for the
  actual user are displayed.
* On its right side are details of the server connection shown including
  database and user informations if connected. It is also noted there, if
  there is no connection to a Tryton server at all. The right side information
  of the status bar is build with the following pattern::

    <user-name>@<tryton-server-address>:<port>/<database-name>

  If the client is connected to the server with an SSL-secured connection, an
  additional lock icon appears rightmost some certificate details in a mouse
  hover popup.

The Status bar can be enabled and disabled in the menu at
Options > Form > Status bar


Menu Bar Items
**************
The following section describes the function of each menu bar entry in detail.
A rule of thumb: All items of the menu bar that are suffixed by three dots
(...) will open an intermediate :term:`dialog` for setting up the provided
menu action. Most dialogs provide a *Cancel* button, used to stop the
complete dialog process.


File
^^^^
The file menu level provides functions about Tryton server login,
Database maintenance and closing the client application.

.. _Menu-File-Connect:

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

__ File-Server-Connection_


.. _Menu-File-Disconnect:

Disconnect...
  Disconnects the client from an active server connection. In case of unsaved
  changes in an open tab, the Tryton client will request for saving the
  changes.

Database
++++++++
This menu level provides tools to maintain Tryton databases.
For all database operations the user needs to know the Tryton server password.

.. warning:: Consider not to use this server-site maintaining functions,
             if there are security concerns. Since there are always security
             concerns in a multiuser environment, better disclaim to provide
             these functions on database level.

.. note:: Database names are restricted by some rules:

          * Allowed characters are alpha-nummeric [A-Za-z0-9] and
            underscore (_).
          * First character must be an alphabetic letter.
          * The maximum length of a database name is 64 characters.

          Tryton automatically checks if the given database name follows
          the rules.

.. _Menu-File-New_Database:

New Database
  Opens a :term:`dialog` for creating a new Tryton database with an initial
  user called *admin*.

  * Server Setup:

    - `Server Connection`__
    - Tryton Server Password: The password given in the Tryton server
      configuration.

  * New Database Setup:

    - Database Name: The name of the new database.
    - Default Language: The default language of the new database.
    - Admin Password: The *admin*-user password of the new database.
    - Confirm Admin Password: Repeat the password of the new 'admin' user.

  * Actions:

    - Create: Creates the new database with initial user *admin* and the
      provided password.
    - Cancel

__ File-Server-Connection_

.. note:: The appropriate Tryton database user (defined in the Tryton server
   configuration) needs to be authorized to create databases for this step.

.. _Menu-File-Restore_Database:

Restore Database
  Opens a :term:`dialog` to restore a previously created database backup
  file.

  * File choose menu dialog

    - Choose a database backup file in the file system to be restored.
    - Actions:

      + Open: Open the chosen backup file.
      + Cancel

  * Restore Database dialog:

    - `Server Connection`__
    - Tryton Server Password: The password given in the Tryton server
      configuration.
    - File to Restore: Show filename and path.
    - New Database Name: Enter a new name for the database to be restored
    - Actions:

      + Restore: Proceed database restore.
      + Cancel

__ File-Server-Connection_

.. _Menu-File-Backup_Database:

Backup Database
  Open a :term:`dialog` to backup an existing database and save it as a file.

  * `Backup a Database` dialog

    - `Server connection`__
    - Database: Choose the Tryton database to backup.
    - Tryton Server Password: The password given in the Tryton server
      configuration.
    - Actions:

      + Backup: Proceed database backup.
      + Cancel

  * `Save Backup File` dialog

    - Choose a filename and location for the created backup file.
    - Save the backup file.

__ File-Server-Connection_

.. _Menu-File-Drop_Database:

Drop Database
  Open a :term:`dialog` to delete an existing Tryton database.

  * `Delete a Database` dialog

    - `Server Connection`__
    - Database: Choose a database to delete.
    - Tryton Server Password: The password given in the Tryton server
      configuration.

  * Confirmation Dialog

    - Yes: Drop the database
    - No: Do not drop the database
    - Cancel

__ File-Server-Connection_

.. _File-Server-Connection:

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
This menu bar item controls the preferences of the actual user and connects
to the *request system* in Tryton.

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
  * Home Action: Defines the action which is called as `Home`__.
  * Language: Language of the client interface.
  * Timezone: The local timezone where the user/client resides.
  * Groups: Displays the users membership to access groups.

.. _Menu-User-Menu-Reload:

Menu Reload:
  Reload the menu.

.. _Menu-User-Menu-Toggle:

Menu Toggle:
  Toggle the menu visibility

.. _Menu-User-Home:

Home:
  Opens a new `Home`__ tab.

.. _Menu-User-send-a-request:

Send a Request
  Opens a tab in :term:`form view` which enables the user to send
  requests to other users of the same database.

.. _Menu-User-read-my-request:

Read my Requests
  Opens a tab in :term:`tree view` showing all requests related to the
  actual user. Fields and actions of requests:

  * On top

    - From: User name of the sender
    - To: User name of the request recipient
    - References: Count of the attached references
    - Subject: The subject of the request.
    - Priority: An importance priority of the request.

      + High
      + Low
      + Normal

  * *Request* tab

    - Body: The textual part of the request.
    - History: The history of past replies to this request.

      + From: Sender of the past request
      + To: Receiver of the past request
      + Summary: Summary of the body text of the past request.

  * Trigger Date: Defines time and date when the request will be sent
    automatically.
  * State: State of the request. Possible states for the request are:

    - Draft: The request is saved in the system, but not posted.
    - Waiting: The request is sent without receiving a reply message.
    - Chatting: The message is replied or in discussion.
    - Closed: The message is closed/fulfilled/answered.

  * Actions:

    - Send: Sends the actual message
    - Reply: Replies or answers the actual message
    - close: Closes the actual message

  * *References* tab

    - References

      + Reference: The reference type
      + (Target): Defines an reference attached to the request.

.. note:: When talking about requests, think of an internal system of
   Tryton, which is very similar to email.


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
  Shows the client in a condensed mode. The PDA (Personal Data Assistant) mode
  hides the shortcut menu in tree views and the system status bar.

Form
++++

.. _Menu-Options-Form-Toolbar:

Toolbar:
  Checkbox to disable/enable the tool bar.

.. _Menu-Options-Form-Statusbar:

Statusbar:
  Checkbox to disable/enable the status bar.

.. _Menu-Options-Form-Save_Columns_Width:

Save Width/Height:
  Check box to enable saving of manually adjusted widths of columns in lists
  and trees. Additionally saving of manually adjusted widths and heights of
  dialog and popup windows.

.. _Menu-Options-Form-Spell_Checking:

Spell Checking:
  Check box to enable spell checking in fields.

.. _Menu-Options-Form-Tabs_Position:

Tabs Position
  Sets up the position of the :term:`tabs` inside :term:`views`:

  * Top
  * Left
  * Right
  * Bottom

.. _Menu-Options-File_Actions:

File Actions...:
  Opens a dialog to set up file types for print and open actions.
  Use ``"%s"`` as a placeholder for the document name.

  * Provided file types:

    - ODT file: Open Office Writer Document
    - PDF file: Adobes(TM) Portable Document Format
    - PNG file: Portable Network Graphics format
    - TXT file: Pure text file

  * Provided actions

    - Open: Setting up program system call which opens the specific file type.
    - Print: Setting up program system call printing the specific file type.

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

.. _Menu-Options-Save_Options:

Save Options:
  Saves all the options.


Plug-ins
^^^^^^^^
Plug-ins are client side add-ons for Tryton. There are some included plug-ins
with the standard client.

Execute a Plug-in
+++++++++++++++++
Translate View:
  Creates a translation table of the current view.

Print Workflow:
  Creates a graph which shows the work flow of the current view.

Print Workflow (complex):
  Like 'Print Workflow', with additional sub work flows inherited by the
  current view.


Shortcuts
^^^^^^^^^
A collection of user defined shortcuts for specific resources.


Help
^^^^

.. _Menu-Help-Tips:

Tips...:
  Opens the tips dialog.

  * Display a new tip next time: If *checked*, the tips dialog will appear on
    start.
  * Previous: Shows last tip.
  * Next: Shows next tip.

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
The tool bar contains functions for the current tab.
Some operations are working with one record or with a selection of
:term:`records`. In :term:`form view` the actual record is selected for
operations. In :term:`tree view` all selected records are used for operations.

.. _Toolbar-New:

New:
  Creates a new record.

.. _Toolbar-Save:

Save:
  Saves the actual record.

.. _Toolbar-Duplicate:

Duplicate:
  Duplicates the content of the actual record in a newly created record.

.. _Toolbar-Delete:

Delete:
  Deletes the selected or actual record.

.. _Toolbar-Find:

.. _search_widget:

Find...:
  Opens a :term:`dialog` for finding :term:`fields` with search criteria and
  operators.

  * Search criteria: Defines the aspects to seek for.
  * General search operators:

    - Equals: Search for results which are exactly the same as the following
      term.
    - Does Not Equal: Search for results which are different from the following
      term.

  * Additional search operators on numbers, amounts and strings:

    - Contains: Search for results which contain the following term.
    - Does Not Contain:  Search for results which do not include the
      following term.
    - Starts With: Search for results beginning with the following term.
    - Ends With: Search for results ending with the following term.

  * Additional search operators for numbers and amounts:

    - Is Between: Search for results inside a range (from - to).
    - Is Not Between: Search for results outside a range (from - to).
    - Is Different: Same as 'Does Not Equal', see above.

  * Advanced Search expander opens additional search criteria.

    - Limit: Limits the count of results.
    - Offset: Skips a number of results and show only the following.

  * Actions:

    - Find: Search for results of the given criteria.
    - New: Create a new record (used when search was fruitless, to create
      quickly a new record).
    - Ok: Open the selected results.
    - Cancel

.. note:: To search for deactivated records the *Active* search criteria must be
        set to *No*.

.. _Toolbar-Next:

Next:
  Goes to the next record in a list (sequence).

.. _Toolbar-Previous:

Previous:
  Goes to the last record in a list (sequence).

.. _Toolbar-Switch_View:

Switch View:
  Switches the actual view aspect to:

  * :term:`Form view`
  * :term:`Tree view`
  * :term:`Graph view`

  Not all views provide all aspects.

.. _Toolbar-Close:

Close Tab:
  Closes the current tab. A Request :term:`Dialog` opens in case of unsaved
  changes.

.. _Toolbar-Previous_Tab:

Previous Tab:
  Shows the previous (left) tab of the actual tab.

.. _Toolbar-Next_Tab:

Next Tab:
  Shows the next (right) tab of the actual tab.

.. _Toolbar-View_Logs:

View Logs...:
  Shows generic information of the current record.

.. _Toolbar-Go_to_Record_ID:

Go to Record ID...:
  Opens specific record id in the current view.

.. _Toolbar-Reload_Undo:

Reload/Undo:
  Reloads the content of the actual tab. Undoes changes, if save request for
  the current record is denied.

.. _Toolbar-Actions:

Actions...:
  Shows all actions for the actual view, model and record.

.. _Toolbar-Print:

Print...:
  Shows all print actions for the actual view, model and record.

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
    - Ok: Exports the data (action depending on *Options*).
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
    - Ok: Proceeds the data import.
    - Cancel

.. _Toolbar-Attachment:

Attachment:
  The attachment item handles the document management system of
  Tryton which is able to attach files to any arbitrary :term:`model`.
  On click it opens the attachments :term:`dialog`. The default dialog
  shows a list view of the attached files and links.


Appendix
********


Configuration File
^^^^^^^^^^^^^^^^^^

::

   ~/.config/tryton/x.y/tryton.conf      # General configuration
   ~/.config/tryton/x.y/accel.map        # Accelerators configuration
   ~/.config/tryton/x.y/known_hosts      # Fingerprints
   ~/.config/tryton/x.y/ca_certs         # Certification Authority (http://docs.python.org/library/ssl.html#ssl-certificates)

