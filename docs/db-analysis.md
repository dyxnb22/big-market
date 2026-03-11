# big-market 数据库结构全面分析

> 适用于面试交流和项目技术文档。整理了 big_market、big_market_01/02 库的全部业务表，包含字段说明、索引设计、业务含义、ER 关系和优化建议。

---

## 一、数据库总览

| 数据库名 | 定位 | 主要表类型 |
|---|---|---|
| `big_market` | **公共配置库（非分片）** | 活动、策略、奖品、规则等配置类主数据 |
| `big_market_01` | **用户数据分片库 01** | 用户账户、订单、中奖记录等流水数据（4 个分片后缀 _000~_003） |
| `big_market_02` | **用户数据分片库 02** | 与 big_market_01 结构完全相同，水平扩展用途 |

---

## 二、`big_market` — 公共配置库

### 2.1 `award`（奖品表）

**业务含义**：抽奖系统中所有可发放奖品的主数据，每条记录对应一类奖品（如 OpenAI 使用次数、AI 模型权限）。

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | int unsigned | 自增主键 |
| `award_id` | int(8) | 业务奖品ID（内部流转标识） |
| `award_key` | varchar(32) | 奖品对接标识，对应具体发奖策略（如 `user_credit_random`、`openai_use_count`） |
| `award_config` | varchar(32) | 奖品配置参数（如积分随机范围 `1,100`、使用次数 `5`） |
| `award_desc` | varchar(128) | 奖品描述 |
| `create_time` | datetime | 创建时间 |
| `update_time` | datetime | 更新时间（自动 ON UPDATE） |

**索引**：
- `PRIMARY KEY (id)`
- `UNIQUE KEY uq_award_id (award_id)` — 保证奖品 ID 业务唯一性

**示例数据**：奖品包含随机积分（award_id=101）、OpenAI 各档使用次数（102~117）、AI 模型解锁（105~109）

---

### 2.2 `daily_behavior_rebate`（日常行为返利活动配置表）

**业务含义**：配置用户特定行为触发的返利规则，如每日签到或支付后可获得积分或活动次数。

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | int unsigned | 自增主键 |
| `behavior_type` | varchar(16) | 行为类型（`sign` 签到、`openai_pay` 支付） |
| `rebate_desc` | varchar(128) | 返利描述 |
| `rebate_type` | varchar(16) | 返利类型（`sku` 充值活动库存次数、`integral` 积分） |
| `rebate_config` | varchar(32) | 返利配置值（sku编号或积分数量） |
| `state` | varchar(12) | 状态（`open` 开启、`close` 关闭） |
| `create_time` | datetime | 创建时间 |
| `update_time` | datetime | 更新时间 |

**索引**：
- `PRIMARY KEY (id)`
- `KEY idx_behavior_type (behavior_type)` — 按行为类型快速查询

---

### 2.3 `raffle_activity`（抽奖活动表）

**业务含义**：抽奖活动的核心配置，定义活动时间窗口、绑定的抽奖策略和活动状态。

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | bigint unsigned | 自增主键 |
| `activity_id` | bigint(12) | 活动业务ID（全局唯一） |
| `activity_name` | varchar(64) | 活动名称 |
| `activity_desc` | varchar(128) | 活动描述 |
| `begin_date_time` | datetime | 活动开始时间 |
| `end_date_time` | datetime | 活动结束时间 |
| `strategy_id` | bigint(8) | 关联的抽奖策略ID（→ `strategy`） |
| `state` | varchar(8) | 活动状态（`create` 创建、`open` 开启、`close` 关闭） |
| `create_time` | datetime | 创建时间 |
| `update_time` | datetime | 更新时间 |

**索引**：
- `PRIMARY KEY (id)`
- `UNIQUE KEY uq_activity_id (activity_id)`
- `UNIQUE KEY uq_strategy_id (strategy_id)` — 活动与策略一对一绑定
- `KEY idx_begin_date_time (begin_date_time)`
- `KEY idx_end_date_time (end_date_time)` — 支持时间范围查询

---

### 2.4 `raffle_activity_count`（抽奖活动次数配置表）

**业务含义**：定义每种活动次数商品包的配额规格（总次数、日次数、月次数）。被 `raffle_activity_sku` 引用。

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | bigint unsigned | 自增主键 |
| `activity_count_id` | bigint(12) | 次数配置业务ID |
| `total_count` | int(8) | 总次数上限 |
| `day_count` | int(8) | 每日次数上限 |
| `month_count` | int(8) | 每月次数上限 |
| `create_time` | datetime | 创建时间 |
| `update_time` | datetime | 更新时间 |

