# AGENTS.md

このリポジトリは OpenSpec の spec-driven ワークフローで開発する。コードより先に仕様を書く。

- まだ何を作るか固まっていない → `openspec-explore`
- 作るものが決まっている → `openspec-propose` で `openspec/changes/<change-id>/` を作る
- 実装する → `openspec-apply-change` で `tasks.md` を上から消化する
- 終わった → `openspec-archive-change` で `openspec/changes/archive/` へ移し、`openspec/specs/` を更新する

着手前に `openspec/config.yaml` の context と `openspec/specs/` を読む。仕様は `openspec/specs/` が正で、進行中の変更は `openspec/changes/` にある。

CLI は `openspec`。未インストールなら `curl -fsSL https://openspec.dev/cli/install.sh | sh`（`~/.local/bin` に入る）。

テストは `.venv/bin/pytest`、lint は `.venv/bin/ruff check src tests`、ビルドは `.venv/bin/python -m build`。venv は PyGObject を使うため `python3 -m venv --system-site-packages .venv` で作る。GNOME と Evolution Data Server の無い環境では EDS 統合を実機検証できない。
