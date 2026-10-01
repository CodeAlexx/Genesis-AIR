if(NOT WIN32 OR AIR_DESKTOP)
  message(FATAL_ERROR "Genesis Windows requires the native Win32/Direct2D host; GTK is forbidden")
endif()
add_library(genesis_native_audio SHARED "${GENESIS_ROOT}/windows/native_audio.cpp")
target_compile_features(genesis_native_audio PRIVATE cxx_std_17)
target_link_libraries(genesis_native_audio PRIVATE winmm)
set_target_properties(genesis_native_audio PROPERTIES OUTPUT_NAME "genesis-native-audio"
  RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin")
