#!/usr/bin/env python3

# typing
from typing import List, Tuple, Dict, Union, Set
from eth_typing import HexAddress, HexStr, ChecksumAddress, BlockNumber
from hexbytes import HexBytes
from brownie.network.account import LocalAccount
from brownie.network.contract import InterfaceConstructor
from geth_client import RequestParams
from web3.eth import Contract, TxParams
from web3.contract import ContractFunction
from eth_account import Account

# misc
import argparse
import random
import numpy
import math
import sys
import aiohttp
import web3

from time import time, sleep
from scipy.optimize import minimize, Bounds
from scipy import stats
from graph_tool.all import Graph, Vertex, Edge, all_paths
from itertools import combinations, permutations, product
from mpmath import mp
from collections import OrderedDict
from functools import reduce
from eth_abi import encode_abi, encode_single
from web3 import Web3

# project-level imports
from ape import Ape
import flashbots

from constants import (
    ETH,
    WETH,
    WETH_SCALE,
    MIN_GAS_COST_PER_SWAP,
    TRADE_SET,
    TICKERS,
    SOLINF,
    ZERO_ADDRESS,
    SUSHISWAP_FACTORY,
    UNISWAPV2_FACTORY,
    UNISWAPV3_FACTORY,
    MOONISWAP_FACTORY,
    BANCOR_NETWORK,
    BALANCER_REGISTRY,
    ZXV4
)
import geth_client
from utils import (
    TokenPair,
    sig,
    checksum,
    encode_pair,
    encode_address,
    tminus
)

if __name__ == "__main__":
    __mode_parser__ = argparse.ArgumentParser()
    __mode_parser__.add_argument('-m', '--mode', required=False,
                                 help='"live" to send over mainnet')
    __mode_parser__.add_argument('-pc', '--price_change', required=False,
                                 help='percent change in price to use in test mode')
    __price_change__ = float(__mode_parser__.parse_args().price_change)
    __live_mode__ = __mode_parser__.parse_args().mode == 'live'
else:
    __live_mode__ = False


__test_mode__ = not __live_mode__


import brownie
import brownie.network as network
brownie.project.load('bot')
brownie.network.connect('mainnet' if __live_mode__ else 'local-mainnet-fork')

from brownie.project.BotProject import interface, ApeBotV3, TestUniswapV3FlashCallback
from brownie import accounts, chain
from brownie.network.gas.strategies import GasNowStrategy
print(f"Ganache forked @ {chain.height - 1}")


# dex calculators
import dex.curve as curve
import dex.snowswap as snowswap
import dex.bancor as bancor
import dex.balancer as balancer


def get_decimals(trade_set: List[ChecksumAddress]) -> Dict[ChecksumAddress, int]:
    token_addresses = set(trade_set)
    decimals_sig = sig('decimals()').hex()
    requests = [[address, decimals_sig, ['uint256'], -1] for address in token_addresses]
    decimals_responses = geth_client.batch_request(requests)
    decimals = dict(zip(token_addresses, decimals_responses))
    decimals.update({ETH: 18})
    print(f"{len(token_addresses)} tokens added to trade set")
    return decimals


__trade_set__ = list(TRADE_SET.values())
__decimals__ = get_decimals(__trade_set__)
__faucet__ = accounts[0] if __test_mode__ else None

__balancer_swap__ = balancer.BalancerSwap()
__bancor_converter__ = bancor.BancorConversionPath()


def from_faucet(value: int) -> TxParams:
    return {'from': __faucet__.address, 'value': value}


class RevertTransactions:

    def __enter__(self):
        if __test_mode__:
            print("Saving chain snapshot")
            chain.snapshot()

    def __exit__(*unused_args):
        if __test_mode__:
            print("Reverting to chain snapshot")
            chain.revert()


class Pool:

    def __init__(self, pool_address: ChecksumAddress):
        self.address = pool_address      # address that swaps the out_token
        self._params = dict()

    def get_param_calls(self, pair: TokenPair):
        """ Return a list of args for retrieving the unipair's parameters in a batch request.
        """
        pass

    def set_params(self):
        """ Set parameters for computing get_out_amount.
        """
        pass

    def get_swap_data(self, in_amount: int, pair: TokenPair) -> HexBytes:
        """ Generate tx calldata for swapping in_amount of pair[0] for at least self.get_out_amount of pair[1].
        """
        pass

    def prep_swap(self, in_amount: int, out_amount: int, token_pair: TokenPair) -> InterfaceConstructor:
        if token_pair[0] == WETH:
            interface.IWETH9(WETH).deposit(from_faucet(in_amount))

        pool = interface.IExchange(self.address)
        for token_address, amount in zip(token_pair, [in_amount, out_amount]):
            token_contract = interface.IERC20(token_address)
            if token_address != ETH and \
               token_contract.allowance(__faucet__, pool) < amount:
                print(f"Infinite approval on {type(self).__name__} @ {pool.address} \n\t Token: {token_address}")
                token_contract.approve(pool, SOLINF, from_faucet(0))

        return pool

    def test_swap(self, in_amount: int, out_amount: int, pair: TokenPair):
        """ Swap in_amount of pair[0]  for out_amount of pair[1] on Gananche using accounts[0].
        """
        pass

    def get_out_amount(self, in_amount: int, pair: TokenPair) -> int:
        """ Calculate the amount of pair[1] you get for in_amount of pair[0] on this pair.
        """
        pass


class UniswapV2Pair(Pool):

    _get_reserves_sig = sig("getReserves()").hex()
    _swap_sig = sig('swap(uint256,uint256,address,bytes)')
    _add_liq_sig = sig('mint(address)').hex()
    _rem_liq_sig = sig('burn(address)').hex()

    def __init__(self, pair_address: ChecksumAddress, tokens: TokenPair):
        super().__init__(pair_address)
        self._reserves = dict()
        self._tokens = tokens
        self._fee = mp.mpf(0.997)

    def get_swap_data(self, in_amount: int, out_amount: int, token_pair: TokenPair, recipient: ChecksumAddress) -> HexBytes:
        in_token, out_token = token_pair
        if (in_token, out_token) == self._tokens:
            args = [0, out_amount, recipient, b'']
        elif (out_token, in_token) == self._tokens:
            args = [out_amount, 0, recipient, b'']
        else:
            raise Exception("malformed token tuple")
        data = encode_abi(['uint256', 'uint256', 'address', 'bytes'], args)

        swap_data = self._swap_sig + data

        return swap_data

    def _get_weth_in_amount_from_price_change(self, price_change: float):
        """ Solving for weth_in_amount in marginal_price(-weth_in_amount) - marginal_price(0) == -price_change * marginal_price(0)
        """
        fee = self._fee
        weth_reserve = self.get_reserve(WETH, ganache=True)
        x = mp.power(mp.sqrt(1 - mp.mpf(price_change)), -1)
        weth_in_amount = int(mp.fdiv(weth_reserve * (x - 1), fee))
        assert weth_in_amount > 0
        return weth_in_amount

    def set_imbalance(self, token_pair: TokenPair, price_change: float, verbose: bool=False):
        """ Create an arbitragable imbalance in this pool on ganache fork.
        Given a token pair (WETH, ChecksumAddress), sell an amount of weth into the pool such that the spot price decreases by price_change percent.
        """
        assert price_change > 0
        assert token_pair[0] == WETH
        in_amount = self._get_weth_in_amount_from_price_change(price_change)
        out_amount = self.get_out_amount(in_amount, token_pair, ganache=True)
        self.test_swap(in_amount, out_amount, token_pair, verbose)

    def test_swap(self, in_amount: int, out_amount: int, token_pair: TokenPair, verbose: bool=False):
        unipair = interface.IExchange(self.address)
        in_token, out_token = token_pair
        if in_token == WETH:
            interface.IWETH9(WETH).deposit(from_faucet(in_amount))
        if verbose:
            in_reserve, out_reserve = self.get_reserves(token_pair, ganache=True)
            print(f"{type(self).__name__}: {self.address}")
            print(f"{TICKERS[in_token]}/{TICKERS[out_token]} reserves: {in_reserve}/{out_reserve} = {round(in_reserve/out_reserve, 4)}")
            print(f"Faucet in token balance: {interface.IERC20(in_token).balanceOf(__faucet__)}")
            print(f"In Amount -> Out Amount: {in_amount} -> {out_amount}")
        interface.IERC20(in_token).transfer(unipair, in_amount, from_faucet(0))
        recipient = checksum(__faucet__.address)
        if (in_token, out_token) == self._tokens:
            unipair.swap(0, out_amount, recipient, b'', from_faucet(0))
        elif (out_token, in_token) == self._tokens:
            unipair.swap(out_amount, 0, recipient, b'', from_faucet(0))
        else:
            raise Exception("malformed token tuple")

    def get_param_calls(self) -> RequestParams:
        out_types = ['uint', 'uint', 'uint']
        return [self.address, self._get_reserves_sig, out_types, None]

    def set_params(self, reserve0: int, reserve1: int):
        token0, token1 = self._tokens
        self._reserves.update({token0: reserve0, token1: reserve1})

    def fee(self) -> mp.mpf:
        return self._fee

    def get_reserves(self, token_pair: TokenPair, ganache: bool=False) -> List[int]:
        if ganache:
            call = self.get_param_calls()[:-1] + [ganache]
            reserves0, reserves1, _ = geth_client.request(*call)
            in_token, out_token = token_pair
            if (in_token, out_token) == self._tokens:
                return (reserves0, reserves1)
            elif (out_token, in_token) == self._tokens:
                return (reserves1, reserves0)
            else:
                raise Exception("malformed token tuple")
        else:
            return tuple([self._reserves[address] for address in token_pair])

    def get_reserve(self, token_address: ChecksumAddress, ganache: bool=False) -> int:
        if ganache:
            call = self.get_param_calls()[:-1] + [ganache]
            reserves0, reserves1, _ = geth_client.request(*call)
            if token_address == self._tokens[0]:
                return reserves0
            elif token_address == self._tokens[1]:
                return reserves1
            else:
                raise Exception("token not in pair contract")
        else:
            return self._reserves[token_address]

    def get_out_amount(self, in_amount: int, token_pair: TokenPair, ganache: bool=False) -> int:
        if in_amount <= 0:
            return 0
        in_reserve, out_reserve = self.get_reserves(token_pair, ganache)
        fee_num, fee_den = 997, 1000
        in_amount_with_fee = fee_num * in_amount
        numerator = out_reserve * in_amount_with_fee
        denominator = fee_den * in_reserve + in_amount_with_fee
        out_amount = numerator // denominator
        return out_amount

    def get_in_amount(self, out_amount: int, token_pair: TokenPair):
        if out_amount <= 0:
            return 0
        in_reserve, out_reserve = self.get_reserves(token_pair)
        fee_num, fee_den = 997, 1000
        numerator = in_reserve * out_amount * fee_den
        denominator = (out_reserve - out_amount) * fee_num
        return 1 + numerator // denominator

    def marginal_price(self, in_amount: int, token_pair: TokenPair) -> mp.mpf:
        """ Returns mp float derivative of get_out_amount evaluated at an in_amount.
        """
        in_reserve, out_reserve = self.get_reserves(token_pair)
        num = self._fee * in_reserve * out_reserve
        den = mp.power(in_reserve - self._fee * in_amount, 2)
        return mp.fdiv(num, den)


