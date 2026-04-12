import json
import sys
import requests
import fnss

from vemu_uestc.Service_layer.redisAPI import UserMapRedis
from vemu_uestc.vemu_config.settings import VemuConfig

master_ip = VemuConfig.master_ip
master_port = VemuConfig.master_port

save2db = 1
# 切分所用数组
split_list = []

ip_address = []

class FrrRouter(object):

    def __init__(self, counter, **kwargs):
        self.name = f'r{counter}'
        self.image_name = 'router/frr:v20'
        self.type = 'router'
        self.subtype = 'frr'
        self.interfaces = []
        # 这里需要定义config中的内容
        self.config = {'router_id': ""}
        self.config.update(kwargs)

    def ipnetmask2cidrip(self):
        ip = self.interfaces[-1]['ip']
        netmask = self.interfaces[-1]['netmask']
        if ip == '' or netmask == '':
            return ''
        else:
            # 计算二进制字符串中 '1' 的个数
            def count_bit(bin_str):
                return len([i for i in bin_str if i == '1'])

            # 分割字符串格式的子网掩码为四段列表
            mask_splited = netmask.split('.')
            # 转换各段子网掩码为二进制, 计算十进制
            mask_count = [count_bit(bin(int(i))) for i in mask_splited]
            ip_cidr = ip + '/' + str(sum(mask_count))
            return ip_cidr


class Link:

    def __init__(self, counter, src, dst):
        self.name = f'l{counter}'
        self.source = getattr(src, 'name', '')
        self.sourceIP = ''
        self.sourceType = getattr(src, 'type', '')
        self.target = getattr(dst, 'name', '')
        self.targetIP = ''
        self.targetType = getattr(dst, 'type', '')
        self.config = {}
        if getattr(src, 'type') == 'host':
            src.interfaces[0]['name'] = src.name + dst.name
            self.sourceIP = src.ipnetmask2cidrip()
        if getattr(dst, 'type') == 'host':
            dst.interfaces[0]['name'] = dst.name + src.name
            self.targetIP = dst.ipnetmask2cidrip()
        if getattr(src, 'type') == "router":
            src.interfaces[-1]['name'] = src.name + dst.name
            self.sourceIP = src.ipnetmask2cidrip()
        # ????????? 这是谁写的哦
        if getattr(dst, 'type') == 'router':
            dst.interfaces[-1]['name'] = dst.name + src.name
            self.targetIP = dst.ipnetmask2cidrip()
        # if getattr(src, 'type') == "router":
        #     dst.interfaces[-1]['name'] = dst.name + src.name
        #     self.sourceIP = src.ipnetmask2cidrip()


class Interface:

    def __init__(self):
        self.name = ''
        self.ip = ''
        self.netmask = ''

    def get_ip(self, counter, ip_prefix):
        ip_base, prefix = ip_prefix.split('/')
        self.netmask = self.cidr_netmask(int(prefix))
        dec_value = self.ip2decimalism(ip_base) + counter + 1
        self.ip = self.decimalism2ip(dec_value)

    @staticmethod
    def cidr_netmask(prefix):
        bin_arr = ['0' for _ in range(32)]
        for i in range(prefix):
            bin_arr[i] = '1'
        tmpmask = [''.join(bin_arr[i * 8:i * 8 + 8]) for i in range(4)]
        tmpmask = [str(int(tmpstr, 2)) for tmpstr in tmpmask]
        return '.'.join(tmpmask)

    @staticmethod
    def ip2decimalism(ip):
        dec_value = 0
        v_list = ip.split('.')
        v_list.reverse()
        t = 1
        for v in v_list:
            dec_value += int(v) * t
            t = t * (2**8)
        return dec_value

    @staticmethod
    def decimalism2ip(dec_value):
        ip = ''
        t = 2**8
        for _ in range(4):
            v = dec_value % t
            ip = '.' + str(v) + ip
            dec_value = dec_value // t
        ip = ip[1:]
        return ip


class SingleRing(object):
    """
    """

    def __init__(self, node_num, count=0, src=None, dst=None):
        self.node_num = node_num
        self.count = count
        self.src = src
        self.dst = dst
        self._info = {}

    @property
    def topo_info(self):
        if not self._info:
            self._get_info()
        return self._info

    def _get_info(self):
        ring = fnss.ring_topology(self.node_num)
        links, nodes = ring.edges, ring.nodes
        # 根据count的参数进行点、边计数的修正
        links = [[src + self.count, dst + self.count] for src, dst in links]
        nodes = [node + self.count for node in nodes]
        self._info.update({'links': links, 'nodes': nodes})
        # print("get_info in single ring...")
        # print(
        #     f"in single ring {self.count}: {len(nodes)} links: {len(links)} ")


