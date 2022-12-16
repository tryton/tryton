
:tocdepth: 2

Client Usage
############
This document is the reference about the concepts of the graphical user
interface (also known as *Tryton client* ) in the Tryton application framework.


Name
****
tryton - Graphical user client of the Tryton application framework


Synopsis
********

::

  tryton [options]

After start up, there raises the `login dialog`__ and optionally a
`tips dialog`__.

__ Menu-File-Connect_
__ Menu-Help-Tips_


Options
*******

--version                            Show program version number and exit

-h, --help                           Show help message and exit

-c FILE, --config=FILE               Specify alternate `configuration file`_

-v, --verbose                        Enable basic debugging

-l LOG_LEVEL, --log-level=LOG_LEVEL  Specify the log level: INFO, DEBUG,
                                     WARNING, ERROR, CRITICAL

-u LOGIN, --user=LOGIN               Specify the login user

-p PORT, --port=PORT                 Specify the server port

-s SERVER, --server=SERVER           Specify the server hostname


Overview
********
The following schematic illustration of the Tryton client shows the names of
all important visual parts.

Figure: Tryton client application::

  Client Window       _______________________________________________________
                     |                      Tryton                      _ o x|
                     |-------------------------------------------------------|
  Menu bar           | File User Form Options Plugins Shortcuts Help         |
                     |_______________________________________________________|
                     |                                                       |
  Tool bar           | New Save | Delete | Find Previous Next Switch    v    |
                     |-------------------------------------------------------|
                     |          ______                                       |
  Tab bar            | [Menu]  |[Tab1]| [Tab2] ...                           |
                     |---------|      | -------------------------------------|
                     | .-------        ------------------------------------. |
                     | |                                                   | |
                     | |                                                   | |
                     | |                                                   | |
                     | |                                                   | |
                     | |                                                   | |
  View               | |                                                   | |
                     | |                                                   | |
                     | |                                                   | |
                     | |                                                   | |
                     | |                                                   | |
                     | |                                                   | |
                     | |___________________________________________________| |
  View Status line   | | Record 1/2 - Editi...                             | |
                     | |___________________________________________________| |
                     |_______________________________________________________|
  Client Status line | user@localh...         user             Requests [] []|
                     |_______________________________________________________|

:TODO: Find a way for translatable illustrations, since SVG is not supported
       by many browsers...


Menu Bar
^^^^^^^^
The menu bar is the main control unit. It provides most of the functionalities
of the client application. The menu bar is grouped into categories. It is
controlled with mouse or keyboard. The `menu bar items`_ are explained later.


Mouse and Keyboard use
++++++++++++++++++++++
Most functions of the Tryton client can be used with mouse or keyboard.
`Key bindings`__ for all menu items are preset. Furthermore all key bindings
are manually configurable. To change the binding of a menu item the user needs
to put the cursor onto it and simply press the user defined key combination.
Usually key bindings are composed with modifier keys.

__ Menu-Help-Keyboard_Shortcuts_

Additionally the menu bar items are accessible with the *Alt* or *Option* key.
The user needs to hold the *Alt* or *Option* key followed by the underlined
character of the menu bar item to choose. To dive into deeper menu levels,
he needs to release the *Alt* or *Option* key and to simply press the
underlined letter of the sub menu item.

.. Warning:: Beware to hold the *Alt* or *Option* key on diving into sub menus.
   It will actually change the key binding for this menu item!

The second mouse button (usually right mouse button) provides an additional
contextual menu for some views and fields. In this context menu the user finds
:term:`actions` to copy and paste contents or setting up default values or
selections for several fields.

Drag and drop is provided for arranging tabs.


Tool Bar
^^^^^^^^
The tool bar contains some often used menu functions mapped to icons.

:TODO: Create a menu item for attachments and move the following paragraph
   to the menu item

In addition to the menu bar the tool bar contains a button called
*Attachment*. The attachment item handles the document management system of 
Tryton which is able to attach files to an arbitrary :term:`model`. The button
has two functions. It is showing how many attachments are linked to the 
current view. On click it opens the attachment :term:`dialog`. This dialog 
has the following layout:

* Preview: Show a preview picture of the selected attachment
* Description: Show and edit free text description for the selected attachment
* Attachment list: Show and select all attachments for the given resource
* Actions:

  - Save Text: Save the description text to the selected attachment.
  - Add File...: Add a file as attachment. A file dialog opens.
  - Add Link...: Add a link to a file as attachment. A file dialog opens.
  - Save as...: Save the selected attachment to the local file system.
  - Delete...: Delete the selected attachment.
  - Close


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

__ TDI_

.. _TDI: http://en.wikipedia.org/wiki/Tabbed_document_interface

.. Note:: Inside :term:`views` there could be tabs, too.

Main Menu
+++++++++
The first left tab contains the *main menu* (... not to mix up with
the menu bar!). The *main menu* does not contain fixed menu items.
All of them are dynamically provided by the actual set of the installed
:term:`modules` depending on the access rules of the current user. If a menu
item is clicked, the appropriate action will open in a new tab. As the figure
below illustrates, the *main menu* is split up in three frames.

The upper left frame contains the first or top level entries of the *main 
menu*. Standard top level entries are 'Administration' and 'Tryton'. 

.. note:: The *administration* menu will be explained in the modules 
   documentation for the 'IR' module, the *information repository*. 

The top level entry 'Tryton' connects to the website of the Tryton project.

The right frame is showing a :term:`tree view` substructure of menu *items*
and *headings*. With the arrow keys it is possible to navigate inside the menu.
By pressing *Enter* or double-clicking onto the menu item the appropriate
:term:`views` opens. Using left and right arrow to expand or contract sub 
items of a heading.

Figure: Main Menu Tab::

       ________________________________________________________
      |                      Tryton                       _ o x|
      |--------------------------------------------------------|
      | File User Form Options Plugins Shortcuts Help          |
      |________________________________________________________|
      |                                                        |
      | New Save | Delete | Find Previous Next Switch     v    |
      |________________________________________________________|
      |   ______                                               |
      |  |[Menu]|   [Tab1]   [Tab2] ...                        |
      |--|      | ---------------------------------------------|
      |  |       -------------.------------------------------. |
      |  | Top Level Entry 1  | Menu                |        | |
      |  | Top Level Entry 2  |---------------------+--------| |
      |  | ...                |   Item 1            |        | |
      |  | Administration     |   Item 2            |        | |
      |  | Tryton             | > Heading           |        | |
      |  |____________________|     Sub Item 1      |        | |
      |  | Shortcuts    [+][-]|     Sub Item 2      |        | |
      |  |--------------------|     > Sub Heading   |        | |
      |  | Sub Item 2         |         Sub Sub ... |        | |
      |  |                    |                     |        | |
      |  |                    |                     |        | |
      |  |____________________|_____________________|________| |
      |  | Record 1/2 - Editi...                             | |
      |  |___________________________________________________| |
      |________________________________________________________|
      | user@localh...         user              Requests [] []|
      |________________________________________________________|


The lower left menu frame shows a user adjustable *shortcuts* menu. This menu
is for collecting often used menu items. Using a *shortcut* item will open
the appropriate view in a new tab, just with a double mouse click.
A menu item is added to the *shortcut* menu by pushing the plus button [+]
in the *shortcut* menu. The minus button [-] in conjunction with a selected
*shortcut* item removes it from the *shortcut* list.

Home Action
+++++++++++
Another tab opens during the startup of the Tryton client: the home action. 
It is usually an item of the `Main Menu`_ which opens, when the user call his 
`Home`__ action defined in the `preferences`__.

__ Menu-Form-Home_

__ Menu-User-Preferences_

Status Lines
^^^^^^^^^^^^
The Tryton client provides two layers of *status lines*. One for the whole
client application, called *client status line* and one for the :term:`views`
residing in :term:`tabs`, called *view status line*.


Client Status Line
++++++++++++++++++
The client status line provides general informations of the state of the
Tryton client. It is divided in three parts.

* On its left side are details of the server connection shown including 
  database and user informations if connected. It is also noted there, if 
  there is no connection to a Tryton server at all. The left side information 
  of the client status line is build with the following pattern::

    <user-name>@<tryton-server-address>:<port>/<database-name>

* In the center the real name of the Tryton user is shown.
* The right side of the client status line provides informations about open
  requests for the actual user. There is also a button to create and to
  find allocated requests.


View Status Lines
+++++++++++++++++

