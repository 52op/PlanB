/**
 * Blog Theme Utilities
 * - Dark/Light mode toggle
 * - Back to top button
 */

(function() {
    'use strict';

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
        });
        
        backToTop.addEventListener('click', scrollToTop);
        
        // Initial check
        updateBackToTopVisibility();
    }

    // ==================== Code Copy Button ====================
    function initCodeCopyButtons() {
        // Find all pre > code blocks
        const codeBlocks = document.querySelectorAll('pre');
        
        codeBlocks.forEach(function(pre) {
            // Skip if already has copy button
            if (pre.querySelector('.code-copy-btn')) return;
            
            // Create wrapper if not exists
            if (!pre.parentElement.classList.contains('code-block-wrapper')) {
                const wrapper = document.createElement('div');
                wrapper.className = 'code-block-wrapper';
                pre.parentNode.insertBefore(wrapper, pre);
                wrapper.appendChild(pre);
            }
            
            // Create copy button
            const copyBtn = document.createElement('button');
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
            
            // Insert button
            pre.parentElement.insertBefore(copyBtn, pre);
        });
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
            initCodeCopyButtons();
            initThemeSwitcher();
        });
    } else {
        initTheme();
        initBackToTop();
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
