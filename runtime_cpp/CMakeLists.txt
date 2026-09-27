cmake_minimum_required(VERSION 3.20)
project(p37_runtime LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

add_library(p37_runtime STATIC src/runtime.cpp src/supervisor.cpp src/loop.cpp)
target_include_directories(p37_runtime PUBLIC include)
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