**索引**：
- `PRIMARY KEY (id)`
- `UNIQUE KEY uq_activity_count_id (activity_count_id)`

---

### 2.5 `raffle_activity_sku`（活动SKU商品表）

**业务含义**：将活动×次数配置的组合抽象为一个可购买的 SKU 商品，管理库存数量与定价（积分）。

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | int unsigned | 自增主键 |
| `sku` | bigint(12) | 商品SKU编号（全局唯一） |
| `activity_id` | bigint(12) | 关联活动ID（→ `raffle_activity`） |
| `activity_count_id` | bigint(12) | 关联次数配置ID（→ `raffle_activity_count`） |
| `stock_count` | int(11) | 总库存 |
| `stock_count_surplus` | int(11) | 剩余库存（实时扣减，通过 Redis 缓存加速） |
| `product_amount` | decimal(10,2) | 商品积分价格 |
| `create_time` | datetime | 创建时间 |
| `update_time` | datetime | 更新时间 |

**索引**：
- `PRIMARY KEY (id)`
- `UNIQUE KEY uq_sku (sku)`
- `KEY idx_activity_id_activity_count_id (activity_id, activity_count_id)` — 联合索引，支持按活动查询可用商品

---

### 2.6 `raffle_activity_stage`（活动展台/上架表）

**业务含义**：控制活动在不同渠道和来源下的展示状态（上架/下架），相当于活动的"橱窗管理"。

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | int unsigned | 自增主键 |
| `channel` | varchar(8) | 渠道标识（如 `c01`） |
| `source` | varchar(8) | 来源标识（如 `s01`） |
| `activity_id` | bigint(12) | 关联活动ID（→ `raffle_activity`） |
| `state` | varchar(8) | 上架状态（`create`、`active`、`expire`） |
| `create_time` | datetime | 创建时间 |
| `update_time` | datetime | 更新时间 |

**索引**：`PRIMARY KEY (id)`

---

### 2.7 规则引擎三表（`rule_tree` / `rule_tree_node` / `rule_tree_node_line`）

**业务含义**：实现可配置的**规则决策树**，用于抽奖过程中的多规则组合过滤（黑名单过滤 → 权重判断 → 库存扣减 → 兜底奖励），通过 DAG（有向无环图）结构描述规则执行流程。

#### `rule_tree`（规则树根表）

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | bigint unsigned | 自增主键 |
| `tree_id` | varchar(32) | 规则树业务ID（如 `tree_lock_1`） |
| `tree_name` | varchar(64) | 规则树名称 |
| `tree_desc` | varchar(128) | 描述 |
| `tree_node_rule_key` | varchar(32) | 规则树根节点入口（首先执行的规则 key） |
| `create_time` / `update_time` | datetime | 时间戳 |

**索引**：`UNIQUE KEY uq_tree_id (tree_id)`

#### `rule_tree_node`（规则树节点表）

| 字段 | 类型 | 说明 |
|---|---|---|
| `tree_id` | varchar(32) | 所属规则树ID（→ `rule_tree`） |
| `rule_key` | varchar(32) | 节点规则Key（如 `rule_lock`、`rule_stock`、`rule_luck_award`） |
| `rule_desc` | varchar(64) | 规则描述 |
| `rule_value` | varchar(128) | 规则参数（如 lock 解锁次数 `1`、兜底奖品范围 `101:1,100`） |

#### `rule_tree_node_line`（规则树连线表）

| 字段 | 类型 | 说明 |
|---|---|---|
| `tree_id` | varchar(32) | 所属规则树ID |
| `rule_node_from` | varchar(32) | 源节点 rule_key |
| `rule_node_to` | varchar(32) | 目标节点 rule_key |
| `rule_limit_type` | varchar(8) | 条件类型（EQUAL 等值匹配） |
| `rule_limit_value` | varchar(32) | 条件值（`ALLOW` 放行、`TAKE_OVER` 接管） |

**规则树执行逻辑示例**（`tree_lock_1`）：
```
rule_lock ──ALLOW──→ rule_stock ──ALLOW──→ rule_luck_award（兜底）
rule_lock ──TAKE_OVER──→ rule_luck_award（直接接管给兜底奖品）
```

---

### 2.8 `strategy`（抽奖策略表）

