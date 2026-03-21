# Big-Market 大营销平台学习指南

> 作者：bugstack.cn @小傅哥  
> 文档整理：项目学习向导  
> 描述：本文档对 `big-market` 项目进行系统性梳理，涵盖各模块功能、设计思路、代码入口及主要流程走向，适合按模块逐步深入学习。

---

## 目录

1. [项目总体介绍](#1-项目总体介绍)
2. [工程模块结构](#2-工程模块结构)
3. [模块一：big-market-types（公共类型层）](#3-模块一big-market-types公共类型层)
4. [模块二：big-market-api（接口定义层）](#4-模块二big-market-api接口定义层)
5. [模块三：big-market-domain（领域层）](#5-模块三big-market-domain领域层)
   - [5.1 策略领域（strategy）](#51-策略领域strategy)
   - [5.2 活动领域（activity）](#52-活动领域activity)
   - [5.3 奖品领域（award）](#53-奖品领域award)
   - [5.4 积分领域（credit）](#54-积分领域credit)
   - [5.5 返利领域（rebate）](#55-返利领域rebate)
   - [5.6 任务领域（task）](#56-任务领域task)
   - [5.7 鉴权领域（auth）](#57-鉴权领域auth)
6. [模块四：big-market-infrastructure（基础设施层）](#6-模块四big-market-infrastructure基础设施层)
7. [模块五：big-market-trigger（触发器层）](#7-模块五big-market-trigger触发器层)
8. [模块六：big-market-querys（查询层）](#8-模块六big-market-querys查询层)
9. [模块七：big-market-app（应用启动层）](#9-模块七big-market-app应用启动层)
10. [核心流程走向](#10-核心流程走向)
    - [10.1 抽奖主流程](#101-抽奖主流程)
    - [10.2 活动下单充值流程](#102-活动下单充值流程)
    - [10.3 行为返利流程](#103-行为返利流程)
    - [10.4 奖品发放流程](#104-奖品发放流程)
    - [10.5 积分兑换抽奖次数流程](#105-积分兑换抽奖次数流程)
11. [设计亮点总结](#11-设计亮点总结)
12. [技术栈一览](#12-技术栈一览)

---

## 1. 项目总体介绍

`big-market` 是一个以 **DDD（领域驱动设计）** 为核心架构的大型营销抽奖平台，集成了抽奖策略、活动管理、奖品发放、积分体系、行为返利等完整业务链路。

**核心业务链路：**
```
用户行为（签到/支付）→ 返利 → 积分 → 购买抽奖次数 → 参与活动 → 抽奖 → 奖品发放
```

**整体架构图（分层）：**
```
┌──────────────────────────────────────────────────┐
│             big-market-trigger（触发器层）          │
│  HTTP Controller / MQ Listener / XxlJob / RPC    │
├──────────────────────────────────────────────────┤
│             big-market-domain（领域层）             │
│  strategy / activity / award / credit / rebate / │
│               task / auth                         │
├──────────────────────────────────────────────────┤
│         big-market-infrastructure（基础设施层）      │
│   Repository实现 / DAO / Redis / MQ / ES / RPC   │
├──────────────────────────────────────────────────┤
│   big-market-types   │   big-market-api           │
│   (公共类型/注解/枚举)  │  (接口定义/DTO)            │
└──────────────────────────────────────────────────┘
```

---

## 2. 工程模块结构

```
big-market/
├── big-market-api            # 对外接口定义（接口 + DTO）
├── big-market-app            # Spring Boot 启动入口、全局配置、AOP
├── big-market-domain         # 领域层（DDD 核心，业务逻辑全部在此）
├── big-market-infrastructure # 基础设施层（数据库、Redis、MQ、ES 实现）
├── big-market-trigger        # 触发器层（HTTP、Job、MQ消费、Dubbo RPC）
├── big-market-querys         # 查询服务（ElasticSearch 数据查询）
└── big-market-types          # 公共类型（注解、枚举、异常、事件基类）
```

---

## 3. 模块一：big-market-types（公共类型层）

### 功能说明
提供全工程通用的基础类型定义，包括注解、枚举、异常、事件基类等，无业务逻辑。

### 目录结构
```
big-market-types/
└── cn/bugstack/types/
    ├── annotations/
    │   ├── DCCValue.java                  # 动态配置中心注解（绑定 Zookeeper 配置）
    │   └── RateLimiterAccessInterceptor.java  # 限流拦截器注解
    ├── common/
    │   └── Constants.java                 # 全局常量（分隔符等）
    ├── enums/
    │   └── ResponseCode.java              # 统一响应码枚举
    ├── event/
    │   └── BaseEvent.java                 # MQ 事件消息基类
    └── exception/
        └── AppException.java              # 自定义业务异常
```

### 设计亮点
- **`@DCCValue`** 注解：标注在字段上后，`DCCValueBeanFactory` 会自动从 Zookeeper 读取配置并注入，支持动态刷新，无需重启服务。
- **`BaseEvent<T>`** 泛型事件：统一了所有 MQ 事件消息格式，含消息 ID、时间戳和泛型数据体，便于反序列化和幂等处理。

---

## 4. 模块二：big-market-api（接口定义层）

### 功能说明
定义所有对外暴露的接口（HTTP 接口 + Dubbo RPC 接口）及其请求/响应 DTO，不包含任何实现。

### 目录结构
```
big-market-api/
└── cn/bugstack/trigger/api/
    ├── IDCCService.java              # 动态配置中心接口
    ├── IErpOperateService.java       # ERP 运营管理接口
    ├── IRaffleActivityService.java   # 抽奖活动接口（核心）
    ├── IRaffleStrategyService.java   # 抽奖策略接口
    ├── IRebateService.java           # 返利服务接口（Dubbo RPC）
    ├── dto/                          # 请求/响应 DTO
    │   ├── ActivityDrawRequestDTO    # 抽奖请求
    │   ├── ActivityDrawResponseDTO   # 抽奖响应
    │   ├── RaffleAwardListRequestDTO # 查询奖品列表请求
    │   ├── SkuProductResponseDTO     # SKU商品响应
    │   └── ...
    ├── request/Request.java          # Dubbo RPC 通用请求包装（含 appId/appToken）
    └── response/Response.java        # 统一响应结构（code + info + data）
```

### 关键接口说明

| 接口 | 主要方法 | 说明 |
|------|----------|------|
| `IRaffleActivityService` | `armory`, `draw`, `calendarSignRebate`, `isCalendarSignRebate`, `queryUserActivityAccount`, `creditPayExchangeSku` | 活动抽奖全流程接口 |
| `IRaffleStrategyService` | `strategyArmory`, `randomRaffle`, `queryRaffleAwardList`, `queryRaffleStrategyRuleWeight` | 策略装配与抽奖接口 |
| `IRebateService` | `rebate` | 返利服务 Dubbo RPC 接口 |
| `IDCCService` | `updateConfig` | 动态配置修改接口 |
| `IErpOperateService` | `queryUserRaffleOrder`, `queryStageActivityList`, `updateStageActivity2Active` | 运营后台接口 |

---

## 5. 模块三：big-market-domain（领域层）

领域层是整个项目的**核心**，采用 DDD 分包，每个领域都遵循统一的内部结构：

```
domain/<领域名>/
├── adapter/
│   ├── event/          # 领域事件定义（MQ 消息 Topic 和消息体）
│   ├── repository/     # 仓储接口（domain 只依赖接口，不依赖实现）
│   └── port/           # 外部服务端口（调用第三方服务）
├── model/
│   ├── aggregate/      # 聚合对象（跨实体的事务边界）
│   ├── entity/         # 实体（有业务标识）
│   └── valobj/         # 值对象（无标识，不可变）
└── service/            # 领域服务（业务逻辑）
```

---

### 5.1 策略领域（strategy）

**代码路径：** `big-market-domain/src/main/java/cn/bugstack/domain/strategy/`

#### 功能说明
策略领域负责**抽奖概率计算**和**规则过滤**，是整个平台最核心的算法模块。

#### 核心服务接口

| 接口 | 实现类 | 功能 |
|------|--------|------|
| `IStrategyArmory` | `StrategyArmoryDispatch` | 策略装配（预热数据到 Redis）|
| `IStrategyDispatch` | `StrategyArmoryDispatch` | 策略抽奖调度（随机获取奖品）|
| `IRaffleStrategy` | `DefaultRaffleStrategy` | 执行抽奖（责任链 + 决策树）|
| `IRaffleAward` | `DefaultRaffleStrategy` | 查询奖品信息 |
| `IRaffleRule` | `DefaultRaffleStrategy` | 查询规则配置 |
| `IRaffleStock` | `DefaultRaffleStrategy` | 奖品库存管理 |

#### 模块设计

**（1）策略装配（Armory）**

> **代码入口：** `StrategyArmoryDispatch#assembleLotteryStrategy(Long strategyId)`

**流程：**
```
assembleLotteryStrategy(strategyId)
  → 查询策略奖品列表 (IStrategyRepository#queryStrategyAwardList)
  → 计算概率范围（最小精度至小数点后几位）
  → 调用算法装配（IAlgorithm#armoryAlgorithm）
       ├── O1Algorithm：构建概率查找表存入 Redis Hash
       └── OLogNAlgorithm：构建区间数组 + 多线程分段处理存入 Redis
  → 查询权重规则，对每个权重段额外装配概率表
```

**抽奖算法选择：**
```
AbstractAlgorithm.Algorithm 枚举
  ├── O1     → O1Algorithm   → O(1) 空间换时间，Hash 直接命中
  └── OLogN  → OLogNAlgorithm → O(logN) 区间二分查找，多线程装配
```

**（2）抽奖执行（Raffle）**

> **代码入口：** `AbstractRaffleStrategy#performRaffle(RaffleFactorEntity)`
> 
> **实现类：** `DefaultRaffleStrategy`

**流程（模板方法模式）：**
```
performRaffle(raffleFactorEntity)
  Step 1: 参数校验（userId、strategyId 非空）
  Step 2: 责任链抽奖 raffleLogicChain(userId, strategyId)
          ├── BlackListLogicChain  → 黑名单直接返回兜底奖品
          ├── RuleWeightLogicChain → 按权重区间抽奖
          └── DefaultLogicChain   → 默认随机抽奖（strategyDispatch.getRandomAwardId）
  Step 3: 如果责任链命中非默认逻辑，直接返回
  Step 4: 决策树过滤 raffleLogicTree(userId, strategyId, awardId, endDateTime)
          ├── RuleLockLogicTreeNode  → 次数锁（今日抽奖次数 >= N 才解锁奖品）
          ├── RuleStockLogicTreeNode → 库存扣减（Redis decrement，写入延迟队列）
          └── RuleLuckAwardLogicTreeNode → 兜底奖品（库存不足时替换）
  Step 5: 返回最终奖品实体
```

**（3）责任链模式（前置规则）**

```
DefaultChainFactory 管理责任链
  → 通过 Spring 按名称注入（@Component("rule_blacklist") 等）
  → 每次使用新建原型 Bean（@Scope(SCOPE_PROTOTYPE)）
  → ILogicChain.next() 串联下一个节点
```

| 责任链节点 | Bean 名称 | 规则说明 |
|-----------|-----------|----------|
| `BlackListLogicChain` | `rule_blacklist` | 黑名单用户，直接给兜底奖品 |
| `RuleWeightLogicChain` | `rule_weight` | 按用户累计抽奖次数命中权重段 |
| `DefaultLogicChain` | `rule_default` | 默认随机抽奖 |

**（4）决策树模式（后置规则）**

```
DefaultTreeFactory 根据策略奖品配置的规则树模型构建决策树
  → RuleTreeVO 描述整棵树的结构（节点 + 连线）
  → DecisionTreeEngine 递归遍历树节点
```

| 决策树节点 | Bean 名称 | 规则说明 |
|-----------|-----------|----------|
| `RuleLockLogicTreeNode` | `rule_lock` | 抽奖次数不足时锁定高价值奖品 |
| `RuleStockLogicTreeNode` | `rule_stock` | 扣减 Redis 库存，写延迟队列 |
| `RuleLuckAwardLogicTreeNode` | `rule_luck_award` | 库存不足兜底奖品 |

---

### 5.2 活动领域（activity）

**代码路径：** `big-market-domain/src/main/java/cn/bugstack/domain/activity/`

#### 功能说明
管理抽奖活动的生命周期，包括**活动装配**、**参与活动**（创建抽奖单）、**账户额度管理**（充值/消费次数）、**SKU 商品**、**活动库存**等。

#### 核心服务接口

| 接口 | 实现类 | 功能 |
|------|--------|------|
| `IActivityArmory` | `ActivityArmory` | 活动数据预热到 Redis |
| `IRaffleActivityPartakeService` | `RaffleActivityPartakeService` | 参与活动（创建抽奖单）|
| `IRaffleActivityAccountQuotaService` | `RaffleActivityAccountQuotaService` | 账户额度管理（充值/下单）|
| `IRaffleActivitySkuStockService` | 内嵌 | SKU 库存管理 |
| `IRaffleActivitySkuProductService` | `RaffleActivitySkuProductService` | SKU 商品列表查询 |
| `IRaffleActivityStageService` | `RaffleActivityStageService` | 上架活动查询 |

#### 模块设计

**（1）参与活动创建抽奖单**

> **代码入口：** `AbstractRaffleActivityPartake#createOrder(PartakeRaffleActivityEntity)`

```
createOrder(partakeRaffleActivityEntity)
  Step 1: 查询活动信息，校验活动状态（必须 open）及时间范围
  Step 2: 查询是否已有未使用的抽奖单（幂等，避免重复创建）
  Step 3: 调用子类 doFilterAccount → 查询并扣减账户额度（总/月/日）
  Step 4: 构建 UserRaffleOrderEntity（抽奖单）
  Step 5: 组装 CreatePartakeOrderAggregate，调用 repository 事务保存
  Step 6: 返回抽奖单
```

**（2）账户充值下单**

> **代码入口：** `AbstractRaffleActivityAccountQuota#createOrder(SkuRechargeEntity)`

```
createOrder(skuRechargeEntity)
  Step 1: 参数校验
  Step 2: 查询未支付订单（积分支付类型需要幂等）
  Step 3: 查询 SKU、活动、次数配置
  Step 4: 账户额度校验（积分支付时检查余额）
  Step 5: 责任链校验 ActionChain（ActivityBaseActionChain → ActivitySkuStockActionChain 扣减 SKU 库存）
  Step 6: 构建订单聚合对象 CreateQuotaOrderAggregate
  Step 7: 交易策略路由（ITradePolicy）
          ├── CreditPayTradePolicy    → 积分支付，扣减积分
          └── RebateNoPayTradePolicy  → 返利免支付，直接充值
  Step 8: 返回未支付订单信息
```

**活动 Action 责任链：**

| 节点 | 说明 |
|------|------|
| `ActivityBaseActionChain` | 校验活动状态、日期、库存 |
| `ActivitySkuStockActionChain` | 扣减 Redis SKU 库存，库存耗尽发 MQ 通知 |

**交易类型（OrderTradeTypeVO）：**

| 类型 | 说明 |
|------|------|
| `credit_pay_trade` | 积分支付购买次数 |
| `rebate_no_pay_trade` | 返利免支付充值次数 |

---

### 5.3 奖品领域（award）

**代码路径：** `big-market-domain/src/main/java/cn/bugstack/domain/award/`

#### 功能说明
负责**保存用户中奖记录**，并通过 MQ 事件触发**奖品分发**。

#### 核心服务接口

| 接口 | 实现类 | 功能 |
|------|--------|------|
| `IAwardService` | `AwardService` | 保存中奖记录 + 奖品分发 |
| `IDistributeAward` | 多种实现 | 具体奖品发放策略 |

#### 模块设计

**（1）保存中奖记录**

> **代码入口：** `AwardService#saveUserAwardRecord(UserAwardRecordEntity)`

```
saveUserAwardRecord(userAwardRecordEntity)
  → 构建 SendAwardMessage（发奖 MQ 消息体）
  → 构建 TaskEntity（MQ 任务记录，状态 create）
  → 组装 UserAwardRecordAggregate 聚合
  → awardRepository.saveUserAwardRecord（事务：写中奖记录 + 写任务记录）
```

**（2）奖品分发**

> **代码入口：** `AwardService#distributeAward(DistributeAwardEntity)`

```
distributeAward(distributeAwardEntity)
  → awardRepository.queryAwardKey(awardId) → 获取奖品 key（如 "openai_account"、"user_credit"）
  → 根据 awardKey 路由到对应的 IDistributeAward 实现
  → 调用 distributeAward.giveOutPrizes(distributeAwardEntity)
```

**奖品分发实现（策略模式）：**

| 实现类 | Bean Key | 功能 |
|--------|----------|------|
| `UserCreditRandomAward` | `user_credit_random` | 发放随机积分（最小值 ~ 最大值间随机）|
| `OpenAIAccountAdjustQuotaAward` | `openai_account` | 调用外部 OpenAI 账户充值 API |

---

### 5.4 积分领域（credit）

**代码路径：** `big-market-domain/src/main/java/cn/bugstack/domain/credit/`

#### 功能说明
管理用户**积分账户**的增减（正向/逆向交易），支持积分充值和积分消费。

#### 核心服务接口

| 接口 | 实现类 | 功能 |
|------|--------|------|
| `ICreditAdjustService` | `CreditAdjustService` | 创建积分交易订单 + 查询账户 |

#### 模块设计

> **代码入口：** `CreditAdjustService#createOrder(TradeEntity)`

```
createOrder(tradeEntity)
  Step 0: 逆向交易（扣积分）时，先查询账户余额是否充足
  Step 1: TradeAggregate.createCreditAccountEntity → 账户实体（增减积分）
  Step 2: TradeAggregate.createCreditOrderEntity   → 订单实体
  Step 3: 构建 MQ 事件消息（CreditAdjustSuccessMessageEvent）
  Step 4: 构建 TaskEntity（任务表记录）
  Step 5: 组装 TradeAggregate
  Step 6: creditRepository.saveUserCreditTradeOrder（事务保存）
  → 返回订单 ID
```

**交易类型（TradeTypeVO）：**

| 类型 | 说明 |
|------|------|
| `FORWARD` | 正向，增加积分（返利奖励）|
| `REVERSE` | 逆向，扣减积分（兑换商品）|

**交易名称（TradeNameVO）：**

| 名称 | 说明 |
|------|------|
| `REBATE` | 行为返利增加积分 |
| `CONSUME` | 消费积分兑换次数 |
| `AWARD` | 抽奖奖励积分 |

---

### 5.5 返利领域（rebate）

**代码路径：** `big-market-domain/src/main/java/cn/bugstack/domain/rebate/`

#### 功能说明
处理用户**行为返利**逻辑（如签到、完成任务等），根据配置生成返利订单并发送 MQ 消息触发奖励。

#### 核心服务接口

| 接口 | 实现类 | 功能 |
|------|--------|------|
| `IBehaviorRebateService` | `BehaviorRebateService` | 创建返利订单 + 查询订单 |

#### 模块设计

> **代码入口：** `BehaviorRebateService#createOrder(BehaviorEntity)`

```
createOrder(behaviorEntity)
  Step 1: 查询返利配置（DailyBehaviorRebateVO），含返利类型和金额
  Step 2: 构建返利订单 BehaviorRebateOrderEntity（含幂等 bizId）
  Step 3: 构建 SendRebateMessageEvent（MQ 消息体）
  Step 4: 构建 TaskEntity
  Step 5: 组装 BehaviorRebateAggregate
  Step 6: behaviorRebateRepository.saveUserRebateRecord（事务保存）
  Step 7: 返回订单 ID 列表
```

**返利类型（RebateTypeVO）：**

| 类型 | 说明 |
|------|------|
| `sku` | 返利直接充值抽奖 SKU 次数 |
| `integral` | 返利增加积分 |

**行为类型（BehaviorTypeVO）：**

| 类型 | 说明 |
|------|------|
| `SIGN` | 签到行为 |
| `OPEN_ACTIVITY` | 参与活动行为 |

---

### 5.6 任务领域（task）

**代码路径：** `big-market-domain/src/main/java/cn/bugstack/domain/task/`

#### 功能说明
提供 **Task 表扫描与 MQ 消息补偿**机制，保障消息至少投递一次（Outbox 模式）。

#### 核心服务接口

| 接口 | 实现类 | 功能 |
|------|--------|------|
| `ITaskService` | `TaskService` | 查询未发送任务、发送 MQ、更新状态 |

> **代码入口：** `TaskService`（被 `SendMessageTaskJob` 定时任务调用）

```
queryNoSendMessageTaskList() → 查询状态为 create/fail 的 task 记录
sendMessage(taskEntity)       → 调用 EventPublisher 发送 MQ
updateTaskSendMessageCompleted → 更新 task 状态为 completed
updateTaskSendMessageFail      → 更新 task 状态为 fail
```

---

### 5.7 鉴权领域（auth）

**代码路径：** `big-market-domain/src/main/java/cn/bugstack/domain/auth/`

#### 功能说明
提供基于 **JWT** 的 Token 校验与 OpenId 解析服务。

#### 模块设计

> **代码入口：** `AuthService`

```
checkToken(token) → AbstractAuthService#isVerify → HMAC256 验签
openid(token)     → AbstractAuthService#decode  → 解析 Claims.openId 字段
```

- Token 由外部（如微信登录服务）生成后传入，本系统只做校验
- 密钥通过 `AbstractAuthService` 中的静态字段配置，**生产环境必须替换为安全的随机密钥，建议通过配置中心或环境变量注入，不要硬编码在代码中**

---

## 6. 模块四：big-market-infrastructure（基础设施层）

**代码路径：** `big-market-infrastructure/src/main/java/cn/bugstack/infrastructure/`

### 功能说明
实现领域层定义的所有 `IXxxRepository` 接口，隔离技术细节，提供 MySQL、Redis、RabbitMQ、ElasticSearch 的访问能力。

### 目录结构
```
infrastructure/
├── adapter/
│   ├── repository/         # Repository 实现类（领域仓储实现）
│   │   ├── StrategyRepository.java       # 策略仓储
│   │   ├── ActivityRepository.java       # 活动仓储
│   │   ├── AwardRepository.java          # 奖品仓储
│   │   ├── BehaviorRebateRepository.java # 返利仓储
│   │   ├── CreditRepository.java         # 积分仓储
│   │   ├── TaskRepository.java           # 任务仓储
│   │   └── ESUserRaffleOrderRepository.java # ES查询仓储
│   └── port/
│       └── AwardPort.java                # 外部奖品发放端口实现（调用 OpenAI）
├── dao/                   # MyBatis DAO 接口
│   ├── po/                # 数据库持久化对象（PO）
│   ├── IStrategyDao.java
│   ├── IStrategyAwardDao.java
│   ├── IStrategyRuleDao.java
│   ├── IRuleTreeDao / IRuleTreeNodeDao / IRuleTreeNodeLineDao
│   ├── IRaffleActivityDao / IRaffleActivityCountDao / IRaffleActivitySkuDao
│   ├── IRaffleActivityAccountDao / IRaffleActivityAccountDayDao / IRaffleActivityAccountMonthDao
│   ├── IRaffleActivityOrderDao
│   ├── IUserRaffleOrderDao
│   ├── IUserAwardRecordDao
│   ├── IUserCreditAccountDao / IUserCreditOrderDao
│   ├── IUserBehaviorRebateOrderDao
│   ├── IDailyBehaviorRebateDao
│   ├── IAwardDao
│   └── ITaskDao
├── elasticsearch/
│   └── IElasticSearchUserRaffleOrderDao.java  # ES 数据访问
├── event/
│   └── EventPublisher.java                    # RabbitMQ 消息发布工具
├── gateway/
│   └── IOpenAIAccountService.java             # Retrofit2 调用 OpenAI 账户服务
└── redis/
    ├── IRedisService.java                     # Redis 操作接口
    └── RedissonService.java                   # Redisson 实现（含分布式锁、队列等）
```

### 核心数据库表

| 表名 | 对应领域 | 说明 |
|------|----------|------|
| `strategy` | 策略 | 抽奖策略基础信息 |
| `strategy_award` | 策略 | 策略奖品配置（概率、库存）|
| `strategy_rule` | 策略 | 策略规则值（黑名单、权重等）|
| `rule_tree / rule_tree_node / rule_tree_node_line` | 策略 | 决策树结构 |
| `raffle_activity` | 活动 | 活动基础信息（状态、日期）|
| `raffle_activity_count` | 活动 | 活动次数配置（总/月/日）|
| `raffle_activity_sku` | 活动 | 活动 SKU（商品 ID、库存）|
| `raffle_activity_order` | 活动 | 活动充值订单 |
| `raffle_activity_account` | 活动 | 用户活动账户（总额度）|
| `raffle_activity_account_day` | 活动 | 用户活动账户（日额度）|
| `raffle_activity_account_month` | 活动 | 用户活动账户（月额度）|
| `user_raffle_order` | 活动 | 用户抽奖单 |
| `user_award_record` | 奖品 | 用户中奖记录 |
| `award` | 奖品 | 奖品配置（key 绑定发放策略）|
| `user_credit_account` | 积分 | 用户积分账户 |
| `user_credit_order` | 积分 | 积分交易订单 |
| `user_behavior_rebate_order` | 返利 | 用户行为返利订单 |
| `daily_behavior_rebate` | 返利 | 每日行为返利配置 |
| `task` | 任务 | MQ 任务记录（Outbox 模式）|

### 关键设计

**Redis 缓存策略：**

| 缓存 Key | 说明 |
|----------|------|
| `strategy_award_list_{strategyId}` | 奖品列表缓存 |
| `strategy_rate_table_{strategyId}` | O(1) 概率查找表（Hash）|
| `strategy_rate_range_{strategyId}` | 概率范围总值 |
| `strategy_award_stock_key_{strategyId}_{awardId}` | 奖品库存（decrement）|
| `activity_sku_stock_key_{sku}` | SKU 库存（decrement）|
| `raffle_activity_account_quota_{userId}_{activityId}` | 用户账户额度 |

**分库分表：** 用户相关表（activity_account / raffle_order 等）通过 `db-router` 按用户 ID 分库分表，分散写入压力。

---

## 7. 模块五：big-market-trigger（触发器层）

**代码路径：** `big-market-trigger/src/main/java/cn/bugstack/trigger/`

### 功能说明
承接所有外部触发点：HTTP 接口、定时任务、MQ 消费、Dubbo RPC。是领域层的调用入口。

### 目录结构
```
trigger/
├── http/                     # HTTP RESTful 接口实现
│   ├── RaffleActivityController.java   # 活动抽奖接口（最核心）
│   ├── RaffleStrategyController.java   # 策略管理接口
│   ├── DCCController.java              # 动态配置中心接口
│   └── ErpOperateController.java       # ERP 运营管理接口
├── job/                      # XxlJob 定时任务
│   ├── SendMessageTaskJob.java          # 扫描 task 表补偿发送 MQ
│   ├── UpdateActivitySkuStockJob.java   # 消费队列更新 SKU 库存到 DB
│   └── UpdateAwardStockJob.java         # 消费队列更新奖品库存到 DB
├── listener/                  # RabbitMQ 消费者
│   ├── SendAwardCustomer.java           # 监听发奖消息，调用 AwardService.distributeAward
│   ├── RebateMessageCustomer.java       # 监听返利消息，充值 SKU 或积分
│   ├── CreditAdjustSuccessCustomer.java # 监听积分调整成功消息，更新活动订单状态
│   └── ActivitySkuStockZeroCustomer.java # 监听 SKU 库存耗尽，清空 Redis 缓存
└── rpc/
    └── RebateServiceRPC.java            # Dubbo 返利服务 RPC 实现
```

### HTTP 接口详解

#### RaffleActivityController（最核心入口）

| 请求路径 | 方法 | 功能 |
|----------|------|------|
| `GET /armory` | `armory` | 活动+策略数据预热（装配）|
| `POST /draw` | `draw` | **执行抽奖**（完整业务流程）|
| `POST /draw_by_token` | `draw` | 带 Token 鉴权的抽奖 |
| `POST /calendar_sign_rebate` | `calendarSignRebate` | 日历签到返利 |
| `GET /is_calendar_sign_rebate` | `isCalendarSignRebate` | 查询今日是否已签到 |
| `POST /query_user_activity_account` | `queryUserActivityAccount` | 查询用户活动账户信息 |
| `POST /credit_pay_exchange_sku` | `creditPayExchangeSku` | 积分兑换 SKU（购买次数）|
| `GET /query_sku_product_list_by_activity_id` | `querySkuProductListByActivityId` | 查询活动 SKU 商品列表 |
| `GET /query_stage_activity_id` | `queryStageActivityId` | 查询上架活动 ID |
| `GET /query_user_credit_account` | `queryUserCreditAccount` | 查询用户积分账户 |

#### `draw` 抽奖接口完整流程（核心）

```java
// 代码位置：RaffleActivityController#draw
POST /api/v1/raffle/activity/draw
Body: {"activityId": 100301, "userId": "xiaofuge"}

// 流程：
1. 限流校验（@RateLimiterAccessInterceptor，Guava RateLimiter + 黑名单）
2. 降级开关检查（@DCCValue("degradeSwitch") + Hystrix 熔断）
3. 参数校验
4. 创建抽奖单：raffleActivityPartakeService.createOrder
   → 检查活动状态/日期 → 扣减账户额度 → 保存抽奖单
5. 执行抽奖：raffleStrategy.performRaffle
   → 责任链（黑名单/权重/默认）→ 决策树（次数锁/库存/兜底）
6. 保存中奖记录：awardService.saveUserAwardRecord
   → 事务写 user_award_record + task 记录
7. 更新抽奖单状态（已使用）
8. 返回奖品信息
```

### 定时任务详解

| 任务类 | XxlJob 名称 | 触发机制 | 功能 |
|--------|-------------|----------|------|
| `SendMessageTaskJob` | `SendMessageTaskJob_DB1/DB2` | 定时（5s）+ 分布式锁 | 扫描 task 表，补偿发送 MQ |
| `UpdateActivitySkuStockJob` | `UpdateActivitySkuStockJob` | 定时（5s）+ 分布式锁 | 消费 SKU 库存扣减队列，更新 DB |
| `UpdateAwardStockJob` | `updateAwardStockJob` | 定时（5s）+ 分布式锁 | 消费奖品库存扣减队列，更新 DB |

**分布式锁机制：** 所有 Job 均使用 `Redisson.getLock().tryLock(3, 0, SECONDS)` 实现分布式互斥，防止多实例重复执行。

### MQ 消费者详解

| 消费者 | Topic 配置 | 功能 |
|--------|------------|------|
| `SendAwardCustomer` | `send_award` | 调用 `awardService.distributeAward` 发放奖品 |
| `RebateMessageCustomer` | `send_rebate` | 按返利类型充值 SKU 次数或积分 |
| `CreditAdjustSuccessCustomer` | `credit_adjust_success` | 更新积分支付订单状态 |
| `ActivitySkuStockZeroCustomer` | `activity_sku_stock_zero` | 清空 SKU 的 Redis 库存缓存和队列 |

---

## 8. 模块六：big-market-querys（查询层）

**代码路径：** `big-market-querys/src/main/java/cn/bugstack/querys/`

### 功能说明
提供基于 **ElasticSearch** 的数据查询能力，用于运营数据分析。通过 Canal 同步 MySQL 数据到 ES。

### 目录结构
```
querys/
├── adapter/repository/
│   └── IESUserRaffleOrderRepository.java  # ES 查询仓储接口
├── model/valobj/
│   └── ESUserRaffleOrderVO.java           # ES 文档值对象
```

**数据链路：**
```
MySQL(user_raffle_order) → Canal → Logstash → ElasticSearch → big-market-querys
```

---

## 9. 模块七：big-market-app（应用启动层）

**代码路径：** `big-market-app/src/main/java/cn/bugstack/`

### 功能说明
Spring Boot 应用启动入口，提供全局配置、切面（AOP）、及各中间件的 Bean 配置。

### 目录结构
```
big-market-app/
├── Application.java              # 启动入口（@SpringBootApplication）
├── aop/
│   └── RateLimiterAOP.java       # 接口限流切面（Guava RateLimiter + 黑名单）
└── config/
    ├── DCCValueBeanFactory.java  # DCC 动态配置中心（Zookeeper 监听 + Bean 注入）
    ├── DataSourceConfig.java     # 数据源配置（支持分库分表）
    ├── RedisClientConfig.java    # Redisson 客户端配置
    ├── ThreadPoolConfig.java     # 线程池配置
    ├── GuavaConfig.java          # Guava 缓存配置
    ├── Retrofit2Config.java      # Retrofit2 HTTP 客户端配置（调用 OpenAI 接口）
    ├── XxlJobAutoConfig.java     # XxlJob 定时任务配置
    ├── ZooKeeperClientConfig.java # ZooKeeper 客户端配置
    └── PrometheusConfiguration.java # Prometheus 监控配置
```

### 关键配置说明

**RateLimiterAOP（限流切面）：**
```java
// 工作原理：
// 1. 读取 @RateLimiterAccessInterceptor 注解参数（key、permitsPerSecond、blacklistCount、fallbackMethod）
// 2. 检查 DCC 开关（rateLimiterSwitch=open 时启用）
// 3. 从 Guava Cache（1分钟过期）获取 userId 的 RateLimiter
// 4. tryAcquire() 失败则计数，超过 blacklistCount 次加入黑名单（24h）
// 5. 走 fallbackMethod 返回降级响应
```

**DCCValueBeanFactory（动态配置）：**
```java
// 工作原理：
// 1. 扫描所有 Bean，找有 @DCCValue 注解的字段
// 2. 在 Zookeeper /big-market-dcc/config/{key} 节点写入默认值
// 3. 监听节点变更事件（CuratorCache），有变更时用反射更新字段值
// 目前支持的配置项：
//   - degradeSwitch: open/close  （熔断降级开关）
//   - rateLimiterSwitch: open/close（限流开关）
```

---

## 10. 核心流程走向

### 10.1 抽奖主流程

```
【用户请求】
  ↓
RaffleActivityController#draw
  ↓ ① 限流检查（RateLimiterAOP）
  ↓ ② 降级检查（DCCValue + Hystrix）
  ↓ ③ 参数校验
  ↓
AbstractRaffleActivityPartake#createOrder（创建抽奖单）
  ├── 查活动信息（IActivityRepository）
  ├── 校验状态/日期
  ├── 查已有未使用单（幂等）
  ├── 扣减账户额度（总/月/日 三级账户）
  └── 事务保存聚合（user_raffle_order + 更新账户）
  ↓
AbstractRaffleStrategy#performRaffle（执行抽奖）
  ├── 责任链（BlackList → Weight → Default）
  │     └── DefaultLogicChain → StrategyDispatch.getRandomAwardId（Redis取随机奖品）
  └── 决策树（Lock → Stock → LuckAward）
        ├── RuleLock：次数不足 → TAKE_OVER（拦截）
        ├── RuleStock：Redis decrement 扣库存 → 写延迟队列
        └── RuleLuckAward：兜底奖品
  ↓
AwardService#saveUserAwardRecord（保存中奖记录）
  └── 事务保存（user_award_record + task 记录）
  ↓
更新抽奖单状态（已使用）
  ↓
【返回奖品信息给用户】

异步流程（MQ + Task 补偿）：
  SendMessageTaskJob → 扫描 task 表 → 发 MQ(send_award)
  SendAwardCustomer  → 消费 MQ → AwardService#distributeAward → 发放具体奖品
```

### 10.2 活动下单充值流程

```
RaffleActivityController#creditPayExchangeSku（积分兑换）
  ↓
AbstractRaffleActivityAccountQuota#createOrder(SkuRechargeEntity)
  ├── 查询 SKU / 活动 / 次数配置
  ├── 检查积分余额（CreditRepository#queryUserCreditAccountAmount）
  ├── 活动责任链校验（ActivityBase → ActivitySkuStock）
  │     └── ActivitySkuStock：Redis decrement SKU 库存
  ├── 构建订单聚合
  └── CreditPayTradePolicy#trade（积分支付）
        ├── 事务保存（raffle_activity_order + user_credit_order + 账户变更）
        └── 发 MQ（credit_adjust_success）

CreditAdjustSuccessCustomer → 消费 MQ → 更新活动订单状态（已支付）→ 充值账户额度
```

### 10.3 行为返利流程

```
RaffleActivityController#calendarSignRebate（日历签到返利）
  ↓
BehaviorRebateService#createOrder(BehaviorEntity)
  ├── 查询返利配置（DailyBehaviorRebateVO）
  ├── 构建返利订单（含幂等 bizId = userId_rebateType_outBusinessNo）
  ├── 事务保存（user_behavior_rebate_order + task 记录）
  └── 发 MQ（send_rebate）

RebateMessageCustomer → 消费 MQ
  ├── sku  类型 → raffleActivityAccountQuotaService.createOrder（直接充值次数）
  └── integral 类型 → creditAdjustService.createOrder（增加积分）
```

### 10.4 奖品发放流程

```
SendAwardCustomer（MQ 消费者）
  └── 接收 send_award 消息
  ↓
AwardService#distributeAward(DistributeAwardEntity)
  ├── 查询奖品 key（award 表 award_key 字段）
  └── 根据 key 路由到 IDistributeAward 实现
        ├── user_credit_random → UserCreditRandomAward
        │     └── 生成随机积分 → CreditAdjustService#createOrder（FORWARD）
        └── openai_account → OpenAIAccountAdjustQuotaAward
              └── AwardPort → Retrofit2 → OpenAI 账户充值 API
```

### 10.5 积分兑换抽奖次数流程

```
【用户点击兑换】
  ↓
RaffleActivityController#creditPayExchangeSku
  → createOrder(SkuRechargeEntity{type=credit_pay_trade})
        → CreditPayTradePolicy：
              ① 保存活动订单（pending 状态）
              ② 创建积分扣减订单（CreditAdjustService，REVERSE）
                   → 事务：扣积分 + 写任务记录

              ③ SendMessageTaskJob 扫任务 → 发 MQ(credit_adjust_success)
  ↓
CreditAdjustSuccessCustomer → 消费 MQ
  → raffleActivityAccountQuotaService.updateOrder(DeliveryOrderEntity)
        → 更新活动订单状态（已完成）→ 充值账户额度（+N 次抽奖次数）
```

---

## 11. 设计亮点总结

### 🎯 亮点一：O(1) 概率抽奖算法

**位置：** `O1Algorithm#armoryAlgorithm` / `O1Algorithm#dispatchAlgorithm`

将所有奖品按概率映射到一个 `List<Integer>`（空间换时间），抽奖时生成 `[0, range)` 随机数直接 `list.get(index)` 命中奖品，时间复杂度 O(1)。同时提供 O(logN) 的区间二分算法（`OLogNAlgorithm`）作为备选，并支持多线程并行装配。

### 🔗 亮点二：责任链 + 决策树的双层规则引擎

**位置：** `AbstractRaffleStrategy#performRaffle`

- **责任链（前置）**：处理抽奖前的用户级规则（黑名单、权重分段），命中后可直接返回结果，短路后续链路。
- **决策树（后置）**：处理抽奖后的奖品级规则（次数锁、库存扣减、兜底），规则配置存储于数据库规则树表，支持动态编排。

两层解耦，扩展新规则只需新增实现类，无需修改主流程代码。

### 📦 亮点三：MQ + Task 表保障消息最终一致性

**位置：** `AwardService`, `BehaviorRebateService`, `CreditAdjustService` + `SendMessageTaskJob`

采用 **Outbox 模式（发件箱模式）**：
1. 业务操作与 task 记录**同事务**写入数据库
2. 定时任务扫描 task 表，对 `create/fail` 状态的消息进行 MQ 补偿发送
3. MQ 消费端幂等处理（通过 bizId / orderId 唯一索引防重）

保障即使 MQ Broker 临时不可用，消息也不会丢失。

### ⚡ 亮点四：Redis 库存扣减 + 延迟队列异步落库

**位置：** `RuleStockLogicTreeNode`, `ActivitySkuStockActionChain`, `UpdateAwardStockJob`, `UpdateActivitySkuStockJob`

- 抽奖时只操作 **Redis** 中的库存（原子 decrement），极速响应
- 扣减后将 `(strategyId, awardId)` 写入 **Redis 延迟队列**
- 定时任务消费队列，**批量** 更新数据库，大幅降低数据库写入压力
- SKU 库存耗尽时发 MQ，消费端清除 Redis 缓存，防止后续无效请求

### 🎛️ 亮点五：基于 Zookeeper 的 DCC 动态配置中心

**位置：** `DCCValueBeanFactory`, `@DCCValue`

字段加 `@DCCValue("key:defaultValue")` 注解即可实现配置动态下发，无需重启服务。通过 Curator 监听 ZK 节点变化，反射更新 Bean 字段。支持：
- `degradeSwitch`：一键开启/关闭全局熔断降级
- `rateLimiterSwitch`：一键开启/关闭全局限流

### 🛡️ 亮点六：多层限流 + 熔断降级

**位置：** `RateLimiterAOP`, `RaffleActivityController`

- **AOP 限流**：基于 Guava RateLimiter，按用户 ID 独立限速，超频自动加黑名单（24h）
- **熔断降级**：使用 Hystrix `@HystrixCommand`，系统过载时走 fallback 方法返回友好响应
- **DCC 开关**：运营人员可通过 HTTP 接口实时切换限流/降级开关

### 🔀 亮点七：分库分表 + 分布式路由

**位置：** `DataSourceConfig`, `db-router` 中间件

用户相关的核心业务表按 userId 进行分库分表，读写路由由 `IDBRouterStrategy` 管理，分散单库压力。`SendMessageTaskJob` 中需要按库分开查询 task 表（`exec_db01` / `exec_db02`），防止跨库查询。

### 📊 亮点八：运营大盘 + 监控

- **ElasticSearch + Canal + Logstash**：MySQL binlog 实时同步到 ES，支持用户抽奖数据快速检索
- **Prometheus + Grafana**：接口性能监控（`@Timed` 注解上报指标）
- **ERP 运营接口**：`ErpOperateController` 提供活动状态管理和抽奖数据查询

---

## 12. 技术栈一览

| 技术 | 版本/说明 | 用途 |
|------|-----------|------|
| Spring Boot | 2.x | 应用框架 |
| MyBatis | 3.x | ORM 持久化 |
| Redis / Redisson | 3.x | 缓存、分布式锁、延迟队列 |
| RabbitMQ | - | 异步消息、事件驱动 |
| XxlJob | - | 分布式定时任务调度 |
| Apache Dubbo | 3.x | RPC 远程调用 |
| Apache ZooKeeper / Curator | - | DCC 动态配置中心 |
| ElasticSearch | 7.x | 运营数据检索 |
| Canal + Logstash | - | MySQL 数据同步到 ES |
| Prometheus + Grafana | - | 应用监控 |
| Hystrix | Netflix | 熔断降级 |
| Guava RateLimiter | Google | 接口限流 |
| JWT（auth0 / jjwt）| - | Token 鉴权 |
| Retrofit2 | - | HTTP 客户端（调用外部服务）|
| Lombok | - | 代码简化 |
| db-router | 自研中间件 | 分库分表路由 |

---

## 附录：学习建议路径

1. **从简单到复杂**：先看 `strategy` 领域（纯算法，无外部依赖），理解责任链和决策树的设计
2. **跟着接口走**：从 `RaffleStrategyController#randomRaffle` 开始，跟踪完整的调用链路到数据库
3. **理解 DDD**：每个领域都有独立的 repository 接口，infrastructure 层实现不影响领域层的逻辑
4. **关注设计模式**：模板方法（Abstract* 类）、策略模式（ITradePolicy / IDistributeAward）、工厂模式（DefaultChainFactory / DefaultTreeFactory）
5. **完整业务链路**：最后跟踪 `draw` 接口的完整流程，理解各领域如何协作完成一次完整的抽奖
