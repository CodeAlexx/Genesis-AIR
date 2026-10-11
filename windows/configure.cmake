# Extend the SDK graph without changing its checkout or sharing its build directory.
# Genesis follows its audio clock; a canvas refresh wait must not hold up its
# preview consumer. The SDK default remains refresh-waiting for other products.
cmake_language(DEFER CALL target_compile_definitions air_rt PRIVATE AIR_WIN32_CANVAS_PRESENT_IMMEDIATE=1)
cmake_language(DEFER CALL include "${GENESIS_ROOT}/windows/audio.cmake")
if(GENESIS_TESTS)
  cmake_language(DEFER CALL include "${GENESIS_ROOT}/windows/targets.cmake")
endif()
