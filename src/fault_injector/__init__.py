# 把核心类和常量暴露出去
from .fault_inject_pool import FaultInjector
from .lab_injector_input import HOST_INJECT_INPUT, LINK_INJECT_INPUT, SERVICE_INJECT_INPUT

__all__ = ["FaultInjector", "HOST_INJECT_INPUT", "LINK_INJECT_INPUT", "SERVICE_INJECT_INPUT"]