import sqlite3

from fastapi.testclient import TestClient

import app.api.wechat_directory as wechat_directory_api
from app.main import create_app


def _create_directory_fixture(decrypted_dir):
    decrypted_dir.mkdir()
    micro_msg = decrypted_dir / "de_MicroMsg.db"
    msg_db = decrypted_dir / "de_MSG0.db"
    with sqlite3.connect(micro_msg) as conn:
        conn.execute("CREATE TABLE Contact (UserName TEXT, Remark TEXT, NickName TEXT, Alias TEXT)")
        conn.execute("CREATE TABLE Session (strUsrName TEXT, strNickName TEXT)")
        conn.execute("CREATE TABLE ChatRoom (ChatRoomName TEXT, UserNameList TEXT, DisplayNameList TEXT)")
        conn.executemany(
            "INSERT INTO Contact (UserName, Remark, NickName, Alias) VALUES (?, ?, ?, ?)",
            [
                ("room-1@chatroom", "项目开发群", "", ""),
                ("wxid_alice", "Alice 备注", "Alice 昵称", "alice"),
                ("wxid_bob", "", "Bob 昵称", "bob"),
                ("wxid_contact", "张三", "Zhang San", "zhangsan"),
                ("filehelper", "文件传输助手", "", ""),
            ],
        )
        conn.execute(
            "INSERT INTO ChatRoom (ChatRoomName, UserNameList, DisplayNameList) VALUES (?, ?, ?)",
            ("room-1@chatroom", "wxid_alice^Gwxid_bob", "群Alice^G群Bob"),
        )
        conn.executemany(
            "INSERT INTO Session (strUsrName, strNickName) VALUES (?, ?)",
            [
                ("room-1@chatroom", "项目开发群 Session"),
                ("wxid_contact", "张三 Session"),
            ],
        )
    with sqlite3.connect(msg_db) as conn:
        conn.execute(
            "CREATE TABLE MSG (localId INTEGER, MsgSvrID TEXT, Type INTEGER, SubType INTEGER, CreateTime INTEGER, StrTalker TEXT, IsSender INTEGER, StrContent TEXT, DisplayContent TEXT)"
        )
        conn.executemany(
            "INSERT INTO MSG (localId, MsgSvrID, Type, SubType, CreateTime, StrTalker, IsSender, StrContent, DisplayContent) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (1, "svr-1", 1, 0, 1781882400, "room-1@chatroom", 0, "wxid_alice:\n设置页保存接口 500", ""),
                (2, "svr-2", 1, 0, 1781882460, "room-1@chatroom", 0, "wxid_bob:\n期望保存成功后提示已保存", ""),
                (3, "svr-3", 1, 0, 1781882520, "wxid_contact", 0, "这个需求我收到", ""),
            ],
        )
    return decrypted_dir


def test_wechat_directory_lists_chatrooms_and_contacts(tmp_path, monkeypatch):
    decrypted_dir = _create_directory_fixture(tmp_path / "decrypted_wechat")
    monkeypatch.setattr(wechat_directory_api, "DEFAULT_DECRYPTED_WECHAT_DIR", decrypted_dir)
    client = TestClient(create_app())

    chatrooms = client.get("/wechat-directory/conversations", params={"kind": "chatroom", "query": "项目", "limit": 20})
    contacts = client.get("/wechat-directory/conversations", params={"kind": "contact", "query": "张三", "limit": 20})

    assert chatrooms.status_code == 200
    assert contacts.status_code == 200
    assert chatrooms.json()["conversations"][0]["id"] == "room-1@chatroom"
    assert chatrooms.json()["conversations"][0]["displayName"] == "项目开发群"
    assert contacts.json()["conversations"][0]["id"] == "wxid_contact"
    assert contacts.json()["conversations"][0]["displayName"] == "张三"


