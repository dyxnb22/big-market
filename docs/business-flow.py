"""
Big-Market Marketing Raffle System - Complete Business Flow Diagram
大市场营销抽奖系统 - 完整业务流程图

Usage / 使用方式:
    pip install matplotlib
    python3 business-flow.py

Output / 输出:
    business-flow.png  - High-res PNG flow diagram
"""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch

# ── Color Theme ─────────────────────────────────────────────
C_TRIGGER   = "#4A90D9"   # Blue   - Trigger layer
C_DOMAIN    = "#27AE60"   # Green  - Domain layer
C_INFRA     = "#E67E22"   # Orange - Infrastructure
C_ASYNC     = "#9B59B6"   # Purple - Async / MQ
C_DECISION  = "#F39C12"   # Yellow - Decision node
C_START_END = "#2C3E50"   # Dark   - Start / End
C_CHAIN     = "#1ABC9C"   # Teal   - Chain / Tree
C_JOB       = "#E74C3C"   # Red    - Scheduled jobs
C_BG        = "#F8F9FA"   # Background


# ── Drawing helpers ──────────────────────────────────────────

def box(ax, x, y, w, h, text, color,
        fontsize=7.5, textcolor="white", bold=False):
    patch = FancyBboxPatch((x - w/2, y - h/2), w, h,
                           boxstyle="round,pad=0.1",
                           facecolor=color, edgecolor="white",
                           linewidth=1.2, zorder=3)
    ax.add_patch(patch)
    ax.text(x, y, text, ha="center", va="center",
            fontsize=fontsize, color=textcolor,
            fontweight="bold" if bold else "normal",
            zorder=4, multialignment="center")


def diamond(ax, x, y, w, h, text, color, fontsize=7):
    dx, dy = w / 2, h / 2
    pts = [(x, y + dy), (x + dx, y), (x, y - dy), (x - dx, y)]
    ax.add_patch(plt.Polygon(pts, facecolor=color, edgecolor="white",
                             linewidth=1.2, zorder=3))
    ax.text(x, y, text, ha="center", va="center",
            fontsize=fontsize, color="white", fontweight="bold", zorder=4)


def arrow(ax, x1, y1, x2, y2, label="", color="#555555",
          lw=1.5, rad=0.0):
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle="->", color=color, lw=lw,
                                connectionstyle=f"arc3,rad={rad}"),
                zorder=2)
    if label:
        mx = (x1 + x2) / 2 + 0.05
        my = (y1 + y2) / 2
        ax.text(mx, my, label, fontsize=6, color=color,
                ha="left", va="center", zorder=5)


def dashed_rect(ax, x, y, w, h, label, color):
    ax.add_patch(plt.Rectangle((x, y), w, h,
                               linewidth=1.5, linestyle="--",
                               edgecolor=color, facecolor=color,
                               alpha=0.07, zorder=1))
    ax.text(x + w / 2, y + h - 0.05, label,
            fontsize=7.5, color=color, ha="center", va="top",
            fontstyle="italic", fontweight="bold", zorder=2)


# ════════════════════════════════════════════════════════════
# Sub-diagram 1: System Architecture Layers
# ════════════════════════════════════════════════════════════

