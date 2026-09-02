# SuperSeriousBot

- Preserve every registered command, callback action, passive message behavior, scheduled workflow, and existing database row during the Telly migration.
- Build Telegram behavior with Telly's package-root interface. Keep Telegram wire details out of feature modules.
- Run `bun run check` before handoff. Prove user-visible Telegram behavior through Telly's fake first and the Test Server before the draft PR.

## Effect

- Read `node_modules/effect/AGENTS.md` completely before writing Effect code.
- Resolve uncertain Effect behavior from the installed source under `node_modules/effect/src`.
- Keep expected failures in typed error channels. Preserve defects as defects.
