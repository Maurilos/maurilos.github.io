---
layout: post
title: Claude Code Memory 系统底层逻辑全解析：你的“记忆”为什么会失效
categories: [AI, CLAUDE]
description: 解析 CLAUDE.md 的底层逻辑、注入机制与最佳实践，帮助你快速理解 Claude 的配置思路。
keywords: CLAUDE.md, Claude, Anthropic, prompt engineering, best practices
mermaid: false
sequence: false
flow: false
mathjax: false
mindmap: false
mindmap2: false
---
# Claude Code Memory 系统底层逻辑全解析：你的“记忆”为什么会失效？

上一篇我们重写了 `CLAUDE.md`，但那只是表层。今天这篇，我们顺着代码调用栈继续往下，扒开 Claude Code 的 **Memory 系统**，看看你的指令在底层究竟被赋予了什么级别的权重。

你让 Claude Code “记住”的东西，下次对话它可能**完全不记得**。或者记得，但**不照做**。

这并不是功能坏了，而是很多人没有真正搞清楚：这些 memory 在系统里到底是怎么流动的，存在哪、怎么加载、权重多高、什么格式才有效。

把这条链路弄明白，memory 才会真正起作用。

> 同样是“记住一条规则”，放错地方，它只是备注；放对地方，它才会变成高权重行为约束。

---

## 目录

