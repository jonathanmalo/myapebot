import sys
import datetime

from web3 import Web3
from constants import WETH, ZERO_ADDRESS, TRADE_SET
from geth_client import TIME_UNTIL_NEXT_BLOCK, get_contract, request


CURVE_POOLS = {
    '0xbEbc44782C7dB0a1A60Cb6fe97d0b483032FF1C7': '3Pool',
    # '0xA2B47E3D5c44877cca798226B7B8118F9BFb7A56': 'Compound', # TODO: exchangeRateCurrent altered by refork() results in exchange overestimation
    '0x4f062658EaAF2C1ccf8C8e36D6824CDf41167956': 'GUSD',
    '0x4CA9b3063Ec5866A4B82E437059D2C43d1be596F': 'HBTC',
    '0x3eF6A01A0f81D6046290f3e2A8c5b843e738E604': 'HUSD',
    '0x8474DdbE98F5aA3179B3B3F5942D724aFcdec9f6': 'MUSD', # TODO: exchange resulted in fewer coins for swapping underlying to underlying, although pasts tests
    '0x890f4e345B1dAED0367A877a1612f86A1f86985f': 'UST',
    '0x0f9cb53Ebe405d49A0bbdBD291A65Ff571bC83e1': 'USDN',
    '0x8038C01A0390a8c547446a0b2c18fc9aEFEcc10c': 'DUSD',
    '0x42d7025938bEc20B69cBae5A77421082407f053A': 'USDP',
    '0x3E01dD8a5E1fb3481F0F589056b428Fc308AF0Fb': 'USDK',  # TODO: estimate errors
    # '0x45F783CCE6B7FF23B2ab2D70e416cdb7D6055f51': 'TUSD',
    # '0xA5407eAE9Ba41422680e2e00537571bcC53efBfD': 'SUSD',
    # '0x93054188d876f558f4a66B2EF1d97d16eDf0895B': 'REN',
    # '0x7fC77b5c7614E1533320Ea6DDc2Eb61fa00A9714': 'SBTC',
    '0xA96A65c051bF88B4095Ee1f2451C2A9d43F53Ae2': 'AETH',
    # '0xc5424B857f758E906013F3555Dad202e4bdB4567': 'seth',
    # '0xDC24316b9AE028F1497c275EB9192a3Ea0f67022': 'steth',

    # '0x79a8C46DeA5aDa233ABaFFD40F3A0A2B1e5A4F27': 'busd', # TODO: no liquidity? what is yBUSD?
    # '0xE7a24EF0C5e95Ffb0f6684b813A78F2a3AD7D171': 'linkusd', # TODO: test get_dy error
    # '0x06364f10B501e868329afBc005b3492902d6C763': 'pax',  # TODO: test get_dy error
    # '0xC25099792E9349C7DD09759744ea681C7de2cb66': 'tbtc',  # TODO: test get_dy error
    # '0x52EA46506B9CC5Ef470C5bf89f17Dc28bB35D85C': 'usdt',  # TODO: obsolete?
    # '0x071c661B4DeefB59E2a3DdB20Db036821eeE8F4b': 'bbtc',  # no liquidity
    # '0xd81dA8D904b52208541Bade1bD6595D8a251F8dd': 'tbtc',  # TODO: determine safety, lower liquidity then first
    # '0x7F55DDe206dbAD629C080068923b36fe9D6bDBeF': 'tbtc',  # TODO: determine safety, lower liquidity then first
    # '0x0Ce6a5fF5217e38315f87032CF90686C96627CAA': 'eurs',  # TODO: test get_dy error
    # '0xEB16Ae0052ed37f479f7fe63849198Df1765a733': 'saave', # TODO: test get_dy error
    # '0xDeBF20617708857ebe4F679508E7b7863a8A8EeE': 'aave',  # TODO: test get_dy error
    # '0x2dded6Da1BF5DBdF597C45fcFaa3194e53EcfeAF': '', # curve ironbank pool    
}

TO_ADDRESS = {name: address for address, name in CURVE_POOLS.items()}

