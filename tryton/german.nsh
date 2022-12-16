;This file is part of Tryton.  The COPYRIGHT file at the top level of
;this repository contains the full copyright notices and license terms.

!verbose 3

!ifdef CURLANG
    !undef CURLANG
!endif
!define CURLANG ${LANG_GERMAN}

LangString LicenseText ${CURLANG} "Tryton wird unter der GNU General Public License wie von der Free Software Foundation veröffentlicht freigegeben, entweder Version 3 der Lizenz oder (nach Ihrer Wahl) jeder späteren Version. Bitte lesen Sie die Lizenz aufmerksam. Klicken Sie auf Weiter, um fortzufahren."
LangString LicenseNext ${CURLANG} "&Weiter"
LangString PreviousInstall ${CURLANG} "Tryton ist bereits installiert.$\n$\nWählen Sie `OK`, um die bisherige Version zu entfernen oder `Abbrechen` um die Aktualisierung abzubrechen."
LangString SecTrytonName ${CURLANG} "Tryton"
LangString SecTrytonDesc ${CURLANG} "tryton.exe und andere benötigte Dateien installieren"
LangString SecStartMenuName ${CURLANG} "Startmenü und Desktop-Verknüpfungen"
LangString SecStartMenuDesc ${CURLANG} "Verknüpfungen im Startmenü und auf dem Desktop erstellen"
