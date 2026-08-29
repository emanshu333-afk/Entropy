// UTF-8
// Cookie banner — appears on home (/) every visit until Accept
(function() {
    const banner = document.getElementById('cookie-banner');
    const acceptBtn = document.querySelector('[data-cookie-accept]');
    const laterBtn = document.querySelector('[data-cookie-later]');
    if (!banner) return;
    // Only on home screen
    const isHome = window.location.pathname === '/' || window.location.pathname === '';
    if (!isHome) return;
    const accepted = localStorage.getItem('bunkloop_cookie_accepted') === '1';
    if (accepted) return;
    // Show banner
    banner.hidden = false;
    function hide() { banner.hidden = true; }
    if (acceptBtn) acceptBtn.addEventListener('click', () => {
        localStorage.setItem('bunkloop_cookie_accepted', '1');
        // Also set a cookie for server-side if needed (1 year)
        document.cookie = 'bunkloop_cookie_accepted=1; path=/; max-age=31536000; SameSite=Lax';
        hide();
    });
    if (laterBtn) laterBtn.addEventListener('click', () => {
        // Ask me later — just hide for now, will reappear on next home visit (no persistent flag)
        hide();
        sessionStorage.setItem('bunkloop_cookie_later', Date.now().toString());
    });
})();
