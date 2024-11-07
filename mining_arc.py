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

import logging
import os
import time

from beem import Hive
from beem.wallet import Wallet
from dotenv import load_dotenv
from hiveengine.api import Api
from hiveengine.tokenobject import Token
from hiveengine.wallet import Wallet as HWallet
from prettytable import PrettyTable, TableStyle

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

# Load environment variables from .env file
load_dotenv()

# Constants
PAYOUT_RATE = 0.250
TOKEN_QUERY = "ARCHONM"
TOKEN_NAME = "ARCHON"
BLACKLISTED_ACCOUNTS = ["ufm.pay", "upfundme"]

# Define the nodes to connect to
NODE_URLS = ["https://api.hive.blog"]
api = Api(url="https://api.hive-engine.com/rpc/")

# Get the Hive WIF from environment variables
active_wif = os.environ["ACTIVE_WIF"]
posting_wif = os.environ["POSTING_WIF"]
hive_instance = Hive(
    node=NODE_URLS,
    keys=[posting_wif, active_wif],
    nobroadcast=True,
)

# Initialize wallet and account instances
wallet = Wallet(blockchain_instance=hive_instance)
sender_account = wallet.getAccountFromPrivateKey(active_wif)
hive_wallet = HWallet(sender_account, blockchain_instance=hive_instance, api=api)

def get_richlist():
    """
    Retrieve the current richlist and filter out accounts with zero balance or in the blacklist.

    Returns:
        list: A filtered list of account holders with non-zero balances.
    """
    token = Token(TOKEN_QUERY, api=api)
    richlist = token.get_holder()
    logging.info("Richlist successfully retrieved.")

    # Filter the richlist to exclude blacklisted accounts and those with zero balance
    filtered_richlist = [
        hodl
        for hodl in richlist
        if (
            int(float(hodl["balance"])) > 0
            and hodl["account"] not in BLACKLISTED_ACCOUNTS
        )
    ]

    return filtered_richlist


def send_transaction(recipient, amount):
    """
    Transfer the specified amount of the specified token to the recipient's account.

    Args:
        recipient (str): The account to send the tokens to.
        amount (str): The amount of tokens to send.
    """
    try:
        print(f"Sending {amount} {TOKEN_NAME} to {recipient}.")
        transaction = hive_wallet.transfer(
            recipient,
            amount,
            TOKEN_NAME,
            f"{amount} = {PAYOUT_RATE} {TOKEN_NAME} mining share per {TOKEN_QUERY}",
        )
        logging.info(transaction)
    except Exception as error:
        logging.warning(f"[Error: {error}]")


def process_payments(data):
    """
    Process payments for the specified accounts based on their balances.

    Args:
        data (list): A list of account holders with their balances.
    """
    for holder in data:
        payment_amount = (int(float(holder["balance"])) // 1) * PAYOUT_RATE
        if payment_amount > 0.0:
            recipient = holder["account"]
            send_transaction(recipient, payment_amount)
            time.sleep(1)  # Rate limit to avoid overwhelming the API


def display_richlist(data):
    """
    Create and print a formatted table of the richlist data.

    Args:
        data (list): A list of account holders with their balances.
    """
    # Create a pretty table
    richlist_table = PrettyTable(["Account", "Holding", "Payment"])
    richlist_table.set_style(TableStyle.MARKDOWN)
    richlist_table.align["Account"] = "l"
    richlist_table.align["Holding"] = "r"
    richlist_table.align["Payment"] = "r"

    # Add rows to the table
    for holder in data:
        payment_amount = (int(float(holder["balance"])) // 1) * PAYOUT_RATE
        richlist_table.add_row(
            [holder["account"], holder["balance"], f"{payment_amount:0.4f}"]
        )

    # Print the table sorted by Holding in descending order
    print(richlist_table.get_string(sortby="Holding", reversesort=True))


def main():
    """
    Main function to execute the richlist processing and display.
    """
    richlist = get_richlist()
    process_payments(richlist)
    display_richlist(richlist)


if __name__ == "__main__":
    main()
