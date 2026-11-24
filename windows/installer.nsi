; Jellyfin DB Editor 1.0.1 — Windows x86/x64 machine-wide installer
; Build with NSIS 3.11 (makensis). Contains both the x64 and x86 portable
; payloads and installs the one matching the current Windows architecture.

Unicode true
!include "MUI2.nsh"
!include "LogicLib.nsh"
!include "x64.nsh"
!include "WinVer.nsh"
!include "FileFunc.nsh"

!ifndef PAYLOAD_X64
  !define PAYLOAD_X64 "installer-payload-x64"
!endif
!ifndef PAYLOAD_X86
  !define PAYLOAD_X86 "installer-payload-x86"
!endif
!ifndef OUT_FILE
  !define OUT_FILE "jellyfin-db-editor_1.0.1_windows_x86_x64_setup.exe"
!endif
!ifndef APP_VERSION
  !define APP_VERSION "1.0.1"
!endif
!ifndef ICON_FILE
  !define ICON_FILE ""
!endif

!define APP_NAME "Jellyfin DB Editor"
!define APP_EXE "jellyfin-db-editor.exe"
!define APP_PUBLISHER "Jellyfin DB Editor contributors"
!define APP_URL "https://github.com/falezor/Jellyfin-Database-editor"
!define UNINST_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\JellyfinDbEditor"

Name "${APP_NAME}"
OutFile "${OUT_FILE}"
InstallDir "$PROGRAMFILES\Jellyfin DB Editor"
InstallDirRegKey HKLM "${UNINST_KEY}" "InstallLocation"
RequestExecutionLevel admin
SetCompressor /SOLID lzma
SetCompressorDictSize 64
BrandingText "${APP_NAME} ${APP_VERSION} — x86/x64"
ShowInstDetails show
ShowUninstDetails show
XPStyle on
ManifestDPIAware true

VIProductVersion "${APP_VERSION}.0"
VIAddVersionKey "ProductName" "${APP_NAME}"
VIAddVersionKey "FileDescription" "${APP_NAME} installer (x86/x64)"
VIAddVersionKey "FileVersion" "${APP_VERSION}"
VIAddVersionKey "ProductVersion" "${APP_VERSION}"
VIAddVersionKey "LegalCopyright" "MIT License — ${APP_PUBLISHER}"
VIAddVersionKey "OriginalFilename" "jellyfin-db-editor_${APP_VERSION}_windows_x86_x64_setup.exe"

!if "${ICON_FILE}" != ""
  Icon "${ICON_FILE}"
  !define MUI_ICON "${ICON_FILE}"
  !define MUI_UNICON "${ICON_FILE}"
!endif

!define MUI_ABORTWARNING
!define MUI_FINISHPAGE_LINK "Project page"
!define MUI_FINISHPAGE_LINK_LOCATION "${APP_URL}"

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "${PAYLOAD_X64}\LICENSE"
!insertmacro MUI_PAGE_COMPONENTS
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_UNPAGE_FINISH

!insertmacro MUI_LANGUAGE "English"
!insertmacro MUI_LANGUAGE "Polish"

LangString RequiresWin10 ${LANG_ENGLISH} "Jellyfin DB Editor requires Windows 10 or newer."
LangString RequiresWin10 ${LANG_POLISH} "Jellyfin DB Editor wymaga systemu Windows 10 lub nowszego."
LangString WebViewMissing ${LANG_ENGLISH} "Microsoft Edge WebView2 Runtime was not detected.$\r$\n$\r$\nThe application will still start and open in your default browser. Install WebView2 for the native window:$\r$\nhttps://go.microsoft.com/fwlink/p/?LinkId=2124703"
LangString WebViewMissing ${LANG_POLISH} "Nie wykryto środowiska Microsoft Edge WebView2.$\r$\n$\r$\nAplikacja nadal uruchomi się i otworzy w domyślnej przeglądarce. Zainstaluj WebView2, aby korzystać z natywnego okna:$\r$\nhttps://go.microsoft.com/fwlink/p/?LinkId=2124703"
LangString SecApp ${LANG_ENGLISH} "Application (required)"
LangString SecApp ${LANG_POLISH} "Aplikacja (wymagane)"
LangString SecAppDesc ${LANG_ENGLISH} "Installs Jellyfin DB Editor 1.0.1 and its Start Menu shortcut for all users. The x64 or x86 payload is selected automatically."
LangString SecAppDesc ${LANG_POLISH} "Instaluje Jellyfin DB Editor 1.0.1 i skrót w menu Start dla wszystkich użytkowników. Wersja x64 lub x86 jest wybierana automatycznie."
LangString SecDesktop ${LANG_ENGLISH} "Desktop shortcut"
LangString SecDesktop ${LANG_POLISH} "Skrót na pulpicie"
LangString SecDesktopDesc ${LANG_ENGLISH} "Creates a Jellyfin DB Editor shortcut on the desktop."
LangString SecDesktopDesc ${LANG_POLISH} "Tworzy skrót Jellyfin DB Editor na pulpicie."

