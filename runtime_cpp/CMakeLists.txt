cmake_minimum_required(VERSION 3.20)
project(p37_runtime LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

include(GNUInstallDirs)

add_library(p37_runtime STATIC src/runtime.cpp src/supervisor.cpp src/loop.cpp)
target_include_directories(
  p37_runtime
  PUBLIC
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
    $<INSTALL_INTERFACE:${CMAKE_INSTALL_INCLUDEDIR}>
)
target_compile_options(p37_runtime PRIVATE -Wall -Wextra -Wpedantic -Werror)

add_executable(p37_runtime_test tests/runtime_test.cpp)
target_link_libraries(p37_runtime_test PRIVATE p37_runtime)
target_compile_options(p37_runtime_test PRIVATE -Wall -Wextra -Wpedantic -Werror)

add_executable(p37_supervisor_test tests/supervisor_test.cpp)
target_link_libraries(p37_supervisor_test PRIVATE p37_runtime)
target_compile_options(p37_supervisor_test PRIVATE -Wall -Wextra -Wpedantic -Werror)

add_executable(p37_loop_test tests/loop_test.cpp)
target_link_libraries(p37_loop_test PRIVATE p37_runtime)
target_compile_options(p37_loop_test PRIVATE -Wall -Wextra -Wpedantic -Werror)

option(P37_BUILD_TENSORRT "Build the optional TensorRT inference engine" OFF)
if(P37_BUILD_TENSORRT)
  find_package(CUDAToolkit REQUIRED)
  find_path(
    TENSORRT_INCLUDE_DIR
    NvInfer.h
    HINTS "$ENV{TENSORRT_ROOT}/include"
    PATHS /usr/include /usr/include/x86_64-linux-gnu /usr/local/include
  )
  find_library(
    TENSORRT_NVINFER_LIBRARY
    nvinfer
    HINTS "$ENV{TENSORRT_ROOT}/lib" "$ENV{TENSORRT_ROOT}/lib64"
    PATHS /usr/lib /usr/lib/x86_64-linux-gnu /usr/local/lib
  )
  if(NOT TENSORRT_INCLUDE_DIR OR NOT TENSORRT_NVINFER_LIBRARY)
    message(FATAL_ERROR "TensorRT headers/library not found")
  endif()

  add_library(p37_tensorrt_engine STATIC tensorrt/src/tensorrt_engine.cpp)
  target_include_directories(
    p37_tensorrt_engine
    PUBLIC include tensorrt/include
    PRIVATE "${TENSORRT_INCLUDE_DIR}"
  )
  target_link_libraries(
    p37_tensorrt_engine
    PUBLIC p37_runtime
    PRIVATE CUDA::cudart "${TENSORRT_NVINFER_LIBRARY}"
  )
  target_compile_options(p37_tensorrt_engine PRIVATE -Wall -Wextra -Wpedantic -Werror)
endif()

option(P37_BUILD_ROS2_BRIDGE "Build the optional ROS 2 joint bridge" OFF)
if(P37_BUILD_ROS2_BRIDGE)
  find_package(ament_cmake REQUIRED)
  find_package(rclcpp REQUIRED)
  find_package(sensor_msgs REQUIRED)
  find_package(std_msgs REQUIRED)

  add_library(p37_ros2_bridge STATIC ros2_bridge/src/ros2_joint_bridge.cpp)
  target_include_directories(
    p37_ros2_bridge
    PUBLIC include ros2_bridge/include
  )
  target_link_libraries(p37_ros2_bridge PRIVATE p37_runtime)
  ament_target_dependencies(p37_ros2_bridge rclcpp sensor_msgs std_msgs)
  target_compile_options(p37_ros2_bridge PRIVATE -Wall -Wextra -Wpedantic -Werror)
endif()

enable_testing()
add_test(NAME p37_runtime_test COMMAND p37_runtime_test)
add_test(NAME p37_supervisor_test COMMAND p37_supervisor_test)
add_test(NAME p37_loop_test COMMAND p37_loop_test)

install(
  TARGETS p37_runtime
  ARCHIVE DESTINATION ${CMAKE_INSTALL_LIBDIR}
  LIBRARY DESTINATION ${CMAKE_INSTALL_LIBDIR}
  RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR}
)
install(DIRECTORY include/p37 DESTINATION ${CMAKE_INSTALL_INCLUDEDIR})
