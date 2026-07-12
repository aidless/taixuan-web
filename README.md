# 泰玄小站 · Taixuan Web

> **8 派传统文化工具箱 · Flask + DeepSeek LLM**  
> Eight Schools of Traditional Chinese Culture

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org)
[![Flask](https://img.shields.io/badge/Flask-3.0-green.svg)](https://flask.palletsprojects.com)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Live](https://img.shields.io/badge/live-116.62.69.83-success)](http://116.62.69.83)

---

## 📖 项目简介

泰玄小站是一个**基于传统文化的文化参考与娱乐工具**,涵盖八字、紫微、奇门遁甲、六爻、梅花易数、塔罗、西方占星、吠陀占星八个流派。

**特点**:
- 🎴 **8 派合参** — 一站式覆盖中华与西方主流命理/占卜体系
- 🤖 **AI 解读** — DeepSeek v4-flash 实时生成文化背景分析(2-5 秒响应)
- 🎨 **简洁 UI** — 深色主题 + 金色点缀,响应式适配桌面和移动端
- ⚡ **轻量部署** — Flask 单进程,2C2G ECS 即可跑(实测 ~600MB 内存)
- 🔓 **开源 MIT** — 完全开源,可自由 fork / 修改 / 商用

> ⚠️ **重要声明**:本服务仅供文化参考与娱乐,不构成任何专业建议(医疗、法律、财务、心理咨询等)。

---

## 🚀 在线访问

**Demo**:http://116.62.69.83

---

## ⚡ 5 分钟上手

### 环境要求

- Python 3.10+
- DeepSeek API key(免费 2000 万 tokens,见 https://platform.deepseek.com)

### 安装

```bash
git clone https://github.com/aidless/taixuan-web.git
cd taixuan-web

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 配置

```bash
export OPENAI_API_KEY="sk-your-deepseek-key"
export OPENAI_API_BASE="https://api.deepseek.com/v1"
export DEEPSEEK_MODEL="deepseek-v4-flash"
```

### 跑

```bash
python app.py
# → 浏览器访问 http://127.0.0.1:5000
```

---

## 🎴 8 派一览

| 派别 | 输入 | 特色 |
|---|---|---|
| **八字** | 出生年月日时 | 天干地支 · 五行生克 · 排盘算法 |
| **紫微斗数** | 出生年月日时 | 十四主星 · 十二宫位 |
| **奇门遁甲** | 起卦时间 + 问题 | 九宫八卦 · 时家奇门 |
| **六爻** | 起卦时间 + 问题 | 三枚铜钱 · 古法起卦 |
| **梅花易数** | 数字 + 时间 | 体用生克 · 数字起卦 |
| **塔罗** | 牌阵 + 问题 | 78 张神秘符号 · 心理投射 |
| **西方占星** | 出生时间地点 | 星盘相位 · 行星运行 |
| **吠陀占星** | 出生时间地点 | 印度古法 · 二十七宿 |

---

## 🏗️ 技术栈

- **前端**:HTML5 + CSS3 + 原生 JS(无框架)
- **后端**:Flask 3.0
- **LLM**:DeepSeek v4-flash(主路)+ Ollama qwen3:4b(兜底)+ Mock(开发)
- **配置**:YAML-based prompts(8 派各一个,独立可编辑)
- **部署**:Ubuntu 22.04 + Nginx + systemd(详细见 [DEPLOY.md](DEPLOY.md))

---

## 📂 目录结构

```
taixuan-web/
├── app.py                    # Flask 主入口
├── llm_backends.py           # LLM 路由器
├── requirements.txt          # Python 依赖
├── README.md                 # 本文件
├── DEPLOY.md                 # 部署文档 ⭐
├── CHANGELOG.md              # 版本日志
├── LICENSE                   # MIT 协议
├── templates/                # Jinja2 模板
│   ├── base.html
│   ├── index.html            # 8 派卡片首页
│   ├── privacy.html
│   ├── terms.html
│   └── liupai/               # 8 派子页
├── static/css/style.css      # 全局样式
├── specs/                    # 配置数据
│   ├── prompts/              # 8 派 prompt YAML
│   ├── schools/              # 8 派结果 schema
│   └── compliance/           # 合规配置
└── tests/                    # 测试
```

---

## 📜 文档

- [README.md](README.md) — 本文件,项目介绍
- [DEPLOY.md](DEPLOY.md) — 部署到 ECS / Nginx / SSL / 故障排除
- [CHANGELOG.md](CHANGELOG.md) — 版本变更历史

---

## 🪤 重要提示

1. **本项目为文化娱乐**,不是命理预测工具。所有解读结果基于 AI 生成,不应作为任何决策的唯一依据。
2. **API key 勿提交**:在 `.gitignore` 已排除,但请自行确认。
3. **合规**:在某些国家/地区,命理/占卜类内容可能受监管,请自行评估法律风险。
4. **数据隐私**:本项目默认**不存储**任何用户输入。如需保存历史,自行加数据库。

---

## 🤝 贡献

欢迎 PR / Issue!

开发规范:
- Python 3.10+,PEP 8
- 测试:`pytest tests/`
- 提交前跑 `python app.py` 确保能起

---

## 📮 联系

- Issue: https://github.com/aidless/taixuan-web/issues

---

## 🙏 致谢

- **DeepSeek** — 提供高质量 LLM API
- **8 派传统文化** — 数千年的智慧积累
- **开源生态** — Flask / Python / Ubuntu

---

_Built with ❤️ by [刘泽文](https://github.com/aidless) · 2026_

_MIT License · 详见 [LICENSE](LICENSE)_