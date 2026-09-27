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

 private:
  RuntimeSupervisor& supervisor_;
  ObservationSource& source_;
  CommandSink& sink_;
};

}  // namespace p37
