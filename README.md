# 🛡️ Argus: Multi-Agent System & Benchmark for Network Fault Diagnosis

## 📖 Project Background

As network architectures evolve toward higher complexity—spanning traditional dynamic routing and Software-Defined Networking (SDN)—troubleshooting has become increasingly challenging. While Large Language Models (LLMs) show immense promise in IT operations, traditional evaluation methods rely on static datasets or manual scenarios. These approaches fail to objectively measure an LLM's true reasoning capabilities in dynamic, multi-step network environments.

**Argus**  bridges this gap. It is an automated, full-lifecycle digital twin sandbox and benchmark platform. It provides a standardized infrastructure encompassing topology building, automated chaos injection, multi-agent diagnosis, and quantitative scoring. Argus is designed to push the boundaries of automated network operations by offering a highly reproducible environment to test, validate, and evolve diagnostic LLM agents.

## ✨ Core Features

* **🌐 High-Fidelity Digital Twin:** Deploys containerized virtual networks natively within Klonet plantform. It abstractly models complex physical mechanisms into dynamically programmable nodes.
* **💉 Standardized Chaos Engine:** Features a highly decoupled fault injection system capable of executing 58 distinct network anomalies across 9 categories.
* **🧠 Multi-Agent Diagnostic Workflow:** A built-in reference diagnostic system driven by state machines, decoupling the troubleshooting process into discrete, manageable roles.
* **📚 Dual-Engine RAG System:** Combines Milvus (vector database) for static theoretical manuals and MySQL (relational database) for dynamic historical troubleshooting experiences.
* **⚖️ Multi-Dimensional Judge:** A built-in evaluation matrix that scores diagnostic performance based on strict objective metrics (time, tokens, accuracy) and subjective LLM-driven process reviews.

---

## 🏗️ System Architecture

Argus is designed with a bottom-up, decoupled architecture consisting of 4 core domains:

### 1. Network Simulation & Instantiation Base

Built on lightweight containerization, this layer translates declarative topology configurations into actual network namespaces and virtual bridges. It handles IP pool allocation, gateway configuration, and base connectivity mapping.

### 2. Fault Injection & Control Engine

This module acts as the "exam question bank." Utilizing a ReAct-based agent and the FastMCP framework, it executes atomic shell commands to inject faults. Before submitting a fault to the testing queue, the engine runs internal probes to guarantee the physical or protocol anomaly has genuinely occurred, ensuring a pristine testing sample.

### 3. Diagnostic Reference System (The Agents)

Argus includes a fully functional, ReAct-driven multi-agent system designed to navigate the sandbox. By utilizing standard OS constraints and avoiding hardcoded scripts, it proves that the benchmark can support complex closed-loop troubleshooting.

### 4. Benchmark & Evaluation Center

Serving as the referee, this module silently tracks execution time, tool invocations, and token consumption. Once a diagnosis is submitted, an LLM Judge evaluates the logic, efficiency, and accuracy of the agent's entire thought trajectory.

---

## 🗺️ Supported Topologies & Fault Space

To prevent agents from simply memorizing standard operating procedures, the platform generates a massive testing matrix by cross-referencing 7 typical network topologies with 58 specific fault models.

**Supported Topologies:**

1. **Static Routing:** Baseline L2/L3 testing environments.
2. **BGP Inter-Domain:** Cross-AS interconnectivity testing.
3. **OSPF Enterprise Campus:** High-availability topologies with redundant links.
4. **RIP Small Internet:** Slow-convergence networks for transient anomaly testing.
5. **SDN Star Topology:** Centralized control plane (Ryu) and data plane (OVS) separation.
6. **P4 Programmable Data Plane:** Software switches (BMv2) with customized packet processing.
7. **AI Inference Network:** Cloud-native Spine-Leaf architecture for QoS/latency testing.

**Fault Injection Categories:**
The injection suite precisely manipulates network state machines across 9 categories (Link, Host, FRR, BGP, OSPF, RIP, P4, SDN, AI). 

