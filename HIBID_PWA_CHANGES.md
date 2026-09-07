# HiBid PWA 改版应对记录（2026-09-05）

## 背景

HiBid 会员站前端升级到 `cdn.hibid.com/cdn/pwa/1.22.0`（Angular 16），引入了新的设计系统组件
`<app-button>`（`data-brand-variant` / `data-radius` / `data-button-size`）。

**核心规律：靠文字渲染的按钮丢掉了 `aria-label`，靠图标渲染的按钮保留了。**

| 按钮 | 渲染方式 | `aria-label` |
|---|---|---|
| tile 上的 Bid | 文字 `Bid 60.00 CAD` | ❌ 没了 |
| 弹窗里的 Confirm Bid | 文字 `Confirm Bid` | ❌ 没了 |
| 加价 `+` | 图标 | ✅ `Click to increase the bid increment` |
| 关闭 `×` | 图标 | ✅ `Close` |

所以凡是用 `get_by_label(...)` 定位**文字按钮**的代码都会静默失效（`count()==0`），
表现为“搜到了 lot 却找不到产品 / 跳过”。

---

## 一、正常出价流程（已修复，已在真实页面验证）

验证环境：账号 David，auction `774244`，Lot 13，2026-09-05。
验证方式：开弹窗 → 连点加价 → **不提交** → 关窗（Lot 13 出价前后均为 10 Bids / High Bid 55.00，未产生出价）。

| 环节 | 选择器 | 结果 |
|---|---|---|
| 定位 tile | `app-lot-tile:has-text("Lot {lot} \| ")` | ✅ 29 个 tile 唯一命中 |
| tile 的 Bid 按钮 | 见下方改动 1 | ✅ 命中 `Bid 60.00 CAD` |
| 出价弹窗容器 | `app-login-container` | ✅ |
| 价格输入框 | `get_by_label("Bid amount")` | ✅ 读到 `60.00` |
| 加价按钮 | `get_by_label("Click to increase the bid increment")` | ✅ 60→65→70→75→80 |
| 确认按钮 | 见下方改动 2 | ✅ 唯一命中 `Confirm Bid` |
| 关闭按钮 | `get_by_label("Close")` | ✅ |

### 改动 1 — automation.py `bot_bid()` tile 上的 Bid 按钮

```python
bid_button = lot_title.locator(
    '[aria-label="Bid"], '                                             # 旧版兜底
    'app-lot-buttons .lot-bid-container button:has(span.lot-bid-text)' # 新版
).first
```

### 改动 2 — automation.py `bot_bid()` 弹窗里的确认按钮

```python
confirm_bid_button = bid_modal.locator(
    '[aria-label="Click to confirm bid"], '        # 旧版兜底
    'app-bid-modal button:has-text("Confirm Bid")' # 新版
).first
```

同时把「tile 没找到」和「按钮没找到」拆成两条日志，便于下次定位。

---

## 二、待处理（1）：注册流程

**现状**：旧的 `app-register-auction` 弹窗**已不存在**。点 Bid 时如果账号未注册该场拍卖，
页面会**整页跳走**到另一套 `/pf/` 前端（页面内没有任何 `app-*` 组件）：

```
/pf/auction-registration/<auction_id>?referral=...&action=place-bid&auction_id=<id>&lot_id=<id>
```

需要完成：Payment Verification（信用卡，含 $1 临时预授权）、Preferred Delivery Method、
Auction Terms and Conditions，最后点 `Next`。

**代码位置**：`bot_register_auction()`，由 `bot_bid()` 在每次出价前调用。

**当前行为**：找不到 `app-register-auction` 就直接 `return True` —— 不报错，纯空转。
所以对**已手工注册**的账号无影响。

**结论 / 建议**：涉及信用卡与条款接受，不适合自动化。建议改成**检测 + 明确报错**：
点完 Bid 后若 `page.url` 落到 `/pf/auction-registration/`，记录
「账号未注册此拍卖，请手动注册」并中止本轮，而不是继续往下跑一路失败。

> 2026-09-05 已由人工完成 David 账号对 auction 774244 的注册，之后点 Bid 不再跳转，
> 弹窗正常打开。

