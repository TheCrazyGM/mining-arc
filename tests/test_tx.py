#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "hive-nectar",
#     "nectarengine",
#     "python-dotenv",
# ]
# ///
import os
from decimal import Decimal

from dotenv import load_dotenv
from nectar import Hive
from nectar.wallet import Wallet
from nectarengine.api import Api
from nectarengine.wallet import Wallet as HiveEngineWallet

# Load .env values
load_dotenv()

# Prepare environment variables
ACTIVE_WIF = os.getenv("ACTIVE_WIF")
POSTING_WIF = os.getenv("POSTING_WIF")
NODE_URL = os.getenv("NODE_URL", "https://api.hive.blog")
HIVE_ENGINE_API_URL = os.getenv("HIVE_ENGINE_API_URL", "https://enginerpc.com/")
NO_BROADCAST = os.getenv("DRY_RUN", "0").lower() in ("true", "1", "yes")

assert ACTIVE_WIF and POSTING_WIF, "You must set ACTIVE_WIF and POSTING_WIF in .env!"

# Set up clients
hive = Hive(node=NODE_URL, keys=[POSTING_WIF, ACTIVE_WIF], nobroadcast=NO_BROADCAST)
wallet = Wallet(blockchain_instance=hive)
account = wallet.getAccountFromPrivateKey(ACTIVE_WIF)
api = Api(url=HIVE_ENGINE_API_URL)
he_wallet = HiveEngineWallet(account, blockchain_instance=hive, api=api)

# Prepare transaction details
recipient = "ecoinstats"
amount = Decimal("0.001")
token = "SWAP.HIVE"
memo = "Test transfer from mining-arc script"

# Send and print transaction
result = he_wallet.transfer(recipient, f"{amount:.3f}", token, memo)
print("Transaction response:", result)
