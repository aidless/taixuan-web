# RFC-003 PWA 实施清单(可执行)

> 给未来"白天精力足时"的刘泽文。每步都有文件名 + 内容骨架 + 验证点。

## 步骤 1 · 创建图标资源

**文件**:
- `static/icons/icon-192.png`(192×192)
- `static/icons/icon-512.png`(512×512)
- `static/icons/icon-maskable-512.png`(带 padding 用于 maskable)

**生成方式**:
- 用 Python PIL 脚本(下面给完整脚本)
- 或用 Figma / Canva 手工设计(推荐:用 ☰ 字符 + 金色 #d4af37 背景)

**PIL 自动生成脚本**(`tmp/_gen_icons.py`):
```python
from PIL import Image, ImageDraw, ImageFont

def gen_icon(size, maskable=False):
    img = Image.new('RGB', (size, size), (26, 26, 26))
    draw = ImageDraw.Draw(img)
    # 绘制 ☰ 字符
    font_size = int(size * 0.6)
    try:
        font = ImageFont.truetype("arial.ttf", font_size)
    except OSError:
        font = ImageFont.load_default()
    text = "☰"
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    x = (size - text_w) // 2
    y = (size - text_h) // 2
    draw.text((x, y), text, fill=(212, 175, 55), font=font)
    img.save(f"static/icons/icon-{size}.png")

for s in [192, 512]:
    gen_icon(s)
print("✓ icons generated")
```

**验证**:在 Windows 资源管理器看图,512×512 像素清晰。

## 步骤 2 · 创建 manifest.json

**文件**:`static/manifest.json`

**完整内容**:
```json
{
  "name": "泰玄小站 · 8 派命理解读",
  "short_name": "泰玄",
  "description": "8 派传统命理:八字 / 紫微 / 奇门 / 六爻 / 梅花 / 塔罗 / 西占 / 吠陀",
  "start_url": "/",
  "scope": "/",
  "display": "standalone",
  "orientation": "portrait",
  "background_color": "#1a1a1a",
  "theme_color": "#d4af37",
  "lang": "zh-CN",
  "icons": [
    {"src": "/static/icons/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
    {"src": "/static/icons/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any"},
    {"src": "/static/icons/icon-maskable-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"}
  ],
  "categories": ["lifestyle", "books"],
  "screenshots": [
    {"src": "/static/icons/screenshot-1.png", "sizes": "1280x720", "type": "image/png"}
  ]
}
```

**验证**:`python -c "import json; json.load(open('static/manifest.json'))"` 不报错。

## 步骤 3 · 创建 sw.js

**文件**:`static/sw.js`(详细)

**完整内容**:
```javascript
// taixuan-web Service Worker · v1
const VERSION = 'taixuan-sw-v1';
const STATIC_CACHE = `static-${VERSION}`;
const DYNAMIC_CACHE = `dynamic-${VERSION}`;
const STATIC_ASSETS = [
  '/',
  '/static/css/main.css',
  '/static/js/stream.js',
  '/static/js/i18n.js',
  '/static/manifest.json',
];

// 安装:预缓存静态资源
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(STATIC_CACHE).then(cache => cache.addAll(STATIC_ASSETS))
      .then(() => self.skipWaiting())
  );
});

// 激活:清旧版本缓存
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys => Promise.all(
      keys.filter(k => k !== STATIC_CACHE && k !== DYNAMIC_CACHE)
          .map(k => caches.delete(k))
    )).then(() => self.clients.claim())
  );
});

// fetch 策略
self.addEventListener('fetch', event => {
  const req = event.request;
  const url = new URL(req.url);
  if (req.method !== 'GET') return;

  // API GET → network first,fallback cache
  if (url.pathname.startsWith('/api/')) {
    event.respondWith(networkFirst(req, DYNAMIC_CACHE));
    return;
  }
  // HTML page → network first,fallback cache
  if (req.headers.get('accept').includes('text/html')) {
    event.respondWith(networkFirst(req, DYNAMIC_CACHE));
    return;
  }
  // 静态资源 → cache first
  event.respondWith(cacheFirst(req, STATIC_CACHE));
});

async function networkFirst(req, cacheName) {
  try {
    const resp = await fetch(req);
    if (resp.ok) {
      const cache = await caches.open(cacheName);
      cache.put(req, resp.clone());
    }
    return resp;
  } catch (e) {
    const cached = await caches.match(req);
    return cached || new Response('Offline', { status: 503 });
  }
}

async function cacheFirst(req, cacheName) {
  const cached = await caches.match(req);
  if (cached) return cached;
  try {
    const resp = await fetch(req);
    if (resp.ok) {
      const cache = await caches.open(cacheName);
      cache.put(req, resp.clone());
    }
    return resp;
  } catch (e) {
    return new Response('Not found', { status: 404 });
  }
}
```

**验证**:打开 Chrome DevTools → Application → Service Workers,看到 sw.js active。

## 步骤 4 · base.html 嵌入

**文件**:`templates/base.html`(已存在,可能需要创建)

**在 `<head>` 中插入**:
```html
<link rel="manifest" href="/static/manifest.json">
<meta name="theme-color" content="#d4af37">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="泰玄">
<link rel="apple-touch-icon" href="/static/icons/icon-192.png">

<script>
  if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
      navigator.serviceWorker.register('/static/sw.js')
        .then(reg => console.log('SW registered:', reg.scope))
        .catch(err => console.log('SW registration failed:', err));
    });
  }
</script>
```

**验证**:
```bash
curl http://127.0.0.1:80/static/sw.js | head -5
curl http://127.0.0.1:80/static/manifest.json | python -m json.tool | head -10
```

## 步骤 5 · 部署到 ECS

**步骤 5.1 · Windows PowerShell 分批 scp**:
```powershell
$env:PATH = "$env:PATH;C:\Windows\System32\OpenSSH"
$ECS = "116.62.69.83"

# 图标(2-3 个)
scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null `
  'C:\Users\Administrator\cow\fortune-web-v2\static\icons\icon-192.png' `
  "root@${ECS}:/var/www/taixuan/static/icons/"

scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null `
  'C:\Users\Administrator\cow\fortune-web-v2\static\icons\icon-512.png' `
  "root@${ECS}:/var/www/taixuan/static/icons/"

# manifest
scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null `
  'C:\Users\Administrator\cow\fortune-web-v2\static\manifest.json' `
  "root@${ECS}:/var/www/taixuan/static/manifest.json"

# sw.js
scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null `
  'C:\Users\Administrator\cow\fortune-web-v2\static\sw.js' `
  "root@${ECS}:/var/www/taixuan/static/sw.js"

# base.html
scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null `
  'C:\Users\Administrator\cow\fortune-web-v2\templates\base.html' `
  "root@${ECS}:/var/www/taixuan/templates/base.html"
```

**步骤 5.2 · Workbench 重启**:
```bash
sudo supervisorctl restart taixuan
sleep 4
curl -s http://127.0.0.1:80/healthz
echo ""
curl -s http://127.0.0.1:80/static/sw.js | head -3
echo ""
```

## 步骤 6 · 浏览器实测

**步骤 6.1 · Chrome DevTools 检查 PWA**:
1. 打开 http://116.62.69.83
2. F12 → Application 标签
3. Manifest:看到 name/icons/theme_color
4. Service Workers:看到 sw.js activated
5. 顶部出现 "Install app" 按钮

**步骤 6.2 · 安装测试**:
1. 点 "Install" → 安装成功
2. 关浏览器
3. 点桌面 "泰玄" 图标 → 全屏打开,主题色金色

**步骤 6.3 · 离线测试**:
1. F12 → Network → 切到 Offline
2. 刷新 → 首页还能看到(SW 缓存)
3. /api/v2/history → 看 SW 缓存的历史(可能空)

**步骤 6.4 · Lighthouse**:
1. F12 → Lighthouse
2. 选 PWA + Performance
3. Run → 期望 PWA 评分 ≥ 90

## 成功标准 Checklist

- [ ] 3 个 PNG 图标生成
- [ ] manifest.json 创建
- [ ] sw.js 创建
- [ ] base.html 嵌入 manifest + SW 注册
- [ ] ECS 部署 + supervisor restart
- [ ] Chrome 显示 "Install" 按钮
- [ ] 安装成功,桌面图标出现
- [ ] 离线打开能看到首页
- [ ] Lighthouse PWA ≥ 90

## 不做(明确划线)

- [ ] Push Notifications(暂不实现)
- [ ] Background Sync(单机无意义)
- [ ] 完整 IndexedDB(用 cache API 够)

## 总工时

- 图标生成:30 min
- manifest + sw.js:1h
- base.html:30 min
- 部署 + 验证:1h
- **总计:~3h**

---

_实施清单 · 触发条件:有真实用户后启动 · 2026-07-13 01:50 整理_