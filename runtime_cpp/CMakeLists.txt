cmake_minimum_required(VERSION 3.20)
project(p37_runtime LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

add_library(p37_runtime STATIC src/runtime.cpp)
target_include_directories(p37_runtime PUBLIC include)
target_compile_options(p37_runtime PRIVATE -Wall -Wextra -Wpedantic -Werror)

add_executable(p37_runtime_test tests/runtime_test.cpp)
target_link_libraries(p37_runtime_test PRIVATE p37_runtime)
target_compile_options(p37_runtime_test PRIVATE -Wall -Wextra -Wpedantic -Werror)

enable_testing()
add_test(NAME p37_runtime_test COMMAND p37_runtime_test)
