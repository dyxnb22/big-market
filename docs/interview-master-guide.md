# Big-Market 面试作战手册

> 目标：把已有 Copilot/Claude 分析去重、纠偏、压缩成一套能在面试中讲清楚、讲准确、讲出深度的版本。本文以当前源码为准。

## 1. 一分钟项目介绍

Big-Market 是一个大营销抽奖中台，核心业务包括活动配置、抽奖策略、奖品发放、行为返利、积分账户、运营查询和动态配置。项目采用 DDD 分层和多模块拆分，把业务规则放在 domain 层，通过 repository 接口隔离 Redis、MySQL、RabbitMQ、ES 等基础设施。

面试可以这样开场：

> 我做的是一个面向营销活动的抽奖中台。用户可以通过签到、积分兑换等方式获得抽奖次数，然后参与活动抽奖。系统的核心难点是高并发下的概率抽奖、库存防超卖、异步发奖和最终一致性。项目里用 Redis 预热概率表实现 O(1) 抽奖，用责任链和决策树把规则配置化，用本地 task 表加 MQ 做可靠事件投递，用 Redis 原子扣减加延迟队列和 XXL-Job 异步落库降低数据库压力。

简历写法建议：

> 基于 Java 8、Spring Boot 2.7、MyBatis、Redis、RabbitMQ、Dubbo、XXL-Job 和 DDD 架构实现的大营销抽奖中台。系统支持活动装配、概率抽奖、规则过滤、库存扣减、异步发奖、行为返利、积分账户和运营查询。核心亮点包括 Redis 概率表 O(1) 抽奖、责任链+决策树规则引擎、Outbox 本地消息表保证 MQ 投递最终一致性、Redis 库存预扣减与 Job 异步落库、2 个业务分片库乘 4 张分表的用户维度分片。

## 2. 架构分层怎么讲

项目模块：

| 模块 | 面试讲法 |
| --- | --- |
| `big-market-api` | 对外接口和 DTO，HTTP Controller 和 Dubbo 服务都实现这里的接口 |
| `big-market-trigger` | 触发层，包含 HTTP、Dubbo、RabbitMQ Listener、XXL-Job |
| `big-market-domain` | 领域层，承载核心业务规则：strategy、activity、award、credit、rebate、task、auth |
| `big-market-infrastructure` | 基础设施适配，Repository 实现、DAO、Redis、MQ、ES、外部接口 |
| `big-market-querys` | 查询侧，主要是 ES 订单查询 |
| `big-market-types` | 通用注解、枚举、异常、事件基类 |
| `big-market-app` | 启动入口、配置、AOP、数据源、线程池 |

关键表达：

> 这个项目没有单独 application/case 层，所以触发层 Controller 会编排多个领域服务。领域层只依赖 repository 接口，不关心 Redis、MySQL、MQ 的细节；基础设施层负责把领域对象和 PO、缓存、消息队列互相转换。

## 3. 核心业务链路

### 3.1 用户抽奖链路

入口：`RaffleActivityController#draw`

流程：

1. 限流和熔断：`@RateLimiterAccessInterceptor` + `@HystrixCommand`，动态降级开关来自 `@DCCValue("degradeSwitch:close")`。
2. 创建抽奖单：`raffleActivityPartakeService.createOrder(userId, activityId)`。
3. 活动参与校验：活动状态、活动时间、是否存在未使用抽奖单。
4. 扣减活动账户额度：总额度、月额度、日额度。
5. 生成 `user_raffle_order`，状态为 `create`。
6. 调用策略域抽奖：`raffleStrategy.performRaffle(...)`。
7. 保存中奖记录：`awardService.saveUserAwardRecord(...)`。
8. 在同一事务里写 `user_award_record`、`task`，并把抽奖单改为 `used`。
9. 事务提交后发布 `send_award` MQ，失败则由 task 表补偿 Job 重发。
10. `SendAwardCustomer` 消费消息，根据奖品 key 分发积分奖品或 OpenAI 额度奖品。