class MainRing(object):
    """
    main ring 需要给ABR加入随机的chord的边来保证拓扑的健壮性
    同时加入的chord的边的对端应该不是ABR节点
    就直接使用fnss的chord_topolopy来实现MainRing就好了
    Main_ring 中的路由器角色
    abr core(area0 非abr)
    """

    def __init__(self, weight, successor_length, count=0):
        self.weight = weight
        self.successor_length = successor_length
        self.node_num = 2**self.weight
        self.count = count
        self._info = {}

    def _get_info(self):
        # 将其转换成无向图， 去除重复的边
        chord = fnss.chord_topology(self.weight,
                                    self.successor_length).to_undirected()
        nodes, links = chord.nodes, chord.edges
        links = [[src + self.count, dst + self.count] for src, dst in links]
        nodes = [node + self.count for node in nodes]
        self._info.update({'links': links, 'nodes': nodes})
        print('*' * 100)
        print(self._info)
        # print("get_info in main ring...")
        # print(
        # f"in main ring {self.count}  nodes: {len(nodes)} links: {len(links)} ")

    @property
    def topo_info(self):
        if not self._info:
            self._get_info()
        return self._info


class CustomRing(object):

    def __init__(self, node_num, count=0, add_links=0):
        self.node_num = node_num
        self.count = count
        self.add_links = add_links
        self._info = {}

    @property
    def topo_info(self):
        if not self._info:
            self._get_info()
        return self._info

    def _get_info(self):
        ring = fnss.ring_topology(self.node_num)
        links, nodes = ring.edges, ring.nodes
        links = [[src + self.count, dst + self.count] for src, dst in links]
        nodes = [node + self.count for node in nodes]
        self._add_edges(links)
        self._info.update({'links': links, 'nodes': nodes})

    def _add_edges(self, links, nums=4):
        # 就只在第一个节点上加边
        quarter = self.node_num // nums
        start = 1 if self.node_num > nums else 2
        for i in range(start, nums - 1):
            links.append([0 + self.count, quarter * i + self.count])


def flatten(a):
    if not isinstance(a, (list, )):
        return [a]
    else:
        b = []
        for item in a:
            b += flatten(item)
    return b