**业务含义**：定义一套抽奖策略，聚合多条规则模型，绑定到具体活动上。

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | bigint unsigned | 自增主键 |
| `strategy_id` | bigint(8) | 策略业务ID |
| `strategy_desc` | varchar(128) | 策略描述 |
| `rule_models` | varchar(256) | 策略级别规则模型集合（逗号分隔，如 `rule_blacklist,rule_weight`） |
| `create_time` / `update_time` | datetime | 时间戳 |

**索引**：`KEY idx_strategy_id (strategy_id)`

---

### 2.9 `strategy_award`（策略奖品概率表）

**业务含义**：每个策略下各奖品的详细配置，包含库存、中奖概率和绑定的规则树，是抽奖核心数据表。

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | bigint unsigned | 自增主键 |
| `strategy_id` | bigint(8) | 所属策略ID（→ `strategy`） |
| `award_id` | int(8) | 关联奖品ID（→ `award`） |
| `award_title` | varchar(128) | 奖品标题（冗余，避免跨表查询） |
| `award_subtitle` | varchar(128) | 奖品副标题（如"抽奖N次后解锁"解锁提示） |
| `award_count` | int(8) | 奖品库存总量 |
| `award_count_surplus` | int(8) | 奖品库存剩余（Redis 缓存实时扣减，DB 兜底） |
| `award_rate` | decimal(6,4) | 中奖概率（精度4位小数，如 0.7900 表示 79%） |
| `rule_models` | varchar(256) | 奖品级别规则树ID（→ `rule_tree`） |
| `sort` | int(2) | 展示排序 |
| `create_time` / `update_time` | datetime | 时间戳 |

**索引**：`KEY idx_strategy_id_award_id (strategy_id, award_id)` — 联合索引，支持按策略查所有奖品

---

### 2.10 `strategy_rule`（策略规则表）

**业务含义**：存储策略或奖品级别的具体规则配置，如黑名单用户列表、权重积分阈值范围。

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | bigint unsigned | 自增主键 |
| `strategy_id` | int(8) | 所属策略ID |
| `award_id` | int(8) | 奖品ID（策略级规则此字段为 NULL） |
| `rule_type` | tinyint(1) | 规则类型（`1` 策略规则、`2` 奖品规则） |
| `rule_model` | varchar(16) | 规则标识（`rule_random`、`rule_blacklist`、`rule_weight`、`rule_lock`、`rule_luck_award`） |
| `rule_value` | varchar(256) | 规则值（如黑名单 `101:user001,user002`，权重 `60:102,103,104`） |
| `rule_desc` | varchar(128) | 规则描述 |
| `create_time` / `update_time` | datetime | 时间戳 |

**索引**：
- `UNIQUE KEY uq_strategy_id_rule_model (strategy_id, rule_model)` — 同一策略下每种规则唯一
- `KEY idx_strategy_id_award_id (strategy_id, award_id)`

---

## 三、`big_market_01/02` — 用户数据分片库

> 以下各表均存在 `_000`、`_001`、`_002`、`_003` 四个分片（按 `user_id` 哈希取模路由），两个库（`big_market_01`、`big_market_02`）结构完全相同。

### 3.1 `raffle_activity_account`（抽奖活动账户表）

**业务含义**：记录某用户在某活动下的抽奖次数**总配额**（含日/月多维度剩余），是用户参与资格的核心账本。

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | bigint unsigned | 自增主键 |
| `user_id` | varchar(128) | 用户ID |
| `activity_id` | bigint(12) | 活动ID（→ `big_market.raffle_activity`） |
| `total_count` | int(8) | 总次数额度 |
| `total_count_surplus` | int(8) | 总次数剩余 |
| `day_count` | int(8) | 日次数额度（上限，从 activity_count 同步） |
| `day_count_surplus` | int(8) | 日次数剩余（**每日凌晨定时重置**） |
| `month_count` | int(8) | 月次数额度 |
| `month_count_surplus` | int(8) | 月次数剩余（**每月1日重置**） |
| `create_time` / `update_time` | datetime | 时间戳 |

**索引**：`UNIQUE KEY uq_user_id_activity_id (user_id, activity_id)` — 用户+活动唯一，防止重复开户

---

### 3.2 `raffle_activity_account_day`（活动账户日次数表）

**业务含义**：按天独立记录用户某天的日次数快照，方便按日期维度管理配额。

| 字段 | 类型 | 说明 |
|---|---|---|
| `user_id` | varchar(128) | 用户ID |
| `activity_id` | bigint(12) | 活动ID |
| `day` | varchar(10) | 日期（格式 `yyyy-mm-dd`） |
| `day_count` | int(8) | 当天总次数额度 |
| `day_count_surplus` | int(8) | 当天剩余次数 |