面试口径：

> 抽奖单和中奖记录不是随便插两张表，而是通过状态流转保证一次抽奖只能被使用一次。先创建 `user_raffle_order`，抽奖完成保存中奖记录时，会把中奖记录、消息任务、抽奖单 used 状态放到一个本地事务里。如果重复抽奖或重复发奖，会被唯一索引和状态更新条件挡住。

### 3.2 签到返利链路

入口：`calendarSignRebate`

流程：

1. 构建用户行为：`BehaviorTypeVO.SIGN`，外部业务号用当天日期。
2. 查 `daily_behavior_rebate` 配置。
3. 每条返利配置生成一条 `user_behavior_rebate_order` 和一条 task。
4. 事务后发布 `send_rebate` MQ。
5. `RebateMessageCustomer` 消费：
   - `sku`：给用户活动账户充值抽奖次数。
   - `integral`：给用户积分账户充值。

面试口径：

> 行为返利不是硬编码签到送什么，而是通过 `daily_behavior_rebate` 配置返利类型和返利值。订单表里有 `biz_id` 唯一键，格式类似 `userId_rebateType_outBusinessNo`，所以同一天重复签到会触发唯一索引幂等。

### 3.3 积分兑换抽奖次数链路

入口：`creditPayExchangeSku`

流程：

1. 用户选择 SKU，SKU 绑定活动和次数包。
2. 活动下单责任链校验活动状态和 SKU 库存。
3. 生成待支付订单 `raffle_activity_order`。
4. 调用积分域 `creditAdjustService.createOrder` 扣积分。
5. 积分账户、积分流水、task 在一个本地事务内提交。
6. 发布 `credit_adjust_success` MQ。
7. `CreditAdjustSuccessCustomer` 消费后把待支付活动订单更新为完成，并给活动账户加次数。

面试口径：

> 积分兑换走了两个领域：活动域先创建待支付订单，积分域扣减积分成功后发事件，活动域消费事件完成发货。这样积分和活动账户没有强耦合，但通过 outBusinessNo 串起来。

## 4. 抽奖策略怎么讲

### 4.1 策略装配

入口：`StrategyArmoryDispatch#assembleLotteryStrategy`

项目会把策略奖品和概率预热到 Redis。装配时先计算最小概率对应的概率范围 `rateRange`，再根据范围选择算法：

| 条件 | 算法 | 说明 |
| --- | --- | --- |
| `rateRange <= 10000` | `O1Algorithm` | 展开概率表，随机下标直接查 Redis |
| `rateRange > 10000` | `OLogNAlgorithm` | 存区间，运行时循环/二分/多线程搜索 |

注意纠偏：

> 之前文档里容易把 O(logN) 说成主要方案。源码实际是按 `rateRange <= 10000` 优先用 O(1)，超过阈值才用 OLogN。OLogN 的多线程发生在运行时查找表项数量大于 16 时，不是装配阶段多线程装配。

### 4.2 O(1) 抽奖算法

举例：三个奖品概率为 0.3、0.5、0.2，最小精度为 0.1，则 `rateRange = 10`。

装配后 Redis 里类似：

```text
rateRange = 10
rateTable = {
  0: 102,
  1: 101,
  2: 103,
  ...
}
```

运行时：

```java
int rateRange = repository.getRateRange(key);
int randomIndex = secureRandom.nextInt(rateRange);
return repository.getStrategyAwardAssemble(key, randomIndex);
```

面试口径：

> 它用空间换时间。传统抽奖每次要遍历概率区间，这里把概率提前展开成 Redis Hash，运行时只需要生成随机数并 HGET 一次，所以核心路径是 O(1)。缺点是概率精度越高，表越大，所以源码里用 `10000` 阈值切到区间算法。

### 4.3 责任链 + 决策树

责任链：抽奖前规则，线性执行，可短路。