class IgpTopo(object):
    """
    进行拓扑的拼接， 并返回不同节点、链路的列y表
    以及节点和所属的NSSA
    需要记录不同节点的信息
    ABR:   router_id 根据接口循环
    BACKBONE:  router_id  循环遍历就好
    NSSA:  需要 NSSA number, rounter_id , 然后循环遍历
    ASBR:  需要NSSA number, router_id, 和CPE相连的接口信息
    CPE:   只需要router_id
    进行连线之后，需要维护ABR的NSSA接口的信息， ， 但只能知道是和谁连的接口
    这一步是不是还没有要到分配IP地址的地步，应该在后面
    只需要区分节点的类型
    """

    def __init__(self,
                 main_node_weight=4,
                 successor_length=2,
                 nssa_num=5,
                 nssa_node_num=15,
                 default_nssa_abr_num=3,
                 cpe_nodes_per_nssa=7,
                 default_nssa_asbr_num=3,
                 if_divide=False):
        self.main_node_weight = main_node_weight
        self.successor_length = successor_length
        self.default_nssa_abr_num = default_nssa_abr_num
        self.default_nssa_asbr_num = default_nssa_asbr_num
        self.link_count = 0
        self.node_count = 0
        self.nssa_num = nssa_num
        self.nssa_node_num = nssa_node_num
        self.abr_num = 0
        self.cpe_nodes_per_nssa = cpe_nodes_per_nssa
        self._info = {"links": [], 'nodes': []}
        # abr 其实也是要按照nssa来区分开的，这样更方便一些
        self.node_types = {
            'abr': [],
            "asbr": [],
            "nssa": [],
            "backbone": [],
            'cpe': [],
            'nssa_abr': []
        }
        # 记录 ABR与 nssa 的连线信息, 便于接口信息的查找
        # 这里记录area_link的 区域信息，即那些链路属于哪个区域
        self.area_links = {}
        self._external_links = []
        self.if_divide = if_divide

    def _extend(self, info):
        self._info['nodes'].extend(info['nodes'])
        self._info['links'].extend(info['links'])

    def _create_topo(self):
        # 在这里添加节点类型
        self._check_topo_para()
        # 主环连接方式(全连和部分连接)
        # main_ring = MainRing(self.main_node_weight, self.successor_length)
        main_ring = CustomRing(2**self.main_node_weight)
        self.node_count += main_ring.node_num
        main_ring_info = main_ring.topo_info
        print('*' * 100)
        print(main_ring_info)
        # print(len(main_ring_info['links']))
        # 进行排序，方便后续节点选择
        main_ring_info['nodes'].sort()
        # print(main_ring_info)
        # print("main ring has links: ", len(main_ring_info["links"]))
        self._extend(main_ring_info)
        # 存储area0的链路信息
        area_links = self.area_links.setdefault('area0', [])
        area_links.extend(main_ring_info['links'])
        # 通过计算ABR的数量并选定索引需要abr的数量
        # main 中除了ABR 就是 backbone, 选中前 2 * nssa 数量的节点为ABR
        # 需要把ABR更新到NSSA—列表中
        self.node_types['backbone'] += main_ring_info['nodes'][self.abr_num:]
        self.node_types['abr'] += main_ring_info['nodes'][:self.abr_num]

        self._create_nssa_nodes()
        

        if not self.if_divide:
            for key in self.node_types:
                if key != 'backbone' and key != 'nssa_abr':
                    self.node_types['backbone'] += self.node_types[key]
                    self.node_types[key] = []
        self.node_types['backbone'] = flatten(self.node_types['backbone'])
        self.node_types['backbone'].sort()
        # print(self.node_types)

    def _add_links(self, updated):
        # print("updated_links: ", updated)
        self._info['links'] += updated
        self._external_links += updated

    def _create_nssa_nodes(self):
        for i in range(self.nssa_num):
            # print(f'init nssa area {i+1}')
            single_ring = SingleRing(self.nssa_node_num, count=self.node_count)
            self.node_count += self.nssa_node_num
            topo_info = single_ring.topo_info
            # print(topo_info)
            abr_index = self._info['nodes'].index(i *
                                                  self.default_nssa_abr_num +
                                                  self._info['nodes'][0])
            updated = []
            abrs = []
            # print(self.nssa_node_num,self.default_nssa_asbr_num,self.default_nssa_abr_num)
            nssa_count = int((self.nssa_node_num - self.default_nssa_asbr_num)/2)-int(self.default_nssa_abr_num/2)
            # print("nssa_count:",nssa_count)
            # 增加 abr 和 nssa 节点间的连线
            for count in range(self.default_nssa_abr_num):
                abr, nssa = self._info['nodes'][
                    count + abr_index], topo_info['nodes'][nssa_count+count]
                abrs.append(abr)
                # print("aaaa:",abr,nssa)
                updated.append([abr, nssa])
            self._extend(topo_info)
            self._add_links(updated)
            self.node_types['nssa'].append(topo_info['nodes'])
            self.node_types['nssa_abr'].append(abrs)
            # 记录该nssa area的链路信息
            area_links = self.area_links.setdefault(f'area{i+1}', [])
            area_links += topo_info['links']
            area_links += updated
            self._create_cpe_topo(i)

    def _create_cpe_topo(self, i):
        if not self.cpe_nodes_per_nssa:
            return
        # 挑选NSSA区域中的节点为ASBR，并维护和记录相关信息
        if self.nssa_node_num < self.default_nssa_abr_num + self.default_nssa_asbr_num:
            raise ValueError('nssa 中节点数量不够，请重新设置参数')
        # for i in range(self.nssa_num):
            # self._choose_nssa_asbr(i)
            # self._create_cpes(i)
        self._choose_nssa_asbr(i)
        self._create_cpes(i)

    def _choose_nssa_asbr(self, i):
        nssa_nodes = self.node_types['nssa'][i]
        # 选择环中间的节点为ASBR, ASBR节点的起始索引
        index = len(nssa_nodes)
        asbrs = []
        # 选取指定数量的ASBR节点
        for j in range(self.default_nssa_asbr_num, 0, -1):
            asbrs.append(nssa_nodes[index - j])
        self.node_types['asbr'].append(asbrs)

    def _create_cpes(self, i):
        cpes = []
        for i_cpe in range(self.cpe_nodes_per_nssa):
            cpe_id = i_cpe + self.node_count
            cpes.append(cpe_id)
        # 创建cpe 和 asbr 相连的链路
        # 这里的链路就是 cpe 和 asbr的链路，应该加入到area_links里面
        self.node_count += len(cpes)
        self._info['nodes'] += cpes
        self.node_types['cpe'].append(cpes)
        links = []
        for asbr in self.node_types['asbr'][i]:
            for cpe in cpes:
                links.append([asbr, cpe])
        self._add_links(links)
        # 将该链路信息加入到area_links中
        # 这里将cpe 这里是需要+1的
        cpe_area = f'cpe_area{i+1}'
        area_links = self.area_links.setdefault(cpe_area, [])
        # area_links = self.area_links.setdefault(f'area{i+1}', [])
        area_links += links

    def _check_topo_para(self):
        # 计算主环中的节点数量
        main_node_num = 2**self.main_node_weight
        self.abr_num += self.default_nssa_abr_num * self.nssa_num
        if self.abr_num > main_node_num:
            raise ValueError(
                f'需要的ABR节点数量大于 主环中总结点数量 {2} * {self.main_node_weight}'
                f' = {self.abr_num} > {main_node_num}')

    @property
    def topo_info(self):
        if (not self._info['links']) or (not self._info['nodes']):
            self._create_topo()
        return self._info


