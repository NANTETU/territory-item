# Territory Item 仕様書

時計アイテムから C++ 製土地保護プラグイン「endstone-territory」のメニュー (`/tty`) を開く Endstone (Python API) プラグイン。

- 作成日: 2026-10-17
- バージョン: 1.0.0
- 対象 API: Endstone 0.11.x (`api_version = "0.11"`)

---

## 1. 目的

Minecraft 統合版 Endstone サーバーにおいて、プレイヤーがチャットコマンドを覚えなくても
専用アイテムを操作するだけで土地保護メニューにアクセスできるようにする。
あわせて、利便性のための自動配布と、セキュリティ/誤操作対策のためのドロップ禁止を提供する。

土地保護の本体ロジックは `endstone-territory` (C++) 側が担い、本プラグインは
「メニュー起動用のアイテム導線」のみを追加する。

---

## 2. 対象環境

| 項目 | 内容 |
|---|---|
| サーバー | Endstone |
| 動作確認 | Endstone 0.11.14 (Minecraft 1.26.52 / Bedrock) |
| 言語 | Python 3.10+ |
| 前提プラグイン | endstone-territory (`/tty` コマンドを提供) |
| プラグイン名 (prefix) | `ClockMenu` |
| 配布物名 | `endstone_clockmenu` (whl) |

---

## 3. メニュー専用アイテム定義

| 属性 | 値 |
|---|---|
| ベースアイテム | `minecraft:clock` (時計) |
| DisplayName | `§e土地保護メニュー` |
| Lore 1行目 | `§7このアイテムを持って画面を長押し、または右クリックすると、土地保護画面が開きます。` |
| Lore 2行目 | `§c※このアイテムは捨てられません。` |
| 個数 | 1 |

### 3.1 識別条件

「メニュー専用時計」と判定するには、以下の **2 条件を両方** 満たす必要がある。

1. アイテム種別の文字列に `clock` を含む (例: `minecraft:clock`)
2. DisplayName が `§e土地保護メニュー` と完全一致

条件 2 により、名前を変更していない通常のバニラ時計は対象外となり、
通常時計の挙動 (設置・取引など) には一切干渉しない。

---

## 4. 機能仕様

### 4.1 自動配布 (OP 不要)

| 項目 | 内容 |
|---|---|
| トリガー | `PlayerJoinEvent` (サーバー参加時) / `PlayerRespawnEvent` (リスポーン時) |
| 条件 | インベントリ内にメニュー専用時計を所持していない |
| 動作 | メニュー専用時計を 1 個インベントリへ追加する |
| 権限 | OP 不要。`player.inventory.add_item()` はプラグイン権限で実行されるためプレイヤーの OP 有無に依存しない |
| 遅延 | イベント発生 1 秒後 (20 tick) に実行。参加/リスポーン直後のインベントリ未同期対策 |
| チャット表示 | なし (配布時にメッセージは出さない) |

- 既に所持している場合は何もしない (重複配布しない)。
- 配布に失敗した場合 (収納不可) は警告ログのみ出力する。
- インベントリ検査で例外が発生した場合は配布せず、警告ログを出力する。

### 4.2 ドロップ (破棄) 禁止

| 項目 | 内容 |
|---|---|
| トリガー | `PlayerDropItemEvent` |
| 条件 | ドロップしようとしたアイテムがメニュー専用時計 |
| 動作 | イベントをキャンセルし、アイテムのドロップを阻止 |
| メッセージ | `§cこのアイテムは捨てられません！` |

- 通常アイテムのドロップは一切妨げない。

### 4.3 メニュー起動

| 項目 | 内容 |
|---|---|
| トリガー | `PlayerInteractEvent` |
| 操作条件 | `action` が **右クリック系** (`RIGHT_CLICK_AIR` / `RIGHT_CLICK_BLOCK`) のみ。左クリックでは反応しない |
| アイテム条件 | 手持ち (またはイベント対象) アイテムがメニュー専用時計 |
| 動作 | イベントをキャンセルし、プレイヤー本人が `tty` コマンドを実行 |
| 実行 | `player.perform_command("tty")` → endstone-territory のメインメニューを表示 |
| 権限 | OP 不要。`tty` の権限 `territory.command.member` は default True |
| 多重防止 | プレイヤーごとに **1.5 秒のクールダウン** (`OPEN_COOLDOWN`) |

