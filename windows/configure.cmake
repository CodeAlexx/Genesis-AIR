# Extend the SDK graph without changing its checkout or sharing its build directory.
cmake_language(DEFER CALL include "${GENESIS_ROOT}/windows/audio.cmake")
if(GENESIS_TESTS)
  cmake_language(DEFER CALL include "${GENESIS_ROOT}/windows/targets.cmake")
endif()
