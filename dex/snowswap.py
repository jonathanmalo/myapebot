import sys
import datetime

from geth_client import TIME_UNTIL_NEXT_BLOCK, get_contract


SNOW_POOLS = {
    '0x4571753311E37dDb44faA8Fb78a6dF9a6E3c6C0B': 'yVault',   # 4 no volume
    '0xBf7CCD6C446acfcc5dF023043f2167B62E81899b': 'yyVault',  # 2 no volume
    '0x16BEa2e63aDAdE5984298D53A4d4d9c09e278192': 'Eth2Snow', # 4
    # '0xeF034645b9035C106acC04cB6460049D3c95F9eE': 'FCRVBTC', dead
}

TO_ADDRESS = {name: address for address, name in SNOW_POOLS.items()}

SNOW_HAS_UNDERLYING = {
    '0x4571753311E37dDb44faA8Fb78a6dF9a6E3c6C0B',
    '0xBf7CCD6C446acfcc5dF023043f2167B62E81899b',
    # '0xeF034645b9035C106acC04cB6460049D3c95F9eE',
}


SNOW_NUM_COINS = {
    '0x4571753311E37dDb44faA8Fb78a6dF9a6E3c6C0B': 4,
    '0xBf7CCD6C446acfcc5dF023043f2167B62E81899b': 2,
    '0x16BEa2e63aDAdE5984298D53A4d4d9c09e278192': 4,
    # '0xeF034645b9035C106acC04cB6460049D3c95F9eE': 2,
}

SNOWSWAP_ERRORS = {  # TODO: False in Eth2Snow is due to tests not supporting buy eth
    '0x16BEa2e63aDAdE5984298D53A4d4d9c09e278192': {('0x898BAD2774EB97cF6b94605677F43b41871410B1', '0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2'): False,
                                                   ('0x898BAD2774EB97cF6b94605677F43b41871410B1', '0xE95A203B1a91a908F9B9CE46459d101078c2c3cb'): False,
                                                   ('0x898BAD2774EB97cF6b94605677F43b41871410B1', '0xcBc1065255cBc3aB41a6868c22d1f1C573AB89fd'): False,
                                                   ('0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2', '0x898BAD2774EB97cF6b94605677F43b41871410B1'): 0,
                                                   ('0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2', '0xE95A203B1a91a908F9B9CE46459d101078c2c3cb'): 0,
                                                   ('0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2', '0xcBc1065255cBc3aB41a6868c22d1f1C573AB89fd'): 0,
                                                   ('0xE95A203B1a91a908F9B9CE46459d101078c2c3cb', '0x898BAD2774EB97cF6b94605677F43b41871410B1'): 0,
                                                   ('0xE95A203B1a91a908F9B9CE46459d101078c2c3cb', '0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2'): False, # TODO: error explodes for small input
                                                   ('0xE95A203B1a91a908F9B9CE46459d101078c2c3cb', '0xcBc1065255cBc3aB41a6868c22d1f1C573AB89fd'): 0,
                                                   ('0xcBc1065255cBc3aB41a6868c22d1f1C573AB89fd', '0x898BAD2774EB97cF6b94605677F43b41871410B1'): 0,
                                                   ('0xcBc1065255cBc3aB41a6868c22d1f1C573AB89fd', '0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2'): False,  # TODO: error explodes for small input
                                                   ('0xcBc1065255cBc3aB41a6868c22d1f1C573AB89fd', '0xE95A203B1a91a908F9B9CE46459d101078c2c3cb'): 0},
    '0x4571753311E37dDb44faA8Fb78a6dF9a6E3c6C0B': {('0x2f08119C6f07c006695E079AAFc638b8789FAf18', '0x37d19d1c4E1fa9DC47bD1eA12f742a0887eDa74a'): 1.9687386733524242e-07,
                                                   ('0x2f08119C6f07c006695E079AAFc638b8789FAf18', '0x597aD1e0c13Bfe8025993D9e79C69E1c0233522e'): 0,
                                                   ('0x2f08119C6f07c006695E079AAFc638b8789FAf18', '0xACd43E627e64355f1861cEC6d3a6688B31a6F952'): -1.797452064509528e-11,
                                                   ('0x37d19d1c4E1fa9DC47bD1eA12f742a0887eDa74a', '0x2f08119C6f07c006695E079AAFc638b8789FAf18'): -2.0264247212758303e-07,
                                                   ('0x37d19d1c4E1fa9DC47bD1eA12f742a0887eDa74a', '0x597aD1e0c13Bfe8025993D9e79C69E1c0233522e'): -1.9345294172556864e-07,
                                                   ('0x37d19d1c4E1fa9DC47bD1eA12f742a0887eDa74a', '0xACd43E627e64355f1861cEC6d3a6688B31a6F952'): -1.768643223465833e-07,
                                                   ('0x597aD1e0c13Bfe8025993D9e79C69E1c0233522e', '0x2f08119C6f07c006695E079AAFc638b8789FAf18'): 0,
                                                   ('0x597aD1e0c13Bfe8025993D9e79C69E1c0233522e', '0x37d19d1c4E1fa9DC47bD1eA12f742a0887eDa74a'): 1.8775878557118465e-07,
                                                   ('0x597aD1e0c13Bfe8025993D9e79C69E1c0233522e', '0xACd43E627e64355f1861cEC6d3a6688B31a6F952'): -1.7671270052185602e-11,
                                                   ('0xACd43E627e64355f1861cEC6d3a6688B31a6F952', '0x2f08119C6f07c006695E079AAFc638b8789FAf18'): 0,
                                                   ('0xACd43E627e64355f1861cEC6d3a6688B31a6F952', '0x37d19d1c4E1fa9DC47bD1eA12f742a0887eDa74a'): 1.7137853993691888e-07,
                                                   ('0xACd43E627e64355f1861cEC6d3a6688B31a6F952', '0x597aD1e0c13Bfe8025993D9e79C69E1c0233522e'): 0},
    '0xBf7CCD6C446acfcc5dF023043f2167B62E81899b': {('0x2994529C0652D127b7842094103715ec5299bBed', '0x5dbcF33D8c2E976c6b560249878e6F1491Bca25c'): False,
                                                   ('0x5dbcF33D8c2E976c6b560249878e6F1491Bca25c', '0x2994529C0652D127b7842094103715ec5299bBed'): 0}
}


