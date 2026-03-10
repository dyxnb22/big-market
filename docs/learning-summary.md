# big-market 项目全量遍历学习总结

> 本文档基于对 `dyxnb22/big-market` 仓库的全量代码遍历生成，涵盖架构设计、业务链路、持久层、接口层、工程关注项及优化建议。

---

## 1. 目录与模块结构概览

### 1.1 整体 Maven 多模块结构

```
big-market/                             ← 父 POM（groupId: cn.bugstack, version: 1.1）
├── big-market-api/                     ← 接口定义层（Dubbo 服务接口 + DTO）
├── big-market-app/                     ← 应用启动层（启动类 + Spring 配置 + AOP）
├── big-market-domain/                  ← 领域层（业务核心，DDD 聚合/实体/值对象/服务）
├── big-market-infrastructure/          ← 基础设施层（DB/Redis/MQ/ES 适配器实现）
├── big-market-trigger/                 ← 触发层（HTTP Controller + MQ Listener + Job + RPC）
├── big-market-types/                   ← 通用类型（枚举/异常/注解/事件基类）
└── big-market-querys/                  ← 查询侧（CQRS 读侧，ES 查询适配）
```

### 1.2 各模块职责说明

| 模块 | 关键路径 | 核心职责 |
|------|----------|----------|
| `big-market-api` | `cn.bugstack.trigger.api` | 定义 Dubbo/HTTP 可共用的服务接口（`IRaffleActivityService`、`IRaffleStrategyService`、`IRebateService`、`IDCCService`、`IErpOperateService`） + DTO/Request/Response 对象 |
| `big-market-app` | `cn.bugstack` | Spring Boot 启动入口 `Application.java`；注册所有 Spring/AOP/Dubbo 开关；提供 Config Bean（Redis、线程池、数据源、ZooKeeper、XXL-Job、Retrofit2、Prometheus、DCC）；限流 AOP |
| `big-market-domain` | `cn.bugstack.domain` | DDD 领域层，包含 `strategy`、`activity`、`award`、`credit`、`rebate`、`task`、`auth` 七大业务域；只依赖 `big-market-types`，通过 Repository 接口隔离持久化 |
| `big-market-infrastructure` | `cn.bugstack.infrastructure` | 实现 domain 中的 Repository 接口；包含 MyBatis DAO、Redis（Redisson）、MQ 发布者、ElasticSearch、第三方 HTTP 网关（Retrofit2）等 |
| `big-market-trigger` | `cn.bugstack.trigger` | HTTP REST Controller（4 个）、RabbitMQ Consumer（4 个）、XXL-Job 定时任务（3 个）、Dubbo RPC 服务端（`RebateServiceRPC`） |
| `big-market-types` | `cn.bugstack.types` | 跨模块公共类：`AppException`、`ResponseCode`（错误码枚举）、`@DCCValue`、`@RateLimiterAccessInterceptor`、`BaseEvent`、`Constants` |
| `big-market-querys` | `cn.bugstack.querys` | CQRS 读侧，封装 ES 查询仓储接口（`IESUserRaffleOrderRepository`），与写侧完全隔离 |

### 1.3 领域子模块结构（以 strategy 为例）

```
domain/strategy/
├── model/
│   ├── entity/           ← 实体（RaffleFactorEntity, StrategyAwardEntity...）
│   ├── valobj/           ← 值对象（RuleWeightVO, RuleLogicCheckTypeVO...）
│   └── aggregate/        ← 聚合根
├── repository/           ← 仓储接口（IStrategyRepository）
└── service/
    ├── armory/           ← 策略装配（StrategyArmoryDispatch + 算法 O1/OLogN）
    ├── raffle/           ← 抽奖实现（DefaultRaffleStrategy）
    └── rule/
        ├── chain/        ← 责任链（黑名单/权重/默认）
        └── tree/         ← 决策树（次数锁/库存/兜底奖）
```

---

## 2. 核心启动方式和配置体系

### 2.1 启动入口

**文件**：`big-market-app/src/main/java/cn/bugstack/Application.java`

```java
@SpringBootApplication
@EnableScheduling           // 开启 Spring 定时任务
@EnableDubbo                // 开启 Dubbo 服务注册
@ImportResource("classpath:spring-config.xml")   // 导入 Spring XML 配置（含 Token Map）
@EnableAspectJAutoProxy(proxyTargetClass = true) // 强制 CGLib 代理
public class Application { ... }
```