def draw_architecture(ax):
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 14)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_facecolor(C_BG)
    ax.set_title("Diagram 1 - Big-Market System Architecture Layers",
                 fontsize=12, fontweight="bold", pad=8, color="#2C3E50")

    layers = [
        (12.5, "Client Layer",
         ["H5 / App / Mini-program / OpenAI caller",
          "HTTP REST API  /  Dubbo RPC"],
         "#34495E"),
        (10.7, "Trigger Layer",
         ["HTTP Controllers: RaffleActivity / Strategy / ERP / DCC",
          "MQ Consumers: SendAward / Rebate / Credit / StockZero",
          "XXL-Jobs: StockSync / SendMessageTask"],
         C_TRIGGER),
        (8.45, "Domain Layer  (DDD Core)",
         ["Strategy Domain: Chain-of-Responsibility + Decision-Tree + O1/OLogN algorithm",
          "Activity Domain: 3-level quota management (total / monthly / daily)",
          "Award Domain:   strategy-pattern award dispatch",
          "Credit Domain:  credit account & transaction flow",
          "Rebate Domain:  behavior-driven rebate (sign-in, etc.)",
          "Task Domain:    MQ compensation tasks"],
         C_DOMAIN),
        (5.65, "Infrastructure Layer",
         ["Repository impl (adapt domain interfaces to storage)",
          "DAO: MyBatis  +  2-DB / 4-table sharding (mini-db-router)",
          "Redis: Redisson cache  +  atomic counters",
          "RabbitMQ: event-driven  +  idempotent consumers",
          "Elasticsearch: CQRS read-side"],
         C_INFRA),
        (2.9, "Storage Layer",
         ["MySQL: big_market (shared) + big_market_01/02 (sharded by userId)",
          "Redis: strategy cache + stock counters + distributed locks",
          "RabbitMQ: async event bus",
          "Elasticsearch: order full-text search"],
         C_JOB),
    ]

    for (cy, title, items, color) in layers:
        h = 1.8
        patch = FancyBboxPatch((0.3, cy - h / 2), 9.4, h,
                               boxstyle="round,pad=0.15",
                               facecolor=color, edgecolor="white",
                               linewidth=2, alpha=0.88, zorder=2)
        ax.add_patch(patch)
        ax.text(0.75, cy + h / 2 - 0.22, title,
                fontsize=8.5, color="white", fontweight="bold",
                va="top", zorder=3)
        for i, item in enumerate(items):
            ax.text(0.9, cy + h / 2 - 0.52 - i * 0.33, f"• {item}",
                    fontsize=6.8, color="white", va="top", zorder=3)

    for y1, y2 in [(11.6, 11.6), (9.55, 9.45), (7.5, 7.3), (4.75, 4.5)]:
        ax.annotate("", xy=(5, y2), xytext=(5, y1),
                    arrowprops=dict(arrowstyle="<->",
                                   color="#7F8C8D", lw=2),
                    zorder=5)

    legend = [
        mpatches.Patch(color=C_TRIGGER, label="Trigger Layer"),
        mpatches.Patch(color=C_DOMAIN,  label="Domain Layer"),
        mpatches.Patch(color=C_INFRA,   label="Infrastructure Layer"),
        mpatches.Patch(color=C_JOB,     label="Storage Layer"),
    ]
    ax.legend(handles=legend, loc="lower right",
              fontsize=7, framealpha=0.9)


# ════════════════════════════════════════════════════════════
# Sub-diagram 2: Complete Raffle Main Flow
# ════════════════════════════════════════════════════════════

