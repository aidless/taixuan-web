# RFC-005 · taixuan-web i18n 多语言

**状态**:📋 草案
**作者**:刘泽文
**日期**:2026-07-13
**目标版本**:v3.0(预计 8-12 月,有海外流量时)

## 一、目标

支持中英双语,海外用户能流畅使用。

**不指望**:
- i18n 完整(所有页面 + 所有 LLM 输出 + 完整国际化)
- 自动翻译(yaml 翻译文件,人工维护)
- 多语种(只中英双语,够覆盖 90% 海外用户)

## 二、技术方案

### 工具选择

| 候选 | 优 | 劣 |
|---|---|---|
| **Flask-Babel** | Flask 生态 | 配置复杂,过时 |
| **i18next + JS** | 行业标准 | 前后端两套 |
| **自写 dict** | 简单可控 | 重复造轮子 |
| **gettext (.po)** | 古老但稳定 | 编辑器支持差 |

**推荐:自写 dict**(项目体量小,模板 < 20 个,自写够用)。

### 文件结构

```
fortune-web-v2/
├── i18n/
│   ├── __init__.py        # t() 函数 + current_locale
│   ├── zh_CN.py          # 中文 dict
│   └── en_US.py          # 英文 dict
├── templates/
│   ├── base.html          # {{ t('nav.home') }}
│   └── liupai/bazi.html  # {{ t('bazi.title') }}
├── static/js/
│   └── i18n.js           # 客户端 t() 函数(用于流式状态显示)
└── app.py                # @app.before_request 设置 locale
```

### 核心实现

```python
# i18n/__init__.py
from flask import request, g

def get_locale():
    # 优先 URL prefix /zh/ /en/
    if request.path.startswith('/en/'):
        return 'en'
    # 其次 Cookie 'locale'
    if request.cookies.get('locale') in ('zh', 'en'):
        return request.cookies.get('locale')
    # 最后 Accept-Language
    best = request.accept_languages.best_match(['zh', 'en'])
    return best or 'zh'

def t(key):
    locale = get_locale()
    from . import zh_CN, en_US
    translations = {'zh': zh_CN, 'en': en_US}
    return translations[locale].dict.get(key, key)
```

### zh_CN.py

```python
dict = {
    'nav.home': '首页',
    'nav.history': '我的历史',
    'bazi.title': '八字排盘',
    'bazi.subtitle': '天干地支 · 五行生克',
    'bazi.form.question': '你想问什么?',
    'bazi.form.birth_date': '出生日期',
    'bazi.form.birth_time': '出生时间',
    'bazi.submit': '开始推演',
    'bazi.stream.thinking': '思考中...',
    'bazi.stream.tokens_per_sec': '{tps} tokens/s',
    'bazi.stream.estimated': '预计 {sec}s',
    'common.copy': '📋 复制',
    'common.download': '💾 下载',
    'common.cancel': '停止',
    'common.error': '出错了',
    # ... 8 派 × ~30 字段 = ~240 字段
}
```

### en_US.py

```python
dict = {
    'nav.home': 'Home',
    'nav.history': 'My History',
    'bazi.title': 'Bazi Fortune',
    'bazi.subtitle': 'Heavenly Stems & Earthly Branches',
    # ... 同结构
}
```

## 三、8 派 标题/描述翻译矩阵

| 派别 | 中文 | 英文 |
|---|---|---|
| bazi | 八字排盘 | Bazi Reading |
| ziwei | 紫微斗数 | Zi Wei Dou Shu |
| qimen | 奇门遁甲 | Qi Men Dun Jia |
| liuyao | 六爻 | Liu Yao |
| meihua | 梅花易数 | Mei Hua Yi Shu |
| tarot | 塔罗 | Tarot |
| western | 西方占星 | Western Astrology |
| vedic | 吠陀占星 | Vedic Astrology |

## 四、工作量

| 任务 | 工作量 |
|---|---:|
| 写 i18n/__init__.py + dict 加载 | 2h |
| 8 派页面中文化提取 | 2h |
| 8 派页面对应英文 dict | 3h |
| 公共页(base / privacy / terms)| 1h |
| 流式状态文案(JS)| 1h |
| 语言切换 UI(右上角下拉)| 30 min |
| 测试 + 文档 | 1h |
| **总计** | **~10.5h** |

## 五、不做(明确划线)

| 不做 | 原因 |
|---|---|
| LLM 输出翻译(8 派 prompt 中文 → 英文)| 复杂度高 |
| 自动检测语种 | Accept-Language 够用 |
| 完整双语(含 prompt YAML 翻译)| 后续按需求 |
| 8 派完整文化差异 | 8 派本质是中式,英文是给 tourist 用 |
| 右到左语言 | 需求 0 |

## 六、触发条件

| 触发 | 启动 |
|---|---|
| umami 显示海外 IP 占 > 5% | 启动实施 |
| 微信里有人分享 taixuan 给海外华人 | 立即 |
| 连续 3 个月 PV 中海外 > 1% | 启动 |

**未触发** → 不实施,聚焦中文市场。

## 七、成功标准

- URL `/en/liupai/bazi` 返回英文页面
- `/liupai/bazi` 默认根据浏览器语言切换
- 文案通过 gettext-like 函数管理(`t('key')`)
- 翻译覆盖率 = 100%(每条中文都有英文对应)
- Lighthouse i18n 评分 > 90

---

_本 RFC 草案 · 触发条件驱动 · 2026-07-13 01:35 整理_