### 2.2 配置文件体系

| 文件 | 路径 | 说明 |
|------|------|------|
| `application.yml` | `big-market-app/src/main/resources/` | 主配置，激活 Profile：`spring.profiles.active=dev` |
| `application-dev.yml` | 同上 | 开发环境：端口 8098，RabbitMQ/Redis/MySQL/Dubbo/Nacos/ZooKeeper/XXL-Job/监控 配置 |
| `application-test.yml` | 同上 | 测试环境配置 |
| `application-prod.yml` | 同上 | 生产环境配置 |
| `logback-spring.xml` | 同上 | 日志配置（控制台 + INFO 滚动文件 + ERROR 滚动文件，15 天保留，单文件 100 MB） |
| `mybatis-config.xml` | `resources/mybatis/config/` | MyBatis 全局配置 |
| `spring-config.xml` | `resources/` | Spring XML Bean 定义（Token 白名单 Map） |
| `spring-config-token.xml` | `resources/spring/` | AppId-Token 映射配置 |
| `mybatis/mapper/mysql/*.xml` | 同上 | 30 张表的 MyBatis Mapper XML |
| `mybatis/mapper/elasticsearch/*.xml` | 同上 | ES JDBC Mapper XML |

### 2.3 关键中间件配置

- **多数据源路由**（分库分表）：`mini-db-router`，2 库（db01/db02）× 4 表，路由键 `userId`；公共库 db00 不分片。
- **Redis**：Redisson，host 可配置，连接池 10，`IRedisService` 封装原子操作/阻塞队列/延迟队列。
- **Dubbo**：3.0.9，注册中心 Nacos（可切 ZooKeeper/multicast），自动扫描 `cn.bugstack.trigger.api`。
- **ZooKeeper**（DCC）：可选开关 `zookeeper.sdk.config.enable`，用于动态配置下发，通过 `DCCValueBeanFactory` 在 Bean 初始化后注入 `@DCCValue` 注解字段。
- **XXL-Job**：分布式定时任务，Admin 地址可配置，执行器名 `big-market-job`。
- **Prometheus + Grafana**：通过 `management.endpoints.web.exposure.include=*` 暴露所有 Actuator 端点（含 `/actuator/prometheus`）；`PrometheusConfiguration` 注册 `TimedAspect`/`CountedAspect`，支持 `@Timed`/`@Counted` 埋点；Grafana 数据源配置见 `docs/dev-ops/grafana/provisioning/datasources/`，Prometheus 抓取配置见 `docs/dev-ops/prometheus/`。
- **外部 HTTP 网关**：Retrofit2 调用外部接口（如 OpenAI 配额），由 `Retrofit2Config` 构建。

---

## 3. 主要业务模块与代码主干链路

### 3.1 七大业务域

| 领域 | 核心服务类 | 职责 |
|------|------------|------|
| `strategy` | `DefaultRaffleStrategy` | 抽奖策略计算（责任链 + 决策树） |
| `activity` | `RaffleActivityPartakeService`、`RaffleActivityAccountQuotaService` | 参与抽奖活动、账户额度管理（总/月/日三级） |
| `award` | `AwardService` | 奖品发放（分发到不同 `IDistributeAward` 实现） |
| `credit` | `CreditAdjustService` | 用户积分账户充值/扣减 |
| `rebate` | `BehaviorRebateService` | 行为返利（签到等行为触发积分/抽奖次数奖励） |
| `task` | `TaskService` | 扫表补偿任务，确保 MQ 消息至少发送一次 |
| `auth` | `AuthService` | JWT 鉴权（Token 签发与验证） |

### 3.2 核心链路：一次完整抽奖流程

