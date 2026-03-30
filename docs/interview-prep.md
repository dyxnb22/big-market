# Big-Market 大型营销平台项目 —— 面试深度准备手册

---

## 一、项目介绍（开场白）

Big-Market 是一个面向高并发场景的营销抽奖中台系统，采用 **DDD 领域驱动设计**进行架构划分，将策略、活动、奖品、积分、返利等核心业务解耦为独立领域，通过仓储层屏蔽基础设施细节，实现业务逻辑的高内聚与低耦合。系统核心是一套基于 Redis 的 O(1) 常数时间复杂度抽奖算法，配合责任链与决策树双层规则引擎，支持黑名单过滤、权重分段、次数锁等灵活的业务规则编排。在高可用方面，引入 Outbox 模式（Task 表 + 补偿 Job）确保 MQ 消息的最终一致性投递；同时利用 Redis 预扣减库存与异步批量落库机制，将数据库写压力降至最低，满足大促期间万级 TPS 的并发需求。整个系统通过 XxlJob 分布式调度、Redisson 分布式锁、数据库分片路由等手段保障多节点下的安全并发，是一套兼顾性能、可靠性和可扩展性的工业级营销中台实践。

---

## 二、核心技术点深度解析

---

### 2.1 DDD 领域驱动设计——业务与基础设施解耦

#### 2.1.1 为什么用 DDD？解决了什么问题？

传统 MVC 架构下，业务逻辑散落在 Service 层，直接依赖 Mapper/DAO，一旦换数据库或引入缓存，改动范围极大。DDD 通过**分层 + 仓储模式**将核心业务逻辑从"怎么存"中彻底解耦。

#### 2.1.2 项目实际分层结构

```
big-market-domain/          ← 领域层：纯业务逻辑，零基础设施依赖
big-market-infrastructure/  ← 基础设施层：仓储实现、Redis、DAO
big-market-app/             ← 应用层：AOP、事务编排
big-market-trigger/         ← 触发器层：HTTP 接口、Job、MQ 监听
big-market-types/           ← 共享类型：枚举、常量、通用异常
```

#### 2.1.3 七大核心领域划分

| 领域 | 包路径 | 核心职责 |
|------|--------|---------|
| strategy（策略） | `cn.bugstack.domain.strategy` | 抽奖算法选择与执行 |
| activity（活动） | `cn.bugstack.domain.activity` | 活动参与、配额管理 |
| award（奖品） | `cn.bugstack.domain.award` | 奖品发放与履约 |
| credit（积分） | `cn.bugstack.domain.credit` | 积分账户与交易 |
| rebate（返利） | `cn.bugstack.domain.rebate` | 行为返利 |
| task（任务） | `cn.bugstack.domain.task` | Outbox 消息任务 |
| auth（认证） | `cn.bugstack.domain.auth` | 用户鉴权 |

#### 2.1.4 仓储模式如何落地

领域层只定义接口（如 `IStrategyRepository`），基础设施层提供实现（`StrategyRepository`）。领域层完全不感知 Redis、MyBatis 等技术选型。

```
domain/strategy/repository/IStrategyRepository.java   ← 接口（领域层）
infrastructure/adapter/repository/StrategyRepository.java ← 实现（基础设施层）
```

**实际代码中的两层转换：**
- `StrategyAward`（持久化对象 PO）→ `StrategyAwardEntity`（领域实体）
- 仓储实现先查 Redis 缓存，未命中再查 MySQL，再回写缓存

---

### 2.2 Redis O(1) 空间换时间抽奖算法

#### 2.2.1 核心思路

用**预计算 + 查表**代替运行时的概率累加计算。

**传统做法（O(n) 时间）：**
每次抽奖时，将所有奖品的概率累加，随机数落入哪个区间就中哪个奖品，需要遍历所有奖品。

**O(1) 做法：**
提前把概率"展开"成一张查找表，每次抽奖只需一次随机数 + 一次 Redis Hash 查找。

#### 2.2.2 装配阶段（预热/Armory）

核心文件：`O1Algorithm.java`，由 `AbstractStrategyAlgorithm.assembleLotteryStrategy()` 在策略预热时调用。

**Step 1：计算概率范围（rateRange）**

```
假设三个奖品：
  奖品A：概率 0.3
  奖品B：概率 0.5
  奖品C：概率 0.2

最小精度 = 0.1 → rateRange = 10
```

**Step 2：按概率填充 List**

