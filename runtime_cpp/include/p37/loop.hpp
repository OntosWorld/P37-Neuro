#pragma once

#include "p37/supervisor.hpp"

#include <cstdint>
#include <optional>
#include <span>
#include <vector>

namespace p37 {

struct ObservationFrame {
  std::vector<double> values;
  std::int64_t timestamp_ns{0};
};

struct RuntimeDiagnostics {
  std::uint64_t ticks{0};
  std::uint64_t allowed_commands{0};
  std::uint64_t rejected_commands{0};
  std::uint64_t stop_requests{0};
  std::uint64_t io_errors{0};
  RuntimeStatus last_status{RuntimeStatus::no_observation};
};

class ObservationSource {
 public:
  virtual ~ObservationSource() = default;
  [[nodiscard]] virtual std::optional<ObservationFrame> read() = 0;
};

class CommandSink {
 public:
  virtual ~CommandSink() = default;
  virtual void write(std::span<const JointCommand> commands) = 0;
  virtual void stop() noexcept = 0;
};

class RuntimeLoop final {
 public:
  RuntimeLoop(RuntimeSupervisor& supervisor, ObservationSource& source, CommandSink& sink)
      : supervisor_(supervisor), source_(source), sink_(sink) {}

  [[nodiscard]] RuntimeDecision tick(std::int64_t now_ns) noexcept;
  [[nodiscard]] const RuntimeDiagnostics& diagnostics() const noexcept { return diagnostics_; }
  void reset_diagnostics() noexcept { diagnostics_ = {}; }

 private:
  void record_rejection(RuntimeStatus status, bool io_error = false) noexcept;

  RuntimeSupervisor& supervisor_;
  ObservationSource& source_;
  CommandSink& sink_;
  RuntimeDiagnostics diagnostics_;
};

}  // namespace p37
