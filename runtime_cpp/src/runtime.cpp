#include "p37/runtime.hpp"

#include <algorithm>
#include <cmath>
#include <utility>

namespace p37 {

SafetyEnvelope::SafetyEnvelope(std::vector<JointLimit> limits) {
  for (auto& limit : limits) {
    if (limit.name.empty()) {
      throw std::invalid_argument("joint name cannot be empty");
    }
    if (!limits_.emplace(limit.name, std::move(limit)).second) {
      throw std::invalid_argument("duplicate joint limit");
    }
  }
}

SafetyResult SafetyEnvelope::apply(std::span<const JointCommand> commands) const {
  SafetyResult result;
  result.commands.reserve(commands.size());

  for (const auto& command : commands) {
    if (!std::isfinite(command.value)) {
      throw UnsafeCommand("non-finite joint command");
    }
    const auto found = limits_.find(command.name);
    if (found == limits_.end()) {
      throw UnsafeCommand("unknown joint command: " + command.name);
    }

    const auto& limit = found->second;
    double safe_value = command.value;
    if (limit.mode == ControlMode::position) {
      if (!limit.minimum || !limit.maximum) {
        throw UnsafeCommand("position joint has no bounds: " + command.name);
      }
      safe_value = std::clamp(command.value, *limit.minimum, *limit.maximum);
      if (safe_value != command.value) {
        result.clamped_joints.push_back(command.name);
      }
    } else {
      if (!limit.magnitude_limit) {
        throw UnsafeCommand("rate/effort joint has no magnitude limit: " + command.name);
      }
      if (std::abs(command.value) > *limit.magnitude_limit) {
        throw UnsafeCommand("rate/effort command exceeds limit: " + command.name);
      }
    }
    result.commands.push_back({command.name, safe_value});
  }

  return result;
}

}  // namespace p37