# 接口上的subnet应该是nssa所有路由器接口的subnet
# 用来生成router_id的
def gen_subnet(ip_format='10.{}.{}.{}', seq=0):
    for i in range(256):
        for j in range(256):
            yield ip_format.format(seq, i, j)


class SubNet:
    """
    接口上的IP地址的配置，是不需要写到网元的链路信息中的吧？？？？
    如果是聚合router_id的话，接口上的地址配置就是不需要进行区分的
    """

    def __init__(self, prefix, subnet_mask=30):
        # 设置成大小一样
        # 这里的ip_prefix也是作为路由聚合的网络段
        # abr 需要同时聚合 area0 和 nssa
        self.ip_prefix = prefix
        self.start_ip, self.net_mask = prefix.split('/')
        # 起始量
        self.ip_num = [int(i) for i in self.start_ip.split('.')]
        self.subnet_mask = subnet_mask

    def get_ip_pair(self):
        a, b = self.ip_num[0], self.ip_num[1]
        for c in range(self.ip_num[2], 255):
            for d in range(self.ip_num[3], 256, 4):
                yield f"{a}.{b}.{c}.{d}/30"
                yield [f"{a}.{b}.{c}.{d+1}/30", f"{a}.{b}.{c}.{d+2}/30"]


class SerializedTopo(object):
    """
    利用router对象给每个router写入信息
        NSSA_frr: router_id, nssa_area_num
        ABR_frr:  router_id,  nssa_area_number, <subnet>
        backbone_frr: router_id,
        asbr_frr:    有多少个实例<实例数目根据cpe的数目进行确定>[]，就有多少个router_id nssa_area_number
        cpe_frr: router_id, 需要和backbone在同一个网段中
    """

    def __init__(self, **kwargs):
        self.topo = IgpTopo(**kwargs)
        self.ori_nodes = self.topo.topo_info['nodes']
        self.ori_links = self.topo.topo_info['links']
        self.nodes = {}
        self.links = {}
        # self.info =
        self.node_types = self.topo.node_types
        self._serialized_info = {}
        self.topo_json = {}
        # 以下配置为网络接口的配置，独立于OPSF协议的配置
        # 就是存了area的links 以及area的相对应的网段，在遍历初始链路的时候方便迭代
        self._area_subnet = {}
        self.networks_map = {}
        self.network_subnet = {}
        for i in range(self.topo.nssa_num + 1):
            area, super_net = f'area{i}', f'170.{i}.0.0/16'
            self._area_subnet[area] = f'10.{i}.0.0/16'
            self.networks_map[area] = SubNet(super_net).get_ip_pair()

        for i in range(self.topo.nssa_num):
            cpe_area, super_net = f'cpe_area{i+1}', f'175.{i+1}.0.0/16'
            cpe_subnet = f'11.{i+1}.0.0/16'
            self._area_subnet[cpe_area] = cpe_subnet
            self.networks_map[cpe_area] = SubNet(super_net).get_ip_pair()

    @property
    def serialized_info(self):
        if not self._serialized_info:
            self.init_topo_info()
            self._get_json_format()
        return self._serialized_info

    def _get_json_format(self):
        routers = {}
        links = {}
        for k, v in self.nodes.items():
            routers[k] = v.__dict__
        for k, v in self.links.items():
            links[k] = v.__dict__
        self._serialized_info.update({'routers': routers, 'links': links})

    def _get_node_obj(self, number):
        try:
            return self.nodes[f'r{number}']
        except:
            raise ValueError(f'no such node r{number}')

    def init_topo_info(self):
        for node in self.ori_nodes:
            node = FrrRouter(node)
            # 这里直接存node会更好一些, 序列化的时候再进行
            # 因为接口里面是不需要填写IP地址的信息的
            self.nodes[node.name] = node
        # 写入links 信息， 写入节点的interface的信息
        self._init_links()
        self._init_node_configs()

    def _init_links(self):
        link_count = 0
        # _area_links = {'area0': [], 'area1': []...}
        for area, links in self.topo.area_links.items():
            # print(area)
            area_sub_net = self.networks_map[area]
            for link in links:
                _ = next(area_sub_net)
                ip_pair = next(area_sub_net)
                ip_address.append(ip_pair)
                # print(ip_pair, link)
                src, dst = self._get_node_obj(link[0]), self._get_node_obj(
                    link[1])
                for i, node in enumerate([src, dst]):
                    ifa = Interface()
                    ip, mask_bit = ip_pair[i].split('/')
                    ifa.ip, ifa.netmask = ip, ifa.cidr_netmask(int(mask_bit))
                    ifa.name = f"{src.name}{dst.name}" if node is src else f"{dst.name}{src.name}"
                    node.interfaces.append(ifa.__dict__)
                    # print(node.name, node.interfaces)
                link = Link(link_count, src, dst)
                link_count += 1
                self.links[link.name] = link
            # print(self.links)

    def _init_node_configs(self):
        """
        利用router对象给每个router写入信息
            NSSA_frr: router_id, nssa_area_num
            ABR_frr:  router_id,  nssa_area_number, subnet
            backbone_frr: router_id,
            cpe_frr: router_id
        # 根据节点类型来设置不同的节点的配置
        self.config = {'router_id': ""}
        self.node_types = {'abr': [], "asbr": [], "nssa": [], "backbone": [], 'cpe': []}
        同时需要为不同的区域配置IP subnet
        """
        self._init_main_ring_config()
        self._init_abr_config()
        self._init_nssa_config()
        self._init_nssa_asbr()

    def _init_main_ring_config(self, subnet_seq=0):
        # 所以是需要abr的总的列表的，因为需要配置主环内的IP地址  router_id
        main_ring_subnet = gen_subnet(seq=subnet_seq)
        for abr in self.topo.node_types['abr']:
            node = self._get_node_obj(abr)
            node.config['router_id'] = next(main_ring_subnet)
            node.config['node_type'] = 'abr'
        # backbone 的设置就完成了
        for backbone in self.topo.node_types['backbone']:
            node = self._get_node_obj(backbone)
            node.config['router_id'] = next(main_ring_subnet)
            node.config['node_type'] = 'backbone'

    def _init_abr_config(self):
        # [[nssa1_abr...], [nssa2_abr...]]
        # 进行ABR的其他属性的配置
        # 先只配置abr
        nssa_abrs = self.topo.node_types['nssa_abr']
        for i, abrs in enumerate(nssa_abrs):
            nssa_seq = i + 1
            # abr 需要同时聚合 area0 和 nssa
            # abr 似乎不需要聚合 area0
            # 所以这里应该是要  area i ???
            nssa_subnet = self._area_subnet[f'area{nssa_seq}']
            # cpe_subnet = self._area_subnet[f'cpe_area{nssa_seq}']
            for abr in abrs:
                node = self._get_node_obj(abr)
                node.config['subnet'] = nssa_subnet
                node.config['nssa_area_number'] = nssa_seq

    def _init_nssa_config(self):
        nssa_nodes = self.topo.node_types['nssa']
        for i, nodes in enumerate(nssa_nodes):
            nssa_seq = i + 1
            nssa_subnet = gen_subnet(seq=nssa_seq)
            for node in nodes:
                node = self._get_node_obj(node)
                node.config['router_id'] = next(nssa_subnet)
                node.config['nssa_area_number'] = nssa_seq
                node.config['node_type'] = 'nssa'
            # 顺便初始化CPE节点的配置信息, CPE只需要router_id 就可以了
            # 这里可能是需要修改的
            self._init_cpe_config(nssa_seq)
            # cpe_sub_net = gen_subnet(ip_format='11.{}.{}.{}', seq=nssa_seq)

            # for cpe in self.topo.node_types['cpe'][i]:
            #     cpe = self._get_node_obj(cpe)
            #     # 只是用来生成router-id的
            #     cpe.config['router_id'] = next(cpe_sub_net)
            #     cpe.config['node_type'] = 'cpe'

    def _init_cpe_config(self, nssa_seq):
        if not self.topo.node_types['cpe']:
            return
        cpe_sub_net = gen_subnet(ip_format='11.{}.{}.{}', seq=nssa_seq)
        # print("608行cpes:",self.topo.node_types['cpe'])
        for cpe in self.topo.node_types['cpe'][nssa_seq - 1]:
            # print("cpe:",cpe)
            cpe = self._get_node_obj(cpe)
            # 只是用来生成router-id的
            cpe.config['router_id'] = next(cpe_sub_net)
            cpe.config['node_type'] = 'cpe'

    def _init_nssa_asbr(self):
        # asbr_frr: nssa_area_number、 router_id, 还有instance的数目
        # nssa_area_number 在上一步已经初始化了关于nssa的基本配置
        asbrs_nodes = self.topo.node_types['asbr']
        for i, nodes in enumerate(asbrs_nodes):
            for node in nodes:
                node = self._get_node_obj(node)
                # 这里需要将instance的数量限制在2
                # 也就是说，对于asbr， 另一端为cpe的链路都在一个域内
                node.config['ospf_instance_num'] = 2
                # node.config['ospf_instance_num'] = self.topo.cpe_nodes_per_nssa + 1
                node.config['node_type'] = 'asbr'
                # 需添加到asbr instance1 需要聚合instance2 中的CPE网段的信息
                cpe_networks = self._area_subnet[f'cpe_area{i+1}']
                node.config['summary_address'] = cpe_networks


