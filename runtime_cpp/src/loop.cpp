#include "p37/loop.hpp"

#include <exception>

namespace p37 {

void RuntimeLoop::record_rejection(RuntimeStatus status, bool io_error) noexcept {
  ++diagnostics_.rejected_commands;
  ++diagnostics_.stop_requests;
  diagnostics_.last_status = status;
  if (io_error) {
    ++diagnostics_.io_errors;
  }
}

RuntimeDecision RuntimeLoop::tick(std::int64_t now_ns) noexcept {
  ++diagnostics_.ticks;
  try {
    const auto frame = source_.read();
    if (!frame.has_value()) {
      sink_.stop();
      record_rejection(RuntimeStatus::no_observation);
      return {RuntimeStatus::no_observation, {}, "no observation available"};
    }

    auto decision = supervisor_.evaluate(frame->values, frame->timestamp_ns, now_ns);
    if (!decision.allowed()) {
      sink_.stop();
      record_rejection(decision.status);
      return decision;
    }

    try {
      sink_.write(decision.commands);
    } catch (const std::exception& error) {
      sink_.stop();
      record_rejection(RuntimeStatus::io_error, true);
      return {RuntimeStatus::io_error, {}, error.what()};
    } catch (...) {
      sink_.stop();
      record_rejection(RuntimeStatus::io_error, true);
      return {RuntimeStatus::io_error, {}, "unknown command sink error"};
    }

    ++diagnostics_.allowed_commands;
    diagnostics_.last_status = decision.status;
    return decision;
  } catch (const std::exception& error) {
    sink_.stop();
    record_rejection(RuntimeStatus::io_error, true);
    return {RuntimeStatus::io_error, {}, error.what()};
  } catch (...) {
    sink_.stop();
    record_rejection(RuntimeStatus::io_error, true);
    return {RuntimeStatus::io_error, {}, "unknown runtime I/O error"};
  }
}

}  // namespace p37