---

## 三、非正常出价分支（已修复，2026-09-05）

### 验证方法：静态分析，全程没有出价

要触发这些分支必须真的提交出价，所以改成从前端资源里找答案：

1. 站点文案在语言包 `assets/lang/web-language-en.json`（2141 条），不在 bundle 里
2. `app-bid-modal` 的模板在懒加载 chunk 里（打开出价弹窗时才加载，约 637 KB）
3. 在该 chunk 中定位所有 `aria-label` 绑定点，看它们分别绑到哪个文案 key

### 结论：这个弹窗里还带 `aria-label` 的只有 4 处

| 文案 key | 渲染成 | Playwright 能否 `get_by_label` |
|---|---|---|
| `bid_amount` / `Bid_Amount` | `aria-label` | ✅ 可以 |
| `CONFIRM_YOUR_BID` | `aria-label`（挂在 `app-bid-modal` 上） | ✅ 可以 |
| `Sign_In` / `create_account` / `Reset_Password` | `aria-label` | ✅（登录用，与出价无关） |
| `Confirm_Bid` | **按钮文字**（`n.Oqu` = textInterpolate） | ❌ |
| `f_Click_Here_to_Reconfirm_0` | **组件类里传给弹窗的文字**，无 `aria-label` 绑定 | ❌ |
| `click_ok_to_continue` | **该 chunk 里根本没引用** | ❌ |

也就是说旧代码里这两个定位**必然失效**：

- `get_by_label("Click Here to Reconfirm")` → 二次确认永远点不到 → **出价远超当前价时，出价实际没有提交**
- `get_by_label("Click OK to Continue")`（历史版本）→ 同理

### 顺带发现的老 bug：`is_visible(timeout=)` 根本不等待

Playwright 文档明确：`Locator.is_visible()` 的 `timeout` 参数**已废弃且被忽略**，该方法立即返回。
旧代码用 `is_visible(timeout=500)` 去等一个需要网络往返才出现的弹窗，等于没等——
即使 `aria-label` 还在的年代，二次确认也大概率会被漏掉。

### 改动

`bot_bid()` 里 `confirm_your_bid_modal(bid_modal, lot)` 现在传 lot 便于日志定位；
`confirm_your_bid_modal()` 重写为一个明确的状态机：

1. 用 `wait_for(state='visible')`（真的会等）**一次性**等「二次确认按钮」或「拒绝提示按钮」出现，最多 2s
2. 出现二次确认 → 点掉 → `has_bid = True`，再等 1s 看是否还跟一个拒绝提示
3. 出现拒绝提示（已出过价 / 价格不更高）→ 记日志 + 点掉 → `has_bid = False`
4. 两者都没有且弹窗已自动关闭 → 视为出价成功 `has_bid = True`
5. 两者都没有但弹窗还在 → **未知状态**，把弹窗文字打进日志（不猜）
6. 无论哪条分支，最后都确保弹窗被关掉，下一个 lot 从干净状态开始

选择器统一提到类常量 `RECONFIRM_BUTTON` / `ACKNOWLEDGE_BUTTON`，同样是「旧 aria-label + 新文字」双写。
这两个后续弹窗不保证渲染在 `app-login-container` 内部，所以改成**页面级**定位（`bid_modal.page`）。

同时修正了返回值语义：以前「没触发二次确认的正常出价」会被记成 `skip`，现在按第 4 条判为成功。

### 已验证：lot 已关闭

拿已结束的 auction `772466` 的 Lot 13 实测：tile 里 `app-lot-buttons` **一个 button 都没有**，
新旧选择器都是 0 命中 → 走 `return 0, 'skip'`。这条分支本来就是对的，无需改动。

### 仍待实盘确认

第 2、3 条分支的**具体 DOM** 没能实测（触发它们必须真出价）。代码已按文案文字匹配，
并且在遇到未知状态时会把弹窗文字打进日志。**下次实盘跑完，搜一下日志里这几条**即可确认：

