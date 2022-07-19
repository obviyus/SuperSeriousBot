# [1.6.0](https://github.com/obviyus/SuperSeriousBot/compare/v1.5.1...v1.6.0) (2022-07-19)


### Bug Fixes

* **move:** move ([e76559c](https://github.com/obviyus/SuperSeriousBot/commit/e76559c8560f47a2048d39c4e80abadcba3e715a))
* **sb:** fix tense logic ([51ce6a3](https://github.com/obviyus/SuperSeriousBot/commit/51ce6a3d590cfb9491b726fc3bd1bf656ca86ccb))
* **seen:** fix seen logic ([d20c637](https://github.com/obviyus/SuperSeriousBot/commit/d20c637b3526b828aaf8c81bcaf2a32b2606833b))
* **tv:** await send message coroutine ([2a06470](https://github.com/obviyus/SuperSeriousBot/commit/2a064706f96d3e5f87d4368065638743cbfba7ba))
* **utils:** rename `internal` to `utils` ([43a119d](https://github.com/obviyus/SuperSeriousBot/commit/43a119d7bd2927f8eefbba084d8038bd93f3061e))


### Features

* **botstats:** add /botstats ([429dafb](https://github.com/obviyus/SuperSeriousBot/commit/429dafbd6b59b41d3dc8b95fdab43c709d700951))
* **botstats:** add dev commands ([d9e1b0e](https://github.com/obviyus/SuperSeriousBot/commit/d9e1b0e73ee4e4c6a9927124e054f30061d357a7))
* **calc:** add calc ([5300506](https://github.com/obviyus/SuperSeriousBot/commit/5300506b3f48a04254a55bc91671403c22fcdfaa))
* **c:** get top comment ([99ce8df](https://github.com/obviyus/SuperSeriousBot/commit/99ce8df0a05609a9bb625bb3b353e1511f8fd08f))
* **commands:** add basic commands ([1820567](https://github.com/obviyus/SuperSeriousBot/commit/1820567f5fba3f7a3f3a65c13e1114329101574a))
* **commands:** add features ([69d5c48](https://github.com/obviyus/SuperSeriousBot/commit/69d5c48e81204874856b98b720dba2cfb66d0f63))
* **deps:** add poetry dependency management ([5947370](https://github.com/obviyus/SuperSeriousBot/commit/5947370bda13be940690fde9e41b6f53cd524ec3))
* **dl:** combine /album and /dl ([f8692b6](https://github.com/obviyus/SuperSeriousBot/commit/f8692b6148e26a6212cc104d8856ee82ad348a91))
* **logging:** add channel for logging ([42bc856](https://github.com/obviyus/SuperSeriousBot/commit/42bc85695c9be84a30105623da6d1af45b2bc853))
* **logs:** add coloredlogs ([f5a7e70](https://github.com/obviyus/SuperSeriousBot/commit/f5a7e701dbba966d8e1862d5be2bf4b195c66afe))
* **sub:** reddit subscriptions handlers ([5ca6738](https://github.com/obviyus/SuperSeriousBot/commit/5ca67388c3c7ea2e1f881bac2e973f2ab4845fd2))
* **tl+tts:** add tl and tts commands ([e770f3d](https://github.com/obviyus/SuperSeriousBot/commit/e770f3d9a0d5ae056967d8592dbc251a48ee2856))
* **tldr:** add TLDR command ([698be95](https://github.com/obviyus/SuperSeriousBot/commit/698be95ba191fdf57eb19d09039bf87a9f485b59))
* **tv:** add /tv command ([daf6773](https://github.com/obviyus/SuperSeriousBot/commit/daf677385e03b445b8efedf5888ad5f9fdecba91))
* **tv:** add button handler ([3e152ee](https://github.com/obviyus/SuperSeriousBot/commit/3e152ee22b96ad7c32b4be80ddef2b843c66e845))
* **uwu+ud:** add uwu and ud ([1ac1f10](https://github.com/obviyus/SuperSeriousBot/commit/1ac1f10d778d201673159dc7c9363cdcc14afcbf))
* **vision:** implement Vision commands ([ba2ae88](https://github.com/obviyus/SuperSeriousBot/commit/ba2ae8814b4fcbe6509f2c00f2940367ee5190d8))
* **weather:** add weather command ([5872360](https://github.com/obviyus/SuperSeriousBot/commit/5872360e7dcd2e4b33f9de0fe135d159521cb5b7))
* **weather:** cache weather location ([1430f45](https://github.com/obviyus/SuperSeriousBot/commit/1430f459dc81de5c3e68fd5076f4de9eb4b95e1e))

## [1.5.1](https://github.com/obviyus/SuperSeriousBot/compare/v1.5.0...v1.5.1) (2022-06-23)


### Bug Fixes

* **deps:** loosen dependency version for regex ([0ae4f25](https://github.com/obviyus/SuperSeriousBot/commit/0ae4f25b8f102afc6470c4d43233813e6a8a0ca6))
* **subscribe:** narrow scope of delivering reddit ([70b1800](https://github.com/obviyus/SuperSeriousBot/commit/70b18009f3c77a5a5b4071da4c1ffde255a7596b))

# [1.5.0](https://github.com/obviyus/SuperSeriousBot/compare/v1.4.6...v1.5.0) (2022-06-10)


### Features

* **pic:** revert /pic to old version ([565f83e](https://github.com/obviyus/SuperSeriousBot/commit/565f83eb291b88b4d6f530cd187fced0571b50dc))

## [1.4.6](https://github.com/obviyus/SuperSeriousBot/compare/v1.4.5...v1.4.6) (2022-06-01)


### Bug Fixes

* **stats:** make username entries db-safe ([1e2814d](https://github.com/obviyus/SuperSeriousBot/commit/1e2814df943260a086d836a2751585284456ab7c))

## [1.4.5](https://github.com/obviyus/SuperSeriousBot/compare/v1.4.4...v1.4.5) (2022-06-01)


### Bug Fixes

* **stats:** escape special characters in first_name ([8e5e311](https://github.com/obviyus/SuperSeriousBot/commit/8e5e31176129698ba76b440b0bfdb2eb672084d2))

## [1.4.4](https://github.com/obviyus/SuperSeriousBot/compare/v1.4.3...v1.4.4) (2022-05-28)


### Bug Fixes

* **dl:** catch exceptions thrown by reddit-video ([a6282b8](https://github.com/obviyus/SuperSeriousBot/commit/a6282b818dd545bb1cddab05189795d256f55146))

## [1.4.3](https://github.com/obviyus/SuperSeriousBot/compare/v1.4.2...v1.4.3) (2022-05-08)


### Bug Fixes

* **error:** remove deprecated buffer warning ([6556e38](https://github.com/obviyus/SuperSeriousBot/commit/6556e382f3b547a1d19692f0802716fac00a630f))

## [1.4.2](https://github.com/obviyus/SuperSeriousBot/compare/v1.4.1...v1.4.2) (2022-05-08)


### Bug Fixes

* **dl:** simplify ytopts ([3db3af8](https://github.com/obviyus/SuperSeriousBot/commit/3db3af824742f3b2a80081f05b44d9a569d306e5))

## [1.4.1](https://github.com/obviyus/SuperSeriousBot/compare/v1.4.0...v1.4.1) (2022-05-08)


### Bug Fixes

* **dl:** remove filesize constraint ([e5bc4a9](https://github.com/obviyus/SuperSeriousBot/commit/e5bc4a9bafa240cf8d4838870360c98bddcf0c8e))

# [1.4.0](https://github.com/obviyus/SuperSeriousBot/compare/v1.3.1...v1.4.0) (2022-05-08)


### Features

* **inline:** add inline keyboard to remove shows ([5940121](https://github.com/obviyus/SuperSeriousBot/commit/59401210de12f665397d3678945cda0837622392))

## [1.3.1](https://github.com/obviyus/SuperSeriousBot/compare/v1.3.0...v1.3.1) (2022-05-08)


### Bug Fixes

* **inline:** skip image if None in InlineResults ([82832ec](https://github.com/obviyus/SuperSeriousBot/commit/82832ec53cbb047ff67cddbc5ecf647b26692f6b))

# [1.3.0](https://github.com/obviyus/SuperSeriousBot/compare/v1.2.1...v1.3.0) (2022-05-07)


### Features

* **tv:** add inline mode to send TV episode notifications ([c82eea0](https://github.com/obviyus/SuperSeriousBot/commit/c82eea01c646e4e3a28585818c159447886d52c0))

## [1.2.1](https://github.com/obviyus/SuperSeriousBot/compare/v1.2.0...v1.2.1) (2022-05-07)


### Bug Fixes

* **api:** remove deprecated covid API ([a07630c](https://github.com/obviyus/SuperSeriousBot/commit/a07630c5ecc8aebaa212d5df15c67f0030b4325e))

# [1.2.0](https://github.com/obviyus/SuperSeriousBot/compare/v1.1.0...v1.2.0) (2022-05-07)


### Bug Fixes

* **covid:** remove deprecated covid command ([30781d6](https://github.com/obviyus/SuperSeriousBot/commit/30781d6a5231c74fb490c0c632efb608fbc11195))
* **define:** add check for list of synonyms ([1888b61](https://github.com/obviyus/SuperSeriousBot/commit/1888b619a601a555215ed01ede00fee65ff763b2))
* **subscribe:** remove failing subscriptions from list ([1f034e4](https://github.com/obviyus/SuperSeriousBot/commit/1f034e451d1cc0e0249a09f4abeeb53f74673a76))
* **wmark:** remove wmark command ([6fe280d](https://github.com/obviyus/SuperSeriousBot/commit/6fe280d66373a587c0e3cf08270865dec73fbe42))


### Features

* **dl:** add downloads for reddit vidoes ([d470b73](https://github.com/obviyus/SuperSeriousBot/commit/d470b73c97ad6974353203e0b323be4671234383))
* **docker:** simplify image ([594ca34](https://github.com/obviyus/SuperSeriousBot/commit/594ca346dbf0e98890c7ce14c75a0b04bd7d59d4))
