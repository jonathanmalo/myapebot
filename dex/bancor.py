from typing import List, Optional


class BancorConversionPath:
    _max_num = 0x200000000000000000000000000000000
    _fixed_1 = 0x080000000000000000000000000000000
    _opt_log_max_val = 0x15bf0a8b1457695355fb8ac404e7a79e3
    _max_precision = 127
    _fixed_2 = 0x100000000000000000000000000000000
    _one = 1
    _max_exp_arr = [0] * 32 + [
        0x1c35fedd14ffffffffffffffffffffffff,
        0x1b0ce43b323fffffffffffffffffffffff,
        0x19f0028ec1ffffffffffffffffffffffff,
        0x18ded91f0e7fffffffffffffffffffffff,
        0x17d8ec7f0417ffffffffffffffffffffff,
        0x16ddc6556cdbffffffffffffffffffffff,
        0x15ecf52776a1ffffffffffffffffffffff,
        0x15060c256cb2ffffffffffffffffffffff,
        0x1428a2f98d72ffffffffffffffffffffff,
        0x13545598e5c23fffffffffffffffffffff,
        0x1288c4161ce1dfffffffffffffffffffff,
        0x11c592761c666fffffffffffffffffffff,
        0x110a688680a757ffffffffffffffffffff,
        0x1056f1b5bedf77ffffffffffffffffffff,
        0x0faadceceeff8bffffffffffffffffffff,
        0x0f05dc6b27edadffffffffffffffffffff,
        0x0e67a5a25da4107fffffffffffffffffff,
        0x0dcff115b14eedffffffffffffffffffff,
        0x0d3e7a392431239fffffffffffffffffff,
        0x0cb2ff529eb71e4fffffffffffffffffff,
        0x0c2d415c3db974afffffffffffffffffff,
        0x0bad03e7d883f69bffffffffffffffffff,
        0x0b320d03b2c343d5ffffffffffffffffff,
        0x0abc25204e02828dffffffffffffffffff,
        0x0a4b16f74ee4bb207fffffffffffffffff,
        0x09deaf736ac1f569ffffffffffffffffff,
        0x0976bd9952c7aa957fffffffffffffffff,
        0x09131271922eaa606fffffffffffffffff,
        0x08b380f3558668c46fffffffffffffffff,
        0x0857ddf0117efa215bffffffffffffffff,
        0x07ffffffffffffffffffffffffffffffff,
        0x07abbf6f6abb9d087fffffffffffffffff,
        0x075af62cbac95f7dfa7fffffffffffffff,
        0x070d7fb7452e187ac13fffffffffffffff,
        0x06c3390ecc8af379295fffffffffffffff,
        0x067c00a3b07ffc01fd6fffffffffffffff,
        0x0637b647c39cbb9d3d27ffffffffffffff,
        0x05f63b1fc104dbd39587ffffffffffffff,
        0x05b771955b36e12f7235ffffffffffffff,
        0x057b3d49dda84556d6f6ffffffffffffff,
        0x054183095b2c8ececf30ffffffffffffff,
        0x050a28be635ca2b888f77fffffffffffff,
        0x04d5156639708c9db33c3fffffffffffff,
        0x04a23105873875bd52dfdfffffffffffff,
        0x0471649d87199aa990756fffffffffffff,
        0x04429a21a029d4c1457cfbffffffffffff,
        0x0415bc6d6fb7dd71af2cb3ffffffffffff,
        0x03eab73b3bbfe282243ce1ffffffffffff,
        0x03c1771ac9fb6b4c18e229ffffffffffff,
        0x0399e96897690418f785257fffffffffff,
        0x0373fc456c53bb779bf0ea9fffffffffff,
        0x034f9e8e490c48e67e6ab8bfffffffffff,
        0x032cbfd4a7adc790560b3337ffffffffff,
        0x030b50570f6e5d2acca94613ffffffffff,
        0x02eb40f9f620fda6b56c2861ffffffffff,
        0x02cc8340ecb0d0f520a6af58ffffffffff,
        0x02af09481380a0a35cf1ba02ffffffffff,
        0x0292c5bdd3b92ec810287b1b3fffffffff,
        0x0277abdcdab07d5a77ac6d6b9fffffffff,
        0x025daf6654b1eaa55fd64df5efffffffff,
        0x0244c49c648baa98192dce88b7ffffffff,
        0x022ce03cd5619a311b2471268bffffffff,
        0x0215f77c045fbe885654a44a0fffffffff,
        0x01ffffffffffffffffffffffffffffffff,
        0x01eaefdbdaaee7421fc4d3ede5ffffffff,
        0x01d6bd8b2eb257df7e8ca57b09bfffffff,
        0x01c35fedd14b861eb0443f7f133fffffff,
        0x01b0ce43b322bcde4a56e8ada5afffffff,
        0x019f0028ec1fff007f5a195a39dfffffff,
        0x018ded91f0e72ee74f49b15ba527ffffff,
        0x017d8ec7f04136f4e5615fd41a63ffffff,
        0x016ddc6556cdb84bdc8d12d22e6fffffff,
        0x015ecf52776a1155b5bd8395814f7fffff,
        0x015060c256cb23b3b3cc3754cf40ffffff,
        0x01428a2f98d728ae223ddab715be3fffff,
        0x013545598e5c23276ccf0ede68034fffff,
        0x01288c4161ce1d6f54b7f61081194fffff,
        0x011c592761c666aa641d5a01a40f17ffff,
        0x0110a688680a7530515f3e6e6cfdcdffff,
        0x01056f1b5bedf75c6bcb2ce8aed428ffff,
        0x00faadceceeff8a0890f3875f008277fff,
        0x00f05dc6b27edad306388a600f6ba0bfff,
        0x00e67a5a25da41063de1495d5b18cdbfff,
        0x00dcff115b14eedde6fc3aa5353f2e4fff,
        0x00d3e7a3924312399f9aae2e0f868f8fff,
        0x00cb2ff529eb71e41582cccd5a1ee26fff,
        0x00c2d415c3db974ab32a51840c0b67edff,
        0x00bad03e7d883f69ad5b0a186184e06bff,
        0x00b320d03b2c343d4829abd6075f0cc5ff,
        0x00abc25204e02828d73c6e80bcdb1a95bf,
        0x00a4b16f74ee4bb2040a1ec6c15fbbf2df,
        0x009deaf736ac1f569deb1b5ae3f36c130f,
        0x00976bd9952c7aa957f5937d790ef65037,
        0x009131271922eaa6064b73a22d0bd4f2bf,
        0x008b380f3558668c46c91c49a2f8e967b9,
        0x00857ddf0117efa215952912839f6473e6,
    ]

    def optimal_log(self, x: int) -> int:
        res, y, z, w = [0] * 4
        fixed_1 = self._fixed_1
        if x >= 0xd3094c70f034de4b96ff7d5b6f99fcd8:
            res += 0x40000000000000000000000000000000
            x = (x * fixed_1) // 0xd3094c70f034de4b96ff7d5b6f99fcd8

        if x >= 0xa45af1e1f40c333b3de1db4dd55f29a7:
            res += 0x20000000000000000000000000000000
            x = (x * fixed_1) // 0xa45af1e1f40c333b3de1db4dd55f29a7

        if x >= 0x910b022db7ae67ce76b441c27035c6a1:
            res += 0x10000000000000000000000000000000
            x = (x * fixed_1) // 0x910b022db7ae67ce76b441c27035c6a1

        if x >= 0x88415abbe9a76bead8d00cf112e4d4a8:
            res += 0x08000000000000000000000000000000
            x = (x * fixed_1) // 0x88415abbe9a76bead8d00cf112e4d4a8

        if x >= 0x84102b00893f64c705e841d5d4064bd3:
            res += 0x04000000000000000000000000000000
            x = (x * fixed_1) // 0x84102b00893f64c705e841d5d4064bd3

        if x >= 0x8204055aaef1c8bd5c3259f4822735a2:
            res += 0x02000000000000000000000000000000
            x = (x * fixed_1) // 0x8204055aaef1c8bd5c3259f4822735a2

        if x >= 0x810100ab00222d861931c15e39b44e99:
            res += 0x01000000000000000000000000000000
            x = (x * fixed_1) // 0x810100ab00222d861931c15e39b44e99

        if x >= 0x808040155aabbbe9451521693554f733:
            res += 0x00800000000000000000000000000000
            x = (x * fixed_1) // 0x808040155aabbbe9451521693554f733

        z = y = x - fixed_1
        w = (y * y) // fixed_1
        res += (z * (0x100000000000000000000000000000000 - y)) // 0x100000000000000000000000000000000
        z = (z * w) // fixed_1
        res += (z * (0x0aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa - y)) // 0x200000000000000000000000000000000
        z = (z * w) // fixed_1
        res += (z * (0x099999999999999999999999999999999 - y)) // 0x300000000000000000000000000000000
        z = (z * w) // fixed_1
        res += (z * (0x092492492492492492492492492492492 - y)) // 0x400000000000000000000000000000000
        z = (z * w) // fixed_1
        res += (z * (0x08e38e38e38e38e38e38e38e38e38e38e - y)) // 0x500000000000000000000000000000000
        z = (z * w) // fixed_1
        res += (z * (0x08ba2e8ba2e8ba2e8ba2e8ba2e8ba2e8b - y)) // 0x600000000000000000000000000000000
        z = (z * w) // fixed_1
        res += (z * (0x089d89d89d89d89d89d89d89d89d89d89 - y)) // 0x700000000000000000000000000000000
        z = (z * w) // fixed_1
        res += (z * (0x088888888888888888888888888888888 - y)) // 0x800000000000000000000000000000000

        return res

    def floor_log2(self, _n: int) -> int:
        res = 0
        if _n < 256:
            while _n > 1:
                _n >>= 1
                res += 1
        else:
            s = 128
            while s > 0:
                if _n >= (1 << s):
                    _n >>= s
                    res |= s
                    s >>= 1

        return res

    def general_log(self, x: int) -> int:
        res = 0
        fixed_2 = self._fixed_2
        fixed_1 = self._fixed_1
        if x >= fixed_2:
            count = self.floor_log2(x // fixed_1)
            x >>= count
            res = count * fixed_1
        if x > fixed_1:
            for i in range(self._max_precision, 0, -1):
                x = (x * x) // fixed_1
                if x >= fixed_2:
                    x >>= 1
                    res += 1 << (i - 1)

        return (res * self._ln2_numerator) // self._ln2_denominator

    def optimal_exp(self, x: int) -> int:
        res, y, z = [0] * 3
        y = x % 0x10000000000000000000000000000000
        z = y
        fixed_1 = self._fixed_1
        z = (z * y) // fixed_1
        res += z * 0x10e1b3be415a0000
        z = (z * y) // fixed_1
        res += z * 0x05a0913f6b1e0000
        z = (z * y) // fixed_1
        res += z * 0x0168244fdac78000
        z = (z * y) // fixed_1
        res += z * 0x004807432bc18000
        z = (z * y) // fixed_1
        res += z * 0x000c0135dca04000
        z = (z * y) // fixed_1
        res += z * 0x0001b707b1cdc000
        z = (z * y) // fixed_1
        res += z * 0x000036e0f639b800
        z = (z * y) // fixed_1
        res += z * 0x00000618fee9f800
        z = (z * y) // fixed_1
        res += z * 0x0000009c197dcc00
        z = (z * y) // fixed_1
        res += z * 0x0000000e30dce400
        z = (z * y) // fixed_1
        res += z * 0x000000012ebd1300
        z = (z * y) // fixed_1
        res += z * 0x0000000017499f00
        z = (z * y) // fixed_1
        res += z * 0x0000000001a9d480
        z = (z * y) // fixed_1
        res += z * 0x00000000001c6380
        z = (z * y) // fixed_1
        res += z * 0x000000000001c638
        z = (z * y) // fixed_1
        res += z * 0x0000000000001ab8
        z = (z * y) // fixed_1
        res += z * 0x000000000000017c
        z = (z * y) // fixed_1
        res += z * 0x0000000000000014
        z = (z * y) // fixed_1
        res += z * 0x0000000000000001
        res = res // 0x21c3677c82b40000 + y + fixed_1

        if (x & 0x010000000000000000000000000000000) != 0:
            res = (res * 0x1c3d6a24ed82218787d624d3e5eba95f9) // 0x18ebef9eac820ae8682b9793ac6d1e776
        if (x & 0x020000000000000000000000000000000) != 0:
            res = (res * 0x18ebef9eac820ae8682b9793ac6d1e778) // 0x1368b2fc6f9609fe7aceb46aa619baed4
        if (x & 0x040000000000000000000000000000000) != 0:
            res = (res * 0x1368b2fc6f9609fe7aceb46aa619baed5) // 0x0bc5ab1b16779be3575bd8f0520a9f21f
        if (x & 0x080000000000000000000000000000000) != 0:
            res = (res * 0x0bc5ab1b16779be3575bd8f0520a9f21e) // 0x0454aaa8efe072e7f6ddbab84b40a55c9
        if (x & 0x100000000000000000000000000000000) != 0:
            res = (res * 0x0454aaa8efe072e7f6ddbab84b40a55c5) // 0x00960aadc109e7a3bf4578099615711ea
        if (x & 0x200000000000000000000000000000000) != 0:
            res = (res * 0x00960aadc109e7a3bf4578099615711d7) // 0x0002bf84208204f5977f9a8cf01fdce3d
        if (x & 0x400000000000000000000000000000000) != 0:
            res = (res * 0x0002bf84208204f5977f9a8cf01fdc307) // 0x0000003c6ab775dd0b95b4cbee7e65d11

        return res

    def general_exp(self, _x: int, _precision: int) -> int:
        xi = _x
        res = 0
        xi = (xi * _x) >> _precision
        res += xi * 0x3442c4e6074a82f1797f72ac0000000
        xi = (xi * _x) >> _precision
        res += xi * 0x116b96f757c380fb287fd0e40000000
        xi = (xi * _x) >> _precision
        res += xi * 0x045ae5bdd5f0e03eca1ff4390000000
        xi = (xi * _x) >> _precision
        res += xi * 0x00defabf91302cd95b9ffda50000000
        xi = (xi * _x) >> _precision
        res += xi * 0x002529ca9832b22439efff9b8000000
        xi = (xi * _x) >> _precision
        res += xi * 0x00054f1cf12bd04e516b6da88000000
        xi = (xi * _x) >> _precision
        res += xi * 0x0000a9e39e257a09ca2d6db51000000
        xi = (xi * _x) >> _precision
        res += xi * 0x000012e066e7b839fa050c309000000
        xi = (xi * _x) >> _precision
        res += xi * 0x000001e33d7d926c329a1ad1a800000
        xi = (xi * _x) >> _precision
        res += xi * 0x0000002bee513bdb4a6b19b5f800000
        xi = (xi * _x) >> _precision
        res += xi * 0x00000003a9316fa79b88eccf2a00000
        xi = (xi * _x) >> _precision
        res += xi * 0x0000000048177ebe1fa812375200000
        xi = (xi * _x) >> _precision
        res += xi * 0x0000000005263fe90242dcbacf00000
        xi = (xi * _x) >> _precision
        res += xi * 0x000000000057e22099c030d94100000
        xi = (xi * _x) >> _precision
        res += xi * 0x0000000000057e22099c030d9410000
        xi = (xi * _x) >> _precision
        res += xi * 0x00000000000052b6b54569976310000
        xi = (xi * _x) >> _precision
        res += xi * 0x00000000000004985f67696bf748000
        xi = (xi * _x) >> _precision
        res += xi * 0x000000000000003dea12ea99e498000
        xi = (xi * _x) >> _precision
        res += xi * 0x00000000000000031880f2214b6e000
        xi = (xi * _x) >> _precision
        res += xi * 0x000000000000000025bcff56eb36000
        xi = (xi * _x) >> _precision
        res += xi * 0x000000000000000001b722e10ab1000
        xi = (xi * _x) >> _precision
        res += xi * 0x0000000000000000001317c70077000
        xi = (xi * _x) >> _precision
        res += xi * 0x00000000000000000000cba84aafa00
        xi = (xi * _x) >> _precision
        res += xi * 0x00000000000000000000082573a0a00
        xi = (xi * _x) >> _precision
        res += xi * 0x00000000000000000000005035ad900
        xi = (xi * _x) >> _precision
        res += xi * 0x000000000000000000000002f881b00
        xi = (xi * _x) >> _precision
        res += xi * 0x0000000000000000000000001b29340
        xi = (xi * _x) >> _precision
        res += xi * 0x00000000000000000000000000efc40
        xi = (xi * _x) >> _precision
        res += xi * 0x0000000000000000000000000007fe0
        xi = (xi * _x) >> _precision
        res += xi * 0x0000000000000000000000000000420
        xi = (xi * _x) >> _precision
        res += xi * 0x0000000000000000000000000000021
        xi = (xi * _x) >> _precision
        res += xi * 0x0000000000000000000000000000001

        return res // 0x688589cc0e9505e2f2fee5580000000 + _x + (self._one << _precision)

    def power(self, base_n: int, base_d: int, exp_n: int, exp_d: int) -> Optional[int]:
        if base_n >= self._max_num:
            return None
        base = (base_n * self._fixed_1) // base_d
        if base < self._opt_log_max_val:
            base_log = self.optimal_log(base)
        else:
            base_log = self.general_log(base)
        base_log_times_exp = (base_log * exp_n) // exp_d
        if base_log_times_exp < self._opt_log_max_val:
            return self.optimial_exp(base_log_times_exp), self._max_precision
        else:
            precision = self.find_pos_in_max_exp_array(base_log_times_exp)
            return self.general_exp(base_log_times_exp >> (self._max_precision - precision), precision), precision

    def convert(self, in_amount: int, params: List[int]) -> int:
        in_reserve, in_weight, out_reserve, out_weight = params
        if in_weight <= 0 or in_weight > self._max_weight or out_weight <= 0 or out_weight > self._max_weight:
            return 0
        if in_weight == out_weight:
            return (out_reserve * in_amount) // (in_reserve + in_amount)
        base_n = in_reserve + in_amount
        result, precision = self.power(base_n, in_reserve, in_weight, out_weight)
        temp1 = out_reserve * result
        temp2 = out_reserve << precision
        return (temp1 - temp2) // result
