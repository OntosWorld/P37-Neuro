#include "p37/tensorrt_engine.hpp"

#include <NvInfer.h>
#include <cuda_runtime_api.h>

#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <fstream>
#include <memory>
#include <span>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

namespace p37 {
namespace {

class TensorRtLogger final : public nvinfer1::ILogger {
 public:
  void log(Severity severity, const char* message) noexcept override {
    if (severity <= Severity::kWARNING) {
      last_message_ = message == nullptr ? "" : message;
    }
  }

  [[nodiscard]] const std::string& last_message() const noexcept { return last_message_; }

 private:
  std::string last_message_;
};

template <typename T>
struct TensorRtDelete {
  void operator()(T* value) const noexcept { delete value; }
};

void check_cuda(cudaError_t status, const char* operation) {
  if (status != cudaSuccess) {
    throw std::runtime_error(std::string(operation) + ": " + cudaGetErrorString(status));
  }
}

std::vector<char> read_binary(const std::filesystem::path& path) {
  std::ifstream stream(path, std::ios::binary | std::ios::ate);
  if (!stream) {
    throw std::runtime_error("unable to open TensorRT engine: " + path.string());
  }
  const auto size = stream.tellg();
  if (size <= 0) {
    throw std::runtime_error("TensorRT engine is empty: " + path.string());
  }
  std::vector<char> bytes(static_cast<std::size_t>(size));
  stream.seekg(0);
  stream.read(bytes.data(), size);
  if (!stream) {
    throw std::runtime_error("unable to read TensorRT engine: " + path.string());
  }
  return bytes;
}

std::size_t element_size(nvinfer1::DataType type) {
  switch (type) {
    case nvinfer1::DataType::kFLOAT:
      return sizeof(float);
    case nvinfer1::DataType::kBOOL:
      return sizeof(std::uint8_t);
    default:
      throw std::runtime_error("P37 TensorRT runtime supports only float and bool tensors");
  }
}

std::size_t element_count(const nvinfer1::Dims& dims) {
  std::size_t count = 1;
  for (int index = 0; index < dims.nbDims; ++index) {
    if (dims.d[index] <= 0) {
      throw std::runtime_error("P37 TensorRT runtime requires fixed positive tensor shapes");
    }
    count *= static_cast<std::size_t>(dims.d[index]);
  }
  return count;
}

struct DeviceBuffer {
  void* pointer{nullptr};
  std::size_t bytes{0};

  DeviceBuffer() = default;
  explicit DeviceBuffer(std::size_t requested_bytes) : bytes(requested_bytes) {
    if (bytes == 0) {
      throw std::invalid_argument("TensorRT buffer cannot be empty");
    }
    check_cuda(cudaMalloc(&pointer, bytes), "cudaMalloc");
  }

  DeviceBuffer(const DeviceBuffer&) = delete;
  DeviceBuffer& operator=(const DeviceBuffer&) = delete;

  DeviceBuffer(DeviceBuffer&& other) noexcept
      : pointer(std::exchange(other.pointer, nullptr)), bytes(std::exchange(other.bytes, 0)) {}

  DeviceBuffer& operator=(DeviceBuffer&& other) noexcept {
    if (this != &other) {
      if (pointer != nullptr) {
        cudaFree(pointer);
      }
      pointer = std::exchange(other.pointer, nullptr);
      bytes = std::exchange(other.bytes, 0);
    }
    return *this;
  }