class SushiswapPair(UniswapV2Pair):
    pass


def exchangeable(pool_address: ChecksumAddress, token_pair: TokenPair) -> bool:
    error = curve.CURVE_ERRORS[pool_address][token_pair]
    return error == 0


class CurvePool(Pool):

    _registry = curve.CURVE_REGISTRY.functions
    _swap_underlying_sig = sig('exchange_underlying(int128,int128,uint256,uint256)')
    _swap_sig = sig('exchange(int128,int128,uint256,uint256)')
    _balances_sig = sig('balances(uint256)').hex()

    def __init__(self, pool_address: ChecksumAddress, coins: List[ChecksumAddress], underlying_coins: List[ChecksumAddress]):
        super().__init__(pool_address)
        self._is_underlying = dict()
        self._ij = dict()
        self._coins = coins
        self._underlying_coins = underlying_coins
        self._update_indices_and_bools(set(coins + underlying_coins))

    def set_params(self, block: BlockNumber):
        self._pool = curve.CURVE_POOLS[self.address](block)

    def _convert_to_eth_pair(self, token_pair: TokenPair) -> TokenPair:
        token_pair = tuple([ETH if token == WETH else token for token in token_pair])
        return token_pair

    def _update_indices_and_bools(self, token_set: Set[ChecksumAddress]):
        for token_pair in permutations(token_set, 2):
            if exchangeable(self.address, token_pair):
                token_pair = self._convert_to_eth_pair(token_pair)
                i, j, is_underlying = self._registry.get_coin_indices(self.address, *token_pair).call()
                self._is_underlying.update({token_pair: is_underlying})
                self._ij.update({token_pair: (i, j)})

    def get_swap_data(self, in_amount: int, out_amount: int, token_pair: TokenPair) -> HexBytes:
        token_pair = self._convert_to_eth_pair(token_pair)
        is_underlying = self._is_underlying[token_pair]
        i, j = self._ij[token_pair]
        args = [i, j, in_amount, out_amount]
        if is_underlying:
            swap_sig = self._swap_underlying_sig
        else:
            swap_sig = self._swap_sig
        swap_data = swap_sig + encode_abi(['int128', 'int128', 'uint256', 'uint256'], args)

        return swap_data

    def get_reserves(self, token_pair: TokenPair) -> List[int]:
        balances = self._pool.balances
        token_pair = self._convert_to_eth_pair(token_pair)
        indices = [balances.index(address) for address in token_pair]
        if self._is_underlying[token_pair]:
            indices = [i - self._pool.MAX_COIN for i in indices]

        return [balances[i] for i in indices]

    def set_imbalance(self, in_amount: int, token_pair: TokenPair, reserves: List[int]):
        self.test_swap(in_amount, 0, token_pair)

    def test_swap(self, in_amount: int, out_amount: int, token_pair: TokenPair, verbose: bool=False):
        curve_exchange = self.prep_swap(in_amount, out_amount, token_pair)
        token_pair = self._convert_to_eth_pair(token_pair)
        is_underlying = self._is_underlying[token_pair]
        i, j = self._ij[token_pair]
        # WETH is aliased over ETH in aETH pool
        in_token, out_token = token_pair
        if in_token == WETH:
            value = in_amount
            interface.IWETH9(WETH).withdraw(value, from_faucet(0))
        else:
            value = 0

        if is_underlying:
            curve_exchange.exchange_underlying(i, j, in_amount, out_amount, from_faucet(value))
        else:
            curve_exchange.exchange(i, j, in_amount, out_amount, from_faucet(value))

        if out_token == WETH:
            interface.IWETH9(WETH).deposit(from_faucet(value))

    def get_out_amount(self, in_amount: int, token_pair: TokenPair) -> int:
        token_pair = self._convert_to_eth_pair(token_pair)
        is_underlying = self._is_underlying[token_pair]
        i, j = self._ij[token_pair]
        if is_underlying:
            exchange = self._pool.exchange_underlying
        else:
            exchange = self._pool.exchange
        out_amount = exchange(i, j, in_amount)

        return out_amount


class BalancerPool(Pool):

    _get_balance_sig = sig('getBalance(address)').hex()           # '0xf8b2cb4f'
    _get_weight_sig = sig('getDenormalizedWeight(address)').hex() # '0x948d8ce6'
    _get_swapfee_sig = sig('getSwapFee()').hex()                  # '0xd4cadf68'
    _swap_sig = sig("swapExactAmountIn(address,uint256,address,uint256,uint256)")

    def __init__(self, pool_address: ChecksumAddress, tokens: List[ChecksumAddress]):
        super().__init__(pool_address)
        self.tokens = tokens
        self.num_tokens = len(tokens)
        self._swap_fee = geth_client.request(pool_address, self._get_swapfee_sig, ['uint'])
        self._pi_fee = mp.fdiv(mp.mpf(self._swap_fee), 1e18)
        self._balances = list()
        self._weights = list()

    def get_param_calls(self, token_pair: TokenPair) -> List[RequestParams]:
        e_in_token, e_out_token = [encode_address(a) for a in token_pair]
        out_type = ['uint']
        in_balance_call = [self.address, f"{self._get_balance_sig}{e_in_token}", out_type, -1]
        out_balance_call = [self.address, f"{self._get_balance_sig}{e_out_token}", out_type, -1]
        in_weight_call = [self.address, f"{self._get_weight_sig}{e_in_token}", out_type, -1]
        out_weight_call = [self.address, f"{self._get_weight_sig}{e_out_token}", out_type, -1]
        return [in_balance_call, out_balance_call, in_weight_call, out_weight_call]

    def set_params(self, token_pair: TokenPair, params: List[int]):
        self._params.update({token_pair: params})

    def balance(self, token: str):
        out_type = ['uint']
        data = f"{self._get_balance_sig}{encode_address(token)}"
        return geth_client.request(self.address, data, out_type)

    def get_swap_data(self, in_amount: int, out_amount: int, token_pair: TokenPair) -> HexBytes:
        max_price = SOLINF        # TODO: use marginal_price
        in_token, out_token = token_pair
        args = [in_token, in_amount, out_token, out_amount, max_price]
        swap_data = self._swap_sig + encode_abi(['address', 'uint256', 'address', 'uint256', 'uint256'], args)

        return swap_data

    def get_reserve(self, token_address: ChecksumAddress) -> int:
        for token_pair, params in self._params.items():
            if token_address == token_pair[0]:
                return params[0]
        raise Exception(f"{token_address} not in {type(self).__name__} @ {self.address}")

    def get_reserves(self, token_pair: TokenPair) -> List[int]:
        in_reserve, out_reserve, _, _ = self._params[token_pair]
        return [in_reserve, out_reserve]

    def set_imbalance(self, in_amount: int, token_pair: TokenPair, reserves: List[int]):
        self.test_swap(in_amount, 0, token_pair)

    def test_swap(self, in_amount: int, out_amount: int, token_pair: TokenPair, verbose: bool=False):
        pool = self.prep_swap(in_amount, out_amount, token_pair)
        in_token, out_token = token_pair
        max_price = SOLINF
        if verbose:
            in_reserve, out_reserve = self.get_reserves(token_pair)
            print(f"{type(self).__name__}: {self.address}")
            print(f"{TICKERS[in_token]}/{TICKERS[out_token]} reserves: {in_reserve}/{out_reserve} = {round(in_reserve/out_reserve, 4)}")
            print(f"Faucet in token balance: {interface.IERC20(in_token).balanceOf(__faucet__)}")
            print(f"In Amount -> Out Amount: {in_amount} -> {out_amount}")
        pool.swapExactAmountIn(in_token, in_amount, out_token, out_amount, max_price, from_faucet(0))

    def get_in_amount(self, out_amount: int, token_pair: TokenPair) -> int:
        in_amount = __balancer_swap__.swap_exact_amount_out(out_amount, self._params[token_pair], self._swap_fee)
        return in_amount

    def get_out_amount(self, in_amount: int, token_pair: TokenPair) -> int:
        out_amount = __balancer_swap__.swap_exact_amount_in(in_amount, self._params[token_pair], self._swap_fee)
        return out_amount

    def marginal_price(self, in_amount: int, token_pair: TokenPair) -> mp.mpf:
        bI, bO, wI, wO = self._params[token_pair]
        wp = mp.fdiv(mp.mpf(wI), wO)
        aI = in_amount
        fee = self._pi_fee
        return (1 - fee) * bO * mp.fdiv(mp.power(bI, wp), mp.power(bI - (1 - fee) * aI, wp - 1))


