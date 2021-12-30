#    @Author: Justin C Presley
#    @Author-Email: justincpresley@gmail.com
#    @Project: NDN State Vector Sync Protocol
#    @Source-Code: https://github.com/justincpresley/ndn-python-svs
#    @Pip-Library: https://pypi.org/project/ndn-svs
#    @Documentation: https://ndn-python-svs.readthedocs.io

# Basic Libraries
from typing import Callable, Optional, Tuple
# NDN Imports
from ndn.app import NDNApp
from ndn.encoding import Name, BinaryStr, Component, parse_data
from ndn.types import InterestNack, InterestTimeout, InterestCanceled, ValidationFailure
from ndn.storage import Storage
# Custom Imports
from .logger import SVSyncLogger
from .security import SecurityOptions
from .svs_base import SVSyncBase

# Class Type: an derived API class
# Class Purpose:
#   to allow the user to interact with SVS, fetch and publish.
#   to allow caching other node's data in case one node goes down.
class SVSyncShared(SVSyncBase):
    def __init__(self, app:NDNApp, groupPrefix:Name, nid:Name, updateCallback:Callable, cacheOthers:bool, storage:Optional[Storage]=None, securityOptions:Optional[SecurityOptions]=None) -> None:
        self.cacheOthers = cacheOthers
        preDataPrefix = groupPrefix + [Component.from_str("d")] if self.cacheOthers else groupPrefix + [Component.from_str("d")] + nid
        preSyncPrefix = groupPrefix + [Component.from_str("s")]
        super().__init__(app, preSyncPrefix, preDataPrefix, groupPrefix, nid, updateCallback, storage, securityOptions)
    async def _fetch(self, nid:Name, seqNum:int, retries:int=0) -> Tuple[Optional[bytes], Optional[BinaryStr]]:
        name = self.getDataName(nid, seqNum)
        while retries+1 > 0:
            try:
                SVSyncLogger.info(f'SVSync: fetching data {Name.to_str(name)}')
                _, _, _, pkt = await self.app.express_interest(name, need_raw_packet=True, must_be_fresh=True, can_be_prefix=False, lifetime=6000)
                ex_int_name, meta_info, content, sig_ptrs = parse_data(pkt)
                isValidated = await self.secOptions.validate(ex_int_name, sig_ptrs)
                if not isValidated:
                    return (None, None)
                SVSyncLogger.info(f'SVSync: received data {bytes(content)}')
                if content and self.cacheOthers:
                    self.storage.put_packet(name, pkt)
                return (bytes(content), pkt) if content else (None, pkt)
            except InterestNack as e:
                SVSyncLogger.warning(f'SVSync: nacked with reason={e.reason}')
            except InterestTimeout:
                SVSyncLogger.warning("SVSync: timeout")
            except InterestCanceled:
                SVSyncLogger.warning("SVSync: canceled")
            except ValidationFailure:
                SVSyncLogger.warning("SVSync: data failed to validate")
            except Exception as e:
                SVSyncLogger.warning(f'SVSync: unknown error has occured: {e}')

            retries = retries - 1
            if retries+1 > 0:
                SVSyncLogger.info("SVSync: retrying fetching data")
        return (None, None)
    def getDataName(self, nid:Name, seqNum:int) -> Name:
        return (self.groupPrefix + [Component.from_str("d")] + nid + Name.from_str(str(seqNum)))