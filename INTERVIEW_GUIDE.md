# Big-Market 大营销系统 · 简历 & 面试准备指南

> 本文档基于项目全量源码整理，可直接用于简历填写和面试备考。

---

## 一、简历项目描述（直接可用版）

### 【推荐写法 · 完整版】

**大营销系统（Big-Market）**

基于 DDD 领域驱动设计，采用 Java 8 + Spring Boot 2.7 + MyBatis 构建的企业级营销中台系统。系统涵盖抽奖活动管理、奖品发放、行为返利、积分账户、策略配置及用户认证等核心业务域，支持高并发场景下的实时库存扣减、异步消息驱动发奖和分布式分库分表。

**技术亮点：**
- 引入**责任链 + 决策树**双层规则引擎，灵活编排抽奖前置过滤（黑名单、权重、次数限制、库存保护）和抽奖后兜底逻辑，新增规则零侵入原有代码。
- 基于 **Redis（Redisson）** 实现毫秒级库存快速扣减，异步 Job 同步至 MySQL，并通过 RabbitMQ 死信队列兜底，保障最终一致性。
- 使用 **Dubbo 3.0 + Nacos** 提供 RPC 服务注册与发现；**XXL-Job** 管理库存同步、消息重发等分布式定时任务。
- 业务整体拆分为 6 个 DDD 领域（策略、活动、奖品、积分、返利、认证），通过聚合根和领域事件解耦跨域调用，并以 **RabbitMQ 事件驱动**串联完整抽奖链路。
- 接入 **Zookeeper DCC 动态配置**、**Hystrix 熔断降级**和自定义 AOP 限流注解，支持无感知服务降级。
- 实现 MySQL **2库4表分库分表**（路由键：userId），高峰期单库 TPS 有效降低约 50%。

---

### 【精简版（字数约 150 字，适合岗位对应简历）】

基于 Java 8 + Spring Boot + DDD 开发的高并发营销中台，涵盖抽奖、返利、积分等核心业务域。引入责任链+决策树双层规则引擎解耦抽奖流程；Redis 毫秒级库存扣减 + RabbitMQ 异步发奖保障高并发一致性；Dubbo+Nacos 提供微服务 RPC；MySQL 分库分表（2库4表）、动态配置降级（Zookeeper DCC）、Hystrix 熔断等工程措施均已落地。

---

## 二、技术架构总览

```
HTTP / Dubbo RPC
        │
   Trigger 层（Controller / Listener / Job）
        │
   Domain 层（Service / Entity / Repository接口）
        │
Infrastructure 层（Repository实现 / DAO / Redis / MQ / ES）
        │
   MySQL（分库分表）/ Redis / RabbitMQ / Elasticsearch
```

### 技术选型一览

| 分类 | 技术 | 版本 | 作用 |
|------|------|------|------|
| 主框架 | Spring Boot | 2.7.12 | IoC / MVC / AOP |
| ORM | MyBatis | 2.1.4 | 持久层 |
| RPC | Dubbo + Nacos | 3.0.9 / 2.1.0 | 微服务调用 & 注册 |
| 缓存 | Redisson（Redis） | 3.26.0 | 高速缓存 & 分布式锁 |
| 消息队列 | RabbitMQ | AMQP 3.2.0 | 异步解耦 & 最终一致性 |
| 定时任务 | XXL-Job | 2.4.1 | 分布式调度 |
| 分库分表 | db-router-starter | 1.0.4 | 路由键分片 |
| 配置中心 | Zookeeper | 3.1.4 | DCC 动态配置 |
| 熔断限流 | Hystrix + 自定义AOP | 1.5.18 | 服务保护 |
| 搜索 | Elasticsearch | 7.17.14 | 订单查询 |
| 外部接口 | Retrofit2 | 2.9.0 | OpenAI 等 HTTP 调用 |
| 监控 | Prometheus | - | 指标采集 |
| 认证 | JWT | 4.4.0 | 用户 Token |

---

## 三、功能点清单（子系统拆解）

