#include "action_contract.h"
#include <array>
#include <cstdlib>
#include <limits>

int main() {
    std::array<double, 64> rows{};
    auto check = [](bool ok) { if (!ok) std::abort(); };
    check(viper_action_contract_abi() == 1);
    check(viper_validate_actions(rows.data(), 16, 4) == 0);
    check(viper_validate_actions(nullptr, 1, 4) == 1);
    check(viper_validate_actions(rows.data(), 0, 4) == 1);
    check(viper_validate_actions(rows.data(), 17, 4) == 1);
    check(viper_validate_actions(rows.data(), 1, 3) == 1);
    rows[60] = 0.003;
    rows[63] = 1.0;
    check(viper_validate_actions(rows.data(), 16, 4) == 0);
    rows[61] = 0.003;
    check(viper_validate_actions(rows.data(), 16, 4) == 3);
    rows[61] = 0.0;
    rows[63] = -0.01;
    check(viper_validate_actions(rows.data(), 16, 4) == 4);
    rows[63] = 1.01;
    check(viper_validate_actions(rows.data(), 16, 4) == 4);
    rows[63] = std::numeric_limits<double>::infinity();
    check(viper_validate_actions(rows.data(), 16, 4) == 2);
    rows[63] = std::numeric_limits<double>::quiet_NaN();
    check(viper_validate_actions(rows.data(), 16, 4) == 2);
}
