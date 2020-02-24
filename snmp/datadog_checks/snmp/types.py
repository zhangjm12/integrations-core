
from typing import Any, Protocol, Sequence, TypedDict

from pyasn1.type.base import Asn1Type
from pysnmp.hlapi import ObjectType


class CommandResult(TypedDict):
    error_indication: Asn1Type
    error_status: Asn1Type
    error_index: Asn1Type
    var_binds: Sequence[ObjectType]


class OID:
    pass


class SnmpCommandFunc(Protocol):
    async def __call__(self, *oids: OID, **kwargs: Any) -> CommandResult:
        ...


class CommandSet(TypedDict):
    get: SnmpCommandFunc
    get_next: SnmpCommandFunc
