# Hive Engine Token Distribution Script

## Overview

The **Hive Engine Token Distribution Script** is a Python script designed to retrieve a token's richlist, calculate payouts based on token holdings, and distribute tokens to the respective holders. This script is particularly useful for token creators and managers who want to automate the distribution of tokens to their community.

## Features

- 🔒 Secure environment-based configuration
- 📊 Rich table-based output of token distributions
- 🧪 Dry run mode for testing
- 📝 Detailed logging
- ⚡ Rate-limited transactions to prevent API throttling
- 🛡️ Blacklist support for excluded accounts
- 🔄 Automatic floor calculation for token balances

## Requirements

- Python version: **>= 3.12**
- Required Python packages:
  - `beem`
  - `hiveengine`
  - `python-dotenv`
  - `prettytable`

## Environment Variables

The script is highly configurable through environment variables. You can set these in a `.env` file or your system environment:

### Required Variables
- `ACTIVE_WIF`: The active key for token transfers
- `POSTING_WIF`: The posting key for blockchain interactions

### Optional Variables
- `PAYOUT_RATE`: The rate at which tokens are distributed (default: `0.250`)
- `TOKEN_QUERY`: The token symbol to query (default: `ARCHONM`)
- `TOKEN_NAME`: The name of the token (default: `ARCHON`)
- `BLACKLISTED_ACCOUNTS`: Comma-separated list of excluded accounts (default: `ufm.pay,upfundme`)
- `NODE_URL`: Hive node URL (default: `https://api.hive.blog`)
- `HIVE_ENGINE_API_URL`: Hive Engine API URL (default: `https://api.hive-engine.com/rpc/`)
- `DRY_RUN`: Enable dry run mode without broadcasting transactions (set to `true`, `1`, or `yes`)

## Usage

### Quick Start
1. Set up your environment variables in a `.env` file:
   ```plaintext
   ACTIVE_WIF=your_active_wif_key
   POSTING_WIF=your_posting_wif_key
   ```

2. The script is self-contained and can be executed directly using `uv` for package management:
   ```bash
   pipx install uv
   curl -L https://raw.githubusercontent.com/TheCrazyGM/mining-arc/refs/heads/main/src/mining_arc/__init__.py -o mining_arc.py
   chmod +x mining_arc.py
   ./mining_arc.py
   ```

### Alternative Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/TheCrazyGM/mining-arc.git
   cd mining-arc 
   ```

2. Install dependencies:
   ```bash
   # Using pip
   pip install -r requirements.txt
   
   # Or using uv
   uv sync
   ```

3. Run the script:
   ```bash
   python3 mining_arc.py
   ```

### Testing Mode

To test the script without broadcasting transactions:
```bash
DRY_RUN=true python3 mining_arc.py
```

## Architecture

The script uses a modern, class-based architecture for better organization and maintainability:

### Core Classes

- `TokenConfig`: Manages all configuration settings with environment variable support
- `TokenHolder`: Represents a token holder with their balance and payment calculations
- `TokenDistributor`: Main class handling all distribution operations

### Key Methods

- `TokenDistributor.get_richlist()`: Retrieves and filters the token holder richlist
- `TokenDistributor.send_transaction()`: Handles individual token transfers
- `TokenDistributor.process_payments()`: Orchestrates the payment distribution process
- `TokenDistributor.display_richlist()`: Generates a formatted table of distributions

## Logging

The script provides detailed logging with different levels:
- INFO: General operation information
- WARNING: Non-critical issues (e.g., transaction failures)
- ERROR: Critical issues that prevent operation
- DEBUG: Detailed transaction information (when needed)

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request. For major changes, please open an issue first to discuss what you would like to change.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
