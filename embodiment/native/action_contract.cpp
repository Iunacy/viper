#include "action_contract.h"
#include <cmath>

extern "C" unsigned viper_action_contract_abi() noexcept { return 1; }

extern "C" int viper_validate_actions(const double* rows, std::size_t count,
                                      std::size_t columns) noexcept {
    if (rows == nullptr || count == 0 || count > 16 || columns != 4) return 1;
    // Validate the complete prediction before releasing any command to control.
    for (std::size_t i = 0; i < count; ++i) {
        const double* row = rows + 4 * i;
        for (std::size_t j = 0; j < 4; ++j) {
            if (!std::isfinite(row[j])) return 2;
        }
        if (std::hypot(row[0], row[1], row[2]) > 0.003 + 1e-12) return 3;
        if (row[3] < 0.0 || row[3] > 1.0) return 4;
    }
    return 0;
}