**索引**：`UNIQUE KEY uq_user_id_activity_id_day (user_id, activity_id, day)` — 三元唯一

---

### 3.3 `raffle_activity_account_month`（活动账户月次数表）

**业务含义**：按月独立记录用户月次数快照，结构与日次数表类似。

| 字段 | 类型 | 说明 |
|---|---|---|
| `user_id` | varchar(128) | 用户ID |
| `activity_id` | bigint(12) | 活动ID |
| `month` | varchar(7) | 月份（格式 `yyyy-mm`） |
| `month_count` | int(8) | 月总次数额度 |
| `month_count_surplus` | int(8) | 月剩余次数 |

**索引**：`UNIQUE KEY uq_user_id_activity_id_month (user_id, activity_id, month)`

---

### 3.4 `raffle_activity_order_{000~003}`（抽奖活动单）

**业务含义**：用户购买/充值抽奖次数所产生的**电商订单**，记录通过哪个 SKU 获得了多少次数配额，支持幂等和对账。

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | bigint unsigned | 自增主键 |
| `user_id` | varchar(128) | 用户ID |
| `sku` | bigint(12) | 商品SKU（→ `big_market.raffle_activity_sku`） |
| `activity_id` | bigint(12) | 活动ID |
| `activity_name` | varchar(64) | 活动名称（冗余） |
| `strategy_id` | bigint(8) | 抽奖策略ID（冗余） |
| `order_id` | varchar(12) | 订单ID（12位纯数字，雪花算法截取） |
| `order_time` | datetime | 下单时间 |
| `total_count` / `day_count` / `month_count` | int(8) | 本次购买获得的各维度次数 |
| `pay_amount` | decimal(10,2) | 支付金额（积分，可为0，如免费活动） |
| `state` | varchar(16) | 订单状态（`complete` / `completed`） |
| `out_business_no` | varchar(64) | **外部幂等号**（上游传入，防重复下单） |
| `create_time` / `update_time` | datetime | 时间戳 |

**索引**：
- `UNIQUE KEY uq_order_id (order_id)`
- `UNIQUE KEY uq_out_business_no (out_business_no)` — 幂等唯一约束
- `KEY idx_user_id_activity_id (user_id, activity_id, state)` — 复合索引含 state，支持状态过滤

---

### 3.5 `task`（消息任务表）

**业务含义**：本地消息表，实现**事务消息/可靠消息**机制。在业务主事务提交后，通过 XXL-Job 定时扫描待发状态任务，驱动 MQ 消息（如发奖通知、返利通知）保证最终一致性。

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | int unsigned | 自增主键 |
| `user_id` | varchar(128) | 关联用户ID |
| `topic` | varchar(32) | MQ 主题（`send_rebate`、`send_award`、`credit_adjust_success`） |
| `message_id` | varchar(11) | 消息唯一编号 |
| `message` | varchar(512) | 消息 JSON 内容 |
| `state` | varchar(16) | 状态（`create` 待发、`completed` 已完成、`fail` 失败） |
| `create_time` / `update_time` | datetime | 时间戳 |

**索引**：
- `UNIQUE KEY uq_message_id (message_id)`
- `KEY idx_state (state)` — 定时任务扫描待处理消息
- `KEY idx_create_time (update_time)` — 按更新时间扫描补偿（**注：索引名 idx_create_time 实际索引列为 update_time，存在命名歧义**）

---

### 3.6 `user_award_record_{000~003}`（用户中奖记录表）

**业务含义**：记录每次抽奖的**中奖结果**，从奖品产生到发奖完成的完整生命周期，每条记录对应一次抽奖行为。

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | int unsigned | 自增主键 |
| `user_id` | varchar(128) | 用户ID |
| `activity_id` | bigint(12) | 活动ID |
| `strategy_id` | bigint(8) | 策略ID |
| `order_id` | varchar(12) | 抽奖订单ID（与 `user_raffle_order` 的 order_id 关联，**幂等键**） |
| `award_id` | int(11) | 中奖奖品ID（→ `big_market.award`） |
| `award_title` | varchar(128) | 奖品名称（冗余） |
| `award_time` | datetime | 中奖时间 |
| `award_state` | varchar(16) | 发奖状态（`create` 待发、`completed` 已发） |
| `create_time` / `update_time` | datetime | 时间戳 |

