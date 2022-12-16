;This file is part of Tryton.  The COPYRIGHT file at the top level of
;this repository contains the full copyright notices and license terms.

;Check version
!ifndef VERSION
    !error "Missing VERSION! Specify it with '/DVERSION=<VERSION>'"
!endif

;General
Name "Tryton ${VERSION}"
OutFile "tryton-${VERSION}.exe"
SetCompressor lzma
SetCompress auto
SilentInstall silent
Icon "tryton\data\pixmaps\tryton\tryton.ico"

Section
    InitPluginsDir

    ;Set output path to the installation directory
    SetOutPath '$PLUGINSDIR'

    ;Put file
    File /r "dist\*"
    File "COPYRIGHT"
    File "INSTALL"
    File "LICENSE"
    File "README"
    File "CHANGELOG"

    SetOutPath "$PLUGINSDIR\doc"
    File /r "doc\*"

    ;Run the exe
    SetOutPath '$EXEDIR'
    nsExec::Exec $PLUGINSDIR\tryton.exe
SectionEnd
