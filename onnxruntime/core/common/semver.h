// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT License.

#pragma once

#include <cstdint>
#include <limits>
#include <optional>
#include <string_view>

#include "core/common/status.h"

namespace onnxruntime {

// Semantic Versioning version utilities.
// See https://github.com/semver/semver/blob/v2.0.0/semver.md.

// Check for exactly `component_count` dot-separated, canonical decimal unsigned 32-bit components.
// A canonical component has no leading zeroes unless it is exactly "0".
constexpr bool is_canonical_numeric_version(std::string_view version_string, size_t component_count) {
  constexpr uint32_t MAXIMUM_COMPONENT_VALUE = std::numeric_limits<uint32_t>::max();
  size_t position = 0;
  for (size_t component_index = 0; component_index < component_count; ++component_index) {
    const size_t component_start = position;
    uint32_t component_value = 0;
    while (
      position < version_string.size()
      && version_string[position] >= '0'
      && version_string[position] <= '9'
    ) {
      const uint32_t digit = static_cast<uint32_t>(version_string[position] - '0');
      if (component_value > (MAXIMUM_COMPONENT_VALUE - digit) / 10) {
        return false;
      }
      component_value = component_value * 10 + digit;
      ++position;
    }

    if (
      position == component_start
      || (version_string[component_start] == '0' && position - component_start > 1)
    ) {
      return false;
    }
    if (position == version_string.size()) {
      return component_index + 1 == component_count;
    }
    if (version_string[position] != '.') {
      return false;
    }
    ++position;
  }
  return false;
}

// Semantic Versioning version components.
struct SemVerVersion {
  uint32_t major{};
  uint32_t minor{};
  uint32_t patch{};
  std::optional<std::string_view> prerelease{};
  std::optional<std::string_view> build_metadata{};
};

// Parse a Semantic Versioning version from `version_string`.
// If provided, the parsed version components will be written to `semver_version`.
Status ParseSemVerVersion(std::string_view version_string, SemVerVersion* semver_version);

// Parse a Semantic Versioning version from `version_string`.
SemVerVersion ParseSemVerVersion(std::string_view version_string);

}  // namespace onnxruntime
