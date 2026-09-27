#pragma once

#include "p37/runtime.hpp"

#include <cstdint>
#include <filesystem>
#include <memory>
#include <string>
#include <vector>

namespace p37 {

struct TensorRtTensorNames {
  std::string joint_features{"joint_features"};
  std::string joint_state{"joint_state"};
  std::string joint_mask{"joint_mask"};
  std::string task_features{"task_features"};
  std::string demonstration_images{"demonstration_images"};
  std::string memory{"memory"};
  std::string action{"action"};
  std::string high_level{"high_level"};
  std::string value{"value"};
  std::string next_memory{"next_memory"};
};

struct TensorRtStaticContext {
  std::vector<float> joint_features;
  std::vector<std::uint8_t> joint_mask;
  std::vector<float> task_features;
  std::vector<float> demonstration_images;
};

class TensorRtEngine final : public InferenceEngine {
 public:
  TensorRtEngine(std::filesystem::path engine_path, TensorRtStaticContext static_context,
                 TensorRtTensorNames names = {});
  ~TensorRtEngine() override;

  TensorRtEngine(const TensorRtEngine&) = delete;
  TensorRtEngine& operator=(const TensorRtEngine&) = delete;
  TensorRtEngine(TensorRtEngine&&) noexcept;
  TensorRtEngine& operator=(TensorRtEngine&&) noexcept;

  void reset(std::string_view embodiment_id) override;
  [[nodiscard]] std::vector<double> infer(std::span<const double> observation) override;

 private:
  class Impl;
  std::unique_ptr<Impl> impl_;
};

}  // namespace p37