CURVE_ERRORS = {
    '0x0f9cb53Ebe405d49A0bbdBD291A65Ff571bC83e1': {('0x674C6Ad92Fd080e4004b2312b45f796a192D27a0', '0x6B175474E89094C44Da98b954EedeAC495271d0F'): 2.0080701158820523e-06,
                                                   ('0x674C6Ad92Fd080e4004b2312b45f796a192D27a0', '0x6c3F90f043a72FA612cbac8115EE7e52BDe6E490'): 0,
                                                   ('0x674C6Ad92Fd080e4004b2312b45f796a192D27a0', '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48'): 1.9856669231380446e-06,
                                                   ('0x674C6Ad92Fd080e4004b2312b45f796a192D27a0', '0xdAC17F958D2ee523a2206206994597C13D831ec7'): 2.033049504992552e-06,
                                                   ('0x6B175474E89094C44Da98b954EedeAC495271d0F', '0x674C6Ad92Fd080e4004b2312b45f796a192D27a0'): -2.5166884937464584e-05,
                                                   ('0x6B175474E89094C44Da98b954EedeAC495271d0F', '0x6c3F90f043a72FA612cbac8115EE7e52BDe6E490'): None,
                                                   ('0x6B175474E89094C44Da98b954EedeAC495271d0F', '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48'): 0,
                                                   ('0x6B175474E89094C44Da98b954EedeAC495271d0F', '0xdAC17F958D2ee523a2206206994597C13D831ec7'): 0,
                                                   ('0x6c3F90f043a72FA612cbac8115EE7e52BDe6E490', '0x674C6Ad92Fd080e4004b2312b45f796a192D27a0'): 0,
                                                   ('0x6c3F90f043a72FA612cbac8115EE7e52BDe6E490', '0x6B175474E89094C44Da98b954EedeAC495271d0F'): None,
                                                   ('0x6c3F90f043a72FA612cbac8115EE7e52BDe6E490', '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48'): None,
                                                   ('0x6c3F90f043a72FA612cbac8115EE7e52BDe6E490', '0xdAC17F958D2ee523a2206206994597C13D831ec7'): None,
                                                   ('0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48', '0x674C6Ad92Fd080e4004b2312b45f796a192D27a0'): -1.0596490099108805e-05,
                                                   ('0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48', '0x6B175474E89094C44Da98b954EedeAC495271d0F'): 0,
                                                   ('0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48', '0x6c3F90f043a72FA612cbac8115EE7e52BDe6E490'): None,
                                                   ('0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48', '0xdAC17F958D2ee523a2206206994597C13D831ec7'): 0,
                                                   ('0xdAC17F958D2ee523a2206206994597C13D831ec7', '0x674C6Ad92Fd080e4004b2312b45f796a192D27a0'): -3.932122213561974e-05,
                                                   ('0xdAC17F958D2ee523a2206206994597C13D831ec7', '0x6B175474E89094C44Da98b954EedeAC495271d0F'): -2.2425292001724874e-12,
                                                   ('0xdAC17F958D2ee523a2206206994597C13D831ec7', '0x6c3F90f043a72FA612cbac8115EE7e52BDe6E490'): None,
                                                   ('0xdAC17F958D2ee523a2206206994597C13D831ec7', '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48'): 0},
    '0x3E01dD8a5E1fb3481F0F589056b428Fc308AF0Fb': {('0x1c48f86ae57291F7686349F12601910BD8D470bb', '0x6B175474E89094C44Da98b954EedeAC495271d0F'): False,
                                                   ('0x1c48f86ae57291F7686349F12601910BD8D470bb', '0x6c3F90f043a72FA612cbac8115EE7e52BDe6E490'): False,
                                                   ('0x1c48f86ae57291F7686349F12601910BD8D470bb', '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48'): False,
                                                   ('0x1c48f86ae57291F7686349F12601910BD8D470bb', '0xdAC17F958D2ee523a2206206994597C13D831ec7'): False,
                                                   ('0x6B175474E89094C44Da98b954EedeAC495271d0F', '0x1c48f86ae57291F7686349F12601910BD8D470bb'): -2.7115825854355432e-05,
                                                   ('0x6B175474E89094C44Da98b954EedeAC495271d0F', '0x6c3F90f043a72FA612cbac8115EE7e52BDe6E490'): None,
                                                   ('0x6B175474E89094C44Da98b954EedeAC495271d0F', '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48'): 1.3454741371526184e-08,
                                                   ('0x6B175474E89094C44Da98b954EedeAC495271d0F', '0xdAC17F958D2ee523a2206206994597C13D831ec7'): -9.9615043392674e-10,
                                                   ('0x6c3F90f043a72FA612cbac8115EE7e52BDe6E490', '0x1c48f86ae57291F7686349F12601910BD8D470bb'): 0,
                                                   ('0x6c3F90f043a72FA612cbac8115EE7e52BDe6E490', '0x6B175474E89094C44Da98b954EedeAC495271d0F'): None,
                                                   ('0x6c3F90f043a72FA612cbac8115EE7e52BDe6E490', '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48'): None,
                                                   ('0x6c3F90f043a72FA612cbac8115EE7e52BDe6E490', '0xdAC17F958D2ee523a2206206994597C13D831ec7'): None,
                                                   ('0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48', '0x1c48f86ae57291F7686349F12601910BD8D470bb'): -1.0596050671513866e-05,
                                                   ('0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48', '0x6B175474E89094C44Da98b954EedeAC495271d0F'): -1.3464611094533291e-08,
                                                   ('0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48', '0x6c3F90f043a72FA612cbac8115EE7e52BDe6E490'): None,
                                                   ('0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48', '0xdAC17F958D2ee523a2206206994597C13D831ec7'): -1.3476397612414785e-08,
                                                   ('0xdAC17F958D2ee523a2206206994597C13D831ec7', '0x1c48f86ae57291F7686349F12601910BD8D470bb'): -4.3221250970914066e-05,
                                                   ('0xdAC17F958D2ee523a2206206994597C13D831ec7', '0x6B175474E89094C44Da98b954EedeAC495271d0F'): 1.1371380274304203e-09,
                                                   ('0xdAC17F958D2ee523a2206206994597C13D831ec7', '0x6c3F90f043a72FA612cbac8115EE7e52BDe6E490'): None,
                                                   ('0xdAC17F958D2ee523a2206206994597C13D831ec7', '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48'): 1.2949600581872173e-08},
    '0x3eF6A01A0f81D6046290f3e2A8c5b843e738E604': {('0x6B175474E89094C44Da98b954EedeAC495271d0F', '0x6c3F90f043a72FA612cbac8115EE7e52BDe6E490'): None,
                                                   ('0x6B175474E89094C44Da98b954EedeAC495271d0F', '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48'): 9.96647521418268e-10,
                                                   ('0x6B175474E89094C44Da98b954EedeAC495271d0F', '0xdAC17F958D2ee523a2206206994597C13D831ec7'): 0,
                                                   ('0x6B175474E89094C44Da98b954EedeAC495271d0F', '0xdF574c24545E5FfEcb9a659c229253D4111d87e1'): -2.3403410298392087e-05,
                                                   ('0x6c3F90f043a72FA612cbac8115EE7e52BDe6E490', '0x6B175474E89094C44Da98b954EedeAC495271d0F'): None,
                                                   ('0x6c3F90f043a72FA612cbac8115EE7e52BDe6E490', '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48'): None,
                                                   ('0x6c3F90f043a72FA612cbac8115EE7e52BDe6E490', '0xdAC17F958D2ee523a2206206994597C13D831ec7'): None,
                                                   ('0x6c3F90f043a72FA612cbac8115EE7e52BDe6E490', '0xdF574c24545E5FfEcb9a659c229253D4111d87e1'): None,
                                                   ('0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48', '0x6B175474E89094C44Da98b954EedeAC495271d0F'): -8.221381978005782e-10,
                                                   ('0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48', '0x6c3F90f043a72FA612cbac8115EE7e52BDe6E490'): None,
                                                   ('0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48', '0xdAC17F958D2ee523a2206206994597C13D831ec7'): -9.982516625373578e-10,
                                                   ('0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48', '0xdF574c24545E5FfEcb9a659c229253D4111d87e1'): -1.05963858576489e-05,
                                                   ('0xdAC17F958D2ee523a2206206994597C13D831ec7', '0x6B175474E89094C44Da98b954EedeAC495271d0F'): 6.804038391868356e-11,
                                                   ('0xdAC17F958D2ee523a2206206994597C13D831ec7', '0x6c3F90f043a72FA612cbac8115EE7e52BDe6E490'): None,
                                                   ('0xdAC17F958D2ee523a2206206994597C13D831ec7', '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48'): 4.980615670428705e-10,
                                                   ('0xdAC17F958D2ee523a2206206994597C13D831ec7', '0xdF574c24545E5FfEcb9a659c229253D4111d87e1'): -3.765719458241843e-05,
                                                   ('0xdF574c24545E5FfEcb9a659c229253D4111d87e1', '0x6B175474E89094C44Da98b954EedeAC495271d0F'): 1.1996465897404586e-07,
                                                   ('0xdF574c24545E5FfEcb9a659c229253D4111d87e1', '0x6c3F90f043a72FA612cbac8115EE7e52BDe6E490'): 0,
                                                   ('0xdF574c24545E5FfEcb9a659c229253D4111d87e1', '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48'): 1.9853425108008054e-06,
                                                   ('0xdF574c24545E5FfEcb9a659c229253D4111d87e1', '0xdAC17F958D2ee523a2206206994597C13D831ec7'): 2.4391889988856256e-07},
    '0x42d7025938bEc20B69cBae5A77421082407f053A': {('0x1456688345527bE1f37E9e627DA0837D6f08C925', '0x6B175474E89094C44Da98b954EedeAC495271d0F'): 0,
                                                   ('0x1456688345527bE1f37E9e627DA0837D6f08C925', '0x6c3F90f043a72FA612cbac8115EE7e52BDe6E490'): 0,
                                                   ('0x1456688345527bE1f37E9e627DA0837D6f08C925', '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48'): None,
                                                   ('0x1456688345527bE1f37E9e627DA0837D6f08C925', '0xdAC17F958D2ee523a2206206994597C13D831ec7'): None,
                                                   ('0x6B175474E89094C44Da98b954EedeAC495271d0F', '0x1456688345527bE1f37E9e627DA0837D6f08C925'): -2.7116952773678932e-05,
                                                   ('0x6B175474E89094C44Da98b954EedeAC495271d0F', '0x6c3F90f043a72FA612cbac8115EE7e52BDe6E490'): None,
                                                   ('0x6B175474E89094C44Da98b954EedeAC495271d0F', '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48'): 1.3454741371526184e-08,
                                                   ('0x6B175474E89094C44Da98b954EedeAC495271d0F', '0xdAC17F958D2ee523a2206206994597C13D831ec7'): -9.9615043392674e-10,
                                                   ('0x6c3F90f043a72FA612cbac8115EE7e52BDe6E490', '0x1456688345527bE1f37E9e627DA0837D6f08C925'): 0,
                                                   ('0x6c3F90f043a72FA612cbac8115EE7e52BDe6E490', '0x6B175474E89094C44Da98b954EedeAC495271d0F'): None,
                                                   ('0x6c3F90f043a72FA612cbac8115EE7e52BDe6E490', '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48'): None,
                                                   ('0x6c3F90f043a72FA612cbac8115EE7e52BDe6E490', '0xdAC17F958D2ee523a2206206994597C13D831ec7'): None,
                                                   ('0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48', '0x1456688345527bE1f37E9e627DA0837D6f08C925'): -1.0596490114640351e-05,
                                                   ('0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48', '0x6B175474E89094C44Da98b954EedeAC495271d0F'): -1.3464611094533291e-08,
                                                   ('0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48', '0x6c3F90f043a72FA612cbac8115EE7e52BDe6E490'): None,
                                                   ('0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48', '0xdAC17F958D2ee523a2206206994597C13D831ec7'): -1.3476397612414785e-08,
                                                   ('0xdAC17F958D2ee523a2206206994597C13D831ec7', '0x1456688345527bE1f37E9e627DA0837D6f08C925'): -4.322304818361029e-05,
                                                   ('0xdAC17F958D2ee523a2206206994597C13D831ec7', '0x6B175474E89094C44Da98b954EedeAC495271d0F'): 1.1371380274304203e-09,
                                                   ('0xdAC17F958D2ee523a2206206994597C13D831ec7', '0x6c3F90f043a72FA612cbac8115EE7e52BDe6E490'): None,
                                                   ('0xdAC17F958D2ee523a2206206994597C13D831ec7', '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48'): 1.2949600581872173e-08},
    '0x4CA9b3063Ec5866A4B82E437059D2C43d1be596F': {('0x0316EB71485b0Ab14103307bf65a021042c6d380', '0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599'): 0,
                                                   ('0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599', '0x0316EB71485b0Ab14103307bf65a021042c6d380'): 0},
    '0x4f062658EaAF2C1ccf8C8e36D6824CDf41167956': {('0x056Fd409E1d7A124BD7017459dFEa2F387b6d5Cd', '0x6B175474E89094C44Da98b954EedeAC495271d0F'): 1.3838383402078198e-08,
                                                   ('0x056Fd409E1d7A124BD7017459dFEa2F387b6d5Cd', '0x6c3F90f043a72FA612cbac8115EE7e52BDe6E490'): 0,
                                                   ('0x056Fd409E1d7A124BD7017459dFEa2F387b6d5Cd', '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48'): 1.985837084339381e-06,
                                                   ('0x056Fd409E1d7A124BD7017459dFEa2F387b6d5Cd', '0xdAC17F958D2ee523a2206206994597C13D831ec7'): 3.166421775774064e-08,
                                                   ('0x6B175474E89094C44Da98b954EedeAC495271d0F', '0x056Fd409E1d7A124BD7017459dFEa2F387b6d5Cd'): -2.49231121988665e-05,
                                                   ('0x6B175474E89094C44Da98b954EedeAC495271d0F', '0x6c3F90f043a72FA612cbac8115EE7e52BDe6E490'): None,
                                                   ('0x6B175474E89094C44Da98b954EedeAC495271d0F', '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48'): 0,
                                                   ('0x6B175474E89094C44Da98b954EedeAC495271d0F', '0xdAC17F958D2ee523a2206206994597C13D831ec7'): 0,
                                                   ('0x6c3F90f043a72FA612cbac8115EE7e52BDe6E490', '0x056Fd409E1d7A124BD7017459dFEa2F387b6d5Cd'): None,
                                                   ('0x6c3F90f043a72FA612cbac8115EE7e52BDe6E490', '0x6B175474E89094C44Da98b954EedeAC495271d0F'): None,
                                                   ('0x6c3F90f043a72FA612cbac8115EE7e52BDe6E490', '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48'): None,
                                                   ('0x6c3F90f043a72FA612cbac8115EE7e52BDe6E490', '0xdAC17F958D2ee523a2206206994597C13D831ec7'): None,
                                                   ('0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48', '0x056Fd409E1d7A124BD7017459dFEa2F387b6d5Cd'): -9.990259496990435e-06,
                                                   ('0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48', '0x6B175474E89094C44Da98b954EedeAC495271d0F'): -9.752249302217753e-11,
                                                   ('0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48', '0x6c3F90f043a72FA612cbac8115EE7e52BDe6E490'): None,
                                                   ('0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48', '0xdAC17F958D2ee523a2206206994597C13D831ec7'): 0,
                                                   ('0xdAC17F958D2ee523a2206206994597C13D831ec7', '0x056Fd409E1d7A124BD7017459dFEa2F387b6d5Cd'): -3.487393074037355e-05,
                                                   ('0xdAC17F958D2ee523a2206206994597C13D831ec7', '0x6B175474E89094C44Da98b954EedeAC495271d0F'): 6.763323419463181e-12,
                                                   ('0xdAC17F958D2ee523a2206206994597C13D831ec7', '0x6c3F90f043a72FA612cbac8115EE7e52BDe6E490'): None,
                                                   ('0xdAC17F958D2ee523a2206206994597C13D831ec7', '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48'): 0},
    '0x8038C01A0390a8c547446a0b2c18fc9aEFEcc10c': {('0x5BC25f649fc4e26069dDF4cF4010F9f706c23831', '0x6B175474E89094C44Da98b954EedeAC495271d0F'): 2.2967299922950524e-06,
                                                   ('0x5BC25f649fc4e26069dDF4cF4010F9f706c23831', '0x6c3F90f043a72FA612cbac8115EE7e52BDe6E490'): 0,
                                                   ('0x5BC25f649fc4e26069dDF4cF4010F9f706c23831', '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48'): 1.985794402912764e-06,
                                                   ('0x5BC25f649fc4e26069dDF4cF4010F9f706c23831', '0xdAC17F958D2ee523a2206206994597C13D831ec7'): 2.6100117927888096e-06,
                                                   ('0x6B175474E89094C44Da98b954EedeAC495271d0F', '0x5BC25f649fc4e26069dDF4cF4010F9f706c23831'): -2.5455513997408586e-05,
                                                   ('0x6B175474E89094C44Da98b954EedeAC495271d0F', '0x6c3F90f043a72FA612cbac8115EE7e52BDe6E490'): None,
                                                   ('0x6B175474E89094C44Da98b954EedeAC495271d0F', '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48'): 0,
                                                   ('0x6B175474E89094C44Da98b954EedeAC495271d0F', '0xdAC17F958D2ee523a2206206994597C13D831ec7'): 4.980752162191333e-10,
                                                   ('0x6c3F90f043a72FA612cbac8115EE7e52BDe6E490', '0x5BC25f649fc4e26069dDF4cF4010F9f706c23831'): 0,
                                                   ('0x6c3F90f043a72FA612cbac8115EE7e52BDe6E490', '0x6B175474E89094C44Da98b954EedeAC495271d0F'): None,
                                                   ('0x6c3F90f043a72FA612cbac8115EE7e52BDe6E490', '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48'): None,
                                                   ('0x6c3F90f043a72FA612cbac8115EE7e52BDe6E490', '0xdAC17F958D2ee523a2206206994597C13D831ec7'): None,
                                                   ('0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48', '0x5BC25f649fc4e26069dDF4cF4010F9f706c23831'): -1.0596470849195652e-05,
                                                   ('0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48', '0x6B175474E89094C44Da98b954EedeAC495271d0F'): 0,
                                                   ('0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48', '0x6c3F90f043a72FA612cbac8115EE7e52BDe6E490'): None,
                                                   ('0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48', '0xdAC17F958D2ee523a2206206994597C13D831ec7'): 0,
                                                   ('0xdAC17F958D2ee523a2206206994597C13D831ec7', '0x5BC25f649fc4e26069dDF4cF4010F9f706c23831'): -3.989874988049572e-05,
                                                   ('0xdAC17F958D2ee523a2206206994597C13D831ec7', '0x6B175474E89094C44Da98b954EedeAC495271d0F'): -3.2277945350071805e-11,
                                                   ('0xdAC17F958D2ee523a2206206994597C13D831ec7', '0x6c3F90f043a72FA612cbac8115EE7e52BDe6E490'): None,
                                                   ('0xdAC17F958D2ee523a2206206994597C13D831ec7', '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48'): 0},
    '0x8474DdbE98F5aA3179B3B3F5942D724aFcdec9f6': {('0x6B175474E89094C44Da98b954EedeAC495271d0F', '0x6c3F90f043a72FA612cbac8115EE7e52BDe6E490'): None,
                                                   ('0x6B175474E89094C44Da98b954EedeAC495271d0F', '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48'): 0,
                                                   ('0x6B175474E89094C44Da98b954EedeAC495271d0F', '0xdAC17F958D2ee523a2206206994597C13D831ec7'): 0,
                                                   ('0x6B175474E89094C44Da98b954EedeAC495271d0F', '0xe2f2a5C287993345a840Db3B0845fbC70f5935a5'): -2.323849980962563e-05,
                                                   ('0x6c3F90f043a72FA612cbac8115EE7e52BDe6E490', '0x6B175474E89094C44Da98b954EedeAC495271d0F'): None,
                                                   ('0x6c3F90f043a72FA612cbac8115EE7e52BDe6E490', '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48'): None,
                                                   ('0x6c3F90f043a72FA612cbac8115EE7e52BDe6E490', '0xdAC17F958D2ee523a2206206994597C13D831ec7'): None,
                                                   ('0x6c3F90f043a72FA612cbac8115EE7e52BDe6E490', '0xe2f2a5C287993345a840Db3B0845fbC70f5935a5'): 0,
                                                   ('0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48', '0x6B175474E89094C44Da98b954EedeAC495271d0F'): -2.601104992604217e-10,
                                                   ('0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48', '0x6c3F90f043a72FA612cbac8115EE7e52BDe6E490'): None,
                                                   ('0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48', '0xdAC17F958D2ee523a2206206994597C13D831ec7'): -4.991258310195524e-10,
                                                   ('0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48', '0xe2f2a5C287993345a840Db3B0845fbC70f5935a5'): -1.0596467910434865e-05,
                                                   ('0xdAC17F958D2ee523a2206206994597C13D831ec7', '0x6B175474E89094C44Da98b954EedeAC495271d0F'): 2.0512568159282734e-11,
                                                   ('0xdAC17F958D2ee523a2206206994597C13D831ec7', '0x6c3F90f043a72FA612cbac8115EE7e52BDe6E490'): None,
                                                   ('0xdAC17F958D2ee523a2206206994597C13D831ec7', '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48'): 0,
                                                   ('0xdAC17F958D2ee523a2206206994597C13D831ec7', '0xe2f2a5C287993345a840Db3B0845fbC70f5935a5'): -3.741008690523408e-05,
                                                   ('0xe2f2a5C287993345a840Db3B0845fbC70f5935a5', '0x6B175474E89094C44Da98b954EedeAC495271d0F'): 3.765080733602504e-08,
                                                   ('0xe2f2a5C287993345a840Db3B0845fbC70f5935a5', '0x6c3F90f043a72FA612cbac8115EE7e52BDe6E490'): 0,
                                                   ('0xe2f2a5C287993345a840Db3B0845fbC70f5935a5', '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48'): 1.9858536784178437e-06,
                                                   ('0xe2f2a5C287993345a840Db3B0845fbC70f5935a5', '0xdAC17F958D2ee523a2206206994597C13D831ec7'): 7.937205127264575e-08},
    '0x890f4e345B1dAED0367A877a1612f86A1f86985f': {('0x6B175474E89094C44Da98b954EedeAC495271d0F', '0x6c3F90f043a72FA612cbac8115EE7e52BDe6E490'): None,
                                                   ('0x6B175474E89094C44Da98b954EedeAC495271d0F', '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48'): 0,
                                                   ('0x6B175474E89094C44Da98b954EedeAC495271d0F', '0xa47c8bf37f92aBed4A126BDA807A7b7498661acD'): -2.5192005340658907e-05,
                                                   ('0x6B175474E89094C44Da98b954EedeAC495271d0F', '0xdAC17F958D2ee523a2206206994597C13D831ec7'): 0,
                                                   ('0x6c3F90f043a72FA612cbac8115EE7e52BDe6E490', '0x6B175474E89094C44Da98b954EedeAC495271d0F'): None,
                                                   ('0x6c3F90f043a72FA612cbac8115EE7e52BDe6E490', '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48'): None,
                                                   ('0x6c3F90f043a72FA612cbac8115EE7e52BDe6E490', '0xa47c8bf37f92aBed4A126BDA807A7b7498661acD'): 0,
                                                   ('0x6c3F90f043a72FA612cbac8115EE7e52BDe6E490', '0xdAC17F958D2ee523a2206206994597C13D831ec7'): None,
                                                   ('0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48', '0x6B175474E89094C44Da98b954EedeAC495271d0F'): 0,
                                                   ('0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48', '0x6c3F90f043a72FA612cbac8115EE7e52BDe6E490'): None,
                                                   ('0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48', '0xa47c8bf37f92aBed4A126BDA807A7b7498661acD'): -1.0596486804958023e-05,
                                                   ('0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48', '0xdAC17F958D2ee523a2206206994597C13D831ec7'): 0,
                                                   ('0xa47c8bf37f92aBed4A126BDA807A7b7498661acD', '0x6B175474E89094C44Da98b954EedeAC495271d0F'): 2.033197022396098e-06,
                                                   ('0xa47c8bf37f92aBed4A126BDA807A7b7498661acD', '0x6c3F90f043a72FA612cbac8115EE7e52BDe6E490'): 0,
                                                   ('0xa47c8bf37f92aBed4A126BDA807A7b7498661acD', '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48'): 1.9855032613494093e-06,
                                                   ('0xa47c8bf37f92aBed4A126BDA807A7b7498661acD', '0xdAC17F958D2ee523a2206206994597C13D831ec7'): 2.083090938497076e-06,
                                                   ('0xdAC17F958D2ee523a2206206994597C13D831ec7', '0x6B175474E89094C44Da98b954EedeAC495271d0F'): -4.85700819054708e-12,
                                                   ('0xdAC17F958D2ee523a2206206994597C13D831ec7', '0x6c3F90f043a72FA612cbac8115EE7e52BDe6E490'): None,
                                                   ('0xdAC17F958D2ee523a2206206994597C13D831ec7', '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48'): 0,
                                                   ('0xdAC17F958D2ee523a2206206994597C13D831ec7', '0xa47c8bf37f92aBed4A126BDA807A7b7498661acD'): -3.937148808742031e-05},
    '0xA2B47E3D5c44877cca798226B7B8118F9BFb7A56': {('0x39AA39c021dfbaE8faC545936693aC917d5E7563', '0x5d3a536E4D6DbD6114cc1Ead35777bAB948E3643'): -3.0274478114835957e-07,
                                                   ('0x39AA39c021dfbaE8faC545936693aC917d5E7563', '0x6B175474E89094C44Da98b954EedeAC495271d0F'): None,
                                                   ('0x39AA39c021dfbaE8faC545936693aC917d5E7563', '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48'): None,
                                                   ('0x5d3a536E4D6DbD6114cc1Ead35777bAB948E3643', '0x39AA39c021dfbaE8faC545936693aC917d5E7563'): 3.0274461012027097e-07,
                                                   ('0x5d3a536E4D6DbD6114cc1Ead35777bAB948E3643', '0x6B175474E89094C44Da98b954EedeAC495271d0F'): None,
                                                   ('0x5d3a536E4D6DbD6114cc1Ead35777bAB948E3643', '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48'): None,
                                                   ('0x6B175474E89094C44Da98b954EedeAC495271d0F', '0x39AA39c021dfbaE8faC545936693aC917d5E7563'): None,
                                                   ('0x6B175474E89094C44Da98b954EedeAC495271d0F', '0x5d3a536E4D6DbD6114cc1Ead35777bAB948E3643'): None,
                                                   ('0x6B175474E89094C44Da98b954EedeAC495271d0F', '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48'): -9.968000425992466e-10,
                                                   ('0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48', '0x39AA39c021dfbaE8faC545936693aC917d5E7563'): None,
                                                   ('0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48', '0x5d3a536E4D6DbD6114cc1Ead35777bAB948E3643'): None,
                                                   ('0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48', '0x6B175474E89094C44Da98b954EedeAC495271d0F'): 7.052515165327776e-10},
    # use WETH instead of ETH here, although we trade ETH
    '0xA96A65c051bF88B4095Ee1f2451C2A9d43F53Ae2': {('0xE95A203B1a91a908F9B9CE46459d101078c2c3cb', WETH): 0,
                                                   (WETH, '0xE95A203B1a91a908F9B9CE46459d101078c2c3cb'): 0},
    '0xbEbc44782C7dB0a1A60Cb6fe97d0b483032FF1C7': {('0x6B175474E89094C44Da98b954EedeAC495271d0F', '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48'): 0,
                                                   ('0x6B175474E89094C44Da98b954EedeAC495271d0F', '0xdAC17F958D2ee523a2206206994597C13D831ec7'): 0,
                                                   ('0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48', '0x6B175474E89094C44Da98b954EedeAC495271d0F'): 0,
                                                   ('0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48', '0xdAC17F958D2ee523a2206206994597C13D831ec7'): 0,
                                                   ('0xdAC17F958D2ee523a2206206994597C13D831ec7', '0x6B175474E89094C44Da98b954EedeAC495271d0F'): 0,
                                                   ('0xdAC17F958D2ee523a2206206994597C13D831ec7', '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48'): 0}
}