| 节点 | 作用 |
| --- | --- |
| `rule_blacklist` | 黑名单用户直接返回固定奖品 |
| `rule_weight` | 按用户累计抽奖次数匹配权重奖池 |
| `rule_default` | 默认奖池随机抽奖 |

决策树：抽奖后规则，对默认抽到的奖品做过滤。

| 节点 | 作用 |
| --- | --- |
| `rule_stock` | 扣减策略奖品库存，成功后写延迟队列，后续 Job 异步落库 |
| `rule_lock` | 判断用户当天抽奖次数是否达到解锁次数 |
| `rule_luck_award` | 命中兜底奖品，常用于库存不足或未解锁场景 |

关键纠偏：

> 当前源码里，如果责任链返回的不是 `rule_default`，会直接返回结果，不再走决策树。也就是说黑名单和权重规则在当前实现里会跳过库存/次数锁过滤。面试时可以说这是当前版本的策略：前置规则具有更高优先级；如果面试官追问高价值权重奖品是否也要扣库存，可以主动补充“这是可优化点，可以把权重抽奖结果也统一进入决策树，或者给权重奖池单独配置库存规则”。

决策树的下一步不是写死在代码里，而是由 `rule_tree_node_line` 表配置。节点只返回 `TAKE_OVER` 或 `ALLOW`，下一节点由库表出边决定。

## 5. 库存防超卖怎么讲

项目里有两类库存，面试要分清楚：

| 库存 | 业务含义 | 扣减位置 | 落库方式 |
| --- | --- | --- | --- |
| 活动 SKU 库存 | 兑换抽奖次数的商品库存 | 活动下单责任链 | Redis 预扣减，延迟队列，`UpdateActivitySkuStockJob` 落库 |
| 策略奖品库存 | 抽中奖品的库存 | 决策树 `rule_stock` | Redis 预扣减，延迟队列，`UpdateAwardStockJob` 落库 |

库存扣减核心：

1. Redis `decr` 原子扣减。
2. 如果扣成负数，恢复为 0 并返回失败。
3. 用 `cacheKey_surplus` 做 `setNx` 库存锁，避免同一个库存槽位被重复消费。
4. 成功后写入 Redisson 延迟队列。
5. XXL-Job 异步消费队列，把数据库库存减一。

面试口径：

> Redis 是实时库存，MySQL 是最终持久化库存。真正防超卖靠 Redis 原子扣减和库存槽位锁，而不是靠数据库行锁硬扛流量。数据库更新异步做，降低高峰写压力。如果服务宕机，队列和 Job 负责补偿，库存最终一致。

## 6. MQ 和最终一致性怎么讲

项目使用类似 Outbox 的本地消息表方案，表名 `task`。

生产端通用模式：

1. 业务数据和 task 表在同一个本地事务提交。
2. 事务提交后发布 MQ。
3. 发布成功把 task 状态改为 complete。
4. 发布失败把 task 标记 fail。
5. `SendMessageTaskJob_DB1`、`SendMessageTaskJob_DB2` 扫描 task 表重发。

可以举三个例子：

| 场景 | 业务数据 | 事件 |
| --- | --- | --- |
| 抽奖后发奖 | `user_award_record` + `user_raffle_order.used` | `send_award` |
| 签到返利 | `user_behavior_rebate_order` | `send_rebate` |
| 积分扣减成功 | `user_credit_account` + `user_credit_order` | `credit_adjust_success` |

重要纠偏和优化点：

> Outbox 主要保障“生产端消息一定能投递出去”。但消费端也要配合重试和幂等。当前 `SendAwardCustomer` 捕获异常后没有重新抛出，RabbitMQ 可能认为消费成功，导致发奖失败后无法自动重试。这是面试里可以主动指出的优化点：消费失败应抛异常触发重试/DLX，或者引入消费侧 task/状态机补偿。

## 7. 分库分表怎么讲

