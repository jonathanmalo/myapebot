from typing import Tuple, List, Optional


class BalancerSwap:
    _bone = 10**18
    _max_in_ratio = _bone // 2

    def badd(self, a: int, b: int) -> int:
        c = a + b
        assert c >= 0
        return c

    def bsubSign(self, a: int, b: int) -> Tuple[int, bool]:
        return abs(a - b), a < b

    def bsub(self, a: int, b: int) -> int:
        assert a >= b
        return a - b

    def bmul(self, a: int, b: int) -> int:
        c0 = a * b
        assert a == 0 or c0 // a == b
        c1 = c0 + (self._bone // 2)
        assert c1 >= c0
        c2 = c1 // self._bone
        return c2

    def bdiv(self, a: int, b: int) -> int:
        assert b != 0
        c0 = a * self._bone
        assert a == 0 or c0 // a == self._bone
        c1 = c0 + (b // 2)
        assert c1 >= c0
        c2 = c1 // b
        return c2

    def bpowi(self, a: int, n: int) -> int:
        z = a if n % 2 != 0 else self._bone
        while n != 0:
            n = n // 2
            a = self.bmul(a, a)
            if n % 2 != 0:
                z = self.bmul(z, a)
        return z

    def bpowApprox(self, base: int, exp: int, precision: int) -> int:
        a = exp
        x, xneg = self.bsubSign(base, self._bone)
        term = self._bone
        _sum = term
        negative = False
        i = 1
        while term >= precision:
            bigK = i * self._bone
            c, cneg = self.bsubSign(a, self.bsub(bigK, self._bone))
            term = self.bmul(term, self.bmul(c, x))
            term = self.bdiv(term, bigK)
            if term == 0:
                break

            if xneg:
                negative = not negative
            if cneg:
                negative = not negative
            if negative:
                _sum = self.bsub(_sum, term)
            else:
                _sum = self.badd(_sum, term)

            i += 1

        return _sum

    def bpow(self, base: int, exp: int) -> int:
        assert base >= 1
        assert base <= (2 * self._bone) - 1
        whole = (exp // self._bone) * self._bone
        remain = self.bsub(exp, whole)
        whole_pow = self.bpowi(base, whole // self._bone)
        if remain == 0:
            return whole_pow

        partial_result = self.bpowApprox(base, remain, self._bone // 10**10)

        return self.bmul(whole_pow, partial_result)

    def spot_price(self, balance_in: int, weight_in: int, balance_out: int, weight_out: int, swap_fee: int) -> int:
        numer = self.bdiv(balance_in, weight_in)
        denom = self.bdiv(balance_out, weight_out)
        ratio = self.bdiv(numer, denom)
        scale = self.bdiv(self._bone, self.bsub(self._bone, swap_fee))
        return self.bmul(ratio, scale)

    def swap_exact_amount_out(self, out_amount: int, params: List[int], swap_fee: int) -> Optional[int]:
        bI, bO, wI, wO = params
        max_out = self.bmul(bO, 2 * self._bone - 1)
        if out_amount > max_out:
            return None
        weightRatio = self.bdiv(wI, wO)
        diff = self.bsub(bO, out_amount)
        y = self.bdiv(bO, diff)
        foo = self.bpow(y, weightRatio)
        foo = self.bsub(foo, self._bone)
        in_amount = self.bsub(self._bone, swap_fee)
        in_amount = self.bdiv(self.bmul(bI, foo), in_amount)
        return in_amount

    def swap_exact_amount_in(self, in_amount: int, params: List[int], swap_fee: int) -> int:
        """ swapExactAmountIn and calcOutGivenIn in BMath.sol
        """
        bI, bO, wI, wO = params
        spot_price_before = self.spot_price(bI, wI, bO, wO, swap_fee)
        max_in = self.bmul(bI, self._bone // 2)
        if in_amount > max_in or in_amount <= 222:  # prevent ERR_MATH_APPROX when in_amount == macheps
            return 0
        weight_ratio = self.bdiv(wI, wO)
        adjusted_in = self.bsub(self._bone, swap_fee)
        adjusted_in = self.bmul(in_amount, adjusted_in)
        y = self.bdiv(bI, self.badd(bI, adjusted_in))
        foo = self.bpow(y, weight_ratio)
        bar = self.bsub(self._bone, foo)
        token_amount_out = self.bmul(bO, bar)
        spot_price_after = self.spot_price(bI + in_amount, wI, bO - token_amount_out, wO, swap_fee)
        if spot_price_after < spot_price_before:
            return 0
        else:
            return token_amount_out
