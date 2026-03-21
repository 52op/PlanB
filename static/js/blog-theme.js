/**
 * Blog Theme Utilities
 * - Dark/Light mode toggle
 * - Back to top button
 */

(function() {
    'use strict';

    const ARTICLE_CONTENT_SELECTORS = [
        '.article-content',
        '.article-body',
        '.article-shell .article-body',
        '.article-container .article-content',
        'article .article-content',
        'article .article-body'
    ];

    const LANGUAGE_LABELS = {
        js: 'JavaScript',
        javascript: 'JavaScript',
        jsx: 'JSX',
        ts: 'TypeScript',
        typescript: 'TypeScript',
        tsx: 'TSX',
        py: 'Python',
        python: 'Python',
        sh: 'Bash',
        shell: 'Bash',
        bash: 'Bash',
        zsh: 'Zsh',
        ps1: 'PowerShell',
        powershell: 'PowerShell',
        html: 'HTML',
        xml: 'XML',
        css: 'CSS',
        scss: 'SCSS',
        sass: 'Sass',
        less: 'Less',
        json: 'JSON',
        yaml: 'YAML',
        yml: 'YAML',
        md: 'Markdown',
        markdown: 'Markdown',
        sql: 'SQL',
        go: 'Go',
        java: 'Java',
        kotlin: 'Kotlin',
        swift: 'Swift',
        php: 'PHP',
        ruby: 'Ruby',
        rust: 'Rust',
        rs: 'Rust',
        c: 'C',
        cpp: 'C++',
        cxx: 'C++',
        cc: 'C++',
        cs: 'C#',
        csharp: 'C#',
        vue: 'Vue',
        dockerfile: 'Dockerfile',
        ini: 'INI',
        toml: 'TOML',
        plaintext: 'Text',
        text: 'Text',
        txt: 'Text'
    };

    // ==================== Theme Toggle ====================
    const THEME_KEY = 'blog-theme-mode';
    
    function getTheme() {
        return localStorage.getItem(THEME_KEY) || 'light';
    }
    
    function setTheme(theme) {
        localStorage.setItem(THEME_KEY, theme);
        document.documentElement.setAttribute('data-theme', theme);
        updateThemeIcon(theme);
    }
    
    function toggleTheme() {
        const currentTheme = getTheme();
        const newTheme = currentTheme === 'light' ? 'dark' : 'light';
        setTheme(newTheme);
    }
    
    function updateThemeIcon(theme) {
        const themeToggle = document.getElementById('themeToggle');
        if (!themeToggle) return;
        
        const iconSun = themeToggle.querySelector('.icon-sun');
        const iconMoon = themeToggle.querySelector('.icon-moon');
        
        if (theme === 'dark') {
            if (iconSun) iconSun.style.display = 'block';
            if (iconMoon) iconMoon.style.display = 'none';
        } else {
            if (iconSun) iconSun.style.display = 'none';
            if (iconMoon) iconMoon.style.display = 'block';
        }
    }
    
    // Initialize theme on page load
    function initTheme() {
        const savedTheme = getTheme();
        setTheme(savedTheme);
        
        // Add click handler to theme toggle button
        const themeToggle = document.getElementById('themeToggle');
        if (themeToggle) {
            themeToggle.addEventListener('click', toggleTheme);
        }
    }

    // ==================== Back to Top ====================
    function initBackToTop() {
        const backToTop = document.getElementById('backToTop');
        if (!backToTop) return;
        
        // Show/hide button based on scroll position
        function updateBackToTopVisibility() {
            if (window.pageYOffset > 300) {
                backToTop.classList.add('visible');
            } else {
                backToTop.classList.remove('visible');
            }
        }
        
        // Smooth scroll to top
        function scrollToTop() {
            window.scrollTo({
                top: 0,
                behavior: 'smooth'
            });
        }
        
        // Throttle scroll event for better performance
        let ticking = false;
        window.addEventListener('scroll', function() {
            if (!ticking) {
                window.requestAnimationFrame(function() {
                    updateBackToTopVisibility();
                    ticking = false;
                });
                ticking = true;
            }
        }, { passive: true });
        
        backToTop.addEventListener('click', scrollToTop);
        
        // Initial check
        updateBackToTopVisibility();
    }

    // ==================== Reading Progress ====================
    function initReadingProgress() {
        const article = findPrimaryArticleElement();
        if (!article) return;

        const articleText = article.textContent ? article.textContent.trim() : '';
        if (articleText.length < 180) return;

        let progress = document.querySelector('.reading-progress');
        if (!progress) {
            progress = document.createElement('div');
            progress.className = 'reading-progress';
            progress.innerHTML = '<span class="reading-progress-bar"></span>';
            document.body.appendChild(progress);
        }

        const bar = progress.querySelector('.reading-progress-bar');
        if (!bar) return;

        function updateReadingProgress() {
            const scrollTop = window.pageYOffset || document.documentElement.scrollTop || 0;
            const viewportHeight = window.innerHeight || document.documentElement.clientHeight || 0;
            const rect = article.getBoundingClientRect();
            const articleTop = scrollTop + rect.top;
            const articleHeight = Math.max(article.scrollHeight, article.offsetHeight, rect.height);
            const start = articleTop - Math.max(72, viewportHeight * 0.16);
            const end = articleTop + articleHeight - Math.max(180, viewportHeight * 0.38);
            const range = Math.max(end - start, 1);
            const progressValue = Math.min(1, Math.max(0, (scrollTop - start) / range));

            bar.style.width = (progressValue * 100).toFixed(2) + '%';
            progress.classList.toggle('is-visible', articleHeight > viewportHeight * 0.35);
        }

        let ticking = false;
        function requestUpdate() {
            if (ticking) return;
            ticking = true;
            window.requestAnimationFrame(function() {
                updateReadingProgress();
                ticking = false;
            });
        }

        window.addEventListener('scroll', requestUpdate, { passive: true });
        window.addEventListener('resize', requestUpdate, { passive: true });
        updateReadingProgress();
    }

    // ==================== Code Copy Button ====================
    function initCodeCopyButtons() {
        // Find all pre > code blocks
        const codeBlocks = document.querySelectorAll('pre');
        
        codeBlocks.forEach(function(pre) {
            const wrapper = ensureCodeBlockWrapper(pre);
            if (!wrapper || wrapper.dataset.codeEnhanced === 'true') return;

            const languageLabel = detectCodeLanguage(pre);

            wrapper.classList.add('has-code-toolbar');
            pre.classList.add('has-code-toolbar');
            if (languageLabel) {
                wrapper.dataset.codeLanguage = languageLabel;
            }

            const toolbar = document.createElement('div');
            toolbar.className = 'code-toolbar';

            if (languageLabel) {
                const badge = document.createElement('span');
                badge.className = 'code-language-badge';
                badge.textContent = languageLabel;
                badge.title = '代码语言: ' + languageLabel;
                toolbar.appendChild(badge);
            }

            // Create copy button
            const copyBtn = document.createElement('button');
            copyBtn.type = 'button';
            copyBtn.className = 'code-copy-btn';
            copyBtn.innerHTML = `
                <svg class="copy-icon" width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"></path>
                </svg>
                <svg class="check-icon" width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24" style="display: none;">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path>
                </svg>
                <span class="copy-text">复制</span>
            `;
            copyBtn.title = '复制代码';
            
            // Add click handler
            copyBtn.addEventListener('click', function() {
                const code = pre.querySelector('code') || pre;
                const text = code.textContent;
                
                // Copy to clipboard
                if (navigator.clipboard && navigator.clipboard.writeText) {
                    navigator.clipboard.writeText(text).then(function() {
                        showCopySuccess(copyBtn);
                    }).catch(function() {
                        fallbackCopy(text, copyBtn);
                    });
                } else {
                    fallbackCopy(text, copyBtn);
                }
            });
            
            toolbar.appendChild(copyBtn);
            wrapper.insertBefore(toolbar, pre);
            wrapper.dataset.codeEnhanced = 'true';
        });
    }

    function ensureCodeBlockWrapper(pre) {
        if (!pre || !pre.parentNode) return null;

        if (pre.parentElement && pre.parentElement.classList.contains('code-block-wrapper')) {
            return pre.parentElement;
        }

        const wrapper = document.createElement('div');
        wrapper.className = 'code-block-wrapper';
        pre.parentNode.insertBefore(wrapper, pre);
        wrapper.appendChild(pre);
        return wrapper;
    }

    function detectCodeLanguage(pre) {
        const code = pre.querySelector('code');
        const sources = [];

        if (pre.dataset.language) {
            sources.push(pre.dataset.language);
        }
        if (pre.getAttribute('data-language')) {
            sources.push(pre.getAttribute('data-language'));
        }
        if (code && code.dataset.language) {
            sources.push(code.dataset.language);
        }
        if (code && code.getAttribute('data-language')) {
            sources.push(code.getAttribute('data-language'));
        }
        if (code && code.className) {
            sources.push(code.className);
        }
        if (pre.className) {
            sources.push(pre.className);
        }

        for (let i = 0; i < sources.length; i += 1) {
            const token = extractLanguageToken(sources[i]);
            if (token) {
                return toLanguageLabel(token);
            }
        }

        return '';
    }

    function extractLanguageToken(value) {
        if (!value) return '';

        const source = String(value).trim();
        if (!source) return '';

        const matched = source.match(/\b(?:language|lang)-([a-z0-9_+#.-]+)/i);
        if (matched && matched[1]) {
            return matched[1].toLowerCase();
        }

        const normalized = source.toLowerCase().replace(/[^a-z0-9+#.-]+/g, ' ').trim().split(/\s+/);
        for (let i = 0; i < normalized.length; i += 1) {
            if (LANGUAGE_LABELS[normalized[i]]) {
                return normalized[i];
            }
        }

        if (normalized.length === 1) {
            return normalized[0];
        }

        return '';
    }

    function toLanguageLabel(token) {
        if (!token) return '';
        if (LANGUAGE_LABELS[token]) {
            return LANGUAGE_LABELS[token];
        }

        if (token.length <= 4) {
            return token.toUpperCase();
        }

        return token.charAt(0).toUpperCase() + token.slice(1);
    }

    function findPrimaryArticleElement() {
        for (let i = 0; i < ARTICLE_CONTENT_SELECTORS.length; i += 1) {
            const element = document.querySelector(ARTICLE_CONTENT_SELECTORS[i]);
            if (element && element.textContent && element.textContent.trim()) {
                return element;
            }
        }

        return null;
    }
    
    function showCopySuccess(button) {
        const copyIcon = button.querySelector('.copy-icon');
        const checkIcon = button.querySelector('.check-icon');
        const copyText = button.querySelector('.copy-text');
        
        // Show success state
        copyIcon.style.display = 'none';
        checkIcon.style.display = 'block';
        copyText.textContent = '已复制';
        button.classList.add('copied');
        
        // Reset after 2 seconds
        setTimeout(function() {
            copyIcon.style.display = 'block';
            checkIcon.style.display = 'none';
            copyText.textContent = '复制';
            button.classList.remove('copied');
        }, 2000);
    }
    
    function fallbackCopy(text, button) {
        // Fallback for older browsers
        const textarea = document.createElement('textarea');
        textarea.value = text;
        textarea.style.position = 'fixed';
        textarea.style.opacity = '0';
        document.body.appendChild(textarea);
        textarea.select();
        
        try {
            document.execCommand('copy');
            showCopySuccess(button);
        } catch (err) {
            console.error('Failed to copy:', err);
            const copyText = button.querySelector('.copy-text');
            copyText.textContent = '复制失败';
            setTimeout(function() {
                copyText.textContent = '复制';
            }, 2000);
        }
        
        document.body.removeChild(textarea);
    }

    // ==================== Initialize ====================
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function() {
            initTheme();
            initBackToTop();
            initReadingProgress();
            initCodeCopyButtons();
            initThemeSwitcher();
        });
    } else {
        initTheme();
        initBackToTop();
        initReadingProgress();
        initCodeCopyButtons();
        initThemeSwitcher();
    }
    
    // ==================== Theme Switcher ====================
    function initThemeSwitcher() {
        const switcher = document.getElementById('themeSwitcher');
        const options = document.getElementById('themeOptions');
        
        if (!switcher || !options) return;
        
        // Toggle dropdown
        switcher.addEventListener('click', function(e) {
            e.stopPropagation();
            options.classList.toggle('show');
        });
        
        // Close dropdown when clicking outside
        document.addEventListener('click', function(e) {
            if (!e.target.closest('.theme-switcher')) {
                options.classList.remove('show');
            }
        });
        
        // Prevent dropdown from closing when clicking inside
        options.addEventListener('click', function(e) {
            e.stopPropagation();
        });
    }
    
    // Export for global access
    window.initThemeSwitcher = initThemeSwitcher;
})();