```
strategyAwardSearchRateTables = [
  101, 101, 101,           ← A 占 3 个位置（30%）
  102, 102, 102, 102, 102, ← B 占 5 个位置（50%）
  103, 103                 ← C 占 2 个位置（20%）
]
```

**Step 3：Fisher-Yates 洗牌打乱**

```
Collections.shuffle(strategyAwardSearchRateTables)
→ [102, 101, 103, 102, 101, 102, 103, 101, 102, 102]
```

**Step 4：构建索引 Map，存入 Redis Hash**

```
Redis Key:   strategy:rate_range:1001  → 10
Redis Hash:  strategy:rate_table:1001
  {0:102, 1:101, 2:103, 3:102, 4:101, 5:102, 6:103, 7:101, 8:102, 9:102}
```

#### 2.2.3 执行阶段（Dispatch）

```java
// O1Algorithm.dispatchAlgorithm()
int rateRange = repository.getRateRange(key);          // 获取范围上限
int randomIndex = secureRandom.nextInt(rateRange);     // 生成随机下标
return repository.getStrategyAwardAssemble(key, randomIndex); // Redis Hash O(1) 查询
```

整个抽奖核心路径：**一次随机数生成 + 一次 Redis HGET = O(1) 时间复杂度**。

#### 2.2.4 多线程预装配

策略预热时，系统针对每个权重配置分别构建独立的查找表（`rule_weight` 的每个分段都有独立 key），并且装配过程通过 Spring 容器注入的线程池并发执行，显著缩短大量策略冷启动耗时。

#### 2.2.5 权重分段的额外查找表

对于 `rule_weight` 规则（如"4000分以上只能抽奖品102~105"），系统为每个分段单独构建一张查找表：

```
key: strategy:rate_table:1001_4000:102,103,104,105
key: strategy:rate_table:1001_5000:102,103,104,105,106,107
```

用户触发权重规则时，直接使用对应 key 的查找表，与默认表完全隔离。

---

### 2.3 规则引擎：责任链 + 决策树双层架构

#### 2.3.1 两层规则的定位差异

| 维度 | 责任链（Chain） | 决策树（Tree） |
|------|----------------|---------------|
| 执行时机 | 抽奖**前**过滤 | 抽奖**后**处理 |
| 结果 | 直接决定中哪个奖品 | 对已选中的奖品进行条件处理 |
| 特点 | 线性顺序执行，可提前短路 | 树形分支执行，有状态转移 |
| 举例 | 黑名单 → 权重分段 → 默认 | 库存扣减 → 次数锁 → 兜底奖品 |

#### 2.3.2 责任链实现

核心接口 `ILogicChain` 继承 `ILogicChainArmory`，通过 `appendNext()` 链接下一节点，每个节点返回 `StrategyAwardVO` 或调用 `next().logic()` 向后传递。

**三个链节点：**

**① BlackListLogicChain（黑名单）**

规则值格式：`102:user001,user002,user003`
- 命中黑名单用户 → 直接返回固定奖品 102（通常是安慰奖/积分）
- 未命中 → 调用 `next().logic()` 传递给下一节点

**② RuleWeightLogicChain（权重分段）**

规则值格式：`4000:102,103,104,105 5000:102,103,104,105,106,107`
- 查询用户累计使用次数（`queryActivityAccountTotalUseCount`）
- 匹配最高满足的分段（如用户 4500 分，匹配 4000 分段）
- 命中 → 用对应权重池的查找表抽奖
- 未命中任何分段 → 向后传递

**③ DefaultLogicChain（兜底）**

始终排在链尾，执行标准抽奖（全量奖品池）。

**链的动态组装（DefaultChainFactory）：**

```java
// 从策略配置读取规则模型列表，如 ["rule_blacklist", "rule_weight"]
// 逐个 getBean + appendNext 链接
// 最后强制附加 rule_default 节点
strategyChainGroup.put(strategyId, chain); // 缓存已组装好的链
```

节点 Bean 使用 `@Scope(SCOPE_PROTOTYPE)` 保证每条链是独立实例，互不干扰。

#### 2.3.3 决策树实现

决策树配置存储在数据库（`rule_tree`、`rule_tree_node`、`rule_tree_node_line` 三张表），运行时加载为 `RuleTreeVO`。

**三个树节点：**

**① RuleStockLogicTreeNode（库存控制）**

