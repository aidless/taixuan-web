# 变更日志 · Changelog

本项目所有重要变更记录在此。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)。

---

## [v1.0.0] - 2026-07-12

### 🎉 首个开源版本

泰玄小站从**微信小程序重定位为独立网站**的首个完整开源版本。

### ✨ 新增

- **Flask 应用** (`app.py`, 9257B) — 主入口,8 派路由 + 健康检查
- **LLM 路由器** (`llm_backends.py`, 10695B) — 三级兜底
  - 主路 DeepSeek v4-flash(在线)
  - 兜底 Ollama qwen3:4b(本地)
  - Mock 后端(无 key 时开发用)
- **8 派 HTML 模板** — 8 个派别独立表单页
  - `templates/base.html` — 基础布局(导航/页脚)
  - `templates/index.html` — 8 派卡片首页
  - `templates/liupai/{bazi,ziwei,qimen,liuyao,meihua,tarot,western,vedic}.html`
  - `templates/privacy.html` + `templates/terms.html` — 法务
- **8 派 Prompt YAML** (`specs/prompts/*.yaml`) — 从微信小程序移植
  - `bazi.yaml` / `ziwei.yaml` / `qimen.yaml` / `liuyao.yaml`
  - `meihua.yaml` / `tarot.yaml` / `western-astro.yaml` / `vedic.yaml`
- **8 派结果 Schema** (`specs/schools/*.result.schema.json`) — LLM 输出格式约束
- **合规配置** (`specs/compliance/*`) — mingli_banned_words + tone_rules + disclaimer
- **响应式 CSS** (`static/css/style.css`, 6462B) — 深色主题 + 金色点缀
- **LLM 测试套件** (`tests/test_llm_backends.py`)
- **部署脚本** (`deploy_ecs.sh`, 5173B)
- **完整文档**:
  - `README.md` — 项目介绍
  - `DEPLOY.md` — 部署/恢复文档
  - `CHANGELOG.md` — 本文件
  - `LICENSE` — MIT
  - `.gitignore`

### 🐛 修复

- **类名 bug**:`DeepSeekV3Backend` → `DeepSeekBackend`(ECS 部署时类名不一致导致 `NameError`)
- **max_tokens 默认值**:1500 → 2500(reasoning 模型需要更大 buffer)
- **Ollama 兜底**:之前默认连接 11434,ECS 没装时 fallback 报错 → 改用静默 fallback
- **Prompt YAML 路径**:支持 `wx-miniprogram/specs/prompts/` 和 `taixuan-web/specs/prompts/` 双路径兼容

### 🔧 变更

- 项目从 `wx-miniprogram/`(微信小程序,8 派 YAML 在 `specs/prompts/`)剥离出来
- 之前 wx-miniprogram 因 v1.0 重定位放弃,改用独立 Flask Web 应用
- 后端从 `wx.request()` 改成标准 `fetch()` + Flask `request.get_json()`
- 登录 UI 从 `wx.login()` 重写为匿名 / 后续可接邮箱 / 短信
- 存储从 `wx.setStorageSync` 改成浏览器 `localStorage`(后续可接)

### 📊 性能

- 1 worker + threaded:实测支持 5-10 并发
- DeepSeek v4-flash 平均响应:2-5s(reasoning 模型)
- 单次解读成本:~¥0.001-0.005(DeepSeek 计费)
- ECS 资源占用:2C2G + 2GB swap(必需)

### 🎯 已知限制

- 单 worker,高并发下会排队
- 不支持用户登录(无后端存储)
- 无支付功能
- 无访问统计
- 无 SSL(部署 SSL 需域名解析后用 certbot)

### 🚀 部署里程碑(本次升级时间线)

| 时间 | 事件 |
|---|---|
| 2026-07-12 09:00 | 决定从小程序转独立网站(域名 wanxiangapp.xyz 已 ICP 备案) |
| 2026-07-12 10:00 | 写 Flask app.py + 8 派 HTML 模板 + CSS |
| 2026-07-12 11:00 | 传到阿里云 ECS(2C2G,Ubuntu 22.04) |
| 2026-07-12 12:00 | 修复 DeepSeekV3Backend 类名 bug |
| 2026-07-12 13:00 | 修复 DeepSeek key 401,找到有效 key |
| 2026-07-12 14:00 | 修复 max_tokens 太小导致 content 为空 |
| 2026-07-12 15:00 | 修复 ECS 2G 内存 OOM(加 2G swap) |
| 2026-07-12 16:00 | 网站成功上线,真实 DeepSeek LLM 工作 |
| 2026-07-12 17:00 | 决定开源到 GitHub,写 README + DEPLOY + CHANGELOG |

---

## [未来规划] - 2026 Q3-Q4

### 待办

- [ ] **GitHub Actions CI**:自动跑 `pytest` 验证
- [ ] **Dockerfile**:一键 Docker 部署
- [ ] **域名绑定 + SSL**:wanxiangapp.xyz 解析 + certbot 证书
- [ ] **supervisor 守护**:Workbench 关了 Flask 也跑
- [ ] **访问统计**:GA / umami / Plausible
- [ ] **支付集成**:支付宝 / 微信扫码 / Stripe
- [ ] **历史记录**:用户解读历史(后端 SQLite)
- [ ] **登录**:邮箱 / 短信 / 微信扫码
- [ ] **移动端 PWA**:加 manifest,离线访问
- [ ] **i18n**:英文版本

---

_格式参考:[Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/) · 语义化版本:[Semantic Versioning](https://semver.org/lang/zh-CN/)_