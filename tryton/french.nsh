;This file is part of Tryton.  The COPYRIGHT file at the top level of
;this repository contains the full copyright notices and license terms.

!verbose 3

!ifdef CURLANG
    !undef CURLANG
!endif
!define CURLANG ${LANG_FRENCH}

LangString LicenseText ${CURLANG} "Tryton est publié sous la GNU General Public License comme publiée par la Free Software Foundation, soit la version 3 de la License, ou (à votre choix) toute version ultérieure. S'il vous plaît lisez attentivement la license. Cliquez sur Suivant pour continuer."
LangString LicenseNext ${CURLANG} "&Suivant"
LangString PreviousInstall ${CURLANG} "Tryton est déjà installé.$\n$\nCliquez `OK` pour supprimer la précédente version ou `Annuler` pour annuler cette mis à jour."
LangString SecTrytonName ${CURLANG} "Tryton"
LangString SecTrytonDesc ${CURLANG} "Installe tryton.exe et d'autres fichiers requis"
LangString SecStartMenuName ${CURLANG} "Raccourcis dans le menu Démarrer et sur le bureau"
LangString SecStartMenuDesc ${CURLANG} "Crée les raccourcis dans le menu Démarrer et sur le bureau"
