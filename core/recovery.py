"""Recovery system for crashed bots."""
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .controller import BotController
    from .bot_instance import BotInstance


class RecoverySystem:
    def __init__(self, controller: "BotController") -> None:
        self.controller = controller

    def handle_crash(self, bot: "BotInstance") -> None:
        """Log crash, optionally restart after cooldown."""
        bot.record_crash()
        bot.add_log("Crash recorded", "RECOVERY")
        if not bot.should_restart():
            bot.add_log("Restart skipped (cooldown or max attempts)", "RECOVERY")
            return
        cooldown = self.controller.settings.get("restart_cooldown", 60)
        time.sleep(cooldown)
        if bot.should_restart():
            self.controller.restart_bot(bot.bot_id)
            bot.add_log("Restarted after crash", "RECOVERY")

    def handle_stuck(self, bot: "BotInstance") -> None:
        """Restart bot that appears stuck (e.g. no XP for long time)."""
        bot.add_log("Stuck detected, restarting", "RECOVERY")
        self.controller.restart_bot(bot.bot_id)

    def recover_all(self) -> int:
        """Attempt to restart all crashed/error bots that should_restart()."""
        # #region agent log
        try:
            import json
            _f = __import__("builtins").open(r"c:\Users\Owner\.cursor\plans\RSC\.cursor\debug.log", "a", encoding="utf-8")
            _f.write(json.dumps({"timestamp": __import__("time").time() * 1000, "location": "recovery.py:recover_all.entry", "message": "recover_all", "data": {"total_bots": len(self.controller.bots), "bot_ids": list(self.controller.bots.keys())[:20]}, "hypothesisId": "H5"}) + "\n")
            _f.close()
        except Exception:
            pass
        # #endregion
        recovered = 0
        for bot_id, bot in list(self.controller.bots.items()):
            if bot.status.value not in ("crashed", "error"):
                continue
            # #region agent log
            try:
                import json
                _f = __import__("builtins").open(r"c:\Users\Owner\.cursor\plans\RSC\.cursor\debug.log", "a", encoding="utf-8")
                _f.write(json.dumps({"timestamp": __import__("time").time() * 1000, "location": "recovery.py:recover_all.candidate", "message": "recover candidate", "data": {"bot_id": bot_id, "status_value": bot.status.value, "should_restart": bot.should_restart()}, "hypothesisId": "H5"}) + "\n")
                _f.close()
            except Exception:
                pass
            # #endregion
            if bot.should_restart():
                if self.controller.restart_bot(bot_id):
                    recovered += 1
        return recovered
