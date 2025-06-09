#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "hive-nectar",
#     "nectarengine",
#     "python-dotenv",
#     "rich",
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

from dotenv import load_dotenv
from nectar import Hive
from nectar.wallet import Wallet
from nectarengine.api import Api
from nectarengine.tokenobject import Token
from nectarengine.wallet import Wallet as HiveEngineWallet
from rich.console import Console
from rich.logging import RichHandler
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)

load_dotenv()
# Rich Console for pretty output
console = Console()

# Decimal precision setup
getcontext().prec = 16


# Configure logging with rich
log_level = getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO)
logging.basicConfig(
    level=log_level,
    format="%(message)s",
    handlers=[RichHandler(rich_tracebacks=True, show_time=True, show_path=False)],
)
logger = logging.getLogger("rich")


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
            # Only log detailed messages if logger level allows it
            if logger.level <= logging.INFO:
                logger.info(f"Paying {recipient} {amount} {self.config.token_name}")

            tx = self.hive_wallet.transfer(
                recipient, f"{amount:.4f}", self.config.token_name, memo
            )
            if tx:
                tx_id = tx.get("trx_id") or ""
            else:
                tx_id = "DRY_RUN"
            self.stats["successful_payments"] += 1
            self.stats["total_tokens_distributed"] += amount
            return tx_id
        except Exception as e:
            # Always log errors, but store them for later display if needed
            if logger.level <= logging.ERROR:
                logger.error(f"Failed tx for {recipient}: {e}")
            self.stats["failed_payments"] += 1
            return None

    def process_payments(self, holders: List[TokenHolder]) -> None:
        self.stats["start_time"] = time.time()

        # Temporarily reduce logging level during progress display
        original_level = logger.level
        logger.setLevel(logging.WARNING)

        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]Processing payments...[/bold blue]"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("({task.completed}/{task.total} holders)"),
            TimeElapsedColumn(),
            console=console,
            transient=False,  # Keep progress bar visible after completion
        ) as progress:
            task = progress.add_task("Processing", total=len(holders))

            for holder in holders:
                amount = holder.payment_amount(self.config)
                if amount > Decimal("0.0000"):
                    # Record transaction time before sending
                    tx_timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

                    # Update progress description with current user
                    progress.update(
                        task,
                        description=f"[bold blue]Paying {holder.account}...[/bold blue]",
                    )

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
                progress.advance(task)

        # Restore original logging level
        logger.setLevel(original_level)

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
        console.print("\n" + "=" * 80)
        console.print("[cyan bold]🔶 TOKEN DISTRIBUTION SUMMARY REPORT 🔶[/cyan bold]")
        console.print("=" * 80)

        # Configuration section
        console.print("[yellow bold]📋 Configuration:[/yellow bold]")
        console.print(
            f"  • Token: [green]{self.config.token_name}[/green] (query: {self.config.token_query})"
        )
        console.print(f"  • Payout Rate: [green]{self.config.payout_rate}[/green]")
        console.print(
            f"  • Mode: [{'red' if self.config.nobroadcast else 'green'}]{'DRY RUN' if self.config.nobroadcast else 'LIVE'}[/{'red' if self.config.nobroadcast else 'green'}]"
        )
        console.print(
            f"  • Timestamp: [cyan]{time.strftime('%Y-%m-%d %H:%M:%S')}[/cyan]"
        )

        # Results section
        console.print("\n[yellow bold]📊 Results:[/yellow bold]")
        console.print(
            f"  • Total Holders Processed: [cyan]{self.stats['total_holders']}[/cyan]"
        )
        console.print(
            f"  • Successful Payments: [green]{self.stats['successful_payments']}[/green]"
        )
        console.print(
            f"  • Failed Payments: [red]{self.stats['failed_payments']}[/red]"
        )
        console.print(
            f"  • Success Rate: [green]{(self.stats['successful_payments'] / max(self.stats['total_holders'], 1)) * 100:.1f}%[/green]"
        )

        # Tokens section
        console.print("\n[yellow bold]💰 Tokens:[/yellow bold]")
        console.print(
            f"  • Total {self.config.token_name} Distributed: [green]{self.stats['total_tokens_distributed']:.4f}[/green]"
        )
        if self.stats["total_holders"] > 0:
            avg_per_holder = (
                self.stats["total_tokens_distributed"] / self.stats["total_holders"]
            )
            console.print(f"  • Average Per Holder: [cyan]{avg_per_holder:.4f}[/cyan]")

        # Time section
        console.print("\n[yellow bold]⏱️ Time:[/yellow bold]")
        console.print(f"  • Duration: [cyan]{duration:.2f} seconds[/cyan]")
        if self.stats["successful_payments"] > 0 and duration > 0:
            console.print(
                f"  • Average Time Per Payment: [cyan]{duration / self.stats['successful_payments']:.2f} seconds[/cyan]"
            )

        console.print("=" * 80)

        # Add a note about the audit file
        audit_filename = self.stats.get("audit_filename", "transaction_audit.csv")
        console.print(
            f"\n[cyan]📝 Detailed transaction audit saved to: {audit_filename}[/cyan]"
        )


def main():
    distributor = TokenDistributor()
    holders = distributor.get_richlist()
    distributor.process_payments(holders)
    distributor.generate_audit_report()
    distributor.display_summary_report()


if __name__ == "__main__":
    main()