```
HTTP POST /api/v1/raffle/activity/draw
         │
         ▼
RaffleActivityController.draw()
  1. JWT Token 验证（authService.checkToken）
  2. 降级开关检查（@DCCValue degradeSwitch）
  3. 限流检查（@RateLimiterAccessInterceptor）
  4. Hystrix 熔断（@HystrixCommand）
         │
         ▼
IRaffleActivityPartakeService.createOrder()        [activity 域]
  → 校验总账户/月账户/日账户额度
  → 构建 CreatePartakeOrderAggregate
  → IActivityRepository.saveCreatePartakeOrderAggregate()
    → TransactionTemplate：
       insert user_raffle_order（分库分表）
       update/insert raffle_activity_account（总额度）
       update/insert raffle_activity_account_month（月额度）
       update/insert raffle_activity_account_day（日额度）
         │
         ▼
IRaffleStrategy.performRaffle()                    [strategy 域]
  → AbstractRaffleStrategy.performRaffle()
    Step 1：责任链（DefaultChainFactory）
      → BlackListLogicChain（黑名单直接返回）
      → RuleWeightLogicChain（积分阈值权重抽奖）
      → DefaultLogicChain（O1/OLogN 随机算法）
    Step 2：决策树（DefaultTreeFactory）
      → RuleLockLogicTreeNode（次数锁：N 次后才可得）
      → RuleStockLogicTreeNode（库存扣减，写延迟队列）
      → RuleLuckAwardLogicTreeNode（兜底奖品）
         │
         ▼
IAwardService.saveUserAwardRecord()                [award 域]
  → IActivityRepository → insert user_award_record + task（同一事务）
  → EventPublisher.publish(send_award topic)       [异步 MQ]
         │
         ▼
[异步] SendAwardCustomer（MQ Consumer）
  → IAwardService.distributeAward()
    → IDistributeAward 策略模式：
      UserCreditRandomAward（积分随机发放）
      OpenAIAccountAdjustQuotaAward（OpenAI 配额充值）
```

### 3.3 策略装配流程（缓存预热）

```
GET /api/v1/raffle/activity/armory?activityId=xxx
  → IActivityArmory.assembleActivitySkuByActivityId()
    → 查询 raffle_activity_sku、raffle_activity、raffle_activity_count
    → 写入 Redis（SKU 库存 AtomicLong、活动信息）
  → IStrategyArmory.assembleLotteryStrategy()
    → 查询 strategy_award、strategy_rule
    → StrategyArmoryDispatch.armoryAlgorithm()：
        概率范围 ≤ 10000 → O1 算法（HashMap 散列表）
        概率范围 > 10000 → OLogN 算法（二分查找）
    → 缓存写入 Redis
```

### 3.4 行为返利链路

```
Dubbo RPC：RebateServiceRPC.rebate()
  → AppId/AppToken 鉴权（spring-config-token.xml 配置）
  → IBehaviorRebateService.createOrder()
    → 查询 daily_behavior_rebate 配置
    → 构建 BehaviorRebateOrderAggregate
    → IBehaviorRebateRepository.saveUserRebateRecord()
      → 同一事务写 user_behavior_rebate_order + task
      → EventPublisher.publish(send_rebate topic)
```

---

## 4. 持久层设计、数据库交互模式

### 4.1 分库分表架构

| 数据库 | 用途 | 分片规则 |
|--------|------|----------|
| `big_market` (db00) | 公共库：strategy/award/rule_tree/raffle_activity/rebate 配置表 | 不分片 |
| `big_market_01` (db01) | 用户数据分片库 1 | `userId` hash 路由 |
| `big_market_02` (db02) | 用户数据分片库 2 | `userId` hash 路由 |

每个分片库内再按 4 个逻辑表（`_000`~`_003`）分表，通过 `plus.gaga.middleware:db-router-spring-boot-starter` 中间件实现动态路由。

### 4.2 数据库表清单

