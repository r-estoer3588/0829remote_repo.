"""system.core: 旧来互換の再エクスポート専用モジュール。
新規実装は core/system*.py に集約し、ここでは import のみを提供する。
コメント/ログ粒度は system5/6 のスタイルに準拠すること。
"""

from core.system1 import *  # noqa: F401,F403
from core.system2 import *  # noqa: F401,F403
from core.system3 import *  # noqa: F401,F403
from core.system4 import *  # noqa: F401,F403
from core.system5 import *  # noqa: F401,F403
from core.system6 import *  # noqa: F401,F403
from core.system7 import *  # noqa: F401,F403