Each tab has a separate *view status line* at the bottom, just above the 
client status line. The status line for :term:`views` in each tab inform on 
the one hand about the actual *position* (sequence) of the selected record and
on the other hand about the total count of records in the corresponding 
:term:`tree view`. The *id number* of the selected record is shown in 
parantheses. The view status line is build by the following pattern::

  Record: <pos> / <count> (id: <id>)


Menu Bar Items
**************
The following section describes the function of each menu bar entry in detail.
A rule of thumb: All items of the menu bar that are suffixed by three dots 
(...) will open an intermediate :term:`dialog` for setting up the provided 
menu action. Most dialogs provides a *Cancel* button, used to stop the 
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
   Default timout for logging out is six minutes.

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

.. warning:: Concider not to use this server-site maintaining functions 
             if there are security concerns. Since there are always security 
             concerns in a multiuser environment, better disclaim to provide 
             this functions on database level. 

.. note:: Postgres database names are restricted by some rules:

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
   and tool bar are de-activated.


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
    `main menu`_.
  * Home Action: Defines the action which is called as `home action`__.
  * Language: Language of the client appearance.
  * Timezone: The local timezone where the user/client resides.
  * Groups: Defines the users membership for accessing.

__ Menu-Form-Home_

.. _Menu-user-send-a-request:

Send a Request
  Opens a tab in :term:`form view` which eneable the user to send
  requests to other users of the same database.

.. _Menu-user-read-my-request:

Read my Requests
  Opens a tab in :term:`tree view` showing all requests depending to the
  actual user. Fields and actions of requests:

  * On top

    - From: User name of the sender
    - To: User name of the request receiver
    - References: Count of the attached references
    - Subject: The subject of the request.
    - Priority: An importance priority of the request.

      + High
      + Low
      + Normal

  * *Request* tab

    - Body: The textual part of the request.
    - History: The history of past reply to this request.

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

    - Send: Sends the actual message to receiver
    - Reply: Reply or answer the actual message
    - close: Closes the actual message

  * *References* tab

    - References

      + Reference: The reference type
      + (Target): Defines an reference attached to the request.

.. note:: When the talk is about requests, think of an internal system of
   Tryton, which is very similar to email.


Form
^^^^
The form menu contains functions for the *actual form* in the tab which
is open. Some operations are working with one record or with a selection of
:term:`records`. In :term:`form view` the actual record is selected for
operations. In :term:`tree view` all selected records are used for operations.

.. _Menu-Form-New:

New:
  Creates a new record.

.. _Menu-Form-Save:

Save:
  Saves the actual record.

.. _Menu-Form-Duplicate:

Duplicate:
  Duplicates the content of the actual record in a newly created record.

.. _Menu-Form-Delete:

Delete:
  Deletes the selected or actual record.

.. _Menu-Form-Find:

.. _search_widget:

Find...:
  Opens a :term:`dialog` for finding :term:`fields` with search criteria and
  operators.

  * Search criteria: Defines the aspects to seek for.
  * General search operators:

    - Equals: Search for results which exactly contain the following term.
    - Is Different: Search for results which are different to the following 
      term.

  * Additional search operators on numbers, amounts and strings:

    - Contains: Search for results which contain the following term.
    - Not Contains:  Search for results which do not include the
      following term.

  * Additional search operators for numbers and amounts:

    - Is Between: Search for results inside a range (from - to).
    - Is Not Between: Search for results outside a range (from - to).

  * Advanced Search expander opens additional search criteria.

    - Limit: Limits the count of results.
    - Offset: Skips a number of results and show only the following.

  * Actions:

    - Find: Search for results of the given criteria.
    - New: Create a new record (used when search was fruitless, to create
      quickly a new record).
    - Ok: Open the selected results.
    - Cancel

.. note:: De-activated records are only shown in the results, when the
         *Active* search criteria is set to *No*.

.. _Menu-Form-Next:

Next:
  Goes to the next record in a list (sequence).

.. _Menu-Form-Previous:

Previous:
  Goes to the last record in a list (sequence).

.. _Menu-Form-Switch_View:

Switch View:
  Switches the actual view aspect to:

  * :term:`Form view`
  * :term:`Tree view`
  * :term:`Graph view`

  Not all views provide all aspects.

.. _Menu-Form-Menu:

Menu:
  Activate or re-open the menu tab.

