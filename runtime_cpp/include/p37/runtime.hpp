#pragma once

#include <cstdint>
#include <optional>
#include <span>
#include <stdexcept>
#include <string>
#include <string_view>
#include <unordered_map>
#include <vector>

namespace p37 {

enum class ControlMode : std::uint8_t { position, velocity, effort };

struct JointLimit {
  std::string name;
  ControlMode mode{ControlMode::position};
  std::optional<double> minimum;
  std::optional<double> maximum;
  std::optional<double> magnitude_limit;
};

struct JointCommand {
  std::string name;
  double value{0.0};
};

struct SafetyResult {
  std::vector<JointCommand> commands;
  std::vector<std::string> clamped_joints;
};

class UnsafeCommand final : public std::runtime_error {
 public:
  using std::runtime_error::runtime_error;
};

class SafetyEnvelope final {
 public:
  explicit SafetyEnvelope(std::vector<JointLimit> limits);
  [[nodiscard]] SafetyResult apply(std::span<const JointCommand> commands) const;

 private:
  std::unordered_map<std::string, JointLimit> limits_;
};

class InferenceEngine {
 public:
  virtual ~InferenceEngine() = default;
  virtual void reset(std::string_view embodiment_id) = 0;
  [[nodiscard]] virtual std::vector<double> infer(std::span<const double> observation) = 0;
};

}  // namespace p37