class SnowswapPool(Pool):

    _swap_sig = sig('exchange(int128,int128,uint256,uint256)')
    _swap_underlying_sig = sig('exchange_underlying(int128,int128,uint256,uint256)')

    def __init__(self, pool_address: ChecksumAddress, coins: List[ChecksumAddress], underlying_coins: List[ChecksumAddress]):
        super().__init__(pool_address)
        self._coins = coins
        self._underlying_coins = underlying_coins

    def set_params(self, block: BlockNumber):
        self._pool = snowswap.SNOW_POOLS[self.address](block)

    def get_swap_data(self, in_amount: int, out_amount: int, token_pair: TokenPair) -> HexBytes:
        in_token, out_token = token_pair
        is_underlying = in_token in self._underlying_coins and out_token in self._underlying_coins
        if is_underlying:
            i, j = [self._underlying_coins.index(a) for a in token_pair]
            swap_sig = self._swap_underlying_sig
        else:
            i, j = [self._coins.index(a) for a in token_pair]
            swap_sig = self._swap_sig

        args = [i, j, in_amount, out_amount]
        swap_data = swap_sig + encode_abi(['int128', 'int128', 'uint256', 'uint256'], args)

        return swap_data

    def get_reserves(self, token_pair: TokenPair) -> List[int]:
        balances = self._pool.balances
        indices = [balances.index(address) for address in token_pair]
        in_token, out_token = token_pair
        if in_token in self._underlying_coins and out_token in self._underlying_coins:
            indices = [i - self._pool.MAX_COIN for i in indices]

        return [balances[i] for i in indices]

    def set_imbalance(self, in_amount: int, token_pair: TokenPair, reserves: List[int]):
        self.test_swap(in_amount, 0, token_pair)

    def test_swap(self, in_amount: int, out_amount: int, token_pair: TokenPair, verbose: bool=False):
        pool = self.prep_swap(in_amount, out_amount, token_pair)
        in_token, out_token = token_pair
        is_underlying = in_token in self._underlying_coins and out_token in self._underlying_coins
        if is_underlying:
            i, j = [self._underlying_coins.index(a) for a in token_pair]
            pool.exchange_underlying(i, j, in_amount, out_amount, from_faucet(0))
        else:
            i, j = [self._coins.index(a) for a in token_pair]
            pool.exchange(i, j, in_amount, out_amount, from_faucet(0))

    def get_out_amount(self, in_amount: int, token_pair: TokenPair) -> int:
        in_token, out_token = token_pair
        is_underlying = in_token in self._underlying_coins and \
            out_token in self._underlying_coins
        if is_underlying:
            i, j = [self._underlying_coins.index(a) for a in token_pair]
        else:
            i, j = [self._coins.index(a) for a in token_pair]
            out_func = self._pool.exchange
        error = snowswap.SNOWSWAP_ERRORS[self.address][token_pair]
        out_amount = out_func(i, j, in_amount)
        if error is None or False:
            return 0
        elif error <= 0:          # TODO: if get_dy underestimates, why does adding error cause revert?
            return out_amount
        else:
            rounded_error = round(math.log(error, 10))
            out_amount = int((1 - 10**rounded_error) * out_amount)

        return out_amount


class MooniswapPool(Pool):

    _fee_den = 10**18
    _add_sig = sig("getBalanceForAddition(address)").hex()
    _min_sig = sig("getBalanceForRemoval(address)").hex()
    _swap_sig = sig("swap(address,address,uint256,uint256,address)")

    def __init__(self, pool_address: ChecksumAddress, tokens: List[ChecksumAddress], fee: int):
        super().__init__(pool_address)
        self._tokens = tokens
        self._referral = ZERO_ADDRESS
        self._fee = fee

    def get_param_calls(self) -> List[RequestParams]:
        out_type = ['uint256']
        token0, token1 = [encode_address(t) for t in self._tokens]
        address = self.address
        return [[address, f"{self._add_sig}{token0}", out_type, -1],
                [address, f"{self._min_sig}{token1}", out_type, -1],
                [address, f"{self._add_sig}{token1}", out_type, -1],
                [address, f"{self._min_sig}{token0}", out_type, -1]]

    def set_params(self, add_reserve0: int, min_reserve1: int, add_reserve1: int, min_reserve0: int):
        token0, token1 = self._tokens
        tr = {(token0, token1): (add_reserve0, min_reserve1),
              (token1, token0): (add_reserve1, min_reserve0)}
        self._params.update(tr)

    def get_swap_data(self, in_amount: int, out_amount: int, token_pair: TokenPair):
        in_token, out_token = token_pair
        args = [in_token, out_token, in_amount, out_amount, self._referral]
        swap_data = self._swap_sig + encode_abi(['address', 'address', 'uint256', 'uint256', 'address'], args)
        return swap_data

    def get_reserves(self, token_pair: TokenPair) -> List[int]:
        return self._params[token_pair]

    def set_imbalance(self, in_amount: int, token_pair: TokenPair, reserves: List[int]):
        self.test_swap(in_amount, 0, token_pair)

    def test_swap(self, in_amount: int, out_amount: int, token_pair: TokenPair, verbose: bool=False):
        exchange = self.prep_swap(in_amount, out_amount, token_pair)
        in_token, out_token = token_pair
        exchange.swap['address,address,uint,uint,address'](in_token, out_token, in_amount, out_amount, self._referral, from_faucet(0))

    def get_out_amount(self, in_amount: int, token_pair: TokenPair) -> int:
        if in_amount <= 0:
            return 0
        in_reserve, out_reserve = self._params[token_pair]
        tax = (in_amount * self._fee) // self._fee_den
        if tax == 0:
            return 0
        taxed_amount = in_amount - tax
        num = out_reserve * taxed_amount
        den = in_reserve + taxed_amount
        out_amount = num // den
        return out_amount

    def marginal_price(self, in_amount: int, token_pair: TokenPair) -> mp.mpf:
        # TODO: reserves change depending on direction of trade
        fee = mp.mpf(self._fee) / self._fee_den
        in_reserve, out_reserve = self._params[token_pair]
        num = fee * in_reserve * out_reserve
        den = mp.power(in_reserve - fee * in_amount, 2)
        return mp.fdiv(num, den)


class BancorPool(Pool):

    def __init__(self, bancor_network: ChecksumAddress, path: List[ChecksumAddress], owner_address: ChecksumAddress):
        super().__init__(bancor_network)
        self._path = path
        self._owner_address = owner_address

    def get_param_calls(self, token_pair: TokenPair) -> RequestParams:
        return [self._owner_address,]

    def set_params(self):
        pass

    def get_swap_data(self, in_amount: int, token_pair: TokenPair) -> HexBytes:
        pass

    def test_swap(self, in_amount: int, out_amount: int, token_pair: TokenPair, recipient: ChecksumAddress):
        network = self.prep_swap(in_amount, out_amount, token_pair)
        network.convertByPath(self._path, in_amount, out_amount, recipient, from_faucet(0))

    def get_out_amount(self, in_amount: int, token_pair: TokenPair) -> int:
        return __bancor_converter__.convert(in_amount, self._params[token_pair])


def has_valid_sig(order: Dict[str, Dict[str, Union[str, int]]]) -> bool:
    signature = order['order']['signature']
    sig_type = signature['signatureType']
    if not (sig_type == 2 or sig_type == 3):
        return False
    order_hash = order['metaData']['orderHash']
    maker_address = checksum(order['order']['maker'])
    formatted_sig = HexBytes(signature['r']) + HexBytes(signature['s']) + HexBytes(signature['v'])
    if sig_type == 3:
        order_hash = Web3.keccak(geth_client.ETH_SIGN_HASH_PREFIX + HexBytes(order_hash))
    recovered = geth_client._http_geth_client.eth.account.recoverHash(order_hash, signature=formatted_sig)
    return maker_address == recovered


def before_expiry(order: Dict[str, Dict[str, Union[str, int]]]) -> bool:
    return tminus(geth_client.TIME_UNTIL_NEXT_BLOCK) < order['order']['expiry']


def is_fillable(order: Dict[str, Dict[str, Union[str, int]]]) -> bool:
    return order['metaData']['remainingFillableAmount_takerToken'] > 0