def test_wechat_directory_pages_messages_and_resolves_group_sender(tmp_path, monkeypatch):
    decrypted_dir = _create_directory_fixture(tmp_path / "decrypted_wechat")
    monkeypatch.setattr(wechat_directory_api, "DEFAULT_DECRYPTED_WECHAT_DIR", decrypted_dir)
    client = TestClient(create_app())

    page = client.get("/wechat-directory/messages", params={"conversation_id": "room-1@chatroom", "limit": 1})

    assert page.status_code == 200
    payload = page.json()
    assert payload["count"] == 1
    assert payload["hasMore"] is True
    item = payload["items"][0]
    assert item["conversationDisplayName"] == "项目开发群"
    assert item["senderId"] == "wxid_bob"
    assert item["senderDisplayName"] == "群Bob"
    assert item["text"] == "期望保存成功后提示已保存"
    assert item["text"].startswith("wxid_") is False


def test_wechat_directory_query_matches_display_name_not_raw_chatroom_id(tmp_path, monkeypatch):
    decrypted_dir = _create_directory_fixture(tmp_path / "decrypted_wechat")
    monkeypatch.setattr(wechat_directory_api, "DEFAULT_DECRYPTED_WECHAT_DIR", decrypted_dir)
    client = TestClient(create_app())

    by_name = client.get("/wechat-directory/conversations", params={"kind": "chatroom", "query": "项目", "limit": 20})
    by_raw_fragment = client.get("/wechat-directory/conversations", params={"kind": "chatroom", "query": "room-1", "limit": 20})
    by_exact_raw = client.get("/wechat-directory/conversations", params={"kind": "chatroom", "query": "room-1@chatroom", "limit": 20})

    assert by_name.status_code == 200
    assert by_raw_fragment.status_code == 200
    assert by_exact_raw.status_code == 200
    assert len(by_name.json()["conversations"]) == 1
    assert by_raw_fragment.json()["conversations"] == []
    assert by_exact_raw.json()["conversations"][0]["id"] == "room-1@chatroom"


def test_wechat_directory_supports_display_name_fuzzy_typo_without_raw_id_matching(tmp_path, monkeypatch):
    decrypted_dir = tmp_path / "decrypted_wechat"
    decrypted_dir.mkdir()
    with sqlite3.connect(decrypted_dir / "de_MicroMsg.db") as conn:
        conn.execute("CREATE TABLE Contact (UserName TEXT, Remark TEXT, NickName TEXT, Alias TEXT)")
        conn.execute("CREATE TABLE Session (strUsrName TEXT, strNickName TEXT)")
        conn.execute("INSERT INTO Session (strUsrName, strNickName) VALUES (?, ?)", ("ln-room@chatroom", "LN 美太咨询顾问"))
    with sqlite3.connect(decrypted_dir / "de_MSG0.db") as conn:
        conn.execute("CREATE TABLE MSG (localId INTEGER, Type INTEGER, CreateTime INTEGER, StrTalker TEXT, IsSender INTEGER, StrContent TEXT)")
        conn.execute(
            "INSERT INTO MSG (localId, Type, CreateTime, StrTalker, IsSender, StrContent) VALUES (?, ?, ?, ?, ?, ?)",
            (1, 1, 1781882400, "ln-room@chatroom", 0, "测试消息"),
        )
    monkeypatch.setattr(wechat_directory_api, "DEFAULT_DECRYPTED_WECHAT_DIR", decrypted_dir)
    client = TestClient(create_app())

    fuzzy = client.get("/wechat-directory/conversations", params={"kind": "chatroom", "query": "LN美大", "limit": 20})
    raw_fragment = client.get("/wechat-directory/conversations", params={"kind": "chatroom", "query": "ln-room", "limit": 20})

    assert fuzzy.status_code == 200
    assert raw_fragment.status_code == 200
    assert fuzzy.json()["conversations"][0]["id"] == "ln-room@chatroom"
    assert raw_fragment.json()["conversations"] == []


