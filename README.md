# 泰玄小站 · Taixuan Web

> 8 派传统文化工具箱 · Flask + DeepSeek LLM  
> Eight Schools of Traditional Chinese Culture · Flask + DeepSeek LLM

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org)
[![Flask](https://img.shields.io/badge/Flask-3.0-green.svg)](https://flask.palletsprojects.com)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

## 📖 简介

泰玄小站是一个基于传统文化的**文化参考与娱乐工具**,涵盖八字、紫微、奇门遁甲、六爻、梅花易数、塔罗、西方占星、吠陀占星八个流派。

**核心特性**:
- 🎴 **8 派合参** — 八字 / 紫微 / 奇门 / 六爻 / 梅花 / 塔罗 / 西占 / 吠陀
- 🤖 **AI 解读** — DeepSeek LLM 实时生成文化背景分析
- 🎨 **简洁 UI** — 深色主题 + 金色点缀,响应式适配
- ⚡ **轻量部署** — Flask + Gunicorn,2C2G ECS 即可跑
- 🔒 **本地优先** — 无追踪,无第三方 Cookie,日志本地化

## 🎯 项目定位

> ⚠️ **本服务仅供文化参考与娱乐,不构成任何专业建议**(医疗、法律、财务、心理咨询等)。

所有解读结果由 AI 模型基于传统算法生成,目的是**文化传承与娱乐**,请勿将解读结果作为人生决策的唯一依据。

## 🏗️ 技术栈

| 层级 | 技术 |
|---|---|
| 前端 | HTML5 + Tailwind-style CSS + 原生 JS |
| 后端 | Flask 3.0 + Gunicorn |
| LLM | DeepSeek v4-flash(主路) + Ollama qwen3-4b(兜底) + Mock(开发) |
| 部署 | Ubuntu 22.04 + Nginx(可选) + systemd |
| 配置 | YAML-based prompts(8 派各一个) |

## 📂 目录结构

```
taixuan-web/
├── app.py                    # Flask 主入口
├── llm_backends.py           # LLM 路由器(主路/兜底/Mock)
├── requirements.txt          # Python 依赖
├── templates/                # Jinja2 模板
│   ├── base.html             # 基础布局(导航/页脚)
│   ├── index.html            # 首页(8 派卡片)
│   ├── privacy.html          # 隐私政策
│   ├── terms.html            # 服务条款
│   └── liupai/               # 8 派子页
│       ├── bazi.html         # 八字
│       ├── ziwei.html        # 紫微
│       ├── qimen.html        # 奇门
│       ├── liuyao.html       # 六爻
│       ├── meihua.html       # 梅花
│       ├── tarot.html        # 塔罗
│       ├── western.html      # 西占
│       └── vedic.html        # 吠陀
├── static/                   # 静态资源
│   └── css/style.css         # 全局样式
├── specs/prompts/            # 8 派 prompt YAML(来自微信小程序)
│   ├── bazi.yaml
│   ├── ziwei.yaml
│   ├── qimen.yaml
│   ├── liuyao.yaml
│   ├── meihua.yaml
│   ├── tarot.yaml
│   ├── western.yaml
│   └── vedic.yaml
└── README.md                 # 本文件
```

## 🚀 快速开始

### 环境要求
- Python 3.10+
- pip
- DeepSeek API key(或本地 Ollama + qwen3:4b)

### 安装

```bash
# 1. 克隆
git clone https://github.com/你的用户名/taixuan-web.git
cd taixuan-web

# 2. 创建虚拟环境
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. 装依赖
pip install -r requirements.txt

# 4. 配置 API key
export OPENAI_API_KEY="sk-your-deepseek-key"
export OPENAI_API_BASE="https://api.deepseek.com/v1"
export DEEPSEEK_MODEL="deepseek-v4-flash"
```

### 跑

```bash
# 开发模式
python app.py
# → http://127.0.0.1:5000

# 生产模式(Gunicorn)
gunicorn --workers 2 --bind 0.0.0.0:5000 app:app
```

## 🔧 配置说明

### 环境变量

| 变量 | 必填 | 说明 |
|---|---|---|
| `OPENAI_API_KEY` 或 `DEEPSEEK_API_KEY` | ✅(主路) | DeepSeek API key |
| `OPENAI_API_BASE` | ❌ | 默认 `https://api.deepseek.com/v1` |
| `DEEPSEEK_MODEL` | ❌ | 默认 `deepseek-v4-flash` |
| `OLLAMA_HOST` | ❌ | 默认 `http://127.0.0.1:11434`(兜底) |
| `OLLAMA_MODEL` | ❌ | 默认 `qwen3:4b` |
| `LLM_MODE` | ❌ | `primary` / `fallback` / `mock` |
| `PORT` | ❌ | 默认 5000 |

### 兜底机制

`LLMRouter` 三级兜底:
1. **主路** DeepSeek v4-flash(在线,~2-5s)
2. **兜底** Ollama + qwen3:4b(本地,30s+,需要 GPU)
3. **Mock** 返回固定开发文案(无 key 时)

## 🎨 截图

(待补)

## 📜 License

MIT License — 详见 [LICENSE](LICENSE) 文件

## 🙏 致谢

- **DeepSeek** 提供高质量 LLM API
- **8 派传统文化** 数千年的智慧积累
- **微信小程序开源生态** 的提示词工程实践

## 📮 联系方式

- Issue: [GitHub Issues](https://github.com/你的用户名/taixuan-web/issues)
- Email: 17353895263@163.com

---

_Built with ❤️ by [刘泽文](https://github.com/你的用户名) · 2026_