```java
Boolean status = strategyDispatch.subtractionAwardStock(strategyId, awardId, endDateTime);
// Redis DECR，原子操作
// 成功：入队异步落库，返回 TAKE_OVER（继续向下走树）
// 失败：返回 ALLOW（此分支出口，中止当前路径）
```

**② RuleLockLogicTreeNode（次数锁）**

```java
long raffleCount = Long.parseLong(ruleValue);  // 如 5，表示需抽 5 次才解锁稀有奖品
Integer userRaffleCount = repository.queryTodayUserRaffleCount(userId, strategyId);
// 未达到次数：返回 TAKE_OVER（锁定，流向兜底奖品节点）
// 已达到次数：返回 ALLOW（解锁，正常发放）
```

**③ RuleLuckAwardLogicTreeNode（兜底奖品）**

规则值格式：`106:0.01,1`（奖品 106，积分区间 0.01~1）
- 当库存不足或次数锁未解锁时触发
- 发放兜底奖品（通常是积分），并将消费事件入队

**树的遍历引擎（DecisionTreeEngine）：**

```java
// 从 treeRootRuleNode 开始
// 执行节点 logic()，获取 TreeActionEntity
// 根据 RuleLogicCheckTypeVO（TAKE_OVER/ALLOW）查找对应出边，跳转到下一节点
// 节点为 null 时结束，返回最终 StrategyAwardVO
```

**典型流程举例：**

```
用户抽中稀有奖品 → rule_stock（有库存？）
  ├─ 有库存 TAKE_OVER → rule_lock（抽够5次？）
  │    ├─ 未解锁 TAKE_OVER → rule_luck_award（发兜底积分）→ END
  │    └─ 已解锁 ALLOW → END（发稀有奖品）
  └─ 无库存 ALLOW → END（不发奖/换奖品）
```

---

### 2.4 Outbox 模式——MQ 消息投递最终一致性

#### 2.4.1 为什么要 Outbox 模式？

奖品发放涉及数据库写入 + MQ 消息发送两个操作，存在以下风险：
- 先发 MQ 后落库：MQ 成功但数据库失败 → **重复消费**
- 先落库后发 MQ：MQ 发送失败 → **消息丢失，奖品未发放**
- 直接两阶段提交：性能差，依赖 XA 协议

Outbox 模式将 MQ 消息先持久化到数据库 `task` 表，与业务数据在**同一个本地事务**中写入，再由异步 Job 扫描并投递，从根本上解决了分布式事务问题。

#### 2.4.2 Task 表结构

```
task 表字段：
  userId     ← 分库分表路由键
  topic      ← MQ Topic，如 "award_topic"
  messageId  ← 幂等键（全局唯一）
  message    ← 序列化后的消息体（JSON）
  state      ← create / completed / fail
  createTime ← 消息创建时间
  updateTime ← 最后更新时间
```

#### 2.4.3 完整写入流程

```
用户触发奖品发放
  ↓
@Transactional 本地事务：
  1. INSERT INTO user_award_record (state='create')
  2. INSERT INTO task (state='create', message=<序列化消息>)
  ↓
事务提交成功 → 两张表数据一致
```

#### 2.4.4 补偿 Job（SendMessageTaskJob）

```java
@XxlJob("SendMessageTaskJob_DB1")
public void exec_db01() {
    // 1. Redisson 分布式锁，避免多实例重复执行
    RLock lock = redissonClient.getLock("big-market-SendMessageTaskJob_DB1");
    if (!lock.tryLock(3, 0, TimeUnit.SECONDS)) return;
    
    // 2. 查询待投递任务
    //    条件：state='create' 或 (state='fail' AND updateTime < now-1分钟)
    List<TaskEntity> tasks = taskService.queryNoSendMessageTaskList();
    
    // 3. 逐条投递 + 更新状态
    for (TaskEntity task : tasks) {
        taskService.sendMessage(task);                    // 发到 MQ Broker
        taskService.updateTaskSendMessageCompleted(...);  // state='completed'
    }
}
```

**多分片处理：** 项目采用数据库分片，Job 有 `exec_db01` 和 `exec_db02` 两个方法分别处理不同分片，每个方法持有独立分布式锁。

**重试策略：** 失败任务 1 分钟后重新被扫描，通过 `updateTime < now-60s` 条件过滤，避免频繁重试。

**幂等保障：** 消费者侧通过 `messageId` 做幂等去重，确保重复投递不重复处理。

---

