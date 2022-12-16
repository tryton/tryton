;This file is part of Tryton.  The COPYRIGHT file at the top level of
;this repository contains the full copyright notices and license terms.

!verbose 3

!ifdef CURLANG
    !undef CURLANG
!endif
!define CURLANG ${LANG_ENGLISH}

LangString LicenseText ${CURLANG} "Tryton is released under the GNU General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version. Please carefully read the license. Click Next to continue."
LangString LicenseNext ${CURLANG} "&Next"
LangString PreviousInstall ${CURLANG} "Tryton is already installed.$\n$\nClick `OK` to remove the previous version or `Cancel` to cancel this upgrade."
LangString SecTrytonName ${CURLANG} "Tryton"
LangString SecTrytonDesc ${CURLANG} "Install tryton.exe and other required files"
LangString SecStartMenuName ${CURLANG} "Start Menu and Desktop Shortcuts"
LangString SecStartMenuDesc ${CURLANG} "Create shortcuts in the start menu and on desktop"
