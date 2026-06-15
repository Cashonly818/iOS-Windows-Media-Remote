/**
 * Service Worker - PWA 离线缓存
 * 缓存静态资源，提供离线访问能力
 */

const CACHE_NAME = 'pc-remote-v1';

const PRE_CACHE = [
    '/',
    '/static/css/style.css',
    '/static/js/app.js',
    '/manifest.json',
];

// 安装事件 - 预缓存静态资源
self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => {
            console.log('[SW] Caching static assets');
            return cache.addAll(PRE_CACHE);
        }).then(() => {
            return self.skipWaiting();
        })
    );
});

// 激活事件 - 清理旧缓存
self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((keys) => {
            return Promise.all(
                keys.filter(key => key !== CACHE_NAME)
                    .map(key => caches.delete(key))
            );
        }).then(() => {
            return self.clients.claim();
        })
    );
});

// 请求拦截 - 缓存优先策略 (静态资源) / 网络优先 (API)
self.addEventListener('fetch', (event) => {
    const url = new URL(event.request.url);

    // API 请求走网络 (不缓存)
    if (url.pathname.startsWith('/api/') || url.pathname === '/ws') {
        return;  // 交给浏览器默认处理
    }

    // 静态资源 - 缓存优先，网络兜底
    event.respondWith(
        caches.match(event.request).then((cached) => {
            if (cached) {
                // 后台更新缓存
                fetch(event.request).then(resp => {
                    if (resp.ok) {
                        caches.open(CACHE_NAME).then(cache => {
                            cache.put(event.request, resp);
                        });
                    }
                }).catch(() => {});
                return cached;
            }
            // 网络请求
            return fetch(event.request).then(resp => {
                if (!resp || resp.status !== 200) return resp;
                const clone = resp.clone();
                caches.open(CACHE_NAME).then(cache => {
                    cache.put(event.request, clone);
                });
                return resp;
            }).catch(() => {
                // 离线时返回一个简单的离线页面 (HTML 请求)
                if (event.request.headers.get('accept')?.includes('text/html')) {
                    return caches.match('/');
                }
            });
        })
    );
});