### 2.5 Redis 预扣减库存 + 异步批量落库

#### 2.5.1 核心思路

```
请求到达 → Redis DECR（纳秒级）→ 入队 → 立即返回响应
                                    ↓
                          后台 Job 消费队列 → 批量写 DB（毫秒级聚合）
```

**优势：** 高并发写操作不直接打到 MySQL，DB 压力从"每次请求一次写"降为"批量聚合写"，TPS 提升数量级。

#### 2.5.2 扣减逻辑（Redis 侧）

```java
// StrategyRepository.subtractionAwardStock()
long result = redisService.decr(cacheKey);  // 原子 DECR
if (result < 0) {
    redisService.incr(cacheKey);  // 超卖恢复
    return false;                 // 库存不足
}
// 扣减成功，入延迟队列
return true;
```

Redis Key 格式：`strategy:award:count:{strategyId}_{awardId}`，初始值为奖品剩余库存数。

#### 2.5.3 队列层（延迟队列）

```java
// 扣减成功后入队
strategyRepository.awardStockConsumeSendQueue(
    StrategyAwardStockKeyVO.builder()
        .strategyId(strategyId)
        .awardId(awardId)
        .build()
);
```

底层使用 Redisson 的 `RDelayedQueue<T>`（延迟队列）+ `RBlockingQueue<T>`（阻塞队列），消费端阻塞等待，元素到期后自动从延迟队列移入阻塞队列。

#### 2.5.4 异步 Job 消费（UpdateAwardStockJob）

```java
@XxlJob("updateAwardStockJob")
public void exec() {
    // 获取所有在运营的策略-奖品组合
    List<StrategyAwardStockKeyVO> stockKeys = raffleAward.queryOpenActivityStrategyAwardList();
    
    for (StrategyAwardStockKeyVO key : stockKeys) {
        // 线程池并发消费，每个 key 分配一个任务
        executor.execute(() -> {
            StrategyAwardStockKeyVO item = raffleStock.takeQueueValue(...); // 阻塞获取
            if (item != null) {
                raffleStock.updateStrategyAwardStock(...); // UPDATE strategy_award SET stock-=1
            }
        });
    }
}
```

**并发安全：** 线程池 + 分布式锁，保证多实例不重复消费。

**活动 SKU 库存同理：** `UpdateActivitySkuStockJob` 处理活动层面的 SKU 库存，使用 `ActivitySkuStockKeyVO` 队列，写入 `raffle_activity_sku` 表。

---

## 三、面试官拷打——问题与答案

---

### 3.1 关于 DDD 架构设计

**Q1: 你们为什么要用 DDD？和传统 MVC 有什么区别？落地过程中遇到了哪些挑战？**

**A:** DDD 的核心价值在于**以业务为中心划分边界**，而不是以技术分层。传统 MVC 下 Service 层直接调 Mapper，业务逻辑和 SQL 耦合在一起，换个缓存策略就要改 Service；DDD 中领域层只依赖仓储接口，不关心底层是 MySQL 还是 Redis，切换基础设施只需改仓储实现。

落地挑战主要有两点：第一，**PO 和 Entity 的双向转换**带来额外代码量，尤其是字段多的聚合根；我们的解法是统一在仓储实现中做转换，领域层完全不见 PO。第二，**事务边界**：DDD 鼓励跨聚合用最终一致性（事件/MQ），但如果业务上要求强一致，就得在应用层用 `@Transactional` 跨仓储操作，这和 DDD 理念有一定矛盾，需要权衡。

---

**Q2: 你们的聚合是怎么设计的？聚合根是什么？**

**A:** 以活动领域为例，`CreatePartakeOrderAggregate` 是参与活动下单的聚合，内部包含：
- `ActivityAccountEntity`（用户总配额账户）
- `ActivityAccountMonthEntity`（月配额账户）
- `ActivityAccountDayEntity`（日配额账户）
- `UserRaffleOrderEntity`（本次参与的抽奖订单）

聚合根是 `ActivityOrderEntity`（活动订单），它持有所有账户实体，对外提供统一的业务方法，数据库写入时在一个事务里完成。聚合内部的实体不能被外部直接访问，只能通过聚合根的方法操作。

---

**Q3: 仓储层的缓存策略是怎么做的？会有缓存一致性问题吗？**

**A:** 策略是 **Cache-Aside 模式**：读时先查 Redis，未命中查 MySQL 并回写；写时先更新 MySQL，再删除/更新对应 Redis 缓存 key。

