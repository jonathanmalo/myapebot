from typing import List
from eth_typing import ChecksumAddress


class Ape:

    def get_action_flags(self, bribe: int) -> int:
        bribe <<= 128
        weth_to_eth_flag = 0x2
        pay_coinbase_flag = 0x4
        action_flags = bribe + weth_to_eth_flag + pay_coinbase_flag
        return action_flags

    def encode_ape_call(self,
                        call_address: ChecksumAddress,
                        call_data: bytes,
                        gas_cost: int=10**6,
                        eth_value: int=0) -> List[int]:
        assert gas_cost.bit_length() <= 24
        address = int(call_address, 16)
        gas_cost <<= 160
        call_length = len(call_data) // 32
        is_function_call = len(call_data) % 32 == 4
        call_sign_data_shift = int.from_bytes(call_data[:4], 'big') if is_function_call else 0x0
        call_sign_data_shift <<= 184
        offset = 4 if is_function_call else 0
        call_data_as_int_arr = [int.from_bytes(call_data[offset + i * 32:offset + (i + 1) * 32], 'big') for i in range(call_length)]
        call_length <<= 216
        call_info = address + gas_cost + call_length + call_sign_data_shift
        ape_call = [call_info, eth_value] + call_data_as_int_arr
        return ape_call
