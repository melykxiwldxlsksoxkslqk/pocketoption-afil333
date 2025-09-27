# Helper script to patch deposit-check logic in trading_api.py
# It replaces the exact text block with a windowed check (±10 USD).

import os

# Try new path first (after refactor), then legacy root path
CANDIDATES = [
    os.path.join('services', 'trading_api.py'),
    'trading_api.py',
]

target = None
for p in CANDIDATES:
    if os.path.exists(p):
        target = p
        break

if not target:
    raise FileNotFoundError("trading_api.py not found in expected locations")

with open(target, 'r', encoding='utf-8') as f:
    content = f.read()

# Original (pre-window) logic block
old_logic = """            logger.info(
                f"Перевірка депозиту для UID {uid}: "
                f"Required: ${min_deposit}, FTD: ${ftd_amount}, Sum of Deposits: ${sum_of_deposits}"
            )

            # ОСНОВНА ЛОГІКА: Перевіряємо, чи є перший або загальний депозит достатнім
            has_sufficient_deposit = (ftd_amount >= min_deposit or sum_of_deposits >= min_deposit)

            if has_sufficient_deposit:
                logger.info(f"✅ Депозит для UID {uid} підтверджено.")
            else:
                logger.warning(f"Недостатній депозит для UID {uid}.")"""

# New windowed logic block (±10 around min_deposit)
new_logic = """            # Создаем окно ±10 от минимального депозита
            deposit_window = 10.0
            min_threshold = max(0, min_deposit - deposit_window)
            max_threshold = min_deposit + deposit_window

            logger.info(
                f"Перевірка депозиту для UID {uid}: "
                f"Required: ${min_deposit} (окно: ${min_threshold:.2f} - ${max_threshold:.2f}), "
                f"FTD: ${ftd_amount}, Sum of Deposits: ${sum_of_deposits}"
            )

            # ОСНОВНА ЛОГІКА: Перевіряємо, чи є перший або загальний депозит в пределах окна
            # Депозит считается достаточным если он в диапазоне [min_deposit-10, min_deposit+10]
            has_sufficient_deposit = (
                (min_threshold <= ftd_amount <= max_threshold) or 
                (min_threshold <= sum_of_deposits <= max_threshold)
            )

            if has_sufficient_deposit:
                logger.info(f"✅ Депозит для UID {uid} підтверджено (в пределах окна ±{deposit_window}).")
            else:
                logger.warning(f"Недостатній депозит для UID {uid} (вне окна ±{deposit_window}).")"""

if old_logic in content:
    content = content.replace(old_logic, new_logic)
    with open(target, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"Patched deposit logic in: {target}")
else:
    print("Old logic block not found. File may already be patched or differs from expected text.")