- [1. Memory 存在哪](#1-memory-存在哪)
- [2. 它怎么被加载到模型里](#2-它怎么被加载到模型里)
- [3. `MEMORY.md` 是索引，不是记事本](#3-memorymd-是索引不是记事本)
- [4. 四种类型：按对行为的影响排序](#4-四种类型按对行为的影响排序)
- [5. 什么不该存](#5-什么不该存)
- [6. 陈旧机制：老 memory 会被警告](#6-陈旧机制老-memory-会被警告)
- [7. 你没说“记住”，它也可能自动存](#7-你没说记住它也可能自动存)
- [8. `/compact` 之后，Memory 会重新加载](#8-compact-之后memory-会重新加载)
- [9. Memory 和 `CLAUDE.md` 应该怎么配合](#9-memory-和-claudemd-应该怎么配合)
- [10. 安全边界](#10-安全边界)

---

## 1. Memory 存在哪

Claude Code 的 memory 文件并不是“云里一团神秘状态”，而是**实际存放在本地文件系统中的 Markdown 文件**，并且按项目隔离。

典型结构如下：

```text
~/.claude/projects/{sanitized-project-path}/memory/
├── MEMORY.md              ← 索引文件
├── user_profile.md        ← topic 文件
├── feedback_no_summary.md
├── project_deadline.md
└── reference_linear.md
```

其中：

- `{sanitized-project-path}` 是项目根目录路径经过处理后的标识
- 不同项目的 memory **互不干扰**
- 这些文件本质上就是普通 Markdown 文件，**可以直接用编辑器打开和修改**

这意味着一件非常重要的事：

> Claude Code 的 memory 不是抽象概念，而是一套本地可见、可编辑、可调试的文件系统结构。

---

## 2. 它怎么被加载到模型里

这是整篇最关键的一点。

Claude Code 的输入结构，核心分成两层：

- **System Prompt**
- **User Message**

而 `Memory` 和 `CLAUDE.md`，恰好分别落在这两层里。

### 2.1 Memory 在 System Prompt 里

Memory 被放在 system prompt 的高优先级部分，大致位置是：

```text
System Prompt（优先级更高）：
  位置 1-9：静态指令（身份、工具使用规范、语气等）
  位置 10：会话指导
  位置 11：★ Memory 系统指令 + MEMORY.md 索引内容
  位置 12-18：环境信息、MCP 指令等
```

### 2.2 `CLAUDE.md` 在 User Message 里

而 `CLAUDE.md` 在另一层：

```text
User Message（优先级更低）：
  第一条：★ CLAUDE.md 内容（包在 <system-reminder> 里，带降权提示）
  第二条：你的第一句话
  后续：对话历史
```

### 2.3 两者最关键的差异

这两个系统最大的区别有两个：

#### Memory 没有降权

Memory 在 system prompt 中，模型会被明确告知：

- 这是一个持久化记忆系统
- 这些信息是可以直接拿来参考和应用的

它没有“可能不相关”的提醒。

#### `CLAUDE.md` 带降权提示

`CLAUDE.md` 注入时，会附带类似这样的语义：

> this context may or may not be relevant to your tasks

也就是说，模型被明确提醒：**这些内容可能相关，也可能不相关。**

### 2.4 结论非常直接

同一条指令：

- 放在 `Memory` 里
- 和放在 `CLAUDE.md` 里

前者**更容易被遵守**。

这不是玄学，也不是“感觉”，而是由**注入层级**和**是否带降权声明**直接决定的。

> **Memory 更像系统级行为约束，CLAUDE.md 更像用户提供的上下文参考。**

---

## 3. `MEMORY.md` 是索引，不是记事本

很多人第一次使用 Memory，都会犯同一个错误：

**往 `MEMORY.md` 里塞大段详细内容。**

问题在于，`MEMORY.md` 有硬编码截断限制。

```text
MAX_ENTRYPOINT_LINES = 200      // 超过 200 行，后面的直接丢弃
MAX_ENTRYPOINT_BYTES = 25_000   // 超过 25KB，在最近的换行处截断
```

也就是说：

- 超过 **200 行**，后面的内容直接被裁掉
- 超过 **25KB**，会在最近换行处截断
- 截断后系统还会自动追加警告

例如：

```md
> WARNING: MEMORY.md is 350 lines (limit: 200). Only part of it was loaded.
> Keep index entries to one line under ~200 chars; move detail into topic files.
```

### 3.1 正确用法：把 `MEMORY.md` 当成索引入口

`MEMORY.md` 最合理的用法不是写正文，而是做索引。

例如：

```md
- [用户画像](user_profile.md) — 高级 Go 开发者，偏好简洁代码
- [不要总结](feedback_no_summary.md) — 回答结束不要总结做了什么
- [发布冻结](project_release_freeze.md) — 2026-04-03 前不合并非关键 PR
```

推荐原则：

- 每条只占一行
- 每行尽量控制在 **150 字符以内**
- 用简短描述告诉模型：这个 topic 文件里存的是什么

### 3.2 为什么索引描述必须写清楚

因为 system prompt 中，默认注入的是：

- Memory 系统的使用说明
- `MEMORY.md` 的索引内容

而不是所有 topic 文件的正文。

topic 文件通常只有在模型主动使用 Read 工具去读取时，才会真正看到详细内容。

所以模型会先根据 `MEMORY.md` 里的这一行描述来判断：

- 要不要读这个 topic
- 这个 topic 是否与当前任务相关

> **`MEMORY.md` 的每一行，不只是目录条目，更是模型做“要不要继续追读”的判断依据。**

---

## 4. 四种类型：按对行为的影响排序

Memory 文件可以通过 frontmatter 声明类型。常见有四种，按对 Claude 行为影响的强弱，大致可以这样理解：

1. `feedback` —— 影响最大
2. `user` —— 影响中等
3. `project` —— 影响中等
4. `reference` —— 影响最小

---

### 4.1 `feedback`：行为修正，权重最高

这是最重要的一类。

它用来记录：

- 你做错了什么，以后不要再这样
- 你做对了什么，以后继续保持

源码里对 `feedback` 的说明非常关键：

> Record from failure AND success: if you only save corrections, you will avoid past mistakes but drift away from approaches the user has already validated, and may grow overly cautious.

意思是：

- 不能只记“错误”
- 也要记“哪些做法用户已经明确认可”

否则模型会越来越保守，只知道避错，却不知道什么是你真正想要的正确风格。

#### 推荐结构：三段式

```md
---
name: no-extra-changes
description: 只改用户要求的部分，不要顺便改其他代码
type: feedback
---

只改用户要求改的部分。不要加注释、加类型标注、重构周围代码。

**Why:** 之前“顺手”改动多次引入新问题，用户需要精确控制变更范围。
**How to apply:** 所有代码修改操作。
```

#### 为什么一定要写 `Why`

因为没有 `Why`，模型只能机械执行。

有了原因，模型在遇到边缘场景时，才更可能做出合理判断，而不是死板套规则。

> **规则决定行为底线，Why 决定模型在边界场景中的判断力。**

---

### 4.2 `user`：用户画像，影响沟通方式

这一类存的是：

- 你是谁
- 你擅长什么
- 你偏好什么表达方式

例如：

```md
---
name: user-profile
description: 高级 Go 开发者，新接触 React，偏好简洁
type: user
---

用户是高级 Go 开发者，10 年经验。刚开始接触项目的 React 前端部分。
偏好简洁代码，不喜欢过度抽象。用中文交流。
```

它不会像 `feedback` 一样强力修正行为，但会持续影响模型的：

- 解释深浅
- 表达风格
- 默认语言
- 示例复杂度

---

### 4.3 `project`：项目背景，提供非代码可推导信息

这一类适合存放**无法直接从代码和 Git 历史中推导出来**的项目背景。

例如：

```md
---
name: release-freeze
description: 2026-04-03 起冻结非关键合并，移动端切 release 分支
type: project
---

2026-04-03 起冻结非关键 merge，移动端团队切 release 分支。

**Why:** 移动端发版需要稳定的代码基线。
**How to apply:** 2026-04-03 后不建议合并非关键 PR。
```

这里有一个非常重要的细节：

### 4.4 相对日期要改成绝对日期

例如不要写：

- 下周四
- 这个月底
- 明天开始冻结

因为 memory 是跨会话长期存在的。

“周四”这次看是这个周四，下次看就不一定是哪天了。

正确写法应该是：

- `2026-04-03`
- `2026-04-30`

> **Memory 是长期上下文，不适合保存依赖“当前时间”的模糊表达。**

---

### 4.5 `reference`：外部指针，权重最低

这类主要是给模型留“去哪里找信息”的线索。

例如：

```md
---
name: bug-tracker
description: pipeline bug 在 Linear 的 INGEST 项目追踪
type: reference
---

Pipeline 相关 bug 在 Linear 项目 “INGEST” 中追踪。
```

它不会强烈改变模型行为，更像一个外部知识入口。

---

## 5. 什么不该存

不是所有“有用信息”都值得进入 memory。

源码里实际上有一套很明确的排除清单，核心原则就是：

> **能从别处可靠获得的信息，不值得占用 memory。**

不建议存入 memory 的内容包括：

- **代码模式、架构、文件路径** —— 读代码就能知道
- **Git 历史、谁改了什么** —— `git log` / `git blame` 才是权威来源
- **调试方案和修复步骤** —— 如果修复已经完成，信息应体现在代码里
- **`CLAUDE.md` 已经明确写过的规则** —— 重复没有意义
- **临时任务进度、当前会话上下文** —— 这应属于任务系统，不是 memory

### 5.1 一个特别值得注意的原则

如果用户要求：

- “记住这个 PR 列表”
- “记住这次活动总结”

真正值得存的，往往不是列表本身，而是：

- 哪个点是反直觉的
- 哪个约束是后来才发现的
- 哪个结论是不能从历史记录里直接看出来的

也就是说，应该保存的是：

- **惊讶点**
- **非显而易见点**
- **高复用判断**

而不是一整个可以从外部系统重新拉出来的清单。

---

## 6. 陈旧机制：老 memory 会被警告

Claude Code 不会把 memory 当成永远正确的事实。

系统会根据 memory 文件的修改时间，自动附加陈旧提示。

大致逻辑如下：

- **今天 / 昨天**：无警告
- **2 天以上**：附加提醒

提醒的大意是：

> This memory is N days old. Memories are point-in-time observations, not live state — verify against current code before asserting as fact.

意思很明确：

- memory 是某个时间点的观察结果
- 不是实时状态
- 使用前应该先和当前代码核对

### 6.1 如果 memory 提到路径或函数名，要先验证

源码还规定了一个非常实用的验证原则：

- 如果 memory 提到了某个**文件路径**，先检查文件是否还存在
- 如果 memory 提到了某个**函数名**，先搜索确认它是否还在

也就是说：

> “memory 说它存在” ≠ “它现在真的还存在”。

所以，不推荐写这种极易过时的内容：

- `handleAuth 在 main.go 第 42 行`

更推荐写成：

- 项目使用中间件模式处理认证，入口在 `main.go`

前者依赖行号，代码一改就失效；后者保留结构性信息，更耐久。

---

## 7. 你没说“记住”，它也可能自动存

很多人以为只有在自己明确说出“记住这个”的时候，Claude Code 才会写 memory。

其实并不一定。

Claude Code 还存在一个**后台自动提取机制**。

在满足某些条件时，系统会在主回答完成后，启动一个后台 agent 扫描对话内容，并自动提取值得保存的信息。

通常需要满足以下条件：

1. 本轮主 agent **没有手动写过 memory**
2. `extractMemories` feature flag 启用
3. 自动 memory 功能开启

这意味着：

- 你的 memory 目录里，可能会出现你**没有主动要求保存**的文件
- 那并不是异常，而是后台 agent 自动提取的结果

> **你看到的 memory，不一定全是“你让它记住的”，也可能是“系统判断值得保留的”。**

---

## 8. `/compact` 之后，Memory 会重新加载

执行 `/compact` 或 `/clear` 时，Memory 的缓存会被清掉。

相关逻辑大致如下：

```ts
function runPostCompactCleanup(): void {
  resetGetMemoryFilesCache('compact')   // Memory 文件缓存清除
  clearSystemPromptSections()           // 包括 memory section
}
```

### 8.1 这意味着什么

如果你在对话进行到一半时：

- 手动打开 memory 文件
- 改了一条 feedback
- 或增加了一条新的 topic

那么执行一次 `/compact` 后，下一轮对话就会重新读取这些内容。

也就是说：

- **不需要重启**
- **不需要重新开新会话**
- 只要触发重新加载，修改就会生效

这对调试 memory 规则非常实用。

---

## 9. Memory 和 `CLAUDE.md` 应该怎么配合

这两个系统不是互相替代，而是应该**分工协作**。

有一个核心原则必须记住：

> **不要把 `CLAUDE.md` 已经写过的内容，原封不动再存进 memory。**

源码层面其实是反对这种重复的。

### 9.1 正确分工

更合理的用法是：

- **`CLAUDE.md` 放规则**
- **Memory 放对规则的强化、纠偏和例外说明**

例如：

`CLAUDE.md` 已经写了：

- commit message 用中文

但模型总是忘。

这时不要在 memory 里再机械重复一遍“commit message 用中文”，而是写成一条 `feedback`：

```md
---
name: enforce-chinese-commit
description: 强调 commit message 必须中文，之前多次忘记
type: feedback
---

CLAUDE.md 中的“commit message 用中文”规则必须严格遵守。

**Why:** 之前多次输出英文 commit message，用户每次都要手动改。
**How to apply:** 每次 git commit 前检查 message 是否为中文。
```

### 9.2 为什么这样更有效

因为这相当于做了两层约束：

- `CLAUDE.md` 在 user message 里，权重较低
- `feedback` 在 system prompt 里，权重更高

它不是简单重复，而是：

- 上层给出规则
- 下层通过历史反馈加固执行

这种组合，往往比把同一句话写两遍有效得多。

> **`CLAUDE.md` 定义“应该怎么做”，Memory 强化“这件事必须真的做到”。**

---

## 10. 安全边界

Memory 虽然很强，但系统在路径权限上有明确防护。

一个非常关键的设计是：

### 10.1 项目级 `settings.json` 不能修改 memory 目录

原因很简单：这是安全边界。

如果项目级配置也能随意改 memory 路径，恶意仓库就可能把路径定向到敏感目录，例如：

- `~/.ssh`
- shell 配置文件
- 其他本地私密目录

然后诱导 AI 往里写内容。

因此系统明确排除了这种可能：

- **项目级 settings 不能改 memory 目录**
- 只有**用户级**或**管理员级**配置才可以调整路径

### 10.2 但内容本身没有校验

路径受保护，不代表内容会被审查。

实际上，memory 文件中的内容基本没有额外校验：

- 你写什么进去
- 系统就按什么注入到 system prompt

这是设计上的有意为之，因为这些文件就在你的本地磁盘上，默认认为：

- 你拥有它们的控制权
- 你也承担内容准确性的责任

所以它既强大，也要求你更谨慎。

---

## 总结

很多人把 Claude Code 的 Memory 理解成“一个自动记忆功能”，但从底层来看，它其实是一套：

- 本地文件存储系统
- system prompt 注入机制
- 类型化行为约束结构
- 可缓存、可重载、可衰老的持久化上下文系统

真正影响效果的关键，不是“有没有存”，而是：

- 存在了什么位置
- 是什么类型
- 是否写成了模型能理解和调用的格式
- 是否会因为老化、截断、重复而失效

可以把整套方法浓缩成下面几条：

1. **把 `MEMORY.md` 当索引，不要当正文**
2. **优先把高价值规则写成 `feedback`**
3. **给 `feedback` 补上 `Why` 和 `How to apply`**
4. **不要存代码里本来就能看出来的东西**
5. **相对时间一律改成绝对日期**
6. **让 Memory 强化 `CLAUDE.md`，而不是重复 `CLAUDE.md`**
7. **记住：老 memory 不是事实，只是历史观察**
8. **必要时用 `/compact` 强制重新加载，验证修改是否生效**

> 你不是在“给 AI 留备注”，而是在设计一套真正会进入 system prompt 的长期行为控制层。

把这点想明白，Memory 才不再是“好像记住了什么”，而会真正变成你能持续调教、持续复用、持续增强的系统能力。
