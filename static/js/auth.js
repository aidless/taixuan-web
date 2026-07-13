/**
 * taixuan-web v2.0 auth helpers
 * Token storage in localStorage (JWT pattern)
 */
(function (global) {
    'use strict';

    const TOKEN_KEY = 'taixuan_token';
    const USER_ID_KEY = 'taixuan_user_id';
    const NICKNAME_KEY = 'taixuan_nickname';

    function setToken(token, userId, nickname) {
        localStorage.setItem(TOKEN_KEY, token);
        if (userId !== undefined) localStorage.setItem(USER_ID_KEY, String(userId));
        if (nickname !== undefined) localStorage.setItem(NICKNAME_KEY, nickname);
    }

    function getToken() {
        return localStorage.getItem(TOKEN_KEY);
    }

    function getUserId() {
        const v = localStorage.getItem(USER_ID_KEY);
        return v ? parseInt(v, 10) : null;
    }

    function getNickname() {
        return localStorage.getItem(NICKNAME_KEY) || '';
    }

    function clear() {
        localStorage.removeItem(TOKEN_KEY);
        localStorage.removeItem(USER_ID_KEY);
        localStorage.removeItem(NICKNAME_KEY);
    }

    function isLoggedIn() {
        return !!getToken();
    }

    /**
     * fetch wrapper that auto-includes Authorization header if token present.
     * Usage: TaixuanAuth.fetch('/api/v2/auth/me')
     */
    async function authFetch(url, options = {}) {
        const token = getToken();
        const headers = Object.assign({}, options.headers || {});
        if (token) {
            headers['Authorization'] = 'Bearer ' + token;
        }
        return fetch(url, Object.assign({}, options, { headers: headers }));
    }

    global.TaixuanAuth = {
        setToken: setToken,
        getToken: getToken,
        getUserId: getUserId,
        getNickname: getNickname,
        clear: clear,
        isLoggedIn: isLoggedIn,
        fetch: authFetch,
    };
})(window);