- 名前なしのバニラ時計では何も起きない。
- 左クリックでは開かない (アクション種別で判定)。
- ブロックを叩いた場合、バニラのブロック操作との競合を避けるためイベントをキャンセルする。
- 1 回の操作で `PlayerInteractEvent` が複数回発火しても、クールダウンにより
  フォームが多重送信されない (「× を何度も押さないと閉じられない」症状を防止)。

### 4.4 死亡時ドロップ対策

死亡時のアイテムドロップは `PlayerDropItemEvent` を経由せず、BDS がインベントリから
直接アイテム実体を生成する。そのため以下の **2 段構え** でメニュー専用時計を落とさせない。

| トリガー | 動作 |
|---|---|
| `PlayerDeathEvent` | 死亡時に所持しているメニュー専用時計をインベントリから取り除く (ドロップ前に除去) |
| `ActorSpawnEvent` | メニュー専用時計のアイテム実体が生成されそうになったらキャンセルして消滅させる |
| `PlayerRespawnEvent` | リスポーン時に所持していなければ再配布する |

- `ActorSpawnEvent` はアイテム実体 (`item_stack` を持つアクター) のみを対象とする。
- `ActorSpawnEvent` のキャンセルにより、死亡ドロップの順序に依存せず地面への残置を防ぐ。
- リスポーン時の再配布により、死亡によって所持が失われても必ず 1 個所持した状態に戻る。

---

## 5. イベント処理仕様

| イベント | ハンドラ | 優先度 | ignore_cancelled | 処理 |
|---|---|---|---|---|
| `PlayerJoinEvent` | `on_player_join` | NORMAL (既定) | - | 時計未所持なら 1 秒後に自動配布 |
| `PlayerRespawnEvent` | `on_player_respawn` | NORMAL (既定) | - | 時計未所持なら 1 秒後に再配布 |
| `PlayerDeathEvent` | `on_player_death` | NORMAL (既定) | - | 所持しているメニュー時計を除去 |
| `ActorSpawnEvent` | `on_actor_spawn` | NORMAL (既定) | - | メニュー時計のアイテム実体生成をキャンセル |
| `PlayerDropItemEvent` | `on_player_drop` | NORMAL (既定) | - | 専用時計ならキャンセル + 警告 |
| `PlayerInteractEvent` | `on_player_interact` | `HIGHEST` | `True` | 右クリック + 専用時計ならキャンセル + `/tty` 実行 (1.5 秒クールダウン) |

### 5.1 ignore_cancelled / 優先度 を HIGHEST とする理由

`endstone-territory` は `PlayerInteractEvent` を監視し、保護地内での不正操作をキャンセルする。
保護地内でもメニューを確実に開けるよう、以下とする。

- `priority=EventPriority.HIGHEST` … territory のハンドラより後に実行する
- `ignore_cancelled=True` … territory 側で既にキャンセル済みでも処理を継続する

### 5.2 endstone-territory との干渉整理 (参照: yuhangle/endstone-territory)

| 観点 | 根拠 | 影響 |
|---|---|---|
| `/tty` 権限 | `territory.command.member` が `default True` | `perform_command("tty")` は OP 不要 |
| 空中での長押し | territory 側 `onPlayerjiaohu` は `getBlock()==null` で早期 return | 空中長押しは保護に阻まれない |
| ブロックへの操作 | territory 側が保護地内でキャンセルする可能性 | 本プラグインは HIGHEST + ignore_cancelled で後勝ち |
| 快速作成モード | `minecraft:stick` 専用 | `minecraft:clock` と競合しない |

---

## 6. 処理フロー

### 6.1 参加 / リスポーン時

```
PlayerJoinEvent / PlayerRespawnEvent
  └─ 20 tick 後に give_menu_clock() 実行
       ├─ インベントリに専用時計あり → 何もしない
       └─ なし → 専用時計を add_item (チャット表示なし)
```

### 6.2 ドロップ時

```
PlayerDropItemEvent
  └─ 対象アイテムが専用時計か?
       ├─ No  → 何もしない
       └─ Yes → イベントキャンセル → 「捨てられません」メッセージ
```

### 6.3 死亡時

```
PlayerDeathEvent
  └─ remove_menu_clocks(player)   # ドロップ前に所持時計を除去

ActorSpawnEvent
  └─ item_stack が専用時計か?
       ├─ No  → 何もしない
       └─ Yes → アイテム実体の生成をキャンセル (地面に残さない)

PlayerRespawnEvent
  └─ 20 tick 後に give_menu_clock() で再配布
```

### 6.4 操作時