- `reconfirmed the bid` —— 二次确认命中，选择器正确
- `bid was not accepted, dismissing the notice` —— 拒绝提示命中
- `unknown bid modal state: ...` —— 出现了没预料到的弹窗，把后面那段文字发我，一次就能补上

---

## 四、「绝不超过 max」的硬约束（2026-09-06）

### 口径：天花板只认我们自己的数

**唯一的上限来源是我们从管理端自己抓到的 `max_bid_price`**
（`get_bids_info()` 从 `my.hibid.com/auctioneer/lotstats/` 抓表格得到），
再按业务规则算出 `target_price`：

- 15% 开关**关闭**（实际运营中的常态）→ 所有分支下 `target = max_bid_price`
- 15% 开关打开且 `msrp_price >= 100` → `target = max(max_bid_price, msrp_price * multiplier)`
  （multiplier：默认 `0.15`，二手 `0.08`，skipped `0`）

> 2026-09-06 确认：这个开关现在几乎不开，所以实际上 **`target` 就是 `max_bid_price`**。
> 任何基于 `msrp * 0.15` 的推算都不能当作运营现状的参考。

**站点接口返回的任何数字都不参与判断**，包括出价响应里的 `suggestedBid`、`minBid` 等。
（曾经一版代码会去解析二次确认按钮上显示的金额来做比较，已按要求移除。）

### 唯一的守卫点：提交前重读输入框

在真正点 `Confirm Bid` 之前：

```
fill(我们算出的金额)  ->  重新 input_value() 读回来  ->  解析  ->  和 target_price 比
```

读不出来、或 `> target_price`，一律不提交：关弹窗、返回 `skip`。
这一步防的是「站点把输入框改写成别的档位」，检查的是**我们自己即将提交的值**，
不是站点建议的值。

加价循环本身也保证不会超：`while 当前值 <= target: 点加价`，退出后 `pop()` 掉
第一个超过目标的值，填回最后一个不超过目标的值。起拍价本身就高于目标时，
列表为空 → 直接关窗 `skip`，一次都不出价。

### 二次确认

`Click Here to Reconfirm` 确认的是**已经提交出去的那个金额**，而那个金额在提交前
已经过上面的守卫。所以这一步直接点，不读、也不依赖站点显示的任何数字。

### 测试（假 locator，不碰线上、不出价）

**`test_confirm_branches.py`** —— `confirm_your_bid_modal` 6 个分支，全过：

| 场景 | 结果 |
|---|---|
| 出现二次确认 | 点掉，判成功 |
| 出现拒绝提示 | 点掉，判 skip |
| 先二次确认、之后仍被拒 | 判 skip |
| 弹窗自动关闭 | 判成功 |
| 弹窗还在但没有已知按钮 | 记录弹窗文字，判 skip |
| 页面上什么都没有 | 判成功 |

**`test_never_over_max.py`** —— 完整跑 `bot_bid`，断言提交金额永不超过 target，6 个用例全过：

| 用例 | target | 实际提交 |
|---|---|---|
| 加价档位停在目标下方 | 72 | 70 |
| 目标正好落在档位上 | 70 | 70 |
| 起拍价已高于目标 | 50 | 不出价 |
| 站点把输入框改成 95 | 70 | **拒绝提交** |
| 出现二次确认 | 70 | 70 |
| 大差价 lot（39 次加价） | 250 | 250 |

### 仍未测到的部分

上面测的是**分支逻辑**，不是**选择器**。`Click Here to Reconfirm` / `Click OK to Continue`
两个真实弹窗的 DOM 仍未实测（触发必须真出价）。若选择器没命中，行为是
「不点 → 记 unknown 状态 → skip」，即**偏向不出价**。实盘日志搜这三条确认：

- `reconfirmed the bid`
- `bid was not accepted, dismissing the notice`
- `unknown bid modal state: ...`

---

## 五、浏览器实测记录（2026-09-06，全程未出价）

在 auction `774244` / Lot 13（起拍 60.00，High Bid 55.00，10 Bids）上，用真实点击验证规则，
**每次都在 Confirm 之前停下并关窗**。全部测完后核对：仍是 `10 Bids / High Bid 55.00 / bidStatus=nobid`，
没有产生任何出价。