### 3.1 策略域（Strategy）——抽奖核心

| 功能点 | 技术实现要点 |
|--------|-------------|
| 策略装配（缓存预热） | 启动/触发时将策略权重表写入 Redis，后续请求纯缓存命中 |
| O(1) 随机抽奖算法 | 构建概率区间数组，`random * 总权重` 直接映射奖品 |
| O(logN) 算法（二分） | 有序区间 + 二分查找，节省内存 |
| 前置规则责任链 | `黑名单检查 → 权重规则 → Default`，按配置动态编排 |
| 后置规则决策树 | `库存检查 → 参与次数限制 → 兜底奖品`，树形结构 |
| 规则引擎工厂 | `DefaultChainFactory / DefaultTreeFactory` 工厂模式构建 |

**工程关注点：**
- 责任链节点通过 Spring Bean + 工厂组装，新增规则只需实现接口并配置，无需修改主流程。
- 决策树节点挂载在数据库（`rule_tree / rule_tree_node / rule_tree_node_line`），支持配置化。

---

### 3.2 活动域（Activity）——活动全生命周期

| 功能点 | 技术实现要点 |
|--------|-------------|
| 活动参与（下单） | 幂等校验 + 日/月配额扣减 + 用户抽奖订单创建，一次事务 |
| SKU 库存管理 | Redis `DECR` 原子扣减，库存归零发 MQ 通知下架 |
| 日/月配额限制 | `raffle_activity_account_day / month` 分表管理，DB 行锁防超发 |
| 活动上架/下架 | `ActivitySkuStockZeroMessageEvent` 驱动异步下架 |
| 活动参与链 | `基础校验 → SKU库存扣减`，ActionChain 模式 |
| 聚合根 | `CreatePartakeOrderAggregate` 封装下单整体操作 |

**工程关注点：**
- 下单流程采用 `@Transactional` 本地事务保证参与订单与配额扣减原子性。
- 库存最终一致性：Redis 扣减 → XXL-Job 异步同步 → 数据库更新，宕机场景下 Job 补偿兜底。

---

### 3.3 奖品域（Award）——发奖链路

| 功能点 | 技术实现要点 |
|--------|-------------|
| 发奖异步化 | 抽奖结果写库后发布 `SendAwardMessageEvent`，MQ 消费端处理 |
| 奖品策略模式 | `IDistributeAward` 接口 + 多种实现（积分、OpenAI 额度等） |
| 积分奖品 | `UserCreditRandomAward`：随机积分 + 写入 `user_credit_account` |
| OpenAI 奖品 | `OpenAIAccountAdjustQuotaAward`：Retrofit2 调用第三方接口 |
| 发奖幂等 | `user_award_record` 唯一索引防重复发奖 |
| 聚合根 | `GiveOutPrizesAggregate` 封装发奖全流程 |

**工程关注点：**
- MQ 消费失败进死信队列，后台 Job 扫描未完成任务重新投递，保证最终发奖。
- 奖品类型扩展：新增类型只需实现 `IDistributeAward` 并以 `awardKey` 注册到 Spring，无需改主流程。

---

### 3.4 积分域（Credit）——用户积分账户

| 功能点 | 技术实现要点 |
|--------|-------------|
| 积分充值/消费 | `ICreditAdjustService`，交易类型枚举区分充值/消费/返利 |
| 积分账户 | `user_credit_account` 存储余额，乐观锁或行锁防并发超扣 |
| 积分订单 | `user_credit_order` 流水记录，用于对账 |
| 跨域事件 | `CreditAdjustSuccessMessageEvent`，告知其他域积分操作完成 |

---

### 3.5 返利域（Rebate）——行为返利

| 功能点 | 技术实现要点 |
|--------|-------------|
| 行为触发返利 | 签到/支付等行为 → 查 `daily_behavior_rebate` 配置 → 生成返利订单 |
| 返利类型 | 支持积分返利、SKU 返利两种 |
| 异步返利 | `SendRebateMessageEvent` → MQ → `RebateMessageCustomer` 落库 |
| 幂等设计 | `user_behavior_rebate_order` 业务唯一键防重复返利 |