.. _Menu-Form-Home:

Home:
  Opens a new `home`__ tab.

__ Menu-User-Preferences_

.. _Menu-Form-Close:

Close:
  Closes the current tab. Request :term:`Dialog` in case of unsaved changes.

.. _Menu-Form-Previous_Tab:

Previous Tab:
  Shows the previous (left) tab of the actual tab.

.. _Menu-Form-Next_Tab:

Next Tab:
  Shows the next (right) tab of the actual tab.

.. _Menu-Form-View_Logs:

View Logs...:
  Shows generic information of the current record.

.. _Menu-Form-Go_to_Record_ID:

Go to Record ID...:
  Opens specific record id in the current view.

.. _Menu-Form-Reload_Undo:

Reload/Undo:
  Reloads the content of the actual tab.

.. _Menu-Form-Actions:

Actions...:
  Shows all actions for the actual view, model and record.

.. _Menu-Form-Print:

Print...:
  Shows all print actions for the actual view, model and record.

.. _Menu-Form-Export_Data:

Export Data...:
  Export of current/selected records into :term:`CSV`-file or open it in Excel.

  * Predefined exports

    - Choose preferences of already saved exports.

  * All Fields: Fields available from the model.
  * Fields to export: Defines the specific fields to export.
  * Options:

    - Save as CSV: Save export as a CSV file.
    - Open in Excel: Open export in an Excel table.

  * Add field names: Add a header row with field names to the export data.
  * Actions:

    - Add: Adds selected fields to *Fields to export*.
    - Remove: Removes selected fields from *Fields to export*.
    - Clear: Removes all fields from *Fields to export*.
    - Save Export: Saves field mapping to a *Predefined export* with a name.
    - Delete Export: Deletes a selected *Predefined export*.
    - Ok: Exports the data (action depending on *Options*).
    - Cancel

.. _Menu-Form-Import_Data:

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


Options
^^^^^^^
The Options menu sets up many visual and context depending preferences.


Menubar
+++++++

.. _Menu-Options-Menubar-Default:

Default:
  Shows labels and icons as defaulted in the GTK configuration.

.. _Menu-Options-Menubar-Text_and_Icons:

Text and Icons:
  Shows labels and icons in the tool bar.

.. _Menu-Options-Menubar-Icons:

Icons:
  Shows icons only in the tool bar.

.. _Menu-Options-Menubar-Text:

Text:
  Shows labels only in the tool bar.

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

.. _Menu-Options-Form-Save_Columns_Width:

Save Columns Width:
  Check box to enable saving of manually adjusted widths of columns in lists
  and trees.

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

.. _Menu-Options-Form-Tabs_Orientation:

Tabs Orientation
  Sets up the orientation of :term:`tabs` labels inside :term:`views`.

  * Horizontal: Shows tab labels oriented from left to right
  * Vertical: Shows tab labels oriented from bottom to top

.. _Menu-Options-File_Actions:

Files Actions...:
  Opens a dialog to setting up file types for print and open actions.
  Use ``%s`` as a placeholder for the document name.

  * Provided file types:

    - ODT file: Open Office Writer Document
    - PDF file: Adobes(TM) Portable Document Format
    - PNG file: Portable Network Graphics format
    - TXT file: Pure text file

  * Provided actions

    - Open: Setting up program system call which opens the specific file type.
    - Print: Setting up program system call printing the specific file type.

.. _Menu-Options-Save_Options:

Save Options:
  Saves all the options.


Plugins
^^^^^^^
Plug-ins are client side add-ons for Tryton. There are some included plug-ins
with the standard client.

Execute a Plugin
++++++++++++++++
Translate View:
  Creates a translation table of the current view.

Print Workflow:
  Creates a graph which shows the work flow of the current view.

Print Workflow (complex):
  Like 'Print Workflow', with additional sub work flows inherited by the 
  curret view.


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


Appendix
********


Configuration File
^^^^^^^^^^^^^^^^^^

::

   ~./tryton      # General configuration
   ~./trytonsc    # Shortcut configuration

:Authors:
  Udo Spallek, Bertrand Chenal, Mattias Behrle, Anne Krings

:TODO:
  * Search for TODO in this document.
  * More and less linking to glossary.
  * Check for mistakes.
  * Better/Corrected explanations
  * Check redundancies
