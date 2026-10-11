# Portable no-replace file publication helper. It is not a media worker.
add_executable(air_file_publish "${GENESIS_ROOT}/native/file_publish.c")
set_target_properties(air_file_publish PROPERTIES OUTPUT_NAME "air-file-publish"
  RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin")
if(GENESIS_TESTS)
  add_executable(genesis-export-ownership-worker "${GENESIS_ROOT}/tests/export_ownership_worker.c")
  set_target_properties(genesis-export-ownership-worker PROPERTIES
    RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin")
endif()