| 表名 | 所在库 | 说明 |
|------|--------|------|
| `strategy` | db00 | 抽奖策略主表 |
| `strategy_award` | db00 | 策略奖品配置 |
| `strategy_rule` | db00 | 策略规则（黑名单/权重/树节点规则） |
| `rule_tree` / `rule_tree_node` / `rule_tree_node_line` | db00 | 决策树结构 |
| `award` | db00 | 奖品基础信息 |
| `raffle_activity` | db00 | 活动信息 |
| `raffle_activity_sku` | db00 | 活动 SKU（含库存） |
| `raffle_activity_count` | db00 | 活动次数配置 |
| `raffle_activity_stage` | db00 | 上架活动渠道/来源映射 |
| `daily_behavior_rebate` | db00 | 行为返利规则配置 |
| `raffle_activity_order` | db01/02 | 活动充值订单（分片） |
| `raffle_activity_account` | db01/02 | 用户总额度账户（分片） |
| `raffle_activity_account_month` | db01/02 | 用户月额度账户（分片） |
| `raffle_activity_account_day` | db01/02 | 用户日额度账户（分片） |
| `user_raffle_order` | db01/02 | 用户抽奖单（分片）—— ES 同步 |
| `user_award_record` | db01/02 | 用户获奖记录（分片） |
| `user_behavior_rebate_order` | db01/02 | 用户行为返利订单（分片） |
| `user_credit_account` | db01/02 | 用户积分账户（分片） |
| `user_credit_order` | db01/02 | 用户积分流水（分片） |
| `task` | db01/02 | MQ 补偿任务表（分片） |

**SQL 初始化脚本**：`docs/dev-ops/mysql/sql/`（`big_market.sql`、`big_market_01.sql`、`big_market_02.sql`、`init.sql`、`nacos.sql`、`xxl_job.sql`）

### 4.3 DAO 层设计

- 所有 DAO 接口位于 `big-market-infrastructure/src/main/java/cn/bugstack/infrastructure/dao/`，命名规范为 `IXxxDao`（MyBatis Mapper 接口）。
- PO（持久化对象）位于 `dao/po/`，与数据库字段一一对应。
- MyBatis XML Mapper 位于 `resources/mybatis/mapper/mysql/*.xml`，独立于 Java 代码。
- **双数据源配置**：`DataSourceConfig` 内部静态类分别配置 MySQL（`IDBRouterStrategy` 动态路由）和 ElasticSearch JDBC 数据源，各自独立的 `SqlSessionFactory`。

### 4.4 事务管理模式

采用 **编程式事务**（`TransactionTemplate`），在 Repository 实现类中手动控制事务边界，具体原因：
- 分库分表场景下跨库事务不可用 `@Transactional`；
- 细粒度控制回滚，`DuplicateKeyException` 触发幂等处理（抛 `AppException(INDEX_DUP)`）；
- 在分布式库路由之后执行事务，确保路由上下文正确。

典型写法：
```java
dbRouter.doRouter(userId);
transactionTemplate.execute(status -> {
    try {
        raffleActivityOrderDao.insert(...);
        raffleActivityAccountDao.updateAccountQuota(...);
        ...
        return 1;
    } catch (DuplicateKeyException e) {
        status.setRollbackOnly();
        throw new AppException(ResponseCode.INDEX_DUP.getCode(), e);
    }
});
dbRouter.clear();  // finally 块中清理路由上下文
```

### 4.5 Redis 缓存层

- 封装接口 `IRedisService`（实现类 `RedissonService`），提供：
  - `setValue` / `getValue` / `isExists`：常规 KV
  - `getAtomicLong` / `addAndGet` / `setAtomicLong`：原子计数（SKU 库存扣减）
  - `getBlockingQueue` / `addToDelayedQueue`：阻塞队列/延迟队列（库存更新异步写 DB）
  - `getLock`（RLock）：分布式锁（Job 防重复执行）
- Redis Key 常量统一定义在 `cn.bugstack.types.common.Constants.RedisKey`。

### 4.6 ElasticSearch 集成

- Canal 监听 MySQL binlog，将 `user_raffle_order`、`raffle_activity_order` 同步到 ES 索引（Canal Adapter 配置见 `docs/dev-ops/canal-adapter/`）。
- 读侧通过 ES JDBC（`x-pack-sql-jdbc`）+ MyBatis 查询，Mapper 接口位于 `infrastructure/elasticsearch/`，独立 SqlSessionFactory。
- CQRS 读侧接口：`big-market-querys` 模块的 `IESUserRaffleOrderRepository`。

---

## 5. Controller 层与 API 入口说明

### 5.1 HTTP REST Controller（`big-market-trigger/src/main/java/cn/bugstack/trigger/http/`）

