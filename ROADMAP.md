# 路线图 · Roadmap

泰玄小站 v1.0 已完成。本文档列出未来版本的功能规划与实施细节。

---

## 当前状态 v1.0(已完成,2026-07-12)

| 模块 | 状态 |
|---|---|
| Flask 应用 | 完成 |
| 8 派页面(bazi/ziwei/qimen/liuyao/meihua/tarot/western/vedic)| 完成 |
| DeepSeek v4-flash 真实 LLM | 完成 |
| Ollama qwen3:4b 兜底 | 完成 |
| Mock 开发后端 | 完成 |
| 8 派 prompt YAML 配置 | 完成 |
| 阿里云 ECS 部署(2C2G)| 完成 |
| supervisor 守护 | 完成 |
| GitHub 开源(MIT)| 完成 |
| 4 份文档(README/DEPLOY/CHANGELOG/LICENSE)| 完成 |

---

## 当前状态 v1.2(已完成,2026-07-12 深夜)

| 模块 | 状态 | 详情 |
|---|---|---|
| **工程优化 10 项** | 完成 | gzip / 缓存 / 限流 / CSP / 日志轮转 / Docker / SQLite / abort 按钮 |
| **Bug 修复 6 项** | 完成 | 🔴 BOM / init_db / 路由错装饰 / injection / 404 / import 重复 |
| **代码质量** | 提升 | reading_stream 116→51 行 + 4 helper;score_response 66→32 行 + 3 helper |
| **单元测试** | 新增 | tests/test_app.py 19 个测试覆盖校验/限流/中文/JSON/长度 |
| **GitHub commit** | `5405cee` | v1.2 feat 工程化 |
| **ECS 部署** | 待传 | 明天精力足时 |

**v1.2 改动统计**:
- 新文件 5:Dockerfile / docker-compose.yml / .dockerignore / .env.example / tests/test_app.py
- 修改 11:app.py / llm_backends.py / benchmark_llm.py / stream.js / 8 派 HTML
- 总 +600 行 / -200 行

**v1.2 关键 bug 修复**:
- 🔴 benchmark_llm.py UTF-8 BOM → 批量去 BOM 脚本
- 🔴 init_db() NameError → 移到 log 定义之后
- 🔴 _validate_question 被错误装饰成 reading_stream 路由 → helper 移到路由之后
- 🟠 Prompt injection → 加 7 关键词检测 + 500 字长度限制

---

## 当前状态 v1.1(已完成,2026-07-12 当晚)

| 模块 | 状态 | 详情 |
|---|---|---|
| 流式输出 SSE | 完成 | 8 派全跑,后端 reading_stream + 前端 streamReading |
| 用户体感提升 | 完成 | 第 1 秒开始有字,vs 之前等 15 秒 |
| LLM 调用方式 | 不变 | 还是 DeepSeek v4-flash |
| 端到端验证 | 完成 | 浏览器实测流式打字机效果正常 |
| GitHub 推送 | 完成 | commit `188fba7` |

