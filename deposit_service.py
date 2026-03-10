import requests
import logging

logger = logging.getLogger(__name__)


class DepositVerifier:

    def __init__(self):
        self.etherscan_api_key = "YOUR_ETHERSCAN_API_KEY"

    def check_eth_deposits(self, address):
        try:
            url = "https://api.etherscan.io/api"

            params = {
                "module": "account",
                "action": "txlist",
                "address": address,
                "sort": "desc",
                "apikey": self.etherscan_api_key
            }

            response = requests.get(url, params=params, timeout=10)
            data = response.json()

            deposits = []

            # =========================
            # ETH TRANSACTIONS
            # =========================
            if data.get("status") == "1":
                for tx in data.get("result", [])[:20]:
                    if (
                        int(tx.get("value", 0)) > 0 and
                        tx.get("to", "").lower() == address.lower()
                    ):
                        deposits.append({
                            "hash": tx["hash"],
                            "from": tx["from"],
                            "to": tx["to"],
                            "amount": int(tx["value"]) / 1e18,
                            "currency": "ETH",
                            "confirmations": int(tx.get("confirmations", 0)),
                            "timestamp": int(tx.get("timeStamp", 0)),
                            "status": (
                                "confirmed"
                                if int(tx.get("confirmations", 0)) > 12
                                else "pending"
                            )
                        })

            # =========================
            # ERC20 TOKEN TRANSFERS
            # =========================
            token_params = {
                "module": "account",
                "action": "tokentx",
                "address": address,
                "sort": "desc",
                "apikey": self.etherscan_api_key
            }

            token_response = requests.get(url, params=token_params, timeout=10)
            token_data = token_response.json()

            if token_data.get("status") == "1":
                for tx in token_data.get("result", [])[:20]:
                    if tx["to"].lower() == address.lower():

                        decimals = int(tx.get("tokenDecimal", 18))

                        deposits.append({
                            "hash": tx["hash"],
                            "from": tx["from"],
                            "to": tx["to"],
                            "amount": int(tx["value"]) / (10 ** decimals),
                            "currency": tx["tokenSymbol"],
                            "token_address": tx["contractAddress"],
                            "confirmations": int(tx.get("confirmations", 0)),
                            "timestamp": int(tx.get("timeStamp", 0)),
                            "status": (
                                "confirmed"
                                if int(tx.get("confirmations", 0)) > 12
                                else "pending"
                            )
                        })

            return deposits

        except Exception as e:
            logger.error(f"Error checking ETH deposits: {e}")
            return []


# =========================
# CREATE GLOBAL INSTANCE
# =========================
verifier = DepositVerifier()