# RFC-005 i18n 实施清单

> 给未来"白天精力足时"的刘泽文。8 派翻译矩阵 + 实施步骤 + 测试点。

## 步骤 1 · 创建 i18n 模块

**文件结构**:
```
fortune-web-v2/
├── i18n/
│   ├── __init__.py
│   ├── zh_CN.py
│   └── en_US.py
```

### `i18n/__init__.py`

```python
# -*- coding: utf-8 -*-
"""taixuan-web i18n 模块
从 request 自动检测语言:URL prefix > Cookie > Accept-Language > 默认 zh
"""
from flask import request, g

SUPPORTED = ['zh', 'en']
DEFAULT = 'zh'

def get_locale():
    # 1. URL prefix: /en/...
    if request.path.startswith('/en/'):
        return 'en'
    # 2. Cookie
    cookie = request.cookies.get('locale')
    if cookie in SUPPORTED:
        return cookie
    # 3. Accept-Language header
    best = request.accept_languages.best_match(SUPPORTED)
    return best if best in SUPPORTED else DEFAULT

def t(key, **kwargs):
    """翻译函数:t('nav.home') → '首页'"""
    locale = get_locale()
    if locale == 'en':
        from . import en_US
        text = en_US.DICT.get(key, key)
    else:
        from . import zh_CN
        text = zh_CN.DICT.get(key, key)
    if kwargs:
        try:
            return text.format(**kwargs)
        except (KeyError, IndexError):
            return text
    return text

def init_app(app):
    """注册到 Flask app"""
    @app.context_processor
    def inject_t():
        return dict(t=t, locale=get_locale())
```

### `i18n/zh_CN.py`(中文)

```python
DICT = {
    # 公共
    'common.home': '首页',
    'common.history': '我的历史',
    'common.about': '关于',
    'common.privacy': '隐私',
    'common.terms': '条款',
    'common.copy': '📋 复制',
    'common.download': '💾 下载',
    'common.cancel': '停止',
    'common.retry': '🔄 重试',
    'common.error': '出错了',

    # 导航
    'nav.title': '泰玄小站',
    'nav.subtitle': '8 派传统命理 · AI 解读',

    # 8 派
    'liupai.bazi.name': '八字排盘',
    'liupai.bazi.subtitle': '天干地支 · 五行生克',
    'liupai.bazi.icon': '☰',
    'liupai.ziwei.name': '紫微斗数',
    'liupai.ziwei.subtitle': '十四主星 · 十二宫位',
    'liupai.ziwei.icon': '✦',
    'liupai.qimen.name': '奇门遁甲',
    'liupai.qimen.subtitle': '九宫八卦 · 时家奇门',
    'liupai.qimen.icon': '☯',
    'liupai.liuyao.name': '六爻',
    'liupai.liuyao.subtitle': '三枚铜钱 · 古法起卦',
    'liupai.liuyao.icon': '⚊',
    'liupai.meihua.name': '梅花易数',
    'liupai.meihua.subtitle': '数字起卦 · 体用生克',
    'liupai.meihua.icon': '✿',
    'liupai.tarot.name': '塔罗',
    'liupai.tarot.subtitle': '78 张神秘符号 · 心理投射',
    'liupai.tarot.icon': '☽',
    'liupai.western.name': '西方占星',
    'liupai.western.subtitle': '星盘相位 · 行星运行',
    'liupai.western.icon': '★',
    'liupai.vedic.name': '吠陀占星',
    'liupai.vedic.subtitle': '印度古法 · 二十七宿',
    'liupai.vedic.icon': '☼',

    # 表单
    'form.question.label': '你想问什么?',
    'form.question.placeholder': '例如:今年事业如何?',
    'form.birth_date.label': '出生日期',
    'form.birth_time.label': '出生时间',
    'form.submit': '开始推演',
    'form.submitting': '推演中...',

    # 流式
    'stream.thinking': '思考中...',
    'stream.tokens_per_sec': '{tps} tokens/s',
    'stream.estimated': '预计 {sec}s',
    'stream.chunks': '{n} chunks',
    'stream.chars': '{n} 字',
    'stream.network_error': '网络中断',
    'stream.server_error': '服务器错误',

    # 结果
    'result.title': '解读结果',
    'result.meta_template': '派别:{liupai} · 耗时:{sec}s · {chunks} chunks · {chars} 字',
    'result.disclaimer': '本解读基于传统文化知识,仅供参考与娱乐,不构成任何专业建议。',

    # 隐私
    'privacy.title': '隐私政策',
    'privacy.intro': '我们尊重您的隐私。本应用不收集任何个人信息,所有解读在匿名模式下进行。',

    # 条款
    'terms.title': '服务条款',
    'terms.intro': '本服务按"现状"提供,不保证解读准确性。使用本服务即表示您同意自行承担解读结果的责任。',
}
```

