#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "beem",
#     "hiveengine",
#     "python-dotenv",
#     "tqdm",
#     "colorama",
# ]
# ///
"""
Hive Engine Token Distribution Script with Decimal precision and CSV audit.

Requires environment variables:
- ACTIVE_WIF
- POSTING_WIF
"""

import csv
import logging
import os
import sys
import time
from dataclasses import dataclass
from decimal import ROUND_DOWN, Decimal, getcontext
from typing import Any, Dict, List, Optional, Tuple

from beem import Hive
from beem.wallet import Wallet
from colorama import Back, Fore, Style
from colorama import init as colorama_init
from dotenv import load_dotenv
from hiveengine.api import Api
from hiveengine.tokenobject import Token
from hiveengine.wallet import Wallet as HiveEngineWallet
from tqdm import tqdm

# Initialize colorama
colorama_init(autoreset=True)

# Decimal precision setup
getcontext().prec = 16


# Configure logging with colorized output
class ColorizedLogFormatter(logging.Formatter):
    FORMATS = {
        logging.DEBUG: Fore.CYAN
        + "%(asctime)s - %(levelname)s - %(message)s"
        + Style.RESET_ALL,
        logging.INFO: Fore.GREEN
        + "%(asctime)s - %(levelname)s - %(message)s"
        + Style.RESET_ALL,
        logging.WARNING: Fore.YELLOW
        + "%(asctime)s - %(levelname)s - %(message)s"
        + Style.RESET_ALL,
        logging.ERROR: Fore.RED
        + "%(asctime)s - %(levelname)s - %(message)s"
        + Style.RESET_ALL,
        logging.CRITICAL: Fore.RED
        + Back.WHITE
        + "%(asctime)s - %(levelname)s - %(message)s"
        + Style.RESET_ALL,
    }

    def format(self, record):
        log_format = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_format)
        return formatter.format(record)


handler = logging.StreamHandler()
handler.setFormatter(ColorizedLogFormatter())
logging.basicConfig(level=logging.INFO, handlers=[handler])
logger = logging.getLogger(__name__)


@dataclass
class TokenConfig:
    payout_rate: Decimal
    token_query: str
    token_name: str
    blacklisted_accounts: List[str]
    node_urls: List[str]
    hive_engine_api_url: str
    nobroadcast: bool

    @classmethod
    def from_env(cls) -> "TokenConfig":
        return cls(
            payout_rate=Decimal(os.getenv("PAYOUT_RATE", "0.25")),
            token_query=os.getenv("TOKEN_QUERY", "ARCHONM"),
            token_name=os.getenv("TOKEN_NAME", "ARCHON"),
            blacklisted_accounts=os.getenv(
                "BLACKLISTED_ACCOUNTS", "ufm.pay,upfundme"
            ).split(","),
            node_urls=[os.getenv("NODE_URL", "https://api.hive.blog")],
            hive_engine_api_url=os.getenv(
                "HIVE_ENGINE_API_URL", "https://api.hive-engine.com/rpc/"
            ),
            nobroadcast=os.getenv("DRY_RUN", "").lower() in ("true", "1", "yes"),
        )


@dataclass
class TokenHolder:
    account: str
    balance: Decimal

    def payment_amount(self, config: TokenConfig) -> Decimal:
        return (self.balance * config.payout_rate).quantize(
            Decimal("0.0001"), rounding=ROUND_DOWN
        )