class HidingBookMarkets(Pool):

    _api = 'https://hidingbook.keeperdao.com/api/v1/'
    _swap_sig = sig('fillOrKillRfqOrder(tuple,tuple,uint128)')
    _order_struct_keys = ['makerToken', 'takerToken', 'makerAmount', 'takerAmount', 'maker', 'taker', 'txOrigin', 'pool', 'expiry', 'salt']
    _order_struct_types = ['address', 'address', 'uint128', 'uint128', 'address', 'address', 'address', 'bytes32', 'uint64', 'uint256']
    _sig_struct_keys = ['signatureType', 'v', 'r', 's']
    _sig_struct_types = ['uint8', 'uint8', 'bytes32', 'bytes32']

    def __init__(self, owner_address: ChecksumAddress, bot_address: ChecksumAddress, init_pairs: Set):
        super().__init__("HidingBookMarkets")
        self._orderbooks = dict()
        self._owner_address = owner_address
        self._init_pairs = init_pairs
        self._exchange = ZXV4

    def _order_price(self, order: Dict[str, Dict[str, Union[str, int]]], maker_over_taker: bool=False) -> float:
        order_no_mdata = order['order']
        if maker_over_taker:
            price = mp.mpf(order_no_mdata['makerAmount']) / order_no_mdata['takerAmount']
        else:
            # lowest taker/maker price gives the most maker per taker
            price = mp.mpf(order_no_mdata['takerAmount']) / order_no_mdata['makerAmount']

        return price

    def set_params(self):
        orders_json = geth_client.SESSION.get(f"{self._api}orders", params={'open': 'True'}).json()
        orders = orders_json['orders']
        orders = [i for i in orders
                  if is_fillable(i)
                  and before_expiry(i)
                  and has_valid_sig(i)
                  and i['order']['txOrigin'] == self._owner_address
                  and (i['order']['taker'] == ZERO_ADDRESS or i['order']['taker'] == KEEPER_ADDRESS)] # TODO: get whitelisted
        pairs = [(i['order']['takerToken'], i['order']['makerToken']) for i in orders]
        pairs = [tuple([checksum(a) for a in pair]) for pair in pairs]
        orderbooks = dict()
        for pair, order in zip(pairs, orders):
            if pair not in self._init_pairs:
                continue
            if pair in self._orderbooks:
                orderbooks[pair].append(order)
            else:
                orderbooks.update({pair: [order]})

        sorted_orderbooks = orderbooks
        for _pair, _orders in orderbooks.items():
            sorted_orderbooks[_pair] = sorted(_orders, key=self._order_price)

        self._orderbooks = sorted_orderbooks

    def _parse_fill_order_args(self, order: Dict[str, Dict[str, Union[str, int]]]) -> Tuple[List[Union[str, int]], HexStr]:
        order_no_mdata = order['order']
        order_sig = order_no_mdata['signature']
        rfq_order = [order_no_mdata[k] for k in self._order_struct_keys]
        sig = [order_sig[k] for k in self._sig_struct_keys]
        return rfq_order, sig

    def get_swap_data(self, bot_address: ChecksumAddress, in_amount: int, out_amount: int, token_pair: TokenPair) -> HexBytes:
        _out_amount, order = self.get_out_amount(in_amount, token_pair, get_order=True)
        assert out_amount == _out_amount
        rfq_order, sig = self._parse_fill_order_args(order)
        swap_data = self._swap_sig + encode_abi([self._order_struct_types, self._sig_struct_types, 'uint128'], [rfq_order, sig, in_amount])

        return swap_data

    def test_swap(self, in_amount: int, out_amount: int, token_pair: TokenPair, verbose: bool=False):
        zxv4 = self.prep_swap(in_amount, out_amount, token_pair)
        out_amount, order = self.get_out_amount(in_amount, token_pair, get_order=True)
        rfq_order, sig = self._parse_fill_order_args(order)
        zxv4.fillOrKillRfqOrder(rfq_order, sig, in_amount, from_faucet(0))

    def get_out_amount(self, in_amount: int, token_pair: TokenPair, get_order: bool=False) -> int:
        # return lowest price order that can be filled with in_amount, else return 0
        orders = self._orderbooks[token_pair]
        for order in orders:
            fillable_amount = order['metaData']['remainingFillableAmount_takerToken']
            if in_amount <= fillable_amount:
                order_no_mdata = order['order']
                out_amount = in_amount * order_no_mdata['makerAmount'] // order_no_mdata['takerAmount']
                if get_order:
                    return out_amount, order
                else:
                    return out_amount
        return 0


class TokenGraphUpdater:

    def __init__(self, token_graph: Graph):
        self.update_token_graph(token_graph)

    def update_token_graph(self, graph: Graph):
        """ Adds graph edges representing pairs on this dex. Nodes represent tokens traded on each pair.
        """
        pass


class UniswapV2(TokenGraphUpdater):

    _get_pair_sig = sig('getPair(address,address)').hex()
    _get_reserves_sig = sig('getReserves()').hex()

    def __init__(self, token_graph: Graph):
        self._pair_class = getattr(sys.modules[__name__], type(self).__name__ + "Pair")
        super().__init__(token_graph)

    def update_token_graph(self, token_graph: Graph):
        trade_set = set(__trade_set__)
        token_pairs = list(combinations(trade_set, 2))
        get_pair_data = [f"{self._get_pair_sig}{encode_pair(token_pair)}" for token_pair in token_pairs]
        factory = SUSHISWAP_FACTORY if type(self) is Sushiswap else UNISWAPV2_FACTORY
        pair_requests = [[factory, data, ['address'], -1] for data in get_pair_data]
        pair_addresses = geth_client.batch_request(pair_requests)
        pair_tokens = [(checksum(address), token_pair) for address, token_pair in zip(pair_addresses, token_pairs)
                       if address != ZERO_ADDRESS]

        reserves_out_types = ['uint'] * 3
        reserve_requests = [[address, self._get_reserves_sig, reserves_out_types, None] for address, _ in pair_tokens]
        reserves = geth_client.batch_request(reserve_requests)

        i = 0
        assert len(reserves) == len(pair_tokens)
        for reserve, pair_token in zip(reserves, pair_tokens):
            pair_address, token_pair = pair_token
            token_a, token_b = token_pair
            reserve0, reserve1, _ = reserve
            token0, token1 = (token_a, token_b) if int(token_a, 16) < int(token_b, 16) else (token_b, token_a)
            check0 = reserve0 // 10 ** __decimals__[token0]
            check1 = reserve1 // 10 ** __decimals__[token1]
            if check0 == 0 or check1 == 0:
                continue

            v1 = token_graph.update_vertex(token0)
            v2 = token_graph.update_vertex(token1)
            pair_object = self._pair_class(pair_address, (token0, token1))
            token_graph.update_edge(v1, v2, pair_object)
            token_graph.update_edge(v2, v1, pair_object)

            i += 1
        print(f"{i} {type(self).__name__} pairs loaded\n", end='')


class Sushiswap(UniswapV2):
    pass


class Curve(TokenGraphUpdater):

    def _trim_zero_addresses(self, coins: List[ChecksumAddress]):
        coins = [WETH if coin == ETH else coin for coin in coins]
        if ZERO_ADDRESS in coins:
            zero_index = coins.index(ZERO_ADDRESS)
            assert set(coins[zero_index:]) == {ZERO_ADDRESS}
            coins = coins[:zero_index]
            assert set(coins).issubset(set(__trade_set__))
        return coins

    def update_token_graph(self, token_graph: Graph):
        registry = curve.CURVE_REGISTRY.functions
        pool_count = registry.pool_count().call()
        # print(f'populating token graph from {pool_count} possible pool addresses in curve registry')
        j = 0
        for i in range(pool_count):
            pool_address = registry.pool_list(i).call()
            try:
                curve.CURVE_POOL_INFO.functions.get_pool_info(pool_address).call()
            except:
                print(f"unknown! > {pool_address}")
                j += 1
                continue
            if pool_address not in curve.CURVE_POOLS:
                print(f"TODO > {pool_address}")
                j += 1
                continue
            coins = registry.get_coins(pool_address).call()
            coins = self._trim_zero_addresses(coins)
            underlying_coins = registry.get_underlying_coins(pool_address).call()
            underlying_coins = self._trim_zero_addresses(coins)
            pool_object = CurvePool(pool_address, coins, underlying_coins)
            for token_pair in permutations(set(coins + underlying_coins), 2):
                v1, v2 = [token_graph.update_vertex(token) for token in token_pair]
                if exchangeable(pool_address, token_pair):
                    token_graph.update_edge(v1, v2, pool_object)

        print(f"{pool_count - j} Curve pools loaded\r\n", end='')


class Balancer(TokenGraphUpdater):

    _get_pools_sig = sig("getBestPools(address,address)").hex()

    def update_token_graph(self, token_graph: Graph):
        pairs = list(combinations(__trade_set__, 2))
        get_pair_data = [f"{self._get_pools_sig}{encode_pair(pair)}" for pair in pairs]
        tdoi_pairs = [[BALANCER_REGISTRY, data, ['address[]'], -1] for data in get_pair_data]
        batch_addresses = geth_client.batch_request(tdoi_pairs)
        pair_addresses = [(pair, {checksum(address) for address in addresses}) for pair, addresses in zip(pairs, batch_addresses)
                          if addresses != list()]

        address_to_pairs = dict()
        for pair, addresses in pair_addresses:
            for address in addresses:
                if address in address_to_pairs.keys():
                    address_to_pairs[address].add(pair)
                else:
                    address_to_pairs.update({address: {pair}})
        # TODO: filter tokens with less than unit reserves
        i = 0
        for address, pairs in address_to_pairs.items():
            tokens = set()
            [tokens.update({t1, t2}) for t1, t2 in pairs]
            pair_object = BalancerPool(address, list(tokens))
            for pair in pairs:
                token_a, token_b = pair
                if pair_object.balance(token_a) > 0 and pair_object.balance(token_b) > 0:
                    v1 = token_graph.update_vertex(token_a)
                    v2 = token_graph.update_vertex(token_b)
                    token_graph.update_edge(v1, v2, pair_object)
                    token_graph.update_edge(v2, v1, pair_object)
            i += 1
        print(f"{i} Balancer pools loaded\n", end='')


class Snowswap(TokenGraphUpdater):

    def _add_coins_to_token_graph(self, token_graph: Graph, pool_object: SnowswapPool, coins: List[ChecksumAddress]):
        if coins != list():
            for token_a, token_b in combinations(coins, 2):
                v1 = token_graph.update_vertex(token_a)
                v2 = token_graph.update_vertex(token_b)
                token_graph.update_edge(v1, v2, pool_object)
                token_graph.update_edge(v2, v1, pool_object)

    def update_token_graph(self, token_graph: Graph):
        j = 0
        pool_count = len(list(snowswap.SNOW_POOLS.keys()))
        for pool_address, n_coins in snowswap.SNOW_NUM_COINS.items():
            pool = geth_client.get_contract(pool_address).functions
            coins = [pool.coins(i).call() for i in range(n_coins)]
            if pool_address in snowswap.SNOW_HAS_UNDERLYING:
                underlying_coins = [pool.underlying_coins(i).call() for i in range(n_coins)]
            else:
                underlying_coins = list()
            all_coins = coins + underlying_coins
            if not set(all_coins).issubset(set(__trade_set__)):
                print(f"{pool_address} tokens {all_coins} not in trade set")
                j += 1
                continue
            pool_object = SnowswapPool(pool_address, coins, underlying_coins)
            self._add_coins_to_token_graph(token_graph, pool_object, coins)
            # TODO: implement exchange_underlying in snowswap.py
            # self._add_coins_to_token_graph(token_graph, pool_object, underlying_coins)
        print(f"{pool_count - j} Snowswap pools loaded\r\n", end='')


