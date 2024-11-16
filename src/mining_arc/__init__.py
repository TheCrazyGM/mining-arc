#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "beem",
#     "hiveengine",
#     "python-dotenv",
#     "prettytable",
# ]
# ///
"""
Hive Engine Token Distribution Script

This script retrieves a token's richlist, calculates payouts based on holdings,
and distributes tokens to token holders.

Requires environment variables:
- ACTIVE_WIF: Active key for token transfers
- POSTING_WIF: Posting key for blockchain interactions
"""
import logging
import math
import os
import sys
import time
from dataclasses import dataclass
from typing import List, Optional, Tuple 

from beem import Hive
from beem.wallet import Wallet
from dotenv import load_dotenv
from hiveengine.api import Api
from hiveengine.tokenobject import Token
from hiveengine.wallet import Wallet as HiveEngineWallet
from prettytable import PrettyTable, TableStyle

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

@dataclass
class TokenConfig:
    """Configuration settings for token distribution."""
    payout_rate: float
    token_query: str
    token_name: str
    blacklisted_accounts: List[str]
    node_urls: List[str]
    hive_engine_api_url: str
    nobroadcast: bool

    @classmethod
    def from_env(cls) -> 'TokenConfig':
        """Create configuration from environment variables with defaults."""
        return cls(
            payout_rate=float(os.getenv('PAYOUT_RATE', '0.250')),
            token_query=os.getenv('TOKEN_QUERY', 'ARCHONM'),
            token_name=os.getenv('TOKEN_NAME', 'ARCHON'),
            blacklisted_accounts=os.getenv('BLACKLISTED_ACCOUNTS', 'ufm.pay,upfundme').split(','),
            node_urls=[os.getenv('NODE_URL', 'https://api.hive.blog')],
            hive_engine_api_url=os.getenv('HIVE_ENGINE_API_URL', 'https://api.hive-engine.com/rpc/'),
            nobroadcast=os.getenv('DRY_RUN', '').lower() in ('true', '1', 'yes')
        )

@dataclass
class TokenHolder:
    """Represents a token holder with their balance."""
    account: str
    balance: float

    @property
    def payment_amount(self, config: TokenConfig) -> float:
        """Calculate payment amount based on balance and payout rate."""
        return self.balance * config.payout_rate

class TokenDistributor:
    """Handles token distribution operations."""
    
    def __init__(self):
        """Initialize the token distributor."""
        load_dotenv()
        self.config = TokenConfig.from_env()
        self._validate_environment()
        self.hive_instance, self.hive_wallet = self._initialize_blockchain()

    def _validate_environment(self) -> None:
        """Validate required environment variables are present."""
        required_vars = ['ACTIVE_WIF', 'POSTING_WIF']
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        if missing_vars:
            logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
            sys.exit(1)

    def _initialize_blockchain(self) -> Tuple[Hive, HiveEngineWallet]:
        """Initialize blockchain connections."""
        try:
            active_wif = os.environ["ACTIVE_WIF"]
            posting_wif = os.environ["POSTING_WIF"]

            if self.config.nobroadcast:
                logger.warning("Running in DRY RUN mode - no transactions will be broadcast")

            hive_instance = Hive(
                node=self.config.node_urls,
                keys=[posting_wif, active_wif],
                nobroadcast=self.config.nobroadcast
            )

            wallet = Wallet(blockchain_instance=hive_instance)
            sender_account = wallet.getAccountFromPrivateKey(active_wif)

            api = Api(url=self.config.hive_engine_api_url)
            hive_wallet = HiveEngineWallet(
                sender_account,
                blockchain_instance=hive_instance,
                api=api
            )

            return hive_instance, hive_wallet

        except Exception as e:
            logger.error(f"Failed to initialize blockchain connections: {e}")
            sys.exit(1)

    def get_richlist(self) -> List[TokenHolder]:
        """Retrieve and filter token holder richlist."""
        try:
            api = Api(url=self.config.hive_engine_api_url)
            token = Token(self.config.token_query, api=api)
            richlist = token.get_holder()

            holders = [
                TokenHolder(
                    account=holder["account"],
                    balance=math.floor(float(holder["balance"]))
                )
                for holder in richlist
                if (
                    math.floor(float(holder["balance"])) > 0
                    and holder["account"] not in self.config.blacklisted_accounts
                )
            ]

            logger.info(f"Retrieved richlist with {len(holders)} accounts")
            return holders

        except Exception as e:
            logger.error(f"Error retrieving richlist: {e}")
            return []

    def send_transaction(self, recipient: str, amount: float) -> Optional[dict]:
        """Send token transaction to a recipient."""
        try:
            logger.info(f"Sending {amount} {self.config.token_name} to {recipient}")
            transaction = self.hive_wallet.transfer(
                recipient,
                amount,
                self.config.token_name,
                f"{amount} = {self.config.payout_rate} {self.config.token_name} "
                f"per whole {self.config.token_query} mining share"
            )
            logger.debug(f"Transaction details: {transaction}")
            return transaction
        except Exception as error:
            logger.warning(f"Transaction error for {recipient}: {error}")
            return None

    def process_payments(self, holders: List[TokenHolder]) -> None:
        """Process and distribute token payments."""
        for holder in holders:
            payment_amount = holder.balance * self.config.payout_rate
            if payment_amount > 0.0:
                self.send_transaction(holder.account, payment_amount)
                time.sleep(1)  # Rate limiting

    def display_richlist(self, holders: List[TokenHolder]) -> None:
        """Display richlist in a formatted table."""
        table = PrettyTable(["Account", "Holding", "Payment"])
        table.set_style(TableStyle.MARKDOWN)
        table.align["Account"] = "l"
        table.align["Holding"] = "r"
        table.align["Payment"] = "r"

        for holder in holders:
            payment_amount = holder.balance * self.config.payout_rate
            table.add_row(
                [holder.account, holder.balance, f"{payment_amount:0.4f}"]
            )

        print(table.get_string(sortby="Holding", reversesort=True))

def main():
    """Main script execution function."""
    try:
        distributor = TokenDistributor()
        richlist = distributor.get_richlist()
        distributor.process_payments(richlist)
        distributor.display_richlist(richlist)
    except Exception as e:
        logger.error(f"Script execution error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
