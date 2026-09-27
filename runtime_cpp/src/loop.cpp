#include "p37/loop.hpp"

#include <exception>

namespace p37 {

RuntimeDecision RuntimeLoop::tick(std::int64_t now_ns) noexcept {
  try {
    const auto frame = source_.read();
    if (!frame.has_value()) {
      sink_.stop();
      return {RuntimeStatus::no_observation, {}, "no observation available"};
    }

    auto decision =
        supervisor_.evaluate(frame->values, frame->timestamp_ns, now_ns);
    if (!decision.allowed()) {
      sink_.stop();
      return decision;
    }

    try {
      sink_.write(decision.commands);
    } catch (const std::exception& error) {
      sink_.stop();
      return {RuntimeStatus::io_error, {}, error.what()};
    } catch (...) {
      sink_.stop();
      return {RuntimeStatus::io_error, {}, "unknown command sink error"};
    }
    return decision;
  } catch (const std::exception& error) {
    sink_.stop();
    return {RuntimeStatus::io_error, {}, error.what()};
  } catch (...) {
    sink_.stop();
    return {RuntimeStatus::io_error, {}, "unknown runtime I/O error"};
  }
}

}  // namespace p37
