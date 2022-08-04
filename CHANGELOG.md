# [1.17.0](https://github.com/obviyus/SuperSeriousBot/compare/v1.16.0...v1.17.0) (2022-08-04)


### Bug Fixes

* **seen:** fix time parsing for legacy entries ([34c01ca](https://github.com/obviyus/SuperSeriousBot/commit/34c01ca89dfc9260712d751cb1dc4927abb35158))


### Features

* **mentions:** store user mentions for future feature ([9382fc6](https://github.com/obviyus/SuperSeriousBot/commit/9382fc6fd6cde6e500dbacde95183df2e4359a7c))

# [1.16.0](https://github.com/obviyus/SuperSeriousBot/compare/v1.15.2...v1.16.0) (2022-08-04)


### Features

* **db:** index busy rows ([a269a70](https://github.com/obviyus/SuperSeriousBot/commit/a269a7083a14a391e9cdd33fba3b166ee6aff293))

## [1.15.2](https://github.com/obviyus/SuperSeriousBot/compare/v1.15.1...v1.15.2) (2022-08-04)


### Bug Fixes

* **stats:** use first_name in stats ([7a1dd58](https://github.com/obviyus/SuperSeriousBot/commit/7a1dd58db68e59e281a4d4dcd6a5d7d16cc7f172))

## [1.15.1](https://github.com/obviyus/SuperSeriousBot/compare/v1.15.0...v1.15.1) (2022-08-04)


### Bug Fixes

* **c:** escape special Reddit markdown ([a0cb2b9](https://github.com/obviyus/SuperSeriousBot/commit/a0cb2b9191ad98dbfd5f7ebd27c34c0a425e0f55))
* **tv:** remove excess args from SQL query ([b8a90c0](https://github.com/obviyus/SuperSeriousBot/commit/b8a90c0f1dbac41161ff518a9f75890d94a0f650))

# [1.15.0](https://github.com/obviyus/SuperSeriousBot/compare/v1.14.6...v1.15.0) (2022-08-03)


### Features

* **tv:** show ETA for upcoming episodes ([71edb95](https://github.com/obviyus/SuperSeriousBot/commit/71edb9534e803630c1296ccf65537389dfee76f7))

## [1.14.6](https://github.com/obviyus/SuperSeriousBot/compare/v1.14.5...v1.14.6) (2022-08-02)


### Bug Fixes

* **tv:** limit list response to only the chat ([80f2d81](https://github.com/obviyus/SuperSeriousBot/commit/80f2d8178b7b17d9b29a2107114b8ea54aeeda84))

## [1.14.5](https://github.com/obviyus/SuperSeriousBot/compare/v1.14.4...v1.14.5) (2022-08-02)


### Bug Fixes

* **tv:** shortedn callback data to < 64 bytes ([75d76f6](https://github.com/obviyus/SuperSeriousBot/commit/75d76f69f458fac3a13a701c493a4f34580d6a76))

## [1.14.4](https://github.com/obviyus/SuperSeriousBot/compare/v1.14.3...v1.14.4) (2022-08-02)


### Bug Fixes

* **tv:** re-add /tv command ([6d2bcea](https://github.com/obviyus/SuperSeriousBot/commit/6d2bcea7dcddf58479cea8ad2857378a7f227083))

## [1.14.3](https://github.com/obviyus/SuperSeriousBot/compare/v1.14.2...v1.14.3) (2022-07-31)


### Bug Fixes

* **c:** re-add command ([9b314a7](https://github.com/obviyus/SuperSeriousBot/commit/9b314a7717b475afcbcf7d884dc8e1ce39fc626f))

## [1.14.2](https://github.com/obviyus/SuperSeriousBot/compare/v1.14.1...v1.14.2) (2022-07-31)


### Bug Fixes

* **quote:** quote works without args ([ad1c138](https://github.com/obviyus/SuperSeriousBot/commit/ad1c138a58eb67d832152ae973d663e0c74e8f15))

## [1.14.1](https://github.com/obviyus/SuperSeriousBot/compare/v1.14.0...v1.14.1) (2022-07-31)


### Bug Fixes

* **object:** re-add object store commands ([40d7c67](https://github.com/obviyus/SuperSeriousBot/commit/40d7c6755e12589e5aa91cf8fccf7a843758ebf2))

# [1.14.0](https://github.com/obviyus/SuperSeriousBot/compare/v1.13.0...v1.14.0) (2022-07-31)


### Features

* **botstats:** use sqlite for botstats ([4b82e3e](https://github.com/obviyus/SuperSeriousBot/commit/4b82e3e67a48550e314627da3ee9913a4e14f03d))

# [1.13.0](https://github.com/obviyus/SuperSeriousBot/compare/v1.12.0...v1.13.0) (2022-07-31)


### Features

* **decorators:** implement decorators for docs ([b3f462c](https://github.com/obviyus/SuperSeriousBot/commit/b3f462c0884b13cd17e8b36aa25c74070fe5fe88))
* **links:** remove /dl for instagram URLs ([d94d89a](https://github.com/obviyus/SuperSeriousBot/commit/d94d89ac00ce21e0270c0d57e6b005bcc4f36413))

# [1.12.0](https://github.com/obviyus/SuperSeriousBot/compare/v1.11.1...v1.12.0) (2022-07-30)


### Features

* **docs:** use `set_my_commands` for docs ([165d6c9](https://github.com/obviyus/SuperSeriousBot/commit/165d6c97630a5d718314aa86ebe50b50ae036d90))
* **object:** implement a generic object store and qouteDB ([f4c1f5d](https://github.com/obviyus/SuperSeriousBot/commit/f4c1f5d3113596bdca6264ca40c63bab5a00b15e))

## [1.11.1](https://github.com/obviyus/SuperSeriousBot/compare/v1.11.0...v1.11.1) (2022-07-30)


### Bug Fixes

* **c:** handle case for `youtu.be` links ([941dfda](https://github.com/obviyus/SuperSeriousBot/commit/941dfda52aacc346964a2d4978dde2ca9f590de1))
* **c:** improve comment loading logic ([eaa5219](https://github.com/obviyus/SuperSeriousBot/commit/eaa52191380c65de108034431520841d05f3b39d))
* **sub:** iterate asynchronously ([a10562c](https://github.com/obviyus/SuperSeriousBot/commit/a10562c4923c568f60f5679b2d63b657647ff449))
* **tl:** check for parent message ([139e53a](https://github.com/obviyus/SuperSeriousBot/commit/139e53a37b9c8baf7603ae5068cd5473a51d59ba))

# [1.11.0](https://github.com/obviyus/SuperSeriousBot/compare/v1.10.1...v1.11.0) (2022-07-29)


### Bug Fixes

* **async:** gather all coroutines at once ([7e0a1fd](https://github.com/obviyus/SuperSeriousBot/commit/7e0a1fdb364a3ff95643ad7bd24dfbc24e7a3f40))
* **dl:** implement Python 3.10 match operators for URLs ([e6254e1](https://github.com/obviyus/SuperSeriousBot/commit/e6254e1e5b4684a5f286ceae619c3ea12e1d8762))
* **weather:** check if location exists ([b982069](https://github.com/obviyus/SuperSeriousBot/commit/b98206953c5bd8dd1ae6139250b5e6cb373f5224))


### Features

* **httpx:** replace requests with httpx ([58ea116](https://github.com/obviyus/SuperSeriousBot/commit/58ea11691e73d02326967885c1a49d8d1dfc6adf))

## [1.10.1](https://github.com/obviyus/SuperSeriousBot/compare/v1.10.0...v1.10.1) (2022-07-24)


### Bug Fixes

* **dl:** handle video posts in Instagram ([27785a7](https://github.com/obviyus/SuperSeriousBot/commit/27785a73becdbda4ace621cf34e6f0246eac3788))

# [1.10.0](https://github.com/obviyus/SuperSeriousBot/compare/v1.9.1...v1.10.0) (2022-07-24)


### Features

* **dl:** support for downloading Instagram posts ([554ddb7](https://github.com/obviyus/SuperSeriousBot/commit/554ddb7c46f8fc5302e7c6e95bc4474b2c657178))

## [1.9.1](https://github.com/obviyus/SuperSeriousBot/compare/v1.9.0...v1.9.1) (2022-07-24)


### Bug Fixes

* **block:** remove block = False flags ([a073788](https://github.com/obviyus/SuperSeriousBot/commit/a0737880926a7ba7a7f585199c29c9e9f425e3a1))

# [1.9.0](https://github.com/obviyus/SuperSeriousBot/compare/v1.8.0...v1.9.0) (2022-07-24)


### Features

* **gstats:** command for total chat stats ([855281f](https://github.com/obviyus/SuperSeriousBot/commit/855281fd7e7b85acbddb60ae52eb9a0a1bffd318))

# [1.8.0](https://github.com/obviyus/SuperSeriousBot/compare/v1.7.1...v1.8.0) (2022-07-24)


### Features

* **stats:** reformat stats ([e48ca88](https://github.com/obviyus/SuperSeriousBot/commit/e48ca880ca506343f742dd34f1fd6f0e5f763ea9))

## [1.7.1](https://github.com/obviyus/SuperSeriousBot/compare/v1.7.0...v1.7.1) (2022-07-24)


### Bug Fixes

* **move:** move db.py to config ([442975e](https://github.com/obviyus/SuperSeriousBot/commit/442975e4ac2cd1c3482730c15c885886f06c63e3))

# [1.7.0](https://github.com/obviyus/SuperSeriousBot/compare/v1.6.1...v1.7.0) (2022-07-24)


### Features

* **move:** store logic in `src` directory ([6d1f6a6](https://github.com/obviyus/SuperSeriousBot/commit/6d1f6a662353f0783db7f989559f319e0c1e6630))

## [1.6.1](https://github.com/obviyus/SuperSeriousBot/compare/v1.6.0...v1.6.1) (2022-07-19)


### Bug Fixes

* **redis:** use Docker network to connect redis ([4d69347](https://github.com/obviyus/SuperSeriousBot/commit/4d6934731350ac746bcba5c86c9de1ca60ba7159))

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
