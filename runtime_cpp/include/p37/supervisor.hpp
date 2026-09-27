#pragma once

#include "p37/runtime.hpp"

#include <cstdint>
#include <span>
#include <string>
#include <string_view>
#include <vector>

namespace p37 {

enum class RuntimeStatus : std::uint8_t {
  allowed,
  no_observation,
  stale_observation,
  clock_error,
  inference_error,
  shape_mismatch,
  invalid_normalized_action,
  unsafe_command,
  io_error,
};

struct RuntimeDecision {
  RuntimeStatus status{RuntimeStatus::inference_error};
  std::vector<JointCommand> commands;
  std::string message;

  [[nodiscard]] bool allowed() const noexcept { return status == RuntimeStatus::allowed; }
};

struct RuntimeConfig {
  std::int64_t max_observation_age_ns{100'000'000};
};

class RuntimeSupervisor final {
 public:
  RuntimeSupervisor(InferenceEngine& engine, std::vector<JointLimit> ordered_limits,
                    RuntimeConfig config = {});

  void reset(std::string_view embodiment_id);

  [[nodiscard]] RuntimeDecision evaluate(std::span<const double> observation,
                                         std::int64_t observation_time_ns,
                                         std::int64_t now_ns) const noexcept;

 private:
  [[nodiscard]] std::vector<JointCommand> to_physical(
      std::span<const double> normalized) const;

  InferenceEngine& engine_;
  std::vector<JointLimit> ordered_limits_;
  SafetyEnvelope safety_;
  RuntimeConfig config_;
};

}  // namespace p37
