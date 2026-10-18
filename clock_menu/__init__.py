# Territory Item - endstone-territory の /tty を時計アイテムから開くプラグイン
# 参考: https://github.com/yuhangle/endstone-territory
#  - territory側は command("tty") を登録し、引数なしで menu_->openMainMenu() を開く
#  - 権限 territory.command.member は default True のため perform_command("tty") はOP不要で全員実行可
#  - territoryのPlayerInteract制御(onPlayerjiaohu)は getBlock()==null(=空中)なら早期returnする
#    ため、時計の空中長押しは保護に邪魔されない。ブロックを叩いた場合は保護側がcancelする
#    可能性があるので、こちらは HIGHEST + ignore_cancelled=True で後勝ちさせる
#  - 快速作成は minecraft:stick 専用のため minecraft:clock と競合しない
import time

from endstone.plugin import Plugin
from endstone.event import (
    ActorSpawnEvent,
    EventPriority,
    event_handler,
    PlayerDeathEvent,
    PlayerDropItemEvent,
    PlayerInteractEvent,
    PlayerJoinEvent,
    PlayerRespawnEvent,
)
from endstone.inventory import ItemStack

# ===== メニュー専用アイテムの定義 =====
ITEM_TYPE = "minecraft:clock"
ITEM_NAME = "§e土地保護メニュー"
ITEM_LORE = [
    "§7このアイテムを持って画面を長押し、または右クリックすると、土地保護画面が開きます。",
    "§c※このアイテムは捨てられません。",
]

# 反応させる操作種別 (右クリック系のみ。左クリックでは開かない)
RIGHT_CLICK_ACTIONS = (
    PlayerInteractEvent.Action.RIGHT_CLICK_AIR,
    PlayerInteractEvent.Action.RIGHT_CLICK_BLOCK,
)

# フォーム多重表示防止のクールダウン (秒)
OPEN_COOLDOWN = 1.5


