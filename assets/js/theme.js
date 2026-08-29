(() => {
  const storageKey = 'monkey-patch-theme';
  const media = window.matchMedia('(prefers-color-scheme: dark)');

  const readSavedTheme = () => {
    try {
      const value = window.localStorage.getItem(storageKey);
      return value === 'light' || value === 'dark' ? value : null;
    } catch {
      return null;
    }
  };

  const saveTheme = (theme) => {
    try {
      window.localStorage.setItem(storageKey, theme);
    } catch {
      // 저장소를 사용할 수 없는 환경에서도 현재 페이지의 전환은 유지합니다.
    }
  };

  const preferredTheme = () => readSavedTheme() ?? (media.matches ? 'dark' : 'light');

  const applyTheme = (theme) => {
    const isDark = theme === 'dark';
    document.documentElement.dataset.theme = theme;
    document.documentElement.style.colorScheme = theme;

    const toggle = document.querySelector('#theme-toggle');
    if (toggle) {
      toggle.setAttribute('aria-pressed', String(isDark));
      toggle.setAttribute('aria-label', isDark ? '라이트 모드로 전환' : '다크 모드로 전환');
      toggle.querySelector('.theme-icon').textContent = isDark ? '☀' : '☾';
      toggle.querySelector('.theme-label').textContent = isDark ? 'light' : 'dark';
    }

    const themeColor = document.querySelector('meta[name="theme-color"]');
    themeColor?.setAttribute('content', isDark ? '#161815' : '#f7f4ea');
  };

  applyTheme(preferredTheme());

  document.addEventListener('DOMContentLoaded', () => {
    applyTheme(preferredTheme());

    document.querySelector('#theme-toggle')?.addEventListener('click', () => {
      const nextTheme = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
      saveTheme(nextTheme);
      applyTheme(nextTheme);
    });
  });

  media.addEventListener?.('change', (event) => {
    if (!readSavedTheme()) applyTheme(event.matches ? 'dark' : 'light');
  });

  window.addEventListener('storage', (event) => {
    if (event.key === storageKey) applyTheme(preferredTheme());
  });
})();