#### RaffleActivityController
**路径**：`/api/v1/raffle/activity/`  
**注解**：`@RestController` + `@DubboService(version="1.0")`（HTTP + Dubbo 双协议）  
**设计权衡**：Controller 同时实现 API 接口并标注 `@DubboService`，减少了类文件数量，但也导致 HTTP 路由逻辑（`@RequestMapping`）与 RPC 服务定义耦合在同一类中。对于规模较大的系统，建议将 Dubbo Service 实现单独拆分，保持各层边界清晰；当前方案适合中小规模快速迭代。

| 方法 | HTTP | 接口路径 | 说明 |
|------|------|----------|------|
| `queryStageActivityId` | GET | `query_stage_activity_id` | 按渠道/来源查询上架活动 |
| `armory` | GET | `armory` | 活动+策略数据预热 |
| `draw` | POST | `draw` | 带 Token 的抽奖请求 |
| `draw` (无 Token) | POST | `draw` | 无 Token 抽奖（降级/测试） |
| `calendarSignRebate` | POST | `calendar_sign_rebate` | 日历签到返利 |
| `isCalendarSignRebate` | GET | `is_calendar_sign_rebate` | 查询是否已签到返利 |
| `queryUserActivityAccount` | POST | `query_user_activity_account` | 查询用户活动账户（总/月/日额度） |
| `querySkuProductListByActivityId` | GET | `query_sku_product_list_by_activity_id` | 查询活动 SKU 商品列表 |
| `creditPayExchangeSku` | POST | `credit_pay_exchange_sku` | 积分兑换活动次数 |
| `queryUserCreditAccount` | GET | `query_user_credit_account` | 查询用户积分账户 |
| `chargePaySuccess` | POST | `charge_pay_success` | 充值成功回调（模拟支付） |
| `queryUserOrderList` | POST | `query_user_order_list` | 查询用户订单列表（ES） |

**关键工程特性**：
- `@DCCValue("degradeSwitch:close")` 动态降级开关；
- `@RateLimiterAccessInterceptor` 限流（每秒 1 次，超限加黑名单，fallback 返回固定响应）；
- `@HystrixCommand` 熔断（部分接口使用）；
- 跨域：`@CrossOrigin("${app.config.cross-origin}")`（默认 `*`）；

#### RaffleStrategyController
**路径**：`/api/v1/raffle/strategy/`

| 方法 | HTTP | 接口路径 | 说明 |
|------|------|----------|------|
| `strategyArmory` | GET | `strategy_armory` | 策略装配（预热 Redis） |
| `queryRaffleAwardList` | POST | `query_raffle_award_list` | 查询策略奖品列表 |
| `queryRaffleStrategyRuleWeight` | POST | `query_raffle_strategy_rule_weight` | 查询权重规则 |
| `randomRaffle` | POST | `random_raffle` | 单纯策略抽奖（不含活动） |

#### DCCController
**路径**：`/api/v1/raffle/dcc/`  
动态配置更新接口，写 ZooKeeper 节点：

```bash
GET /api/v1/raffle/dcc/update_config?key=degradeSwitch&value=open
GET /api/v1/raffle/dcc/update_config?key=rateLimiterSwitch&value=close
```

#### ErpOperateController
**路径**：`/api/v1/raffle/erp/`  
ERP 运营后台接口（活动上架、库存设置等管理操作）。

### 5.2 Dubbo RPC 服务（`big-market-trigger/src/main/java/cn/bugstack/trigger/rpc/`）

| 实现类 | 接口 | 说明 |
|--------|------|------|
| `RebateServiceRPC` | `IRebateService` | 行为返利 RPC，含 AppId/AppToken 鉴权 |

注：`RaffleActivityController` 和 `RaffleStrategyController` 同时实现了 `IRaffleActivityService` / `IRaffleStrategyService` 接口，兼具 HTTP 和 Dubbo 服务能力。

### 5.3 统一响应结构

```java
// cn.bugstack.trigger.api.response.Response<T>
{
    "code": "0000",   // ResponseCode 枚举
    "info": "调用成功",
    "data": { ... }
}
```

---

## 6. 工程级关注项

### 6.1 异常处理

- 自定义异常：`cn.bugstack.types.exception.AppException`（含 `code` + `info`）；
- Controller 层 `try-catch` 捕获所有异常，返回 `ResponseCode.UN_ERROR`，避免异常栈泄漏到客户端；
- 特殊异常（`DuplicateKeyException`）在 Repository 层捕获并转换为 `INDEX_DUP` 业务异常，实现幂等保证；
- **⚠️ 缺失**：无全局 `@ControllerAdvice` 统一异常处理器，每个 Controller 方法单独 try-catch，存在冗余代码。

