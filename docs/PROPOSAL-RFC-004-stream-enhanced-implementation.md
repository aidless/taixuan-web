# RFC-004 流式增强实施清单

> 给未来"白天精力足时"的刘泽文。每个痛点都有具体步骤 + 代码骨架 + 验证点。

## 痛点 1 · reasoning 完整展示

### 后端改动:`app.py` reading_stream()

**当前**(`yield f"data: {json.dumps({'type': 'done', 'reasoning_text': reasoning_text, ...})"`):

**改为**:
```python
# 流式推完成后,前端用 data.reasoning_text 拿全文
# 但 done 时也告诉前端 reasoning 总长度
done_payload = {
    "type": "done",
    "full_text": state["full_text"],
    "reasoning_text": state["reasoning_text"],
    "reasoning_chars": len(state["reasoning_text"]),  # 🆕
    "latency_sec": elapsed,
    "chunk_count": state["chunk_count"],
    "disclaimer": fallback_text,
}
```

### 前端改动:`static/js/stream.js` v3.0

**扩展 onDone callback**:
```javascript
if (data.type === 'done') {
  // reasoning 完整模式
  if (data.reasoning_chars > 500) {
    // 用 <details> 折叠
    onReasoningComplete?.({
      totalChars: data.reasoning_chars,
      truncated: data.reasoning_text.substring(0, 500) + '...',
      full: data.reasoning_text,
    });
  }
}
```

### 8 派 HTML 改造:bazi.html

**改 onDone 段**:
```javascript
// 现有:resultReasoning.textContent = '思考过程(' + reasoningChars + ' 字):\n\n' + data.reasoning_text.substring(0, 500) + '...';
// 改为:
if (data.reasoning_chars > 500) {
  resultReasoning.innerHTML = `
    <details>
      <summary>思考过程(${data.reasoning_chars} 字) - 点击展开完整</summary>
      <pre>${escapeHtml(data.reasoning_text)}</pre>
    </details>
  `;
} else {
  resultReasoning.textContent = `思考过程(${data.reasoning_chars} 字):\n\n` + data.reasoning_text;
}
```

**注意**:`escapeHtml()` 防 XSS(放在 stream.js 工具函数中)。

## 痛点 2 · token 速率 + 剩余时间

### 后端:不做改动(由前端算)

**原理**:
- 后端每个 chunk 都带 timestamp(已经在 `t0` 里)
- 前端每 10 chunk 算一次:tokens/sec = 10 chunks / (last_ts - first_ts)
- 剩余:max_tokens / rate

### 前端:`static/js/stream.js` 新增 tps 计算

```javascript
let chunkTimes = []; // 最近 10 个 chunk 的 timestamp

// 在 onContent callback 里:
const now = performance.now();
chunkTimes.push(now);
if (chunkTimes.length > 10) chunkTimes.shift();

if (chunkTimes.length >= 2) {
  const span = (chunkTimes[chunkTimes.length - 1] - chunkTimes[0]) / 1000;
  const tps = (chunkTimes.length - 1) / span;
  const maxTokens = 2500;
  const currentChars = contentChars; // 累计已生字
  const remaining = Math.max(0, maxTokens - currentChars / 2); // 粗略:2 chars/token
  const etaSec = tps > 0 ? remaining / tps : 0;

  onProgress?.({
    tps: tps.toFixed(1),
    etaSec: Math.ceil(etaSec),
    chunks: data.chunk_count,
    chars: contentChars,
  });
}
```

### 8 派 HTML 显示

```html
<!-- 在 result-meta div 里 -->
<span id="stream-progress"></span>
```

```javascript
// 新 callback:onProgress
onProgress: ({ tps, etaSec, chunks, chars }) => {
  resultMeta.textContent = `派别:{{ liupai_name }} · ${chars} 字 · ${chunks} chunks · ${tps} tok/s · 预计 ${etaSec}s`;
},
```

## 痛点 3 · 网络中断反馈

### 前端:`static/js/stream.js` 区分错误类型

```javascript
async function streamReading(url, formData, callbacks) {
  const controller = new AbortController();
  (async () => {
    try {
      const resp = await fetch(url, { ... });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      // ... 正常处理
    } catch (err) {
      if (err.name === 'AbortError') return; // 用户主动

      // 区分错误类型
      let errType = 'unknown';
      if (err.message.includes('Failed to fetch') || err.message.includes('NetworkError')) {
        errType = 'network';
      } else if (err.message.includes('500')) {
        errType = 'server';
      } else if (err.message.includes('JSON')) {
        errType = 'parse';
      }

      callbacks.onError?.({
        type: errType,
        message: err.message,
        canRetry: errType === 'network', // 网络错可重试
      });
    }
  })();
  return controller;
}
```