mode_index = sys.argv.index('-m') if sys.argv.index('-m') > -1 else sys.argv.index('--mode')
__test_mode__ = sys.argv[mode_index + 1] != 'live'


address_provider = get_contract('0x0000000022d53366457f9d5e68ec105046fc4383', ganache=__test_mode__)
curve_provider = address_provider.functions
curve_pool_info_address = curve_provider.get_address(1).call()
CURVE_POOL_INFO = get_contract(curve_pool_info_address, ganache=__test_mode__)
registry_address = curve_provider.get_registry().call()
CURVE_REGISTRY = get_contract(registry_address, ganache=__test_mode__)
CURVE_EXCHANGE = curve_provider.get_address(2).call()

CURVE_CONTRACTS = {address: get_contract(address, ganache=__test_mode__) for address in CURVE_POOLS.keys()}
CURVE_TOKENS = {address: CURVE_REGISTRY.functions.get_lp_token(address).call() for address in CURVE_POOLS.keys()}
CURVE_TOKEN_CONTRACTS = {pool_address: get_contract(token_address, ganache=__test_mode__) for pool_address, token_address in CURVE_TOKENS.items()}
USDT = get_contract(TRADE_SET['USDT'], ganache=__test_mode__)
CTOKENS = ['0x5d3a536E4D6DbD6114cc1Ead35777bAB948E3643', '0x39AA39c021dfbaE8faC545936693aC917d5E7563']
CTOKEN_CONTRACTS = [get_contract(a, ganache=__test_mode__) for a in CTOKENS]


