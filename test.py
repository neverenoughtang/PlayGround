from qwen_token_counter import get_token_count

text = """
[Ping]

=== Host-to-Host 可达性 ===

[h1 -> h10] : ✅ 连通 | 丢包率: 0% | 时延: 400.103/400.119/400.136/0.011 ms

[h1 -> h11] : ✅ 连通 | 丢包率: 0% | 时延: 400.098/400.119/400.142/0.014 ms

[h1 -> h12] : ✅ 连通 | 丢包率: 0% | 时延: 400.116/400.190/400.445/0.127 ms

[h1 -> h2] : ✅ 连通 | 丢包率: 0% | 时延: 400.080/480.264/800.977/160.356 ms

[h1 -> h3] : ✅ 连通 | 丢包率: 0% | 时延: 400.109/400.293/401.003/0.354 ms

[h1 -> h4] : ✅ 连通 | 丢包率: 0% | 时延: 400.056/400.076/400.116/0.022 ms

[h1 -> h5] : ✅ 连通 | 丢包率: 0% | 时延: 400.113/401.002/404.497/1.747 ms

[h1 -> h6] : ✅ 连通 | 丢包率: 0% | 时延: 400.114/400.123/400.149/0.012 ms

[h1 -> h7] : ✅ 连通 | 丢包率: 0% | 时延: 400.119/400.314/401.066/0.375 ms

[h1 -> h8] : ✅ 连通 | 丢包率: 0% | 时延: 400.096/400.274/400.877/0.301 ms

[h1 -> h9] : ✅ 连通 | 丢包率: 0% | 时延: 400.124/400.321/401.079/0.378 ms

[h1 -> r1] : ✅ 连通 | 丢包率: 0% | 时延: 400.076/400.081/400.091/0.005 ms

[h1 -> r2] : ✅ 连通 | 丢包率: 0% | 时延: 400.090/400.101/400.115/0.008 ms

[h1 -> r3] : ✅ 连通 | 丢包率: 0% | 时延: 400.099/400.109/400.121/0.007 ms

[h10 -> h11] : ✅ 连通 | 丢包率: 0% | 时延: 0.081/0.092/0.097/0.005 ms

[h10 -> h12] : ✅ 连通 | 丢包率: 0% | 时延: 0.094/0.822/3.717/1.447 ms

[h10 -> h2] : ✅ 连通 | 丢包率: 0% | 时延: 0.106/0.719/3.121/1.200 ms

[h10 -> h3] : ✅ 连通 | 丢包率: 0% | 时延: 0.111/0.228/0.673/0.222 ms

[h10 -> h4] : ✅ 连通 | 丢包率: 0% | 时延: 0.094/0.107/0.126/0.010 ms

[h10 -> h5] : ✅ 连通 | 丢包率: 0% | 时延: 0.089/0.103/0.110/0.007 ms

[h10 -> h6] : ✅ 连通 | 丢包率: 0% | 时延: 0.113/0.309/1.080/0.385 ms

[h10 -> h7] : ✅ 连通 | 丢包率: 0% | 时延: 0.104/0.286/0.973/0.343 ms

[h10 -> h8] : ✅ 连通 | 丢包率: 0% | 时延: 0.094/0.102/0.113/0.006 ms

[h10 -> h9] : ✅ 连通 | 丢包率: 0% | 时延: 0.063/0.223/0.849/0.312 ms

[h10 -> r1] : ✅ 连通 | 丢包率: 0% | 时延: 0.087/0.099/0.114/0.010 ms

[h10 -> r2] : ✅ 连通 | 丢包率: 0% | 时延: 0.070/0.084/0.127/0.021 ms

[h10 -> r3] : ✅ 连通 | 丢包率: 0% | 时延: 0.055/0.060/0.068/0.004 ms

[h11 -> h12] : ✅ 连通 | 丢包率: 0% | 时延: 0.063/0.206/0.773/0.283 ms

[h11 -> h2] : ✅ 连通 | 丢包率: 0% | 时延: 0.102/0.418/1.656/0.618 ms

[h11 -> h3] : ✅ 连通 | 丢包率: 0% | 时延: 0.107/0.172/0.415/0.121 ms

[h11 -> h4] : ✅ 连通 | 丢包率: 0% | 时延: 0.084/0.241/0.838/0.298 ms

[h11 -> h5] : ✅ 连通 | 丢包率: 0% | 时延: 0.108/0.118/0.135/0.009 ms

[h11 -> h6] : ✅ 连通 | 丢包率: 0% | 时延: 0.105/0.188/0.481/0.146 ms

[h11 -> h7] : ✅ 连通 | 丢包率: 0% | 时延: 0.097/0.112/0.137/0.015 ms

[h11 -> h8] : ❓ 状态未知 | 丢包率: 未知

[h11 -> h9] : ✅ 连通 | 丢包率: 0% | 时延: 0.091/0.183/0.509/0.163 ms

[h11 -> r1] : ✅ 连通 | 丢包率: 0% | 时延: 0.092/0.097/0.104/0.004 ms

[h11 -> r2] : ✅ 连通 | 丢包率: 0% | 时延: 0.076/0.084/0.091/0.005 ms

[h11 -> r3] : ✅ 连通 | 丢包率: 0% | 时延: 0.048/0.059/0.074/0.008 ms

[h12 -> h2] : ✅ 连通 | 丢包率: 0% | 时延: 0.107/0.209/0.572/0.181 ms

[h12 -> h3] : ❓ 状态未知 | 丢包率: 未知

[h12 -> h4] : ✅ 连通 | 丢包率: 0% | 时延: 0.106/0.114/0.125/0.007 ms

[h12 -> h5] : ✅ 连通 | 丢包率: 0% | 时延: 0.098/0.114/0.126/0.010 ms

[h12 -> h6] : ✅ 连通 | 丢包率: 0% | 时延: 0.106/0.422/1.662/0.619 ms

[h12 -> h7] : ✅ 连通 | 丢包率: 0% | 时延: 0.086/0.110/0.154/0.024 ms

[h12 -> h8] : ✅ 连通 | 丢包率: 0% | 时延: 0.107/0.206/0.587/0.190 ms

[h12 -> h9] : ❓ 状态未知 | 丢包率: 未知

[h12 -> r1] : ✅ 连通 | 丢包率: 0% | 时延: 0.084/0.091/0.101/0.006 ms

[h12 -> r2] : ✅ 连通 | 丢包率: 0% | 时延: 0.073/0.085/0.096/0.008 ms

[h12 -> r3] : ❓ 状态未知 | 丢包率: 未知

[h2 -> h3] : ✅ 连通 | 丢包率: 0% | 时延: 0.057/0.089/0.103/0.016 ms

[h2 -> h4] : ✅ 连通 | 丢包率: 0% | 时延: 0.064/0.174/0.531/0.178 ms

[h2 -> h5] : ✅ 连通 | 丢包率: 0% | 时延: 0.094/0.103/0.110/0.005 ms

[h2 -> h6] : ❓ 状态未知 | 丢包率: 未知

[h2 -> h7] : ❓ 状态未知 | 丢包率: 未知

[h2 -> h8] : ✅ 连通 | 丢包率: 0% | 时延: 0.100/0.117/0.136/0.012 ms

[h2 -> h9] : ✅ 连通 | 丢包率: 0% | 时延: 0.092/0.112/0.150/0.020 ms

[h2 -> r1] : ❓ 状态未知 | 丢包率: 未知

[h2 -> r2] : ❓ 状态未知 | 丢包率: 未知

[h2 -> r3] : ❓ 状态未知 | 丢包率: 未知

[h3 -> h4] : ❓ 状态未知 | 丢包率: 未知

[h3 -> h5] : ✅ 连通 | 丢包率: 0% | 时延: 0.115/0.123/0.138/0.008 ms

[h3 -> h6] : ❓ 状态未知 | 丢包率: 未知

[h3 -> h7] : ❓ 状态未知 | 丢包率: 未知

[h3 -> h8] : ❓ 状态未知 | 丢包率: 未知

[h3 -> h9] : ✅ 连通 | 丢包率: 0% | 时延: 0.102/0.107/0.114/0.004 ms

[h3 -> r1] : ✅ 连通 | 丢包率: 0% | 时延: 0.060/0.067/0.078/0.006 ms

[h3 -> r2] : ✅ 连通 | 丢包率: 0% | 时延: 0.079/0.084/0.091/0.005 ms

[h3 -> r3] : ❓ 状态未知 | 丢包率: 未知

[h4 -> h5] : ❓ 状态未知 | 丢包率: 未知

[h4 -> h6] : ❓ 状态未知 | 丢包率: 未知

[h4 -> h7] : ❓ 状态未知 | 丢包率: 未知

[h4 -> h8] : ❓ 状态未知 | 丢包率: 未知

[h4 -> h9] : ❓ 状态未知 | 丢包率: 未知

[h4 -> r1] : ❓ 状态未知 | 丢包率: 未知

[h4 -> r2] : ❓ 状态未知 | 丢包率: 未知

[h4 -> r3] : ❓ 状态未知 | 丢包率: 未知

[h5 -> h6] : ❓ 状态未知 | 丢包率: 未知

[h5 -> h7] : ❓ 状态未知 | 丢包率: 未知

[h5 -> h8] : ❓ 状态未知 | 丢包率: 未知

[h5 -> h9] : ❓ 状态未知 | 丢包率: 未知

[h5 -> r1] : ❓ 状态未知 | 丢包率: 未知

[h5 -> r2] : ❓ 状态未知 | 丢包率: 未知

[h5 -> r3] : ❓ 状态未知 | 丢包率: 未知

[h6 -> h7] : ❓ 状态未知 | 丢包率: 未知

[h6 -> h8] : ❓ 状态未知 | 丢包率: 未知

[h6 -> h9] : ❓ 状态未知 | 丢包率: 未知

[h6 -> r1] : ❓ 状态未知 | 丢包率: 未知

[h6 -> r2] : ❓ 状态未知 | 丢包率: 未知

[h6 -> r3] : ❓ 状态未知 | 丢包率: 未知

[h7 -> h8] : ❓ 状态未知 | 丢包率: 未知

[h7 -> h9] : ❓ 状态未知 | 丢包率: 未知

[h7 -> r1] : ❓ 状态未知 | 丢包率: 未知

[h7 -> r2] : ❓ 状态未知 | 丢包率: 未知

[h7 -> r3] : ❓ 状态未知 | 丢包率: 未知

[h8 -> h9] : ❓ 状态未知 | 丢包率: 未知

[h8 -> r1] : ❓ 状态未知 | 丢包率: 未知

[h8 -> r2] : ❓ 状态未知 | 丢包率: 未知

[h8 -> r3] : ❓ 状态未知 | 丢包率: 未知

[h9 -> r1] : ❓ 状态未知 | 丢包率: 未知

[h9 -> r2] : ❓ 状态未知 | 丢包率: 未知

[h9 -> r3] : ❓ 状态未知 | 丢包率: 未知

[r1 -> r2] : ❓ 状态未知 | 丢包率: 未知

[r1 -> r3] : ❓ 状态未知 | 丢包率: 未知

[r2 -> r3] : ❓ 状态未知 | 丢包率: 未知



[ARP]

[h1 ARP/Neigh]:

192.168.3.3 dev tos1_1 lladdr b2:30:12:25:09:75 STALE

192.168.3.1 dev tos1_1 lladdr e6:9d:ca:c5:d1:68 STALE

[h10 ARP/Neigh]:

192.168.7.2 dev tos5_1 lladdr 4e:46:43:bf:d8:b6 STALE

192.168.7.1 dev tos5_1 lladdr da:d1:5b:d5:e7:66 STALE

[h11 ARP/Neigh]:

192.168.8.3 dev tos6_1 lladdr e6:8d:34:9a:aa:ab STALE

192.168.8.1 dev tos6_1 lladdr 56:12:c0:78:e9:54 STALE

[h12 ARP/Neigh]:

192.168.8.1 dev tos6_1 lladdr 56:12:c0:78:e9:54 STALE

192.168.8.2 dev tos6_1 lladdr 82:b9:62:ae:e2:c1 STALE

[h2 ARP/Neigh]:

192.168.3.2 dev tos1_1 lladdr 56:4d:79:35:8a:6e STALE

192.168.3.1 dev tos1_1 lladdr e6:9d:ca:c5:d1:68 STALE

[h3 ARP/Neigh]:

192.168.4.1 dev tos2_1 lladdr 0e:ab:63:a3:3a:46 STALE

192.168.4.3 dev tos2_1 lladdr 96:33:d8:f7:05:20 STALE

[h4 ARP/Neigh]:

192.168.4.1 dev tos2_1 lladdr 0e:ab:63:a3:3a:46 REACHABLE

192.168.4.2 dev tos2_1 lladdr ea:b7:77:77:0b:77 STALE

[h5 ARP/Neigh]:

192.168.5.1 dev tos3_1 lladdr 46:f7:43:04:83:51 REACHABLE

192.168.5.3 dev tos3_1 lladdr ea:81:7c:11:76:ee REACHABLE

[h6 ARP/Neigh]:

192.168.5.1 dev tos3_1 lladdr 46:f7:43:04:83:51 REACHABLE

192.168.5.2 dev tos3_1 lladdr ae:e9:4a:d6:48:7d REACHABLE

[h7 ARP/Neigh]:

192.168.6.1 dev tos4_1 lladdr b6:98:5b:88:b1:37 STALE

192.168.6.3 dev tos4_1 lladdr be:a8:86:0b:75:ff REACHABLE

[h8 ARP/Neigh]:

192.168.6.1 dev tos4_1 lladdr b6:98:5b:88:b1:37 REACHABLE

192.168.6.2 dev tos4_1 lladdr ba:f8:46:38:35:1b REACHABLE

[h9 ARP/Neigh]:

192.168.7.3 dev tos5_1 lladdr 52:e5:f3:15:55:52 STALE

192.168.7.1 dev tos5_1 lladdr da:d1:5b:d5:e7:66 REACHABLE

[r1 ARP/Neigh]:

192.168.4.3 dev tos2_1 lladdr 96:33:d8:f7:05:20 REACHABLE

192.168.4.2 dev tos2_1 lladdr ea:b7:77:77:0b:77 STALE

192.168.3.3 dev tos1_1 lladdr b2:30:12:25:09:75 STALE

192.168.0.2 dev tor2_1 lladdr d2:4d:ec:85:fd:6a REACHABLE

192.168.3.2 dev tos1_1 lladdr 56:4d:79:35:8a:6e STALE

192.168.2.1 dev tor3_1 lladdr 6e:63:f7:6b:d3:0a REACHABLE

[r2 ARP/Neigh]:

192.168.1.2 dev tor3_1 lladdr 46:bd:7d:ca:ad:23 REACHABLE

192.168.6.3 dev tos4_1 lladdr be:a8:86:0b:75:ff REACHABLE

192.168.6.2 dev tos4_1 lladdr ba:f8:46:38:35:1b REACHABLE

192.168.5.2 dev tos3_1 lladdr ae:e9:4a:d6:48:7d REACHABLE

192.168.5.3 dev tos3_1 lladdr ea:81:7c:11:76:ee REACHABLE

192.168.0.1 dev tor1_1 lladdr 62:7a:32:3a:c0:44 DELAY

[r3 ARP/Neigh]:

192.168.8.2 dev tos6_1 lladdr 82:b9:62:ae:e2:c1 STALE

192.168.2.2 dev tor1_1 lladdr 56:92:14:84:4c:3e DELAY

192.168.8.3 dev tos6_1 lladdr e6:8d:34:9a:aa:ab STALE

192.168.7.2 dev tos5_1 lladdr 4e:46:43:bf:d8:b6 REACHABLE

192.168.1.1 dev tor2_1 lladdr 22:bb:78:bd:9d:c2 DELAY

192.168.7.3 dev tos5_1 lladdr 52:e5:f3:15:55:52 STALE

[s1 ARP/Neigh]:

[WARN] s1 命令 'ip neigh' 无输出。

[s2 ARP/Neigh]:

[WARN] s2 命令 'ip neigh' 无输出。

[s3 ARP/Neigh]:

[WARN] s3 命令 'ip neigh' 无输出。

[s4 ARP/Neigh]:

[WARN] s4 命令 'ip neigh' 无输出。

[s5 ARP/Neigh]:

[WARN] s5 命令 'ip neigh' 无输出。

[s6 ARP/Neigh]:

[WARN] s6 命令 'ip neigh' 无输出。



[Interface]

[h1 Interfaces]:

lo               UNKNOWN        00:00:00:00:00:00 <LOOPBACK,UP,LOWER_UP> 

tunl0@NONE       DOWN           0.0.0.0 <NOARP> 

tos1_1@if7       UP             56:4d:79:35:8a:6e <BROADCAST,MULTICAST,UP,LOWER_UP> 

eth0@if33012     DOWN           02:42:ac:11:00:45 <BROADCAST,MULTICAST>

[h10 Interfaces]:

lo               UNKNOWN        00:00:00:00:00:00 <LOOPBACK,UP,LOWER_UP> 

tunl0@NONE       DOWN           0.0.0.0 <NOARP> 

tos5_1@if7       UP             52:e5:f3:15:55:52 <BROADCAST,MULTICAST,UP,LOWER_UP> 

eth0@if33044     DOWN           02:42:ac:11:00:73 <BROADCAST,MULTICAST>

[h11 Interfaces]:

lo               UNKNOWN        00:00:00:00:00:00 <LOOPBACK,UP,LOWER_UP> 

tunl0@NONE       DOWN           0.0.0.0 <NOARP> 

tos6_1@if5       UP             82:b9:62:ae:e2:c1 <BROADCAST,MULTICAST,UP,LOWER_UP> 

eth0@if33046     DOWN           02:42:ac:11:00:74 <BROADCAST,MULTICAST>

[h12 Interfaces]:

lo               UNKNOWN        00:00:00:00:00:00 <LOOPBACK,UP,LOWER_UP> 

tunl0@NONE       DOWN           0.0.0.0 <NOARP> 

tos6_1@if6       UP             e6:8d:34:9a:aa:ab <BROADCAST,MULTICAST,UP,LOWER_UP> 

eth0@if33048     DOWN           02:42:ac:11:00:75 <BROADCAST,MULTICAST>

[h2 Interfaces]:

lo               UNKNOWN        00:00:00:00:00:00 <LOOPBACK,UP,LOWER_UP> 

tunl0@NONE       DOWN           0.0.0.0 <NOARP> 

tos1_1@if6       UP             b2:30:12:25:09:75 <BROADCAST,MULTICAST,UP,LOWER_UP> 

eth0@if33028     DOWN           02:42:ac:11:00:54 <BROADCAST,MULTICAST>

[h3 Interfaces]:

lo               UNKNOWN        00:00:00:00:00:00 <LOOPBACK,UP,LOWER_UP> 

tunl0@NONE       DOWN           0.0.0.0 <NOARP> 

tos2_1@if7       UP             ea:b7:77:77:0b:77 <BROADCAST,MULTICAST,UP,LOWER_UP> 

eth0@if33030     DOWN           02:42:ac:11:00:55 <BROADCAST,MULTICAST>

[h4 Interfaces]:

lo               UNKNOWN        00:00:00:00:00:00 <LOOPBACK,UP,LOWER_UP> 

tunl0@NONE       DOWN           0.0.0.0 <NOARP> 

tos2_1@if6       UP             96:33:d8:f7:05:20 <BROADCAST,MULTICAST,UP,LOWER_UP> 

eth0@if33034     DOWN           02:42:ac:11:00:57 <BROADCAST,MULTICAST>

[h5 Interfaces]:

lo               UNKNOWN        00:00:00:00:00:00 <LOOPBACK,UP,LOWER_UP> 

tunl0@NONE       DOWN           0.0.0.0 <NOARP> 

tos3_1@if6       UP             ae:e9:4a:d6:48:7d <BROADCAST,MULTICAST,UP,LOWER_UP> 

eth0@if33032     DOWN           02:42:ac:11:00:56 <BROADCAST,MULTICAST>

[h6 Interfaces]:

lo               UNKNOWN        00:00:00:00:00:00 <LOOPBACK,UP,LOWER_UP> 

tunl0@NONE       DOWN           0.0.0.0 <NOARP> 

tos3_1@if7       UP             ea:81:7c:11:76:ee <BROADCAST,MULTICAST,UP,LOWER_UP> 

eth0@if33036     DOWN           02:42:ac:11:00:58 <BROADCAST,MULTICAST>

[h7 Interfaces]:

lo               UNKNOWN        00:00:00:00:00:00 <LOOPBACK,UP,LOWER_UP> 

tunl0@NONE       DOWN           0.0.0.0 <NOARP> 

tos4_1@if5       UP             ba:f8:46:38:35:1b <BROADCAST,MULTICAST,UP,LOWER_UP> 

eth0@if33038     DOWN           02:42:ac:11:00:59 <BROADCAST,MULTICAST>

[h8 Interfaces]:

lo               UNKNOWN        00:00:00:00:00:00 <LOOPBACK,UP,LOWER_UP> 

tunl0@NONE       DOWN           0.0.0.0 <NOARP> 

tos4_1@if6       UP             be:a8:86:0b:75:ff <BROADCAST,MULTICAST,UP,LOWER_UP> 

eth0@if33040     DOWN           02:42:ac:11:00:5a <BROADCAST,MULTICAST>

[h9 Interfaces]:

lo               UNKNOWN        00:00:00:00:00:00 <LOOPBACK,UP,LOWER_UP> 

tunl0@NONE       DOWN           0.0.0.0 <NOARP> 

tos5_1@if6       UP             4e:46:43:bf:d8:b6 <BROADCAST,MULTICAST,UP,LOWER_UP> 

eth0@if33042     DOWN           02:42:ac:11:00:5b <BROADCAST,MULTICAST>

[r1 Interfaces]:

lo               UNKNOWN        00:00:00:00:00:00 <LOOPBACK,UP,LOWER_UP> 

tunl0@NONE       DOWN           0.0.0.0 <NOARP> 

tor2_1@tor2_1    UP             62:7a:32:3a:c0:44 <BROADCAST,MULTICAST,UP,LOWER_UP> 

tor3_1@tor3_1    UP             56:92:14:84:4c:3e <BROADCAST,MULTICAST,UP,LOWER_UP> 

tos1_1@tos1_1    UP             e6:9d:ca:c5:d1:68 <BROADCAST,MULTICAST,UP,LOWER_UP> 

tos2_1@tos1_1    UP             0e:ab:63:a3:3a:46 <BROADCAST,MULTICAST,UP,LOWER_UP> 

eth0@if33010     DOWN           02:42:ac:11:00:44 <BROADCAST,MULTICAST>

[r2 Interfaces]:

lo               UNKNOWN        00:00:00:00:00:00 <LOOPBACK,UP,LOWER_UP> 

tunl0@NONE       DOWN           0.0.0.0 <NOARP> 

tor1_1@tor1_1    UP             d2:4d:ec:85:fd:6a <BROADCAST,MULTICAST,UP,LOWER_UP> 

tor3_1@tor1_1    UP             22:bb:78:bd:9d:c2 <BROADCAST,MULTICAST,UP,LOWER_UP> 

tos3_1@tos3_1    UP             46:f7:43:04:83:51 <BROADCAST,MULTICAST,UP,LOWER_UP> 

tos4_1@if7       UP             b6:98:5b:88:b1:37 <BROADCAST,MULTICAST,UP,LOWER_UP> 

eth0@if33018     DOWN           02:42:ac:11:00:49 <BROADCAST,MULTICAST>

[r3 Interfaces]:

lo               UNKNOWN        00:00:00:00:00:00 <LOOPBACK,UP,LOWER_UP> 

tunl0@NONE       DOWN           0.0.0.0 <NOARP> 

tor2_1@tor1_1    UP             46:bd:7d:ca:ad:23 <BROADCAST,MULTICAST,UP,LOWER_UP> 

tor1_1@tor1_1    UP             6e:63:f7:6b:d3:0a <BROADCAST,MULTICAST,UP,LOWER_UP> 

tos5_1@tos5_1    UP             da:d1:5b:d5:e7:66 <BROADCAST,MULTICAST,UP,LOWER_UP> 

tos6_1@if7       UP             56:12:c0:78:e9:54 <BROADCAST,MULTICAST,UP,LOWER_UP> 

eth0@if33024     DOWN           02:42:ac:11:00:4c <BROADCAST,MULTICAST>

[s1 Interfaces]:

lo               UNKNOWN        00:00:00:00:00:00 <LOOPBACK,UP,LOWER_UP> 

tunl0@NONE       DOWN           0.0.0.0 <NOARP> 

ovs-system       DOWN           1e:dc:93:68:1b:ce <BROADCAST,MULTICAST> 

init-br0         DOWN           52:cb:d2:9f:e5:41 <BROADCAST,MULTICAST> 

tor1_1@if5       UP             52:11:2e:66:05:18 <BROADCAST,MULTICAST,UP,LOWER_UP> 

toh2_1@if3       UP             de:49:d2:94:6f:65 <BROADCAST,MULTICAST,UP,LOWER_UP> 

toh1_1@if3       UP             5a:81:c3:7a:94:7c <BROADCAST,MULTICAST,UP,LOWER_UP> 

eth0@if33022     DOWN           02:42:ac:11:00:4b <BROADCAST,MULTICAST>

[s2 Interfaces]:

lo               UNKNOWN        00:00:00:00:00:00 <LOOPBACK,UP,LOWER_UP> 

tunl0@NONE       DOWN           0.0.0.0 <NOARP> 

ovs-system       DOWN           12:e5:c8:50:fa:c0 <BROADCAST,MULTICAST> 

init-br0         DOWN           3e:17:98:ac:f2:45 <BROADCAST,MULTICAST> 

tor1_1@if6       UP             7e:32:f9:48:6e:4a <BROADCAST,MULTICAST,UP,LOWER_UP> 

toh4_1@if3       UP             e2:9d:ae:4c:93:6a <BROADCAST,MULTICAST,UP,LOWER_UP> 

toh3_1@if3       UP             ca:3e:57:23:34:d7 <BROADCAST,MULTICAST,UP,LOWER_UP> 

eth0@if33014     DOWN           02:42:ac:11:00:46 <BROADCAST,MULTICAST>

[s3 Interfaces]:

lo               UNKNOWN        00:00:00:00:00:00 <LOOPBACK,UP,LOWER_UP> 

tunl0@NONE       DOWN           0.0.0.0 <NOARP> 

ovs-system       DOWN           5a:c6:f2:36:4a:b3 <BROADCAST,MULTICAST> 

init-br0         DOWN           7e:af:c5:f3:57:4b <BROADCAST,MULTICAST> 

tor2_1@if5       UP             2e:62:2e:89:36:1f <BROADCAST,MULTICAST,UP,LOWER_UP> 

toh5_1@if3       UP             c2:39:52:40:26:26 <BROADCAST,MULTICAST,UP,LOWER_UP> 

toh6_1@if3       UP             0e:33:ff:39:1d:28 <BROADCAST,MULTICAST,UP,LOWER_UP> 

eth0@if33008     DOWN           02:42:ac:11:00:43 <BROADCAST,MULTICAST>

[s4 Interfaces]:

lo               UNKNOWN        00:00:00:00:00:00 <LOOPBACK,UP,LOWER_UP> 

tunl0@NONE       DOWN           0.0.0.0 <NOARP> 

ovs-system       DOWN           82:3e:c8:71:a8:92 <BROADCAST,MULTICAST> 

init-br0         DOWN           12:4c:8e:f6:5c:47 <BROADCAST,MULTICAST> 

toh7_1@if3       UP             16:8a:d5:56:6b:fd <BROADCAST,MULTICAST,UP,LOWER_UP> 

toh8_1@if3       UP             16:c4:5e:f0:0c:47 <BROADCAST,MULTICAST,UP,LOWER_UP> 

tor2_1@if6       UP             ae:63:e8:25:7f:9f <BROADCAST,MULTICAST,UP,LOWER_UP> 

eth0@if33016     DOWN           02:42:ac:11:00:47 <BROADCAST,MULTICAST>

[s5 Interfaces]:

lo               UNKNOWN        00:00:00:00:00:00 <LOOPBACK,UP,LOWER_UP> 

tunl0@NONE       DOWN           0.0.0.0 <NOARP> 

ovs-system       DOWN           8e:15:2c:a6:d0:89 <BROADCAST,MULTICAST> 

init-br0         DOWN           fe:fd:90:ba:e0:4f <BROADCAST,MULTICAST> 

tor3_1@if5       UP             ea:87:77:a5:dc:41 <BROADCAST,MULTICAST,UP,LOWER_UP> 

toh9_1@if3       UP             32:85:25:96:d7:30 <BROADCAST,MULTICAST,UP,LOWER_UP> 

toh10_1@if3      UP             3e:8b:5a:5a:e4:86 <BROADCAST,MULTICAST,UP,LOWER_UP> 

eth0@if33020     DOWN           02:42:ac:11:00:4a <BROADCAST,MULTICAST>

[s6 Interfaces]:

eth0@if33026     DOWN           02:42:ac:11:00:53 <BROADCAST,MULTICAST> 

lo               UNKNOWN        00:00:00:00:00:00 <LOOPBACK,UP,LOWER_UP> 

tunl0@NONE       DOWN           0.0.0.0 <NOARP> 

ovs-system       DOWN           6a:6a:e4:f5:fc:b4 <BROADCAST,MULTICAST> 

init-br0         DOWN           62:3e:b4:92:57:4a <BROADCAST,MULTICAST> 

toh11_1@if3      UP             ea:68:ae:37:dc:83 <BROADCAST,MULTICAST,UP,LOWER_UP> 

toh12_1@if3      UP             92:24:73:16:c2:b8 <BROADCAST,MULTICAST,UP,LOWER_UP> 

tor3_1@if6       UP             be:09:ac:3b:05:d2 <BROADCAST,MULTICAST,UP,LOWER_UP>



[FRR]

暂无相关动态路由(FRR)配置

【全局巡检报告】

1. **大量主机间连通性异常（状态未知）**：

   - 主机 h4、h5、h6、h7、h8、h9 与网络中其他大部分节点（包括彼此及路由器 r1/r2/r3）的 Ping 测试均显示“状态未知”，表明这些主机可能未正确接入网络或存在严重的二层/三层隔离。

   - 主机 h2 无法连通路由器 r1、r2、r3。

   - 主机 h3 无法连通路由器 r3。

   - 主机 h10 无法连通部分节点（如 h11->h8, h12->h9, h12->r3 等显示未知或异常）。



2. **交换机 ARP 表项缺失**：

   - 所有交换机（s1 至 s6）执行 `ip neigh` 命令均无输出，表明交换机未能学习到任何邻居 MAC 地址信息，可能存在 VLAN 配置错误、端口隔离或链路层故障。



3. **ARP 表项状态异常**：

   - 大量主机（h1, h2, h3, h9, h10, h11, h12）的网关及邻居 ARP 表项处于 `STALE` 状态，且部分关键路径（如 h1->r1/r2/r3 虽 Ping 通但 ARP 为 STALE）可能存在解析延迟或缓存失效风险。

   - 路由器 r2 连接 h10 的接口 ARP 状态为 `DELAY`，r3 连接 h1/h10 的接口 ARP 状态为 `DELAY`，表明邻居可达性正在探测中，存在潜在的不稳定性。



4. **物理/逻辑接口 DOWN**：

   - 所有主机（h1-h12）和路由器（r1-r3）的 `eth0` 接口均处于 `DOWN` 状态，这通常是容器化环境下的预期行为（使用 veth pair），但若业务依赖 eth0 则属异常。

   - 交换机 s6 缺少关键的 `tor` 或 `toh` 上行/下行接口配置（仅显示 eth0 DOWN, lo, tunl0, ovs-system, init-br0, toh11, toh12, tor3），相比其他交换机配置不完整，可能存在拓扑缺失。



5. **路由协议未运行**：

   - FRR 无动态路由配置，全网依赖静态路由。结合上述连通性异常，若静态路由配置有误（如 h4-h9 所在网段路由缺失或下一跳不可达），将导致大面积断网。



👑 [Supervisor] 正在进入门控层级: 【物理链路层】 提取假设...

👑 [Supervisor] 本层拆解子任务：['link_latency: [物理链路层] 发生在 ubuntu 主机上，通过 Linux TC netem 注入延迟规则，表现为网络延迟异常偏高但抖动极小，导致业务响应缓慢', 'link_loss: [物理链路层] 发生在 ubuntu 主机上，通过 Linux TC netem 注入丢包规则，表现为网络链路具有一定丢包率（如50%），导致通信不稳定、延迟高或部分数据包丢失']



🚀 [Dispatch] 唤醒 2 个 Worker 并发执行...

🔧 [Worker-0-1] 执行: node_execute | 参数: {'node': 'h1', 'cli_cmd': 'tc -s qdisc show dev tos1_1'}

🔧 [Worker-0-2] 执行: node_execute | 参数: {'node': 'h1', 'cli_cmd': 'tc -s qdisc show dev tos1_1'}

🔧 [Worker-0-1] 执行: node_execute | 参数: {'node': 'r1', 'cli_cmd': 'tc -s qdisc show dev tos1_1'}

🔧 [Worker-0-1] 执行: submit_diagnosis | 参数: {'faults_json_str': '{"link_latency": ["h1"]}'}

🎯 [Worker-0-1] 确认状态: False



🧠 [Gatekeeper] 正在汇总第 0 层的排查报告...



📊 [Gatekeeper 汇总结论]:

[物理链路层 排查结论]:

 - 本层未发现异常。



--------------------------------------------------



🔍 [Inspector] 正在底座线程池中极速并发采集全网底层健康快照...

🧠 [Inspector] 正在调用 Qwen-Small 压缩底层日志...

✅ [Inspector] 全局底检任务着陆！

[Ping]

=== Host-to-Host 可达性 ===

[h1 -> h10] : ✅ 连通 | 丢包率: 0% | 时延: 400.068/400.079/400.100/0.011 ms

...



[FRR]

暂无相关动态路由(FRR)配置

【全局巡检报告】

1. **大量主机间连通性异常（状态未知）**：

   - 涉及 h11->h2, h11->h4, h11->h6, h12->h7, h12->r1/r2/r3, h2->h3/h7/r1/r3, h3->h4/h6/h7/h9/r1/r3, h4->h5/h6/h7/h8/h9/r3, h5->h7/h8/r1/r2, h6->r1/r2/r3, h7->h8/h9/r1/r2/r3, h8->h9/r1/r2/r3, h9->r1/r2/r3 等大量主机对及主机到路由器对显示“状态未知”，表明这些路径存在严重的连通性问题或探测失败。

   - h10 无法 ping 通 r3。



2. **交换机 ARP/邻居表缺失**：

   - 所有交换机（s1, s2, s3, s4, s5, s6）执行 `ip neigh` 命令均无输出，表明交换机层面未能学习到任何二层邻居信息或 ARP 缓存为空，可能导致基于 MAC 的转发异常。



3. **主机接口状态异常**：

   - 所有主机（h1-h12）的 `eth0` 接口均处于 `DOWN` 状态，仅依赖虚拟接口（如 `tos*_1`）进行通信，物理链路或底层虚拟化网络配置可能存在非标准状态。



4. **ARP 邻居表大量 STALE/DELAY 状态**：

   - 多个关键节点（h1, h2, h5, h6, h7, h8, h9, r1, r2, r3）的 ARP 表中存在大量 `STALE` 或 `DELAY` 状态的邻居项，表明地址解析不稳定或最近通信中断，可能引发间歇性丢包或延迟增加。
"""
count = get_token_count(text)
print(f"Token数量: {count}")