def draw_raffle_flow(ax):
    ax.set_xlim(0, 22)
    ax.set_ylim(0, 28)
    ax.axis("off")
    ax.set_facecolor(C_BG)
    ax.set_title("Diagram 2 - Complete Raffle Main Flow",
                 fontsize=12, fontweight="bold", pad=8, color="#2C3E50")

    # --- Group backgrounds ---
    dashed_rect(ax,  0.1, 22.0,  6.8, 5.5, "Trigger Layer (HTTP + AOP)", C_TRIGGER)
    dashed_rect(ax,  7.2, 22.0,  6.8, 5.5, "Activity Domain", C_DOMAIN)
    dashed_rect(ax, 14.3, 22.0,  7.4, 5.5, "Strategy Domain - Chain", C_CHAIN)
    dashed_rect(ax,  0.1,  8.0,  6.8, 13.5, "Strategy Domain - Decision Tree", C_CHAIN)
    dashed_rect(ax,  7.2,  8.0,  6.8, 13.5, "Award Domain", C_DOMAIN)
    dashed_rect(ax, 14.3,  0.3,  7.4, 20.7, "Async Award Dispatch", C_ASYNC)

    # 1. Entry
    box(ax, 3.5, 27.2, 4.0, 0.55,
        "User  POST /api/v1/raffle/activity/draw", C_START_END, bold=True, fontsize=8)

    # 2. AOP Interceptors
    box(ax, 3.5, 26.2, 4.0, 0.5,
        "JWT Token Auth  (AuthService.checkToken)", C_TRIGGER)
    arrow(ax, 3.5, 26.92, 3.5, 26.45)

    diamond(ax, 3.5, 25.45, 3.5, 0.55, "DCC degrade switch?", C_DECISION)
    arrow(ax, 3.5, 25.95, 3.5, 25.72)
    box(ax, 1.1, 25.45, 1.6, 0.45, "Return ERR_DCC\n(degraded)", C_JOB, fontsize=6.5)
    arrow(ax, 1.75, 25.45, 2.72, 25.45)
    ax.text(2.0, 25.55, "ON", fontsize=6.5, color=C_DECISION, ha="center")

    diamond(ax, 3.5, 24.65, 3.5, 0.55, "Rate limit exceeded?", C_DECISION)
    arrow(ax, 3.5, 25.17, 3.5, 24.92)
    box(ax, 1.1, 24.65, 1.6, 0.45, "Return ERR_RATE\n(rate limited)", C_JOB, fontsize=6.5)
    arrow(ax, 1.75, 24.65, 2.72, 24.65)
    ax.text(2.0, 24.75, "YES", fontsize=6.5, color=C_DECISION, ha="center")

    box(ax, 3.5, 23.85, 4.0, 0.5,
        "@HystrixCommand  (circuit breaker)", C_TRIGGER)
    arrow(ax, 3.5, 24.37, 3.5, 24.1)

    # 3. Activity domain - create order
    arrow(ax, 5.5, 23.85, 7.95, 23.85, lw=1.5, color=C_DOMAIN)
    ax.text(6.5, 23.95, "createOrder()", fontsize=6.5, color=C_DOMAIN, ha="center")

    box(ax, 10.6, 23.85, 5.6, 0.5,
        "RaffleActivityPartakeService.createOrder()", C_DOMAIN, bold=True)

    activity_steps = [
        ("1. Validate total account quota  (activity_account)", C_INFRA),
        ("2. Validate monthly quota  (account_month, create if absent)", C_INFRA),
        ("3. Validate daily quota    (account_day, create if absent)", C_INFRA),
        ("4. [TX] insert user_raffle_order + update accounts", "#C0392B"),
    ]
    prev_y = 23.6
    cy = 23.15
    for label, color in activity_steps:
        box(ax, 10.6, cy, 5.6, 0.42, label, color, fontsize=6.8)
        arrow(ax, 10.6, prev_y, 10.6, cy + 0.21)
        prev_y = cy - 0.21
        cy -= 0.5

    # 4. Strategy domain - chain of responsibility
    arrow(ax, 13.4, 21.6, 17.5, 22.0, lw=1.5, color=C_CHAIN)
    ax.text(15.2, 22.1, "performRaffle()", fontsize=6.5, color=C_CHAIN, ha="center")

    box(ax, 17.8, 22.0, 4.5, 0.5,
        "DefaultRaffleStrategy.performRaffle()", C_CHAIN, bold=True)

    chain_nodes = [
        (15.0, 24.5, "BlackListLogicChain\nBlacklist check"),
        (17.8, 24.5, "RuleWeightLogicChain\nWeighted raffle"),
        (20.6, 24.5, "DefaultLogicChain\nO1 / OLogN random"),
    ]
    for i, (cx, cy_c, label) in enumerate(chain_nodes):
        box(ax, cx, cy_c, 2.4, 0.85, label, C_CHAIN, fontsize=6.5)
        if i < 2:
            arrow(ax, cx + 1.2, cy_c, cx + 1.2 + 1.2, cy_c,
                  label="miss" if i == 0 else "", color=C_CHAIN)
    arrow(ax, 17.8, 21.75, 17.8, 24.08)

    box(ax, 17.8, 25.4, 4.5, 0.55,
        "Award matched  ->  awardId", "#2ECC71", bold=True)
    arrow(ax, 20.6, 24.93, 20.6, 25.4)
    arrow(ax, 20.6, 25.4, 20.05, 25.4)

    # 5. Decision tree
    arrow(ax, 17.8, 22.0 - 0.25, 3.5, 21.0,
          lw=1.5, color=C_CHAIN, rad=-0.2)
    ax.text(10.5, 21.3, "enter decision tree",
            fontsize=6.5, color=C_CHAIN, ha="center")

    box(ax, 3.5, 21.0, 4.8, 0.5,
        "DefaultTreeFactory  (decision tree)", C_CHAIN, bold=True)

    tree_steps = [
        (3.5, 20.1, "RuleLockLogicTreeNode\nN-raffle lock: block if count < N"),
        (3.5, 18.9, "RuleStockLogicTreeNode\nStock check: Redis DECR"),
        (3.5, 17.7, "RuleLuckAwardLogicTreeNode\nFallback award (luck award)"),
        (3.5, 16.5, "Final  RaffleAwardEntity  (award result)"),
    ]
    prev_y2 = 20.75
    for x, y, label in tree_steps:
        c = C_CHAIN if "Node" in label else "#27AE60"
        box(ax, x, y, 4.8, 0.6, label, c, fontsize=6.5)
        arrow(ax, x, prev_y2, x, y + 0.3)
        prev_y2 = y - 0.3

    box(ax, 1.0, 18.9, 1.3, 0.45, "Redis\nDECR", C_INFRA, fontsize=6.5)
    arrow(ax, 1.65, 18.9, 2.1, 18.9)
    box(ax, 1.0, 17.7, 1.3, 0.45, "Emit\nStockZero", C_ASYNC, fontsize=6.5)
    arrow(ax, 1.65, 17.7, 2.1, 17.7)

    # 6. Award domain - save record
    arrow(ax, 5.9, 16.5, 10.0, 16.5, lw=1.5, color=C_DOMAIN)
    ax.text(7.8, 16.65, "saveUserAwardRecord()",
            fontsize=6.5, color=C_DOMAIN, ha="center")

    box(ax, 10.6, 16.5, 5.6, 0.5,
        "AwardService.saveUserAwardRecord()", C_DOMAIN, bold=True)

    award_steps = [
        ("1. [TX] insert user_award_record", C_INFRA),
        ("2. [TX] insert task  (compensation task)", C_INFRA),
        ("3. Publish SendAwardMessageEvent -> RabbitMQ", C_ASYNC),
        ("4. Mark task status = completed", C_INFRA),
    ]
    prev_y3 = 16.25
    cy3 = 15.8
    for label, c in award_steps:
        box(ax, 10.6, cy3, 5.6, 0.42, label, c, fontsize=6.8)
        arrow(ax, 10.6, prev_y3, 10.6, cy3 + 0.21)
        prev_y3 = cy3 - 0.21
        cy3 -= 0.5

    # 7. Return result
    arrow(ax, 5.9, 16.5, 3.5, 13.5, lw=1.5, color=C_START_END, rad=0.2)
    box(ax, 3.5, 13.2, 4.0, 0.55,
        "Return awardId / awardTitle to user  [OK]",
        C_START_END, bold=True, fontsize=8)

    # 8. Async award dispatch
    box(ax, 17.8, 19.8, 5.6, 0.55,
        "SendAwardCustomer  (MQ Consumer)", C_ASYNC, bold=True)
    arrow(ax, 10.6, 14.3 - 0.21, 17.8, 19.8,
          lw=1.5, color=C_ASYNC, rad=-0.3)
    ax.text(14.5, 17.5, "RabbitMQ\ntopic: send_award",
            fontsize=6.5, color=C_ASYNC, ha="center", style="italic")

    box(ax, 17.8, 19.1, 5.6, 0.5,
        "distributeAward()  (strategy pattern)", C_DOMAIN)
    arrow(ax, 17.8, 19.52, 17.8, 19.35)

    award_types = [
        (15.4, 18.1, "UserCreditRandomAward\nRandom credit reward"),
        (18.5, 18.1, "OpenAIAccountAdjustQuotaAward\nOpenAI quota adjust"),
        (21.5, 18.1, "... Other\naward types"),
    ]
    arrow(ax, 17.8, 18.85, 17.8, 18.45)
    for x, y, label in award_types:
        box(ax, x, y, 2.6, 0.62, label, C_DOMAIN, fontsize=6.5)
        arrow(ax, 17.8, 18.45, x, y + 0.31, rad=0.1)

    box(ax, 17.8, 17.1, 5.6, 0.5,
        "Update user_award_record  state = COMPLETED", C_INFRA)
    for x, y, _ in award_types:
        arrow(ax, x, y - 0.31, 17.8, 17.35, rad=0.1)

    # Credit chain
    box(ax, 17.8, 16.2, 5.6, 0.55,
        "CreditAdjustService.createOrder()", C_DOMAIN, bold=True)
    arrow(ax, 17.8, 16.85, 17.8, 16.47)

    box(ax, 17.8, 15.5, 5.6, 0.5,
        "Publish CreditAdjustSuccessMessageEvent -> MQ", C_ASYNC)
    arrow(ax, 17.8, 15.92, 17.8, 15.75)

    box(ax, 17.8, 14.75, 5.6, 0.5,
        "CreditAdjustSuccessCustomer  (consume)", C_ASYNC)
    arrow(ax, 17.8, 15.25, 17.8, 15.0)

    box(ax, 17.8, 14.0, 5.6, 0.5,
        "Update user_credit_account  balance += amount", C_INFRA)
    arrow(ax, 17.8, 14.5, 17.8, 14.25)

    # 9. Stock sync job
    box(ax, 3.5, 11.2, 4.8, 0.55,
        "UpdateActivitySkuStockJob\n(XXL-Job, every minute)", C_JOB, bold=True)
    arrow(ax, 3.5, 18.6, 3.5, 11.47, lw=1, color=C_JOB)
    box(ax, 3.5, 10.3, 4.8, 0.55,
        "Drain Redis delay-queue\nbatch update MySQL stock", C_INFRA)
    arrow(ax, 3.5, 10.92, 3.5, 10.58)

    # 10. MQ compensation job
    box(ax, 10.6, 11.2, 5.6, 0.55,
        "SendMessageTaskJob\n(XXL-Job compensation, every minute)", C_JOB, bold=True)
    box(ax, 10.6, 10.3, 5.6, 0.55,
        "Scan task table, re-publish pending MQ msgs\n(at-least-once guarantee)", C_INFRA)
    arrow(ax, 10.6, 10.92, 10.6, 10.58)

    legend = [
        mpatches.Patch(color=C_TRIGGER,   label="Trigger Layer"),
        mpatches.Patch(color=C_DOMAIN,    label="Domain Layer"),
        mpatches.Patch(color=C_INFRA,     label="Infrastructure"),
        mpatches.Patch(color=C_CHAIN,     label="Rule Engine"),
        mpatches.Patch(color=C_ASYNC,     label="Async MQ"),
        mpatches.Patch(color=C_JOB,       label="Scheduled Job"),
        mpatches.Patch(color=C_DECISION,  label="Decision Node"),
    ]
    ax.legend(handles=legend, loc="lower right",
              fontsize=7, framealpha=0.95, ncol=2)