class TokenDistributor:
    def __init__(self):
        load_dotenv()
        self.config = TokenConfig.from_env()
        self.validate_environment()
        self.api = Api(url=self.config.hive_engine_api_url)
        self.token = Token(self.config.token_query, api=self.api)
        self.hive_instance, self.hive_wallet = self.initialize_blockchain()
        self.audit_log: List[dict] = []
        # Add stats tracking
        self.stats: Dict[str, Any] = {
            "total_holders": 0,
            "successful_payments": 0,
            "failed_payments": 0,
            "total_tokens_distributed": Decimal("0"),
            "start_time": None,
            "end_time": None,
        }

    def validate_environment(self) -> None:
        required_vars = ["ACTIVE_WIF", "POSTING_WIF"]
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        if missing_vars:
            logger.error(
                f"Missing required environment vars: {', '.join(missing_vars)}"
            )
            sys.exit(1)

    def initialize_blockchain(self) -> Tuple[Hive, HiveEngineWallet]:
        try:
            active_wif = os.environ["ACTIVE_WIF"]
            posting_wif = os.environ["POSTING_WIF"]

            if self.config.nobroadcast:
                logger.warning("DRY RUN mode active: transactions will not broadcast")

            hive_instance = Hive(
                node=self.config.node_urls,
                keys=[posting_wif, active_wif],
                nobroadcast=self.config.nobroadcast,
            )
            wallet = Wallet(blockchain_instance=hive_instance)
            sender_account = wallet.getAccountFromPrivateKey(active_wif)
            hive_wallet = HiveEngineWallet(
                sender_account, blockchain_instance=hive_instance, api=self.api
            )
            return hive_instance, hive_wallet
        except Exception as e:
            logger.critical(f"Blockchain initialization error: {e}")
            sys.exit(1)

    def get_richlist(self) -> List[TokenHolder]:
        try:
            richlist_raw = self.token.get_holder()
            holders = [
                TokenHolder(
                    account=holder["account"],
                    balance=Decimal(holder["balance"]).quantize(
                        Decimal("1."), rounding=ROUND_DOWN
                    ),
                )
                for holder in richlist_raw
                if Decimal(holder["balance"]) >= 1
                and holder["account"] not in self.config.blacklisted_accounts
            ]
            logger.info(f"Richlist retrieved: {len(holders)} holder(s) after filters")
            self.stats["total_holders"] = len(holders)
            return holders
        except Exception as e:
            logger.error(f"Error getting richlist: {e}")
            return []

    def send_transaction(self, recipient: str, amount: Decimal) -> Optional[str]:
        memo = f"{amount:.4f} {self.config.token_name} payout at {self.config.payout_rate} per {self.config.token_query}"
        try:
            logger.info(f"Paying {recipient} {amount} {self.config.token_name}")
            tx = self.hive_wallet.transfer(
                recipient, f"{amount:.4f}", self.config.token_name, memo
            )
            tx_id = tx.get("transactionId", "") if tx else "DRY_RUN"
            self.stats["successful_payments"] += 1
            self.stats["total_tokens_distributed"] += amount
            return tx_id
        except Exception as e:
            logger.error(f"Failed tx for {recipient}: {e}")
            self.stats["failed_payments"] += 1
            return None

    def process_payments(self, holders: List[TokenHolder]) -> None:
        self.stats["start_time"] = time.time()
        # Add progress bar
        for holder in tqdm(
            holders,
            desc=f"{Fore.BLUE}Processing payments{Style.RESET_ALL}",
            unit="holder",
        ):
            amount = holder.payment_amount(self.config)
            if amount > Decimal("0.0000"):
                # Record transaction time before sending
                tx_timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                tx_id = self.send_transaction(holder.account, amount)
                status = "Success" if tx_id else "Failed"
                self.audit_log.append(
                    {
                        "account": holder.account,
                        "balance": str(holder.balance),
                        "payment": f"{amount:.4f}",
                        "status": status,
                        "transaction_id": tx_id or "",
                        "tx_timestamp": tx_timestamp,  # Individual transaction timestamp
                    }
                )
                time.sleep(1)
        self.stats["end_time"] = time.time()

    def generate_audit_report(self, filename: str = None) -> None:
        """Generate a CSV audit report with timestamp in filename and as a column."""
        # Generate a timestamp for this run
        timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")

        # If no filename provided, create one with timestamp
        if filename is None:
            filename = f"transaction_audit_{timestamp}.csv"

        # Add run timestamp to each record
        for record in self.audit_log:
            record["run_timestamp"] = timestamp

        # Define fields with timestamps included
        fields = [
            "account",
            "balance",
            "payment",
            "status",
            "transaction_id",
            "tx_timestamp",
            "run_timestamp",
        ]

        with open(filename, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            writer.writerows(self.audit_log)

        logger.info(f"Audit report saved as '{filename}'")

        # Store the filename for reference in the summary report
        self.stats["audit_filename"] = filename

    def display_summary_report(self) -> None:
        """Display a comprehensive summary report of the distribution process."""
        if self.stats["start_time"] and self.stats["end_time"]:
            duration = self.stats["end_time"] - self.stats["start_time"]
        else:
            duration = 0

        # Create a visually appealing summary report
        print("\n" + "=" * 80)
        print(
            f"{Fore.CYAN}{Style.BRIGHT}🔶 TOKEN DISTRIBUTION SUMMARY REPORT 🔶{Style.RESET_ALL}"
        )
        print("=" * 80)

        # Configuration section
        print(f"{Fore.YELLOW}{Style.BRIGHT}📋 Configuration:{Style.RESET_ALL}")
        print(
            f"  • Token: {Fore.GREEN}{self.config.token_name}{Style.RESET_ALL} (query: {self.config.token_query})"
        )
        print(
            f"  • Payout Rate: {Fore.GREEN}{self.config.payout_rate}{Style.RESET_ALL}"
        )
        print(
            f"  • Mode: {Fore.RED if self.config.nobroadcast else Fore.GREEN}{'DRY RUN' if self.config.nobroadcast else 'LIVE'}{Style.RESET_ALL}"
        )
        print(
            f"  • Timestamp: {Fore.CYAN}{time.strftime('%Y-%m-%d %H:%M:%S')}{Style.RESET_ALL}"
        )

        # Results section
        print(f"\n{Fore.YELLOW}{Style.BRIGHT}📊 Results:{Style.RESET_ALL}")
        print(
            f"  • Total Holders Processed: {Fore.CYAN}{self.stats['total_holders']}{Style.RESET_ALL}"
        )
        print(
            f"  • Successful Payments: {Fore.GREEN}{self.stats['successful_payments']}{Style.RESET_ALL}"
        )
        print(
            f"  • Failed Payments: {Fore.RED}{self.stats['failed_payments']}{Style.RESET_ALL}"
        )
        print(
            f"  • Success Rate: {Fore.GREEN}{(self.stats['successful_payments'] / max(self.stats['total_holders'], 1)) * 100:.1f}%{Style.RESET_ALL}"
        )

        # Tokens section
        print(f"\n{Fore.YELLOW}{Style.BRIGHT}💰 Tokens:{Style.RESET_ALL}")
        print(
            f"  • Total {self.config.token_name} Distributed: {Fore.GREEN}{self.stats['total_tokens_distributed']:.4f}{Style.RESET_ALL}"
        )
        if self.stats["total_holders"] > 0:
            avg_per_holder = (
                self.stats["total_tokens_distributed"] / self.stats["total_holders"]
            )
            print(
                f"  • Average Per Holder: {Fore.CYAN}{avg_per_holder:.4f}{Style.RESET_ALL}"
            )

        # Time section
        print(f"\n{Fore.YELLOW}{Style.BRIGHT}⏱️ Time:{Style.RESET_ALL}")
        print(f"  • Duration: {Fore.CYAN}{duration:.2f} seconds{Style.RESET_ALL}")
        if self.stats["successful_payments"] > 0 and duration > 0:
            print(
                f"  • Average Time Per Payment: {Fore.CYAN}{duration / self.stats['successful_payments']:.2f} seconds{Style.RESET_ALL}"
            )

        print("=" * 80)

        # Add a note about the audit file
        audit_filename = self.stats.get("audit_filename", "transaction_audit.csv")
        print(
            f"\n{Fore.CYAN}📝 Detailed transaction audit saved to: {audit_filename}{Style.RESET_ALL}"
        )


def main():
    distributor = TokenDistributor()
    holders = distributor.get_richlist()
    distributor.process_payments(holders)
    distributor.generate_audit_report()
    distributor.display_summary_report()


if __name__ == "__main__":
    main()
