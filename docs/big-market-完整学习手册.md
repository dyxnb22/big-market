# Big-Market 大营销系统 — 完整学习与面试手册

> **整合来源：** INTERVIEW_GUIDE + PROJECT_GUIDE + LEARNING_NOTES + interview-prep + learning-summary + db-analysis + 01-业务流程解析(7篇) + 02-URL走读解析(4篇)
>
> **用途：** 系统化学习项目 + 面试准备一站式参考

---

## 目录

1. [项目概览](#1-项目概览)
2. [架构设计](#2-架构设计)
3. [模块详解](#3-模块详解)
4. [数据库设计](#4-数据库设计)
5. [API 接口参考](#5-api-接口参考)
6. [核心业务流程](#6-核心业务流程)
7. [关键技术设计](#7-关键技术设计)
8. [横切关注点](#8-横切关注点)
9. [运维与部署](#9-运维与部署)
10. [面试深挖问答（25题）](#10-面试深挖问答25题)
11. [改进建议与风险](#11-改进建议与风险)
12. [快速索引](#12-快速索引)

---

## 1. 项目概览

### 1.1 项目定位

Big-Market 是一个基于 **DDD（领域驱动设计）** 的企业级营销抽奖中台，集成了抽奖活动管理、奖品发放、行为返利、积分账户、策略配置及用户认证等核心业务域，支持高并发场景下的实时库存扣减、异步消息驱动发奖和分布式分库分表。

| 项目信息 | 详情 |
|---------|------|
| GroupId/ArtifactId | `cn.bugstack / big-market` (v1.1) |
| 父框架 | Spring Boot 2.7.12 |
| Java 版本 | 1.8 |
| 作者 | xiaofuge (GitHub: fuzhengwei) |
| 源码文件数 | 285+ |
| REST API 端点 | 20+ |
| 数据库表 | 22 张（含分片） |
| DDD 领域数 | 7 个 |
| MQ Topic 数 | 4 个 |
| 设计模式 | 9+ 种 |
| 分库分表 | 2库 × 4表 = 8 分片 |

### 1.2 技术栈一览

| 分类 | 技术 | 版本 | 用途 |
|------|------|------|------|
| 主框架 | Spring Boot | 2.7.12 | IoC / MVC / AOP |
| ORM | MyBatis | 2.1.4 | 持久层 |
| RPC | Dubbo + Nacos | 3.0.9 / 2.1.0 | 微服务调用与注册 |
| 缓存/锁 | Redisson (Redis) | 3.26.0 | 高速缓存、分布式锁、延迟队列 |
| 消息队列 | RabbitMQ (AMQP) | 3.2.0 | 异步解耦与最终一致性 |
| 定时任务 | XXL-Job | 2.4.1 | 分布式调度 |
| 分库分表 | db-router-starter | 1.0.4（自研） | 路由键分片 |
| 动态配置 | ZooKeeper + Curator | 3.1.4 | DCC 热更新 |
| 熔断 | Hystrix | 1.5.18 | 服务熔断降级 |
| 限流 | Guava RateLimiter | — | 令牌桶接口限流 |
| 搜索 | Elasticsearch | 7.17.14 | CQRS 查询端 |
| 数据同步 | Canal + Logstash | — | MySQL → ES 同步 |
| 外部调用 | Retrofit2 | 2.9.0 | OpenAI 等 HTTP 调用 |
| 监控 | Prometheus + Grafana | — | 指标采集与可视化 |
| 认证 | JWT (auth0 + jjwt) | 4.4.0 / 0.9.1 | 用户 Token |

### 1.3 简历描述（可直接使用）

**完整版：**
> 基于 DDD 领域驱动设计，采用 Java 8 + Spring Boot 2.7 + MyBatis 构建的企业级营销中台。涵盖抽奖活动管理、奖品发放、行为返利、积分账户、策略配置及用户认证等核心业务。引入**责任链 + 决策树**双层规则引擎灵活编排抽奖逻辑；基于 **Redis 原子操作**实现毫秒级库存扣减，RabbitMQ + 本地消息表（Outbox）保障最终一致性；使用 **Dubbo + Nacos** 提供 RPC 服务，**XXL-Job** 管理分布式定时任务；MySQL **2库4表分库分表**（路由键：userId）；接入 Zookeeper DCC 动态配置、Hystrix 熔断降级和自定义 AOP 限流。

**精简版（约 150 字）：**
> 基于 Java 8 + Spring Boot + DDD 开发的高并发营销中台，涵盖抽奖、返利、积分等核心业务域。引入责任链+决策树双层规则引擎解耦抽奖流程；Redis 毫秒级库存扣减 + RabbitMQ 异步发奖保障高并发一致性；Dubbo+Nacos 提供微服务 RPC；MySQL 分库分表（2库4表）、动态配置降级（Zookeeper DCC）、Hystrix 熔断等工程措施均已落地。

### 1.4 一句话亮点（面试开场）

> "这个项目是一个基于 DDD 的企业级营销中台，核心挑战是在高并发场景下同时保证库存不超卖、消息不丢失、业务规则可灵活配置——通过 Redis 原子操作、本地消息表 + MQ 补偿、责任链+决策树规则引擎三个核心方案来解决问题。"

---

## 2. 架构设计

### 2.1 分层架构

```
┌─────────────────────────────────────────────┐
│       big-market-trigger（触发器层）          │
│  HTTP Controller / MQ Listener / XXL-Job / RPC │
├─────────────────────────────────────────────┤
│       big-market-domain（领域层）              │
│  strategy / activity / award / credit /      │
│  rebate / task / auth                        │
├─────────────────────────────────────────────┤
│    big-market-infrastructure（基础设施层）     │
│  Repository实现 / DAO / Redis / MQ / ES /    │
│  Retrofit2                                    │
├─────────────────────────────────────────────┤
│  big-market-types    │  big-market-api       │
│  (公共类型/注解/枚举)  │  (接口定义/DTO)        │
├─────────────────────────────────────────────┤
│  big-market-querys   │  big-market-app       │
│  (CQRS 查询侧/ES)    │  (Spring Boot 启动)    │
└─────────────────────────────────────────────┘
```

**依赖方向：** `app → trigger → domain → types`，`trigger → api`，`infrastructure → domain`，`trigger → querys`

### 2.2 Maven 模块与职责

| 模块 | 关键路径 | 核心职责 |
|------|----------|----------|
| **types** | `cn.bugstack.types` | 全局常量(`Constants`)、响应码枚举(`ResponseCode`)、自定义注解(`@DCCValue`/`@RateLimiterAccessInterceptor`)、事件基类(`BaseEvent`)、异常(`AppException`) |
| **api** | `cn.bugstack.trigger.api` | Dubbo 服务接口定义(`IRaffleStrategyService`等5个)、DTO、统一请求/响应包装(`Request<T>`/`Response<T>`) |
| **domain** | `cn.bugstack.domain.*` | 7 个子域的核心业务逻辑，零基础设施依赖，通过 Repository 接口隔离技术细节 |
| **infrastructure** | `cn.bugstack.infrastructure` | 实现 domain 定义的 Repository 接口，包含 MyBatis DAO(22个)、Redisson Redis、RabbitMQ EventPublisher、ES 查询 |
| **trigger** | `cn.bugstack.trigger` | 4 个 HTTP Controller、4 个 MQ Consumer、3 个 XXL-Job、1 个 Dubbo RPC 实现 |
| **querys** | `cn.bugstack.querys` | CQRS 读侧：`IESUserRaffleOrderRepository` 封装 ES 查询接口 |
| **app** | `cn.bugstack` | Spring Boot 启动入口 `Application.java`、AOP 限流切面、14 个配置类 |

### 2.3 领域层子包结构（以 strategy 为例）

```
domain/strategy/
├── model/
│   ├── entity/         ← RaffleFactorEntity, StrategyAwardEntity, RaffleAwardEntity...
│   ├── valobj/         ← RuleWeightVO, RuleTreeNodeVO, StrategyAwardStockKeyVO...
│   └── aggregate/      ← 聚合根
├── adapter/
│   ├── event/          ← 领域事件（MQ 消息定义）
│   ├── repository/     ← IStrategyRepository 接口
│   └── port/           ← 外部服务端口接口
└── service/
    ├── armory/         ← IStrategyArmory → StrategyArmoryDispatch（装配+算法 O1/OLogN）
    ├── raffle/         ← IRaffleStrategy → DefaultRaffleStrategy（执行抽奖）
    └── rule/
        ├── chain/      ← 责任链：BlackList/Weight/Default + DefaultChainFactory
        └── tree/       ← 决策树：Lock/Stock/LuckAward + DefaultTreeFactory + DecisionTreeEngine
```

### 2.4 七大领域划分

| 领域 | 包路径 | 核心职责 |
|------|--------|---------|
| **strategy** | `domain.strategy` | 抽奖策略装配与执行：O(1)/O(logN) 算法、责任链规则过滤、决策树后置处理 |
| **activity** | `domain.activity` | 活动参与管理：创建抽奖单、SKU 库存管理、日/月/总三级配额、活动上架/下架 |
| **award** | `domain.award` | 奖品记录保存与分发：策略模式路由到不同奖品实现（积分/OpenAI/...） |
| **credit** | `domain.credit` | 用户积分账户：正向/逆向交易、余额管理、流水记录 |
| **rebate** | `domain.rebate` | 行为返利：签到等行为触发积分或 SKU 次数奖励 |
| **task** | `domain.task` | Outbox 模式：Task 表扫描与 MQ 消息补偿 |
| **auth** | `domain.auth` | JWT Token 验证与 OpenId 解析 |

### 2.5 仓储模式落地

领域层只定义接口，基础设施层提供实现。领域层完全不感知 Redis、MyBatis 等技术：

```
domain/strategy/adapter/repository/IStrategyRepository.java    ← 接口（领域层）
infrastructure/adapter/repository/StrategyRepository.java      ← 实现（基础设施层）
```

两层转换：`PO (持久化对象) → Entity (领域实体)`，转换在 Repository 实现类中完成（手动 set 或 BeanUtils）。

### 2.6 设计模式汇总

| 模式 | 落地场景 |
|------|---------|
| **策略模式** | `IDistributeAward`（积分/OpenAI/自定义奖品）、`ITradePolicy`（积分支付/免支付） |
| **工厂模式** | `DefaultChainFactory` 组装责任链、`DefaultTreeFactory` 构建决策树 |
| **模板方法** | `AbstractRaffleStrategy`：定义抽奖标准流程，子类实现细节 |
| **责任链** | 前置规则过滤（黑名单 → 权重 → 默认） |
| **决策树** | 后置奖品路由（库存 → 次数锁 → 兜底） |
| **仓储模式** | Repository 接口隔离数据访问 |
| **观察者/事件驱动** | 领域事件 + RabbitMQ 异步处理 |
| **适配器模式** | Repository 实现适配 Domain 接口 |
| **聚合模式** | `CreatePartakeOrderAggregate`、`CreateQuotaOrderAggregate` |

---

## 3. 模块详解

### 3.1 big-market-types（公共类型层）

```
big-market-types/src/main/java/cn/bugstack/types/
├── annotations/
│   ├── DCCValue.java                  ← 动态配置中心注解（绑定 Zookeeper key:defaultValue）
│   └── RateLimiterAccessInterceptor.java ← 限流注解（permitsPerSecond/blacklistCount/fallbackMethod）
├── common/Constants.java              ← 全局常量（分隔符 + RedisKey 内部类统一定义所有缓存 key 前缀）
├── enums/ResponseCode.java            ← 统一响应码枚举（系统级 0001~0008 + 业务级 ERR_*）
├── event/BaseEvent.java               ← MQ 事件基类，泛型 EventMessage<T>（id/timestamp/data）
└── exception/AppException.java        ← 自定义业务异常（code + info）
```

**设计亮点：**
- `@DCCValue`：标注在 Bean 字段上，`DCCValueBeanFactory` 自动从 Zookeeper 读取值并注入，支持监听节点变化热更新
- `@RateLimiterAccessInterceptor`：AOP 切面拦截，基于 Guava RateLimiter，按 userId 独立限速，超频自动加黑名单

### 3.2 big-market-api（接口定义层）

定义 5 个对外接口及 DTO：

| 接口 | 主要方法 | 说明 |
|------|----------|------|
| `IRaffleActivityService` | `armory`, `draw`, `calendarSignRebate`, `queryUserActivityAccount`, `creditPayExchangeSku` | 活动抽奖全流程 |
| `IRaffleStrategyService` | `strategyArmory`, `randomRaffle`, `queryRaffleAwardList`, `queryRaffleStrategyRuleWeight` | 策略装配与抽奖 |
| `IRebateService` | `rebate` | 返利服务 Dubbo RPC |
| `IDCCService` | `updateConfig` | 动态配置修改 |
| `IErpOperateService` | `queryUserRaffleOrder`, `queryStageActivityList`, `updateStageActivity2Active` | 运营后台 |

**统一响应格式：**
```json
{ "code": "0000", "info": "调用成功", "data": { ... } }
```

### 3.3 big-market-domain（领域层）

#### 3.3.1 策略域（strategy）— 抽奖核心引擎

**核心入口：** `AbstractRaffleStrategy#performRaffle(RaffleFactorEntity)` → `DefaultRaffleStrategy`

**流程（模板方法模式）：**
```
performRaffle(raffleFactorEntity)
  Step 1: 参数校验（userId、strategyId 非空）
  Step 2: 责任链抽奖 raffleLogicChain(userId, strategyId)
          ├── BlackListLogicChain  → 黑名单直接返回固定奖品（如 102 号奖品）
          ├── RuleWeightLogicChain → 按权重区间抽奖（查用户累计次数→匹配分段→权重池随机）
          └── DefaultLogicChain   → 默认随机抽奖（查 Redis 概率表，O(1) 命中）
  Step 3: 如果责任链命中非默认逻辑（ruleModel != default），直接返回
  Step 4: 决策树过滤 raffleLogicTree(userId, strategyId, awardId, endDateTime)
          ├── RuleLockLogicTreeNode  → 次数锁（累计抽奖次数 >= N 才解锁该奖品）
          ├── RuleStockLogicTreeNode → Redis DECR 原子扣减库存，写入延迟队列
          └── RuleLuckAwardLogicTreeNode → 兜底奖品（库存不足或未解锁时替换）
  Step 5: 返回最终奖品实体 RaffleAwardEntity
```

**抽奖算法选择：**
- `O1Algorithm`：HashMap 查找表（概率区间 ≤ 10000 时使用），O(1) 时间复杂度
- `OLogNAlgorithm`：有序区间 + 二分查找，O(logN) 时间复杂度，节省内存

**算法切换逻辑（StrategyArmoryDispatch）：**
```java
if (rateRange <= 10000) algorithm = O1;  // 空间换时间
else algorithm = OLogN;                   // 二分查找节省内存
```

**责任链接口设计：**
```java
public interface ILogicChain extends ILogicChainArmory {
    StrategyAwardVO logic(String userId, Long strategyId);  // 执行逻辑
    ILogicChain next();                                      // 获取下一节点
    ILogicChain appendNext(ILogicChain next);                // 设置下一节点
}
```

**三个链节点：**

| 节点 | Bean 名称 | 规则值示例 | 行为 |
|------|-----------|-----------|------|
| `BlackListLogicChain` | `rule_blacklist` | `102:user001,user002` | 命中则直接返回 102 号奖品（兜底积分） |
| `RuleWeightLogicChain` | `rule_weight` | `4000:102,103,104 5000:102,103,104,105,106` | 按积分分段匹配独立权重池 |
| `DefaultLogicChain` | `rule_default` | — | 全量概率表 O(1) 随机 |

**三个树节点：**

| 节点 | Bean 名称 | 规则值 | 逻辑 |
|------|-----------|--------|------|
| `RuleLockLogicTreeNode` | `rule_lock` | `5`（需抽5次解锁） | 未达标→TAKE_OVER→兜底奖品 |
| `RuleStockLogicTreeNode` | `rule_stock` | — | Redis DECR→成功TAKE_OVER / 失败ALLOW |
| `RuleLuckAwardLogicTreeNode` | `rule_luck_award` | `106:0.01,1` | 兜底发放积分奖品 |

**树的遍历引擎（DecisionTreeEngine）：**
从 `treeRootRuleNode` 开始，执行节点 `logic()` → 获取 `RuleLogicCheckTypeVO`（TAKE_OVER/ALLOW）→ 查找对应出边 → 跳转到下一节点 → 节点为 null 时结束。

**典型决策树流程：**
```
用户抽中稀有奖品
  → rule_stock: 有库存? 
    ├─ TAKE_OVER → rule_lock: 抽够5次?
    │    ├─ TAKE_OVER (未解锁) → rule_luck_award (发兜底积分)
    │    └─ ALLOW (已解锁) → 发稀有奖品
    └─ ALLOW (无库存) → END (不发奖/走兜底)
```

#### 3.3.2 活动域（activity）

**服务与职责：**

| 接口 | 实现类 | 功能 |
|------|--------|------|
| `IActivityArmory` | `ActivityArmory` | 活动 SKU 数据预热到 Redis |
| `IRaffleActivityPartakeService` | `RaffleActivityPartakeService` | 创建抽奖参与单 |
| `IRaffleActivityAccountQuotaService` | `RaffleActivityAccountQuotaService` | 账户额度管理（充值/扣减） |
| `IRaffleActivitySkuProductService` | `RaffleActivitySkuProductService` | SKU 商品列表查询 |
| `IRaffleActivityStageService` | `RaffleActivityStageService` | 上架活动查询（按渠道/来源路由） |

**创建抽奖单流程：**
```
createOrder(partakeRaffleActivityEntity)
  Step 1: 查询活动信息（Redis 缓存 → MySQL 兜底），校验活动状态（必须 open）及时间范围
  Step 2: 查询已有未使用的抽奖单（幂等，避免重复创建同一活动订单）
  Step 3: 扣减账户额度（总/月/日三级）
  Step 4: 构建 UserRaffleOrderEntity
  Step 5: 组装 CreatePartakeOrderAggregate → repository 事务保存（user_raffle_order + 更新三级账户）
  Step 6: 返回抽奖单
```

**活动充值下单流程：**
```
createOrder(skuRechargeEntity)
  Step 1: 查询 SKU / 活动 / 次数配置
  Step 2: 查询未支付订单（积分支付类型需要幂等）
  Step 3: 账户额度/积分余额校验
  Step 4: ActionChain 校验（ActivityBaseActionChain → ActivitySkuStockActionChain 扣减 SKU 库存）
  Step 5: 构建订单聚合 CreateQuotaOrderAggregate
  Step 6: 交易策略路由（ITradePolicy）
          ├── CreditPayTradePolicy → 积分支付，扣减积分
          └── RebateNoPayTradePolicy → 返利免支付，直接充值
  Step 7: 返回未支付订单信息
```

**聚合根设计（CreatePartakeOrderAggregate）：**
包含 `ActivityAccountEntity`（总账户）、`ActivityAccountMonthEntity`（月账户）、`ActivityAccountDayEntity`（日账户）、`UserRaffleOrderEntity`（参与订单）。聚合根对外提供统一业务方法，数据库写入在一个事务内完成。

**活动 Action 责任链：**

| 节点 | 说明 |
|------|------|
| `ActivityBaseActionChain` | 校验活动状态、日期、库存 |
| `ActivitySkuStockActionChain` | 扣减 Redis SKU 库存（DECR），库存耗尽发 MQ 下架 |

**交易类型：**

| 类型 | 枚举值 | 说明 |
|------|--------|------|
| 积分支付 | `credit_pay_trade` | 用户消费积分购买抽奖次数 |
| 返利免支付 | `rebate_no_pay_trade` | 返利直接充值次数 |

#### 3.3.3 奖品域（award）

**服务：** `AwardService`

**保存中奖记录：**
```
saveUserAwardRecord(UserAwardRecordEntity)
  → 构建 SendAwardMessage（MQ 消息体）
  → 构建 TaskEntity（MQ 任务记录，state=create）
  → 组装 UserAwardRecordAggregate
  → 事务保存（user_award_record + task 记录）
```

**奖品分发（策略模式）：**
```
distributeAward(DistributeAwardEntity)
  → 查询奖品 awardKey → 如 "user_credit_random"、"openai_account"
  → applicationContext.getBean(awardKey) 获取 IDistributeAward 实现
  → distributeAward.giveOutPrizes(entity)
```

| 实现类 | Bean Key | 功能 |
|--------|----------|------|
| `UserCreditRandomAward` | `user_credit_random` | 随机发放积分（最小值~最大值间随机）→ `CreditAdjustService.createOrder(FORWARD)` |
| `OpenAIAccountAdjustQuotaAward` | `openai_account` | Retrofit2 调用外部 OpenAI 账户充值 API |

**扩展方式：** 新增奖品类型只需在 `award` 表插入记录 + 实现 `IDistributeAward` + `@Component("newKey")` 注解，不需改任何 if-else。

#### 3.3.4 积分域（credit）

**服务：** `CreditAdjustService`

```
createOrder(TradeEntity)
  Step 0: 逆向交易（扣积分）时先查询账户余额是否充足
  Step 1: 构建 CreditAccountEntity（增减积分）
  Step 2: 构建 CreditOrderEntity（流水订单）
  Step 3: 构建 MQ 事件消息（CreditAdjustSuccessMessageEvent）
  Step 4: 构建 TaskEntity（task 表记录）
  Step 5: 组装 TradeAggregate
  Step 6: 事务保存（user_credit_account + user_credit_order + task）
```

**交易类型：**

| 类型 | 枚举值 | 说明 |
|------|--------|------|
| 正向 | `FORWARD` | 增加积分（返利奖励、抽奖奖励） |
| 逆向 | `REVERSE` | 扣减积分（消费兑换商品） |

**交易名称：**

| 名称 | 枚举值 | 说明 |
|------|--------|------|
| 行为返利 | `REBATE` | 签到等行为增加积分 |
| 消费 | `CONSUME` | 积分兑换次数 |
| 抽奖奖励 | `AWARD` | 抽奖获得积分 |

#### 3.3.5 返利域（rebate）

**服务：** `BehaviorRebateService`

```
createOrder(BehaviorEntity)
  Step 1: 查询返利配置（DailyBehaviorRebateVO），获取 rebateType 和 rebateConfig
  Step 2: 构建返利订单 BehaviorRebateOrderEntity（bizId = userId + behaviorType + outBizNo 幂等）
  Step 3: 构建 SendRebateMessageEvent（MQ 消息体）
  Step 4: 构建 TaskEntity
  Step 5: 事务保存（user_behavior_rebate_order + task）
```

**返利类型：**
- `sku`：直接充值 SKU 抽奖次数
- `integral`：增加积分

**行为类型：** `SIGN`（签到）、`OPEN_ACTIVITY`（参与活动）

#### 3.3.6 任务域（task）— Outbox 模式

**服务：** `TaskService`

```
queryNoSendMessageTaskList() → 扫描 state=create/fail 的 task
sendMessage(taskEntity)       → 调用 EventPublisher 发布 MQ
updateTaskSendMessageCompleted → state=completed
updateTaskSendMessageFail      → state=fail
```

#### 3.3.7 鉴权域（auth）

**服务：** `AuthService`，基于 JWT 的 Token 校验与 OpenId 解析：
- `checkToken(token)` → `AbstractAuthService#isVerify` → HMAC256 验签
- `openid(token)` → `AbstractAuthService#decode` → 解析 Claims.openId
- Token 由外部（如微信登录服务）生成后传入，本系统只做校验
- **安全提醒：** 密钥硬编码在 `AbstractAuthService` 静态字段中，生产环境必须替换为环境变量或配置中心注入

### 3.4 big-market-infrastructure（基础设施层）

**目录结构：**
```
infrastructure/
├── adapter/
│   ├── repository/         ← 7 个 Repository 实现类
│   │   ├── StrategyRepository.java    ← 策略仓储（Redis 缓存+DB兜底）
│   │   ├── ActivityRepository.java    ← 活动仓储（DB路由+编程式事务）
│   │   ├── AwardRepository.java       ← 奖品仓储
│   │   ├── BehaviorRebateRepository.java
│   │   ├── CreditRepository.java
│   │   ├── TaskRepository.java
│   │   └── ESUserRaffleOrderRepository.java ← ES 查询仓储
│   └── port/
│       └── AwardPort.java             ← 外部 OpenAI API 调用
├── dao/                   ← 22 个 MyBatis DAO 接口 + PO 类
├── elasticsearch/
│   └── IElasticSearchUserRaffleOrderDao.java
├── event/EventPublisher.java          ← RabbitMQ 消息发布
├── gateway/IOpenAIAccountService.java ← Retrofit2 HTTP 调用接口
└── redis/
    ├── IRedisService.java             ← Redis 操作接口
    └── RedissonService.java           ← Redisson 实现（AtomicLong/BlockingQueue/DelayedQueue/Lock）
```

**22 个 DAO 清单：**

| DAO 接口 | 对应 PO | 说明 |
|----------|---------|------|
| `IStrategyDao` | `Strategy` | 策略查询 |
| `IStrategyAwardDao` | `StrategyAward` | 策略奖品 CRUD |
| `IStrategyRuleDao` | `StrategyRule` | 策略规则查询 |
| `IRaffleActivityDao` | `RaffleActivity` | 活动基础信息 |
| `IRaffleActivitySkuDao` | `RaffleActivitySku` | SKU 库存查询与扣减 |
| `IRaffleActivityStageDao` | `RaffleActivityStage` | 活动上架/下架 |
| `IRaffleActivityAccountDao` | `RaffleActivityAccount` | 用户总账户 |
| `IRaffleActivityAccountDayDao` | `RaffleActivityAccountDay` | 日账户 |
| `IRaffleActivityAccountMonthDao` | `RaffleActivityAccountMonth` | 月账户 |
| `IRaffleActivityCountDao` | `RaffleActivityCount` | 活动次数配置 |
| `IRaffleActivityOrderDao` | `RaffleActivityOrder` | 充值订单 |
| `IUserRaffleOrderDao` | `UserRaffleOrder` | 抽奖单（分片） |
| `IAwardDao` | `Award` | 奖品基础信息 |
| `IUserAwardRecordDao` | `UserAwardRecord` | 中奖记录（分片） |
| `IUserCreditAccountDao` | `UserCreditAccount` | 积分账户 |
| `IUserCreditOrderDao` | `UserCreditOrder` | 积分流水（分片） |
| `IUserBehaviorRebateOrderDao` | `UserBehaviorRebateOrder` | 返利订单（分片） |
| `IDailyBehaviorRebateDao` | `DailyBehaviorRebate` | 返利配置 |
| `IRuleTreeDao` / `IRuleTreeNodeDao` / `IRuleTreeNodeLineDao` | 规则树 PO | 决策树结构 |
| `ITaskDao` | `Task` | Outbox 消息任务 |

**Redis 缓存 Key 汇总：**

| Key 模式 | 结构 | 用途 |
|----------|------|------|
| `strategy_rate_table_{strategyId}` | Hash | O(1) 概率查找表 |
| `strategy_rate_range_{strategyId}` | String | 概率范围上限 |
| `strategy_award_stock_{strategyId}_{awardId}` | AtomicLong | 奖品库存 |
| `activity_sku_stock_{sku}` | AtomicLong | SKU 库存 |
| `strategy_award_list_{strategyId}` | — | 策略奖品列表 |
| `raffle_activity_account_quota_{userId}_{activityId}` | — | 用户账户额度 |
| `user_raffle_count_{userId}_{strategyId}` | — | 用户抽奖次数（次数锁） |

### 3.5 big-market-trigger（触发器层）

#### HTTP Controller（4 个）

**RaffleActivityController** — `/api/v1/raffle/activity/`（核心入口）

| 方法 | URL | 说明 | 防护措施 |
|------|-----|------|----------|
| GET | `query_stage_activity_id` | 按渠道/来源查询活动ID | — |
| GET | `armory` | 活动+策略数据预热 | — |
| POST | `draw` | **执行抽奖（主链路）** | 限流 + Hystrix + DCC降级 |
| POST | `draw_by_token` | Token 鉴权版本的抽奖 | 限流 + Hystrix + DCC降级 |
| POST | `calendar_sign_rebate` | 日历签到返利 | 限流 |
| POST | `is_calendar_sign_rebate` | 查询今日是否已签到 | — |
| POST | `query_user_activity_account` | 查询活动账户额度 | — |
| GET | `query_sku_product_list_by_activity_id` | 查询 SKU 商品列表 | — |
| POST | `credit_pay_exchange_sku` | 积分兑换 SKU | 限流 |
| GET | `query_user_credit_account` | 查询积分账户 | — |

**`draw` 接口完整流程（核心）：**
```
1. 限流校验（@RateLimiterAccessInterceptor，Guava RateLimiter + 黑名单）
2. 降级开关检查（@DCCValue("degradeSwitch") + @HystrixCommand 熔断）
3. 参数校验
4. 创建抽奖单：raffleActivityPartakeService.createOrder
   → 检查活动状态/日期 → 扣减账户额度（总/月/日三级）→ 保存抽奖单
5. 执行抽奖：raffleStrategy.performRaffle
   → 责任链（黑名单/权重/默认）→ 决策树（次数锁/库存/兜底）
6. 保存中奖记录：awardService.saveUserAwardRecord
   → 事务写 user_award_record + task 记录
7. 更新抽奖单状态（已使用）
8. 返回奖品信息
```

**RaffleStrategyController** — `/api/v1/raffle/strategy/`

| 方法 | URL | 说明 |
|------|-----|------|
| GET | `strategy_armory` | 装配指定策略（预热 Redis） |
| POST | `query_raffle_award_list` | 查询策略奖品列表 |
| POST | `query_raffle_strategy_rule_weight` | 查询权重规则配置 |
| POST | `random_raffle` | 直接执行随机抽奖（测试用） |

**ErpOperateController** — `/api/v1/raffle/erp/`

| 方法 | URL | 说明 |
|------|-----|------|
| GET | `query_user_raffle_order` | 查询用户抽奖订单（ES） |
| POST | `update_stage_activity_2_active` | 将阶段活动上线 |
| GET | `query_raffle_activity_stage_list` | 查询阶段活动列表 |

**DCCController** — `/api/v1/raffle/dcc/`

| 方法 | URL | 说明 |
|------|-----|------|
| GET | `update_config?key=&value=` | 更新 Zookeeper 动态配置节点 |

#### MQ Consumer（4 个）

| 消费者 | Topic | 功能 |
|--------|-------|------|
| `SendAwardCustomer` | `send_award` | 调用 `awardService.distributeAward` 发放奖品 |
| `RebateMessageCustomer` | `send_rebate` | 按返利类型充值 SKU 次数或积分 |
| `CreditAdjustSuccessCustomer` | `credit_adjust_success` | 更新积分支付订单状态（完成活动订单） |
| `ActivitySkuStockZeroCustomer` | `activity_sku_stock_zero` | 清空 SKU 的 Redis 库存缓存和队列，活动下架 |

#### XXL-Job 定时任务（3 个）

| Job 类 | XXL-Job 名称 | 触发机制 | 功能 |
|--------|-------------|----------|------|
| `SendMessageTaskJob` | `SendMessageTaskJob_DB1/DB2` | 定时 + 分布式锁 | 扫描 task 表，补偿发送 MQ |
| `UpdateActivitySkuStockJob` | `UpdateActivitySkuStockJob` | 定时 + 分布式锁 | 消费 SKU 库存扣减延迟队列，批量更新 DB |
| `UpdateAwardStockJob` | `updateAwardStockJob` | 定时 + 分布式锁 | 消费奖品库存扣减延迟队列，批量更新 DB |

**分布式锁机制：** 所有 Job 均使用 `Redisson.getLock().tryLock(3, 0, SECONDS)` 实现分布式互斥

#### Dubbo RPC

| 实现类 | 接口 | 说明 |
|--------|------|------|
| `RebateServiceRPC` | `IRebateService` | 行为返利 RPC，含 AppId/AppToken 鉴权 |

注：`RaffleActivityController` 和 `RaffleStrategyController` 同时标注 `@DubboService(version="1.0")`，HTTP 与 Dubbo 双协议暴露同一逻辑。

### 3.6 big-market-querys（查询层）

CQRS 读侧，提供基于 Elasticsearch 的数据查询：

**数据链路：** `MySQL(user_raffle_order) → Canal (binlog) → Logstash → Elasticsearch → big-market-querys`

```
querys/
├── adapter/repository/IESUserRaffleOrderRepository.java  ← ES 查询仓储接口
└── model/valobj/ESUserRaffleOrderVO.java                 ← ES 文档值对象
```

### 3.7 big-market-app（应用启动层）

**启动入口：** `Application.java`
```java
@SpringBootApplication
@Configurable
@EnableScheduling                    // 启用本地定时任务
@EnableDubbo                         // 启用 Dubbo RPC
@ImportResource("classpath:spring-config.xml")  // 导入 XML Bean（Token Map）
@EnableAspectJAutoProxy(proxyTargetClass = true)  // CGLib AOP 代理
public class Application {
    public static void main(String[] args) {
        SpringApplication.run(Application.class);
    }
}
```

**14 个配置类：**

| 配置类 | 用途 |
|--------|------|
| `DataSourceConfig` | 多数据源（MySQL 分库分表 + ES JDBC） |
| `DCCValueBeanFactory` | DCC 动态配置：扫描 `@DCCValue` 注解 → ZK 监听 → 反射注入 |
| `RedisClientConfig` / `RedisClientConfigProperties` | Redisson 客户端 |
| `GuavaConfig` | Guava Cache（限流 RateLimiter 缓存 1min，黑名单 24h） |
| `ThreadPoolConfig` / `ThreadPoolConfigProperties` | 线程池（core=20, max=50, queue=5000） |
| `Retrofit2Config` / `Retrofit2ConfigProperties` | Retrofit2 HTTP 客户端（调用 OpenAI API） |
| `XxlJobAutoConfig` | XXL-Job 执行器 |
| `ZooKeeperClientConfig` / `ZookeeperClientConfigProperties` | CuratorFramework |
| `PrometheusConfiguration` | Prometheus 监控指标（`TimedAspect`/`CountedAspect`） |
| `RateLimiterAOP` | 限流切面（Guava RateLimiter + 黑名单） |

**Profile 配置：**
- `application-dev.yml`：端口 8098，2库4表 db-router，Redis/RabbitMQ/Dubbo/Nacos/XXL-Job/ES 全配置
- `application-test.yml`：端口 8099
- `application-prod.yml`：端口 8092，Docker 部署，中间件 hostname 引用
- `application.yml`：`spring.profiles.active=dev`

**关键配置项：**

| 配置项 | 值 | 说明 |
|--------|-----|------|
| `server.tomcat.threads.max` | 150 | Tomcat 最大线程 |
| `server.tomcat.max-connections` | 200 | 最大连接数 |
| `mini-db-router.jdbc.datasource.dbCount` | 2 | 分库数 |
| `mini-db-router.jdbc.datasource.tbCount` | 4 | 分表数 |
| `mini-db-router.jdbc.datasource.routerKey` | `userId` | 路由键 |
| `thread.pool.executor.config.core-pool-size` | 20 | 线程池核心线程 |
| `thread.pool.executor.config.max-pool-size` | 50 | 线程池最大线程 |
| `thread.pool.executor.config.block-queue-size` | 5000 | 阻塞队列容量 |

---

## 4. 数据库设计

### 4.1 数据库总览

| 数据库 | 定位 | 主要表 |
|--------|------|--------|
| `big_market`（db00） | 公共配置库（非分片） | strategy/award/rule_tree/raffle_activity/raffle_activity_sku 等配置表 |
| `big_market_01`（db01） | 用户数据分片库 1 | 用户账户、订单、中奖记录等流水数据（4 个分片后缀 _000~_003） |
| `big_market_02`（db02） | 用户数据分片库 2 | 与 big_market_01 结构完全相同，水平扩展 |

### 4.2 分库分表策略

| 维度 | 规则 |
|------|------|
| 分库 | 2 个库（`big_market_01`、`big_market_02`），`userId % 2` 路由 |
| 分表 | 每张用户数据表 4 个分片（`_000`~`_003`），`userId / 2 % 4` 路由，共 8 个物理分片 |
| 路由键 | `userId`（字符串哈希取模） |
| 路由中间件 | `db-router-spring-boot-starter`（自研，基于 MyBatis 插件 + AOP + ThreadLocal） |
| 分片表 | `raffle_activity_order`、`user_raffle_order`、`user_award_record`、`user_behavior_rebate_order`、`user_credit_order`、`raffle_activity_account*`、`task` |
| 不分片表 | `user_credit_account`（单表，唯一键 user_id）、`big_market` 库全部配置表 |

### 4.3 配置库 `big_market` 核心表

**（1）`strategy` — 抽奖策略主表**
- `strategy_id` (bigint)：策略业务 ID
- `rule_models` (varchar)：策略级别规则模型集合（逗号分隔，如 `rule_blacklist,rule_weight`）
- 索引：`KEY idx_strategy_id (strategy_id)`

**（2）`strategy_award` — 策略奖品概率表（核心）**
- `strategy_id` → `strategy`，`award_id` → `award`
- `award_count`：库存总量，`award_count_surplus`：库存剩余（Redis 缓存实时扣减，DB 兜底）
- `award_rate` (decimal(6,4))：中奖概率（4位小数，如 0.7900 = 79%）
- `rule_models`：奖品级别绑定的规则树 ID
- 索引：`KEY idx_strategy_id_award_id (strategy_id, award_id)`

**（3）`strategy_rule` — 策略规则表**
- `rule_type` (tinyint)：1=策略规则，2=奖品规则
- `rule_model` (varchar)：`rule_random`、`rule_blacklist`、`rule_weight`、`rule_lock`、`rule_luck_award`
- `rule_value` (varchar)：如黑名单 `102:user001,user002`，权重 `60:102,103,104`
- 索引：`UNIQUE KEY uq_strategy_id_rule_model`

**（4）规则引擎三表 — 可配置决策树**

| 表 | 核心字段 | 说明 |
|----|---------|------|
| `rule_tree` | `tree_id`, `tree_node_rule_key` | 规则树定义 + 入口节点 |
| `rule_tree_node` | `rule_key`(如`rule_lock`), `rule_value` | 节点规则参数 |
| `rule_tree_node_line` | `rule_node_from`→`rule_node_to`, `rule_limit_type`(EQUAL), `rule_limit_value`(ALLOW/TAKE_OVER) | 节点间连线与条件 |

**规则树执行逻辑示例（`tree_lock_1`）：**
```
rule_lock ──ALLOW──────→ rule_stock ──ALLOW──→ rule_luck_award（兜底）
rule_lock ──TAKE_OVER──→ rule_luck_award（直接接管给兜底奖品）
```

**（5）`raffle_activity` — 活动表**
- `activity_id` → `strategy_id`（一对一绑定策略），`state` (create/open/close)
- `begin_date_time` / `end_date_time`
- 索引：`UNIQUE KEY uq_activity_id`，`UNIQUE KEY uq_strategy_id`

**（6）`raffle_activity_count` — 次数配置表**
- `total_count` / `day_count` / `month_count`

**（7）`raffle_activity_sku` — 活动 SKU 商品表**
- `sku` → `activity_id` → `activity_count_id`
- `stock_count`：总库存，`stock_count_surplus`：剩余库存（Redis 缓存加速）
- `product_amount` (decimal)：积分价格

**（8）`award` — 奖品表**
- `award_id`：业务奖品 ID
- `award_key` (varchar)：对应发奖策略 Bean 名称（如 `user_credit_random`、`openai_account`）
- `award_config` (varchar)：配置参数（如积分随机范围 `1,100`）

**（9）`daily_behavior_rebate` — 行为返利配置**
- `behavior_type` (sign/openai_pay)，`rebate_type` (sku/integral)，`rebate_config`

**（10）`raffle_activity_stage` — 活动上架表（渠道/来源路由）**
- `channel` / `source` → `activity_id`，`state` (create/active/expire)
- **缺少 `activity_id` 索引**

### 4.4 分片库 `big_market_01/02` 核心表

**（1）`raffle_activity_account` — 用户活动账户（总/月/日三级管理）**
- `user_id` + `activity_id` [UQ]
- `total_count_surplus` / `day_count_surplus` / `month_count_surplus`：总/日/月剩余次数
- 日剩余每日凌晨重置，月剩余每月1日重置

**（2）`raffle_activity_account_day` / `_month` — 日/月账户快照**
- `day` (yyyy-mm-dd) / `month` (yyyy-mm)
- 三元唯一约束，独立管理日/月维度

**（3）`raffle_activity_order` — 活动充值订单**
- `order_id` [UQ]、`out_business_no` [UQ 幂等]
- `state` (complete/completed)、`pay_amount`（积分/金额）

**（4）`user_raffle_order` — 抽奖凭证订单**
- `order_id` [UQ]、`order_state` (create → used/cancel)
- 索引：`idx_user_id_activity_id`
- 通过 Canal 同步到 ES 供查询

**（5）`user_award_record` — 中奖记录**
- `order_id` [UQ 幂等]、`award_state` (create → completed)
- **索引命名歧义：** `KEY idx_award_id (strategy_id)` 实际字段是 strategy_id

**（6）`user_credit_account` — 积分账户（未分片）**
- `user_id` [UQ]
- `total_amount`：累计总积分（只增不减）
- `available_amount`：可用积分（扣减后余额）
- `account_status` (open/close)

**（7）`user_credit_order` — 积分流水**
- `trade_type` (forward/reverse)：正向加分 / 逆向扣分
- `trade_amount`：正值为获得，负值为扣减
- `out_business_no` [UQ 幂等]

**（8）`user_behavior_rebate_order` — 返利流水**
- `biz_id` [UQ]（`out_business_no + 类型枚举` 拼接）
- `rebate_type` (sku/integral)

**（9）`task` — Outbox 本地消息表**
- `message_id` [UQ]，`topic` (send_rebate/send_award/credit_adjust_success)
- `state` (create → completed / fail)，`message` (varchar 512)
- **索引命名歧义：** `KEY idx_create_time (update_time)`
- **风险：** `message` 长度仅 512，可能截断

### 4.5 ER 关系

```
strategy (1) ──→ (N) strategy_award ──→ (N:1) award
strategy (1) ──→ (N) strategy_rule
strategy_award ──→ rule_tree (1:N) ──→ rule_tree_node (1:N) ──→ rule_tree_node_line

raffle_activity (1:1) ──→ strategy
raffle_activity (1) ──→ (N) raffle_activity_sku ──→ (N:1) raffle_activity_count

═══════════ 分片库 ═══════════

raffle_activity_account ──→ _account_day / _account_month  (1:N)
raffle_activity_order (充值) ──→ user_credit_order (积分流水) ──→ user_credit_account
user_raffle_order (抽奖凭证) ──→ user_award_record (中奖) ──→ task (MQ消息)
user_behavior_rebate_order ──→ task
```

### 4.6 典型业务链路 × 表交互

**链路 1：用户签到返利**
```
签到 → 查 daily_behavior_rebate → 写 user_behavior_rebate_order + task → MQ → 更新 user_credit_account + user_credit_order
```

**链路 2：积分兑换抽奖次数**
```
兑换 → 查 raffle_activity_sku → 扣 user_credit_account → 写 user_credit_order → 写 raffle_activity_order → 充值 raffle_activity_account
```

**链路 3：执行抽奖**
```
抽奖 → 查 raffle_activity → 扣 raffle_activity_account（三级） → 建 user_raffle_order
     → 查 strategy + strategy_award（奖品池） → 规则过滤（strategy_rule + rule_tree）
     → 写 user_award_record + task → MQ → 更新 award_state
```

### 4.7 数据库设计优点
- 幂等设计完善：各订单表均设计唯一索引（`out_business_no`/`biz_id`/`order_id`）
- 规则引擎可配置：rule_tree 三表实现 DAG，改规则不须发版
- 冗余字段减少跨库 JOIN（`activity_name`、`award_title`）
- 多维度次数管理：总/日/月三级账户独立管理
- 积分账户正逆向流水：`trade_type` 区分 forward/reverse

### 4.8 数据库设计缺陷
- 索引命名歧义 2 处（`idx_award_id` 实际列是 strategy_id，`idx_create_time` 实际列是 update_time）
- 状态字段用 varchar 而非 enum/tinyint
- `user_credit_account` 未分片，高并发下可能成为单点瓶颈
- `task.message` 长度仅 512，可能截断
- `raffle_activity_stage` 缺少 `activity_id` 索引
- 分片数固定为 4（取模），不支持弹性缩扩容
- 缺少显式外键约束
- 冗余字段（`activity_name` 等）可能与主表不一致

---

## 5. API 接口参考

### 5.1 RaffleStrategyController (`/api/v1/raffle/strategy/`)

**GET `strategy_armory`**
- 参数：`strategyId` (Long, Query)
- 调用链：Controller → `StrategyArmoryDispatch.assembleLotteryStrategy()` → Redis + MySQL
- 流程：查询策略奖品列表 → 计算概率范围 → 选择算法（O1/OLogN）→ 装配查找表 → 写入 Redis Hash

**POST `query_raffle_award_list`**
- Body：`{strategyId: 100001}`
- 调用链：→ `IRaffleAward.queryRaffleAwardList()` → 返回奖品列表（含奖品名、概率、库存）

**POST `random_raffle`**
- Body：`{strategyId: 100001}`
- 调用链：→ `DefaultRaffleStrategy.performRaffle()` → 责任链 + 决策树
- 用途：纯策略维度抽奖，不含活动参与校验

**POST `query_raffle_strategy_rule_weight`**
- Body：`{strategyId: 100001}`
- 调用链：→ `IRaffleRule.queryRaffleStrategyRuleWeight()` → 返回权重分段配置

### 5.2 RaffleActivityController (`/api/v1/raffle/activity/`)

**GET `query_stage_activity_id`**
- 参数：`channel` (String), `source` (String)
- 调用链：→ `RaffleActivityStageService.queryStageActivityId()` → DB `raffle_activity_stage`

**GET `armory`**
- 参数：`activityId` (Long)
- 调用链：→ `ActivityArmory.assembleActivitySkuByActivityId()` → Redis + MySQL
- 流程：查活动信息 → 查 SKU 库存 → Redis 写入 SKU AtomicLong + 活动信息

**POST `draw`**（核心）
- Body：`{activityId: 100301, userId: "xiaofuge"}`
- 完整链路见 [6.1 抽奖主流程](#61-抽奖主流程完整链路)

**POST `calendar_sign_rebate`**
- Body：`{userId: "xiaofuge"}`
- 调用链：→ `BehaviorRebateService.createOrder()` → 写返利订单 + task → MQ `send_rebate`

**POST `credit_pay_exchange_sku`**
- Body：`{userId: "xiaofuge", sku: 100001}`
- 调用链：→ `RaffleActivityAccountQuotaService.createOrder()` → CreditPayTradePolicy → 扣积分 + 写活动订单 → MQ

### 5.3 ErpOperateController

**GET `query_user_raffle_order`**
- 调用链：→ `ESUserRaffleOrderRepository.query()` → Elasticsearch

**POST `update_stage_activity_2_active`**
- Body：`{channel, source, activityId}`
- 功能：将阶段活动上线

### 5.4 DCCController

**GET `update_config`**
- 参数：`key` (String), `value` (String)
- 实现：写 Zookeeper 节点 → `CuratorCache` 监听回调 → `DCCValueBeanFactory` 反射更新 Bean 字段
- 支持：`degradeSwitch=open/close`、`rateLimiterSwitch=open/close`

---

## 6. 核心业务流程

### 6.1 抽奖主流程（完整链路）

```
【用户请求】
  POST /api/v1/raffle/activity/draw  {activityId, userId}
       │
       ▼
  RaffleActivityController.draw()
    ① 限流检查（RateLimiterAOP：Guava RateLimiter 令牌桶 + 黑名单 24h）
    ② 降级检查（@DCCValue("degradeSwitch") = open → 直接返回降级响应）
    ③ Hystrix 熔断（@HystrixCommand，超时/异常走 fallback）
    ④ JWT Token 验证（AuthService.checkToken）
       │
       ▼
  RaffleActivityPartakeService.createOrder()           [Activity 域]
    ├── 查活动信息（Redis 缓存 → MySQL 兜底）
    ├── 校验活动状态（open）+ 时间范围
    ├── 查已有未使用抽奖单（幂等，防重复创建）
    ├── 扣减账户额度：
    │     UPDATE raffle_activity_account SET total_count_surplus = total_count_surplus - 1 WHERE surplus > 0
    │     UPDATE raffle_activity_account_month SET month_count_surplus = ... WHERE surplus > 0
    │     UPDATE raffle_activity_account_day SET day_count_surplus = ... WHERE surplus > 0
    └── @Transactional 事务保存：
          INSERT user_raffle_order (state=create) + 更新三级账户
       │
       ▼
  DefaultRaffleStrategy.performRaffle()                [Strategy 域]
    Step A: 责任链前置规则 raffleLogicChain(userId, strategyId)
      ├── BlackListLogicChain: 用户在黑名单? → 直接返回固定奖品(如102号积分)
      ├── RuleWeightLogicChain:
      │     查用户累计抽奖次数 → 匹配权重分段(如4000分以上)
      │     → 用对应权重池的 Redis 查找表 O(1) 随机抽奖
      └── DefaultLogicChain:
            查 Redis Hash 概率表 → SecureRandom.nextInt(rateRange) → HGET 命中奖品
    Step B: 决策树后置规则 raffleLogicTree(userId, strategyId, awardId)
      ├── RuleStockLogicTreeNode:
      │     Redis DECR strategy:award:stock:{strategyId}_{awardId}
      │     成功 → 入延迟队列(5秒后批量写DB) + TAKE_OVER
      │     失败 → ALLOW (库存不足)
      ├── RuleLockLogicTreeNode:
      │     查今日抽奖次数 → 达到N次解锁? → ALLOW : TAKE_OVER → 兜底
      └── RuleLuckAwardLogicTreeNode: 兜底发放积分奖品
       │
       ▼
  AwardService.saveUserAwardRecord()                    [Award 域]
    └── @Transactional 事务：
          INSERT user_award_record (award_state=create)
          INSERT task (state=create, topic=send_award, message=序列化消息)
       │
       ▼
  更新 user_raffle_order (order_state=used)
       │
       ▼
  【返回 ActivityDrawResponseDTO {awardId, awardTitle, ...}】

═══════════════════ 异步流程（MQ + Job） ═══════════════════

  SendMessageTaskJob (XXL-Job, 定时扫描)
    → 查 task 表 state=create → EventPublisher.publish(send_award topic)
    → 更新 task state=completed

  SendAwardCustomer (@RabbitListener, topic=send_award)
    → AwardService.distributeAward()
      → 根据 awardKey 路由到 IDistributeAward 实现
        ├── UserCreditRandomAward: 随机积分 → CreditAdjustService.createOrder(FORWARD)
        └── OpenAIAccountAdjustQuotaAward: Retrofit2 → OpenAI API

  UpdateAwardStockJob (XXL-Job, 定时消费延迟队列)
    → 批量 UPDATE strategy_award SET award_count_surplus = surplus - N WHERE surplus > 0
```

### 6.2 策略装配流程（缓存预热）

```
GET /api/v1/raffle/strategy/strategy_armory?strategyId=100001
         │
         ▼
  StrategyArmoryDispatch.assembleLotteryStrategy(strategyId)
    ① 查询策略奖品列表（strategy_award 表）
    ② 查询规则配置（strategy_rule 表）
    ③ 计算概率范围 rateRange：
         找所有奖品概率的最小精度单位 → rateRange = 1/最小精度
         例：精度 0.1 → rateRange=10，精度 0.001 → rateRange=1000
    ④ 选择算法：
         rateRange ≤ 10000 → O1Algorithm
         rateRange > 10000 → OLogNAlgorithm
    ⑤ 算法装配：
         【O(1)算法】
           - 构建长度为 rateRange 的 List
           - 按概率填充 awardId（如奖品A概率30%填30%位置）
           - Fisher-Yates 洗牌打乱
           - 构建 Map<Integer, Integer> {index → awardId}
           - 写入 Redis Hash: strategy_rate_table_{strategyId}
           - 写入 Redis: strategy_rate_range_{strategyId} = rateRange
         【O(logN)算法】
           - 构建累积概率区间数组
           - 多线程分段处理
           - 写入 Redis
    ⑥ 处理权重规则（rule_weight）
         对每个权重分段（如 4000、5000）分别构建独立的查找表：
           strategy_rate_table_{strategyId}_4000:102,103,104,105
           strategy_rate_table_{strategyId}_5000:102,103,104,105,106,107

GET /api/v1/raffle/activity/armory?activityId=100301
         │
         ▼
  ActivityArmory.assembleActivitySkuByActivityId(activityId)
    ① 查询 raffle_activity_sku + raffle_activity + raffle_activity_count
    ② 写入 Redis：
         SKU 库存 AtomicLong: activity_sku_stock_{sku} = stockCountSurplus
         活动信息缓存
```

### 6.3 行为返利流程

```
DUBBO RPC: RebateServiceRPC.rebate(RebateRequestDTO)
  ① AppId/AppToken 鉴权（spring-config-token.xml 配置）
         │
         ▼
  BehaviorRebateService.createOrder(BehaviorEntity)
    → 查询 daily_behavior_rebate 配置（behavior_type=sign）
    → 构建 BehaviorRebateOrderEntity（幂等 bizId）
    → 构建 SendRebateMessageEvent
    → @Transactional 事务：写 user_behavior_rebate_order + task 记录
         │
         ▼
  【异步】SendMessageTaskJob 扫 task → 发 MQ (send_rebate)
         │
         ▼
  【异步】RebateMessageCustomer 消费
    ├── rebate_type=sku → RaffleActivityAccountQuotaService.createOrder（直接充值次数）
    └── rebate_type=integral → CreditAdjustService.createOrder(FORWARD)（增加积分）
```

### 6.4 积分兑换抽奖次数流程

```
POST /api/v1/raffle/activity/credit_pay_exchange_sku
         │
         ▼
  RaffleActivityAccountQuotaService.createOrder(SkuRechargeEntity)
    ① 查询 SKU / 活动 / 次数配置
    ② 检查积分余额：user_credit_account.available_amount >= pay_amount
    ③ ActionChain 校验：
         ActivityBaseActionChain: 校验活动状态/日期/库存
         ActivitySkuStockActionChain: Redis DECR SKU 库存
    ④ CreditPayTradePolicy.trade():
         @Transactional 事务：
           INSERT raffle_activity_order (state=pending, out_business_no幂等)
           INSERT user_credit_order (trade_type=reverse, trade_amount=-N)
           UPDATE user_credit_account (available_amount -= N)
           INSERT task (topic=credit_adjust_success)
         │
         ▼
  【异步】SendMessageTaskJob → MQ (credit_adjust_success)
         │
         ▼
  【异步】CreditAdjustSuccessCustomer 消费
    → 更新 raffle_activity_order (state=completed)
    → 充值 raffle_activity_account (total/day/month_count_surplus += N)
```

### 6.5 库存最终一致性链路

```
Redis DECR（原子，纳秒级）
  ↓ 成功 → 入 Redisson 延迟队列（5秒延迟聚合）
  ↓ 库存归零 → MQ (activity_sku_stock_zero) → Consumer 更新活动状态=下架
  ↓
后台 XXL-Job (UpdateAwardStockJob / UpdateActivitySkuStockJob)
  → 消费延迟队列
  → 批量 UPDATE DB:
      UPDATE strategy_award SET award_count_surplus = surplus - N
      WHERE strategy_id = ? AND award_id = ? AND award_count_surplus > 0
  ↓ 宕机/消费失败
XXL-Job 定时扫描 Redis 队列补偿
```

---

## 7. 关键技术设计

### 7.1 O(1) 抽奖算法

**核心思路：** 用预计算 + 查表代替运行时的概率累加计算。

**装配阶段（Armory）：**
1. 读取所有奖品及概率，计算最小精度单位 → 得到 `rateRange`
2. 构建长度为 `rateRange` 的 List，按概率填充 `awardId`
3. `Collections.shuffle()` Fisher-Yates 洗牌打乱
4. 构建 `Map<index, awardId>` → 写入 Redis Hash

**执行阶段（Dispatch）：**
```java
int rateRange = repository.getRateRange(key);                  // Redis GET
int randomIndex = secureRandom.nextInt(rateRange);             // 本地CPU
return repository.getStrategyAwardAssemble(key, randomIndex);  // Redis HGET
```
三步均为常数时间，与奖品数量无关 → **O(1) 时间复杂度**。

**权重分段：** 对 `rule_weight` 的每个积分分段分别构建独立查找表，与默认表完全隔离。

**为什么用 Fisher-Yates 洗牌？**
- 不洗牌：相同 awardId 的槽位连续，低维度实验概率偏差大
- 洗牌后：每个槽位等概率出现，有限次抽奖也更均匀
- 防作弊：攻击者无法通过枚举下标预测奖品

**为什么用 SecureRandom 而不是 Random？**
- SecureRandom 基于操作系统熵源（`/dev/urandom`），随机性更强
- 防止攻击者通过预测伪随机序列猜测抽奖结果
- 性能影响可忽略（微秒级 vs Redis RT 毫秒级）

**Redis 宕机恢复：**
- Redis 配置 AOF + RDB 持久化
- 代码层面 `assembleLotteryStrategy()` 幂等，重启后自动重建所有活跃策略的查找表

### 7.2 规则引擎：责任链 + 决策树双层架构

**两层定位差异：**

| 维度 | 责任链（前置） | 决策树（后置） |
|------|---------------|---------------|
| 执行时机 | 抽奖**前**过滤 | 抽奖**后**处理 |
| 解决的问题 | "用哪个奖品池来抽？" | "抽到的奖品能不能发？" |
| 模式特点 | 线性顺序，可提前短路 | 树形分支，有状态转移 |
| 配置方式 | 策略 `rule_models` 字段逗号分隔 | DB `rule_tree` 三表完整 DAG |
| 失败处理 | 短路返回固定结果 | 路由到兜底节点 |

**责任链线程安全：**
- 每个节点 Bean 使用 `@Scope(SCOPE_PROTOTYPE)` 原型作用域
- `DefaultChainFactory.openLogicChain()` 通过 `applicationContext.getBean()` 创建新实例
- 已组装好的链缓存在 `ConcurrentHashMap`（strategyId → 链头），链对象只保存引用不保存状态

**决策树配置缓存优化：**
- 树配置（三表）首次访问时加载 → 序列化为 `RuleTreeVO` → 写入 Redis
- `DefaultTreeFactory` 内存 `HashMap<treeId, DecisionTreeEngine>` 缓存已构建的引擎对象
- 配置变更：删除 Redis key → 下次访问自动重建

### 7.3 Outbox 模式 — MQ 消息最终一致性

**核心原理：** 把"发消息"转换为"写数据库记录"，业务数据与 Task 在同一本地事务中写入，异步 Job 负责实际投递。

**写入流程：**
```
@Transactional 本地事务：
  1. INSERT user_award_record (state='create')
  2. INSERT task (state='create', message=<序列化JSON>)
事务提交 → 两条记录原子性一致
```

**补偿 Job（SendMessageTaskJob）：**
```java
@XxlJob("SendMessageTaskJob_DB1")
public void exec_db01() {
    RLock lock = redissonClient.getLock("big-market-SendMessageTaskJob_DB1");
    if (!lock.tryLock(3, 0, SECONDS)) return;  // 分布式锁防重

    List<TaskEntity> tasks = taskService.queryNoSendMessageTaskList();
    // 查询条件：state='create' 或 (state='fail' AND updateTime < now-1分钟)

    for (TaskEntity task : tasks) {
        taskService.sendMessage(task);                     // 发 MQ
        taskService.updateTaskSendMessageCompleted(task);  // state='completed'
    }
}
```

**多分片处理：** 分 `exec_db01` / `exec_db02` 两个方法，各自独立分布式锁。

**重试策略：** 失败任务 1 分钟后重新扫描，避免因瞬时网络问题频繁重试。

**幂等保障：**
- 消费端通过 `messageId` 做幂等去重
- 关键表均有唯一索引防重复处理（`user_award_record.order_id`、`user_behavior_rebate_order.biz_id`）
- 发送端 at-least-once + 消费端幂等 = 业务层 exactly-once

### 7.4 Redis 预扣减库存 + 异步批量落库

**核心思路：**
```
请求到达 → Redis DECR（原子操作，纳秒级）→ 入延迟队列 → 立即返回
                                              ↓
                                    后台 Job 消费队列 → 批量写 DB（毫秒级聚合）
```

**扣减逻辑：**
```java
long result = redisService.decr(cacheKey);  // 原子 DECR
if (result < 0) {
    redisService.incr(cacheKey);  // 回滚
    return false;
}
// 成功 → 入延迟队列 → 异步批量写 DB
return true;
```

**延迟队列方案：**
- Redisson `RDelayedQueue<T>` + `RBlockingQueue<T>`
- 5 秒延迟聚合，积累多个扣减事件后批量 UPDATE
- 优势：DB 写压力从"每次请求一次写"降为"批量聚合写"，TPS 提升数量级

**为什么用 Redisson 延迟队列而非 RabbitMQ？**
- 库存落库是系统内部批处理，不需要跨系统通信
- Redisson 队列原子性由 Redis 保证，满足需求
- 减少外部 MQ 运维复杂度和故障点

**防超卖多层防护：**
- 第一层：Redis 原子 DECR，result < 0 立即 INCR 回滚
- 第二层：DB 更新时 `WHERE award_count_surplus > 0` 乐观锁条件
- 第三层：活动配额校验（日/月/总额度提前拦截）

**部分失败处理：**
- Redis 扣减成功但进程崩溃 → 对账 Job 定期比对 Redis 计数 vs DB 实际消耗，发现偏差修正
- DB 写入失败 → `INCR` 回滚 Redis 计数
- 活动结束 → Redis key 设置 expireDate 自动清理

### 7.5 DCC 动态配置中心

**原理：** 基于 Zookeeper + Curator + 反射

**工作流程：**
1. Bean 初始化后，`DCCValueBeanFactory` 扫描所有 `@DCCValue` 注解的字段
2. 在 Zookeeper `/big-market-dcc/config/{key}` 节点写入默认值
3. 通过 `CuratorCache` 监听节点变更
4. 值变更时通过反射更新对应 Bean 字段 → 热更新（无需重启）

**支持的开关：**
- `degradeSwitch`: `open`/`close` — 全局熔断降级
- `rateLimiterSwitch`: `open`/`close` — 全局限流

**更新接口：** `GET /api/v1/raffle/dcc/update_config?key=degradeSwitch&value=open`

### 7.6 限流体系

**实现：** `RateLimiterAOP` — 自定义 `@RateLimiterAccessInterceptor` AOP 注解

**工作流程：**
1. 读取注解参数（`permitsPerSecond`、`blacklistCount`、`fallbackMethod`）
2. 检查 DCC 开关（`rateLimiterSwitch=open` 时启用）
3. 从 Guava Cache（1 分钟过期）获取 userId 的 `RateLimiter`
4. `tryAcquire()` 失败 → 计数 → 超过 `blacklistCount` 次加入黑名单（Guava Cache 24h）
5. 走 `fallbackMethod` 返回降级响应

**多层防护：** AOP 限流（令牌桶）→ Hystrix 熔断（服务过载）→ DCC 降级开关（全局关闭）

### 7.7 编程式事务管理

项目采用 `TransactionTemplate` 编程式事务而非 `@Transactional` 注解，原因：
- 分库分表场景需先执行 `dbRouter.doRouter(userId)` 设置路由上下文，再用事务
- 需要细粒度控制回滚：`DuplicateKeyException` → 幂等处理 → 抛 `AppException(INDEX_DUP)` 而非回滚
- 事务结束后 `finally { dbRouter.clear(); }` 清理 ThreadLocal 路由上下文

```java
dbRouter.doRouter(userId);
transactionTemplate.execute(status -> {
    try {
        raffleActivityOrderDao.insert(...);
        raffleActivityAccountDao.updateAccountQuota(...);
        return 1;
    } catch (DuplicateKeyException e) {
        status.setRollbackOnly();
        throw new AppException(ResponseCode.INDEX_DUP.getCode(), e);
    }
});
dbRouter.clear();
```

---

## 8. 横切关注点

### 8.1 日志
- 框架：Logback（`logback-spring.xml`）
- 输出：控制台 + 滚动文件（INFO/ERROR 分离，15天保留，单文件 100MB）
- 格式：`%d{yy-MM-dd.HH:mm:ss.SSS} [%-16t] %-5p %-22c{0} %X{trace-id} %m%n`
- 使用 Lombok `@Slf4j`，关键操作打印 userId/strategyId
- **缺失：** 虽有 `%X{trace-id}` 占位，但无 `TraceIdFilter` 写入 MDC

### 8.2 安全
- JWT 鉴权：`AuthService` 基于 java-jwt，Token 由外部签发后传入校验
- Dubbo RPC 鉴权：`spring-config-token.xml` 配置 AppId → Token Map
- **高风险：** Token/密码明文存储，生产需迁移至 Vault/Nacos Config 加密方案
- **高风险：** `cross-origin=*` 全量跨域，生产需限制具体域名

### 8.3 缓存策略
- Cache-Aside：读时查 Redis → 未命中查 MySQL 并回写 → 写时更新 MySQL → 删除 Redis key
- 策略配置等低频变更数据设 TTL；高频库存计数以 Redis 为准，DB 异步追赶
- 缓存预热：活动/策略上线时通过 armory 接口全量写入 Redis
- 缓存击穿：装配使用 Redisson `RLock` 分布式锁，同一策略仅一个线程执行装配

### 8.4 消息（RabbitMQ）

| Topic | 生产者 | 消费者 | 业务含义 |
|-------|--------|--------|----------|
| `send_award` | AwardRepository | SendAwardCustomer | 奖品发放异步处理 |
| `send_rebate` | BehaviorRebateRepository | RebateMessageCustomer | 返利订单通知 |
| `credit_adjust_success` | CreditRepository | CreditAdjustSuccessCustomer | 积分调整完成通知 |
| `activity_sku_stock_zero` | ActivityRepository | ActivitySkuStockZeroCustomer | SKU 库存耗尽下架 |

**可靠性风险：** 消费者 catch 异常后不重新抛出，消息被自动 ACK，异常消息静默丢失，建议改为手动 ACK + 死信队列。

### 8.5 监控
- Prometheus：`/actuator/prometheus` 暴露 JVM 及自定义指标
- `@Timed`/`@Counted` 注解标注关键方法（Job 执行耗时/次数）
- Grafana 可视化（配置文件在 `docs/dev-ops/grafana/`）
- **缺失：** 分布式链路追踪（TraceId 未贯通 Dubbo/MQ）、线程池监控指标

### 8.6 异常处理
- 自定义异常：`AppException(code, info)`
- Controller 层 try-catch 捕获所有异常 → 返回统一 `Response<T>` 结构
- Repository 层 `DuplicateKeyException` → `AppException(INDEX_DUP)`（幂等）
- **缺失：** 无全局 `@RestControllerAdvice` 统一异常处理器，每个 Controller 方法单独 try-catch

### 8.7 测试覆盖
- 测试位于 `big-market-app/src/test/`，覆盖 DAO → Service → Controller
- 以集成测试为主（需本地 MySQL/Redis/RabbitMQ），缺乏 Mock 单元测试
- 无 JaCoCo 覆盖率配置
- 建议：引入 Mockito 为 Domain 层写纯单元测试，引入 Testcontainers 支持 CI

---

## 9. 运维与部署

### 9.1 运行时中间件

| 中间件 | Dev 地址 | 用途 |
|--------|----------|------|
| MySQL 8.x | `127.0.0.1:3306` | 主存储（2 库 × 4 表） |
| Redis | `192.168.1.108:16379` | 策略/库存缓存 |
| RabbitMQ | `192.168.1.108:5672` | 事件解耦 |
| Nacos | `192.168.1.108:8848` | Dubbo 注册中心 |
| Elasticsearch | `192.168.1.109:9200` | CQRS 查询侧 |
| Zookeeper（可选）| `192.168.1.108:2181` | DCC 动态配置 |
| XXL-Job | `192.168.1.108:9090` | 分布式调度 |

### 9.2 Docker Compose 环境

配置位于 `docs/dev-ops/`：
- `docker-compose-environment.yml` — 中间件环境编排
- `docker-compose-app.yml` — 应用服务编排
- `docker-compose-environment-aliyun.yml` — 阿里云环境
- MySQL 初始化脚本：`docs/dev-ops/mysql/sql/`
- Canal 配置：`docs/dev-ops/canal-adapter/es7/`（4库×4表同步到 ES）
- Grafana/Prometheus/Kibana/Logstash 配置齐全

### 9.3 构建与启动

```bash
mvn clean package -DskipTests
java -jar big-market-app/target/big-market-app-1.1-SNAPSHOT.jar --spring.profiles.active=dev
```

### 9.4 JVM 参数

| 环境 | JVM |
|------|-----|
| dev/test | `-Xms1G -Xmx1G -XX:+UseG1GC` |
| prod | `-Xms6G -Xmx6G -XX:+UseG1GC` |

---

## 10. 面试深挖问答（25题）

### 板块一：DDD 架构设计

**Q1：为什么用 DDD？和 MVC 有什么区别？**

> 营销系统业务规则复杂（抽奖规则、活动配置、积分算法各自独立演进）。传统 MVC 下 Service 直接调 Mapper，业务逻辑和 SQL 耦合，换缓存策略就要改 Service。DDD 通过仓储模式隔离领域层与基础设施，领域层只依赖接口不依赖实现。项目划分了 7 个域，域间通过 DomainEvent + RabbitMQ 或 Repository 接口隔离——例如发奖域只消费 `SendAwardMessageEvent`，不直接依赖活动域代码。
>
> 落地挑战：PO 和 Entity 的双向转换带来额外代码量；DDD 鼓励跨聚合用最终一致性但部分场景业务需要强一致，需在应用层用 `@Transactional` 跨仓储操作做权衡。

**Q2：聚合怎么设计？聚合根是什么？**

> 以活动域为例，`CreatePartakeOrderAggregate` 是参与活动下单的聚合，内部包含：`ActivityAccountEntity`（总账户）、`ActivityAccountMonthEntity`（月账户）、`ActivityAccountDayEntity`（日账户）、`UserRaffleOrderEntity`（抽奖订单）。聚合根对外提供统一业务方法，内部实体不能被外部直接访问，数据库写入在一个事务里完成。

**Q3：分库分表如何设计？路由键为什么选 userId？**

> 2库（`big_market_01/02`）× 4表（`_000~_003`）= 8物理分片，路由键 userId。选 userId 的原因：营销系统绝大多数查询都是用户维度（我的订单、我的配额），以 userId 分片使同一用户数据落在同库，避免跨库 JOIN；活动维度的全量统计通过 ES 异步同步，不需要跨库聚合。`order_id` 由雪花算法生成（12位数字），具备全局唯一性，不依赖 DB 自增。

**Q4：如何保证分布式事务的一致性？**

> 采用 **Outbox 模式（事务消息 + 本地消息表）**：
> 1. 业务操作与 task 记录在同一本地事务中写入
> 2. XXL-Job 定期扫描 task 表（state=create/fail），重新投递 MQ
> 3. 消费端幂等处理（messageId / 唯一索引去重）
> 4. 对于库存扣减：Redis 先扣 → Job 异步写 DB，超卖风险通过 Redis 原子操作保证，写 DB 只是持久化

### 板块二：抽奖核心

**Q5：O(1) 抽奖算法怎么实现？**

> 策略装配时：计算所有奖品概率的最小精度单位 → 得到 rateRange → 构建长度为 rateRange 的 List 按概率填充 awardId → Fisher-Yates 洗牌 → 写入 Redis Hash。抽奖时：`random.nextInt(rateRange) → Redis HGET`，三步常数时间。这里的 O(1) 指每次抽奖请求的执行时间，装配阶段是 O(n) 但属于一次性预热成本。

**Q6：rateRange 怎么确定？如果概率精度很高怎么办？**

> rateRange 是所有奖品概率的最小公倍分母，例如精度 0.001 → rateRange=1000，查找表 1000 个槽位。若精度极高（0.00001 → rateRange=100000），查找表约 100KB，Redis 内存开销可接受。若奖品多 + 精度极高，切换 O(logN) 算法（`OLogNAlgorithm`），用区间数组替代展开表，空间 O(n) 时间 O(log n)。

**Q7：责任链和决策树分别解决什么问题？为什么分两层？**

> 责任链（前置）决定"用哪个奖品池抽"，在抽奖前；决策树（后置）决定"抽到的奖品能不能发"，在抽奖后。两者的配置数据结构不同（链是有序列表，树是有向图），强行合并会使逻辑混乱。分层后业务方可以独立配置前置和后置规则，编排灵活度更高。

**Q8：决策树配置在 DB，每次抽奖都要查库吗？**

> 不。树配置首次访问时加载并缓存到 Redis（`RuleTreeVO` 序列化），后续从 Redis 读取。`DefaultTreeFactory` 在内存中维护 `HashMap<treeId, DecisionTreeEngine>` 缓存，已构建引擎直接复用。配置变更只需删对应 Redis key，下次自动重建。

**Q9：库存扣减如何防止超卖？**

> 三层防护：
> 1. Redis 原子 DECR：`result < 0 → INCR 回滚 → 返回 false`
> 2. DB 乐观更新：`UPDATE ... WHERE award_count_surplus > 0`
> 3. 活动配额提前拦截：日/月/总额度不足不进入抽奖流程
>
> 库存归零时 MQ 通知活动下架，后续请求在活动校验阶段即拦截。

**Q10：增加一种奖品类型需要改哪些地方？**

> 1. 在 `award` 表插入新类型记录（含 `award_key`）
> 2. 实现 `IDistributeAward` 接口，`@Component("newAwardKey")` 注解
> 3. `AwardService` 通过 `applicationContext.getBean(awardKey)` 获取实现
> 不需要改任何 if-else 或 switch，符合开闭原则。

### 板块三：高并发与性能

**Q11：高并发下日/月配额如何不超发？**

> `UPDATE ... WHERE day_count_surplus > 0` 起到乐观锁作用——并发线程中只有一个能将最后一个配额成功扣减，其他线程 affected rows=0 后返回配额不足。更高频场景可在 Redis 层加前置计数减少 DB 压力。

**Q12：限流怎么实现？**

> 自定义 `@RateLimiterAccessInterceptor` AOP 注解 → `RateLimiterAOP` 切面：Guava RateLimiter 令牌桶按 userId 独立限速（QPS 可配）→ 超频自动加 Guava Cache 黑名单（24h）→ 走 fallbackMethod 返回降级。与 Hystrix 组合：限流在前（AOP），熔断在后（Hystrix），梯级保护。

**Q13：缓存预热是什么？为什么要做？缓存击穿怎么处理？**

> 调用 armory 接口时将策略/活动的权重表、奖品、规则树全量写入 Redis，之后抽奖全部缓存命中，RT < 10ms。装配使用 Redisson `RLock` 分布式锁，同一策略同时只有一个线程执行装配，防止缓存击穿。缓存穿透从业务流程规避（奖品列表不为空必须装配过才能参与）。

**Q14：如果活动参与人数爆炸，系统如何应对？**

> - 库存层：Redis DECR 单实例 10w+ QPS
> - 配额层：乐观锁更新，无悲观锁等待
> - 接口层：限流 + Hystrix 熔断 + DCC 降级
> - DB 层：分库分表 + Tomcat 线程池控制（max 150）+ HikariCP（最大 25）
> - 水平扩展：无状态服务 + Nacos 注册，加机器即可

### 板块四：可靠性与异常处理

**Q15：MQ 消息丢失了怎么办？重复消费怎么处理？**

> 防丢失：
> - 生产端：先写 task 本地消息表，再发 MQ；Job 扫描重试
> - Broker 端：交换机/队列 durable=true，消息持久化
> - 消费端：手动 ACK，失败进死信队列
>
> 防重复消费：
> - 关键表均有业务唯一键（`order_id`/`biz_id`/`out_business_no`），重复触发 DuplicateKeyException 后幂等返回
> - 消费端先查状态，已处理则直接 ACK

**Q16：Outbox 模式中消息已发但 Task 状态更新失败会怎样？**

> at-least-once 语义。下一轮 Job 扫描时 Task 还是 create/fail，重新发送消息。消费者通过 `messageId` 做幂等去重——发送端 at-least-once + 消费端幂等 = 业务层 exactly-once。

**Q17：系统如何做降级？DCC 原理？**

> Controller 字段用 `@DCCValue("degradeSwitch:close")` 注入，值来自 Zookeeper。`DCCValueBeanFactory` 监听 ZK 节点变化，节点更新时反射修改 Bean 字段值，实现热更新。抽奖入口判断 `degradeSwitch == "open"` 时直接返回降级响应。搭配 Hystrix 超时熔断多级保护。

**Q18：Redis DECR 成功了但进程崩溃，库存扣了订单没建？**

> 1. Redis 库存 ≠ 最终库存：Redis 只是"乐观锁"层，真正库存以 DB 为准，允许短暂偏差
> 2. 对账 Job 定期比对 Redis 计数和 DB 实际消耗，发现偏差修正
> 3. 活动结束时间作 Redis key 的 expireDate，活动结束后自动清理

### 板块五：设计模式

**Q19：项目用了哪些设计模式？**

> 策略模式（`IDistributeAward`、`ITradePolicy`）、工厂模式（`DefaultChainFactory`、`DefaultTreeFactory`）、模板方法（`AbstractRaffleStrategy`）、责任链（前置规则）、决策树（后置规则）、仓储模式（Repository 接口隔离）、观察者（Event + MQ）、适配器（Repository 实现）。最复杂的例子是决策树——节点配置在 DB，规则修改只需改数据行。

**Q20：如何保证接口幂等性？**

> - 下单：`user_raffle_order` 以 `(userId, activityId)` 查询已有未使用订单，返回已有订单号
> - 发奖：`user_award_record.order_id` 唯一索引防重
> - 返利：`user_behavior_rebate_order.biz_id` 唯一索引
> - 充值：`raffle_activity_order.out_business_no` 唯一索引

### 板块六：综合设计

**Q21：从请求到拿到奖品，整个链路走一遍？**

> 见 [6.1 抽奖主流程](#61-抽奖主流程完整链路)，从 HTTP `draw` → 活动校验/配额扣减 → 责任链(黑名单/权重/默认) → 决策树(库存/次数锁/兜底) → 写中奖记录+task → MQ → 发奖 Consumer → 积分/OpenAI → 库存延迟队列 → Job 批量写 DB。

**Q22：为什么选用 Redisson 而不是 Jedis/Lettuce？**

> Redisson 提供了高级分布式数据结构（`RMap`、`RDelayedQueue`、`RBlockingQueue`、`RLock`、`RAtomicLong`），屏蔽了分布式锁实现（Lua 脚本 + watchdog 续期）、延迟队列（`ZADD`+`BLPOP` 组合）等复杂细节。自研成本高风险大，Redisson 开箱即用且基于 Netty 异步 IO 性能满足需求。

**Q23：活动状态机怎么设计？**

> 活动状态流转：`edit→open→running→close/finish`，中间可 `suspend↔running`。通过 `ActivityStateVO` 枚举 + 状态机方法（`openActivity()`/`closeActivity()`）封装，防止非法状态转换。

**Q24：多线程预装配怎么实现？**

> `StrategyArmoryDispatch` 中，一个策略需构建默认奖品池 + 每个 `rule_weight` 分段各自的查找表，这些互相独立。通过注入的 `ThreadPoolExecutor` 并行提交，主线程等待所有 `Future.get()` 返回。线程池参数：corePoolSize=CPU核数×2，maxPoolSize=core×2，queue=策略数上限。

**Q25：如果让你优化这个系统，从哪里入手？**

> 按优先级：
> - **性能：** rule_lock 今日抽奖次数统计改 Redis INCR+expire；责任链规则值缓存到 Redis；多策略并行预热用 CompletableFuture
> - **可靠性：** MQ 消费端改手动 ACK + 死信队列；增加 Redis vs DB 对账 Job；关键指标 Prometheus 告警
> - **安全性：** Token/密码迁移至 Vault/Nacos Config 加密方案；CORS 限制具体域名
> - **可扩展性：** 规则引擎支持 DB 配置热更新（删除缓存即重建）；Lua 脚本将 Redis 扣减+入队原子化；引入一致性哈希支持弹性扩缩容

---

## 11. 改进建议与风险

### 11.1 安全风险（高优先级）

| 风险 | 描述 | 建议 |
|------|------|------|
| 硬编码凭证 | `application-dev.yml` 中 DB/Redis/RabbitMQ 密码明文、`big-market-appToken` 明文 | 使用 Vault / Nacos Config 加密或环境变量注入 |
| CORS 全放开 | `cross-origin: '*'` 误用于生产存在 CSRF 风险 | 生产明确指定允许域名白名单 |
| AppToken 明文 | `spring-config-token.xml` 中 AppId/Token 明文硬编码在仓库 | 迁移至 Nacos Config 加密存储，从版本控制移除 |
| Token 简单校验 | 密钥硬编码在 `AbstractAuthService` 静态字段 | 生产使用配置中心或环境变量注入密钥 |

### 11.2 可靠性改进（高优先级）

| 问题 | 建议 |
|------|------|
| MQ 消费端静默丢消息 | 改为手动 ACK 模式，消费失败 `nack`，配置死信队列（DLQ）+ 告警 |
| Task 表无失败监控 | 增加 Prometheus 指标上报 fail 数量，超阈值 Grafana 告警 |
| Redis 宕机库存丢失 | 增加降级策略（回退到 DB 乐观锁），定期对账 Job 比对修正 |

### 11.3 架构与技术债

| 问题 | 位置 | 建议 |
|------|------|------|
| Controller 过胖 | `RaffleActivityController` 注入 10+ Service | 增加 Application/Case 层封装跨域编排（作者注释已提到） |
| 缺少全局异常处理 | 每个 Controller 方法单独 try-catch | 添加 `@RestControllerAdvice` |
| Dubbo 与 HTTP 耦合 | Controller 同时实现 Dubbo 接口 | 分离 HTTP Controller 与 Dubbo Provider |
| 分布式锁粒度粗 | `SendMessageTaskJob` 整表扫描 | 按 userId Hash 分片扫描，减少单次扫描量 |
| FastJSON 版本 | 2.0.28 历史上有 RCE 漏洞 | 升级至最新稳定版或替换为 Jackson/Gson |
| DTO 手动转换 | Repository 中大量手动 `setXxx` | 引入 MapStruct 减少样板代码 |
| Spring 2.7 已 EOL | — | 升级至 Spring Boot 3.x |

### 11.4 性能隐患

| 隐患 | 建议 |
|------|------|
| Redis 单节点，无主从/哨兵/集群 | 生产使用 Redis Sentinel 或 Cluster |
| Tomcat `max-connections: 200` 偏低 | 压测后调整或切换 Undertow |
| ES 使用 X-Pack SQL JDBC（商业驱动） | 评估替换为 Elasticsearch Java API Client |
| `task.message` 仅 varchar(512) | 改为 `text` 类型 |
| 分片固定取模 4 | 引入一致性哈希支持弹性扩容 |

### 11.5 可观测性改进（高优先级）

- 添加 `TraceIdFilter` 写入 MDC，实现 HTTP → Dubbo → MQ 全链路追踪
- 线程池通过 Micrometer 上报队列深度/拒绝数到 Prometheus
- 关键业务指标（下单量、抽奖成功率、库存剩余、消息延迟）接入 Grafana 告警
- `app.config.cross-origin` 已配置但需确认生产环境收紧

---

## 12. 快速索引

| 需求 | 起点 |
|------|------|
| 看抽奖主流程 | `RaffleActivityController.draw()` → `AbstractRaffleStrategy.performRaffle()` |
| 看 O(1) 装配算法 | `StrategyArmoryDispatch.assembleLotteryStrategy()` → `O1Algorithm.armoryAlgorithm()` |
| 看责任链规则 | `DefaultChainFactory` → `BlackListLogicChain` → `RuleWeightLogicChain` → `DefaultLogicChain` |
| 看决策树规则 | `DefaultTreeFactory` → `RuleLockLogicTreeNode` → `RuleStockLogicTreeNode` → `RuleLuckAwardLogicTreeNode` |
| 看 Outbox 可靠消息 | `SendMessageTaskJob` → `TaskService` → `TaskDao` |
| 看限流 AOP | `@RateLimiterAccessInterceptor` → `RateLimiterAOP` |
| 看分库分表路由 | `DataSourceConfig` → `db-router` 中间件 → `application-dev.yml` |
| 看 DCC 动态配置 | `@DCCValue` → `DCCValueBeanFactory` → Zookeeper |
| 看活动参与 | `RaffleActivityPartakeService.createOrder()` |
| 看奖品分发 | `AwardService.distributeAward()` → `IDistributeAward` 策略模式 |
| 看积分交易 | `CreditAdjustService.createOrder()` |
| 看行为返利 | `BehaviorRebateService.createOrder()` |
| 看库存异步落库 | `UpdateAwardStockJob` → Redis DelayedQueue |
| 看 DB 完整设计 | [第4节 数据库设计](#4-数据库设计) |
| 准备面试回答 | [第10节 面试深挖问答](#10-面试深挖问答25题) |

---

> **文档生成日期：** 2026-05-05，基于项目 v1.1 全量源码与文档整合。