def test_wechat_directory_sorts_by_latest_message_time_desc(tmp_path, monkeypatch):
    decrypted_dir = tmp_path / "decrypted_wechat"
    decrypted_dir.mkdir()
    with sqlite3.connect(decrypted_dir / "de_MicroMsg.db") as conn:
        conn.execute("CREATE TABLE Contact (UserName TEXT, Remark TEXT, NickName TEXT, Alias TEXT)")
        conn.execute("CREATE TABLE Session (strUsrName TEXT, strNickName TEXT)")
        conn.executemany(
            "INSERT INTO Contact (UserName, Remark, NickName, Alias) VALUES (?, ?, ?, ?)",
            [
                ("old-room@chatroom", "LN美大旧群", "", ""),
                ("new-room@chatroom", "LN美大新群", "", ""),
            ],
        )
    with sqlite3.connect(decrypted_dir / "de_MSG0.db") as conn:
        conn.execute("CREATE TABLE MSG (localId INTEGER, Type INTEGER, CreateTime INTEGER, StrTalker TEXT, IsSender INTEGER, StrContent TEXT)")
        conn.executemany(
            "INSERT INTO MSG (localId, Type, CreateTime, StrTalker, IsSender, StrContent) VALUES (?, ?, ?, ?, ?, ?)",
            [
                (1, 1, 1781882400, "old-room@chatroom", 0, "旧群消息"),
                (2, 1, 1781889999, "new-room@chatroom", 0, "新群消息"),
            ],
        )
    monkeypatch.setattr(wechat_directory_api, "DEFAULT_DECRYPTED_WECHAT_DIR", decrypted_dir)
    client = TestClient(create_app())

    response = client.get("/wechat-directory/conversations", params={"kind": "chatroom", "query": "LN美大", "limit": 20})

    assert response.status_code == 200
    conversations = response.json()["conversations"]
    assert [item["id"] for item in conversations] == ["new-room@chatroom", "old-room@chatroom"]


def test_wechat_directory_missing_databases_return_empty_results(tmp_path, monkeypatch):
    decrypted_dir = tmp_path / "decrypted_wechat"
    decrypted_dir.mkdir()
    monkeypatch.setattr(wechat_directory_api, "DEFAULT_DECRYPTED_WECHAT_DIR", decrypted_dir)
    client = TestClient(create_app())

    conversations = client.get("/wechat-directory/conversations", params={"kind": "chatroom", "query": "项目", "limit": 20})
    page = client.get("/wechat-directory/messages", params={"conversation_id": "missing@chatroom", "limit": 20})

    assert conversations.status_code == 200
    assert conversations.json()["conversations"] == []
    assert page.status_code == 200
    assert page.json()["items"] == []
    assert page.json()["hasMore"] is False


def test_wechat_directory_missing_tables_and_columns_are_tolerated(tmp_path, monkeypatch):
    decrypted_dir = tmp_path / "decrypted_wechat"
    decrypted_dir.mkdir()
    with sqlite3.connect(decrypted_dir / "de_MicroMsg.db") as conn:
        conn.execute("CREATE TABLE Contact (NickName TEXT)")
    with sqlite3.connect(decrypted_dir / "de_MSG0.db") as conn:
        conn.execute("CREATE TABLE MSG (StrTalker TEXT)")
    monkeypatch.setattr(wechat_directory_api, "DEFAULT_DECRYPTED_WECHAT_DIR", decrypted_dir)
    client = TestClient(create_app())

    conversations = client.get("/wechat-directory/conversations", params={"kind": "all", "limit": 20})
    page = client.get("/wechat-directory/messages", params={"conversation_id": "room@chatroom", "limit": 20})

    assert conversations.status_code == 200
    assert conversations.json()["conversations"] == []
    assert page.status_code == 200
    assert page.json()["items"] == []