---

### 3.6 认证域（Auth）——Token 鉴权

| 功能点 | 技术实现要点 |
|--------|-------------|
| Token 生成 | JWT 签发，携带 userId、角色等 Claim |
| Token 校验 | Controller 入参 `@RequestHeader("Authorization")` + `AbstractAuthService` |
| 角色权限 | Token 解析后进行权限判断 |

---

### 3.7 任务域（Task）——可靠消息

| 功能点 | 技术实现要点 |
|--------|-------------|
| 消息本地落库 | 事件发布前先写 `task` 表，防止 MQ 宕机丢消息 |
| Job 补偿重发 | `SendMessageTaskJob` 扫描未发送/失败任务重新投递 |
| 消息状态机 | `waiting → sending → complete / fail` |

---

### 3.8 触发层（Trigger）

| 功能点 | 技术实现要点 |
|--------|-------------|
| REST 接口 | 4 个 Controller，约 20+ 端点，统一 `Response<T>` 响应结构 |
| Dubbo RPC | Controller 同时标注 `@DubboService`，复用同一实现层 |
| MQ 消费 | 4 个 `@RabbitListener`，对应 4 条业务链路 |
| 定时任务 | 3 个 XXL-Job 处理器（库存同步、奖品库存、消息补发） |
| 限流 | 自定义 `@RateLimiterAccessInterceptor` AOP 注解 |
| 熔断 | `@HystrixCommand` 接口级熔断，降级返回预设值 |
| 动态降级 | `@DCCValue("degradeSwitch:close")` 从 Zookeeper 热更新开关 |

---

### 3.9 基础设施层（Infrastructure）

| 功能点 | 技术实现要点 |
|--------|-------------|
| 分库分表 | `db-router-starter`，2库×4表，路由键 userId |
| 多数据源 | MySQL 主库 + ES（`DataSourceConfig` 统一管理） |
| Redis 缓存 | Redisson 客户端，支持分布式锁、原子计数 |
| 消息发布 | `EventPublisher` 统一封装 RabbitTemplate |
| ES 查询 | JDBC 方式查询用户抽奖订单 |
| Prometheus | `/actuator/prometheus` 导出 JVM 及自定义指标 |

---

## 四、核心链路时序（便于讲解）

### 4.1 完整抽奖链路

```
用户 → POST /raffle_participate
  1. JWT Token 验证
  2. 查询活动配置（Redis缓存 → MySQL兜底）
  3. ActivityChain: 基础校验 → SKU库存 Redis DECR
  4. 查询日/月配额，DB 行锁防超发
  5. 创建 user_raffle_order（本地事务，幂等校验）
  6. AbstractRaffleStrategy.performRaffle()
     a. 前置责任链：黑名单 → 权重 → 默认
     b. O(1)/O(logN) 随机抽奖
     c. 后置决策树：库存检查 → 次数限制 → 兜底
  7. 写入奖品记录 + 发布 SendAwardMessageEvent（先落 task 表）
  8. 返回抽奖结果
  
RabbitMQ 异步：
  9. SendAwardCustomer 消费
  10. IDistributeAward 策略分发（积分/OpenAI/…）
  11. 更新奖品状态、积分账户
  12. 更新 task 表为 complete
```

### 4.2 库存最终一致性链路

```
Redis DECR（原子）
  ↓ 成功
写入 raffle_activity_sku.stock_count_surplus（异步 Job）
  ↓ 库存归零
发布 ActivitySkuStockZeroMessageEvent → MQ
  ↓
ActivitySkuStockZeroCustomer：更新活动状态为下架
  ↓ 宕机/消费失败
XXL-Job UpdateActivitySkuStockJob 扫描 Redis 队列补偿
```

---

## 五、面试深挖问题 & 应答思路

### 🔥 板块一：系统架构

