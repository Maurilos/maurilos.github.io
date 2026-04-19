---
layout: post
title: CLAUDE.md 底层逻辑全解析：从注入机制到最佳实践
categories: [Claude]
description: some word here
keywords: claude
mermaid: false
sequence: false
flow: false
mathjax: false
mindmap: false
mindmap2: false
---

# CLAUDE.md 底层逻辑全解析：从注入机制到最佳实践

大多数人写 `CLAUDE.md` 的方式通常是：**随便写几条规则，感觉效果不明显，然后放弃。**

问题不在于你写了没写，而在于你可能根本不知道：

- 这些文字在 Claude 眼里是什么身份
- 它们被放在上下文的什么位置
- 它们和 system prompt、Memory、用户消息之间是什么优先级关系

今天这篇文章，就来把 `Claude Code` 的底层逻辑拆开讲清楚。

> 真正影响效果的，不只是“写了什么”，而是“它被注入到哪里、以什么身份出现、离当前任务有多近”。

---

## 目录

- [1. CLAUDE.md 不在 System Prompt 里](#1-claudemd-不在-system-prompt-里)
- [2. 从当前目录一路向上遍历到根目录](#2-从当前目录一路向上遍历到根目录)
- [3. `@include` 指令如何引入外部文件](#3-include-指令如何引入外部文件)
- [4. Memory 系统和 CLAUDE.md 是两套机制](#4-memory-系统和-claudemd-是两套机制)
- [5. System Prompt 的 22 层结构](#5-system-prompt-的-22-层结构)
- [6. 缓存机制为什么会影响成本与效果](#6-缓存机制为什么会影响成本与效果)
- [7. `.claude/rules/` 的递归发现机制](#7-clauderules-的递归发现机制)
- [8. Git Worktree 的去重逻辑](#8-git-worktree-的去重逻辑)
- [9. 一些很少被提到的功能](#9-一些很少被提到的功能)
- [10. 我推荐的配置方式](#10-我推荐的配置方式)

---

## 1. CLAUDE.md 不在 System Prompt 里

这是最大的认知误区。

大多数人以为 `CLAUDE.md` 的内容会被直接拼接进 system prompt。**其实不是。**

源码中，`CLAUDE.md` 是通过 `prependUserContext()` 函数注入的：

```ts
export function prependUserContext(messages, context): Message[] {
  return [
    createUserMessage({
      content: `<system-reminder>
As you answer the user's questions, you can use the following context:
# claudeMd
${claudeMdContent}

      IMPORTANT: this context may or may not be relevant to your tasks.
      You should not respond to this context unless it is highly relevant to your task.
</system-reminder>`,
      isMeta: true,
    }),
    ...messages,
  ]
}
```

也就是说：

- `CLAUDE.md` 被包装在 `<system-reminder>` 标签里
- 它作为**第一条 user message**插入到对话最前面
- **它不是 system prompt，而是 user message**

这会直接带来几个后果。

### 1.1 优先级低于 System Prompt

`system prompt` 更像模型的“宪法”，而 `user message` 更像“法律”。

当两者冲突时，**system prompt 通常胜出**。所以很多人觉得 `CLAUDE.md` “没效果”，并不是模型没看到，而是**优先级没有你想象中那么高**。

### 1.2 模型被明确告知：这些内容“可能不相关”

请注意这句：

> IMPORTANT: this context may or may not be relevant to your tasks.

这其实是在显式告诉模型：**这段上下文不一定与你当前任务相关。**

这是一种明确的降权信号。

### 1.3 但 CLAUDE.md 又用强指令尝试抬权

与此同时，`CLAUDE.md` 的开头还有一句强语气说明：

```text
Codebase and user instructions are shown below. Be sure to adhere to these
instructions. IMPORTANT: These instructions OVERRIDE any default behavior
and you MUST follow them exactly as written.
```

关键词很关键：

- **OVERRIDE any default behavior**
- **MUST follow them exactly**

这本质上是在用更强硬的措辞，对抗前面“可能不相关”的降权提示。

### 1.4 具体性，决定了执行率

真正影响效果的，不是你有没有写规则，而是你写得是否**具体、明确、可验证**。

不要写这类模糊要求：

- 尽量简洁
- 代码优雅一点
- 回答自然一些

更推荐写成这种形式：

- 回答不超过 3 句话
- 不要给未修改的代码添加注释
- commit message 用中文，且不超过 50 字

> **越具体的规则，越容易被遵守；越模糊的规则，越容易被忽略。**

---

## 2. 从当前目录一路向上遍历到根目录

`CLAUDE.md` 并不只是项目根目录里的一个文件。

Claude Code 会从**当前目录开始**，逐级向上遍历到文件系统根目录，并在每一级检查以下文件：

```text
每一级目录检查：
├── CLAUDE.md              → Project 类型（可版本控制）
├── .claude/CLAUDE.md      → Project 类型（可版本控制）
├── .claude/rules/*.md     → Project 类型（可版本控制，递归扫描子目录）
└── CLAUDE.local.md        → Local 类型（不应提交到版本控制）
```

此外，还会检查两个全局位置：

```text
~/.claude/CLAUDE.md        → User 类型（个人全局指令）
~/.claude/rules/*.md       → User 类型（个人全局规则）
/etc/claude-code/CLAUDE.md → Managed 类型（企业管理员策略）
/etc/claude-code/.claude/rules/*.md → Managed 类型
```

### 2.1 加载顺序决定注意力优先级

源码注释写得很直接：

```text
Files are loaded in reverse order of priority, i.e. the latest files
are highest priority with the model paying more attention to them.
```

意思是：

- **最后加载的，优先级最高**
- 因为模型对更靠近输入末尾的内容通常更敏感
- 这就是常说的 **recency bias（近因偏置）**

### 2.2 完整加载顺序

从先到后、也就是从低到高，大致如下：

1. `/etc/claude-code/CLAUDE.md`（Managed）
2. `/etc/claude-code/.claude/rules/*.md`
3. `~/.claude/CLAUDE.md`（User）
4. `~/.claude/rules/*.md`
5. `/repo-root/CLAUDE.md`（Project）
6. `/repo-root/.claude/CLAUDE.md`
7. `/repo-root/.claude/rules/*.md`
8. `/repo-root/src/CLAUDE.md`
9. `/repo-root/src/.claude/rules/*.md`
10. `/repo-root/src/feature/CLAUDE.md`
11. `/repo-root/src/feature/CLAUDE.local.md`

### 2.3 实际配置建议

可以按这个思路来分层：

- **仓库根目录的 `.claude/rules/`**：放项目通用规则
- **`~/.claude/CLAUDE.md`**：放个人偏好，例如语言、风格
- **子目录的 `CLAUDE.md`**：放局部规则，例如前端目录、后端目录的特定约束

例如：

- `frontend/CLAUDE.md` 写“用 React，不用 Vue”
- `backend/CLAUDE.md` 写“统一使用 errors.Join”
- `~/.claude/CLAUDE.md` 写“默认用中文回答”

> **离当前工作目录越近，优先级越高。**

---

## 3. `@include` 指令如何引入外部文件

`CLAUDE.md` 支持 `@` 语法引入其他文件。

例如：

```md
# 我的项目规则

@./coding-standards.md
@~/global-rules.md
@/etc/team-rules/backend.md
```

### 3.1 解析逻辑

支持以下路径形式：

- `@./path` 或 `@path`：相对于当前 `CLAUDE.md`
- `@~/path`：相对于 home 目录
- `@/path`：绝对路径

还支持：

- 转义空格：`@./my\ file.md`
- `#fragment` 后缀：例如 `@./rules.md#section-1`，但这个 fragment 会被忽略

### 3.2 安全限制

#### 扩展名白名单

只能引入**文本文件**。

支持的扩展名包括：

- `.md`
- `.txt`
- `.json`
- `.yaml`
- `.ts`
- `.py`
- `.go`
- `.rs`
- `.sql`

以及其他几十种文本类型。

**二进制文件会被静默忽略。**

#### 循环引用检测

系统会追踪已经处理过的路径，避免循环 include。

也就是说：

- A 引 B
- B 再引 A

这种情况不会无限展开。

#### 代码块免疫

`@` 指令只在 Markdown 的普通文本节点中解析。

代码块和行内代码里的 `@` 不会被当作 include：

```ts
if (element.type === 'code' || element.type === 'codespan') {
  continue
}
```

#### 外部文件需要审批

如果引入的是**工作目录之外**的文件，通常需要 `claudeMdExternalIncludesApproved` 配置开启。

- User 类型的 `CLAUDE.md` 默认更宽松
- Project 类型的 `CLAUDE.md` 往往需要显式批准

#### 不存在的文件会被静默忽略

不会报错，也不会打断加载流程。

### 3.3 推荐用法：模块化拆分规则

你可以把 `CLAUDE.md` 变成一个总入口，把规则拆成多个主题文件：

```md
# 项目根目录 CLAUDE.md

@.claude/rules/code-style.md
@.claude/rules/git-conventions.md
@.claude/rules/testing.md
```

这样做的好处是：

- 规则更清晰
- 更容易维护
- 修改某一类规则时不会牵动全部内容

---

## 4. Memory 系统和 CLAUDE.md 是两套机制

很多人会把 `Memory` 和 `CLAUDE.md` 混为一谈，但它们其实是**两套独立机制**。

虽然它们在上下文中挨得很近，但身份完全不同。

### 4.1 Memory 注入在 System Prompt 的动态层

Memory 通过 `loadMemoryPrompt()` 加载，注入到 system prompt 的动态部分，也就是 `SYSTEM_PROMPT_DYNAMIC_BOUNDARY` 之后。

而 `CLAUDE.md` 则是在 system prompt 之外，以**user message**的形式出现。

### 4.2 MEMORY.md 有硬编码截断限制

源码里写死了两个限制：

```ts
export const MAX_ENTRYPOINT_LINES = 200
export const MAX_ENTRYPOINT_BYTES = 25_000  // 25KB
```

也就是说：

- 超过 **200 行**：先按行截断
- 超过 **25KB**：再按字节截断

截断后还会自动追加警告：

```md
> WARNING: MEMORY.md is 350 lines (limit: 200). Only part of it was loaded.
> Keep index entries to one line under ~200 chars; move detail into topic files.
```

### 4.3 正确理解：Memory 应该当索引，不该当正文

很多人喜欢把大量详细说明直接堆进 `MEMORY.md`，这是错误用法。

错误示例：

```md
## 用户偏好
用户是一名高级 Go 开发者，有 10 年经验，主要在 Linux 环境下工作。
偏好简洁代码，不喜欢过度抽象。使用 Neovim 编辑器...
```

更合理的写法是把它做成索引：

```md
- [User Profile](user_profile.md) — 高级 Go 开发者，10年经验，偏好简洁
```

也就是说：

- `MEMORY.md` 负责入口
- 详细内容放 topic 文件
- 每条尽量控制在一行、约 200 字以内

> **Memory 是索引系统，不是笔记仓库。**

---

## 5. System Prompt 的 22 层结构

Claude Code 的 system prompt 不是一整段纯文本，而是由多个模块拼接而成。

源码中可以看到，它大致分成 **22 个模块**，并且采用三层缓存策略。

### 5.1 整体结构

```text
┌─── 静态层（全局可缓存，跨用户复用）────────────────────────────┐
│  1. Attribution Header（指纹校验）                          │
│  2. CLI 前缀标识                                           │
│  3. 身份介绍："You are Claude Code..."                     │
│  4. 系统规则（prompt injection 警告等）                     │
│  5. 编码任务指南                                           │
│  6. 操作谨慎性指南                                         │
│  7. 工具使用指南                                           │
│  8. 语气风格                                              │
│  9. 输出效率                                              │
├─── SYSTEM_PROMPT_DYNAMIC_BOUNDARY ───────────────────────┤
│                                                          │
│  ── 动态层（会话级缓存，/clear 或 /compact 后重算）──         │
│  10. 会话指导                                             │
│  11. ★ Memory 内容（loadMemoryPrompt）                    │
│  12. 环境信息（平台、shell、模型名、Git 状态）              │
│  13. 语言偏好                                             │
│  14. 输出样式                                             │
│                                                          │
│  ── 易变层（每轮重算，标记为 DANGEROUS_uncached）──          │
│  15. MCP 服务器指令                                        │
│  16. 暂存板指令                                            │
│  17. 函数结果清除提醒                                      │
│  18. 工具结果摘要                                          │
│                                                          │
│  ── 条件注入 ──                                           │
│  19-22. token 预算 / Advisor 指令 / 系统上下文             │
└──────────────────────────────────────────────────────────┘
```

### 5.2 CLAUDE.md 在哪里？

它不在上面那 22 层里。

它处在 system prompt **之外**：

```text
┌─── User Message 层 ─────────────────────────────────────┐
│  ★ CLAUDE.md 内容（包装在 <system-reminder> 中）         │
│  作为对话的第一条 user message                           │
├──────────────────────────────────────────────────────────┤
│  用户的第一条实际消息                                    │
│  ...后续对话...                                          │
└──────────────────────────────────────────────────────────┘
```

### 5.3 两者定位完全不同

需要特别记住这两个位置：

- **Memory**：system prompt 的动态层
- **CLAUDE.md**：user message 层的第一条消息

因此：

- Memory 更接近“系统级指令”
- CLAUDE.md 更接近“用户提供的上下文”

虽然 `CLAUDE.md` 会通过 “OVERRIDE any default behavior” 来提升权重，但它的**身份并没有因此改变**。

> **Memory 是系统内部的一部分；CLAUDE.md 是外部注入的上下文。**

---

## 6. 缓存机制为什么会影响成本与效果

这部分很多人不注意，但它直接关系到：

- token 成本
- 首轮延迟
- 修改规则后为什么“突然不稳定”

### 6.1 三层缓存结构

#### 静态层

第 1 到第 9 模块使用：

```text
cacheScope: 'global'
```

也就是说：

- 跨用户、跨组织复用
- 命中缓存时，通常不需要重新支付这些 token 的处理成本

#### 动态层

第 10 到第 14 模块使用：

```text
cacheScope: 'org'
```

意思是：

- 在你的组织或账户内复用
- 第一次需要创建缓存
- 后续会话更容易命中

#### 易变层

第 15 到第 18 模块被标记为：

```text
DANGEROUS_uncached
```

这些内容每轮都会重算，无法稳定复用缓存。

而且源码要求每一段都要写清楚为什么不能缓存，例如：

```ts
DANGEROUS_uncachedSystemPromptSection(
  'mcp_instructions',
  () => getMcpInstructionsSection(mcpClients),
  'MCP servers connect/disconnect between turns',
)
```

### 6.2 CLAUDE.md 为什么不会打爆 system prompt 缓存

因为 `CLAUDE.md` 不在 system prompt 里。

它属于 **user message**，所以：

- **不会使 system prompt 缓存失效**
- 但它自己也会进入 prompt caching 机制
- 如果内容没变，后续轮次仍然可能复用缓存

### 6.3 几个非常实用的结论

- **不要频繁改 `CLAUDE.md`**，否则 user message 缓存会失效
- **MCP 配置变化无所谓**，因为那部分本来就每轮重算
- **`/compact` 和 `/clear` 会清掉动态层缓存**，包括 Memory、环境信息等

> **你以为你只是在改规则，实际上你也可能在重置缓存命中率。**

---

## 7. `.claude/rules/` 的递归发现机制

`.claude/rules/` 不只是一个平铺目录，它支持**递归扫描子目录**。

例如你可以这样组织：

```text
.claude/
├── CLAUDE.md
└── rules/
    ├── general.md
    ├── frontend/
    │   ├── react.md
    │   └── testing.md
    └── backend/
        ├── api-design.md
        └── database.md
```

### 7.1 递归扫描规则

系统会：

- 递归发现所有子目录中的 `.md` 文件
- 自动加载这些规则文件
- 忽略非 `.md` 文件

这意味着你可以把规则按领域拆开：

- 前端规则一组
- 后端规则一组
- 测试规范一组
- 通用约束一组

### 7.2 symlink 安全处理

这里还有一个细节：**符号链接安全**。

系统会同时记录：

- 原始路径
- 解析后的真实路径

这样做是为了避免 symlink 造成目录循环，例如：

- A 链到 B
- B 又链回 A

如果不做处理，就可能导致递归死循环。

---

## 8. Git Worktree 的去重逻辑

如果你在 Git worktree 环境下工作，`CLAUDE.md` 的加载还有一层特殊处理。

源码注释大意是：

```text
当一个 worktree 嵌套在主仓库内部时，向上遍历会同时经过 worktree 根目录和主仓库根目录。
这两个地方都可能有相同的 CLAUDE.md，因此会重复加载同样的内容。
```

### 8.1 Claude Code 会自动跳过重复的 Project 文件

如果检测到你当前位于一个**嵌套 worktree**中，它会跳过主仓库中的 Project 类型文件，避免同一份规则被加载两次。

### 8.2 但 CLAUDE.local.md 例外

`CLAUDE.local.md` 一般不会被 worktree 一起复制，因为它通常是 `.gitignore` 的。

因此：

- Project 规则会去重
- Local 规则可能仍然只存在于主仓库本地

这意味着在 worktree 场景里，**本地私有规则的行为可能与项目规则不同步**。

---

## 9. 一些很少被提到的功能

除了常规机制，源码里还有一些很少有人提到，但很关键的功能点。

### 9.1 `--bare` 模式会跳过 CLAUDE.md

逻辑大致如下：

```ts
const shouldDisableClaudeMd =
  isEnvTruthy(process.env.CLAUDE_CODE_DISABLE_CLAUDE_MDS) ||
  (isBareMode() && getAdditionalDirectoriesForClaudeMd().length === 0)
```

这意味着：

- 使用 `claude --bare`
- 或设置 `CLAUDE_CODE_DISABLE_CLAUDE_MDS=1`

都可能让所有 `CLAUDE.md` 完全不加载。

`--bare` 的语义可以理解为：

> 跳过那些我没有明确要求加载的额外内容。

如果你发现规则“突然全部失效”，先检查是不是进入了 bare 模式。

### 9.2 `settings.json` 可以关闭特定来源

例如：

```ts
if (isSettingSourceEnabled('projectSettings')) {
  // 才会加载 Project 类型的 CLAUDE.md
}
if (isSettingSourceEnabled('localSettings')) {
  // 才会加载 Local 类型的 CLAUDE.local.md
}
```

也就是说，企业管理员或策略层可以通过配置禁用：

- Project 类型规则
- Local 类型规则

如果某些指令一直不生效，除了怀疑写法，还要检查：

- `settings.json`
- `settingSources` 配置
- 企业策略是否屏蔽了某类来源

### 9.3 GrowthBook feature flag 可以跳过 Project 和 Local

还有这样一段逻辑：

```ts
const skipProjectLevel = getFeatureValue_CACHED_MAY_BE_STALE(
  'tengu_paper_halyard', false,
)
if (skipProjectLevel && (file.type === 'Project' || file.type === 'Local'))
  continue
```

这说明 Anthropic 内部保留了一个 feature flag：

- 名叫 `tengu_paper_halyard`
- 开启后会跳过所有 Project 和 Local 类型的 `CLAUDE.md`

虽然这个开关默认关闭，但它说明了一件事：

> **服务端是具备禁用项目级规则能力的。**

---

## 10. 我推荐的配置方式

理解完底层逻辑之后，真正重要的是：**怎么写，才更稳定、更高效。**

### 10.1 用入口文件做总调度

推荐把根目录 `CLAUDE.md` 写成一个总入口：

```md
# 项目根目录 CLAUDE.md

@.claude/rules/code-style.md
@.claude/rules/git-workflow.md
@.claude/rules/testing.md
```

建议原则：

- 每个规则文件只负责一个主题
- 每个文件尽量不超过 50 行
- 避免把所有规则堆成一坨

### 10.2 规则一定要可验证

不要写：

```text
代码要简洁
```

要写成：

```md
- 函数不超过 30 行
- 不要添加注释到你没有修改的代码行
- commit message 用中文，不超过 50 字
```

这是最重要的一条经验。

> **模型更擅长遵守“可以检查是否做到”的规则，而不是理解“感觉上更好”的规则。**

### 10.3 充分利用层级优先级

建议这样分布：

#### 全局偏好放在 `~/.claude/CLAUDE.md`

```md
- 用中文回答
- 不要在回答末尾总结你做了什么
```

#### 项目通用规则放在 `项目根目录/.claude/rules/`

例如：

```md
# .claude/rules/backend.md
- 使用 Go 1.22+ 的新特性
- 错误处理用 errors.Join 而不是 fmt.Errorf
- 测试用 testify
```

#### 子目录特定规则放在对应目录的 `CLAUDE.md`

例如：

```md
# frontend/CLAUDE.md
- 组件用函数组件，不用 class 组件
- 状态管理用 zustand
```

### 10.4 一套更实用的最终原则

你可以直接记住这几条：

1. **把 `CLAUDE.md` 当成 user message，不要把它幻想成 system prompt**
2. **把规则写具体，尽量写成可验证条件**
3. **把规则拆文件，不要塞成一大坨**
4. **把通用规则、项目规则、子目录规则分层管理**
5. **离当前工作目录越近的规则，优先级越高**
6. **Memory 只做索引，不做正文**
7. **不要频繁改 `CLAUDE.md`，否则会影响缓存命中**
8. **如果规则失效，先检查 bare 模式、settings 和策略开关**

---

## 总结

很多人把 `CLAUDE.md` 当成“写了就该生效的万能法条”，但从底层实现来看，它其实只是：

- 被包装在 `<system-reminder>` 中
- 作为**第一条 user message**注入
- 带有一定降权提示
- 通过强措辞尽量提升执行概率

它不是 system prompt，也不等同于 Memory。

真正决定它是否好用的，是以下几件事：

- 你的规则是否具体
- 你的结构是否分层
- 你的上下文位置是否足够靠近当前任务
- 你的缓存是否被频繁打断

> 写 `CLAUDE.md` 不是“写几条提示词”，而是在设计一套分层、可维护、可执行的上下文系统。

如果你之前一直觉得 `CLAUDE.md` 不太好用，很可能不是它没能力，而是你一直在用错方式。