### 加价档位

| 点击次数 | 输入框值 |
|---|---|
| 0（起拍） | 60 |
| 1–10 | 65, 70, 75, 80, 85, 90, 95, 100, 105, 110 |

固定 +5，100 以上不变阶。单次点击到输入框更新耗时 **6–35 ms**。

### 规则实测（真点击、真读值）

| target | 加价停在 | 最终填入 | 判定 |
|---|---|---|---|
| 72 | 60→65→70（越过的 75 被弹掉） | 70 | would CONFIRM |
| 65 | 60→65 | 65 | would CONFIRM |
| 60（等于起拍价） | 60 | 60 | would CONFIRM |
| 50（低于起拍价 60） | 一次都没点 | 不填 | **SKIP，不出价** |

「超过就回退」这条（`pop()` 掉第一个超标值）在 target=72 上直接看到了：
点到 75 才退出循环，弹掉 75，填回 70。

### 站点不会改写输入框

分别填入并触发 `input` / `change` / `blur`：

| 填入 | 读回 |
|---|---|
| 63.33（不在档位上） | 63.33 |
| 50（低于起拍价） | 50 |
| 70（正好在档位上） | 70 |
| 999999 | 999999 |

**客户端不做任何规整**，校验发生在提交后的服务端（对应 `BidIncrement` / `IncreaseBid` 等响应分支）。
也就是说：我们填多少就提交多少，不存在「被站点悄悄抬到下一档」的超价路径。

### 一个操作注意事项

在**同一个页面**上反复开关出价弹窗几十次后，页面明显退化，加价点击从 30ms 掉到数秒。
生产代码每个 lot 都 `page.goto()` 重新加载页面，不会踩到这个；但如果将来改成复用页面连续出价，
要注意这一点——循环里 `current_bid_amount == bid_price_list[-2]` 的防卡死判断会因为读到滞后值而提前 break，
结果是**填一个比目标低的价**（方向安全，但会少出价）。

### 这一节没有覆盖的

- 测的是**规则和页面行为**，不是 Python 实现本身（本机没装 playwright，无法直接跑 `bot_bid`）；
  Python 侧由 `test_confirm_branches.py` / `test_never_over_max.py` 用假 locator 覆盖。
- Confirm 之后的一切（二次确认弹窗、拒绝提示的真实 DOM）仍未测，触发必须真出价。

---

## 六、注册流程实录（2026-09-06，auction 774240 走通全程）

### 触发与落点

未注册的拍卖点 tile 上的 Bid → **整页跳转**（不是弹窗）：

```
/pf/auction-registration/<auction_id>?referral=<catalog_url>&action=place-bid&auction_id=<id>&lot_id=<id>
```

这是另一套 `/pf/` 前端，页面里 **`app-*` 组件为 0**，旧的 `app-register-auction` 弹窗已不存在。
两场拍卖（774244 / 774240）行为一致。

### 关键判据：注册状态可以提前查，不必先点 Bid

拍卖头部按钮 `app-auction-header app-button` 的文字：

| 状态 | 按钮文字 | title 属性 |
|---|---|---|
| 未注册 | `Register to Bid` | `Registered`（**这个属性没用，两种状态都一样**） |
| 已注册 | `You are Registered` | `Registered` |

实测：774240 注册前 `Register to Bid` → 注册后 `You are Registered`；
774244（前一天手工注册）显示 `You are Registered`。
**判 `text == 'You are Registered'`，不要判 title。**

### 分步结构（三段式向导，全程同一个 URL，不跳页）

三个分区都是 `button.accordion-header`，靠 `aria-label` 定位，当前步骤的那个带 `non-toggleable`
且 `aria-expanded="true"`：

| 步骤 | 分区 `aria-label` | 要操作的控件 | 底部按钮 |
|---|---|---|---|
| 0 | `payment` | `input#selected-card-0[name=selected-card]` —— 在档卡，**默认已 checked，无需任何输入** | `Next` |
| 1 | `delivery-method` | `input#delivery-method-1` = Pickup / `input#delivery-method-2` = Ship to address（默认都未选） | `Next`（选之前 `disabled`） |
| 2 | `terms` | `input#terms-input[type=checkbox]`（默认未勾）；另有可选的 `button[aria-label="Toggle notes"]` = `+ Notes to seller` | **`Complete registration`**（勾选前 `disabled`） |