  ~DeviceBuffer() {
    if (pointer != nullptr) {
      cudaFree(pointer);
    }
  }
};

struct TensorBinding {
  std::string name;
  nvinfer1::DataType type{nvinfer1::DataType::kFLOAT};
  std::size_t elements{0};
  DeviceBuffer device;
};

TensorBinding make_binding(const nvinfer1::ICudaEngine& engine, std::string name) {
  const auto* c_name = name.c_str();
  const auto dims = engine.getTensorShape(c_name);
  const auto type = engine.getTensorDataType(c_name);
  const auto elements = element_count(dims);
  return TensorBinding{
      std::move(name),
      type,
      elements,
      DeviceBuffer(elements * element_size(type)),
  };
}

void require_size(std::size_t actual, const TensorBinding& binding, const char* label) {
  if (actual != binding.elements) {
    throw std::invalid_argument(std::string(label) + " has " + std::to_string(actual) +
                                " elements but engine expects " +
                                std::to_string(binding.elements));
  }
}

void copy_async(const void* source, const TensorBinding& target, cudaStream_t stream) {
  check_cuda(cudaMemcpyAsync(target.device.pointer, source, target.device.bytes,
                             cudaMemcpyHostToDevice, stream),
             "cudaMemcpyAsync host-to-device");
}

void copy_from_async(void* target, const TensorBinding& source, cudaStream_t stream) {
  check_cuda(cudaMemcpyAsync(target, source.device.pointer, source.device.bytes,
                             cudaMemcpyDeviceToHost, stream),
             "cudaMemcpyAsync device-to-host");
}

}  // namespace

class TensorRtEngine::Impl {
 public:
  Impl(std::filesystem::path engine_path, TensorRtStaticContext static_context,
       TensorRtTensorNames names)
      : names_(std::move(names)), static_context_(std::move(static_context)) {
    const auto bytes = read_binary(engine_path);
    runtime_.reset(nvinfer1::createInferRuntime(logger_));
    if (!runtime_) {
      throw std::runtime_error("unable to create TensorRT runtime: " + logger_.last_message());
    }
    engine_.reset(runtime_->deserializeCudaEngine(bytes.data(), bytes.size()));
    if (!engine_) {
      throw std::runtime_error("unable to deserialize TensorRT engine: " + logger_.last_message());
    }
    context_.reset(engine_->createExecutionContext());
    if (!context_) {
      throw std::runtime_error("unable to create TensorRT execution context");
    }

    check_cuda(cudaStreamCreate(&stream_), "cudaStreamCreate");

    joint_features_ = make_binding(*engine_, names_.joint_features);
    joint_state_ = make_binding(*engine_, names_.joint_state);
    joint_mask_ = make_binding(*engine_, names_.joint_mask);
    task_features_ = make_binding(*engine_, names_.task_features);
    demonstration_images_ = make_binding(*engine_, names_.demonstration_images);
    memory_ = make_binding(*engine_, names_.memory);
    action_ = make_binding(*engine_, names_.action);
    high_level_ = make_binding(*engine_, names_.high_level);
    value_ = make_binding(*engine_, names_.value);
    next_memory_ = make_binding(*engine_, names_.next_memory);

    require_float(joint_features_);
    require_float(joint_state_);
    require_bool(joint_mask_);
    require_float(task_features_);
    require_float(demonstration_images_);
    require_float(memory_);
    require_float(action_);
    require_float(high_level_);
    require_float(value_);
    require_float(next_memory_);

    require_size(static_context_.joint_features.size(), joint_features_, "joint_features");
    require_size(static_context_.joint_mask.size(), joint_mask_, "joint_mask");
    require_size(static_context_.task_features.size(), task_features_, "task_features");
    require_size(static_context_.demonstration_images.size(), demonstration_images_,
                 "demonstration_images");
    if (memory_.elements != next_memory_.elements) {
      throw std::runtime_error("memory and next_memory shapes differ");
    }

    joint_state_host_.resize(joint_state_.elements);
    action_host_.resize(action_.elements);
    high_level_host_.resize(high_level_.elements);
    value_host_.resize(value_.elements);
    memory_host_.assign(memory_.elements, 0.0F);
    next_memory_host_.resize(next_memory_.elements);

    set_address(joint_features_);
    set_address(joint_state_);
    set_address(joint_mask_);
    set_address(task_features_);
    set_address(demonstration_images_);
    set_address(memory_);
    set_address(action_);
    set_address(high_level_);
    set_address(value_);
    set_address(next_memory_);

    copy_async(static_context_.joint_features.data(), joint_features_, stream_);
    copy_async(static_context_.joint_mask.data(), joint_mask_, stream_);
    copy_async(static_context_.task_features.data(), task_features_, stream_);
    copy_async(static_context_.demonstration_images.data(), demonstration_images_, stream_);
    check_cuda(cudaStreamSynchronize(stream_), "cudaStreamSynchronize");
  }