| Fault Category | Fault Name | Supported Topologies |
| :--- | :--- | :--- |
| **Link Level** | Link Loss | static routing, etc. |
| | Link Latency | static routing, etc. |
| | Link Jitter | static routing, etc. |
| | Link Bandwidth | static routing, etc. |
| **Host Level** | IP Misconfig | static routing, etc. |
| | Default Route Missing | static routing, etc. |
| | ARP Poisoning | static routing, etc. |
| | Interface Down | static routing, etc. |
| | DNS Error | static routing, etc. |
| | CPU Overload | static routing, etc. |
| | Routing Error | static routing, etc. |
| | Mask Error | static routing, etc. |
| | Host Port Exhaustion | static routing, etc. |
| **FRR Level** | Route Missing | static routing |
| | Static Route Blackhole | static routing |
| | Data Plane Drop | static routing |
| | FRR Service Down | static routing / ospf enterprise |
| | IP Forward Disabled | static routing |
| | Router Interface IP Wrong | static routing |
| **BGP Level** | BGP Neighbor Shutdown | simple bgp |
| | BGP Withdraw Route | simple bgp |
| | BGP Wrong Peer ASN | simple bgp |
| | ACL Blocking BGP Traffic | simple bgp |
| | BGP Local Preference Spike | simple bgp |
| | BGP MED Spike | simple bgp |
| **OSPF Level** | OSPF Passive Interface | ospf enterprise |
| | OSPF Cost Spike | ospf enterprise |
| | OSPF Daemon Crash | ospf enterprise |
| | ACL Blocking OSPF Traffic | ospf enterprise |
| | OSPF Neighbor Misconfiguration | ospf enterprise |
| | OSPF Area Misconfiguration | ospf enterprise |
| | OSPF Auth Misconfig | ospf enterprise |
| **RIP Level** | RIP Passive Interface | rip internet |
| | RIP Route Filter | rip internet |
| | RIP Metric Offset | rip internet |
| | ACL Blocking RIP Traffic | rip internet |
| | RIP Version Mismatch | rip internet |
| | RIP Timer Misconfiguration | rip internet |
| | RIP Network Withdraw | rip internet |
| **P4 Level** | BMv2 Process Crash | p4 star |
| | P4 Table Drop | p4 star |
| | P4 Wrong Forwarding | p4 star |
| | P4 Table Entry Missing | p4 star |
| | P4 Default Action Drop | p4 star |
| **SDN Level** | SDN Controller Crash | sdn openflow |
| | OVS Disconnect | sdn openflow |
| | OVS Global Drop | sdn openflow |
| | Southbound Wrong Controller Address | sdn openflow |
| | Southbound Protocol Mismatch | sdn openflow |
| | Flow Rule Shadowing | sdn openflow |
| | Flow Rule Loop | sdn openflow |
| | OVS Fail Mode Secure | sdn openflow |
| **AI Inference Level** | AI Service Crash | ai inference |
| | Compute CPU Starvation | ai inference |
| | Compute Memory Exhaustion | ai inference |
| | Inference Port Blocked | ai inference |
| | TCP RST Injection | ai inference |
| | Cross-Layer Traffic Blackhole | ai inference |

---

## 🤖 Multi-Agent Diagnostic Workflow

Argus utilizes LangGraph to orchestrate a linear, 5-node collaborative workflow that mimics the mindset of a human network engineering team:

1. **Global Inspection Agent:** Acts as the frontline responder. It translates vague user complaints into specific ping/traceroute probes, clustering micro-network fluctuations into macro-symptoms (e.g., cross-subnet disconnection).
2. **Knowledge Retrieval (Dual RAG) Node:**
- *Static Track:* Chunks theoretical manuals into Milvus. Uses `bge-m3` for dense retrieval, BM25Plus for sparse retrieval, and `bge-reranker-v2-m3` for final reranking and sorting.
- *Dynamic Track:* Queries MySQL for successful historical troubleshooting cases to find logical shortcuts.
1. **Expert Reasoning Agent:** It dynamically invokes atomic tools (e.g., `ping_by_ip`, `tc_set`, `node_execute`) to investigate protocol states and system resources.
2. **Context Filtering Node:** Intercepts raw device outputs and uses a sub-model to extract only the decisive anomalous metrics, preventing the LLM context window from overflowing.
3. **Summary & Reflection Agent:** Validates the final answer against the ground truth. If correct, it strips away redundant trial-and-error steps and persists the clean causal chain into the MySQL experience database for future RAG queries.

---

## 📊 Evaluation & Scoring Metrics

The platform enforces a rigorous 100-point scoring system to evaluate any diagnostic agent connected to it.

#### **Objective Metrics:**
* **2D Accuracy:** Must correctly identify *both* the faulty node and the root cause attribute.
* **Execution Time:** Total end-to-end sandbox time.
* **Token Efficiency:** Total input/output tokens consumed per task.
* **Tool Invocation Rate:** Measures the information gain of the agent's exploratory actions.


#### **Subjective LLM Judge Metrics (100 Points):**
* **Logic (50 pts):** Penalizes blind trial-and-error, repetitive tool calls, and endless loops.
* **Efficiency (20 pts):** Rewards rapid narrowing of the fault domain based on topology scale.
* **Accuracy (30 pts):** Validates the exactness of the final diagnostic payload.


---

## 🚀 Web Interface

Argus includes a lightweight, decoupled Web UI designed for researchers to monitor the full lifecycle of a benchmark test. Connected via RESTful APIs and WebSockets, the UI offers real-time visualization of:

* The dynamically generated network topology.
* Real-time execution logs from the underlying containers.
* The step-by-step reasoning chain and tool calls generated by the multi-agent system.
![[UI.png]]