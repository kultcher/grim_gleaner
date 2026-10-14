cmake_minimum_required(VERSION 3.24)
project(gg_hook LANGUAGES CXX)

# Grim Gleaner's in-game hook DLL.
#
# The game hands this DLL Microsoft C++ objects (std::string inside
# ItemReplicaInfo), so the shipped DLL MUST be built with MSVC, x64, against
# the shared runtime (/MD) with iterator debugging off. A layout mismatch here
# corrupts game memory instead of failing cleanly.

if(NOT CMAKE_SIZEOF_VOID_P EQUAL 8)
  message(FATAL_ERROR "gg_hook must be built for x64 (Grim Dawn is 64-bit).")
endif()

include(FetchContent)
FetchContent_Declare(
  detours
  GIT_REPOSITORY https://github.com/microsoft/Detours.git
  GIT_TAG v4.0.1
  GIT_SHALLOW TRUE
)
FetchContent_MakeAvailable(detours)
# FetchContent_MakeAvailable does nothing for a repo without CMakeLists, so
# build the library from its sources directly.
set(DETOURS_SRC ${detours_SOURCE_DIR}/src)
add_library(detours STATIC
  ${DETOURS_SRC}/detours.cpp
  ${DETOURS_SRC}/modules.cpp
  ${DETOURS_SRC}/disasm.cpp
  ${DETOURS_SRC}/image.cpp
  ${DETOURS_SRC}/creatwth.cpp
  ${DETOURS_SRC}/disolx86.cpp
  ${DETOURS_SRC}/disolx64.cpp
  ${DETOURS_SRC}/disolia64.cpp
  ${DETOURS_SRC}/disolarm.cpp
  ${DETOURS_SRC}/disolarm64.cpp
)
target_include_directories(detours PUBLIC ${DETOURS_SRC})
target_compile_definitions(detours PRIVATE WIN32_LEAN_AND_MEAN _WIN32_WINNT=0x0601)

add_library(gg_hook SHARED
  src/dllmain.cpp
  src/game_types.h
  src/hook_log.cpp
  src/hook_log.h
  src/reporter.cpp
  src/reporter.h
  src/tooltip_hook.cpp
  src/tooltip_hook.h
)
target_compile_features(gg_hook PRIVATE cxx_std_17)
target_link_libraries(gg_hook PRIVATE detours ws2_32)
target_compile_definitions(gg_hook PRIVATE WIN32_LEAN_AND_MEAN NOMINMAX UNICODE _UNICODE)

if(MSVC)
  # Same runtime and std::string layout as Game.dll in every configuration,
  # including Debug (which otherwise changes the layout of std::string).
  set_property(TARGET gg_hook detours PROPERTY
    MSVC_RUNTIME_LIBRARY "MultiThreadedDLL")
  target_compile_definitions(gg_hook PRIVATE _ITERATOR_DEBUG_LEVEL=0)
  target_compile_definitions(detours PRIVATE _ITERATOR_DEBUG_LEVEL=0)
  target_compile_options(gg_hook PRIVATE /W4 /EHa)
endif()