缓存一致性主要靠**缓存失效**来保证——对于策略配置、奖品信息等低频变更的数据，设置合理的 TTL；对于库存这类高频变更的计数，直接以 Redis 为准，DB 通过异步 Job 追赶，不要求强一致，只要最终一致即可。极端情况（Redis 宕机重启）下，系统会降级到直接走 DB，并在策略预热时重新构建 Redis 数据结构。

---

### 3.2 关于 O(1) 抽奖算法

**Q4: 你说是 O(1) 时间复杂度，但构建阶段不是 O(n) 吗？怎么理解这个 O(1)？**

**A:** 这里的 O(1) 指的是**每次抽奖请求的执行时间**，而非算法总体时间。构建（Armory）阶段是 O(n)，在系统启动或活动上线时执行一次，属于一次性预热成本。之后每次抽奖只需：
1. 读取 Redis 中的 `rateRange`（一次 GET）
2. `new SecureRandom().nextInt(rateRange)`（本地 CPU 操作）
3. Redis Hash HGET（一次 HGET）

三步均为常数时间，与奖品数量无关，因此摊薄到每次请求是 O(1)。

---

**Q5: 为什么用 Fisher-Yates 洗牌？不洗牌会怎样？**

**A:** 不洗牌的话，查找表中相同 awardId 的槽位是连续的，虽然抽奖结果概率上正确，但在统计上存在"局部聚集"问题——例如前 30% 的随机数永远对应同一个奖品，概率分布在低维度的实验里偏差较大。Fisher-Yates 洗牌保证每个槽位等概率出现，使得概率分布在有限次抽奖中也均匀，更符合"随机"的统计期望。此外洗牌也有一定防作弊效果：攻击者无法通过枚举下标预测奖品分布规律。

---

**Q6: rateRange 是怎么确定的？如果奖品概率精度很高怎么办？**

**A:** `rateRange` 是所有奖品概率的**最小公倍分母**的最简形式，实际代码中是通过 BigDecimal 找最小精度单位，然后取倒数得到范围大小。例如概率精度为 0.001，则 rateRange = 1000，查找表有 1000 个槽位。

如果精度极高（如 0.00001），rateRange 就是 100000，查找表占用 100KB 左右的 Redis Hash，内存开销可接受。若奖品数量很多且精度极高，可以选用 O(log n) 算法（`OLogNAlgorithm`），它用范围区间而非展开表，空间复杂度 O(n)，时间 O(log n)，两种算法在装配时通过策略模式可切换。

---

**Q7: Redis 宕机了，抽奖查找表丢失，怎么处理？**

**A:** 有两道防线：

第一，Redis 本身配置了 AOF 持久化 + RDB 快照，宕机重启后数据可以恢复。

第二，代码层面在策略服务初始化时（`@PostConstruct` 或活动上线 Event 触发）会执行 `assembleLotteryStrategy()`，自动重建所有在运营活动的查找表。这个预热逻辑幂等，无论 Redis 里是否已有数据，重跑不影响正确性。

---

**Q8: 使用 SecureRandom 而不是 Random，为什么？有性能影响吗？**

**A:** `SecureRandom` 基于操作系统的熵源（如 `/dev/urandom`），随机性更强，防止攻击者通过预测伪随机序列猜测抽奖结果（尤其在高价值奖品场景下）。

性能影响：在 Linux 下使用 `/dev/urandom` 的 `SecureRandom` 吞吐量和 `Random` 接近，不是瓶颈。实际测试中，单次 `nextInt` 耗时在微秒级，远低于 Redis 网络 RT（毫秒级），不是系统瓶颈。

---

### 3.3 关于规则引擎

**Q9: 为什么要分两层——责任链和决策树？合并成一层不行吗？**

**A:** 两层的职责根本不同：

- **责任链**处理的是"**这次抽奖用哪个奖品池**"，它在抽奖动作之前，决定的是**输入**（用哪个概率表）。
- **决策树**处理的是"**抽中的这个奖品能不能发、怎么发**"，它在抽奖动作之后，决定的是**输出**（库存、次数限制、兜底替换）。

两者的配置数据结构也不同：链是有序列表，树是有向图。强行合并会使逻辑混乱，规则扩展时互相影响。分层后，业务方可以独立配置"前置过滤规则"和"后置处理规则"，编排灵活度更高。

---