def test_wechat_directory_paginates_same_timestamp_without_duplicates(tmp_path, monkeypatch):
    decrypted_dir = tmp_path / "decrypted_wechat"
    decrypted_dir.mkdir()
    with sqlite3.connect(decrypted_dir / "de_MicroMsg.db") as conn:
        conn.execute("CREATE TABLE Contact (UserName TEXT, Remark TEXT, NickName TEXT, Alias TEXT)")
        conn.execute("CREATE TABLE Session (strUsrName TEXT, strNickName TEXT)")
        conn.execute("INSERT INTO Contact (UserName, Remark, NickName, Alias) VALUES (?, ?, ?, ?)", ("room-page@chatroom", "分页群", "", ""))
    with sqlite3.connect(decrypted_dir / "de_MSG0.db") as conn:
        conn.execute("CREATE TABLE MSG (localId INTEGER, Type INTEGER, CreateTime INTEGER, StrTalker TEXT, IsSender INTEGER, StrContent TEXT)")
        conn.executemany(
            "INSERT INTO MSG (localId, Type, CreateTime, StrTalker, IsSender, StrContent) VALUES (?, ?, ?, ?, ?, ?)",
            [(1, 1, 1781882400, "room-page@chatroom", 0, "第一条"), (2, 1, 1781882400, "room-page@chatroom", 0, "第二条"), (3, 1, 1781882400, "room-page@chatroom", 0, "第三条")],
        )
    monkeypatch.setattr(wechat_directory_api, "DEFAULT_DECRYPTED_WECHAT_DIR", decrypted_dir)
    client = TestClient(create_app())

    page1 = client.get("/wechat-directory/messages", params={"conversation_id": "room-page@chatroom", "limit": 2})
    cursor = page1.json()["nextCursor"]
    page2 = client.get("/wechat-directory/messages", params={"conversation_id": "room-page@chatroom", "before_ts": cursor["beforeTs"], "before_local_id": cursor["beforeLocalId"], "limit": 2})

    assert [item["localId"] for item in page1.json()["items"]] == [3, 2]
    assert [item["localId"] for item in page2.json()["items"]] == [1]
    assert set(item["localId"] for item in page1.json()["items"]).isdisjoint({item["localId"] for item in page2.json()["items"]})


def test_wechat_directory_normalizes_xml_and_emoji_noise(tmp_path, monkeypatch):
    decrypted_dir = tmp_path / "decrypted_wechat"
    decrypted_dir.mkdir()
    with sqlite3.connect(decrypted_dir / "de_MicroMsg.db") as conn:
        conn.execute("CREATE TABLE Contact (UserName TEXT, Remark TEXT, NickName TEXT, Alias TEXT)")
        conn.execute("CREATE TABLE Session (strUsrName TEXT, strNickName TEXT)")
        conn.execute("INSERT INTO Contact (UserName, Remark, NickName, Alias) VALUES (?, ?, ?, ?)", ("room-noise@chatroom", "噪声群", "", ""))
    with sqlite3.connect(decrypted_dir / "de_MSG0.db") as conn:
        conn.execute("CREATE TABLE MSG (localId INTEGER, Type INTEGER, CreateTime INTEGER, StrTalker TEXT, IsSender INTEGER, StrContent TEXT)")
        conn.executemany(
            "INSERT INTO MSG (localId, Type, CreateTime, StrTalker, IsSender, StrContent) VALUES (?, ?, ?, ?, ?, ?)",
            [(1, 49, 1781882400, "room-noise@chatroom", 0, "<msg><title>需求文档链接</title><des>描述</des></msg>"), (2, 47, 1781882460, "room-noise@chatroom", 0, "<msg><emoji fromusername='wxid_a'/></msg>")],
        )
    monkeypatch.setattr(wechat_directory_api, "DEFAULT_DECRYPTED_WECHAT_DIR", decrypted_dir)
    client = TestClient(create_app())

    page = client.get("/wechat-directory/messages", params={"conversation_id": "room-noise@chatroom", "limit": 2})

    assert page.status_code == 200
    items = page.json()["items"]
    assert items[0]["messageType"] == "emoji"
    assert items[0]["text"] == "[emoji]"
    assert items[1]["messageType"] == "link"
    assert items[1]["text"] == "需求文档链接"


