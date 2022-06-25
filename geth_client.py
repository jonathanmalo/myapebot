import asyncio
import sys
import requests
import json
import configparser
from aiohttp import ClientSession
from time import sleep

# typing
from web3.eth import Contract, TxParams
from typing import List, Tuple, Union, Optional
from eth_typing import ChecksumAddress, HexAddress, BlockNumber, HexStr

from web3 import Web3
from web3.exceptions import MismatchedABI
from web3.providers.base import JSONBaseProvider
from web3.providers import HTTPProvider, WebsocketProvider

from eth_abi import decode_abi
from eth_abi.exceptions import InsufficientDataBytes
from hexbytes import HexBytes


TIME_UNTIL_NEXT_BLOCK = 7         # TODO: Poissonify

config = configparser.ConfigParser()
config.read('config.ini')
CONFIG = config['DEFAULT']
_web_socket = CONFIG['ws']
_ws_provider = WebsocketProvider(_web_socket)
_ws_geth_client = Web3(_ws_provider)
_geth_local_host = CONFIG['http']
_http_provider = HTTPProvider(_geth_local_host)
_http_geth_client = Web3(_http_provider)
_ganache_local_host = CONFIG['ganache']
_ganache_provider = HTTPProvider(_ganache_local_host)
_ganache_client = Web3(_ganache_provider)
_aws_host = CONFIG['aws']
_aws_provider = HTTPProvider(_aws_host)
_aws_client = Web3(_aws_provider)

_etherscan_apikey = CONFIG['etherscan_apikey']
_etherscan_url = 'https://api.etherscan.io/api'
SESSION = requests.Session()
BOT = CONFIG['bot']


def rebind():
    provider = WebsocketProvider(_web_socket)
    setattr(sys.modules[__name__], '_provider', provider)
    setattr(sys.modules[__name__], '_ws_geth_client', Web3(provider))


def get_abi(address: HexAddress) -> dict:
    print(f"retreiving contract ABI @ {address}")
    params = {
        'module': 'contract',
        'action': 'getabi',
        'apikey': _etherscan_apikey,
        'address': address
    }
    abi_str = SESSION.get(_etherscan_url, params=params).json()['result']
    if abi_str == 'contract source code not verified':
        return False
    abi = json.loads(abi_str)
    sleep(0.2)
    return abi


def get_contract(address: HexAddress, abi: dict=None, ganache: bool=False) -> Union[Contract, bool]:
    try:
        abi = get_abi(address) if abi is None else abi
        client = _ganache_client if ganache else _http_geth_client
        contract = client.eth.contract(Web3.toChecksumAddress(address), abi=abi)
        return contract
    except MismatchedABI:
        print(f'MismatchedABI @ {address}')
        return False


def wait_for_sync():
    while _http_geth_client.eth.syncing:
        syncing_attr = _http_geth_client.eth.syncing
        if syncing_attr.currentBlock == syncing_attr.highestBlock:
            break
        print("waiting for nodes to sync...\r", end="")
        sleep(1)


async def async_make_request(session: ClientSession, rpc_endpoint: str, method: str, params: list, _id: int):
    base_provider = JSONBaseProvider()
    request_data = base_provider.encode_rpc_request(method, params)
    async with session.post(rpc_endpoint,
                            data=request_data,
                            headers={'Content-Type': 'application/json'}) as response:
        content = await response.read()
    response = base_provider.decode_rpc_response(content)
    response['id'] = _id

    return response


async def run_batch(rpc_endpoint: str, payload: List[dict]):
    tasks = []

    async with ClientSession() as session:
        for job in payload:
            task = asyncio.ensure_future(async_make_request(session, rpc_endpoint, job['method'], job['params'], job['id']))
            tasks.append(task)

        return await asyncio.gather(*tasks)


RequestParams = Tuple[HexAddress, HexStr, List[str], Optional[int]]
ContractCallReturnValue = Union[int, HexAddress, List[Union[int, HexAddress]]]


def batch_request(requests: List[RequestParams], ganache: bool=False) -> List[ContractCallReturnValue]:
    # credit to jakublipinski
    payload = [{'method': 'eth_call',
                'params': [{'to': req[0], 'data': req[1]}, 'latest'], 'id': i}
               for i, req in enumerate(requests)]
    responses = asyncio.run(run_batch(_ganache_local_host if ganache else _geth_local_host, payload))
    results = [response['result'] for response in sorted(responses, key=lambda r: r['id'])]
    decoded_results = list()
    for req, res in zip(requests, results):
        try:
            decoded_result = decode_abi(req[2], HexBytes(res))
            decoded_results.append(decoded_result)
        except InsufficientDataBytes:
            print(f"Failed on request: {req}")
            print(f"Gave result: {res}")
            raise

    decoded_results = [dres if req[3] is None else dres[req[3]] for req, dres in zip(requests, decoded_results)]
    list_results = [list(res) if type(res) is tuple else res for res in decoded_results]
    return list_results


def request(to_address: HexAddress, data: HexStr, output_type: str, ganache: bool=False) -> ContractCallReturnValue:
    provider = _ganache_provider if ganache else _http_provider
    response = provider.make_request('eth_call', [{'to': to_address, 'data': data}, 'latest'])
    if 'error' in response.keys():
        raise ValueError
    else:
        result = response['result']
        value = decode_abi(output_type, HexBytes(result))
        if len(output_type) == 1:
            list_result = list(value[0]) if type(value[0]) is tuple else value[0]
            return list_result
        return value


def latest_block(ganache: bool=False) -> BlockNumber:
    client = _ganache_client if ganache else _http_geth_client
    return client.eth.blockNumber


def balance(address: ChecksumAddress, ganache: bool=False):
    client = _ganache_client if ganache else _http_geth_client
    return client.eth.get_balance(address)


def estimate_gas(transaction: TxParams, ganache: bool=False) -> int:
    client = _ganache_client if ganache else _http_geth_client
    return client.eth.estimate_gas(transaction)
