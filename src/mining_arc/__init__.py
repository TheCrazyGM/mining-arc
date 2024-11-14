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
import time
from typing import Dict, List

from beem import Hive
from beem.wallet import Wallet
from dotenv import load_dotenv
from hiveengine.api import Api
from hiveengine.tokenobject import Token
from hiveengine.wallet import Wallet as HiveEngineWallet
from prettytable import PrettyTable, TableStyle

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

# Load environment variables
load_dotenv()

# Configuration Constants
CONFIG = {
    "PAYOUT_RATE": 0.250,
    "TOKEN_QUERY": "ARCHONM",
    "TOKEN_NAME": "ARCHON",
    "BLACKLISTED_ACCOUNTS": ["ufm.pay", "upfundme"],
    "NODE_URLS": ["https://api.hive.blog"],
    "HIVE_ENGINE_API_URL": "https://api.hive-engine.com/rpc/",
}


def initialize_blockchain_connections() -> tuple:
    """
    Initialize Hive and Hive Engine blockchain connections.

    Returns:
        tuple: Initialized Hive instance, wallet, and Hive Engine wallet
    """
    # Retrieve WIF keys from environment
    active_wif = os.environ["ACTIVE_WIF"]
    posting_wif = os.environ["POSTING_WIF"]

    # Initialize Hive instance
    hive_instance = Hive(
        node=CONFIG["NODE_URLS"], keys=[posting_wif, active_wif], nobroadcast=False
    )

    # Initialize wallets
    wallet = Wallet(blockchain_instance=hive_instance)
    sender_account = wallet.getAccountFromPrivateKey(active_wif)

    api = Api(url=CONFIG["HIVE_ENGINE_API_URL"])
    hive_wallet = HiveEngineWallet(
        sender_account, blockchain_instance=hive_instance, api=api
    )

    return hive_instance, hive_wallet


def get_richlist() -> List[Dict[str, str]]:
    """
    Retrieve and filter the token holder richlist.

    Returns:
        List of dictionaries containing account and balance information
    """
    try:
        api = Api(url=CONFIG["HIVE_ENGINE_API_URL"])
        token = Token(CONFIG["TOKEN_QUERY"], api=api)
        richlist = token.get_holder()

        # Filter and process richlist
        filtered_richlist = [
            {
                "account": holder["account"],
                "balance": math.floor(float(holder["balance"])),
            }
            for holder in richlist
            if (
                math.floor(float(holder["balance"])) > 0
                and holder["account"] not in CONFIG["BLACKLISTED_ACCOUNTS"]
            )
        ]

        logging.info(f"Retrieved richlist with {len(filtered_richlist)} accounts")
        return filtered_richlist

    except Exception as e:
        logging.error(f"Error retrieving richlist: {e}")
        return []


def send_transaction(hive_wallet, recipient: str, amount: float):
    """
    Send token transaction to a recipient.

    Args:
        hive_wallet: Hive Engine wallet instance
        recipient: Account to receive tokens
        amount: Amount of tokens to transfer
    """
    try:
        logging.info(f"Sending {amount} {CONFIG['TOKEN_NAME']} to {recipient}")
        transaction = hive_wallet.transfer(
            recipient,
            amount,
            CONFIG["TOKEN_NAME"],
            f"{amount} = {CONFIG['PAYOUT_RATE']} {CONFIG['TOKEN_NAME']} per whole {CONFIG['TOKEN_QUERY']} mining share",
        )
        logging.debug(transaction)
    except Exception as error:
        logging.warning(f"Transaction error for {recipient}: {error}")


def process_payments(hive_wallet, data: List[Dict[str, str]]):
    """
    Process and distribute token payments.

    Args:
        hive_wallet: Hive Engine wallet instance
        data: List of account holders with balances
    """
    for holder in data:
        payment_amount = holder["balance"] * CONFIG["PAYOUT_RATE"]
        if payment_amount > 0.0:
            send_transaction(hive_wallet, holder["account"], payment_amount)
            time.sleep(1)  # Rate limiting


def display_richlist(data: List[Dict[str, str]]):
    """
    Display richlist in a formatted table.

    Args:
        data: List of account holders with balances
    """
    table = PrettyTable(["Account", "Holding", "Payment"])
    table.set_style(TableStyle.MARKDOWN)
    table.align["Account"] = "l"
    table.align["Holding"] = "r"
    table.align["Payment"] = "r"

    for holder in data:
        payment_amount = holder["balance"] * CONFIG["PAYOUT_RATE"]
        table.add_row([holder["account"], holder["balance"], f"{payment_amount:0.4f}"])

    print(table.get_string(sortby="Holding", reversesort=True))


def main():
    """
    Main script execution function.
    """
    try:
        _, hive_wallet = initialize_blockchain_connections()
        richlist = get_richlist()
        process_payments(hive_wallet, richlist)
        display_richlist(richlist)
    except Exception as e:
        logging.error(f"Script execution error: {e}")


if __name__ == "__main__":
    main()