Function .onInit
  !insertmacro MUI_LANGDLL_DISPLAY
  ${IfNot} ${AtLeastWin10}
    MessageBox MB_ICONSTOP "$(RequiresWin10)"
    Abort
  ${EndIf}
  ; Standard machine-wide location. The x64 payload goes to Program Files;
  ; the x86 payload goes to Program Files on 32-bit Windows.
  ReadRegStr $0 HKLM "${UNINST_KEY}" "InstallLocation"
  ${If} $0 == ""
    ${If} ${RunningX64}
      StrCpy $INSTDIR "$PROGRAMFILES64\Jellyfin DB Editor"
    ${Else}
      StrCpy $INSTDIR "$PROGRAMFILES32\Jellyfin DB Editor"
    ${EndIf}
  ${Else}
    StrCpy $INSTDIR $0
  ${EndIf}
FunctionEnd

Function ReadWebView2Version
  StrCpy $0 ""
  SetRegView 64
  ReadRegStr $0 HKLM "SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}" "pv"
  ${If} $0 == ""
    ReadRegStr $0 HKLM "SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}" "pv"
  ${EndIf}
  SetRegView 32
  ${If} $0 == ""
    ReadRegStr $0 HKLM "SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}" "pv"
  ${EndIf}
  ${If} $0 == ""
    ReadRegStr $0 HKCU "Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}" "pv"
  ${EndIf}
FunctionEnd

Function CheckWebView2
  Call ReadWebView2Version
  ${If} $0 == ""
    ${IfNot} ${Silent}
      MessageBox MB_ICONINFORMATION|MB_OK "$(WebViewMissing)"
    ${EndIf}
  ${EndIf}
FunctionEnd