**索引**：
- `UNIQUE KEY uq_order_id (order_id)` — 防重复中奖
- `KEY idx_user_id (user_id)`
- `KEY idx_activity_id (activity_id)`
- `KEY idx_award_id (strategy_id)` — 注：字段名与索引名命名不一致（索引名 idx_award_id，实际索引列是 strategy_id，存在命名歧义）

---

### 3.7 `user_behavior_rebate_order_{000~003}`（用户行为返利流水订单表）

**业务含义**：记录用户因签到、支付等行为触发的每笔返利流水，包含返利类型（积分 or SKU 次数）和业务幂等号。

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | int unsigned | 自增主键 |
| `user_id` | varchar(128) | 用户ID |
| `order_id` | varchar(12) | 订单ID |
| `behavior_type` | varchar(16) | 触发行为（`sign`、`openai_pay`） |
| `rebate_desc` | varchar(128) | 返利描述 |
| `rebate_type` | varchar(16) | 返利类型（`sku`、`integral`） |
| `rebate_config` | varchar(32) | 返利配置值（积分数量或 SKU 编号） |
| `out_business_no` | varchar(128) | 外部业务单号（幂等） |
| `biz_id` | varchar(128) | 内部业务唯一ID（`out_business_no + 类型枚举` 拼接） |
| `create_time` / `update_time` | datetime | 时间戳 |

**索引**：
- `UNIQUE KEY uq_order_id (order_id)`
- `UNIQUE KEY uq_biz_id (biz_id)` — 业务幂等约束
- `KEY idx_user_id (user_id)`

---

### 3.8 `user_credit_account`（用户积分账户表）

**业务含义**：用户积分钱包，维护积分总额（只增不减）和可用积分（扣减后余额），支持账户冻结。**注意：此表不分片**，单表存储所有用户积分账户。

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | bigint unsigned | 自增主键 |
| `user_id` | varchar(128) | 用户ID（唯一） |
| `total_amount` | decimal(10,2) | 累计总积分（历史积累，只增） |
| `available_amount` | decimal(10,2) | 当前可用积分（扣减后余额） |
| `account_status` | varchar(8) | 账户状态（`open` 可用、`close` 冻结） |
| `create_time` / `update_time` | datetime | 时间戳 |

**索引**：`UNIQUE KEY uq_user_id (user_id)`

---

### 3.9 `user_credit_order_{000~003}`（用户积分订单记录）

**业务含义**：积分账户的流水明细，每次积分变更（行为返利获得积分、兑换抽奖扣减积分）产生一条流水记录，正向/逆向交易均覆盖。

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | bigint unsigned | 自增主键 |
| `user_id` | varchar(128) | 用户ID |
| `order_id` | varchar(12) | 订单ID |
| `trade_name` | varchar(32) | 交易名称（如"行为返利"、"兑换抽奖"） |
| `trade_type` | varchar(8) | 交易类型（`forward` 正向加分、`reverse` 逆向扣分） |
| `trade_amount` | decimal(10,2) | 交易金额（正值为获得，负值为扣减） |
| `out_business_no` | varchar(64) | 外部幂等号 |
| `create_time` / `update_time` | datetime | 时间戳 |

**索引**：
- `UNIQUE KEY uq_order_id (order_id)`
- `UNIQUE KEY uq_out_business_no (out_business_no)`
- `KEY idx_user_id (user_id)`

---

### 3.10 `user_raffle_order_{000~003}`（用户抽奖订单表）

**业务含义**：每次用户发起抽奖所产生的**抽奖凭证订单**，状态机驱动（create → used/cancel），防止重复消费。

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | int unsigned | 自增主键 |
| `user_id` | varchar(128) | 用户ID |
| `activity_id` | bigint(12) | 活动ID |
| `activity_name` | varchar(64) | 活动名称（冗余） |
| `strategy_id` | bigint(8) | 抽奖策略ID（冗余） |
| `order_id` | varchar(12) | 抽奖订单ID（唯一，用于关联 `user_award_record`） |
| `order_time` | datetime | 下单时间 |
| `order_state` | varchar(16) | 订单状态（`create` 创建、`used` 已使用、`cancel` 已作废） |
| `create_time` / `update_time` | datetime | 时间戳 |

**索引**：
- `UNIQUE KEY uq_order_id (order_id)`
- `KEY idx_user_id_activity_id (user_id, activity_id)` — 支持查询用户在某活动的抽奖记录

---

## 四、ER 关系图（文字版）

