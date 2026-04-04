# This file will be configured to contain variables for CPack. These variables
# should be set in the CMake list file of the project before CPack module is
# included. The list of available CPACK_xxx variables and their associated
# documentation may be obtained using
#  cpack --help-variable-list
#
# Some variables are common to all generators (e.g. CPACK_PACKAGE_NAME)
# and some are specific to a generator
# (e.g. CPACK_NSIS_EXTRA_INSTALL_COMMANDS). The generator specific variables
# usually begin with CPACK_<GENNAME>_xxxx.


set(CPACK_BUILD_SOURCE_DIRS "/Users/alex/projects/guachin/agent/curl-8.16.0;/Users/alex/projects/guachin/agent/curl-8.16.0/build-win64")
set(CPACK_CMAKE_GENERATOR "Unix Makefiles")
set(CPACK_COMPONENT_UNSPECIFIED_HIDDEN "TRUE")
set(CPACK_COMPONENT_UNSPECIFIED_REQUIRED "TRUE")
set(CPACK_DEFAULT_PACKAGE_DESCRIPTION_FILE "/usr/local/RemoteDevelopmentToolkit/share/cmake-3.30/Templates/CPack.GenericDescription.txt")
set(CPACK_DEFAULT_PACKAGE_DESCRIPTION_SUMMARY "CURL built using CMake")
set(CPACK_GENERATOR "TGZ")
set(CPACK_INNOSETUP_ARCHITECTURE "x64")
set(CPACK_INSTALL_CMAKE_PROJECTS "/Users/alex/projects/guachin/agent/curl-8.16.0/build-win64;CURL;ALL;/")
set(CPACK_INSTALL_PREFIX "/usr/local")
set(CPACK_MODULE_PATH "/Users/alex/projects/guachin/agent/curl-8.16.0/CMake")
set(CPACK_NSIS_DISPLAY_NAME "CURL 8.16.0")
set(CPACK_NSIS_INSTALLER_ICON_CODE "")
set(CPACK_NSIS_INSTALLER_MUI_ICON_CODE "")
set(CPACK_NSIS_INSTALL_ROOT "$PROGRAMFILES64")
set(CPACK_NSIS_PACKAGE_NAME "CURL 8.16.0")
set(CPACK_NSIS_UNINSTALL_NAME "Uninstall")
set(CPACK_OBJCOPY_EXECUTABLE "/opt/homebrew/bin/x86_64-w64-mingw32-objcopy")
set(CPACK_OBJDUMP_EXECUTABLE "/opt/homebrew/bin/x86_64-w64-mingw32-objdump")
set(CPACK_OUTPUT_CONFIG_FILE "/Users/alex/projects/guachin/agent/curl-8.16.0/build-win64/CPackConfig.cmake")
set(CPACK_PACKAGE_DEFAULT_LOCATION "/")
set(CPACK_PACKAGE_DESCRIPTION_FILE "/usr/local/RemoteDevelopmentToolkit/share/cmake-3.30/Templates/CPack.GenericDescription.txt")
set(CPACK_PACKAGE_DESCRIPTION_SUMMARY "CURL built using CMake")
set(CPACK_PACKAGE_FILE_NAME "CURL-8.16.0-win64")
set(CPACK_PACKAGE_INSTALL_DIRECTORY "CURL 8.16.0")
set(CPACK_PACKAGE_INSTALL_REGISTRY_KEY "CURL 8.16.0")
set(CPACK_PACKAGE_NAME "CURL")
set(CPACK_PACKAGE_RELOCATABLE "true")
set(CPACK_PACKAGE_VENDOR "Humanity")
set(CPACK_PACKAGE_VERSION "8.16.0")
set(CPACK_PACKAGE_VERSION_MAJOR "8")
set(CPACK_PACKAGE_VERSION_MINOR "16")
set(CPACK_PACKAGE_VERSION_PATCH "0")
set(CPACK_READELF_EXECUTABLE "/opt/homebrew/bin/x86_64-w64-mingw32-readelf")
set(CPACK_RESOURCE_FILE_LICENSE "/usr/local/RemoteDevelopmentToolkit/share/cmake-3.30/Templates/CPack.GenericLicense.txt")
set(CPACK_RESOURCE_FILE_README "/usr/local/RemoteDevelopmentToolkit/share/cmake-3.30/Templates/CPack.GenericDescription.txt")
set(CPACK_RESOURCE_FILE_WELCOME "/usr/local/RemoteDevelopmentToolkit/share/cmake-3.30/Templates/CPack.GenericWelcome.txt")
set(CPACK_SET_DESTDIR "OFF")
set(CPACK_SOURCE_7Z "ON")
set(CPACK_SOURCE_GENERATOR "7Z;ZIP")
set(CPACK_SOURCE_OUTPUT_CONFIG_FILE "/Users/alex/projects/guachin/agent/curl-8.16.0/build-win64/CPackSourceConfig.cmake")
set(CPACK_SOURCE_ZIP "ON")
set(CPACK_SYSTEM_NAME "win64")
set(CPACK_THREADS "1")
set(CPACK_TOPLEVEL_TAG "win64")
set(CPACK_WIX_SIZEOF_VOID_P "8")

if(NOT CPACK_PROPERTIES_FILE)
  set(CPACK_PROPERTIES_FILE "/Users/alex/projects/guachin/agent/curl-8.16.0/build-win64/CPackProperties.cmake")
endif()

if(EXISTS ${CPACK_PROPERTIES_FILE})
  include(${CPACK_PROPERTIES_FILE})
endif()