配置在 `application-dev.yml`：

```yaml
mini-db-router:
  jdbc:
    datasource:
      dbCount: 2
      tbCount: 4
      default: db00
      routerKey: userId
      list: db01,db02
```

准确口径：

> 项目有一个公共库 `db00` 存放活动、策略、规则、奖品等偏配置数据；用户相关高频写表分布在两个业务库 `db01/db02`，每个库 4 张分表，比如 `user_raffle_order_000` 到 `_003`、`user_award_record_000` 到 `_003`。路由键是 `userId`，这样同一个用户的订单、账户、发奖记录尽量落到同一分片，方便本地事务。

不要说得太绝对：

> 可以说“通过 db-router 中间件按 userId 路由到 2 个库和 4 张表”，不要强行背具体取模公式，除非你能把中间件源码也展开讲清楚。

## 8. 限流、熔断、动态配置怎么讲

限流：

> `RateLimiterAOP` 拦截 `@RateLimiterAccessInterceptor`，用 Guava RateLimiter 按注解里的 key 限频。当前抽奖接口按 `userId` 每秒 1 次，超过后调用 fallback。它还用本地 Guava Cache 做 24 小时黑名单，但这个黑名单不是分布式的，生产可以改成 Redis。

熔断：

> 抽奖接口使用 Hystrix，超时时间 150ms，超时后走 `drawHystrixError`。这是接口级保护，防止下游慢调用拖垮 Tomcat 线程。

DCC：

> `@DCCValue` 配合 `DCCValueBeanFactory` 从 Zookeeper `/big-market-dcc/config` 下读取配置，并监听节点变化热更新字段。项目里用它控制 `degradeSwitch` 和 `rateLimiterSwitch`。配置里 `zookeeper.sdk.config.enable=false` 时可以关闭这套能力。

## 9. 各领域职责速记

| 领域 | 记忆句 |
| --- | --- |
| strategy | 管概率、规则、奖品库存，是抽奖核心 |
| activity | 管活动参与、次数账户、SKU 库存、活动订单 |
| award | 管中奖记录、发奖事件、奖品分发策略 |
| rebate | 管签到等行为返利，生成返利订单和返利事件 |
| credit | 管积分账户、积分流水、积分变动成功事件 |
| task | 管本地消息表和补偿重发 |
| auth | 管 token 生成和校验 |

## 10. 面试高频问答

### Q1：为什么用 DDD？

答：

> 因为营销系统规则变化很快，抽奖、活动、积分、返利、发奖都有各自的业务不变量。如果放在传统 MVC Service 里，会互相调用、越写越乱。DDD 让每个领域维护自己的聚合和规则，跨领域通过事件或接口协作。比如抽奖策略不关心中奖记录怎么落库，发奖域也不关心抽奖概率怎么计算。

补一句源码落地：

> domain 定义 repository 接口，infrastructure 实现接口并适配 Redis/MySQL/MQ，这样领域层不依赖基础设施。

### Q2：O(1) 抽奖会不会内存很大？

答：

> 会，所以项目按概率精度做了阈值控制。`rateRange <= 10000` 时用 O(1) 展开表，超过阈值就用 OLogN 区间算法。O(1) 适合奖品数量不多、概率精度可控的营销抽奖；如果概率特别细，比如百万分之一，直接展开会浪费内存，就应该用区间或 Alias Method。

### Q3：库存怎么防超卖？

答：

> 第一层靠 Redis `decr` 原子扣减，扣成负数立即回滚到 0 并失败；第二层用 `cacheKey_surplus` 做 `setNx` 库存槽位锁，防止同一个库存被重复消费；第三层通过延迟队列和 Job 异步落库。MySQL 不是实时拦截入口，而是最终一致的持久化视图。

### Q4：MQ 如何保证可靠？

答：