Section "Application" SEC_APP
  SectionIn RO
  SetShellVarContext all
  SetOutPath "$INSTDIR"

  ; Replace the application files on upgrade, but keep user data
  ; (backups/, history/, tmp/, jf_browser.settings.json).
  RMDir /r "$INSTDIR\_internal"
  RMDir /r "$INSTDIR\licenses"
  Delete "$INSTDIR\${APP_EXE}"
  Delete "$INSTDIR\README.md"
  Delete "$INSTDIR\README-extensive.md"
  Delete "$INSTDIR\README-extensivePL.md"
  Delete "$INSTDIR\LICENSE"
  Delete "$INSTDIR\versions.md"
  Delete "$INSTDIR\wersje.md"
  Delete "$INSTDIR\BUILD-INFO.txt"
  Delete "$INSTDIR\RUN-ME.txt"
  Delete "$INSTDIR\SHA256SUMS.txt"
  Delete "$INSTDIR\Uninstall.exe"

  ${If} ${RunningX64}
    File /r "${PAYLOAD_X64}\*.*"
  ${Else}
    File /r "${PAYLOAD_X86}\*.*"
  ${EndIf}

  WriteUninstaller "$INSTDIR\Uninstall.exe"

  ; Remove shortcuts created by older builds with different casing.
  Delete "$SMPROGRAMS\Jellyfin DB editor\Jellyfin DB editor.lnk"
  Delete "$SMPROGRAMS\Jellyfin DB editor\Uninstall Jellyfin DB editor.lnk"
  RMDir "$SMPROGRAMS\Jellyfin DB editor"
  Delete "$DESKTOP\Jellyfin DB editor.lnk"

  CreateDirectory "$SMPROGRAMS\Jellyfin DB Editor"
  CreateShortCut "$SMPROGRAMS\Jellyfin DB Editor\Jellyfin DB Editor.lnk" "$INSTDIR\${APP_EXE}" "" "$INSTDIR\${APP_EXE}" 0 SW_SHOWNORMAL "" "Browse and edit the Jellyfin database."
  CreateShortCut "$SMPROGRAMS\Jellyfin DB Editor\Uninstall Jellyfin DB Editor.lnk" "$INSTDIR\Uninstall.exe"

  WriteRegStr HKLM "${UNINST_KEY}" "DisplayName" "${APP_NAME}"
  WriteRegStr HKLM "${UNINST_KEY}" "DisplayVersion" "${APP_VERSION}"
  WriteRegStr HKLM "${UNINST_KEY}" "Publisher" "${APP_PUBLISHER}"
  WriteRegStr HKLM "${UNINST_KEY}" "URLInfoAbout" "${APP_URL}"
  WriteRegStr HKLM "${UNINST_KEY}" "DisplayIcon" "$INSTDIR\${APP_EXE},0"
  WriteRegStr HKLM "${UNINST_KEY}" "InstallLocation" "$INSTDIR"
  WriteRegStr HKLM "${UNINST_KEY}" "UninstallString" '"$INSTDIR\Uninstall.exe"'
  WriteRegStr HKLM "${UNINST_KEY}" "QuietUninstallString" '"$INSTDIR\Uninstall.exe" /S'
  WriteRegDWORD HKLM "${UNINST_KEY}" "NoModify" 1
  WriteRegDWORD HKLM "${UNINST_KEY}" "NoRepair" 1
  WriteRegDWORD HKLM "${UNINST_KEY}" "EstimatedSize" 33000

  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\App Paths\${APP_EXE}" "" "$INSTDIR\${APP_EXE}"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\App Paths\${APP_EXE}" "Path" "$INSTDIR"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\App Paths\Jellyfin DB Editor.exe" "" "$INSTDIR\${APP_EXE}"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\App Paths\Jellyfin DB Editor.exe" "Path" "$INSTDIR"

  Call CheckWebView2
SectionEnd

Section /o "Desktop shortcut" SEC_DESKTOP
  SetShellVarContext all
  CreateShortCut "$DESKTOP\Jellyfin DB Editor.lnk" "$INSTDIR\${APP_EXE}" "" "$INSTDIR\${APP_EXE}" 0 SW_SHOWNORMAL "" "Browse and edit the Jellyfin database."
SectionEnd

!insertmacro MUI_FUNCTION_DESCRIPTION_BEGIN
  !insertmacro MUI_DESCRIPTION_TEXT ${SEC_APP} "$(SecAppDesc)"
  !insertmacro MUI_DESCRIPTION_TEXT ${SEC_DESKTOP} "$(SecDesktopDesc)"
!insertmacro MUI_FUNCTION_DESCRIPTION_END

Section "Uninstall"
  SetShellVarContext all

  Delete "$SMPROGRAMS\Jellyfin DB Editor\Jellyfin DB Editor.lnk"
  Delete "$SMPROGRAMS\Jellyfin DB Editor\Uninstall Jellyfin DB Editor.lnk"
  RMDir "$SMPROGRAMS\Jellyfin DB Editor"
  Delete "$DESKTOP\Jellyfin DB Editor.lnk"

  DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\App Paths\${APP_EXE}"
  DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\App Paths\Jellyfin DB Editor.exe"
  DeleteRegKey HKLM "${UNINST_KEY}"

  ; Installed application files. User data (backups/, history/, tmp/,
  ; jf_browser.settings.json) is intentionally left in place.
  RMDir /r "$INSTDIR\_internal"
  RMDir /r "$INSTDIR\licenses"
  Delete "$INSTDIR\${APP_EXE}"
  Delete "$INSTDIR\README.md"
  Delete "$INSTDIR\README-extensive.md"
  Delete "$INSTDIR\README-extensivePL.md"
  Delete "$INSTDIR\LICENSE"
  Delete "$INSTDIR\versions.md"
  Delete "$INSTDIR\wersje.md"
  Delete "$INSTDIR\BUILD-INFO.txt"
  Delete "$INSTDIR\RUN-ME.txt"
  Delete "$INSTDIR\SHA256SUMS.txt"
  Delete "$INSTDIR\Uninstall.exe"
  RMDir "$INSTDIR"
SectionEnd