mode_index = sys.argv.index('-m') if sys.argv.index('-m') > -1 else sys.argv.index('--mode')
__test_mode__ = sys.argv[mode_index + 1] != 'live'


SNOW_CONTRACTS = {address: get_contract(address, ganache=__test_mode__) for address in SNOW_POOLS.keys()}

YVAULT_UNDERLYING = ['0x6B175474E89094C44Da98b954EedeAC495271d0F',
                     '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48',
                     '0xdAC17F958D2ee523a2206206994597C13D831ec7',
                     '0x0000000000085d4780B73119b644AE5ecd22b376']
YVAULT_U_CONTRACTS = [get_contract(a, ganache=__test_mode__) for a in YVAULT_UNDERLYING]
YVAULT_TOKENS = ['0xACd43E627e64355f1861cEC6d3a6688B31a6F952',
                 '0x597aD1e0c13Bfe8025993D9e79C69E1c0233522e',
                 '0x2f08119C6f07c006695E079AAFc638b8789FAf18',
                 '0x37d19d1c4E1fa9DC47bD1eA12f742a0887eDa74a']
YVAULT_CONTRACTS = [get_contract(a, ganache=__test_mode__) for a in YVAULT_TOKENS]

YYVAULT_UNDERLYING = ['0xdF5e0e81Dff6FAF3A7e52BA697820c5e32D806A8', '0x3B3Ac5386837Dc563660FB6a0937DFAa5924333B']
YYVAULT_U_CONTRACTS = [get_contract(a, ganache=__test_mode__) for a in YYVAULT_UNDERLYING]
YYVAULT_TOKENS = ['0x5dbcF33D8c2E976c6b560249878e6F1491Bca25c', '0x2994529C0652D127b7842094103715ec5299bBed']
YYVAULT_CONTRACTS = [get_contract(a, ganache=__test_mode__) for a in YYVAULT_TOKENS]


