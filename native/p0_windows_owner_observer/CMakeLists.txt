cmake_minimum_required(VERSION 3.25)

project(p0_windows_owner_observer LANGUAGES CXX RC)

if(NOT MSVC OR NOT CMAKE_SIZEOF_VOID_P EQUAL 8)
  message(FATAL_ERROR "This bounded candidate requires the MSVC x64 toolchain")
endif()

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(CMAKE_MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>")

add_library(p0_owner_observer_core STATIC
  observer_candidate.cpp
  observer_candidate.hpp
)

target_compile_definitions(p0_owner_observer_core PRIVATE
  UNICODE
  _UNICODE
  WIN32_LEAN_AND_MEAN
  NOMINMAX
  _WIN32_WINNT=0x0A00
  NTDDI_VERSION=0x0A00000C
  PSAPI_VERSION=2
)

target_compile_options(p0_owner_observer_core PRIVATE
  /W4
  /WX
  /permissive-
  /EHsc
  /utf-8
  /GS
  /sdl
  /guard:cf
  /guard:ehcont
  /Brepro
  /Zc:__cplusplus
  /Zc:inline
  /Zc:wchar_t
)

add_executable(p0_windows_owner_observer_service
  p0_owner_observer_service.cpp
  observer_resources.rc
)

add_executable(p0_windows_owner_observer_diagnostic
  p0_owner_observer_diagnostic.cpp
)

foreach(target IN ITEMS
    p0_windows_owner_observer_service
    p0_windows_owner_observer_diagnostic)
  target_link_libraries(${target} PRIVATE
    p0_owner_observer_core
    advapi32
    bcrypt
  )
  target_compile_definitions(${target} PRIVATE
    UNICODE
    _UNICODE
    WIN32_LEAN_AND_MEAN
    NOMINMAX
    _WIN32_WINNT=0x0A00
  )
  target_compile_options(${target} PRIVATE
    /W4
    /WX
    /permissive-
    /EHsc
    /utf-8
    /GS
    /sdl
    /guard:cf
    /guard:ehcont
    /Brepro
    /Zc:__cplusplus
  )
  target_link_options(${target} PRIVATE
    /guard:cf
    /guard:ehcont
    /CETCOMPAT
    /DYNAMICBASE
    /NXCOMPAT
    /HIGHENTROPYVA
    /LARGEADDRESSAWARE
    /DEPENDENTLOADFLAG:0x800
    /Brepro
    /WX
    /INCREMENTAL:NO
    /OPT:REF
    /OPT:ICF
    /MANIFEST:EMBED
  )
endforeach()

set_target_properties(p0_windows_owner_observer_service PROPERTIES
  OUTPUT_NAME "llm-novel-dc-owner-verifier"
)