### 8 派 HTML 重连按钮

```javascript
onError: (err) => {
  loading.classList.add('hidden');
  submitBtn.disabled = false;
  let errMsg = '出错了:' + err.message;
  let retryBtn = '';
  if (err.type === 'network') {
    errMsg = '网络中断,请检查连接';
    retryBtn = '<button onclick="location.reload()">🔄 重试</button>';
  }
  document.getElementById('error-msg').innerHTML = errMsg + retryBtn;
  errorBox.classList.remove('hidden');
}
```

## 痛点 4 · 流式完成后操作

### 后端:加 /api/v2/history/<id>/export.md 路由

```python
@app.route("/api/v2/history/<int:reading_id>/export.md", methods=["GET"])
def export_reading_md(reading_id: int):
    """导出某条解读为 Markdown"""
    conn = get_db()
    row = conn.execute("SELECT * FROM readings WHERE id = ?", (reading_id,)).fetchone()
    conn.close()
    if not row:
        return "Not found", 404
    md = f"""# 解读 #{row['id']}

派别: {row['liupai']}
问题: {row['question']}
时间: {row['created_at']}
耗时: {row['latency_sec']:.1f}s
后端: {row['backend']}

---

{row['response_text']}

---

## 思考过程

{row['reasoning_text']}

---

*本解读由 taixuan-web 生成,仅供参考与娱乐*
"""
    return md, 200, {'Content-Type': 'text/markdown; charset=utf-8'}
```

### 前端:复制 / 下载按钮

```html
<!-- 在 result 区添加 -->
<div id="result-actions" class="result-actions hidden">
  <button onclick="copyResult()">📋 复制</button>
  <button onclick="downloadMarkdown()">💾 下载</button>
</div>
```

```javascript
function copyResult() {
  const text = document.getElementById('result-text').textContent;
  navigator.clipboard.writeText(text).then(() => {
    alert('已复制到剪贴板');
  });
}

function downloadMarkdown() {
  // 用 /api/v2/history/<id>/export.md(需要先有 reading_id)
  // 简化方案:本地构造 md
  const text = document.getElementById('result-text').textContent;
  const md = `# 解读结果\n\n${text}\n\n---\n\n*本解读由 taixuan-web 生成*`;
  const blob = new Blob([md], {type: 'text/markdown'});
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `taixuan-${Date.now()}.md`;
  a.click();
}
```

## 痛点 5 · 派别定制(可选,本期不做)

如果想做:
- 8 派 YAML 加 `stream_custom` 字段
- 后端按字段推额外 SSE event
- 前端按 event type 渲染

**本次不做,放 v1.4**。

## 实施步骤(按顺序)

| # | 任务 | 文件 | 工作量 |
|---|---|---|---:|
| 1 | reasoning 完整展示(痛点 1) | stream.js + 8 HTML | 30 min |
| 2 | tps 计算 + 显示(痛点 2) | stream.js + 8 HTML | 1h |
| 3 | 网络中断检测(痛点 3) | stream.js + 8 HTML | 30 min |
| 4 | 复制 / 下载按钮(痛点 4) | 8 HTML + 新 API | 45 min |
| 5 | 单元测试 + 验证 | tests/ | 30 min |
| **总** | | | **3.5h** |

## 单元测试扩展(`tests/test_app.py`)

```python
def test_tps_calculation():
    """tps 应该在 0.5s 内 5 个 chunk 时算出"""
    times = [0, 0.1, 0.2, 0.3, 0.4, 0.5]
    span = (times[-1] - times[0]) / 1
    tps = (len(times) - 1) / span  # 10
    assert tps == 10

def test_reasoning_chars_threshold():
    """超过 500 字应该折叠"""
    long_reasoning = "x" * 800
    assert len(long_reasoning) > 500
    # 实际 HTML 用 <details> 折叠

def test_export_md_route():
    """/api/v2/history/<id>/export.md 返回 markdown"""
    # 模拟 save_reading 然后 GET export.md
    # 断言 Content-Type 是 markdown
```

## 成功标准 Checklist

- [ ] reasoning > 500 字显示 `<details>` 折叠
- [ ] 流式过程显示 "12.5 tok/s · 预计 8s"
- [ ] 网络中断显示 "🔄 重试" 按钮
- [ ] 流式完成后显示 [📋 复制] [💾 下载] 按钮
- [ ] 点击下载生成 .md 文件
- [ ] 5 个新单元测试通过
- [ ] Lighthouse 性能分数不下降

## 不做

- [ ] 派别定制流式字段(痛点 5)
- [ ] 断点真续传(需要 chat 状态机)
- [ ] 多 LLM 切换 UI

---

_实施清单 · 触发条件:有 100+ 用户时启动 · 2026-07-13 01:55 整理_