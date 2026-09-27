#include "p37/runtime.hpp"

#include <cassert>
#include <vector>

int main() {
  using p37::ControlMode;
  using p37::JointCommand;
  using p37::JointLimit;
  using p37::SafetyEnvelope;
  using p37::UnsafeCommand;

  SafetyEnvelope safety({
      JointLimit{"shoulder", ControlMode::position, -1.0, 1.0, std::nullopt},
      JointLimit{"wheel", ControlMode::velocity, std::nullopt, std::nullopt, 2.0},
  });

  const auto safe = safety.apply(std::vector<JointCommand>{{"shoulder", 3.0}});
  assert(safe.commands.at(0).value == 1.0);
  assert(safe.clamped_joints.size() == 1);

  bool rejected = false;
  try {
    static_cast<void>(safety.apply(std::vector<JointCommand>{{"wheel", 3.0}}));
  } catch (const UnsafeCommand&) {
    rejected = true;
  }
  assert(rejected);
  return 0;
}
