#include "p37/supervisor.hpp"

#include <cassert>
#include <span>
#include <string>
#include <string_view>
#include <vector>

namespace {

class FakeEngine final : public p37::InferenceEngine {
 public:
  explicit FakeEngine(std::vector<double> output) : output_(std::move(output)) {}

  void reset(std::string_view embodiment_id) override { last_embodiment_ = embodiment_id; }

  std::vector<double> infer(std::span<const double> observation) override {
    static_cast<void>(observation);
    return output_;
  }

  std::vector<double> output_;
  std::string last_embodiment_;
};

}  // namespace

int main() {
  using p37::ControlMode;
  using p37::JointLimit;
  using p37::RuntimeStatus;
  using p37::RuntimeSupervisor;

  std::vector<JointLimit> limits{
      JointLimit{"arm", ControlMode::position, -2.0, 2.0, std::nullopt},
      JointLimit{"wheel", ControlMode::velocity, std::nullopt, std::nullopt, 4.0},
  };

  FakeEngine engine({0.5, -0.5});
  RuntimeSupervisor runtime(engine, limits);
  runtime.reset("robot-a");
  assert(engine.last_embodiment_ == "robot-a");

  const auto allowed = runtime.evaluate(std::vector<double>{1.0, 2.0}, 900, 1000);
  assert(allowed.allowed());
  assert(allowed.commands.at(0).value == 1.0);
  assert(allowed.commands.at(1).value == -2.0);

  const auto stale = runtime.evaluate(std::vector<double>{}, 0, 200'000'000);
  assert(stale.status == RuntimeStatus::stale_observation);
  assert(stale.commands.empty());

  FakeEngine wrong_shape({0.0});
  RuntimeSupervisor shape_runtime(wrong_shape, limits);
  assert(shape_runtime.evaluate({}, 0, 1).status == RuntimeStatus::shape_mismatch);

  FakeEngine invalid({1.5, 0.0});
  RuntimeSupervisor invalid_runtime(invalid, limits);
  assert(invalid_runtime.evaluate({}, 0, 1).status == RuntimeStatus::invalid_normalized_action);

  return 0;
}