class ClockMenuPlugin(Plugin):
    prefix = "ClockMenu"
    api_version = "0.11"

    def on_enable(self):
        # イベントを受け取るために自分自身を登録
        self.register_events(self)
        # プレイヤーごとの最終メニュー起動時刻 (多重オープン防止用)
        self._last_open = {}
        self.logger.info("ClockMenu enabled!")

    # ---------- 共通ヘルパー ----------

    def create_menu_clock(self) -> ItemStack:
        """メニュー専用の時計を1個作る"""
        item = ItemStack(ITEM_TYPE, 1)
        # item_meta は読み取り専用(コピーを返す)ため、必ず set_item_meta() で書き戻す
        meta = item.item_meta
        meta.display_name = ITEM_NAME
        meta.lore = ITEM_LORE
        item.set_item_meta(meta)
        return item

    def is_menu_clock(self, item) -> bool:
        """そのアイテムがメニュー専用時計かどうか判定"""
        if item is None:
            return False
        try:
            # 1. 種類が時計かチェック (バニラ時計と区別する第一関門)
            item_type_str = str(item.type).lower() if hasattr(item, "type") else ""
            if "clock" not in item_type_str:
                return False

            # 2. DisplayNameが完全一致するかチェック (第二関門)
            meta = item.item_meta
            name = meta.display_name if meta and hasattr(meta, "display_name") else None
            if name is None and hasattr(item, "get_display_name"):
                name = item.get_display_name()
            return name == ITEM_NAME
        except Exception:
            return False

    def has_menu_clock(self, player) -> bool:
        """インベントリ内に専用時計を持っているか"""
        try:
            inv = player.inventory
            contents = inv.contents if hasattr(inv, "contents") else inv.get_contents()
            for stack in contents:
                if self.is_menu_clock(stack):
                    return True
            for getter in ("item_in_main_hand", "get_item_in_main_hand", "get_item_in_hand"):
                if hasattr(inv, getter):
                    attr = getattr(inv, getter)
                    hand = attr() if callable(attr) else attr
                    if self.is_menu_clock(hand):
                        return True
            return False
        except Exception as e:
            self.logger.warning(f"inventory check failed: {e}")
            return False

    def remove_menu_clocks(self, player):
        """インベントリ内のメニュー専用時計をすべて取り除く"""
        try:
            inv = player.inventory
            size = inv.size if hasattr(inv, "size") else 36
            for index in range(size):
                if self.is_menu_clock(inv.get_item(index)):
                    inv.set_item(index, None)
        except Exception as e:
            self.logger.warning(f"remove failed for {player.name}: {e}")

    def give_menu_clock(self, player):
        """専用時計を持っていなければ配布する (成功・失敗のチャット表示はしない)"""
        try:
            if self.has_menu_clock(player):
                return
            leftover = player.inventory.add_item(self.create_menu_clock())
            # add_item は収納できなかった分を返すので、空dictなら成功
            if leftover:
                self.logger.warning(f"clock could not be added for {player.name}: {leftover}")
        except Exception as e:
            self.logger.warning(f"give failed for {player.name}: {e}")

    def _cancel(self, event):
        """API差吸収: cancelled=True / cancel() 両対応"""
        try:
            event.cancelled = True
        except Exception:
            pass
        try:
            if hasattr(event, "cancel"):
                event.cancel()
        except Exception:
            pass

    # ---------- 自動配布 (OP不要) ----------
    @event_handler
    def on_player_join(self, event: PlayerJoinEvent):
        """参加時に専用時計を持っていなければ自動配布"""
        player = event.player
        # Join直後はインベントリ未同期の場合があるので1秒遅延させる
        self.server.scheduler.run_task(self, lambda: self.give_menu_clock(player), delay=20)

    @event_handler
    def on_player_respawn(self, event: PlayerRespawnEvent):
        """リスポーン時に専用時計を再配布 (死亡で失った分の補填)"""
        player = event.player
        self.server.scheduler.run_task(self, lambda: self.give_menu_clock(player), delay=20)

    # ---------- 死亡時のドロップ対策 ----------
    @event_handler
    def on_player_death(self, event: PlayerDeathEvent):
        """死亡時に所持しているメニュー時計をあらかじめ取り除く"""
        self.remove_menu_clocks(event.player)

    @event_handler
    def on_actor_spawn(self, event: ActorSpawnEvent):
        """メニュー時計が地面のアイテム実体として生成されるのを防ぐ(死亡ドロップ含む)"""
        actor = event.actor
        # アイテム実体のみが item_stack を持つ。それ以外は None で素通り
        try:
            stack = getattr(actor, "item_stack", None)
        except Exception:
            return
        if self.is_menu_clock(stack):
            self._cancel(event)

    # ---------- ドロップ禁止 ----------
    @event_handler
    def on_player_drop(self, event: PlayerDropItemEvent):
        """専用時計を捨てようとしたらキャンセル"""
        dropped = getattr(event, "item", None)
        if self.is_menu_clock(dropped):
            self._cancel(event)
            event.player.send_message("§cこのアイテムは捨てられません！")

    # ---------- 右クリック/長押しで /tty を開く ----------
    # territory保護より後に走らせるため HIGHEST、保護にcancelされていても開くため ignore_cancelled=True
    @event_handler(priority=EventPriority.HIGHEST, ignore_cancelled=True)
    def on_player_interact(self, event: PlayerInteractEvent):
        """専用時計を持って右クリック/長押ししたら /tty を実行"""
        player = event.player

        # 左クリック(LEFT_CLICK_*)では開かない。右クリック系のみ反応する
        if event.action not in RIGHT_CLICK_ACTIONS:
            return

        item = getattr(event, "item", None)
        if item is None and hasattr(event, "get_item"):
            try:
                item = event.get_item()
            except Exception:
                item = None
        if item is None:
            try:
                inv = player.inventory
                hand_attr = getattr(inv, "item_in_main_hand", None)
                item = hand_attr() if callable(hand_attr) else hand_attr
            except Exception:
                item = None

        # バニラ時計(名前なし)はここで弾かれる
        if not self.is_menu_clock(item):
            return

        # バニラ挙動と競合させないためキャンセル
        self._cancel(event)

        # 1クリックでイベントが複数回発火してもフォームを1つだけ開くようクールダウン
        key = player.unique_id
        now = time.monotonic()
        if now - self._last_open.get(key, 0.0) < OPEN_COOLDOWN:
            return
        self._last_open[key] = now

        # 土地保護プラグインのコマンドを本人実行させる
        player.perform_command("tty")
