#include "p37/loop.hpp"

#include <cassert>
#include <optional>
#include <stdexcept>
#include <string_view>
#include <vector>

namespace {

class FakeEngine final : public p37::InferenceEngine {
 public:
  void reset(std::string_view) override {}

  std::vector<double> infer(std::span<const double>) override { return {0.0}; }
};

class FakeSource final : public p37::ObservationSource {
 public:
  std::optional<p37::ObservationFrame> frame;

  std::optional<p37::ObservationFrame> read() override { return frame; }
};

class FakeSink final : public p37::CommandSink {
 public:
  bool stopped{false};
  bool fail_write{false};
  std::vector<p37::JointCommand> commands;

  void write(std::span<const p37::JointCommand> values) override {
    if (fail_write) {
      throw std::runtime_error("hardware write failed");
    }
    commands.assign(values.begin(), values.end());
  }

  void stop() noexcept override { stopped = true; }
};

p37::RuntimeSupervisor supervisor(FakeEngine& engine) {
  std::vector<p37::JointLimit> limits{
      {"joint_1", p37::ControlMode::position, -1.0, 1.0, std::nullopt}};
  return p37::RuntimeSupervisor(engine, std::move(limits));
}

}  // namespace

int main() {
  FakeEngine engine;
  auto runtime_supervisor = supervisor(engine);
  FakeSource source;
  FakeSink sink;
  p37::RuntimeLoop loop(runtime_supervisor, source, sink);

  auto missing = loop.tick(100);
  assert(missing.status == p37::RuntimeStatus::no_observation);
  assert(sink.stopped);
  assert(loop.diagnostics().ticks == 1);
  assert(loop.diagnostics().rejected_commands == 1);
  assert(loop.diagnostics().stop_requests == 1);

  sink.stopped = false;
  source.frame = p37::ObservationFrame{{0.0}, 100};
  auto allowed = loop.tick(100);
  assert(allowed.allowed());
  assert(!sink.stopped);
  assert(sink.commands.size() == 1);
  assert(loop.diagnostics().ticks == 2);
  assert(loop.diagnostics().allowed_commands == 1);

  sink.fail_write = true;
  auto rejected = loop.tick(100);
  assert(rejected.status == p37::RuntimeStatus::io_error);
  assert(sink.stopped);
  assert(loop.diagnostics().ticks == 3);
  assert(loop.diagnostics().rejected_commands == 2);
  assert(loop.diagnostics().io_errors == 1);
  assert(loop.diagnostics().last_status == p37::RuntimeStatus::io_error);

  loop.reset_diagnostics();
  assert(loop.diagnostics().ticks == 0);
  assert(loop.diagnostics().allowed_commands == 0);
}

