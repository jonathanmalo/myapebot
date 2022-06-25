pragma solidity ^0.6.5;
pragma experimental ABIEncoderV2;

interface IExchange {
    /* uniswap */
    function swap(uint amount0Out, uint amount1Out, address to, bytes calldata data) external;
    /* curve */
    function exchange(int128 i, int128 j, uint256 dx, uint256 min_dy) external;
    function exchange_underlying(int128 i, int128 j, uint256 dx, uint256 min_dy) external returns (uint256);
    /* balancer */
    function swapExactAmountIn(address tokenIn, uint tokenAmountIn, address tokenOut, uint minAmountOut, uint maxPrice) external returns (uint tokenAmountOut, uint spotPriceAfter);
    /* mooniswap */
    function swap(address src, address dst, uint256 amount, uint256 minReturn, address referral) external payable returns (uint256 result);
    /* hiding book */
    struct RfqOrder {
        address makerToken;
        address takerToken;
        uint128 makerAmount;
        uint128 takerAmount;
        address maker;
        address taker;
        address txOrigin;
        bytes32 pool;
        uint64 expiry;
        uint256 salt;
    }
    struct Signature {
     uint8 signatureType; // Either 2 or 3
     uint8 v; // Signature data.
     bytes32 r; // Signature data.
     bytes32 s; // Signature data.
    }
    function fillOrKillRfqOrder(RfqOrder calldata order, Signature calldata signature, uint128 takerTokenFillAmount) external payable returns (uint128 makerTokenFillAmount);
}
