# Genesis Clip: the small video-dataset tool, linked like the SDK's external Windows
# application (see AIR_WINDOWS_APP_C in the SDK) but as a second executable beside Genesis-AIR.
if(GENESIS_CLIP_C AND EXISTS "${GENESIS_CLIP_C}")
  add_executable(genesis_clip_app "${GENESIS_CLIP_C}")
  target_include_directories(genesis_clip_app PRIVATE "${CMAKE_SOURCE_DIR}/runtime")
  target_link_libraries(genesis_clip_app PRIVATE air_rt)
  if(MSVC)
    target_compile_options(genesis_clip_app PRIVATE /W3)
    target_link_options(genesis_clip_app PRIVATE
      /SUBSYSTEM:WINDOWS
      /ENTRY:mainCRTStartup
      "/MANIFESTINPUT:${CMAKE_SOURCE_DIR}/cmake/windows-app.manifest")
  endif()
  set_target_properties(genesis_clip_app PROPERTIES
    OUTPUT_NAME "Genesis-Clip"
    RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin")
endif()
if(GENESIS_CLIP_TESTS AND EXISTS "${GENESIS_GENERATED_DIR}/clip-logic.c")
  add_executable(genesis-clip-logic "${GENESIS_GENERATED_DIR}/clip-logic.c")
  target_include_directories(genesis-clip-logic PRIVATE "${CMAKE_SOURCE_DIR}/runtime")
  target_link_libraries(genesis-clip-logic PRIVATE air_rt)
  set_target_properties(genesis-clip-logic PROPERTIES RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin")
endif()
