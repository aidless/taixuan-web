# RFC-003 · taixuan-web PWA 支持

**状态**:📋 草案
**作者**:刘泽文
**日期**:2026-07-13

## 一、目标

把 taixuan-web 升级为**渐进式 Web 应用(PWA)**:
- ✅ 桌面 / 移动浏览器都能"安装"到桌面
- ✅ 离线时仍能浏览最近解读历史
- ✅ 类 App 体验(全屏 / 主题色 / 启动画面)

**价值**:
- 移动端用户留存提升(已发现用户多在手机访问)
- 类 App 体验让用户感知"这是产品不是网页"
- 不占 App Store 审核

## 二、技术方案(最小化)

### 文件清单(3 个新文件 + 2 个 HTML 改)

```
static/
├── manifest.json         # 🆕 Web App 清单
├── sw.js                 # 🆕 Service Worker(简化版)
└── icons/                # 🆕 192x192 + 512x512 PNG
templates/
├── base.html             # 加 <link rel="manifest"> + SW 注册
└── index.html            # 加 ios-app-capable meta
```

### manifest.json 关键字段

```json
{
  "name": "泰玄小站",
  "short_name": "泰玄",
  "start_url": "/",
  "display": "standalone",
  "background_color": "#1a1a1a",
  "theme_color": "#d4af37",
  "icons": [
    {"src": "/static/icons/icon-192.png", "sizes": "192x192", "type": "image/png"},
    {"src": "/static/icons/icon-512.png", "sizes": "512x512", "type": "image/png"}
  ]
}
```

### sw.js 简化(只缓存静态资源 + 最近 N 条历史)

```javascript
const VERSION = 'v1';
const STATIC_CACHE = `taixuan-static-${VERSION}`;
const DYNAMIC_CACHE = `taixuan-dynamic-${VERSION}`;

self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(STATIC_CACHE).then(c => c.addAll([
      '/', '/static/css/main.css', '/static/js/stream.js'
    ]))
  );
});

self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);
  // /api/v2/history GET 才缓存
  if (e.request.method === 'GET' && url.pathname.startsWith('/api/')) {
    e.respondWith(networkFirst(e.request, DYNAMIC_CACHE));
  } else {
    e.respondWith(cacheFirst(e.request, STATIC_CACHE));
  }
});
```

### base.html 嵌入(2 行)

```html
<link rel="manifest" href="/static/manifest.json">
<meta name="theme-color" content="#d4af37">
<script>
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/static/sw.js');
  }
</script>
```

## 三、不做(明确划线)

| 不做 | 原因 |
|---|---|
| 完整 Push Notifications | 价值低 + 后端要 Web Push 服务 |
| Background Sync | 单机 SQLite,后台同步无意义 |
| IndexedDB 完整存储 | 用 cache API + 服务端 SQLite 够了 |
| 原生 App(PWA 包含) | PWA 是个"伪 App"够用 |
| 多页 Service Worker | 单 sw.js 维护简单 |

## 四、触发条件

| 触发 | 立即做 |
|---|---|
| 已经有真实用户访问数据(umami 上线后)| 启动实施 |
| 用户反馈"想加桌面"| 启动 |

未触发 → 不实施,等用户基数起来。

## 五、工时估计

| 任务 | 工作量 |
|---|---:|
| 写 manifest + 注册 | 30 min |
| 写 sw.js(离线缓存)| 1h |
| 生成图标(2 PNG)| 30 min |
| base.html / index.html 嵌入 | 30 min |
| 浏览器实测(Chrome DevTools → Application → PWA)| 30 min |
| **总计** | **~3h** |

## 六、成功标准

- Chrome 浏览器右上角出现"安装"按钮
- 安装后桌面出现图标
- 离线打开应用:首页 + 上次历史可见
- Lighthouse PWA 评分 > 90

---

_本 RFC 草案 · 触发条件驱动 · 2026-07-13 01:25 整理_