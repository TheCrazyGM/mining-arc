# Hive Engine Token Distribution Script

## Overview

The **Hive Engine Token Distribution Script** is a Python script designed to retrieve a token's richlist, calculate payouts based on token holdings, and distribute tokens to the respective holders. This script is particularly useful for token creators and managers who want to automate the distribution of tokens to their community.

## Requirements

- Python version: **>= 3.12**
- Required Python packages:
  - `beem`
  - `hiveengine`
  - `python-dotenv`
  - `prettytable`

## Environment Variables

Before running the script, ensure that the following environment variables are set:

- `ACTIVE_WIF`: The active key for token transfers.
- `POSTING_WIF`: The posting key for blockchain interactions.

You can use a `.env` file to store these variables, and the script will load them automatically using the `python-dotenv` package.

## Configuration

The script contains a configuration section where you can adjust the following parameters:

- `PAYOUT_RATE`: The rate at which tokens are distributed (default is `0.250`).
- `TOKEN_QUERY`: The token symbol to query (default is `ARCHONM`).
- `TOKEN_NAME`: The name of the token (default is `ARCHON`).
- `BLACKLISTED_ACCOUNTS`: A list of accounts that should be excluded from the distribution (default includes `ufm.pay` and `upfundme`).
- `NODE_URLS`: A list of Hive node URLs to connect to (default includes `https://api.hive.blog`).
- `HIVE_ENGINE_API_URL`: The API URL for Hive Engine (default is `https://api.hive-engine.com/rpc/`).

## Usage
1. Set up your environment variables in a `.env` file:

   ```plaintext
   ACTIVE_WIF=your_active_wif_key
   POSTING_WIF=your_posting_wif_key
   ```
2. The script is self-contained and can be executed directly using `uv` for package management.

   ```bash
   pipx install uv
   curl -L https://raw.githubusercontent.com/TheCrazyGM/mining-arc/refs/heads/main/src/mining_arc/__init__.py -o mining_arc.py
   chmod +x mining_arc.py
   ./mining_arc.py
   ```

## Alternative Usage

1. Clone the repository:

   ```bash
   git clone https://github.com/TheCrazyGM/mining-arc.git
   cd mining-arc 
   ```

2. Install the required dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Set up your environment variables in a `.env` file:

   ```plaintext
   ACTIVE_WIF=your_active_wif_key
   POSTING_WIF=your_posting_wif_key
   ```

4. Run the script:
   ```bash
   python3 mining_arc.py
   ```

## Logging

The script uses Python's built-in logging module to log information and errors. The log messages will be printed to the console, providing insights into the script's execution flow.

## Functions

- `initialize_blockchain_connections()`: Initializes connections to the Hive and Hive Engine blockchains.
- `get_richlist()`: Retrieves and filters the token holder richlist.
- `send_transaction(hive_wallet, recipient, amount)`: Sends a token transaction to a specified recipient.
- `process_payments(hive_wallet, data)`: Processes and distributes token payments to holders.
- `display_richlist(data)`: Displays the richlist in a formatted table.

## Contributing

Contributions are welcome! If you have suggestions for improvements or find bugs, please open an issue or submit a pull request.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## Acknowledgments

- [Beem](https://github.com/holgerd77/beem): A Python library for interacting with the Hive blockchain.
- [Hive Engine](https://hive-engine.com): A decentralized token platform on the Hive blockchain.
- [PrettyTable](https://pypi.org/project/prettytable/): A simple Python library for displaying tabular data in a visually appealing way.