注意：

- 走**在档卡**这条路，全程**不需要输入卡号 / CVV**。只有选 `#selected-card-new` 才会要卡信息。
- 最后一步按钮文字**不是 `Next` 而是 `Complete registration`** —— 自动化不能只找 `Next`。
- 每一步的推进条件就是提交按钮的 `disabled` 属性：填完就变 `false`，不用猜等待时间。

### 提交后

跳回 `referral` 指定的目录页（`/catalog/774240/...`），回到 Angular PWA，头部按钮变成
`You are Registered`。

**注意**：URL 里带着 `action=place-bid&lot_id=...`，但注册完成后**并没有**自动打开出价弹窗、
也没有自动出价（实测 Lot 1a 仍是 0 Bids）。所以注册完必须自己重新走一遍「点 Bid → 出价」。

### 自动化骨架

```
若 头部按钮文字 != 'You are Registered':
    点任一 lot 的 Bid  ->  页面跳到 /pf/auction-registration/<id>
    循环:
        找 button.accordion-header[aria-expanded="true"] 读它的 aria-label
        payment          -> 确认 #selected-card-0 已 checked
        delivery-method  -> 点 #delivery-method-1 (Pickup)
        terms            -> 勾 #terms-input
        等底部 submit 按钮 disabled -> false
        点它（前两步 Next，末步 Complete registration）
    直到 URL 离开 /pf/auction-registration/
    回目录页，重新开始出价流程
```

> 已确认走全自动，实现见第七节。

---

## 七、自动注册实现（2026-09-06）

### 行为

`bot_bid()` 在**点 Bid 之前**先确认注册状态（`self.registered` 缓存，每次自动化只查一次）：

```
ensure_registered(page)
  ├─ 头部按钮是 "You are Registered"        -> True，直接出价
  ├─ 页面上有 app-register-auction（老站点） -> 走原来的 bot_register_auction()
  └─ 否则                                   -> register_auction() 走三步向导
```

未注册且注册失败时，记日志并 `return 0, 'skip'`，**不会**对着注册页空跑后面的逻辑。

### `register_auction()` 的循环

不写死三步，而是每轮读 `button.accordion-header[aria-expanded="true"]` 的 `aria-label`
来决定做什么，遇到不认识的分区就停下报错：

| 分区 | 动作 |
|---|---|
| `payment` | 确认 `input#selected-card-0` 已选中；**卡不存在就中止**（不会去输入卡号） |
| `delivery-method` | 勾 `input#delivery-method-1`（Pickup，类常量 `DELIVERY_METHOD`） |
| `terms` | 勾 `input#terms-input` |
| 其他 | 中止并记日志 |

每步用 `wait_enabled()` 轮询提交按钮的 `disabled`（最多 5s），再点它——按钮文字前两步是
`Next`、最后一步是 `Complete registration`，代码不依赖文字，只取 `button[type="submit"]` 的最后一个。
点完后等「展开的分区变了」或「URL 离开注册页」，最多 10s。

### 实测发现：已注册时注册页会跳走

带着已注册的账号访问 `/pf/auction-registration/774240`，页面**重定向到 `hibid.com/catalog/774240`**
（公共站，不是拍卖行子域）。所以「注册完成后在落地页判断是否成功」是不可靠的——
落地页可能根本没有 `app-auction-header`。

代码因此改成：流程结束后**先 `goto(self.bid_link)` 回到拍卖页**，再判断
`is_registered()`。这样「已经注册了但头部没读到」这种误判也能自愈。

### 测试（`test_registration.py`，假向导，9 项全过）

