# Spec Delta

## REMOVED Requirements

### Requirement: 起動時の振り分け

**Reason**: CLI には起動画面と画面遷移が無く、毎回同じ生成処理を実行するだけである。

**Migration**: 設定ファイルを用意して `paperphone` を実行する。

### Requirement: オンボーディングのページ送り

**Reason**: CLI にはページ送りの UI が無い。

**Migration**: 使い方は README と `--help` を読む。

### Requirement: 名前の登録

**Reason**: 名前は設定ファイルの値として扱う。

**Migration**: `[booklet].name` に名前を書く。

### Requirement: Google アカウントの登録

**Reason**: 認証は GNOME Online Accounts に任せ、paperphone 自身はアカウントを登録しない。

**Migration**: GNOME の設定でアカウントを追加する。

### Requirement: 登録内容の変更

**Reason**: 変更は設定ファイルと GNOME の設定で行う。

**Migration**: `config.toml` を編集し、必要なら `dav add|remove` を使う。
