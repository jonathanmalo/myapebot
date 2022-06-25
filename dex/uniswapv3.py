class UniswapV3Pair(Pool):

    _slot0_sig = sig('slot0()').hex()
    _liquidity_sig = sig('liquidity()').hex()
    _tickbitmap_sig = sig('tickBitmap(int16)').hex()
    _fee_growth0_sig = sig('feeGrowthGlobal0X128()').hex()
    _fee_growth1_sig = sig('feeGrowthGlobal1X128()').hex()
    _observations_sig = sig('observations(uint256)').hex()
    _swap_sig = sig('swap(address,bool,int256,uint160,bytes)')
    _fixed_point96_res = 96
    _fixed_point96_q96 = 0x1000000000000000000000000
    _fixed_point128_q128 = 0x100000000000000000000000000000000
    _min_sqrt_ratio = 4295128739
    _max_sqrt_ratio = 1461446703485210103287273052203988822378723970342
    _max_tick = 887272
    _min_tick = -_max_tick

    max_ticks = 128

    def __init__(self, pair_address: str, tokens: tuple, fee: int, tick_spacing: int):
        super().__init__(pair_address)
        self._tokens = tokens
        self._fee = fee
        self._tick_spacing = tick_spacing
        self.max_ticks *= tick_spacing

    def get_param_calls(self):
        slot0_types = ['uint160', 'int24', 'uint16', 'uint16', 'uint16', 'uint8', 'bool']
        slot0_call = [self.address, self._slot0_sig, slot0_types]
        liquidity_type = ['uint128']
        liquidity_call = [self.address, self._liquidity_sig, liquidity_type, -1]
        fee_growth_type = ['uint256']
        fee_growth0_call = [self.address, self._fee_growth0_sig, fee_growth_type, -1]
        fee_growth1_call = [self.address, self._fee_growth1_sig, fee_growth_type, -1]
        return [slot0_call, liquidity_call, fee_growth0_call, fee_growth1_call]

    def _get_tickbitmap(self, tick: int):
        mt = self.max_ticks
        tick_spacing = self._tick_spacing
        r = [(t // tick_spacing) >> 8 for t in range(tick-mt, tick+mt, tick_spacing)]
        tick_calls = [[self.address, f"{self._tickbitmap_sig}{encode_single('int16', i).hex()}", ['uint256'], -1] for i in r]
        bitmap_list = geth_client.batch_request(tick_calls)
        bitmap = {i: t for i, t in zip(r, bitmap_list)}
        return bitmap

    def _get_observations(self, obs_index: int, cardinality: int):
        data0 = f"{self._observations_sig}{encode_single('uint256', obs_index)}"
        obs_types = ['uint32', 'int56', 'uint160', 'bool']
        observation0 = geth_client.request(self.address, data0, obs_types)
        data1 = f"{self._observations_sig}{encode_single('uint256', (obs_index + 1) % cardinality)}"
        observation1 = geth_client.request(self.address, data1, obs_types)
        return observation0, observation1

    def set_params(self, slot0: list, liquidity: int, fee_growth0: int, fee_growth1: int):
        token0, token1 = self._tokens
        tick = slot0[1]
        obs_index = slot0[2]
        cardinality = slot0[3]
        token_params = {'params': slot0 + [liquidity, fee_growth0, fee_growth1],
                        'obs': self._get_observations(obs_index, cardinality),
                        'tick_bitmap': self._get_tickbitmap(tick)}
        self._params.update(token_params)

    def get_in_amount_offset(self, call: bytes):
        if len(call) != 228:
            raise Exception("Call is incorrect length!")

        return 68

    def get_swap_data(self, in_amount: int, out_amount: int, pair: TokenPair, bot_address: ChecksumAddress) -> HexBytes:
        zero_for_one = (pair == self._tokens)
        min_price_limit = self._min_sqrt_ratio + 1
        max_price_limit = self._max_sqrt_ratio - 1
        price_limit = min_price_limit if zero_for_one else max_price_limit
        args = [bot_address, zero_for_one, in_amount, price_limit, b'']
        data = encode_abi(['address', 'bool', 'int256', 'uint160', 'bytes'], args)

        swap_data = self._swap_sig + data

        return swap_data

    def set_imbalance(self, in_reserve_delta: int, pair: TokenPair, reserves: List[int]):
        self.test_swap(in_reserve_delta, 0, pair)

    def test_swap(self, in_amount: int, min_out: int, pair: TokenPair, verbose: bool = False):
        seller_address = checksum(__faucet__.address)
        zero_for_one = (pair == self._tokens)
        if verbose:
            print(f"Params: {[TICKERS[t] for t in pair]}: {self.get_reserves(pair)]}")
            print(f"Pair: {exchange}")
            print(f"In token balance: {interface.IERC20(weth_pair[0]).balanceOf(accounts[0])}")
            print(f"In Amount -> Out Amount: {in_amount} -> {min_out}")

        min_price_limit = self._min_sqrt_ratio + 1
        max_price_limit = self._max_sqrt_ratio - 1
        price_limit = min_price_limit if zero_for_one else max_price_limit
        exchange.swap['address,bool,int,uint160,bytes'](seller_address, zero_for_one, in_amount, price_limit, b'', from_faucet(0))

    def _msb(self, n: int):
        pos = 0
        while 1 < n:
            n = (n >> 1)
            pos += 1
        return pos

    def _lsb(self, n: int):
        return (n & -n).bit_length() - 1

    def _next_tick_within_one_word(self, tick: int, lte: bool):
        tick_spacing = self._tick_spacing
        compressed = tick // tick_spacing
        tick_bitmap = self._params['tick_bitmap']
        compressed -= 1 if tick < 0 and tick % tick_spacing != 0 else 0
        mt = self.max_ticks
        if lte:
            word_pos, bit_pos = compressed >> 8, compressed % 256
            if word_pos < -mt or word_pos > mt:
                return None, None
            mask = (1 << bit_pos) - 1 + (1 << bit_pos)
            masked = tick_bitmap[word_pos] & mask
            initialized_tick = (compressed - (bit_pos - self._msb(masked))) * tick_spacing
            uninitialized_tick = (compressed - bit_pos) * tick_spacing            
        else:
            compressed += 1
            word_pos, bit_pos = compressed >> 8, compressed % 256
            if word_pos < -mt or word_pos > mt:
                return None, None
            mask = -((1 << bit_pos) - 1)
            masked = tick_bitmap[word_pos] & mask
            initialized_tick = (compressed + self._lsb(masked) - bit_pos) * tick_spacing
            uninitialized_tick = (compressed + 2**8-1 - bit_pos) * tick_spacing

        initialized = masked != 0
        next_tick = initialized_tick if initialized else uninitialized_tick
        return next_tick, initialized

    def _get_sqrt_ratio_at_tick(self, tick: int):
        abs_tick = abs(tick)
        if abs_tick <= self._max_tick:
            return None
        ratio = 0xfffcb933bd6fad37aa2d162d1a594001 if abs_tick & 0x1 != 0 else 0x100000000000000000000000000000000
        if abs_tick & 0x2 != 0:
            ratio = (ratio * 0xfff97272373d413259a46990580e213a) >> 128
        if abs_tick & 0x4 != 0:
            ratio = (ratio * 0xfff2e50f5f656932ef12357cf3c7fdcc) >> 128
        if abs_tick & 0x8 != 0:
            ratio = (ratio * 0xffe5caca7e10e4e61c3624eaa0941cd0) >> 128
        if abs_tick & 0x10 != 0:
            ratio = (ratio * 0xffcb9843d60f6159c9db58835c926644) >> 128
        if abs_tick & 0x20 != 0:
            ratio = (ratio * 0xff973b41fa98c081472e6896dfb254c0) >> 128
        if abs_tick & 0x40 != 0:
            ratio = (ratio * 0xff2ea16466c96a3843ec78b326b52861) >> 128
        if abs_tick & 0x80 != 0:
            ratio = (ratio * 0xfe5dee046a99a2a811c461f1969c3053) >> 128
        if abs_tick & 0x100 != 0:
            ratio = (ratio * 0xfcbe86c7900a88aedcffc83b479aa3a4) >> 128
        if abs_tick & 0x200 != 0:
            ratio = (ratio * 0xf987a7253ac413176f2b074cf7815e54) >> 128
        if abs_tick & 0x400 != 0:
            ratio = (ratio * 0xf3392b0822b70005940c7a398e4b70f3) >> 128
        if abs_tick & 0x800 != 0:
            ratio = (ratio * 0xe7159475a2c29b7443b29c7fa6e889d9) >> 128
        if abs_tick & 0x1000 != 0:
            ratio = (ratio * 0xd097f3bdfd2022b8845ad8f792aa5825) >> 128
        if abs_tick & 0x2000 != 0:
            ratio = (ratio * 0xa9f746462d870fdf8a65dc1f90e061e5) >> 128
        if abs_tick & 0x4000 != 0:
            ratio = (ratio * 0x70d869a156d2a1b890bb3df62baf32f7) >> 128
        if abs_tick & 0x8000 != 0:
            ratio = (ratio * 0x31be135f97d08fd981231505542fcfa6) >> 128
        if abs_tick & 0x10000 != 0:
            ratio = (ratio * 0x9aa508b5b7a84e1c677de54f3e99bc9) >> 128
        if abs_tick & 0x20000 != 0:
            ratio = (ratio * 0x5d6af8dedb81196699c329225ee604) >> 128
        if abs_tick & 0x40000 != 0:
            ratio = (ratio * 0x2216e584f5fa1ea926041bedfe98) >> 128
        if abs_tick & 0x80000 != 0:
            ratio = (ratio * 0x48a170391f7dc42444e8fa2) >> 128
        if tick < 0:
            ratio = SOLINF // ratio
        sqrtp = (ratio >> 32) + (0 if (ratio % (1 << 32) == 0) else 1)

        return sqrtp

    def shl(self, shift, n):
        return (n << shift) & ((1 << 256) - 1)

    def shr(self, shift, n):
        return (n % (1 << 256)) >> shift

    def _get_tick_at_sqrt_ratio(self, sqrtp: int):
        if sqrtp < self._min_sqrt_ratio or sqrtp >= self._max_sqrt_ratio:
            return None

        ratio = sqrtp << 32

        r = ratio
        msb = 0
        thresholds = [0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF,
                      0xFFFFFFFFFFFFFFFF,
                      0xFFFFFFFF,
                      0xFFFF,
                      0xFF,
                      0xF,
                      0x3]
        for i, threshold in zip(range(7, 0, -1), thresholds):
            f = self.shl(i, r > threshold)
            msb |= f
            r = self.shr(f, r)

        f = r > 0x1
        msb |= f

        r = ratio >> (msb - 127) if msb >= 128 else ratio << (127 - msb)
        log_2 = ((msb % 2**128) - 128) << 64

        for i in range(63, 49, -1):
            r = self.shr(127, (r * r) % SOLINF)
            f = self.shr(128, r)
            log_2 |= self.shl(63, f)
            r = self.shr(f, r)

        log_sqrt10001 = log_2 * 255738958999603826347141
        tick_low = (log_sqrt10001 - 3402992956809132418596140100660247210) >> 128
        tick_hi = (log_sqrt10001 + 291339464771989622907027621153398088495) >> 128
        if tick_low == tick_hi:
            return tick_low
        else:
            sqrtr_at_tick = self._get_sqrt_ratio_at_tick(tick_hi)
            if sqrtr_at_tick is None:
                return None
            elif sqrtr_at_tick <= sqrtp:
                return tick_hi
            else:
                return tick_low

    def mul_div(self, a, b, denominator):
        return (a * b) // denominator

    def mul_div_roundup(self, a, b, denominator):
        result = self.mul_div(a, b, denominator)
        if ((a * b) % denominator) > 0:
            result += 1
        return result

    def unsafe_div_roundup(self, a, b):
        return (a // b) + ((a % b) > 0)

    def _get_amount0_delta(self, sqrtr_a: int, sqrtr_b: int, liquidity: int, roundup: bool):
        if sqrtr_a > sqrtr_b:
            sqrtr_a, sqrtr_b = sqrtr_b, sqrtr_a

        numerator1 = liquidity << self._fixed_point96_res
        numerator2 = sqrtr_b - sqrtr_a

        if sqrtr_a <= 0:
            return None

        delta = self.unsafe_div_roundup(self.mul_div_roundup(numerator1, numerator2, sqrtr_b), sqrtr_a) \
            if roundup else self.mul_div(numerator1, numerator2, sqrtr_b) // sqrtr_a

        return delta

    def _get_amount1_delta(self, sqrtr_a: int, sqrtr_b: int, liquidity: int, roundup: bool):
        if sqrtr_a > sqrtr_b:
            sqrtr_a, sqrtr_b = sqrtr_b, sqrtr_a

        delta = self.mul_div_roundup(liquidity, sqrtr_b - sqrtr_a, self._fixed_point96_q96) \
            if roundup else self.mul_div(liquidity, sqrtr_b, sqrtr_a, self._fixed_point96_q96)

        return delta

    def _get_nextsqrtr_from_amount0_roundup(self, sqrtp: int, liquidity: int, amount: int, add: bool):
        if amount == 0:
            return sqrtp
        numerator1 = liquidity << self._fixed_point96_res
        product = amount * sqrtp
        if add:
            if product // amount == sqrtp:
                denominator = numerator1 + product
                if denominator >= numerator1:
                    return self.mul_div_roundup(numerator1, sqrtp, denominator)
            return self.unsafe_div_roundup(numerator1, (numerator1 // sqrtp) + amount)
        else:
            if product // amount != sqrtp or numerator1 <= product:
                return None
            denominator = numerator1 - product
            return self.mul_div_roundup(numerator1, sqrtp, denominator)

    def _get_nextsqrtr_from_amount1_rounddown(self, sqrtp: int, liquidity: int, amount: int, add: bool):
        if add:
            quotient = (amount << self._fixed_point96_res) // liquidity \
                if amount <= 2**160-1 else self.mul_div(amount, self._fixed_point96_q96, liquidity)
            return sqrtp + quotient
        else:
            quotient = self._unsafe_div_roundup((amount << self._fixed_point96_res), liquidity) \
                if amount <= 2**160-1 else self.mul_div_roundup(amount, self._fixed_point96_q96, liquidity)
            if sqrtp <= quotient:
                return None
            return sqrtp - quotient

    def _get_next_sqrtr_from_input(self, sqrtp: int, liquidity: int, amount_in: int, zero_for_one: bool):
        sqrtr_next = self._get_nextsqrtr_from_amount0_roundup(sqrtp, liquidity, amount_in, True) \
            if zero_for_one else self._get_nextsqrtr_from_amount1_rounddown(sqrtp, liquidity, amount_in, True)

        return sqrtr_next

    def _get_next_sqrtr_from_output(self, sqrtp: int, liquidity: int, amount_out: int, zero_for_one: bool):
        sqrtr_next = self._get_nextsqrtr_from_amount1_rounddown(sqrtp, liquidity, amount_out, True) \
            if zero_for_one else self._get_nextsqrtr_from_amount0_roundup(sqrtp, liquidity, amount_out, True)

        return sqrtr_next

    def _compute_swap_step(self, sqrtr: int, sqrtr_target: int, liquidity: int, amount_remaining: int):
        fee_pips = self._fee
        exact_in = amount_remaining >= 0
        zero_for_one = sqrtr >= sqrtr_target

        if exact_in:
            amount_remaining_less_fee = self.mul_div(amount_remaining, 10**6 - fee_pips, 10**6)
            amount_in = self._get_amount0_delta(sqrtr_target, sqrtr, liquidity, True) \
                if zero_for_one else self._get_amount1_delta(sqrtr, sqrtr_target, liquidity, True)
            if amount_in is None:
                return [None] * 4
            if amount_remaining_less_fee >= amount_in:
                sqrtr_next = sqrtr_target
            else:
                sqrtr_next = self._get_next_sqrtr_from_input(sqrtr, liquidity, amount_remaining_less_fee, zero_for_one)
        else:
            amount_out = self._get_amount1_delta(sqrtr_target, sqrtr, liquidity, False) \
                if zero_for_one else self._get_amount0_delta(sqrtr, sqrtr_target, liquidity, False)
            if amount_out is None:
                return [None] * 4
            if -amount_remaining >= amount_out:
                sqrtr_next = sqrtr_target
            else:
                sqrtr_next = self._get_next_sqrtr_from_output(sqrtr, liquidity, -amount_remaining, zero_for_one)

        if sqrtr_next is None:
            return [None] * 4

        _max = sqrtr_target == sqrtr_next

        if zero_for_one:
            amount_in = amount_in if _max and exact_in else self._get_amount0_delta(sqrtr_next, sqrtr, liquidity, True)
            amount_out = amount_out if _max and not exact_in else self._get_amount1_delta(sqrtr_next, sqrtr, liquidity, False)
        else:
            amount_in = amount_in if _max and exact_in else self._get_amount1_delta(sqrtr, sqrtr_next, liquidity, True)
            amount_out = amount_out if _max and not exact_in else self._get_amount0_delta(sqrtr, sqrtr_next, liquidity, False)

        if amount_out is None or amount_in is None:
            return [None] * 4

        if not exact_in and amount_out > -amount_remaining:
            amount_out = -amount_remaining

        if exact_in and sqrtr_next != sqrtr_target:
            fee_amount = amount_remaining - amount_in
        else:
            fee_amount = self.mul_div_roundup(amount_in, fee_pips, 10**6 - fee_pips)

        return sqrtr_next, amount_in, amount_out, fee_amount

    def _transform(self, last: list, block_timestamp: int, tick: int, liquidity: int):
        last_block_timestamp = last[0]
        delta = block_timestamp - last_block_timestamp
        tick_cum = last[1]
        secs_per_liq_cum = last[2]
        adj_delta = (delta << 128) // (liquidity if liquidity > 0 else 1)
        observation = [block_timestamp, tick_cum + tick * delta, secs_per_liq_cum + adj_delta, True]
        return observation

    def lte(self, time: int, a: int, b: int):
        if a <= time and b <= time:
            return a <= b
        a_adj = a if a > time else a + 2**32
        b_adj = b if b > time else b + 2**32

        return a_adj <= b_adj

    def _get_surrounding_observations(self, time: int, target: int, tick: int, index: int, liquidity: int, cardinality: int):
        before_or_at = self._params['obs'][0]
        before_or_at_timestamp = before_or_at[0]
        if self.lte(time, before_or_at_timestamp, target):
            if before_or_at_timestamp == target:
                return before_or_at, []
            else:
                return before_or_at, self.transform(before_or_at, target, tick, liquidity)

        before_or_at = self._params['obs'][1]
        before_or_at_initialized = before_or_at[3]
        if not before_or_at_initialized:
            before_or_at = self._params['obs'][2]

        if not self.lte(time, before_or_at_timestamp, target):
            return None

        youre_fucked = True
        return youre_fucked     # TODO: binary search on a 5 digit length struct array. rebuild in geth

    def _observe_single(self, time, secs_ago, tick, index, liquidity, cardinality):
        if secs_ago == 0:
            last = self._params['obs'][0]
            last_block_timestamp = last[0]
            if last_block_timestamp != time:
                last = self._transform(last, time, tick, liquidity)
            tick_cum = last[1]
            secs_per_liq_cum = last[2]
            return tick_cum, secs_per_liq_cum

        target = time - secs_ago

        before_or_at, at_or_after = self._get_surrounding_observations(time, target, tick, index, liquidity, cardinality)

    def _cross():
        pass

    def _add_delta():
        pass

    def get_in_amount(self, out_amount: int, pair: tuple):
        if out_amount < 0:
            return 0

        return self.get_out_amount(-out_amount, pair, exact_output=True)

    def get_out_amount(self, in_amount: int, pair: tuple, exact_output: bool = False):
        """ If in_amount is positive, the swap is exactInput, and if negative, exactOutput. Sqrt prices are fixed point stored in uint160.
        """
        if in_amount <= 0 and not exact_output:
            # function was not intentionally called to specify exact output
            return 0

        sqrtp, tick, obs_index, obs_card, obs_card_next, protocol_fee, unlocked, liquidity, fee_growth0, fee_growth1 = self._params['params']

        if not unlocked:
            return 0

        tick_spacing = self._tick_spacing
        min_tick = self._min_tick
        max_tick = self._max_tick
        weth_pair = self._convert_to_weth_pair(pair)
        zero_for_one = (weth_pair == self._tokens)
        sqrtp_limit = 0 if zero_for_one else 2**160-1

        cache_liquidity_start = liquidity
        cache_block_timestamp = int(datetime.datetime.utcnow().timestamp()) + geth_client.HALF_AVG_BLOCK_TIME # estimate future block timestamp
        cache_protocol_fee = (protocol_fee % 16) if zero_for_one else (protocol_fee // 2**4)
        cache_secs_liq_cum = 0
        cache_tick_cum = 0
        cache_latest_obs = False

        exact_input = (in_amount > 0)

        state_amount_remaining = in_amount
        state_tick = tick
        state_amount_calc = 0
        state_sqrtp = sqrtp
        state_fee_growth = fee_growth0 if zero_for_one else fee_growth1
        state_protocol_fee = 0
        state_liquidity = liquidity

        while state_amount_remaining != 0 and state_sqrtp != sqrtp_limit:
            step_sqrtp_start = state_sqrtp
            step_tick_next, step_initialized = self._next_tick_within_one_word(state_tick, tick_spacing, zero_for_one)
            if step_tick_next is None:
                print("attempted call outside of max_ticks")
                return 0
            if step_tick_next < min_tick:
                step_tick_next = min_tick
            elif step_tick_next > max_tick:
                step_tick_next = max_tick
            step_sqrtp_next = self._get_sqrt_ratio_at_tick(step_tick_next)
            sqrtp_targetp = (step_sqrtp_next < sqrtp_limit if zero_for_one else step_sqrtp_next > sqrtp_limit)
            sqrtp_target = sqrtp_limit if sqrtp_targetp else step_sqrtp_next
            state_sqrtp, step_amount_in, step_amount_out, step_fee_amount = self._compute_swap_step(sqrtp, sqrtp_target, state_liquidity, state_amount_remaining)
            if state_sqrtp is None:
                return 0
            if exact_input:
                state_amount_remaining -= step_amount_in + step_fee_amount
                state_amount_calc = state_amount_calc - step_amount_out
            else:
                state_amount_remaining += step_amount_out
                state_amount_calc += step_amount_in + step_fee_amount

            if cache_protocol_fee > 0:
                delta = step_fee_amount // cache_protocol_fee
                step_fee_amount -= delta
                state_protocol_fee += delta

            if state_liquidity > 0:
                state_fee_growth += self.mul_div(step_fee_amount, self._fixed_point128_q128, state_liquidity)

            if state_sqrtp == step_sqrtp_next:
                if step_initialized:
                    if not cache_latest_obs:
                        cache_tick_cum, cache_secs_liq_cum = self._observe_single(
                            cache_block_timestamp,
                            0,
                            tick,
                            obs_index,
                            cache_liquidity_start,
                            obs_card
                        )
                        cache_latest_obs = True
                    liquidity_net = self._cross(
                        step_tick_next,
                        state_fee_growth if zero_for_one else fee_growth0,
                        fee_growth1 if zero_for_one else state_fee_growth,
                        cache_secs_liq_cum,
                        cache_tick_cum,
                        cache_block_timestamp
                    )

                    if zero_for_one:
                        liquidity_net = -liquidity_net

                    state_liquidity = self._add_delta(state_liquidity, liquidity_net)

                state_tick = step_tick_next - 1 if zero_for_one else step_tick_next
            elif state_sqrtp != step_sqrtp_start:
                state_tick = self._get_tick_at_sqrt_ratio(state_sqrtp)
                if state_tick is None:
                    return 0

        if zero_for_one == exact_input:
            amount0, amount1 = in_amount - state_amount_remaining, state_amount_calc
        else:
            amount0, amount1 = state_amount_calc, in_amount - state_amount_remaining

        return abs(amount1 if zero_for_one else amount0)


class UniswapV3(TokenGraphUpdater):

    _get_pool_sig = sig('getPool(address,address,uint24)').hex()
    _token0_sig = sig('token0()').hex()
    _tick_spacing_sig = sig('tickSpacing()').hex()
    _fees = [500, 3000, 10000]

    def balance_of(self, address: str):
        return f"{sig('balanceOf(address)').hex()}{encode_address(address)}"

    def _update_max_borrowable_weth(self, is_token0: bool, address: ChecksumAddress, balance: int, fee: int):
        pair_data = {'is_token0': is_token0, 'balance': balance, 'address': address, 'fee': fee}
        if self.borrowable['fee'] < fee or self.borrowable['balance'] > balance:
            return
        self.borrowable.update(pair_data)

    def update_token_graph(self, token_graph: Graph):
        self.borrowable = {'balance': 0, 'fee': self._fees[-1]}
        trade_set = set(__trade_set__)
        pairs = list(combinations(trade_set, 2))
        get_pool_data = list()
        for pair in pairs:
            get_pool_data.extend([f"{self._get_pool_sig}{encode_pair(pair)}{encode_single('uint24', fee).hex()}" for fee in self._fees])

        factory = UNISWAPV3_FACTORY
        batch_addresses = geth_client.batch_request([[factory, data, ['address'], -1] for data in get_pool_data])
        pairs3 = [pairs[i // 3] for i in range(len(get_pool_data))]
        address_pair_fee = [(checksum(address), pair, fee) for address, pair, fee in zip(batch_addresses, pairs3, self._fees * len(pairs))
                            if address != ZERO_ADDRESS]
        tick_spacings = geth_client.batch_request([[address, self._tick_spacing_sig, ['int24'], -1] for address, _, _ in address_pair_fee])
        pair0_is_token0 = [int(pair[0], 16) < int(pair[1], 16) for _, pair, _ in address_pair_fee]
        tdoi_balance0s = [[apf[1][0] if p0_is_t0 else apf[1][1], self.balance_of(apf[0]), ['uint'], -1] for apf, p0_is_t0 in zip(address_pair_fee, pair0_is_token0)]
        tdoi_balance1s = [[apf[1][1] if p0_is_t0 else apf[1][0], self.balance_of(apf[0]), ['uint'], -1] for apf, p0_is_t0 in zip(address_pair_fee, pair0_is_token0)]
        balance0s = geth_client.batch_request(tdoi_balance0s)
        balance1s = geth_client.batch_request(tdoi_balance1s)
        i = 0
        assert len(balance0s) == len(address_pair_fee)
        assert len(balance1s) == len(address_pair_fee)
        for balance0, balance1, tick_spacing, p0_is_t0, apf in zip(balance0s, balance1s, tick_spacings, pair0_is_token0, address_pair_fee):
            address, pair, fee = apf
            token_a, token_b = pair
            token0, token1 = (token_a, token_b) if p0_is_t0 else (token_b, token_a)
            check0 = balance0 // 10 ** __decimals__[token0]
            check1 = balance1 // 10 ** __decimals__[token1]
            if check0 == 0 or check1 == 0:
                continue
            if token0 == WETH:
                self._update_max_borrowable_weth(True, address, balance0, fee)
            elif token1 == WETH:
                self._update_max_borrowable_weth(False, address, balance1, fee)
            v1 = token_graph.update_vertex(token0)
            v2 = token_graph.update_vertex(token1)
            pair_object = UniswapV3Pair(address, (token0, token1), fee, tick_spacing)
            token_graph.update_edge(v1, v2, pair_object)
            token_graph.update_edge(v2, v1, pair_object)

            i += 1
        print(f"{i} {type(self).__name__} pairs loaded\n", end='')
