#include "p37/ros2_joint_bridge.hpp"

#include <algorithm>
#include <cstdint>
#include <stdexcept>
#include <unordered_map>
#include <utility>

namespace p37 {

Ros2JointBridge::Ros2JointBridge(rclcpp::Node& node, std::vector<std::string> joint_order,
                                 std::string state_topic, std::string command_topic,
                                 std::string stop_topic)
    : node_(node), joint_order_(std::move(joint_order)) {
  if (joint_order_.empty()) {
    throw std::invalid_argument("ROS 2 bridge requires a non-empty joint order");
  }

  state_subscription_ = node_.create_subscription<sensor_msgs::msg::JointState>(
      std::move(state_topic), rclcpp::SensorDataQoS(),
      [this](const sensor_msgs::msg::JointState& message) { on_joint_state(message); });
  command_publisher_ =
      node_.create_publisher<std_msgs::msg::Float64MultiArray>(std::move(command_topic), 10);
  stop_publisher_ = node_.create_publisher<std_msgs::msg::Bool>(std::move(stop_topic), 10);
}

std::optional<ObservationFrame> Ros2JointBridge::read() {
  std::scoped_lock lock(mutex_);
  return latest_;
}

void Ros2JointBridge::write(std::span<const JointCommand> commands) {
  if (commands.size() != joint_order_.size()) {
    throw std::runtime_error("command count does not match configured joint order");
  }

  std_msgs::msg::Float64MultiArray message;
  message.data.reserve(commands.size());
  for (std::size_t index = 0; index < commands.size(); ++index) {
    if (commands[index].name != joint_order_[index]) {
      throw std::runtime_error("command joint order mismatch");
    }
    message.data.push_back(commands[index].value);
  }

  std_msgs::msg::Bool stop_message;
  stop_message.data = false;
  stop_publisher_->publish(stop_message);
  command_publisher_->publish(message);
}

void Ros2JointBridge::stop() noexcept {
  try {
    std_msgs::msg::Bool message;
    message.data = true;
    stop_publisher_->publish(message);
  } catch (...) {
  }
}

void Ros2JointBridge::on_joint_state(const sensor_msgs::msg::JointState& message) {
  if (message.position.size() != message.name.size() ||
      message.velocity.size() != message.name.size()) {
    return;
  }

  std::unordered_map<std::string, std::size_t> index;
  index.reserve(message.name.size());
  for (std::size_t item = 0; item < message.name.size(); ++item) {
    index.emplace(message.name[item], item);
  }

  std::vector<double> values;
  values.reserve(joint_order_.size() * 2);
  for (const auto& joint : joint_order_) {
    const auto found = index.find(joint);
    if (found == index.end()) {
      return;
    }
    values.push_back(message.position[found->second]);
  }
  for (const auto& joint : joint_order_) {
    const auto found = index.find(joint);
    values.push_back(message.velocity[found->second]);
  }

  const auto timestamp_ns =
      static_cast<std::int64_t>(message.header.stamp.sec) * 1'000'000'000LL +
      static_cast<std::int64_t>(message.header.stamp.nanosec);

  std::scoped_lock lock(mutex_);
  latest_ = ObservationFrame{std::move(values), timestamp_ns};
}

}  // namespace p37