**Q10: 责任链中，节点如何保证线程安全？一个策略的链被多个用户并发使用，会互相干扰吗？**

**A:** 每个责任链节点 Bean 都使用 Spring 的 `@Scope(SCOPE_PROTOTYPE)` 原型作用域，`DefaultChainFactory` 在 `openLogicChain()` 中通过 `applicationContext.getBean()` 创建新实例，而不是复用单例。

已组装好的链对象缓存在 `strategyChainGroup`（ConcurrentHashMap）中，每个策略一条链。链对象本身只保存"下一节点引用"，不保存任何请求状态；每个节点的 `logic()` 方法是无状态方法，所有数据来自参数或从 Redis/DB 读取，不存在实例变量共享，天然线程安全。

---

**Q11: 决策树的配置是存在数据库里的，每次抽奖都要查库吗？如何优化？**

**A:** 不是每次查库。树的配置（`rule_tree`、`rule_tree_node`、`rule_tree_node_line`）在首次访问时加载，存入 Redis（`RuleTreeVO` 序列化后缓存），后续抽奖直接从 Redis 读取完整树结构，构建 `DecisionTreeEngine` 对象。

进一步优化：`DefaultTreeFactory` 在内存中维护了一个 `HashMap<treeId, IDecisionTreeEngine>` 缓存，已构建的引擎对象直接复用，无需每次反序列化 Redis 数据。树配置变更时，只需删除对应 Redis 缓存 key，下次访问自动重建。

---

**Q12: rule_lock（次数锁）每次都要查数据库统计今日抽奖次数吗？**

**A:** `queryTodayUserRaffleCount` 查询的是 `user_raffle_order` 表当天该用户的记录数。这个查询走索引（userId + createTime），通常很快。

更优化的做法是用 Redis 计数器：用户每次参与抽奖时，`INCR user:raffle:count:{userId}:{date}`，次数锁直接读 Redis。这样规避了 DB 查询，且天然具有 expire 属性（设置到次日零点自动过期），项目中这个优化空间可以在迭代中继续完善。

---

### 3.4 关于 Outbox 模式

**Q13: Outbox 模式的本质是什么？为什么说它能保证最终一致性？**

**A:** Outbox 模式的本质是**把"发消息"这个动作转换为"写数据库记录"**。由于业务数据和 Task 记录在同一个本地事务中写入，要么都成功，要么都失败，不存在中间状态。MQ 的实际投递由异步 Job 完成，即使 Job 失败，Task 记录仍在数据库，下一轮重试时仍会被处理，最终一定会发出去——这就是最终一致性的保证。

关键约束：消费者侧必须做**幂等处理**（基于 messageId 去重），因为 Job 可能在消息已发但状态未更新时重启，导致重复投递。

---

**Q14: 如果 MQ 消息发送成功，但更新 Task.state='completed' 失败（网络抖动），会怎样？**

**A:** 这是 Outbox 模式的经典问题——"at-least-once" 语义。Task 记录会在下一轮 Job 执行时被再次扫描（因为 state 还是 'create' 或更新时间过期），重新发送一次消息。

消费者必须通过 `messageId` 做幂等去重：收到重复消息时，检查对应业务记录是否已处理，若已处理则丢弃，不重复执行。这是分布式系统中保证"exactly-once"语义的标准做法——发送端 at-least-once + 消费端幂等 = 业务层 exactly-once。

---

**Q15: 补偿 Job 的扫描频率怎么设定？太频繁会有什么问题？**

**A:** 扫描频率和消息投递延迟是 trade-off：
- 频率过高：DB 扫描压力大（全表扫 state+updateTime 索引），多实例争抢分布式锁
- 频率过低：奖品发放延迟大，用户体验差

我们的策略是：Job 执行周期设为 10 秒，配合 `updateTime < now-60s` 的过滤条件。正常情况下，任务在 10 秒内首次投递；失败后等待 1 分钟再重试，避免因瞬时网络问题频繁重试造成 MQ Broker 压力。

生产上还可以配合 MQ 回调（发送成功回调立即更新 state），减少对 Job 扫描的依赖，只有回调失败时才靠 Job 兜底。

---

### 3.5 关于 Redis 库存与并发

**Q16: Redis DECR 扣减库存，如果 DECR 成功但后续业务失败，库存怎么恢复？**