### 6.2 日志

- 框架：Logback（`logback-spring.xml`）；
- 输出：控制台 + INFO 滚动文件（`./data/log/log_info.log`）+ ERROR 滚动文件（`./data/log/log_error.log`）；
- 格式：`%d{yy-MM-dd.HH:mm:ss.SSS} [%-16t] %-5p %-22c{0}%X{ServiceId} -%X{trace-id} %m%n`（支持 MDC trace-id）；
- 保留策略：15 天，单文件最大 100 MB，总上限 10 GB；
- 使用 Lombok `@Slf4j`，`log.info/error` 链路追踪关键步骤。
- **⚠️ 缺失**：`%X{trace-id}` 占位符已在日志格式中声明，但未见统一的 TraceId 过滤器写入 MDC，分布式链路追踪未落地。

### 6.3 事务管理

- 采用**编程式事务**（`TransactionTemplate`）替代声明式 `@Transactional`（见第 4.4 节）；
- 分布式库路由上下文（`IDBRouterStrategy`）在事务提交后的 `finally` 块中通过 `dbRouter.clear()` 清理，防止 ThreadLocal 泄漏；
- 跨库写场景（如同时写公共库 + 用户分片库）无分布式事务，靠 task 表补偿机制保证最终一致性。

### 6.4 安全

- **JWT 鉴权**：`AuthService` 基于 `com.auth0:java-jwt` 实现 Token 签发与验证，Controller 中通过 `authService.checkToken(token)` 解析 userId；
- **Dubbo RPC 鉴权**：`RebateServiceRPC` 中通过 AppId + AppToken Map（配置在 `spring-config-token.xml`）校验调用方身份；
- **DCC 动态配置**：限流/降级开关通过 ZooKeeper 实时下发，防止高并发场景下服务雪崩；
- **限流**：Guava `RateLimiter`（`RateLimiterAOP`）按 userId 粒度限频，超限自动加 Guava Cache 黑名单（24 小时）；
- **熔断**：Hystrix（Netflix）对部分外部接口提供 fallback；
- **⚠️ 注意**：`app.config.cross-origin=*` 开发阶段全量跨域，生产环境应限制来源域名；`spring-config-token.xml` 中 AppToken 为明文，建议改为加密存储或接入 Nacos Config 加密方案（详见第 7.2 节安全优化建议）。

### 6.5 缓存

| 缓存类型 | 用途 | 实现 |
|----------|------|------|
| Redis AtomicLong | SKU 库存计数（原子扣减） | `IRedisService.addAndGet` |
| Redis Map | 抽奖策略散列表（O1 算法）| `IRedisService.setValue(key, map)` |
| Redis String | 活动/策略基础信息 | `IRedisService.setValue` |
| Redis BlockingQueue | SKU 库存消费队列（延迟写 DB）| `RBlockingQueue` |
| Redis DelayedQueue | 库存延迟更新 | `RDelayedQueue` |
| Redis Lock (RLock) | 分布式锁（Job 防重入）| `redissonClient.getLock` |
| Guava Cache | 限流 RateLimiter 对象缓存（1 min）| `CacheBuilder` |
| Guava Cache | 限流黑名单（24 h）| `CacheBuilder` |
| JVM 本地缓存 | 策略规则查询（部分场景）| Repository 内部 Map |

### 6.6 MQ 消息与最终一致性

项目使用 RabbitMQ 实现异步解耦，共 4 个 Topic：

| Topic | 发送时机 | 消费者 | 说明 |
|-------|----------|--------|------|
| `send_award` | 保存用户获奖记录时 | `SendAwardCustomer` | 触发发奖逻辑 |
| `send_rebate` | 保存返利订单时 | `RebateMessageCustomer` | 触发返利积分/次数发放 |
| `credit_adjust_success` | 积分调整完成时 | `CreditAdjustSuccessCustomer` | 通知积分变动 |
| `activity_sku_stock_zero` | SKU 库存清零时 | `ActivitySkuStockZeroCustomer` | 更新 SKU 库存状态 |