```
PlayerInteractEvent
  └─ action が右クリック系 かつ 対象アイテムが専用時計か?
       ├─ No  → 何もしない (バニラ挙動を維持)
       └─ Yes → イベントキャンセル → クールダウン判定 → perform_command("tty")
```

---

## 7. エラーハンドリング / フォールバック

- アイテム判定・インベントリ検査は例外を握りつぶし、致命的エラーにしない。
- インベントリ検査失敗時は配布を見送り警告ログ出力 (誤配布の防止)。
- アイテム取得は `event.item` を優先し、取得できない場合は API 差を吸収して
  手持ちスロット (`inventory.item_in_main_hand`) からフォールバック取得する。
- イベントキャンセルは `cancelled = True` と `cancel()` の双方に対応する。

---

## 8. 設定ファイル

### 8.1 `pyproject.toml`

```toml
[project]
name = "endstone-clockmenu"
version = "1.0.0"
description = "時計アイテムから土地保護メニュー(/tty)を開くプラグイン。自動配布+ドロップ禁止付き。"
readme = "README.md"
requires-python = ">=3.9"
authors = [{ name = "ServerAdmin" }]
dependencies = ["endstone"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["clock_menu"]

[project.entry-points."endstone"]
clockmenu = "clock_menu:ClockMenuPlugin"
```

- 配布名は Endstone の規則により `endstone-` または `endstone_` で始める必要がある。
- プラグインのエントリポイントは `[project.entry-points."endstone"]` で宣言する。

### 8.2 プラグインメタ情報 (コード内)

| 属性 | 値 |
|---|---|
| `prefix` | `ClockMenu` |
| `api_version` | `0.11` |

---

## 9. ビルド手順

```
cd clock-menu
python -m build --wheel
```

成果物:

```
dist/endstone_clockmenu-1.0.0-py3-none-any.whl
```

導入手順:

1. サーバーの `plugins/` 直下に上記 whl を配置する。
2. サーバーを起動 (または再起動) する。
3. ログにプラグインがエラーなくロードされることを確認する。

> 補足: 旧ファイル名 `clock_menu-1.0.0-*.whl` が `plugins/` に残っている場合は削除する。

---

## 10. 動作確認項目

| # | 手順 | 期待結果 |
|---|---|---|
| 1 | 初回参加 | 時計「§e土地保護メニュー」が 1 個配布される (チャット表示なし) |
| 2 | 再参加 | 既に所持しているため重複配布されない |
| 3 | 専用時計をドロップ | ドロップされず「§cこのアイテムは捨てられません！」が表示される |
| 4 | 通常の(名前なし)時計をドロップ | 通常どおりドロップできる |
| 5 | 専用時計を空中で長押し/右クリック | `/tty` が実行され土地保護メニューが開く。× 1 回で閉じられる (多重表示しない) |
| 6 | 保護地内で専用時計を使用 | 保護の影響を受けずメニューが開く |
| 7 | 通常の時計で右クリック | 何も起きない |
| 8 | 通常の時計でブロックを叩く | バニラどおりに動作する |
| 9 | 専用時計を左クリック | 何も起きない (メニューは開かない) |
| 10 | 専用時計を所持したまま死亡 | 時計が地面に落ちない。リスポーン後に 1 個所持している |

---

## 11. 既知の制限 / 補足

- `/tty` の仕様変更 (コマンド名・権限) があった場合、`perform_command` の引数調整が必要。
- チェスト等への移動やゴミ箱機能など、ドロップ以外の破棄経路は本仕様の対象外。
- クリエイティブモードでのアイテム破棄などの特殊操作は、別途対策が必要な場合がある。
- `api_version` はサーバーの Endstone バージョンに合わせて更新する。

---

## 12. ファイル構成

```
clock-menu/
├── pyproject.toml          # 設定ファイル (プラグインメタ + ビルド設定)
├── README.md               # 概要
├── SPECIFICATION.md        # 本仕様書
└── clock_menu/
    └── __init__.py         # プラグイン本体 (ClockMenuPlugin)
```

## 13. 変更履歴

| バージョン | 日付 | 内容 |
|---|---|---|
| 1.0.0 | 2026-10-17 | 初版。自動配布・ドロップ禁止・メニュー起動を実装 |
| 1.1.0 | 2026-10-17 | 死亡時ドロップ対策を追加 (`PlayerDeathEvent` / `ActorSpawnEvent` / `PlayerRespawnEvent`)。配布時チャット表示を削除 |