```
                                     ┌────────────────────┐
                                     │   raffle_activity   │
                                     │  (活动)             │
                                     │  activity_id [UQ]  │
                                     │  strategy_id [UQ]  │
                                     └────────┬───────────┘
                                              │ 1:1
               ┌──────────────────────────────┼──────────────────────────────┐
               │                              │                              │
               ▼                              ▼                              ▼
  ┌────────────────────┐       ┌──────────────────────┐      ┌───────────────────────┐
  │ raffle_activity_sku│       │     strategy          │      │ raffle_activity_stage  │
  │ (活动SKU商品)      │       │ (抽奖策略)            │      │ (活动展台/上架)        │
  │ sku [UQ]           │       │ strategy_id           │      └───────────────────────┘
  │ activity_id        │       └──────────┬────────────┘
  │ activity_count_id  │                  │ 1:N
  └─────────┬──────────┘                  │
            │                    ┌────────┴──────────┐
            ▼                    ▼                   ▼
  ┌──────────────────┐  ┌───────────────┐    ┌───────────────┐
  │raffle_activity   │  │ strategy_award│    │ strategy_rule  │
  │  _count          │  │ (策略奖品概率)│    │ (策略规则)     │
  │ (次数配置)       │  │ strategy_id   │    │ rule_model     │
  └──────────────────┘  │ award_id      │    └───────────────┘
                        │ rule_models   │
                        └──────┬────────┘
                               │ N:1
                    ┌──────────┴────────────┐
                    ▼                       ▼
              ┌──────────┐         ┌──────────────┐
              │  award   │         │  rule_tree   │
              │ (奖品)   │         │ (规则树)     │
              └──────────┘         └──────┬───────┘
                                          │ 1:N
                             ┌────────────┴──────────────┐
                             ▼                           ▼
                    ┌─────────────────┐      ┌──────────────────────┐
                    │ rule_tree_node  │──────▶│ rule_tree_node_line  │
                    │ (规则节点)      │      │ (节点连线/条件)      │
                    └─────────────────┘      └──────────────────────┘

═══════════════════════════════════════════════════════════════
              用户数据分片库（big_market_01/02）
═══════════════════════════════════════════════════════════════

user_id → hash % 4 → 路由到 _000/_001/_002/_003 分片

  ┌──────────────────────────────────────────────────────┐
  │  raffle_activity_account (用户活动账户)               │
  │  user_id + activity_id [UQ]                          │
  └────────────┬──────────────┬───────────────────────────┘
               │              │
               ▼              ▼
   ┌─────────────────┐  ┌──────────────────────┐
   │_account_day     │  │_account_month        │
   │(日次数快照)     │  │(月次数快照)          │
   └─────────────────┘  └──────────────────────┘

  ┌──────────────────────┐       ┌────────────────────────┐
  │ raffle_activity_order│  充值  │ user_credit_order      │
  │ (活动购买订单)       │──────▶│ (积分流水)             │
  │ out_business_no [UQ] │       │ trade_type=forward/rev │
  └──────────────────────┘       └──────────┬─────────────┘
                                             │ 更新
                                             ▼
  ┌──────────────────────┐       ┌────────────────────────┐
  │ user_raffle_order    │  扣减  │ user_credit_account    │
  │ (抽奖凭证订单)       │──────▶│ (用户积分账户)         │
  │ order_state:create   │       │ available_amount       │
  │ → used/cancel        │       └────────────────────────┘
  └──────────┬───────────┘
             │ 产生中奖
             ▼
  ┌──────────────────────┐       ┌────────────────────────┐
  │ user_award_record    │  驱动  │      task              │
  │ (中奖记录)           │──────▶│ (本地消息表)           │
  │ award_state:create   │  MQ   │ topic:send_award       │
  │ → completed          │       │ state:create→completed │
  └──────────────────────┘       └────────────────────────┘

  ┌───────────────────────────────┐
  │ user_behavior_rebate_order    │  触发 → 写 task → MQ → 积分/SKU返利
  │ (行为返利流水)                │
  │ biz_id [UQ] 幂等防重          │
  └───────────────────────────────┘

  ┌──────────────────────┐
  │ daily_behavior_rebate│  配置  →  触发行为返利规则
  │ (返利活动配置)        │
  └──────────────────────┘
```

---

## 五、典型业务链路 × 表关系

### 链路 1：用户签到返利

