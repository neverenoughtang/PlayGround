from .base_api import KlonetBaseAPI

try:
    from .bmv2_api import KlonetBMv2API
except ImportError:
    print("[Warn] bmv2_api load failed, KlonetBMv2API unavailable.")
    KlonetBMv2API = object # 定义为空对象占位

try:
    from .frr_api import KlonetFRRAPI
except ImportError:
    print("[Warn] frr_api load failed, KlonetFRRAPI unavailable.")
    KlonetFRRAPI = object # 定义为空对象占位

try:
    from .iptables_api import KlonetIptablesAPI
except ImportError:
    print("[Warn] iptables_api load failed, KlonetIptablesAPI unavailable.")
    KlonetIptablesAPI = object

try:
    from .ovs_api import KlonetOVSAPI
except ImportError:
    print("[Warn] ovs_api load failed, KlonetOVSAPI unavailable.")
    KlonetOVSAPI = object

try:
    from .sdn_api import KlonetSDNAPI
except ImportError:
    print("[Warn] sdn_api load failed, KlonetSDNAPI unavailable.")
    KlonetSDNAPI = object

try:
    from .tc_api import KlonetTCAPI
except ImportError:
    print("[Warn] tc_api load failed, KlonetTCAPI unavailable.")
    KlonetTCAPI = object


# 显式导出 (帮助 IDE 识别)
__all__ = ['KlonetAPIALL', 'KlonetBaseAPI', 'KlonetBMv2API', 'KlonetFRRAPI', 'KlonetIptablesAPI', 'KlonetOVSAPI', 'KlonetSDNAPI', 'KlonetTCAPI']