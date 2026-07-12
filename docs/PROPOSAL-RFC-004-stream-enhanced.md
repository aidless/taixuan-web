# RFC-004 · taixuan-web 流式再增强

**状态**:📋 草案
**作者**:刘泽文
**日期**:2026-07-13
**目标版本**:v1.3

## 一、v1.1 流式现状

| 项 | 状态 |
|---|---|
| SSE 流式输出(逐 token)| ✅ 完成 |
| 思考过程(reasoning_content)分离 | ✅ 完成 |
| AbortController 中止按钮 | ✅ 完成 |
| chunk_count 字数计数 | ✅ 完成 |

**当前痛点(用户反馈 + 我设计时发现)**:

1. ✗ **reasoning 完整展示只有前 500 字**(超出截断)
2. ✗ **没有 token 速率显示**(用户不知道还要等多久)
3. ✗ **网络断流时流中断,用户不知道原因**(只显示"加载中")
4. ✗ **流式完成后,没有"复制 / 收藏 / 分享"按钮**
5. ✗ **所有派别共用同一份系统 prompt**(没有派别定制能力)

## 二、本 RFC 解决 5 个痛点

### 痛点 1 · reasoning 完整展示

**当前限制**:`result-reasoning` div 只显示 "思考过程(XX字):" + 前 500 字符
**改进**:
- 加 "展开完整思考" 按钮
- 后端 SSE 增加 `reasoning_chars` 字段,前端用 v1.1 的 abbreviations
- 完整 reasoning 放在 `<details><summary>展开 XXX 字思考过程</summary>...</details>`

### 痛点 2 · 实时 token 速率 + 剩余时间

**新增字段**:
```javascript
// 前端每秒更新 meta 区
"正在流式生成 · 12.5 tokens/s · 预计还要 8 秒"
```

**实现**:
- 后端 SSE 每隔 1 秒算 tps
- 前端定时器读出最近 10 chunk 的 timestamp 差,算速率
- 用 max_tokens 推算剩余

### 痛点 3 · 网络断流反馈

**当前**:`fetch` 失败只显示 "连接错误,请重试"
**改进**:
- 区分 fetch 失败类型(network / server / parse)
- 显示明确提示"网络中断,点击此处重连"
- 重连按钮调 `streamReading(url, formData, callbacks)`,带上 `resume=true`

**后端配合**:
- 接受 `?resume_from_token=N` 参数(从上次 token 续传)
- 需要 chat 状态暂存(简化:不真续传,只重跑整个)

### 痛点 4 · 流式完成后操作

**新增按钮区**:
- 📋 复制全文(textarea.select() + Clipboard API)
- ★ 收藏(登录用户)
- 🔗 分享(生成分享链接带解读 ID)
- 💾 下载 Markdown(.md 文件)

**前端实现**:
```html
<div id="result-actions" class="hidden">
  <button onclick="copyResult()">📋 复制</button>
  <button onclick="downloadMarkdown()">💾 下载</button>
</div>
```

### 痛点 5 · 派别定制能力(可选)

**当前痛点**:`build_messages()` 用 `cfg["role"]`(8 派共用同一字段)
**扩展**:增加 `cfg["stream_custom"]` 字段(可选),派别特定 SSE 增强:
- `bazi`:额外推 `chart_summary`(八字排盘信息)
- `tarot`:额外推 `cards_drawn`(已抽牌)
- `vedic`:额外推 `planetary_positions`(星位)

## 三、本 RFC 实施(2-3h 工作量)

| 任务 | 文件 | 工作量 |
|---|---|---:|
| reasoning 完整展开 | 8 派 HTML + stream.js | 30 min |
| tps 计算 + UI | stream.js + 后端 | 1h |
| 网络中断检测 + 重连提示 | stream.js | 30 min |
| 复制 / 下载 / 分享按钮 | 8 派 HTML + JS | 45 min |
| 单元测试 + 文档 | tests/ | 30 min |
| **总计** | | **3.5h** |

## 四、不做(明确划线)

| 不做 | 原因 |
|---|---|
| 派别定制 stream 字段(痛点 5)| 复杂度高,先解决前 4 个 |
| 多 LLM 切换 UI | v2.0 用户系统 + 付费后再做 |
| 流式断点真续传 | 需要 chat 状态机,简化:重新跑 |

## 五、成功标准

- 流式开始后 1 秒看到 token 速率
- 流中断显示明确"网络中断"提示 + 重连按钮
- 流式完成后显示 [复制 / 下载 / 分享] 按钮
- reasoning 超过 500 字时显示 "展开完整思考"
- Lighthouse Performance 分数不下降(< 200ms 额外负载)

---

_本 RFC 草案 · 2026-07-13 01:30 整理_