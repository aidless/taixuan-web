# 泰玄小站 · Taixuan Web

> Flask + DeepSeek 写的传统文化解读网站。八派合参(八字、紫微、奇门、六爻、梅花、塔罗、西方占星、吠陀占星),LLM 实时生成解读。

**在线地址**:http://116.62.69.83

**源码**:https://github.com/aidless/taixuan-web

**声明**:本项目仅供文化参考与娱乐,不构成任何专业建议(医疗、法律、财务、心理咨询等)。

---

## 目录

- [项目背景](#项目背景)
- [核心特性](#核心特性)
- [系统架构](#系统架构)
- [技术栈](#技术栈)
- [目录结构](#目录结构)
- [数据流](#数据流)
- [LLM 集成设计](#llm-集成设计)
- [Prompt 工程](#prompt-工程)
- [8 派实现差异](#8-派实现差异)
- [部署架构](#部署架构)
- [性能与成本](#性能与成本)
- [安全与合规](#安全与合规)
- [路线图](#路线图)
- [贡献与许可](#贡献与许可)

---

## 项目背景

传统文化解读工具(命理、占卜、占星)在微信生态内有合规风险:

- **个人主体小程序** 不能上线命理类目(强制企业资质 + 算法备案)
- **关键词触发审核**:微信对"算命"、"占卜"、"预测"等词敏感,易下架
- **小程序 API 受限**:无原生 LLM 流式调用、JS 执行受限

**项目定位**:从微信小程序转向**独立网站**,绕开小程序合规限制。

**业务目标**:
1. 用 AI 让传统文化解读更易触达(免去翻书、找师傅)
2. 8 派合参(用户不用装 8 个 App)
3. 开源 MIT 协议,接受社区贡献

---

## 核心特性

### 1. 八派合参

| 派别 | 算法基础 | 输入 | 解读维度 |
|---|---|---|---|
| 八字 | 天干地支 + 五行生克 | 出生年月日时 | 命格、五行、十神、大运流年 |
| 紫微斗数 | 十四主星 + 十二宫 | 出生年月日时 | 命宫、财帛宫、官禄宫、夫妻宫 |
| 奇门遁甲 | 九宫八卦 + 时家奇门 | 起卦时间 + 问题 | 三奇、六仪、八门、九星 |
| 六爻 | 周易六十四卦 + 纳甲 | 起卦时间 + 问题 | 本卦、变卦、世爻、应爻 |
| 梅花易数 | 体用生克 + 数字起卦 | 数字 + 时间 | 体卦、用卦、互卦、变卦 |
| 塔罗 | 78 张神秘符号 | 牌阵 + 问题 | 大阿卡纳、小阿卡纳、逆位解读 |
| 西方占星 | 星盘相位 + 行星运行 | 出生时间地点 | 太阳、月亮、上升、水星 |
| 吠陀占星 | 二十七宿 + 印度古法 | 出生时间地点 | 命盘、月亮星座、Nakshatra |

### 2. 三级 LLM 兜底

| 优先级 | 后端 | 用途 | 响应时间 |
|---|---|---|---|
| 主路 | DeepSeek v4-flash | 日常解读 | 2-5 秒 |
| 兜底 | Ollama + qwen3:4b | 主路失败 / 离线 | 30 秒+ |
| 开发 | Mock | 无 key 时 | 0.3 秒 |

### 3. 自适应 Prompt 配置

8 派 prompt 独立成 YAML(`specs/prompts/*.yaml`),改一处不影响其他派。Schema 强约束输出格式(`specs/schools/*.result.schema.json`)。

### 4. 轻量部署

Flask 单进程,2C2G ECS(2 核 2GB)就能跑。无数据库、无 Redis、无外部服务依赖。

---

## 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                    浏览器 (用户)                              │
│  - HTML5 + CSS3 (无框架)                                       │
│  - localStorage (历史记录预留)                                  │
└────────────────────┬────────────────────────────────────────┘
                     │ HTTPS / HTTP
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                阿里云 ECS (116.62.69.83)                     │
│                  Ubuntu 22.04 / 2C2G                          │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Flask App (Python 3.10)                             │   │
│  │                                                       │   │
│  │  ┌────────────┐    ┌─────────────┐   ┌────────────┐ │   │
│  │  │  路由层    │───▶│  LLM Router │──▶│ DeepSeek   │ │   │
│  │  │  /liupai/* │    │             │   │ API        │ │   │
│  │  │  /api/v2/* │    │  三级兜底:   │   │ (外网)     │ │   │
│  │  │  /healthz  │    │  primary   │   └────────────┘ │   │
│  │  └────────────┘    │  fallback  │                   │   │
│  │         │           │  mock      │   ┌────────────┐ │   │
│  │         │           └─────────────┘──▶│ Ollama     │ │   │
│  │         │                              │ qwen3:4b   │ │   │
│  │         ▼                              │ (本地)     │ │   │
│  │  ┌─────────────────────────────┐      └────────────┘ │   │
│  │  │  Prompt 渲染引擎             │                      │   │
│  │  │  - 加载 specs/prompts/*.yaml│                      │   │
│  │  │  - Jinja2 模板渲染排盘要素   │                      │   │
│  │  │  - 引用 specs/compliance/   │                      │   │
│  │  └─────────────────────────────┘                      │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
                  ┌────────────────────┐
                  │  DeepSeek API       │
                  │  (api.deepseek.com) │
                  │  deepseek-v4-flash   │
                  └────────────────────┘
```

---

## 技术栈

### 后端

| 技术 | 版本 | 用途 |
|---|---|---|
| Python | 3.10+ | 主语言 |
| Flask | 3.0+ | Web 框架 |
| Gunicorn / Flask dev | - | WSGI 服务器 |
| requests / urllib | - | HTTP 客户端 |
| PyYAML | - | 加载 8 派 prompt 配置 |

### 前端

| 技术 | 用途 |
|---|---|
| HTML5 | 语义化结构 |
| CSS3 | 深色主题 + 金色点缀(无 Tailwind 等框架) |
| Vanilla JS | 表单提交 + fetch API |

### LLM

| 平台 | 模型 | 用途 |
|---|---|---|
| DeepSeek | deepseek-v4-flash | 主路(reasoning 模型) |
| Ollama | qwen3:4b | 兜底(本地) |

### 部署

| 组件 | 用途 |
|---|---|
| 阿里云 ECS | 服务器(2C2G) |
| Ubuntu 22.04 | 操作系统 |
| nohup + Flask | 进程管理 |
| Nginx (可选) | 反向代理 |

**为什么不选这些**:
- **不用数据库**:本项目无用户系统、无需持久化,SQLite 也省了
- **不用 Redis**:无缓存、无 Session
- **不用 Docker**:2C2G 跑 Docker 自己吃 500MB+,反而 OOM
- **不用 React / Vue**:8 个静态表单,Vanilla JS 够了
- **不用 Tailwind**:深色主题自写 CSS 才 6.5KB

---

## 目录结构

```
taixuan-web/
│
├── app.py                          # Flask 主入口
│                                    # 路由 + 模板渲染 + LLM 调用编排
│
├── llm_backends.py                 # LLM 路由器
│                                    # - DeepSeekBackend (主路)
│                                    # - OllamaQwenBackend (兜底)
│                                    # - MockBackend (开发)
│                                    # - LLMRouter (三级调度)
│
├── benchmark_llm.py                # LLM 对比测试脚本
│                                    # DeepSeek vs qwen3:4b 多维度基准
│
├── requirements.txt                # Python 依赖清单
│
├── README.md                       # 本文件
├── DEPLOY.md                       # 部署文档(ECS、Nginx、SSL)
├── CHANGELOG.md                    # 版本变更日志
├── LICENSE                         # MIT 协议
│
├── templates/                      # Jinja2 模板
│   ├── base.html                   # 基础布局(导航、页脚)
│   ├── index.html                  # 8 派卡片首页
│   ├── privacy.html                # 隐私政策
│   ├── terms.html                  # 服务条款
│   └── liupai/                     # 8 派子页
│       ├── bazi.html               # 八字
│       ├── ziwei.html              # 紫微
│       ├── qimen.html              # 奇门
│       ├── liuyao.html             # 六爻
│       ├── meihua.html             # 梅花
│       ├── tarot.html              # 塔罗
│       ├── western.html            # 西占
│       └── vedic.html              # 吠陀
│
├── static/
│   └── css/
│       └── style.css               # 全局样式(深色 + 金色)
│
├── specs/                          # 配置数据(运行时加载)
│   ├── prompts/                    # 8 派 LLM prompt YAML
│   │   ├── bazi.yaml
│   │   ├── ziwei.yaml
│   │   ├── qimen.yaml
│   │   ├── liuyao.yaml
│   │   ├── meihua.yaml
│   │   ├── tarot.yaml
│   │   ├── western-astro.yaml
│   │   ├── vedic.yaml
│   │   └── README.md               # Prompt 契约说明
│   │
│   ├── schools/                    # 8 派 LLM 输出 JSON Schema
│   │   ├── bazi.result.schema.json
│   │   ├── ziwei.result.schema.json
│   │   ├── qimen.result.schema.json
│   │   ├── liuyao.result.schema.json
│   │   ├── meihua.result.schema.json
│   │   ├── tarot.result.schema.json
│   │   ├── western-astro.result.schema.json
│   │   └── vedi.cresult.schema.json
│   │
│   └── compliance/                 # 合规配置
│       ├── mingli_banned_words.json    # 命理敏感词
│       ├── tone_rules.json             # 语气规则
│       └── disclaimer_templates.json   # 免责声明模板
│
└── tests/                          # 测试套件
    └── test_llm_backends.py        # LLM 后端单元测试
```

---

## 数据流

以"用户提交八字表单"为例:

```
用户浏览器                    Flask 应用                        DeepSeek API
─────────                    ─────────                        ─────────────
│                            │                                 │
│  1. 填写表单                │                                 │
│     (生日 + 问题)           │                                 │
│     │                       │                                 │
│     ▼                       │                                 │
│  2. POST /api/v2/liupai/bazi/reading                         │
│     │           ────────▶   │                                 │
│     │                       │ 3. 加载 specs/prompts/bazi.yaml│
│     │                       │                                 │
│     │                       │ 4. 渲染排盘要素                  │
│     │                       │    (用用户输入填 Jinja2 模板)    │
│     │                       │                                 │
│     │                       │ 5. 组装最终 prompt               │
│     │                       │    system: role + 语气规则       │
│     │                       │    user: 排盘 + 用户问题        │
│     │                       │                                 │
│     │                       │ 6. 调用 DeepSeekBackend.chat()   │
│     │                       │ ──────────────────────────────▶ │
│     │                       │                                 │
│     │                       │                       7. DeepSeek 生成
│     │                       │                          (2-5 秒)
│     │                       │                                 │
│     │                       │ 8. 后处理                       │
│     │                       │    - 截断超长段                  │
│     │                       │    - 替换敏感词                  │
│     │                       │    - 注入免责声明                │
│     │                       │ ◀────────────────────────────── │
│     │                       │                                 │
│     │   9. JSON 响应        │                                 │
│     ◀────────────────────   │                                 │
│     │                       │                                 │
│ 10. 渲染解读结果           │                                 │
│     (派别、后端、耗时)      │                                 │
│     ▼                       │                                 │
│  11. 用户阅读               │                                 │
└────────────────────────────┴─────────────────────────────────┘
```

**关键路径耗时**(实测 116.62.69.83):
- 网络往返:< 100ms(国内到 DeepSeek)
- DeepSeek 推理:2-5 秒(reasoning 模型 + 中文生成)
- 后处理:< 50ms
- **总耗时:5-15 秒**

---

## LLM 集成设计

### 设计目标

1. **可降级**:DeepSeek 挂了能用本地模型,本地模型挂了能返回 mock
2. **可观测**:每次调用记录 backend、latency、是否降级
3. **可扩展**:加新后端只需实现 `LLMBackend` 协议
4. **零依赖**:不绑 LangChain / LlamaIndex

### LLMBackend 协议

```python
from typing import Protocol, List, Dict

class LLMBackend(Protocol):
    name: str

    def chat(
        self,
        messages: List[Dict],         # [{"role": "system", "content": ...}, ...]
        temperature: float = 0.7,
        max_tokens: int = 2500,
    ) -> Dict:
        """
        返回:
        {
            "text": str,                  # 生成的文本
            "backend": str,               # 后端标识
            "fallback_used": bool,        # 是否走了降级
            "latency_sec": float,         # 耗时
            "error": str | None,          # 错误信息
        }
        """
```

### LLMRouter 调度逻辑

```python
class LLMRouter:
    def __init__(self):
        self.primary = DeepSeekBackend()       # 主路
        self.fallback = OllamaQwenBackend()    # 兜底
        self.mock = MockBackend()              # 开发

    def chat(self, messages, temperature, max_tokens):
        # 1. 试主路
        result = self.primary.chat(messages, ...)
        if result["text"] and not result["error"]:
            return result

        # 2. 主路失败,试兜底
        result = self.fallback.chat(messages, ...)
        if result["text"] and not result["error"]:
            result["fallback_used"] = True
            return result

        # 3. 都失败,返回 mock
        return self.mock.chat(messages, ...)
```

### 关键决策

- **为什么 max_tokens=2500**:DeepSeek v4-flash 是 reasoning 模型,推理 token 占 50%+,默认 1500 太少会输出空
- **为什么不用 streaming**:v1.0 阶段先把同步跑通,后续接 SSE 流式输出
- **为什么记 fallback_used**:让前端知道是真实 LLM 还是降级,数据透明

---

## Prompt 工程

### 8 派 Prompt 独立成 YAML

每个派别有独立 prompt 配置(`specs/prompts/<liupai>.yaml`),改一个不影响其他。

```yaml
# 例:bazi.yaml
liupai: bazi
version: '1.0.0'
output_schema_ref: ../schools/bazi.result.schema.json

role: |
  你是一位资深的八字命理研究者...

style:
  max_words: 500
  tone: warm
  banned_phrases:
    - 命中注定
    - 注定
    - 100%
  requirements:
    - 用概率性语言(通常、可能、倾向)
    - 多具体场景(工作、感情、决策)
    - 避免恐吓性结论

output_format:
  - { id: total_lun,    title: '命格总论',   min_words: 80,  max_words: 120 }
  - { id: question,     title: '所问分析',   min_words: 100, max_words: 150 }
  - { id: season,       title: '时令建议',   min_words: 60,  max_words: 100 }
  - { id: quote,        title: '金句与寄语', min_words: 60,  max_words: 100 }
  - { id: term_bless,   title: '节气寄语',   min_words: 80,  max_words: 120 }

tuning:
  temperature: 0.7
  max_tokens: 1500
  top_p: 0.9
  few_shot_count: 1
```

### 排盘要素渲染

每个派别有独立的"排盘要素"(传统命理算法):

| 派别 | 排盘要素 |
|---|---|
| 八字 | 年柱、月柱、日柱、时柱 + 大运 + 流年 |
| 紫微 | 命宫、身宫、十二宫位 + 主星分布 |
| 奇门 | 三奇、六仪、八门、九星 + 值符值使 |
| 六爻 | 本卦、变卦、互卦 + 世爻应爻 |
| 梅花 | 体卦、用卦、互卦、变卦 |
| 塔罗 | 牌阵(过去/现在/未来)、正逆位 |
| 西占 | 太阳、月亮、上升、水星相位 |
| 吠陀 | 月亮星座、Nakshatra、Dasha |

排盘要素在 prompt 里以 **Jinja2 模板**渲染,变量从用户输入 + 服务端排盘算法计算填充。

### 合规约束

`specs/compliance/` 里有三层合规配置:

- **`mingli_banned_words.json`**:禁止出现的命理词汇(如"命中注定"、"100%")
- **`tone_rules.json`**:语气规则(必须用概率语言、必须给具体场景建议)
- **`disclaimer_templates.json`**:免责声明模板(每派一个)

LLM 输出后会过一遍禁词扫描,触发替换为合规词。

---

## 8 派实现差异

8 派共用同一个 Flask 路由 + LLM 路由器,**只有 prompt 和排盘要素不同**。

```python
# app.py 路由
@app.route('/api/v2/liupai/<liupai>/reading', methods=['POST'])
def reading(liupai):
    spec = load_prompt_spec(liupai)           # 加载 specs/prompts/<liupai>.yaml
    pan_data = render_pan(liupai, form_data) # 调用对应排盘算法
    messages = assemble_prompt(spec, pan_data, form_data)
    result = llm_router.chat(messages)
    return jsonify(result)
```

**派别判断**:URL 路径 `/liupai/<liupai>/` 决定派别,无需额外参数。

**排盘算法差异**:

- **八字 / 紫微 / 西占 / 吠陀**:需要万年历(查表,客户端输入年月日时 → 天干地支 / 星座 / Nakshatra)
- **奇门 / 六爻 / 梅花**:可纯随机起卦(根据当前时间或问题生成)
- **塔罗**:78 张牌随机抽取

v1.0 阶段排盘算法做最简版(主要靠 LLM 自身的命理知识),v2.0 接入专业排盘库(如 `lunardate` / `swisseph`)。

---

## 部署架构

### 当前线上

```
用户浏览器
   │
   │  HTTP (80 端口)
   ▼
阿里云 ECS (116.62.69.83)
   Ubuntu 22.04 / 2C2G
   ├─ 2GB swap(必需,防 OOM)
   │
   Flask (nohup, PID 70446)
   ├─ 绑 0.0.0.0:80
   ├─ 1 worker + threaded
   ├─ 内存占用 ~80MB
   │
   └─ 调 DeepSeek API (api.deepseek.com, HTTPS 443)
```

### 完整架构(可选)

```
用户浏览器
   │
   │  HTTPS (443)
   ▼
Nginx (反代 + SSL 终止 + 静态资源)
   │
   │  HTTP (127.0.0.1:5000)
   ▼
Gunicorn (4 workers)
   │
   ▼
Flask App (Django-equivalent)
```

### 部署脚本

- `DEPLOY.md`:完整部署文档(8 步)
- `deploy_ecs.sh`:一键部署脚本

---

## 性能与成本

### 实测性能(2C2G ECS)

| 指标 | 值 |
|---|---|
| 启动时间 | ~3 秒 |
| 内存占用(Flask + OS) | ~600 MB + 2GB swap |
| 单次解读端到端 | 5-15 秒(主要在 LLM 推理) |
| 并发能力 | 5-10 用户/秒(threaded 模式) |
| 静态资源响应 | < 50 ms |

### LLM 成本(DeepSeek v4-flash)

| 项目 | 用量 | 成本 |
|---|---|---|
| 单次输入 | 500 tokens | ¥0.0001 |
| reasoning 消耗 | 500-1500 tokens | ¥0.0002 |
| 主输出 | 500-1000 tokens | ¥0.0002 |
| **单次解读** | ~1500-3000 tokens | **¥0.0005-0.001** |

**每月 1000 次解读成本**:¥0.5-1(几乎免费)。

### 性能瓶颈

- **网络延迟**:到 DeepSeek 的 RTT ~50ms(国内到北京机房)
- **LLM 推理**:reasoning 模型比非 reasoning 慢 2-3 倍
- **Flask sync**:高并发下排队(v1.0 阶段不优化)

---

## 安全与合规

### 数据隐私

- **零持久化**:本项目不存储任何用户输入或解读结果
- **无追踪**:无 Google Analytics、无 Sentry
- **无第三方 Cookie**:无广告 SDK

### 内容合规

- **免责声明**:每个解读结果末尾强制注入
- **禁词过滤**:LLM 输出后扫描 `mingli_banned_words.json`,触发则替换
- **语气规则**:prompt 里强制要求用概率语言,避免恐吓性结论
- **不预测死亡/疾病/具体事件**:明示文化参考,不替代专业建议

### API Key 安全

- 写到 `/etc/systemd/system/taixuan.service.d/override.conf`(权限 600)
- 或写到 `/etc/taixuan.env`(权限 600)
- **不提交到 git**(.gitignore 已排除)

### 网络安全

- 阿里云安全组只放行 80 端口
- 没暴露数据库端口、Redis 端口
- Flask 绑 127.0.0.1 或 0.0.0.0(根据需要)

---

## 路线图

### v1.0(已完成,2026-07-12)

- [x] 8 派基础实现
- [x] DeepSeek 主路 + Ollama 兜底 + Mock
- [x] 阿里云 ECS 部署
- [x] GitHub 开源(MIT)

### v1.1(短期)

- [ ] 域名绑定 + SSL 证书(certbot)
- [ ] supervisor 守护(Workbench 关了也能跑)
- [ ] 访问统计(umami 或 Plausible,自托管)
- [ ] 流式输出(SSE,降低 perceived latency)

### v2.0(中期)

- [ ] 专业排盘库接入(`lunardate` / `swisseph`)
- [ ] 用户系统(邮箱注册)
- [ ] 历史记录(SQLite 后端)
- [ ] 解读收藏、分享

### v3.0(远期)

- [ ] 支付(单次解读付费 / 包月)
- [ ] 移动端 PWA(离线访问)
- [ ] 英文版(i18n)
- [ ] 多 LLM 后端对比测试(A/B test)

---

## 贡献与许可

### 贡献

PR 和 issue 都欢迎。

代码风格:Python 3.10+,PEP 8,提交前跑 `python app.py` 确保能起。

**未来需要贡献的方向**:
- 8 派排盘算法精度(目前 v1.0 靠 LLM 兜底)
- 新的 LLM 后端适配(Gemini / Claude / 本地 llama)
- 多语言(英文 / 繁体)
- 移动端 UI 优化

### 许可

MIT License — 详见 [LICENSE](LICENSE) 文件。

### 联系

提 issue:https://github.com/aidless/taixuan-web/issues

---

_作者:刘泽文 · 2026-07-12 首发 · MIT 协议_