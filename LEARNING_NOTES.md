# big-market 大营销系统 — 全量代码学习笔记

> 版本：v1.1 | Spring Boot 2.7.12 | 生成于 2026-03-10
>
> 本文档对仓库 **dyxnb22/big-market** 做全量遍历，涵盖模块职责、启动方式、配置体系、核心业务链路、数据层、API 层、横切关注点、测试覆盖以及风险改进建议，所有分析均附关键文件路径与类名，便于快速溯源。

---

## 目录

1. [仓库 / 模块结构与职责](#1-仓库--模块结构与职责)
2. [构建与启动](#2-构建与启动)
3. [配置体系](#3-配置体系)
4. [核心业务领域与请求链路](#4-核心业务领域与请求链路)
5. [数据层设计](#5-数据层设计)
6. [API 层设计](#6-api-层设计)
7. [横切关注点](#7-横切关注点)
8. [测试覆盖](#8-测试覆盖)
9. [风险与改进建议](#9-风险与改进建议)

---

## 1. 仓库 / 模块结构与职责

项目采用 **DDD（领域驱动设计）** 多模块分层架构，共 7 个 Maven 子模块：

```
big-market/                         ← 父 POM（v1.1）
├── big-market-types/               ← 公共类型（枚举/注解/异常/事件基类）
├── big-market-api/                 ← API 接口定义（Dubbo 接口 + Request/Response DTO）
├── big-market-domain/              ← 领域层（业务核心逻辑，无基础设施依赖）
├── big-market-infrastructure/      ← 基础设施层（数据库/缓存/消息/ES 实现）
├── big-market-trigger/             ← 触发层（HTTP Controller / 消息监听 / 定时任务）
├── big-market-querys/              ← 查询层（CQRS 读侧，ElasticSearch 查询）
└── big-market-app/                 ← 应用启动层（Spring Boot 入口 + 配置文件）
```

### 各模块职责

| 模块 | 关键路径 | 职责 |
|------|----------|------|
| **types** | `cn.bugstack.types` | 全局常量、响应码枚举、自定义注解、`AppException`、事件基类 |
| **api** | `cn.bugstack.trigger.api` | Dubbo 服务接口定义（`IRaffleStrategyService` / `IRaffleActivityService` 等）、所有入参 / 出参 DTO |
| **domain** | `cn.bugstack.domain.*` | 7 个子域（策略、活动、奖品、积分、返利、任务、认证），仅依赖 types；通过 repository 接口隔离基础设施 |
| **infrastructure** | `cn.bugstack.infrastructure` | 实现 domain 定义的 `repository` 接口；包含 MyBatis DAO、Redis（Redisson）、RabbitMQ 发布、ES 查询 |
| **trigger** | `cn.bugstack.trigger` | HTTP 控制器（同时作 Dubbo 服务实现）、消息监听器、XXL-Job 定时任务；协调多个领域完成业务链路 |
| **querys** | `cn.bugstack.querys` | CQRS 读侧，`IESUserRaffleOrderRepository` 封装 ES 查询接口 |
| **app** | `cn.bugstack` | `Application.java` 启动入口；`application*.yml` 全部配置文件 |

### 模块依赖关系（简化）

```
app
 └── trigger ──── domain ──── types
      ├── api           └── infrastructure
      └── querys
```

---

## 2. 构建与启动

### 构建

```bash
# 从项目根目录构建（需 JDK 8/11 + Maven 3.x）
mvn clean package -DskipTests

# 启动
java -jar big-market-app/target/big-market-app-1.1-SNAPSHOT.jar \
     --spring.profiles.active=dev
```

### 入口类

**文件：** `big-market-app/src/main/java/cn/bugstack/Application.java`

```java
@SpringBootApplication
@Configurable
@EnableScheduling                                   // 启用本地定时任务
@EnableDubbo                                        // 启用 Dubbo RPC
@ImportResource(locations = {"classpath:spring-config.xml"}) // 导入 XML Bean
@EnableAspectJAutoProxy(proxyTargetClass = true)    // 启用 AOP（限流等切面）
public class Application {
    public static void main(String[] args) {
        SpringApplication.run(Application.class);
    }
}
```

### 运行时依赖（中间件）

| 中间件 | 用途 | Dev 地址 |
|--------|------|----------|
| MySQL 8.x | 主存储（2 库 × 4 表） | `127.0.0.1:3306` |
| Redis（Redisson）| 策略/库存缓存 | `192.168.1.108:16379` |
| RabbitMQ | 事件解耦（奖品/积分/返利/SKU 归零） | `192.168.1.108:5672` |
| Nacos | Dubbo 注册中心 | `192.168.1.108:8848` |
| ElasticSearch | 抽奖订单查询（CQRS 读侧）| `192.168.1.109:9200` |
| Zookeeper（可选）| DCC 动态配置下发 | `192.168.1.108:2181` |
| XXL-Job | 分布式定时任务 | `192.168.1.108:9090` |
| Prometheus + Grafana | 监控指标采集 | — |

---

## 3. 配置体系

### Profile 切换

**文件：** `big-market-app/src/main/resources/application.yml`

```yaml
spring:
  profiles:
    active: dev   # 可选 dev / test / prod
```

### 关键配置项（application-dev.yml）

**文件：** `big-market-app/src/main/resources/application-dev.yml`

| 配置项 | 值 / 说明 |
|--------|-----------|
| `server.port` | `8098` |
| `server.tomcat.threads.max` | `150` |
| `server.tomcat.max-connections` | `200` |
| `app.config.api-version` | `v1`（接口路径前缀） |
| `app.config.cross-origin` | `*`（Dev 环境跨域放开） |
| `mini-db-router.jdbc.datasource.dbCount` | `2`（分库数） |
| `mini-db-router.jdbc.datasource.tbCount` | `4`（分表数） |
| `mini-db-router.jdbc.datasource.routerKey` | `userId`（路由字段） |
| `thread.pool.executor.config.core-pool-size` | `20` |
| `thread.pool.executor.config.max-pool-size` | `50` |
| `thread.pool.executor.config.block-queue-size` | `5000` |
| `spring.rabbitmq.topic.*` | 4 个 Topic：`activity_sku_stock_zero` / `send_award` / `send_rebate` / `credit_adjust_success` |
| `dubbo.registry.address` | `nacos://192.168.1.108:8848` |
| `zookeeper.sdk.config.enable` | `false`（可动态开启 DCC） |
| `gateway.config.enable` | `true`（外部网关开关） |
| `management.metrics.export.prometheus.enabled` | `true` |
| `logging.config` | `classpath:logback-spring.xml` |

### 动态配置（DCC）

- **注解：** `@DCCValue`（`big-market-types`），标注在 Spring Bean 字段上，值由 Zookeeper 节点动态注入。
- **接口：** `DCCController.GET /api/v1/raffle/dcc/update_config?key=&value=` 触发 ZK 节点写入。
- **文件：** `big-market-trigger/src/main/java/cn/bugstack/trigger/http/DCCController.java`

---

## 4. 核心业务领域与请求链路

### 4.1 领域总览

```
strategy  ──► 抽奖策略装配 & 执行（责任链 + 决策树）
activity  ──► 活动 SKU / 账户 / 订单 / 参与管理
award     ──► 奖品记录保存 & 分发
credit    ──► 积分账户调整
rebate    ──► 行为返利（签到等行为触发积分奖励）
task      ──► MQ 消息可靠发送（outbox 模式）
auth      ──► Token 签发 & 校验
```

### 4.2 主链路：用户参与活动抽奖（最核心）

```
HTTP POST /api/v1/raffle/activity/draw
         ↓
RaffleActivityController.draw()
  [1] IAuthService.checkToken(token)              ← 认证
  [2] IRaffleActivityPartakeService.createOrder() ← 创建抽奖参与单（校验活动/扣库存/扣配额）
        └── ActivityRepository：数据库事务（分库分表）
  [3] IRaffleStrategy.performRaffle()             ← 执行抽奖
        ├── AbstractRaffleStrategy.performRaffle()
        │     [3.1] raffleLogicChain()            ← 责任链前置规则
        │           → BlackListLogicChain         ← 黑名单直接返回兜底奖
        │           → RuleWeightLogicChain        ← 权重区间抽奖（O(1)/O(logN)）
        │           → DefaultLogicChain           ← 默认随机抽奖
        │     [3.2] raffleLogicTree()             ← 决策树后置规则
        │           → RuleLockLogicTreeNode       ← 累计抽奖次数解锁
        │           → RuleStockLogicTreeNode      ← Redis 原子扣减库存
        │           → RuleLuckAwardLogicTreeNode  ← 兜底奖
        └── (结果) RaffleAwardEntity
  [4] IAwardService.saveUserAwardRecord()         ← 保存奖品记录
        └── AwardRepository：写 DB + 写 outbox Task
  [5] 返回 ActivityDrawResponseDTO
         ↓
MQ 异步（SendAwardCustomer 消费 send_award 主题）
  → IAwardService.distributeAward()              ← 奖品分发
      ├── UserCreditRandomAward                  ← 积分随机奖励
      └── OpenAIAccountAdjustQuotaAward          ← OpenAI 额度奖励
```

**关键类：**
- `big-market-trigger/.../RaffleActivityController.java`
- `big-market-domain/.../strategy/service/AbstractRaffleStrategy.java`
- `big-market-domain/.../strategy/service/raffle/DefaultRaffleStrategy.java`
- `big-market-domain/.../activity/service/partake/RaffleActivityPartakeService.java`
- `big-market-domain/.../award/service/AwardService.java`

### 4.3 策略装配链路（初始化/预热）

```
GET /api/v1/raffle/strategy/strategy_armory?strategyId=100
         ↓
RaffleStrategyController.strategyArmory()
  [1] IStrategyArmory.assembleLotteryStrategy(strategyId)
        └── StrategyArmoryDispatch：
              - 查询策略奖品表
              - O(1) 算法：构建随机数 → 奖品ID 映射，写入 Redis
              - O(logN) 算法：构建权重累计数组，写入 Redis
```

### 4.4 行为返利链路

```
用户签到 → POST /api/v1/raffle/activity/calender_sign_rebate
         ↓
RaffleActivityController.calenderSignRebate()
  → IBehaviorRebateService.createOrder(BehaviorEntity)
      - 查询返利配置（DailyBehaviorRebate）
      - 生成返利订单 + outbox Task（写 DB）
  → MQ Topic: send_rebate
  → RebateMessageCustomer.listen()
      → IBehaviorRebateService.create() 幂等处理
  → MQ Topic: credit_adjust_success
  → CreditAdjustSuccessCustomer.listen()
      → ICreditAdjustService.adjustCredit() 积分到账
```

---

## 5. 数据层设计

### 5.1 分库分表

- **路由中间件：** `mini-db-router`（自研，基于 MyBatis 插件 + AOP）
- **路由字段：** `userId`（Hash 取模）
- **库表规格：** 2 库（`big_market_01` / `big_market_02`）× 4 表 = 8 个物理分片
- **默认库：** `db00`（`big_market`，存不按用户路由的全局数据）

### 5.2 实体 / PO 分层

| 层次 | 类 | 路径 |
|------|-----|------|
| 领域实体（Domain Entity）| `StrategyEntity`、`ActivityEntity`、`UserRaffleOrderEntity`… | `big-market-domain/.../model/entity/` |
| 值对象（Value Object）| `RuleWeightVO`、`UserRaffleOrderStateVO`… | `big-market-domain/.../model/valobj/` |
| 持久化对象（PO）| `Strategy`、`RaffleActivity`、`UserRaffleOrder`… | `big-market-infrastructure/.../dao/po/` |

**Domain 层与 PO 之间无直接依赖**，转换在 Repository 实现类中完成（手动 set 或 BeanUtils）。

### 5.3 DAO 接口（全量清单）

| DAO 接口 | 主要操作 |
|----------|----------|
| `IStrategyDao` | 策略查询 |
| `IStrategyAwardDao` | 策略奖品 CRUD |
| `IStrategyRuleDao` | 策略规则查询 |
| `IRaffleActivityDao` | 活动基础信息 |
| `IRaffleActivitySkuDao` | SKU 库存查询与扣减 |
| `IRaffleActivityStageDao` | 活动状态流转 |
| `IRaffleActivityAccountDao` | 用户活动总账户 |
| `IRaffleActivityAccountDayDao` | 用户每日账户 |
| `IRaffleActivityAccountMonthDao` | 用户每月账户 |
| `IRaffleActivityCountDao` | 活动次数配置 |
| `IRaffleActivityOrderDao` | 活动充值订单 |
| `IUserRaffleOrderDao` | 用户抽奖单 |
| `IAwardDao` | 奖品基础信息 |
| `IUserAwardRecordDao` | 用户奖品记录 |
| `IUserCreditAccountDao` | 用户积分账户 |
| `IUserCreditOrderDao` | 积分变动流水 |
| `IUserBehaviorRebateOrderDao` | 行为返利订单 |
| `IDailyBehaviorRebateDao` | 每日返利配置 |
| `IRuleTreeDao` / `IRuleTreeNodeDao` / `IRuleTreeNodeLineDao` | 规则树结构 |
| `ITaskDao` | outbox 消息任务 |

所有 DAO 均通过 MyBatis XML Mapper（`classpath:/mybatis/mapper/mysql/*.xml`）映射 SQL。

### 5.4 Redis 用法

- **实现：** `RedissonService`（`big-market-infrastructure/.../redis/`）
- **主要 Key 模式：**

| Key 模式 | 用途 |
|----------|------|
| `big_market_strategy_rate_table_#{strategyId}` | O(1) 随机表（Hash） |
| `big_market_strategy_rate_range_#{strategyId}` | 随机范围上限 |
| `big_market_award_count_#{strategyId}_#{awardId}` | 奖品库存（原子减） |
| `big_market_activity_sku_stock_count_#{sku}` | SKU 库存 |
| `big_market_user_raffle_count_#{userId}_#{strategyId}` | 用户抽奖次数（锁规则） |

---

## 6. API 层设计

### 6.1 控制器一览

| 控制器 | 文件 | 基础路径 | Dubbo 服务接口 |
|--------|------|----------|----------------|
| `RaffleStrategyController` | `trigger/http/` | `/api/v1/raffle/strategy/` | `IRaffleStrategyService` |
| `RaffleActivityController` | `trigger/http/` | `/api/v1/raffle/activity/` | `IRaffleActivityService` |
| `DCCController` | `trigger/http/` | `/api/v1/raffle/dcc/` | `IDCCService` |
| `ErpOperateController` | `trigger/http/` | — | `IErpOperateService` |

所有控制器同时声明了 `@DubboService(version="1.0")`，即 HTTP 与 Dubbo RPC 双协议暴露同一逻辑。

### 6.2 主要接口（RaffleActivityController）

| Method | 路径 | 功能 | 关键注解 |
|--------|------|------|----------|
| GET | `activity_armory` | 装配活动缓存 | — |
| POST | `draw` | **执行抽奖（主链路）** | `@RateLimiterAccessInterceptor` + `@HystrixCommand` |
| POST | `calender_sign_rebate` | 日历签到返利 | `@RateLimiterAccessInterceptor` |
| POST | `is_calender_sign_rebate` | 查询当日签到状态 | — |
| POST | `query_user_activity_account` | 查询账户余额/配额 | — |
| POST | `query_sku_product_list_by_activity_id` | 查询 SKU 商品列表 | — |
| POST | `credit_pay_exchange_sku` | 积分兑换 SKU | `@RateLimiterAccessInterceptor` |

### 6.3 统一响应格式

**文件：** `big-market-api/.../response/Response.java`

```json
{
  "code": "0000",
  "info": "调用成功",
  "data": { ... }
}
```

响应码定义见 `ResponseCode` 枚举（`big-market-types`），涵盖系统级（`0001`~`0008`）和业务级（`ERR_BIZ_*` / `ERR_CONFIG_*` / `ERR_CREDIT_*`）错误码。

### 6.4 参数校验与异常处理

- **校验方式：** 以业务代码手动校验为主（`StringUtils.isBlank`、对象空判断），少量 `AppException` 抛出。
- **异常捕获：** 各控制器方法 `try-catch`，捕获 `AppException` 返回对应业务错误码，捕获 `Exception` 返回通用 `UN_ERROR`。
- **熔断降级：** `@HystrixCommand(fallbackMethod = "drawError")` 对 `draw` 接口启用 Hystrix 熔断，降级时返回 `ResponseCode.HYSTRIX`。

---

## 7. 横切关注点

### 7.1 日志

- **框架：** Logback，配置文件 `classpath:logback-spring.xml`
- **使用：** Lombok `@Slf4j`，关键业务操作均有 `log.info`/`log.error` 打印 userId、strategyId 等关键字段。
- **级别：** `root: info`（生产建议配置 Dev 为 debug）。

### 7.2 限流

- **注解：** `@RateLimiterAccessInterceptor`（`big-market-types/.../annotations/`）
  - `permitsPerSecond`：令牌桶每秒颁发速率
  - `blacklistCount`：超限后加入黑名单的阈值
  - `fallbackMethod`：降级方法名
- **实现：** AOP 切面（`spring-config.xml` 引入），基于 Guava `RateLimiter` + Redis 黑名单计数。

### 7.3 事务

- 跨多表的写操作（如创建抽奖单：更新账户 + 写订单 + 写 Task）使用 Spring `@Transactional`。
- 分库分表下需通过 `mini-db-router` 的 `@DBRouter` 指定路由键，确保同一事务内所有操作落在同一分片。

### 7.4 缓存

- **Redis Redisson：** 策略随机表预热（`assembleLotteryStrategy`）、库存扣减（`decrStrategyAwardStockValue`）、SKU 库存、用户黑名单等均走 Redis。
- **本地缓存：** 部分枚举/规则树通过 `IStrategyRepository` 返回后在 `StrategyArmoryDispatch` 中保存到 Redis，无 Caffeine / Guava Cache 显式本地缓存。

### 7.5 消息（RabbitMQ）

| Topic | 生产者 | 消费者类 | 业务含义 |
|-------|--------|----------|----------|
| `send_award` | `AwardRepository` | `SendAwardCustomer` | 奖品发放异步处理 |
| `send_rebate` | `BehaviorRebateRepository` | `RebateMessageCustomer` | 返利订单创建通知 |
| `credit_adjust_success` | `CreditRepository` | `CreditAdjustSuccessCustomer` | 积分调整完成通知 |
| `activity_sku_stock_zero` | `ActivityRepository` | `ActivitySkuStockZeroCustomer` | SKU 库存耗尽通知 |

**可靠发送（outbox 模式）：**
1. 业务写 DB 同时写 `task` 表（状态 = `create`）。
2. `SendMessageTaskJob` 定时扫描 `task` 表，发送 MQ，更新状态为 `completed` / `fail`。

### 7.6 定时任务

| Job 类 | 注解 | 周期 | 功能 |
|--------|------|------|------|
| `UpdateAwardStockJob` | `@XxlJob` | 可配置 | 将 Redis 库存扣减队列同步回数据库 |
| `UpdateActivitySkuStockJob` | `@XxlJob` | 可配置 | 多线程 SKU 库存同步（线程池） |
| `SendMessageTaskJob` | `@XxlJob`（分 DB1/DB2） | 可配置 | outbox 消息扫描发送（Redisson 分布式锁） |

所有 Job 均支持本地 `@Scheduled` 注解与分布式 `@XxlJob` 注解双模式。

### 7.7 安全 / 认证

- **实现：** `AuthService`（`big-market-domain/.../auth/`），`IAuthService.checkToken(token)` 校验请求令牌。
- **应用：** `RaffleStrategyController.queryRaffleAwardListByToken`、`RaffleActivityController.draw` 等接口调用认证服务。
- **外部网关：** `gateway.config.enable = true` 时通过 `gateway.config.apiHost` 调用外部接口；通过 `big-market-appToken` 做签名校验（`GatewayConfig`）。

### 7.8 监控

- **Prometheus：** `management.metrics.export.prometheus.enabled: true`，通过 `/actuator/prometheus` 暴露指标。
- **自定义指标：** `@Timed`（Micrometer）标注在 Job 方法上，如 `SendMessageTaskJob_DB1`。
- **健康检查：** `/actuator/health`（显示详情）。

---

## 8. 测试覆盖

**测试根目录：** `big-market-app/src/test/java/cn/bugstack/`

### 测试类清单

| 测试类 | 覆盖域 |
|--------|--------|
| `ApiTest` | 基础接口烟测 |
| `ZookeeperTest` | ZK 动态配置 |
| **策略域** | |
| `StrategyArmoryDispatchTest` | 策略装配预热 |
| `RaffleStrategyTest` | 完整抽奖流程（含规则链/树） |
| `LogicChainTest` | 责任链各节点 |
| `LogicTreeTest` | 决策树各节点 |
| **活动域** | |
| `RaffleActivityPartakeServiceTest` | 活动参与单创建 |
| `RaffleActivityAccountQuotaServiceTest` | 配额扣减逻辑 |
| **奖品域** | |
| `AwardServiceTest` | 奖品记录 & 分发 |
| **积分域** | |
| `CreditAdjustServiceTest` | 积分调整 |
| **返利域** | |
| `BehaviorRebateServiceTest` | 行为返利创建 |
| **控制器** | |
| `RaffleStrategyControllerTest` | Strategy HTTP 接口 |
| `RaffleActivityControllerTest` | Activity HTTP 接口 |
| **基础设施** | |
| `StrategyRepositoryTest` | 策略仓储 |
| `RaffleActivityDaoTest` / `RaffleActivityOrderDaoTest` | 活动 DAO |
| `RaffleActivityAccountDayDaoTest` | 日账户 DAO |
| `AwardDaoTest` | 奖品 DAO |
| `RuleTreeNodeDaoTest` | 规则树节点 DAO |
| `ElasticSearchUserRaffleOrderDaoTest` | ES 查询 |

### 覆盖评估

- **覆盖面广：** 从 DAO 到 Service 到 Controller 均有测试类，主链路有集成测试。
- **类型以集成测试为主：** 大量测试直连 DB / Redis，需本地中间件环境，不适合 CI 无环境场景。
- **单元测试缺失：** 纯逻辑（责任链节点、算法、VO 构建等）未见 Mock-based 单元测试。
- **无覆盖率报告：** 未发现 JaCoCo 或 Surefire 覆盖率配置。

---

## 9. 风险与改进建议

### 9.1 安全风险

| 风险 | 描述 | 建议 |
|------|------|------|
| **硬编码凭证** | `application-dev.yml` 中 DB 密码（`123456`）、Redis/RabbitMQ 密码（`admin`）、`big-market-appToken` 明文存储 | 使用 Vault / Nacos 加密配置或环境变量注入 |
| **跨域全放开** | `cross-origin: '*'`（Dev 配置）若误用于 Prod 则存在 CSRF 风险 | Prod 配置明确指定允许域 |
| **Token 简单校验** | `IAuthService.checkToken` 的校验强度未知，需确保不可伪造 | 使用 JWT 并验签，设置合理过期时间 |

### 9.2 技术债

| 问题 | 位置 | 建议 |
|------|------|------|
| **Controller 过胖** | `RaffleActivityController` 同时注入 10+ 个 Service，承担过多协调逻辑 | 引入 Application/Case 层（作者注释已提到），将跨域编排从 Trigger 层下沉 |
| **缺少 Application 层** | 作者代码注释：`在不引用 application/case 层的时候，就需要让接口实现层来做领域的串联` | 增加 `big-market-application` 模块，封装跨域 Use Case |
| **集成测试依赖外部环境** | 测试类均需本地 MySQL/Redis/RabbitMQ | 增加 Testcontainers 或 H2 / embedded Redis 支持 CI |
| **DTO 手动转换** | Repository 实现中大量手动 `entity.setXxx(po.getXxx())` | 引入 MapStruct 减少样板代码并降低转换出错概率 |
| **FastJSON 版本** | FastJSON 2.0.28（历史上有多个 RCE 漏洞） | 升级到最新稳定版或替换为 Jackson / Gson |
| **Dubbo 与 HTTP 耦合** | Controller 同时实现 Dubbo 接口，导致 HTTP 参数绑定与 RPC 语义混用 | 分离 HTTP Controller 与 Dubbo Provider |
| **分布式锁粒度粗** | `SendMessageTaskJob` 每次执行均扫描整张 `task` 表 | 按 userId Hash 分片扫描，减少单次扫描量 |

### 9.3 性能隐患

| 隐患 | 描述 | 建议 |
|------|------|------|
| **Tomcat 连接数偏低** | `max-connections: 200`，`threads.max: 150` | 根据实际 QPS 压测后调整，或切换 Undertow |
| **Redis 单节点** | 配置仅单节点 Redis，无主从/哨兵/集群 | 生产环境使用 Redis Sentinel 或 Cluster |
| **库存 Redis 扣减无保护** | 极端情况下 Redis 宕机时库存扣减丢失 | 增加降级策略（回退到 DB 乐观锁） |
| **ES Driver 使用 SQL JDBC** | `org.elasticsearch.xpack.sql.jdbc.EsDriver` 为 X-Pack 商业驱动 | 评估是否需要替换为官方 Elasticsearch Java API Client（`elasticsearch-java`，7.15+ 推荐）|

### 9.4 可观测性改进

- 增加链路追踪（SkyWalking / Zipkin），打通从 HTTP → Dubbo → MQ 的全链路 TraceId。
- 关键业务指标（下单量、抽奖成功率、库存剩余）接入 Prometheus 自定义指标（`MeterRegistry`）。
- 日志增加结构化字段（MDC 写入 requestId / userId），便于 ELK 检索。

---

## 快速索引

| 需求 | 起点 |
|------|------|
| 看抽奖主流程 | `RaffleActivityController.draw()` → `AbstractRaffleStrategy.performRaffle()` |
| 看策略装配算法 | `StrategyArmoryDispatch.assembleLotteryStrategy()` → `O1Algorithm` / `OLogNAlgorithm` |
| 看责任链规则 | `DefaultChainFactory` → `BlackListLogicChain` → `RuleWeightLogicChain` → `DefaultLogicChain` |
| 看决策树规则 | `DefaultTreeFactory` → `RuleLockLogicTreeNode` → `RuleStockLogicTreeNode` |
| 看可靠消息 | `SendMessageTaskJob` → `ITaskService` → `ITaskDao` |
| 看限流 AOP | `@RateLimiterAccessInterceptor` 注解 → `spring-config.xml` 切面 Bean |
| 看分库分表路由 | `mini-db-router` 依赖 → `application-dev.yml` `mini-db-router` 段 |
| 看动态配置 | `@DCCValue` 注解 → `DCCController.updateConfig()` → Zookeeper |