class BaseCurvePool:

    N_COINS = None
    FEE_DENOMINATOR = 10 ** 10
    LENDING_PRECISION = 10 ** 18
    PRECISION = 10 ** 18  # The precision to convert to

    def set_balances(self, block, pool):
        self.balances = [pool.functions.balances(i).call(block_identifier=block) for i in range(self.N_COINS)]

    def set_fees(self, block, pool):
        self.fee = pool.functions.fee().call(block_identifier=block)
        self.admin_fee = pool.functions.admin_fee().call(block_identifier=block)

    def set_As(self, block, pool):
        self.initial_A = pool.functions.initial_A().call(block_identifier=block)
        self.future_A = pool.functions.future_A().call(block_identifier=block)
        self.initial_A_time = pool.functions.initial_A_time().call(block_identifier=block)
        self.future_A_time = pool.functions.future_A_time().call(block_identifier=block)

    def set_timestamp(self):
        # inherently innacurate
        # timestamp is set as close as possible to future block timestamp
        self.block_timestamp = int(datetime.datetime.utcnow().timestamp()) + TIME_UNTIL_NEXT_BLOCK

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
        for _x in xp:
            S += _x
        if S == 0:
            return 0
        Dprev = 0
        D = S
        Ann = amp * self.N_COINS
        for _i in range(255):
            D_P = D
            for _x in xp:
                D_P = D_P * D // (_x * self.N_COINS)  # If division by 0, this will be borked: only withdrawal will work. And that is good
            Dprev = D
            D = (Ann * S + D_P * self.N_COINS) * D // ((Ann - 1) * D + (self.N_COINS + 1) * D_P)
            # Equality with the precision of 1
            if D > Dprev:
                if D - Dprev <= 1:
                    break
            else:
                if Dprev - D <= 1:
                    break
        return D

    def _A(self):
        """
        Handle ramping A up or down
        """
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

    def get_y(self, i, j, x, xp_):
        # x in the input is converted to the same price/precision

        assert i != j       # dev: same coin
        assert j >= 0       # dev: j below zero
        assert j < self.N_COINS  # dev: j above N_COINS

        # should be unreachable, but good for safety
        assert i >= 0
        assert i < self.N_COINS

        amp = self._A()
        D = self.get_D(xp_, amp)
        c = D
        S_ = 0
        Ann = amp * self.N_COINS

        _x = 0
        for _i in range(self.N_COINS):
            if _i == i:
                _x = x
            elif _i != j:
                _x = xp_[_i]
            else:
                continue
            S_ += _x
            c = c * D // (_x * self.N_COINS)
        c = c * D // (Ann * self.N_COINS)
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


