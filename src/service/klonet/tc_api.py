from .base_api import KlonetBaseAPI
from typing import Optional # 确保导入 Optional


class KlonetTCAPI(KlonetBaseAPI):
    """
    在 Klonet 内与 Linux TC 交互的接口类
    """

    def tc_set_netem(
        self,
        host_name: str,
        link: str,
        bw_kbps: Optional[int] = None,
        delay_ms: Optional[int] = None,
        jitter_ms: Optional[int] = None,
        correlation: Optional[int] = None,
        delay_distribution: Optional[str] = None, 
        loss: Optional[int] = None,
        duplicate: Optional[int] = None, 
        reorder: Optional[int] = None, 
        corrupt: Optional[int] = None, 
        queue_size_bytes:Optional[int] = None,
    ) -> str:
        """
        在主机的指定接口上设置流量控制 (tc) 参数

        Args:
            host_name: 主机名称
            link: 网络链路名称
            bw_kbps: 带宽限制，单位 kbps (千比特每秒)
            delay_ms: 延迟时间，单位ms
            jitter_ms: 抖动时间，单位ms
            correlation: 延迟或丢包的相关性，百分比 (例如 25 代表 25%)
            delay_distribution: 延迟分布模式 (例如 "uniform", "normal", "pareto", "paretonormal")
            loss: 丢包率，百分比 (例如 10 代表 10%)
            duplicate: 重复包率，百分比 (例如 5 代表 5%)
            reorder: 乱序包率，百分比 (例如 5 代表 5%)
            corrupt: 损坏包率，百分比 (例如 2 代表 2%)
            queue_size_bytes: 队列大小，单位字节

        Returns:
            output: 命令输出
        """

        config = {
            "linkchoice": "static",
            "link": link,
            "ne": host_name
        }

        if bw_kbps is not None:
            config["bw_kbps"] = str(bw_kbps)

        if delay_ms is not None:
            config["delay_us"] = str(delay_ms * 1000)

        if jitter_ms is not None:
            config["jitter_us"] = str(jitter_ms * 1000)

        if correlation is not None:
            config["correlation"] = str(f"{correlation}%")

        if delay_distribution is not None:
            config["delay_distribution"] = delay_distribution

        if loss is not None:
            config["loss"] = str(loss)

        if duplicate is not None:
            config["duplicate"] = str(duplicate)

        if reorder is not None:
            config["reorder"] = str(reorder)

        if corrupt is not None:
            config["corrupt"] = str(corrupt)

        if queue_size_bytes is not None:
            config["queue_size_bytes"] = str(queue_size_bytes)

        return self.lab.configure_link(config=config)

    def tc_clear_netem(self, link_name: str) -> str:
        """
        清除主机的流量控制配置

        Args:
            link_name: 主机名称

        Returns:
            output: 命令输出
        """
        
        return self.lab.reset_link(link_name)

    def tc_show_intf(self, host_name: str) -> str:
        """
        显示主机指定接口的流量控制配置

        Args:
            host_name: 主机名称

        Returns:
            output: tc qdisc show 输出
        """
        intf_name = self._get_host_interface_name(host_name=host_name)
        if not intf_name:
            return f"[ERROR] 无法获取主机 {host_name} 的唯一接口名称。"
        command = f"tc qdisc show dev {intf_name}"
        return self._run_cmd(host_name, command)

    def tc_show_statistics(self, host_name: str) -> str:
        """
        显示主机指定接口的流量控制统计信息

        Args:
            host_name: 主机名称

        Returns:
            output: tc -s qdisc show 输出
        """
        intf_name = self._get_host_interface_name(host_name=host_name)
        if not intf_name:
            return f"[ERROR] 无法获取主机 {host_name} 的唯一接口名称。"
        command = f"tc -s qdisc show dev {intf_name}"
        return self._run_cmd(host_name, command)


if __name__ == "__main__":
    print("======= 测试环节 =======")
    lab_name = "static_routing"
    Klonet_api = KlonetTCAPI(lab_name)

    print("启动TC之前, 可达性测试:")
    print(Klonet_api.get_reachability())

    print("正在启动 TC ...")
    Klonet_api.tc_set_netem(
        host_name="h1",
        link="l6",
        loss=50,
        delay_ms=1000,
        jitter_ms=1000
    )

    print("启动TC之后, 流量控制:")
    print(Klonet_api.tc_show_intf(host_name="h1"))
    print("启动TC之后, 流量统计:")
    print(Klonet_api.tc_show_statistics(host_name="h1"))

    print("可达性测试:")
    print(Klonet_api.get_reachability())

    Klonet_api.tc_clear_netem(link_name="l6")
    print("清除TC之后, 流量控制:")
    print(Klonet_api.tc_show_intf(host_name="h1"))
    print("清除TC之后, 流量统计:")
    print(Klonet_api.tc_show_statistics(host_name="h1"))