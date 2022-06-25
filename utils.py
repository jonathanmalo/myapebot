from typing import Tuple
from web3 import Web3
from eth_abi import encode_abi, encode_single
from datetime import datetime
from hexbytes import HexBytes

from eth_typing import HexAddress, ChecksumAddress, HexStr

TokenPair = Tuple[ChecksumAddress, ChecksumAddress]


def sig(signature: str) -> HexBytes:
    return Web3.keccak(text=signature)[:4]


def checksum(token: HexAddress) -> ChecksumAddress:
    return Web3.toChecksumAddress(token)


def encode_pair(pair: TokenPair) -> HexStr:
    return encode_abi(['address', 'address'], pair).hex()


def encode_address(address: HexAddress) -> HexStr:
    return encode_single('address', address).hex()


def tminus(n: int) -> int:
    now = datetime.utcnow().timestamp()
    return int(now + n)