| 项 | 结果 |
|---|---|
| `registration_url()` 解析 catalog URL（带/不带 query）、非 catalog URL 返回 None | 4/4 |
| 已注册 → 不碰向导 | PASS |
| 未注册 → 三步走完，点击序列 `payment:Next` → `delivery-method:Next` → `terms:Complete registration` | PASS |
| 账号无在档卡 → 中止，返回 False | PASS |
| 提交按钮一直 disabled → 中止，返回 False | PASS |
| 向导被重定向跳走（服务端已注册）→ 回拍卖页复查，返回 True | PASS |

### 未做端到端实测

774240 / 774244 两场在售拍卖现在都已注册，**没有未注册的拍卖可以真跑一遍**。
向导的每个选择器都是在 774240 真实注册过程中逐步抓下来的（第六节），
但「Python 代码自己跑完整个向导」没有验证过。下一期新拍卖上线时是第一次真实检验——
届时看日志里这几条：

- `Not registered for this auction, registering at ...`
- `Registration: filled "payment", clicked "Next"`（三条）
- `Registration finished, registered=True`

---

## 八、`confirm_your_bid_modal` 的真实覆盖情况（2026-09-06 复核）

### 老实说：这个方法从没在真实站点上跑过

它只在点了 Confirm Bid 之后才执行，而全程没有点过 Confirm。三层可靠性递减：

| 部分 | 验证方式 |
|---|---|
| `app-login-container`、`Close` | ✅ 真页面实测 |
| `Click Here to Reconfirm` / `Click OK to Continue` | ⚠️ 仅静态反查，选择器**从未匹配过真实元素** |
| 6 条分支逻辑 | ⚠️ 仅假 locator |

### 全量 bundle 复核（47 个 chunk）

| 文案 key | 所在 chunk | 结论 |
|---|---|---|
| `f_Click_Here_to_Reconfirm_0` | 427（出价弹窗） | ✅ 二次确认确实在这个流程里 |
| `Previous_Bid` | 427 | ✅ 在弹窗里 |
| `click_ok_to_continue` | **46** | ❌ 目录页出价流程**不加载这个 chunk** |
| `click_to_confirm_bid` | 无 | 旧 aria-label 已从整个应用移除 |

### 「已出过价 / 价格不更高」实际长什么样

`Previous_Bid` 出现在 `setBidResponse` 的标题/消息映射里，同组文案：

- `f_You_have_previously_entered_a_flat_bid_for_0` = "You have previously entered a flat bid for {0}"
- `Only_bids_larger_than_this_amount_will_be_accepted` = "Only bids larger than this amount will be accepted"

弹窗状态只有 `INITIAL / BIDREQUESTED / RECONFIRM` 三个 —— 这种拒绝是**弹窗里的标题+文案，不是一个待点击的按钮**。

所以 `ACKNOWLEDGE_BUTTON` 分支在目录页流程里基本不会触发。代码行为仍然正确
（落到「弹窗还开着」那条 → 记录文字 → 判 skip → 关窗），已把日志措辞从
`unknown bid modal state` 改成 `bid not confirmed, modal says: ...`，因为这并非未知状态。
`ACKNOWLEDGE_BUTTON` 作为兜底保留（一次 locator 检查的开销）。

### 二次确认分支的触发条件

站点代码里的硬阈值（chunk 427）：

```js
t >= 10 * this.lotModel.lotState.minBid
```

`t` = 填进输入框的金额，`minBid` = 该 lot 当前最低出价。这是**客户端判断**
（`currentState != ut.RECONFIRM` 是唯一的状态比较），点 Confirm 时先切到 RECONFIRM 状态。

15% 开关关闭时 `target = max_bid_price`，所以触发条件就是：

```
max_bid_price >= 10 * 该 lot 当前 minBid
```

`max_bid_price` 只在管理端可见，无法从公开页面统计触发频率。要精确评估，
需要某一期的 lotstats 导出（lot + max bid）配上当时的 minBid。

### 唯一能真正验证它的办法

跑一次真实出价。建议挑一个 max 价接近起拍价的便宜 lot，让程序真出一次，然后看日志：

- `reconfirmed the bid` → 二次确认分支命中
- `bid not confirmed, modal says: ...` → 拒绝分支命中，后面那段文字能直接确认是哪种拒绝
- 两条都没有、`status=success` → 弹窗自动关闭那条路径