```
用户签到
 └─ 查询 daily_behavior_rebate (behavior_type=sign，找到返利规则)
 └─ 写入 user_behavior_rebate_order_{shard}（幂等 biz_id 防重）
 └─ 写入 task（topic=send_rebate，state=create）
 └─ 【同事务提交】
 └─ XXL-Job 扫描 task → 发 MQ
 └─ Consumer 消费 → 更新 user_credit_account（积分 forward）
                   + 写入 user_credit_order（流水）
                   + 扣减 raffle_activity_sku 库存（如为 sku 类型）
                   + 更新 raffle_activity_account（总次数增加）
```

### 链路 2：用户兑换抽奖次数（积分购买）

```
用户消费积分购买 SKU
 └─ 查询 raffle_activity_sku（检查库存 stock_count_surplus）
 └─ 查询 raffle_activity_count（获取次数规格）
 └─ 扣减积分 user_credit_account（available_amount -= pay_amount）
 └─ 写入 user_credit_order（trade_type=reverse，负值）
 └─ 写入 raffle_activity_order_{shard}（out_business_no 幂等）
 └─ 更新 raffle_activity_account（total_count_surplus += count）
 └─ 扣减 raffle_activity_sku.stock_count_surplus
```

### 链路 3：用户执行抽奖

```
用户发起抽奖
 └─ 查询 raffle_activity（检查活动有效期和状态）
 └─ 查询 raffle_activity_account（校验剩余次数）
 └─ 创建 user_raffle_order（state=create）—— 事务开始
 └─ 扣减 raffle_activity_account（total/day/month 三维度）—— 同事务
 └─ 【事务提交后】
 └─ 加载 strategy + strategy_award（获取奖品池）
 └─ 加载 strategy_rule（规则过滤：黑名单/权重）
 └─ 规则树执行：rule_tree → rule_tree_node → rule_tree_node_line
    ├─ rule_blacklist（黑名单检查 → 兜底积分）
    ├─ rule_weight（积分阈值 → 特定奖品范围）
    ├─ rule_lock（抽奖次数未达到 → TAKE_OVER → 兜底）
    ├─ rule_stock（扣减 strategy_award.award_count_surplus）
    └─ rule_luck_award（库存耗尽兜底随机积分）
 └─ 写入 user_award_record（award_state=create）
 └─ 写入 task（topic=send_award，state=create）
 └─ 更新 user_raffle_order（state=used）
 └─ XXL-Job → MQ → 发奖 Consumer → 更新 award_state=completed
```

---

## 六、分库分表设计分析

### 分片策略

| 维度 | 规则 |
|---|---|
| **分库** | 2 个库（big_market_01、big_market_02），目前代码以 01 为主，02 为预留扩展 |
| **分表** | 每张用户数据表 4 个分片（后缀 _000~_003） |
| **路由键** | `user_id`（字符串哈希取模） |
| **路由表** | `raffle_activity_order`、`user_award_record`、`user_behavior_rebate_order`、`user_credit_order`、`user_raffle_order` |
| **未分片** | `user_credit_account`（用户积分账户，单表，唯一键 user_id） |
| **配置库** | `big_market`（全局配置，不分片） |

### 分片优势

1. 用户数据水平拆分，单表数据量可控
2. 路由逻辑简单，基于 user_id hash，查询时明确路由片
3. 配置库与用户库分离，降低锁竞争，配置可缓存到 Redis

---

## 七、设计优点

1. **幂等设计完善**：各类订单表均设计 `out_business_no` 或 `biz_id` 唯一索引，防止重复提交。
2. **规则引擎可配置**：rule_tree 三表实现 DAG 规则树，无需发版即可调整抽奖过滤逻辑。
3. **本地消息表保证最终一致性**：`task` 表配合 XXL-Job 定时扫描，规避分布式事务，实现"写库+发MQ"可靠化。
4. **冗余字段减少跨库 Join**：订单表冗余 `activity_name`、`award_title` 等，避免跨库联查。
5. **多维度次数管理**：`account`/`account_day`/`account_month` 三表分别管理总/日/月次数，逻辑清晰。
6. **库存双写**：`stock_count_surplus` 在 Redis 缓存扣减，DB 记录兜底，高并发下库存安全。
7. **积分账户正逆向流水**：`user_credit_order.trade_type` 区分 forward/reverse，可准确核对账户余额。

---

## 八、设计缺陷与可优化点

### 缺陷

