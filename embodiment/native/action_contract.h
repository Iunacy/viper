#pragma once
#include <cstddef>

// C ABI shared by isolated GR00T and Isaac interpreters; no simulator dependency.
// Rows are physical world-frame [dx, dy, dz, aperture], meters and [0, 1].
extern "C" {
unsigned viper_action_contract_abi() noexcept;
// 0: valid; 1: invalid buffer/shape; 2: nonfinite; 3: translation; 4: aperture.
int viper_validate_actions(const double* rows, std::size_t count,
                           std::size_t columns) noexcept;
}