class BaseSnowPool:

    N_COINS = None
    FEE_DENOMINATOR = 10 ** 10
    PRECISION = 10 ** 18  # The precision to convert to
    PRECISION_MUL = None
    TETHERED = None

    def set_balances(self, block, pool):
        self.balances = [pool.functions.balances(i).call(block_identifier=block) for i in range(self.N_COINS)]

    def set_A(self, block, pool):
        self.A = pool.functions.A().call(block_identifier=block)

    def set_share_prices(self, block, pool, vault_contracts):
        self.share_prices = [y.functions.getPricePerFullShare().call(block_identifier=block) for y in vault_contracts]

    def __init__(self, block: int, vault_contracts: list, token_contracts):
        _i = len('SnowSwap')
        name = type(self).__name__[_i:]
        address = TO_ADDRESS[name]
        pool = SNOW_CONTRACTS[address]
        self.set_balances(block, pool)
        self.set_A(block, pool)
        self.fee = pool.functions.fee().call(block_identifier=block)
        self.set_share_prices(block, pool, vault_contracts)
        # self.underlying_balances = [ut.functions.balanceOf(vt.address).call() for ut, vt in zip(token_contracts, vault_contracts)]
        # self.yvault_balances = [vt.functions.balance().call() for vt in vault_contracts]
        # self.yvault_total_supplies = [vt.functions.totalSupply().call() for vt in vault_contracts]

    def _xp(self, rates):
        result = [0] * self.N_COINS
        for i in range(self.N_COINS):
            result[i] = rates[i] * self.balances[i] // self.PRECISION
        return result

    def get_D(self, xp):
        S = 0
        for _x in xp:
            S += _x
        if S == 0:
            return 0

        Dprev = 0
        D = S
        n_coins = self.N_COINS
        Ann = self.A * n_coins
        for _i in range(255):
            D_P = D
            for _x in xp:
                D_P = D_P * D // (_x * n_coins + 1)  # +1 is to prevent /0
            Dprev = D
            D = (Ann * S + D_P * n_coins) * D // ((Ann - 1) * D + (n_coins + 1) * D_P)
            # Equality with the precision of 1
            if D > Dprev:
                if D - Dprev <= 1:
                    break
            else:
                if Dprev - D <= 1:
                    break
        return D

    def get_y(self, i, j, x, _xp):
        # x in the input is converted to the same price/precision
        n_coins = self.N_COINS
        assert (i != j) and (i >= 0) and (j >= 0) and (i < n_coins) and (j < n_coins)

        D = self.get_D(_xp)
        c = D
        S_ = 0
        Ann = self.A * n_coins

        _x = 0
        for _i in range(n_coins):
            if _i == i:
                _x = x
            elif _i != j:
                _x = _xp[_i]
            else:
                continue
            S_ += _x
            c = c * D // (_x * n_coins)
        c = c * D // (Ann * n_coins)
        b = S_ + D // Ann  # - D
        y_prev = 0
        y = D
        for _i in range(255):
            y_prev = y
            y = (y*y + c) // (2 * y + b - D)
            # Equality with the precision of 1
            if y > y_prev:
                if y - y_prev <= 1:
                    break
            else:
                if y_prev - y <= 1:
                    break
        return y

    def _exchange(self, i, j, dx, rates):
        # dx and dy are in c-tokens
        xp = self._xp(rates)

        x = xp[i] + dx * rates[i] // self.PRECISION
        y = self.get_y(i, j, x, xp)
        dy = xp[j] - y
        dy_fee = dy * self.fee // self.FEE_DENOMINATOR
        _dy = (dy - dy_fee) * self.PRECISION // rates[j]

        return _dy

    def _stored_rates(self):
        rates = self.PRECISION_MUL
        n_coins = self.N_COINS
        result = [0] * n_coins
        for i in range(n_coins):
            result[i] = rates[i] * self.share_prices[i]

        return result

    def exchange(self, i, j, dx):
        rates = self._stored_rates()
        dy = self._exchange(i, j, dx, rates)

        return dy

    # def controller_withdraw(self, _amount):
    #     # TODO: implement strategy withdrawals at ['0x2F90c531857a2086669520e772E9d433BbfD5496', '0x4f2fdebE0dF5C92EEe77Ff902512d725F6dfE65c', '0xAa12d6c9d680EAfA48D8c1ECba3FCF1753940A12', '0x4BA03330338172fEbEb0050Be6940c6e7f9c91b0']
    #     pass

    # def yvault_withdraw(self, i: int, _shares: int):
    #     balance = self.yvault_balances[i]
    #     r = balance * _shares // self.yvault_total_supplies[i]
    #     b = self.underlying_balances[i]
    #     if b < r:
    #         _withdraw = r - b
    #         _diff = self.controller_withdraw(_withdraw)
    #         if _diff < _withdraw:
    #             r = b + _diff

    #     return r

    # def dx_w_fee(self, dx):
    #     fee = dx * self.usdt_basis_points_rate // 10000
    #     fee = min(fee, self.usdt_max_fee)
    #     return dx - fee

    # def exchange_underlying(self, i, j, dx):
    #     rates = self._stored_rates()
    #     precisions = self.PRECISION_MUL
    #     rate_i = rates[i] // precisions[i]
    #     rate_j = rates[j] // precisions[j]
    #     dx_ = dx * self.PRECISION // rate_i

    #     dy_ = self._exchange(i, j, dx_, rates)
    #     dy = dy_ * rate_j // self.PRECISION
    #     # TODO: tether fees not accounted for, prevent from tether swaps
    #     tethered = self.TETHERED
    #     # if tethered[i]:
    #     #     dx = self.dx_w_fee(dx)
    #     # check that yVault token contract has sufficient balance
    #     # if it doesn't, we will incur a 0.5% withdrawal fee
    #     balance_underlying = self.underlying_balances[j]
    #     # if withdrawal fee will be incurred, pass fee onto user
    #     if balance_underlying < dy_:
    #         # integer maths
    #         dy = (995 * dy) // 1000

    #     dy = self.yvault_withdraw(dy_)

    #     if tethered[j]:
    #         dy = self.dx_w_fee(dy)

    #     return dy


