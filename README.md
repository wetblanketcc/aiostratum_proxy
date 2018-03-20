**`aiostratum_proxy`** is a Stratum Protocol proxy (ie cryptocurrency/mining) built using Python3. It was built to be a modern, code-concise, **extensible**, and fast replacement for existing aging Stratum Protocol proxy solutions & implementations.

* Requires Python 3.5 or greater (built with `asyncio` using `async`/`await` syntax)
* Extensible: easily implement new coin/algorithm 'stratum-like' protocols as dynamically-loaded, external Python3 modules (via config file)
* Can run multiple proxies at the same time (ie. mine different coins on different pools)
* Each proxy supports up to 65536 miner connections (per pool connection), each mining a separate nonce space (dependent on miner support)
* Supports plaintext and secure connections (ie. TLS/SSL) for both incoming miner connections and outgoing pool connections
* Plain socket transport only (ie. not JSONRPC over HTTP, HTTP Push, or HTTP Poll); this is the defacto standard in the cryptocurrency space

#### Donations

I built this on my own time, outside of my day job. If you find this mining proxy useful, donate to help continue development. **I value my time.**

* **BTC**:  1BS4QYAFiya4tsjyvHeY945biKnDj6bRA4
* **LTC**:﻿ LTN1LPGnJjHMKq4DcuQYifQgLfT4Phmn9d
* **ETH**:  0x4B005e68D323bdABD8eeD1D415117Ff1B57b3EC5
* **BTCP**: b1CACK65UTwzmHGw2VvyozdPsRLMb8utGLg
* **ZCL**:  t1eoqTqyatJzL2rErW83waZLQHZLKuipMbi

#### Installation

Installation is simple:

```
pip install aiostratum-proxy
```

However, for an isolated and more robust installation, you should consider using Python virtual environments:

```
# this will create a directory 'containing' the Python3 virtual environment
python3 -m venv aiostratum_proxy

cd aiostratum_proxy

# this will install the aiostratum-proxy package
bin/pip install aiostratum-proxy

# verify the installation by checking the package version
bin/aiostratum-proxy --version
```

#### Usage

Installation creates a new command-line shortcut called `aiostratum-proxy`; it has built-in command-line help, just run:

```
bin/aiostratum-proxy --help
```

A config file is needed for the proxy to run; you can generate one:

```
bin/aiostratum-proxy --generate-config > proxy-config.yaml
```

Open and edit the generated `proxy-config.yaml` in a text editor. The config file's syntax is YAML ([here's a good guide to YAML](https://github.com/Animosity/CraftIRC/wiki/Complete-idiot's-introduction-to-yaml)).

To run `aiostratum-proxy`, pass it your edited config file:

```
bin/aiostratum-proxy --config proxy-config.yaml
```


#### Supported Algorithms/Coins

`aiostratum-proxy` was designed to be modular and extensible when it comes to coin and algorithm support. This is done via miner+pool protocol module pairs (more on this below).

Current support includes:

* any coin based on Equihash (ZCash, ZClassic, Bitcoin Gold, Bitcoin Private, etc):
  * miner module: `aiostratum_proxy.protocols.equihash.EquihashWorkerProtocol`
  * pool module: `aiostratum_proxy.protocols.equihash.EquihashPoolProtocol`
* (**EXPERIMENTAL/UNTESTED**/probably not working just yet) Bitcoin (and related coins):
  * miner module: `aiostratum_proxy.protocols.stratum.StratumWorkerProtocol`
  * pool module: `aiostratum_proxy.protocols.stratum.StratumPoolProtocol`

As you can see, it is possible for a protocol implementation (ie. both the worker & pool sides) to support multiple coins, assuming they share some common ancestry or have heavily borrowed technical decisions.

#### Add Support for New Coins & Algorithms

The terms 'Stratum' and 'Stratum Protocol' are used broadly (perhaps too much so) in the cryptocurrency ecosystem. The concept behind the Stratum protocol started with the specific desire to improve the efficiency of Bitcoin mining pools.

In time, the rise of altcoins demanded a similar approach to managing the communications between miners and pools. For whatever reason, most altcoins have tweaked the original Stratum spec to their needs, borrowing and learning from prior mistakes.

To add support for a new coin or algorithm, there are two options:

1. Use an existing protocol implementation and tweak; note that this means if there are future changes, it may have cascading impacts (see the Equihash protocol pair as an example, it is based off of the Stratum protocol pair)
1. Create a new protocol pairing by implementing both `BasePoolProtocol` (to handle connections to pools) and `BaseWorkerProtocol` (to handle incoming miner connections)

For example, if you were implementing Monero support:

1. Create a new Python module with the Monero 'worker' and 'pool' protocol class implementations
1. Add the new Monero worker/pool classes to your proxy config file
1. You will need to ensure your Python module is visible within `PYTHONPATH` to use it within your proxy YAML config file
1. **Consider [submitting it as a pull request](https://github.com/wetblanketcc/aiostratum_proxy/pulls) to `aiostratum_proxy`!** If so, you would place the new module alongside the existing Equihash implementation at `aiostratum_proxy.protocols.monero`


#### Future Considerations

Community involvement is appreciated. [Code review](https://github.com/wetblanketcc/aiostratum_proxy), [pull requests for bug fixes & new protocols](https://github.com/wetblanketcc/aiostratum_proxy/pulls), [reporting issues](https://github.com/wetblanketcc/aiostratum_proxy/issues), spreading the word - all appreciated.

##### TODO:

Community feedback on the following is appreciated.

* More coin/algo support
* Complete `mining.set_extranonce` support
* Consider additional authentication improvements (currently miners aren't authenticated)
  * authenticate miners locally within proxy via config
  * authenticate miners via passthru to pool; would require per-pool mappings of username/password for fallback pools in config?
* Consider immediate reply to miner share submissions instead of waiting for pool response
* HAProxy `PROXY` protocol support

#### Related & Informative Links

1. [Stratum Protocol Specification](https://slushpool.com/help/manual/stratum-protocol)
1. [Stratum Protocol Specification Draft](https://docs.google.com/document/d/17zHy1SUlhgtCMbypO8cHgpWH73V5iUQKk_0rWvMqSNs/edit?hl=en_US)
1. [Stratum Protocol Bitcoin Wiki Page](https://en.bitcoin.it/wiki/Stratum_mining_protocol)
1. [Original Bitcointalk.org Stratum Announcement](https://bitcointalk.org/index.php?topic=108533.0)
1. [Follow-on Bitcointalk.org Stratum Discussion](https://bitcointalk.org/index.php?topic=557991.0)
