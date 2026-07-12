# Changelog

## v1.0.0  2026-07-12

第一个开源版本。从微信小程序改成独立网站。

新增:

- app.py Flask 主入口,8 派路由加 healthz
- llm_backends.py LLM 路由器,三级兜底(DeepSeek 主、Ollama 兜底、Mock 开发用)
- 8 派 HTML 模板:bazi、ziwei、qimen、liuyao、meihua、tarot、western、vedic
- base.html、index.html、privacy.html、terms.html
- 8 派 prompt YAML,从 wx-miniprogram 移植到 specs/prompts/
- 8 派结果 schema 在 specs/schools/
- specs/compliance/ 里有 mingli_banned_words、tone_rules、disclaimer
- static/css/style.css 样式
- tests/test_llm_backends.py 测试
- deploy_ecs.sh 一键部署脚本
- 文档:README、DEPLOY、CHANGELOG、LICENSE

修复:

- DeepSeekV3Backend 类名问题,改成 DeepSeekBackend
- max_tokens 默认从 1500 调到 2500,因为 v4-flash 是 reasoning 模型需要更多 buffer
- Ollama 兜底改静默失败,不抛错

变了:

- 从 wx-miniprogram 拆出来,改用 Flask
- 后端从 wx.request 改成 fetch
- 登录从 wx.login 改成浏览器 localStorage(还没接)

线上表现:

- 1 worker 加 threaded,5 到 10 并发
- DeepSeek 一次解读 2 到 5 秒
- 单次成本大概几厘钱
- 2C2G 加 2G swap 占 600MB

已知问题:

- 单 worker,高并发会排队
- 没用户系统
- 没支付
- 没统计
- 没 SSL,要先域名解析再做 certbot

部署时间线:

- 09:00 决定改网站
- 10:00 写代码
- 11:00 上传到 ECS
- 12:00 改类名 bug
- 13:00 换有效的 key
- 14:00 改 max_tokens
- 15:00 加 swap
- 16:00 跑通
- 22:30 开源

---

## 之后想做但还没做的

- GitHub Actions 自动跑 pytest
- Dockerfile 一键部署
- 域名绑定加 SSL 证书
- supervisor 让 Workbench 关了也能跑
- 访问统计
- 支付
- 历史记录(后端存 SQLite)
- 登录(邮箱、短信)
- PWA
- i18n 英文版