class SnowSwapyVault(BaseSnowPool):

    N_COINS = 4
    PRECISION_MUL = [1, 1000000000000, 1000000000000, 1]
    TETHERED = [False, False, True, False]

    def __init__(self, block: int):
        super().__init__(block, YVAULT_CONTRACTS, YVAULT_U_CONTRACTS)


class SnowSwapyyVault(BaseSnowPool):

    N_COINS = 2
    PRECISION_MUL = [1, 1]

    def __init__(self, block: int):
        super().__init__(block, YYVAULT_CONTRACTS, YYVAULT_U_CONTRACTS)


class SnowSwapEth2Snow(BaseSnowPool):

    N_COINS = 4
    RATES = [1000000000000000000, 1000000000000000000, 1000000000000000000, 1000000000000000000]
    LENDING_PRECISION = 10 ** 18
    A_PRECISION = 100

    def set_As(self, block, pool):
        self.initial_A = pool.functions.initial_A().call(block_identifier=block)
        self.future_A = pool.functions.future_A().call(block_identifier=block)
        self.initial_A_time = pool.functions.initial_A_time().call(block_identifier=block)
        self.future_A_time = pool.functions.future_A_time().call(block_identifier=block)

    def set_timestamp(self, block):
        # inherently innacurate
        # timestamp is set as close as possible to future block timestamp
        self.block_timestamp = int(datetime.datetime.utcnow().timestamp()) + TIME_UNTIL_NEXT_BLOCK

    def __init__(self, block: int):
        _i = len('SnowSwap')
        name = type(self).__name__[_i:]
        address = TO_ADDRESS[name]
        pool = SNOW_CONTRACTS[address]
        self.set_balances(block, pool)
        self.set_As(block, pool)
        self.set_timestamp(block)
        self.fee = pool.functions.fee().call(block_identifier=block)

    def _A(self):
        t1 = self.future_A_time
        A1 = self.future_A

        if self.block_timestamp < t1:
            A0 = self.initial_A
            t0 = self.initial_A_time
            # Expressions in uint256 cannot have negative numbers, thus "if"
            if A1 > A0:
                return A0 + (A1 - A0) * (self.block_timestamp - t0) // (t1 - t0)
            else:
                return A0 - (A0 - A1) * (self.block_timestamp - t0) // (t1 - t0)

        else:  # when t1 == 0 or block.timestamp >= t1
            return A1

    def _xp(self):
        rates = self.RATES
        result = [0] * self.N_COINS
        for i in range(self.N_COINS):
            result[i] = rates[i] * self.balances[i] // self.LENDING_PRECISION

        return result

    def _xp_mem(self, _balances):
        rates = self.RATES
        result = [0] * self.N_COINS
        for i in range(self.N_COINS):
            result[i] = rates[i] * _balances[i] // self.PRECISION

        return result

    def get_D(self, xp, amp):
        S = 0
        Dprev = 0

        for _x in xp:
            S += _x
        if S == 0:
            return 0

        D = S
        n_coins = self.N_COINS
        a_prec = self.A_PRECISION
        Ann = amp * n_coins
        for _i in range(255):
            D_P = D
            for _x in xp:
                D_P = D_P * D // (_x * n_coins)  # If division by 0, this will be borked: only withdrawal will work. And that is good
            Dprev = D
            D = (Ann * S // a_prec + D_P * n_coins) * D // ((Ann - a_prec) * D // a_prec + (n_coins + 1) * D_P)
            # Equality with the precision of 1
            if D > Dprev:
                if D - Dprev <= 1:
                    return D
            else:
                if Dprev - D <= 1:
                    return D

        # convergence typically occurs in 4 rounds or less, this should be unreachable!
        # if it does happen the pool is borked and LPs can withdraw via `remove_liquidity`
        raise Exception()

    def get_y(self, i, j, x, xp_):
        # x in the input is converted to the same price/precision
        n_coins = self.N_COINS
        assert i != j       # dev: same coin
        assert j >= 0       # dev: j below zero
        assert j < n_coins  # dev: j above n_coins

        # should be unreachable, but good for safety
        assert i >= 0
        assert i < n_coins

        amp = self._A()
        D = self.get_D(xp_, amp)
        Ann = amp * n_coins
        c = D
        S_ = 0
        _x = 0
        y_prev = 0

        for _i in range(n_coins):
            if _i == i:
                _x = x
            elif _i != j:
                _x = xp_[_i]
            else:
                continue
            S_ += _x
            c = c * D // (_x * n_coins)
        c = c * D * self.A_PRECISION // (Ann * n_coins)
        b = S_ + D * self.A_PRECISION // Ann  # - D
        y = D
        for _i in range(255):
            y_prev = y
            y = (y*y + c) // (2 * y + b - D)
            # Equality with the precision of 1
            if y > y_prev:
                if y - y_prev <= 1:
                    return y
            else:
                if y_prev - y <= 1:
                    return y

        raise Exception()

    def exchange(self, i, j, dx):
        old_balances = self.balances
        xp = self._xp_mem(old_balances)

        rates = self.RATES
        x = xp[i] + dx * rates[i] // self.PRECISION
        y = self.get_y(i, j, x, xp)

        dy = xp[j] - y - 1  # -1 just in case there were some rounding errors
        dy_fee = dy * self.fee // self.FEE_DENOMINATOR

        # Convert all to real units
        dy = (dy - dy_fee) * self.PRECISION // rates[j]

        return dy


SNOW_POOLS = {address: getattr(sys.modules[__name__], f"SnowSwap{name}") for address, name in SNOW_POOLS.items()}
