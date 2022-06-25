import json
import requests
import sys
import random

# typing
from typing import List, Dict, Union
from eth_typing import HexStr, BlockNumber, ChecksumAddress
from web3.eth import TxParams

from web3 import Web3
from getpass import getpass
from pathlib import Path
from eth_account import Account, messages

from geth_client import CONFIG


_owner_address = CONFIG['owner']
_owner_key_file = CONFIG['owner_keyfile']
_flashbots_relay_host = "https://relay.flashbots.net"
owner = None


def set_owner(key_file: str=_owner_key_file):
    key_file = Path.home().joinpath('.ethereum/keystore').joinpath(key_file)
    with open(key_file) as keyfile:
        encrypted_key = keyfile.read()
        key = Account.decrypt(encrypted_key, getpass("Enter the password to unlock this account: "))
    setattr(sys.modules[__name__], 'owner', Account.from_key(key))


def sign_transactions(transactions: List[TxParams]) -> List[List[HexStr]]:
    signed_txs_dicts = [Account.sign_transaction(tx, owner.key) for tx in transactions]
    tx_hashs = [tx['hash'].hex() for tx in signed_txs_dicts]
    signed_txs = [tx['rawTransaction'].hex() for tx in signed_txs_dicts]
    return tx_hashs, signed_txs


def sign_and_send_bundle(transactions: List[TxParams],
                         current_block: BlockNumber,
                         target_block: BlockNumber,
                         arb_data: Dict[str, Union[int, TxParams, Dict[str, Union[int, List[ChecksumAddress]]]]],
                         simulate: bool=True) -> Union[bool, List[HexStr]]:

    tx_hashs, signed_txs = sign_transactions(transactions)

    body = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": f"eth_{'call' if simulate else 'send'}Bundle",
        "params": [signed_txs, hex(target_block)] + (['latest'] if simulate else [])
    }
    body_str = json.dumps(body)
    message = messages.encode_defunct(text=Web3.keccak(text=body_str).hex())
    sig = owner.address + ':' + Account.sign_message(message, owner.key).signature.hex()

    print(f"sending transactions to flashbots relay @ {_flashbots_relay_host}:\n{tx_hashs}")
    response = requests.post(_flashbots_relay_host,
                             json=body, headers={"X-Flashbots-Signature": sig})
    results = json.loads(response.text)
    print(results)

    if simulate:
        if 'error' in results:
            raise Exception(results['error'])

    for r in results['result']['results']:
        if 'error' in r or r['ethSentToCoinbase'] == '0':
            return False

        relay_block_height = results['result']['stateBlockNumber']
        if relay_block_height < current_block:
            print("flashbots relay behind this node")
        elif relay_block_height > current_block:
            print("this node behind flashbots relay")

        with open("flashbots_log.json", 'r+') as f:
            log = json.load(f)
            log.update({current_block: {'arb_data': arb_data, 'relay_response': results}})
            f.seek(0)
            f.truncate()
            json.dump(log, f)

    return tx_hashs


def get_bribe(profit: int, min_gas_cost_eth: int) -> int:
    min_bribe = 0.9
    max_bribe = 0.95
    bribe = int(random.uniform(min_bribe, max_bribe) * profit)
    return max(bribe, min_gas_cost_eth)