**A:** 这是个很好的问题。当前代码的做法是：`subtractionAwardStock` 返回 true 后，会将库存消费事件入队，后续异步落库。如果落库这步失败（如 DB 写入异常），队列中的事件会丢失，导致 Redis 扣减了但 DB 没有对应记录，形成"幽灵扣减"。

更健壮的做法：
1. 落库失败时执行 `INCR` 回滚 Redis 计数，保持 Redis 和 DB 的最终一致
2. 或者在 DB 记录本地事务失败时触发补偿，重新加回计数
3. 定时对账 Job：定期比对 Redis 计数和 DB 实际消耗数量，发现偏差时修正

---

**Q17: 你们用了延迟队列，延迟时间是多少？为什么不用普通 List 或者 RabbitMQ？**

**A:** 延迟时间是 5 秒左右（通过 Redisson `RDelayedQueue` 配置）。使用延迟队列的目的是**聚合批量写**：5 秒内的库存消耗事件积累后，后台 Job 一次性批量写入 DB，减少 DB 写次数，提升吞吐。

选 Redisson 内置延迟队列而不是外部 MQ 的原因：库存落库是系统内部的批处理任务，不需要跨系统通信，引入外部 MQ 增加了运维复杂度和故障点。Redisson 的队列原子性由 Redis 保证，足以满足需求，且与现有 Redis 基础设施复用。

---

**Q18: 高并发下，Redis DECR 是原子的，但 DECR 之后如果进程崩溃，库存扣了但订单没建，怎么办？**

**A:** 这是分布式系统中的典型**部分失败**问题。处理方式：

1. **Redis 库存 ≠ 最终库存**：Redis 只是"乐观锁"层，真正的库存以 DB 为准。Redis 计数允许有短暂偏差。
2. **对账机制**：定时 Job 比对 `strategy_award.award_count_surplus`（DB 剩余量）和 Redis 计数，若 Redis 偏低，说明有"扣了但没落库"的情况，执行 `INCR` 修正。
3. **Redis 过期策略**：活动结束时间可以作为 Redis key 的 expireDate，活动结束后自动清理，不影响下次活动。

---

**Q19: 数据库分片（分库分表）是怎么做的？对跨库查询有什么影响？**

**A:** 数据库路由以 `userId` 为分片键，通过自研 `db-router-spring-boot-starter`（基于 AOP + ThreadLocal）在 SQL 执行前动态切换数据源。例如 `userId % 2` 决定路由到 DB1 还是 DB2。

跨库查询的影响：无法做 JOIN、无法做全局排序分页。解决方式：
- 查询层引入 Elasticsearch（项目中有 `ESUserRaffleOrderRepository`），将订单数据异步同步到 ES，复杂查询走 ES
- 排行榜、统计类数据用 Redis ZSet/Hash 汇总，不依赖 DB 聚合查询
- SendMessageTaskJob 分为 `exec_db01` 和 `exec_db02` 两个方法分别处理，体现了分片带来的 Job 复杂度

---

### 3.6 综合设计问题

**Q20: 整个抽奖流程走一遍，从用户发请求到最终拿到奖品，经历了哪些环节？**

**A:** 完整链路如下：

```
1. [Trigger 层] HTTP 接口接收请求
       ↓
2. [Activity 领域] 检查活动状态、用户配额（总/月/日），扣减配额，建抽奖订单
       ↓
3. [Strategy 领域] 责任链过滤
   - BlackList：是否黑名单用户？→ 是则直接返回固定安慰奖品
   - RuleWeight：用户积分够哪个分段？→ 是则用对应权重池
   - Default：标准抽奖（O(1) Redis Hash 查找）
       ↓
4. [Strategy 领域] 决策树处理
   - rule_stock：Redis DECR 扣库存 → 入延迟队列
   - rule_lock：今日抽奖次数够了吗？→ 够则发原奖品，不够则走 rule_luck_award
   - rule_luck_award：发兜底积分奖品
       ↓
5. [Award 领域] 记录用户获奖记录 + 写 Task 表（同一事务）
       ↓
6. [异步] SendMessageTaskJob 扫描 Task 表，发 MQ 消息
       ↓
7. [MQ Consumer] 接收消息，执行奖品发放（积分入账/实物发货等）
       ↓
8. [异步] UpdateAwardStockJob 消费延迟队列，批量更新 strategy_award.award_count_surplus
```

---

**Q21: 系统如何防止超卖？从 Redis 到 DB 整条链路是否安全？**

**A:** 防超卖是多层防护：