class StableSwap3Pool(BaseCurvePool):

    N_COINS = 3
    PRECISION_MUL = [1, 1000000000000, 1000000000000]
    RATES = [1000000000000000000, 1000000000000000000000000000000, 1000000000000000000000000000000]
    FEE_INDEX = 2

    def __init__(self, block: int):
        address = TO_ADDRESS['3Pool']
        pool = CURVE_CONTRACTS[address]
        self.set_balances(block, pool)
        self.initial_balances = self.balances
        self.set_fees(block, pool)
        self.set_As(block, pool)
        self.set_timestamp()
        self.usdt_basis_points_rate = USDT.functions.basisPointsRate().call(block_identifier=block)
        self.usdt_max_fee = USDT.functions.maximumFee().call(block_identifier=block)
        self.total_pool_token_supply = CURVE_TOKEN_CONTRACTS[address].functions.totalSupply().call(block_identifier=block)
        self.virtual_price = pool.functions.get_virtual_price().call(block_identifier=block)

    def reset_balances(self):
        self.balances = self.initial_balances

    def dx_w_fee(self, dx):
        fee = dx * self.usdt_basis_points_rate // 10000
        fee = min(fee, self.usdt_max_fee)
        return dx - fee

    def exchange(self, i, j, dx):
        rates = self.RATES

        old_balances = self.balances
        xp = self._xp_mem(old_balances)

        # Handling an unexpected charge of a fee on transfer (USDT, PAXG)
        if i == self.FEE_INDEX:
            dx_w_fee = self.dx_w_fee(dx)
        else:
            dx_w_fee = dx

        x = xp[i] + dx_w_fee * rates[i] // self.PRECISION
        y = self.get_y(i, j, x, xp)

        dy = xp[j] - y - 1  # -1 just in case there were some rounding errors
        dy_fee = dy * self.fee // self.FEE_DENOMINATOR

        # Convert all to real units
        dy = (dy - dy_fee) * self.PRECISION // rates[j]

        if j == self.FEE_INDEX:
            dy = self.dx_w_fee(dy)

        return dy

    def get_D_mem(self, _balances, amp):
        return self.get_D(self._xp_mem(_balances), amp)

    def add_liquidity(self, amounts, min_mint_amount):
        fees = [0] * self.N_COINS
        _fee = self.fee * self.N_COINS // (4 * (self.N_COINS - 1))
        _admin_fee = self.admin_fee
        amp = self._A()

        token_supply = self.total_pool_token_supply
        # Initial invariant
        D0 = 0
        old_balances = self.balances
        if token_supply > 0:
            D0 = self.get_D_mem(old_balances, amp)
        new_balances = old_balances

        for i in range(self.N_COINS):
            in_amount = amounts[i]
            if token_supply == 0:
                assert in_amount > 0  # dev: initial deposit requires all coins

            # Take coins from the sender
            if in_amount > 0 and i == self.FEE_INDEX:
                in_amount = self.dx_w_fee(in_amount)

            new_balances[i] = old_balances[i] + in_amount

        # Invariant after change
        D1 = self.get_D_mem(new_balances, amp)
        assert D1 > D0

        # We need to recalculate the invariant accounting for fees
        # to calculate fair user's share
        D2 = D1
        if token_supply > 0:
            # Only account for fees if we are not the first to deposit
            for i in range(self.N_COINS):
                ideal_balance = D1 * old_balances[i] // D0
                difference = 0
                if ideal_balance > new_balances[i]:
                    difference = ideal_balance - new_balances[i]
                else:
                    difference = new_balances[i] - ideal_balance
                fees[i] = _fee * difference // self.FEE_DENOMINATOR
                self.balances[i] = new_balances[i] - (fees[i] * _admin_fee // self.FEE_DENOMINATOR)
                new_balances[i] -= fees[i]
            D2 = self.get_D_mem(new_balances, amp)
        else:
            self.balances = new_balances

        # Calculate, how much pool tokens to mint
        mint_amount = 0
        if token_supply == 0:
            mint_amount = D1  # Take the dust if there was any
        else:
            mint_amount = token_supply * (D2 - D0) // D0

        assert mint_amount >= min_mint_amount

        return mint_amount

    def get_y_D(self, A_, i, xp, D):
        """
        Calculate x[i] if one reduces D from being calculated for xp to D
        Done by solving quadratic equation iteratively.
        x_1**2 + x1 * (sum' - (A*n**n - 1) * D / (A * n**n)) = D ** (n + 1) / (n ** (2 * n) * prod' * A)
        x_1**2 + b*x_1 = c
        x_1 = (x_1**2 + c) / (2*x_1 + b)
        """
        # x in the input is converted to the same price/precision

        assert i >= 0  # dev: i below zero
        assert i < self.N_COINS  # dev: i above N_COINS

        c = D
        S_ = 0
        Ann = A_ * self.N_COINS

        _x = 0
        for _i in range(self.N_COINS):
            if _i != i:
                _x = xp[_i]
            else:
                continue
            S_ += _x
            c = c * D // (_x * self.N_COINS)
        c = c * D // (Ann * self.N_COINS)
        b = S_ + D // Ann
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

    def _calc_withdraw_one_coin(self, _token_amount, i):
        # First, need to calculate
        # * Get current D
        # * Solve Eqn against y_i for D - _token_amount
        amp = self._A()
        _fee = self.fee * self.N_COINS // (4 * (self.N_COINS - 1))
        precisions = self.PRECISION_MUL
        total_supply = self.total_pool_token_supply

        xp = self._xp()

        D0 = self.get_D(xp, amp)
        D1 = D0 - _token_amount * D0 // total_supply
        xp_reduced = xp

        new_y = self.get_y_D(amp, i, xp, D1)
        dy_0 = (xp[i] - new_y) // precisions[i]  # w/o fees

        for j in range(self.N_COINS):
            dx_expected = 0
            if j == i:
                dx_expected = xp[j] * D1 // D0 - new_y
            else:
                dx_expected = xp[j] - xp[j] * D1 // D0
            xp_reduced[j] -= _fee * dx_expected // self.FEE_DENOMINATOR

        dy = xp_reduced[i] - self.get_y_D(amp, i, xp_reduced, D1)
        dy = (dy - 1) // precisions[i]  # Withdraw less to account for rounding errors

        return dy, dy_0 - dy

    def remove_liquidity_one_coin(self, _token_amount, i, min_amount):
        """
        Remove _amount of liquidity all in a form of coin i
        """
        dy = 0
        dy_fee = 0
        dy, dy_fee = self._calc_withdraw_one_coin(_token_amount, i)
        assert dy >= min_amount
        self.balances[i] -= (dy + dy_fee * self.admin_fee // self.FEE_DENOMINATOR)

        return dy


class StableSwapCompound(BaseCurvePool):

    N_COINS = 2
    PRECISION_MUL = [1, 1000000000000]
    USE_LENDING = [True, True]

    def __init__(self, block: int):
        address = TO_ADDRESS['Compound']
        pool = CURVE_CONTRACTS[address]
        self.set_balances(block, pool)
        self.fee = pool.functions.fee().call(block_identifier=block)
        self.A = pool.functions.A().call(block_identifier=block)
        self.exchangeRateCurrent = [c.functions.exchangeRateCurrent().call(block_identifier=block) for c in CTOKEN_CONTRACTS]
        self.block = block

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
        Ann = self.A * self.N_COINS
        for _i in range(255):
            D_P = D
            for _x in xp:
                D_P = D_P * D // (_x * self.N_COINS + 1)  # +1 is to prevent /0
            Dprev = D
            D = (Ann * S + D_P * self.N_COINS) * D // ((Ann - 1) * D + (self.N_COINS + 1) * D_P)
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

        assert (i != j) and (i >= 0) and (j >= 0) and (i < self.N_COINS) and (j < self.N_COINS)

        D = self.get_D(_xp)
        c = D
        S_ = 0
        Ann = self.A * self.N_COINS

        _x = 0
        for _i in range(self.N_COINS):
            if _i == i:
                _x = x
            elif _i != j:
                _x = _xp[_i]
            else:
                continue
            S_ += _x
            c = c * D // (_x * self.N_COINS)
        c = c * D // (Ann * self.N_COINS)
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

    def _current_rates(self):
        rates = self.PRECISION_MUL
        use_lending = self.USE_LENDING
        result = [0] * self.N_COINS
        for i in range(self.N_COINS):
            rate = self.LENDING_PRECISION  # Used with no lending
            if use_lending[i]:
                rate = self.exchangeRateCurrent[i]
            result[i] = rates[i] * rate
        return result

    def exchange(self, i, j, dx):
        rates = self._current_rates()
        dy = self._exchange(i, j, dx, rates)
        return dy

    def exchange_underlying(self, i, j, dx):
        rates = self._current_rates()
        precisions = self.PRECISION_MUL
        rate_i = rates[i] // precisions[i]
        rate_j = rates[j] // precisions[j]
        dx_ = dx * self.PRECISION // rate_i
        dy_ = self._exchange(i, j, dx_, rates)
        dy = dy_ * rate_j // self.PRECISION
        return dy


class StableSwapAETH(BaseCurvePool):

    N_COINS = 2
    A_PRECISION = 100
    _ratio_sig = Web3.keccak(text='ratio()')[:4].hex()

    def __init__(self, block: int):
        address = TO_ADDRESS['AETH']
        pool = CURVE_CONTRACTS[address]
        self.set_balances(block, pool)
        self.fee = pool.functions.fee().call(block_identifier=block)
        self.set_As(block, pool)
        self.set_timestamp()
        self.aeth_ratio = request(TRADE_SET['aETH'], self._ratio_sig, ['uint'])

    def _stored_rates(self):
        return [self.PRECISION, self.PRECISION * self.LENDING_PRECISION // self.aeth_ratio]

    def _xp(self, rates):
        result = [0] * self.N_COINS
        for i in range(self.N_COINS):
            result[i] = rates[i] * self.balances[i] // self.PRECISION
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
        assert j < n_coins  # dev: j above N_COINS

        # should be unreachable, but good for safety
        assert i >= 0
        assert i < n_coins

        A_ = self._A()
        D = self.get_D(xp_, A_)
        Ann = A_ * n_coins
        c = D
        S_ = 0
        _x = 0
        y_prev = 0
        a_prec = self.A_PRECISION
        for _i in range(n_coins):
            if _i == i:
                _x = x
            elif _i != j:
                _x = xp_[_i]
            else:
                continue
            S_ += _x
            c = c * D // (_x * n_coins)
        c = c * D * a_prec // (Ann * n_coins)
        b = S_ + D * a_prec // Ann  # - D
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
        rates = self._stored_rates()
        xp = self._xp(rates)
        x = xp[i] + dx * rates[i] // self.PRECISION
        y = self.get_y(i, j, x, xp)
        dy = xp[j] - y - 1  # -1 just in case there were some rounding errors
        dy_fee = dy * self.fee // self.FEE_DENOMINATOR
        dy = (dy - dy_fee) * self.PRECISION // rates[j]

        return dy


class StableSwapHBTC(BaseCurvePool):

    N_COINS = 2
    RATES = [1000000000000000000, 10000000000000000000000000000]

    def __init__(self, block: int):
        address = TO_ADDRESS['HBTC']
        pool = CURVE_CONTRACTS[address]
        self.set_balances(block, pool)
        self.fee = pool.functions.fee().call(block_identifier=block)
        self.set_As(block, pool)
        self.set_timestamp()

    def exchange(self, i, j, dx):
        rates = self.RATES

        old_balances = self.balances
        xp = self._xp_mem(old_balances)

        x = xp[i] + dx * rates[i] // self.PRECISION
        y = self.get_y(i, j, x, xp)

        dy = xp[j] - y - 1  # -1 just in case there were some rounding errors
        dy_fee = dy * self.fee // self.FEE_DENOMINATOR

        # Convert all to real units
        dy = (dy - dy_fee) * self.PRECISION // rates[j]

        return dy


class BasedCurvePool(BaseCurvePool):

    N_COINS = 2
    BASE_N_COINS = 3
    MAX_COIN = N_COINS - 1
    FEE_ASSET = TRADE_SET['USDT']
    BASE_CACHE_EXPIRES = 10*60
    A_PRECISION = 100
    RATES = [1000000000000000000, 1000000000000000000]

    def __init__(self, block: int, curve_class: BaseCurvePool, ticker: str):
        self.base_pool = curve_class(block)
        address = TO_ADDRESS[ticker]
        pool = CURVE_CONTRACTS[address]
        self.coins = [pool.functions.coins(i).call() for i in range(self.N_COINS)]
        self.base_coins = [pool.functions.base_coins(i).call() for i in range(self.BASE_N_COINS)]
        self.set_balances(block, pool)
        self.fee = pool.functions.fee().call(block_identifier=block)
        self.set_As(block, pool)
        self.set_timestamp()
        self.base_virtual_price = pool.functions.base_virtual_price().call(block_identifier=block)
        self.base_cache_updated = pool.functions.base_cache_updated().call(block_identifier=block)
        _i = len('StableSwap')
        base_pool_address = TO_ADDRESS[curve_class.__name__[_i:]]
        self.pool_token_balance = CURVE_TOKEN_CONTRACTS[base_pool_address].functions.balanceOf(address).call(block_identifier=block)
        self.usdt_max_fee = USDT.functions.maximumFee().call(block_identifier=block)
        self.usdt_basis_points_rate = USDT.functions.basisPointsRate().call(block_identifier=block)
        self.total_pool_token_supply = CURVE_TOKEN_CONTRACTS[address].functions.totalSupply().call(block_identifier=block)

    def _xp_mem(self, vp_rate, _balances):
        rates = self.RATES
        rates[self.MAX_COIN] = vp_rate  # virtual price for the metacurrency
        result = [0] * self.N_COINS
        for i in range(self.N_COINS):
            result[i] = rates[i] * _balances[i] // self.PRECISION

        return result

    def _vp_rate(self):
        if self.block_timestamp > self.base_cache_updated + self.BASE_CACHE_EXPIRES:
            vprice = self.base_pool.virtual_price
            return vprice
        else:
            return self.base_virtual_price

    def get_D(self, xp, amp):
        S = 0
        Dprev = 0
        for _x in xp:
            S += _x
        if S == 0:
            return 0

        D = S
        n_coins = self.N_COINS
        Ann = amp * n_coins
        a_prec = self.A_PRECISION
        for _i in range(255):
            D_P = D
            for _x in xp:
                D_P = D_P * D // (_x * n_coins)  # If division by 0, this will be borked: only withdrawal will work. And that is good
            Dprev = D
            D = (Ann * S // a_prec + D_P * n_coins) * D // ((Ann - a_prec) * D // a_prec + (n_coins + 1) * D_P)
            # Equality with the precision of 1
            if D > Dprev:
                if D - Dprev <= 1:
                    break
            else:
                if Dprev - D <= 1:
                    break
        return D

    def get_y(self, i, j, x, xp_):
        # x in the input is converted to the same price/precision
        n_coins = self.N_COINS
        assert i != j       # dev: same coin
        assert j >= 0       # dev: j below zero
        assert j < n_coins  # dev: j above N_COINS

        # should be unreachable, but good for safety
        assert i >= 0
        assert i < n_coins

        amp = self._A()         # use StableSwap3Pool _A()
        D = self.get_D(xp_, amp)

        S_ = 0
        _x = 0
        y_prev = 0
        c = D
        Ann = amp * n_coins
        a_prec = self.A_PRECISION
        for _i in range(n_coins):
            if _i == i:
                _x = x
            elif _i != j:
                _x = xp_[_i]
            else:
                continue
            S_ += _x
            c = c * D // (_x * n_coins)
        c = c * D * a_prec // (Ann * n_coins)
        b = S_ + D * a_prec // Ann  # - D
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

    def dx_w_fee(self, dx):
        fee = dx * self.usdt_basis_points_rate // 10000
        fee = min(fee, self.usdt_max_fee)
        return dx - fee

    def exchange(self, i, j, dx):
        rates = self.RATES
        rates[self.MAX_COIN] = self._vp_rate()

        old_balances = self.balances
        xp = self._xp_mem(rates[self.MAX_COIN], old_balances)

        x = xp[i] + dx * rates[i] // self.PRECISION
        y = self.get_y(i, j, x, xp)

        dy = xp[j] - y - 1  # -1 just in case there were some rounding errors
        dy_fee = dy * self.fee // self.FEE_DENOMINATOR

        # Convert all to real units
        dy = (dy - dy_fee) * self.PRECISION // rates[j]
        return dy

    def exchange_underlying(self, i, j, dx):
        rates = self.RATES
        rates[self.MAX_COIN] = self._vp_rate()

        # Use base_i or base_j if they are >= 0
        base_i = i - self.MAX_COIN
        base_j = j - self.MAX_COIN
        meta_i = self.MAX_COIN
        meta_j = self.MAX_COIN
        if base_i < 0:
            meta_i = i
        if base_j < 0:
            meta_j = j
        dy = 0

        # Addresses for input and output coins
        input_coin = ZERO_ADDRESS
        if base_i < 0:
            input_coin = self.coins[i]
        else:
            input_coin = self.base_coins[base_i]

        # Handle potential Tether fees
        dx_w_fee = dx
        if input_coin == self.FEE_ASSET:
            dx_w_fee = self.dx_w_fee(dx)

        if base_i < 0 or base_j < 0:
            old_balances = self.balances
            xp = self._xp_mem(rates[self.MAX_COIN], old_balances)

            x = 0
            if base_i < 0:
                x = xp[i] + dx_w_fee * rates[i] // self.PRECISION
            else:
                # i is from BasePool
                # At first, get the amount of pool tokens
                base_inputs = [0] * self.BASE_N_COINS
                base_inputs[base_i] = dx_w_fee
                # Deposit and measure delta
                # Need to convert pool token to "virtual" units using rates
                # dx is also different now
                # TODO: depends on side effects in 3pool, not just minted pool tokens
                dx_w_fee = self.base_pool.add_liquidity(base_inputs, 0)
                x = dx_w_fee * rates[self.MAX_COIN] // self.PRECISION
                # Adding number of pool tokens
                x += xp[self.MAX_COIN]

            y = self.get_y(meta_i, meta_j, x, xp)

            # Either a real coin or token
            dy = xp[meta_j] - y - 1  # -1 just in case there were some rounding errors
            dy_fee = dy * self.fee // self.FEE_DENOMINATOR

            # Convert all to real units
            # Works for both pool coins and real coins
            dy = (dy - dy_fee) * self.PRECISION // rates[meta_j]

            # Withdraw from the base pool if needed
            if base_j >= 0:
                dy = self.base_pool.remove_liquidity_one_coin(dy, base_j, 0)

            # prevent state pollution from previous trades
            self.base_pool.reset_balances()
        else:
            # If both are from the base pool
            dy = self.base_pool.exchange(base_i, base_j, dx_w_fee)

        return dy


class StableSwapGUSD(BasedCurvePool):

    RATES = [10000000000000000000000000000000000, 1000000000000000000]

    def __init__(self, block: int):
        super().__init__(block, StableSwap3Pool, 'GUSD')


class StableSwapHUSD(BasedCurvePool):

    RATES = [10000000000000000000000000000, 1000000000000000000]

    def __init__(self, block: int):
        super().__init__(block, StableSwap3Pool, 'HUSD')


class StableSwapMUSD(BasedCurvePool):

    def __init__(self, block: int):
        super().__init__(block, StableSwap3Pool, 'MUSD')


class StableSwapUST(BasedCurvePool):

    def __init__(self, block: int):
        super().__init__(block, StableSwap3Pool, 'UST')


class StableSwapUSDN(BasedCurvePool):

    def __init__(self, block: int):
        super().__init__(block, StableSwap3Pool, 'USDN')


class StableSwapDUSD(BasedCurvePool):

    def __init__(self, block: int):
        super().__init__(block, StableSwap3Pool, 'DUSD')


class StableSwapUSDP(BasedCurvePool):

    def __init__(self, block: int):
        super().__init__(block, StableSwap3Pool, 'USDP')


class StableSwapUSDK(BasedCurvePool):

    def __init__(self, block: int):
        super().__init__(block, StableSwap3Pool, 'USDK')


CURVE_POOLS = {address: getattr(sys.modules[__name__], f"StableSwap{name}") for address, name in CURVE_POOLS.items()}