# ════════════════════════════════════════════════════════════
# Sub-diagram 3: Behavior Rebate Flow  &  Armory Flow
# ════════════════════════════════════════════════════════════

def draw_rebate_and_armory(ax):
    ax.set_xlim(0, 22)
    ax.set_ylim(0, 18)
    ax.axis("off")
    ax.set_facecolor(C_BG)
    ax.set_title("Diagram 3 - Behavior Rebate Flow  &  Strategy/Activity Armory Flow",
                 fontsize=12, fontweight="bold", pad=8, color="#2C3E50")

    # ── Left: Rebate Flow ──────────────────────────────────────
    dashed_rect(ax, 0.1, 0.5, 10.5, 17.2,
                "Behavior Rebate Flow  (e.g. sign-in -> reward)", C_DOMAIN)

    box(ax, 5.3, 17.1, 5.0, 0.55,
        "User  POST /calendar_sign_rebate", C_START_END, bold=True)

    box(ax, 5.3, 16.2, 5.0, 0.5,
        "RaffleActivityController.calendarSignRebate()", C_TRIGGER)
    arrow(ax, 5.3, 16.82, 5.3, 16.45)

    box(ax, 5.3, 15.4, 5.0, 0.5,
        "BehaviorRebateService.createOrder(behaviorEntity)", C_DOMAIN, bold=True)
    arrow(ax, 5.3, 15.95, 5.3, 15.65)

    rebate_steps = [
        ("Query daily_behavior_rebate config", C_INFRA),
        ("Build BehaviorRebateOrderEntity", C_DOMAIN),
        ("Build TaskEntity  (MQ compensation)", C_DOMAIN),
        ("[TX] insert rebate_order + task", C_INFRA),
        ("Publish SendRebateMessageEvent -> RabbitMQ", C_ASYNC),
        ("Mark task status = completed", C_INFRA),
    ]
    cy = 14.8
    prev_y = 15.15
    for label, color in rebate_steps:
        box(ax, 5.3, cy, 5.0, 0.45, label, color, fontsize=7)
        arrow(ax, 5.3, prev_y, 5.3, cy + 0.225)
        prev_y = cy - 0.225
        cy -= 0.6

    arrow(ax, 5.3, prev_y + 0.225, 5.3, 10.65, color=C_ASYNC)

    box(ax, 5.3, 10.4, 5.0, 0.55,
        "RebateMessageCustomer  (MQ Consumer)", C_ASYNC, bold=True)

    box(ax, 2.8, 9.3, 4.0, 0.55,
        "type = 'sku'\nRecharge activity quota", C_DOMAIN)
    box(ax, 7.8, 9.3, 4.0, 0.55,
        "type = 'integral'\nAdd user credit", C_DOMAIN)
    arrow(ax, 5.3, 10.12, 5.3, 9.62)
    arrow(ax, 5.3, 9.62, 2.8, 9.58, rad=0.1)
    arrow(ax, 5.3, 9.62, 7.8, 9.58, rad=-0.1)

    box(ax, 2.8, 8.3, 4.0, 0.55,
        "ActivityAccountQuotaService\n.createOrder(SkuRechargeEntity)", C_DOMAIN, fontsize=6.5)
    box(ax, 7.8, 8.3, 4.0, 0.55,
        "CreditAdjustService\n.createOrder(TradeEntity)", C_DOMAIN, fontsize=6.5)
    arrow(ax, 2.8, 9.02, 2.8, 8.58)
    arrow(ax, 7.8, 9.02, 7.8, 8.58)

    box(ax, 2.8, 7.4, 4.0, 0.5,
        "Deduct SKU stock\nUpdate activity_account", C_INFRA, fontsize=7)
    box(ax, 7.8, 7.4, 4.0, 0.5,
        "insert credit_order\nUpdate credit_account balance", C_INFRA, fontsize=7)
    arrow(ax, 2.8, 8.02, 2.8, 7.65)
    arrow(ax, 7.8, 8.02, 7.8, 7.65)

    box(ax, 5.3, 6.4, 5.0, 0.5,
        "Rebate Complete  [OK]", C_START_END, bold=True)
    arrow(ax, 2.8, 7.15, 5.3, 6.65, rad=0.1)
    arrow(ax, 7.8, 7.15, 5.3, 6.65, rad=-0.1)

    box(ax, 5.3, 5.3, 5.0, 0.6,
        "SendMessageTaskJob  (fallback)\nScan task table, re-publish failed MQ msgs", C_JOB, fontsize=7)

    # ── Right: Armory Flow ─────────────────────────────────────
    dashed_rect(ax, 11.0, 0.5, 10.8, 17.2,
                "Strategy / Activity Armory (Cache Warm-up)", C_TRIGGER)

    box(ax, 16.4, 17.1, 6.0, 0.55,
        "GET /strategy_armory?strategyId=xxx", C_START_END, bold=True)

    box(ax, 16.4, 16.2, 6.0, 0.5,
        "RaffleStrategyController.strategyArmory()", C_TRIGGER)
    arrow(ax, 16.4, 16.82, 16.4, 16.45)

    box(ax, 16.4, 15.4, 6.0, 0.5,
        "StrategyArmoryDispatch\n.assembleLotteryStrategy(strategyId)", C_DOMAIN, bold=True)
    arrow(ax, 16.4, 15.95, 16.4, 15.65)

    armory_steps = [
        ("Query strategy_award  (award probability list)", C_INFRA),
        ("Query strategy_rule   (rule config)", C_INFRA),
        ("Query rule_tree / node / line  (decision tree)", C_INFRA),
        ("Compute probability-range intervals", C_DOMAIN),
    ]
    cy2 = 14.75
    prev_y2 = 15.15
    for label, color in armory_steps:
        box(ax, 16.4, cy2, 6.0, 0.45, label, color, fontsize=7)
        arrow(ax, 16.4, prev_y2, 16.4, cy2 + 0.225)
        prev_y2 = cy2 - 0.225
        cy2 -= 0.62

    arrow(ax, 16.4, prev_y2 + 0.225, 16.4, 12.35)
    diamond(ax, 16.4, 12.1, 4.8, 0.65, "Precision <= 10000?", C_DECISION)

    box(ax, 13.5, 11.0, 3.8, 0.65,
        "O1 Algorithm\nHashMap direct lookup\nQuery O(1)", C_CHAIN, fontsize=7)
    box(ax, 19.3, 11.0, 3.8, 0.65,
        "OLogN Algorithm\nSorted array + binary search\nQuery O(logN)", C_CHAIN, fontsize=7)
    arrow(ax, 16.4, 11.77, 13.5, 11.33, rad=0.0)
    arrow(ax, 16.4, 11.77, 19.3, 11.33, rad=0.0)
    ax.text(14.5, 11.65, "YES", fontsize=6.5, color=C_DECISION, ha="center")
    ax.text(18.5, 11.65, "NO",  fontsize=6.5, color=C_DECISION, ha="center")

    box(ax, 16.4, 10.0, 6.0, 0.55, "Write to Redis cache", C_INFRA, bold=True)
    arrow(ax, 13.5, 10.67, 13.5, 10.28)
    arrow(ax, 19.3, 10.67, 19.3, 10.28)
    arrow(ax, 13.5, 10.28, 16.4, 10.28)
    arrow(ax, 19.3, 10.28, 16.4, 10.28)

    redis_entries = [
        "strategy:{strategyId}        ->  strategy config",
        "strategy_award:{id}           ->  award list",
        "strategy_rate_table           ->  probability range table",
        "rule_tree:{treeId}            ->  decision tree",
    ]
    cy3 = 9.35
    prev_y3 = 9.72
    for entry in redis_entries:
        box(ax, 16.4, cy3, 6.0, 0.43, entry, C_INFRA, fontsize=6.8)
        arrow(ax, 16.4, prev_y3, 16.4, cy3 + 0.215)
        prev_y3 = cy3 - 0.215
        cy3 -= 0.58

    box(ax, 16.4, 6.8, 6.0, 0.55,
        "Strategy Armory Complete  ->  Ready to raffle  [OK]",
        C_START_END, bold=True)
    arrow(ax, 16.4, prev_y3 + 0.215, 16.4, 7.08)

    # Activity armory
    box(ax, 16.4, 5.6, 6.0, 0.55,
        "GET /armory?activityId=xxx\n(Activity + SKU warm-up)", C_START_END, fontsize=7)

    box(ax, 16.4, 4.6, 6.0, 0.5,
        "ActivityArmory.assembleActivitySkuByActivityId()", C_DOMAIN)
    arrow(ax, 16.4, 5.32, 16.4, 4.85)

    box(ax, 16.4, 3.8, 6.0, 0.5,
        "Query raffle_activity_sku  ->  write Redis\nKey: raffle_activity_sku_stock_count:{sku}", C_INFRA, fontsize=6.5)
    arrow(ax, 16.4, 4.35, 16.4, 4.05)

    box(ax, 16.4, 3.05, 6.0, 0.5,
        "Activity Armory Complete  [OK]", C_START_END, bold=True)
    arrow(ax, 16.4, 3.55, 16.4, 3.3)


