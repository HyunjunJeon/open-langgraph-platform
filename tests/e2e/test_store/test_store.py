import pytest

from tests.e2e._utils import elog, get_e2e_client


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_store_endpoints_via_sdk():
    client = get_e2e_client()

    # Use a user-private namespace implicitly; server will scope to ["users", <identity>]
    # Insert item
    ns = ["notes"]
    key = "e2e-item-1"
    value = {"title": "Hello", "tags": ["e2e", "store"], "score": 42}

    await client.store.put_item(ns, key=key, value=value)
    elog("store.put_item", {"namespace": ns, "key": key, "value": value})

    # Get item (SDK sends dotted namespace on GET)
    got = await client.store.get_item(ns, key=key)
    elog("store.get_item", got)
    assert got["key"] == key
    assert got["value"] == value
    assert got.get("namespace") in (ns, ["users"]) or isinstance(
        got.get("namespace"), list
    )

    # Search by namespace prefix
    search = await client.store.search_items(["notes"], limit=10)
    elog("store.search_items", search)
    assert isinstance(search, dict)
    assert "items" in search
    assert any(item.get("key") == key for item in search["items"])

    # Delete item (SDK sends JSON body)
    await client.store.delete_item(ns, key=key)
    elog("store.delete_item", {"namespace": ns, "key": key})

    # Ensure deleted
    with pytest.raises(Exception):  # noqa: B017 - SDK doesn't expose specific exception type
        await client.store.get_item(ns, key=key)