**可靠性保证**：
1. MQ 消息与业务订单在同一数据库事务内写入（`task` 表）；
2. `SendMessageTaskJob`（XXL-Job）定时扫表，将 `task.state=fail/init` 的消息重新发送；
3. Redisson 分布式锁防止多实例 Job 重复发送；
4. **⚠️ 消费端可靠性风险**：`SendAwardCustomer` 等消费者 catch 异常后不重新抛出，消息会被自动 ACK，导致异常情况下消息静默丢失（无重试、无 DLQ）；建议改为手动 ACK 模式 + 配置死信队列（DLQ），并在死信队列上增加告警（详见第 7.2 节第 3 条）。

### 6.7 定时任务（XXL-Job）

| Job 方法 | XXL-Job Name | 功能 |
|----------|--------------|------|
| `SendMessageTaskJob.exec_db01/02` | `SendMessageTaskJob_DB1/2` | 扫描 task 表补发 MQ，各分片库独立 Job |
| `UpdateActivitySkuStockJob.exec` | — | 消费 Redis BlockingQueue，将 SKU 库存写入 DB |
| `UpdateAwardStockJob.exec` | — | 消费 Redis 延迟队列，将奖品库存写入 DB |

所有 Job 使用 `@Timed` + `@XxlJob` 双注解，同时支持 Prometheus 指标上报。

---

## 7. 测试情况与建议优化点

### 7.1 现有测试情况

测试代码位于 `big-market-app/src/test/java/cn/bugstack/test/`，分三层：

| 测试包 | 测试类 | 测试内容 |
|--------|--------|----------|
| `domain/strategy` | `RaffleStrategyTest`、`LogicChainTest`、`LogicTreeTest`、`StrategyArmoryDispatchTest` | 策略装配、责任链、决策树单元测试 |
| `domain/activity` | `RaffleActivityAccountQuotaServiceTest`、`RaffleActivityPartakeServiceTest` | 活动账户、参与抽奖测试 |
| `domain/award` | `AwardServiceTest` | 奖品发放测试 |
| `domain/credit` | `CreditAdjustServiceTest` | 积分调整测试 |
| `domain/rebate` | `BehaviorRebateServiceTest` | 行为返利测试 |
| `infrastructure` | `AwardDaoTest`、`RaffleActivityDaoTest`、`StrategyRepositoryTest` 等 | DAO 层集成测试 |
| `infrastructure/elasticsearch` | `ElasticSearchUserRaffleOrderDaoTest` | ES 查询测试 |
| `trigger` | `RaffleActivityControllerTest`、`RaffleStrategyControllerTest` | HTTP 接口集成测试 |

**特点**：以集成测试为主，需要外部依赖（MySQL/Redis/RabbitMQ）；缺乏纯单元测试（Mock 隔离）。

### 7.2 建议优化点

#### 架构与设计

1. **增加 Application/Case 层**：Controller 直接串联多个 Domain 服务，如 `draw` 方法涉及 activity/strategy/award/rebate 四个域，建议增加应用服务层（UseCase）封装业务编排，降低 Controller 复杂度。
2. **统一全局异常处理**：添加 `@RestControllerAdvice` + `@ExceptionHandler`，消除每个 Controller 方法的 try-catch 冗余。

#### 安全（高优先级）

3. **⚠️【高优先级】生产环境 CORS 策略收紧**：当前 `app.config.cross-origin=*` 允许任意来源跨域请求，生产环境必须改为具体允许的域名白名单，防止 CSRF 攻击。
4. **⚠️【高优先级】AppToken 安全存储**：`spring-config-token.xml` 中 AppId/Token 明文硬编码在代码仓库中，存在凭据泄露风险；建议迁移至 Nacos Config（加密存储）或 HashiCorp Vault，并从版本控制中移除明文 Token。

#### 可靠性（高优先级）

5. **⚠️【高优先级】MQ 消费端手动 ACK + 死信队列**：`SendAwardCustomer`、`RebateMessageCustomer` 等消费者 catch 异常后不重新抛出，消息被自动 ACK 静默丢失，无法重试；建议改为手动 ACK 模式，消费失败时拒绝消息（`nack`），配合 RabbitMQ 死信队列（DLQ）和告警，确保消息不丢失。
6. **task 表失败监控告警**：`SendMessageTaskJob` 将失败任务重置为 fail 状态，建议增加 Prometheus 指标上报 fail 数量，并在超阈值时触发 Grafana 告警。

