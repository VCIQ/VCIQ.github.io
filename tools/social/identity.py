"""Conservative explicit identity aliases; no title/name similarity merges."""
import re
from .contracts import ContractError, digest


def observation_id(row):
    return digest({key: row[key] for key in ("attemptId", "signalId", "contentHash")})


def checked_aliases(row):
    result = []
    for alias in row["nativeAliases"]:
        if row["platform"] != "bili" or row["contentType"] != "video" or not re.fullmatch(r"bili:bvid:BV[A-Za-z0-9]{10}", alias):
            raise ContractError("unproven_alias_kind")
        result.append(alias)
    return result
