;This file is part of Tryton.  The COPYRIGHT file at the top level of
;this repository contains the full copyright notices and license terms.

;Check version
!ifndef VERSION
    !error "Missing VERSION! Specify it with '/DVERSION=<VERSION>'"
!endif
!ifndef GTKDIR
    !error "Missing GTKDIR! Specify it with '/DGTKDIR=<GTKDIR>'"
!endif

;General
Name "Tryton ${VERSION}"
OutFile "tryton-${VERSION}.exe"
SetCompressor lzma
SetCompress auto
SilentInstall silent
Icon "share\pixmaps\tryton\tryton.ico"

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
    File "TODO"
    File "CHANGELOG"

    SetOutPath "$PLUGINSDIR\GTK\bin"
    File /r "${GTKDIR}\bin\*"

    SetOutPath "$PLUGINSDIR\GTK\etc"
    File /r "${GTKDIR}\etc\*"

    SetOutPath "$PLUGINSDIR\GTK\lib"
    File /r "${GTKDIR}\lib\*"

    SetOutPath "$PLUGINSDIR\GTK\share\gtk-2.0"
    File /r "${GTKDIR}\share\gtk-2.0\*"

    SetOutPath "$PLUGINSDIR\GTK\share\gtkthemeselector"
    File /r "${GTKDIR}\share\gtkthemeselector\*"

    SetOutPath "$PLUGINSDIR\GTK\share\locale\de"
    File /r "${GTKDIR}\share\locale\de\*"

    SetOutPath "$PLUGINSDIR\GTK\share\locale\es"
    File /r "${GTKDIR}\share\locale\es\*"

    SetOutPath "$PLUGINSDIR\GTK\share\locale\fr"
    File /r "${GTKDIR}\share\locale\fr\*"

    SetOutPath "$PLUGINSDIR\GTK\share\themes"
    File /r "${GTKDIR}\share\themes\*"

    SetOutPath "$PLUGINSDIR\doc"
    File /r "doc\*"

    SetOutPath "$PLUGINSDIR\plugins"
    File /r "tryton\plugins\*"

    ;Run the exe
    SetOutPath '$EXEDIR'
    nsExec::Exec $PLUGINSDIR\tryton.exe
SectionEnd