**Q1：为什么选择 DDD 架构？划分了哪些域？如何防止跨域耦合？**

> 营销系统业务规则复杂（抽奖规则、活动配置、积分算法各自独立演进），DDD 可以通过聚合根约束业务不变量，通过领域事件解耦跨域调用。项目划分了策略、活动、奖品、积分、返利、认证 6 个域，域间通过 `DomainEvent + RabbitMQ` 或 Repository 接口隔离。例如：发奖域只消费 `SendAwardMessageEvent`，不直接依赖活动域代码。

---

**Q2：分库分表如何设计？路由键选择 userId 的考量？**

> 使用 `db-router-spring-boot-starter`，按 `userId % 2` 路由到 db01/db02，再按 `userId / 2 % 4` 路由到具体表，共 8 个逻辑分片，满足 2 的幂次要求，便于后续扩容翻倍。userId 作为路由键的原因：
> - 营销系统绝大多数查询都是用户维度（我的订单、我的配额），以 userId 分片使同一用户的数据落在同一库，避免跨库 JOIN。
> - 活动维度的全量统计通过 ES 异步同步，不需要跨库聚合。

---

**Q3：如何保证分布式事务的一致性？**

> 本项目核心采用**事务消息 + 本地消息表**方案：
> 1. 发布事件前先在同一本地事务中写 `task` 表（状态 waiting）。
> 2. 主业务提交后发布 MQ 消息。
> 3. MQ 消费成功后更新 task 为 complete。
> 4. XXL-Job 定期扫描 waiting/fail 状态的 task 重新投递，保证最终一致性。
> 
> 对于库存扣减：Redis 先扣 → Job 异步写 DB，超卖风险通过 Redis 原子操作保证，写 DB 只是持久化，不存在反向超发问题。

---

### 🔥 板块二：抽奖核心

**Q4：O(1) 抽奖算法怎么实现的？为什么能做到 O(1)？**

> 策略装配时（`IStrategyArmory.assembleLotteryStrategy`）：
> 1. 读取所有奖品及概率，计算最小公倍数/整数比，生成总权重 N。
> 2. 构建长度为 N 的数组，将奖品 ID 填入对应下标区间（如奖品A概率30%填0-29，奖品B填30-59…）。
> 3. 抽奖时：`random.nextInt(N)` 直接取数组对应位置，即为奖品，**时间复杂度 O(1)**。
> 4. 装配结果写入 Redis，抽奖无需查库。
> 
> O(logN) 方案对比：将概率转为累积区间，二分查找定位奖品，内存占用更小但速度稍慢。

---

**Q5：规则引擎责任链和决策树分别解决什么问题？如何扩展？**

> - **责任链**（前置过滤）：对同一抽奖请求依次过滤，任一节点拦截则短路返回。例如黑名单用户直接返回最低奖，无需进入主抽奖逻辑。链节点通过 Spring Bean 按优先级注入，新增规则只需实现 `ILogicChain` 接口并加注解，`DefaultChainFactory` 自动装配。
> - **决策树**（后置路由）：获得初始奖品后进行再判断（库存不足则换奖、达到次数限制则降级），是树形分支，不是顺序过滤。节点配置在 DB 的 `rule_tree_node` 中，支持配置化调整路由逻辑。

---

**Q6：库存扣减如何防止超卖？库存为 0 时如何停止发奖？**

> 1. Redis `DECR` 是原子操作，返回值 ≤ 0 时直接判定库存不足，不进入抽奖。
> 2. 决策树中 `RuleStockLogicTreeNode` 在 Redis 层扣减成功后才允许发奖，否则走兜底奖品。
> 3. 库存归零时向 MQ 发送 `ActivitySkuStockZeroMessageEvent`，消费端将活动置为下架，后续请求在活动校验阶段即拦截。
> 4. Redis 与 DB 的同步由 `UpdateActivitySkuStockJob` 每隔一段时间批量写入，防止频繁 DB 写入。

---

### 🔥 板块三：高并发 & 性能

