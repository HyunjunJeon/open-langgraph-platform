from uuid import UUID

# Standard namespace UUID for deriving a deterministic assistant ID from a graph ID.
# IMPORTANT: Do not change after initial deployment unless you plan to migrate data.
ASSISTANT_NAMESPACE_UUID = UUID("6ba7b821-9dad-11d1-80b4-00c04fd430c8")
