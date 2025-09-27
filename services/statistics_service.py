import json
import random
from datetime import datetime, timedelta

from storage import (
    get_statistics_accounts as storage_get_statistics_accounts,
    set_statistics_accounts as storage_set_statistics_accounts,
)

PLATFORMS = ["Pocket Option", "ByBit", "Binance"]

class StatisticsService:
    def __init__(self):
        self.accounts = self._load_accounts()
        self.last_update_time = datetime.now()

    def _load_accounts(self):
        accounts_data = storage_get_statistics_accounts()
        if not isinstance(accounts_data, list):
            accounts_data = []

        # Seed demo accounts if none exist yet
        if len(accounts_data) == 0:
            now_iso = datetime.now().isoformat()
            for i in range(5):
                accounts_data.append({
                    'id': 1000 + i,
                    'platform': random.choice(PLATFORMS),
                    'boost_days': random.randint(30, 40),
                    'start_balance': 1000,
                    'current_balance': random.randint(9000, 11000),
                    'last_update': now_iso,
                })

        for account in accounts_data:
            if 'platform' not in account:
                account['platform'] = random.choice(PLATFORMS)
            if 'boost_days' not in account:
                account['boost_days'] = random.randint(30, 40)
            if account.get('start_balance') != 1000:
                account['start_balance'] = 1000
            if account.get('current_balance') is None or account.get('current_balance') < 10000:
                account['current_balance'] = random.randint(9000, 11000)
            if 'last_update' not in account:
                account['last_update'] = datetime.now().isoformat()
        self._save_accounts(accounts_data)  # persist applied defaults
        return accounts_data

    def _save_accounts(self, accounts):
        storage_set_statistics_accounts(accounts if isinstance(accounts, list) else [])

    def get_accounts_count(self):
        return len(self.accounts)

    async def update_balances(self):
        now = datetime.now()
        updated = False
        # The global check self.last_update_time is a throttle to avoid checking too often.
        # The actual logic for updating is per-account.
        if now - self.last_update_time >= timedelta(seconds=10):
            for account in self.accounts:
                last_update_dt = datetime.fromisoformat(account['last_update'])
                time_since_last_update = now - last_update_dt
                intervals_passed = int(time_since_last_update.total_seconds() // 864000) # 10 days

                if intervals_passed > 0:
                    current_balance = account['current_balance']

                    for _ in range(intervals_passed):
                        increase_percent = 0.30 # 30% increase
                        current_balance *= (1 + increase_percent)

                    account['current_balance'] = current_balance
                    # Correctly advance the last_update time by the number of processed intervals
                    account['last_update'] = (last_update_dt + timedelta(seconds=intervals_passed * 864000)).isoformat()
                    updated = True

            if updated:
                self._save_accounts(self.accounts)
                self.last_update_time = now
                return True
        return False

    def get_account_info(self, index):
        if not self.accounts or index >= len(self.accounts):
            return "No account data available."
        account = self.accounts[index]
        return (
            f"🧾 Account: #{account['id']}\n"
            f"💻 Platform: {account['platform']}\n"
            f"💰 Start Balance: ${account['start_balance']:.2f}\n"
            f"🚀 Current Balance: ${account['current_balance']:.2f} ✅\n"
            f"⏳ Boost Duration: {account['boost_days']} days"
        )

stats_service = StatisticsService() 