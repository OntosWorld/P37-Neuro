#include "p37/supervisor.hpp"

#include <cmath>
#include <exception>
#include <stdexcept>
#include <utility>

namespace p37 {

RuntimeSupervisor::RuntimeSupervisor(InferenceEngine& engine,
                                     std::vector<JointLimit> ordered_limits,
                                     RuntimeConfig config)
    : engine_(engine),
      ordered_limits_(std::move(ordered_limits)),
      safety_(ordered_limits_),
      config_(config) {
  if (ordered_limits_.empty()) {
    throw std::invalid_argument("runtime requires at least one controlled joint");
  }
  if (config_.max_observation_age_ns <= 0) {
    throw std::invalid_argument("max_observation_age_ns must be positive");
  }
}

void RuntimeSupervisor::reset(std::string_view embodiment_id) {
  engine_.reset(embodiment_id);
}

RuntimeDecision RuntimeSupervisor::evaluate(std::span<const double> observation,
                                            std::int64_t observation_time_ns,
                                            std::int64_t now_ns) const noexcept {
  if (now_ns < observation_time_ns) {
    return {RuntimeStatus::clock_error, {}, "observation timestamp is in the future"};
  }
  if (now_ns - observation_time_ns > config_.max_observation_age_ns) {
    return {RuntimeStatus::stale_observation, {}, "observation exceeded freshness limit"};
  }

  try {
    const auto normalized = engine_.infer(observation);
    if (normalized.size() != ordered_limits_.size()) {
      return {RuntimeStatus::shape_mismatch, {}, "inference output does not match joint count"};
    }
    const auto physical = to_physical(normalized);
    const auto safe = safety_.apply(physical);
    return {RuntimeStatus::allowed, safe.commands, {}};
  } catch (const UnsafeCommand& error) {
    return {RuntimeStatus::unsafe_command, {}, error.what()};
  } catch (const std::domain_error& error) {
    return {RuntimeStatus::invalid_normalized_action, {}, error.what()};
  } catch (const std::exception& error) {
    return {RuntimeStatus::inference_error, {}, error.what()};
  }
}

std::vector<JointCommand> RuntimeSupervisor::to_physical(
    std::span<const double> normalized) const {
  std::vector<JointCommand> commands;
  commands.reserve(normalized.size());
  for (std::size_t index = 0; index < normalized.size(); ++index) {
    const double value = normalized[index];
    if (!std::isfinite(value) || value < -1.0 || value > 1.0) {
      throw std::domain_error("model action must be finite and normalized to [-1, 1]");
    }
    const auto& limit = ordered_limits_[index];
    double physical = 0.0;
    if (limit.mode == ControlMode::position) {
      if (!limit.minimum || !limit.maximum) {
        throw UnsafeCommand("position joint has no physical range: " + limit.name);
      }
      const double midpoint = (*limit.minimum + *limit.maximum) / 2.0;
      const double half_range = (*limit.maximum - *limit.minimum) / 2.0;
      physical = midpoint + value * half_range;
    } else {
      if (!limit.magnitude_limit) {
        throw UnsafeCommand("rate/effort joint has no magnitude limit: " + limit.name);
      }
      physical = value * *limit.magnitude_limit;
    }
    commands.push_back({limit.name, physical});
  }
  return commands;
}

}  // namespace p37