**第一层：Redis 原子 DECR**
```java
long result = redisService.decr(cacheKey);
if (result < 0) { redisService.incr(cacheKey); return false; }
```
单次请求中，若 DECR 后值 < 0 则立即 INCR 回滚，返回"库存不足"。Redis 单线程命令执行，DECR 天然原子。

**第二层：DB 乐观更新**
更新 `strategy_award` 时：
```sql
UPDATE strategy_award SET award_count_surplus = award_count_surplus - 1
WHERE strategy_id = ? AND award_id = ? AND award_count_surplus > 0
```
`award_count_surplus > 0` 的条件防止 DB 层超卖，即使 Redis 计数出现偏差也有兜底。

**第三层：活动配额校验**
在 Activity 领域参与活动时，检查用户总/月/日配额，提前拦截超出限额的请求，减少无效进入后续流程的压力。

---

**Q22: 如果让你优化这个系统，你会从哪些方面入手？**

**A:** 按优先级排列：

**性能优化：**
- 责任链节点读取规则值目前走 DB（加 Redis 缓存可降低延迟）
- rule_lock 的今日抽奖次数统计改为 Redis INCR+expire，避免 DB COUNT 查询
- 批量预热：多个策略并行预热，利用 CompletableFuture 并行提升启动速度

**可靠性优化：**
- 引入 MQ 发送回调（成功回调立即更新 Task.state），减少对轮询 Job 的依赖
- 增加 Redis 和 DB 的对账 Job，定期校正库存偏差
- 对关键业务指标（抽奖成功率、消息延迟、库存偏差量）做监控告警

**可扩展性优化：**
- 规则引擎支持动态加载（从数据库读取规则配置后热更新链/树，无需重启）
- 引入 Lua 脚本将 Redis 扣减+入队合并为一个原子操作，消除 DECR 成功但入队失败的窗口
- 考虑 CQRS 进一步分离读写，查询侧用 Elasticsearch 支撑复杂统计报表

---

**Q23: 为什么选用 Redisson 而不是直接用 Jedis/Lettuce 操作 Redis？**

**A:** Redisson 在原生 Redis 命令之上提供了高级数据结构（`RMap`、`RDelayedQueue`、`RBlockingQueue`、`RLock`、`RAtomicLong`），屏蔽了分布式锁实现（Lua 脚本 + watchdog 续期）、延迟队列（`ZADD`+`BLPOP`组合）等复杂实现细节。

如果用 Jedis 自己实现分布式锁，需要处理锁超时、可重入、看门狗续期、Failover 等大量边界情况。Redisson 开箱即用，减少了自研轮子的风险，且性能满足需求（内部也是基于 Netty 异步 IO）。

---

**Q24: 活动的状态机是怎么设计的？有哪些状态？**

**A:** 活动状态流转：
```
编辑（edit）→ 待开始（open）→ 进行中（running）→ 关闭（close） / 结束（finish）
                               ↓
                           暂停（suspend）→ 进行中（running）（可恢复）
```
策略中的奖品状态：`open`（可用）/ `close`（已下架）/ `排期中`。

状态变更通过 `ActivityStateVO` 枚举 + 状态机方法（如 `openActivity()`、`closeActivity()`）封装，防止非法状态转换（如从 close 直接到 running）。

---

**Q25: 项目里说到"多线程预装配"，具体是怎么实现的？线程池参数怎么配置？**

**A:** 在 `AbstractStrategyAlgorithm.assembleLotteryStrategy()` 中，针对一个策略，需要构建：
1. 默认奖品池的查找表（全量奖品）
2. 每个 `rule_weight` 分段各自的查找表

这些查找表的构建互相独立，通过注入的 `ThreadPoolExecutor` 并行提交，主线程等待所有子任务完成（`CountDownLatch` 或 `Future.get()`）后返回。

线程池参数按业务峰值配置：
- corePoolSize = CPU 核数 × 2（IO 密集，Redis 写操作）
- maxPoolSize = corePoolSize × 2
- queueCapacity = 策略数量上限（避免拒绝策略触发）
- keepAliveTime = 60s

配置文件中可以动态调整，不硬编码在 Java 代码里。

---

> 文档基于 [big-market](https://github.com/dyxnb22/big-market) 项目实际代码整理，包含 O(1) 抽奖算法、双层规则引擎、Outbox 消息模式、Redis 库存预扣减等核心实现的深度解析，以及 25 道面试深挖题与参考答案。
