import functools
from typing import Any, Callable, Literal, Union

from pysnmp.hlapi import CommunityData, ContextData, SnmpEngine, UdpTransportTarget, UsmUserData
from pysnmp.hlapi import asyncio as pysnmp_asyncio

from .types import OID, CommandResult, CommandSet, SnmpCommandFunc


def _pysnmp_command(command: Callable) -> SnmpCommandFunc:
    async def wrapper(*oids: OID, **options: Any) -> CommandResult:
        error_indication, error_status, error_index, var_binds = await command(*oids, **options)
        return {
            'error_indication': error_indication,
            'error_status': error_status,
            'error_index': error_index,
            'var_binds': var_binds,
        }

    return wrapper


class PySNMPAsyncSession:
    def __init__(
        self,
        engine: SnmpEngine,
        auth: Union[CommunityData, UsmUserData],
        transport: UdpTransportTarget,
        context_data: ContextData,
        ignore_nonincreasing_oids: bool = False,
        enforce_constraints: bool = False,
    ) -> None:
        args = (engine, auth, transport, context_data)

        self.commands: CommandSet = {
            'get': _pysnmp_command(functools.partial(pysnmp_asyncio.getCmd, *args, lookupMib=enforce_constraints)),
            'get_next': _pysnmp_command(
                functools.partial(
                    pysnmp_asyncio.nextCmd,
                    *args,
                    ignoreNonIncreasingOid=ignore_nonincreasing_oids,
                    lexicographicMode=False
                )
            ),
        }

    async def _dispatch(self, command: Literal['get', 'get_next'], *oids: OID, **kwargs) -> CommandResult:
        # TODO: raise on error indication.
        # TODO: raise on error status.
        return await self.commands[command](*oids, **kwargs)

    async def get(self, *oids: OID) -> CommandResult:
        return await self._dispatch('get', *oids)

    async def get_next(self, *oids: OID) -> CommandResult:
        return await self._dispatch('get_next', *oids)
