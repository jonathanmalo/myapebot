pragma solidity ^0.4.18;

contract IWETH9 {
    function deposit() external payable;
    function balanceOf(address guy) external view returns (uint256);
    function approve(address guy, uint wad) external returns (bool);
    function transfer(address dst, uint wad) external returns (bool);
}