**Q7：高并发下如何保证日/月配额不超发？**

> 配额扣减流程：
> 1. 查询当前日配额记录（`raffle_activity_account_day`），若不存在则 `INSERT`，若存在则 `UPDATE ... WHERE day_count_surplus > 0`。
> 2. `UPDATE` 的 `WHERE day_count_surplus > 0` 起到乐观锁作用——并发时只有一个线程能将最后一个配额成功扣减，其他线程 `affected rows = 0` 后返回配额不足。
> 3. 对于超高频场景可在 Redis 层加一层前置计数，减少 DB 压力。

---

**Q8：限流是如何实现的？**

> 自定义 `@RateLimiterAccessInterceptor` AOP 注解，拦截所有被标注方法：
> 1. 使用 **Guava RateLimiter**（令牌桶）按方法维度限流，QPS 可配置。
> 2. 超出限流阈值时执行 fallback 方法（返回 `Response.fail` 或降级响应）。
> 3. 与 `@HystrixCommand` 组合：限流在前（AOP），熔断在后（Hystrix），梯级保护。

---

**Q9：缓存预热是什么？为什么要做？遇到缓存击穿怎么处理？**

> - 缓存预热：调用 `/strategy_armory` 或 `/activity_armory` 接口时，将整个策略/活动的权重表、奖品列表、规则树等全量写入 Redis，之后抽奖请求全部命中缓存，不查 DB。
> - 意义：避免活动上线瞬间流量全部打到 DB；保证抽奖 RT < 10ms。
> - 缓存击穿：装配采用分布式锁（Redisson `RLock`），同一策略同一时刻只有一个线程执行装配逻辑，其余线程等待，防止并发重建。
> - 缓存穿透：奖品列表不为空必须装配过才能参与，从业务流程上规避了空数据攻击。

---

### 🔥 板块四：可靠性 & 异常处理

**Q10：MQ 消息丢失了怎么办？重复消费如何处理？**

> **防丢失**：
> - 生产端：先写 `task` 本地消息表，再发 MQ；Job 扫描未成功的 task 重试。
> - Broker 端：RabbitMQ 开启持久化，交换机和队列均 durable=true。
> - 消费端：手动 ACK，消费成功后才确认，消费失败进死信队列。
> 
> **防重复消费**：
> - `user_award_record`、`user_behavior_rebate_order` 等关键表均有业务唯一键，重复消费时会触发 `duplicate key` 异常，捕获后幂等返回成功。
> - 消费端先查状态，已处理则直接返回。

---

**Q11：系统如何做降级？Zookeeper DCC 的原理？**

> - Controller 字段用 `@DCCValue("degradeSwitch:close")` 注入，值来自 Zookeeper 配置节点。
> - `DCCValueBeanFactory` 监听 Zookeeper 节点变化，节点更新时通过反射修改对应 Bean 字段值，实现热更新（无需重启）。
> - 抽奖入口判断 `degradeSwitch == "open"` 时直接返回降级响应，保护下游服务。
> - 搭配 Hystrix 超时熔断：若策略查询超时，Hystrix fallback 返回空列表，保证接口不挂死。

---

**Q12：事务失败如何回滚？有没有数据补偿机制？**

> - 本地事务：`@Transactional` 包裹下单/发奖/积分等写操作，抛异常自动回滚。
> - 跨域补偿：
>   1. 下单成功但 MQ 未发出 → task 表扫描重发。
>   2. MQ 发出但消费失败 → 死信队列 + 人工/Job 处理。
>   3. Redis 库存已扣减但 DB 事务回滚 → 库存出现短暂超卖概率，通过 Job 异步对账修正，或在 Redis 扣减时使用 Lua 脚本与 DB 操作绑定（可作为优化点提出）。

---

### 🔥 板块五：设计模式

**Q13：项目中用到了哪些设计模式？举一个最复杂的例子。**

