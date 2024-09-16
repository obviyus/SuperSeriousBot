## [1.87.1](https://github.com/obviyus/SuperSeriousBot/compare/v1.87.0...v1.87.1) (2024-09-16)


### Bug Fixes

* handle invalid chats in habit ([1d175ec](https://github.com/obviyus/SuperSeriousBot/commit/1d175ec74d7afe40a9fdb0fb49d9adbe0e162fae))

# [1.87.0](https://github.com/obviyus/SuperSeriousBot/compare/v1.86.1...v1.87.0) (2024-08-19)


### Features

* **tldw:** create TLDW function ([8e8b9e0](https://github.com/obviyus/SuperSeriousBot/commit/8e8b9e091ad9f6054ec47ad6f505c75a960e2244))

## [1.86.1](https://github.com/obviyus/SuperSeriousBot/compare/v1.86.0...v1.86.1) (2024-08-03)


### Bug Fixes

* **button:** remove unused YT handler ([049b9da](https://github.com/obviyus/SuperSeriousBot/commit/049b9da030066d4f992fccf9399de50920c4b266))

# [1.86.0](https://github.com/obviyus/SuperSeriousBot/compare/v1.85.2...v1.86.0) (2024-08-02)


### Features

* **yt:** remove YouTube notifications ([cbec22d](https://github.com/obviyus/SuperSeriousBot/commit/cbec22d8d50807dcb6e9c9806d17e8599b16ad83))

## [1.85.2](https://github.com/obviyus/SuperSeriousBot/compare/v1.85.1...v1.85.2) (2024-07-28)


### Bug Fixes

* **r:** remove nsfw command ([35eff81](https://github.com/obviyus/SuperSeriousBot/commit/35eff81ee83ab7097668883125213f7c5a05453a))

## [1.85.1](https://github.com/obviyus/SuperSeriousBot/compare/v1.85.0...v1.85.1) (2024-07-19)


### Bug Fixes

* **summon:** create PK to ensure no duplicates ([44fdc0d](https://github.com/obviyus/SuperSeriousBot/commit/44fdc0d8fac20b830f3e978c7b45802ddae16740))

# [1.85.0](https://github.com/obviyus/SuperSeriousBot/compare/v1.84.0...v1.85.0) (2024-07-19)


### Features

* **ask:** upgrade to 4o-mini ([cdb5451](https://github.com/obviyus/SuperSeriousBot/commit/cdb54513f6e6d82cf314fee700afd55317b14157))

# [1.84.0](https://github.com/obviyus/SuperSeriousBot/compare/v1.83.3...v1.84.0) (2024-07-11)


### Features

* **caption:** use litellm for vision ([4b33aed](https://github.com/obviyus/SuperSeriousBot/commit/4b33aed8105afd5f801a246ea9fa5dd6a4f872ac))

## [1.83.3](https://github.com/obviyus/SuperSeriousBot/compare/v1.83.2...v1.83.3) (2024-07-10)


### Bug Fixes

* **caption:** upgrade to gpt-4o for vision ([b30ad04](https://github.com/obviyus/SuperSeriousBot/commit/b30ad046f93474663100af4818a9a7cc3313ac80))

## [1.83.2](https://github.com/obviyus/SuperSeriousBot/compare/v1.83.1...v1.83.2) (2024-06-26)


### Bug Fixes

* **yt:** use write conn ([f04b8e9](https://github.com/obviyus/SuperSeriousBot/commit/f04b8e99ce6f0d3dc4effd2996d8c10a01032b45))

## [1.83.1](https://github.com/obviyus/SuperSeriousBot/compare/v1.83.0...v1.83.1) (2024-06-26)


### Bug Fixes

* **redis:** deprecate aioredis ([9db58df](https://github.com/obviyus/SuperSeriousBot/commit/9db58df423cfeda4835e3d1040041ebaa59d92de))

# [1.83.0](https://github.com/obviyus/SuperSeriousBot/compare/v1.82.4...v1.83.0) (2024-06-26)


### Features

* **redis:** switch to aioredis ([8ec5687](https://github.com/obviyus/SuperSeriousBot/commit/8ec56873c232d8e84efb5d5ae41589bb3ac15ac4))

## [1.82.4](https://github.com/obviyus/SuperSeriousBot/compare/v1.82.3...v1.82.4) (2024-06-26)


### Bug Fixes

* **yt:** import ydl instance, not opts ([c6413b3](https://github.com/obviyus/SuperSeriousBot/commit/c6413b381e9ae49bea3f1cfb2e9d98cd31056bac))

## [1.82.3](https://github.com/obviyus/SuperSeriousBot/compare/v1.82.2...v1.82.3) (2024-06-26)


### Bug Fixes

* **highlight:** fix missing import for /hl ([e24ea68](https://github.com/obviyus/SuperSeriousBot/commit/e24ea689d76dec686840246faa1a69fa868679cb))

## [1.82.2](https://github.com/obviyus/SuperSeriousBot/compare/v1.82.1...v1.82.2) (2024-06-26)


### Bug Fixes

* **main:** crash if polling fails ([b392f66](https://github.com/obviyus/SuperSeriousBot/commit/b392f66794752bfaa111e4223ad7ceb91d4065ee))

## [1.82.1](https://github.com/obviyus/SuperSeriousBot/compare/v1.82.0...v1.82.1) (2024-06-26)


### Bug Fixes

* **asyncio:** run application in main event loop ([230a580](https://github.com/obviyus/SuperSeriousBot/commit/230a580def8e85c081c88a40434a6884d0d5bcc1))

# [1.82.0](https://github.com/obviyus/SuperSeriousBot/compare/v1.81.4...v1.82.0) (2024-06-26)


### Bug Fixes

* **redis:** remove async redis ([6c7e535](https://github.com/obviyus/SuperSeriousBot/commit/6c7e535c4a7c120887d571f0b7f988716d1ff2a6))


### Features

* **async:** run tasks in parallel ([c596089](https://github.com/obviyus/SuperSeriousBot/commit/c5960894e50782ecc2fae5f4c45a131608f9b953))
* **db:** use aiosqlite instead of sqlite3 ([466bf95](https://github.com/obviyus/SuperSeriousBot/commit/466bf95771e144e432a43a796cd240cb5b7f151e))
* **sql:** migrate to aiosqlite with connection manager ([b8cd7b0](https://github.com/obviyus/SuperSeriousBot/commit/b8cd7b035081e36b0a2a18112acd768e93ebe285))
* **sql:** switch to aiosqlite ([c8baf4d](https://github.com/obviyus/SuperSeriousBot/commit/c8baf4d8294892d81cd49eb6fd1ef3d7055870fe))

## [1.81.4](https://github.com/obviyus/SuperSeriousBot/compare/v1.81.3...v1.81.4) (2024-06-24)


### Bug Fixes

* **youtube:** remove await from cursor calls ([e4d49c1](https://github.com/obviyus/SuperSeriousBot/commit/e4d49c10f2963bd10aaae2c5a0501756480bd123))

## [1.81.3](https://github.com/obviyus/SuperSeriousBot/compare/v1.81.2...v1.81.3) (2024-06-24)


### Bug Fixes

* **db:** remove async cursors ([70e6b79](https://github.com/obviyus/SuperSeriousBot/commit/70e6b798b53c7a56e7b2d5dcb2b091d756799ca2))

## [1.81.2](https://github.com/obviyus/SuperSeriousBot/compare/v1.81.1...v1.81.2) (2024-06-24)


### Bug Fixes

* **migrations:** fix DB path for docker ([d85e6e0](https://github.com/obviyus/SuperSeriousBot/commit/d85e6e0abcf875418477516b3848b03084448375))

## [1.81.1](https://github.com/obviyus/SuperSeriousBot/compare/v1.81.0...v1.81.1) (2024-06-24)


### Bug Fixes

* **db:** reversion DB migration ([ce2bc4d](https://github.com/obviyus/SuperSeriousBot/commit/ce2bc4d0f8ee748fb7b816302e7978e5fb444f77))

# [1.81.0](https://github.com/obviyus/SuperSeriousBot/compare/v1.80.4...v1.81.0) (2024-06-24)


### Features

* **db:** use caribou for DB migrations ([7b0e97e](https://github.com/obviyus/SuperSeriousBot/commit/7b0e97e82211f14ba51ed10b7c9fd10bd70986e0))
* **httpx:** replace httpx with aiohttp ([ea0caf7](https://github.com/obviyus/SuperSeriousBot/commit/ea0caf76675d83839df508b67a7191b79e928f25))
* **yt:** re-work /dl logic ([55206fa](https://github.com/obviyus/SuperSeriousBot/commit/55206fa3c1086fd1ea50a7588ea47ba73a400106))

## [1.80.4](https://github.com/obviyus/SuperSeriousBot/compare/v1.80.3...v1.80.4) (2024-06-22)


### Bug Fixes

* **import:** fix utils ([3ffb399](https://github.com/obviyus/SuperSeriousBot/commit/3ffb399f5b65ec62fd6c3674886bd09e5ce51dae))

## [1.80.3](https://github.com/obviyus/SuperSeriousBot/compare/v1.80.2...v1.80.3) (2024-06-22)


### Bug Fixes

* **main:** fix incorrect utils import ([070c0d9](https://github.com/obviyus/SuperSeriousBot/commit/070c0d9e08a5f5fc26e9c9ff67a982bc595f6d1d))

## [1.80.2](https://github.com/obviyus/SuperSeriousBot/compare/v1.80.1...v1.80.2) (2024-06-22)


### Bug Fixes

* **main:** uncomment workers ([41b55c5](https://github.com/obviyus/SuperSeriousBot/commit/41b55c5ecd7e5c0d1a4e2283774866fbc197c0f4))

## [1.80.1](https://github.com/obviyus/SuperSeriousBot/compare/v1.80.0...v1.80.1) (2024-06-22)


### Bug Fixes

* **init:** fix mention parser ([70d12b1](https://github.com/obviyus/SuperSeriousBot/commit/70d12b186a156bcead08c172061b86ff3ec86bff))

# [1.80.0](https://github.com/obviyus/SuperSeriousBot/compare/v1.79.0...v1.80.0) (2024-06-21)


### Features

* **aiohttp:** move from httpx to aiohttp ([35beb03](https://github.com/obviyus/SuperSeriousBot/commit/35beb0304283028cce2c2a23ecc2af38823fa1d5))
* **aiohttp:** use aiohttp over httpx ([41033a5](https://github.com/obviyus/SuperSeriousBot/commit/41033a5e8d3b8f49e736313352c856455a954a54))
* **calc:** use aiohttp over httpx ([ce7806f](https://github.com/obviyus/SuperSeriousBot/commit/ce7806f53b24e159894866cfdc29ae510061dc2b))
* **gif:** use aiohttp ([de976fd](https://github.com/obviyus/SuperSeriousBot/commit/de976fd704292f78289b4e2b28d7a84d2b480f06))
* **ud:** support wotd + aiohttp ([ff9e736](https://github.com/obviyus/SuperSeriousBot/commit/ff9e73646def3a4336f228857ae5b4ba3e105f73))

# [1.79.0](https://github.com/obviyus/SuperSeriousBot/compare/v1.78.1...v1.79.0) (2024-06-21)


### Features

* **steam:** steam free game notifier ([df232c4](https://github.com/obviyus/SuperSeriousBot/commit/df232c4ef0c1359fec7620af2d66487134692fcd))

## [1.78.1](https://github.com/obviyus/SuperSeriousBot/compare/v1.78.0...v1.78.1) (2024-06-13)


### Bug Fixes

* **remind:** handle timezones in reminders ([f0ec045](https://github.com/obviyus/SuperSeriousBot/commit/f0ec045faa8c3367e5793edc2bf483373bf67f26))
* **translate:** improve text grabber logic ([ac6d12a](https://github.com/obviyus/SuperSeriousBot/commit/ac6d12acf9c8a5308d4c45e732f428f2969df13c))

# [1.78.0](https://github.com/obviyus/SuperSeriousBot/compare/v1.77.1...v1.78.0) (2024-05-14)


### Features

* **tl:** update translation package ([5b05719](https://github.com/obviyus/SuperSeriousBot/commit/5b05719e5d88c69e93a025dcba738b9c47c4ddce))

## [1.77.1](https://github.com/obviyus/SuperSeriousBot/compare/v1.77.0...v1.77.1) (2024-05-08)


### Bug Fixes

* **ask:** remove mini prompt ([9783d52](https://github.com/obviyus/SuperSeriousBot/commit/9783d5205c9e07fd3f2e8887580bbb06d93fc12f))

# [1.77.0](https://github.com/obviyus/SuperSeriousBot/compare/v1.76.5...v1.77.0) (2024-05-03)


### Features

* **ask:** remove /based and use litellm ([630961d](https://github.com/obviyus/SuperSeriousBot/commit/630961dd38723de34330b7bed926fb5cf5961df5))

## [1.76.5](https://github.com/obviyus/SuperSeriousBot/compare/v1.76.4...v1.76.5) (2024-04-28)


### Bug Fixes

* **remind:** check for reminders due within a minute ([5334b75](https://github.com/obviyus/SuperSeriousBot/commit/5334b75fb30ac72c31fbc3e359e1ea4838fec78f))
* **search:** allow in private chats ([d6e45b4](https://github.com/obviyus/SuperSeriousBot/commit/d6e45b47f0af0283f1ff20e8a3839d053debdb48))
* **search:** rebuild fts5 every hour ([6ee9ae8](https://github.com/obviyus/SuperSeriousBot/commit/6ee9ae8fac4878d988cebc05dd5a76d8d044a5ce))
* **stats:** fix stat builder ([30292a5](https://github.com/obviyus/SuperSeriousBot/commit/30292a5d90242a77b625fbaea2bffedf5d9106ba))
* **stats:** handle lowercased usernames ([3b30a2a](https://github.com/obviyus/SuperSeriousBot/commit/3b30a2a90739651d54170db479f3bb162000437f))

## [1.76.4](https://github.com/obviyus/SuperSeriousBot/compare/v1.76.3...v1.76.4) (2024-04-24)


### Bug Fixes

* **search:** improve filter logic for commands ([b1f01ad](https://github.com/obviyus/SuperSeriousBot/commit/b1f01adc1571cb49479d558890f38b4df3b1b06e))

## [1.76.3](https://github.com/obviyus/SuperSeriousBot/compare/v1.76.2...v1.76.3) (2024-04-23)


### Bug Fixes

* **c:** handle different YT URLs ([83ed55a](https://github.com/obviyus/SuperSeriousBot/commit/83ed55ae9884bf6b73a5b34112095826bfe753fa))
* **search:** exclude commands from search ([05b2624](https://github.com/obviyus/SuperSeriousBot/commit/05b2624b05d688973a52ea08ece9da81b1c348a0))

## [1.76.2](https://github.com/obviyus/SuperSeriousBot/compare/v1.76.1...v1.76.2) (2024-04-04)


### Bug Fixes

* **db:** use WAL mode for multiple writers ([db5f4ef](https://github.com/obviyus/SuperSeriousBot/commit/db5f4efa4d4ac610b90cfb8de3f379b67d25cfe3))

## [1.76.1](https://github.com/obviyus/SuperSeriousBot/compare/v1.76.0...v1.76.1) (2024-04-04)


### Bug Fixes

* **import:** fix ijson importing ([7a62b62](https://github.com/obviyus/SuperSeriousBot/commit/7a62b62ffc1ed424f327881ed259aafa7951348f))

# [1.76.0](https://github.com/obviyus/SuperSeriousBot/compare/v1.75.1...v1.76.0) (2024-04-04)


### Features

* **import:** use ijson + aiosqlite to import large chats ([bf80790](https://github.com/obviyus/SuperSeriousBot/commit/bf807902a926004e2582142b9db8946e6a59908e))

## [1.75.1](https://github.com/obviyus/SuperSeriousBot/compare/v1.75.0...v1.75.1) (2024-04-03)


### Bug Fixes

* **increment:** handle duplicates in chat_stats ([31e05df](https://github.com/obviyus/SuperSeriousBot/commit/31e05dfa10a0feaef275a87f4da53e76d3a9a911))

# [1.75.0](https://github.com/obviyus/SuperSeriousBot/compare/v1.74.1...v1.75.0) (2024-04-03)


### Features

* **import:** allow users to import chats into bot ([47e0c55](https://github.com/obviyus/SuperSeriousBot/commit/47e0c55a47a172a833ee4a9e76b6c24b30104351))

## [1.74.1](https://github.com/obviyus/SuperSeriousBot/compare/v1.74.0...v1.74.1) (2024-04-03)


### Bug Fixes

* **result:** remove indexing for fetchone() ([bef7402](https://github.com/obviyus/SuperSeriousBot/commit/bef74021350226055b5328877cb12bc27a467b2a))

# [1.74.0](https://github.com/obviyus/SuperSeriousBot/compare/v1.73.1...v1.74.0) (2024-04-03)


### Features

* **search:** search globally when no user specified ([8ff8d9e](https://github.com/obviyus/SuperSeriousBot/commit/8ff8d9e6b03d9bbb4aa6094880ef4c5387345bc4))

## [1.73.1](https://github.com/obviyus/SuperSeriousBot/compare/v1.73.0...v1.73.1) (2024-04-03)


### Bug Fixes

* **stats:** skip users without username ([da32a90](https://github.com/obviyus/SuperSeriousBot/commit/da32a90b8560e86f2d2a90ed8aedc3d84efc68e9))

# [1.73.0](https://github.com/obviyus/SuperSeriousBot/compare/v1.72.0...v1.73.0) (2024-04-03)


### Features

* **setting:** make fts opt-in ([2d7cd5b](https://github.com/obviyus/SuperSeriousBot/commit/2d7cd5b14debc97d66952e75e902a6a568d1626c))

# [1.72.0](https://github.com/obviyus/SuperSeriousBot/compare/v1.71.1...v1.72.0) (2024-04-03)


### Features

* **search:** create fts for messages ([3fe1c7a](https://github.com/obviyus/SuperSeriousBot/commit/3fe1c7a30bc8ec02cd00db0085139ab6025d7d2d))

## [1.71.1](https://github.com/obviyus/SuperSeriousBot/compare/v1.71.0...v1.71.1) (2024-04-02)


### Bug Fixes

* **asyncio:** gather tasks in parallel ([d16268c](https://github.com/obviyus/SuperSeriousBot/commit/d16268c565faaf887289b65125fee4f779bcae20))

# [1.71.0](https://github.com/obviyus/SuperSeriousBot/compare/v1.70.1...v1.71.0) (2024-04-01)


### Features

* **reaction:** react to bot feedback ([2f4eb73](https://github.com/obviyus/SuperSeriousBot/commit/2f4eb73d0dc9a89fee5ed5aca0ceaeda3ccbe7e6))

## [1.70.1](https://github.com/obviyus/SuperSeriousBot/compare/v1.70.0...v1.70.1) (2024-03-19)


### Bug Fixes

* **wrapper:** return if None in message ([2a8ae9f](https://github.com/obviyus/SuperSeriousBot/commit/2a8ae9f8c4593e4b79ea030b197c267c011e5e90))

# [1.70.0](https://github.com/obviyus/SuperSeriousBot/compare/v1.69.6...v1.70.0) (2024-03-15)


### Features

* **asyncio:** run in parallel ([c297025](https://github.com/obviyus/SuperSeriousBot/commit/c297025760e1f4086643c55c88f14b3fa99550bb))

## [1.69.6](https://github.com/obviyus/SuperSeriousBot/compare/v1.69.5...v1.69.6) (2024-03-11)


### Bug Fixes

* **reaction:** check if reaction allowed in chat ([293d6e6](https://github.com/obviyus/SuperSeriousBot/commit/293d6e6339c13228876be1004f965471f2c31591))

## [1.69.5](https://github.com/obviyus/SuperSeriousBot/compare/v1.69.4...v1.69.5) (2024-03-10)


### Bug Fixes

* **ask:** handle RateLimitError ([34bdb5e](https://github.com/obviyus/SuperSeriousBot/commit/34bdb5ebe9f0c344f462bc5444c351e81537fbbc))

## [1.69.4](https://github.com/obviyus/SuperSeriousBot/compare/v1.69.3...v1.69.4) (2024-03-10)


### Bug Fixes

* **ask:** replace incorrect Exception handler ([dde4962](https://github.com/obviyus/SuperSeriousBot/commit/dde49626ed39cf5bafcd4ac87f2d7b181d671fa5))

## [1.69.3](https://github.com/obviyus/SuperSeriousBot/compare/v1.69.2...v1.69.3) (2024-02-27)


### Bug Fixes

* **dl:** remove ddinstagram fallback ([fe001fc](https://github.com/obviyus/SuperSeriousBot/commit/fe001fc0a486135396b6c0d27e58a41212ad9773))

## [1.69.2](https://github.com/obviyus/SuperSeriousBot/compare/v1.69.1...v1.69.2) (2024-02-26)


### Bug Fixes

* **db:** allow configurable DB path prefix ([41e4348](https://github.com/obviyus/SuperSeriousBot/commit/41e434857578ac1b22d441a6eba74f5003196733))

## [1.69.1](https://github.com/obviyus/SuperSeriousBot/compare/v1.69.0...v1.69.1) (2024-02-21)


### Bug Fixes

* **ask:** use temperature 1.3 ([c230b76](https://github.com/obviyus/SuperSeriousBot/commit/c230b76b2401bf8139be95d1fa05cbe8d25ad0e7))

# [1.69.0](https://github.com/obviyus/SuperSeriousBot/compare/v1.68.0...v1.69.0) (2024-02-15)


### Features

* **remind:** reminder feature ([4da0071](https://github.com/obviyus/SuperSeriousBot/commit/4da00710ad3cf40868ed3de48b739c92df3380e3))

# [1.68.0](https://github.com/obviyus/SuperSeriousBot/compare/v1.67.1...v1.68.0) (2024-01-25)


### Features

* **caption:** allow custom prompts ([ce25e19](https://github.com/obviyus/SuperSeriousBot/commit/ce25e197dd3d009b3f0aa5d1d284c2ace9543226))

## [1.67.1](https://github.com/obviyus/SuperSeriousBot/compare/v1.67.0...v1.67.1) (2024-01-25)


### Bug Fixes

* **caption:** fix check for parent ([0a4659a](https://github.com/obviyus/SuperSeriousBot/commit/0a4659ade908ac0e42b68e505220013939553b05))

# [1.67.0](https://github.com/obviyus/SuperSeriousBot/compare/v1.66.3...v1.67.0) (2024-01-25)


### Features

* **caption:** implement /caption ([909c73f](https://github.com/obviyus/SuperSeriousBot/commit/909c73f7580a587db97d4d0974dd60f71ad2bd81))

## [1.66.3](https://github.com/obviyus/SuperSeriousBot/compare/v1.66.2...v1.66.3) (2024-01-14)


### Bug Fixes

* **dl:** follow redirect in /dl ([06402de](https://github.com/obviyus/SuperSeriousBot/commit/06402de5acabf96acc36d8a0ae6717dc64fb44a8))

## [1.66.2](https://github.com/obviyus/SuperSeriousBot/compare/v1.66.1...v1.66.2) (2023-12-08)


### Bug Fixes

* **dl:** download actual YouTube videos ([9137327](https://github.com/obviyus/SuperSeriousBot/commit/9137327709b0c55e56a716a63122c158a9eb6e33))

## [1.66.1](https://github.com/obviyus/SuperSeriousBot/compare/v1.66.0...v1.66.1) (2023-11-14)


### Bug Fixes

* **whitelist:** filter whitelist by type and ID ([02a3980](https://github.com/obviyus/SuperSeriousBot/commit/02a39801a5ea706ac5d254d937986584b1e13c51))

# [1.66.0](https://github.com/obviyus/SuperSeriousBot/compare/v1.65.1...v1.66.0) (2023-11-13)


### Features

* **ask:** gate /ask behind whitelist ([69407c2](https://github.com/obviyus/SuperSeriousBot/commit/69407c20182f03aad67997576fe6475be51cdc46))

## [1.65.1](https://github.com/obviyus/SuperSeriousBot/compare/v1.65.0...v1.65.1) (2023-10-20)


### Bug Fixes

* **ud:** set User-Agent in call ([3e6571a](https://github.com/obviyus/SuperSeriousBot/commit/3e6571aa034aca370b4d37da2eea5e2c366ba54b))

# [1.65.0](https://github.com/obviyus/SuperSeriousBot/compare/v1.64.1...v1.65.0) (2023-10-19)


### Features

* **cleanup:** remove unused Twitter code ([4003a2c](https://github.com/obviyus/SuperSeriousBot/commit/4003a2cdc70f8e5e2fe3a209ca37298c5e45ca15))

## [1.64.1](https://github.com/obviyus/SuperSeriousBot/compare/v1.64.0...v1.64.1) (2023-10-14)


### Bug Fixes

* **seen:** improve check for message link ([bb49d11](https://github.com/obviyus/SuperSeriousBot/commit/bb49d114ed030bb8601d4a132f9a2c2a79a3c056))

# [1.64.0](https://github.com/obviyus/SuperSeriousBot/compare/v1.63.2...v1.64.0) (2023-10-14)


### Bug Fixes

* **camera:** upgrade to Windy API v3 ([dc24c83](https://github.com/obviyus/SuperSeriousBot/commit/dc24c832902e57d2cfcaea3fc58cebe8c13eb84e))
* **c:** escape markdown for /c ([bee7b79](https://github.com/obviyus/SuperSeriousBot/commit/bee7b79b4b4f46d815b59f03c98279bd7d7cc21d))
* **tl:** translate replied to message ([83d48d5](https://github.com/obviyus/SuperSeriousBot/commit/83d48d54459cc92292f8426bb2ac363356945e1c))


### Features

* **stats:** store last message of user ([246e099](https://github.com/obviyus/SuperSeriousBot/commit/246e099b6b0d7ff8d66a56584737f11124964d83))

## [1.63.2](https://github.com/obviyus/SuperSeriousBot/compare/v1.63.1...v1.63.2) (2023-10-12)


### Bug Fixes

* **lru:** cache async routines using alru_cache ([f965532](https://github.com/obviyus/SuperSeriousBot/commit/f965532fc62894b21360247aaea42cbd84d17701))

## [1.63.1](https://github.com/obviyus/SuperSeriousBot/compare/v1.63.0...v1.63.1) (2023-10-10)


### Bug Fixes

* **docker:** remove user clause ([6319493](https://github.com/obviyus/SuperSeriousBot/commit/6319493e81e5f79bbf800180c05cfcc8d8e358a6))

# [1.63.0](https://github.com/obviyus/SuperSeriousBot/compare/v1.62.0...v1.63.0) (2023-10-10)


### Bug Fixes

* **worker:** reduce social graph frequency ([5e55288](https://github.com/obviyus/SuperSeriousBot/commit/5e552889b5948f56fa9d4b4067a71ebd9fb9ff41))


### Features

* **docker:** use dumb-init ([63e9943](https://github.com/obviyus/SuperSeriousBot/commit/63e994323dc60351c206c0800da91efc78cad2dd))
* **memo:** memoize network call fns ([a1e63b8](https://github.com/obviyus/SuperSeriousBot/commit/a1e63b89b781ec389cc44136ad4cf1b30f1273e8))

# [1.62.0](https://github.com/obviyus/SuperSeriousBot/compare/v1.61.1...v1.62.0) (2023-09-24)


### Features

* **inline:** cache content URLs ([79df3a9](https://github.com/obviyus/SuperSeriousBot/commit/79df3a99f9eb2db41f2a1e8270e1f7508051c68d))

## [1.61.1](https://github.com/obviyus/SuperSeriousBot/compare/v1.61.0...v1.61.1) (2023-09-24)


### Bug Fixes

* **inline:** defer data get until chosen inline result ([481e7ca](https://github.com/obviyus/SuperSeriousBot/commit/481e7ca9312a16244d78f188e11a10b59ae101a2))

# [1.61.0](https://github.com/obviyus/SuperSeriousBot/compare/v1.60.0...v1.61.0) (2023-09-24)


### Features

* **tv:** handle TV streams ([821a388](https://github.com/obviyus/SuperSeriousBot/commit/821a3881a6eca28123700638e4dd471964f335fc))

# [1.60.0](https://github.com/obviyus/SuperSeriousBot/compare/v1.59.2...v1.60.0) (2023-09-24)


### Features

* **tv:** generate streaming links & deprecate TV notifications ([8f4f253](https://github.com/obviyus/SuperSeriousBot/commit/8f4f253c89b69bae455a84486289f58b45839af7))

## [1.59.2](https://github.com/obviyus/SuperSeriousBot/compare/v1.59.1...v1.59.2) (2023-09-12)


### Bug Fixes

* **pic:** remove reference to removed command ([4fa40c2](https://github.com/obviyus/SuperSeriousBot/commit/4fa40c20bdd7655bf1d13ded5ecb1c6cdff564ac))

## [1.59.1](https://github.com/obviyus/SuperSeriousBot/compare/v1.59.0...v1.59.1) (2023-09-12)


### Bug Fixes

* **pic:** remove /pic command ([ae74358](https://github.com/obviyus/SuperSeriousBot/commit/ae7435818e422c5de9f2a12594911cbd94f90ee4))

# [1.59.0](https://github.com/obviyus/SuperSeriousBot/compare/v1.58.3...v1.59.0) (2023-09-12)


### Features

* **webhook:** log port during webhook init ([136ea7c](https://github.com/obviyus/SuperSeriousBot/commit/136ea7c370b7c1280a1e4f4937ad3acf72703c51))

## [1.58.3](https://github.com/obviyus/SuperSeriousBot/compare/v1.58.2...v1.58.3) (2023-09-12)


### Bug Fixes

* **webhook:** remove port from webhook URL ([a867816](https://github.com/obviyus/SuperSeriousBot/commit/a867816edd7f8c7ad87b67eae030933cf27b1b37))

## [1.58.2](https://github.com/obviyus/SuperSeriousBot/compare/v1.58.1...v1.58.2) (2023-09-12)


### Bug Fixes

* **webhook:** embed port in webhook URL ([99cbe58](https://github.com/obviyus/SuperSeriousBot/commit/99cbe5802fa5e1f2cbd991d4bbb3287061a572af))

## [1.58.1](https://github.com/obviyus/SuperSeriousBot/compare/v1.58.0...v1.58.1) (2023-09-12)


### Bug Fixes

* **webhook:** simplify webhook config ([a0f7f24](https://github.com/obviyus/SuperSeriousBot/commit/a0f7f24ee73d00e23d6bee17f7fa6ba262c8da17))

# [1.58.0](https://github.com/obviyus/SuperSeriousBot/compare/v1.57.3...v1.58.0) (2023-09-09)


### Bug Fixes

* **dl:** fix improper response access ([987369c](https://github.com/obviyus/SuperSeriousBot/commit/987369c51507470409ab8b8cf12fba34c30379af))


### Features

* **summon:** create resummon button ([cee4188](https://github.com/obviyus/SuperSeriousBot/commit/cee418886058e3aa2e3bc834d7b614ad9ad54755))

## [1.57.3](https://github.com/obviyus/SuperSeriousBot/compare/v1.57.2...v1.57.3) (2023-09-01)


### Bug Fixes

* **ask:** downgrade to 3.5-turbo ([7a9f3a6](https://github.com/obviyus/SuperSeriousBot/commit/7a9f3a62afa86548c56d29a53fc728650cf31dcc))

## [1.57.2](https://github.com/obviyus/SuperSeriousBot/compare/v1.57.1...v1.57.2) (2023-08-26)


### Bug Fixes

* **reddit:** handle exceptions in reddit worker ([f879242](https://github.com/obviyus/SuperSeriousBot/commit/f8792427623f3e079e6d054c47fde64fcc63388e))

## [1.57.1](https://github.com/obviyus/SuperSeriousBot/compare/v1.57.0...v1.57.1) (2023-07-10)


### Bug Fixes

* **habit:** fix SQL query to since 12AM Monday ([a17201f](https://github.com/obviyus/SuperSeriousBot/commit/a17201f0621162030fdbe4b100827241fccc870e))

# [1.57.0](https://github.com/obviyus/SuperSeriousBot/compare/v1.56.0...v1.57.0) (2023-07-09)


### Features

* **db:** create tables for habits ([706d24e](https://github.com/obviyus/SuperSeriousBot/commit/706d24e49c4a83fc72f27cf901b26144d4672e2c))
* **habit:** new command for `/habit` ([6071534](https://github.com/obviyus/SuperSeriousBot/commit/6071534383f5cbb38c856dd64b7bbd2ccd9e7cab))
* **habits:** add habit worker and button handlers ([6172bac](https://github.com/obviyus/SuperSeriousBot/commit/6172bac8d8be41be6ff8210d43c16f1c9ed040ae))

# [1.56.0](https://github.com/obviyus/SuperSeriousBot/compare/v1.55.1...v1.56.0) (2023-07-07)


### Features

* **ask:** use `simpleaichat` instead of raw API calls ([dbc83f0](https://github.com/obviyus/SuperSeriousBot/commit/dbc83f0d0236c5063425c0242ead7f9964a3d43a))

## [1.55.1](https://github.com/obviyus/SuperSeriousBot/compare/v1.55.0...v1.55.1) (2023-06-10)


### Bug Fixes

* **redis:** allow setting REDIS_PORT ([3f6914b](https://github.com/obviyus/SuperSeriousBot/commit/3f6914b379379a115bfecc1b5703441fe0c986cb))

# [1.55.0](https://github.com/obviyus/SuperSeriousBot/compare/v1.54.4...v1.55.0) (2023-06-10)


### Features

* **redis:** allow specifying REDIS_HOST ([ae43eaa](https://github.com/obviyus/SuperSeriousBot/commit/ae43eaa7897d57af6ad8cfc74b6615bc00bcb1c5))

## [1.54.4](https://github.com/obviyus/SuperSeriousBot/compare/v1.54.3...v1.54.4) (2023-06-09)


### Bug Fixes

* **summon:** fix incorrect callback argument ([8e1d879](https://github.com/obviyus/SuperSeriousBot/commit/8e1d879cde88a6775bdb08f71312b3d47e82c196))

## [1.54.3](https://github.com/obviyus/SuperSeriousBot/compare/v1.54.2...v1.54.3) (2023-06-08)


### Bug Fixes

* **stats:** handle missing username ([927a3d3](https://github.com/obviyus/SuperSeriousBot/commit/927a3d3205888f50dcb5ed3f12098ae53c48d814))

## [1.54.2](https://github.com/obviyus/SuperSeriousBot/compare/v1.54.1...v1.54.2) (2023-06-07)


### Bug Fixes

* **jobs:** allow misfire grace time for long jobs ([b4b6fcf](https://github.com/obviyus/SuperSeriousBot/commit/b4b6fcfb120d720f1a0ad3cedc4a19b1ad827397))

## [1.54.1](https://github.com/obviyus/SuperSeriousBot/compare/v1.54.0...v1.54.1) (2023-06-03)


### Bug Fixes

* **utils:** make username search case insensitive ([0186ede](https://github.com/obviyus/SuperSeriousBot/commit/0186edeeaee60373faddddf86027ec962be8383c))

# [1.54.0](https://github.com/obviyus/SuperSeriousBot/compare/v1.53.3...v1.54.0) (2023-06-02)


### Features

* **dl:** handle fallback instagram case ([f59c9b7](https://github.com/obviyus/SuperSeriousBot/commit/f59c9b739fdb7596b51157c8c922baad43238f8f))

## [1.53.3](https://github.com/obviyus/SuperSeriousBot/compare/v1.53.2...v1.53.3) (2023-05-30)


### Bug Fixes

* **subscribe:** re-order subscription delivery ([517e2ed](https://github.com/obviyus/SuperSeriousBot/commit/517e2ed3959efc57682ee6b909430780b27ae246))

## [1.53.2](https://github.com/obviyus/SuperSeriousBot/compare/v1.53.1...v1.53.2) (2023-05-29)


### Bug Fixes

* **subscribe:** re-add `@` symbol in delivery ([7d2ea07](https://github.com/obviyus/SuperSeriousBot/commit/7d2ea0774d72c054b3322c4eac65c1dbaf540c8a))

## [1.53.1](https://github.com/obviyus/SuperSeriousBot/compare/v1.53.0...v1.53.1) (2023-05-29)


### Bug Fixes

* **subscribe:** change subscribe time ([6976e04](https://github.com/obviyus/SuperSeriousBot/commit/6976e04db54a6b5919a855c81d4e053bc2ce5f6f))
* **subscribe:** fix incorrect command invocation ([83b2f23](https://github.com/obviyus/SuperSeriousBot/commit/83b2f23e0e442e9f1d3622a8ed613f41adc9d81b))

# [1.53.0](https://github.com/obviyus/SuperSeriousBot/compare/v1.52.0...v1.53.0) (2023-05-29)


### Bug Fixes

* **camera:** formatting ([a66d51c](https://github.com/obviyus/SuperSeriousBot/commit/a66d51cd0d93cfe0b4e9bc0174c135824873190d))
* **camera:** handle invalid address ([2b637d2](https://github.com/obviyus/SuperSeriousBot/commit/2b637d2ee9676686889a432d8b97079ecd8252d3))
* **camera:** improve formatting ([5495b62](https://github.com/obviyus/SuperSeriousBot/commit/5495b6216ec5a72afd35e1978df7e7b383134d77))
* **camera:** include time since update ([bacd454](https://github.com/obviyus/SuperSeriousBot/commit/bacd45438e49ffcc8d5546da1c9cc68102a8a931))
* **subscribe:** fix incorrect asyncio implementation ([16568a9](https://github.com/obviyus/SuperSeriousBot/commit/16568a9862b82af42f452882a782043a99fc6605))


### Features

* **camera:** create new command `/cam` ([a844ca2](https://github.com/obviyus/SuperSeriousBot/commit/a844ca2d1c923b30f1c19914945cbe7f7a070cea))

# [1.53.0](https://github.com/obviyus/SuperSeriousBot/compare/v1.52.0...v1.53.0) (2023-05-29)


### Bug Fixes

* **camera:** handle invalid address ([2b637d2](https://github.com/obviyus/SuperSeriousBot/commit/2b637d2ee9676686889a432d8b97079ecd8252d3))
* **camera:** improve formatting ([5495b62](https://github.com/obviyus/SuperSeriousBot/commit/5495b6216ec5a72afd35e1978df7e7b383134d77))
* **camera:** include time since update ([bacd454](https://github.com/obviyus/SuperSeriousBot/commit/bacd45438e49ffcc8d5546da1c9cc68102a8a931))
* **subscribe:** fix incorrect asyncio implementation ([16568a9](https://github.com/obviyus/SuperSeriousBot/commit/16568a9862b82af42f452882a782043a99fc6605))


### Features

* **camera:** create new command `/cam` ([a844ca2](https://github.com/obviyus/SuperSeriousBot/commit/a844ca2d1c923b30f1c19914945cbe7f7a070cea))

# [1.53.0](https://github.com/obviyus/SuperSeriousBot/compare/v1.52.0...v1.53.0) (2023-05-29)


### Bug Fixes

* **camera:** handle invalid address ([2b637d2](https://github.com/obviyus/SuperSeriousBot/commit/2b637d2ee9676686889a432d8b97079ecd8252d3))
* **camera:** include time since update ([bacd454](https://github.com/obviyus/SuperSeriousBot/commit/bacd45438e49ffcc8d5546da1c9cc68102a8a931))
* **subscribe:** fix incorrect asyncio implementation ([16568a9](https://github.com/obviyus/SuperSeriousBot/commit/16568a9862b82af42f452882a782043a99fc6605))


### Features

* **camera:** create new command `/cam` ([a844ca2](https://github.com/obviyus/SuperSeriousBot/commit/a844ca2d1c923b30f1c19914945cbe7f7a070cea))

# [1.53.0](https://github.com/obviyus/SuperSeriousBot/compare/v1.52.0...v1.53.0) (2023-05-29)


### Bug Fixes

* **subscribe:** fix incorrect asyncio implementation ([16568a9](https://github.com/obviyus/SuperSeriousBot/commit/16568a9862b82af42f452882a782043a99fc6605))


### Features

* **camera:** create new command `/cam` ([a844ca2](https://github.com/obviyus/SuperSeriousBot/commit/a844ca2d1c923b30f1c19914945cbe7f7a070cea))

# [1.52.0](https://github.com/obviyus/SuperSeriousBot/compare/v1.51.1...v1.52.0) (2023-05-28)


### Features

* **reddit:** include title in post ([57945c2](https://github.com/obviyus/SuperSeriousBot/commit/57945c2c088ee33d6dad3562836c5bea49e68383))
* **subscribe:** pre-seed posts before sending ([47b4c1c](https://github.com/obviyus/SuperSeriousBot/commit/47b4c1c5a66c12da954a97a9f479c7fd47a05407))

## [1.51.1](https://github.com/obviyus/SuperSeriousBot/compare/v1.51.0...v1.51.1) (2023-05-25)


### Bug Fixes

* **mj:** fix broken function definitions ([335e22d](https://github.com/obviyus/SuperSeriousBot/commit/335e22d5cdaf241efa420e578cb543e966930709))

# [1.51.0](https://github.com/obviyus/SuperSeriousBot/compare/v1.50.1...v1.51.0) (2023-05-25)


### Features

* **mj:** deprecate /mj command ([b5d8968](https://github.com/obviyus/SuperSeriousBot/commit/b5d89680927cd37242e00a9ed16da66130de9ce3))

## [1.50.1](https://github.com/obviyus/SuperSeriousBot/compare/v1.50.0...v1.50.1) (2023-05-24)


### Bug Fixes

* **ask:** reply on exceptions ([0a03449](https://github.com/obviyus/SuperSeriousBot/commit/0a034498ed43b5ac4c8f6e9d6c33f943671c56ae))

# [1.50.0](https://github.com/obviyus/SuperSeriousBot/compare/v1.49.1...v1.50.0) (2023-05-23)


### Bug Fixes

* **ask:** make queries async ([0a47c93](https://github.com/obviyus/SuperSeriousBot/commit/0a47c934f33e932cc35894ee626cb46dadb0fdb3))
* **ud:** handle long messages ([98be12a](https://github.com/obviyus/SuperSeriousBot/commit/98be12a83c81b1a2a424213500c6636992e67046))


### Features

* **ask:** improve based GPT jailbreak ([a204cd3](https://github.com/obviyus/SuperSeriousBot/commit/a204cd39f2403ebaee5313646e2624b369f463e9))

## [1.49.1](https://github.com/obviyus/SuperSeriousBot/compare/v1.49.0...v1.49.1) (2023-05-13)


### Bug Fixes

* **tldr:** return correct error message ([d1e9ddc](https://github.com/obviyus/SuperSeriousBot/commit/d1e9ddc4df3331c4c9cdc189db247549e078c84f))

# [1.49.0](https://github.com/obviyus/SuperSeriousBot/compare/v1.48.0...v1.49.0) (2023-05-07)


### Bug Fixes

* **store:** re-add reply to get'd object ([351f9d0](https://github.com/obviyus/SuperSeriousBot/commit/351f9d0eb8ae42cf49da7f990859972bf14120a6))


### Features

* **object:** return fetch count for objects ([6669238](https://github.com/obviyus/SuperSeriousBot/commit/666923866838e26f6665553845e99671fcda0eb4))
* **quote:** allow filtering quote by user ([3eb6189](https://github.com/obviyus/SuperSeriousBot/commit/3eb61898f1ec41977851f81e28375cf4db90e488))
* **store:** don't delete on /get reply ([bd58e76](https://github.com/obviyus/SuperSeriousBot/commit/bd58e76ee651c70d8b990c89f5024566d0d41025))
* **store:** increment fetch count for objects ([c5dfb0c](https://github.com/obviyus/SuperSeriousBot/commit/c5dfb0cd86bec9faef4a563dc9f2d87fb3378969))
* **summon:** filter out removed users ([6bbf2fa](https://github.com/obviyus/SuperSeriousBot/commit/6bbf2fa89b1e4bc9970c036aa90b3dd70f3f9555))
* **weather:** include apparent temperature ([fbbf3cf](https://github.com/obviyus/SuperSeriousBot/commit/fbbf3cf8002ae5cc24cbb09506bd03b992ae0313))

# [1.48.0](https://github.com/obviyus/SuperSeriousBot/compare/v1.47.4...v1.48.0) (2023-04-02)


### Bug Fixes

* **movie:** remove duplicate key ([8c48589](https://github.com/obviyus/SuperSeriousBot/commit/8c48589e7cd619be598d618241d3887df251662a))


### Features

* **weather:** include AQI and remove forecast ([4a0d41a](https://github.com/obviyus/SuperSeriousBot/commit/4a0d41aa2530df104b91fdcb6c0d9187ffa08f26))

## [1.47.4](https://github.com/obviyus/SuperSeriousBot/compare/v1.47.3...v1.47.4) (2023-03-24)


### Bug Fixes

* **imports:** update imports for ruff ([31f0505](https://github.com/obviyus/SuperSeriousBot/commit/31f0505a03ef2457bae21613bfb4374b51f4d506))

## [1.47.3](https://github.com/obviyus/SuperSeriousBot/compare/v1.47.2...v1.47.3) (2023-03-24)


### Bug Fixes

* **meme:** update endpoint for meme ([b1c99d1](https://github.com/obviyus/SuperSeriousBot/commit/b1c99d123ae0f93934d0a78b75ad89bd15ff228e))

## [1.47.2](https://github.com/obviyus/SuperSeriousBot/compare/v1.47.1...v1.47.2) (2023-03-17)


### Bug Fixes

* **http:** downgrade to HTTP/1.1 ([69c8812](https://github.com/obviyus/SuperSeriousBot/commit/69c881228fc9ed5cfb1361c465f9c9543524f229))

## [1.47.1](https://github.com/obviyus/SuperSeriousBot/compare/v1.47.0...v1.47.1) (2023-03-14)


### Bug Fixes

* **worker:** change command reset time ([24ca596](https://github.com/obviyus/SuperSeriousBot/commit/24ca5962c055e1b8fa2b38fc96d5082bd563b1a6))
* **worker:** change command signature for reset ([db823f1](https://github.com/obviyus/SuperSeriousBot/commit/db823f1279344db6b2eecab5eb14789d7ae60fdf))

# [1.47.0](https://github.com/obviyus/SuperSeriousBot/compare/v1.46.2...v1.47.0) (2023-03-13)


### Features

* **summon:** split summons when > 5 ([a133cb7](https://github.com/obviyus/SuperSeriousBot/commit/a133cb7e8308dab5f7a176129accabee4a6cbe42))

## [1.46.2](https://github.com/obviyus/SuperSeriousBot/compare/v1.46.1...v1.46.2) (2023-03-12)


### Bug Fixes

* **dl:** fix check for hostname ([882f54c](https://github.com/obviyus/SuperSeriousBot/commit/882f54c45a3c5aef318537209d37002023238842))

## [1.46.1](https://github.com/obviyus/SuperSeriousBot/compare/v1.46.0...v1.46.1) (2023-03-12)


### Bug Fixes

* **dl:** handle case for insgram.com URLs ([60ccf7d](https://github.com/obviyus/SuperSeriousBot/commit/60ccf7d260fe3b944e767aa80520ad4b5551c13a))

# [1.46.0](https://github.com/obviyus/SuperSeriousBot/compare/v1.45.2...v1.46.0) (2023-03-12)


### Features

* **dl:** support Instagram downloads with RapidAPI ([c6ca26c](https://github.com/obviyus/SuperSeriousBot/commit/c6ca26c30fa44ad01fa7df00a54c944e5ef1fc58))

## [1.45.2](https://github.com/obviyus/SuperSeriousBot/compare/v1.45.1...v1.45.2) (2023-03-10)


### Bug Fixes

* **reset:** update reset query ([3c5d0a6](https://github.com/obviyus/SuperSeriousBot/commit/3c5d0a6f552244786199baa8d308e9e0e28542de))

## [1.45.1](https://github.com/obviyus/SuperSeriousBot/compare/v1.45.0...v1.45.1) (2023-03-09)


### Bug Fixes

* **limits:** fix for resetting command usage limits ([40f31a0](https://github.com/obviyus/SuperSeriousBot/commit/40f31a05c8906717b2dae78198bc9e03b4721346))

# [1.45.0](https://github.com/obviyus/SuperSeriousBot/compare/v1.44.0...v1.45.0) (2023-03-07)


### Features

* **limit:** limit command usage ([bbfea64](https://github.com/obviyus/SuperSeriousBot/commit/bbfea64807523f88d816273a4fc6e02c981ef8bc))

# [1.44.0](https://github.com/obviyus/SuperSeriousBot/compare/v1.43.0...v1.44.0) (2023-03-07)


### Features

* **gpt:** create GPT jailbreak command ([6aa6127](https://github.com/obviyus/SuperSeriousBot/commit/6aa612711bce8dbfc84ffe78c2c4a93a0d01a21d))

# [1.43.0](https://github.com/obviyus/SuperSeriousBot/compare/v1.42.0...v1.43.0) (2023-03-07)


### Features

* **ask:** implement /ask using GPT-3.5-turbo ([507e36b](https://github.com/obviyus/SuperSeriousBot/commit/507e36babee30913a6b736cadccf52c712a76d41))

# [1.42.0](https://github.com/obviyus/SuperSeriousBot/compare/v1.41.4...v1.42.0) (2023-01-22)


### Features

* **quote:** `/addquote` now forwards messages to channel ([d786194](https://github.com/obviyus/SuperSeriousBot/commit/d786194f28e3b6b6408f59c86faf7fec2920c306))

## [1.41.4](https://github.com/obviyus/SuperSeriousBot/compare/v1.41.3...v1.41.4) (2023-01-11)


### Bug Fixes

* **imagine:** remove unused command ([689b07a](https://github.com/obviyus/SuperSeriousBot/commit/689b07aa8c0a560e7e67775b175b8e10e4e0938c))

## [1.41.3](https://github.com/obviyus/SuperSeriousBot/compare/v1.41.2...v1.41.3) (2022-12-22)


### Bug Fixes

* **summon:** update group list on join/part ([1123b7d](https://github.com/obviyus/SuperSeriousBot/commit/1123b7dd9e2f2c07f24f2a36de5fb862d6ff6a02))

## [1.41.2](https://github.com/obviyus/SuperSeriousBot/compare/v1.41.1...v1.41.2) (2022-12-02)


### Bug Fixes

* **imagine:** verbose error messages ([31de5e0](https://github.com/obviyus/SuperSeriousBot/commit/31de5e07ade2934bacb08d276562c384449b7fa2))

## [1.41.1](https://github.com/obviyus/SuperSeriousBot/compare/v1.41.0...v1.41.1) (2022-12-02)


### Bug Fixes

* **deps:** create dep for APScheduler ([c1cdc0b](https://github.com/obviyus/SuperSeriousBot/commit/c1cdc0bef81c418e0a6faa2e463454af4df20cee))

# [1.41.0](https://github.com/obviyus/SuperSeriousBot/compare/v1.40.0...v1.41.0) (2022-12-02)


### Features

* **imagine:** create command to invoke Dall-E ([0707b7d](https://github.com/obviyus/SuperSeriousBot/commit/0707b7d5e4c7aed8e9823180b7338e1392c17e61))

# [1.40.0](https://github.com/obviyus/SuperSeriousBot/compare/v1.39.1...v1.40.0) (2022-11-19)


### Features

* **yt:** new function to subscribe to YouTube channels ([343f3b0](https://github.com/obviyus/SuperSeriousBot/commit/343f3b0f9901360b162dd4838dfc13ad9502ffe7))

## [1.39.1](https://github.com/obviyus/SuperSeriousBot/compare/v1.39.0...v1.39.1) (2022-11-19)


### Bug Fixes

* **build:** re-add ffmpeg dependency ([9b5f415](https://github.com/obviyus/SuperSeriousBot/commit/9b5f415f84e7ea4345dbdb37daff4591ec3fd011))

# [1.39.0](https://github.com/obviyus/SuperSeriousBot/compare/v1.38.1...v1.39.0) (2022-11-13)


### Bug Fixes

* **c:** improved comment escaping by Markdown ([a56f428](https://github.com/obviyus/SuperSeriousBot/commit/a56f4282d4d9815ec981ec5e545d614969502776))
* **dl:** always reply to invoking message ([99e8626](https://github.com/obviyus/SuperSeriousBot/commit/99e862619d0fe06cdb5a72b67718ab652c7ca2ad))
* **tl:** handle unknown language error ([45fac2e](https://github.com/obviyus/SuperSeriousBot/commit/45fac2e0fa04e9964caf1ae884056c3599317079))


### Features

* **3.11:** bump to Python 3.11 ([88bbfb1](https://github.com/obviyus/SuperSeriousBot/commit/88bbfb1a8528bcbe162717e668844bda6aafc102))

## [1.38.1](https://github.com/obviyus/SuperSeriousBot/compare/v1.38.0...v1.38.1) (2022-10-25)


### Bug Fixes

* **highlight:** make function case insensitive ([95f21f6](https://github.com/obviyus/SuperSeriousBot/commit/95f21f69045443bdbfb1bdbbd07ea45ab6482585))

# [1.38.0](https://github.com/obviyus/SuperSeriousBot/compare/v1.37.0...v1.38.0) (2022-10-25)


### Bug Fixes

* **summon:** make group names case insensitive ([b4dc25b](https://github.com/obviyus/SuperSeriousBot/commit/b4dc25b492239dc13c71d0c3c15aa33f1bc661c5))


### Features

* **highlight:** create new highlights feature ([26f5e2c](https://github.com/obviyus/SuperSeriousBot/commit/26f5e2c3badc8cb690463ec02dca12e6c025322d))

# [1.37.0](https://github.com/obviyus/SuperSeriousBot/compare/v1.36.6...v1.37.0) (2022-10-25)


### Features

* **summon:** make group name case insensitive ([0a09157](https://github.com/obviyus/SuperSeriousBot/commit/0a09157fed437753fe77549c8fdd107b193239a5))

## [1.36.6](https://github.com/obviyus/SuperSeriousBot/compare/v1.36.5...v1.36.6) (2022-10-24)


### Bug Fixes

* **ping:** fix latency measurement ([c03bf23](https://github.com/obviyus/SuperSeriousBot/commit/c03bf23ee664115b9e8035ef68bab7276ff5f606))

## [1.36.5](https://github.com/obviyus/SuperSeriousBot/compare/v1.36.4...v1.36.5) (2022-10-24)


### Bug Fixes

* **link:** check for message in link grabber ([b8ec067](https://github.com/obviyus/SuperSeriousBot/commit/b8ec0677b5b4b95f2e8c2de70511630082b8376d))

## [1.36.4](https://github.com/obviyus/SuperSeriousBot/compare/v1.36.3...v1.36.4) (2022-10-23)


### Bug Fixes

* **link:** return None if empty message ([54f8555](https://github.com/obviyus/SuperSeriousBot/commit/54f8555de0f7d66e465e248acb6be5dab060fe0e))

## [1.36.3](https://github.com/obviyus/SuperSeriousBot/compare/v1.36.2...v1.36.3) (2022-10-23)


### Bug Fixes

* **links:** improve link parsing logic ([b979aec](https://github.com/obviyus/SuperSeriousBot/commit/b979aec16b9e0c7c4d708b0ef61ae5bc52a3489c))
* **tl|tts:** improve text grabbing logic ([68319f5](https://github.com/obviyus/SuperSeriousBot/commit/68319f505b3535f44758171d5803f413ca9f4e6a))
* **twitter:** fix check for error ([5eb0f37](https://github.com/obviyus/SuperSeriousBot/commit/5eb0f37c859406f342f3302122bf6b5c82da23a0))

## [1.36.2](https://github.com/obviyus/SuperSeriousBot/compare/v1.36.1...v1.36.2) (2022-10-22)


### Bug Fixes

* **dl:** handle Reddit crossposts ([67e18b1](https://github.com/obviyus/SuperSeriousBot/commit/67e18b11dafbce5ac7493a95de1823e38578ac70))

## [1.36.1](https://github.com/obviyus/SuperSeriousBot/compare/v1.36.0...v1.36.1) (2022-10-22)


### Bug Fixes

* **summon:** fix string for usage ([80d3f80](https://github.com/obviyus/SuperSeriousBot/commit/80d3f8094b52e33b4c819fcd2f718af236fd4b1f))

# [1.36.0](https://github.com/obviyus/SuperSeriousBot/compare/v1.35.3...v1.36.0) (2022-10-22)


### Features

* **summon:** create summon command ([1020f06](https://github.com/obviyus/SuperSeriousBot/commit/1020f06931643f5c9e6d18cfa800d515a6e481a9))

## [1.35.3](https://github.com/obviyus/SuperSeriousBot/compare/v1.35.2...v1.35.3) (2022-10-22)


### Bug Fixes

* **c:** escape more chars from Reddit MD ([466a254](https://github.com/obviyus/SuperSeriousBot/commit/466a2546ac691522a78b81a4124c308e34a78f8d))
* **dl:** reduce max size to 45M ([6834cf5](https://github.com/obviyus/SuperSeriousBot/commit/6834cf5d3a1066288e1df2c0d7accf3b8097a929))

## [1.35.2](https://github.com/obviyus/SuperSeriousBot/compare/v1.35.1...v1.35.2) (2022-10-21)


### Bug Fixes

* **dl:** return reason for failure ([f52f378](https://github.com/obviyus/SuperSeriousBot/commit/f52f378812ac1d2fcc740f413c96ab3ffa48bc48))

## [1.35.1](https://github.com/obviyus/SuperSeriousBot/compare/v1.35.0...v1.35.1) (2022-10-17)


### Bug Fixes

* **r:** fix immediate response when empty ([885f43a](https://github.com/obviyus/SuperSeriousBot/commit/885f43a0aaa164b187f71209128447cb3142b15b))

# [1.35.0](https://github.com/obviyus/SuperSeriousBot/compare/v1.34.0...v1.35.0) (2022-10-17)


### Features

* **misc:** create more playtime commands ([1654f53](https://github.com/obviyus/SuperSeriousBot/commit/1654f53c245c0fb4deedd7555b3bcd9cf4d2bd4a))

# [1.34.0](https://github.com/obviyus/SuperSeriousBot/compare/v1.33.3...v1.34.0) (2022-10-17)


### Features

* **er:** steam playtime for ER ([d092fd9](https://github.com/obviyus/SuperSeriousBot/commit/d092fd9aab67d3e9e84bd1d24fa26786a09b0fb1))

## [1.33.3](https://github.com/obviyus/SuperSeriousBot/compare/v1.33.2...v1.33.3) (2022-10-16)


### Bug Fixes

* **r:** fix command for alternate usage ([80e843d](https://github.com/obviyus/SuperSeriousBot/commit/80e843da85b79473632b64a1d5d9a2df7f7fa5c9))

## [1.33.2](https://github.com/obviyus/SuperSeriousBot/compare/v1.33.1...v1.33.2) (2022-10-16)


### Bug Fixes

* **r:** perform check before to avoid exception ([b121d39](https://github.com/obviyus/SuperSeriousBot/commit/b121d39b3fac63e01ea78a56b64f638c0cca6ab9))

## [1.33.1](https://github.com/obviyus/SuperSeriousBot/compare/v1.33.0...v1.33.1) (2022-10-15)


### Bug Fixes

* **c:** escape `-` character ([0dd99f8](https://github.com/obviyus/SuperSeriousBot/commit/0dd99f8b7f3ef0865ca76bcd4a8f3670c0db161c))
* **graph:** update networkx API ([e16e811](https://github.com/obviyus/SuperSeriousBot/commit/e16e811809786e34de51a2cc23b6c0ff5ad9c0ed))
* **hltb:** update API consumers for new response ([f0c46c5](https://github.com/obviyus/SuperSeriousBot/commit/f0c46c5ad05271dfbf5b19e3752ba10f8a701199))
* **vision:** remove Azure APIs ([cf207bc](https://github.com/obviyus/SuperSeriousBot/commit/cf207bc7e2c959eea165c91f3fbea14938b86790))

# [1.33.0](https://github.com/obviyus/SuperSeriousBot/compare/v1.32.4...v1.33.0) (2022-10-13)


### Features

* **tr:** transcribe audio using Whisper ([c415360](https://github.com/obviyus/SuperSeriousBot/commit/c415360faf65f4761c983e7340cd98e136f0fc11))

## [1.32.4](https://github.com/obviyus/SuperSeriousBot/compare/v1.32.3...v1.32.4) (2022-10-12)


### Bug Fixes

* **dl:** fix pattern match for `v.redd.it` links ([b4af92b](https://github.com/obviyus/SuperSeriousBot/commit/b4af92ba169ada368c592d25485e2a85f0034fdf))

## [1.32.3](https://github.com/obviyus/SuperSeriousBot/compare/v1.32.2...v1.32.3) (2022-10-02)


### Bug Fixes

* **link:** send text if no video available ([bfce732](https://github.com/obviyus/SuperSeriousBot/commit/bfce7322239d4145140d1e240f7b53a26821a875))

## [1.32.2](https://github.com/obviyus/SuperSeriousBot/compare/v1.32.1...v1.32.2) (2022-10-01)


### Bug Fixes

* **twitter:** check for error ([648042e](https://github.com/obviyus/SuperSeriousBot/commit/648042eb74ca9d78d4a817f95d83af8faf11df0a))

## [1.32.1](https://github.com/obviyus/SuperSeriousBot/compare/v1.32.0...v1.32.1) (2022-09-28)


### Bug Fixes

* **usage:** fix usage_string for /spurdo ([8f81bcd](https://github.com/obviyus/SuperSeriousBot/commit/8f81bcdba4734c2133eb93e2c0d781dd5ff53d2a))

# [1.32.0](https://github.com/obviyus/SuperSeriousBot/compare/v1.31.0...v1.32.0) (2022-09-28)


### Features

* **law:** create `/cpc` command ([33b6f5b](https://github.com/obviyus/SuperSeriousBot/commit/33b6f5b2972d29b1cb6005cdbfd14753f0a21504))

# [1.31.0](https://github.com/obviyus/SuperSeriousBot/compare/v1.30.2...v1.31.0) (2022-09-28)


### Features

* **ipc:** create new /ipc and /crpc commands ([5af9d45](https://github.com/obviyus/SuperSeriousBot/commit/5af9d4541be79d19e307fabec8b833c3133966f7))

## [1.30.2](https://github.com/obviyus/SuperSeriousBot/compare/v1.30.1...v1.30.2) (2022-09-24)


### Bug Fixes

* **rate:** set `max_retries` to 10 ([721f22b](https://github.com/obviyus/SuperSeriousBot/commit/721f22bd8aba0691ee5ea921893838d11101dc2b))

## [1.30.1](https://github.com/obviyus/SuperSeriousBot/compare/v1.30.0...v1.30.1) (2022-09-21)


### Bug Fixes

* **link:** set `Timeout=None` for Twitter previews ([d9cc15a](https://github.com/obviyus/SuperSeriousBot/commit/d9cc15aee2e4cc53acf49a58d9403e10921dabe9))

# [1.30.0](https://github.com/obviyus/SuperSeriousBot/compare/v1.29.2...v1.30.0) (2022-09-04)


### Bug Fixes

* **tl:** handle NoResult ([1f54ebd](https://github.com/obviyus/SuperSeriousBot/commit/1f54ebd9a4ad9beffe19b0e527d9715fab502e67))


### Features

* **tv:** include runtime in response ([9d0a407](https://github.com/obviyus/SuperSeriousBot/commit/9d0a40798f17223ebd7f0d74028d0a825075435b))

## [1.29.2](https://github.com/obviyus/SuperSeriousBot/compare/v1.29.1...v1.29.2) (2022-08-28)


### Bug Fixes

* **graph:** fix edge mapping ([d052e13](https://github.com/obviyus/SuperSeriousBot/commit/d052e134f61fbc0aef73fc5fa4280b8f8a829cc3))

## [1.29.1](https://github.com/obviyus/SuperSeriousBot/compare/v1.29.0...v1.29.1) (2022-08-28)


### Bug Fixes

* **graph:** remove interactions with self ([e0168a0](https://github.com/obviyus/SuperSeriousBot/commit/e0168a009f34687009355c1b04ec3798b6a283e3))

# [1.29.0](https://github.com/obviyus/SuperSeriousBot/compare/v1.28.0...v1.29.0) (2022-08-28)


### Features

* **graph:** use networkx for graph building ([0ba2fa5](https://github.com/obviyus/SuperSeriousBot/commit/0ba2fa5f3c07f97e689d7b398e8b7775e21d9b5a))

# [1.28.0](https://github.com/obviyus/SuperSeriousBot/compare/v1.27.1...v1.28.0) (2022-08-28)


### Bug Fixes

* **utils:** fallback to user_id ([379a0e1](https://github.com/obviyus/SuperSeriousBot/commit/379a0e19c0f6e123a49d95c49ab2a53166100b11))


### Features

* **graph:** show top 3 ranks ([32b2ce5](https://github.com/obviyus/SuperSeriousBot/commit/32b2ce547085ec3ca8725d962a2c5e56a7f8a010))

## [1.27.1](https://github.com/obviyus/SuperSeriousBot/compare/v1.27.0...v1.27.1) (2022-08-28)


### Bug Fixes

* **graph:** fix URL to graph ([87bc69d](https://github.com/obviyus/SuperSeriousBot/commit/87bc69d23a0be21f79edb105a467b6ea9fb98674))

# [1.27.0](https://github.com/obviyus/SuperSeriousBot/compare/v1.26.0...v1.27.0) (2022-08-28)


### Features

* **graph:** fix formatting ([405fdfc](https://github.com/obviyus/SuperSeriousBot/commit/405fdfce855bfa9f36af9faf5e113531eda00474))

# [1.26.0](https://github.com/obviyus/SuperSeriousBot/compare/v1.25.0...v1.26.0) (2022-08-28)


### Features

* **graph:** include check for activity ([e9a01dc](https://github.com/obviyus/SuperSeriousBot/commit/e9a01dcd5c2d4f412f83710d50bf4e99c7ebd6db))

# [1.25.0](https://github.com/obviyus/SuperSeriousBot/compare/v1.24.0...v1.25.0) (2022-08-28)


### Bug Fixes

* **dl:** remove ParseReddit from Reddit URLs ([cee0795](https://github.com/obviyus/SuperSeriousBot/commit/cee0795d3530ccc3cbc7a07b4fdf10bcf1bc6edc))
* **d:** remove optional lang parameter ([1004d73](https://github.com/obviyus/SuperSeriousBot/commit/1004d73bec4b205974f27560b4fff91643bf7f22))


### Features

* **graph:** create commands for social graph ([c3dae9d](https://github.com/obviyus/SuperSeriousBot/commit/c3dae9d0af1ac9d6de37636e6df69479cc84c805))

# [1.24.0](https://github.com/obviyus/SuperSeriousBot/compare/v1.23.1...v1.24.0) (2022-08-28)


### Bug Fixes

* **sleep:** remove Reddit delivery sleep ([b2e437a](https://github.com/obviyus/SuperSeriousBot/commit/b2e437ab4e58708421cf6b4ab3557b3a89d3eae5))


### Features

* **rate:** use AIORateLimiter ([3da6671](https://github.com/obviyus/SuperSeriousBot/commit/3da66719b1a38388475e2ea973bfcd1fea4200ad))

## [1.23.1](https://github.com/obviyus/SuperSeriousBot/compare/v1.23.0...v1.23.1) (2022-08-24)


### Bug Fixes

* **main:** remove chosen result handler ([3dde62a](https://github.com/obviyus/SuperSeriousBot/commit/3dde62aacc44bed43b1cfcf45732b38c87111d7f))

# [1.23.0](https://github.com/obviyus/SuperSeriousBot/compare/v1.22.12...v1.23.0) (2022-08-24)


### Features

* **tv:** Add IMDb search inline ([c268967](https://github.com/obviyus/SuperSeriousBot/commit/c268967817d77452da64e002de79f757f5a278f9))

## [1.22.12](https://github.com/obviyus/SuperSeriousBot/compare/v1.22.11...v1.22.12) (2022-08-23)


### Bug Fixes

* **seen:** use correct func argument ([bde79e7](https://github.com/obviyus/SuperSeriousBot/commit/bde79e7623343bdf22da386690030c5f1d7d38e4))

## [1.22.11](https://github.com/obviyus/SuperSeriousBot/compare/v1.22.10...v1.22.11) (2022-08-23)


### Bug Fixes

* **r:** await coroutine in spoiler check ([f1a6468](https://github.com/obviyus/SuperSeriousBot/commit/f1a6468960d5263fdaaf6de61b5858ea7fa01cbf))
* **stats:** check for username in seen ([c4e7e33](https://github.com/obviyus/SuperSeriousBot/commit/c4e7e33c4177e479cae90e91ae52b52b797a5988))

## [1.22.10](https://github.com/obviyus/SuperSeriousBot/compare/v1.22.9...v1.22.10) (2022-08-16)


### Bug Fixes

* **tv:** handle shows without a cover image ([592a19f](https://github.com/obviyus/SuperSeriousBot/commit/592a19f11d82746d03c2a15e302d26e47491bad4))

## [1.22.9](https://github.com/obviyus/SuperSeriousBot/compare/v1.22.8...v1.22.9) (2022-08-16)


### Bug Fixes

* **link:** check for empty hostname ([bc5e439](https://github.com/obviyus/SuperSeriousBot/commit/bc5e439a062f90d21055763fc0fd1f70d3a8d2b6))

## [1.22.8](https://github.com/obviyus/SuperSeriousBot/compare/v1.22.7...v1.22.8) (2022-08-16)


### Bug Fixes

* **tv:** use `chat_id` in callback data ([502067b](https://github.com/obviyus/SuperSeriousBot/commit/502067be292432a166bd172ea69a03684be1a897))

## [1.22.7](https://github.com/obviyus/SuperSeriousBot/compare/v1.22.6...v1.22.7) (2022-08-16)


### Bug Fixes

* **r:** avoid await inside a job queue ([893ab78](https://github.com/obviyus/SuperSeriousBot/commit/893ab78e1f010124b81c1a6ade8d8c447ebc9bc7))
* **tl:** improve error handling ([a65a9f1](https://github.com/obviyus/SuperSeriousBot/commit/a65a9f15d9a57507f19ae253e046f5c068271ba2))

## [1.22.6](https://github.com/obviyus/SuperSeriousBot/compare/v1.22.5...v1.22.6) (2022-08-12)


### Bug Fixes

* **quote:** handle deleted messages ([369accc](https://github.com/obviyus/SuperSeriousBot/commit/369accc102544e173e6bb87cbaf1eccbfeb0bb83))

## [1.22.5](https://github.com/obviyus/SuperSeriousBot/compare/v1.22.4...v1.22.5) (2022-08-12)


### Bug Fixes

* **stats:** use total count for stats ([e47a1c6](https://github.com/obviyus/SuperSeriousBot/commit/e47a1c60d5fdfa4c9f0fb2689e149733250df7d6))

## [1.22.4](https://github.com/obviyus/SuperSeriousBot/compare/v1.22.3...v1.22.4) (2022-08-12)


### Bug Fixes

* **r:** await coroutines in fallback post ([aa52518](https://github.com/obviyus/SuperSeriousBot/commit/aa525187ea923b322610f0f7b6198200003dba60))

## [1.22.3](https://github.com/obviyus/SuperSeriousBot/compare/v1.22.2...v1.22.3) (2022-08-11)


### Bug Fixes

* **dl:** perform check for file in redvid ([0c1b400](https://github.com/obviyus/SuperSeriousBot/commit/0c1b4000163c02f32fd09f9e8a82584c7f4284bd))

## [1.22.2](https://github.com/obviyus/SuperSeriousBot/compare/v1.22.1...v1.22.2) (2022-08-11)


### Bug Fixes

* **str:** improve numeric formatting ([653eb93](https://github.com/obviyus/SuperSeriousBot/commit/653eb93097e52549737716636ccd7b8902eab0c9))

## [1.22.1](https://github.com/obviyus/SuperSeriousBot/compare/v1.22.0...v1.22.1) (2022-08-08)


### Bug Fixes

* **c:** escape `(` and `)` in Reddit markdown ([33622cf](https://github.com/obviyus/SuperSeriousBot/commit/33622cf3747f6fc389328fd6aa72de812e3b17c6))

# [1.22.0](https://github.com/obviyus/SuperSeriousBot/compare/v1.21.3...v1.22.0) (2022-08-07)


### Features

* **mj:** create command for returning random MidJourney images ([2d18d85](https://github.com/obviyus/SuperSeriousBot/commit/2d18d85024262e19fba8e9744ed680051a8113c4))

## [1.21.3](https://github.com/obviyus/SuperSeriousBot/compare/v1.21.2...v1.21.3) (2022-08-06)


### Bug Fixes

* **link:** remove broken import ([aa3abf0](https://github.com/obviyus/SuperSeriousBot/commit/aa3abf08b22f819c57c84ee9683e9465c51dbb60))

## [1.21.2](https://github.com/obviyus/SuperSeriousBot/compare/v1.21.1...v1.21.2) (2022-08-06)


### Bug Fixes

* **links:** fix regression from last commit ([b285f71](https://github.com/obviyus/SuperSeriousBot/commit/b285f71056d313e84b58034a4a504b29540853ab))

## [1.21.1](https://github.com/obviyus/SuperSeriousBot/compare/v1.21.0...v1.21.1) (2022-08-06)


### Bug Fixes

* **link:** handle reply checker with exceptions ([a0c9d9d](https://github.com/obviyus/SuperSeriousBot/commit/a0c9d9d8451a05936bf466eb7ab896fc94ce1358))

# [1.21.0](https://github.com/obviyus/SuperSeriousBot/compare/v1.20.0...v1.21.0) (2022-08-06)


### Bug Fixes

* **string:** round readable numbers ([e6b7bf4](https://github.com/obviyus/SuperSeriousBot/commit/e6b7bf4445e278fb109dab9f87386cb05b713657))


### Features

* **viz:** change solver to `forceAtlas2Based` ([8b68e73](https://github.com/obviyus/SuperSeriousBot/commit/8b68e73dd10ad1a3eaa3a21147f78a3b78f76b6b))

# [1.20.0](https://github.com/obviyus/SuperSeriousBot/compare/v1.19.0...v1.20.0) (2022-08-06)


### Features

* **viz:** visualise social graph for chats ([095cc6d](https://github.com/obviyus/SuperSeriousBot/commit/095cc6dcb18576986c4aa2cba49e2ad9c15f366c))

# [1.19.0](https://github.com/obviyus/SuperSeriousBot/compare/v1.18.2...v1.19.0) (2022-08-06)


### Features

* **mentions:** measure reply frequency ([4bbc72b](https://github.com/obviyus/SuperSeriousBot/commit/4bbc72be301a82157e127c5ae675d401b1ed440f))

## [1.18.2](https://github.com/obviyus/SuperSeriousBot/compare/v1.18.1...v1.18.2) (2022-08-05)


### Bug Fixes

* **dl:** remove `old.` prefix from Reddit URLs ([7406601](https://github.com/obviyus/SuperSeriousBot/commit/7406601e9d53c6a48b7a0099dff62bff4acae75f))
* **subs:** re-add list subscriptions command ([5506c39](https://github.com/obviyus/SuperSeriousBot/commit/5506c3988b505793cc661a46ea563d98314975db))

## [1.18.1](https://github.com/obviyus/SuperSeriousBot/compare/v1.18.0...v1.18.1) (2022-08-05)


### Bug Fixes

* **dl:** refactor youtube-dl function ([9788cf7](https://github.com/obviyus/SuperSeriousBot/commit/9788cf79437344fad65b2e16e64600eff2ea3beb))

# [1.18.0](https://github.com/obviyus/SuperSeriousBot/compare/v1.17.0...v1.18.0) (2022-08-05)


### Features

* **tweet:** return Twitter tweet previews ([09f28d4](https://github.com/obviyus/SuperSeriousBot/commit/09f28d47a5a198bb63dc6e707648b152c8a8dec8))

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