def test_wechat_directory_merges_multiple_msg_databases_by_time(tmp_path, monkeypatch):
    decrypted_dir = tmp_path / "decrypted_wechat"
    decrypted_dir.mkdir()
    with sqlite3.connect(decrypted_dir / "de_MicroMsg.db") as conn:
        conn.execute("CREATE TABLE Contact (UserName TEXT, Remark TEXT, NickName TEXT, Alias TEXT)")
        conn.execute("CREATE TABLE Session (strUsrName TEXT, strNickName TEXT)")
        conn.execute("INSERT INTO Contact (UserName, Remark, NickName, Alias) VALUES (?, ?, ?, ?)", ("room-multi@chatroom", "多库群", "", ""))
    for db_name, create_time, text in [("de_MSG0.db", 1781882400, "旧库消息"), ("de_MSG1.db", 1781882600, "新库消息")]:
        with sqlite3.connect(decrypted_dir / db_name) as conn:
            conn.execute("CREATE TABLE MSG (localId INTEGER, Type INTEGER, CreateTime INTEGER, StrTalker TEXT, IsSender INTEGER, StrContent TEXT)")
            conn.execute("INSERT INTO MSG (localId, Type, CreateTime, StrTalker, IsSender, StrContent) VALUES (?, ?, ?, ?, ?, ?)", (1, 1, create_time, "room-multi@chatroom", 0, text))
    monkeypatch.setattr(wechat_directory_api, "DEFAULT_DECRYPTED_WECHAT_DIR", decrypted_dir)
    client = TestClient(create_app())

    page = client.get("/wechat-directory/messages", params={"conversation_id": "room-multi@chatroom", "limit": 2})
    conversations = client.get("/wechat-directory/conversations", params={"kind": "chatroom", "query": "多库", "limit": 20})

    assert [item["text"] for item in page.json()["items"]] == ["新库消息", "旧库消息"]
    assert conversations.json()["conversations"][0]["lastPreview"] == "新库消息"


def test_wechat_directory_message_limit_is_capped(tmp_path, monkeypatch):
    decrypted_dir = tmp_path / "decrypted_wechat"
    decrypted_dir.mkdir()
    with sqlite3.connect(decrypted_dir / "de_MicroMsg.db") as conn:
        conn.execute("CREATE TABLE Contact (UserName TEXT, Remark TEXT, NickName TEXT, Alias TEXT)")
        conn.execute("CREATE TABLE Session (strUsrName TEXT, strNickName TEXT)")
        conn.execute("INSERT INTO Contact (UserName, Remark, NickName, Alias) VALUES (?, ?, ?, ?)", ("room-big@chatroom", "大群", "", ""))
    with sqlite3.connect(decrypted_dir / "de_MSG0.db") as conn:
        conn.execute("CREATE TABLE MSG (localId INTEGER, Type INTEGER, CreateTime INTEGER, StrTalker TEXT, IsSender INTEGER, StrContent TEXT)")
        conn.executemany(
            "INSERT INTO MSG (localId, Type, CreateTime, StrTalker, IsSender, StrContent) VALUES (?, ?, ?, ?, ?, ?)",
            [(index, 1, 1781882400 + index, "room-big@chatroom", 0, f"第 {index} 条消息") for index in range(250)],
        )
    monkeypatch.setattr(wechat_directory_api, "DEFAULT_DECRYPTED_WECHAT_DIR", decrypted_dir)
    client = TestClient(create_app())

    page = client.get("/wechat-directory/messages", params={"conversation_id": "room-big@chatroom", "limit": 10000})

    assert page.status_code == 200
    assert page.json()["limit"] == 200
    assert page.json()["count"] == 200
    assert page.json()["hasMore"] is True