| # | 问题 | 位置 | 影响 |
|---|---|---|---|
| 1 | **索引命名歧义（1）**：`user_award_record` 表中 `KEY idx_award_id (strategy_id)`，索引名为 idx_award_id 但实际索引列是 strategy_id | `user_award_record_{shard}` | 可读性差，误导运维 DBA |
| 2 | **索引命名歧义（2）**：`task` 表中 `KEY idx_create_time (update_time)`，索引名为 idx_create_time 但实际索引列是 update_time | `task` | 同上 |
| 3 | **状态字段用 varchar**：`state`、`order_state`、`award_state` 等用 varchar 存枚举值，未使用 ENUM 或 tinyint | 多表 | 存储冗余，且无数据库级别枚举约束 |
| 4 | **缺少显式外键约束**：表间关联靠应用层保证，数据库层无外键约束 | 全库 | 数据一致性风险，脏数据难以发现 |
| 5 | **`user_credit_account` 未分片**：高并发下可能成单点瓶颈 | `user_credit_account` | 亿级用户时单表性能问题 |
| 6 | **`task.message` 长度仅 512**：消息内容可能超长 | `task` | 消息截断风险 |
| 7 | **`raffle_activity_stage` 缺少索引**：无 `activity_id` 索引，按活动查询需全表扫 | `raffle_activity_stage` | 查询性能低 |
| 8 | **分片数固定为 4**：扩容时需要迁移数据，不支持弹性扩缩 | 分片设计 | 后期扩展成本高 |
| 9 | **冗余字段同步问题**：`activity_name`、`award_title` 等冗余字段，若原表更新，历史订单数据不一致 | 订单表 | 数据一致性风险 |

### 优化建议

1. **修正索引命名**：将 `user_award_record` 中 `KEY idx_award_id (strategy_id)` 改为 `KEY idx_strategy_id (strategy_id)`。
2. **状态字段改用 tinyint**：用枚举映射替代 varchar，节省存储，数据库层可加 CHECK 约束。
3. **`user_credit_account` 按 user_id 分片**：与其他用户表保持一致，避免单表瓶颈。
4. **扩展 task.message 长度**：改为 `text` 类型，适应未来消息体增长。
5. **`raffle_activity_stage` 添加索引**：增加 `KEY idx_activity_id (activity_id)`。
6. **引入一致性哈希**：替代简单取模分片，支持弹性扩缩容。
7. **增加归档表**：订单、流水表历史数据定期归档到冷存储，避免单分片持续膨胀。
8. **冗余字段版本化**：在订单中记录配置版本号，隔离历史数据与当前主表变更。

---

## 九、面试常见追问要点

### Q1：为什么要分库分表？分片键如何选择？
**答**：用户订单、中奖记录随用户规模线性增长，单表承载有限。选 `user_id` 作为分片键，因为绝大多数查询都带有 `user_id` 条件，可精准路由到对应分片，避免跨片查询。

### Q2：分片后如何保证订单 ID 全局唯一？
**答**：`order_id` 由雪花算法生成（12位数字），雪花 ID 本身具备全局唯一性，不依赖数据库自增。分片内 `id` 字段使用自增仅为分片内排序，非全局唯一标识。

### Q3：如何保证抽奖次数扣减的并发安全？
**答**：采用乐观锁 + Redis 原子操作双保险：① Redis 用 `DECR` 原子操作扣减缓存计数；② DB 层写 `UPDATE ... SET surplus = surplus - 1 WHERE surplus > 0`，CAS 方式避免超扣；③ 活动账户的日/月次数通过 UNIQUE KEY + 覆盖插入保证并发安全。

### Q4：`task` 表的本地消息表是什么设计模式？
**答**：是**本地事务表（Outbox Pattern）**的实现。业务主逻辑（写订单）和写 task 在**同一个本地事务**中提交，消除分布式事务需求。XXL-Job 定时扫描 `state=create` 的任务发送 MQ，消费端幂等处理，保证**至少一次投递**和**最终一致性**。

### Q5：规则树三张表是什么设计思路？
**答**：将抽奖过滤规则抽象为**可配置的有向无环图（DAG）**。`rule_tree` 定义入口节点，`rule_tree_node` 定义每个规则节点的参数，`rule_tree_node_line` 定义节点间的跳转条件（ALLOW/TAKE_OVER）。这样新增/修改抽奖规则只需改数据库配置，无需发布代码，体现了**数据驱动**的设计思想。

### Q6：积分账户为何拆分 total_amount 和 available_amount？
**答**：`total_amount` 记录历史累计积分（只增），用于统计用户价值；`available_amount` 是实际可用余额（可扣减），用于业务消费。两者分离可同时支持"总积分排行"和"实时余额"查询，互不干扰。