# ════════════════════════════════════════════════════════════
# Sub-diagram 4: Stock Consistency  &  DB Sharding
# ════════════════════════════════════════════════════════════

def draw_stock_and_db(ax):
    ax.set_xlim(0, 22)
    ax.set_ylim(0, 18)
    ax.axis("off")
    ax.set_facecolor(C_BG)
    ax.set_title("Diagram 4 - Stock Eventual Consistency  &  DB Sharding Architecture",
                 fontsize=12, fontweight="bold", pad=8, color="#2C3E50")

    # ── Left: Stock Consistency ───────────────────────────────
    dashed_rect(ax, 0.1, 0.5, 10.5, 17.2,
                "Stock Eventual Consistency Chain", C_INFRA)

    box(ax, 5.3, 17.0, 5.0, 0.55,
        "RuleStockLogicTreeNode  (stock check hit)", C_CHAIN, bold=True)

    box(ax, 5.3, 16.0, 5.0, 0.55,
        "Redis AtomicLong  DECR\nKey: strategy_award_stock:{strategyId}:{awardId}", C_INFRA)
    arrow(ax, 5.3, 16.72, 5.3, 16.28)

    diamond(ax, 5.3, 15.0, 4.8, 0.7, "stock > 0?", C_DECISION)
    arrow(ax, 5.3, 15.72, 5.3, 15.35)

    box(ax, 1.8, 15.0, 2.4, 0.55, "Stock exhausted\nReturn fallback award", C_JOB)
    arrow(ax, 2.9, 15.0, 3.05, 15.0)
    ax.text(2.2, 15.1, "NO", fontsize=6.5, color=C_DECISION, ha="center")
    ax.text(5.7, 15.3, "YES", fontsize=6.5, color=C_DECISION, ha="center")

    box(ax, 5.3, 14.0, 5.0, 0.55,
        "Push to Redis delay-queue\nKey: strategy_award_count_queue:{id}", C_INFRA)
    arrow(ax, 5.3, 14.65, 5.3, 14.28)

    box(ax, 5.3, 13.0, 5.0, 0.55,
        "UpdateAwardStockJob  (XXL-Job, every minute)\nDrain queue, batch update MySQL", C_JOB, bold=True)
    arrow(ax, 5.3, 13.72, 5.3, 13.28)

    diamond(ax, 5.3, 12.0, 5.0, 0.7, "MySQL update OK?", C_DECISION)
    arrow(ax, 5.3, 12.72, 5.3, 12.35)

    box(ax, 1.8, 12.0, 2.4, 0.55, "MQ dead-letter queue\nfallback retry", C_JOB)
    arrow(ax, 2.9, 12.0, 3.05, 12.0)
    ax.text(2.2, 12.1, "FAIL", fontsize=6.5, color=C_JOB, ha="center")
    ax.text(5.7, 12.3, "OK", fontsize=6.5, color=C_DOMAIN, ha="center")

    box(ax, 5.3, 11.0, 5.0, 0.55,
        "MySQL strategy_award.stock synced  [OK]", C_INFRA)
    arrow(ax, 5.3, 11.65, 5.3, 11.28)

    # Stock-zero event
    box(ax, 5.3, 9.7, 5.0, 0.55,
        "When Redis stock = 0\nEmit ActivitySkuStockZeroMessageEvent", C_ASYNC, bold=True)
    ax.annotate("", xy=(5.3, 9.97), xytext=(5.3, 9.3),
                arrowprops=dict(arrowstyle="<-", color=C_ASYNC, lw=1),
                zorder=2)
    ax.text(5.65, 9.55, "on zero", fontsize=6.5, color=C_ASYNC)

    box(ax, 5.3, 8.7, 5.0, 0.55,
        "ActivitySkuStockZeroCustomer  (consume)", C_ASYNC)
    arrow(ax, 5.3, 9.42, 5.3, 8.97)

    box(ax, 5.3, 7.7, 5.0, 0.5,
        "Update raffle_activity_sku\nSet stock_count_surplus = 0  (delist)", C_INFRA, fontsize=6.8)
    arrow(ax, 5.3, 8.42, 5.3, 7.95)

    box(ax, 5.3, 6.7, 5.0, 0.5,
        "Stock zero handling complete  [OK]", C_START_END, bold=True)
    arrow(ax, 5.3, 7.45, 5.3, 6.97)

    box(ax, 5.3, 5.5, 5.0, 0.65,
        "SendMessageTaskJob  (compensation, every minute)\nScan task table status=create\nRe-publish pending MQ messages", C_JOB, fontsize=7)
    arrow(ax, 1.8, 11.72, 1.8, 5.83, lw=1, color=C_JOB)
    arrow(ax, 1.8, 5.83, 2.8, 5.83, color=C_JOB)

    # ── Right: DB Sharding ────────────────────────────────────
    dashed_rect(ax, 11.0, 0.5, 10.8, 17.2,
                "Database Sharding Architecture  (mini-db-router)", C_INFRA)

    box(ax, 16.4, 17.0, 6.0, 0.55,
        "DB Router  (route key: userId)", C_INFRA, bold=True)

    box(ax, 16.4, 16.0, 6.0, 0.55,
        "hashCode  = userId.hashCode()\nDB index  = hashCode % 2\nTable index = hashCode % 4",
        "#8E44AD", textcolor="white", fontsize=7)
    arrow(ax, 16.4, 16.72, 16.4, 16.28)

    box(ax, 13.5, 14.7, 4.5, 0.6,
        "big_market_01\n(userId hashCode % 2 == 0)", C_INFRA, bold=True)
    box(ax, 19.3, 14.7, 4.5, 0.6,
        "big_market_02\n(userId hashCode % 2 == 1)", C_INFRA, bold=True)
    arrow(ax, 16.4, 15.72, 13.5, 15.0, rad=0.1)
    arrow(ax, 16.4, 15.72, 19.3, 15.0, rad=-0.1)

    shard_tables = [
        "raffle_activity_account_{000~003}",
        "raffle_activity_account_day_{000~003}",
        "raffle_activity_account_month_{000~003}",
        "user_raffle_order_{000~003}",
        "user_award_record_{000~003}",
        "user_behavior_rebate_order_{000~003}",
        "user_credit_account_{000~003}",
        "user_credit_order_{000~003}",
        "task_{000~003}",
    ]
    cy4 = 14.1
    for t in shard_tables:
        box(ax, 16.4, cy4, 8.0, 0.42, t, "#5D6D7E", fontsize=6.8)
        cy4 -= 0.58

    arrow(ax, 13.5, 14.4, 13.5, 13.8)
    arrow(ax, 19.3, 14.4, 19.3, 13.8)
    arrow(ax, 13.5, 13.8, 16.4, 13.8)
    arrow(ax, 19.3, 13.8, 16.4, 13.8)

    # Shared (non-sharded) DB
    ax.axhline(y=cy4 - 0.1, xmin=0.52, xmax=0.98,
               color="#BDC3C7", lw=1, linestyle="--")
    box(ax, 16.4, cy4 - 0.5, 8.0, 0.42,
        "-- big_market  shared DB (no sharding) --",
        "#2C3E50", fontsize=7)
    cy4 -= 1.2

    common_tables = [
        "strategy  /  strategy_award  /  strategy_rule",
        "rule_tree  /  rule_tree_node  /  rule_tree_node_line",
        "award  /  raffle_activity  /  raffle_activity_sku",
        "raffle_activity_count  /  daily_behavior_rebate",
    ]
    for t in common_tables:
        box(ax, 16.4, cy4, 8.0, 0.42, t, "#5D6D7E", fontsize=6.8)
        cy4 -= 0.55

    box(ax, 16.4, cy4 - 0.2, 8.0, 0.55,
        "Elasticsearch\nuser_raffle_order  (CQRS read-side, real-time sync)",
        "#16A085", bold=True, fontsize=7)


# ════════════════════════════════════════════════════════════
# Main
# ════════════════════════════════════════════════════════════

def main():
    fig = plt.figure(figsize=(28, 60), facecolor=C_BG)
    fig.suptitle(
        "Big-Market Marketing Raffle System  —  Complete Business Flow Diagram",
        fontsize=16, fontweight="bold", color="#2C3E50", y=0.995
    )

    gs = fig.add_gridspec(4, 1, hspace=0.08,
                          top=0.990, bottom=0.005,
                          left=0.01, right=0.99)

    ax1 = fig.add_subplot(gs[0])
    ax2 = fig.add_subplot(gs[1])
    ax3 = fig.add_subplot(gs[2])
    ax4 = fig.add_subplot(gs[3])

    draw_architecture(ax1)
    draw_raffle_flow(ax2)
    draw_rebate_and_armory(ax3)
    draw_stock_and_db(ax4)

    out = "business-flow.png"
    fig.savefig(out, dpi=150, bbox_inches="tight",
                facecolor=C_BG, format="png")
    print(f"Generated: {out}")
    plt.close(fig)


if __name__ == "__main__":
    main()
