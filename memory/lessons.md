# lessons
- Telegramグループに追加されても反応しない時は、設定ファイル（openclaw.json）の `channels.telegram.groups` にそのグループIDが含まれているか確認し、なければ追加して `openclaw gateway restart` する。
- TelegramグループIDを追加する際は、`requireMention: false`, `groupPolicy: "open"` も合わせて設定する。
- ユーザーから「グループで会話したい」と言われたら、まずはそのグループIDを特定し、許可リストになければ即座に追加・再起動の提案をする。