if __name__ == "__main__":

    user, topo = 'ma', 'test2'
    # 拓扑json模板
    topo_module = {
        "user": user,
        "topo": topo,
        "networks": {
            "controller": {},
            "routers": {},
            "switches": {},
            "hosts": {},
            "links": {}
        }
    }
    nssa_num = int(sys.argv[2])
    default_nssa_asbr_num = int(sys.argv[5])
    init_para = {
        "main_node_weight": int(sys.argv[1]),
        'successor_length': 1,
        'nssa_num': nssa_num,
        'nssa_node_num': int(sys.argv[3]),
        'default_nssa_abr_num': int(sys.argv[4]),
        'default_nssa_asbr_num': default_nssa_asbr_num,
        'cpe_nodes_per_nssa': int(sys.argv[6])
        # 'if_divide': True
    }
    if sys.argv[7] == "true":
        init_para.update({'if_divide':True})
    else:
        init_para.update({'if_divide':False})
    node_counts = int(2**init_para["main_node_weight"]) + int(init_para["nssa_node_num"])*int(init_para["nssa_num"]) \
            + int(init_para["cpe_nodes_per_nssa"]) * int(init_para["nssa_num"])

    # split_list = [int(init_para['nssa_node_num'])-int(default_nssa_asbr_num) + int(default_nssa_asbr_num)+int(init_para['cpe_nodes_per_nssa'])] \
    #     * init_para['nssa_num']
    split_list = [int(init_para['nssa_node_num'])-int(default_nssa_asbr_num)+ int(default_nssa_asbr_num)+int(init_para['cpe_nodes_per_nssa'])] \
        * init_para['nssa_num']
    area0_worker_num = 4
    for i in range(area0_worker_num):
        split_list.insert(0, int(2**int(init_para['main_node_weight'])/area0_worker_num))
    print("split_list: ",split_list)
    with open('split_list', 'w') as f:
        f.write(str(split_list))

    json_topo = SerializedTopo(**init_para)
    # pprint(json_topo.topo.node_types)

    # from topo_view import draw_topo
    # draw_topo(json_topo.topo.topo_info)

    # 存储topo_ne_area表
    topo_ne_area = {}
    type_list = ["abr", "nssa", "backbone", "asbr", "cpe"]
    #print(json_topo.topo.node_types)
    for type in type_list:
        tmp = {}
        nodes = []
        if type == "abr":
            for node_num in json_topo.node_types[type]:
                nodes.append("r" + str(node_num))
            tmp = {"area0_abr": nodes}
            topo_ne_area.update(tmp)
        elif type == "asbr":
            for node_num in flatten(json_topo.topo.node_types[type]):
                nodes.append("r" + str(node_num))
            tmp = {"asbr": nodes}
            topo_ne_area.update(tmp)
        elif type == "backbone":
            for node_num in json_topo.topo.node_types[type]:
                nodes.append("r" + str(node_num))
            tmp = {"area0_backbone": nodes}
            topo_ne_area.update(tmp)
        elif type == "cpe":
            for node_num in flatten(json_topo.topo.node_types[type]):
                nodes.append("r" + str(node_num))
            tmp = {"cpe": nodes}
            topo_ne_area.update(tmp)
        else:
            for node_num in flatten(json_topo.node_types[type]):
                nodes.append("r" + str(node_num))
            tmp = {"nssa": nodes}
            topo_ne_area.update(tmp)
    print("+++++++++", topo_ne_area)
    routers_json = json_topo.serialized_info['routers']
    interface_info = {}
    for ne in routers_json:
        num = len(routers_json[ne]['interfaces'])
        # print(ne*10, routers_json[ne]['config'])
        ne_type = routers_json[ne]['config']['node_type']
        interface_info.update({ne: [ne_type, str(num)]})
    # print(interface_info)

    # type_list = ["abr", "nssa", "backbone", "asbr", "cpe"]
    # topo_ne_area = {}
    # for type in type_list:
    #     tmp = {}
    #     nodes = []
    #     if type == "abr":
    #         for node_num in json_topo.topo.node_types[type]:
    #             nodes.append("r" + str(node_num))
    #         tmp = {"area0_abr": nodes}
    #         topo_ne_area.update(tmp)
    #     elif type == "asbr":
    #         for node_num in json_topo.topo.node_types[type]:
    #             for node in node_num:
    #                 nodes.append("r" + str(node))
    #         tmp = {"asbr": nodes}
    #         topo_ne_area.update(tmp)
    #     elif type == "backbone":
    #         for node_num in json_topo.topo.node_types[type]:
    #             nodes.append("r" + str(node_num))
    #         tmp = {"area0_backbone": nodes}
    #         topo_ne_area.update(tmp)
    #     elif type == "cpe":
    #         for node_num in json_topo.topo.node_types[type]:
    #             for node in node_num:
    #                 nodes.append("r" + str(node))
    #         tmp = {"cpe": nodes}
    #         topo_ne_area.update(tmp)
    #     else:
    #         for node_nums in json_topo.topo.node_types[type]:
    #             num = 0
    #             if json_topo.topo.node_types["asbr"]:
    #                 asbr_node = json_topo.topo.node_types["asbr"][num]
    #                 nssa_node = [i for i in node_nums if i not in asbr_node]
    #                 for nssa_n in nssa_node:
    #                     nodes.append("r" + str(nssa_n))
    #         tmp = {"nssa": nodes}
    #         topo_ne_area.update(tmp)

    # print(json_topo.topo.topo_info)
    #pprint(json_topo.serialized_info)
    topo_module['networks'].update(json_topo.serialized_info)
    para_str = "_".join([str(value) for value in init_para.values()])
    if save2db == 1:
        user_db_map = UserMapRedis()
        user_db_cli = user_db_map.get_user_db(user)
        print("set table")
        user_db_cli.set_value(f"{topo}_NE_ips", topo, ip_address)
        print(topo_ne_area)
        user_db_cli.set_value(f"{topo}_topo_ne_area", topo, topo_ne_area)
        # 写入interface数量信息表
        user_db_cli.set_value(f"{topo}_ne_interface", topo, interface_info)
        print(para_str)

    with open(f"./topo_json/{user}_{topo}_{para_str}_{node_counts}.json",
              "w") as f:
        json.dump(topo_module, f)
        print(f"{user}_{topo}_{para_str}_{node_counts}.json  created...")
    
    if sys.argv[8] == 'post':
        # 直接发送post请求到master
        print("post json to master")
        # json_data = json.dumps(topo_module)
        url = f'http://{master_ip}:{master_port}/master/topo/'
        resp = requests.post(url=url, json=topo_module)
        if resp.status_code == '0':
            print("post success!")
    else:
        pass