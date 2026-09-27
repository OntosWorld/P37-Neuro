#pragma once

#include "p37/loop.hpp"

#include <mutex>
#include <optional>
#include <string>
#include <vector>

#include <rclcpp/rclcpp.hpp>
#include <sensor_msgs/msg/joint_state.hpp>
#include <std_msgs/msg/bool.hpp>
#include <std_msgs/msg/float64_multi_array.hpp>

namespace p37 {

class Ros2JointBridge final : public ObservationSource, public CommandSink {
 public:
  Ros2JointBridge(rclcpp::Node& node, std::vector<std::string> joint_order,
                  std::string state_topic, std::string command_topic,
                  std::string stop_topic);

  [[nodiscard]] std::optional<ObservationFrame> read() override;
  void write(std::span<const JointCommand> commands) override;
  void stop() noexcept override;

 private:
  void on_joint_state(const sensor_msgs::msg::JointState& message);

  rclcpp::Node& node_;
  std::vector<std::string> joint_order_;
  rclcpp::Subscription<sensor_msgs::msg::JointState>::SharedPtr state_subscription_;
  rclcpp::Publisher<std_msgs::msg::Float64MultiArray>::SharedPtr command_publisher_;
  rclcpp::Publisher<std_msgs::msg::Bool>::SharedPtr stop_publisher_;
  std::mutex mutex_;
  std::optional<ObservationFrame> latest_;
};

}  // namespace p37
