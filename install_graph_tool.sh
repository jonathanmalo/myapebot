#!/bin/bash

rm -rf graph-tool .venv

sudo dnf install python3.8
sudo alternatives --install /usr/bin/python python /usr/bin/python3.8 1
virtualenv -p python3.8 .venv
source .venv/bin/activate
sudo dnf install boost-devel boost-python3 boost-python3-devel expat-devel CGAL-devel sparsehash-devel cairomm-devel automake libtool
pip install numpy pycairo
git clone https://git.skewed.de/count0/graph-tool.git
cd graph-tool
./autogen.sh
./configure --with-python-module-path="$HOME/winbot/.venv/lib/python3.8/site-packages"
make
sudo make install
cd ..
pip install --upgrade-strategy only-if-needed scipy py-solc-x eth-brownie aiohttp elasticsearch mpmath