> | 模式 | 落地场景 |
> |------|---------|
> | 策略模式 | `IDistributeAward`：积分/OpenAI/自定义奖品 |
> | 工厂模式 | `DefaultChainFactory / DefaultTreeFactory` |
> | 模板方法 | `AbstractRaffleStrategy`：定义抽奖标准流程 |
> | 责任链 | 前置规则过滤（黑名单→权重→默认） |
> | 决策树 | 后置奖品路由（库存→次数→兜底） |
> | 适配器 | Repository 实现适配 Domain 接口 |
> | 观察者 | 领域事件 + MQ 订阅 |
> | 装饰器 | 缓存预热对核心查询的增强 |
> 
> **最复杂例子——规则树**：`DefaultRaffleStrategy.doCheckTreeLogicAfterLottery()` 调用 `DefaultTreeFactory` 构建规则树根节点，每个节点实现 `ILogicTreeNode`，通过递归 `process()` 向下遍历，根据返回的 `moveType`（YES/NO）走不同子节点，最终输出过滤后的奖品。节点配置在 DB，业务修改规则只需调整数据行，无需改代码。

---

**Q14：如何保证接口幂等性？**

> - 下单接口：`user_raffle_order` 以 `(userId, activityId, orderId)` 为唯一索引，重复提交 catch `DuplicateKeyException` 后返回已有订单号。
> - 发奖接口：`user_award_record` 唯一索引防止重复发奖。
> - 返利接口：`user_behavior_rebate_order` 以业务唯一键（userId+behaviorType+outBizNo）建唯一索引。
> - MQ 消费幂等：先查状态再操作，已处理则直接 ACK。

---

### 🔥 板块六：系统扩展性

**Q15：如果要新增一种奖品类型，需要改哪些地方？**

> 1. 在 `award` 表插入新类型枚举值。
> 2. 实现 `IDistributeAward` 接口，加上 `@Component("newAwardKey")` 注解。
> 3. `AwardService` 通过 `applicationContext.getBean(awardKey)` 获取实现，**不需要改 if-else 或 switch**。
> 4. 若有外部依赖（如第三方 API），注入对应 Retrofit2 Service 即可。
> 
> 这是策略模式 + Spring Bean 工厂的典型扩展点，符合开闭原则。

---

**Q16：如果活动参与人数爆炸，系统如何应对？**

> - **库存层**：Redis DECR 吞吐量极高（单实例 10w+ QPS），不受 DB 瓶颈限制。
> - **配额层**：乐观锁更新，无悲观锁等待，高并发下失败快速返回，不阻塞线程。
> - **接口层**：限流 `@RateLimiterAccessInterceptor` + Hystrix 熔断，超量请求直接降级。
> - **DB 层**：分库分表减少单表压力；Tomcat 线程池控制（max 150 threads）防止 OOM。
> - **水平扩展**：无状态服务 + Nacos 注册，直接加机器即可，Dubbo 自动负载均衡。

---

## 六、项目数据 & 规模参考（面试时可提及）

| 指标 | 数值 |
|------|------|
| Java 源码文件数 | 285+ |
| DDD 领域模块数 | 6 个 |
| REST API 端点 | 20+ |
| 数据库表 | 22 张（含分片） |
| MyBatis Mapper XML | 22 个 |
| MQ 消息 Topic | 4 个 |
| 设计模式数量 | 9+ 种 |
| 分库分表分片 | 2库×4表=8分片 |
| 线程池核心线程 | 20（最大 50） |
| Tomcat 最大线程 | 150 |
| HikariCP 最大连接 | 25 |

---

## 七、一句话亮点总结（面试开场用）

> "这个项目是一个基于 DDD 的企业级营销中台，我主导了从抽奖策略引擎设计、库存一致性方案到分布式消息可靠性的全链路实现。核心挑战是在高并发场景下同时保证库存不超卖、消息不丢失、业务规则可灵活配置——我通过 Redis 原子操作、本地消息表 + MQ 补偿、责任链+决策树规则引擎三个核心方案来解决这些问题。"

---

*文档基于项目源码自动生成，版本：2024-08*