### `i18n/en_US.py`(英文)

```python
DICT = {
    # Common
    'common.home': 'Home',
    'common.history': 'My History',
    'common.about': 'About',
    'common.privacy': 'Privacy',
    'common.terms': 'Terms',
    'common.copy': '📋 Copy',
    'common.download': '💾 Download',
    'common.cancel': 'Cancel',
    'common.retry': '🔄 Retry',
    'common.error': 'Error',

    # Nav
    'nav.title': 'Taixuan',
    'nav.subtitle': '8 Schools of Fortune Telling · AI Reading',

    # 8 schools
    'liupai.bazi.name': 'Bazi Reading',
    'liupai.bazi.subtitle': 'Heavenly Stems · Five Elements',
    'liupai.bazi.icon': '☰',
    'liupai.ziwei.name': 'Zi Wei Dou Shu',
    'liupai.ziwei.subtitle': '14 Main Stars · 12 Palaces',
    'liupai.ziwei.icon': '✦',
    'liupai.qimen.name': 'Qi Men Dun Jia',
    'liupai.qimen.subtitle': '9 Palaces · Time-based',
    'liupai.qimen.icon': '☯',
    'liupai.liuyao.name': 'Liu Yao',
    'liupai.liuyao.subtitle': '3 Coins · Ancient Divination',
    'liupai.liuyao.icon': '⚊',
    'liupai.meihua.name': 'Mei Hua Yi Shu',
    'liupai.meihua.subtitle': 'Number-based · Trigram Relations',
    'liupai.meihua.icon': '✿',
    'liupai.tarot.name': 'Tarot',
    'liupai.tarot.subtitle': '78 Mystical Symbols',
    'liupai.tarot.icon': '☽',
    'liupai.western.name': 'Western Astrology',
    'liupai.western.subtitle': 'Natal Chart · Planetary',
    'liupai.western.icon': '★',
    'liupai.vedic.name': 'Vedic Astrology',
    'liupai.vedic.subtitle': 'Indian Ancient · 27 Nakshatras',
    'liupai.vedic.icon': '☼',

    # Form
    'form.question.label': 'What would you like to ask?',
    'form.question.placeholder': 'e.g. How is my career this year?',
    'form.birth_date.label': 'Birth Date',
    'form.birth_time.label': 'Birth Time',
    'form.submit': 'Start Reading',
    'form.submitting': 'Reading...',

    # Stream
    'stream.thinking': 'Thinking...',
    'stream.tokens_per_sec': '{tps} tokens/s',
    'stream.estimated': 'ETA {sec}s',
    'stream.chunks': '{n} chunks',
    'stream.chars': '{n} chars',
    'stream.network_error': 'Network error',
    'stream.server_error': 'Server error',

    # Result
    'result.title': 'Reading Result',
    'result.meta_template': '{liupai} · {sec}s · {chunks} chunks · {chars} chars',
    'result.disclaimer': 'This reading is for cultural reference and entertainment only, not professional advice.',

    # Privacy
    'privacy.title': 'Privacy Policy',
    'privacy.intro': 'We respect your privacy. This app collects no personal information; all readings are anonymous.',

    # Terms
    'terms.title': 'Terms of Service',
    'terms.intro': 'This service is provided "as is" without warranty of accuracy. By using it, you agree to take responsibility for any outcomes.',
}
```

## 步骤 2 · app.py 集成

**改动**:

```python
# 顶部
import sys
sys.path.insert(0, str(BASE_DIR))
from i18n import init_app, t  # noqa: E402

# 在 router = LLMRouter() 后
init_app(app)
```

**改 routes**:

```python
@app.route("/")
def index():
    return render_template("index.html", liupai_list=LIUPAI_LIST)

# 加英文版
@app.route("/en/")
def index_en():
    return render_template("index.html", liupai_list=LIUPAI_LIST)

@app.route("/liupai/<name>")
def liupai_form(name):
    # 现有逻辑
    ...

@app.route("/en/liupai/<name>")
def liupai_form_en(name):
    return liupai_form(name)  # 复用同一个 handler,locale 自动从 URL 检测
```

**改 base.html(已存在)**:

```html
<!DOCTYPE html>
<html lang="{{ locale }}">
<head>
  <title>{{ t('nav.title') }} · {{ t('nav.subtitle') }}</title>
  ...
</head>
<body>
  <header>
    <h1>{{ t('nav.title') }}</h1>
    <p>{{ t('nav.subtitle') }}</p>
    <!-- 语言切换 -->
    <div class="lang-switch">
      <a href="{{ request.path.replace('/en/', '/') if request.path.startswith('/en/') else '/en' + request.path }}">中 / EN</a>
    </div>
  </header>
  {% block content %}{% endblock %}
</body>
</html>
```

## 步骤 3 · 8 派模板改造

**示例 bazi.html** (改 text 部分):

```html
<h1>{{ t('liupai.bazi.icon') }} {{ t('liupai.bazi.name') }}</h1>
<p class="subtitle">{{ t('liupai.bazi.subtitle') }}</p>

<form>
  <label>{{ t('form.question.label') }}</label>
  <input type="text" name="question" placeholder="{{ t('form.question.placeholder') }}">
  <button type="submit">{{ t('form.submit') }}</button>
</form>
```

**8 派都要这样改** — 用 t() 函数包裹所有用户可见文本。

## 步骤 4 · 客户端流式 JS 国际化

**`static/js/i18n.js`**(新建):

```javascript
// 客户端翻译(从 server-rendered t() 标签读 locale)
const LOCALE = document.documentElement.lang || 'zh';

const DICT = {
  zh: {
    thinking: '思考中...',
    network_error: '网络中断,请检查连接',
    retry: '🔄 重试',
    chars_per_sec: '{tps} 字/s',
  },
  en: {
    thinking: 'Thinking...',
    network_error: 'Network error, please check connection',
    retry: '🔄 Retry',
    chars_per_sec: '{tps} chars/s',
  },
};

function clientT(key, params = {}) {
  let text = DICT[LOCALE]?.[key] || key;
  for (const [k, v] of Object.entries(params)) {
    text = text.replace(`{${k}}`, v);
  }
  return text;
}

window.clientT = clientT;
```

## 步骤 5 · 单元测试

**`tests/test_i18n.py`**(新建):

```python
import sys
sys.path.insert(0, 'C:\\Users\\Administrator\\cow\\fortune-web-v2')

from i18n import t

def test_t_zh():
    """t() 默认 zh 应该返回中文"""
    # 注意:t() 用 Flask request context,需要 mock
    # 简化测试:DICT 加载
    from i18n import zh_CN
    assert zh_CN.DICT['common.home'] == '首页'

def test_t_en_dict_complete():
    """en_US 必须覆盖所有 zh_CN keys"""
    from i18n import zh_CN, en_US
    zh_keys = set(zh_CN.DICT.keys())
    en_keys = set(en_US.DICT.keys())
    missing_in_en = zh_keys - en_keys
    assert not missing_in_en, f'EN missing keys: {missing_in_en}'

def test_t_format():
    """t() 应该支持 kwargs 替换"""
    from i18n import zh_CN
    text = zh_CN.DICT['stream.tokens_per_sec'].format(tps='12.5')
    assert text == '12.5 tokens/s'
```

## 实施步骤

| # | 任务 | 文件 | 工作量 |
|---|---|---|---:|
| 1 | 写 i18n/__init__.py + zh_CN.py + en_US.py | i18n/ | 2h |
| 2 | app.py 集成 init_app + 加 /en/ 路由 | app.py | 30 min |
| 3 | 改 base.html(国际化模板)| templates/base.html | 30 min |
| 4 | 改 8 派 HTML(用 t() 替换文本) | templates/liupai/*.html | 2h |
| 5 | 改 1 派 HTML(隐私 + 条款 + 首页) | templates/ | 30 min |
| 6 | 客户端 i18n.js | static/js/ | 1h |
| 7 | 单元测试 | tests/test_i18n.py | 1h |
| 8 | 部署 + 实测 | ECS + Chrome | 1h |
| **总** | | | **~8.5h** |

## 成功标准 Checklist

- [ ] `/` 显示中文(默认)
- [ ] `/en/` 显示英文
- [ ] 浏览器语言 Accept-Language: en → 显示英文
- [ ] 中文 Cookie locale=zh → 切回中文
- [ ] 语言切换 UI 工作
- [ ] 流式 JS 文案随 locale 变
- [ ] en_US 翻译覆盖 100% zh_CN keys
- [ ] 单元测试通过(7 个)
- [ ] Lighthouse i18n 评分 ≥ 90

## 不做(明确划线)

- [ ] LLM 输出翻译(8 派 prompt 中文 → 英文)
- [ ] 自动检测语种(用 Accept-Language)
- [ ] 完整 8 派文化差异适配
- [ ] 右到左语言

---

_实施清单 · 触发条件:海外 IP > 5% 时启动 · 2026-07-13 02:00 整理_