  ~Impl() {
    if (stream_ != nullptr) {
      cudaStreamDestroy(stream_);
    }
  }

  void reset(std::string_view embodiment_id) {
    if (embodiment_id.empty()) {
      throw std::invalid_argument("embodiment_id cannot be empty");
    }
    std::fill(memory_host_.begin(), memory_host_.end(), 0.0F);
  }

  std::vector<double> infer(std::span<const double> observation) {
    require_size(observation.size(), joint_state_, "observation");
    std::transform(observation.begin(), observation.end(), joint_state_host_.begin(),
                   [](double value) { return static_cast<float>(value); });

    copy_async(joint_state_host_.data(), joint_state_, stream_);
    copy_async(memory_host_.data(), memory_, stream_);
    if (!context_->enqueueV3(stream_)) {
      throw std::runtime_error("TensorRT enqueueV3 failed");
    }
    copy_from_async(action_host_.data(), action_, stream_);
    copy_from_async(next_memory_host_.data(), next_memory_, stream_);
    check_cuda(cudaStreamSynchronize(stream_), "cudaStreamSynchronize");

    memory_host_.swap(next_memory_host_);
    return std::vector<double>(action_host_.begin(), action_host_.end());
  }

 private:
  static void require_float(const TensorBinding& binding) {
    if (binding.type != nvinfer1::DataType::kFLOAT) {
      throw std::runtime_error(binding.name + " must be float32");
    }
  }

  static void require_bool(const TensorBinding& binding) {
    if (binding.type != nvinfer1::DataType::kBOOL) {
      throw std::runtime_error(binding.name + " must be bool");
    }
  }

  void set_address(const TensorBinding& binding) {
    if (!context_->setTensorAddress(binding.name.c_str(), binding.device.pointer)) {
      throw std::runtime_error("unable to bind TensorRT tensor: " + binding.name);
    }
  }

  TensorRtLogger logger_;
  std::unique_ptr<nvinfer1::IRuntime, TensorRtDelete<nvinfer1::IRuntime>> runtime_;
  std::unique_ptr<nvinfer1::ICudaEngine, TensorRtDelete<nvinfer1::ICudaEngine>> engine_;
  std::unique_ptr<nvinfer1::IExecutionContext, TensorRtDelete<nvinfer1::IExecutionContext>>
      context_;
  cudaStream_t stream_{nullptr};

  TensorRtTensorNames names_;
  TensorRtStaticContext static_context_;

  TensorBinding joint_features_;
  TensorBinding joint_state_;
  TensorBinding joint_mask_;
  TensorBinding task_features_;
  TensorBinding demonstration_images_;
  TensorBinding memory_;
  TensorBinding action_;
  TensorBinding high_level_;
  TensorBinding value_;
  TensorBinding next_memory_;

  std::vector<float> joint_state_host_;
  std::vector<float> action_host_;
  std::vector<float> high_level_host_;
  std::vector<float> value_host_;
  std::vector<float> memory_host_;
  std::vector<float> next_memory_host_;
};

TensorRtEngine::TensorRtEngine(std::filesystem::path engine_path,
                               TensorRtStaticContext static_context, TensorRtTensorNames names)
    : impl_(std::make_unique<Impl>(std::move(engine_path), std::move(static_context),
                                  std::move(names))) {}

TensorRtEngine::~TensorRtEngine() = default;
TensorRtEngine::TensorRtEngine(TensorRtEngine&&) noexcept = default;
TensorRtEngine& TensorRtEngine::operator=(TensorRtEngine&&) noexcept = default;

void TensorRtEngine::reset(std::string_view embodiment_id) { impl_->reset(embodiment_id); }

std::vector<double> TensorRtEngine::infer(std::span<const double> observation) {
  return impl_->infer(observation);
}

}  // namespace p37