class Mooniswap(TokenGraphUpdater):

    _get_tokens_sig = sig("getTokens()").hex()
    _add_sig = sig("getBalanceForAddition(address)").hex()
    _min_sig = sig("getBalanceForRemoval(address)").hex()
    _all_pools_sig = sig('getAllPools()').hex()
    _fee_sig = sig('fee()').hex()

    def update_token_graph(self, token_graph: Graph):
        all_pools = geth_client.request(MOONISWAP_FACTORY, self._all_pools_sig, ['address[]'])
        fee = geth_client.request(MOONISWAP_FACTORY, self._fee_sig, ['uint'])
        pool_tokens = geth_client.batch_request([[a, self._get_tokens_sig, ['address[]'], -1] for a in all_pools])
        pool_tokens = [[checksum(t) for t in pt] for pt in pool_tokens]
        pool_tokens_sans = pool_tokens
        for i, tokens in enumerate(pool_tokens):
            checksummed_tokens = [checksum(t) for t in tokens]
            # TODO: eth reserve calls revert
            if ZERO_ADDRESS in checksummed_tokens or ETH in checksummed_tokens:
                del all_pools[i]
                del pool_tokens_sans[i]
            else:
                pool_tokens_sans[i] = checksummed_tokens

        reserves_calls = list()
        for pool_address, tokens in zip(all_pools, pool_tokens_sans):
            add_calls = [[pool_address, f"{self._add_sig}{encode_address(t)}", ['uint256'], -1] for t in tokens]
            min_calls = [[pool_address, f"{self._min_sig}{encode_address(t)}", ['uint256'], -1] for t in tokens]
            reserves_calls.extend(add_calls + min_calls)
        reserves = geth_client.batch_request(reserves_calls)
        # TODO: reserves not accurately checked
        i = 0
        for pool_address, tokens in zip(all_pools, pool_tokens_sans):
            token0, token1 = tokens
            if token0 not in __trade_set__ or \
               token1 not in __trade_set__:
                continue
            pr = reserves[i*4: (i+1)*4]
            i += 1
            min_reserves0 = 10**__decimals__[token0]
            min_reserves1 = 10**__decimals__[token1]
            if pr[0] < min_reserves0 or \
               pr[2] < min_reserves0 or \
               pr[1] < min_reserves1 or \
               pr[3] < min_reserves1:
                continue
            v1 = token_graph.update_vertex(token0)
            v2 = token_graph.update_vertex(token1)
            pair_object = MooniswapPool(pool_address, tokens, fee)
            token_graph.update_edge(v1, v2, pair_object)
            token_graph.update_edge(v2, v1, pair_object)
        print(f"{i} Mooniswap pairs loaded\r\n", end='')


class Bancor(TokenGraphUpdater):

    _cp_sig = sig('conversionPath(address,address)').hex()
    _own_sig = sig('owner()').hex()
    _is_gte_v2_sig = sig('isV28OrHigher()').hex()

    def update_token_graph(self, token_graph: Graph):
        bnt = TRADE_SET['BNT']
        trade_set = set(__trade_set__)
        trade_set.remove(bnt)
        pairs = [(t, bnt) for t in trade_set]
        conversion_paths = geth_client.batch_request([[BANCOR_NETWORK, f"{self._cp_sig}{encode_pair(p)}", ['address[]'], -1] for p in pairs])
        valid_paths = [cp for cp in conversion_paths if cp != tuple()]
        valid_pairs = [p for p, cp in zip(pairs, conversion_paths) if cp != list()]
        anchors = [vp[1] for vp in valid_paths]
        converters = geth_client.batch_request([[anchor, self._own_sig, ['address'], -1] for anchor in anchors])  # owners are converters
        is_gte_v2 = list()
        for converter in converters:
            try:
                geth_client.request(converter, self._is_gte_v2_sig, ['bool'])
                is_gte_v2.append(True)
            except ValueError:
                is_gte_v2.append(False)
        vbnt = token_graph.update_vertex(bnt)
        for pair, path, converter in zip(valid_pairs, valid_paths, converters):
            token = pair[0]
            vt = token_graph.update_vertex(token)
            path_object = BancorPool(BANCOR_NETWORK, path, converter)
            token_graph.update_edge(vt, vbnt, path_object)
            token_graph.update_edge(vbnt, vt, path_object)


class HidingBook(TokenGraphUpdater):

    _api = 'https://hidingbook.keeperdao.com/api/v1/'

    def __init__(self, owner_address: ChecksumAddress, bot_address: ChecksumAddress, token_graph: Graph):
        super().__init__(token_graph)
        self._owner_address = owner_address
        self._bot_address = bot_address

    def update_token_graph(self, token_graph: Graph):
        token_json = geth_client.SESSION.get(f"{self._api}tokenList").json()
        tokens = {checksum(i["address"]) for i in token_json["result"]["tokens"]}
        missing_tokens = tokens - set(__trade_set__).intersection(tokens)
        if missing_tokens != set():
            print(f"tokens not in trade set: {missing_tokens}")

        orders_json = geth_client.SESSION.get(f"{self._api}orders", params={'open': 'True'}).json()
        orders = orders_json['orders']
        orders = [i for i in orders
                  if is_fillable(i)
                  and before_expiry(i)
                  and has_valid_sig(i)
                  and i['order']['txOrigin'] == self._owner_address
                  and (i['order']['taker'] == ZERO_ADDRESS or i['order']['taker'] == self._bot_address)] # TODO: get whitelisted
        orders_no_mdata = [i['order'] for i in orders]
        # TODO: get whitelisted
        pairs = {(order['takerToken'], order['makerToken']) for order in orders_no_mdata}
        pairs = {tuple([checksum(a) for a in pair]) for pair in pairs}
        all_markets = HidingBookMarkets(self._owner_address, pairs)
        market_count = 0
        for token_a, token_b in pairs:
            v1 = token_graph.update_vertex(token_a)
            v2 = token_graph.update_vertex(token_b)
            token_graph.update_edge(v1, v2, all_markets)
            market_count += 1
        print(f"{market_count} HidingBook markets loaded")