> 生产端用 task 本地消息表。业务数据和 task 同事务提交，提交后发 MQ；发失败标记 fail，定时任务扫描重发。消费端用唯一索引和状态机做幂等。需要注意当前发奖消费者吞异常，这是可靠消费的一个优化点，应该抛出异常触发 MQ 重试或引入消费侧补偿。

### Q5：责任链和决策树为什么都要用？

答：

> 两者解决的问题不同。责任链适合抽奖前的线性过滤，比如黑名单、权重奖池、默认抽奖，可以提前短路。决策树适合抽奖后的条件分支，比如库存成功走次数锁，库存不足走兜底奖品，分支由数据库配置。这样简单规则线性化，复杂规则配置化。

### Q6：项目的幂等点有哪些？

答：

> 抽奖单 `order_id` 唯一，中奖记录 `order_id` 唯一，task `message_id` 唯一，返利订单 `biz_id` 唯一，积分订单 `out_business_no` 唯一。除此之外，更新抽奖单状态时要求从 create 更新到 used，重复更新会失败。

### Q7：分库分表为什么用 userId？

答：

> 用户维度是最主要的读写路径，比如用户抽奖单、活动账户、中奖记录、积分流水都按 userId 查询和更新。用 userId 路由可以让同一用户的数据尽量落在同一分片，减少跨库事务。活动、策略、规则这类配置数据放公共库，不参与用户维度分片。

### Q8：如果让你优化这个项目，你会做什么？

建议答这几个，显得你真的读过代码：

1. 发奖消费者失败不能吞异常，应接入 MQ 重试、死信队列或消费侧补偿表。
2. 限流黑名单当前是本地 Guava Cache，多实例不共享，生产可改 Redis。
3. 权重规则当前跳过决策树，高价值奖池可以统一进入库存和次数锁校验。
4. O(1) 概率表可引入 Alias Method，兼顾 O(1) 查询和更小内存。
5. task 补偿目前按 DB1/DB2 扫描固定表键，分表扩展时要让补偿任务按分片枚举。
6. OpenAI 发奖只调用外部接口，没有像积分奖品一样更新中奖记录完成态，可补齐状态一致性。

## 11. 旧文档去重与纠错清单

这些点面试时按本文口径讲：

| 旧说法 | 更准确说法 |
| --- | --- |
| “2库4表 = 8 个逻辑分片” | 业务分片是 db01/db02，每库 4 张分表；还有 db00 公共库 |
| “OLogN 多线程装配” | OLogN 装配是区间表；运行时根据表大小选择循环、二分或多线程搜索 |
| “责任链后都走决策树” | 当前只有 `rule_default` 结果继续走决策树，黑名单/权重直接返回 |
| “库存只有一套” | 活动 SKU 库存和策略奖品库存是两套 |
| “MQ 完全可靠” | 生产端有 Outbox 补偿；消费端仍要靠重试和幂等，发奖消费者吞异常是优化点 |
| “所有 Controller 都是 Dubbo” | 主要 HTTP Controller 标了 `@DubboService`，另外 `RebateServiceRPC` 是独立 RPC 实现 |

## 12. 面试前背诵版

最应该背熟的 5 段：

1. 项目介绍：DDD 营销抽奖中台，解决高并发抽奖、库存、发奖一致性。
2. 抽奖算法：Redis 预热概率表，O(1) 查表，超过阈值切 OLogN。
3. 规则引擎：责任链管抽奖前短路，决策树管抽奖后库存/次数/兜底。
4. 一致性：业务表+task 本地事务，事务后发 MQ，Job 补偿重发，消费端幂等。
5. 库存：Redis 原子预扣减 + 库存槽位锁 + 延迟队列 + XXL-Job 异步落库。

最后的高级表达：

> 我不会把这个项目讲成“完美系统”。它的核心设计是完整的，但也有教学项目常见的可优化点，比如消费端可靠性、分布式限流状态、权重规则是否统一走后置库存过滤。面试时我会先讲清楚当前实现，再给出生产级优化方案。
