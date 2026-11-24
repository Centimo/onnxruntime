// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT License.

#include "core/common/semver.h"

#include "gtest/gtest.h"

#include "test/util/include/asserts.h"

namespace onnxruntime::test {

TEST(SemVerParsingTest, Basic) {
  {
    auto semver = ParseSemVerVersion("1.2.3-abcde+fghij");
    EXPECT_EQ(semver.major, 1);
    EXPECT_EQ(semver.minor, 2);
    EXPECT_EQ(semver.patch, 3);
    EXPECT_EQ(semver.prerelease, "abcde");
    EXPECT_EQ(semver.build_metadata, "fghij");
  }

  {
    auto semver = ParseSemVerVersion("1.2.3");
    EXPECT_EQ(semver.major, 1);
    EXPECT_EQ(semver.minor, 2);
    EXPECT_EQ(semver.patch, 3);
    EXPECT_EQ(semver.prerelease, std::nullopt);
    EXPECT_EQ(semver.build_metadata, std::nullopt);
  }
}

TEST(SemVerParsingTest, Invalid) {
  SemVerVersion semver{};
  ASSERT_STATUS_NOT_OK(ParseSemVerVersion("version one point zero", &semver));
  ASSERT_STATUS_NOT_OK(ParseSemVerVersion("1.23.2.2", &semver));
}

TEST(CanonicalNumericVersionTest, Valid) {
  static_assert(is_canonical_numeric_version("0.0.0", 3));
  static_assert(is_canonical_numeric_version("1.23.2", 3));
  static_assert(is_canonical_numeric_version("1.23.2.2", 4));
  static_assert(is_canonical_numeric_version("0.0.0.0", 4));
  static_assert(is_canonical_numeric_version("4294967295.4294967295.4294967295.4294967295", 4));
}

TEST(CanonicalNumericVersionTest, Invalid) {
  EXPECT_FALSE(is_canonical_numeric_version("", 3));
  EXPECT_FALSE(is_canonical_numeric_version("1.2", 3));
  EXPECT_FALSE(is_canonical_numeric_version("1.2.3.4", 3));
  EXPECT_FALSE(is_canonical_numeric_version("1.2.3", 4));
  EXPECT_FALSE(is_canonical_numeric_version("1.2.3.4.5", 4));
  EXPECT_FALSE(is_canonical_numeric_version("1.2.3.4-", 4));
  EXPECT_FALSE(is_canonical_numeric_version("1.2.3.4+build", 4));
  EXPECT_FALSE(is_canonical_numeric_version("01.2.3.4", 4));
  EXPECT_FALSE(is_canonical_numeric_version("1.02.3.4", 4));
  EXPECT_FALSE(is_canonical_numeric_version("1.2.03.4", 4));
  EXPECT_FALSE(is_canonical_numeric_version("1.2.3.04", 4));
  EXPECT_FALSE(is_canonical_numeric_version("1.2.3.", 4));
  EXPECT_FALSE(is_canonical_numeric_version("1.2..3", 4));
  EXPECT_FALSE(is_canonical_numeric_version("4294967296.2.3.4", 4));
  EXPECT_FALSE(is_canonical_numeric_version("1.4294967296.3.4", 4));
  EXPECT_FALSE(is_canonical_numeric_version("1.2.4294967296.4", 4));
  EXPECT_FALSE(is_canonical_numeric_version("1.2.3.4294967296", 4));
}

}  // namespace onnxruntime::test