class UniswapV3Loans:

    _get_pool_sig = sig('getPool(address,address,uint24)').hex()
    _token0_sig = sig('token0()').hex()
    _fees = [500, 3000, 10000]

    def _mul_div(self, a: int, b: int, denominator: int) -> int:
        return (a * b) // denominator

    def _mul_div_roundup(self, a: int, b: int, denominator: int) -> int:
        result = self._mul_div(a, b, denominator)
        if ((a * b) % denominator) > 0:
            result += 1
        return result

    def fee(self, amount: int, fee: int) -> int:
        return self._mul_div_roundup(amount, fee, 10**6)

    def _balance_of(self, address: HexAddress) -> str:
        return f"{sig('balanceOf(address)').hex()}{encode_address(address)}"

    def _get_balances(self, token_to_borrow: ChecksumAddress, pool_data: List[Tuple[ChecksumAddress, TokenPair, int]]) -> List[int]:
        balance_requests = list()
        out_type = ['uint']
        for data in pool_data:
            address, _, _ = data
            balance_requests.append([token_to_borrow, self._balance_of(address), out_type, -1])

        balances = geth_client.batch_request(balance_requests)

        return balances

    def get_max_borrowable_weth_pool_data(self) -> Dict[str, Union[bool, ChecksumAddress, int]]:
        token_pairs = [(WETH, token) for token in __trade_set__]
        get_pool_data = list()
        for token_pair in token_pairs:
            get_pool_data.extend([f"{self._get_pool_sig}{encode_pair(token_pair)}{encode_single('uint24', fee).hex()}" for fee in self._fees])

        pool_address_requests = [[UNISWAPV3_FACTORY, data, ['address'], -1] for data in get_pool_data]
        pool_addresses = geth_client.batch_request(pool_address_requests)
        pairs3 = [token_pairs[i // 3] for i in range(len(get_pool_data))]
        pool_data = [(checksum(address), pair, fee) for address, pair, fee in zip(pool_addresses, pairs3, self._fees * len(token_pairs))
                     if address != ZERO_ADDRESS]
        balances = self._get_balances(WETH, pool_data)
        assert len(balances) == len(pool_data)
        weth_pool_data = dict(balance=0, fee=SOLINF)
        for balance, data in zip(balances, pool_data):
            address, token_pair, fee = data
            fee_weighted_balance_is_higher = weth_pool_data['balance'] * fee < balance * weth_pool_data['fee']
            if fee_weighted_balance_is_higher:
                assert WETH == token_pair[0]
                weth_is_token0 = int(WETH, 16) < int(token_pair[1], 16)
                weth_pool_data = dict(
                    is_token0=weth_is_token0,
                    address=address,
                    balance=balance,
                    fee=fee
                )

        return weth_pool_data


def is_unipair(pool: Pool):
    return type(pool) in {UniswapV2Pair, SushiswapPair}


class TokenGraph(Graph):

    def __init__(self, owner: Union[Account, LocalAccount], max_hops: int=3):
        super().__init__()
        self._owner = owner
        self._loans = UniswapV3Loans()
        self._ape = Ape()
        self._max_hops = max_hops                                              # maximum number of trades considered in arbitrage
        self.address_to_vertex = dict()
        self.address_to_pool = dict()
        self.vertex_properties['tokens'] = self.new_vertex_property('string')  # token addresses
        self.edge_properties['pools'] = self.new_edge_property('object')       # set of uniswap pair addresses associated with the tokens on this edge
        self.edge_properties['token_pair'] = self.new_edge_property('object')  # tuples representing direction of tokens traded on edge

    def update_vertex(self, token_address: ChecksumAddress) -> Vertex:
        if token_address not in self.vp.tokens:
            v = self.add_vertex()
            self.vp.tokens[v] = token_address
            self.address_to_vertex.update({token_address: v})
            return v
        else:
            return self.address_to_vertex[token_address]

    def update_edge(self, v1: Vertex, v2: Vertex, pool: Pool):
        e = self.edge(v1, v2)
        if not e:
            e = self.add_edge(v1, v2)
            self.ep.pools[e] = set()
        address = pool.address
        self.ep.pools[e].add(address)
        self.address_to_pool.update({address: pool})
        in_token = self.vp.tokens[v1]
        out_token = self.vp.tokens[v2]
        self.ep.token_pair[e] = (in_token, out_token)

    def _test_swaps(self, in_amount: int, swap_calls: Tuple[Pool, Tuple[int, int, Tuple[TokenPair]]]):
        with RevertTransactions():
            for pool, args in swap_calls:
                if __test_mode__:
                    pool.test_swap(*(list(args) + [True]))

    def _get_approvals(self, bot_address: ChecksumAddress, swap_calls: Tuple[Pool, Tuple[int, int, Tuple[TokenPair]]]) -> List[List[ChecksumAddress]]:
        approvals = list()
        for pool, args in swap_calls:
            if not is_unipair(pool):
                token_pair = args[-1]
                amounts = args[:-1]
                pool_address = pool.address
                approval = [pool_address]
                for token, amount in zip(token_pair, amounts):
                    # aETH pool does not need approval for ETH swaps
                    if not (type(pool) is CurvePool and token == WETH) and \
                       approval not in approvals and \
                       interface.IERC20(token).allowance(bot_address, pool_address) < amount:
                        approval += [token]
                if len(approval) > 1:
                    approvals.append(approval)

        return approvals

    def _get_ape_data(self,
                      bot_address: ChecksumAddress,
                      approvals: List[List[ChecksumAddress]],
                      swap_calls: Tuple[Pool, Tuple[int, int, Tuple[TokenPair]]]) -> List[int]:
        pools = [pool for pool, _ in swap_calls]
        pool = None
        ape_data = list()
        for i, call in enumerate(swap_calls):
            last_pool = pool
            pool, args = call
            in_amount, out_amount, token_pair = args
            in_token, out_token = token_pair
            pool_address = pool.address
            # transfer to uniswap pool if necessary
            if is_unipair(pool):
                if not is_unipair(last_pool):
                    in_token_transfer_data = sig('transfer(address,uint256)') + encode_abi(['address', 'uint'], [pool_address, in_amount])
                    ape_data.extend(self._ape.encode_ape_call(in_token, in_token_transfer_data))
                args = list(args) + [bot_address]
                if i != len(swap_calls) - 1:
                    next_pool = pools[i + 1]
                    if is_unipair(next_pool):
                        args[-1] = next_pool.address
            elif approvals != list():
                # approve non uniswap pool
                approval = approvals.pop(0)
                if pool_address == approval[0]:
                    for token in approval[0:]:
                        approval_data = sig('approve(address,uint256)') + encode_abi(['address', 'uint'], [pool_address, SOLINF])
                        ape_data.extend(self._ape.encode_ape_call(token, approval_data))

            # convert weth to eth for aETH pool
            if type(pool) is CurvePool and in_token == WETH:
                value = in_amount
                withdraw_data = sig('withdraw(uint256)') + encode_single('uint', value)
                ape_data.extend(self._ape.encode_ape_call(WETH, withdraw_data))
            else:
                value = 0
            # encode call to pool contract in apebot
            swap_data = pool.get_swap_data(*args)
            ape_data.extend(self._ape.encode_ape_call(pool_address, swap_data, eth_value=value))
            # convert eth to weth for next pool if traded on aETH pool
            if type(pool) is CurvePool and out_token == WETH:
                deposit_data = sig('deposit()')
                ape_data.extend(self._ape.encode_ape_call(WETH, deposit_data, eth_value=out_amount))

        return ape_data

    def _wrap_ape_data_in_flashloan(self,
                                    in_amount: int,
                                    bot_address: ChecksumAddress,
                                    weth_loan_pool_data: Dict[str, Union[bool, ChecksumAddress, int]],
                                    ape_data: List[int]) -> Tuple[int, List[int]]:
        flash_sig = sig('flash(address,uint256,uint256,bytes)')
        flash_callback = encode_single('uint[]', ape_data)
        is_token0 = weth_loan_pool_data['is_token0']
        args = [
            bot_address,
            in_amount if is_token0 else 0,
            in_amount if not is_token0 else 0,
            flash_callback
        ]
        flash_data = flash_sig + encode_abi(['address', 'uint', 'uint', 'bytes'], args)
        flash_pool_address = weth_loan_pool_data['address']
        wrapped_ape_data = self._ape.encode_ape_call(flash_pool_address, flash_data)

        return wrapped_ape_data

    def _get_payback_data(self,
                          payback_amount: int,
                          weth_loan_pool_data: Dict[str, Union[bool, ChecksumAddress, int]]) -> List[int]:
        flash_pool_address = weth_loan_pool_data['address']
        payback_data = sig('transfer(address,uint256)') + encode_abi(['address', 'uint'], [flash_pool_address, payback_amount])
        payback_data = self._ape.encode_ape_call(WETH, payback_data)

        return payback_data

    def _get_return_to_owner_data(self, owner_address: ChecksumAddress, profit_to_return: int) -> List[int]:
        return_to_owner_data = sig('transfer(address,uint256)') + encode_abi(['address', 'uint'], [owner_address, profit_to_return])
        return_to_owner_data = self._ape.encode_ape_call(WETH, return_to_owner_data)

        return return_to_owner_data

    def _construct_arbitrage(self,
                             in_amount: int,
                             bribe: int,
                             pools: List[Pool],
                             token_pairs: List[TokenPair],
                             bot_contract: Contract,
                             weth_loan_pool_data: Dict[str, Union[bool, ChecksumAddress, int]]) -> Union[int, Tuple[int, int, ContractFunction, TxParams]]:
        # generate data to be encoded in swap calls
        in_amounts = list()
        out_amounts = list()
        pool_addresses = list()
        next_amount = in_amount
        for _pool, _token_pair in zip(pools, token_pairs):
            pool_addresses.append(_pool.address)
            in_token, out_token = _token_pair
            in_amounts.append(next_amount)
            next_amount = _pool.get_out_amount(next_amount, _token_pair)
            out_amounts.append(next_amount)

        swap_args = list(zip(in_amounts, out_amounts, token_pairs))
        swap_calls = list(zip(pools, swap_args))
        self._test_swaps(in_amount, swap_calls)

        bot_address = bot_contract.address
        approvals = self._get_approvals(bot_address, swap_calls)

        ape_data = self._get_ape_data(bot_address, approvals, swap_calls)
        loan_fee = self._loans.fee(in_amount, weth_loan_pool_data['fee'])
        payback_amount = in_amount + loan_fee
        payback_data = self._get_payback_data(payback_amount, weth_loan_pool_data)
        owner_address = checksum(self._owner.address)
        profit = out_amounts[-1] - in_amount
        profit_to_return = profit - bribe - loan_fee - 1  # minus one to leave a balance of 1 in contract
        return_to_owner_data = self._get_return_to_owner_data(owner_address, profit_to_return)
        null_action_flags = 0x0
        ape_data = [null_action_flags] + ape_data + payback_data + return_to_owner_data

        flash_loan_data = self._wrap_ape_data_in_flashloan(in_amount, bot_address, weth_loan_pool_data, ape_data)
        action_flags = self._ape.get_action_flags(bribe)
        data = [action_flags] + flash_loan_data

        bot_function = bot_contract.functions.eldddhzr(data)
        bot_tx_params = {'from': owner_address, 'gasPrice': 0}
        estimated_gas_cost = bot_function.estimateGas(bot_tx_params)
        bot_tx_params.update({'gas': len(pools) * estimated_gas_cost})
        if __test_mode__:
            with RevertTransactions():
                coinbase_before = geth_client.balance(ZERO_ADDRESS, ganache=True)
                weth = interface.IWETH9(WETH)
                balance_before = weth.balanceOf(owner_address)

                tx = interface.Bot(bot_address).eldddhzr(data, bot_tx_params)

                coinbase_after = geth_client.balance(ZERO_ADDRESS, ganache=True)
                block_reward = 2 * 10**18
                coinbase_bribe_recieved = coinbase_after - coinbase_before - block_reward
                balance_after = weth.balanceOf(owner_address)
                actual_profit = balance_after - balance_before
                predicted_profit = profit - bribe
                if coinbase_bribe_recieved != bribe:
                    print(f"coinbase bribe recieved {coinbase_bribe_recieved} does not match {bribe} ({coinbase_bribe_recieved - bribe} diff)")

                if actual_profit != predicted_profit:
                    print(f"predicted profit {predicted_profit} does not match {actual_profit} ({predicted_profit - actual_profit} diff)")

                exact_gas_cost = tx.gas_used
                raise
            return exact_gas_cost
        else:
            implied_gas_price = int(bribe / estimated_gas_cost)
            return estimated_gas_cost, implied_gas_price, bot_function, bot_tx_params

    def _cache_pool_params(self, block: BlockNumber, ganache: bool=False):
        # set uniswap pool parameters
        univ2_pairs = [pool for pool in self.address_to_pool.values() if is_unipair(pool)]
        reserve_requests = [unipair.get_param_calls() for unipair in univ2_pairs]
        reserves = geth_client.batch_request(reserve_requests, ganache)
        assert len(univ2_pairs) == len(reserves)
        for reserve, unipair in zip(reserves, univ2_pairs):
            unipair.set_params(reserve[0], reserve[1])

        # univ3_pairs = [pool for pool in self.address_to_pool.values() if type(pool) is UniswapV3Pair]
        # to_data_out_v3params = list()
        # for v3_pair in univ3_pairs:
        #     to_data_out_v3params.extend(v3_pair.get_param_calls())
        # params = geth_client.batch_request(to_data_out_v3params, ganache)
        # offset = 0
        # for v3_pair in univ3_pairs:
        #     slot0, liquidity, fee_growth0, fee_growth1 = params[4*offset:4*(offset+1)]
        #     offset += 1
        #     v3_pair.set_params(slot0, liquidity, fee_growth0, fee_growth1)

        # set mooniswap pool parameters
        moon_pools = [pool for pool in self.address_to_pool.values() if type(pool) is MooniswapPool]
        m_to_data_out_reserves = list()
        for m_pool in moon_pools:
            m_to_data_out_reserves.extend(m_pool.get_param_calls())
        m_reserves = geth_client.batch_request(m_to_data_out_reserves, ganache)
        m_call_len = 4
        for m_offset, moon_pool in enumerate(moon_pools):
            moon_pool.set_params(*m_reserves[m_offset * m_call_len: (m_offset + 1) * m_call_len])

        # set balancer pool parameters
        pair_pools = list()
        pairs = list()
        for edge in self.edges():
            edge_pools = [self.address_to_pool[address] for address in self.ep.pools[edge]]
            edge_bpools = [pool for pool in edge_pools if type(pool) is BalancerPool]
            if edge_bpools == list():
                continue
            pairs.append(self.ep.token_pair[edge])
            pair_pools.append(edge_bpools)

        to_data_out_bp = list()
        for pair, pools in zip(pairs, pair_pools):
            for pool in pools:
                to_data_out_bp.extend(pool.get_param_calls(pair))

        bparams = geth_client.batch_request(to_data_out_bp, ganache)
        offset = 0
        call_len = 4
        for pair, pools in zip(pairs, pair_pools):
            for i, pool in enumerate(pools):
                pool.set_params(pair, bparams[offset + call_len*i:offset + call_len*(i+1)])  # SIDE EFFECT on pool
            offset += call_len*len(pools)

        # set curve pool parameters
        curve_pools = [pool for pool in self.address_to_pool.values() if type(pool) is CurvePool]
        [pool.set_params(block) for pool in curve_pools]
        snoswap_pools = [pool for pool in self.address_to_pool.values() if type(pool) is SnowswapPool]
        [pool.set_params(block) for pool in snoswap_pools]

        # update hidingbook
        # self.address_to_pool['HidingBookMarkets'].set_params() # TODO: get whitelisted
        # update 0xv3 orderbooks
        # self.address_to_pool['ZxMarkets'].set_params()

    def _circuits(self) -> OrderedDict:
        """ Find all circuits containing weth.
        """
        circuits = OrderedDict()
        weth_v = self.address_to_vertex[WETH]
        for vertex_path in all_paths(self, weth_v, weth_v, cutoff=self._max_hops):
            swap_vertices = tuple([(v1, v2) for v1, v2 in zip(vertex_path, vertex_path[1:])])
            swap_edges = [self.edge(*swap) for swap in swap_vertices]
            circuits.update({swap_vertices: swap_edges})

        return circuits

    def _prune_circuits(self, circuits: OrderedDict) -> OrderedDict:
        pruned_circuits = OrderedDict(circuits)
        for swap_vertices, swap_edges in circuits.items():
            pool_sets = [self.ep.pools[e] for e in swap_edges]
            # prune circuits that contain a single pool
            if reduce(lambda s1, s2: s1 == s2, pool_sets) and \
               reduce(lambda l1, l2: l1 and l2, [len(us) == 1 for us in pool_sets]):
                del pruned_circuits[swap_vertices]
                continue

        return pruned_circuits

    def _locally_optimize_profit(self, loan_max: int, circuit: List[Edge]) -> Tuple[int, int, List[Pool]]:
        pool_sets = [self.ep.pools[edge] for edge in circuit]
        token_pairs = [self.ep.token_pair[edge] for edge in circuit]
        max_optimal_in_amount = 0
        max_profit = 0
        max_pools = list()
        for pool_addresses in product(*pool_sets):
            pool_repeat = False
            for pool_address, next_pool_address in zip(pool_addresses, pool_addresses[1:]):
                pool_repeat = pool_address == next_pool_address
                if pool_repeat:
                    break
            if pool_repeat:
                continue

            pools = [self.address_to_pool[address] for address in pool_addresses]

            def scaled_profit(in_amount: float) -> float:
                next_in_amount = int(in_amount * WETH_SCALE)
                for pool, token_pair in zip(pools, token_pairs):
                    next_in_amount = pool.get_out_amount(next_in_amount, token_pair)

                return next_in_amount / WETH_SCALE - in_amount

            macheps = numpy.finfo(float).eps
            bounds = Bounds(macheps, loan_max / WETH_SCALE)
            x0 = (macheps,)
            result = minimize(lambda x: -scaled_profit(x), x0, method='L-BFGS-B', bounds=bounds, options={'ftol': macheps})
            optimal_in_amount = int(result.x * WETH_SCALE)

            def profit(in_amount: int) -> int:
                next_in_amount = in_amount
                for pool, token_pair in zip(pools, token_pairs):
                    next_in_amount = pool.get_out_amount(next_in_amount, token_pair)

                return next_in_amount - in_amount

            profit = profit(optimal_in_amount)
            if profit > max_profit:
                max_optimal_in_amount = optimal_in_amount
                max_profit = profit
                max_pools = pools

        return max_optimal_in_amount, max_profit, max_pools

    def _get_arb_to_buy_uniswapv2x2(self, buy_unipair: UniswapV2Pair, sell_unipair: UniswapV2Pair, impact_pair: TokenPair) -> int:
        arb_reserve0, weth_reserve0 = buy_unipair.get_reserves(impact_pair)
        fee0 = buy_unipair.fee()
        arb_reserve1, weth_reserve1 = sell_unipair.get_reserves(impact_pair)
        fee1 = sell_unipair.fee()
        num = fee0 * weth_reserve0 * arb_reserve0
        den = fee1 * weth_reserve1 * arb_reserve1
        rat = mp.sqrt(mp.fdiv(num, den))
        quot = mp.fdiv(arb_reserve0 - arb_reserve1 * rat, fee0 + fee1 * rat)
        arb_to_buy = int(quot)
        if arb_to_buy < 0:
            print(f"{impact_pair} reserves {arb_reserve0} {weth_reserve0}")
        return arb_to_buy

    def _enforce_no_arbitrage(self, loan_max: int, edge: Edge) -> Union[Tuple[int, int, List[Pool]], List[None]]:
        pools = [self.address_to_pool[address] for address in self.ep.pools[edge]]
        no_arb_pools = [pool for pool in pools if is_unipair(pool) or type(pool) is BalancerPool]
        weth, arb_token = self.ep.token_pair[edge]
        arbs = [[0, 0, [None, None]]]
        buy_pair = (weth, arb_token)
        sell_pair = (arb_token, weth)
        impact_pair = sell_pair
        for buy_pool, sell_pool in permutations(no_arb_pools, 2):
            if buy_pool.address == sell_pool.address:
                continue

            def price_after_buy(x):
                return buy_pool.marginal_price(x, impact_pair)

            def price_after_sell(x):
                return sell_pool.marginal_price(-x, impact_pair)

            spot_price_on_buy_pool = price_after_buy(0)
            spot_price_on_sell_pool = price_after_sell(0)
            max_arb = min(buy_pool.get_reserve(arb_token), sell_pool.get_reserve(arb_token))
            # TODO: add mooniswap
            if spot_price_on_buy_pool < spot_price_on_sell_pool  and \
               price_after_buy(max_arb) > price_after_sell(max_arb):
                if is_unipair(buy_pool) and is_unipair(sell_pool):
                    arb_to_buy = self._get_arb_to_buy_uniswapv2x2(buy_pool, sell_pool, impact_pair)
                else:
                    try:
                        arb_to_buy = int(mp.findroot(lambda x: price_after_buy(x) - price_after_sell(x),
                                                     (0, max_arb),
                                                     tol=1e-18,
                                                     solver='anderson'))
                    except ValueError as ve:
                        # print(f"{type(buy_pool).__name__} -> {type(sell_pool).__name__} pool price impact is non-monotonic: {ve}")
                        continue
                optimal_in_amount = buy_pool.get_in_amount(arb_to_buy, buy_pair)
                if optimal_in_amount is None:
                    continue
                arb_bought = buy_pool.get_out_amount(optimal_in_amount, buy_pair)
                # if arb_bought != arb_to_buy:
                    # print(f"{type(buy_pool).__name__} @ {buy_pool.address} estimated optimal in amount gives out amount off by {100 * (arb_bought - arb_to_buy) / arb_bought}%")
                if optimal_in_amount > loan_max:
                    optimal_in_amount = loan_max
                    arb_bought = buy_pool.get_out_amount(loan_max, buy_pair)
                profit = sell_pool.get_out_amount(arb_bought, sell_pair) - optimal_in_amount
                if profit > 0:
                    arbs.append([optimal_in_amount, profit, [buy_pool, sell_pool]])

        return max(arbs, key=lambda x: x[1])

    def _get_optimal_arbitrage_params(self, loan_max: int, circuit: List[Edge]) -> Union[Tuple[int, int, List[Pool]], List[None]]:
        no_arb_profit = 0
        if len(circuit) == 2:
            no_arb_in_amount, no_arb_profit, no_arb_pools = self._enforce_no_arbitrage(loan_max, circuit[0])

        loc_in_amount, loc_profit, loc_pools = self._locally_optimize_profit(loan_max, circuit)

        if no_arb_profit != 0 and max(no_arb_profit, loc_profit) == no_arb_profit:
            return no_arb_in_amount, no_arb_profit, no_arb_pools
        else:
            return loc_in_amount, loc_profit, loc_pools

    def _imbalance_uniswapv2_pools(self, circuits: OrderedDict, price_change: float):
        pert = price_change * 1e-4
        imbalanced = set()
        for circuit in circuits.values():
            weth_in_edge = circuit[0]
            weth_in_pair = self.ep.token_pair[weth_in_edge]
            pool_addresses = self.ep.pools[weth_in_edge]
            for address in pool_addresses:
                pool = self.address_to_pool[address]
                if is_unipair(pool) and address not in imbalanced:
                    pool.set_imbalance(weth_in_pair, price_change + random.uniform(-pert, pert), verbose=True)
                    imbalanced.add(address)

    def test_arbitrages(self, price_change: float):
        """ Create imbalance between uniswap v2 pools and other types of pools by forking mainnet and
        selling weth into them such that the token/weth spot price decreases by price_change percent +/- a small perturbation for each pool.
        """
        circuits = self._circuits()
        pruned_circuits = self._prune_circuits(circuits)
        weth_loan_pool_data = UniswapV3Loans().get_max_borrowable_weth_pool_data()
        loan_max = weth_loan_pool_data['balance']
        self._imbalance_uniswapv2_pools(pruned_circuits, price_change)
        # bot_address = geth_client.BOT
        bot = ApeBotV3.deploy(from_faucet(0))
        test_callback = TestUniswapV3FlashCallback.deploy(from_faucet(0))
        bot_address = bot.address
        bot_contract = geth_client.get_contract(bot_address, abi=ApeBotV3.abi, ganache=True)
        current_block = chain.height
        self._cache_pool_params(current_block, ganache=True)
        pool_types = [attr for attr in dir(sys.modules[__name__]) if attr[-4:] in {'Pool', 'Pair'}]
        gas_stats = dict()
        for num_swaps in range(2, self._max_hops + 1):
            one_more_swap = {swaps_pool_types: numpy.array(list()) for swaps_pool_types in product(pool_types, repeat=num_swaps)}
            gas_stats.update(one_more_swap)

        for circuit in pruned_circuits.values():
            in_amount, profit, pools = self._get_optimal_arbitrage_params(loan_max, circuit)
            print(profit)
            min_gas_cost_eth = GasNowStrategy('rapid').get_gas_price() * MIN_GAS_COST_PER_SWAP
            loan_fee = self._loans.fee(in_amount, weth_loan_pool_data['fee'])
            if profit < min_gas_cost_eth:
                continue
            bribe = flashbots.get_bribe(profit, min_gas_cost_eth)
            loan_fee = self._loans.fee(in_amount, weth_loan_pool_data['fee'])
            if profit > bribe + loan_fee:
                token_pairs = [self.ep.token_pair[edge] for edge in circuit]
                with RevertTransactions():
                    gas_used = self._construct_arbitrage(in_amount, bribe, pools, token_pairs, bot_contract, weth_loan_pool_data)
                pool_types = tuple([type(pool).__name__ for pool in pools])
                gas_stats[pool_types] = numpy.append(gas_stats[pool_types], gas_used)

        for pool_types, gas_stat in gas_stats.items():
            if gas_stat.size != 0:
                num_arbs, min_max, mean, _, _, _, _ = stats.describe(gas_stat)
                print(f"{' -> '.join(pool_types)}\n\tmean gas used over {num_arbs} arbs: {mean}\n\tmin/max: {min_max}")

    def _dispatch_to_relay(self,
                           current_block: BlockNumber,
                           arbitrage_params: List[Dict[str, Union[int, ContractFunction, TxParams]]]) -> List[HexStr]:
        bundled_txs = list()
        arb_data = list()
        owner_address = checksum(self._owner.address)
        nonce = geth_client.get_nonce(owner_address)
        count = 0
        for params in arbitrage_params:
            bot_function = params['caller']
            tx = bot_function.buildTransaction()
            tx.update({'nonce': hex(nonce), 'chainId': '0x1', 'gasPrice': '0x0'})
            tx.update({k: hex(v) if type(v) == int else v for k, v in tx.items() if k != 'to' and k != 'from'})
            bundled_txs.append(tx)
            arb_data.append({'id': count, 'arb_data': params['arb_data']})
            count += 1

        target_block = current_block + 1
        success = flashbots.sign_and_send_bundle(bundled_txs, current_block, target_block, arb_data, simulate=True)
        if success:
            tx_hashs = flashbots.sign_and_send_bundle(bundled_txs, current_block, target_block, arb_data, simulate=False)

        return tx_hashs

    def find_arbitrage(self):
        last_block = geth_client.latest_block()
        current_block = last_block
        bot_address = geth_client.BOT
        bot_contract = geth_client.get_contract(bot_address, abi=ApeBotV3.abi)
        while True:
            start = time()
            while(current_block == last_block):
                print(f"waiting for block {current_block + 1} ... {round(time() - start, 2)} secs\r", end='')
                current_block = geth_client.latest_block()
            print("")
            circuits = self._circuits()
            pruned_circuits = self._prune_circuits(circuits)
            weth_loan_pool_data = UniswapV3Loans().get_max_borrowable_weth_pool_data()
            loan_max = weth_loan_pool_data['balance']
            self._cache_pool_params(current_block)
            sorted_circuits = OrderedDict(sorted(pruned_circuits.items(), key=lambda vc: len(vc[0])))
            circuits_searched = 0
            start = time()
            swap_id_to_arb_params = dict()
            for circuit in sorted_circuits.values():
                in_amount, profit, pools = self._get_optimal_arbitrage_params(loan_max, circuit)

                circuits_searched += 1

                last_block = current_block
                current_block = geth_client.latest_block()
                if current_block > last_block:
                    print(f"{last_block}: missed chain state 🤡")
                    break

                if profit > 0:
                    min_gas_price = GasNowStrategy('rapid').get_gas_price()
                    min_gas_cost_eth = min_gas_price * len(circuit) * MIN_GAS_COST_PER_SWAP
                    if profit < min_gas_cost_eth:
                        continue
                    bribe = flashbots.get_bribe(profit, min_gas_cost_eth)
                    loan_fee = self._loans.fee(in_amount, weth_loan_pool_data['fee'])
                    if profit > bribe + loan_fee:
                        token_pairs = [self.ep.token_pair[edge] for edge in circuit]
                        estimated_gas_cost, implied_gas_price, bot_caller, bot_tx_params = \
                            self._construct_arbitrage(in_amount, bribe, pools, token_pairs, bot_contract, weth_loan_pool_data)
                        if implied_gas_price < min_gas_price:
                            continue
                        estimated_tx_cost = implied_gas_price * estimated_gas_cost
                        profit_after_fees = profit - estimated_tx_cost
                        rounded_profit = round(profit_after_fees / WETH_SCALE, 4)
                        rounded_cost = round(estimated_tx_cost / WETH_SCALE, 4)
                        print(f'{current_block}: ⛏ {rounded_profit} WETH profit ({estimated_gas_cost} gas x {implied_gas_price} gwei = {rounded_cost}) WETH')
                        pool_addresses = [pool.address for pool in pools]
                        ordered_token_pairs = [tp if int(tp[0], 16) < int(tp[1], 16) else (tp[1], tp[0]) for tp in token_pairs]
                        swap_ids = [(pool_address, token_pair) for pool_address, token_pair in zip(pool_addresses, ordered_token_pairs)]
                        arb_params = {
                            'caller': bot_caller,
                            'tx_params': bot_tx_params,
                            'implied_gas_price': implied_gas_price,
                            'swap_ids': set(swap_ids),
                            'arb_data': {
                                'in_amount': in_amount,
                                'pools': pool_addresses,
                                'profit': profit
                            }
                        }
                        for swap_id in swap_ids:
                            if swap_id in swap_id_to_arb_params:
                                prev_implied_gas_price = swap_id_to_arb_params[swap_id]['implied_gas_price']
                                if prev_implied_gas_price < implied_gas_price:
                                    swap_id_to_arb_params.update({swap_id: arb_params})
                            else:
                                swap_id_to_arb_params.update({swap_id: arb_params})

            if swap_id_to_arb_params != dict():
                # get arbitrage tx parameters from redundant dict
                max_gas_price_arb_params = list()
                mask = set()
                for swap_id, params in swap_id_to_arb_params.items():
                    if swap_id not in mask:
                        max_gas_price_arb_params.append(params)
                    mask = mask.union(params['swap_ids'])

                last_block = current_block
                current_block = geth_client.latest_block()
                if current_block > last_block:
                    print(f"{last_block}: missed chain state 🤡")
                    continue

                self._dispatch_to_relay(current_block, max_gas_price_arb_params)

            stop = time()
            print(f"{circuits_searched} possible arbitrages searched in {round(stop - start, 2)} secs")


if __name__ == "__main__":
    if __live_mode__:
        flashbots.set_owner()
    owner = __faucet__ if __test_mode__ else flashbots.owner
    successful_startup = False
    while not successful_startup:
        try:
            geth_client.wait_for_sync()
            token_graph = TokenGraph(owner)
            # UniswapV3(token_graph)
            # HidingBook(owner.address, bot_address, token_graph) TODO: get whitelisted
            # Bancor(token_graph)
            UniswapV2(token_graph)
            Sushiswap(token_graph)
            Balancer(token_graph)
            Curve(token_graph)
            Snowswap(token_graph)
            Mooniswap(token_graph)
            successful_startup = True
        except (BrokenPipeError, ConnectionRefusedError) as e:
            print(e)
            print("waiting for geth to restart...")
            sleep(300)
            geth_client.rebind()

    while True:
        try:
            geth_client.wait_for_sync()
            if __live_mode__:
                token_graph.find_arbitrages()
            else:
                token_graph.test_arbitrages(__price_change__)
        except (BrokenPipeError, ConnectionRefusedError, ConnectionResetError, aiohttp.client_exceptions.ClientConnectorError) as e:
            print(e)
            print("waiting for geth to restart...")
            sleep(300)          # wait for chain reorg
            geth_client.rebind()
            continue
        except (brownie.exceptions.VirtualMachineError, web3._utils.threads.Timeout) as e:
            print(e)
        break
