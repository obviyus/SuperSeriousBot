# /// script
# requires-python = ">=3.12"
# ///
import argparse
import importlib.util
import json
import os
import sys
from pathlib import Path

path = Path(os.environ["TELEGRAM_E2E_SKILL_DIR"]) / "scripts/user-driver.py"
spec = importlib.util.spec_from_file_location("telegram_search_driver", path)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
config, bot_config = module.load_config()
driver = module.UserDriver(config, bot_config)
try:
    driver.authorize(argparse.Namespace(timeout_ms=30000))
    if sys.argv[1] == "create":
        driver.client.request({"@type": "searchPublicChat", "username": sys.argv[3]})
        chat = driver.client.request({
            "@type": "createNewSupergroupChat",
            "title": "SuperSeriousBot search test",
            "is_forum": False,
            "is_channel": False,
            "description": "Temporary search verification",
            "message_auto_delete_time": 0,
            "for_import": False,
        })
        chat_id = chat["id"]
        print(json.dumps({"chatId": chat_id}), flush=True)
        driver.client.request({"@type": "addChatMember", "chat_id": chat_id,
                               "user_id": int(sys.argv[2]), "forward_limit": 0})
        message = driver.send_text(chat_id, "Alice builds satellites.")
        print(json.dumps({"chatId": chat_id, "messageId": message["id"] >> 20}), flush=True)
    else:
        driver.client.request({"@type": "searchChatsOnServer", "query": "SuperSeriousBot search test", "limit": 100})
        chat = driver.client.request({"@type": "getChat", "chat_id": int(sys.argv[2])})
        bots = driver.client.request({"@type": "getSupergroupMembers", "supergroup_id": chat["type"]["supergroup_id"],
                                      "filter": {"@type": "supergroupMembersFilterBots"}, "offset": 0, "limit": 200})
        for bot in bots["members"]:
            driver.client.request({"@type": "setChatMemberStatus", "chat_id": chat["id"],
                                   "member_id": bot["member_id"], "status": {"@type": "chatMemberStatusLeft"}})
        driver.client.request({"@type": "leaveChat", "chat_id": chat["id"]})
finally:
    driver.client.destroy()
