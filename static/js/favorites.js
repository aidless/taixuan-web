/**
 * taixuan-web v2.0 favorite button helper.
 * Usage:
 *   TaixuanFav.mount(container, readingId, onUpdate?)
 *     - container: DOM element where button will be rendered
 *     - readingId: int from reading/reading_stream response
 *     - onUpdate: optional callback (state) => void
 *
 * States: 'hidden' (not logged in), 'idle' (logged in, can favorite), 'favorited', 'error'
 */
(function (global) {
    'use strict';

    function isLoggedIn() {
        return typeof TaixuanAuth !== 'undefined' && TaixuanAuth.isLoggedIn();
    }

    function getToken() {
        return typeof TaixuanAuth !== 'undefined' ? TaixuanAuth.getToken() : null;
    }

    function render(container, state, readingId) {
        container.innerHTML = '';
        container.classList.remove('hidden');

        if (!isLoggedIn()) {
            // Not logged in: hide completely (or show "login to favorite")
            const msg = document.createElement('span');
            msg.className = 'fav-msg';
            msg.innerHTML = '<a href="/login">登录</a>后可收藏';
            container.appendChild(msg);
            return;
        }

        if (state === 'favorited') {
            const btn = document.createElement('button');
            btn.className = 'fav-btn fav-done';
            btn.disabled = true;
            btn.textContent = '\u2605 已收藏';
            container.appendChild(btn);
            return;
        }

        if (state === 'error') {
            const btn = document.createElement('button');
            btn.className = 'fav-btn';
            btn.textContent = '\u2606 重试收藏';
            btn.onclick = () => doFavorite(container, readingId);
            container.appendChild(btn);
            return;
        }

        // idle
        const btn = document.createElement('button');
        btn.className = 'fav-btn';
        btn.textContent = '\u2606 收藏';
        btn.onclick = () => doFavorite(container, readingId);
        container.appendChild(btn);
    }

    async function doFavorite(container, readingId) {
        if (!readingId) {
            console.warn('No reading_id, cannot favorite');
            return;
        }
        const token = getToken();
        if (!token) {
            window.location.href = '/login';
            return;
        }
        try {
            const resp = await fetch('/api/v2/favorites', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': 'Bearer ' + token,
                },
                body: JSON.stringify({ reading_id: readingId }),
            });
            if (resp.status === 401) {
                // Token expired
                if (typeof TaixuanAuth !== 'undefined') TaixuanAuth.clear();
                window.location.href = '/login';
                return;
            }
            if (!resp.ok) {
                const err = await resp.json().catch(() => ({}));
                console.warn('favorite failed:', err);
                render(container, 'error', readingId);
                return;
            }
            render(container, 'favorited', readingId);
        } catch (err) {
            console.error('favorite error:', err);
            render(container, 'error', readingId);
        }
    }

    function mount(container, readingId) {
        if (!container) return;
        render(container, isLoggedIn() ? 'idle' : 'hidden', readingId);
    }

    global.TaixuanFav = { mount: mount, render: render };
})(window);