#### 可观测性

7. **TraceId 链路追踪**：日志格式已预留 `%X{trace-id}` 占位，建议添加 `TraceIdFilter`（OncePerRequestFilter）在请求进入时生成 UUID 写入 MDC，Dubbo 侧通过 Filter 传递，实现完整分布式链路追踪。
8. **线程池监控**：`ThreadPoolExecutor` 建议通过 Micrometer 上报队列深度/拒绝数等指标到 Prometheus，及时发现压力。

#### 性能

9. **缓存穿透防护**：`queryActivitySku` 等查询在 Redis Miss 时回源数据库，高并发下可能产生缓存穿透/击穿，建议加布隆过滤器或空值缓存。

#### 测试覆盖

10. **补充 Mock 单元测试**：引入 Mockito，为 Domain 层服务编写纯单元测试，解耦外部依赖，提升测试速度和稳定性。
11. **接口契约测试**：Dubbo RPC 接口建议添加消费端契约测试，防止接口变更导致的兼容性问题。

#### 代码质量

12. **Lombok + 反射性能**：`RateLimiterAOP.getAttrValue` 中使用反射逐 Field 查找，对高 QPS 接口有性能开销，可考虑通过 SpEL 或接口约束替代。
13. **分片表 Job 复制问题**：`SendMessageTaskJob` 中 `exec_db01`/`exec_db02` 代码完全重复，仅 DB Key 不同，建议抽取公共方法减少重复。

---

## 关键文件速查

| 关注点 | 文件路径 |
|--------|----------|
| 启动入口 | `big-market-app/src/main/java/cn/bugstack/Application.java` |
| 主配置 | `big-market-app/src/main/resources/application-dev.yml` |
| 日志配置 | `big-market-app/src/main/resources/logback-spring.xml` |
| 数据源配置 | `big-market-app/src/main/java/cn/bugstack/config/DataSourceConfig.java` |
| 限流 AOP | `big-market-app/src/main/java/cn/bugstack/aop/RateLimiterAOP.java` |
| DCC 动态配置 | `big-market-app/src/main/java/cn/bugstack/config/DCCValueBeanFactory.java` |
| 抽奖活动 Controller | `big-market-trigger/src/main/java/cn/bugstack/trigger/http/RaffleActivityController.java` |
| 策略 Controller | `big-market-trigger/src/main/java/cn/bugstack/trigger/http/RaffleStrategyController.java` |
| DCC Controller | `big-market-trigger/src/main/java/cn/bugstack/trigger/http/DCCController.java` |
| 返利 RPC | `big-market-trigger/src/main/java/cn/bugstack/trigger/rpc/RebateServiceRPC.java` |
| 发奖 MQ 消费者 | `big-market-trigger/src/main/java/cn/bugstack/trigger/listener/SendAwardCustomer.java` |
| 扫表补发 Job | `big-market-trigger/src/main/java/cn/bugstack/trigger/job/SendMessageTaskJob.java` |
| 抽奖策略抽象 | `big-market-domain/src/main/java/cn/bugstack/domain/strategy/service/AbstractRaffleStrategy.java` |
| 策略装配 | `big-market-domain/src/main/java/cn/bugstack/domain/strategy/service/armory/StrategyArmoryDispatch.java` |
| 活动仓储实现 | `big-market-infrastructure/src/main/java/cn/bugstack/infrastructure/adapter/repository/ActivityRepository.java` |
| Redis 封装 | `big-market-infrastructure/src/main/java/cn/bugstack/infrastructure/redis/RedissonService.java` |
| MQ 发布者 | `big-market-infrastructure/src/main/java/cn/bugstack/infrastructure/event/EventPublisher.java` |
| 错误码枚举 | `big-market-types/src/main/java/cn/bugstack/types/enums/ResponseCode.java` |
| 自定义异常 | `big-market-types/src/main/java/cn/bugstack/types/exception/AppException.java` |
| SQL 初始化 | `docs/dev-ops/mysql/sql/big_market.sql` 等 |
| Docker 环境 | `docs/dev-ops/docker-compose-environment.yml` |