**v1.1 改动统计**:
- llm_backends.py +140 行(4 个 chat_stream 方法)
- app.py +65 行(reading_stream SSE 路由)
- static/js/stream.js 67 行(公共流式客户端,新建)
- templates/liupai/*.html × 8(JS 段 fetch → streamReading)
- ROADMAP.md 新建
- **总计 +953 行 / -250 行**

**v1.1 bug 修复**:
- app.py:LIUPAI 名字错 → 改用 LIUPAI_IDS
- app.py:build_messages 参数错 → (name, form_data)

---

## 未来版本

### v1.1 — 用户体验层(预计 1-2 周)

目标:让用户停留时间更长、感知更快、运营有数据。

#### 1. 流式输出 SSE(Server-Sent Events)

**状态**:✅ **已完成** (commit `188fba7`,2026-07-12)

**实际效果**:
- 用户提交表单后,第 1 秒开始有字
- 后端 LLM 调用方式不变(DeepSeek v4-flash)
- 只是改变推送方式:逐 token yield,前端边收边渲染

**实施细节**:

| # | 任务 | 工作量 | 文件 | 状态 |
|---|---|---:|---|---|
| 1 | DeepSeekBackend 加 chat_stream() | 30 min | `llm_backends.py` | ✅ |
| 2 | OllamaBackend 加 chat_stream() | 20 min | `llm_backends.py` | ✅ |
| 3 | MockBackend 加 chat_stream() | 10 min | `llm_backends.py` | ✅ |
| 4 | LLMRouter 加 chat_stream() 调度 | 30 min | `llm_backends.py` | ✅ |
| 5 | Flask 加 /reading_stream SSE 路由 | 30 min | `app.py` | ✅ |
| 6 | 公共流式客户端 streamReading | 30 min | `static/js/stream.js` | ✅ |
| 7 | 8 派 HTML 改 JS 段 | 40 min | `templates/liupai/*.html` | ✅ |
| 8 | 端到端测试 + 调试 + 修 2 个 bug | 60 min | - | ✅ |
| **总计** | | **~3.5h** | | |

**痛点**:当前用户提交表单后,看到 5-15 秒转圈,然后一大坨文字突然刷出。LLM 实际在实时生成,但用户感知是"等待 + 突然出现"。

**方案**:把后端 LLM 的 token-by-token 输出实时推到前端,实现打字机效果。

**实施步骤**:

| # | 任务 | 工作量 | 文件 |
|---|---|---:|---|
| 1 | DeepSeekBackend 加 chat_stream() 方法,逐 chunk yield | 30 min | `llm_backends.py` |
| 2 | LLMRouter 加 chat_stream() 调度 | 20 min | `llm_backends.py` |
| 3 | Flask 加 /api/v2/liupai/<liupai>/reading_stream SSE 路由 | 30 min | `app.py` |
| 4 | 新建 static/js/stream.js 公共流式客户端 | 30 min | `static/js/stream.js` |
| 5 | 8 派 HTML 模板改 fetch 为 streamReading 调用 | 40 min | `templates/liupai/*.html` × 8 |
| 6 | nginx 反代配置(若启用 nginx) | 10 min | `nginx.conf` |
| 7 | 端到端测试 + 调试 | 60 min | - |
| **总计** | | **~3.5h** | |

**关键技术点**:

```python
# DeepSeek 流式 API
POST /chat/completions
{"model": "deepseek-v4-flash", "stream": true, "messages": [...]}

# 响应:每行一个 SSE 事件
data: {"id":"...","choices":[{"delta":{"content":"根"}}]}
data: {"id":"...","choices":[{"delta":{"content":"据"}}]}
data: {"id":"...","choices":[{"delta":{"content":"您"}}]}
...
data: [DONE]
```

```javascript
// 前端 EventSource 或 fetch + ReadableStream
const reader = resp.body.getReader();
const decoder = new TextDecoder();
let buffer = '';
while (true) {
  const {done, value} = await reader.read();
  if (done) break;
  buffer += decoder.decode(value, {stream: true});
  // 解析 SSE 协议:data: {...}\n\n
  // 每个 chunk 累加到 DOM
}
```

**注意事项**:
- **nginx 必须设 `proxy_buffering off`**,否则会缓冲到 response 完整才推
- Flask dev server 默认不缓冲,可以直接用
- 浏览器对 SSE 兼容性:除 IE 外都支持

**用户价值**:体感延迟从"等 15 秒"降到"第 1 秒就有字出现",实际是同样 15 秒,但感知完全不一样。

---

#### 2. 访问统计(umami 自托管)

**优先级**:中

**痛点**:网站上线后不知道:
- 多少人来过?
- 哪个派别最受欢迎?
- 转化率(首页 → 提交表单)多少?
- 用户来自哪里?

**方案**:umami 自托管,隐私友好,免费。

**为什么不用 Google Analytics**:
- GA 把数据送给 Google,有合规风险
- 国内访问 GA 经常被屏蔽
- umami 自托管,数据完全在自己 ECS 上

**为什么不用百度统计**:
- 百度统计是国内工具,合规风险更高(可能被用作审计追踪)
- 数据出境问题

**实施步骤**:

| # | 任务 | 工作量 | 备注 |
|---|---|---:|---|
| 1 | docker-compose.yml 加 umami 服务 | 20 min | umami + postgres |
| 2 | 配置 umami 管理后台密码 + 网站 | 10 min | 首次启动初始化 |
| 3 | 嵌 JS 追踪代码到 base.html | 10 min | 1 行 script |
| 4 | nginx 反代 /umami 路径(可选) | 20 min | 不暴露 3000 端口 |
| 5 | 部署 + 验证数据流入 | 30 min | - |
| 6 | 配置事件追踪(派别点击、提交表单) | 30 min | 知道哪些派别热 |
| **总计** | | **~2h** | |

**docker-compose.yml 示例**:

```yaml
services:
  umami:
    image: ghcr.io/umami-software/umami:postgresql-v2
    ports:
      - "127.0.0.1:3000:3000"
    environment:
      DATABASE_URL: postgresql://umami:umami@db:5432/umami
      APP_SECRET: <random-32-char>
    depends_on:
      - db
    restart: always

  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: umami
      POSTGRES_USER: umami
      POSTGRES_PASSWORD: umami
    volumes:
      - umami-db:/var/lib/postgresql/data
    restart: always

volumes:
  umami-db:
```

**前端嵌入**(base.html footer 段加):

```html
<script async defer data-website-id="<your-umami-id>" src="https://116.62.69.83/umami/script.js"></script>
```

**用户价值**:你能看到真实的流量数据,而不是猜"今天有没有人来"。

---

### v2.0 — 用户系统(预计 2-3 周)

目标:从匿名工具升级为有用户账号的"个人命理档案"。

#### 3. 用户系统 + 历史记录(SQLite)

**优先级**:低(流量起来前不上)

**痛点**:
- 用户每次都是匿名访问,没法看自己历史
- 没法建立用户粘性(回头客没动力)
- 没法做付费墙(不知道谁付了)

**方案**:SQLite + 邮箱验证码登录 + 历史记录存储。

**为什么不一开始就做**:
- SQLite + 用户系统 = ~10h 工作量
- v1.0 阶段日 UV 可能就 10-50,做了也是空跑
- **流量起来后再做**(umami 数据会告诉你什么时候该做)

**数据模型**:

```sql
-- 用户表
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    nickname TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login_at TIMESTAMP,
    is_active BOOLEAN DEFAULT 1
);

-- 验证码表
CREATE TABLE verification_codes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL,
    code TEXT NOT NULL,           -- 6 位数字
    expires_at TIMESTAMP NOT NULL,
    used BOOLEAN DEFAULT 0
);

-- 解读历史表
CREATE TABLE readings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    liupai TEXT NOT NULL,
    question TEXT,
    pan_input TEXT,               -- 排盘要素 JSON
    llm_response TEXT,           -- LLM 完整解读
    backend TEXT,                 -- deepseek-v3 / ollama-qwen3-4b / mock
    latency_sec REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- 索引
CREATE INDEX idx_readings_user_id ON readings(user_id);
CREATE INDEX idx_readings_created_at ON readings(created_at);
```

**实施步骤**:

| # | 任务 | 工作量 | 备注 |
|---|---|---:|---|
| 1 | Flask + SQLAlchemy 集成 | 1h | ORM + migration |
| 2 | 建表 + 索引 | 30 min | schema + 测试 |
| 3 | /api/v2/auth/send_code 路由(发邮件) | 1h | SMTP 配置 |
| 4 | /api/v2/auth/verify_code 路由(登录) | 1h | session/JWT |
| 5 | /api/v2/readings POST(保存) | 30 min | 解读完成自动入库 |
| 6 | /api/v2/readings GET 列表(分页) | 1h | - |
| 7 | /api/v2/readings/<id> GET 详情 | 30 min | - |
| 8 | DELETE /api/v2/readings/<id> | 20 min | - |
| 9 | DELETE /api/v2/users/me(账号注销) | 30 min | GDPR 合规 |
| 10 | /history 页面(解读列表) | 2h | 模板 + JS |
| 11 | /login 页面(邮箱输入 → 验证码) | 2h | UI |
| 12 | 登录态前端管理(localStorage / cookie)| 1h | - |
| 13 | 单元测试 + E2E 测试 | 2h | - |
| 14 | 隐私政策更新(GDPR-style 注销) | 1h | 法律 |
| **总计** | | **~14h** | |

**第三方依赖**:
- 邮件发送:**SendGrid** 免费层(100 邮件/天)/ **阿里云邮件推送** / 自建 SMTP(被反垃圾邮件)
- Session 管理:**Flask-Login** 或 **JWT**(无状态)

**用户价值**:
- 回头客能看到自己的"八字档案"
- 可对比不同时间的解读("我今年 vs 去年运势对比")
- 可分享解读链接给朋友

---

### v3.0 — 商业化(预计 1-2 月)

目标:从个人项目到可持续运营。

#### 4. 付费功能

**模式 A · 单次付费**(类似 ChatGPT)
- 每次解读收费 ¥1
- 微信扫码 / 支付宝
- 用户系统是前提

**模式 B · 包月订阅**
- ¥9.9/月,无限次解读
- 高级功能:更长解读、深度分析、跨派合参

**实施步骤**(粗略):
| # | 任务 | 工作量 |
|---|---|---:|
| 1 | 接入微信支付 / 支付宝 | 4h |
| 2 | 订单表 + 支付回调 | 2h |
| 3 | 配额控制(免费 5 次/天,会员无限) | 2h |
| 4 | 发票申请 | 1h |
| **总计** | | **~9h** |

**法律风险**:
- 命理类内容商业化合规复杂,需要 ICP + 算法备案
- 国内可能需要"经营性 ICP 许可证"
- **建议先做海外华人市场**(英文版 + Stripe)

---

#### 5. 移动端 PWA(Progressive Web App)

**痛点**:移动端体验好,但没法装 App。

**方案**:
- 加 `manifest.json`(应用元信息)
- 加 Service Worker(离线访问)
- 加 "添加到主屏幕" 引导

**实施步骤**:
| # | 任务 | 工作量 |
|---|---|---:|
| 1 | manifest.json + icons | 1h |
| 2 | Service Worker(离线 shell + 缓存策略) | 3h |
| 3 | "添加到主屏幕" 引导 UI | 1h |
| **总计** | | **~5h** |

---

#### 6. 多语言(i18n)

**目标市场**:海外华人 + 英文用户。

**优先级**:低(等流量有迹象再上)

**实施步骤**:
| # | 任务 | 工作量 |
|---|---|---:|
| 1 | Flask-Babel 集成 | 1h |
| 2 | 提取所有中文字符串到 .po 文件 | 2h |
| 3 | 翻译为英文(机械翻译 + 人工 review)| 4h |
| 4 | UI 加语言切换器 | 1h |
| **总计** | | **~8h** |

---

## 决策记录(为什么这么排优先级)

### 为什么流式 SSE 最优先

- **影响所有用户**:8 派都用 LLM,流式提升是普遍的
- **工作量适中**:3.5h,周末能搞定
- **零成本**:不增加 LLM API 调用量,只是改变推送方式
- **效果立竿见影**:体感差异巨大,用户会觉得"这网站快多了"

### 为什么 umami 第二

- **数据驱动决策**:没数据你不知道下一步该做什么
- **工作量小**:2h,一个 docker compose
- **不影响代码**:只是加一个 JS 标签
- **隐私友好**:不依赖外部服务

### 为什么用户系统低优先

- **工作量巨大**:14h,接近一周
- **v1.0 阶段用不到**:日 UV < 100 时做了也空跑
- **流量起来再做**:umami 数据会告诉你什么时候该做(看 PV / 重复访问率)
- **后期投入**:有用户系统才能做付费,这是 v3.0 的基础

### 为什么付费推后到 v3.0

- **法律风险高**:命理商业化在国内可能有监管问题
- **前提依赖**:没用户系统没法做付费墙
- **海外华人市场更稳**:避开国内合规,用 Stripe + 海外服务器

---

## 时间线(预估)

```
v1.0       v1.1.0          v1.1.1         v2.0.0          v3.0.0
2026-07    2026-07 第三周    2026-08 第一周    2026-08-09    2026-09-10
─●───────●──────────●──────────────●──────────────●─────────→
 │         │          │              │              │
 开源上线  + SSE 流式  + umami 统计   + 用户系统      + 付费 + PWA
                            SQLite + 邮箱登录
```

**总工作量估算**(从 v1.0 到 v3.0):
- v1.1.0 流式:3.5h
- v1.1.1 umami:2h
- v2.0 用户系统:14h
- v3.0 付费:9h
- v3.0 PWA:5h
- v3.0 i18n:8h
- **总计:~41.5h 工作量**

折算成连续开发:约 1 周全职。

---

## 评估触发器(什么时候做什么)

| 数据信号 | 触发动作 |
|---|---|
| **日 PV > 100** | 上 umami |
| **日 PV > 500 + 重复访问率 > 10%** | 上用户系统 |
| **月独立访客 > 5000** | 上付费墙 + PWA |
| **海外访客 > 20%** | 上 i18n 英文版 |

---

## 未来可能加的功能(头脑风暴)

- **跨派合参**:八字 + 紫微 + 塔罗 三派合参,LLM 综合解读
- **历史回顾**:"去年今日你测过什么"
- **AI 助手对话**:基于历史解读,跟 AI 持续对话
- **专家市场**:开放给真正命理师入驻,平台抽成
- **小程序回归**:微信小程序原生应用,做轻量入口
- **iOS / Android App**:React Native 打包
- **专业排盘库**:接 Swiss Ephemeris 精确排盘
- **OpenAI GPT 兜底**:除了 DeepSeek,加 OpenAI 当兜底

---

## 反馈

如果你想改优先级、加新功能、或者觉得某些不该做,在 GitHub Issues 提:

https://github.com/aidless/taixuan-web/issues

---

_最后更新:2026-07-12 23:50_
_版本:v1.0 完成 → v1.1 流式 SSE 完成 → v1.2 工程化完成(GitHub commit `5405cee`)_
_下一步:v1.2.1 ECS 部署 → v1.3 umami + 用户系统 v2.0 RFC_